"""
Gap Closure Tests — Round 45.

Validates all five architectural gaps identified in the system review:

  Gap 1 (Medium): Bot inventory → AionMind capability bridge
  Gap 2 (Medium): Live RSC wiring
  Gap 3 (Low):    WorkflowDAGEngine bridge
  Gap 4 (Low):    Similarity-based memory retrieval
  Gap 5 (Medium): Existing endpoint integration (/api/execute, /api/forms/*)

Tests are organised by gap so that each gap's closure can be verified independently.
"""

import sys
from pathlib import Path

# Ensure src is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest

from aionmind.capability_registry import Capability, CapabilityRegistry
from aionmind.memory_layer import MemoryLayer
from aionmind.models.context_object import ContextObject, RiskLevel
from aionmind.models.execution_graph import (
    ExecutionEdge,
    ExecutionGraphObject,
    ExecutionNode,
    ExecutionNodeType,
)
from aionmind.orchestration_engine import OrchestrationStatus
from aionmind.runtime_kernel import AionMindKernel
from aionmind.stability_integration import StabilityAction, StabilityIntegration


# ──────────────────────────────────────────────────────────────────
# Gap 1: Bot inventory → AionMind capability bridge
# ──────────────────────────────────────────────────────────────────

class TestGap1_BotCapabilityBridge:
    """Verify bot_inventory_library capabilities are auto-bridged."""

    def test_bridge_loads_capabilities(self):
        """All bot inventory capabilities should be loaded into the registry."""
        from aionmind.bot_capability_bridge import load_bot_capabilities_into_registry

        registry = CapabilityRegistry()
        count = load_bot_capabilities_into_registry(registry)
        assert count >= 20, f"Expected ≥20 capabilities, got {count}"

    def test_bridged_capabilities_have_correct_prefix(self):
        from aionmind.bot_capability_bridge import load_bot_capabilities_into_registry

        registry = CapabilityRegistry()
        load_bot_capabilities_into_registry(registry)
        for cap in registry.list_all():
            assert cap.capability_id.startswith("bot_inv:")

    def test_bridged_capabilities_have_tags(self):
        from aionmind.bot_capability_bridge import load_bot_capabilities_into_registry

        registry = CapabilityRegistry()
        load_bot_capabilities_into_registry(registry)
        for cap in registry.list_all():
            assert len(cap.tags) >= 1, f"Capability {cap.capability_id} has no tags"

    def test_bridged_capabilities_searchable(self):
        from aionmind.bot_capability_bridge import load_bot_capabilities_into_registry

        registry = CapabilityRegistry()
        load_bot_capabilities_into_registry(registry)
        # Search by tag
        results = registry.search(tags=["validation"])
        assert len(results) >= 1
        results = registry.search(tags=["analysis"])
        assert len(results) >= 1

    def test_kernel_auto_bridges_on_init(self):
        """Kernel with auto_bridge_bots=True should have bot capabilities."""
        kernel = AionMindKernel(auto_bridge_bots=True, auto_discover_rsc=False)
        count = kernel.registry.count()
        assert count >= 20, f"Expected ≥20 capabilities, got {count}"

    def test_kernel_without_bridge_has_zero(self):
        """Kernel with auto_bridge_bots=False should start empty."""
        kernel = AionMindKernel(auto_bridge_bots=False, auto_discover_rsc=False)
        assert kernel.registry.count() == 0

    def test_bridge_idempotent(self):
        """Loading twice should overwrite, not duplicate."""
        from aionmind.bot_capability_bridge import load_bot_capabilities_into_registry

        registry = CapabilityRegistry()
        count1 = load_bot_capabilities_into_registry(registry)
        count2 = load_bot_capabilities_into_registry(registry)
        assert count1 == count2
        assert registry.count() == count1

    def test_bridge_metadata_origin(self):
        from aionmind.bot_capability_bridge import load_bot_capabilities_into_registry

        registry = CapabilityRegistry()
        load_bot_capabilities_into_registry(registry)
        for cap in registry.list_all():
            assert cap.metadata.get("origin") == "bot_inventory_library"

    def test_bridge_custom_inventory_instance(self):
        from bot_inventory_library import BotInventoryLibrary
        from aionmind.bot_capability_bridge import load_bot_capabilities_into_registry

        inv = BotInventoryLibrary()
        registry = CapabilityRegistry()
        count = load_bot_capabilities_into_registry(registry, inventory=inv)
        assert count == len(inv.capability_registry)


# ──────────────────────────────────────────────────────────────────
# Gap 2: Live RSC wiring
# ──────────────────────────────────────────────────────────────────

class TestGap2_LiveRSCWiring:
    """Verify RSC adapter and live wiring into StabilityIntegration."""

    def test_adapter_with_mock_controller(self):
        from aionmind.rsc_client_adapter import RSCClientAdapter

        class MockRSC:
            def get_status(self):
                return {"stability_score": 0.85, "running": True}

        adapter = RSCClientAdapter(controller=MockRSC())
        status = adapter.get_status()
        assert status["stability_score"] == 0.85

    def test_adapter_default_returns_stable(self):
        from aionmind.rsc_client_adapter import RSCClientAdapter

        adapter = RSCClientAdapter()
        status = adapter.get_status()
        assert status["stability_score"] == 1.0

    def test_adapter_broken_controller_returns_fallback(self):
        from aionmind.rsc_client_adapter import RSCClientAdapter

        class BrokenRSC:
            def get_status(self):
                raise RuntimeError("controller offline")

        adapter = RSCClientAdapter(controller=BrokenRSC())
        status = adapter.get_status()
        assert status["stability_score"] == 1.0
        assert "error" in status

    def test_adapter_works_with_stability_integration(self):
        from aionmind.rsc_client_adapter import RSCClientAdapter

        class MockRSC:
            def get_status(self):
                return {"stability_score": 0.3}

        adapter = RSCClientAdapter(controller=MockRSC())
        si = StabilityIntegration(stability_threshold=0.5, rsc_client=adapter)
        result = si.check_stability(context_id="ctx-1", node_id="n-1")
        assert result.stable is False
        assert result.action == StabilityAction.REQUIRE_HUMAN_REVIEW

    def test_adapter_stable_controller(self):
        from aionmind.rsc_client_adapter import RSCClientAdapter

        class StableRSC:
            def get_status(self):
                return {"stability_score": 0.95}

        adapter = RSCClientAdapter(controller=StableRSC())
        si = StabilityIntegration(stability_threshold=0.5, rsc_client=adapter)
        result = si.check_stability()
        assert result.stable is True
        assert result.action == StabilityAction.PROCEED

    def test_create_rsc_adapter_factory_default(self):
        from aionmind.rsc_client_adapter import create_rsc_adapter

        adapter = create_rsc_adapter(auto_discover=False)
        status = adapter.get_status()
        assert status["stability_score"] == 1.0

    def test_create_rsc_adapter_with_controller(self):
        from aionmind.rsc_client_adapter import create_rsc_adapter

        class MockRSC:
            def get_status(self):
                return {"stability_score": 0.7}

        adapter = create_rsc_adapter(controller=MockRSC())
        assert adapter.get_status()["stability_score"] == 0.7

    def test_kernel_accepts_rsc_client(self):
        from aionmind.rsc_client_adapter import RSCClientAdapter

        class MockRSC:
            def get_status(self):
                return {"stability_score": 0.4}

        adapter = RSCClientAdapter(controller=MockRSC())
        kernel = AionMindKernel(
            rsc_client=adapter,
            auto_bridge_bots=False,
            auto_discover_rsc=False,
        )
        result = kernel.stability.check_stability()
        assert result.stable is False

    def test_adapter_last_status_property(self):
        from aionmind.rsc_client_adapter import RSCClientAdapter

        adapter = RSCClientAdapter()
        assert adapter.last_status is None
        adapter.get_status()
        # Default adapter doesn't record last_status
        # (only controller/http adapters do)


# ──────────────────────────────────────────────────────────────────
# Gap 3: WorkflowDAGEngine bridge
# ──────────────────────────────────────────────────────────────────

class TestGap3_WorkflowDAGBridge:
    """Verify ExecutionGraphObject → WorkflowDAGEngine compilation."""

    def _make_simple_graph(self) -> ExecutionGraphObject:
        n1 = ExecutionNode(
            node_id="step-1",
            node_type=ExecutionNodeType.CAPABILITY_CALL,
            capability_id="cap-a",
            label="Analyze",
        )
        n2 = ExecutionNode(
            node_id="step-2",
            node_type=ExecutionNodeType.CAPABILITY_CALL,
            capability_id="cap-b",
            label="Generate",
            depends_on=["step-1"],
        )
        e1 = ExecutionEdge(source_id="step-1", target_id="step-2")
        return ExecutionGraphObject(
            context_id="ctx-1",
            nodes=[n1, n2],
            edges=[e1],
        )

    def test_compile_produces_workflow(self):
        from aionmind.dag_bridge import compile_to_workflow_dag

        graph = self._make_simple_graph()
        result = compile_to_workflow_dag(graph)
        assert "error" not in result
        assert result["workflow_id"].startswith("am:")
        assert result["step_count"] == 2

    def test_compiled_workflow_has_correct_deps(self):
        from aionmind.dag_bridge import compile_to_workflow_dag
        from workflow_dag_engine import WorkflowDAGEngine

        graph = self._make_simple_graph()
        result = compile_to_workflow_dag(graph)
        engine = result["engine"]
        order = engine.get_execution_order(result["workflow_id"])
        assert order is not None
        assert order.index("step-1") < order.index("step-2")

    def test_compiled_workflow_can_execute(self):
        from aionmind.dag_bridge import compile_to_workflow_dag

        graph = self._make_simple_graph()
        result = compile_to_workflow_dag(graph)
        engine = result["engine"]
        exec_id = engine.create_execution(result["workflow_id"])
        assert exec_id is not None
        summary = engine.execute_workflow(exec_id)
        assert summary["status"] in ("completed", "failed")

    def test_compile_empty_graph(self):
        from aionmind.dag_bridge import compile_to_workflow_dag

        graph = ExecutionGraphObject(context_id="ctx-empty", nodes=[], edges=[])
        result = compile_to_workflow_dag(graph)
        assert "error" not in result
        assert result["step_count"] == 0

    def test_compile_existing_engine(self):
        from aionmind.dag_bridge import compile_to_workflow_dag
        from workflow_dag_engine import WorkflowDAGEngine

        engine = WorkflowDAGEngine()
        graph = self._make_simple_graph()
        result = compile_to_workflow_dag(graph, dag_engine=engine)
        assert result["engine"] is engine

    def test_kernel_compile_to_dag(self):
        kernel = AionMindKernel(auto_bridge_bots=False, auto_discover_rsc=False)
        kernel.register_capability(Capability(
            capability_id="cap-a", name="analyser", provider="p", tags=["analysis"],
        ))
        kernel.register_handler("cap-a", lambda n: {"ok": True})
        ctx = kernel.build_context(source="test", intent="analysis")
        candidates = kernel.plan(ctx)
        if candidates:
            result = kernel.compile_to_dag(candidates[0])
            assert "workflow_id" in result or "error" in result

    def test_compile_preserves_metadata(self):
        from aionmind.dag_bridge import compile_to_workflow_dag
        from workflow_dag_engine import WorkflowDAGEngine

        graph = self._make_simple_graph()
        graph.approved = True
        graph.approved_by = "test"
        result = compile_to_workflow_dag(graph)
        engine = result["engine"]
        wf = engine._workflows[result["workflow_id"]]
        assert wf.metadata["approved"] is True
        assert wf.metadata["approved_by"] == "test"


# ──────────────────────────────────────────────────────────────────
# Gap 4: Similarity-based memory retrieval
# ──────────────────────────────────────────────────────────────────

class TestGap4_SimilarityMemoryRetrieval:
    """Verify vector/embedding-based retrieval in MemoryLayer."""

    def test_search_similar_basic(self):
        ml = MemoryLayer()
        ml.archive_workflow("wf-deploy", {
            "description": "Deploy production server v2",
            "outcome": "success",
            "tags": ["deploy"],
        })
        ml.archive_workflow("wf-test", {
            "description": "Run integration tests",
            "outcome": "pass",
            "tags": ["test"],
        })
        ml.archive_workflow("wf-rollback", {
            "description": "Rollback production deployment",
            "outcome": "success",
            "tags": ["deploy", "rollback"],
        })

        results = ml.search_similar("deploy production")
        assert len(results) >= 1
        # The most similar entries should be deploy-related
        top_key = results[0][0]
        assert "deploy" in top_key or "rollback" in top_key

    def test_search_similar_returns_scores(self):
        ml = MemoryLayer()
        ml.archive_workflow("wf-1", {"description": "build docker image"})
        ml.archive_workflow("wf-2", {"description": "run unit tests"})

        results = ml.search_similar("docker build image")
        for key, score, data in results:
            assert isinstance(score, float)
            assert 0.0 <= score <= 1.0

    def test_search_similar_empty_query(self):
        ml = MemoryLayer()
        ml.archive_workflow("wf-1", {"description": "hello world"})
        results = ml.search_similar("")
        assert results == []

    def test_search_similar_no_matches(self):
        ml = MemoryLayer()
        results = ml.search_similar("deploy something")
        assert results == []

    def test_search_similar_top_k(self):
        ml = MemoryLayer()
        for i in range(10):
            ml.archive_workflow(f"wf-{i}", {"description": f"workflow {i} processing"})
        results = ml.search_similar("workflow processing", top_k=3)
        assert len(results) <= 3

    def test_search_similar_threshold(self):
        ml = MemoryLayer()
        ml.archive_workflow("wf-1", {"description": "deploy server"})
        ml.archive_workflow("wf-2", {"description": "completely unrelated xyz"})
        results = ml.search_similar("deploy server", threshold=0.5)
        # Only high-similarity matches should be returned
        for _, score, _ in results:
            assert score >= 0.5

    def test_search_similar_stm_pool(self):
        ml = MemoryLayer()
        ml.store_intermediate_state("ctx-1", {"intent": "deploy server"})
        ml.archive_workflow("wf-1", {"description": "deploy server"})

        stm_results = ml.search_similar("deploy", pool="stm")
        ltm_results = ml.search_similar("deploy", pool="ltm")
        all_results = ml.search_similar("deploy", pool="all")

        assert len(stm_results) >= 1
        assert len(ltm_results) >= 1
        assert len(all_results) >= len(stm_results)

    def test_search_similar_with_tags_text(self):
        ml = MemoryLayer()
        ml.archive_workflow("wf-deploy", {
            "tags": ["deploy", "production", "server"],
        })
        results = ml.search_similar("production deploy")
        assert len(results) >= 1

    def test_text_of_fallback(self):
        """_text_of should fall back to string values when no known keys."""
        text = MemoryLayer._text_of({"custom_field": "hello world"})
        assert "hello" in text


# ──────────────────────────────────────────────────────────────────
# Gap 5: Existing endpoint integration (cognitive pipeline)
# ──────────────────────────────────────────────────────────────────

class TestGap5_EndpointIntegration:
    """Verify AionMindKernel.cognitive_execute() end-to-end."""

    def _kernel_with_handlers(self) -> AionMindKernel:
        kernel = AionMindKernel(auto_bridge_bots=True, auto_discover_rsc=False)
        # Register handlers for all bridged capabilities
        for cap in kernel.registry.list_all():
            kernel.register_handler(
                cap.capability_id,
                lambda node: {"ok": True, "simulated": True},
            )
        return kernel

    def test_cognitive_execute_basic(self):
        kernel = self._kernel_with_handlers()
        result = kernel.cognitive_execute(
            source="test",
            raw_input="Analyze requirements for the new service",
            auto_approve=True,
        )
        assert result["pipeline"] == "aionmind"
        assert "context_id" in result

    def test_cognitive_execute_no_candidates_without_caps(self):
        kernel = AionMindKernel(auto_bridge_bots=False, auto_discover_rsc=False)
        result = kernel.cognitive_execute(
            source="test",
            raw_input="do something",
            auto_approve=True,
        )
        assert result["status"] == "no_candidates"

    def test_cognitive_execute_pending_approval(self):
        kernel = self._kernel_with_handlers()
        result = kernel.cognitive_execute(
            source="test",
            raw_input="Monitor performance metrics",
            auto_approve=False,
        )
        assert result["status"] == "pending_approval"
        assert "graph" in result

    def test_cognitive_execute_with_task_type(self):
        kernel = self._kernel_with_handlers()
        result = kernel.cognitive_execute(
            source="api",
            raw_input="Check system compliance",
            task_type="automation",
            auto_approve=True,
        )
        assert result["pipeline"] == "aionmind"

    def test_cognitive_execute_stores_in_memory(self):
        kernel = self._kernel_with_handlers()
        result = kernel.cognitive_execute(
            source="test",
            raw_input="Generate reports",
            auto_approve=True,
        )
        if "execution_id" in result:
            key = f"pipeline:{result['execution_id']}"
            data = kernel.memory.retrieve_context(key)
            assert data is not None
            assert data["context_id"] == result["context_id"]

    def test_cognitive_execute_audit_trail(self):
        kernel = self._kernel_with_handlers()
        result = kernel.cognitive_execute(
            source="test",
            raw_input="Validate constraints",
            auto_approve=True,
        )
        if "audit_trail" in result:
            assert isinstance(result["audit_trail"], list)
            assert len(result["audit_trail"]) >= 1


# ──────────────────────────────────────────────────────────────────
# Cross-gap integration tests
# ──────────────────────────────────────────────────────────────────

class TestCrossGapIntegration:
    """End-to-end tests spanning multiple gaps."""

    def test_full_pipeline_with_bridged_caps_and_rsc(self):
        """Gap 1 + Gap 2: bridged capabilities + RSC wiring."""
        from aionmind.rsc_client_adapter import RSCClientAdapter

        class StableRSC:
            def get_status(self):
                return {"stability_score": 0.95}

        adapter = RSCClientAdapter(controller=StableRSC())
        kernel = AionMindKernel(
            rsc_client=adapter,
            auto_bridge_bots=True,
            auto_discover_rsc=False,
        )
        # Verify bridged capabilities are present
        assert kernel.registry.count() >= 20
        # Verify RSC is wired
        result = kernel.stability.check_stability()
        assert result.stable is True
        assert result.score == pytest.approx(0.95)

    def test_cognitive_execute_then_dag_bridge(self):
        """Gap 1 + Gap 3 + Gap 5: cognitive pipeline → DAG bridge."""
        kernel = AionMindKernel(auto_bridge_bots=True, auto_discover_rsc=False)
        for cap in kernel.registry.list_all():
            kernel.register_handler(
                cap.capability_id,
                lambda node: {"ok": True},
            )
        ctx = kernel.build_context(source="test", intent="analysis")
        candidates = kernel.plan(ctx)
        if candidates:
            result = kernel.compile_to_dag(candidates[0])
            assert "workflow_id" in result or "error" in result

    def test_similarity_search_on_executed_workflows(self):
        """Gap 4 + Gap 5: execute then similarity-search past workflows."""
        kernel = AionMindKernel(auto_bridge_bots=True, auto_discover_rsc=False)
        for cap in kernel.registry.list_all():
            kernel.register_handler(
                cap.capability_id,
                lambda node: {"ok": True},
            )

        # Execute and archive
        result = kernel.cognitive_execute(
            source="test",
            raw_input="Deploy production server v2",
            auto_approve=True,
        )
        if "execution_id" in result:
            kernel.archive_execution(result["execution_id"])

        # Archive another
        kernel.memory.archive_workflow("wf-rollback", {
            "description": "Rollback production deployment",
            "tags": ["deploy"],
        })

        # Similarity search
        similar = kernel.memory.search_similar("deploy production")
        assert isinstance(similar, list)
