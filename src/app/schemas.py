"""Pydantic v2 request/response schemas.

StrictModel is the base for every INPUT (body/query/path) model. It rejects unknown
fields with a 422 at the API boundary, per the security bar.
"""
from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Any

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    """Base for input models. extra='forbid' makes unknown fields -> 422."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# ---------- Auth ----------

class LoginRequest(StrictModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class RefreshRequest(StrictModel):
    refresh_token: str = Field(min_length=10)


class ChangePasswordRequest(StrictModel):
    new_password: str = Field(min_length=12, max_length=128)


# ---------- Output models (BaseModel, not StrictModel) ----------

class UserPublic(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    role: str
    must_change_password: bool
    is_active: bool


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserPublic


# ---------- Flags ----------

class FlagCreate(StrictModel):
    transaction_id: int = Field(ge=1)
    reason_code: str = Field(min_length=1, max_length=64)
    details: dict = Field(default_factory=dict)


class FlagResolveRequest(StrictModel):
    resolution_note: Optional[str] = Field(default=None, max_length=2000)


class FlagPublic(BaseModel):
    id: int
    transaction_id: int
    reason_code: str
    status: str
    details: dict
    opened_at: datetime
    resolved_at: Optional[datetime] = None
    resolution_note: Optional[str] = None


# ---------- Paginated reads ----------

class TransactionQuery(StrictModel):
    source_id: Optional[int] = Field(default=None, ge=1)
    status: Optional[str] = Field(default=None, max_length=32)
    value_date_from: Optional[date] = None
    value_date_to: Optional[date] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=500)


class Paginated(BaseModel):
    items: List[dict]
    total: int
    page: int
    page_size: int


class DailySummary(BaseModel):
    date: date
    ingested: int
    matched: int
    flag_count: int
    open_count: int
    total_usd: Decimal


class IngestAccepted(BaseModel):
    raw_file_id: int
    rows_accepted: int


class WebhookAccepted(BaseModel):
    raw_file_id: int

# ---------- Aliases for auth.py compatibility ----------
# (Auth.py uses *In/*Out suffix; schemas.py uses *Request/*Public. Map both ways.)
LoginIn = LoginRequest
RefreshIn = RefreshRequest
PasswordChangeIn = ChangePasswordRequest
TokenPairOut = TokenPair
UserOut = UserPublic
