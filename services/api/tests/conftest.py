from __future__ import annotations

import os
import sys
from pathlib import Path

# Entorno de pruebas: SQLite en archivo temporal, antes de importar la app.
os.environ["DATABASE_URL"] = "sqlite:///./test_sismo.sqlite3"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["SEED_ADMIN_PASSWORD"] = "admin-test-123"
os.environ["ARTIFACTS_DIR"] = "var/artifacts-test"
os.environ["REPORTS_DIR"] = "var/reports-test"

SERVICES_DIR = Path(__file__).resolve().parents[2]  # .../services
for extra in (SERVICES_DIR / "api", SERVICES_DIR):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402

ADMIN_EMAIL = "admin@sismoplatform.pe"
ADMIN_PASSWORD = "admin-test-123"


@pytest.fixture(scope="session", autouse=True)
def _database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def admin_headers(client):
    res = client.post(
        "/api/v1/auth/login",
        data={"username": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert res.status_code == 200, res.text
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
