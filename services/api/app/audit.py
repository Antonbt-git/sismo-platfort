"""Servicio de auditoria: registro inmutable de acciones criticas (Fase 2/8)."""
from __future__ import annotations

import uuid

from fastapi import Request
from sqlalchemy.orm import Session

from app.models import AuditLog


def _client_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def log_action(
    db: Session,
    *,
    action: str,
    entity_type: str,
    actor_id: uuid.UUID | None = None,
    actor_email: str | None = None,
    entity_id: str | None = None,
    before: dict | None = None,
    after: dict | None = None,
    result: str = "success",
    request: Request | None = None,
    correlation_id: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_id=actor_id,
        actor_email=actor_email,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before_json=before,
        after_json=after,
        result=result,
        ip=_client_ip(request),
        correlation_id=correlation_id,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
