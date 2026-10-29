"""Parametros operativos del sistema (§6.13 «Auditoria y configuracion»).

El catalogo `CONFIG_SPECS` es la unica fuente de verdad de los parametros
editables: define clave, tipo, rango, descripcion y grupo. La base de datos solo
almacena los valores modificados (`system_config`); lo no modificado se resuelve
con el default del catalogo, de modo que una clave eliminada vuelve a su valor
por defecto en lugar de quedar huérfana.

Toda modificacion debe registrarse en `audit_logs` (lo hace el router de
configuracion) y nunca puede incluir secretos: estos viven en variables de
entorno / secret manager, no aqui.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SystemConfig, utcnow

Json = dict | list | str | int | float | bool | None


@dataclass(frozen=True)
class ConfigSpec:
    key: str
    default: Json
    kind: str  # int | float | bool | str
    minimum: float | None
    maximum: float | None
    description: str
    group: str


CONFIG_SPECS: tuple[ConfigSpec, ...] = (
    ConfigSpec("ingesta_interval_seconds", 300, "int", 60, 86400,
               "Frecuencia del daemon de ingesta (segundos)", "ingesta"),
    ConfigSpec("ingesta_lookback_hours", 24, "int", 1, 8760,
               "Ventana hacia atras que revisa cada sincronizacion (horas)", "ingesta"),
    ConfigSpec("ingesta_min_magnitude", 2.5, "float", 0.0, 10.0,
               "Magnitud minima admitida por el conector IGP/CENSIS", "ingesta"),
    ConfigSpec("report_retention_days", 7, "int", 1, 90,
               "Dias de vigencia de los reportes exportados", "reportes"),
    ConfigSpec("alert_cooldown_default_seconds", 1800, "int", 0, 86400,
               "Enfriamiento por defecto de las reglas de alerta (segundos)", "alertas"),
    ConfigSpec("audit_retention_days", 365, "int", 30, 3650,
               "Retencion de la bitacora de auditoria (dias)", "auditoria"),
)

SPECS_BY_KEY: dict[str, ConfigSpec] = {spec.key: spec for spec in CONFIG_SPECS}

DEFAULTS: dict[str, Json] = {spec.key: spec.default for spec in CONFIG_SPECS}


class ConfigError(ValueError):
    """Clave desconocida o valor fuera del rango permitido."""


def _coerce(spec: ConfigSpec, raw: Json) -> Json:
    if spec.kind == "int":
        if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
            raise ConfigError(f"{spec.key}: se espera un numero entero")
        try:
            value: Json = int(float(raw))
        except (TypeError, ValueError):
            raise ConfigError(f"{spec.key}: se espera un numero entero") from None
    elif spec.kind == "float":
        if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
            raise ConfigError(f"{spec.key}: se espera un numero")
        try:
            value = float(raw)
        except (TypeError, ValueError):
            raise ConfigError(f"{spec.key}: se espera un numero") from None
    elif spec.kind == "bool":
        if isinstance(raw, bool):
            value = raw
        elif str(raw).strip().lower() in {"true", "1", "yes", "si", "sí"}:
            value = True
        elif str(raw).strip().lower() in {"false", "0", "no"}:
            value = False
        else:
            raise ConfigError(f"{spec.key}: se espera un valor booleano")
    else:
        if not isinstance(raw, str):
            raise ConfigError(f"{spec.key}: se espera texto")
        value = raw[:255]

    if spec.minimum is not None and isinstance(value, (int, float)) and value < spec.minimum:
        raise ConfigError(f"{spec.key}: minimo {spec.minimum}")
    if spec.maximum is not None and isinstance(value, (int, float)) and value > spec.maximum:
        raise ConfigError(f"{spec.key}: maximo {spec.maximum}")
    return value


def effective_config(db: Session) -> dict[str, Json]:
    """Valores vigentes: defaults del catalogo sobrescritos por los guardados."""
    values = dict(DEFAULTS)
    rows = db.scalars(select(SystemConfig)).all()
    for row in rows:
        if row.key in SPECS_BY_KEY:
            values[row.key] = row.value
    return values


def get_value(db: Session, key: str) -> Json:
    """Valor vigente de una clave; valida que la clave exista en el catalogo."""
    spec = SPECS_BY_KEY.get(key)
    if spec is None:
        raise ConfigError(f"Clave desconocida: {key}")
    row = db.get(SystemConfig, key)
    return row.value if row is not None else spec.default


def apply_updates(db: Session, changes: dict[str, Json], actor_id: uuid.UUID | None) -> tuple[dict[str, Json], dict[str, Json]]:
    """Valida y persiste cambios. Devuelve (antes, despues) para la auditoria."""
    before = effective_config(db)
    unknown = sorted(set(changes) - set(SPECS_BY_KEY))
    if unknown:
        raise ConfigError(f"Claves desconocidas: {', '.join(unknown)}")

    now: datetime = utcnow()
    for key, raw in changes.items():
        spec = SPECS_BY_KEY[key]
        value = _coerce(spec, raw)
        row = db.get(SystemConfig, key)
        if row is None:
            db.add(SystemConfig(key=key, value=value, description=spec.description,
                                updated_by=actor_id, updated_at=now))
        else:
            row.value = value
            row.description = spec.description
            row.updated_by = actor_id
            row.updated_at = now
    db.flush()
    return before, effective_config(db)
