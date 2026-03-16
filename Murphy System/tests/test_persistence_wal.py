"""
Tests for SQLite WAL Persistence Layer (INC-17 / H-05).

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import os
import sys
import tempfile

import pytest

_src_dir = os.path.join(os.path.dirname(__file__), "..", "src")
if os.path.abspath(_src_dir) not in sys.path:

from persistence_wal import (
    MIGRATIONS,
    PersistenceConfig,
    SQLiteWALBackend,
    create_persistence,
)


@pytest.fixture
def tmp_db(tmp_path):
    """Provide a temporary database path."""
    return str(tmp_path / "test_murphy.db")


@pytest.fixture
def backend(tmp_db):
    """Create a fresh SQLite WAL backend with migrations."""
    cfg = PersistenceConfig(database_url=f"sqlite:///{tmp_db}", wal_mode=True)
    b = SQLiteWALBackend(cfg)
    b.run_migrations()
    yield b
    b.close()


class TestSQLiteWAL:
    """Tests for SQLite WAL persistence."""

    def test_wal_mode_enabled(self, backend) -> None:
        status = backend.get_status()
        assert status["wal_mode"] == "wal"

    def test_migrations_applied(self, backend) -> None:
        status = backend.get_status()
        assert status["migrations_applied"] >= len(MIGRATIONS)

    def test_idempotent_migrations(self, backend) -> None:
        # Running migrations again should be a no-op
        applied = backend.run_migrations()
        assert len(applied) == 0

    def test_set_and_get_state(self, backend) -> None:
        backend.set_state("test_key", "test_value")
        val = backend.get_state("test_key")
        assert val == "test_value"

    def test_get_missing_state(self, backend) -> None:
        val = backend.get_state("nonexistent_key")
        assert val is None

    def test_upsert_state(self, backend) -> None:
        backend.set_state("key1", "v1")
        backend.set_state("key1", "v2")
        assert backend.get_state("key1") == "v2"

    def test_log_execution(self, backend) -> None:
        log_id = backend.log_execution(
            hypothesis_id="hyp_001",
            action="test_action",
            payload='{"data": "test"}',
        )
        assert log_id is not None
        assert len(log_id) > 0

    def test_close_and_reopen(self, tmp_db) -> None:
        cfg = PersistenceConfig(database_url=f"sqlite:///{tmp_db}")
        b = SQLiteWALBackend(cfg)
        b.run_migrations()
        b.set_state("persist_key", "persist_value")
        b.close()

        # Reopen and verify data persists
        b2 = SQLiteWALBackend(cfg)
        b2.connect()
        val = b2.get_state("persist_key")
        b2.close()
        assert val == "persist_value"


class TestPersistenceConfig:
    """Tests for configuration."""

    def test_from_env_defaults(self) -> None:
        from unittest.mock import patch
        with patch.dict(os.environ, {}, clear=True):
            cfg = PersistenceConfig.from_env()
        assert "sqlite" in cfg.database_url
        assert cfg.wal_mode is True

    def test_from_env_custom(self) -> None:
        from unittest.mock import patch
        env = {"DATABASE_URL": "sqlite:///custom.db", "DB_WAL_MODE": "false"}
        with patch.dict(os.environ, env, clear=True):
            cfg = PersistenceConfig.from_env()
        assert cfg.database_url == "sqlite:///custom.db"
        assert cfg.wal_mode is False


class TestCreatePersistence:
    """Tests for the factory function."""

    def test_create_persistence(self, tmp_path) -> None:
        cfg = PersistenceConfig(
            database_url=f"sqlite:///{tmp_path / 'factory.db'}"
        )
        backend = create_persistence(cfg)
        assert backend is not None
        status = backend.get_status()
        assert status["wal_mode"] == "wal"
        backend.close()
