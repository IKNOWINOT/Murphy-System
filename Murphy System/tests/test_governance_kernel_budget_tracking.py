"""
Tests: Governance Kernel — Department-Specific Budget Tracking

Proves that ``record_execution`` correctly debits the *specified*
department's budget rather than the first budget whose pending amount
is large enough (the pre-fix behaviour).

Bug Label  : CWE-682 — Incorrect Calculation
Module     : src/governance_kernel.py
Fixed In   : GovernanceKernel.record_execution (department_id parameter)
"""

import os
import unittest


from governance_kernel import (
    GovernanceKernel,
    DepartmentScope,
    EnforcementAction,
)


class TestDepartmentSpecificBudgetDebit(unittest.TestCase):
    """record_execution(department_id=...) must debit the correct budget."""

    def setUp(self):
        self.kernel = GovernanceKernel()
        # Register two departments with identical budgets
        self.kernel.register_department(
            DepartmentScope(department_id="eng", name="Engineering")
        )
        self.kernel.register_department(
            DepartmentScope(department_id="mkt", name="Marketing")
        )
        self.kernel.set_budget("eng", total_budget=100.0)
        self.kernel.set_budget("mkt", total_budget=100.0)

    # ── Core scenario: correct department is debited ─────────────────
    def test_debit_targets_correct_department(self):
        """When department_id is supplied, only that department's budget moves."""
        # Reserve via enforce
        self.kernel.enforce("alice", "eng", "build", estimated_cost=20.0)
        self.kernel.enforce("bob", "mkt", "campaign", estimated_cost=30.0)

        # Record execution for engineering only
        self.kernel.record_execution(
            "alice", "build", cost=20.0, success=True, department_id="eng"
        )

        eng = self.kernel.get_budget_status("eng")
        mkt = self.kernel.get_budget_status("mkt")

        # Engineering: pending 0, spent 20
        self.assertAlmostEqual(eng["spent"], 20.0)
        self.assertAlmostEqual(eng["pending"], 0.0)
        # Marketing: pending 30, spent 0 — untouched
        self.assertAlmostEqual(mkt["spent"], 0.0)
        self.assertAlmostEqual(mkt["pending"], 30.0)

    # ── Two departments with same pending should not cross-pollinate ──
    def test_identical_pending_no_cross_pollination(self):
        """Even if two departments have the same pending amount, the right one is debited."""
        self.kernel.enforce("a", "eng", "t1", estimated_cost=10.0)
        self.kernel.enforce("b", "mkt", "t2", estimated_cost=10.0)

        self.kernel.record_execution("b", "t2", 10.0, True, department_id="mkt")

        eng = self.kernel.get_budget_status("eng")
        mkt = self.kernel.get_budget_status("mkt")
        self.assertAlmostEqual(eng["pending"], 10.0)
        self.assertAlmostEqual(eng["spent"], 0.0)
        self.assertAlmostEqual(mkt["pending"], 0.0)
        self.assertAlmostEqual(mkt["spent"], 10.0)

    # ── Legacy fallback when department_id is None ───────────────────
    def test_legacy_fallback_without_department_id(self):
        """When department_id is omitted, legacy first-match fallback is used."""
        self.kernel.enforce("a", "eng", "t", estimated_cost=5.0)
        # Legacy call — no department_id
        self.kernel.record_execution("a", "t", 5.0, True)

        eng = self.kernel.get_budget_status("eng")
        # Should still debit *something* (legacy path)
        self.assertAlmostEqual(eng["spent"], 5.0)

    # ── No debit when department has no budget entry ─────────────────
    def test_no_debit_for_unknown_department(self):
        """Passing an unregistered department_id causes no budget change."""
        self.kernel.enforce("a", "eng", "t", estimated_cost=10.0)
        self.kernel.record_execution("a", "t", 10.0, True, department_id="unknown")

        eng = self.kernel.get_budget_status("eng")
        # Engineering pending should remain — nothing was debited
        self.assertAlmostEqual(eng["pending"], 10.0)
        self.assertAlmostEqual(eng["spent"], 0.0)


class TestAuditLogBounded(unittest.TestCase):
    """_audit_log must not grow without bound (CWE-770)."""

    def test_audit_log_capped(self):
        kernel = GovernanceKernel()
        kernel.register_department(
            DepartmentScope(department_id="d", name="D")
        )
        cap = GovernanceKernel._MAX_AUDIT_ENTRIES
        # Generate more entries than the cap
        for i in range(cap + 500):
            kernel.enforce(f"caller-{i}", "d", "tool")

        total = kernel.get_status()["total_audit_entries"]
        self.assertLessEqual(total, cap)

    def test_executions_capped(self):
        kernel = GovernanceKernel()
        kernel.register_department(
            DepartmentScope(department_id="d", name="D")
        )
        cap = GovernanceKernel._MAX_EXECUTIONS
        for i in range(cap + 500):
            kernel.record_execution(f"c-{i}", "t", 0.0, True)

        total = kernel.get_status()["total_executions"]
        self.assertLessEqual(total, cap)


if __name__ == "__main__":
    unittest.main()
