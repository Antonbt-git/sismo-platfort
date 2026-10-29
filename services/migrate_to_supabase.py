"""Migra todos los datos de SQLite (var/dev.sqlite3) a una base PostgreSQL (Supabase).

Uso:
    TARGET_DATABASE_URL="postgresql+psycopg://..." \
    /tmp/opencode/venv/bin/python services/migrate_to_supabase.py

Es idempotente: si un registro ya existe en el destino por su PK, se omite.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

SERVICES_DIR = Path(__file__).resolve().parent  # services/
REPO_DIR = SERVICES_DIR.parent  # raiz del proyecto
API_DIR = SERVICES_DIR / "api"
for extra in (API_DIR, REPO_DIR):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

os.environ.setdefault("SECRET_KEY", "dev-local-secret")

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import (
    Alert,
    AlertDelivery,
    AlertRule,
    AuditLog,
    DataSource,
    Dataset,
    IngestionRun,
    MlExperiment,
    ModelRegistry,
    ReportJob,
    RiskEstimate,
    Role,
    SeismicEvent,
    SystemConfig,
    User,
    UserRole,
)

SQLITE_URL = os.environ.get(
    "SOURCE_DATABASE_URL", f"sqlite:///{REPO_DIR / 'var' / 'dev.sqlite3'}"
)
TARGET_URL = os.environ.get("TARGET_DATABASE_URL") or os.environ.get("DATABASE_URL")
if not TARGET_URL:
    raise SystemExit("Define TARGET_DATABASE_URL (o DATABASE_URL) con la cadena de PostgreSQL.")
if TARGET_URL.startswith("sqlite"):
    raise SystemExit("TARGET_DATABASE_URL debe apuntar a PostgreSQL, no a SQLite.")

src_engine = create_engine(SQLITE_URL)
tgt_engine = create_engine(TARGET_URL, pool_pre_ping=True)

Base.metadata.create_all(bind=tgt_engine)
print("Tablas verificadas/creadas en el destino.")

models_order = [
    Role,
    User,
    UserRole,
    DataSource,
    SeismicEvent,
    IngestionRun,
    Dataset,
    MlExperiment,
    ModelRegistry,
    RiskEstimate,
    AlertRule,
    Alert,
    AlertDelivery,
    AuditLog,
    ReportJob,
    SystemConfig,
]

with Session(src_engine) as ssrc, Session(tgt_engine) as stgt:
    for Model in models_order:
        rows = ssrc.query(Model).all()
        table = Model.__table__
        pk_cols = [c.name for c in table.primary_key.columns]
        existing_keys = {
            row[0] if len(pk_cols) == 1 else tuple(row)
            for row in stgt.execute(select(*(table.c[name] for name in pk_cols)))
        }
        new_rows = []
        for r in rows:
            data = {c.name: getattr(r, c.name) for c in table.columns}
            key = tuple(data[name] for name in pk_cols)
            key = key[0] if len(key) == 1 else key
            if key in existing_keys:
                continue
            new_rows.append(Model(**data))
            existing_keys.add(key)
        for i in range(0, len(new_rows), 200):
            stgt.add_all(new_rows[i : i + 200])
            stgt.commit()
        print(f"{table.name}: {len(rows)} leidas, {len(new_rows)} insertadas")

print("MIGRACION COMPLETA")
