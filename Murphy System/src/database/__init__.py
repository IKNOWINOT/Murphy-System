# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL-1.1
"""
Unified database initialization for Murphy System.

This package coordinates the two database subsystems so they always use the
same connection string:

* ``src/db.py``                         — SQLAlchemy ORM layer
* ``src/integrations/database_connectors.py`` — raw SQL connector layer

Environment variables
---------------------
DATABASE_URL : str
    SQLAlchemy connection URL.  When unset, defaults to
    ``sqlite:///murphy_logs.db`` (SQLite, suitable for development only).
MURPHY_DB_MODE : str
    ``stub`` (default) — raw SQL connector returns fake data.
    ``live``           — raw SQL connector uses the same DATABASE_URL.
    In ``production`` / ``staging`` environments, ``stub`` raises a
    ``RuntimeError`` at import time.
MURPHY_AUTO_MIGRATE : str
    When ``true`` (default in development/test), pending Alembic migrations
    are applied automatically on startup.  Set to ``false`` in
    production/staging where you prefer explicit migration control.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared connection URL (single source of truth)
# ---------------------------------------------------------------------------

DATABASE_URL: str = os.environ.get(
    "DATABASE_URL",
    os.environ.get("MURPHY_DB_URL", "sqlite:///murphy_logs.db"),
)

_MURPHY_ENV: str = os.environ.get("MURPHY_ENV", "development").lower()
_PRODUCTION_ENVS = {"production", "staging"}

# ---------------------------------------------------------------------------
# Auto-migration default: True for dev/test, False for production/staging
# ---------------------------------------------------------------------------

_AUTO_MIGRATE_DEFAULT = "false" if _MURPHY_ENV in _PRODUCTION_ENVS else "true"
MURPHY_AUTO_MIGRATE: bool = (
    os.environ.get("MURPHY_AUTO_MIGRATE", _AUTO_MIGRATE_DEFAULT).lower() == "true"
)


def init_database(
    *,
    run_migrations: Optional[bool] = None,
    create_tables_fallback: bool = True,
) -> dict:
    """Initialise both database subsystems from a single DATABASE_URL.

    This function is the canonical entry-point for all database setup.  It:

    1. Ensures the ORM engine (``src.db``) and the raw-SQL connector
       (``src.integrations.database_connectors``) use the same
       ``DATABASE_URL``.
    2. Optionally runs pending Alembic migrations (when ``run_migrations``
       is ``True`` or ``MURPHY_AUTO_MIGRATE=true``).
    3. Falls back to ``Base.metadata.create_all()`` when Alembic is
       unavailable (e.g. first-run without alembic installed).

    Parameters
    ----------
    run_migrations:
        Override the ``MURPHY_AUTO_MIGRATE`` env variable.  ``None`` means
        "use the env variable".
    create_tables_fallback:
        When ``True`` (default), call ``create_tables()`` if Alembic
        migration fails or is unavailable.

    Returns
    -------
    dict
        A status dict with keys ``orm``, ``migrations``, ``db_mode``, and
        optionally ``error``.
    """
    status: dict = {
        "orm": "not_initialized",
        "migrations": "skipped",
        "db_mode": os.environ.get("MURPHY_DB_MODE", "stub").lower(),
        "database_url": _redact_url(DATABASE_URL),
    }

    # ── ORM initialisation ───────────────────────────────────────────────
    try:
        from src.db import create_tables, DATABASE_URL as orm_url  # noqa: PLC0415

        # Verify both subsystems share the same URL
        if orm_url != DATABASE_URL:
            logger.warning(
                "DATABASE_URL mismatch: unified layer uses %r, ORM uses %r — "
                "check that DATABASE_URL env var is set before importing src.db",
                _redact_url(DATABASE_URL),
                _redact_url(orm_url),
            )

        create_tables()
        status["orm"] = "ok"
        logger.info("ORM tables ensured (url=%s)", _redact_url(DATABASE_URL))
    except Exception as exc:
        status["orm"] = "error"
        status["error"] = str(exc)
        logger.error("ORM initialisation failed: %s", exc)

    # ── Alembic migrations ───────────────────────────────────────────────
    should_migrate = run_migrations if run_migrations is not None else MURPHY_AUTO_MIGRATE

    if should_migrate:
        migration_status = run_pending_migrations()
        status["migrations"] = migration_status
    else:
        logger.debug(
            "Auto-migrations disabled (MURPHY_AUTO_MIGRATE=%s, env=%s). "
            "Run 'scripts/db_migrate.sh' or set MURPHY_AUTO_MIGRATE=true.",
            os.environ.get("MURPHY_AUTO_MIGRATE", _AUTO_MIGRATE_DEFAULT),
            _MURPHY_ENV,
        )

    return status


def run_pending_migrations() -> str:
    """Run any pending Alembic migrations.

    Uses the Alembic Python API so it works programmatically without
    shelling out.  The ``alembic.ini`` must be present in the Murphy
    System project root.

    Returns
    -------
    str
        ``"ok"`` — migrations ran (or were already up-to-date).
        ``"skipped"`` — Alembic not installed or ``alembic.ini`` not found.
        ``"error"`` — migrations failed (details logged at ERROR level).
    """
    try:
        import alembic.config  # noqa: PLC0415
        from alembic import command as alembic_command  # noqa: PLC0415
    except ImportError:
        logger.warning(
            "Alembic not installed — skipping automatic migrations. "
            "Install with: pip install alembic"
        )
        return "skipped"

    # Locate alembic.ini relative to this file: src/database/ → project root
    _here = os.path.dirname(os.path.abspath(__file__))
    alembic_ini = os.path.join(_here, "..", "..", "alembic.ini")
    alembic_ini = os.path.normpath(alembic_ini)

    if not os.path.isfile(alembic_ini):
        logger.warning(
            "alembic.ini not found at %s — skipping automatic migrations.",
            alembic_ini,
        )
        return "skipped"

    try:
        cfg = alembic.config.Config(alembic_ini)
        # Always use the runtime DATABASE_URL, not the ini default
        cfg.set_main_option("sqlalchemy.url", DATABASE_URL)

        # Check if any migrations are pending before running
        pending = _get_pending_migrations(cfg)
        if pending is None:
            # Could not determine pending migrations; run upgrade anyway
            alembic_command.upgrade(cfg, "head")
            logger.info("Alembic migrations applied (url=%s)", _redact_url(DATABASE_URL))
        elif len(pending) == 0:
            logger.info("Alembic: database is already up-to-date.")
        else:
            logger.info(
                "Alembic: applying %d pending migration(s): %s",
                len(pending),
                pending,
            )
            alembic_command.upgrade(cfg, "head")
            logger.info(
                "Alembic migrations complete (url=%s)", _redact_url(DATABASE_URL)
            )
        return "ok"
    except Exception as exc:
        logger.error("Alembic migration failed: %s", exc)
        return "error"


def _get_pending_migrations(cfg: "alembic.config.Config") -> "Optional[list]":
    """Return a list of pending Alembic revision IDs, or None on error."""
    try:
        from alembic.runtime.migration import MigrationContext  # noqa: PLC0415
        from alembic.script import ScriptDirectory  # noqa: PLC0415
        from sqlalchemy import create_engine  # noqa: PLC0415

        script = ScriptDirectory.from_config(cfg)
        url = cfg.get_main_option("sqlalchemy.url")

        connect_args: dict = {}
        if url and url.startswith("sqlite"):
            connect_args["check_same_thread"] = False

        engine = create_engine(url, connect_args=connect_args)
        with engine.connect() as conn:
            migration_ctx = MigrationContext.configure(conn)
            current_heads = set(migration_ctx.get_current_heads())
            all_heads = set(script.get_heads())
            if current_heads == all_heads:
                return []
            # Collect revisions between current and head
            pending = []
            for rev in script.walk_revisions():
                if rev.revision not in current_heads:
                    pending.append(rev.revision)
            return pending
    except Exception as exc:
        logger.debug("Could not determine pending migrations: %s", exc)
        return None


def get_database_status() -> dict:
    """Return a status snapshot of both database subsystems.

    Suitable for inclusion in health-check responses.

    Returns
    -------
    dict
        Keys: ``db_mode``, ``orm``, ``database_url`` (redacted), and
        optionally ``pool`` (connection-pool stats).
    """
    db_mode = os.environ.get("MURPHY_DB_MODE", "stub").lower()
    status: dict = {
        "db_mode": db_mode,
        "database_url": _redact_url(DATABASE_URL),
    }

    if db_mode == "stub":
        status["orm"] = "stub"
        return status

    try:
        from src.db import check_database, get_pool_status  # noqa: PLC0415
        status["orm"] = check_database()
        try:
            status["pool"] = get_pool_status()
        except Exception:
            pass
    except Exception as exc:
        status["orm"] = "error"
        status["error"] = str(exc)

    return status


def _redact_url(url: str) -> str:
    """Replace password in a SQLAlchemy URL with ``***`` for safe logging."""
    try:
        from sqlalchemy.engine import make_url  # noqa: PLC0415
        parsed = make_url(url)
        return parsed.render_as_string(hide_password=True)
    except Exception:
        # Fallback: redact anything between :// and @ if it contains a colon
        import re  # noqa: PLC0415
        return re.sub(r"(:\/\/[^:]+:)[^@]+(@)", r"\1***\2", url)
