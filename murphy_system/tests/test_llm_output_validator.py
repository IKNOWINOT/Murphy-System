"""
Tests for llm_output_validator.py — envelope-level validation (Gap CFP-6).

Covers:
- Schema registration
- Valid output passes validation
- Invalid output fails with specific errors
- validate_and_reject() returns None for invalid
- Pre-registered schemas exist for core output types
"""

import os


import pytest
from llm_output_validator import (
    LLMOutputEnvelope,
    LLMOutputValidator,
    ValidationResult,
    LLMGeneratedExpert,
    LLMGeneratedGate,
    LLMGeneratedConstraint,
    LLMExpansionResult,
)


# ======================================================================
# Schema registration
# ======================================================================

class TestSchemaRegistration:
    """register_schema() stores schemas that are used by validate()."""

    def setup_method(self):
        self.validator = LLMOutputValidator()

    def test_register_custom_schema(self):
        try:
            from pydantic import BaseModel, Field

            class MyOutput(BaseModel):
                label: str
                score: float = Field(ge=0.0, le=1.0)

        except ImportError:
            pytest.skip("pydantic not installed")

        self.validator.register_schema("my_output", MyOutput)
        envelope = LLMOutputEnvelope(
            output_type="my_output",
            parsed_output={"label": "ok", "score": 0.9},
        )
        result = self.validator.validate(envelope)
        assert result.valid is True
        assert result.errors == []

    def test_unknown_schema_returns_invalid(self):
        envelope = LLMOutputEnvelope(
            output_type="nonexistent_type",
            parsed_output={"x": 1},
        )
        result = self.validator.validate(envelope)
        assert result.valid is False
        assert len(result.errors) > 0


# ======================================================================
# Pre-registered schemas
# ======================================================================

class TestPreRegisteredSchemas:
    """The four core output types must be pre-registered."""

    def setup_method(self):
        self.validator = LLMOutputValidator()

    def test_generated_expert_schema_exists(self):
        assert "generated_expert" in self.validator._schemas

    def test_domain_gate_schema_exists(self):
        assert "domain_gate" in self.validator._schemas

    def test_constraint_schema_exists(self):
        assert "constraint" in self.validator._schemas

    def test_expansion_result_schema_exists(self):
        assert "expansion_result" in self.validator._schemas


# ======================================================================
# validate() — valid output passes
# ======================================================================

class TestValidateValid:
    """Valid outputs pass envelope-level validation."""

    def setup_method(self):
        self.validator = LLMOutputValidator()

    def test_valid_generated_expert(self):
        envelope = LLMOutputEnvelope(
            output_type="generated_expert",
            parsed_output={
                "name": "Dr. Smith",
                "domain": "finance",
                "capabilities": ["risk assessment"],
                "confidence": 0.85,
            },
        )
        result = self.validator.validate(envelope)
        assert result.valid is True
        assert result.errors == []

    def test_valid_domain_gate(self):
        envelope = LLMOutputEnvelope(
            output_type="domain_gate",
            parsed_output={
                "gate_type": "safety_check",
                "target": "deploy",
                "trigger_condition": "murphy_index > 0.5",
                "risk_reduction": 0.4,
            },
        )
        result = self.validator.validate(envelope)
        assert result.valid is True

    def test_valid_constraint(self):
        envelope = LLMOutputEnvelope(
            output_type="constraint",
            parsed_output={
                "parameter": "latency",
                "operator": "<=",
                "threshold": 200.0,
                "severity": "high",
            },
        )
        result = self.validator.validate(envelope)
        assert result.valid is True

    def test_valid_expansion_result(self):
        envelope = LLMOutputEnvelope(
            output_type="expansion_result",
            parsed_output={
                "new_dimension": "customer_satisfaction",
                "initial_value": 0.5,
                "uncertainty": 0.3,
                "rationale": "Added based on CX feedback loop.",
            },
        )
        result = self.validator.validate(envelope)
        assert result.valid is True

    def test_valid_result_confidence_is_one(self):
        envelope = LLMOutputEnvelope(
            output_type="generated_expert",
            parsed_output={
                "name": "Ada",
                "domain": "robotics",
                "capabilities": ["path planning"],
            },
        )
        result = self.validator.validate(envelope)
        assert result.confidence == pytest.approx(1.0)


# ======================================================================
# validate() — invalid output fails
# ======================================================================

class TestValidateInvalid:
    """Invalid outputs return a ValidationResult with errors."""

    def setup_method(self):
        self.validator = LLMOutputValidator()

    def test_missing_required_field(self):
        envelope = LLMOutputEnvelope(
            output_type="generated_expert",
            parsed_output={"name": "X"},  # missing domain, capabilities
        )
        result = self.validator.validate(envelope)
        assert result.valid is False
        assert len(result.errors) > 0

    def test_invalid_confidence_field(self):
        envelope = LLMOutputEnvelope(
            output_type="generated_expert",
            parsed_output={
                "name": "X",
                "domain": "test",
                "capabilities": ["a"],
                "confidence": 5.0,  # out of range
            },
        )
        result = self.validator.validate(envelope)
        assert result.valid is False

    def test_invalid_constraint_severity(self):
        envelope = LLMOutputEnvelope(
            output_type="constraint",
            parsed_output={
                "parameter": "p",
                "operator": "<=",
                "threshold": 1.0,
                "severity": "extreme",  # not allowed
            },
        )
        result = self.validator.validate(envelope)
        assert result.valid is False
        assert len(result.errors) > 0

    def test_invalid_result_confidence_is_zero(self):
        envelope = LLMOutputEnvelope(
            output_type="generated_expert",
            parsed_output={},
        )
        result = self.validator.validate(envelope)
        assert result.valid is False
        assert result.confidence == pytest.approx(0.0)


# ======================================================================
# validate_and_reject()
# ======================================================================

class TestValidateAndReject:
    """validate_and_reject() returns (True, model) or (False, None)."""

    def setup_method(self):
        self.validator = LLMOutputValidator()

    def test_valid_returns_true_and_model(self):
        envelope = LLMOutputEnvelope(
            output_type="generated_expert",
            parsed_output={
                "name": "Eve",
                "domain": "nlp",
                "capabilities": ["translation"],
            },
        )
        ok, model = self.validator.validate_and_reject(envelope)
        assert ok is True
        assert model is not None

    def test_invalid_returns_false_and_none(self):
        envelope = LLMOutputEnvelope(
            output_type="generated_expert",
            parsed_output={"name": "Eve"},  # missing fields
        )
        ok, model = self.validator.validate_and_reject(envelope)
        assert ok is False
        assert model is None

    def test_unknown_type_returns_false_and_none(self):
        envelope = LLMOutputEnvelope(
            output_type="totally_unknown",
            parsed_output={"x": 1},
        )
        ok, model = self.validator.validate_and_reject(envelope)
        assert ok is False
        assert model is None

    def test_valid_constraint_returns_model(self):
        envelope = LLMOutputEnvelope(
            output_type="constraint",
            parsed_output={
                "parameter": "cpu_usage",
                "operator": "<=",
                "threshold": 0.8,
                "severity": "critical",
            },
        )
        ok, model = self.validator.validate_and_reject(envelope)
        assert ok is True
        assert model is not None


# ======================================================================
# Backward-compatible validate_expert / validate_gate / validate_constraint
# ======================================================================

class TestLegacyValidateMethods:
    """Original validate_* methods still work after CFP-6 additions."""

    def setup_method(self):
        self.validator = LLMOutputValidator()

    def test_validate_expert_still_works(self):
        raw = {
            "name": "Dr. Smith",
            "domain": "software_engineering",
            "capabilities": ["code review"],
        }
        ok, obj, errors = self.validator.validate_expert(raw)
        assert ok is True
        assert errors == []

    def test_validate_gate_still_works(self):
        raw = {
            "gate_type": "safety",
            "target": "deploy",
            "trigger_condition": "score < 0.5",
        }
        ok, obj, errors = self.validator.validate_gate(raw)
        assert ok is True

    def test_validate_any_expansion_result(self):
        raw = {
            "new_dimension": "uptime",
            "initial_value": 1.0,
            "uncertainty": 0.1,
        }
        ok, obj, errors = self.validator.validate_any(raw, "expansion_result")
        assert ok is True
