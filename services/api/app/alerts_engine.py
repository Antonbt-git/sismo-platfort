"""Motor de alertas (Fase 7).

Evalúa reglas operativas contra eventos OBSERVADOS. Nunca emite mensajes de peligro
oficial: toda alerta identifica fuente y enlace de procedencia. Las estimaciones
experimentales de ML nunca pasan por aquí (se publican aparte, con disclaimer).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Alert, AlertDelivery, AlertRule, SeismicEvent
from app.models import utcnow

logger = logging.getLogger(__name__)


def _matches_zone(rule: AlertRule, event: SeismicEvent) -> bool:
    bbox = (rule.zone_spec or {}).get("bbox")
    if not bbox or len(bbox) != 4:
        return True
    min_lon, min_lat, max_lon, max_lat = bbox
    return min_lon <= event.longitude <= max_lon and min_lat <= event.latitude <= max_lat


def rule_matches(rule: AlertRule, event: SeismicEvent) -> bool:
    cond = rule.condition_json or {}
    mag = event.magnitude
    if mag is None:
        return False
    if "min_magnitude" in cond and mag < float(cond["min_magnitude"]):
        return False
    if cond.get("max_magnitude") is not None and mag > float(cond["max_magnitude"]):
        return False
    if cond.get("min_depth_km") is not None and (event.depth_km is None or event.depth_km < float(cond["min_depth_km"])):
        return False
    if cond.get("max_depth_km") is not None and (event.depth_km is None or event.depth_km > float(cond["max_depth_km"])):
        return False
    return _matches_zone(rule, event)


def _in_cooldown(db: Session, rule: AlertRule, event: SeismicEvent) -> bool:
    """Deduplicacion: ya existe una alerta para este evento+regla, o la regla esta en cooldown."""
    existing = db.scalar(
        select(Alert).where(Alert.rule_id == rule.id, Alert.event_id == event.id)
    )
    if existing is not None:
        return True
    if rule.last_triggered_at and rule.cooldown_seconds:
        last = rule.last_triggered_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - last < timedelta(seconds=rule.cooldown_seconds):
            return True
    return False


def build_alert_message(rule: AlertRule, event: SeismicEvent) -> tuple[str, str]:
    place = event.place or "ubicacion no especificada"
    mag = event.magnitude
    depth = event.depth_km
    title = f"[{rule.severity.upper()}] Sismo reportado {mag if mag is not None else 's/m'} — {place}"
    message = (
        f"Aviso operativo basado en un evento reportado por la fuente oficial conectada. "
        f"Magnitud {mag} ({event.magnitude_type or 'n/d'}), profundidad "
        f"{depth if depth is not None else 'n/d'} km, {place}. "
        f"Ocurre a las {event.occurred_at.isoformat()}. "
        f"Informacion verificable en: {event.source_url or 'sin enlace'} — "
        f"No es una prediccion ni un comunicado oficial de proteccion civil."
    )
    return title, message


def evaluate_event(db: Session, event: SeismicEvent) -> list[Alert]:
    """Evalua todas las reglas habilitadas contra un evento recien recibido."""
    rules = db.scalars(select(AlertRule).where(AlertRule.enabled.is_(True))).all()
    created: list[Alert] = []
    for rule in rules:
        try:
            if not rule_matches(rule, event):
                continue
            if _in_cooldown(db, rule, event):
                continue
            title, message = build_alert_message(rule, event)
            alert = Alert(
                event_id=event.id,
                rule_id=rule.id,
                severity=rule.severity,
                title=title,
                message=message,
                source_url=event.source_url,
                status="pending_approval" if rule.requires_approval else "approved",
                dedupe_key=f"evt:{event.external_id}",
            )
            db.add(alert)
            db.flush()
            for channel in rule.channels or ["console"]:
                db.add(AlertDelivery(alert_id=alert.id, channel=channel))
            rule.last_triggered_at = utcnow()
            created.append(alert)
        except Exception:  # noqa: BLE001 - una regla rota no debe tumbar la ingesta
            logger.exception("Error evaluando regla %s", rule.id)
    if created:
        db.commit()
    return created


def deliver_alert(db: Session, alert: Alert) -> Alert:
    """Entrega con reintentos idempotentes; registra estado por canal (stub console/email)."""
    deliveries = db.scalars(select(AlertDelivery).where(AlertDelivery.alert_id == alert.id)).all()
    all_ok = True
    for delivery in deliveries:
        delivery.attempts += 1
        delivery.last_attempt_at = utcnow()
        try:
            if delivery.channel == "console":
                logger.info("[ALERTA %s] %s | %s", alert.severity, alert.title, alert.message)
                delivery.status = "sent"
                delivery.delivered_at = utcnow()
                delivery.error_code = None
            elif delivery.channel == "email":
                # Stub: integrar SMTP real en produccion (config fuera del repositorio).
                logger.info("[EMAIL-STUB] para %s: %s", delivery.destination_ref, alert.title)
                delivery.status = "sent"
                delivery.delivered_at = utcnow()
                delivery.error_code = None
            else:
                delivery.status = "failed"
                delivery.error_code = "canal_no_soportado"
                all_ok = False
        except Exception as exc:  # noqa: BLE001
            delivery.status = "failed"
            delivery.error_code = type(exc).__name__[:120]
            all_ok = False
    alert.status = "sent" if all_ok else "failed"
    db.commit()
    db.refresh(alert)
    return alert
