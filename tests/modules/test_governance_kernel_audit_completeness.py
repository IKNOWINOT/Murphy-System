"""
Tests for governance_kernel.py — cross-department audit log completeness

Closes Gap 5: Existing tests verified cross-department arbitration outcomes
but did NOT verify that the audit log entries contain all required fields
(source_dept, target_dept, tool_name, action, reason, timestamp).
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from governance_kernel import (
    GovernanceKernel,
    DepartmentScope,
    EnforcementAction,
)


class TestCrossDepartmentAuditFields(unittest.TestCase):
    """Cross-department arbitration must log complete audit entries."""

    def setUp(self):
        self.kernel = GovernanceKernel()
        self.kernel.register_department(
            DepartmentScope(department_id="eng", name="Engineering")
        )
        self.kernel.register_department(
            DepartmentScope(
                department_id="finance", name="Finance",
                memory_isolation=True,
            )
        )
        self.kernel.register_department(
            DepartmentScope(department_id="ops", name="Operations")
        )

    def _required_fields(self):
        return {"event", "source_dept", "target_dept", "tool_name",
                "action", "reason", "timestamp"}

    def test_allowed_cross_dept_audit_entry_has_all_fields(self):
        self.kernel.check_cross_department("eng", "ops", "deploy")
        log = self.kernel.get_audit_log()
        cross_entries = [e for e in log if e.get("event") == "cross_department_check"]
        self.assertTrue(len(cross_entries) >= 1)
        entry = cross_entries[-1]
        for field in self._required_fields():
            self.assertIn(field, entry, f"Missing field: {field}")
        self.assertEqual(entry["action"], "allow")

    def test_denied_isolation_audit_entry_has_all_fields(self):
        self.kernel.check_cross_department("eng", "finance", "read_budget")
        log = self.kernel.get_audit_log()
        cross_entries = [e for e in log if e.get("event") == "cross_department_check"]
        self.assertTrue(len(cross_entries) >= 1)
        entry = cross_entries[-1]
        for field in self._required_fields():
            self.assertIn(field, entry, f"Missing field: {field}")
        self.assertEqual(entry["action"], "deny")

    def test_unregistered_source_audit_entry_has_all_fields(self):
        self.kernel.check_cross_department("unknown", "eng", "tool")
        log = self.kernel.get_audit_log()
        cross_entries = [e for e in log if e.get("event") == "cross_department_check"]
        entry = cross_entries[-1]
        for field in self._required_fields():
            self.assertIn(field, entry, f"Missing field: {field}")

    def test_unregistered_target_audit_entry_has_all_fields(self):
        self.kernel.check_cross_department("eng", "unknown", "tool")
        log = self.kernel.get_audit_log()
        cross_entries = [e for e in log if e.get("event") == "cross_department_check"]
        entry = cross_entries[-1]
        for field in self._required_fields():
            self.assertIn(field, entry, f"Missing field: {field}")


class TestEnforcementAuditLogFields(unittest.TestCase):
    """enforce() audit entries must include all required fields."""

    def setUp(self):
        self.kernel = GovernanceKernel()
        self.kernel.register_department(
            DepartmentScope(department_id="eng", name="Engineering",
                           allowed_tools={"build", "test"})
        )
        self.kernel.set_budget("eng", total_budget=100.0, limit_per_task=10.0)

    def _required_fields(self):
        return {"event", "caller_id", "department_id", "tool_name",
                "estimated_cost", "action", "reason", "enforced_by",
                "context", "timestamp"}

    def test_allowed_enforcement_log_completeness(self):
        self.kernel.enforce("alice", "eng", "build", estimated_cost=5.0)
        log = self.kernel.get_audit_log()
        entry = [e for e in log if e.get("event") == "enforcement"][-1]
        for field in self._required_fields():
            self.assertIn(field, entry, f"Missing field: {field}")

    def test_denied_enforcement_log_completeness(self):
        self.kernel.enforce("alice", "eng", "forbidden_tool")
        log = self.kernel.get_audit_log()
        entry = [e for e in log if e.get("event") == "enforcement"][-1]
        for field in self._required_fields():
            self.assertIn(field, entry, f"Missing field: {field}")


if __name__ == "__main__":
    unittest.main()
