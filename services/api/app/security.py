"""Autenticacion JWT, hashing de contraseñas y autorizacion por rol (Fase 2)."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

ALGORITHM = "HS256"

# Mapeo rol -> endpoints/acciones permitidas (minimo privilegio).
ROLE_PERMISSIONS: dict[str, set[str]] = {
    "admin": {"*"},
    "analyst": {
        "events:read", "dashboard:read", "analytics:read", "datasets:write", "datasets:read",
        "ml:read", "ml:train", "models:approve", "estimates:read", "estimates:write",
        "reports:read", "reports:write", "sources:read", "sources:write", "sources:sync", "audit:read",
    },
    "alert_operator": {
        "events:read", "dashboard:read", "alerts:read", "alerts:write", "alerts:approve",
        "rules:read", "rules:write", "reports:read", "sources:read",
    },
    "auditor": {"events:read", "dashboard:read", "audit:read", "alerts:read", "ml:read",
                "reports:read", "estimates:read", "config:read"},
    "viewer": {"events:read", "dashboard:read", "analytics:read", "reports:read"},
}

ALL_ROLES = list(ROLE_PERMISSIONS.keys())


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user: User) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": str(user.id), "email": user.email, "roles": user.roles or [], "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales invalidas o sesion expirada",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, get_settings().secret_key, algorithms=[ALGORITHM])
        user_id = uuid.UUID(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise credentials_error from None

    user = db.get(User, user_id)
    if user is None or user.status != "active":
        raise credentials_error
    request.state.user_id = str(user.id)
    return user


def user_permissions(user: User) -> set[str]:
    perms: set[str] = set()
    for role in user.roles or []:
        perms |= ROLE_PERMISSIONS.get(role, set())
    return perms


def require(perm: str):
    """Dependencia: verifica que el usuario autenticado tenga el permiso indicado."""

    def checker(user: User = Depends(get_current_user)) -> User:
        if "*" in user_permissions(user) or perm in user_permissions(user):
            return user
        raise HTTPException(status_code=403, detail=f"Permiso requerido: {perm}")

    return checker
