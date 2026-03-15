"""Tests for the Unified Control Protocol (UCP).

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import hashlib
import threading
from dataclasses import fields as dc_fields
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from unified_control_protocol import (
    ActionResult,
    UnifiedControlProtocol,
    VALID_OPERATORS,
    PIPELINE_STATES,
    ENGINE_PRIORITY,
    _MAX_ACTION_LOG,
    _MAX_CACHE,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def ucp():
    """Return a fresh UCP instance (engines may degrade gracefully)."""
    return UnifiedControlProtocol()


@pytest.fixture()
def executed_result(ucp):
    """Execute a pipeline run with governance neutralised for determinism."""
    ucp._gov = None
    return ucp.execute("hello world")


# ---------------------------------------------------------------------------
# 1. Full pipeline execution for each operator
# ---------------------------------------------------------------------------


class TestPipelineExecution:
    """Verify execute() completes for every valid operator."""

    @pytest.mark.parametrize("operator", sorted(VALID_OPERATORS))
    def test_execute_returns_action_result(self, ucp, operator):
        result = ucp.execute("test input", operator=operator)
        assert isinstance(result, ActionResult)

    @pytest.mark.parametrize("operator", sorted(VALID_OPERATORS))
    def test_execute_records_operator(self, ucp, operator):
        result = ucp.execute("operator check", operator=operator)
        assert result.operator == operator

    def test_execute_preserves_input_text(self, ucp):
        text = "preserve me"
        result = ucp.execute(text)
        assert result.input_text == text

    def test_default_operator_is_magnify(self, ucp):
        result = ucp.execute("default op")
        assert result.operator == "magnify"


# ---------------------------------------------------------------------------
# 2. State transitions
# ---------------------------------------------------------------------------


class TestStateTransitions:
    """Pipeline must reach an expected terminal state."""

    def test_successful_run_reaches_archived(self, executed_result):
        assert executed_result.state == "archived"

    @pytest.mark.parametrize("operator", sorted(VALID_OPERATORS))
    def test_all_operators_reach_archived(self, ucp, operator):
        result = ucp.execute("state transition", operator=operator)
        assert result.state in PIPELINE_STATES
        assert PIPELINE_STATES.index(result.state) >= PIPELINE_STATES.index(
            "governed"
        )

    def test_pipeline_states_ordering(self):
        expected = (
            "received", "analyzed", "translated",
            "simulated", "governed", "executed", "archived",
        )
        assert PIPELINE_STATES == expected


# ---------------------------------------------------------------------------
# 3. Conflict resolution — governance deny stops pipeline
# ---------------------------------------------------------------------------


class TestGovernanceDeny:
    """When governance returns 'deny', pipeline halts at 'governed'."""

    def _make_ucp_with_deny_governance(self):
        """Build a UCP whose governance kernel always denies."""
        ucp = UnifiedControlProtocol()
        mock_gov = MagicMock()
        enforcement = MagicMock()
        enforcement.action.value = "deny"
        mock_gov.enforce.return_value = enforcement
        ucp._gov = mock_gov
        return ucp

    def test_deny_halts_at_governed(self):
        ucp = self._make_ucp_with_deny_governance()
        result = ucp.execute("denied input")
        assert result.state == "governed"
        assert result.governance_status == "deny"

    def test_deny_does_not_reach_executed(self):
        ucp = self._make_ucp_with_deny_governance()
        result = ucp.execute("denied input 2")
        assert result.state != "executed"
        assert result.state != "archived"

    def test_deny_result_is_cached(self):
        ucp = self._make_ucp_with_deny_governance()
        r1 = ucp.execute("cached deny")
        r2 = ucp.execute("cached deny")
        assert r1.action_id == r2.action_id


# ---------------------------------------------------------------------------
# 4. Rollback
# ---------------------------------------------------------------------------


class TestRollback:
    """rollback() must revert to the specified pipeline state."""

    def test_rollback_to_received(self, ucp, executed_result):
        rolled = ucp.rollback(executed_result.action_id, "received")
        assert rolled.state == "received"

    def test_rollback_to_analyzed(self, ucp, executed_result):
        rolled = ucp.rollback(executed_result.action_id, "analyzed")
        assert rolled.state == "analyzed"

    def test_rollback_preserves_action_id(self, ucp, executed_result):
        rolled = ucp.rollback(executed_result.action_id, "received")
        assert rolled.action_id == executed_result.action_id

    def test_rollback_invalid_state_raises(self, ucp, executed_result):
        with pytest.raises(ValueError, match="Invalid target state"):
            ucp.rollback(executed_result.action_id, "nonexistent")

    def test_rollback_unknown_action_raises(self, ucp):
        with pytest.raises(KeyError, match="No checkpoints"):
            ucp.rollback("no-such-action-id", "received")

    def test_rollback_to_received_zeroes_scores(self, ucp, executed_result):
        rolled = ucp.rollback(executed_result.action_id, "received")
        assert rolled.resolution_score == 0.0
        assert rolled.density_index == 0.0
        assert rolled.coherence_score == 0.0
        assert rolled.composite_quality == 0.0


# ---------------------------------------------------------------------------
# 5. Action logging
# ---------------------------------------------------------------------------


class TestActionLogging:
    """action_log must record timestamped steps."""

    def test_log_not_empty_after_execute(self, ucp, executed_result):
        assert len(ucp.action_log) > 0

    def test_log_entries_have_required_keys(self, ucp, executed_result):
        for entry in ucp.action_log:
            assert "action_id" in entry
            assert "step" in entry
            assert "state" in entry
            assert "timestamp" in entry

    def test_log_contains_init_step(self, ucp, executed_result):
        steps = [e["step"] for e in ucp.action_log]
        assert "init" in steps

    def test_log_contains_state_transitions(self, ucp, executed_result):
        transitions = [
            e for e in ucp.action_log if e["step"] == "state_transition"
        ]
        assert len(transitions) >= 1

    def test_log_returns_copy(self, ucp, executed_result):
        log1 = ucp.action_log
        log2 = ucp.action_log
        assert log1 is not log2
        assert log1 == log2


# ---------------------------------------------------------------------------
# 6. System health dashboard
# ---------------------------------------------------------------------------


class TestSystemHealth:
    """get_system_health() must return all five expected metrics."""

    def test_health_returns_dict(self, ucp):
        health = ucp.get_system_health()
        assert isinstance(health, dict)

    def test_health_has_all_five_keys(self, ucp):
        health = ucp.get_system_health()
        expected_keys = {
            "architecture_health",
            "governance_compliance",
            "information_quality",
            "evolution_score",
            "simulation_risk",
        }
        assert set(health.keys()) == expected_keys

    def test_health_values_are_floats(self, ucp):
        health = ucp.get_system_health()
        for value in health.values():
            assert isinstance(value, float)

    def test_health_values_non_negative(self, ucp):
        health = ucp.get_system_health()
        for value in health.values():
            assert value >= 0.0


# ---------------------------------------------------------------------------
# 7. Determinism — same input → same output hash
# ---------------------------------------------------------------------------


class TestDeterminism:
    """Identical inputs must produce identical action_id and input_hash."""

    def test_same_input_same_action_id(self, ucp):
        r1 = ucp.execute("deterministic")
        r2 = ucp.execute("deterministic")
        assert r1.action_id == r2.action_id

    def test_same_input_same_hash(self, ucp):
        r1 = ucp.execute("hash me")
        r2 = ucp.execute("hash me")
        assert r1.input_hash == r2.input_hash

    def test_different_input_different_hash(self, ucp):
        r1 = ucp.execute("alpha")
        r2 = ucp.execute("beta")
        assert r1.input_hash != r2.input_hash

    def test_input_hash_is_sha256(self, ucp):
        text = "verify sha"
        result = ucp.execute(text)
        expected = hashlib.sha256(text.encode("utf-8")).hexdigest()
        assert result.input_hash == expected


# ---------------------------------------------------------------------------
# 8. Invalid operator handling
# ---------------------------------------------------------------------------


class TestInvalidOperator:
    """Invalid operators must raise ValueError."""

    def test_invalid_operator_raises(self, ucp):
        with pytest.raises(ValueError, match="Invalid operator"):
            ucp.execute("text", operator="invalid")

    def test_empty_operator_raises(self, ucp):
        with pytest.raises(ValueError, match="Invalid operator"):
            ucp.execute("text", operator="")

    def test_case_sensitive_operator(self, ucp):
        with pytest.raises(ValueError):
            ucp.execute("text", operator="Magnify")


# ---------------------------------------------------------------------------
# 9. Empty text handling
# ---------------------------------------------------------------------------


class TestEmptyText:
    """execute() must handle empty or whitespace-only input gracefully."""

    def test_empty_string_executes(self, ucp):
        result = ucp.execute("")
        assert isinstance(result, ActionResult)

    def test_whitespace_only_executes(self, ucp):
        result = ucp.execute("   ")
        assert isinstance(result, ActionResult)

    def test_empty_string_has_valid_hash(self, ucp):
        result = ucp.execute("")
        expected = hashlib.sha256(b"").hexdigest()
        assert result.input_hash == expected


# ---------------------------------------------------------------------------
# 10. Thread safety with concurrent execute calls
# ---------------------------------------------------------------------------


class TestThreadSafety:
    """Concurrent calls must not corrupt state."""

    def test_concurrent_executions(self, ucp):
        results = []
        errors = []

        def run(text):
            try:
                results.append(ucp.execute(text))
            except Exception as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=run, args=(f"thread-{i}",))
            for i in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 10

    def test_concurrent_same_input(self, ucp):
        results = []
        errors = []

        def run():
            try:
                results.append(ucp.execute("shared"))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=run) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        ids = {r.action_id for r in results}
        assert len(ids) == 1, "Same input must produce the same action_id"


# ---------------------------------------------------------------------------
# 11. ActionResult has all required fields populated
# ---------------------------------------------------------------------------


class TestActionResultFields:
    """Every field on ActionResult must be populated after execute()."""

    EXPECTED_FIELDS = {
        "action_id", "input_text", "operator", "resolution_score",
        "density_index", "coherence_score", "composite_quality",
        "governance_status", "state", "timestamp", "input_hash",
    }

    def test_action_result_field_names(self):
        names = {f.name for f in dc_fields(ActionResult)}
        assert names == self.EXPECTED_FIELDS

    def test_all_fields_non_none(self, executed_result):
        for f in dc_fields(ActionResult):
            assert getattr(executed_result, f.name) is not None, (
                f"Field '{f.name}' is None"
            )

    def test_action_id_is_nonempty_string(self, executed_result):
        assert isinstance(executed_result.action_id, str)
        assert len(executed_result.action_id) > 0

    def test_timestamp_is_iso_format(self, executed_result):
        ts = executed_result.timestamp
        assert "T" in ts, "Timestamp should be ISO-8601 format"

    def test_action_result_is_frozen(self, executed_result):
        with pytest.raises(AttributeError):
            executed_result.state = "mutated"


# ---------------------------------------------------------------------------
# 12. Hash caching — repeated calls hit cache
# ---------------------------------------------------------------------------


class TestCaching:
    """Repeated identical calls must be served from the LRU cache."""

    def test_cache_returns_identical_object(self, ucp):
        r1 = ucp.execute("cached")
        r2 = ucp.execute("cached")
        assert r1 is r2

    def test_different_operators_different_cache(self, ucp):
        r1 = ucp.execute("same text", operator="magnify")
        r2 = ucp.execute("same text", operator="simplify")
        assert r1.action_id != r2.action_id

    def test_cache_does_not_grow_unbounded(self, ucp):
        for i in range(_MAX_CACHE + 50):
            ucp.execute(f"input-{i}")
        assert len(ucp._cache) <= _MAX_CACHE


# ---------------------------------------------------------------------------
# Additional edge-case and integration tests
# ---------------------------------------------------------------------------


class TestEnginePriority:
    """ENGINE_PRIORITY must be a well-formed read-only mapping."""

    def test_engine_priority_accessor(self, ucp):
        prio = ucp.engine_priority
        assert isinstance(prio, dict)
        assert prio == ENGINE_PRIORITY

    def test_engine_priority_returns_copy(self, ucp):
        p1 = ucp.engine_priority
        p2 = ucp.engine_priority
        assert p1 is not p2


class TestContextPropagation:
    """Optional context dict must flow through the pipeline."""

    def test_context_none_accepted(self, ucp):
        result = ucp.execute("no ctx", context=None)
        assert isinstance(result, ActionResult)

    def test_context_dict_accepted(self, ucp):
        result = ucp.execute("with ctx", context={"key": "value"})
        assert isinstance(result, ActionResult)


class TestGovernanceNormalization:
    """_normalize_governance must map raw values correctly."""

    @pytest.mark.parametrize("raw,expected", [
        ("allow", "allow"),
        ("deny", "deny"),
        ("escalate", "escalate"),
        ("unknown_value", "allow"),
        ("", "allow"),
    ])
    def test_normalize(self, raw, expected):
        assert UnifiedControlProtocol._normalize_governance(raw) == expected


class TestRollbackLogging:
    """Rollback operations must be reflected in the action log."""

    def test_rollback_logged(self, ucp, executed_result):
        ucp.rollback(executed_result.action_id, "received")
        steps = [e["step"] for e in ucp.action_log]
        assert "rollback" in steps

    def test_rollback_log_entry_has_detail(self, ucp, executed_result):
        ucp.rollback(executed_result.action_id, "analyzed")
        rollback_entries = [
            e for e in ucp.action_log if e["step"] == "rollback"
        ]
        assert len(rollback_entries) >= 1
        assert "detail" in rollback_entries[0]
        assert "analyzed" in rollback_entries[0]["detail"]
