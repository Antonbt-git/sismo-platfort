def test_login_ok(client):
    res = client.post(
        "/api/v1/auth/login",
        data={"username": "admin@sismoplatform.pe", "password": "admin-test-123"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["access_token"]
    assert body["user"]["roles"] == ["admin"]


def test_login_bad_password(client):
    res = client.post(
        "/api/v1/auth/login",
        data={"username": "admin@sismoplatform.pe", "password": "incorrecta"},
    )
    assert res.status_code == 401


def test_me_requires_token(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_with_token(client, admin_headers):
    res = client.get("/api/v1/auth/me", headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["email"] == "admin@sismoplatform.pe"


def test_viewer_cannot_create_users(client, admin_headers):
    # Crear usuario viewer y comprobar que no puede administrar usuarios.
    res = client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "full_name": "Lector",
            "email": "lector@sismoplatform.pe",
            "password": "lector-pass-123",
            "roles": ["viewer"],
        },
    )
    assert res.status_code == 201

    login = client.post(
        "/api/v1/auth/login",
        data={"username": "lector@sismoplatform.pe", "password": "lector-pass-123"},
    )
    viewer_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    forbidden = client.post(
        "/api/v1/users",
        headers=viewer_headers,
        json={"full_name": "X", "email": "x@sismoplatform.pe", "password": "password-123", "roles": ["viewer"]},
    )
    assert forbidden.status_code == 403


def test_audit_records_logins(client, admin_headers):
    res = client.get("/api/v1/audit-logs?action=auth.login", headers=admin_headers)
    assert res.status_code == 200
    assert len(res.json()) >= 2
