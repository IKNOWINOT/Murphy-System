"""Tests for gate_execution_wiring module."""

import uuid

import pytest


from gate_execution_wiring import (
    GATE_SEQUENCE,
    GateDecision,
    GateEvaluation,
    GateExecutionWiring,
    GatePolicy,
    GateType,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_evaluator(decision: GateDecision, reason: str = "ok"):
    """Return a simple evaluator callable that always returns *decision*."""

    def _evaluator(task, session_id):
        return GateEvaluation(
            gate_id=str(uuid.uuid4()),
            gate_type=GateType.QA,  # overwritten by wiring
            decision=decision,
            reason=reason,
            policy=GatePolicy.WARN,  # overwritten by wiring
            evaluated_at="2025-01-01T00:00:00",
        )

    return _evaluator


def _make_executor(result=None):
    """Return a simple task executor callable."""

    def _executor(task):
        return result if result is not None else {"executed": True}

    return _executor


# ---------------------------------------------------------------------------
# Registration & evaluation
# ---------------------------------------------------------------------------

class TestGateRegistrationAndEvaluation:
    def test_register_single_gate(self):
        w = GateExecutionWiring()
        w.register_gate(GateType.QA, _make_evaluator(GateDecision.APPROVED))
        assert GateType.QA in w._gates

    def test_evaluate_returns_one_per_registered_gate(self):
        w = GateExecutionWiring()
        w.register_gate(GateType.QA, _make_evaluator(GateDecision.APPROVED))
        w.register_gate(GateType.BUDGET, _make_evaluator(GateDecision.APPROVED))
        evals = w.evaluate_gates({"id": "t1"}, "s1")
        assert len(evals) == 2

    def test_evaluate_respects_sequence_order(self):
        w = GateExecutionWiring()
        w.register_gate(GateType.HITL, _make_evaluator(GateDecision.APPROVED))
        w.register_gate(GateType.COMPLIANCE, _make_evaluator(GateDecision.APPROVED))
        evals = w.evaluate_gates({"id": "t1"}, "s1")
        # COMPLIANCE comes before HITL in GATE_SEQUENCE
        assert evals[0].gate_type == GateType.COMPLIANCE
        assert evals[1].gate_type == GateType.HITL

    def test_unregistered_types_are_skipped(self):
        w = GateExecutionWiring()
        w.register_gate(GateType.EXECUTIVE, _make_evaluator(GateDecision.APPROVED))
        evals = w.evaluate_gates({"id": "t1"}, "s1")
        types = [e.gate_type for e in evals]
        assert types == [GateType.EXECUTIVE]

    def test_evaluator_exception_produces_blocked(self):
        def bad_evaluator(task, session_id):
            raise RuntimeError("boom")

        w = GateExecutionWiring()
        w.register_gate(GateType.QA, bad_evaluator, policy=GatePolicy.WARN)
        evals = w.evaluate_gates({"id": "t1"}, "s1")
        assert len(evals) == 1
        assert evals[0].decision == GateDecision.BLOCKED
        assert "boom" in evals[0].reason


# ---------------------------------------------------------------------------
# Policy enforcement
# ---------------------------------------------------------------------------

class TestPolicyEnforcement:
    def test_enforce_blocked_prevents_execution(self):
        w = GateExecutionWiring()
        w.register_gate(
            GateType.COMPLIANCE,
            _make_evaluator(GateDecision.BLOCKED, "non-compliant"),
            policy=GatePolicy.ENFORCE,
        )
        allowed, evals = w.can_execute({"id": "t1"}, "s1")
        assert allowed is False
        assert evals[0].decision == GateDecision.BLOCKED

    def test_enforce_approved_allows_execution(self):
        w = GateExecutionWiring()
        w.register_gate(
            GateType.COMPLIANCE,
            _make_evaluator(GateDecision.APPROVED),
            policy=GatePolicy.ENFORCE,
        )
        allowed, _ = w.can_execute({"id": "t1"}, "s1")
        assert allowed is True

    def test_warn_blocked_still_allows_execution(self):
        w = GateExecutionWiring()
        w.register_gate(
            GateType.QA,
            _make_evaluator(GateDecision.BLOCKED, "quality issue"),
            policy=GatePolicy.WARN,
        )
        allowed, _ = w.can_execute({"id": "t1"}, "s1")
        assert allowed is True

    def test_audit_blocked_still_allows_execution(self):
        w = GateExecutionWiring()
        w.register_gate(
            GateType.BUDGET,
            _make_evaluator(GateDecision.BLOCKED, "over budget"),
            policy=GatePolicy.AUDIT,
        )
        allowed, _ = w.can_execute({"id": "t1"}, "s1")
        assert allowed is True

    def test_enforce_escalated_blocks(self):
        w = GateExecutionWiring()
        w.register_gate(
            GateType.EXECUTIVE,
            _make_evaluator(GateDecision.ESCALATED, "needs exec sign-off"),
            policy=GatePolicy.ENFORCE,
        )
        allowed, _ = w.can_execute({"id": "t1"}, "s1")
        assert allowed is False

    def test_enforce_needs_review_allows(self):
        w = GateExecutionWiring()
        w.register_gate(
            GateType.OPERATIONS,
            _make_evaluator(GateDecision.NEEDS_REVIEW),
            policy=GatePolicy.ENFORCE,
        )
        allowed, _ = w.can_execute({"id": "t1"}, "s1")
        assert allowed is True


# ---------------------------------------------------------------------------
# Gate chain sequencing / short-circuit
# ---------------------------------------------------------------------------

class TestGateChainSequencing:
    def test_enforce_block_short_circuits_later_gates(self):
        call_log = []

        def compliance_eval(task, sid):
            call_log.append("compliance")
            return GateEvaluation(
                gate_id="c1", gate_type=GateType.COMPLIANCE,
                decision=GateDecision.BLOCKED, reason="fail",
                policy=GatePolicy.ENFORCE,
                evaluated_at="2025-01-01T00:00:00",
            )

        def qa_eval(task, sid):
            call_log.append("qa")
            return GateEvaluation(
                gate_id="q1", gate_type=GateType.QA,
                decision=GateDecision.APPROVED, reason="ok",
                policy=GatePolicy.ENFORCE,
                evaluated_at="2025-01-01T00:00:00",
            )

        w = GateExecutionWiring()
        w.register_gate(GateType.COMPLIANCE, compliance_eval, GatePolicy.ENFORCE)
        w.register_gate(GateType.QA, qa_eval, GatePolicy.ENFORCE)

        evals = w.evaluate_gates({"id": "t1"}, "s1")
        assert call_log == ["compliance"]
        assert len(evals) == 1

    def test_warn_block_does_not_short_circuit(self):
        call_log = []

        def compliance_eval(task, sid):
            call_log.append("compliance")
            return GateEvaluation(
                gate_id="c1", gate_type=GateType.COMPLIANCE,
                decision=GateDecision.BLOCKED, reason="fail",
                policy=GatePolicy.WARN,
                evaluated_at="2025-01-01T00:00:00",
            )

        def qa_eval(task, sid):
            call_log.append("qa")
            return GateEvaluation(
                gate_id="q1", gate_type=GateType.QA,
                decision=GateDecision.APPROVED, reason="ok",
                policy=GatePolicy.WARN,
                evaluated_at="2025-01-01T00:00:00",
            )

        w = GateExecutionWiring()
        w.register_gate(GateType.COMPLIANCE, compliance_eval, GatePolicy.WARN)
        w.register_gate(GateType.QA, qa_eval, GatePolicy.WARN)

        evals = w.evaluate_gates({"id": "t1"}, "s1")
        assert call_log == ["compliance", "qa"]
        assert len(evals) == 2


# ---------------------------------------------------------------------------
# Execution wrapping
# ---------------------------------------------------------------------------

class TestWrapExecution:
    def test_approved_gates_run_executor(self):
        w = GateExecutionWiring()
        w.register_gate(GateType.QA, _make_evaluator(GateDecision.APPROVED))
        result = w.wrap_execution({"id": "t1"}, _make_executor(), "s1")
        assert result["status"] == "completed"
        assert result["executed"] is True
        assert "gate_evaluations" in result

    def test_blocked_enforce_returns_blocked_status(self):
        w = GateExecutionWiring()
        w.register_gate(
            GateType.COMPLIANCE,
            _make_evaluator(GateDecision.BLOCKED),
            GatePolicy.ENFORCE,
        )
        result = w.wrap_execution({"id": "t1"}, _make_executor(), "s1")
        assert result["status"] == "blocked"
        assert len(result["blocking_gates"]) == 1

    def test_executor_exception_returns_error(self):
        def bad_executor(task):
            raise ValueError("executor crash")

        w = GateExecutionWiring()
        w.register_gate(GateType.QA, _make_evaluator(GateDecision.APPROVED))
        result = w.wrap_execution({"id": "t1"}, bad_executor, "s1")
        assert result["status"] == "error"
        assert "executor crash" in result["error"]

    def test_non_dict_executor_result(self):
        w = GateExecutionWiring()
        w.register_gate(GateType.QA, _make_evaluator(GateDecision.APPROVED))
        result = w.wrap_execution(
            {"id": "t1"}, lambda t: 42, "s1"
        )
        assert result["status"] == "completed"
        assert result["result"] == 42


# ---------------------------------------------------------------------------
# HITL gate behaviour
# ---------------------------------------------------------------------------

class TestHITLGate:
    def test_hitl_needs_review_with_enforce_allows(self):
        w = GateExecutionWiring()
        w.register_gate(
            GateType.HITL,
            _make_evaluator(GateDecision.NEEDS_REVIEW, "human review needed"),
            GatePolicy.ENFORCE,
        )
        allowed, evals = w.can_execute({"id": "t1"}, "s1")
        assert allowed is True
        assert evals[0].decision == GateDecision.NEEDS_REVIEW

    def test_hitl_blocked_with_enforce_blocks(self):
        w = GateExecutionWiring()
        w.register_gate(
            GateType.HITL,
            _make_evaluator(GateDecision.BLOCKED, "human rejected"),
            GatePolicy.ENFORCE,
        )
        allowed, _ = w.can_execute({"id": "t1"}, "s1")
        assert allowed is False

    def test_hitl_evaluated_last_in_sequence(self):
        w = GateExecutionWiring()
        w.register_gate(GateType.HITL, _make_evaluator(GateDecision.APPROVED))
        w.register_gate(GateType.BUDGET, _make_evaluator(GateDecision.APPROVED))
        evals = w.evaluate_gates({"id": "t1"}, "s1")
        assert evals[-1].gate_type == GateType.HITL


# ---------------------------------------------------------------------------
# Gate history
# ---------------------------------------------------------------------------

class TestGateHistory:
    def test_history_records_evaluations(self):
        w = GateExecutionWiring()
        w.register_gate(GateType.QA, _make_evaluator(GateDecision.APPROVED))
        w.evaluate_gates({"id": "t1"}, "s1")
        history = w.get_gate_history()
        assert len(history) == 1
        assert history[0]["session_id"] == "s1"

    def test_history_filters_by_session(self):
        w = GateExecutionWiring()
        w.register_gate(GateType.QA, _make_evaluator(GateDecision.APPROVED))
        w.evaluate_gates({"id": "t1"}, "s1")
        w.evaluate_gates({"id": "t2"}, "s2")
        assert len(w.get_gate_history("s1")) == 1
        assert len(w.get_gate_history("s2")) == 1
        assert len(w.get_gate_history()) == 2

    def test_history_returns_empty_for_unknown_session(self):
        w = GateExecutionWiring()
        assert w.get_gate_history("nope") == []


# ---------------------------------------------------------------------------
# Status reporting
# ---------------------------------------------------------------------------

class TestStatusReporting:
    def test_status_shows_registered_gates(self):
        w = GateExecutionWiring()
        w.register_gate(GateType.QA, _make_evaluator(GateDecision.APPROVED), GatePolicy.ENFORCE)
        w.register_gate(GateType.BUDGET, _make_evaluator(GateDecision.APPROVED), GatePolicy.AUDIT)
        status = w.get_status()
        assert status["total_registered"] == 2
        assert status["registered_gates"]["qa"] == "enforce"
        assert status["registered_gates"]["budget"] == "audit"

    def test_status_default_policy(self):
        w = GateExecutionWiring(default_policy=GatePolicy.AUDIT)
        assert w.get_status()["default_policy"] == "audit"

    def test_status_total_evaluations(self):
        w = GateExecutionWiring()
        w.register_gate(GateType.QA, _make_evaluator(GateDecision.APPROVED))
        w.evaluate_gates({"id": "t1"}, "s1")
        assert w.get_status()["total_evaluations"] == 1

    def test_status_gate_sequence(self):
        w = GateExecutionWiring()
        seq = w.get_status()["gate_sequence"]
        assert seq == [gt.value for gt in GATE_SEQUENCE]


# ---------------------------------------------------------------------------
# Mixed policy scenarios
# ---------------------------------------------------------------------------

class TestMixedPolicies:
    def test_audit_and_warn_failures_with_enforce_pass(self):
        """All non-enforce gates fail but the enforce gate passes → allowed."""
        w = GateExecutionWiring()
        w.register_gate(GateType.COMPLIANCE, _make_evaluator(GateDecision.APPROVED), GatePolicy.ENFORCE)
        w.register_gate(GateType.BUDGET, _make_evaluator(GateDecision.BLOCKED), GatePolicy.AUDIT)
        w.register_gate(GateType.QA, _make_evaluator(GateDecision.BLOCKED), GatePolicy.WARN)
        allowed, evals = w.can_execute({"id": "t1"}, "s1")
        assert allowed is True
        assert len(evals) == 3

    def test_one_enforce_fail_among_many_passes(self):
        """Single enforce failure among passes → blocked."""
        w = GateExecutionWiring()
        w.register_gate(GateType.COMPLIANCE, _make_evaluator(GateDecision.APPROVED), GatePolicy.ENFORCE)
        w.register_gate(GateType.BUDGET, _make_evaluator(GateDecision.BLOCKED), GatePolicy.ENFORCE)
        w.register_gate(GateType.QA, _make_evaluator(GateDecision.APPROVED), GatePolicy.WARN)
        allowed, evals = w.can_execute({"id": "t1"}, "s1")
        assert allowed is False

    def test_all_approved_allows(self):
        w = GateExecutionWiring()
        for gt in GateType:
            w.register_gate(gt, _make_evaluator(GateDecision.APPROVED), GatePolicy.ENFORCE)
        allowed, evals = w.can_execute({"id": "t1"}, "s1")
        assert allowed is True
        assert len(evals) == len(GateType)

    def test_default_policy_applied_when_none_specified(self):
        w = GateExecutionWiring(default_policy=GatePolicy.ENFORCE)
        w.register_gate(GateType.QA, _make_evaluator(GateDecision.BLOCKED))
        _, evals = w.can_execute({"id": "t1"}, "s1")
        assert evals[0].policy == GatePolicy.ENFORCE
