"""
Tests for Layer 2 — CapabilityRegistry and ReasoningEngine.
"""

import pytest

from aionmind.capability_registry import Capability, CapabilityRegistry
from aionmind.models.context_object import ContextObject, RiskLevel
from aionmind.models.execution_graph import (
    ExecutionGraphObject,
    ExecutionNodeType,
)
from aionmind.reasoning_engine import ReasoningEngine


# ── helpers ───────────────────────────────────────────────────────

def _sample_caps() -> list:
    return [
        Capability(
            capability_id="cap-analysis",
            name="analysis",
            provider="bot-a",
            tags=["analysis", "data"],
        ),
        Capability(
            capability_id="cap-generation",
            name="generation",
            provider="bot-b",
            tags=["generation"],
            requires_approval=True,
        ),
        Capability(
            capability_id="cap-validation",
            name="validation",
            provider="bot-c",
            tags=["validation"],
        ),
    ]


def _registry_with_caps() -> CapabilityRegistry:
    reg = CapabilityRegistry()
    for c in _sample_caps():
        reg.register(c)
    return reg


# ── CapabilityRegistry ────────────────────────────────────────────

class TestCapabilityRegistry:

    def test_register_and_get(self):
        reg = CapabilityRegistry()
        cap = Capability(capability_id="c1", name="test", provider="p1")
        reg.register(cap)
        assert reg.get("c1") is cap
        assert reg.count() == 1

    def test_unregister(self):
        reg = CapabilityRegistry()
        cap = Capability(capability_id="c1", name="test", provider="p1")
        reg.register(cap)
        reg.unregister("c1")
        assert reg.get("c1") is None
        assert reg.count() == 0

    def test_search_by_tags(self):
        reg = _registry_with_caps()
        results = reg.search(tags=["analysis"])
        assert len(results) == 1
        assert results[0].capability_id == "cap-analysis"

    def test_search_by_provider(self):
        reg = _registry_with_caps()
        results = reg.search(provider="bot-b")
        assert len(results) == 1

    def test_search_by_name(self):
        reg = _registry_with_caps()
        results = reg.search(name_contains="valid")
        assert len(results) == 1
        assert results[0].capability_id == "cap-validation"

    def test_list_all(self):
        reg = _registry_with_caps()
        assert len(reg.list_all()) == 3


# ── ReasoningEngine ──────────────────────────────────────────────

class TestReasoningEngine:

    def test_generate_three_candidates(self):
        reg = _registry_with_caps()
        engine = ReasoningEngine(reg)
        ctx = ContextObject(source="test", intent="analysis generation")
        candidates = engine.generate_candidates(ctx, max_candidates=3)
        assert len(candidates) == 3
        for g in candidates:
            assert isinstance(g, ExecutionGraphObject)
            assert g.context_id == ctx.context_id

    def test_candidates_contain_rsc_checks(self):
        """Every candidate graph must include RSC check nodes."""
        reg = _registry_with_caps()
        engine = ReasoningEngine(reg)
        ctx = ContextObject(source="test", intent="analysis")
        candidates = engine.generate_candidates(ctx)
        for g in candidates:
            rsc_nodes = [
                n for n in g.nodes
                if n.node_type == ExecutionNodeType.RSC_CHECK
            ]
            assert len(rsc_nodes) > 0, "Graph must include at least one RSC check node"

    def test_high_risk_context_forces_approval(self):
        """All nodes must require approval when context is high-risk."""
        reg = _registry_with_caps()
        engine = ReasoningEngine(reg)
        ctx = ContextObject(
            source="test",
            intent="analysis",
            risk_level=RiskLevel.CRITICAL,
        )
        candidates = engine.generate_candidates(ctx)
        for g in candidates:
            for n in g.nodes:
                if n.node_type == ExecutionNodeType.CAPABILITY_CALL:
                    assert n.requires_approval, (
                        f"Node {n.node_id} should require approval for critical risk"
                    )

    def test_select_best_returns_highest_score(self):
        reg = _registry_with_caps()
        engine = ReasoningEngine(reg)
        ctx = ContextObject(source="test", intent="analysis")
        candidates = engine.generate_candidates(ctx)
        best = engine.select_best(candidates, ctx)
        assert best is not None
        assert best.score > 0
        assert best.rationale != ""

    def test_select_best_empty_returns_none(self):
        reg = _registry_with_caps()
        engine = ReasoningEngine(reg)
        ctx = ContextObject(source="test")
        best = engine.select_best([], ctx)
        assert best is None

    def test_no_capabilities_returns_empty(self):
        reg = CapabilityRegistry()
        engine = ReasoningEngine(reg)
        ctx = ContextObject(source="test")
        candidates = engine.generate_candidates(ctx)
        assert candidates == []

    def test_graphs_are_not_approved_by_default(self):
        """Generated graphs must be proposals — never pre-approved."""
        reg = _registry_with_caps()
        engine = ReasoningEngine(reg)
        ctx = ContextObject(source="test", intent="validation")
        candidates = engine.generate_candidates(ctx)
        for g in candidates:
            assert g.approved is False, "Candidate graph must not be pre-approved"
            assert g.approved_by is None
