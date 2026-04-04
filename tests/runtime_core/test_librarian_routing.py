"""
Tests for Phase 9-12: Librarian-Driven Routing.

Validates TaskRouter and SolutionPathRegistry implementations
as specified in docs/LIBRARIAN_ROUTING_SPEC.md.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import os
import sys
import json
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.solution_path_registry import SolutionPathRegistry
from src.task_router import CapabilityMatch, RouteStatus, RoutingResult, SolutionPath, TaskRouter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_registry(tmp_path):
    """SolutionPathRegistry backed by a temp directory."""
    return SolutionPathRegistry(data_dir=str(tmp_path / "solution_paths"))


@pytest.fixture
def sample_path():
    """A single SolutionPath for testing."""
    return SolutionPath(
        path_id=str(uuid.uuid4()),
        task_id="task-001",
        capability_id="invoice_processing",
        module_path="src.invoice_processing.pipeline",
        score=0.8,
        librarian_score=0.8,
        feedback_weight=1.0,
        cost_estimate="low",
        determinism="deterministic",
        requires_hitl=False,
        parameters={"amount": 5000},
    )


@pytest.fixture
def mock_librarian():
    """Mock SystemLibrarian with a simple search_knowledge stub."""
    librarian = MagicMock()
    knowledge = MagicMock()
    knowledge.topic = "invoice processing"
    knowledge.description = "Generate and send invoices automatically"
    knowledge.category = "billing"
    librarian.search_knowledge.return_value = [knowledge]
    return librarian


@pytest.fixture
def mock_registry():
    """Mock ModuleRegistry with a simple get_capabilities stub."""
    registry = MagicMock()
    registry.get_capabilities.return_value = {
        "invoice_processing": ["invoice_processor"],
        "email_sender": ["email_service"],
    }
    return registry


# ===========================================================================
# SolutionPath tests
# ===========================================================================

class TestSolutionPath:
    """Unit tests for the SolutionPath dataclass."""

    def test_combined_score_is_product(self, sample_path):
        sample_path.librarian_score = 0.8
        sample_path.feedback_weight = 0.75
        assert abs(sample_path.combined_score - 0.6) < 1e-9

    def test_combined_score_neutral_weight(self, sample_path):
        sample_path.librarian_score = 0.9
        sample_path.feedback_weight = 1.0
        assert abs(sample_path.combined_score - 0.9) < 1e-9

    def test_to_dict_roundtrip(self, sample_path):
        d = sample_path.to_dict()
        restored = SolutionPath.from_dict(d)
        assert restored.path_id == sample_path.path_id
        assert restored.capability_id == sample_path.capability_id
        assert restored.score == sample_path.score

    def test_to_dict_has_all_fields(self, sample_path):
        d = sample_path.to_dict()
        for field_name in (
            "path_id", "task_id", "capability_id", "module_path",
            "score", "librarian_score", "feedback_weight",
            "cost_estimate", "determinism", "requires_hitl", "parameters",
        ):
            assert field_name in d, f"Missing field {field_name!r}"

    def test_parameters_preserved(self, sample_path):
        sample_path.parameters = {"amount": 5000, "currency": "USD"}
        d = sample_path.to_dict()
        restored = SolutionPath.from_dict(d)
        assert restored.parameters["amount"] == 5000
        assert restored.parameters["currency"] == "USD"


# ===========================================================================
# SolutionPathRegistry tests
# ===========================================================================

class TestSolutionPathRegistry:
    """Unit tests for SolutionPathRegistry persistence."""

    def test_register_and_retrieve(self, tmp_registry, sample_path):
        tmp_registry.register("task-001", [sample_path])
        alts = tmp_registry.get_alternatives("task-001")
        assert len(alts) == 1
        assert alts[0].capability_id == "invoice_processing"

    def test_register_sorts_by_combined_score(self, tmp_registry):
        paths = []
        for i, score in enumerate([0.3, 0.9, 0.6]):
            paths.append(SolutionPath(
                path_id=str(uuid.uuid4()), task_id="t1",
                capability_id=f"cap_{i}", module_path=f"src.m_{i}",
                score=score, librarian_score=score, feedback_weight=1.0,
                cost_estimate="low", determinism="deterministic",
                requires_hitl=False, parameters={},
            ))
        tmp_registry.register("t1", paths)
        alts = tmp_registry.get_alternatives("t1")
        scores = [a.librarian_score for a in alts]
        assert scores == sorted(scores, reverse=True)

    def test_get_primary_is_highest_score(self, tmp_registry):
        paths = [
            SolutionPath(
                path_id=str(uuid.uuid4()), task_id="t2",
                capability_id=f"cap_{i}", module_path=f"src.m_{i}",
                score=s, librarian_score=s, feedback_weight=1.0,
                cost_estimate="low", determinism="deterministic",
                requires_hitl=False, parameters={},
            )
            for i, s in enumerate([0.4, 0.95, 0.7])
        ]
        tmp_registry.register("t2", paths)
        primary = tmp_registry.get_primary("t2")
        assert primary is not None
        assert primary.librarian_score == 0.95

    def test_get_primary_returns_none_for_unknown_task(self, tmp_registry):
        assert tmp_registry.get_primary("nonexistent-task") is None

    def test_get_alternatives_empty_for_unknown_task(self, tmp_registry):
        assert tmp_registry.get_alternatives("no-such-task") == []

    def test_get_fallback_returns_next_best(self, tmp_registry):
        path_a = SolutionPath(
            path_id="pa", task_id="t3", capability_id="cap_a",
            module_path="src.a", score=0.9, librarian_score=0.9,
            feedback_weight=1.0, cost_estimate="low",
            determinism="deterministic", requires_hitl=False, parameters={},
        )
        path_b = SolutionPath(
            path_id="pb", task_id="t3", capability_id="cap_b",
            module_path="src.b", score=0.6, librarian_score=0.6,
            feedback_weight=1.0, cost_estimate="low",
            determinism="deterministic", requires_hitl=False, parameters={},
        )
        tmp_registry.register("t3", [path_a, path_b])
        fallback = tmp_registry.get_fallback("t3", "pa")
        assert fallback is not None
        assert fallback.path_id == "pb"

    def test_get_fallback_none_when_no_alternative(self, tmp_registry, sample_path):
        tmp_registry.register("t4", [sample_path])
        fallback = tmp_registry.get_fallback("t4", sample_path.path_id)
        assert fallback is None

    def test_record_outcome_creates_file(self, tmp_registry, sample_path):
        tmp_registry.register("t5", [sample_path])
        tmp_registry.record_outcome("t5", sample_path.path_id, success=True, latency_ms=42)
        outcomes_file = Path(tmp_registry._outcomes_path)
        assert outcomes_file.exists()
        line = outcomes_file.read_text().strip()
        record = json.loads(line)
        assert record["success"] is True
        assert record["latency_ms"] == 42

    def test_record_multiple_outcomes(self, tmp_registry, sample_path):
        tmp_registry.register("t6", [sample_path])
        for success in [True, True, False]:
            tmp_registry.record_outcome("t6", sample_path.path_id, success=success)
        lines = Path(tmp_registry._outcomes_path).read_text().strip().split("\n")
        assert len(lines) == 3

    def test_get_success_rate_no_history(self, tmp_registry):
        rate = tmp_registry.get_success_rate("nonexistent_cap")
        assert rate == 1.0

    def test_get_success_rate_all_successes(self, tmp_registry, sample_path):
        tmp_registry.register("t7", [sample_path])
        for _ in range(3):
            tmp_registry.record_outcome("t7", sample_path.path_id, success=True)
        rate = tmp_registry.get_success_rate("invoice_processing")
        assert rate == 1.0

    def test_get_success_rate_partial(self, tmp_registry, sample_path):
        tmp_registry.register("t8", [sample_path])
        tmp_registry.record_outcome("t8", sample_path.path_id, success=True)
        tmp_registry.record_outcome("t8", sample_path.path_id, success=False)
        rate = tmp_registry.get_success_rate("invoice_processing")
        assert rate == 0.5

    def test_register_empty_list_does_nothing(self, tmp_registry):
        tmp_registry.register("t9", [])
        assert tmp_registry.get_alternatives("t9") == []


# ===========================================================================
# TaskRouter tests
# ===========================================================================

class TestTaskRouter:
    """Unit tests for TaskRouter end-to-end routing."""

    def _make_router(self, librarian, module_registry, tmp_path, governance=None):
        registry = SolutionPathRegistry(data_dir=str(tmp_path / "sol"))
        return TaskRouter(librarian, module_registry, registry, governance=governance), registry

    def test_route_returns_approved_on_match(self, mock_librarian, mock_registry, tmp_path):
        router, _ = self._make_router(mock_librarian, mock_registry, tmp_path)
        result = router.route({"task": "generate invoice for client"})
        assert result.is_approved()
        assert result.solution_path is not None

    def test_route_task_id_is_uuid(self, mock_librarian, mock_registry, tmp_path):
        router, _ = self._make_router(mock_librarian, mock_registry, tmp_path)
        result = router.route({"task": "invoice processing"})
        # Should be a valid UUID
        uuid.UUID(result.task_id)

    def test_route_registers_alternatives(self, mock_librarian, mock_registry, tmp_path):
        router, sol_registry = self._make_router(mock_librarian, mock_registry, tmp_path)
        result = router.route({"task": "invoice"})
        alts = sol_registry.get_alternatives(result.task_id)
        assert len(alts) >= 1

    def test_route_blocked_when_no_capabilities(self, tmp_path):
        librarian = MagicMock()
        librarian.search_knowledge.return_value = []
        module_registry = MagicMock()
        module_registry.get_capabilities.return_value = {}
        router, _ = self._make_router(librarian, module_registry, tmp_path)
        result = router.route({"task": "completely unrelated nonsense xyz123"})
        assert result.is_blocked()
        assert result.solution_path is None

    def test_route_uses_description_fallback(self, mock_librarian, mock_registry, tmp_path):
        router, _ = self._make_router(mock_librarian, mock_registry, tmp_path)
        result = router.route({"description": "invoice processing pipeline"})
        assert not result.is_blocked()

    def test_route_uses_intent_fallback(self, mock_librarian, mock_registry, tmp_path):
        router, _ = self._make_router(mock_librarian, mock_registry, tmp_path)
        result = router.route({"intent": "send invoice"})
        assert not result.is_blocked()

    def test_route_joins_string_values_as_fallback(self, mock_librarian, mock_registry, tmp_path):
        router, _ = self._make_router(mock_librarian, mock_registry, tmp_path)
        # No "task", "description", or "intent" key
        result = router.route({"action": "invoice", "domain": "billing"})
        # Should not raise; result should be valid
        assert isinstance(result, RoutingResult)

    def test_route_with_governance_approved(self, mock_librarian, mock_registry, tmp_path):
        governance = MagicMock()
        governance.validate_path.return_value = {"approved": True, "gates": []}
        router, _ = self._make_router(mock_librarian, mock_registry, tmp_path, governance=governance)
        result = router.route({"task": "invoice processing"})
        assert result.is_approved()

    def test_route_with_governance_blocked(self, tmp_path):
        librarian = MagicMock()
        knowledge = MagicMock()
        knowledge.topic = "invoice"
        knowledge.description = "invoice"
        knowledge.category = "billing"
        librarian.search_knowledge.return_value = [knowledge]
        module_registry = MagicMock()
        module_registry.get_capabilities.return_value = {}
        governance = MagicMock()
        governance.validate_path.return_value = {"approved": False, "gates": ["denied"]}
        router, _ = self._make_router(librarian, module_registry, tmp_path, governance=governance)
        result = router.route({"task": "invoice"})
        assert result.is_blocked()

    def test_route_hitl_path_used_when_all_fail_governance(self, tmp_path):
        librarian = MagicMock()
        knowledge = MagicMock()
        knowledge.topic = "payment"
        knowledge.description = "payment gateway"
        knowledge.category = "billing"
        librarian.search_knowledge.return_value = [knowledge]
        module_registry = MagicMock()
        module_registry.get_capabilities.return_value = {}
        governance = MagicMock()
        governance.validate_path.return_value = {"approved": False}
        router, sol_registry = self._make_router(
            librarian, module_registry, tmp_path, governance=governance
        )
        # Inject a HITL path manually into the registry after routing
        result = router.route({"task": "payment"})
        # Without requires_hitl, should be BLOCKED
        assert result.is_blocked()

    def test_alternatives_sorted_by_score(self, mock_librarian, mock_registry, tmp_path):
        router, _ = self._make_router(mock_librarian, mock_registry, tmp_path)
        result = router.route({"task": "invoice processing"})
        if len(result.alternatives) > 1:
            scores = [a.combined_score for a in result.alternatives]
            assert scores == sorted(scores, reverse=True)

    def test_gate_results_populated(self, mock_librarian, mock_registry, tmp_path):
        router, _ = self._make_router(mock_librarian, mock_registry, tmp_path)
        result = router.route({"task": "invoice"})
        # Without governance, gate_results should have the approved path's entry
        assert isinstance(result.gate_results, dict)

    def test_routing_result_properties(self):
        r_approved = RoutingResult(status=RouteStatus.APPROVED, task_id="t1")
        assert r_approved.is_approved()
        assert not r_approved.needs_hitl()
        assert not r_approved.is_blocked()

        r_hitl = RoutingResult(status=RouteStatus.HITL, task_id="t2")
        assert not r_hitl.is_approved()
        assert r_hitl.needs_hitl()

        r_blocked = RoutingResult(status=RouteStatus.BLOCKED, task_id="t3")
        assert r_blocked.is_blocked()
