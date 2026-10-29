"""Smoke end-to-end: API + ingesta IGP/CENSIS real + endpoints principales."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
VENV_PY = ROOT / ".venv" / "Scripts" / "python.exe"
DB = ROOT / "var" / "dev.sqlite3"
BASE = "http://127.0.0.1:8000"

ENV = {
    **os.environ,
    "DATABASE_URL": f"sqlite:///{DB}",
    "SECRET_KEY": "dev-smoke",
    "SEED_ADMIN_PASSWORD": "admin-dev-123",
}


def main() -> None:
    for stale in (DB, Path(str(DB) + "-wal"), Path(str(DB) + "-shm")):
        stale.unlink(missing_ok=True)

    server = subprocess.Popen(
        [str(VENV_PY), "-m", "uvicorn", "app.main:app", "--port", "8000", "--log-level", "warning"],
        cwd=str(ROOT / "services" / "api"),
        env=ENV,
    )
    try:
        for _ in range(40):
            try:
                httpx.get(f"{BASE}/health", timeout=2)
                break
            except Exception:
                time.sleep(0.5)

        print("== Ingesta IGP/CENSIS (48 h, mag >= 4.0) ==")
        sync = subprocess.run(
            [str(VENV_PY), str(ROOT / "services" / "ingestion" / "sync.py"), "--hours", "48", "--min-magnitude", "4.0"],
            cwd=str(ROOT / "services"),
            env=ENV,
            capture_output=True,
            text=True,
            timeout=180,
        )
        print(sync.stdout[-500:] or sync.stderr[-800:])

        client = httpx.Client(base_url=BASE, timeout=30)
        login = client.post("/api/v1/auth/login", data={"username": "admin@sismoplatform.pe", "password": "admin-dev-123"})
        print("\n== Login ==", login.status_code)
        login.raise_for_status()
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        events = client.get("/api/v1/events", params={"limit": 3}, headers=headers).json()
        print("== Eventos ==", events["total"], "registros; ultimo:")
        if events["items"]:
            e = events["items"][0]
            print("  ", e["occurred_at"], e["magnitude"], e["magnitude_type"], "-", e["place"], "|", e["source_url"])

        summary = client.get("/api/v1/dashboard/summary", headers=headers).json()
        print("== Dashboard ==", {k: summary[k] for k in ("total_events", "events_last_24h", "max_magnitude_7d", "last_sync_at")})

        ts = client.get("/api/v1/analytics/timeseries", params={"granularity": "day"}, headers=headers).json()
        print("== Serie temporal ==", ts[-3:] if ts else "vacia")

        geo = client.get("/api/v1/events/geojson", params={"min_magnitude": 5.0, "limit": 5}, headers=headers).json()
        print("== GeoJSON ==", len(geo["features"]), "features con mag >= 5")

        rule = client.post("/api/v1/alert-rules", headers=headers, json={
            "name": "smoke-m5", "min_magnitude": 5.5, "severity": "warning",
            "channels": ["console"], "requires_approval": True, "enabled": True,
        })
        print("== Regla de alerta ==", rule.status_code)
    finally:
        server.send_signal(signal.SIGTERM)
        server.wait(timeout=10)
        print("\nServidor detenido.")


if __name__ == "__main__":
    sys.exit(main())
