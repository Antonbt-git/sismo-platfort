"""Catalogo de eventos sismicos, formato geografico y canal en vivo (Fase 3/4)."""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import SessionLocal, get_db
from app.models import DataSource, SeismicEvent, utcnow
from app.schemas import EventOut, EventPage, GeoJsonFeatureCollection
from app.security import require

router = APIRouter(prefix="/api/v1/events", tags=["eventos"])

# Cadencia del canal en vivo: consulta rapida a la BD + latido anti-timeout.
STREAM_POLL_SECONDS = 3.0
STREAM_HEARTBEAT_SECONDS = 15.0
STREAM_INITIAL_OVERLAP_SECONDS = 5.0


def apply_event_filters(
    stmt,
    *,
    date_from: datetime | None,
    date_to: datetime | None,
    min_magnitude: float | None,
    max_magnitude: float | None,
    source_id: uuid.UUID | None,
    bbox: list[float] | None,
    place: str | None,
):
    if date_from:
        stmt = stmt.where(SeismicEvent.occurred_at >= date_from)
    if date_to:
        stmt = stmt.where(SeismicEvent.occurred_at <= date_to)
    if min_magnitude is not None:
        stmt = stmt.where(SeismicEvent.magnitude >= min_magnitude)
    if max_magnitude is not None:
        stmt = stmt.where(SeismicEvent.magnitude <= max_magnitude)
    if source_id:
        stmt = stmt.where(SeismicEvent.source_id == source_id)
    if bbox and len(bbox) == 4:
        min_lon, min_lat, max_lon, max_lat = bbox
        stmt = stmt.where(
            SeismicEvent.longitude >= min_lon,
            SeismicEvent.longitude <= max_lon,
            SeismicEvent.latitude >= min_lat,
            SeismicEvent.latitude <= max_lat,
        )
    if place:
        stmt = stmt.where(SeismicEvent.place.ilike(f"%{place}%"))
    return stmt


@router.get("", response_model=EventPage)
def list_events(
    db: Session = Depends(get_db),
    _: object = Depends(require("events:read")),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    min_magnitude: float | None = Query(default=None, ge=0, le=10),
    max_magnitude: float | None = Query(default=None, ge=0, le=10),
    source_id: uuid.UUID | None = None,
    bbox: list[float] | None = Query(default=None),
    place: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
):
    base = apply_event_filters(
        select(SeismicEvent),
        date_from=date_from, date_to=date_to, min_magnitude=min_magnitude,
        max_magnitude=max_magnitude, source_id=source_id, bbox=bbox, place=place,
    )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(
        base.order_by(SeismicEvent.occurred_at.desc()).offset(offset).limit(limit)
    ).all()
    return EventPage(total=total, offset=offset, limit=limit, items=rows)


# ---------- Canal en vivo (Server-Sent Events) ----------


def _as_utc(dt: datetime) -> datetime:
    """SQLite devuelve datetimes sin tz; normaliza a UTC para comparar cursor."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _fetch_events_after(cursor: datetime, limit: int = 200) -> list[SeismicEvent]:
    """Consulta corta con sesion propia: el stream no debe agotar el pool."""
    db = SessionLocal()
    try:
        return list(db.scalars(
            select(SeismicEvent)
            .where(SeismicEvent.received_at > cursor)
            .order_by(SeismicEvent.received_at.asc())
            .limit(limit)
        ).all())
    finally:
        db.close()


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"


async def _event_stream():
    """Emite los eventos que llegan a la BD, sin refrescar la pagina.

    El cursor avanza por `received_at`, de modo que funciona igual si los
    inserta el daemon de ingesta, una sincronizacion manual u otro proceso.
    Se parte de un solape corto para no perder los eventos que llegan justo
    al conectar; el cliente descarta los repetidos por id.
    """
    cursor = utcnow() - timedelta(seconds=STREAM_INITIAL_OVERLAP_SECONDS)
    yield "retry: 3000\n\n" + _sse({"type": "hello", "server_time": utcnow().isoformat()})
    loop = asyncio.get_running_loop()
    last_beat = loop.time()
    while True:
        try:
            rows = await asyncio.to_thread(_fetch_events_after, cursor)
        except Exception:  # noqa: BLE001 BD temporalmente caida: se reintenta
            rows = []
        if rows:
            cursor = max([cursor] + [_as_utc(r.received_at) for r in rows])
            yield _sse({
                "type": "events",
                "events": [EventOut.model_validate(r).model_dump(mode="json") for r in rows],
            })
        if loop.time() - last_beat >= STREAM_HEARTBEAT_SECONDS:
            last_beat = loop.time()
            yield ": ping\n\n"
        await asyncio.sleep(STREAM_POLL_SECONDS)


@router.get("/stream")
async def stream_live_events(_: object = Depends(require("events:read"))):
    """Canal SSE con los eventos observados que se reciben en vivo."""
    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/geojson", response_model=GeoJsonFeatureCollection)
def events_geojson(
    db: Session = Depends(get_db),
    _: object = Depends(require("events:read")),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    min_magnitude: float | None = Query(default=None, ge=0, le=10),
    max_magnitude: float | None = Query(default=None, ge=0, le=10),
    bbox: list[float] | None = Query(default=None),
    limit: int = Query(default=2000, ge=1, le=5000),
):
    stmt = apply_event_filters(
        select(SeismicEvent),
        date_from=date_from, date_to=date_to, min_magnitude=min_magnitude,
        max_magnitude=max_magnitude, source_id=None, bbox=bbox, place=None,
    ).order_by(SeismicEvent.occurred_at.desc()).limit(limit)

    features = []
    for e in db.scalars(stmt):
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [e.longitude, e.latitude]},
            "properties": {
                "id": str(e.id),
                "external_id": e.external_id,
                "magnitude": e.magnitude,
                "magnitude_type": e.magnitude_type,
                "depth_km": e.depth_km,
                "place": e.place,
                "occurred_at": e.occurred_at.isoformat(),
                "source_url": e.source_url,
            },
        })
    return GeoJsonFeatureCollection(features=features)


@router.get("/{event_id}", response_model=EventOut)
def get_event(
    event_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: object = Depends(require("events:read")),
):
    event = db.get(SeismicEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    return event


@router.get("/{event_id}/source-name")
def get_event_source_name(
    event_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: object = Depends(require("events:read")),
):
    event = db.get(SeismicEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    source = db.get(DataSource, event.source_id)
    return {"source_name": source.name if source else "desconocida"}
