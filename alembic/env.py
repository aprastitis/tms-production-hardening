"""Alembic environment.

Reads DATABASE_URL from environment, imports the app's Base.metadata,
and runs migrations against the configured database.
"""
from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make src/ importable so `from app.config import get_settings` resolves
# when alembic is invoked from the repo root (where src/ is).
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Importing settings triggers fail-fast validation of DATABASE_URL
# and SECRET_KEY — alembic refuses to run with bad config too.
from app.config import get_settings  # noqa: E402
from app.db import Base  # noqa: E402

# Import all model modules so their tables register with Base.metadata.
import app.models  # noqa: E402,F401

config = context.config

# Override the empty sqlalchemy.url in alembic.ini with the env value.
# get_settings() is called once at env.py import time — this triggers
# fail-fast validation of DATABASE_URL and SECRET_KEY so alembic refuses
# to run with bad config.
config.set_main_option("sqlalchemy.url", get_settings().DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without a live DB connection (emits SQL)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live DB connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()