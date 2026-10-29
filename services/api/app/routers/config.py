"""Configuracion operativa del sistema (§6.13 del plan).

Lectura restringida (admin y auditor) y escritura solo administrativa. Cada
modificacion se registra en `audit_logs` con valores antes/despues para
mantener el control de cambios exigido por el plan.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import log_action
from app.db import get_db
from app.models import SystemConfig, User
from app.runtime_config import CONFIG_SPECS, ConfigError, apply_updates, effective_config
from app.schemas import ConfigDefinition, ConfigOut, ConfigUpdate
from app.security import require

router = APIRouter(prefix="/api/v1/config", tags=["configuracion"])


def _build_out(db: Session) -> ConfigOut:
    values = effective_config(db)
    rows = {r.key: r for r in db.scalars(select(SystemConfig)).all()}
    definitions = [
        ConfigDefinition(
            key=spec.key,
            value=values[spec.key],
            default=spec.default,
            kind=spec.kind,
            minimum=spec.minimum,
            maximum=spec.maximum,
            description=spec.description,
            group=spec.group,
            # "modificado" = hay un valor almacenado distinto de su default;
            # si el operador revierte al default, la etiqueta desaparece.
            modified=spec.key in rows and rows[spec.key].value != spec.default,
        )
        for spec in CONFIG_SPECS
    ]
    latest = max((r.updated_at for r in rows.values()), default=None)
    latest_by = max(rows.values(), key=lambda r: r.updated_at).updated_by if rows else None
    return ConfigOut(definitions=definitions, last_updated_at=latest, last_updated_by=latest_by)


@router.get("", response_model=ConfigOut)
def read_config(
    db: Session = Depends(get_db),
    _: object = Depends(require("config:read")),
):
    return _build_out(db)


@router.put("", response_model=ConfigOut)
def update_config(
    payload: ConfigUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require("config:write")),
):
    if not payload.values:
        raise HTTPException(status_code=400, detail="Sin valores para actualizar")
    try:
        before, _after = apply_updates(db, payload.values, actor_id=user.id)
    except ConfigError as exc:
        db.rollback()
        log_action(
            db,
            action="config.update",
            entity_type="system_config",
            actor_id=user.id,
            actor_email=user.email,
            after={"intentado": payload.values},
            result="error",
            request=request,
        )
        db.commit()
        raise HTTPException(status_code=400, detail=str(exc)) from None

    changed = {k: v for k, v in _after.items() if before.get(k) != v}
    log_action(
        db,
        action="config.update",
        entity_type="system_config",
        actor_id=user.id,
        actor_email=user.email,
        entity_id=", ".join(sorted(changed)) or None,
        before={k: before[k] for k in changed},
        after=changed,
        request=request,
    )
    db.commit()
    return _build_out(db)
