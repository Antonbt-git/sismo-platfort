"""Sincronizacion incremental de fuentes de eventos (Fase 3).

Uso:
    python ingestion/sync.py                       # todas las fuentes habilitadas
    python ingestion/sync.py --source-id <uuid>    # fuente especifica
    python ingestion/sync.py --loop                # daemon (contenedor `ingesta`)

Garantiza idempotencia: la restriccion unica (external_id, source_id) + upsert evitan
duplicados al repetir la sincronizacion. Cada ejecucion queda registrada en ingestion_runs.
En modo daemon se relee el intervalo de configuracion en cada ciclo y se sincroniza
cada fuente habilitada, de modo que una fuente creada desde el modulo Fuentes de datos
empieza a actualizarse sola en la siguiente pasada.
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.alerts_engine import evaluate_event  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import DataSource, IngestionRun, SeismicEvent, utcnow  # noqa: E402
from app.runtime_config import ConfigError, get_value  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("ingestion")


def _config_value(db, key: str, fallback):
    """Valor operativo vigente (§6.13) con fallback al .env si la BD no lo tiene."""
    try:
        return get_value(db, key)
    except ConfigError:
        return fallback


def sync_source(source: DataSource, *, hours: int | None = None, min_magnitude: float | None = None) -> IngestionRun:
    from ingestion.igp import fetch_events

    settings = get_settings()
    db = SessionLocal()
    # Rehidratar la fuente en ESTA sesion para que sus actualizaciones se persistan.
    source = db.get(DataSource, source.id)
    if source is None:
        raise ValueError("Fuente no encontrada")
    run = IngestionRun(source_id=source.id, status="running")
    db.add(run)
    db.commit()
    db.refresh(run)
    started = time.monotonic()
    lookback_hours = _config_value(db, "ingesta_lookback_hours", settings.ingesta_lookback_hours)
    default_min_magnitude = _config_value(db, "ingesta_min_magnitude", settings.ingesta_min_magnitude)
    lookback = timedelta(hours=hours or int(lookback_hours))
    end = datetime.now(timezone.utc)
    start = end - lookback

    try:
        events = fetch_events(
            source.base_url,
            start=start,
            end=end,
            min_magnitude=min_magnitude if min_magnitude is not None else float(default_min_magnitude),
        )
        seen = inserted = updated = 0
        new_events: list[SeismicEvent] = []
        for e in events:
            seen += 1
            existing = db.scalar(
                select(SeismicEvent).where(
                    SeismicEvent.external_id == e.external_id,
                    SeismicEvent.source_id == source.id,
                )
            )
            if existing is not None:
                changed = False
                if e.magnitude is not None and existing.magnitude != e.magnitude:
                    existing.magnitude = e.magnitude
                    changed = True
                if e.depth_km is not None and existing.depth_km != e.depth_km:
                    existing.depth_km = e.depth_km
                    changed = True
                updated += 1 if changed else 0
                continue
            event = SeismicEvent(
                external_id=e.external_id,
                source_id=source.id,
                occurred_at=e.occurred_at,
                latitude=e.latitude,
                longitude=e.longitude,
                magnitude=e.magnitude,
                magnitude_type=e.magnitude_type,
                depth_km=e.depth_km,
                place=e.place,
                region=e.region,
                source_url=e.source_url,
            )
            db.add(event)
            new_events.append(event)
        db.flush()

        alertas = 0
        for event in new_events:
            alertas += len(evaluate_event(db, event))

        run.status = "success"
        run.records_seen = seen
        run.records_inserted = len(new_events)
        run.records_updated = updated
        source.status = "ok"
        source.last_success_at = utcnow()
        logger.info(
            "Sincronizacion ok: vistos=%s insertados=%s actualizados=%s alertas=%s",
            seen, len(new_events), updated, alertas,
        )
    except Exception as exc:  # noqa: BLE001
        run.status = "error"
        run.error_summary = f"{type(exc).__name__}: {exc}"[:2000]
        source.status = "error"
        logger.exception("Error en sincronizacion de %s", source.name)
    finally:
        run.finished_at = utcnow()
        source.last_sync_at = utcnow()
        source.last_latency_ms = int((time.monotonic() - started) * 1000)
        db.commit()
        db.refresh(run)
        db.close()
    return run


def resolve_sources(db, source_id: str | None) -> list[DataSource]:
    """Fuentes a sincronizar: una concreta (si se indico) o todas las habilitadas.

    Iterar todas hace que una fuente recien creada en el modulo Fuentes de datos
    empiece a actualizarse sola en el proximo ciclo, sin tocar el daemon.
    """
    if source_id:
        try:
            pk: uuid.UUID | str = uuid.UUID(str(source_id))
        except ValueError:
            logger.error("Identificador de fuente invalido: %r", source_id)
            return []
        source = db.get(DataSource, pk)
        return [source] if source is not None else []
    return list(db.scalars(
        select(DataSource).where(DataSource.enabled.is_(True)).order_by(DataSource.name)
    ))


def resolve_source(db, source_id: str | None) -> DataSource | None:
    sources = resolve_sources(db, source_id)
    return sources[0] if sources else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Sincronizacion de fuente sismica")
    parser.add_argument("--source-id", default=None)
    parser.add_argument("--hours", type=int, default=None)
    parser.add_argument("--min-magnitude", type=float, default=None)
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=int, default=None)
    args = parser.parse_args()

    settings = get_settings()

    def resolve_interval() -> int:
        if args.interval:
            return args.interval
        db = SessionLocal()
        try:
            return int(_config_value(db, "ingesta_interval_seconds", settings.ingesta_interval_seconds))
        finally:
            db.close()

    interval = resolve_interval()

    def run_once() -> None:
        db = SessionLocal()
        try:
            sources = resolve_sources(db, args.source_id)
        finally:
            db.close()
        if not sources:
            logger.error("Fuente no encontrada" if args.source_id else "Sin fuentes habilitadas")
            return
        for source in sources:
            if not source.enabled:
                logger.info("Fuente %s deshabilitada; se omite", source.name)
                continue
            try:
                sync_source(source, hours=args.hours, min_magnitude=args.min_magnitude)
            except Exception:  # noqa: BLE001 una fuente rota no detiene a las demas
                logger.exception("Fallo la sincronizacion de %s", source.name)

    if args.loop:
        logger.info("Modo daemon: %s fuente(s), intervalo inicial %ss",
                    "varias" if args.source_id is None else "1", interval)
        while True:
            run_once()
            # Se relee en cada ciclo para aplicar cambios de configuracion sin reiniciar.
            time.sleep(resolve_interval())
    else:
        run_once()


if __name__ == "__main__":
    main()
