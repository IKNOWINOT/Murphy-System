"""
Tests for SetupRetryAmplifier — MMSMMS cadence for environment setup retries.

Design Label: TEST-SRA-001
Owner: QA Team
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from environment_setup_agent import (
    EnvironmentProbe,
    EnvironmentReport,
    SetupPlanGenerator,
    SetupPlan,
    SetupStep,
    StepStatus,
    RiskLevel,
    HITLApprovalGate,
    SetupExecutor,
    EnvironmentSetupAgent,
    REQUIRED_PORTS,
)
from setup_retry_amplifier import (
    SetupAmplificationPhase,
    SetupAmplificationResult,
    SetupRetryAmplifier,
    SETUP_AMPLIFIER_SEQUENCE,
    CONFIDENCE_EXPAND,
    CONFIDENCE_CONSTRAIN,
    CONFIDENCE_EXECUTE,
)


# ---------------------------------------------------------------------------
# Helpers / stubs  (mirrors style from test_environment_setup_agent.py)
# ---------------------------------------------------------------------------


def _ok_report() -> EnvironmentReport:
    report = EnvironmentReport(
        os_name="linux",
        python_version="3.11.0",
        python_ok=True,
        pip_available=True,
        git_available=True,
        disk_free_mb=10_000,
        disk_ok=True,
        ram_mb=4096,
        ram_ok=True,
        playwright_installed=True,
        dotenv_exists=True,
        venv_exists=True,
        murphy_installed=True,
    )
    for port in REQUIRED_PORTS:
        report.ports_available[port] = True
    return report


def _bad_report() -> EnvironmentReport:
    report = EnvironmentReport(
        os_name="linux",
        python_version="3.8.0",
        python_ok=False,
        pip_available=False,
        git_available=False,
        disk_free_mb=50,
        disk_ok=False,
        ram_mb=256,
        ram_ok=False,
        playwright_installed=False,
        dotenv_exists=False,
        venv_exists=False,
        murphy_installed=False,
        env_vars_missing=["MURPHY_HOME"],
    )
    for port in REQUIRED_PORTS:
        report.ports_available[port] = False
    return report


def _pip_only_bad_report() -> EnvironmentReport:
    """Only pip is missing."""
    report = EnvironmentReport(
        os_name="linux",
        python_version="3.11.0",
        python_ok=True,
        pip_available=False,
        disk_ok=True,
        disk_free_mb=5_000,
    )
    for port in REQUIRED_PORTS:
        report.ports_available[port] = True
    return report


def _port_conflict_report(port: int = 8000) -> EnvironmentReport:
    """Only a port conflict."""
    report = EnvironmentReport(
        os_name="linux",
        python_version="3.11.0",
        python_ok=True,
        pip_available=True,
        disk_ok=True,
        disk_free_mb=5_000,
    )
    for p in REQUIRED_PORTS:
        report.ports_available[p] = p != port
    return report


class _AlwaysOkProbe(EnvironmentProbe):
    def probe(self) -> EnvironmentReport:
        return _ok_report()


class _AlwaysBadProbe(EnvironmentProbe):
    def probe(self) -> EnvironmentReport:
        return _bad_report()


class _NoOpExecutor(SetupExecutor):
    def execute_plan(self, plan: SetupPlan):
        results = []
        for step in plan.approved_steps():
            step.status = StepStatus.EXECUTED
            r = {"step_id": step.step_id, "status": "success"}
            step.result = r
            results.append(r)
        return results


# ---------------------------------------------------------------------------
# TestSetupAmplificationSequence
# ---------------------------------------------------------------------------


class TestSetupAmplificationSequence:
    def test_sequence_constant_is_mmsmms(self):
        assert SETUP_AMPLIFIER_SEQUENCE == "MMSMMS"

    def test_sequence_has_four_magnifies(self):
        assert SETUP_AMPLIFIER_SEQUENCE.count("M") == 4

    def test_sequence_has_one_simplify(self):
        # MMSMMS has 2 S chars: position 2 is Simplify, position 5 is Solidify
        assert SETUP_AMPLIFIER_SEQUENCE.count("S") == 2

    def test_sequence_ends_with_s(self):
        # The final S is the Solidify phase
        assert SETUP_AMPLIFIER_SEQUENCE[-1] == "S"

    def test_confidence_constants_ordered(self):
        assert CONFIDENCE_EXPAND < CONFIDENCE_CONSTRAIN < CONFIDENCE_EXECUTE


# ---------------------------------------------------------------------------
# TestSetupAmplificationResult
# ---------------------------------------------------------------------------


class TestSetupAmplificationResult:
    def test_to_dict_contains_required_keys(self):
        result = SetupAmplificationResult(
            phase=SetupAmplificationPhase.MAGNIFY_EXPAND,
            input_context={"issues": ["pip_not_available"]},
            output_context={"expanded": True},
            confidence=0.7,
        )
        d = result.to_dict()
        assert "phase" in d
        assert "confidence" in d
        assert "output_keys" in d
        assert "completed_at" in d

    def test_confidence_stored(self):
        result = SetupAmplificationResult(
            phase=SetupAmplificationPhase.SIMPLIFY_DISTILL,
            input_context={},
            output_context={},
            confidence=0.75,
        )
        assert result.confidence == pytest.approx(0.75)


# ---------------------------------------------------------------------------
# TestSetupAmplificationPhase
# ---------------------------------------------------------------------------


class TestSetupAmplificationPhase:
    def test_all_six_phases_defined(self):
        phases = list(SetupAmplificationPhase)
        assert len(phases) == 6

    def test_phase_values(self):
        assert SetupAmplificationPhase.MAGNIFY_EXPAND == "magnify_expand"
        assert SetupAmplificationPhase.MAGNIFY_DEEPEN == "magnify_deepen"
        assert SetupAmplificationPhase.SIMPLIFY_DISTILL == "simplify_distill"
        assert SetupAmplificationPhase.MAGNIFY_SOLUTIONS == "magnify_solutions"
        assert SetupAmplificationPhase.MAGNIFY_RANK == "magnify_rank"
        assert SetupAmplificationPhase.SOLIDIFY_LOCK == "solidify_lock"


# ---------------------------------------------------------------------------
# TestSetupRetryAmplifier — amplify_failure
# ---------------------------------------------------------------------------


class TestSetupRetryAmplifier:
    def test_amplify_returns_setup_plan_for_pip_issue(self):
        amp = SetupRetryAmplifier()
        report = _pip_only_bad_report()
        issues = EnvironmentSetupAgent._collect_issues(report)
        plan = amp.amplify_failure(report=report, issues=issues, attempt=3)
        assert plan is not None
        assert isinstance(plan, SetupPlan)
        assert len(plan.steps) >= 1

    def test_amplified_plan_steps_have_liability_note(self):
        amp = SetupRetryAmplifier()
        report = _pip_only_bad_report()
        issues = EnvironmentSetupAgent._collect_issues(report)
        plan = amp.amplify_failure(report=report, issues=issues, attempt=3)
        assert plan is not None
        for step in plan.steps:
            assert "Murphy" in step.liability_note or "approved" in step.liability_note.lower()

    def test_amplified_plan_step_ids_unique(self):
        amp = SetupRetryAmplifier()
        report = _bad_report()
        issues = EnvironmentSetupAgent._collect_issues(report)
        plan = amp.amplify_failure(report=report, issues=issues, attempt=3)
        if plan is not None:
            ids = [s.step_id for s in plan.steps]
            assert len(ids) == len(set(ids))

    def test_amplify_returns_plan_for_port_conflict(self):
        amp = SetupRetryAmplifier()
        report = _port_conflict_report(8000)
        issues = EnvironmentSetupAgent._collect_issues(report)
        plan = amp.amplify_failure(report=report, issues=issues, attempt=3)
        assert plan is not None
        assert len(plan.steps) >= 1

    def test_amplify_returns_none_for_empty_issues(self):
        """No issues → nothing to amplify (confidence below threshold)."""
        amp = SetupRetryAmplifier()
        report = _ok_report()
        # Force empty issues but pass bad report to exercise the path
        plan = amp.amplify_failure(report=report, issues=[], attempt=3)
        # With no issues, MAGNIFY_EXPAND confidence is very low → None
        assert plan is None

    def test_audit_log_populated_after_amplification(self):
        amp = SetupRetryAmplifier()
        report = _pip_only_bad_report()
        issues = EnvironmentSetupAgent._collect_issues(report)
        amp.amplify_failure(report=report, issues=issues, attempt=3)
        log = amp.get_audit_log()
        assert len(log) >= 1

    def test_audit_log_contains_phase_entries(self):
        amp = SetupRetryAmplifier()
        report = _pip_only_bad_report()
        issues = EnvironmentSetupAgent._collect_issues(report)
        amp.amplify_failure(report=report, issues=issues, attempt=3)
        log = amp.get_audit_log()
        actions = [e["action"] for e in log]
        # At minimum MAGNIFY_EXPAND and MAGNIFY_DEEPEN should be logged
        assert any("mmsmms_phase_magnify_expand" in a for a in actions)

    def test_solidified_plan_has_valid_risk_levels(self):
        amp = SetupRetryAmplifier()
        report = _pip_only_bad_report()
        issues = EnvironmentSetupAgent._collect_issues(report)
        plan = amp.amplify_failure(report=report, issues=issues, attempt=3)
        if plan is not None:
            valid_levels = {r.value for r in RiskLevel}
            for step in plan.steps:
                assert step.risk_level.value in valid_levels

    def test_amplified_plan_differs_from_simple_retry(self):
        """Amplified plan should have different step IDs than a plain planner plan."""
        amp = SetupRetryAmplifier()
        report = _pip_only_bad_report()
        issues = EnvironmentSetupAgent._collect_issues(report)

        amplified_plan = amp.amplify_failure(
            report=report, issues=issues, attempt=3
        )
        normal_plan = SetupPlanGenerator().generate(report)

        if amplified_plan is not None and normal_plan.steps:
            amp_ids = {s.step_id for s in amplified_plan.steps}
            normal_ids = {s.step_id for s in normal_plan.steps}
            # IDs must differ (amplified uses sra_ prefix)
            assert amp_ids.isdisjoint(normal_ids)

    def test_amplified_step_ids_contain_attempt_number(self):
        amp = SetupRetryAmplifier()
        report = _pip_only_bad_report()
        issues = EnvironmentSetupAgent._collect_issues(report)
        plan = amp.amplify_failure(report=report, issues=issues, attempt=6)
        if plan is not None:
            for step in plan.steps:
                assert "6" in step.step_id  # attempt=6 embedded in ID


# ---------------------------------------------------------------------------
# TestMMSMMSIntegration — every-3rd-attempt trigger in EnvironmentSetupAgent
# ---------------------------------------------------------------------------


class TestMMSMMSIntegration:
    def test_non_third_attempts_skip_mmsmms(self):
        """Attempts 1, 2 should not trigger MMSMMS amplification."""
        call_count = [0]
        ok_probe = _AlwaysOkProbe()
        bad_probe = _AlwaysBadProbe()

        class _FixOnAttempt2(EnvironmentProbe):
            def probe(self_inner) -> EnvironmentReport:
                call_count[0] += 1
                # Fix on 2nd call (after 1st execute), so attempt 1 passes
                if call_count[0] <= 1:
                    return bad_probe.probe()
                return ok_probe.probe()

        agent = EnvironmentSetupAgent(
            probe=_FixOnAttempt2(),
            executor=_NoOpExecutor(),
            max_attempts=3,
        )
        plan = agent.probe_and_plan()
        agent.hitl_gate.approve_all(plan)
        result = agent.execute_and_verify(plan)
        assert result.success
        # Should succeed before or at attempt 2 (no 3rd-attempt trigger needed)
        assert result.attempts <= 2

    def test_third_attempt_triggers_mmsmms_log(self):
        """Attempt 3 should produce an mmsmms_amplified or mmsmms_plan_generated log entry."""
        agent = EnvironmentSetupAgent(
            probe=_AlwaysBadProbe(),
            executor=_NoOpExecutor(),
            max_attempts=4,
        )
        plan = agent.probe_and_plan()
        agent.hitl_gate.approve_all(plan)
        result = agent.execute_and_verify(plan)
        log = agent.get_audit_log()
        actions = [e["action"] for e in log]
        # After 3 attempts, we expect at least a MMSMMS trigger in the log
        assert result.attempts >= 3
        mmsmms_entries = [
            a for a in actions
            if "mmsmms" in a or "sra_" in a
        ]
        assert len(mmsmms_entries) >= 1

    def test_max_attempts_still_respected_with_mmsmms(self):
        """MMSMMS must not cause the retry loop to exceed max_attempts."""
        agent = EnvironmentSetupAgent(
            probe=_AlwaysBadProbe(),
            executor=_NoOpExecutor(),
            max_attempts=5,
        )
        plan = agent.probe_and_plan()
        agent.hitl_gate.approve_all(plan)
        result = agent.execute_and_verify(plan)
        assert result.attempts <= 5

    def test_solidify_confidence_meets_execute_threshold(self):
        """The solidified plan from amplify_failure must meet CONFIDENCE_EXECUTE."""
        amp = SetupRetryAmplifier()
        report = _pip_only_bad_report()
        issues = EnvironmentSetupAgent._collect_issues(report)
        plan = amp.amplify_failure(report=report, issues=issues, attempt=3)
        # If we get a plan, it means solidify confidence passed CONFIDENCE_EXECUTE
        if plan is not None:
            # Verify by inspecting the audit log
            log = amp.get_audit_log()
            solidify_entries = [
                e for e in log if "solidify_lock" in e.get("action", "")
            ]
            assert len(solidify_entries) >= 1
            solidify_entry = solidify_entries[-1]
            assert solidify_entry.get("confidence", 0) >= CONFIDENCE_EXECUTE

    def test_full_retry_loop_with_amplification(self):
        """Full integration: bad env for 2 attempts, then fixed — MMSMMS fires on 3rd."""
        call_count = [0]
        ok_probe = _AlwaysOkProbe()
        bad_probe = _AlwaysBadProbe()

        class _FixAfterThirdExec(EnvironmentProbe):
            def probe(self_inner) -> EnvironmentReport:
                call_count[0] += 1
                # probe_and_plan (call 1) → bad
                # attempt 1 probe (call 2) → bad
                # attempt 2 probe (call 3) → bad
                # attempt 3 probe (call 4) → bad  ← MMSMMS fires here
                # attempt 4 probe (call 5) → OK   ← success
                if call_count[0] < 5:
                    return bad_probe.probe()
                return ok_probe.probe()

        agent = EnvironmentSetupAgent(
            probe=_FixAfterThirdExec(),
            executor=_NoOpExecutor(),
            max_attempts=6,
        )
        plan = agent.probe_and_plan()
        agent.hitl_gate.approve_all(plan)
        result = agent.execute_and_verify(plan)
        assert result.success
        assert result.attempts >= 3
        # Audit log should contain MMSMMS activity at attempt 3
        log = agent.get_audit_log()
        actions = [e["action"] for e in log]
        assert any("mmsmms" in a for a in actions)
