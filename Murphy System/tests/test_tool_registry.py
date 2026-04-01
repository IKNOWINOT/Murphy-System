"""
Tests for the Universal Tool Registry (TR-001..TR-003).

Covers: registration, lookup, search, execution tracking,
confidence history, AionMind integration, and budget summary.
"""

from __future__ import annotations

import pytest

from src.tool_registry.models import (
    CostEstimate,
    CostTier,
    PermissionLevel,
    ToolDefinition,
    ToolExecutionResult,
    ToolInputSchema,
    ToolOutputSchema,
)
from src.tool_registry.registry import UniversalToolRegistry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def registry():
    return UniversalToolRegistry()


@pytest.fixture
def sample_tool():
    return ToolDefinition(
        tool_id="bot.triage",
        name="Triage Bot",
        description="Routes requests to the correct handler.",
        provider="bot",
        tags=["routing", "triage"],
        category="orchestration",
        permission_level=PermissionLevel.LOW,
        cost_estimate=CostEstimate(tier=CostTier.FREE, estimated_usd=0.0),
        input_schema=ToolInputSchema(
            fields={"request": {"type": "string"}},
            required=["request"],
        ),
        output_schema=ToolOutputSchema(
            fields={"handler": {"type": "string"}},
        ),
    )


@pytest.fixture
def expensive_tool():
    return ToolDefinition(
        tool_id="engine.trading",
        name="Trading Engine",
        description="Executes trades on financial markets.",
        provider="engine",
        tags=["trading", "finance"],
        category="finance",
        permission_level=PermissionLevel.CRITICAL,
        requires_approval=True,
        cost_estimate=CostEstimate(
            tier=CostTier.PREMIUM,
            estimated_usd=2.50,
            token_estimate=5000,
        ),
    )


# ---------------------------------------------------------------------------
# Registration tests
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_register_and_get(self, registry, sample_tool):
        registry.register(sample_tool)
        fetched = registry.get("bot.triage")
        assert fetched.tool_id == "bot.triage"
        assert fetched.name == "Triage Bot"

    def test_register_overwrites(self, registry, sample_tool):
        registry.register(sample_tool)
        updated = sample_tool.model_copy(update={"version": "2.0.0"})
        registry.register(updated)
        assert registry.get("bot.triage").version == "2.0.0"
        assert registry.count() == 1

    def test_unregister(self, registry, sample_tool):
        registry.register(sample_tool)
        removed = registry.unregister("bot.triage")
        assert removed.tool_id == "bot.triage"
        assert registry.count() == 0

    def test_unregister_not_found(self, registry):
        with pytest.raises(KeyError):
            registry.unregister("nonexistent")

    def test_get_not_found(self, registry):
        with pytest.raises(KeyError):
            registry.get("nonexistent")

    def test_count(self, registry, sample_tool, expensive_tool):
        assert registry.count() == 0
        registry.register(sample_tool)
        assert registry.count() == 1
        registry.register(expensive_tool)
        assert registry.count() == 2

    def test_list_all(self, registry, sample_tool, expensive_tool):
        registry.register(sample_tool)
        registry.register(expensive_tool)
        all_tools = registry.list_all()
        assert len(all_tools) == 2
        ids = {t.tool_id for t in all_tools}
        assert ids == {"bot.triage", "engine.trading"}


# ---------------------------------------------------------------------------
# Search tests
# ---------------------------------------------------------------------------

class TestSearch:
    def test_search_by_tags(self, registry, sample_tool, expensive_tool):
        registry.register(sample_tool)
        registry.register(expensive_tool)
        results = registry.search(tags=["trading"])
        assert len(results) == 1
        assert results[0].tool_id == "engine.trading"

    def test_search_by_provider(self, registry, sample_tool, expensive_tool):
        registry.register(sample_tool)
        registry.register(expensive_tool)
        results = registry.search(provider="bot")
        assert len(results) == 1
        assert results[0].tool_id == "bot.triage"

    def test_search_by_category(self, registry, sample_tool, expensive_tool):
        registry.register(sample_tool)
        registry.register(expensive_tool)
        results = registry.search(category="finance")
        assert len(results) == 1

    def test_search_by_name(self, registry, sample_tool):
        registry.register(sample_tool)
        results = registry.search(name_contains="triage")
        assert len(results) == 1

    def test_search_max_permission(self, registry, sample_tool, expensive_tool):
        registry.register(sample_tool)
        registry.register(expensive_tool)
        results = registry.search(max_permission=PermissionLevel.MEDIUM)
        assert len(results) == 1
        assert results[0].tool_id == "bot.triage"

    def test_search_max_cost_tier(self, registry, sample_tool, expensive_tool):
        registry.register(sample_tool)
        registry.register(expensive_tool)
        results = registry.search(max_cost_tier=CostTier.MODERATE)
        assert len(results) == 1
        assert results[0].tool_id == "bot.triage"

    def test_search_no_results(self, registry, sample_tool):
        registry.register(sample_tool)
        results = registry.search(tags=["nonexistent"])
        assert len(results) == 0

    def test_search_by_input_field(self, registry, sample_tool):
        registry.register(sample_tool)
        results = registry.search_by_input_field("request")
        assert len(results) == 1

    def test_search_combined_filters(self, registry, sample_tool, expensive_tool):
        registry.register(sample_tool)
        registry.register(expensive_tool)
        results = registry.search(provider="bot", tags=["routing"])
        assert len(results) == 1


# ---------------------------------------------------------------------------
# Execution tracking tests
# ---------------------------------------------------------------------------

class TestExecutionTracking:
    def test_record_execution(self, registry):
        result = ToolExecutionResult(
            tool_id="bot.triage",
            success=True,
            output={"handler": "sales"},
            execution_time_ms=15.0,
        )
        registry.record_execution(result)
        log = registry.get_execution_log()
        assert len(log) == 1
        assert log[0].tool_id == "bot.triage"

    def test_confidence_history(self, registry):
        for _ in range(5):
            registry.record_execution(ToolExecutionResult(
                tool_id="bot.triage", success=True,
            ))
        registry.record_execution(ToolExecutionResult(
            tool_id="bot.triage", success=False,
        ))

        stats = registry.get_confidence_history("bot.triage")
        assert stats["total_executions"] == 6
        assert stats["successes"] == 5
        assert stats["failures"] == 1
        assert stats["consecutive_successes"] == 0  # last was failure

    def test_confidence_history_unknown_tool(self, registry):
        stats = registry.get_confidence_history("nonexistent")
        assert stats["total_executions"] == 0
        assert stats["success_rate"] == 0.0

    def test_consecutive_successes(self, registry):
        for _ in range(10):
            registry.record_execution(ToolExecutionResult(
                tool_id="bot.triage", success=True,
            ))
        stats = registry.get_confidence_history("bot.triage")
        assert stats["consecutive_successes"] == 10


# ---------------------------------------------------------------------------
# AionMind integration tests
# ---------------------------------------------------------------------------

class TestAionMindIntegration:
    def test_to_capability_list(self, registry, sample_tool):
        registry.register(sample_tool)
        caps = registry.to_capability_list()
        assert len(caps) == 1
        assert caps[0]["capability_id"] == "bot.triage"
        assert caps[0]["risk_level"] == "low"

    def test_budget_summary(self, registry, sample_tool, expensive_tool):
        registry.register(sample_tool)
        registry.register(expensive_tool)
        summary = registry.get_budget_summary()
        assert summary["total_tools"] == 2
        assert "free" in summary["tier_distribution"]
        assert "premium" in summary["tier_distribution"]
        assert summary["total_estimated_usd"] == 2.50


# ---------------------------------------------------------------------------
# Model validation tests
# ---------------------------------------------------------------------------

class TestModelValidation:
    def test_tool_id_required(self):
        with pytest.raises(Exception):
            ToolDefinition(tool_id="", name="Test")

    def test_name_required(self):
        with pytest.raises(Exception):
            ToolDefinition(tool_id="test", name="")

    def test_cost_estimate_non_negative(self):
        with pytest.raises(Exception):
            CostEstimate(estimated_usd=-1.0)

    def test_permission_levels(self):
        assert PermissionLevel.UNRESTRICTED.value == "unrestricted"
        assert PermissionLevel.CRITICAL.value == "critical"

    def test_tool_definition_defaults(self):
        tool = ToolDefinition(tool_id="test.tool", name="Test Tool")
        assert tool.version == "1.0.0"
        assert tool.permission_level == PermissionLevel.MEDIUM
        assert tool.cost_estimate.tier == CostTier.FREE
