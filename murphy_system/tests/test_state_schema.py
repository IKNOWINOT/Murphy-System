"""
Tests for state_schema.py (Gap CFP-1 — Formal State Vector Schema).

Covers:
- TypedStateVector creation with explicit dimensions
- dimensionality() returns correct count
- uncertainty_vector() / to_uncertainty_vector() returns correct floats
- expand_state() adds dimension and updates uncertainty vector
- validate() rejects invalid state
- StateVectorRegistry tracks schemas per domain
"""

import os


import pytest
from state_schema import (
    StateVariable,
    StateVectorSchema,
    TypedStateVector,
    StateVectorRegistry,
)


# ======================================================================
# TypedStateVector — basic construction
# ======================================================================

class TestTypedStateVectorCreation:
    """TypedStateVector is created from explicit StateVariable dimensions."""

    def _make_sv(self) -> TypedStateVector:
        schema = StateVectorSchema(
            domain="test",
            dimensions=[
                StateVariable(name="confidence", value=0.8, dtype="float", uncertainty=0.1),
                StateVariable(name="risk", value=0.3, dtype="float", uncertainty=0.4),
            ],
        )
        return TypedStateVector(schema=schema)

    def test_creation_populates_dimensions(self):
        sv = self._make_sv()
        assert sv.get("confidence") is not None
        assert sv.get("risk") is not None

    def test_get_returns_state_variable(self):
        sv = self._make_sv()
        var = sv.get("confidence")
        assert isinstance(var, StateVariable)
        assert var.name == "confidence"

    def test_get_missing_returns_none(self):
        sv = self._make_sv()
        assert sv.get("nonexistent") is None

    def test_set_updates_value(self):
        sv = self._make_sv()
        sv.set("confidence", 0.95, uncertainty=0.05)
        var = sv.get("confidence")
        assert var is not None
        assert var.value == 0.95
        assert var.uncertainty == pytest.approx(0.05)

    def test_set_adds_new_dimension(self):
        sv = self._make_sv()
        sv.set("new_dim", 0.5, uncertainty=0.2)
        assert sv.get("new_dim") is not None

    def test_contains(self):
        sv = self._make_sv()
        assert "confidence" in sv
        assert "unknown" not in sv


# ======================================================================
# dimensionality()
# ======================================================================

class TestDimensionality:
    """dimensionality() returns the number of tracked dimensions."""

    def test_dimensionality_base(self):
        schema = StateVectorSchema(
            domain="d",
            dimensions=[
                StateVariable(name="a", value=0.0),
                StateVariable(name="b", value=0.0),
                StateVariable(name="c", value=0.0),
            ],
        )
        sv = TypedStateVector(schema=schema)
        assert sv.dimensionality() == 3

    def test_dimensionality_empty(self):
        sv = TypedStateVector()
        assert sv.dimensionality() == 0

    def test_dimensionality_after_set(self):
        sv = TypedStateVector()
        sv.set("x", 1.0)
        sv.set("y", 2.0)
        assert sv.dimensionality() == 2


# ======================================================================
# uncertainty_vector() / to_uncertainty_vector()
# ======================================================================

class TestUncertaintyVector:
    """uncertainty_vector() returns per-dimension uncertainties."""

    def test_uncertainty_vector_values(self):
        schema = StateVectorSchema(
            domain="d",
            dimensions=[
                StateVariable(name="a", value=0.0, uncertainty=0.1),
                StateVariable(name="b", value=0.0, uncertainty=0.5),
                StateVariable(name="c", value=0.0, uncertainty=0.9),
            ],
        )
        sv = TypedStateVector(schema=schema)
        vec = sv.uncertainty_vector()
        assert vec == pytest.approx([0.1, 0.5, 0.9])

    def test_to_uncertainty_vector_alias(self):
        sv = TypedStateVector()
        sv.set("x", 1.0, uncertainty=0.3)
        assert sv.to_uncertainty_vector() == sv.uncertainty_vector()

    def test_uncertainty_vector_length_matches_dimensionality(self):
        sv = TypedStateVector()
        sv.set("a", 0.0, uncertainty=0.2)
        sv.set("b", 0.0, uncertainty=0.7)
        assert len(sv.uncertainty_vector()) == sv.dimensionality()

    def test_uncertainty_vector_all_floats(self):
        sv = TypedStateVector()
        sv.set("x", 0.5, uncertainty=0.4)
        for v in sv.uncertainty_vector():
            assert isinstance(v, float)


# ======================================================================
# expand_state()
# ======================================================================

class TestExpandState:
    """expand_state() adds a new dimension and updates uncertainty vector."""

    def test_expand_increases_dimensionality(self):
        sv = TypedStateVector()
        sv.set("a", 0.0, uncertainty=0.1)
        assert sv.dimensionality() == 1
        sv.expand_state(StateVariable(name="b", value=0.5, uncertainty=0.3))
        assert sv.dimensionality() == 2

    def test_expand_adds_uncertainty_entry(self):
        sv = TypedStateVector()
        sv.set("a", 0.0, uncertainty=0.1)
        sv.expand_state(StateVariable(name="b", value=0.5, uncertainty=0.3))
        vec = sv.uncertainty_vector()
        assert len(vec) == 2
        assert 0.3 in vec

    def test_expand_updates_schema_dimensions(self):
        sv = TypedStateVector()
        sv.expand_state(StateVariable(name="new", value=1.0, uncertainty=0.5))
        assert "new" in sv

    def test_expand_overwrites_existing_dimension(self):
        sv = TypedStateVector()
        sv.set("a", 0.0, uncertainty=0.1)
        sv.expand_state(StateVariable(name="a", value=0.9, uncertainty=0.8))
        assert sv.dimensionality() == 1
        assert sv.get("a").uncertainty == pytest.approx(0.8)


# ======================================================================
# validate()
# ======================================================================

class TestValidate:
    """validate() returns False for invalid states."""

    def test_valid_state(self):
        sv = TypedStateVector()
        sv.set("x", 0.5, uncertainty=0.2)
        assert sv.validate() is True

    def test_invalid_uncertainty_above_one(self):
        sv = TypedStateVector()
        # Use model_construct to bypass Pydantic validation for this test
        try:
            bad_var = StateVariable.model_construct(name="bad", value=0.0, uncertainty=1.5)
        except AttributeError:
            # Fallback for non-Pydantic dataclass stub
            bad_var = StateVariable(name="bad", value=0.0)
            bad_var.uncertainty = 1.5  # type: ignore[misc]
        sv._dimensions["bad"] = bad_var
        assert sv.validate() is False

    def test_invalid_uncertainty_below_zero(self):
        sv = TypedStateVector()
        # Use model_construct to bypass Pydantic validation for this test
        try:
            bad_var = StateVariable.model_construct(name="bad", value=0.0, uncertainty=-0.1)
        except AttributeError:
            bad_var = StateVariable(name="bad", value=0.0)
            bad_var.uncertainty = -0.1  # type: ignore[misc]
        sv._dimensions["bad"] = bad_var
        assert sv.validate() is False

    def test_empty_state_is_valid(self):
        sv = TypedStateVector()
        assert sv.validate() is True


# ======================================================================
# StateVectorRegistry
# ======================================================================

class TestStateVectorRegistry:
    """StateVectorRegistry tracks schemas per domain."""

    def test_register_and_get_latest(self):
        reg = StateVectorRegistry()
        schema = StateVectorSchema(domain="finance", schema_version="1.0")
        reg.register(schema)
        assert reg.get_latest("finance") is schema

    def test_get_latest_returns_none_for_unknown_domain(self):
        reg = StateVectorRegistry()
        assert reg.get_latest("unknown") is None

    def test_multiple_schemas_same_domain(self):
        reg = StateVectorRegistry()
        s1 = StateVectorSchema(domain="ops", schema_version="1.0")
        s2 = StateVectorSchema(domain="ops", schema_version="2.0")
        reg.register(s1)
        reg.register(s2)
        assert reg.get_latest("ops") is s2

    def test_list_domains(self):
        reg = StateVectorRegistry()
        reg.register(StateVectorSchema(domain="a", schema_version="1.0"))
        reg.register(StateVectorSchema(domain="b", schema_version="1.0"))
        domains = reg.list_domains()
        assert "a" in domains
        assert "b" in domains

    def test_get_version(self):
        reg = StateVectorRegistry()
        s = StateVectorSchema(domain="svc", schema_version="3.0")
        reg.register(s)
        assert reg.get_version("svc", "3.0") is s
        assert reg.get_version("svc", "99.0") is None

    def test_migrate_adds_missing_dimensions(self):
        reg = StateVectorRegistry()

        old_schema = StateVectorSchema(
            domain="svc",
            schema_version="1.0",
            dimensions=[StateVariable(name="conf", value=0.0)],
        )
        new_schema = StateVectorSchema(
            domain="svc",
            schema_version="2.0",
            dimensions=[
                StateVariable(name="conf", value=0.0),
                StateVariable(name="risk", value=0.0, uncertainty=0.5),
            ],
        )
        reg.register(old_schema)
        reg.register(new_schema)

        old_sv = TypedStateVector(schema=old_schema)
        old_sv.set("conf", 0.7, uncertainty=0.1)

        new_sv = reg.migrate(old_sv, new_schema)
        assert new_sv.dimensionality() == 2
        assert new_sv.get("conf").value == 0.7
        assert new_sv.get("risk") is not None
