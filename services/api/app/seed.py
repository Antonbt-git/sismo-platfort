"""Semilla inicial: roles, usuario administrador y fuente oficial IGP/CENSIS por defecto."""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import DataSource, Role, User, UserRole
from app.security import ALL_ROLES, hash_password

logger = logging.getLogger(__name__)

IGP_SOURCE = {
    "name": "IGP / CENSIS (Centro Sismológico Nacional)",
    "organization": "Instituto Geofísico del Perú (IGP)",
    "base_url": "https://censis.igp.gob.pe/api/ultimo-sismo/sismos",
    "source_type": "rest",
    "license": "Información oficial del Estado peruano (CENSIS/IGP): citar fuente y enlace de procedencia",
    "contact": "https://www.igp.gob.pe",
    "frequency_minutes": 5,
}


def seed_all(db: Session) -> None:
    settings = get_settings()

    for role_name in ALL_ROLES:
        if db.scalar(select(Role).where(Role.name == role_name)) is None:
            db.add(Role(name=role_name))
    db.flush()

    admin = db.scalar(select(User).where(User.email == settings.seed_admin_email))
    if admin is None:
        admin = User(
            full_name="Administrador",
            email=settings.seed_admin_email,
            password_hash=hash_password(settings.seed_admin_password),
            roles=["admin"],
        )
        db.add(admin)
        db.flush()
        admin_role = db.scalar(select(Role).where(Role.name == "admin"))
        db.add(UserRole(user_id=admin.id, role_id=admin_role.id))
        logger.warning("Usuario administrador creado: %s (cambie la contraseña)", settings.seed_admin_email)

    if db.scalar(select(DataSource).where(DataSource.name == IGP_SOURCE["name"])) is None:
        db.add(DataSource(**IGP_SOURCE, status="unknown", enabled=True))

    # Limpieza de la fuente legada USGS: la plataforma opera unicamente con IGP/CENSIS.
    legacy = db.scalars(select(DataSource).where(DataSource.name.like("%USGS%"))).all()
    for source in legacy:
        logger.warning("Eliminando fuente legada: %s (sus eventos asociados se depuran)", source.name)
        db.delete(source)

    db.commit()
