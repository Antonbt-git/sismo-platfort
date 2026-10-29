"""Reglas y centro de alertas (Fase 7)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.alerts_engine import deliver_alert, rule_matches
from app.audit import log_action
from app.db import get_db
from app.models import Alert, AlertDelivery, AlertRule, SeismicEvent, User, utcnow
from app.schemas import AlertOut, AlertRuleCreate, AlertRuleOut, DeliveryOut, RuleSimulationRequest
from app.security import require

router = APIRouter(prefix="/api/v1", tags=["alertas"])

ALLOWED_CHANNELS = {"console", "email"}


@router.get("/alert-rules", response_model=list[AlertRuleOut])
def list_rules(
    db: Session = Depends(get_db),
    _: object = Depends(require("rules:read")),
):
    return db.scalars(select(AlertRule).order_by(AlertRule.created_at.desc())).all()


@router.post("/alert-rules", response_model=AlertRuleOut, status_code=201)
def create_rule(
    payload: AlertRuleCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require("rules:write")),
):
    if db.scalar(select(AlertRule).where(AlertRule.name == payload.name)):
        raise HTTPException(status_code=409, detail="Ya existe una regla con ese nombre")
    bad_channels = [c for c in payload.channels if c not in ALLOWED_CHANNELS]
    if bad_channels:
        raise HTTPException(status_code=422, detail=f"Canales no soportados: {bad_channels}")

    condition = {"min_magnitude": payload.min_magnitude, "max_magnitude": payload.max_magnitude}
    if payload.min_depth_km is not None:
        condition["min_depth_km"] = payload.min_depth_km
    if payload.max_depth_km is not None:
        condition["max_depth_km"] = payload.max_depth_km

    rule = AlertRule(
        name=payload.name,
        condition_json=condition,
        severity=payload.severity,
        zone_spec={"bbox": payload.bbox} if payload.bbox else {},
        channels=payload.channels,
        cooldown_seconds=payload.cooldown_seconds,
        requires_approval=payload.requires_approval,
        enabled=payload.enabled,
        created_by=user.id,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    log_action(
        db,
        action="alert_rule.create",
        entity_type="alert_rule",
        actor_id=user.id,
        actor_email=user.email,
        entity_id=str(rule.id),
        after={"name": rule.name, "condition": condition, "severity": rule.severity},
        request=request,
    )
    return rule


@router.post("/alert-rules/simulate")
def simulate_rule(
    payload: RuleSimulationRequest,
    _: object = Depends(require("rules:read")),
):
    """Prueba de regla sin efectos: no crea alertas ni envia mensajes."""
    fake_event = SeismicEvent(
        external_id="simulacion",
        source_id=uuid.uuid4(),
        occurred_at=utcnow(),
        latitude=payload.latitude if payload.latitude is not None else -12.0,
        longitude=payload.longitude if payload.longitude is not None else -77.0,
        magnitude=payload.magnitude,
        depth_km=payload.depth_km,
    )
    from types import SimpleNamespace

    fake_rule = SimpleNamespace(
        condition_json={"min_magnitude": 4.5, "max_magnitude": None},
        zone_spec={},
    )
    return {
        "nota": "Simulacion sin efectos: usa los campos de la regla para evaluar un caso hipotetico.",
        "coincidencia_con_regla_ejemplo": bool(rule_matches(fake_rule, fake_event)),
    }


@router.patch("/alert-rules/{rule_id}/enabled", response_model=AlertRuleOut)
def toggle_rule(
    rule_id: uuid.UUID,
    enabled: bool,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require("rules:write")),
):
    rule = db.get(AlertRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Regla no encontrada")
    before = {"enabled": rule.enabled}
    rule.enabled = enabled
    db.commit()
    db.refresh(rule)
    log_action(
        db,
        action="alert_rule.enable" if enabled else "alert_rule.disable",
        entity_type="alert_rule",
        actor_id=user.id,
        actor_email=user.email,
        entity_id=str(rule.id),
        before=before,
        after={"enabled": rule.enabled},
        request=request,
    )
    return rule


@router.get("/alerts", response_model=list[AlertOut])
def list_alerts(
    db: Session = Depends(get_db),
    _: object = Depends(require("alerts:read")),
    status: str | None = None,
    limit: int = 100,
):
    stmt = select(Alert).order_by(Alert.created_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(Alert.status == status)
    return db.scalars(stmt).all()


@router.post("/alerts/{alert_id}/approve", response_model=AlertOut)
def approve_alert(
    alert_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require("alerts:approve")),
):
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    if alert.status != "pending_approval":
        raise HTTPException(status_code=409, detail=f"Estado actual no aprobable: {alert.status}")
    alert.status = "approved"
    alert.approved_by = user.id
    alert.approved_at = utcnow()
    db.commit()
    log_action(
        db,
        action="alert.approve",
        entity_type="alert",
        actor_id=user.id,
        actor_email=user.email,
        entity_id=str(alert.id),
        after={"status": alert.status},
        request=request,
    )
    return deliver_alert(db, alert)


@router.post("/alerts/{alert_id}/cancel", response_model=AlertOut)
def cancel_alert(
    alert_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require("alerts:approve")),
):
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    if alert.status == "sent":
        raise HTTPException(status_code=409, detail="No se puede cancelar una alerta ya enviada")
    alert.status = "cancelled"
    db.commit()
    db.refresh(alert)
    log_action(
        db,
        action="alert.cancel",
        entity_type="alert",
        actor_id=user.id,
        actor_email=user.email,
        entity_id=str(alert.id),
        after={"status": alert.status},
        request=request,
    )
    return alert


@router.get("/alerts/{alert_id}/deliveries", response_model=list[DeliveryOut])
def alert_deliveries(
    alert_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: object = Depends(require("alerts:read")),
):
    return db.scalars(select(AlertDelivery).where(AlertDelivery.alert_id == alert_id)).all()
