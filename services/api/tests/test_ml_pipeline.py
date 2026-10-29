from datetime import datetime, timedelta, timezone
from uuid import uuid4

from ml.train import train_experiment

from app.db import SessionLocal
from app.models import DataSource, MlExperiment, ModelRegistry, SeismicEvent
from sqlalchemy import select


def _seed_synthetic_events(n: int = 200) -> None:
    db = SessionLocal()
    try:
        source = DataSource(
            name=f"Sintetica {uuid4().hex[:8]}",
            organization="Test",
            base_url="https://example.test",
            status="ok",
        )
        db.add(source)
        db.flush()
        start = datetime.now(timezone.utc) - timedelta(days=200)
        for i in range(n):
            db.add(SeismicEvent(
                external_id=f"syn-{uuid4().hex}",
                source_id=source.id,
                occurred_at=start + timedelta(hours=i * 24),
                latitude=-10 - (i % 20) * 0.2,
                longitude=-75 - (i % 15) * 0.3,
                magnitude=2.5 + (i % 8) * 0.6,
                magnitude_type="ml",
                depth_km=10 + (i % 40) * 2.0,
                place=f"Zona {i % 5}, Peru",
                region="Peru",
                source_url="https://example.test/e",
            ))
        db.commit()
    finally:
        db.close()


def test_classification_experiment_trains(client, admin_headers):
    _seed_synthetic_events()
    res = client.post(
        "/api/v1/ml/experiments",
        headers=admin_headers,
        json={
            "name": f"clf-{uuid4().hex[:6]}",
            "task_type": "classification",
            "algorithm": "random_forest",
        },
    )
    assert res.status_code == 202, res.text
    experiment_id = res.json()["id"]

    # El entrenamiento corre como proceso hijo (subprocess); lo ejecutamos sincrono aqui.
    import uuid as uuid_mod

    db = SessionLocal()
    try:
        exp = db.get(MlExperiment, uuid_mod.UUID(experiment_id))
    finally:
        db.close()
    result = train_experiment(exp)

    assert result.status == "completed"
    assert "accuracy" in result.metrics and "f1_macro" in result.metrics
    assert result.metrics["confusion_matrix"]
    assert result.validation_spec["split"].startswith("temporal")
    assert result.artifact_uri and result.artifact_uri.endswith(".joblib")
    assert "NO predice" in result.limitations

    db = SessionLocal()
    try:
        model = db.scalar(select(ModelRegistry).where(ModelRegistry.experiment_id == result.id))
        assert model is not None and model.status == "candidate"
        model_id = str(model.id)
    finally:
        db.close()

    # Aprobacion y publicacion de estimacion experimental.
    approve = client.post(f"/api/v1/ml/models/{model_id}/approve", headers=admin_headers)
    assert approve.status_code == 200

    estimate = client.post(
        "/api/v1/ml/estimates",
        headers=admin_headers,
        json={"model_id": model_id, "area_code": "TEST", "window_hours": 24 * 250},
    )
    assert estimate.status_code == 201, estimate.text
    body = estimate.json()
    assert body["is_experimental"] is True
    assert "No es una prediccion" in body["disclaimer"]


def test_regression_baseline_comparison(client, admin_headers):
    _seed_synthetic_events()
    db = SessionLocal()
    try:
        exp = MlExperiment(
            name=f"reg-{uuid4().hex[:6]}",
            task_type="regression",
            algorithm="linear_regression",
        )
        db.add(exp)
        db.commit()
        db.refresh(exp)
    finally:
        db.close()

    result = train_experiment(exp)
    assert result.status == "completed"
    for key in ("mae", "rmse", "r2"):
        assert key in result.metrics
        assert key in result.metrics["baseline_dummy"]
