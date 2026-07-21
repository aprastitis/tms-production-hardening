"""SQLAlchemy 2.x ORM models for the TMS domain.

This module owns the table-level definition of truth. Alembic autogenerate reads
Base.metadata; seed data is loaded by app.seed.
"""
from __future__ import annotations

import enum
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


# ---------- Enums ----------

class RoleCode(str, enum.Enum):
    ADMIN = "ADMIN"
    OPERATOR = "OPERATOR"
    VIEWER = "VIEWER"


class FlagStatus(str, enum.Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"


class TransactionStatus(str, enum.Enum):
    INGESTED = "INGESTED"
    MATCHED = "MATCHED"
    FLAGGED = "FLAGGED"
    REJECTED = "REJECTED"


class RawFileStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


# ---------- Auth & people ----------

class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255))


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255))
    # Argon2id PHC string; verify with argon2-cffi's PasswordHasher.check
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.utcnow())
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    role: Mapped["Role"] = relationship(lazy="joined")


# ---------- Ingest ----------

class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    parser_type: Mapped[str] = mapped_column(String(32), nullable=False, default="CSV")
    is_webhook_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tolerance_config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.utcnow())


class ReasonCode(Base):
    __tablename__ = "reason_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)


class RawFile(Base):
    __tablename__ = "raw_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    # Idempotency: same source + sha256 already processed returns the existing record
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[RawFileStatus] = mapped_column(
        SAEnum(RawFileStatus, name="raw_file_status"),
        default=RawFileStatus.PENDING,
        nullable=False,
    )
    rows_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_accepted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_rejected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processing_log: Mapped[List[dict]] = mapped_column(JSONB, default=list, nullable=False)
    uploaded_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.utcnow())

    __table_args__ = (
        UniqueConstraint("source_id", "sha256", name="uq_raw_source_sha"),
    )


# ---------- FX ----------

class FXRate(Base):
    __tablename__ = "fx_rates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_currency: Mapped[str] = mapped_column(String(8), nullable=False)
    to_currency: Mapped[str] = mapped_column(String(8), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.utcnow())

    __table_args__ = (
        UniqueConstraint("from_currency", "to_currency", "as_of_date", name="uq_fx_pair_date"),
    )


# ---------- Transactions & matching ----------

class Transaction(Base):
    """External transaction ingested from a Source."""
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    raw_file_id: Mapped[int] = mapped_column(ForeignKey("raw_files.id"), nullable=False, index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    counterparty: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    value_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    reference: Mapped[Optional[str]] = mapped_column(String(255))
    status: Mapped[TransactionStatus] = mapped_column(
        SAEnum(TransactionStatus, name="transaction_status"),
        default=TransactionStatus.INGESTED,
        nullable=False,
        index=True,
    )
    extra: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.utcnow())

    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_tx_source_external"),
        Index("ix_tx_source_value_date", "source_id", "value_date"),
    )


class InternalTransaction(Base):
    """Internal ledger transaction; the matching engine searches here for candidates."""
    __tablename__ = "internal_transactions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    reference: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    counterparty: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    value_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    extra: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.utcnow())


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), nullable=False, index=True)
    internal_transaction_id: Mapped[int] = mapped_column(ForeignKey("internal_transactions.id"), nullable=False, index=True)
    score: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    matched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.utcnow())
    matched_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))

    __table_args__ = (
        UniqueConstraint("transaction_id", "internal_transaction_id", name="uq_match_pair"),
    )


class Flag(Base):
    __tablename__ = "flags"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), nullable=False, index=True)
    reason_code_id: Mapped[int] = mapped_column(ForeignKey("reason_codes.id"), nullable=False, index=True)
    status: Mapped[FlagStatus] = mapped_column(
        SAEnum(FlagStatus, name="flag_status"),
        default=FlagStatus.OPEN,
        nullable=False,
        index=True,
    )
    details: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.utcnow())
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    resolved_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    resolution_note: Mapped[Optional[str]] = mapped_column(Text)


# ---------- Audit ----------

class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    actor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.utcnow(), nullable=False, index=True
    )

# ---------- Refresh tokens ----------

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.utcnow(), nullable=False)
