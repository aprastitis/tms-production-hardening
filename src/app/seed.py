"""Seed minimal data: admin user, DEFAULT Source, three ReasonCodes.

Idempotent: re-running does not duplicate rows. Run via:
    cd src && python -m app.seed
(or via the container entrypoint that prepends /src to PYTHONPATH).
"""
from __future__ import annotations

import logging
import sys

from sqlalchemy import select

from app.config import get_settings
from app.db import Base, SessionLocal, engine
from app.models import RawFile, RawFileStatus, ReasonCode, Role, Source, User
from app.security import hash_password

# Fail-fast on missing secrets BEFORE we touch the DB.
get_settings()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("seed")

REASON_CODES = [
    ("AMOUNT_MISMATCH", "FX-normalized amount outside tolerance"),
    ("DATE_OUTSIDE_WINDOW", "Value date outside configured business-day window"),
    ("MISSING_COUNTERPARTY", "No internal candidate with matching counterparty"),
]


def main() -> int:
    # In production, alembic upgrade head is the canonical migration step;
    # this is a no-op when tables already exist. We deliberately do NOT
    # call Base.metadata.create_all here because it would race with
    # alembic's table registry and create duplicate enums.
    with SessionLocal() as db:
        role = db.execute(select(Role).where(Role.code == "ADMIN")).scalar_one_or_none()
        if role is None:
            role = Role(code="ADMIN", description="Administrator")
            db.add(role)
            db.flush()
            log.info("created role ADMIN")

        admin = db.execute(select(User).where(User.username == "admin")).scalar_one_or_none()
        if admin is None:
            admin = User(
                username="admin",
                email=None,
                password_hash=hash_password("admin"),
                role_id=role.id,
                is_active=True,
                must_change_password=True,
            )
            db.add(admin)
            log.info("created admin user (must_change_password=true, default password=admin)")
        else:
            log.info("admin user already exists")

        src = db.execute(select(Source).where(Source.code == "DEFAULT")).scalar_one_or_none()
        if src is None:
            src = Source(
                code="DEFAULT",
                name="Default CSV",
                parser_type="CSV",
                is_webhook_enabled=True,
                tolerance_config={"amount_pct": 0.01, "window_days": 2},
            )
            db.add(src)
            log.info("created source DEFAULT")
        else:
            log.info("source DEFAULT already exists")

        for code, desc in REASON_CODES:
            rc = db.execute(select(ReasonCode).where(ReasonCode.code == code)).scalar_one_or_none()
            if rc is None:
                db.add(ReasonCode(code=code, description=desc))
                log.info("created reason code %s", code)

        # Minimal RawFile so transactions can reference it.
        db.flush()  # ensure src.id is populated
        rf = db.execute(select(RawFile).where(RawFile.sha256 == "seed-min")).scalar_one_or_none()
        if rf is None:
            db.add(RawFile(
                source_id=src.id,
                filename="seed.csv",
                content_type="text/csv",
                storage_path="/var/lib/tms/seed.csv",
                sha256="seed-min",
                status=RawFileStatus.PROCESSED,
                rows_total=0,
            ))
            log.info("created raw_file seed.csv")
        else:
            log.info("raw_file seed already exists")

        db.commit()

    log.info("seed complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())