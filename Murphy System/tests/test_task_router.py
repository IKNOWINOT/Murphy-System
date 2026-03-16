"""
Unit tests for the Librarian-driven routing system:
  - TaskRouter
  - SystemLibrarian.find_capabilities()
  - SolutionPathRegistry

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Path helpers — load modules directly from src/ without a package install
# ---------------------------------------------------------------------------

_SRC = Path(__file__).resolve().parent.parent / "src"


def _load(name: str) -> Any:
    """Load a module from *_SRC/<name>.py* and register it in sys.modules."""
    mod_path = _SRC / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, mod_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    sys.modules[f"src.{name}"] = mod
    spec.loader.exec_module(mod)
    return mod


# Pre-load task_router and solution_path_registry.
# system_librarian depends on them only at call time (lazy import), so we
# don't need to preload it here.

def _load_task_router():
    return _load("task_router")


def _load_solution_path_registry():
    # solution_path_registry imports from feedback_integrator and state_schema
    # only inside try/except blocks — safe to load without those present.
    return _load("solution_path_registry")


def _load_system_librarian():
    return _load("system_librarian")


# ===========================================================================
# TaskRouter tests
# ===========================================================================


class TestTaskRouterInit:
    def setup_method(self):
        self.mod = _load_task_router()

    def test_route_status_enum_values(self):
        rs = self.mod.RouteStatus
        assert rs.APPROVED.value == "approved"
        assert rs.HITL.value == "hitl_required"
        assert rs.BLOCKED.value == "blocked"
        assert rs.NO_PATH.value == "no_viable_path"

    def test_solution_path_combined_score(self):
        SP = self.mod.SolutionPath
        path = SP(
            path_id="p1",
            task_id="t1",
            capability_id="invoice_pipeline",
            module_path="src.invoice_pipeline",
            score=0.8,
            librarian_score=0.8,
            feedback_weight=0.9,
        )
        assert abs(path.combined_score - 0.72) < 1e-9

    def test_solution_path_default_feedback_weight(self):
        SP = self.mod.SolutionPath
        path = SP(
            path_id="p2",
            task_id="t2",
            capability_id="cap",
            module_path="src.cap",
            score=0.5,
            librarian_score=0.5,
        )
        assert path.feedback_weight == 1.0
        assert path.combined_score == 0.5

    def test_capability_match_defaults(self):
        CM = self.mod.CapabilityMatch
        m = CM(capability_id="llm_routing", module_path="src.llm_controller", score=0.7)
        assert m.filtered is False
        assert m.filter_reason is None
        assert m.cost_estimate == "medium"


class TestTaskRouterHappyPath:
    """TaskRouter returns APPROVED when Librarian finds capabilities and no blocking gate."""

    def setup_method(self):
        self.mod = _load_task_router()

    def _make_librarian(self, matches: List):
        lib = MagicMock()
        lib.find_capabilities.return_value = matches
        return lib

    def _make_registry(self):
        reg = MagicMock()
        reg.register.return_value = None
        return reg

    @pytest.mark.asyncio
    async def test_route_returns_approved_with_valid_capability(self):
        CM = self.mod.CapabilityMatch
        TR = self.mod.TaskRouter
        RS = self.mod.RouteStatus

        match = CM(
            capability_id="invoice_pipeline",
            module_path="src.invoice_pipeline",
            score=0.9,
        )
        librarian = self._make_librarian([match])
        registry = self._make_registry()
        router = TR(librarian=librarian, solution_registry=registry)

        result = await router.route({"task": "generate invoice for Acme $5000"})

        assert result.status == RS.APPROVED
        assert result.solution_path is not None
        assert result.solution_path.capability_id == "invoice_pipeline"
        assert result.confidence > 0.0

    @pytest.mark.asyncio
    async def test_route_registers_alternatives(self):
        CM = self.mod.CapabilityMatch
        TR = self.mod.TaskRouter

        matches = [
            CM(capability_id="cap_a", module_path="src.cap_a", score=0.9),
            CM(capability_id="cap_b", module_path="src.cap_b", score=0.7),
        ]
        librarian = self._make_librarian(matches)
        registry = self._make_registry()
        router = TR(librarian=librarian, solution_registry=registry)

        result = await router.route({"task": "do something"})

        registry.register.assert_called_once()
        call_args = registry.register.call_args
        task_id = call_args[0][0]
        paths = call_args[0][1]
        assert len(paths) == 2
        # Best path is first (highest score)
        assert paths[0].librarian_score >= paths[1].librarian_score


class TestTaskRouterNoPath:
    """TaskRouter returns NO_PATH when Librarian finds nothing."""

    def setup_method(self):
        self.mod = _load_task_router()

    @pytest.mark.asyncio
    async def test_route_returns_no_path_on_empty_capabilities(self):
        TR = self.mod.TaskRouter
        RS = self.mod.RouteStatus

        librarian = MagicMock()
        librarian.find_capabilities.return_value = []
        registry = MagicMock()

        router = TR(librarian=librarian, solution_registry=registry)
        result = await router.route({"task": "completely unknown task"})

        assert result.status == RS.NO_PATH
        assert result.solution_path is None
        assert result.confidence == 0.0


class TestTaskRouterFilteredCapabilities:
    """Filtered capabilities are excluded from SolutionPath construction."""

    def setup_method(self):
        self.mod = _load_task_router()

    @pytest.mark.asyncio
    async def test_filtered_capabilities_not_promoted_to_paths(self):
        CM = self.mod.CapabilityMatch
        TR = self.mod.TaskRouter
        RS = self.mod.RouteStatus

        matches = [
            CM(
                capability_id="good_cap",
                module_path="src.good_cap",
                score=0.8,
                filtered=False,
            ),
            CM(
                capability_id="bad_cap",
                module_path="src.bad_cap",
                score=0.95,
                filtered=True,
                filter_reason="hipaa gate incompatible",
            ),
        ]
        librarian = MagicMock()
        librarian.find_capabilities.return_value = matches
        registry = MagicMock()

        router = TR(librarian=librarian, solution_registry=registry)
        result = await router.route({"task": "hipaa workflow"})

        assert result.status == RS.APPROVED
        assert result.solution_path.capability_id == "good_cap"


class TestTaskRouterHITL:
    """TaskRouter returns HITL when best path has requires_hitl=True and no clean paths exist."""

    def setup_method(self):
        self.mod = _load_task_router()

    @pytest.mark.asyncio
    async def test_route_returns_hitl_when_path_requires_hitl(self):
        CM = self.mod.CapabilityMatch
        SP = self.mod.SolutionPath
        TR = self.mod.TaskRouter
        RS = self.mod.RouteStatus

        # Return a capability that will become a HITL path
        match = CM(capability_id="audit_cap", module_path="src.audit", score=0.85)
        librarian = MagicMock()
        librarian.find_capabilities.return_value = [match]
        registry = MagicMock()

        router = TR(librarian=librarian, solution_registry=registry)

        # Monkey-patch _rank_paths to set requires_hitl=True
        original_rank = router._rank_paths

        def patched_rank(matches, feedback):
            paths = original_rank(matches, feedback)
            for p in paths:
                p.requires_hitl = True
            return paths

        router._rank_paths = patched_rank

        result = await router.route({"task": "audit financial records"})

        assert result.status == RS.HITL
        assert result.solution_path is not None


class TestTaskRouterFeedbackWeight:
    """FeedbackIntegrator weights are applied to path ranking."""

    def setup_method(self):
        self.mod = _load_task_router()

    def test_feedback_weight_applied_to_path_score(self):
        CM = self.mod.CapabilityMatch
        TR = self.mod.TaskRouter

        match = CM(capability_id="cap", module_path="src.cap", score=0.8)
        feedback = MagicMock()
        feedback.get_weight.return_value = 1.25

        router = TR(librarian=MagicMock(), solution_registry=MagicMock(), feedback=feedback)
        paths = router._rank_paths([match], feedback)

        assert len(paths) == 1
        assert paths[0].feedback_weight == 1.25
        assert abs(paths[0].combined_score - (0.8 * 1.25)) < 1e-9

    def test_missing_feedback_uses_neutral_weight(self):
        CM = self.mod.CapabilityMatch
        TR = self.mod.TaskRouter

        match = CM(capability_id="cap", module_path="src.cap", score=0.6)
        router = TR(librarian=MagicMock(), solution_registry=MagicMock(), feedback=None)
        paths = router._rank_paths([match], None)

        assert paths[0].feedback_weight == 1.0


class TestTaskRouterBlocked:
    """TaskRouter returns BLOCKED when GovernanceKernel denies all paths."""

    def setup_method(self):
        self.mod = _load_task_router()

    @pytest.mark.asyncio
    async def test_route_returns_blocked_when_governance_denies_all(self):
        CM = self.mod.CapabilityMatch
        TR = self.mod.TaskRouter
        RS = self.mod.RouteStatus

        match = CM(capability_id="restricted_cap", module_path="src.restricted", score=0.9)
        librarian = MagicMock()
        librarian.find_capabilities.return_value = [match]
        registry = MagicMock()

        governance = MagicMock()
        enforcement_result = MagicMock()
        enforcement_result.action.value = "deny"
        governance.enforce.return_value = enforcement_result

        router = TR(
            librarian=librarian,
            solution_registry=registry,
            governance=governance,
        )
        result = await router.route({"task": "access restricted data"})

        assert result.status == RS.BLOCKED
        assert result.solution_path is None


# ===========================================================================
# SolutionPathRegistry tests
# ===========================================================================


class TestSolutionPathRegistryMemory:
    """SolutionPathRegistry stores and retrieves paths in memory."""

    def setup_method(self):
        self.mod = _load_solution_path_registry()

    def _registry(self):
        return self.mod.SolutionPathRegistry(data_dir="/tmp/test_solution_paths")

    def _make_path(self, path_id="p1", capability_id="cap_a", score=0.9):
        return {"path_id": path_id, "capability_id": capability_id, "score": score}

    def test_register_and_get_alternatives(self):
        reg = self._registry()
        paths = [self._make_path("p1", "cap_a", 0.9), self._make_path("p2", "cap_b", 0.7)]
        reg.register("t1", paths)
        alts = reg.get_alternatives("t1")
        assert len(alts) == 2
        assert alts[0]["path_id"] == "p1"

    def test_get_alternatives_returns_empty_for_unknown_task(self):
        reg = self._registry()
        alts = reg.get_alternatives("unknown_task_id")
        assert alts == []

    def test_get_primary_returns_first(self):
        reg = self._registry()
        paths = [self._make_path("p1", "cap_a", 0.9), self._make_path("p2", "cap_b", 0.5)]
        reg.register("t2", paths)
        primary = reg.get_primary("t2")
        assert primary is not None
        assert primary["path_id"] == "p1"

    def test_get_primary_returns_none_for_empty(self):
        reg = self._registry()
        assert reg.get_primary("no_task") is None

    def test_get_fallback_skips_failed_path(self):
        reg = self._registry()
        paths = [
            self._make_path("p1", "cap_a", 0.9),
            self._make_path("p2", "cap_b", 0.7),
            self._make_path("p3", "cap_c", 0.5),
        ]
        reg.register("t3", paths)
        fallback = reg.get_fallback("t3", "p1")
        assert fallback is not None
        assert fallback["path_id"] == "p2"

    def test_get_fallback_returns_none_when_all_failed(self):
        reg = self._registry()
        paths = [self._make_path("p1")]
        reg.register("t4", paths)
        fallback = reg.get_fallback("t4", "p1")
        assert fallback is None


class TestSolutionPathRegistryOutcome:
    """record_outcome updates the stored record."""

    def setup_method(self):
        self.mod = _load_solution_path_registry()

    def test_record_outcome_updates_success_flag(self):
        reg = self.mod.SolutionPathRegistry(data_dir="/tmp/test_solution_paths")
        paths = [{"path_id": "p1", "capability_id": "cap_a", "score": 0.8}]
        reg.register("t5", paths)
        reg.record_outcome("t5", "p1", success=True, latency_ms=200)

        alts = reg.get_alternatives("t5")
        assert alts[0].get("last_outcome_success") is True
        assert alts[0].get("last_outcome_latency_ms") == 200

    def test_record_outcome_forwards_to_feedback(self):
        feedback = MagicMock()
        feedback.get_weight = MagicMock(return_value=1.0)
        reg = self.mod.SolutionPathRegistry(
            data_dir="/tmp/test_solution_paths",
            feedback_integrator=feedback,
        )
        paths = [{"path_id": "p1", "capability_id": "cap_a", "score": 0.8}]
        reg.register("t6", paths)
        reg.record_outcome("t6", "p1", success=False)

        # record_outcome() on the feedback mock should have been called
        # (the registry falls back to feedback.record_outcome when FeedbackSignal isn't available)
        assert feedback.record_outcome.called or feedback.integrate.called


class TestSolutionPathRegistryPersistence:
    """SolutionPathRegistry writes to and reads from disk."""

    def setup_method(self):
        self.mod = _load_solution_path_registry()
        import tempfile

        self.tmpdir = tempfile.mkdtemp()

    def test_persists_to_disk_and_reloads(self):
        reg = self.mod.SolutionPathRegistry(data_dir=self.tmpdir)
        paths = [{"path_id": "px", "capability_id": "cap_x", "score": 0.55}]
        reg.register("tx", paths)

        # A fresh registry instance (no cache) should load from disk
        reg2 = self.mod.SolutionPathRegistry(data_dir=self.tmpdir)
        alts = reg2.get_alternatives("tx")
        assert len(alts) == 1
        assert alts[0]["path_id"] == "px"


# ===========================================================================
# SystemLibrarian.find_capabilities() tests
# ===========================================================================


class TestSystemLibrarianFindCapabilities:
    def setup_method(self):
        self.mod = _load_system_librarian()
        # Pre-register task_router so that find_capabilities can import CapabilityMatch
        _load_task_router()

    def _librarian(self):
        return self.mod.SystemLibrarian()

    def test_returns_list(self):
        lib = self._librarian()
        results = lib.find_capabilities({"task": "generate invoice for customer"})
        assert isinstance(results, list)

    def test_results_sorted_by_score_descending(self):
        lib = self._librarian()
        results = lib.find_capabilities({"task": "generate invoice for customer"})
        scores = [r.score for r in results if not r.filtered]
        assert scores == sorted(scores, reverse=True)

    def test_top_n_limits_unfiltered_results(self):
        lib = self._librarian()
        results = lib.find_capabilities({"task": "any task"}, top_n=3)
        unfiltered = [r for r in results if not r.filtered]
        assert len(unfiltered) <= 3

    def test_empty_task_returns_results(self):
        lib = self._librarian()
        results = lib.find_capabilities({"task": ""})
        assert isinstance(results, list)

    def test_capability_match_has_required_fields(self):
        lib = self._librarian()
        results = lib.find_capabilities({"task": "route llm request"})
        if results:
            m = results[0]
            assert hasattr(m, "capability_id")
            assert hasattr(m, "module_path")
            assert hasattr(m, "score")
            assert hasattr(m, "filtered")

    def test_live_module_registry_capabilities_merged(self):
        """When a ModuleRegistry is passed, its capabilities appear in results."""
        lib = self._librarian()
        mock_registry = MagicMock()
        mock_registry.get_capabilities.return_value = {
            "generate_invoice": ["invoice_pipeline"],
        }
        results = lib.find_capabilities(
            {"task": "generate invoice"},
            module_registry=mock_registry,
        )
        cap_ids = [r.capability_id for r in results]
        assert "generate_invoice" in cap_ids

    def test_all_results_have_nonnegative_score(self):
        lib = self._librarian()
        results = lib.find_capabilities({"task": "analyse data and produce report"})
        for r in results:
            assert r.score >= 0.0


# ===========================================================================
# Integration: TaskRouter + SystemLibrarian + SolutionPathRegistry
# ===========================================================================


class TestEndToEndRouting:
    """Smoke test: route a natural language task through the full pipeline."""

    def setup_method(self):
        self.tr_mod = _load_task_router()
        self.spr_mod = _load_solution_path_registry()
        self.sl_mod = _load_system_librarian()

    @pytest.mark.asyncio
    async def test_full_pipeline_chat_route(self):
        TR = self.tr_mod.TaskRouter
        RS = self.tr_mod.RouteStatus
        SPR = self.spr_mod.SolutionPathRegistry
        SL = self.sl_mod.SystemLibrarian

        librarian = SL()
        registry = SPR(data_dir="/tmp/e2e_solution_paths")
        router = TR(librarian=librarian, solution_registry=registry)

        task = {"task": "route llm request to domain engine"}
        result = await router.route(task)

        # The pipeline should complete without exception and return a valid result.
        assert result.task_id is not None
        assert isinstance(result.gate_results, dict)
        # The result must have a valid RouteStatus value.
        assert result.status in list(RS)

    @pytest.mark.asyncio
    async def test_full_pipeline_invoice_route(self):
        TR = self.tr_mod.TaskRouter
        RS = self.tr_mod.RouteStatus
        SPR = self.spr_mod.SolutionPathRegistry
        SL = self.sl_mod.SystemLibrarian

        librarian = SL()
        registry = SPR(data_dir="/tmp/e2e_solution_paths")
        router = TR(librarian=librarian, solution_registry=registry)

        task = {"task": "generate invoice document"}
        result = await router.route(task)

        assert result.task_id is not None
        assert result.confidence >= 0.0


# ===========================================================================
# PROD-001 and CAMP-001 capability registration tests
# ===========================================================================


class TestSystemLibrarianRegisteredCapabilities:
    """Verify that PROD-001 (production_assistant) and CAMP-001
    (outreach_campaign_planner) are registered in the SystemLibrarian
    capability map and are discoverable via find_capabilities().
    """

    def setup_method(self):
        self.sl_mod = _load_system_librarian()

    def test_production_assistant_in_module_capabilities(self):
        """PROD-001 must appear in _load_module_capabilities()."""
        librarian = self.sl_mod.SystemLibrarian()
        assert "production_assistant" in librarian.module_capabilities

    def test_production_assistant_has_expected_capabilities(self):
        librarian = self.sl_mod.SystemLibrarian()
        caps = librarian.module_capabilities["production_assistant"]
        lower = [c.lower() for c in caps]
        assert any("proposal" in c for c in lower), "PROD-001 must include 'proposal' capability"
        assert any("work order" in c for c in lower), "PROD-001 must include 'work order' capability"

    def test_outreach_campaign_planner_in_module_capabilities(self):
        """CAMP-001 must appear in _load_module_capabilities()."""
        librarian = self.sl_mod.SystemLibrarian()
        assert "outreach_campaign_planner" in librarian.module_capabilities

    def test_outreach_campaign_planner_has_expected_capabilities(self):
        librarian = self.sl_mod.SystemLibrarian()
        caps = librarian.module_capabilities["outreach_campaign_planner"]
        lower = [c.lower() for c in caps]
        assert any("campaign" in c for c in lower), "CAMP-001 must include 'campaign' capability"
        assert any("suppression" in c for c in lower), "CAMP-001 must include 'suppression' capability"

    def test_production_proposal_discoverable_via_find_capabilities(self):
        """find_capabilities() should surface production_assistant for production queries."""
        librarian = self.sl_mod.SystemLibrarian()
        matches = librarian.find_capabilities({"task": "submit production proposal"}, top_n=10)
        capability_ids = [m.capability_id for m in matches if not m.filtered]
        # At least one match from production_assistant should surface
        assert any("production" in cid for cid in capability_ids), (
            f"No production capability found in: {capability_ids}"
        )

    def test_campaign_discoverable_via_find_capabilities(self):
        """find_capabilities() should surface outreach_campaign_planner for campaign queries."""
        librarian = self.sl_mod.SystemLibrarian()
        matches = librarian.find_capabilities({"task": "create outreach campaign"}, top_n=10)
        capability_ids = [m.capability_id for m in matches if not m.filtered]
        assert any("campaign" in cid for cid in capability_ids), (
            f"No campaign capability found in: {capability_ids}"
        )

    def test_find_capabilities_returns_non_empty_for_production_query(self):
        librarian = self.sl_mod.SystemLibrarian()
        matches = librarian.find_capabilities({"task": "validate work order"}, top_n=5)
        assert len(matches) > 0

    def test_find_capabilities_returns_non_empty_for_campaign_query(self):
        librarian = self.sl_mod.SystemLibrarian()
        matches = librarian.find_capabilities({"task": "execute campaign step"}, top_n=5)
        assert len(matches) > 0


# ===========================================================================
# /api/librarian/query endpoint tests (unit — no live server)
# ===========================================================================


class TestLibrarianQueryEndpoint:
    """Verify the /api/librarian/query endpoint logic by calling the
    SystemLibrarian + TaskRouter directly (no live HTTP server needed).
    """

    def setup_method(self):
        self.sl_mod = _load_system_librarian()
        self.tr_mod = _load_task_router()
        self.spr_mod = _load_solution_path_registry()

    def _run_query(self, query: str, top_n: int = 5):
        """Helper: replicate the endpoint logic without a live server."""
        SL = self.sl_mod.SystemLibrarian
        TR = self.tr_mod.TaskRouter
        RS = self.tr_mod.RouteStatus
        SPR = self.spr_mod.SolutionPathRegistry

        task_dict = {"task": query}
        librarian = SL()
        raw_matches = librarian.find_capabilities(task_dict, top_n=top_n)

        matches = [
            {
                "capability_id": m.capability_id,
                "module_path": m.module_path,
                "score": m.score,
                "match_reasons": m.match_reasons,
                "cost_estimate": m.cost_estimate,
                "determinism": m.determinism,
                "filtered": m.filtered,
                "filter_reason": m.filter_reason,
            }
            for m in raw_matches
        ]

        router = TR(librarian=librarian, solution_registry=SPR(data_dir="/tmp/lq_test"))
        result = router.route_sync(task_dict)
        routing = {
            "status": result.status.value,
            "capability_id": result.solution_path.capability_id if result.solution_path else None,
            "score": result.solution_path.combined_score if result.solution_path else None,
        }

        return {"success": True, "query": query, "matches": matches, "routing": routing}

    def test_query_returns_success_true(self):
        resp = self._run_query("generate an invoice for a consulting project")
        assert resp["success"] is True

    def test_query_preserves_query_string(self):
        q = "submit production proposal for construction site"
        resp = self._run_query(q)
        assert resp["query"] == q

    def test_query_matches_is_list(self):
        resp = self._run_query("create outreach campaign for B2B segment")
        assert isinstance(resp["matches"], list)

    def test_query_matches_have_required_fields(self):
        resp = self._run_query("validate proposal")
        for m in resp["matches"]:
            assert "capability_id" in m
            assert "module_path" in m
            assert "score" in m
            assert "match_reasons" in m
            assert "filtered" in m

    def test_routing_has_status_field(self):
        resp = self._run_query("generate invoice document")
        assert "status" in resp["routing"]
        valid_statuses = {"approved", "hitl_required", "blocked", "no_viable_path"}
        assert resp["routing"]["status"] in valid_statuses

    def test_top_n_limits_unfiltered_matches(self):
        resp = self._run_query("route task to domain engine", top_n=3)
        unfiltered = [m for m in resp["matches"] if not m["filtered"]]
        assert len(unfiltered) <= 3

    def test_production_query_routes_successfully(self):
        resp = self._run_query("submit production proposal for OSHA compliance")
        assert resp["success"] is True
        assert len(resp["matches"]) > 0

    def test_campaign_query_routes_successfully(self):
        resp = self._run_query("create outreach campaign for ecommerce segment")
        assert resp["success"] is True
        assert len(resp["matches"]) > 0
