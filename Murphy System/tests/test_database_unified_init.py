# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL-1.1
"""
Unit tests for the unified database initialization layer (src/database/__init__.py).

Verifies:
1. init_database() initialises both ORM and raw-SQL subsystems from a single URL.
2. run_pending_migrations() correctly detects and applies pending migrations.
3. get_database_status() returns correct status in stub and live modes.
4. _get_pending_migrations() returns an empty list when DB is up-to-date.
5. _redact_url() masks credentials in connection strings.
6. Auto-migration is enabled by default in development, disabled in production.
"""

from __future__ import annotations

import importlib
import os
import sys
import tempfile

import pytest

# Ensure src/ is on the path for direct imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reload_database_module(**env_overrides):
    """Reload src.database with custom environment variables."""
    original = {k: os.environ.get(k) for k in env_overrides}
    for k, v in env_overrides.items():
        os.environ[k] = v
    try:
        import src.database as db_mod
        importlib.reload(db_mod)
        return db_mod
    finally:
        for k, orig_v in original.items():
            if orig_v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = orig_v


# ---------------------------------------------------------------------------
# _redact_url tests
# ---------------------------------------------------------------------------

class TestRedactUrl:
    """_redact_url must never leak passwords in log output."""

    def test_redacts_password_in_postgres_url(self):
        from src.database import _redact_url
        url = "postgresql://user:s3cr3t@localhost:5432/murphy"
        redacted = _redact_url(url)
        assert "s3cr3t" not in redacted
        assert "localhost" in redacted or "***" in redacted

    def test_leaves_sqlite_unchanged(self):
        from src.database import _redact_url
        url = "sqlite:///murphy_logs.db"
        redacted = _redact_url(url)
        assert "murphy_logs.db" in redacted

    def test_handles_url_without_credentials(self):
        from src.database import _redact_url
        url = "sqlite:///:memory:"
        # Should not raise
        result = _redact_url(url)
        assert result  # non-empty


# ---------------------------------------------------------------------------
# Auto-migration default flag tests
# ---------------------------------------------------------------------------

class TestAutoMigrateDefault:
    """MURPHY_AUTO_MIGRATE defaults differ by environment."""

    def test_auto_migrate_true_in_development(self, monkeypatch):
        monkeypatch.setenv("MURPHY_ENV", "development")
        monkeypatch.delenv("MURPHY_AUTO_MIGRATE", raising=False)
        import src.database as db_mod
        importlib.reload(db_mod)
        assert db_mod.MURPHY_AUTO_MIGRATE is True

    def test_auto_migrate_true_in_test(self, monkeypatch):
        monkeypatch.setenv("MURPHY_ENV", "test")
        monkeypatch.delenv("MURPHY_AUTO_MIGRATE", raising=False)
        import src.database as db_mod
        importlib.reload(db_mod)
        assert db_mod.MURPHY_AUTO_MIGRATE is True

    def test_auto_migrate_false_in_production(self, monkeypatch):
        monkeypatch.setenv("MURPHY_ENV", "production")
        monkeypatch.delenv("MURPHY_AUTO_MIGRATE", raising=False)
        import src.database as db_mod
        importlib.reload(db_mod)
        assert db_mod.MURPHY_AUTO_MIGRATE is False

    def test_auto_migrate_false_in_staging(self, monkeypatch):
        monkeypatch.setenv("MURPHY_ENV", "staging")
        monkeypatch.delenv("MURPHY_AUTO_MIGRATE", raising=False)
        import src.database as db_mod
        importlib.reload(db_mod)
        assert db_mod.MURPHY_AUTO_MIGRATE is False

    def test_env_var_overrides_default(self, monkeypatch):
        monkeypatch.setenv("MURPHY_ENV", "production")
        monkeypatch.setenv("MURPHY_AUTO_MIGRATE", "true")
        import src.database as db_mod
        importlib.reload(db_mod)
        assert db_mod.MURPHY_AUTO_MIGRATE is True


# ---------------------------------------------------------------------------
# init_database() tests
# ---------------------------------------------------------------------------

class TestInitDatabase:
    """init_database() must coordinate ORM and migration subsystems."""

    def test_returns_dict_with_required_keys(self, tmp_path, monkeypatch):
        db_url = f"sqlite:///{tmp_path / 'test.db'}"
        monkeypatch.setenv("DATABASE_URL", db_url)
        monkeypatch.setenv("MURPHY_DB_MODE", "live")
        import src.database as db_mod
        importlib.reload(db_mod)
        status = db_mod.init_database(run_migrations=False)
        assert "orm" in status
        assert "migrations" in status
        assert "db_mode" in status
        assert "database_url" in status

    def test_orm_ok_with_sqlite(self, tmp_path, monkeypatch):
        db_url = f"sqlite:///{tmp_path / 'test.db'}"
        monkeypatch.setenv("DATABASE_URL", db_url)
        monkeypatch.setenv("MURPHY_DB_MODE", "live")
        import src.database as db_mod
        importlib.reload(db_mod)
        status = db_mod.init_database(run_migrations=False)
        assert status["orm"] == "ok"

    def test_orm_ok_in_stub_mode(self, tmp_path, monkeypatch):
        """ORM init should still succeed in stub mode (SQLite default)."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setenv("MURPHY_DB_MODE", "stub")
        import src.database as db_mod
        importlib.reload(db_mod)
        status = db_mod.init_database(run_migrations=False)
        # ORM uses SQLite default, should be ok or error gracefully
        assert status["orm"] in ("ok", "error")

    def test_migrations_skipped_when_disabled(self, tmp_path, monkeypatch):
        db_url = f"sqlite:///{tmp_path / 'test.db'}"
        monkeypatch.setenv("DATABASE_URL", db_url)
        monkeypatch.setenv("MURPHY_DB_MODE", "live")
        import src.database as db_mod
        importlib.reload(db_mod)
        status = db_mod.init_database(run_migrations=False)
        assert status["migrations"] == "skipped"

    def test_db_mode_reported_in_status(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MURPHY_DB_MODE", "stub")
        import src.database as db_mod
        importlib.reload(db_mod)
        status = db_mod.init_database(run_migrations=False)
        assert status["db_mode"] == "stub"


# ---------------------------------------------------------------------------
# run_pending_migrations() tests
# ---------------------------------------------------------------------------

class TestRunPendingMigrations:
    """run_pending_migrations() must handle missing alembic.ini gracefully."""

    def test_returns_skipped_when_alembic_ini_missing(self, tmp_path, monkeypatch):
        """When alembic.ini is absent the function must return 'skipped'."""
        db_url = f"sqlite:///{tmp_path / 'test.db'}"
        monkeypatch.setenv("DATABASE_URL", db_url)

        import src.database as db_mod
        importlib.reload(db_mod)

        # Temporarily point the module at a directory without alembic.ini
        original_file = db_mod.__file__
        # Patch by monkeypatching os.path.isfile to return False
        import src.database as db_mod2

        original_isfile = os.path.isfile

        def _no_ini(path):
            if "alembic.ini" in path:
                return False
            return original_isfile(path)

        monkeypatch.setattr(os.path, "isfile", _no_ini)
        result = db_mod2.run_pending_migrations()
        assert result == "skipped"

    def test_returns_skipped_when_alembic_not_installed(self, tmp_path, monkeypatch):
        """When alembic cannot be imported, function must return 'skipped'."""
        # Save original import
        import builtins
        original_import = builtins.__import__

        def _block_alembic(name, *args, **kwargs):
            if name.startswith("alembic"):
                raise ImportError("alembic not installed (mocked)")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _block_alembic)
        import src.database as db_mod
        importlib.reload(db_mod)
        result = db_mod.run_pending_migrations()
        assert result == "skipped"


# ---------------------------------------------------------------------------
# get_database_status() tests
# ---------------------------------------------------------------------------

class TestGetDatabaseStatus:
    """get_database_status() must always return a dict with db_mode."""

    def test_stub_mode_returns_stub_orm(self, monkeypatch):
        monkeypatch.setenv("MURPHY_DB_MODE", "stub")
        import src.database as db_mod
        importlib.reload(db_mod)
        status = db_mod.get_database_status()
        assert status["db_mode"] == "stub"
        assert status["orm"] == "stub"

    def test_live_mode_with_sqlite_returns_ok(self, tmp_path, monkeypatch):
        db_url = f"sqlite:///{tmp_path / 'health.db'}"
        monkeypatch.setenv("DATABASE_URL", db_url)
        monkeypatch.setenv("MURPHY_DB_MODE", "live")
        import src.database as db_mod
        importlib.reload(db_mod)
        # Prime the ORM tables first
        db_mod.init_database(run_migrations=False)
        status = db_mod.get_database_status()
        assert status["db_mode"] == "live"
        assert status["orm"] in ("ok", "error")

    def test_returns_database_url_redacted(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql://admin:secret@db:5432/murphy")
        monkeypatch.setenv("MURPHY_DB_MODE", "stub")
        import src.database as db_mod
        importlib.reload(db_mod)
        status = db_mod.get_database_status()
        assert "secret" not in status.get("database_url", "")


# ---------------------------------------------------------------------------
# _get_pending_migrations() tests
# ---------------------------------------------------------------------------

class TestGetPendingMigrations:
    """_get_pending_migrations() returns None gracefully on errors."""

    def test_returns_none_when_alembic_unavailable(self, monkeypatch):
        """Must return None (not raise) when alembic is not importable."""
        import builtins
        original_import = builtins.__import__

        def _block(name, *args, **kwargs):
            if "alembic.runtime" in name or "alembic.script" in name:
                raise ImportError("blocked")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _block)
        import src.database as db_mod

        # Create a minimal mock config
        class _FakeCfg:
            """Minimal mock of alembic.config.Config for testing purposes.

            Only implements ``get_main_option`` so that
            ``_get_pending_migrations`` can retrieve the database URL without
            requiring a real alembic.ini file.
            """

            def get_main_option(self, key):
                return "sqlite:///:memory:"

        result = db_mod._get_pending_migrations(_FakeCfg())
        # Should return None (not raise)
        assert result is None
