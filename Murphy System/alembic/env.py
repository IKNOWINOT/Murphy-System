# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL-1.1
"""
Alembic env.py for Murphy System database migrations.
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

from src.db import Base, DATABASE_URL  # noqa: E402
# Add project root to path so src.db can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.db import Base  # noqa: E402

config = context.config

# Read DATABASE_URL fresh from the environment at runtime so that:
# 1. Tests that monkeypatch DATABASE_URL get the correct value.
# 2. run_pending_migrations() can override via config.set_main_option()
#    without being clobbered by a stale src.db module-level import.
# Priority: env var > alembic.ini default.
_runtime_db_url = (
    os.environ.get("DATABASE_URL")
    or os.environ.get("MURPHY_DB_URL")
    or os.environ.get("MURPHY_ALEMBIC_DB_URL")
)
if _runtime_db_url:
    config.set_main_option("sqlalchemy.url", _runtime_db_url)
# If none of the env vars are set, alembic.ini's sqlalchemy.url is used as-is.

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
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
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
