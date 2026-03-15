"""Tests for the Wingman Protocol module."""

import pytest
from datetime import datetime, timezone

from src.wingman_protocol import (
    BuiltinChecks,
    ExecutionRunbook,
    ValidationRule,
    ValidationResult,
    ValidationSeverity,
    WingmanPair,
    WingmanProtocol,
)


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def protocol():
    """Return a fresh WingmanProtocol instance."""
    return WingmanProtocol()


@pytest.fixture
def pair(protocol):
    """Return a protocol with one pre-created pair using the default runbook."""
    return protocol.create_pair(
        subject="test-subject",
        executor_id="exec-1",
        validator_id="val-1",
    )


# ------------------------------------------------------------------
# Runbook registration
# ------------------------------------------------------------------

class TestRunbookRegistration:

    def test_default_runbook_exists(self, protocol):
        rb = protocol.get_runbook("default")
        assert rb is not None
        assert rb.name == "Default Validation Runbook"
        assert len(rb.validation_rules) == 5

    def test_register_custom_runbook(self, protocol):
        custom = ExecutionRunbook(
            runbook_id="custom-1",
            name="Custom Runbook",
            domain="finance",
            validation_rules=[
                ValidationRule(
                    rule_id="check_has_output",
                    description="Need output",
                    check_fn_name="check_has_output",
                    severity=ValidationSeverity.BLOCK,
                ),
            ],
        )
        rid = protocol.register_runbook(custom)
        assert rid == "custom-1"
        assert protocol.get_runbook("custom-1") is not None

    def test_get_missing_runbook(self, protocol):
        assert protocol.get_runbook("nonexistent") is None


# ------------------------------------------------------------------
# Pair creation and lookup
# ------------------------------------------------------------------

class TestPairManagement:

    def test_create_pair(self, protocol):
        p = protocol.create_pair("subj", "e1", "v1")
        assert p.subject == "subj"
        assert p.executor_id == "e1"
        assert p.validator_id == "v1"
        assert p.pair_id.startswith("wp-")

    def test_get_pair(self, protocol):
        p = protocol.create_pair("subj", "e1", "v1")
        fetched = protocol.get_pair(p.pair_id)
        assert fetched is not None
        assert fetched.pair_id == p.pair_id

    def test_get_missing_pair(self, protocol):
        assert protocol.get_pair("wp-missing") is None

    def test_list_all_pairs(self, protocol):
        protocol.create_pair("a", "e1", "v1")
        protocol.create_pair("b", "e2", "v2")
        assert len(protocol.list_pairs()) == 2

    def test_list_pairs_filtered(self, protocol):
        protocol.create_pair("a", "e1", "v1")
        protocol.create_pair("b", "e2", "v2")
        protocol.create_pair("a", "e3", "v3")
        assert len(protocol.list_pairs(subject="a")) == 2
        assert len(protocol.list_pairs(subject="b")) == 1

    def test_pair_with_runbook(self, protocol):
        p = protocol.create_pair("subj", "e1", "v1", runbook_id="default")
        assert p.runbook_id == "default"


# ------------------------------------------------------------------
# Built-in validation checks
# ------------------------------------------------------------------

class TestCheckHasOutput:

    def test_pass(self):
        r = BuiltinChecks.check_has_output({"result": "some value"})
        assert r.passed is True

    def test_fail_missing(self):
        r = BuiltinChecks.check_has_output({})
        assert r.passed is False

    def test_fail_empty_string(self):
        r = BuiltinChecks.check_has_output({"result": ""})
        assert r.passed is False

    def test_fail_empty_list(self):
        r = BuiltinChecks.check_has_output({"result": []})
        assert r.passed is False


class TestCheckNoPii:

    def test_pass_no_pii(self):
        r = BuiltinChecks.check_no_pii({"result": "clean output"})
        assert r.passed is True

    def test_fail_email(self):
        r = BuiltinChecks.check_no_pii({"result": "contact user@example.com"})
        assert r.passed is False

    def test_fail_ssn(self):
        r = BuiltinChecks.check_no_pii({"result": "SSN is 123-45-6789"})
        assert r.passed is False

    def test_fail_phone(self):
        r = BuiltinChecks.check_no_pii({"result": "call 555-123-4567"})
        assert r.passed is False


class TestCheckConfidenceThreshold:

    def test_pass_above(self):
        r = BuiltinChecks.check_confidence_threshold({"confidence": 0.9})
        assert r.passed is True

    def test_pass_exactly_threshold(self):
        r = BuiltinChecks.check_confidence_threshold({"confidence": 0.5})
        assert r.passed is True

    def test_fail_below(self):
        r = BuiltinChecks.check_confidence_threshold({"confidence": 0.3})
        assert r.passed is False

    def test_skip_when_absent(self):
        r = BuiltinChecks.check_confidence_threshold({"result": "ok"})
        assert r.passed is True


class TestCheckBudgetLimit:

    def test_pass_within(self):
        r = BuiltinChecks.check_budget_limit({"cost": 50, "budget": 100})
        assert r.passed is True

    def test_fail_over(self):
        r = BuiltinChecks.check_budget_limit({"cost": 150, "budget": 100})
        assert r.passed is False

    def test_skip_no_cost(self):
        r = BuiltinChecks.check_budget_limit({"budget": 100})
        assert r.passed is True

    def test_fail_no_budget(self):
        r = BuiltinChecks.check_budget_limit({"cost": 50})
        assert r.passed is False


class TestCheckGateClearance:

    def test_pass_all_gates(self):
        r = BuiltinChecks.check_gate_clearance({
            "gates": [{"name": "g1", "passed": True}, {"name": "g2", "passed": True}],
        })
        assert r.passed is True

    def test_fail_one_gate(self):
        r = BuiltinChecks.check_gate_clearance({
            "gates": [{"name": "g1", "passed": True}, {"name": "g2", "passed": False}],
        })
        assert r.passed is False

    def test_skip_no_gates(self):
        r = BuiltinChecks.check_gate_clearance({"result": "ok"})
        assert r.passed is True


# ------------------------------------------------------------------
# End-to-end validation via protocol
# ------------------------------------------------------------------

class TestValidateOutput:

    def test_approved_clean_output(self, protocol, pair):
        result = protocol.validate_output(pair.pair_id, {
            "result": "done",
            "confidence": 0.95,
            "cost": 10,
            "budget": 100,
            "gates": [{"name": "g1", "passed": True}],
        })
        assert result["approved"] is True
        assert len(result["blocking_failures"]) == 0

    def test_rejected_missing_result(self, protocol, pair):
        result = protocol.validate_output(pair.pair_id, {})
        assert result["approved"] is False
        blocking_ids = [b["rule_id"] for b in result["blocking_failures"]]
        assert "check_has_output" in blocking_ids

    def test_rejected_pii(self, protocol, pair):
        result = protocol.validate_output(pair.pair_id, {
            "result": "email is user@example.com",
        })
        assert result["approved"] is False
        blocking_ids = [b["rule_id"] for b in result["blocking_failures"]]
        assert "check_no_pii" in blocking_ids

    def test_warning_low_confidence(self, protocol, pair):
        result = protocol.validate_output(pair.pair_id, {
            "result": "ok",
            "confidence": 0.2,
        })
        # Confidence is WARN in the default runbook, so still approved
        assert result["approved"] is True
        warn_results = [
            r for r in result["results"]
            if r["rule_id"] == "check_confidence_threshold"
        ]
        assert len(warn_results) == 1
        assert warn_results[0]["passed"] is False

    def test_rejected_over_budget(self, protocol, pair):
        result = protocol.validate_output(pair.pair_id, {
            "result": "ok",
            "cost": 200,
            "budget": 100,
        })
        assert result["approved"] is False
        blocking_ids = [b["rule_id"] for b in result["blocking_failures"]]
        assert "check_budget_limit" in blocking_ids

    def test_validation_with_missing_pair(self, protocol):
        result = protocol.validate_output("wp-missing", {"result": "ok"})
        assert result["approved"] is False

    def test_validation_with_missing_runbook(self, protocol):
        p = protocol.create_pair("s", "e", "v", runbook_id="nonexistent")
        result = protocol.validate_output(p.pair_id, {"result": "ok"})
        assert result["approved"] is False


# ------------------------------------------------------------------
# Blocking vs warning
# ------------------------------------------------------------------

class TestBlockingVsWarning:

    def test_block_severity_rejects(self, protocol, pair):
        result = protocol.validate_output(pair.pair_id, {})
        assert result["approved"] is False
        for bf in result["blocking_failures"]:
            assert bf["severity"] == "block"

    def test_warn_severity_does_not_reject(self, protocol):
        custom = ExecutionRunbook(
            runbook_id="warn-only",
            name="Warn Only",
            domain="test",
            validation_rules=[
                ValidationRule(
                    rule_id="check_confidence_threshold",
                    description="Confidence check",
                    check_fn_name="check_confidence_threshold",
                    severity=ValidationSeverity.WARN,
                ),
            ],
        )
        protocol.register_runbook(custom)
        p = protocol.create_pair("s", "e", "v", runbook_id="warn-only")
        result = protocol.validate_output(p.pair_id, {"confidence": 0.1})
        assert result["approved"] is True
        assert len(result["blocking_failures"]) == 0


# ------------------------------------------------------------------
# Validation history
# ------------------------------------------------------------------

class TestValidationHistory:

    def test_history_empty_initially(self, protocol, pair):
        assert protocol.get_validation_history(pair.pair_id) == []

    def test_history_grows(self, protocol, pair):
        protocol.validate_output(pair.pair_id, {"result": "a"})
        protocol.validate_output(pair.pair_id, {"result": "b"})
        history = protocol.get_validation_history(pair.pair_id)
        assert len(history) == 2

    def test_history_contains_expected_keys(self, protocol, pair):
        protocol.validate_output(pair.pair_id, {"result": "ok"})
        record = protocol.get_validation_history(pair.pair_id)[0]
        assert "pair_id" in record
        assert "approved" in record
        assert "results" in record
        assert "validated_at" in record

    def test_history_for_unknown_pair(self, protocol):
        assert protocol.get_validation_history("wp-none") == []


# ------------------------------------------------------------------
# Status reporting
# ------------------------------------------------------------------

class TestStatus:

    def test_initial_status(self, protocol):
        status = protocol.get_status()
        assert status["total_pairs"] == 0
        assert status["total_runbooks"] == 1  # default
        assert status["total_validations"] == 0

    def test_status_after_operations(self, protocol, pair):
        protocol.validate_output(pair.pair_id, {"result": "ok"})
        protocol.validate_output(pair.pair_id, {})
        status = protocol.get_status()
        assert status["total_pairs"] == 1
        assert status["total_validations"] == 2
        assert status["total_approved"] == 1
        assert status["total_rejected"] == 1
