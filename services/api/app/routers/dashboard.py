"""KPI del dashboard y analitica descriptiva (Fase 4)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Alert, DataSource, SeismicEvent
from app.schemas import DashboardSummary, HistogramBin, QualitySummary, RegionCount, TimeseriesPoint
from app.routers.events import apply_event_filters
from app.security import require

router = APIRouter(prefix="/api/v1", tags=["dashboard"])

MAG_BINS = [(0, 3), (3, 4), (4, 5), (5, 6), (6, 7), (7, 10)]


def _aware(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


@router.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(
    db: Session = Depends(get_db),
    _: object = Depends(require("dashboard:read")),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
):
    now = datetime.now(timezone.utc)
    d24 = now - timedelta(hours=24)
    d7 = now - timedelta(days=7)

    total = db.scalar(select(func.count(SeismicEvent.id))) or 0
    last24 = db.scalar(select(func.count(SeismicEvent.id)).where(SeismicEvent.occurred_at >= d24)) or 0
    last7 = db.scalar(select(func.count(SeismicEvent.id)).where(SeismicEvent.occurred_at >= d7)) or 0
    max_mag = db.scalar(select(func.max(SeismicEvent.magnitude)).where(SeismicEvent.occurred_at >= d7))
    avg_depth = db.scalar(select(func.avg(SeismicEvent.depth_km)).where(SeismicEvent.occurred_at >= d7))

    depths = db.scalars(
        select(SeismicEvent.depth_km).where(SeismicEvent.occurred_at >= d7, SeismicEvent.depth_km.is_not(None))
    ).all()
    median_depth = sorted(depths)[len(depths) // 2] if depths else None

    last_sync = db.scalar(select(func.max(DataSource.last_sync_at)))
    active_alerts = db.scalar(
        select(func.count(Alert.id)).where(Alert.status.in_(["pending_approval", "approved", "sent"]))
    ) or 0
    sources = db.scalars(select(DataSource).order_by(DataSource.name)).all()

    stmt = select(func.count(SeismicEvent.id))
    stmt = apply_event_filters(stmt, date_from=date_from, date_to=date_to,
                               min_magnitude=None, max_magnitude=None,
                               source_id=None, bbox=None, place=None)
    filtered = db.scalar(stmt) or 0

    # Estadisticas del periodo seleccionado (7 dias por defecto): alimentan los
    # KPI con filtro de rango (ultimos 7 dias / 30 dias / 1 anio).
    period_from = _aware(date_from) or d7
    period_to = _aware(date_to) or now
    period_max = db.scalar(
        select(func.max(SeismicEvent.magnitude)).where(
            SeismicEvent.occurred_at >= period_from, SeismicEvent.occurred_at <= period_to
        )
    )
    period_avg_depth = db.scalar(
        select(func.avg(SeismicEvent.depth_km)).where(
            SeismicEvent.occurred_at >= period_from,
            SeismicEvent.occurred_at <= period_to,
            SeismicEvent.depth_km.is_not(None),
        )
    )

    return DashboardSummary(
        total_events=filtered,
        events_last_24h=last24,
        events_last_7d=last7,
        max_magnitude_7d=max_mag,
        avg_depth=round(float(avg_depth), 2) if avg_depth is not None else None,
        median_depth=median_depth,
        last_sync_at=_aware(last_sync),
        active_alerts=active_alerts,
        sources=sources,
        period_start=date_from,
        period_end=date_to,
        period_max_magnitude=period_max,
        period_avg_depth=round(float(period_avg_depth), 2) if period_avg_depth is not None else None,
    )


@router.get("/analytics/timeseries", response_model=list[TimeseriesPoint])
def analytics_timeseries(
    db: Session = Depends(get_db),
    _: object = Depends(require("analytics:read")),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    min_magnitude: float | None = Query(default=None, ge=0, le=10),
    granularity: str = Query(default="day", pattern="^(hour|day)$"),
):
    fmt = "%Y-%m-%dT%H:00" if granularity == "hour" else "%Y-%m-%d"
    if db.bind.dialect.name == "sqlite":
        col = func.strftime(fmt, SeismicEvent.occurred_at)
    else:
        pg_fmt = 'YYYY-MM-DD"T"HH24:00' if granularity == "hour" else "YYYY-MM-DD"
        col = func.to_char(SeismicEvent.occurred_at, pg_fmt)
    stmt = (
        select(col.label("bucket"), func.count(SeismicEvent.id).label("count"))
        .group_by("bucket")
        .order_by("bucket")
    )
    stmt = apply_event_filters(stmt, date_from=date_from, date_to=date_to,
                               min_magnitude=min_magnitude, max_magnitude=None,
                               source_id=None, bbox=None, place=None)
    return [TimeseriesPoint(bucket=r.bucket, count=r.count) for r in db.execute(stmt).all()]


@router.get("/analytics/magnitude-histogram", response_model=list[HistogramBin])
def magnitude_histogram(
    db: Session = Depends(get_db),
    _: object = Depends(require("analytics:read")),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
):
    rows = db.scalars(
        apply_event_filters(
            select(SeismicEvent.magnitude),
            date_from=date_from, date_to=date_to,
            min_magnitude=None, max_magnitude=None, source_id=None, bbox=None, place=None,
        ).where(SeismicEvent.magnitude.is_not(None))
    ).all()
    counts = [0] * len(MAG_BINS)
    for m in rows:
        for i, (lo, hi) in enumerate(MAG_BINS):
            if lo <= m < hi or (i == len(MAG_BINS) - 1 and m == hi):
                counts[i] += 1
                break
    return [
        HistogramBin(label=f"{lo}–{hi}", count=c)
        for (lo, hi), c in zip(MAG_BINS, counts, strict=True)
    ]


@router.get("/analytics/magnitude-depth")
def magnitude_depth(
    db: Session = Depends(get_db),
    _: object = Depends(require("analytics:read")),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    min_magnitude: float | None = Query(default=None, ge=0, le=10),
    limit: int = Query(default=1000, ge=1, le=5000),
):
    stmt = apply_event_filters(
        select(SeismicEvent.depth_km, SeismicEvent.magnitude, SeismicEvent.place),
        date_from=date_from, date_to=date_to, min_magnitude=min_magnitude,
        max_magnitude=None, source_id=None, bbox=None, place=None,
    ).where(SeismicEvent.depth_km.is_not(None), SeismicEvent.magnitude.is_not(None)).limit(limit)
    return [
        {"depth_km": d, "magnitude": m, "place": p}
        for d, m, p in db.execute(stmt).all()
    ]


@router.get("/analytics/regions", response_model=list[RegionCount])
def regions_count(
    db: Session = Depends(get_db),
    _: object = Depends(require("analytics:read")),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = Query(default=15, ge=1, le=100),
):
    stmt = apply_event_filters(
        select(SeismicEvent.region, func.count(SeismicEvent.id).label("count"))
        .group_by(SeismicEvent.region)
        .order_by(func.count(SeismicEvent.id).desc())
        .limit(limit),
        date_from=date_from, date_to=date_to, min_magnitude=None,
        max_magnitude=None, source_id=None, bbox=None, place=None,
    )
    return [RegionCount(region=r.region or "Sin region", count=r.count) for r in db.execute(stmt).all()]


@router.get("/analytics/quality", response_model=QualitySummary)
def quality_summary(
    db: Session = Depends(get_db),
    _: object = Depends(require("analytics:read")),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
):
    base = apply_event_filters(
        select(SeismicEvent),
        date_from=date_from, date_to=date_to, min_magnitude=None,
        max_magnitude=None, source_id=None, bbox=None, place=None,
    )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    miss_mag = db.scalar(select(func.count()).select_from(
        base.where(SeismicEvent.magnitude.is_(None)).subquery())) or 0
    miss_depth = db.scalar(select(func.count()).select_from(
        base.where(SeismicEvent.depth_km.is_(None)).subquery())) or 0
    dup = db.scalar(
        select(func.count()).select_from(
            base.with_only_columns(SeismicEvent.external_id, SeismicEvent.source_id)
            .group_by(SeismicEvent.external_id, SeismicEvent.source_id)
            .having(func.count() > 1)
            .subquery()
        )
    ) or 0
    return QualitySummary(
        sample_size=total,
        missing_magnitude=miss_mag,
        missing_depth=miss_depth,
        duplicate_external_ids=dup,
        period_start=date_from,
        period_end=date_to,
    )
