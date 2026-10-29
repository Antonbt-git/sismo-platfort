"""Modelo de datos PostgreSQL (§7 del plan). UUID internos, UTC y restricciones CHECK."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | disabled
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    roles: Mapped[list[str]] = mapped_column(JSON, default=list)  # nombres de rol sincronizados


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(50), unique=True)


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)


class DataSource(Base):
    __tablename__ = "data_sources"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    organization: Mapped[str] = mapped_column(String(120), default="")
    base_url: Mapped[str] = mapped_column(String(500))
    source_type: Mapped[str] = mapped_column(String(40), default="rest")  # rest | feed | manual
    status: Mapped[str] = mapped_column(String(20), default="unknown")  # ok | degraded | error | unknown
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    license: Mapped[str] = mapped_column(String(255), default="")
    contact: Mapped[str] = mapped_column(String(255), default="")
    frequency_minutes: Mapped[int] = mapped_column(Integer, default=5)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Secretos nunca en texto plano: solo referencia a variable/secret manager.
    config_ref: Mapped[str] = mapped_column(String(255), default="")


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"
    __table_args__ = (Index("ix_runs_source_started", "source_id", "started_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("data_sources.id", ondelete="CASCADE"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="running")  # running | success | error
    records_seen: Mapped[int] = mapped_column(Integer, default=0)
    records_inserted: Mapped[int] = mapped_column(Integer, default=0)
    records_updated: Mapped[int] = mapped_column(Integer, default=0)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class SeismicEvent(Base):
    __tablename__ = "seismic_events"
    __table_args__ = (
        UniqueConstraint("external_id", "source_id", name="uq_event_external_source"),
        CheckConstraint("latitude >= -90 AND latitude <= 90", name="ck_lat_range"),
        CheckConstraint("longitude >= -180 AND longitude <= 180", name="ck_lon_range"),
        CheckConstraint("depth_km >= 0 AND depth_km <= 800", name="ck_depth_range"),
        CheckConstraint("magnitude >= 0 AND magnitude <= 10", name="ck_mag_range"),
        Index("ix_events_occurred_at", "occurred_at"),
        Index("ix_events_magnitude", "magnitude"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id: Mapped[str] = mapped_column(String(80))
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("data_sources.id", ondelete="CASCADE"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    magnitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    magnitude_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    depth_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    place: Mapped[str | None] = mapped_column(String(300), nullable=True)
    region: Mapped[str | None] = mapped_column(String(150), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    review_status: Mapped[str] = mapped_column(String(20), default="observed")  # observed | reviewed


class Dataset(Base):
    __tablename__ = "datasets"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_dataset_name_version"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120))
    version: Mapped[int] = mapped_column(Integer, default=1)
    query_spec: Mapped[dict] = mapped_column(JSON, default=dict)
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    quality_report: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MlExperiment(Base):
    __tablename__ = "ml_experiments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(150))
    task_type: Mapped[str] = mapped_column(String(20))  # classification | regression
    algorithm: Mapped[str] = mapped_column(String(80))
    dataset_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("datasets.id"), nullable=True)
    feature_spec: Mapped[list] = mapped_column(JSON, default=list)
    target_name: Mapped[str] = mapped_column(String(80), default="")
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    validation_spec: Mapped[dict] = mapped_column(JSON, default=dict)
    seed: Mapped[int] = mapped_column(Integer, default=42)
    library_versions: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="completed")  # running | completed | failed
    artifact_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)
    limitations: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ModelRegistry(Base):
    __tablename__ = "model_registry"
    __table_args__ = (UniqueConstraint("experiment_id", "version", name="uq_model_exp_version"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    experiment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ml_experiments.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="candidate")  # candidate | approved | rejected
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    limitations: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RiskEstimate(Base):
    __tablename__ = "risk_estimates"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("model_registry.id", ondelete="CASCADE"))
    area_code: Mapped[str] = mapped_column(String(80))
    window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metric_name: Mapped[str] = mapped_column(String(80))
    value: Mapped[float] = mapped_column(Float)
    lower_bound: Mapped[float | None] = mapped_column(Float, nullable=True)
    upper_bound: Mapped[float | None] = mapped_column(Float, nullable=True)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    disclaimer: Mapped[str] = mapped_column(Text, default="")
    is_experimental: Mapped[bool] = mapped_column(Boolean, default=True)


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(150), unique=True)
    condition_json: Mapped[dict] = mapped_column(JSON, default=dict)
    severity: Mapped[str] = mapped_column(String(20), default="info")  # info | warning | critical
    zone_spec: Mapped[dict] = mapped_column(JSON, default=dict)  # bbox: [minLon,minLat,maxLon,maxLat]
    channels: Mapped[list] = mapped_column(JSON, default=lambda: ["console"])
    cooldown_seconds: Mapped[int] = mapped_column(Integer, default=1800)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        UniqueConstraint("event_id", "rule_id", "dedupe_key", name="uq_alert_dedupe"),
        Index("ix_alerts_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("seismic_events.id", ondelete="SET NULL"), nullable=True)
    rule_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("alert_rules.id", ondelete="SET NULL"), nullable=True)
    severity: Mapped[str] = mapped_column(String(20), default="info")
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending_approval")  # pending_approval | approved | sent | failed | cancelled
    dedupe_key: Mapped[str] = mapped_column(String(120), default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AlertDelivery(Base):
    __tablename__ = "alert_deliveries"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("alerts.id", ondelete="CASCADE"))
    channel: Mapped[str] = mapped_column(String(30))  # console | email
    destination_ref: Mapped[str] = mapped_column(String(255), default="operadores")
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | sent | failed
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_occurred", "occurred_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    actor_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    action: Mapped[str] = mapped_column(String(80))
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    before_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ip: Mapped[str | None] = mapped_column(String(60), nullable=True)
    result: Mapped[str] = mapped_column(String(20), default="success")  # success | error
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ReportJob(Base):
    __tablename__ = "report_jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    requested_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    report_type: Mapped[str] = mapped_column(String(40))  # events | alerts | quality | models
    filters_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | done | error
    file_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SystemConfig(Base):
    """Parametros operativos editables (§6.13 Auditoria y configuracion).

    Solo se persisten claves presentes en `app/runtime_config.CONFIG_SPECS`; los
    valores no modificados viven en los defaults de ese catalogo. El valor se
    guarda como JSON escalar y toda modificacion queda en audit_logs.
    """

    __tablename__ = "system_config"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSON, nullable=False)
    description: Mapped[str] = mapped_column(String(255), default="")
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
