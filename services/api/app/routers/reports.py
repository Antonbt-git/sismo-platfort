"""Generacion y descarga de reportes operativos en CSV/XLSX/PDF (Fase 8, §6.11)."""
from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import log_action
from app.config import get_settings
from app.db import SessionLocal, get_db
from app.models import Alert, Dataset, MlExperiment, ReportJob, SeismicEvent, User, utcnow
from app.routers.events import apply_event_filters
from app.runtime_config import ConfigError, get_value
from app.schemas import ReportCreate, ReportOut
from app.security import require

router = APIRouter(prefix="/api/v1/reports", tags=["reportes"])

DEFAULT_RETENTION_DAYS = 7

MIME_TYPES = {
    "csv": "text/csv; charset=utf-8",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}

REPORT_LABELS = {
    "events": "Eventos observados",
    "alerts": "Alertas y entregas",
    "quality": "Calidad de datasets",
    "models": "Experimentos y modelos",
}


def _retention_days(db: Session) -> int:
    """Retencion vigente: configuracion del sistema con fallback al default."""
    try:
        return int(get_value(db, "report_retention_days"))
    except (ConfigError, TypeError, ValueError):
        return DEFAULT_RETENTION_DAYS


def _collect(db: Session, job: ReportJob, filters: dict) -> tuple[list[str], list[list]]:
    """Construye cabeceras y filas del reporte, independiente del formato."""
    date_from = datetime.fromisoformat(filters["date_from"]) if filters.get("date_from") else None
    date_to = datetime.fromisoformat(filters["date_to"]) if filters.get("date_to") else None

    if job.report_type == "events":
        headers = ["ocurrio_utc", "lat", "lon", "magnitud", "tipo_mag", "profundidad_km", "lugar", "enlace_fuente"]
        stmt = apply_event_filters(
            select(SeismicEvent), date_from=date_from, date_to=date_to,
            min_magnitude=filters.get("min_magnitude"), max_magnitude=None,
            source_id=None, bbox=None, place=None,
        ).order_by(SeismicEvent.occurred_at.desc()).limit(20000)
        rows = [[e.occurred_at.isoformat(), e.latitude, e.longitude, e.magnitude,
                 e.magnitude_type, e.depth_km, e.place, e.source_url] for e in db.scalars(stmt)]
    elif job.report_type == "alerts":
        headers = ["creada_utc", "severidad", "titulo", "estado", "mensaje"]
        rows = [[a.created_at.isoformat(), a.severity, a.title, a.status, a.message]
                for a in db.scalars(select(Alert).order_by(Alert.created_at.desc()).limit(5000))]
    elif job.report_type == "quality":
        headers = ["dataset", "version", "filas", "nulos_mag_%", "nulos_prof_%", "duplicados"]
        rows = []
        for d in db.scalars(select(Dataset).order_by(Dataset.created_at.desc())):
            q = d.quality_report or {}
            rows.append([d.name, d.version, d.row_count, q.get("missing_magnitude_pct"),
                         q.get("missing_depth_pct"), q.get("duplicate_external_ids")])
    else:  # models
        headers = ["experimento", "tarea", "algoritmo", "estado", "metricas", "limitaciones"]
        rows = [[m.name, m.task_type, m.algorithm, m.status,
                 json.dumps(m.metrics, ensure_ascii=False), m.limitations]
                for m in db.scalars(select(MlExperiment).order_by(MlExperiment.created_at.desc()))]
    return headers, rows


def _meta(job: ReportJob, filters: dict, row_count: int) -> list[list[str]]:
    """Cabecera comun: generacion, tipo, filtros, fuente, solicitante y filas."""
    return [
        ["generado_utc", datetime.now(timezone.utc).isoformat()],
        ["tipo_reporte", f"{job.report_type} ({REPORT_LABELS.get(job.report_type, job.report_type)})"],
        ["formato", str(filters.get("format", "csv"))],
        ["filtros", json.dumps(filters, ensure_ascii=False)],
        ["fuente", "IGP / CENSIS (Centro Sismológico Nacional)"],
        ["registros", row_count],
        [],
    ]


def _write_csv(path: Path, meta: list[list[str]], headers: list[str], rows: list[list]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        for line in meta:
            writer.writerow(line)
        writer.writerow(headers)
        writer.writerows(rows)


def _write_xlsx(path: Path, meta: list[list[str]], headers: list[str], rows: list[list]) -> None:
    import pandas as pd

    buffer = io.StringIO()
    writer_csv = csv.writer(buffer)
    writer_csv.writerows(meta)
    writer_csv.writerow(headers)
    writer_csv.writerows(rows)
    buffer.seek(0)
    # Lee la parte de datos (salta las filas de metadatos terminadas en vacio).
    skiprows = len(meta) - 1
    frame = pd.read_csv(buffer, skiprows=skiprows)
    with pd.ExcelWriter(path, engine="openpyxl") as xlsx:
        frame.to_excel(xlsx, index=False, sheet_name="Reporte")


def _write_pdf(path: Path, meta: list[list[str]], headers: list[str], rows: list[list]) -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(path), pagesize=landscape(A4),
                            leftMargin=12 * mm, rightMargin=12 * mm,
                            topMargin=12 * mm, bottomMargin=12 * mm)
    story: list = [Paragraph("Reporte — Sistema de Monitoreo Sísmico", styles["Title"])]
    for line in meta:
        if line:
            story.append(Paragraph(f"<b>{line[0]}:</b> {line[1]}", styles["Normal"]))
    story.append(Spacer(1, 6 * mm))

    limit = 900  # el PDF es para lectura humana: se recorta y se indica
    truncated = len(rows) > limit
    table_rows = [headers] + [[("" if c is None else str(c))[:60] for c in r] for r in rows[:limit]]
    if table_rows:
        table = Table(table_rows, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f2a4a")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 6),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(table)
    if truncated:
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(
            f"Se muestran {limit} de {len(rows)} registros. Exporte en XLSX/CSV para el conjunto completo.",
            styles["Normal"]))
    doc.build(story)


WRITERS = {"csv": _write_csv, "xlsx": _write_xlsx, "pdf": _write_pdf}


def _generate(report_id: str) -> None:
    db = SessionLocal()
    try:
        job = db.get(ReportJob, uuid.UUID(report_id))
        if job is None:
            return
        try:
            settings = get_settings()
            reports_dir = Path(settings.reports_dir)
            reports_dir.mkdir(parents=True, exist_ok=True)
            filters = dict(job.filters_json or {})
            fmt = str(filters.get("format", "csv"))
            headers, rows = _collect(db, job, filters)
            meta = _meta(job, filters, len(rows))

            path = reports_dir / f"{job.report_type}_{job.id}.{fmt}"
            WRITERS[fmt](path, meta, headers, rows)

            job.file_ref = str(path)
            job.status = "done"
            job.expires_at = utcnow() + timedelta(days=_retention_days(db))
        except Exception as exc:  # noqa: BLE001
            job.status = "error"
            job.error_summary = f"{type(exc).__name__}: {exc}"
        db.commit()
    finally:
        db.close()


@router.post("", response_model=ReportOut, status_code=201)
def create_report(
    payload: ReportCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require("reports:write")),
):
    job = ReportJob(
        requested_by=user.id,
        report_type=payload.report_type,
        filters_json={
            "date_from": payload.date_from.isoformat() if payload.date_from else None,
            "date_to": payload.date_to.isoformat() if payload.date_to else None,
            "min_magnitude": payload.min_magnitude,
            "format": payload.format,
        },
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    log_action(
        db,
        action="report.request",
        entity_type="report_job",
        actor_id=user.id,
        actor_email=user.email,
        entity_id=str(job.id),
        after={"report_type": job.report_type},
        request=request,
    )
    background_tasks.add_task(_generate, str(job.id))
    return job


@router.get("", response_model=list[ReportOut])
def list_reports(
    db: Session = Depends(get_db),
    user: User = Depends(require("reports:read")),
):
    stmt = select(ReportJob).order_by(ReportJob.created_at.desc()).limit(50)
    jobs = db.scalars(stmt).all()
    if "reports:write" not in _perms(user):
        # Solo lectura: ve metadatos propios.
        jobs = [j for j in jobs if j.requested_by == user.id]
    return jobs


def _perms(user: User) -> set[str]:
    from app.security import user_permissions

    return user_permissions(user)


@router.get("/{report_id}")
def download_report(
    report_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require("reports:read")),
):
    job = db.get(ReportJob, report_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")
    if job.status != "done" or not job.file_ref:
        raise HTTPException(status_code=409, detail=f"Reporte en estado {job.status}")
    expires = job.expires_at
    if expires is not None and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires and expires < utcnow():
        raise HTTPException(status_code=410, detail="Reporte expirado")
    log_action(
        db,
        action="report.download",
        entity_type="report_job",
        actor_id=user.id,
        actor_email=user.email,
        entity_id=str(job.id),
    )
    fmt = str((job.filters_json or {}).get("format", "csv"))
    suffix = Path(job.file_ref).suffix.lstrip(".") or fmt
    return FileResponse(
        job.file_ref,
        media_type=MIME_TYPES.get(suffix, MIME_TYPES["csv"]),
        filename=f"{job.report_type}_{job.id}.{suffix}",
    )
