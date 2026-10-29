def test_report_events_flow(client, admin_headers):
    res = client.post(
        "/api/v1/reports",
        headers=admin_headers,
        json={"report_type": "events", "min_magnitude": 0},
    )
    assert res.status_code == 201, res.text
    report_id = res.json()["id"]

    # TestClient ejecuta las tareas en segundo plano de forma sincrona.
    download = client.get(f"/api/v1/reports/{report_id}", headers=admin_headers)
    assert download.status_code == 200
    text = download.text
    assert "generado_utc" in text
    assert "tipo_reporte" in text
    assert "filtros" in text


def test_report_requires_permission_for_guest(client):
    assert client.get("/api/v1/reports").status_code == 401


def test_dataset_quality_report(client, admin_headers):
    res = client.post(
        "/api/v1/datasets",
        headers=admin_headers,
        json={"name": "ds-calidad-test", "min_magnitude": 0},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["version"] >= 1
    assert "missing_magnitude_pct" in body["quality_report"]
    assert "duplicate_external_ids" in body["quality_report"]

    quality = client.get(f"/api/v1/datasets/{body['id']}/quality", headers=admin_headers)
    assert quality.status_code == 200
    assert quality.json()["dataset"] == body["name"]
