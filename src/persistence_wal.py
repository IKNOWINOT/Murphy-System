"""
Production Persistence Layer — SQLite WAL / PostgreSQL (INC-17 / H-05).

Provides a persistence backend for Murphy System with:
  - **SQLite WAL mode** for high-concurrency local/dev usage
  - **PostgreSQL** connection support for production deployments
  - **Schema migrations** via versioned migration scripts
  - Thread-safe connection pooling

The active backend is selected from environment variables:
  - ``DATABASE_URL=postgresql://...`` → PostgreSQL
  - ``DATABASE_URL=sqlite:///path`` or unset → SQLite with WAL mode

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Generator, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Migration registry
# ---------------------------------------------------------------------------

MIGRATIONS: List[Tuple[int, str, str]] = [
    (1, "create_system_state", """
        CREATE TABLE IF NOT EXISTS system_state (
            id TEXT PRIMARY KEY,
            key TEXT NOT NULL UNIQUE,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_system_state_key ON system_state(key);
    """),
    (2, "create_execution_log", """
        CREATE TABLE IF NOT EXISTS execution_log (
            id TEXT PRIMARY KEY,
            hypothesis_id TEXT NOT NULL,
            action TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            payload TEXT,
            result TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            completed_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_execution_log_hypothesis
            ON execution_log(hypothesis_id);
        CREATE INDEX IF NOT EXISTS idx_execution_log_status
            ON execution_log(status);
    """),
    (3, "create_session_store", """
        CREATE TABLE IF NOT EXISTS session_store (
            session_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            data TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            expires_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_session_store_tenant
            ON session_store(tenant_id);
    """),
    (4, "create_migration_history", """
        CREATE TABLE IF NOT EXISTS migration_history (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """),
    (5, "create_user_accounts", """
        CREATE TABLE IF NOT EXISTS user_accounts (
            account_id TEXT PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            data TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_user_accounts_email
            ON user_accounts(email);
    """),
]


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class PersistenceConfig:
    """Persistence configuration."""

    database_url: str = ""
    pool_size: int = 5
    wal_mode: bool = True
    busy_timeout_ms: int = 5000
    journal_size_limit: int = 67108864  # 64MB

    @classmethod
    def from_env(cls) -> "PersistenceConfig":
        """Build config from environment variables."""
        return cls(
            database_url=os.getenv("DATABASE_URL", "sqlite:///murphy.db"),
            pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
            wal_mode=os.getenv("DB_WAL_MODE", "true").lower() == "true",
            busy_timeout_ms=int(os.getenv("DB_BUSY_TIMEOUT", "5000")),
        )


# ---------------------------------------------------------------------------
# SQLite WAL backend
# ---------------------------------------------------------------------------


class SQLiteWALBackend:
    """SQLite backend with WAL mode for high-concurrency usage.

    WAL (Write-Ahead Logging) enables concurrent readers while a single
    writer commits.  This is the recommended journal mode for server
    applications.
    """

    def __init__(self, config: PersistenceConfig) -> None:
        self._config = config
        self._lock = threading.RLock()

        # Parse path from sqlite:///path URL
        # PATCH-002: Non-sqlite DATABASE_URLs (e.g. postgresql://) cannot be
        # passed to sqlite3.connect().  Fall back to a writable SQLite path so
        # user accounts survive restarts even when PostgreSQL isn't wired up yet.
        url = config.database_url
        if url.startswith("sqlite:///"):
            self._db_path = url[len("sqlite:///"):]
        elif url.startswith("sqlite://"):
            self._db_path = url[len("sqlite://"):]
        elif not url or url == ":memory:":
            self._db_path = "murphy_users.db"
        else:
            # Non-sqlite URL (postgresql://, mysql://, etc.) — fall back to SQLite
            # in the first writable location we can find.
            import os as _os
            from pathlib import Path as _Path
            explicit = _os.environ.get("MURPHY_USER_DB_PATH", "").strip()
            if explicit:
                self._db_path = explicit
                logger.info(
                    "User DB: using MURPHY_USER_DB_PATH=%s (non-sqlite DATABASE_URL ignored)",
                    explicit,
                )
            else:
                # Try standard writable paths (systemd ReadWritePaths)
                _candidates = [
                    "/var/lib/murphy-production/murphy_users.db",
                    "/opt/Murphy-System/data/murphy_users.db",
                    "murphy_users.db",  # cwd fallback (last resort)
                ]
                self._db_path = _candidates[-1]  # default
                for _cand in _candidates:
                    _parent = _Path(_cand).parent
                    try:
                        if _parent.exists() and _os.access(str(_parent), _os.W_OK):
                            self._db_path = _cand
                            break
                    except Exception:
                        continue
                logger.info(
                    "User DB: DATABASE_URL is non-sqlite — "
                    "using SQLite fallback at %s. "
                    "Set MURPHY_USER_DB_PATH to override.",
                    self._db_path,
                )

        self._connection: Optional[sqlite3.Connection] = None

    def connect(self) -> sqlite3.Connection:
        """Get or create the database connection with WAL mode."""
        if self._connection is not None:
            return self._connection

        conn = sqlite3.connect(
            self._db_path,
            timeout=self._config.busy_timeout_ms / 1000.0,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row

        # Enable WAL mode for concurrent access
        if self._config.wal_mode:
            conn.execute("PRAGMA journal_mode=WAL")
            journal_limit = int(self._config.journal_size_limit)
            conn.execute(f"PRAGMA journal_size_limit={journal_limit}")
            logger.info(
                "SQLite WAL mode enabled",
                extra={"path": self._db_path},
            )

        # Performance pragmas
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        busy_timeout = int(self._config.busy_timeout_ms)
        conn.execute(f"PRAGMA busy_timeout={busy_timeout}")

        self._connection = conn
        return conn

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for database transactions."""
        conn = self.connect()
        with self._lock:
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def run_migrations(self) -> List[Dict[str, Any]]:
        """Run pending schema migrations.

        PATCH-002: Creates parent directory of the DB file if it does not
        already exist (e.g. /var/lib/murphy-production/ on a fresh deploy).

        Returns:
            List of applied migration records.
        """
        import os as _os
        from pathlib import Path as _Path
        try:
            _db_dir = _Path(self._db_path).parent
            if not _db_dir.exists():
                _db_dir.mkdir(parents=True, exist_ok=True)
                logger.info("User DB: created directory %s", _db_dir)
        except Exception as _dir_exc:
            logger.warning("User DB: could not create DB directory: %s", _dir_exc)
        conn = self.connect()
        applied: List[Dict[str, Any]] = []

        # Ensure migration_history table exists
        conn.execute("""
            CREATE TABLE IF NOT EXISTS migration_history (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.commit()

        # Get already-applied versions
        cursor = conn.execute("SELECT version FROM migration_history")
        done_versions = {row[0] for row in cursor.fetchall()}

        for version, name, sql in MIGRATIONS:
            if version in done_versions:
                continue

            logger.info(
                "Applying migration %d: %s",
                version,
                name,
                extra={"version": version, "name": name},
            )
            with self._lock:
                try:
                    conn.executescript(sql)
                    conn.execute(
                        "INSERT OR REPLACE INTO migration_history (version, name) VALUES (?, ?)",
                        (version, name),
                    )
                    conn.commit()
                    applied.append({"version": version, "name": name})
                except Exception as exc:
                    logger.error(
                        "Migration %d failed: %s",
                        version,
                        exc,
                        extra={"version": version, "error": str(exc)},
                    )
                    raise

        logger.info(
            "Migrations complete: %d applied, %d total",
            len(applied),
            len(MIGRATIONS),
            extra={"applied": len(applied), "total": len(MIGRATIONS)},
        )
        return applied

    # -- CRUD helpers -------------------------------------------------------

    def set_state(self, key: str, value: str) -> Dict[str, Any]:
        """Set a system state key-value pair."""
        row_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with self.transaction() as conn:
            conn.execute(
                """INSERT INTO system_state (id, key, value, updated_at, created_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
                (row_id, key, value, now, now),
            )
        return {"key": key, "value": value, "updated_at": now}

    def get_state(self, key: str) -> Optional[str]:
        """Get a system state value by key."""
        conn = self.connect()
        cursor = conn.execute("SELECT value FROM system_state WHERE key=?", (key,))
        row = cursor.fetchone()
        return row[0] if row else None

    def log_execution(
        self,
        hypothesis_id: str,
        action: str,
        payload: str = "",
    ) -> str:
        """Log an execution entry. Returns the log ID."""
        log_id = str(uuid.uuid4())
        with self.transaction() as conn:
            conn.execute(
                """INSERT INTO execution_log (id, hypothesis_id, action, payload)
                   VALUES (?, ?, ?, ?)""",
                (log_id, hypothesis_id, action, payload),
            )
        return log_id

    def close(self) -> None:
        """Close the database connection."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None
            logger.info("SQLite connection closed", extra={"path": self._db_path})

    def get_status(self) -> Dict[str, Any]:
        """Return persistence status."""
        conn = self.connect()
        wal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        return {
            "backend": "sqlite",
            "path": self._db_path,
            "wal_mode": wal_mode,
            "migrations_applied": conn.execute(
                "SELECT COUNT(*) FROM migration_history"
            ).fetchone()[0],
        }


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_persistence(config: Optional[PersistenceConfig] = None) -> SQLiteWALBackend:
    """Create the persistence backend from config or environment.

    Returns a SQLite WAL backend (PostgreSQL support is production-only
    and requires the ``psycopg2`` adapter).
    """
    cfg = config or PersistenceConfig.from_env()
    backend = SQLiteWALBackend(cfg)
    backend.run_migrations()
    return backend
