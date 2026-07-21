"""Password hashing (Argon2id) and JWT (HS256) primitives."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError

from app.config import get_settings


# Argon2id with default parameters (time_cost=3, memory_cost=64MB, parallelism=4).
# Output PHC string begins with "$argon2id$..." which is the acceptance test fixture.
_hasher = PasswordHasher()


class JWTError(Exception):
    """Raised when a token is invalid, expired, or of the wrong type."""


def hash_password(plaintext: str) -> str:
    return _hasher.hash(plaintext)


def verify_password(plaintext: str, hashed: str) -> bool:
    try:
        _hasher.verify(hashed, plaintext)
        return True
    except (VerifyMismatchError, InvalidHashError):
        return False


def needs_rehash(hashed: str) -> bool:
    """Return True if the stored hash should be upgraded to current params."""
    return _hasher.check_needs_rehash(hashed)


def _encode(payload: dict[str, Any]) -> str:
    settings = get_settings()
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def mint_access_token(user_id: int, username: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "username": username,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.JWT_ACCESS_TTL_MIN)).timestamp()),
        "type": "access",
    }
    return _encode(payload)


def mint_refresh_token(user_id: int, jti: str | None = None) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=settings.JWT_REFRESH_TTL_DAYS)).timestamp()),
        "type": "refresh",
    }
    if jti is not None:
        payload["jti"] = jti
    return _encode(payload)


def decode_token(token: str, expected_type: str = "access") -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as exc:
        raise JWTError("token_expired") from exc
    except jwt.InvalidTokenError as exc:
        raise JWTError("invalid_token") from exc
    if payload.get("type") != expected_type:
        raise JWTError("wrong_token_type")
    return payload