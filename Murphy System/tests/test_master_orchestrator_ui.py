# test_master_orchestrator_ui.py — Tests for Master Orchestrator UI + Backend Wiring
# © 2020 Inoni Limited Liability Company by Corey Post
# License: BSL 1.1
"""
Verifies the new backend modules introduced by the master-orchestrator-ui PR:
  - src/golden_path_engine.py  (GoldenPathEngine, Recommendation, Priority)
  - New API endpoints registered in murphy_system_1.0_runtime.py
"""

import pytest
import sys
import os

# Ensure the Murphy System root is on sys.path
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


# ---------------------------------------------------------------------------
# Helpers (storyline-actuals record pattern from test_documentation_remediation)
# ---------------------------------------------------------------------------

def record(check_id, description, expected, actual, cause="", effect="", lesson=""):
    """Record a test check and return True/False."""
    passed = bool(actual == expected if not callable(expected) else expected(actual))
    if not passed:
        print(
            f"\n  FAIL [{check_id}] {description}\n"
            f"    expected: {expected}\n"
            f"    actual:   {actual}\n"
            f"    cause:    {cause}\n"
            f"    effect:   {effect}\n"
            f"    lesson:   {lesson}"
        )
    return passed


# ---------------------------------------------------------------------------
# GoldenPathEngine — unit tests
# ---------------------------------------------------------------------------

class TestGoldenPathEngine:
    """Tests for src/golden_path_engine.py."""

    def _engine(self):
        from src.golden_path_engine import GoldenPathEngine
        return GoldenPathEngine()

    def test_import(self):
        """GoldenPathEngine can be imported."""
        from src.golden_path_engine import GoldenPathEngine, Priority, Recommendation
        assert GoldenPathEngine is not None
        assert Priority is not None
        assert Recommendation is not None

    def test_empty_state_returns_empty_recs(self):
        """Empty system state → empty recommendations list."""
        engine = self._engine()
        recs = engine.get_recommendations("FOUNDER", {})
        assert isinstance(recs, list)
        assert len(recs) == 0

    def test_hitl_priority_first(self):
        """HITL gates appear at priority 1 (most urgent)."""
        engine = self._engine()
        state = {
            "hitl_pending": [{"id": "h1", "workflow_id": "wf1", "description": "Approve step"}],
            "optimisations": [{"id": "o1", "title": "Save money", "saving": "$10"}],
        }
        recs = engine.get_recommendations("FOUNDER", state)
        assert len(recs) >= 2
        assert record(
            "GPE-001", "HITL is first recommendation",
            1, recs[0]["priority"],
            cause="HITL gates are highest priority",
        )

    def test_priority_order(self):
        """Recommendations are sorted by priority ascending."""
        engine = self._engine()
        state = {
            "optimisations":   [{"id": "o1", "title": "Opt A", "saving": "$5"}],
            "stuck_workflows": [{"id": "w1", "name": "WF1", "step": "step2"}],
            "hitl_pending":    [{"id": "h1", "workflow_id": "wf1", "description": "Gate"}],
        }
        recs = engine.get_recommendations("FOUNDER", state)
        priorities = [r["priority"] for r in recs]
        assert record(
            "GPE-002", "Priorities are sorted ascending",
            True, priorities == sorted(priorities),
            cause="recs.sort(key=priority)",
        )

    def test_founder_sees_all_priorities(self):
        """FOUNDER role receives all priority categories."""
        engine = self._engine()
        state = {
            "hitl_pending":    [{"id": "h1", "workflow_id": "wf1", "description": "x"}],
            "stuck_workflows": [{"id": "w1", "name": "W1",  "step": "s1"}],
            "qc_ready":        [{"id": "q1", "name": "Q1"}],
            "config_gaps":     [{"key": "DEEPINFRA_API_KEY", "description": "Missing key"}],
            "optimisations":   [{"id": "o1", "title": "Opt", "saving": "$1"}],
        }
        recs = engine.get_recommendations("FOUNDER", state)
        assert record(
            "GPE-003", "FOUNDER gets 5 recommendations",
            5, len(recs),
            cause="All 5 priority tiers populated",
        )

    def test_viewer_limited_recs(self):
        """VIEWER role does not see config_gaps or optimisations."""
        engine = self._engine()
        state = {
            "config_gaps":   [{"key": "DEEPINFRA_API_KEY", "description": "Missing"}],
            "optimisations": [{"id": "o1", "title": "Opt", "saving": "$1"}],
        }
        recs = engine.get_recommendations("VIEWER", state)
        assert record(
            "GPE-004", "VIEWER gets 0 recs (no admin_config or view_all)",
            0, len(recs),
            cause="VIEWER only has view_assigned permission",
        )

    def test_operator_sees_hitl_and_stuck(self):
        """OPERATOR role sees HITL gates and stuck workflows."""
        engine = self._engine()
        state = {
            "hitl_pending":    [{"id": "h1", "workflow_id": "wf1", "description": "Gate"}],
            "stuck_workflows": [{"id": "w1", "name": "W1", "step": "s1"}],
            "config_gaps":     [{"key": "KEY", "description": "Missing"}],
        }
        recs = engine.get_recommendations("OPERATOR", state)
        priorities = {r["priority"] for r in recs}
        assert record(
            "GPE-005", "OPERATOR sees HITL (1) and stuck (2)",
            True, 1 in priorities and 2 in priorities,
        )
        assert record(
            "GPE-006", "OPERATOR does NOT see config gaps (4)",
            True, 4 not in priorities,
            cause="OPERATOR lacks admin_config permission",
        )

    def test_rec_has_required_fields(self):
        """Each recommendation dict has all required fields."""
        engine = self._engine()
        state = {"hitl_pending": [{"id": "h1", "workflow_id": "wf1", "description": "x"}]}
        recs = engine.get_recommendations("FOUNDER", state)
        assert len(recs) == 1
        rec = recs[0]
        required = {"priority", "priority_name", "element_id", "title", "description", "action_url"}
        missing = required - rec.keys()
        assert record(
            "GPE-007", "Recommendation has all required fields",
            set(), missing,
            cause="Recommendation.to_dict() should return all fields",
        )

    def test_get_critical_path_empty_id(self):
        """get_critical_path with empty string returns []."""
        engine = self._engine()
        result = engine.get_critical_path("")
        assert record(
            "GPE-008", "Empty workflow_id returns []",
            [], result,
        )

    def test_get_critical_path_returns_7_phases(self):
        """get_critical_path for any workflow_id returns 7 MFGC phases."""
        engine = self._engine()
        result = engine.get_critical_path("wf-test-123")
        assert record(
            "GPE-009", "Critical path has 7 MFGC phases",
            7, len(result),
            cause="MFGC defines 7 phases: EXPAND, TYPE, SHOW, COUNTS, COLLAPSE, SIZE, TEST",
        )

    def test_critical_path_has_test_gate(self):
        """The TEST phase is marked as requires_hitl=True."""
        engine = self._engine()
        result = engine.get_critical_path("wf-abc")
        test_phase = next((p for p in result if p["phase"] == "TEST"), None)
        assert test_phase is not None
        assert record(
            "GPE-010", "TEST phase requires_hitl is True",
            True, test_phase.get("requires_hitl"),
        )

    def test_get_permissions_founder(self):
        """FOUNDER has override_gate and view_all."""
        engine = self._engine()
        perms = engine.get_permissions("FOUNDER")
        assert "override_gate" in perms
        assert "view_all" in perms

    def test_get_permissions_unknown_role(self):
        """Unknown role defaults to view_assigned only."""
        engine = self._engine()
        perms = engine.get_permissions("UNKNOWN_ROLE")
        assert record(
            "GPE-011", "Unknown role gets view_assigned",
            {"view_assigned"}, perms,
        )

    def test_recommendation_element_id_format(self):
        """HITL element IDs use 'hitl-' prefix."""
        engine = self._engine()
        state = {"hitl_pending": [{"id": "abc123", "workflow_id": "wf1", "description": "x"}]}
        recs = engine.get_recommendations("FOUNDER", state)
        assert recs[0]["element_id"] == "hitl-abc123"

    def test_multiple_hitl_items_all_included(self):
        """Multiple HITL items all appear in recommendations."""
        engine = self._engine()
        state = {
            "hitl_pending": [
                {"id": "h1", "workflow_id": "w1", "description": "Gate 1"},
                {"id": "h2", "workflow_id": "w2", "description": "Gate 2"},
                {"id": "h3", "workflow_id": "w3", "description": "Gate 3"},
            ]
        }
        recs = engine.get_recommendations("FOUNDER", state)
        assert record(
            "GPE-012", "All 3 HITL items included",
            3, len(recs),
        )

    def test_none_state_values_handled(self):
        """None values in system_state lists don't crash the engine."""
        engine = self._engine()
        state = {
            "hitl_pending":    None,
            "stuck_workflows": None,
            "qc_ready":        None,
            "config_gaps":     None,
            "optimisations":   None,
        }
        recs = engine.get_recommendations("FOUNDER", state)
        assert isinstance(recs, list)
        assert len(recs) == 0


# ---------------------------------------------------------------------------
# Priority enum
# ---------------------------------------------------------------------------

class TestPriorityEnum:
    def test_priority_values_ascending(self):
        """Priority enum values increase with urgency (1=most urgent)."""
        from src.golden_path_engine import Priority
        assert Priority.HITL_GATE < Priority.STUCK_PROCESS
        assert Priority.STUCK_PROCESS < Priority.QC_READY
        assert Priority.QC_READY < Priority.CONFIG_GAP
        assert Priority.CONFIG_GAP < Priority.OPTIMISATION

    def test_priority_int_comparable(self):
        """Priority values can be used in arithmetic comparisons."""
        from src.golden_path_engine import Priority
        assert Priority.HITL_GATE.value == 1
        assert Priority.OPTIMISATION.value == 5


# ---------------------------------------------------------------------------
# Recommendation dataclass
# ---------------------------------------------------------------------------

class TestRecommendation:
    def test_to_dict_round_trip(self):
        """Recommendation.to_dict() includes all expected keys."""
        from src.golden_path_engine import Recommendation, Priority
        rec = Recommendation(
            priority=Priority.HITL_GATE,
            element_id="hitl-xyz",
            title="Test Gate",
            description="Needs human approval",
            action_url="/terminal_orchestrator.html#hitl",
            workflow_id="wf-1",
            metadata={"extra": "data"},
        )
        d = rec.to_dict()
        assert d["priority"] == 1
        assert d["priority_name"] == "HITL_GATE"
        assert d["element_id"] == "hitl-xyz"
        assert d["title"] == "Test Gate"
        assert d["action_url"] == "/terminal_orchestrator.html#hitl"
        assert d["workflow_id"] == "wf-1"
        assert d["metadata"] == {"extra": "data"}

    def test_default_metadata_is_empty_dict(self):
        """Recommendation metadata defaults to empty dict, not None."""
        from src.golden_path_engine import Recommendation, Priority
        rec = Recommendation(
            priority=Priority.QC_READY,
            element_id="qc-1",
            title="QC Ready",
            description="Item ready",
            action_url="/",
        )
        d = rec.to_dict()
        assert d["metadata"] == {}

    def test_default_workflow_id_is_none(self):
        """Recommendation workflow_id defaults to None."""
        from src.golden_path_engine import Recommendation, Priority
        rec = Recommendation(
            priority=Priority.CONFIG_GAP,
            element_id="cfg-1",
            title="Config Gap",
            description="Missing key",
            action_url="/terminal_integrations.html",
        )
        assert rec.workflow_id is None
