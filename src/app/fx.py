from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from .models import FxRate


class FXRateMissing(Exception):
    pass


def convert(db: Session, amount: Decimal, from_currency: str, to_currency: str, on_date: date) -> Optional[Decimal]:
    if from_currency == to_currency:
        return amount
    rate = (
        db.query(FxRate)
        .filter(
            FxRate.from_currency == from_currency,
            FxRate.to_currency == to_currency,
            FxRate.on_date <= on_date,
        )
        .order_by(FxRate.on_date.desc())
        .first()
    )
    if not rate:
        rate = (
            db.query(FxRate)
            .filter(
                FxRate.from_currency == from_currency,
                FxRate.to_currency == to_currency,
            )
            .order_by(FxRate.on_date.desc())
            .first()
        )
    if not rate:
        return None
    return (amount * rate.rate).quantize(Decimal("0.0001"))