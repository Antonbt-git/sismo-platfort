"""Conector para la fuente oficial IGP / CENSIS (Centro Sismológico Nacional del Perú).

El IGP publica el catálogo de sismos reportados mediante su API JSON:

    GET https://censis.igp.gob.pe/api/ultimo-sismo/sismos

Devuelve el catálogo del año en curso como arreglo JSON. Cada registro contiene:
``codigo`` (p. ej. "2026-0753"), ``fecha_hora`` (ISO 8601 UTC), ``latitud``,
``longitud``, ``magnitud``, ``profundidad`` (km), ``referencia``, ``intensidades``,
``tipo_evento`` (P = sismo real, S = simulacro) y ``simulacro``.

Endpoints relacionados (documentación de referencia):
    - ``/api/ultimo-sismo``                 último evento reportado
    - ``/api/ultimo-sismo/sismo/{codigo}``  reporte sísmico completo
    - ``/api/ultimo-sismo/inicio``          estadísticas anuales

La plataforma no sustituye al IGP ni a INDECI: solo difunde lo reportado por la fuente.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://censis.igp.gob.pe/api/ultimo-sismo/sismos"
EVENT_PAGE_URL = "https://censis.igp.gob.pe/evento/{code}"
TIMEOUT_SECONDS = 30

# El esquema CHECK de seismic_events limita depth_km a [0, 800].
MAX_DEPTH_KM = 800.0


@dataclass
class NormalizedEvent:
    external_id: str
    occurred_at: datetime
    latitude: float
    longitude: float
    magnitude: float | None
    magnitude_type: str | None
    depth_km: float | None
    place: str | None
    region: str | None
    source_url: str | None


def _to_float(value) -> float | None:
    """Convierte escalares IGP (que llegan como texto) a float; None si no es numerico."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_drill(item: dict) -> bool:
    """Detecta simulacros, que el IGP reporta de dos formas.

    Algunos endpoints marcan ``simulacro`` (0/1 o booleano) y otros solo cambian
    ``tipo_evento`` a "S" (simulacro) manteniendo ``simulacro`` en falso. Los
    simulacros reutilizan el codigo de un sismo real, por lo que deben excluirse
    para no contaminar el catalogo observado ni romper la unicidad externa.
    """
    if item.get("tipo_evento") == "S":
        return True
    value = item.get("simulacro")
    return value is True or value == 1 or str(value).strip().lower() in {"1", "true", "sí", "si"}


def derive_region(reference: str | None) -> str | None:
    """Obtiene la region a partir de la referencia del IGP.

    Formato habitual: "48 km al SO de Casma, Casma - Áncash" -> "Áncash".
    """
    if not reference:
        return None
    if " - " in reference:
        return reference.rsplit(" - ", 1)[-1].strip() or None
    if ", " in reference:
        return reference.rsplit(", ", 1)[-1].strip() or None
    return reference.strip() or None


def normalize_item(item: dict) -> NormalizedEvent | None:
    """Convierte un registro del catalogo CENSIS al modelo normalizado interno."""
    code = item.get("codigo") or item.get("code") or item.get("id")
    ts = item.get("fecha_hora")
    lat = _to_float(item.get("latitud"))
    lon = _to_float(item.get("longitud"))
    if code is None or not ts or lat is None or lon is None:
        return None

    try:
        occurred_at = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        logger.warning("Registro CENSIS con fecha_hora invalida: %r", ts)
        return None
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=timezone.utc)

    depth = _to_float(item.get("profundidad"))
    if depth is not None:
        # El esquema CHECK no admite profundidades negativas ni mayores a 800 km.
        depth = max(0.0, min(depth, MAX_DEPTH_KM))

    reference = (item.get("referencia") or item.get("place") or None)
    magnitude = _to_float(item.get("magnitud"))
    if magnitude is not None and not 0.0 <= magnitude <= 10.0:
        logger.warning("Registro CENSIS %s con magnitud fuera de rango: %r", code, magnitude)
        magnitude = None

    return NormalizedEvent(
        external_id=str(code),
        occurred_at=occurred_at.astimezone(timezone.utc),
        latitude=lat,
        longitude=lon,
        magnitude=magnitude,
        # El CENSIS no publica tipo de magnitud: no se inventa ninguno.
        magnitude_type=None,
        depth_km=depth,
        place=reference,
        region=derive_region(reference),
        source_url=EVENT_PAGE_URL.format(code=str(code)),
    )


def fetch_events(
    base_url: str = DEFAULT_BASE_URL,
    *,
    start: datetime,
    end: datetime,
    min_magnitude: float = 2.5,
    limit: int = 5000,
) -> list[NormalizedEvent]:
    """Descarga el catalogo IGP/CENSIS y devuelve los eventos del rango consultado.

    El endpoint entrega el catalogo completo del anio, por lo que el filtro por
    ventana temporal y magnitud se aplica localmente. Los simulacros se excluyen.
    """
    response = httpx.get(base_url, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise ValueError(f"Respuesta inesperada del IGP: tipo {type(payload).__name__}")

    start_utc = start.astimezone(timezone.utc)
    end_utc = end.astimezone(timezone.utc)

    events: list[NormalizedEvent] = []
    skipped_drills = 0
    duplicates = 0
    seen_codes: set[str] = set()
    for item in payload:
        if not isinstance(item, dict):
            continue
        if _is_drill(item):
            skipped_drills += 1
            continue
        normalized = normalize_item(item)
        if normalized is None:
            continue
        if not (start_utc <= normalized.occurred_at <= end_utc):
            continue
        if normalized.magnitude is not None and normalized.magnitude < min_magnitude:
            continue
        # El catalogo IGP repite registros identicos bajo el mismo codigo; como
        # (external_id, source_id) es unica en la base, se conserva el primero.
        if normalized.external_id in seen_codes:
            duplicates += 1
            continue
        seen_codes.add(normalized.external_id)
        events.append(normalized)

    events.sort(key=lambda e: e.occurred_at)
    if skipped_drills:
        logger.info("IGP/CENSIS: %s simulacros excluidos del catalogo", skipped_drills)
    if duplicates:
        logger.info("IGP/CENSIS: %s registros repetidos descartados", duplicates)
    return events[:limit]
