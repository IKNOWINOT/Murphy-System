"""
Tests for EnvironmentSetupAgent — Probe, plan generation, execution
simulation, HITL approval gate, verify-and-retry loop, and state save.

Design Label: TEST-ENV-SETUP-001
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


# ---------------------------------------------------------------------------
# Helpers / stubs
# ---------------------------------------------------------------------------


class _AlwaysOkProbe(EnvironmentProbe):
    """Stub probe that always returns a healthy environment."""

    def probe(self) -> EnvironmentReport:
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


class _NeedsEverythingProbe(EnvironmentProbe):
    """Stub probe that always reports all requirements are missing."""

    def probe(self) -> EnvironmentReport:
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


class _NoOpExecutor(SetupExecutor):
    """Executor stub that marks every step as success without running anything."""

    def execute_plan(self, plan: SetupPlan):
        results = []
        for step in plan.approved_steps():
            step.status = StepStatus.EXECUTED
            r = {"step_id": step.step_id, "status": "success"}
            step.result = r
            results.append(r)
        return results


# ---------------------------------------------------------------------------
# EnvironmentReport
# ---------------------------------------------------------------------------


class TestEnvironmentReport:
    def test_all_ok_requires_python_and_pip_and_disk_and_ports(self):
        report = EnvironmentReport(
            python_ok=True,
            pip_available=True,
            disk_ok=True,
            ports_available={8000: True, 8090: True},
        )
        assert report.all_ok

    def test_all_ok_false_if_python_bad(self):
        report = EnvironmentReport(
            python_ok=False,
            pip_available=True,
            disk_ok=True,
            ports_available={8000: True, 8090: True},
        )
        assert not report.all_ok

    def test_to_dict_contains_required_keys(self):
        report = EnvironmentReport()
        d = report.to_dict()
        for key in ["os_name", "python_ok", "pip_available", "playwright_installed", "probed_at"]:
            assert key in d


# ---------------------------------------------------------------------------
# EnvironmentProbe
# ---------------------------------------------------------------------------


class TestEnvironmentProbe:
    def test_probe_returns_report(self):
        probe = EnvironmentProbe()
        report = probe.probe()
        assert isinstance(report, EnvironmentReport)

    def test_probe_sets_os(self):
        probe = EnvironmentProbe()
        report = probe.probe()
        assert report.os_name in ("linux", "windows", "darwin")

    def test_probe_sets_python_version(self):
        probe = EnvironmentProbe()
        report = probe.probe()
        assert report.python_version
        major, minor, _ = report.python_version.split(".")
        assert int(major) >= 3

    def test_probe_checks_all_required_ports(self):
        probe = EnvironmentProbe()
        report = probe.probe()
        for port in REQUIRED_PORTS:
            assert port in report.ports_available

    def test_probe_sets_disk_info(self):
        probe = EnvironmentProbe()
        report = probe.probe()
        assert report.disk_free_mb > 0

    def test_probe_sets_probed_at(self):
        probe = EnvironmentProbe()
        report = probe.probe()
        assert report.probed_at


# ---------------------------------------------------------------------------
# SetupPlanGenerator
# ---------------------------------------------------------------------------


class TestSetupPlanGenerator:
    def test_no_steps_for_healthy_env(self):
        report = _AlwaysOkProbe().probe()
        plan = SetupPlanGenerator().generate(report)
        assert isinstance(plan, SetupPlan)
        assert plan.steps == []

    def test_steps_for_all_missing(self):
        report = _NeedsEverythingProbe().probe()
        plan = SetupPlanGenerator().generate(report)
        assert len(plan.steps) >= 3

    def test_step_ids_are_unique(self):
        report = _NeedsEverythingProbe().probe()
        plan = SetupPlanGenerator().generate(report)
        ids = [s.step_id for s in plan.steps]
        assert len(ids) == len(set(ids))

    def test_risk_levels_present(self):
        report = _NeedsEverythingProbe().probe()
        plan = SetupPlanGenerator().generate(report)
        levels = {s.risk_level for s in plan.steps}
        # At least one step should be MEDIUM or HIGH
        assert levels & {RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL}

    def test_plan_has_id_and_timestamp(self):
        report = EnvironmentReport(python_ok=True, pip_available=True,
                                   disk_ok=True, ports_available={8000: True, 8090: True})
        plan = SetupPlanGenerator().generate(report)
        assert plan.plan_id
        assert plan.created_at

    def test_liability_note_in_steps(self):
        report = _NeedsEverythingProbe().probe()
        plan = SetupPlanGenerator().generate(report)
        for step in plan.steps:
            assert "Murphy" in step.liability_note or "approved" in step.liability_note.lower()


# ---------------------------------------------------------------------------
# HITLApprovalGate
# ---------------------------------------------------------------------------


class TestHITLApprovalGate:
    def test_approve_all_marks_all_approved(self):
        report = _NeedsEverythingProbe().probe()
        plan = SetupPlanGenerator().generate(report)
        gate = HITLApprovalGate()
        gate.approve_all(plan)
        assert all(s.status == StepStatus.APPROVED for s in plan.steps)

    def test_approve_step_by_id(self):
        report = _NeedsEverythingProbe().probe()
        plan = SetupPlanGenerator().generate(report)
        gate = HITLApprovalGate()
        first = plan.steps[0]
        result = gate.approve_step(plan, first.step_id)
        assert result is True
        assert first.status == StepStatus.APPROVED

    def test_reject_step_by_id(self):
        report = _NeedsEverythingProbe().probe()
        plan = SetupPlanGenerator().generate(report)
        gate = HITLApprovalGate()
        first = plan.steps[0]
        result = gate.reject_step(plan, first.step_id)
        assert result is True
        assert first.status == StepStatus.REJECTED

    def test_approve_nonexistent_step_returns_false(self):
        plan = SetupPlan()
        gate = HITLApprovalGate()
        assert gate.approve_step(plan, "nonexistent") is False

    def test_audit_log_records_approval(self):
        report = _NeedsEverythingProbe().probe()
        plan = SetupPlanGenerator().generate(report)
        gate = HITLApprovalGate()
        gate.approve_all(plan)
        log = gate.get_audit_log()
        assert len(log) == len(plan.steps)
        for entry in log:
            assert entry["approved"] is True
            assert "liability_note" in entry
            assert "timestamp" in entry


# ---------------------------------------------------------------------------
# SetupExecutor
# ---------------------------------------------------------------------------


class TestSetupExecutor:
    def test_executes_file_op_create_directory(self, tmp_path):
        target = str(tmp_path / "murphy_test_dir")
        step = SetupStep(
            step_id="s001",
            description="Create test dir",
            risk_level=RiskLevel.LOW,
            file_op={"path": target, "type": "directory"},
            status=StepStatus.APPROVED,
        )
        plan = SetupPlan(steps=[step])
        executor = SetupExecutor()
        results = executor.execute_plan(plan)
        assert results[0]["status"] == "success"
        assert os.path.isdir(target)

    def test_executes_file_op_write_file(self, tmp_path):
        target = str(tmp_path / "test.env")
        step = SetupStep(
            step_id="s002",
            description="Write .env",
            risk_level=RiskLevel.LOW,
            file_op={"path": target, "content": "TEST_VAR=1\n"},
            status=StepStatus.APPROVED,
        )
        plan = SetupPlan(steps=[step])
        executor = SetupExecutor()
        results = executor.execute_plan(plan)
        assert results[0]["status"] == "success"
        assert os.path.isfile(target)

    def test_unapproved_steps_not_executed(self):
        step = SetupStep(
            step_id="s003",
            description="Should not run",
            risk_level=RiskLevel.LOW,
            command="echo hello",
            status=StepStatus.PENDING,
        )
        plan = SetupPlan(steps=[step])
        executor = SetupExecutor()
        results = executor.execute_plan(plan)
        assert results == []
        assert step.status == StepStatus.PENDING

    def test_browser_op_deferred(self):
        step = SetupStep(
            step_id="s004",
            description="Browser op",
            risk_level=RiskLevel.LOW,
            browser_op={"task_type": "navigate", "url": "http://localhost:8000"},
            status=StepStatus.APPROVED,
        )
        plan = SetupPlan(steps=[step])
        executor = SetupExecutor()
        results = executor.execute_plan(plan)
        assert results[0]["browser_op"] == "deferred"


# ---------------------------------------------------------------------------
# EnvironmentSetupAgent — full loop
# ---------------------------------------------------------------------------


class TestEnvironmentSetupAgent:
    def test_probe_and_plan_healthy_env(self):
        agent = EnvironmentSetupAgent(probe=_AlwaysOkProbe())
        plan = agent.probe_and_plan()
        assert isinstance(plan, SetupPlan)
        assert len(plan.steps) == 0

    def test_execute_and_verify_healthy_env(self):
        agent = EnvironmentSetupAgent(
            probe=_AlwaysOkProbe(),
            executor=_NoOpExecutor(),
        )
        plan = agent.probe_and_plan()
        agent.hitl_gate.approve_all(plan)
        result = agent.execute_and_verify(plan)
        assert result.success

    def test_execute_and_verify_with_fixes(self):
        """Bad probe fixes itself after first execution in the retry loop."""
        call_count = [0]
        ok_probe = _AlwaysOkProbe()
        bad_probe = _NeedsEverythingProbe()

        class _FixingProbe(EnvironmentProbe):
            def probe(self_inner) -> EnvironmentReport:
                call_count[0] += 1
                # First call returns bad env; subsequent calls return OK
                if call_count[0] == 1:
                    return bad_probe.probe()
                return ok_probe.probe()

        agent = EnvironmentSetupAgent(
            probe=_FixingProbe(),
            executor=_NoOpExecutor(),
        )
        plan = agent.probe_and_plan()
        agent.hitl_gate.approve_all(plan)
        result = agent.execute_and_verify(plan)
        assert result.success
        assert result.attempts >= 1

    def test_max_attempts_respected(self):
        agent = EnvironmentSetupAgent(
            probe=_NeedsEverythingProbe(),
            executor=_NoOpExecutor(),
            max_attempts=2,
        )
        plan = agent.probe_and_plan()
        agent.hitl_gate.approve_all(plan)
        result = agent.execute_and_verify(plan)
        assert result.attempts <= 2

    def test_audit_log_populated(self):
        agent = EnvironmentSetupAgent(
            probe=_AlwaysOkProbe(),
            executor=_NoOpExecutor(),
        )
        plan = agent.probe_and_plan()
        agent.hitl_gate.approve_all(plan)
        agent.execute_and_verify(plan)
        log = agent.get_audit_log()
        assert len(log) >= 1

    def test_collect_issues_enumerates_problems(self):
        report = _NeedsEverythingProbe().probe()
        issues = EnvironmentSetupAgent._collect_issues(report)
        assert any("python" in i for i in issues)
        assert any("pip" in i for i in issues)
        assert any("disk" in i for i in issues)
