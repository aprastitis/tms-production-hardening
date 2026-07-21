"""AuditLog write helper."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models import AuditLog


def write_audit(
    db: Session,
    actor_id: Optional[int],
    event_type: str,
    payload: dict,
) -> AuditLog:
    row = AuditLog(
        actor_id=actor_id,
        event_type=event_type,
        payload=payload,
        occurred_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.flush()
    return row