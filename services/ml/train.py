"""Entrenamiento reproducible de modelos supervisados (Fase 6).

Preguntas aceptadas (ver docs/Fase0_alcance.md):
- Clasificacion: banda de magnitud de un evento YA reportado (<4.5 / 4.5-6 / >=6).
- Regresion: estimacion de la profundidad reportada a partir de ubicacion y magnitud.

Ambas son descriptivas/academicas: NO anticipan sismos futuros. Particion temporal para
evitar fuga de datos; semilla fija; metricas y limitaciones registradas en ml_experiments.
"""
from __future__ import annotations

import argparse
import io
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))

import joblib  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import sklearn  # noqa: E402
from sklearn.dummy import DummyClassifier, DummyRegressor  # noqa: E402
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor  # noqa: E402
from sklearn.linear_model import LinearRegression, LogisticRegression  # noqa: E402
from sklearn.metrics import (  # noqa: E402
    accuracy_score,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
)
from sklearn.pipeline import Pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import Dataset, MlExperiment, ModelRegistry, SeismicEvent  # noqa: E402

SEED = 42
FEATURES = ["depth_km", "latitude", "longitude", "hour_sin", "hour_cos", "dow_sin", "dow_cos", "prev_24h_count"]
TRAIN_RATIO = 0.8

LIMITACIONES_CLF = (
    "Clasificador de bandas de magnitud sobre eventos ya reportados. Describe registros "
    "existentes; NO predice la ocurrencia, el momento, el lugar ni la magnitud de futuros "
    "sismos. Requiere validacion de especialistas antes de cualquier uso operativo."
)
LIMITACIONES_REG = (
    "Regresion didactica de profundidad reportada. Asociacion numerica sin causalidad "
    "demostrada; NO constituye un indicador de riesgo ni una alerta sismica."
)


def build_feature_frame(events: list) -> pd.DataFrame:
    """Construye el frame de features SOLO con informacion disponible al momento del reporte.

    `prev_24h_count` usa un desplazamiento temporal (ventana hacia atras) para evitar fuga.
    """
    rows = []
    for e in sorted(events, key=lambda x: x.occurred_at):
        ts = e.occurred_at
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        rows.append({
            "occurred_at": ts,
            "depth_km": e.depth_km,
            "latitude": e.latitude,
            "longitude": e.longitude,
            "hour": ts.hour,
            "dow": ts.weekday(),
            "magnitude": e.magnitude,
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=FEATURES)
    epochs = df["occurred_at"].astype("int64").to_numpy() // 10**9
    window = 24 * 3600
    counts = np.searchsorted(epochs, epochs - window, side="left")
    df["prev_24h_count"] = np.arange(len(df)) - counts
    angle_h = 2 * np.pi * df["hour"] / 24
    angle_d = 2 * np.pi * df["dow"] / 7
    df["hour_sin"], df["hour_cos"] = np.sin(angle_h), np.cos(angle_h)
    df["dow_sin"], df["dow_cos"] = np.sin(angle_d), np.cos(angle_d)
    return df


def mag_band(mag: float) -> int:
    if mag < 4.5:
        return 0
    if mag < 6.0:
        return 1
    return 2


def make_model(task_type: str, algorithm: str, seed: int = SEED):
    if task_type == "classification":
        if algorithm == "random_forest":
            return RandomForestClassifier(n_estimators=200, random_state=seed, class_weight="balanced", n_jobs=-1)
        if algorithm == "logistic_regression":
            return Pipeline([("scaler", StandardScaler()), ("clf", LogisticRegression(max_iter=1000, random_state=seed))])
        return DummyClassifier(strategy="most_frequent", random_state=seed)
    if algorithm == "random_forest":
        return RandomForestRegressor(n_estimators=200, random_state=seed, n_jobs=-1)
    if algorithm == "linear_regression":
        return Pipeline([("scaler", StandardScaler()), ("reg", LinearRegression())])
    return DummyRegressor(strategy="mean")


def load_events(db, date_from: datetime | None, date_to: datetime | None,
               min_magnitude: float | None = None, source_id: str | None = None) -> list[SeismicEvent]:
    stmt = select(SeismicEvent).where(
        SeismicEvent.magnitude.is_not(None),
        SeismicEvent.latitude.is_not(None),
        SeismicEvent.depth_km.is_not(None),
    )
    if date_from:
        stmt = stmt.where(SeismicEvent.occurred_at >= date_from)
    if date_to:
        stmt = stmt.where(SeismicEvent.occurred_at <= date_to)
    if min_magnitude is not None:
        stmt = stmt.where(SeismicEvent.magnitude >= min_magnitude)
    if source_id:
        try:
            stmt = stmt.where(SeismicEvent.source_id == uuid.UUID(str(source_id)))
        except (ValueError, TypeError):
            pass
    return list(db.scalars(stmt.order_by(SeismicEvent.occurred_at)).all())


def evaluate_classification(model, X_test: pd.DataFrame, y_test: np.ndarray) -> dict:
    preds = model.predict(X_test)
    return {
        "accuracy": round(float(accuracy_score(y_test, preds)), 4),
        "precision_macro": round(float(precision_score(y_test, preds, average="macro", zero_division=0)), 4),
        "recall_macro": round(float(recall_score(y_test, preds, average="macro", zero_division=0)), 4),
        "f1_macro": round(float(f1_score(y_test, preds, average="macro", zero_division=0)), 4),
        "confusion_matrix": confusion_matrix(y_test, preds).tolist(),
        "classes": ["<4.5", "4.5-6", ">=6"],
    }


def evaluate_regression(model, X_test: pd.DataFrame, y_test: np.ndarray) -> dict:
    preds = model.predict(X_test)
    mse = mean_squared_error(y_test, preds)
    return {
        "mae": round(float(mean_absolute_error(y_test, preds)), 4),
        "rmse": round(float(np.sqrt(mse)), 4),
        "r2": round(float(r2_score(y_test, preds)), 4),
    }


def _parse_iso(value) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None

def train_experiment(
    experiment: MlExperiment,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> MlExperiment:
    settings = get_settings()
    db = SessionLocal()
    try:
        exp = db.get(MlExperiment, experiment.id)
        if exp is None:
            return experiment

        # Si el experimento se vinculo a un dataset preparado, ese dataset define
        # el subconjunto de eventos (periodo, magnitud minima, fuente). Si no hay
        # dataset, se usan las fechas pasadas por CLI (ventana temporal).
        dataset = db.get(Dataset, exp.dataset_id) if exp.dataset_id else None
        if dataset is not None:
            spec = dataset.query_spec or {}
            df_date = _parse_iso(spec.get("date_from")) or date_from
            dt_date = _parse_iso(spec.get("date_to")) or date_to
            min_mag = spec.get("min_magnitude")
            source_id = spec.get("source_id")
        else:
            df_date, dt_date = date_from, date_to
            min_mag, source_id = None, None

        events = load_events(db, df_date, dt_date, min_magnitude=min_mag, source_id=source_id)
        df = build_feature_frame(events)
        df = df.dropna(subset=FEATURES)
        if exp.task_type == "classification":
            df = df[df["magnitude"].notna()]
            df["target"] = df["magnitude"].apply(mag_band)
        else:
            df = df.copy()

        if len(df) < 50:
            exp.status = "failed"
            exp.limitations = f"Insuficientes filas utiles ({len(df)}) para entrenar (minimo 50)."
            db.commit()
            return exp

        split_idx = int(len(df) * TRAIN_RATIO)
        train_df, test_df = df.iloc[:split_idx], df.iloc[split_idx:]
        X_train, X_test = train_df[FEATURES], test_df[FEATURES]
        y_train = train_df["target"] if exp.task_type == "classification" else train_df["depth_km"]
        y_test = test_df["target"] if exp.task_type == "classification" else test_df["depth_km"]

        model = make_model(exp.task_type, exp.algorithm, seed=SEED)
        model.fit(X_train, y_train)

        metrics = (
            evaluate_classification(model, X_test, y_test.to_numpy())
            if exp.task_type == "classification"
            else evaluate_regression(model, X_test, y_test.to_numpy())
        )

        # Baseline de referencia bajo la misma particion.
        baseline = make_model(exp.task_type, "baseline_dummy", seed=SEED)
        baseline.fit(X_train, y_train)
        metrics["baseline_dummy"] = (
            evaluate_classification(baseline, X_test, y_test.to_numpy())
            if exp.task_type == "classification"
            else evaluate_regression(baseline, X_test, y_test.to_numpy())
        )

        artifacts = Path(settings.artifacts_dir).resolve()
        artifacts.mkdir(parents=True, exist_ok=True)
        artifact_path = artifacts / f"{exp.id}.joblib"
        joblib.dump(model, artifact_path)
        artifact_bytes = artifact_path.read_bytes()

        exp.feature_spec = FEATURES
        exp.target_name = "mag_band" if exp.task_type == "classification" else "depth_km"
        exp.params = {
            "seed": SEED,
            "train_ratio": TRAIN_RATIO,
            "algorithm": exp.algorithm,
            "dataset": (
                {"id": str(dataset.id), "name": dataset.name, "version": dataset.version,
                 "rows": dataset.row_count, "query_spec": dataset.query_spec}
                if dataset is not None else None
            ),
            # Ventana efectiva usada: permite reentrenar reproduciendo los mismos datos.
            "window": {
                "date_from": df_date.isoformat() if df_date else None,
                "date_to": dt_date.isoformat() if dt_date else None,
                "rows": int(len(df)),
            },
        }
        exp.metrics = metrics
        exp.validation_spec = {
            "split": "temporal (80% mas antiguo / 20% mas reciente)",
            "train_rows": int(len(train_df)),
            "test_rows": int(len(test_df)),
            "train_period": [str(train_df["occurred_at"].min()), str(train_df["occurred_at"].max())],
            "test_period": [str(test_df["occurred_at"].min()), str(test_df["occurred_at"].max())],
            "source": "dataset preparado" if dataset is not None else "ventana temporal",
        }
        exp.seed = SEED
        exp.library_versions = {
            "scikit-learn": sklearn.__version__,
            "pandas": pd.__version__,
            "numpy": np.__version__,
        }
        exp.status = "completed"
        project_root = Path(__file__).resolve().parents[2]
        try:
            # Ruta relativa a la raiz del proyecto: portable entre entornos.
            exp.artifact_uri = str(artifact_path.relative_to(project_root))
        except ValueError:
            exp.artifact_uri = str(artifact_path)
        exp.artifact_blob = artifact_bytes
        exp.limitations = LIMITACIONES_CLF if exp.task_type == "classification" else LIMITACIONES_REG
        exp.dataset_id = exp.dataset_id

        existing_version = [
            m.version for m in db.scalars(
                select(ModelRegistry).where(ModelRegistry.experiment_id == exp.id)
            )
        ]
        db.add(ModelRegistry(
            experiment_id=exp.id,
            version=(max(existing_version) if existing_version else 0) + 1,
            status="candidate",
            limitations=exp.limitations,
        ))
        db.commit()
        db.refresh(exp)
        return exp
    finally:
        db.close()


def load_artifact(uri: str | None, experiment=None):
    """Carga el modelo desde disco o, si el archivo no existe (contenedor efimero),
    desde la copia guardada en la base de datos (`ml_experiments.artifact_blob`)."""
    if uri:
        p = Path(uri)
        candidates = [p]
        if not p.is_absolute():
            candidates += [
                Path(__file__).resolve().parents[2] / p,  # raiz del proyecto
                Path(__file__).resolve().parents[1] / p,  # services/
                Path(__file__).resolve().parents[1] / "api" / p,  # services/api
            ]
        for c in candidates:
            if c.exists():
                return joblib.load(c)
    blob = getattr(experiment, "artifact_blob", None)
    if blob:
        return joblib.load(io.BytesIO(blob))
    if not uri:
        raise FileNotFoundError("El experimento no tiene artefacto entrenado")
    return joblib.load(Path(uri))


def main() -> None:
    parser = argparse.ArgumentParser(description="Entrenamiento de experimentos ML")
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--date-from", default=None)
    parser.add_argument("--date-to", default=None)
    args = parser.parse_args()

    date_from = datetime.fromisoformat(args.date_from) if args.date_from else None
    date_to = datetime.fromisoformat(args.date_to) if args.date_to else None

    db = SessionLocal()
    try:
        experiment = db.get(MlExperiment, uuid.UUID(args.experiment_id))
        if experiment is None:
            print("Experimento no encontrado", file=sys.stderr)
            sys.exit(1)
    finally:
        db.close()

    result = train_experiment(experiment, date_from=date_from, date_to=date_to)
    print(f"Experimento {result.id} -> {result.status}; metricas: {result.metrics}")


if __name__ == "__main__":
    main()
