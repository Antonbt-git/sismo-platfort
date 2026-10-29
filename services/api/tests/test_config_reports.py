"""Pruebas de las capacidades de §6.11 (reportes CSV/XLSX/PDF) y §6.13 (configuracion)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.audit import AuditLog
from app.db import SessionLocal
from app.models import DataSource, SeismicEvent


def _seed_events(db, count: int = 3):
    source = DataSource(
        name=f"Fuente cfg {uuid4().hex[:8]}",
        organization="Test",
        base_url="https://example.test/query",
        status="ok",
    )
    db.add(source)
    db.flush()
    base = datetime.now(timezone.utc) - timedelta(hours=2)
    for i in range(count):
        db.add(SeismicEvent(
            external_id=f"cfg-{uuid4().hex}",
            source_id=source.id,
            occurred_at=base + timedelta(minutes=i),
            latitude=-12.5,
            longitude=-77.0,
            magnitude=5.0 + i,
            magnitude_type="ml",
            depth_km=30.0,
            place="Lima, Peru",
            region="Peru",
            source_url="https://example.test/event",
        ))
    db.commit()


# ---------- Configuracion (§6.13) ----------

def test_config_catalog_and_defaults(client, admin_headers):
    res = client.get("/api/v1/config", headers=admin_headers)
    assert res.status_code == 200
    defs = {d["key"]: d for d in res.json()["definitions"]}
    assert "ingesta_min_magnitude" in defs
    assert "report_retention_days" in defs
    assert defs["ingesta_min_magnitude"]["value"] == defs["ingesta_min_magnitude"]["default"] == 2.5
    assert defs["report_retention_days"]["modified"] is False


def test_config_update_persists_and_audits(client, admin_headers):
    res = client.put("/api/v1/config", headers=admin_headers,
                     json={"values": {"report_retention_days": 3, "ingesta_min_magnitude": 3.5}})
    assert res.status_code == 200, res.text
    defs = {d["key"]: d for d in res.json()["definitions"]}
    assert defs["report_retention_days"]["value"] == 3
    assert defs["report_retention_days"]["modified"] is True
    assert defs["ingesta_min_magnitude"]["value"] == 3.5

    db = SessionLocal()
    try:
        entry = db.query(AuditLog).filter(AuditLog.action == "config.update").order_by(
            AuditLog.occurred_at.desc()).first()
        assert entry is not None
        assert entry.result == "success"
        assert entry.after_json["report_retention_days"] == 3
        assert entry.before_json["report_retention_days"] == 7
    finally:
        db.close()

    # el valor persistido es el que lee el servicio de configuracion
    from app.runtime_config import get_value

    db = SessionLocal()
    try:
        assert get_value(db, "report_retention_days") == 3
        assert get_value(db, "ingesta_min_magnitude") == 3.5
    finally:
        db.close()

    # revertir al valor por defecto elimina la etiqueta "modificado"
    revert = client.put("/api/v1/config", headers=admin_headers,
                        json={"values": {"report_retention_days": 7}})
    defs = {d["key"]: d for d in revert.json()["definitions"]}
    assert defs["report_retention_days"]["value"] == 7
    assert defs["report_retention_days"]["modified"] is False
    assert defs["ingesta_min_magnitude"]["modified"] is True  # sigue en 3.5


def test_config_rejects_unknown_key_and_out_of_range(client, admin_headers):
    unknown = client.put("/api/v1/config", headers=admin_headers, json={"values": {"clave_inexistente": 1}})
    assert unknown.status_code == 400
    assert "desconoc" in unknown.json()["detail"].lower()

    out_of_range = client.put("/api/v1/config", headers=admin_headers,
                              json={"values": {"ingesta_min_magnitude": 42}})
    assert out_of_range.status_code == 400
    assert "maximo" in out_of_range.json()["detail"].lower()

    empty = client.put("/api/v1/config", headers=admin_headers, json={"values": {}})
    assert empty.status_code == 400


def test_config_requires_admin_to_write(client, admin_headers):
    # auditor: puede leer configuracion pero no escribirla
    db = SessionLocal()
    try:
        from app.models import User
        from app.security import hash_password

        auditor = User(full_name="Auditor cfg", email=f"auditor-{uuid4().hex[:6]}@test.pe",
                       password_hash=hash_password("auditor-pass-123"), roles=["auditor"])
        db.add(auditor)
        db.commit()
        email, password = auditor.email, "auditor-pass-123"
    finally:
        db.close()

    login = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    assert client.get("/api/v1/config", headers=headers).status_code == 200
    write = client.put("/api/v1/config", headers=headers, json={"values": {"report_retention_days": 10}})
    assert write.status_code == 403
    assert client.get("/api/v1/config").status_code == 401  # sin token


# ---------- Reportes CSV/XLSX/PDF (§6.11) ----------

def test_report_generation_in_three_formats(client, admin_headers):
    db = SessionLocal()
    try:
        _seed_events(db)
    finally:
        db.close()

    created = {}
    for fmt in ("csv", "xlsx", "pdf"):
        res = client.post("/api/v1/reports", headers=admin_headers,
                          json={"report_type": "events", "min_magnitude": 4.0, "format": fmt})
        assert res.status_code == 201, res.text
        created[fmt] = res.json()["id"]

    downloads = {}
    for fmt, report_id in created.items():
        res = client.get(f"/api/v1/reports/{report_id}", headers=admin_headers)
        assert res.status_code == 200, res.text
        downloads[fmt] = res
        assert res.headers["content-type"].split(";")[0] in {
            "text/csv",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/pdf",
        }

    # contenido verificable por formato
    body_csv = downloads["csv"].content.decode("utf-8")
    assert "generado_utc" in body_csv and "enlace_fuente" in body_csv
    assert "IGP / CENSIS" in body_csv and "registros" in body_csv

    assert downloads["pdf"].content[:5] == b"%PDF-"
    assert downloads["xlsx"].content[:2] == b"PK"  # contenedor OOXML

    # el formato elegido queda registrado en los filtros del trabajo
    listed = client.get("/api/v1/reports", headers=admin_headers).json()
    fmts = {r["id"]: r["filters_json"].get("format") for r in listed}
    assert fmts[created["xlsx"]] == "xlsx" and fmts[created["pdf"]] == "pdf"


def test_report_retention_follows_system_config(client, admin_headers):
    # fija retencion en 2 dias (valor por defecto: 7)
    assert client.put("/api/v1/config", headers=admin_headers,
                      json={"values": {"report_retention_days": 2}}).status_code == 200
    res = client.post("/api/v1/reports", headers=admin_headers, json={"report_type": "alerts", "format": "csv"})
    report_id = res.json()["id"]

    from app.db import SessionLocal as _SL
    from app.models import ReportJob
    import uuid as _uuid

    db = _SL()
    try:
        job = db.get(ReportJob, _uuid.UUID(report_id))
        # el trabajo se genera en background: se espera a que termine
        for _ in range(50):
            db.refresh(job)
            if job.status in {"done", "error"}:
                break
        assert job.status == "done", job.error_summary
        delta = job.expires_at - job.created_at
        assert 1.9 < delta.total_seconds() / 86400 < 2.1, delta
    finally:
        db.close()


def test_report_rejects_unknown_format(client, admin_headers):
    res = client.post("/api/v1/reports", headers=admin_headers,
                      json={"report_type": "events", "format": "doc"})
    assert res.status_code == 422
