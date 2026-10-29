"""Pruebas del canal en vivo (SSE), el alta de fuentes y el filtro de periodo del dashboard."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.audit import AuditLog
from app.db import SessionLocal
from app.models import DataSource, SeismicEvent, User
from app.security import hash_password


def _seed_source(db) -> DataSource:
    source = DataSource(
        name=f"Fuente rt {uuid4().hex[:8]}",
        organization="Test",
        base_url=f"https://example.test/{uuid4().hex[:8]}/query",
        status="ok",
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


def _login(client, email: str, password: str) -> dict:
    res = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _make_user(role: str) -> tuple[str, str]:
    password = f"{role}-pass-123"
    db = SessionLocal()
    try:
        user = User(
            full_name=f"Usuario {role}",
            email=f"{role}-{uuid4().hex[:6]}@test.pe",
            password_hash=hash_password(password),
            roles=[role],
        )
        db.add(user)
        db.commit()
        email = user.email
    finally:
        db.close()
    return email, password


# ---------- Canal en vivo (SSE) ----------


def test_event_stream_greeting_frame(client, admin_headers):
    """El stream contesta de inmediato con trama `hello` y cabeceras SSE."""
    with client.stream("GET", "/api/v1/events/stream", headers=admin_headers, timeout=20) as res:
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("text/event-stream")
        lines = []
        for line in res.iter_lines():
            lines.append(line)
            if line.startswith("data:"):
                break
        frame = next(l for l in lines if l.startswith("data:"))
        payload = json.loads(frame[len("data:"):].strip())
        assert payload["type"] == "hello"
        assert "server_time" in payload

    # sin credenciales no hay canal
    assert client.get("/api/v1/events/stream").status_code == 401


def test_event_stream_emits_inserted_event(client, admin_headers):
    """Un evento insertado mientras el canal esta abierto llega como trama events."""
    db = SessionLocal()
    try:
        source = _seed_source(db)
        external = f"rt-{uuid4().hex}"
    finally:
        db.close()

    with client.stream("GET", "/api/v1/events/stream", headers=admin_headers, timeout=30) as res:
        lines = res.iter_lines()  # un solo iterador: httpx no permite releer el stream

        # 1) trama de bienvenida
        hello = next(l for l in lines if l.startswith("data:"))
        assert json.loads(hello[len("data:"):].strip())["type"] == "hello"

        # 2) llega un evento nuevo (por encima del cursor del stream)
        db = SessionLocal()
        try:
            db.add(SeismicEvent(
                external_id=external,
                source_id=source.id,
                occurred_at=datetime.now(timezone.utc),
                latitude=-12.0,
                longitude=-77.0,
                magnitude=5.5,
                magnitude_type="ml",
                depth_km=40.0,
                place="Lima, Peru",
                region="Peru",
                source_url="https://example.test/event",
            ))
            db.commit()
        finally:
            db.close()

        # 3) el siguiente frame de datos lo contiene (polling: ~3 s)
        seen = None
        for line in lines:
            if not line.startswith("data:"):
                continue
            frame = json.loads(line[len("data:"):].strip())
            if frame.get("type") != "events":
                continue
            ids = [e["external_id"] for e in frame.get("events", [])]
            if external in ids:
                seen = frame
                break
        assert seen is not None, "el canal no emitio el evento insertado"
        emitted = next(e for e in seen["events"] if e["external_id"] == external)
        assert emitted["magnitude"] == 5.5
        assert emitted["source_url"] == "https://example.test/event"


# ---------- Alta de fuentes ----------


def test_create_source_flow_and_audit(client, admin_headers):
    payload = {
        "name": f"Fuente alta {uuid4().hex[:8]}",
        "organization": "Instituto de Prueba",
        "base_url": f"https://alta.test/{uuid4().hex[:8]}/sismos",
        "source_type": "rest",
        "license": "Uso con citacion",
        "contact": "https://example.test",
        "frequency_minutes": 15,
    }
    res = client.post("/api/v1/sources", headers=admin_headers, json=payload)
    assert res.status_code == 201, res.text
    created = res.json()
    assert created["name"] == payload["name"]
    assert created["frequency_minutes"] == 15
    assert created["enabled"] is True
    assert isinstance(created["status"], str)

    # aparece en el listado
    listing = client.get("/api/v1/sources", headers=admin_headers).json()
    assert any(s["id"] == created["id"] for s in listing)

    # queda auditada con autor y valores finales
    db = SessionLocal()
    try:
        entry = db.query(AuditLog).filter(AuditLog.action == "source.create").order_by(
            AuditLog.occurred_at.desc()).first()
        assert entry is not None
        assert entry.actor_email == "admin@sismoplatform.pe"
        assert entry.entity_id == created["id"]
        assert entry.after_json["base_url"] == payload["base_url"]
    finally:
        db.close()

    # duplicados rechazados (mismo nombre en otras mayusculas / mismo endpoint)
    dup_name = client.post("/api/v1/sources", headers=admin_headers,
                           json={**payload, "name": payload["name"].upper(),
                                 "base_url": "https://otro.test/sismos"})
    assert dup_name.status_code == 409
    dup_url = client.post("/api/v1/sources", headers=admin_headers,
                          json={**payload, "name": "Otra fuente"})
    assert dup_url.status_code == 409

    # endpoint que no es http(s) -> validacion 422
    bad_url = client.post("/api/v1/sources", headers=admin_headers,
                          json={**payload, "name": "Fuente mala", "base_url": "ftp://inseguro"})
    assert bad_url.status_code == 422


def test_resolve_sources_accepts_string_id():
    """Regresion: `sync.py --source-id <uuid>` recibe el id como string desde el CLI.

    La API lanza el daemon con `str(source.id)`; antes de normalizarlo, SQLAlchemy
    fallaba con `AttributeError: 'str' object has no attribute 'hex'`.
    """
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # services/
    from ingestion.sync import resolve_sources

    db = SessionLocal()
    try:
        source = _seed_source(db)
        # 1) id en formato string (como llega de la linea de comandos)
        found = resolve_sources(db, str(source.id))
        assert [s.id for s in found] == [source.id]
        # 2) id ya convertido a uuid
        found_uuid = resolve_sources(db, uuid.UUID(str(source.id)))
        assert [s.id for s in found_uuid] == [source.id]
        # 3) id inexistente o corrupto: lista vacia, sin excepcion
        assert resolve_sources(db, str(uuid4())) == []
        assert resolve_sources(db, "no-es-uuid") == []
    finally:
        db.close()


def test_create_source_permissions(client, admin_headers):
    # viewer: ni lectura ni escritura de fuentes
    viewer_email, viewer_password = _make_user("viewer")
    viewer = _login(client, viewer_email, viewer_password)
    viewer_post = client.post("/api/v1/sources", headers=viewer, json={
        "name": "Fuente no permitida",
        "organization": "Test",
        "base_url": "https://denegado.test/sismos",
    })
    assert viewer_post.status_code == 403

    # analyst: puede crear (sources:write)
    analyst_email, analyst_password = _make_user("analyst")
    analyst = _login(client, analyst_email, analyst_password)
    ok = client.post("/api/v1/sources", headers=analyst, json={
        "name": f"Fuente analista {uuid4().hex[:8]}",
        "organization": "Test",
        "base_url": f"https://analista.test/{uuid4().hex[:8]}",
    })
    assert ok.status_code == 201, ok.text

    # sin sesion -> 401
    assert client.post("/api/v1/sources", json={
        "name": "Sin sesion", "organization": "Test", "base_url": "https://sin.test/x",
    }).status_code == 401


# ---------- Filtro de periodo del dashboard ----------


def _window_stats(client, headers, params: dict) -> dict:
    """Cruza el resumen del periodo con la API de eventos para el mismo rango.

    Comprueba la propiedad exigida por el plan: los KPI coinciden con los datos
    que devuelven los endpoints de eventos con idénticos filtros.
    """
    page = client.get("/api/v1/events", headers=headers, params={**params, "limit": 500}).json()
    summary = client.get("/api/v1/dashboard/summary", headers=headers, params=params).json()

    items = page["items"]
    mags = [e["magnitude"] for e in items if e["magnitude"] is not None]
    depths = [e["depth_km"] for e in items if e["depth_km"] is not None]

    assert summary["total_events"] == page["total"], "total distinto al de la API de eventos"
    if mags:
        assert summary["period_max_magnitude"] == max(mags), "mag. maxima no coincide con los eventos"
    else:
        assert summary["period_max_magnitude"] is None
    if depths:
        expected_depth = round(sum(depths) / len(depths), 2)
        assert summary["period_avg_depth"] == expected_depth, "profundidad media no coincide"
    else:
        assert summary["period_avg_depth"] is None

    # La serie temporal del mismo rango debe sumar exactamente esos eventos
    ts = client.get("/api/v1/analytics/timeseries", headers=headers,
                    params={**params, "granularity": "day"}).json()
    assert sum(p["count"] for p in ts) == page["total"]
    return summary


def test_dashboard_summary_period_stats(client, admin_headers):
    db = SessionLocal()
    try:
        source = _seed_source(db)
        base = {"source_id": source.id, "latitude": -12.0, "longitude": -77.0,
                "magnitude_type": "ml", "place": "Lima, Peru", "region": "Peru",
                "source_url": "https://example.test/event"}
        # magnitud 8.5 fuera del rango que siembran las demas pruebas: su presencia
        # en la ventana es verificable de forma inequivoca.
        old_external = f"old-{uuid4().hex}"
        new_external = f"new-{uuid4().hex}"
        db.add(SeismicEvent(external_id=old_external,
                            occurred_at=datetime.now(timezone.utc) - timedelta(days=10),
                            magnitude=8.5, depth_km=500.0, **base))
        db.add(SeismicEvent(external_id=new_external,
                            occurred_at=datetime.now(timezone.utc) - timedelta(days=2),
                            magnitude=3.0, depth_km=10.0, **base))
        db.commit()
    finally:
        db.close()

    # Sin parametros: el periodo por defecto son los ultimos 7 dias y es
    # coherente con el KPI historico de 7 dias.
    default = client.get("/api/v1/dashboard/summary", headers=admin_headers).json()
    assert default["period_max_magnitude"] == default["max_magnitude_7d"]
    assert default["period_start"] is None  # sin rango explicito no hay periodo declarado

    # Ventana que encierra el evento antiguo (mag. 8.5): consistencia total
    now = datetime.now(timezone.utc)
    old_window = {
        "date_from": (now - timedelta(days=11)).isoformat(),
        "date_to": (now - timedelta(days=9)).isoformat(),
    }
    summary_old = _window_stats(client, admin_headers, old_window)
    assert summary_old["period_max_magnitude"] == 8.5
    assert summary_old["total_events"] >= 1

    # Rango amplio (1 anio): el evento de 8.5 sigue mandando en el maximo
    year = {"date_from": (now - timedelta(days=365)).isoformat()}
    summary_year = _window_stats(client, admin_headers, year)
    assert summary_year["period_max_magnitude"] == 8.5
    assert summary_year["total_events"] >= 2

    # Rango corto (5 dias): el evento reciente debe entrar y el antiguo no
    short = {"date_from": (now - timedelta(days=5)).isoformat(),
             "date_to": (now - timedelta(days=1)).isoformat()}
    # Rango corto (5 dias): el evento reciente cae dentro y el antiguo fuera,
    # con las estadisticas del periodo consistentes con la API de eventos.
    summary_short = _window_stats(client, admin_headers, short)
    assert summary_short["period_start"] is not None
    page = client.get("/api/v1/events", headers=admin_headers, params={**short, "limit": 500}).json()
    ids = {e["external_id"] for e in page["items"]}
    assert new_external in ids, "el evento reciente no entra en el rango de 5 dias"
    assert old_external not in ids, "el evento antiguo no debe entrar en el rango de 5 dias"

    # El histograma del mismo rango suma los eventos con magnitud del periodo
    hist = client.get("/api/v1/analytics/magnitude-histogram", headers=admin_headers,
                      params=short).json()
    con_mag = [e for e in page["items"] if e["magnitude"] is not None]
    assert sum(b["count"] for b in hist) == len(con_mag)
