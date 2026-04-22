"""Tests for Phase-2 continuation features:

* E25 — `kernel.metrics()` + `GET /api/aionmind/metrics`
* E26 — append-only JSONL audit log gated by ``set_audit_log_path``
* The ``auto_approved`` flag returned by ``cognitive_execute``

Naming: this lives next to ``test_capability_bridges.py`` and reuses
its conventions.
"""

from __future__ import annotations

import json

import pytest

from aionmind.capability_registry import Capability
from aionmind.models.context_object import RiskLevel
from aionmind.runtime_kernel import AionMindKernel


@pytest.fixture
def kernel():
    """Kernel with one trivial low-risk capability + handler."""
    k = AionMindKernel(auto_bridge_bots=False, auto_discover_rsc=False)
    k.register_capability(
        Capability(
            capability_id="t.echo",
            name="Echo",
            description="Echo handler used in continuation tests.",
            provider="test",
            input_schema={"_": {"type": "null"}},
            output_schema={"status": {"type": "string"}},
            risk_level="low",
            tags=["general"],
        )
    )
    k.register_handler("t.echo", lambda node: {"status": "ok"})
    return k


class TestMetrics:
    def test_metrics_seeded_with_zero_counts(self, kernel):
        metrics = kernel.metrics()
        for key in (
            "calls_total",
            "auto_approved",
            "pending_approval",
            "no_candidates",
            "executed",
            "failed",
        ):
            assert metrics.get(key) == 0, f"{key} not seeded to 0"

    def test_auto_approved_flag_and_executed_counter(self, kernel):
        out = kernel.cognitive_execute(
            source="t",
            raw_input="echo",
            auto_approve=True,
            approver="alice",
            max_auto_approve_risk=RiskLevel.LOW,
        )
        # Pipeline ran end-to-end on a low-risk task with auto_approve.
        assert out["status"] in ("completed", "failed"), out
        assert out["auto_approved"] is True
        m = kernel.metrics()
        assert m["calls_total"] == 1
        assert m["auto_approved"] == 1
        assert m["executed"] >= 1 or m["failed"] >= 1

    def test_pending_approval_increments_only_pending_counter(self, kernel):
        out = kernel.cognitive_execute(
            source="t",
            raw_input="echo",
            auto_approve=False,
            approver="anon",
        )
        assert out["status"] == "pending_approval"
        assert out["auto_approved"] is False
        m = kernel.metrics()
        assert m["pending_approval"] == 1
        assert m["auto_approved"] == 0


class TestAuditLog:
    def test_audit_log_disabled_by_default(self, kernel, tmp_path):
        kernel.cognitive_execute(
            source="t", raw_input="echo",
            auto_approve=True, approver="alice",
            max_auto_approve_risk=RiskLevel.LOW,
        )
        # No file should appear anywhere in tmp_path.
        assert list(tmp_path.glob("*")) == []

    def test_audit_log_appends_one_line_per_call(self, kernel, tmp_path):
        log_path = tmp_path / "subdir" / "aionmind-audit.jsonl"
        kernel.set_audit_log_path(str(log_path))
        kernel.cognitive_execute(
            source="t", raw_input="echo",
            auto_approve=True, approver="alice",
            actor="alice@example.com",
            max_auto_approve_risk=RiskLevel.LOW,
        )
        kernel.cognitive_execute(
            source="t", raw_input="echo",
            auto_approve=False, approver="anon",
            actor="anon",
        )
        assert log_path.exists()
        lines = log_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2
        first = json.loads(lines[0])
        second = json.loads(lines[1])
        assert first["actor"] == "alice@example.com"
        assert first["status"] in ("completed", "failed")
        assert first["auto_approved"] is True
        assert second["actor"] == "anon"
        assert second["status"] == "pending_approval"
        assert second["auto_approved"] is False
        assert "ts" in first and isinstance(first["ts"], (int, float))


class TestMetricsEndpoint:
    @pytest.fixture
    def client(self, kernel):
        try:
            from fastapi.testclient import TestClient
        except Exception:  # pragma: no cover
            pytest.skip("fastapi[testclient] not installed")
        from fastapi import FastAPI
        from aionmind import api as aionmind_api
        aionmind_api.init_kernel(kernel)
        app = FastAPI()
        app.include_router(aionmind_api.router)
        with TestClient(app) as c:
            yield c

    def test_metrics_endpoint_returns_seeded_keys(self, client):
        resp = client.get("/api/aionmind/metrics")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "metrics" in body
        for key in (
            "calls_total",
            "auto_approved",
            "pending_approval",
            "no_candidates",
            "executed",
            "failed",
            # P1b (FORGE-KERNEL-001): external pipeline counters are
            # part of the public metrics schema and the D20 KPI strip
            # depends on them being present even before any traffic.
            "executed_external",
            "failed_external",
        ):
            assert key in body["metrics"]


class TestRecordExternalExecution:
    """P1b (FORGE-KERNEL-001) — out-of-band pipelines (today: the
    Demo Forge ``/api/demo/generate-deliverable`` route) record
    successes and failures against the kernel via
    :meth:`AionMindKernel.record_external_execution`.  Audit entries
    must be appended exactly once per call, the
    ``executed_external`` / ``failed_external`` counters must move
    in lock-step, and the entry must be tagged ``source="external"``
    so a UI can distinguish external from kernel-driven rows.
    """

    def test_completed_status_bumps_executed_external_counter(self, kernel):
        before = kernel.metrics()["executed_external"]
        entry = kernel.record_external_execution(
            actor="alice@example.com",
            task_type="demo_forge",
            status="completed",
            summary="build me a html5 game",
            details={"scenario": "game", "llm_provider": "llm-remote:deepinfra"},
        )
        after = kernel.metrics()
        assert after["executed_external"] == before + 1
        assert after["failed_external"] == 0
        # The returned entry mirrors what would be persisted.
        assert entry["status"] == "completed"
        assert entry["actor"] == "alice@example.com"
        assert entry["task_type"] == "demo_forge"
        assert entry["source"] == "external"
        assert entry["external"]["scenario"] == "game"
        assert entry["external"]["llm_provider"] == "llm-remote:deepinfra"
        assert entry["summary"] == "build me a html5 game"

    def test_non_completed_status_bumps_failed_external_counter(self, kernel):
        kernel.record_external_execution(
            actor=None,
            task_type="demo_forge",
            status="failed",
            summary="x" * 500,  # exercises summary truncation
            details={"error": "boom"},
        )
        m = kernel.metrics()
        assert m["failed_external"] == 1
        assert m["executed_external"] == 0

    def test_audit_log_disabled_no_file_written(self, kernel, tmp_path):
        # No path configured -> audit-only call still updates metrics
        # but writes nothing, mirroring _append_audit_log semantics.
        kernel.record_external_execution(
            actor="bob", task_type="demo_forge", status="completed",
        )
        assert list(tmp_path.glob("*")) == []
        assert kernel.metrics()["executed_external"] == 1

    def test_audit_log_appends_external_entry_with_summary_truncation(self, kernel, tmp_path):
        log_path = tmp_path / "subdir" / "aionmind-audit.jsonl"
        kernel.set_audit_log_path(str(log_path))
        long_query = "build me " + ("foo " * 200)
        kernel.record_external_execution(
            actor="alice@example.com",
            task_type="demo_forge",
            status="completed",
            summary=long_query,
            details={"bytes": 14588, "tier": "anonymous"},
        )
        assert log_path.exists()
        lines = log_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["source"] == "external"
        assert entry["actor"] == "alice@example.com"
        assert entry["task_type"] == "demo_forge"
        assert entry["status"] == "completed"
        assert entry["auto_approved"] is False
        assert len(entry["summary"]) == 240, "summary must be truncated to 240 chars"
        assert entry["external"]["bytes"] == 14588

    def test_anonymous_actor_falls_back_to_string(self, kernel, tmp_path):
        log_path = tmp_path / "audit.jsonl"
        kernel.set_audit_log_path(str(log_path))
        kernel.record_external_execution(
            actor=None, task_type="demo_forge", status="completed",
        )
        entry = json.loads(log_path.read_text(encoding="utf-8").strip())
        assert entry["actor"] == "anonymous"

    def test_tail_audit_log_returns_external_entries(self, kernel, tmp_path):
        log_path = tmp_path / "audit.jsonl"
        kernel.set_audit_log_path(str(log_path))
        kernel.record_external_execution(
            actor="alice", task_type="demo_forge", status="completed", summary="q1",
        )
        kernel.record_external_execution(
            actor="bob", task_type="demo_forge", status="failed", summary="q2",
        )
        tail = kernel.tail_audit_log(limit=10)
        assert len(tail) == 2
        # tail_audit_log returns newest-first
        assert tail[0]["actor"] == "bob"
        assert tail[0]["status"] == "failed"
        assert tail[1]["actor"] == "alice"
        # External entries carry the ``source`` discriminator.
        assert all(e.get("source") == "external" for e in tail)

