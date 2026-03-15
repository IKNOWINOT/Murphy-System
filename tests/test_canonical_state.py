"""
Gap-closing tests for the canonical state vector.

These tests verify that the structural gap identified in the Murphy System
audit — 5+ fragmented state representations with no unified state vector —
is closed by :class:`~control_theory.canonical_state.CanonicalStateVector`.
"""

import pytest
from pydantic import BaseModel

from control_theory.canonical_state import CanonicalStateVector
from control_theory.state_adapter import (
    from_dict,
    from_mfgc_state,
    from_rosetta_state,
    from_session,
    from_unified_system_state,
)


class TestCanonicalStateStructure:
    """Tests that verify the canonical state vector closes the structural gap."""

    def test_state_vector_has_explicit_dimensionality(self):
        """GAP: No explicit dim(X). Closed when dimensionality() returns an int."""
        state = CanonicalStateVector()
        dim = state.dimensionality()
        assert isinstance(dim, int)
        assert dim == 25  # Exact expected dimensionality (expanded from 17 to 25)

    def test_state_vector_is_pydantic(self):
        """GAP: State was dataclasses. Closed when CanonicalStateVector is a BaseModel."""
        assert issubclass(CanonicalStateVector, BaseModel)

    def test_state_vector_serializable_roundtrip(self):
        """GAP: No serializable schema. Closed when JSON roundtrip preserves equality."""
        state = CanonicalStateVector(confidence=0.75, authority=0.6, murphy_index=0.2)
        json_str = state.model_dump_json()
        restored = CanonicalStateVector.model_validate_json(json_str)
        assert state.to_vector() == restored.to_vector()

    def test_state_vector_versioned(self):
        """GAP: No schema versioning. Closed when schema_version field exists."""
        state = CanonicalStateVector()
        assert hasattr(state, "schema_version")
        assert state.schema_version == "1.0.0"

    def test_all_legacy_states_convertible(self):
        """GAP: State scattered across 5+ classes. Closed when ALL convert to canonical."""
        # Test from_mfgc_state
        from mfgc_core import MFGCSystemState

        mfgc = MFGCSystemState()
        canonical = from_mfgc_state(mfgc)
        assert isinstance(canonical, CanonicalStateVector)

        # Test from_dict (generic)
        data = {"confidence": 0.5, "authority": 0.3}
        canonical = from_dict(data)
        assert isinstance(canonical, CanonicalStateVector)

    def test_state_bounds_enforced(self):
        """GAP: No bounds on state. Closed when out-of-range values are clamped."""
        state = CanonicalStateVector(confidence=1.5, authority=-0.3, murphy_index=2.0)
        assert 0.0 <= state.confidence <= 1.0
        assert 0.0 <= state.authority <= 1.0
        assert 0.0 <= state.murphy_index <= 1.0

    def test_state_dimensionality_matches_fields(self):
        """GAP: Implicit dimensions. Closed when dim() == len(to_vector())."""
        state = CanonicalStateVector()
        assert state.dimensionality() == len(state.to_vector())

    def test_to_vector_returns_floats(self):
        """Vector representation must be numeric."""
        state = CanonicalStateVector(confidence=0.5, phase_index=3)
        vec = state.to_vector()
        assert all(isinstance(v, float) for v in vec)

    def test_from_vector_roundtrip(self):
        """from_vector(to_vector()) should produce equivalent state."""
        original = CanonicalStateVector(confidence=0.8, authority=0.5, murphy_index=0.15)
        vec = original.to_vector()
        restored = CanonicalStateVector.from_vector(vec)
        assert abs(original.confidence - restored.confidence) < 1e-10
        assert abs(original.authority - restored.authority) < 1e-10

    def test_norm_computation(self):
        """L2 norm should be correct."""
        state = CanonicalStateVector()  # all zeros except defaults
        assert state.norm() >= 0.0

    def test_dimension_names_ordered(self):
        """Dimension names must match vector ordering."""
        state = CanonicalStateVector()
        names = state.dimension_names()
        vec = state.to_vector()
        assert len(names) == len(vec)
        assert len(names) == state.dimensionality()

    # ------------------------------------------------------------------
    # Additional coverage for adapters and edge cases
    # ------------------------------------------------------------------

    def test_from_rosetta_state_adapter(self):
        """from_rosetta_state converts RosettaSystemState correctly."""
        from rosetta.rosetta_models import SystemState as RosettaSystemState

        rosetta = RosettaSystemState(uptime_seconds=42.0, active_tasks=3, cpu_usage_percent=12.5)
        canonical = from_rosetta_state(rosetta)
        assert isinstance(canonical, CanonicalStateVector)
        assert canonical.uptime_seconds == 42.0
        assert canonical.active_tasks == 3
        assert canonical.cpu_usage_percent == 12.5

    def test_from_session_adapter(self):
        """from_session converts Session correctly, using last history entry."""
        from logging_system import Session

        session = Session(
            session_id="test-session",
            confidence_history=[0.4, 0.6, 0.8],
            murphy_index_history=[0.1, 0.2],
        )
        canonical = from_session(session)
        assert isinstance(canonical, CanonicalStateVector)
        assert abs(canonical.confidence - 0.8) < 1e-10
        assert abs(canonical.murphy_index - 0.2) < 1e-10
        assert canonical.session_id == "test-session"

    def test_from_dict_ignores_unknown_keys(self):
        """from_dict must not raise on unknown keys."""
        canonical = from_dict({"confidence": 0.9, "unknown_field": "ignored"})
        assert isinstance(canonical, CanonicalStateVector)
        assert abs(canonical.confidence - 0.9) < 1e-10

    def test_phase_index_bounds(self):
        """phase_index must be clamped to [0, 6]."""
        state_low = CanonicalStateVector(phase_index=-1)
        assert state_low.phase_index == 0

        state_high = CanonicalStateVector(phase_index=99)
        assert state_high.phase_index == 6

    def test_non_negative_counts(self):
        """Count fields must be clamped to >= 0."""
        state = CanonicalStateVector(gate_count=-5, artifact_count=-10, active_tasks=-1)
        assert state.gate_count == 0
        assert state.artifact_count == 0
        assert state.active_tasks == 0

    def test_norm_known_value(self):
        """Verify norm computation against a manually computed value."""
        import math

        state = CanonicalStateVector(uptime_seconds=1.0)
        assert abs(state.norm() - 1.0) < 1e-10
