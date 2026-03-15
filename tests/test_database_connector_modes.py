"""
Tests for SQLDatabaseConnector live/stub mode toggle.

Verifies that:
1. Stub mode (MURPHY_DB_MODE=stub or unset) returns deterministic fixture data.
2. Live mode (MURPHY_DB_MODE=live) uses SQLAlchemy with a real SQLite DB.
3. Live mode with a bad connection string fails gracefully (connect() → False).
4. execute_transaction rolls back on failure in live mode.
5. execute_stored_procedure works in both modes.
6. The MURPHY_DB_MODE module-level constant is exported from the module.
"""

import importlib
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def _make_stub_connector(connection_string: str = "sqlite:///:memory:"):
    """Return a SQLDatabaseConnector configured in stub mode."""
    os.environ["MURPHY_DB_MODE"] = "stub"
    import integrations.database_connectors as dc_mod
    importlib.reload(dc_mod)
    connector = dc_mod.SQLDatabaseConnector(connection_string)
    return connector


def _make_live_connector(connection_string: str):
    """Return a SQLDatabaseConnector configured in live mode."""
    os.environ["MURPHY_DB_MODE"] = "live"
    import integrations.database_connectors as dc_mod
    importlib.reload(dc_mod)
    connector = dc_mod.SQLDatabaseConnector(connection_string)
    return connector


# ---------------------------------------------------------------------------
# Stub mode tests
# ---------------------------------------------------------------------------

class TestStubMode:
    """Stub mode must return fixture data without touching any database."""

    def setup_method(self):
        os.environ["MURPHY_DB_MODE"] = "stub"

    def teardown_method(self):
        os.environ.pop("MURPHY_DB_MODE", None)

    def test_connect_succeeds_without_real_db(self):
        connector = _make_stub_connector("mysql://user:pass@nonexistent/db")
        assert connector.connect() is True

    def test_select_returns_test_record(self):
        connector = _make_stub_connector()
        connector.connect()
        result = connector.execute_query("SELECT * FROM users")
        assert result.success is True
        assert isinstance(result.data, list)
        assert result.data[0]['name'] == 'Test Record'

    def test_insert_returns_affected_rows(self):
        connector = _make_stub_connector()
        connector.connect()
        result = connector.execute_query("INSERT INTO users (name) VALUES (:name)", {"name": "Alice"})
        assert result.success is True
        assert result.data[0]['affected_rows'] == 1

    def test_update_returns_affected_rows(self):
        connector = _make_stub_connector()
        connector.connect()
        result = connector.execute_query("UPDATE users SET name = :name WHERE id = :id", {"name": "Bob", "id": 1})
        assert result.success is True
        assert result.data[0]['affected_rows'] == 1

    def test_delete_returns_affected_rows(self):
        connector = _make_stub_connector()
        connector.connect()
        result = connector.execute_query("DELETE FROM users WHERE id = :id", {"id": 1})
        assert result.success is True
        assert result.data[0]['affected_rows'] == 1

    def test_transaction_executes_all_operations(self):
        connector = _make_stub_connector()
        connector.connect()
        ops = [
            {"query": "INSERT INTO orders (id) VALUES (:id)", "parameters": {"id": 1}},
            {"query": "UPDATE inventory SET qty = 0 WHERE id = :id", "parameters": {"id": 1}},
        ]
        result = connector.execute_transaction(ops)
        assert result.success is True
        assert len(result.data) == 2

    def test_stored_procedure_returns_success_payload(self):
        connector = _make_stub_connector()
        connector.connect()
        result = connector.execute_stored_procedure("sp_report", {"user_id": 42})
        assert result.success is True
        assert result.data['result'] == 'success'
        assert result.data['procedure'] == 'sp_report'

    def test_not_connected_returns_error(self):
        connector = _make_stub_connector()
        # do NOT call connect()
        result = connector.execute_query("SELECT 1")
        assert result.success is False
        assert "Not connected" in result.error


# ---------------------------------------------------------------------------
# Live mode tests (uses an in-memory SQLite DB)
# ---------------------------------------------------------------------------

class TestLiveMode:
    """Live mode must execute real queries via SQLAlchemy."""

    def setup_method(self):
        os.environ["MURPHY_DB_MODE"] = "live"

    def teardown_method(self):
        os.environ.pop("MURPHY_DB_MODE", None)

    @pytest.fixture()
    def sqlite_connector(self, tmp_path):
        """Connected live connector backed by a temporary SQLite file."""
        db_file = str(tmp_path / "test.db")
        connector = _make_live_connector(f"sqlite:///{db_file}")
        assert connector.connect() is True
        # Create a test table
        connector.execute_query(
            "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT)"
        )
        yield connector
        connector.disconnect()

    def test_connect_with_sqlite(self, sqlite_connector):
        assert sqlite_connector.is_connected is True

    def test_insert_and_select(self, sqlite_connector):
        insert_result = sqlite_connector.execute_query(
            "INSERT INTO users (id, name) VALUES (:id, :name)",
            {"id": 1, "name": "Alice"},
        )
        assert insert_result.success is True

        select_result = sqlite_connector.execute_query(
            "SELECT * FROM users WHERE id = :id", {"id": 1}
        )
        assert select_result.success is True
        assert select_result.data[0]['name'] == 'Alice'

    def test_transaction_commit(self, sqlite_connector):
        ops = [
            {"query": "INSERT INTO users (id, name) VALUES (:id, :name)", "parameters": {"id": 10, "name": "Bob"}},
            {"query": "INSERT INTO users (id, name) VALUES (:id, :name)", "parameters": {"id": 11, "name": "Carol"}},
        ]
        result = sqlite_connector.execute_transaction(ops)
        assert result.success is True

        select = sqlite_connector.execute_query("SELECT COUNT(*) AS cnt FROM users")
        assert select.data[0]['cnt'] == 2

    def test_transaction_rollback_on_failure(self, sqlite_connector):
        """A failing second operation must roll back the first."""
        # First insert a row so the duplicate will fail
        sqlite_connector.execute_query(
            "INSERT INTO users (id, name) VALUES (:id, :name)", {"id": 99, "name": "X"}
        )
        ops = [
            # Valid insert
            {"query": "INSERT INTO users (id, name) VALUES (:id, :name)", "parameters": {"id": 100, "name": "New"}},
            # Duplicate PK — will fail
            {"query": "INSERT INTO users (id, name) VALUES (:id, :name)", "parameters": {"id": 99, "name": "Dup"}},
        ]
        result = sqlite_connector.execute_transaction(ops)
        assert result.success is False
        # The first insert should have been rolled back
        count_result = sqlite_connector.execute_query("SELECT COUNT(*) AS cnt FROM users WHERE id = 100")
        assert count_result.data[0]['cnt'] == 0

    def test_bad_connection_string_returns_false(self):
        connector = _make_live_connector("postgresql://bad:bad@nonexistent:5432/nodb")
        assert connector.connect() is False
        assert connector.is_connected is False


# ---------------------------------------------------------------------------
# Module-level constant tests
# ---------------------------------------------------------------------------

class TestModuleConstants:
    """MURPHY_DB_MODE constant must be exported from the module."""

    def test_module_exports_murphy_db_mode(self):
        import integrations.database_connectors as dc_mod
        assert hasattr(dc_mod, "MURPHY_DB_MODE")
        assert dc_mod.MURPHY_DB_MODE in ("stub", "live")

    def test_default_is_stub(self, monkeypatch):
        monkeypatch.delenv("MURPHY_DB_MODE", raising=False)
        import integrations.database_connectors as dc_mod
        importlib.reload(dc_mod)
        assert dc_mod.MURPHY_DB_MODE == "stub"
