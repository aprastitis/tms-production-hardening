# ASSUMES: 401 with {"detail":"missing_token"} on missing/invalid bearer; stashes user_id on request.state.
import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.security import decode_token


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise _unauthorized("missing_token")
    token = auth.removeprefix("Bearer ").strip()
    if not token:
        raise _unauthorized("missing_token")
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise _unauthorized("invalid_token")
    except jwt.InvalidTokenError:
        raise _unauthorized("invalid_token")
    if payload.get("type") != "access":
        raise _unauthorized("invalid_token")
    sub = payload.get("sub")
    if not sub:
        raise _unauthorized("invalid_token")
    try:
        user_id = int(sub)
    except (TypeError, ValueError):
        raise _unauthorized("invalid_token")
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise _unauthorized("invalid_token")
    request.state.user_id = user_id
    return user