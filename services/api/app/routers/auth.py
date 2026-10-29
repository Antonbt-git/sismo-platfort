"""Autenticacion (Fase 2)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import log_action
from app.db import get_db
from app.models import User, utcnow
from app.schemas import TokenResponse, UserOut
from app.security import create_access_token, get_current_user, verify_password

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(request: Request, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == form.username))
    if user is None or not verify_password(form.password, user.password_hash):
        log_action(
            db,
            action="auth.login",
            entity_type="user",
            actor_email=form.username,
            result="error",
            request=request,
        )
        raise HTTPException(status_code=401, detail="Credenciales invalidas")
    if user.status != "active":
        raise HTTPException(status_code=403, detail="Usuario deshabilitado")

    user.last_login_at = utcnow()
    db.commit()
    log_action(
        db,
        action="auth.login",
        entity_type="user",
        actor_id=user.id,
        actor_email=user.email,
        entity_id=str(user.id),
        request=request,
    )
    return TokenResponse(access_token=create_access_token(user), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
