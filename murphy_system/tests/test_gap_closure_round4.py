"""
Gap-closure tests — Round 4 (Final).

Tests the `capped_append` utility and its application to remaining
uncapped lists across core modules.

Gaps addressed:
11. thread_safe_operations — new capped_append utility for CWE-770
12. full_automation_controller — _audit_log unbounded
13. analytics_dashboard — _executions, _records, _task_costs, _alerts_history unbounded
14. control_plane_separation — _routing_history unbounded
15. llm_routing_completeness — _selection_history, _optimisation_log, _routing_log, _validation_log unbounded
"""

import os

import pytest



# ===================================================================
# Gap 11 — capped_append utility
# ===================================================================
class TestCappedAppend:
    """The capped_append utility must enforce size limits."""

    def test_basic_append(self):
        from thread_safe_operations import capped_append

        lst = []
        capped_append(lst, "a")
        capped_append(lst, "b")
        assert lst == ["a", "b"]

    def test_cap_enforced(self):
        from thread_safe_operations import capped_append

        lst = []
        for i in range(25):
            capped_append(lst, i, max_size=20)

        assert len(lst) <= 20

    def test_most_recent_preserved(self):
        from thread_safe_operations import capped_append

        lst = []
        for i in range(30):
            capped_append(lst, i, max_size=20)

        assert lst[-1] == 29
        assert 29 in lst

    def test_default_cap_is_10k(self):
        from thread_safe_operations import capped_append

        lst = list(range(9999))
        capped_append(lst, 9999)
        assert len(lst) == 10000

        capped_append(lst, 10000)
        assert len(lst) < 10001


# ===================================================================
# Gap 12 — full_automation_controller._audit_log
# ===================================================================
class TestFullAutomationControllerBounded:
    """FullAutomationController._audit_log must be bounded via capped_append."""

    def test_audit_log_uses_capped_append(self):
        import inspect
        from full_automation_controller import FullAutomationController

        source = inspect.getsource(FullAutomationController)
        assert "capped_append" in source, (
            "FullAutomationController should use capped_append for _audit_log"
        )
        assert "_audit_log.append(" not in source, (
            "_audit_log.append() should be replaced by capped_append()"
        )


# ===================================================================
# Gap 13 — analytics_dashboard lists bounded
# ===================================================================
class TestAnalyticsDashboardBounded:
    """analytics_dashboard should use capped_append for all append sites."""

    def test_all_appends_use_capped(self):
        import inspect
        from analytics_dashboard import ExecutionAnalytics, ComplianceAnalytics

        ea_src = inspect.getsource(ExecutionAnalytics)
        ca_src = inspect.getsource(ComplianceAnalytics)

        for name, src in [("ExecutionAnalytics", ea_src), ("ComplianceAnalytics", ca_src)]:
            # Should not have raw .append on tracked lists
            for attr in ("_executions", "_records", "_task_costs", "_alerts_history"):
                raw = f"self.{attr}.append("
                if raw in src:
                    pytest.fail(f"{name} still uses raw {raw}")


# ===================================================================
# Gap 14 — control_plane_separation._routing_history bounded
# ===================================================================
class TestControlPlaneSeparationBounded:
    """_routing_history should use capped_append."""

    def test_routing_history_uses_capped(self):
        import inspect
        from control_plane_separation import ControlPlaneSeparation

        src = inspect.getsource(ControlPlaneSeparation)
        assert "_routing_history.append(" not in src, (
            "_routing_history should use capped_append"
        )
        assert "capped_append" in src


# ===================================================================
# Gap 15 — llm_routing_completeness lists bounded
# ===================================================================
class TestLLMRoutingBounded:
    """All history/log lists in llm_routing_completeness should use capped_append."""

    def test_no_raw_appends(self):
        import inspect
        from llm_routing_completeness import (
            ModelSelectionMatrix,
            PromptOptimizationPipeline,
        )

        for cls in (ModelSelectionMatrix, PromptOptimizationPipeline):
            src = inspect.getsource(cls)
            for attr in ("_selection_history", "_optimisation_log"):
                raw = f"self.{attr}.append("
                if raw in src:
                    pytest.fail(f"{cls.__name__} still uses raw {raw}")
