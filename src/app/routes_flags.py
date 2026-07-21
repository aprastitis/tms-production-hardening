"""Flags router — list, create, resolve."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.audit import write_audit
from app.db import get_db
from app.deps import require_user
from app.models import Flag, FlagStatus, ReasonCode, Transaction, User
from app.schemas import (
    FlagCreate,
    FlagResolveRequest,
    Paginated,
)

router = APIRouter(prefix="/flags", tags=["flags"])


def _to_public(f: Flag, reason_code: str | None) -> dict:
    return {
        "id": f.id,
        "transaction_id": f.transaction_id,
        "reason_code": reason_code or "",
        "status": f.status.value if hasattr(f.status, "value") else str(f.status),
        "details": f.details or {},
        "opened_at": f.opened_at.isoformat() if f.opened_at else None,
        "resolved_at": f.resolved_at.isoformat() if f.resolved_at else None,
        "resolution_note": f.resolution_note,
    }


@router.get("", response_model=Paginated)
def list_flags(
    status: str = Query(default="all", pattern="^(open|resolved|all)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    stmt = select(Flag)
    if status == "open":
        stmt = stmt.where(Flag.status == FlagStatus.OPEN)
    elif status == "resolved":
        stmt = stmt.where(Flag.status == FlagStatus.RESOLVED)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
    flags = db.execute(
        stmt.order_by(Flag.opened_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()
    rc_ids = {f.reason_code_id for f in flags if f.reason_code_id}
    rc_map = {}
    if rc_ids:
        rows = db.execute(
            select(ReasonCode.id, ReasonCode.code).where(ReasonCode.id.in_(rc_ids))
        ).all()
        rc_map = {r[0]: r[1] for r in rows}
    items = [_to_public(f, rc_map.get(f.reason_code_id)) for f in flags]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("", response_model=dict, status_code=201)
def create_flag(
    body: FlagCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    tx = db.get(Transaction, body.transaction_id)
    if tx is None:
        raise HTTPException(status_code=404, detail="transaction_not_found")
    rc = db.execute(
        select(ReasonCode).where(ReasonCode.code == body.reason_code)
    ).scalar_one_or_none()
    if rc is None:
        raise HTTPException(status_code=422, detail="unknown_reason_code")
    flag = Flag(
        transaction_id=body.transaction_id,
        reason_code_id=rc.id,
        status=FlagStatus.OPEN,
        details=body.details or {},
        opened_at=datetime.now(timezone.utc),
    )
    db.add(flag)
    db.flush()
    write_audit(
        db,
        actor_id=user.id,
        event_type="flag.created",
        payload={"flag_id": flag.id, "transaction_id": body.transaction_id,
                 "reason_code": body.reason_code, "details": body.details},
    )
    db.commit()
    db.refresh(flag)
    return {"flag_id": flag.id}


@router.post("/{flag_id}/resolve", response_model=dict)
def resolve_flag(
    flag_id: int,
    body: FlagResolveRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    flag = db.get(Flag, flag_id)
    if flag is None:
        raise HTTPException(status_code=404, detail="flag_not_found")
    if (flag.status.value if hasattr(flag.status, "value") else flag.status) != "open":
        raise HTTPException(status_code=409, detail="flag_already_resolved")
    flag.status = FlagStatus.RESOLVED
    flag.resolved_at = datetime.now(timezone.utc)
    flag.resolved_by_user_id = user.id
    flag.resolution_note = body.resolution_note
    write_audit(
        db,
        actor_id=user.id,
        event_type="flag.resolved",
        payload={"flag_id": flag.id, "resolution_note": body.resolution_note},
    )
    db.commit()
    return {"flag_id": flag.id, "status": "resolved"}