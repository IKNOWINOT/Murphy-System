"""
AUAR Persistence Layer
=======================

Pluggable persistence interface so AUAR state (capability graph, ML
model data, schema mappings, circuit-breaker counters, observability
traces) can survive restarts.

Provides:
  - :class:`StateBackend` — abstract base class.
  - :class:`FileStateBackend` — JSON-file-based reference implementation.

Usage::

    backend = FileStateBackend("/var/lib/auar/state")
    backend.save("graph", graph.get_stats())
    data = backend.load("graph")

Copyright 2024 Inoni LLC – BSL-1.1
"""

import json
import logging
import os
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------

class StateBackend(ABC):
    """Abstract persistence backend for AUAR state.

    Implementations must be thread-safe.  Keys are dot-separated
    namespaces (e.g. ``graph.capabilities``, ``ml.scores``).
    """

    @abstractmethod
    def save(self, key: str, data: Any) -> None:
        """Persist *data* under *key*.  Must be JSON-serialisable."""

    @abstractmethod
    def load(self, key: str) -> Optional[Any]:
        """Load data previously saved under *key*.

        Returns ``None`` if the key does not exist.
        """

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete the entry for *key*.  Returns ``True`` if it existed."""

    @abstractmethod
    def list_keys(self) -> List[str]:
        """Return all keys currently stored."""

    @abstractmethod
    def flush(self) -> None:
        """Ensure all pending writes are durable (e.g. fsync)."""


# ---------------------------------------------------------------------------
# In-memory backend (testing / ephemeral usage)
# ---------------------------------------------------------------------------

class InMemoryStateBackend(StateBackend):
    """In-memory backend — data is lost on process exit.

    Useful for unit tests or short-lived processes where durability
    is unnecessary.
    """

    def __init__(self) -> None:
        self._store: Dict[str, Any] = {}
        self._lock = threading.Lock()

    def save(self, key: str, data: Any) -> None:
        with self._lock:
            self._store[key] = data

    def load(self, key: str) -> Optional[Any]:
        with self._lock:
            return self._store.get(key)

    def delete(self, key: str) -> bool:
        with self._lock:
            return self._store.pop(key, None) is not None

    def list_keys(self) -> List[str]:
        with self._lock:
            return list(self._store.keys())

    def flush(self) -> None:
        pass  # No-op — everything is already in memory.


# ---------------------------------------------------------------------------
# File-based backend
# ---------------------------------------------------------------------------

class FileStateBackend(StateBackend):
    """JSON-file-based persistence backend.

    Each key is stored as a separate ``<key>.json`` file inside
    *base_dir*.  Dots in keys are translated to directory separators
    so that ``graph.capabilities`` becomes ``graph/capabilities.json``.

    Thread-safe via a per-instance lock.  Writes are atomic (write to
    temp then rename) to prevent corruption.
    """

    def __init__(self, base_dir: str) -> None:
        self._base = Path(base_dir)
        self._base.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        logger.info("FileStateBackend: %s", self._base)

    def _key_path(self, key: str) -> Path:
        parts = key.replace(".", os.sep)
        return self._base / f"{parts}.json"

    def save(self, key: str, data: Any) -> None:
        path = self._key_path(key)
        with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, default=str, indent=2))
            tmp.rename(path)

    def load(self, key: str) -> Optional[Any]:
        path = self._key_path(key)
        with self._lock:
            if not path.exists():
                return None
            try:
                return json.loads(path.read_text())
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to load %s: %s", key, exc)
                return None

    def delete(self, key: str) -> bool:
        path = self._key_path(key)
        with self._lock:
            if path.exists():
                path.unlink()
                return True
            return False

    def list_keys(self) -> List[str]:
        keys: List[str] = []
        with self._lock:
            for p in self._base.rglob("*.json"):
                rel = p.relative_to(self._base).with_suffix("")
                keys.append(str(rel).replace(os.sep, "."))
        return keys

    def flush(self) -> None:
        # Files are written atomically in save(); nothing to flush.
        pass


# ---------------------------------------------------------------------------
# PostgreSQL-backed backend — AUAR-PERSIST-002
# ---------------------------------------------------------------------------

class PostgresStateBackend(StateBackend):
    """PostgreSQL-backed persistence for production AUAR state.

    Uses the database configured in ``DATABASE_URL`` (or the SQLAlchemy
    engine from :mod:`src.db`).  Falls back to ``sqlite:///:memory:`` for
    test isolation when no URL is set.

    Table: ``auar_state`` — auto-created on first access.

    Thread-safe via the engine's built-in connection pool.

    Environment variables
    ---------------------
    DATABASE_URL        : PostgreSQL connection string.
    MURPHY_DB_URL       : Alias checked when DATABASE_URL is absent.
    MURPHY_DB_MODE      : When ``stub``, disables real DB access.
    """

    _TABLE_DDL = """
        CREATE TABLE IF NOT EXISTS auar_state (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """

    def __init__(self, engine: Optional[Any] = None) -> None:
        self._engine = engine
        self._lock = threading.Lock()
        self._table_ensured = False

    def _get_engine(self) -> Any:
        """Lazily resolve or create the SQLAlchemy engine."""
        if self._engine is not None:
            return self._engine
        with self._lock:
            if self._engine is not None:
                return self._engine
            try:
                from src.db import _get_engine  # type: ignore[import-untyped]
                self._engine = _get_engine()
            except Exception as exc:
                logger.debug("Could not import src.db engine: %s", exc)
                # Fallback: in-process SQLite (tests, dev)
                try:
                    from sqlalchemy import create_engine  # type: ignore[import-untyped]
                    url = os.environ.get(
                        "DATABASE_URL",
                        os.environ.get("MURPHY_DB_URL", "sqlite:///:memory:"),
                    )
                    self._engine = create_engine(url, echo=False)
                except ImportError:
                    raise RuntimeError(
                        "PostgresStateBackend requires sqlalchemy. "
                        "Install with: pip install sqlalchemy"
                    )
            return self._engine

    def _ensure_table(self) -> None:
        """Create the ``auar_state`` table if it doesn't exist."""
        if self._table_ensured:
            return
        with self._lock:
            if self._table_ensured:
                return
            try:
                from sqlalchemy import text  # type: ignore[import-untyped]
                engine = self._get_engine()
                with engine.begin() as conn:
                    conn.execute(text(self._TABLE_DDL))
                self._table_ensured = True
                logger.info("PostgresStateBackend: auar_state table ensured")
            except Exception as exc:
                logger.warning("PostgresStateBackend table creation failed: %s", exc)

    # -- StateBackend contract ----------------------------------------------

    def save(self, key: str, data: Any) -> None:
        """Upsert *data* (JSON) under *key*."""
        self._ensure_table()
        try:
            from sqlalchemy import text  # type: ignore[import-untyped]
            payload = json.dumps(data, default=str)
            engine = self._get_engine()
            with engine.begin() as conn:
                # UPSERT — works on both PostgreSQL and SQLite
                conn.execute(
                    text(
                        "INSERT INTO auar_state (key, value, updated_at) "
                        "VALUES (:key, :value, CURRENT_TIMESTAMP) "
                        "ON CONFLICT (key) DO UPDATE SET "
                        "value = :value, updated_at = CURRENT_TIMESTAMP"
                    ),
                    {"key": key, "value": payload},
                )
        except Exception as exc:
            logger.error("PostgresStateBackend.save(%s) failed: %s", key, exc)
            raise

    def load(self, key: str) -> Optional[Any]:
        """Load data for *key*, returning ``None`` if absent."""
        self._ensure_table()
        try:
            from sqlalchemy import text  # type: ignore[import-untyped]
            engine = self._get_engine()
            with engine.connect() as conn:
                row = conn.execute(
                    text("SELECT value FROM auar_state WHERE key = :key"),
                    {"key": key},
                ).fetchone()
            if row is None:
                return None
            return json.loads(row[0])
        except Exception as exc:
            logger.warning("PostgresStateBackend.load(%s) failed: %s", key, exc)
            return None

    def delete(self, key: str) -> bool:
        """Delete *key*.  Returns ``True`` if the row existed."""
        self._ensure_table()
        try:
            from sqlalchemy import text  # type: ignore[import-untyped]
            engine = self._get_engine()
            with engine.begin() as conn:
                result = conn.execute(
                    text("DELETE FROM auar_state WHERE key = :key"),
                    {"key": key},
                )
                return result.rowcount > 0
        except Exception as exc:
            logger.error("PostgresStateBackend.delete(%s) failed: %s", key, exc)
            return False

    def list_keys(self) -> List[str]:
        """Return all stored keys."""
        self._ensure_table()
        try:
            from sqlalchemy import text  # type: ignore[import-untyped]
            engine = self._get_engine()
            with engine.connect() as conn:
                rows = conn.execute(
                    text("SELECT key FROM auar_state ORDER BY key")
                ).fetchall()
            return [r[0] for r in rows]
        except Exception as exc:
            logger.error("PostgresStateBackend.list_keys() failed: %s", exc)
            return []

    def flush(self) -> None:
        """No-op — database commits are immediate via engine.begin()."""
        pass
