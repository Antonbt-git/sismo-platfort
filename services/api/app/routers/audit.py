"""Bitacora de auditoria (Fase 2/8)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AuditLog
from app.schemas import AuditLogOut
from app.security import require

router = APIRouter(prefix="/api/v1/audit-logs", tags=["auditoria"])


@router.get("", response_model=list[AuditLogOut])
def list_logs(
    db: Session = Depends(get_db),
    _: object = Depends(require("audit:read")),
    action: str | None = None,
    entity_type: str | None = None,
    actor_id: uuid.UUID | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
):
    stmt = select(AuditLog).order_by(AuditLog.occurred_at.desc()).limit(limit)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if actor_id:
        stmt = stmt.where(AuditLog.actor_id == actor_id)
    return db.scalars(stmt).all()


@router.get("/{log_id}", response_model=AuditLogOut)
def get_log(
    log_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: object = Depends(require("audit:read")),
):
    entry = db.get(AuditLog, log_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    return entry
