# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL-1.1
"""
Murphy System — Critical Error Fix Regression Tests

Validates fixes for critical errors identified by security scanning:
  - SHA1 → SHA256 in cutsheet_engine.py (B324 HIGH)
  - MD5 → SHA256 in murphy_system_core.py (B324 HIGH)
  - PRAGMA int validation in persistence_wal.py (SQL injection prevention)
  - Swallowed exceptions now log in critical paths

Run with: pytest tests/test_critical_error_fixes.py -v
"""

import hashlib
import json
import os
import sqlite3
from pathlib import Path

import pytest

os.environ.setdefault("MURPHY_ENV", "test")


# ── 1. SHA256 replaces SHA1 in cutsheet_engine ──────────────────

class TestCutsheetHashUpgrade:
    """Verify CommissioningTest uses SHA256, not SHA1."""

    def test_test_id_uses_sha256(self):
        """Generated test_id must match SHA256 digest, not SHA1."""
        from src.cutsheet_engine import CommissioningTest

        ct = CommissioningTest(
            equipment_tag="AHU-01",
            cutsheet_id="CS-001",
            manufacturer="Trane",
            model_number="XR-100",
            test_type="functional",
            test_description="Verify fan operation",
        )

        # Compute expected SHA256-based ID
        seed = f"{ct.cutsheet_id}|{ct.test_type}|{ct.test_description}"
        expected = hashlib.sha256(seed.encode()).hexdigest()[:10]
        assert ct.test_id == expected, (
            f"test_id should be SHA256-based: expected {expected}, got {ct.test_id}"
        )

    def test_test_id_not_sha1(self):
        """Ensure the old SHA1 digest is NOT used."""
        from src.cutsheet_engine import CommissioningTest

        ct = CommissioningTest(
            equipment_tag="AHU-01",
            cutsheet_id="CS-001",
            manufacturer="Trane",
            model_number="XR-100",
            test_type="functional",
            test_description="Verify fan operation",
        )

        seed = f"{ct.cutsheet_id}|{ct.test_type}|{ct.test_description}"
        # Intentionally compute SHA1 to verify production code does NOT use it
        sha1_id = hashlib.sha1(seed.encode()).hexdigest()[:10]  # noqa: S324
        assert ct.test_id != sha1_id, "test_id must NOT use SHA1"

    def test_explicit_test_id_preserved(self):
        """When test_id is explicitly provided, it should not be overwritten."""
        from src.cutsheet_engine import CommissioningTest

        ct = CommissioningTest(
            equipment_tag="AHU-01",
            cutsheet_id="CS-001",
            manufacturer="Trane",
            model_number="XR-100",
            test_type="functional",
            test_description="Verify fan operation",
            test_id="explicit-id",
        )
        assert ct.test_id == "explicit-id"


# ── 2. SHA256 replaces MD5 in murphy_system_core ────────────────

class TestMurphyCoreHashUpgrade:
    """Verify the onboarding summary dedup hash uses SHA256."""

    def test_source_uses_sha256_not_md5(self):
        """Scan the source for md5 usage — it must be replaced with sha256."""
        import inspect
        from src.runtime.murphy_system_core import MurphySystem

        source = inspect.getsource(MurphySystem._build_readiness_reply)
        assert "sha256" in source, "Dedup hash must use SHA256"
        assert "md5" not in source.lower(), "MD5 must not be used for dedup hash"


# ── 3. PRAGMA integer validation in persistence_wal ─────────────

class TestPragmaIntValidation:
    """Verify PRAGMA values are validated as integers."""

    def test_connect_with_valid_config(self):
        """SQLiteWALBackend.connect() should work with valid config."""
        from src.persistence_wal import PersistenceConfig, SQLiteWALBackend

        config = PersistenceConfig(
            database_url="sqlite:///:memory:",
            wal_mode=True,
            busy_timeout_ms=5000,
            journal_size_limit=67108864,
        )
        backend = SQLiteWALBackend(config)
        conn = backend.connect()
        assert conn is not None

        # Verify PRAGMA was applied
        result = conn.execute("PRAGMA busy_timeout").fetchone()
        assert result[0] == 5000
        conn.close()

    def test_pragma_rejects_non_integer(self):
        """PRAGMA config values must be integers — non-int should raise."""
        from src.persistence_wal import PersistenceConfig, SQLiteWALBackend

        config = PersistenceConfig(
            database_url="sqlite:///:memory:",
            wal_mode=True,
            busy_timeout_ms=5000,
            journal_size_limit=67108864,
        )
        backend = SQLiteWALBackend(config)
        # Inject a non-integer to test the int() guard
        backend._config.busy_timeout_ms = "not_a_number"  # type: ignore[assignment]
        with pytest.raises((ValueError, TypeError)):
            backend.connect()


# ── 4. Swallowed exceptions now log ─────────────────────────────

class TestSwallowedExceptionsLog:
    """Verify that formerly-silent except blocks now emit log messages."""

    def test_security_audit_logs_on_persist_failure(self):
        """SecurityHardeningConfig audit must log when persistence fails."""
        import inspect
        from src.security_hardening_config import AuditLogger

        source = inspect.getsource(AuditLogger.log)
        assert "logger.warning" in source, (
            "Audit persistence failure must log a warning, not silently pass"
        )

    def test_codebase_swarm_logs_on_introspection_failure(self):
        """Self-codebase swarm must log when introspection fails."""
        import ast

        with open(Path(__file__).resolve().parent.parent.parent / "src" / "self_codebase_swarm.py", "r") as f:
            source = f.read()

        # Verify no bare 'except Exception: pass' remains
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if (
                    node.type
                    and isinstance(node.type, ast.Name)
                    and node.type.id == "Exception"
                    and len(node.body) == 1
                    and isinstance(node.body[0], ast.Pass)
                ):
                    pytest.fail(
                        f"Found 'except Exception: pass' at line {node.lineno} "
                        "— all exception handlers should log"
                    )
