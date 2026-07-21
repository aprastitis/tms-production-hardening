"""Reports router — daily summary aggregate."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_user
from app.models import Flag, FlagStatus, RawFile, Transaction, User
from app.schemas import DailySummary

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/daily-summary", response_model=DailySummary)
def daily_summary(
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    """Aggregate for today UTC."""
    today = datetime.now(timezone.utc).date()
    ingested = db.execute(
        select(func.count(RawFile.id)).where(
            func.date(RawFile.uploaded_at) == today
        )
    ).scalar() or 0
    matched = db.execute(
        select(func.count(Transaction.id)).where(
            func.date(Transaction.value_date) == today
        )
    ).scalar() or 0
    flag_count = db.execute(
        select(func.count(Flag.id)).where(
            func.date(Flag.opened_at) == today
        )
    ).scalar() or 0
    open_count = db.execute(
        select(func.count(Flag.id)).where(Flag.status == FlagStatus.OPEN)
    ).scalar() or 0
    total_usd = 0  # not modeled in this build; placeholder (use int to match schema)
    return {
        "date": today,
        "ingested": ingested,
        "matched": matched,
        "flag_count": flag_count,
        "open_count": open_count,
        "total_usd": total_usd,
    }