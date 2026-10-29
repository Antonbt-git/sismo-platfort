"""Aplicacion FastAPI — monitoreo sismico, analitica ML y alertas."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import Base, SessionLocal, engine
from app.routers import alerts, audit, auth, config, dashboard, datasets, events, ml, reports, sources, users
from app.seed import seed_all

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Esquema inicial para desarrollo; produccion usa migraciones Alembic (database/migrations).
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_all(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="API Monitoreo Sismico",
    version="0.1.0",
    description=(
        "Monitoreo de eventos observados, analitica descriptiva, experimentos de ML claramente "
        "etiquetados y alertas operativas trazables. No predice terremotos ni sustituye a los "
        "organismos oficiales (IGP, INDECI, proteccion civil)."
    ),
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def correlation_id(request: Request, call_next):
    corr = request.headers.get("x-correlation-id") or request.headers.get("x-request-id")
    response = await call_next(request)
    if corr:
        response.headers["x-correlation-id"] = corr
    return response


@app.get("/health", tags=["salud"])
def health():
    return {"status": "ok"}


for router in (auth.router, users.router, events.router, dashboard.router, sources.router,
               datasets.router, ml.router, alerts.router, reports.router, audit.router,
               config.router):
    app.include_router(router)
