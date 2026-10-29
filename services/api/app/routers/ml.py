"""Experimentos ML, registro de modelos y estimaciones experimentales (Fase 6)."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import log_action
from app.db import SessionLocal, get_db
from app.models import Dataset, MlExperiment, ModelRegistry, RiskEstimate, SeismicEvent, User, utcnow
from app.schemas import EstimateCreate, EstimateOut, ExperimentCreate, ExperimentOut, ModelOut
from app.security import require

router = APIRouter(prefix="/api/v1", tags=["ml"])

EXPERIMENTALDisclaimer = (
    "Estimacion experimental generada por un modelo de machine learning sobre datos historicos "
    "reportados. No es una prediccion de terremotos ni un aviso oficial. Toda salida identifica "
    "modelo y version."
)


def _train_in_background(experiment_id: str, date_from: str | None, date_to: str | None) -> None:
    """Entrena en un proceso separado para no bloquear el event loop."""
    import subprocess
    import sys
    from pathlib import Path

    train_py = Path(__file__).resolve().parents[3] / "ml" / "train.py"
    cmd = [sys.executable, str(train_py), "--experiment-id", experiment_id]
    if date_from:
        cmd += ["--date-from", date_from]
    if date_to:
        cmd += ["--date-to", date_to]
    subprocess.Popen(cmd, cwd=str(train_py.parents[2]))


@router.post("/ml/experiments", response_model=ExperimentOut, status_code=202)
def create_experiment(
    payload: ExperimentCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require("ml:train")),
):
    if payload.task_type == "classification" and payload.algorithm not in {
        "random_forest", "logistic_regression", "baseline_dummy",
    }:
        raise HTTPException(status_code=422, detail="Algoritmo no soportado para clasificacion")
    if payload.task_type == "regression" and payload.algorithm not in {"random_forest", "linear_regression", "baseline_dummy"}:
        raise HTTPException(status_code=422, detail="Algoritmo no soportado para regresion")

    experiment = MlExperiment(
        name=payload.name,
        task_type=payload.task_type,
        algorithm=payload.algorithm,
        dataset_id=payload.dataset_id,
        target_name="mag_band" if payload.task_type == "classification" else "depth_km",
        status="running",
        limitations="Entrenamiento en curso; las limitaciones se registran al finalizar.",
    )
    db.add(experiment)
    db.commit()
    db.refresh(experiment)

    log_action(
        db,
        action="ml.experiment.create",
        entity_type="ml_experiment",
        actor_id=user.id,
        actor_email=user.email,
        entity_id=str(experiment.id),
        after={"task_type": payload.task_type, "algorithm": payload.algorithm},
        request=request,
    )
    background_tasks.add_task(
        _train_in_background,
        str(experiment.id),
        payload.date_from.isoformat() if payload.date_from else None,
        payload.date_to.isoformat() if payload.date_to else None,
    )
    return experiment


@router.get("/ml/experiments", response_model=list[ExperimentOut])
def list_experiments(
    db: Session = Depends(get_db),
    _: object = Depends(require("ml:read")),
):
    return db.scalars(select(MlExperiment).order_by(MlExperiment.created_at.desc())).all()


@router.get("/ml/experiments/{experiment_id}", response_model=ExperimentOut)
def get_experiment(
    experiment_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: object = Depends(require("ml:read")),
):
    exp = db.get(MlExperiment, experiment_id)
    if exp is None:
        raise HTTPException(status_code=404, detail="Experimento no encontrado")
    return exp


@router.get("/ml/models", response_model=list[ModelOut])
def list_models(
    db: Session = Depends(get_db),
    _: object = Depends(require("ml:read")),
):
    return db.scalars(select(ModelRegistry).order_by(ModelRegistry.created_at.desc())).all()


@router.post("/ml/models/{model_id}/approve", response_model=ModelOut)
def approve_model(
    model_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require("models:approve")),
):
    model = db.get(ModelRegistry, model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Modelo no encontrado")
    before = {"status": model.status}
    model.status = "approved"
    model.approved_by = user.id
    model.approved_at = utcnow()
    db.commit()
    db.refresh(model)
    log_action(
        db,
        action="ml.model.approve",
        entity_type="model_registry",
        actor_id=user.id,
        actor_email=user.email,
        entity_id=str(model.id),
        before=before,
        after={"status": model.status},
        request=request,
    )
    return model


@router.post("/ml/models/{model_id}/reject", response_model=ModelOut)
def reject_model(
    model_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require("models:approve")),
):
    model = db.get(ModelRegistry, model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Modelo no encontrado")
    before = {"status": model.status}
    model.status = "rejected"
    model.approved_by = user.id
    model.approved_at = utcnow()
    db.commit()
    db.refresh(model)
    log_action(
        db,
        action="ml.model.reject",
        entity_type="model_registry",
        actor_id=user.id,
        actor_email=user.email,
        entity_id=str(model.id),
        before=before,
        after={"status": model.status},
        request=request,
    )
    return model


def _load_events(db: Session, area_code: str, since: datetime):
    """Eventos recientes; area_code PER limita a la ventana temporal (cobertura global por fuente)."""
    stmt = select(SeismicEvent).where(
        SeismicEvent.occurred_at >= since,
        SeismicEvent.magnitude.is_not(None),
        SeismicEvent.depth_km.is_not(None),
    ).order_by(SeismicEvent.occurred_at)
    return db.scalars(stmt).all()


@router.post("/ml/estimates", response_model=EstimateOut, status_code=201)
def publish_estimate(
    payload: EstimateCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require("estimates:write")),
):
    model = db.get(ModelRegistry, payload.model_id)
    if model is None or model.status != "approved":
        raise HTTPException(status_code=409, detail="Solo modelos aprobados pueden publicar estimaciones")

    import sys
    from pathlib import Path

    _services = Path(__file__).resolve().parents[3]
    if str(_services) not in sys.path:
        sys.path.insert(0, str(_services))

    from ml.train import FEATURES, build_feature_frame, load_artifact  # import tardio (paquete ml)

    experiment = db.get(MlExperiment, model.experiment_id)
    since = datetime.now(timezone.utc) - timedelta(hours=payload.window_hours)
    events = _load_events(db, payload.area_code, since)
    if not events:
        raise HTTPException(status_code=409, detail="Sin eventos en la ventana para estimar")

    frame = build_feature_frame(events)[FEATURES].dropna()
    if experiment.task_type == "classification":
        clf = load_artifact(experiment.artifact_uri)
        proba = clf.predict_proba(frame)
        classes = list(getattr(clf, "classes_", []))
        # Probabilidad de banda moderada o superior (indice 1+)
        idx = [i for i, c in enumerate(classes) if c >= 1]
        value = float(sum(proba[:, i] for i in idx).mean()) if idx else 0.0
        metric = "prob_evento_mayor_o_igual_magnitud_4.5"
    else:
        reg = load_artifact(experiment.artifact_uri)
        preds = reg.predict(frame)
        value = float(preds.mean())
        metric = "profundidad_estimada_media_km"

    estimate = RiskEstimate(
        model_id=model.id,
        area_code=payload.area_code,
        window_start=since,
        window_end=datetime.now(timezone.utc),
        metric_name=metric,
        value=round(value, 4),
        lower_bound=None,
        upper_bound=None,
        disclaimer=f"{EXPERIMENTALDisclaimer} Modelo: {experiment.name} v{model.version} "
                  f"({experiment.algorithm}).",
        is_experimental=True,
    )
    db.add(estimate)
    db.commit()
    db.refresh(estimate)
    log_action(
        db,
        action="estimate.publish",
        entity_type="risk_estimate",
        actor_id=user.id,
        actor_email=user.email,
        entity_id=str(estimate.id),
        after={"metric": metric, "value": estimate.value, "model_id": str(model.id)},
        request=request,
    )
    return estimate





@router.get("/estimates", response_model=list[EstimateOut])
def list_estimates(
    db: Session = Depends(get_db),
    _: object = Depends(require("estimates:read")),
    limit: int = 50,
):
    return db.scalars(select(RiskEstimate).order_by(RiskEstimate.calculated_at.desc()).limit(limit)).all()
