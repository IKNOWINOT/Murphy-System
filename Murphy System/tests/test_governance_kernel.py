"""Tests for the GovernanceKernel enforcement layer."""

import threading
from datetime import datetime, timezone

import pytest

from src.governance_kernel import (
    BudgetTracker,
    DepartmentScope,
    EnforcementAction,
    EnforcementResult,
    GovernanceKernel,
)


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def kernel() -> GovernanceKernel:
    return GovernanceKernel()


@pytest.fixture
def strict_kernel() -> GovernanceKernel:
    return GovernanceKernel(strict_mode=True)


@pytest.fixture
def engineering_scope() -> DepartmentScope:
    return DepartmentScope(
        department_id="eng",
        name="Engineering",
        allowed_tools={"code_search", "file_edit", "test_runner"},
        memory_isolation=False,
        escalation_target="eng-lead",
    )


@pytest.fixture
def finance_scope() -> DepartmentScope:
    return DepartmentScope(
        department_id="fin",
        name="Finance",
        allowed_tools={"ledger_read", "report_gen"},
        memory_isolation=True,
        escalation_target="cfo",
    )


@pytest.fixture
def open_scope() -> DepartmentScope:
    """Department with no tool restrictions."""
    return DepartmentScope(
        department_id="ops",
        name="Operations",
        allowed_tools=set(),
        memory_isolation=False,
    )


# ------------------------------------------------------------------
# Department registration
# ------------------------------------------------------------------

class TestDepartmentRegistration:
    def test_register_returns_id(self, kernel, engineering_scope):
        result = kernel.register_department(engineering_scope)
        assert result == "eng"

    def test_registered_department_in_status(self, kernel, engineering_scope):
        kernel.register_department(engineering_scope)
        status = kernel.get_status()
        assert "eng" in status["department_ids"]
        assert status["total_departments"] == 1

    def test_register_multiple_departments(self, kernel, engineering_scope, finance_scope):
        kernel.register_department(engineering_scope)
        kernel.register_department(finance_scope)
        status = kernel.get_status()
        assert status["total_departments"] == 2


# ------------------------------------------------------------------
# Enforcement allow / deny / escalate
# ------------------------------------------------------------------

class TestEnforcementDecisions:
    def test_allow_when_tool_permitted(self, kernel, engineering_scope):
        kernel.register_department(engineering_scope)
        result = kernel.enforce("alice", "eng", "code_search")
        assert result.action == EnforcementAction.ALLOW

    def test_deny_unregistered_department(self, kernel):
        result = kernel.enforce("alice", "ghost", "any_tool")
        assert result.action == EnforcementAction.DENY
        assert "not registered" in result.reason

    def test_deny_tool_not_in_allowed_set(self, kernel, engineering_scope):
        kernel.register_department(engineering_scope)
        result = kernel.enforce("alice", "eng", "delete_database")
        assert result.action == EnforcementAction.DENY
        assert "not in allowed tools" in result.reason

    def test_allow_any_tool_when_allowed_tools_empty(self, kernel, open_scope):
        kernel.register_department(open_scope)
        result = kernel.enforce("bob", "ops", "anything_goes")
        assert result.action == EnforcementAction.ALLOW

    def test_enforcement_result_fields(self, kernel, engineering_scope):
        kernel.register_department(engineering_scope)
        result = kernel.enforce("alice", "eng", "code_search")
        assert isinstance(result, EnforcementResult)
        assert isinstance(result.timestamp, datetime)
        assert result.enforced_by != ""
        assert isinstance(result.metadata, dict)


# ------------------------------------------------------------------
# Budget tracking and enforcement
# ------------------------------------------------------------------

class TestBudgetEnforcement:
    def test_set_and_get_budget(self, kernel, engineering_scope):
        kernel.register_department(engineering_scope)
        kernel.set_budget("eng", total_budget=100.0, limit_per_task=10.0)
        status = kernel.get_budget_status("eng")
        assert status["total_budget"] == 100.0
        assert status["remaining"] == 100.0
        assert status["limit_per_task"] == 10.0

    def test_no_budget_set_returns_status(self, kernel, engineering_scope):
        kernel.register_department(engineering_scope)
        status = kernel.get_budget_status("eng")
        assert status["status"] == "no_budget_set"

    def test_escalate_when_cost_exceeds_remaining(self, kernel, engineering_scope):
        kernel.register_department(engineering_scope)
        kernel.set_budget("eng", total_budget=5.0)
        result = kernel.enforce("alice", "eng", "code_search", estimated_cost=10.0)
        assert result.action == EnforcementAction.ESCALATE

    def test_deny_when_cost_exceeds_remaining_strict(self, strict_kernel, engineering_scope):
        strict_kernel.register_department(engineering_scope)
        strict_kernel.set_budget("eng", total_budget=5.0)
        result = strict_kernel.enforce("alice", "eng", "code_search", estimated_cost=10.0)
        assert result.action == EnforcementAction.DENY

    def test_escalate_when_per_task_limit_exceeded(self, kernel, engineering_scope):
        kernel.register_department(engineering_scope)
        kernel.set_budget("eng", total_budget=100.0, limit_per_task=2.0)
        result = kernel.enforce("alice", "eng", "code_search", estimated_cost=5.0)
        assert result.action == EnforcementAction.ESCALATE

    def test_deny_when_per_task_limit_exceeded_strict(self, strict_kernel, engineering_scope):
        strict_kernel.register_department(engineering_scope)
        strict_kernel.set_budget("eng", total_budget=100.0, limit_per_task=2.0)
        result = strict_kernel.enforce("alice", "eng", "code_search", estimated_cost=5.0)
        assert result.action == EnforcementAction.DENY

    def test_budget_decreases_after_execution(self, kernel, engineering_scope):
        kernel.register_department(engineering_scope)
        kernel.set_budget("eng", total_budget=100.0)
        kernel.enforce("alice", "eng", "code_search", estimated_cost=10.0)
        kernel.record_execution("alice", "code_search", cost=10.0, success=True)
        status = kernel.get_budget_status("eng")
        assert status["spent"] == 10.0
        assert status["remaining"] == pytest.approx(90.0)

    def test_get_all_budgets(self, kernel, engineering_scope, finance_scope):
        kernel.register_department(engineering_scope)
        kernel.register_department(finance_scope)
        kernel.set_budget("eng", total_budget=100.0)
        kernel.set_budget("fin", total_budget=50.0)
        all_budgets = kernel.get_budget_status()
        assert "eng" in all_budgets
        assert "fin" in all_budgets

    def test_update_existing_budget(self, kernel, engineering_scope):
        kernel.register_department(engineering_scope)
        kernel.set_budget("eng", total_budget=100.0, limit_per_task=5.0)
        kernel.set_budget("eng", total_budget=200.0, limit_per_task=20.0)
        status = kernel.get_budget_status("eng")
        assert status["total_budget"] == 200.0
        assert status["limit_per_task"] == 20.0


# ------------------------------------------------------------------
# Cross-department arbitration
# ------------------------------------------------------------------

class TestCrossDepartmentArbitration:
    def test_allow_when_no_isolation(self, kernel, engineering_scope, open_scope):
        kernel.register_department(engineering_scope)
        kernel.register_department(open_scope)
        result = kernel.check_cross_department("eng", "ops", "file_edit")
        assert result.action == EnforcementAction.ALLOW

    def test_deny_when_target_has_memory_isolation(self, kernel, engineering_scope, finance_scope):
        kernel.register_department(engineering_scope)
        kernel.register_department(finance_scope)
        result = kernel.check_cross_department("eng", "fin", "ledger_read")
        assert result.action == EnforcementAction.DENY
        assert "memory isolation" in result.reason

    def test_deny_unregistered_source(self, kernel, finance_scope):
        kernel.register_department(finance_scope)
        result = kernel.check_cross_department("ghost", "fin", "ledger_read")
        assert result.action == EnforcementAction.DENY

    def test_deny_unregistered_target(self, kernel, engineering_scope):
        kernel.register_department(engineering_scope)
        result = kernel.check_cross_department("eng", "ghost", "any_tool")
        assert result.action == EnforcementAction.DENY


# ------------------------------------------------------------------
# Audit log recording
# ------------------------------------------------------------------

class TestAuditLog:
    def test_enforce_creates_audit_entry(self, kernel, engineering_scope):
        kernel.register_department(engineering_scope)
        kernel.enforce("alice", "eng", "code_search")
        log = kernel.get_audit_log()
        assert len(log) == 1
        assert log[0]["event"] == "enforcement"
        assert log[0]["caller_id"] == "alice"

    def test_denied_calls_also_audited(self, kernel):
        kernel.enforce("alice", "ghost", "any_tool")
        log = kernel.get_audit_log()
        assert len(log) == 1
        assert log[0]["action"] == "deny"

    def test_filter_by_department(self, kernel, engineering_scope, finance_scope):
        kernel.register_department(engineering_scope)
        kernel.register_department(finance_scope)
        kernel.enforce("alice", "eng", "code_search")
        kernel.enforce("bob", "fin", "ledger_read")
        eng_log = kernel.get_audit_log(department_id="eng")
        assert all(e["department_id"] == "eng" for e in eng_log)

    def test_audit_limit(self, kernel, engineering_scope):
        kernel.register_department(engineering_scope)
        for i in range(10):
            kernel.enforce(f"user-{i}", "eng", "code_search")
        log = kernel.get_audit_log(limit=3)
        assert len(log) == 3

    def test_cross_department_check_audited(self, kernel, engineering_scope, open_scope):
        kernel.register_department(engineering_scope)
        kernel.register_department(open_scope)
        kernel.check_cross_department("eng", "ops", "file_edit")
        log = kernel.get_audit_log()
        assert any(e["event"] == "cross_department_check" for e in log)


# ------------------------------------------------------------------
# Status reporting
# ------------------------------------------------------------------

class TestStatusReporting:
    def test_initial_status(self, kernel):
        status = kernel.get_status()
        assert status["total_departments"] == 0
        assert status["total_audit_entries"] == 0
        assert status["total_executions"] == 0
        assert status["strict_mode"] is False

    def test_strict_mode_reflected(self, strict_kernel):
        assert strict_kernel.get_status()["strict_mode"] is True

    def test_status_after_operations(self, kernel, engineering_scope):
        kernel.register_department(engineering_scope)
        kernel.set_budget("eng", total_budget=100.0)
        kernel.enforce("alice", "eng", "code_search", estimated_cost=1.0)
        kernel.record_execution("alice", "code_search", cost=1.0, success=True)
        status = kernel.get_status()
        assert status["total_departments"] == 1
        assert status["total_budgets"] == 1
        assert status["total_audit_entries"] == 1
        assert status["total_executions"] == 1


# ------------------------------------------------------------------
# Thread safety
# ------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_enforce_calls(self, kernel, engineering_scope):
        kernel.register_department(engineering_scope)
        kernel.set_budget("eng", total_budget=10000.0)
        errors: list = []

        def worker(idx: int) -> None:
            try:
                for _ in range(50):
                    result = kernel.enforce(f"user-{idx}", "eng", "code_search", estimated_cost=0.01)
                    assert result.action in (EnforcementAction.ALLOW, EnforcementAction.ESCALATE)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Thread errors: {errors}"
        log = kernel.get_audit_log(limit=500)
        assert len(log) == 400  # 8 threads * 50 calls

    def test_concurrent_registration_and_enforce(self, kernel):
        errors: list = []

        def register_worker() -> None:
            try:
                for i in range(20):
                    scope = DepartmentScope(
                        department_id=f"dept-{i}",
                        name=f"Department {i}",
                    )
                    kernel.register_department(scope)
            except Exception as exc:
                errors.append(exc)

        def enforce_worker() -> None:
            try:
                for i in range(20):
                    kernel.enforce("user", f"dept-{i}", "tool")
            except Exception as exc:
                errors.append(exc)

        t1 = threading.Thread(target=register_worker)
        t2 = threading.Thread(target=enforce_worker)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert errors == [], f"Thread errors: {errors}"


# ------------------------------------------------------------------
# Dataclass unit tests
# ------------------------------------------------------------------

class TestDataclasses:
    def test_budget_tracker_remaining(self):
        bt = BudgetTracker(total_budget=100.0, spent=30.0, pending=10.0)
        assert bt.remaining == pytest.approx(60.0)

    def test_enforcement_result_defaults(self):
        er = EnforcementResult(
            action=EnforcementAction.ALLOW,
            reason="ok",
            enforced_by="test",
        )
        assert isinstance(er.timestamp, datetime)
        assert er.metadata == {}

    def test_department_scope_defaults(self):
        ds = DepartmentScope(department_id="x", name="X")
        assert ds.allowed_tools == set()
        assert ds.memory_isolation is False
        assert ds.escalation_target is None
