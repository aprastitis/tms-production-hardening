from datetime import timedelta, date
from decimal import Decimal
from typing import Optional, List, Tuple

from sqlalchemy.orm import Session

from .models import Source, InternalTransaction, ExternalTransaction, Match, Flag, ReasonCode, FlagStatus
from .fx import convert


def _business_days_window(d: date, window_days: int) -> Tuple[date, date]:
    return (d - timedelta(days=window_days * 2), d + timedelta(days=window_days * 2))


def match_external(db: Session, external: ExternalTransaction, source: Source) -> Optional[Match]:
    """Try to find an internal transaction that matches the external one.
    Returns Match if matched, None otherwise.
    """
    lo, hi = _business_days_window(external.value_date, source.date_window_days)
    candidates = (
        db.query(InternalTransaction)
        .filter(
            InternalTransaction.source_id == source.id,
            InternalTransaction.value_date >= lo,
            InternalTransaction.value_date <= hi,
            InternalTransaction.reference == external.reference,
        )
        .all()
    )
    if not candidates:
        return None
    ext_usd = external.amount_usd
    for cand in candidates:
        cand_usd = convert(db, cand.amount, cand.currency, "USD", cand.value_date)
        if cand_usd is None:
            continue
        if cand_usd == 0:
            continue
        diff = abs(ext_usd - cand_usd) / cand_usd
        if diff <= source.amount_tolerance_pct:
            m = Match(
                internal_txn_id=cand.id,
                external_txn_id=external.id,
                score=Decimal("1.0") - diff,
            )
            db.add(m)
            return m
    return None


def open_flag(db: Session, external: ExternalTransaction, reason_code_str: str, note: Optional[str] = None) -> Flag:
    rc = db.query(ReasonCode).filter(ReasonCode.code == reason_code_str).one()
    flag = Flag(
        external_txn_id=external.id,
        reason_code_id=rc.id,
        status=FlagStatus.OPEN,
        note=note,
    )
    db.add(flag)
    db.flush()
    return flag