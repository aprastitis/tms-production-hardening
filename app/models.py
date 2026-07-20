# app/models.py
"""SQLAlchemy ORM models for the Transaction Monitoring System."""
from __future__ import annotations

import enum
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class FlagSeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(str, enum.Enum):
    OPEN = "open"
    UNDER_REVIEW = "under_review"
    CLOSED = "closed"
    ESCALATED = "escalated"


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    external_ref: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    risk_rating: Mapped[str] = mapped_column(String(16), nullable=False, default="standard")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="account")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    counterparty: Mapped[str] = mapped_column(String(255), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    account: Mapped[Account] = relationship(back_populates="transactions")
    flags: Mapped[list["Flag"]] = relationship(back_populates="transaction", cascade="all, delete-orphan")


class Rule(Base):
    __tablename__ = "rules"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(512), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    severity: Mapped[FlagSeverity] = mapped_column(
        SAEnum(FlagSeverity, name="flag_severity"), nullable=False, default=FlagSeverity.MEDIUM
    )


class Flag(Base):
    __tablename__ = "flags"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    transaction_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rule_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("rules.id", ondelete="SET NULL"), nullable=True
    )
    severity: Mapped[FlagSeverity] = mapped_column(
        SAEnum(FlagSeverity, name="flag_severity"), nullable=False, default=FlagSeverity.MEDIUM
    )
    reason: Mapped[str] = mapped_column(String(512), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    transaction: Mapped[Transaction] = relationship(back_populates="flags")


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    flag_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("flags.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[AlertStatus] = mapped_column(
        SAEnum(AlertStatus, name="alert_status"), nullable=False, default=AlertStatus.OPEN
    )
    summary: Mapped[str] = mapped_column(String(512), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )