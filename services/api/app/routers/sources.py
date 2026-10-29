"""Fuentes de datos e ingesta (Fase 3/10)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy import func, select, delete as sql_delete, update as sql_update
from sqlalchemy.orm import Session

from app.audit import log_action
from app.db import get_db
from app.models import Alert, DataSource, IngestionRun, SeismicEvent, User, utcnow
from app.schemas import DataSourceCreate, DataSourceOut, IngestionRunOut
from app.security import require

router = APIRouter(prefix="/api/v1/sources", tags=["fuentes"])


@router.get("", response_model=list[DataSourceOut])
def list_sources(
    db: Session = Depends(get_db),
    _: object = Depends(require("sources:read")),
):
    return db.scalars(select(DataSource).order_by(DataSource.name)).all()


@router.post("", response_model=DataSourceOut, status_code=201)
def create_source(
    payload: DataSourceCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require("sources:write")),
):
    """Alta de fuente de datos; queda auditada y disponible para la proxima ingesta.

    No se admiten secretos en claro: si el endpoint requiere credenciales se
    referencian por variable de entorno / secret manager.
    """
    name = payload.name.strip()
    base_url = payload.base_url.strip()

    dup_name = db.scalar(select(DataSource).where(func.lower(DataSource.name) == name.lower()))
    if dup_name is not None:
        raise HTTPException(status_code=409, detail=f"Ya existe una fuente llamada «{dup_name.name}»")
    dup_url = db.scalar(select(DataSource).where(DataSource.base_url == base_url))
    if dup_url is not None:
        raise HTTPException(status_code=409, detail=f"Ese endpoint ya esta configurado en «{dup_url.name}»")

    data = payload.model_dump()
    data["name"] = name
    data["base_url"] = base_url
    source = DataSource(**data)
    db.add(source)
    db.commit()
    db.refresh(source)

    log_action(
        db,
        action="source.create",
        entity_type="data_source",
        actor_id=user.id,
        actor_email=user.email,
        entity_id=str(source.id),
        after={"name": source.name, "organization": source.organization,
               "base_url": source.base_url, "source_type": source.source_type,
               "frequency_minutes": source.frequency_minutes, "enabled": source.enabled},
        request=request,
    )
    db.commit()
    return source


@router.get("/{source_id}/runs", response_model=list[IngestionRunOut])
def list_runs(
    source_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: object = Depends(require("sources:read")),
    limit: int = 20,
):
    return db.scalars(
        select(IngestionRun)
        .where(IngestionRun.source_id == source_id)
        .order_by(IngestionRun.started_at.desc())
        .limit(limit)
    ).all()


def _run_sync_background(source_id: str) -> None:
    """Ejecuta la sincronizacion en un proceso independiente (background task)."""
    import subprocess
    import sys
    from pathlib import Path

    sync_py = Path(__file__).resolve().parents[3] / "ingestion" / "sync.py"
    subprocess.Popen(
        [sys.executable, str(sync_py), "--source-id", source_id],
        cwd=str(sync_py.parents[2]),
    )


@router.post("/{source_id}/sync", response_model=IngestionRunOut, status_code=202)
def trigger_sync(
    source_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require("sources:sync")),
):
    source = db.get(DataSource, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Fuente no encontrada")
    if not source.enabled:
        raise HTTPException(status_code=409, detail="Fuente deshabilitada")

    log_action(
        db,
        action="source.sync.trigger",
        entity_type="data_source",
        actor_id=user.id,
        actor_email=user.email,
        entity_id=str(source.id),
        request=request,
    )
    run = IngestionRun(source_id=source.id, status="running")
    db.add(run)
    db.commit()
    db.refresh(run)

    background_tasks.add_task(_run_sync_background, str(source.id))
    return run


@router.patch("/{source_id}/status", response_model=DataSourceOut)
def update_source_status(
    source_id: uuid.UUID,
    enabled: bool,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require("sources:sync")),
):
    source = db.get(DataSource, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Fuente no encontrada")
    before = {"enabled": source.enabled}
    source.enabled = enabled
    source.last_sync_at = utcnow()
    db.commit()
    db.refresh(source)
    log_action(
        db,
        action="source.status.update",
        entity_type="data_source",
        actor_id=user.id,
        actor_email=user.email,
        entity_id=str(source.id),
        before=before,
        after={"enabled": source.enabled},
        request=request,
    )
    return source


@router.delete("/{source_id}", status_code=204)
def delete_source(
    source_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require("sources:write")),
):
    """Elimina una fuente y, en cascada, sus ejecuciones y eventos observados.

    Los eventos se eliminan para no dejar registros sin procedencia (el plan exige
    trazabilidad). La operacion queda auditada con los conteos eliminados.
    """
    source = db.get(DataSource, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Fuente no encontrada")

    before = {
        "name": source.name,
        "organization": source.organization,
        "base_url": source.base_url,
        "enabled": source.enabled,
    }
    n_events = (
        db.scalar(
            select(func.count()).select_from(SeismicEvent).where(SeismicEvent.source_id == source_id)
        )
        or 0
    )
    n_runs = (
        db.scalar(
            select(func.count()).select_from(IngestionRun).where(IngestionRun.source_id == source_id)
        )
        or 0
    )

    # SQLite no aplica ON DELETE CASCADE en esta configuracion: borramos hijos a mano.
    # Las alertas quedan con event_id = null (preserva la bitacora, sin huérfanos rotos).
    db.execute(
        sql_update(Alert)
        .where(Alert.event_id.in_(select(SeismicEvent.id).where(SeismicEvent.source_id == source_id)))
        .values(event_id=None)
    )
    db.execute(sql_delete(IngestionRun).where(IngestionRun.source_id == source_id))
    db.execute(sql_delete(SeismicEvent).where(SeismicEvent.source_id == source_id))
    db.delete(source)
    db.commit()

    log_action(
        db,
        action="source.delete",
        entity_type="data_source",
        actor_id=user.id,
        actor_email=user.email,
        entity_id=str(source.id),
        before=before,
        after={"events_deleted": n_events, "runs_deleted": n_runs},
        request=request,
    )
    db.commit()
