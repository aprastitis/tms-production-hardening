"""Transactions router — paginated read-only list with filters + create."""
from __future__ import annotations

from datetime import date as _date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_user
from app.models import Source, Transaction, TransactionStatus, User
from app.schemas import Paginated, StrictModel

router = APIRouter(prefix="/transactions", tags=["transactions"])


class TransactionCreate(StrictModel):
    source_id: int = Field(ge=1)
    raw_file_id: Optional[int] = Field(default=None, ge=1)
    external_id: str = Field(min_length=1, max_length=128)
    amount: float
    currency: str = Field(min_length=3, max_length=8)
    value_date: _date
    counterparty: Optional[str] = Field(default=None, max_length=255)
    reference: Optional[str] = Field(default=None, max_length=255)
    status: Optional[str] = Field(default="ingested", max_length=32)
    extra: dict = Field(default_factory=dict)


@router.get("", response_model=Paginated)
def list_transactions(
    source_id: Optional[int] = Query(default=None, ge=1),
    status: Optional[str] = Query(default=None, max_length=32),
    value_date_from: Optional[_date] = Query(default=None),
    value_date_to: Optional[_date] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    stmt = select(Transaction)
    if source_id is not None:
        stmt = stmt.where(Transaction.source_id == source_id)
    if status is not None:
        try:
            stmt = stmt.where(Transaction.status == TransactionStatus(status))
        except ValueError:
            pass  # unknown status filter; return empty
    if value_date_from is not None:
        stmt = stmt.where(Transaction.value_date >= value_date_from)
    if value_date_to is not None:
        stmt = stmt.where(Transaction.value_date <= value_date_to)
    total = db.execute(
        select(func.count()).select_from(stmt.subquery())
    ).scalar() or 0
    txs = db.execute(
        stmt.order_by(Transaction.value_date.desc(), Transaction.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()
    items = [
        {
            "id": t.id,
            "source_id": t.source_id,
            "external_id": t.external_id,
            "amount": float(t.amount),
            "currency": t.currency,
            "value_date": t.value_date.isoformat() if t.value_date else None,
            "status": t.status.value if hasattr(t.status, "value") else str(t.status),
            "counterparty": t.counterparty,
        }
        for t in txs
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("", response_model=dict, status_code=201)
def create_transaction(
    body: TransactionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    src = db.get(Source, body.source_id)
    if src is None:
        raise HTTPException(status_code=404, detail="source_not_found")
    # If raw_file_id not provided (or invalid), fall back to the source's
    # most recent raw_file. The Transaction model requires non-null FK.
    rf_id = body.raw_file_id
    if rf_id:
        from app.models import RawFile
        rf = db.get(RawFile, rf_id)
    else:
        from app.models import RawFile
        rf = db.execute(
            select(RawFile).where(RawFile.source_id == body.source_id)
            .order_by(RawFile.id.desc()).limit(1)
        ).scalar_one_or_none()
    if rf is None:
        raise HTTPException(
            status_code=422,
            detail="no_raw_file_for_source:ingest_first",
        )
    try:
        st = TransactionStatus(body.status or "ingested")
    except ValueError:
        st = TransactionStatus.INGESTED
    t = Transaction(
        source_id=body.source_id,
        raw_file_id=rf.id,
        external_id=body.external_id,
        amount=body.amount,
        currency=body.currency,
        value_date=body.value_date,
        counterparty=body.counterparty,
        reference=body.reference,
        status=st,
        extra=body.extra or {},
        created_at=datetime.utcnow(),
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return {"transaction_id": t.id}