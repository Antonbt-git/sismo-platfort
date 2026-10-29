"""Esquemas Pydantic de request/response (validacion estricta en bordes)."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Auth / usuarios ----------
class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=4, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class UserCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    roles: list[str] = Field(default_factory=lambda: ["viewer"])


class UserOut(ORMModel):
    id: uuid.UUID
    full_name: str
    email: EmailStr
    status: str
    roles: list[str]
    created_at: datetime
    last_login_at: datetime | None = None


class UserRoleUpdate(BaseModel):
    roles: list[str]


# ---------- Fuentes / ingesta ----------
class DataSourceOut(ORMModel):
    id: uuid.UUID
    name: str
    organization: str
    base_url: str
    source_type: str
    status: str
    enabled: bool
    license: str
    frequency_minutes: int
    last_sync_at: datetime | None = None
    last_success_at: datetime | None = None
    last_latency_ms: int | None = None


class DataSourceCreate(BaseModel):
    """Alta de fuente desde el modulo Fuentes de datos (sin secretos en claro)."""

    name: str = Field(min_length=3, max_length=120)
    organization: str = Field(min_length=2, max_length=120)
    base_url: str = Field(min_length=10, max_length=500, pattern=r"^https?://\S+$")
    source_type: str = Field(default="rest", pattern=r"^[a-z0-9_-]{2,40}$")
    license: str = Field(default="", max_length=255)
    contact: str = Field(default="", max_length=255)
    frequency_minutes: int = Field(default=5, ge=1, le=1440)
    enabled: bool = True


class IngestionRunOut(ORMModel):
    id: uuid.UUID
    source_id: uuid.UUID
    started_at: datetime
    finished_at: datetime | None
    status: str
    records_seen: int
    records_inserted: int
    records_updated: int
    error_summary: str | None


# ---------- Eventos ----------
class EventOut(ORMModel):
    id: uuid.UUID
    external_id: str
    source_id: uuid.UUID
    occurred_at: datetime
    latitude: float
    longitude: float
    magnitude: float | None
    magnitude_type: str | None
    depth_km: float | None
    place: str | None
    region: str | None
    source_url: str | None
    received_at: datetime
    review_status: str


class EventPage(BaseModel):
    total: int
    offset: int
    limit: int
    items: list[EventOut]


class GeoJsonFeatureCollection(BaseModel):
    type: str = "FeatureCollection"
    features: list[dict]


# ---------- Dashboard / analisis ----------
class DashboardSummary(BaseModel):
    total_events: int
    events_last_24h: int
    events_last_7d: int
    max_magnitude_7d: float | None
    avg_depth: float | None
    median_depth: float | None
    last_sync_at: datetime | None
    active_alerts: int
    sources: list[DataSourceOut]
    period_start: datetime | None
    period_end: datetime | None
    # Estadisticas sobre el periodo seleccionado (filtro 7d / 30d / 1 anio)
    period_max_magnitude: float | None = None
    period_avg_depth: float | None = None


class TimeseriesPoint(BaseModel):
    bucket: str
    count: int


class HistogramBin(BaseModel):
    label: str
    count: int


class RegionCount(BaseModel):
    region: str
    count: int


class QualitySummary(BaseModel):
    sample_size: int
    missing_magnitude: int
    missing_depth: int
    duplicate_external_ids: int
    period_start: datetime | None
    period_end: datetime | None


# ---------- Datasets ----------
class DatasetCreate(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    date_from: datetime | None = None
    date_to: datetime | None = None
    min_magnitude: float | None = None
    source_id: uuid.UUID | None = None


class DatasetOut(ORMModel):
    id: uuid.UUID
    name: str
    version: int
    query_spec: dict
    period_start: datetime | None
    period_end: datetime | None
    row_count: int
    quality_report: dict
    created_at: datetime


# ---------- ML ----------
class ExperimentCreate(BaseModel):
    name: str = Field(min_length=3, max_length=150)
    task_type: str = Field(pattern="^(classification|regression)$")
    algorithm: str = "random_forest"
    dataset_id: uuid.UUID | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None


class ExperimentOut(ORMModel):
    id: uuid.UUID
    name: str
    task_type: str
    algorithm: str
    dataset_id: uuid.UUID | None
    feature_spec: list
    target_name: str
    params: dict
    metrics: dict
    validation_spec: dict
    seed: int
    status: str
    artifact_uri: str | None
    limitations: str
    created_at: datetime


class ModelOut(ORMModel):
    id: uuid.UUID
    experiment_id: uuid.UUID
    version: int
    status: str
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    limitations: str
    created_at: datetime


class EstimateCreate(BaseModel):
    model_id: uuid.UUID
    area_code: str = Field(default="PER", max_length=80)
    window_hours: int = Field(default=168, ge=1, le=8760)


class EstimateOut(ORMModel):
    id: uuid.UUID
    model_id: uuid.UUID
    area_code: str
    window_start: datetime | None
    window_end: datetime | None
    metric_name: str
    value: float
    lower_bound: float | None
    upper_bound: float | None
    calculated_at: datetime
    disclaimer: str
    is_experimental: bool


# ---------- Alertas ----------
class AlertRuleCreate(BaseModel):
    name: str = Field(min_length=3, max_length=150)
    min_magnitude: float = Field(ge=0, le=10)
    max_magnitude: float | None = Field(default=None, ge=0, le=10)
    min_depth_km: float | None = Field(default=None, ge=0)
    max_depth_km: float | None = Field(default=None, ge=0)
    bbox: list[float] | None = None  # [minLon, minLat, maxLon, maxLat]
    severity: str = Field(default="warning", pattern="^(info|warning|critical)$")
    channels: list[str] = Field(default_factory=lambda: ["console"])
    cooldown_seconds: int = Field(default=1800, ge=0)
    requires_approval: bool = True
    enabled: bool = False


class AlertRuleOut(ORMModel):
    id: uuid.UUID
    name: str
    condition_json: dict
    severity: str
    zone_spec: dict
    channels: list
    cooldown_seconds: int
    requires_approval: bool
    enabled: bool
    last_triggered_at: datetime | None
    created_at: datetime


class AlertOut(ORMModel):
    id: uuid.UUID
    event_id: uuid.UUID | None
    rule_id: uuid.UUID | None
    severity: str
    title: str
    message: str
    source_url: str | None
    status: str
    created_at: datetime
    approved_by: uuid.UUID | None
    approved_at: datetime | None


class DeliveryOut(ORMModel):
    id: uuid.UUID
    alert_id: uuid.UUID
    channel: str
    destination_ref: str
    status: str
    attempts: int
    last_attempt_at: datetime | None
    delivered_at: datetime | None
    error_code: str | None


class RuleSimulationRequest(BaseModel):
    magnitude: float = Field(ge=0, le=10)
    depth_km: float | None = Field(default=None, ge=0)
    latitude: float | None = None
    longitude: float | None = None


# ---------- Reportes ----------
class ReportCreate(BaseModel):
    report_type: str = Field(pattern="^(events|alerts|quality|models)$")
    date_from: datetime | None = None
    date_to: datetime | None = None
    min_magnitude: float | None = None
    format: str = Field(default="csv", pattern="^(csv|xlsx|pdf)$")


class ReportOut(ORMModel):
    id: uuid.UUID
    report_type: str
    filters_json: dict
    status: str
    file_ref: str | None
    error_summary: str | None
    created_at: datetime
    expires_at: datetime | None


# ---------- Auditoria ----------
class AuditLogOut(ORMModel):
    id: uuid.UUID
    actor_id: uuid.UUID | None
    actor_email: str | None
    action: str
    entity_type: str
    entity_id: str | None
    before_json: dict | None
    after_json: dict | None
    occurred_at: datetime
    ip: str | None
    result: str
    correlation_id: str | None


# ---------- Configuracion del sistema ----------
class ConfigDefinition(BaseModel):
    key: str
    value: dict | list | str | int | float | bool | None
    default: dict | list | str | int | float | bool | None
    kind: str
    minimum: float | None = None
    maximum: float | None = None
    description: str
    group: str
    modified: bool


class ConfigOut(BaseModel):
    definitions: list[ConfigDefinition]
    last_updated_at: datetime | None = None
    last_updated_by: uuid.UUID | None = None


class ConfigUpdate(BaseModel):
    values: dict[str, dict | list | str | int | float | bool | None]


TokenResponse.model_rebuild()
