"""PCR-053f — Shadow-tick heartbeat regression suite.

Exercises run_tick() against a real TelemetryCollector and a temporary
sqlite DB. The scheduler integration itself is smoke-tested separately
(register_heartbeat needs a live app).
"""
import json
import os
import sqlite3
import tempfile
from datetime import datetime, timezone

import pytest

from src.org_compiler_heartbeat import (
    DEFAULT_INDUSTRY,
    DEFAULT_JURISDICTION,
    ROLE_OVERRIDES,
    run_tick,
    set_role_jurisdiction,
)


# ──────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    try: os.unlink(path)
    except Exception: pass


@pytest.fixture
def collector():
    from src.org_compiler.shadow_learning import TelemetryCollector
    return TelemetryCollector()


@pytest.fixture(autouse=True)
def _clear_overrides():
    ROLE_OVERRIDES.clear()
    yield
    ROLE_OVERRIDES.clear()


def _rows(db_path):
    con = sqlite3.connect(db_path); con.row_factory = sqlite3.Row
    try:
        cur = con.execute("SELECT * FROM shadow_audit_snapshots ORDER BY snapshot_id")
        return [dict(r) for r in cur.fetchall()]
    finally:
        con.close()


# ──────────────────────────────────────────────────────────────
# Schema
# ──────────────────────────────────────────────────────────────


class TestSchema:
    def test_tick_creates_schema_on_first_run(self, collector, tmp_db):
        run_tick(collector, db_path=tmp_db)
        con = sqlite3.connect(tmp_db)
        try:
            tables = [r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()]
            assert "shadow_audit_snapshots" in tables
        finally:
            con.close()


# ──────────────────────────────────────────────────────────────
# Empty collector → no snapshots
# ──────────────────────────────────────────────────────────────


class TestEmptyCollector:
    def test_no_roles_produces_no_snapshots(self, collector, tmp_db):
        summary = run_tick(collector, db_path=tmp_db)
        assert summary["roles_processed"] == 0
        assert _rows(tmp_db) == []


# ──────────────────────────────────────────────────────────────
# One role with telemetry → snapshot row written
# ──────────────────────────────────────────────────────────────


class TestTickWithObservations:
    def test_single_role_produces_one_snapshot(self, collector, tmp_db):
        collector.record_task_assignment(
            "Sales Rep", "send_quote", datetime.now(timezone.utc),
            metadata={"deal_size_usd": 5000, "operator": "alice"},
        )
        summary = run_tick(collector, db_path=tmp_db, tick_id="test_t1")
        assert summary["roles_processed"] == 1
        rows = _rows(tmp_db)
        assert len(rows) == 1
        r = rows[0]
        assert r["role"] == "Sales Rep"
        assert r["role_family"] == "sales_rep"
        assert r["events_observed"] == 1
        assert r["distinct_operators_seen"] == 1
        assert r["max_money_seen_usd"] == 5000.0
        # Defaults applied: US-CA / saas
        assert r["jurisdiction"] == DEFAULT_JURISDICTION
        assert r["industry"]     == DEFAULT_INDUSTRY
        # Should fail TIME (1d < 14d) and OPERATORS (1 < 3)
        assert r["passes"] == 0
        reasons = json.loads(r["reasons_json"])
        assert any("TIME:" in s for s in reasons)
        assert any("OPERATORS:" in s for s in reasons)

    def test_verdict_flips_to_pass_when_evidence_sufficient(self, collector, tmp_db):
        # 3 distinct operators across a 21-day span
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        for i, op in enumerate(["alice", "bob", "carol"]):
            ts = now - timedelta(days=20 - i*10)  # 20d, 10d, today
            collector.record_task_assignment(
                "Sales Rep", "send_quote", ts,
                metadata={"deal_size_usd": 10_000, "operator": op},
            )
        summary = run_tick(collector, db_path=tmp_db)
        assert summary["roles_processed"] == 1
        rows = _rows(tmp_db)
        assert rows[0]["distinct_operators_seen"] == 3
        # window should be >= 14d, operators >= 3, money <= 50k, regs ok → PASS
        assert rows[0]["passes"] == 1
        assert summary["verdicts_passed"] == 1

    def test_two_roles_two_snapshots(self, collector, tmp_db):
        now = datetime.now(timezone.utc)
        collector.record_task_assignment("Sales Rep", "send_quote", now,
                                          metadata={"operator": "alice"})
        collector.record_task_assignment("Engineer", "code_review", now,
                                          metadata={"operator": "bob"})
        summary = run_tick(collector, db_path=tmp_db)
        assert summary["roles_processed"] == 2
        rows = _rows(tmp_db)
        assert len(rows) == 2
        assert {r["role"] for r in rows} == {"Sales Rep", "Engineer"}


# ──────────────────────────────────────────────────────────────
# Per-role overrides + fail-closed
# ──────────────────────────────────────────────────────────────


class TestOverridesAndFailClosed:
    def test_role_override_changes_jurisdiction(self, collector, tmp_db):
        set_role_jurisdiction("Sales Rep", "EU-DE", "saas")
        collector.record_task_assignment(
            "Sales Rep", "send_quote", datetime.now(timezone.utc),
            metadata={"operator": "alice", "deal_size_usd": 5_000},
        )
        run_tick(collector, db_path=tmp_db)
        rows = _rows(tmp_db)
        assert rows[0]["jurisdiction"] == "EU-DE"
        # EU-DE/saas/sales_rep requires GDPR_consent; we only supplied audit_trail
        assert rows[0]["passes"] == 0
        reasons = json.loads(rows[0]["reasons_json"])
        assert any("GDPR_consent" in s or "right_to_erasure" in s for s in reasons)

    def test_unmapped_combination_records_fail_closed(self, collector, tmp_db):
        set_role_jurisdiction("Sales Rep", "MARS", "interplanetary")
        collector.record_task_assignment(
            "Sales Rep", "send_quote", datetime.now(timezone.utc),
            metadata={"operator": "alice"},
        )
        summary = run_tick(collector, db_path=tmp_db)
        assert summary["fail_closed"] == 1
        assert summary["verdicts_blocked"] == 1
        rows = _rows(tmp_db)
        assert rows[0]["fail_closed"] == 1
        assert rows[0]["passes"] == 0


# ──────────────────────────────────────────────────────────────
# Idempotency
# ──────────────────────────────────────────────────────────────


class TestIdempotency:
    def test_repeated_ticks_accumulate_snapshots(self, collector, tmp_db):
        """Each tick is a new snapshot row — that's the audit trail by design."""
        collector.record_task_assignment(
            "Sales Rep", "send_quote", datetime.now(timezone.utc),
            metadata={"operator": "alice"},
        )
        run_tick(collector, db_path=tmp_db, tick_id="t1")
        run_tick(collector, db_path=tmp_db, tick_id="t2")
        rows = _rows(tmp_db)
        assert len(rows) == 2
        assert {r["tick_id"] for r in rows} == {"t1", "t2"}


# ──────────────────────────────────────────────────────────────
# Summary log shape
# ──────────────────────────────────────────────────────────────


class TestSummary:
    def test_summary_includes_required_fields(self, collector, tmp_db):
        summary = run_tick(collector, db_path=tmp_db)
        for k in ("tick_id", "roles_processed", "verdicts_passed",
                  "verdicts_blocked", "fail_closed", "errors"):
            assert k in summary, f"missing {k} in summary"
