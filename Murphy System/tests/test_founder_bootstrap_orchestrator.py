# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Tests for FounderBootstrapOrchestrator.

Validates:
  - Each stage executes in dependency order
  - Stage 1 cannot run before Stage 0 completes
  - Rollback triggered on failure
  - Status reporting across all stages
  - Individual step execution and verification
  - Founder email validation (only cpost@murphy.systems)
  - Idempotency (running bootstrap twice doesn't duplicate work)
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR      = PROJECT_ROOT / "src"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))

from founder_bootstrap_orchestrator import (
    BootstrapStage,
    BootstrapStep,
    BootstrapStepStatus,
    FounderBootstrapOrchestrator,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_orchestrator(**kwargs: Any) -> FounderBootstrapOrchestrator:
    return FounderBootstrapOrchestrator(**kwargs)


def _patch_all_actions(orchestrator: FounderBootstrapOrchestrator, return_value: bool = True) -> None:
    """Monkey-patch every action method to return *return_value* without side effects."""
    for step in orchestrator._steps.values():
        setattr(orchestrator, step.action, MagicMock(return_value=return_value))


# ---------------------------------------------------------------------------
# Construction / validation
# ---------------------------------------------------------------------------

class TestConstruction:
    def test_default_founder_email(self) -> None:
        orc = _make_orchestrator()
        assert orc._founder_email == "cpost@murphy.systems"

    def test_wrong_email_raises(self) -> None:
        with pytest.raises(ValueError, match="cpost@murphy.systems"):
            FounderBootstrapOrchestrator(founder_email="hacker@evil.com")

    def test_steps_populated(self) -> None:
        orc = _make_orchestrator()
        assert len(orc._steps) == 20  # 4 + 5 + 6 + 5

    def test_initial_status_all_pending(self) -> None:
        orc = _make_orchestrator()
        status = orc.get_status()
        for stage_data in status["stages"].values():
            for step in stage_data:
                assert step["status"] == BootstrapStepStatus.PENDING.value

    def test_progress_zero_at_start(self) -> None:
        orc = _make_orchestrator()
        assert orc.get_status()["progress_pct"] == 0.0


# ---------------------------------------------------------------------------
# Dependency enforcement
# ---------------------------------------------------------------------------

class TestDependencies:
    def test_step_blocked_if_dependency_incomplete(self) -> None:
        orc = _make_orchestrator()
        _patch_all_actions(orc)
        # Step 1.1 depends on 0.3 — leave 0.3 pending and try to run stage 1
        # Mark 0.1 and 0.2 completed so 0.3 can run but skip 0.3 manually
        for step_id in ("0.1", "0.2"):
            orc._steps[step_id].status = BootstrapStepStatus.COMPLETED
        # Do NOT complete 0.3 — so stage 1 step 1.1 should fail on dep check
        result = orc._execute_step(orc._steps["1.1"])
        assert result["status"] == BootstrapStepStatus.FAILED

    def test_stage_0_completes_before_stage_1_can_run(self) -> None:
        orc = _make_orchestrator()
        _patch_all_actions(orc)
        # Run stage 0 first
        r0 = orc.run_stage(BootstrapStage.CORE_RUNTIME)
        assert r0["status"] == "completed"
        # Now stage 1 should succeed
        r1 = orc.run_stage(BootstrapStage.SELF_OPERATION)
        assert r1["status"] == "completed"

    def test_stage_1_fails_without_stage_0(self) -> None:
        orc = _make_orchestrator()
        _patch_all_actions(orc)
        # Attempt stage 1 without completing stage 0
        r1 = orc.run_stage(BootstrapStage.SELF_OPERATION)
        assert r1["status"] == "failed"


# ---------------------------------------------------------------------------
# Full bootstrap
# ---------------------------------------------------------------------------

class TestFullBootstrap:
    def test_full_bootstrap_succeeds(self) -> None:
        orc = _make_orchestrator()
        _patch_all_actions(orc)
        result = orc.run_full_bootstrap()
        assert result["status"] == "completed"

    def test_full_bootstrap_all_steps_completed(self) -> None:
        orc = _make_orchestrator()
        _patch_all_actions(orc)
        orc.run_full_bootstrap()
        status = orc.get_status()
        assert status["completed"] == status["total_steps"]
        assert status["progress_pct"] == 100.0

    def test_full_bootstrap_halts_on_failure(self) -> None:
        orc = _make_orchestrator()
        _patch_all_actions(orc)
        # Make step 0.1 fail
        setattr(orc, "_deploy_runtime", MagicMock(return_value=False))
        result = orc.run_full_bootstrap()
        # Should have failed at stage 0
        assert result["status"] == "partial"


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

class TestIdempotency:
    def test_second_run_skips_completed_steps(self) -> None:
        orc = _make_orchestrator()
        _patch_all_actions(orc)
        orc.run_full_bootstrap()
        # Record call counts after first run
        call_counts_1 = {
            step_id: getattr(orc, step.action).call_count
            for step_id, step in orc._steps.items()
        }
        # Second run — completed steps must be skipped
        orc.run_full_bootstrap()
        for step_id, step in orc._steps.items():
            assert getattr(orc, step.action).call_count == call_counts_1[step_id], (
                f"Step {step_id} was called again on second run (not idempotent)"
            )

    def test_completed_step_returns_skipped(self) -> None:
        orc = _make_orchestrator()
        _patch_all_actions(orc)
        step = orc._steps["0.1"]
        step.status = BootstrapStepStatus.COMPLETED
        result = orc._execute_step(step)
        assert result["status"] == BootstrapStepStatus.SKIPPED


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------

class TestRollback:
    def test_rollback_called_on_failure(self) -> None:
        orc = _make_orchestrator()
        _patch_all_actions(orc)
        # Give step 0.2 a rollback action and make it fail
        step = orc._steps["0.2"]
        step.rollback_action = "_rollback_founder_auth"
        setattr(orc, "_provision_founder_auth", MagicMock(side_effect=RuntimeError("boom")))
        setattr(orc, "_rollback_founder_auth", MagicMock())
        # Mark dependency 0.1 as completed
        orc._steps["0.1"].status = BootstrapStepStatus.COMPLETED
        orc._execute_step(step)
        orc._rollback_founder_auth.assert_called_once()
        assert step.status == BootstrapStepStatus.ROLLED_BACK


# ---------------------------------------------------------------------------
# Status reporting
# ---------------------------------------------------------------------------

class TestStatus:
    def test_status_includes_all_stages(self) -> None:
        orc = _make_orchestrator()
        status = orc.get_status()
        assert set(status["stages"].keys()) == {s.value for s in BootstrapStage}

    def test_status_tracks_partial_progress(self) -> None:
        orc = _make_orchestrator()
        _patch_all_actions(orc)
        orc.run_stage(BootstrapStage.CORE_RUNTIME)
        status = orc.get_status()
        completed = status["completed"]
        assert 0 < completed < status["total_steps"]

    def test_audit_log_grows(self) -> None:
        orc = _make_orchestrator()
        _patch_all_actions(orc)
        orc.run_stage(BootstrapStage.CORE_RUNTIME)
        assert orc.get_status()["audit_entries"] > 0


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_get_status_is_safe(self) -> None:
        orc = _make_orchestrator()
        errors: list[Exception] = []

        def _worker() -> None:
            try:
                for _ in range(50):
                    orc.get_status()
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
