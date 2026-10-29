"""Datasets versionados con informe de calidad (Fase 5)."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Dataset, SeismicEvent, User
from app.routers.events import apply_event_filters
from app.schemas import DatasetCreate, DatasetOut
from app.security import require

router = APIRouter(prefix="/api/v1/datasets", tags=["datasets"])


def build_quality_report(db: Session, stmt) -> dict:
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    miss_mag = db.scalar(
        select(func.count()).select_from(stmt.with_only_columns(SeismicEvent.id)
        .where(SeismicEvent.magnitude.is_(None)).subquery())
    ) or 0
    miss_depth = db.scalar(
        select(func.count()).select_from(stmt.with_only_columns(SeismicEvent.id)
        .where(SeismicEvent.depth_km.is_(None)).subquery())
    ) or 0
    dups = db.scalars(
        stmt.with_only_columns(SeismicEvent.external_id)
        .group_by(SeismicEvent.external_id)
        .having(func.count() > 1)
    ).all()
    out_of_range = db.scalar(
        select(func.count()).select_from(stmt.with_only_columns(SeismicEvent.id)
        .where((SeismicEvent.magnitude < 0) | (SeismicEvent.magnitude > 10)).subquery())
    ) or 0
    return {
        "rows": total,
        "missing_magnitude_pct": round(100 * miss_mag / total, 2) if total else 0.0,
        "missing_depth_pct": round(100 * miss_depth / total, 2) if total else 0.0,
        "duplicate_external_ids": len(dups),
        "out_of_range_values": out_of_range,
        "cleaning_rules": [
            "Exclusion de eventos sin magnitud ni coordenadas validas",
            "Validacion de rangos lat/lon/profundidad/magnitud por CHECK en BD",
        ],
        "imputation": "sin imputacion: los nulos se excluyen del entrenamiento y se reportan",
    }


@router.post("", response_model=DatasetOut, status_code=201)
def create_dataset(
    payload: DatasetCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require("datasets:write")),
):
    base = apply_event_filters(
        select(SeismicEvent),
        date_from=payload.date_from, date_to=payload.date_to,
        min_magnitude=payload.min_magnitude, max_magnitude=None,
        source_id=payload.source_id, bbox=None, place=None,
    )
    base = base.where(SeismicEvent.magnitude.is_not(None), SeismicEvent.latitude.is_not(None))

    quality = build_quality_report(db, base)
    version = (db.scalar(
        select(func.max(Dataset.version)).where(Dataset.name == payload.name)
    ) or 0) + 1

    periods = db.execute(
        base.with_only_columns(func.min(SeismicEvent.occurred_at), func.max(SeismicEvent.occurred_at))
    ).one()
    dataset = Dataset(
        name=payload.name,
        version=version,
        query_spec={
            "date_from": payload.date_from.isoformat() if payload.date_from else None,
            "date_to": payload.date_to.isoformat() if payload.date_to else None,
            "min_magnitude": payload.min_magnitude,
            "source_id": str(payload.source_id) if payload.source_id else None,
        },
        period_start=periods[0],
        period_end=periods[1],
        row_count=quality["rows"],
        quality_report=quality,
        created_by=user.id,
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    return dataset


@router.get("", response_model=list[DatasetOut])
def list_datasets(
    db: Session = Depends(get_db),
    _: object = Depends(require("datasets:read")),
):
    return db.scalars(select(Dataset).order_by(Dataset.created_at.desc())).all()


@router.get("/{dataset_id}", response_model=DatasetOut)
def get_dataset(
    dataset_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: object = Depends(require("datasets:read")),
):
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset no encontrado")
    return dataset


@router.get("/{dataset_id}/quality")
def dataset_quality(
    dataset_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: object = Depends(require("datasets:read")),
):
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset no encontrado")
    return {
        "dataset": dataset.name,
        "version": dataset.version,
        "period": {"start": dataset.period_start, "end": dataset.period_end},
        "quality_report": dataset.quality_report,
    }
