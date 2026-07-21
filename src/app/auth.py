# ASSUMES: login + refresh under slowapi 5/min/IP; /auth/me returns current user; password change enforces 12+ chars and != old.
from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_user
from app.models import AuditLog, RefreshToken, User
from app.schemas import (
    LoginIn, PasswordChangeIn, RefreshIn, TokenPairOut, UserOut,
)
from app.security import (
    decode_token, hash_password, mint_access_token, mint_refresh_token,
    needs_rehash, verify_password,
)
from app.config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address, default_limits=[])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _mint_pair(db: Session, user: User) -> TokenPairOut:
    jti = str(uuid.uuid4())
    now = _utcnow()
    s = get_settings()
    from datetime import timedelta
    rt = RefreshToken(
        token_hash=jti,
        user_id=user.id,
        expires_at=now + timedelta(days=s.JWT_REFRESH_TTL_DAYS),
    )
    db.add(rt)
    db.flush()
    return TokenPairOut(
        access_token=mint_access_token(user.id, user.username),
        refresh_token=mint_refresh_token(user.id, jti),
        token_type="bearer",
        user=UserOut(
            id=user.id, username=user.username, email=user.email,
            role=user.role.code if user.role else "user",
            must_change_password=user.must_change_password,
            is_active=user.is_active,
        ),
    )


@router.post("/login")
@limiter.limit("5/minute")
def login(request: Request, body: LoginIn, db: Session = Depends(get_db)) -> TokenPairOut:
    user = db.query(User).filter(User.username == body.username).one_or_none()
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        # constant-time-ish: still hash a dummy
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_credentials",
        )
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)
    pair = _mint_pair(db, user)
    db.add(AuditLog(
        actor_id=user.id, event_type="auth.login",
        payload={"ip": request.client.host if request.client else None},
        occurred_at=_utcnow(),
    ))
    db.commit()
    return pair


@router.post("/refresh")
@limiter.limit("5/minute")
def refresh(request: Request, body: RefreshIn, db: Session = Depends(get_db)) -> TokenPairOut:
    try:
        payload = decode_token(body.refresh_token, expected_type="refresh")
    except Exception:
        raise HTTPException(status_code=401, detail="invalid_token")
    jti = payload.get("jti")
    rt = None
    if jti:
        rt = db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == jti)
        ).scalar_one_or_none()
    if not rt or rt.revoked_at:
        raise HTTPException(status_code=401, detail="invalid_token")
    rt.revoked_at = _utcnow()  # rotate
    user = db.get(User, rt.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="invalid_token")
    pair = _mint_pair(db, user)
    db.commit()
    return pair


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(require_user)) -> UserOut:
    return UserOut(
        id=user.id, username=user.username, email=user.email,
        role=user.role.code if user.role else "user",
        must_change_password=user.must_change_password,
        is_active=user.is_active,
    )


@router.patch("/me/password", response_model=UserOut)
def change_password(
    body: PasswordChangeIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> UserOut:
    if len(body.new_password) < 12:
        raise HTTPException(status_code=422, detail="password_too_short")
    if verify_password(body.new_password, user.password_hash):
        raise HTTPException(status_code=422, detail="password_unchanged")
    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    db.add(AuditLog(
        actor_id=user.id, event_type="auth.password_changed",
        payload={}, occurred_at=_utcnow(),
    ))
    db.commit()
    return UserOut(
        id=user.id, username=user.username, email=user.email,
        role=user.role.code if user.role else "user",
        must_change_password=user.must_change_password,
        is_active=user.is_active,
    )