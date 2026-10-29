"""Administracion de usuarios y roles (Fase 2/8)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import log_action
from app.db import get_db
from app.models import User
from app.schemas import UserCreate, UserRoleUpdate, UserOut
from app.security import ALL_ROLES, hash_password, require

router = APIRouter(prefix="/api/v1/users", tags=["usuarios"])


@router.get("", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    _: object = Depends(require("users:read")),
):
    return db.scalars(select(User).order_by(User.created_at.desc())).all()


@router.post("", response_model=UserOut, status_code=201)
def create_user(
    payload: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require("users:write")),
):
    invalid = [r for r in payload.roles if r not in ALL_ROLES]
    if invalid:
        raise HTTPException(status_code=422, detail=f"Roles invalidos: {invalid}")
    if db.scalar(select(User).where(User.email == payload.email)):
        raise HTTPException(status_code=409, detail="Correo ya registrado")
    user = User(
        full_name=payload.full_name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        roles=payload.roles,
        status="active",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    log_action(
        db,
        action="user.create",
        entity_type="user",
        actor_id=actor.id,
        actor_email=actor.email,
        entity_id=str(user.id),
        after={"email": user.email, "roles": user.roles},
        request=request,
    )
    return user


@router.patch("/{user_id}/roles", response_model=UserOut)
def update_roles(
    user_id: uuid.UUID,
    payload: UserRoleUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require("users:write")),
):
    invalid = [r for r in payload.roles if r not in ALL_ROLES]
    if invalid:
        raise HTTPException(status_code=422, detail=f"Roles invalidos: {invalid}")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    before = {"roles": user.roles}
    user.roles = payload.roles
    db.commit()
    db.refresh(user)
    log_action(
        db,
        action="user.roles.update",
        entity_type="user",
        actor_id=actor.id,
        actor_email=actor.email,
        entity_id=str(user.id),
        before=before,
        after={"roles": user.roles},
        request=request,
    )
    return user


@router.patch("/{user_id}/status", response_model=UserOut)
def update_status(
    user_id: uuid.UUID,
    status: str,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require("users:write")),
):
    if status not in {"active", "disabled"}:
        raise HTTPException(status_code=422, detail="Estado invalido")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    before = {"status": user.status}
    user.status = status
    db.commit()
    db.refresh(user)
    log_action(
        db,
        action="user.status.update",
        entity_type="user",
        actor_id=actor.id,
        actor_email=actor.email,
        entity_id=str(user.id),
        before=before,
        after={"status": user.status},
        request=request,
    )
    return user
