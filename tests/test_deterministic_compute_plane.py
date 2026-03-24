"""Tests for the DeterministicComputePlane dispatch layer."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from src.deterministic_compute_plane import DeterministicComputePlane
from src.deterministic_compute_plane.compute_plane import DeterministicComputePlane as DCP


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def plane():
    return DeterministicComputePlane()


# ------------------------------------------------------------------
# Imports and construction
# ------------------------------------------------------------------

class TestImport:
    def test_package_exports_class(self):
        from src.deterministic_compute_plane import DeterministicComputePlane
        assert DeterministicComputePlane is not None

    def test_instantiate(self, plane):
        assert plane is not None


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

class TestStatus:
    def test_status_shape(self, plane):
        s = plane.get_status()
        assert s["status"] == "active"
        assert "routing_engine" in s
        assert "compute_service" in s

    def test_routing_stats_shape(self, plane):
        s = plane.get_routing_stats()
        assert "decisions_count" in s
        assert "status" in s


# ------------------------------------------------------------------
# Routing dispatch
# ------------------------------------------------------------------

class TestDispatch:
    def test_dispatch_math_routes_deterministic(self, plane):
        result = plane.dispatch(
            task_type="math",
            expression="x**2",
            language="sympy",
            tags=["math"],
        )
        assert result["route_type"] == "deterministic"

    def test_dispatch_creative_deferred_to_llm(self, plane):
        result = plane.dispatch(
            task_type="creative",
            expression="write a poem",
            language="text",
            tags=["creative"],
        )
        assert result["route_type"] == "llm"
        assert result["status"] == "deferred_to_llm"

    def test_dispatch_analysis_deferred_to_hybrid(self, plane):
        result = plane.dispatch(
            task_type="analysis",
            expression="analyze data",
            language="text",
            tags=["analysis"],
        )
        assert result["route_type"] == "hybrid"
        assert result["status"] == "deferred_to_hybrid"

    def test_dispatch_result_contains_routing_decision(self, plane):
        result = plane.dispatch("math", "1+1", "sympy")
        assert "routing_decision" in result
        assert "route_type" in result["routing_decision"]

    def test_dispatch_deterministic_returns_compute_status(self, plane):
        result = plane.dispatch("math", "1+1", "sympy")
        # Status is "computed" on success, "error" when dependencies missing
        assert result["status"] in ("computed", "error")


# ------------------------------------------------------------------
# Validate
# ------------------------------------------------------------------

class TestValidate:
    def test_validate_returns_dict(self, plane):
        v = plane.validate("x**2 + 1", "sympy")
        assert isinstance(v, dict)
        assert "is_valid" in v

    def test_validate_unknown_language(self, plane):
        v = plane.validate("some text", "unknown_lang")
        assert isinstance(v, dict)
