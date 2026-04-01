"""
Universal Tool Registry — thread-safe in-process registry.

Design Label: TR-003

Provides:
  • register / unregister / get / list_all / search
  • Permission-gated lookup
  • Cost-aware discovery for budget planners
  • Integration hooks for AionMind CapabilityRegistry
"""

from __future__ import annotations

import logging
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional

from src.tool_registry.models import (
    CostTier,
    PermissionLevel,
    ToolDefinition,
    ToolExecutionResult,
)

logger = logging.getLogger(__name__)

_MAX_DECISION_LOG = 200


class UniversalToolRegistry:
    """Thread-safe universal tool registry.

    Every bot, engine, and integration self-registers here.
    AionMind queries this to reason about available capabilities.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tools: Dict[str, ToolDefinition] = {}
        self._execution_log: Deque[ToolExecutionResult] = deque(maxlen=_MAX_DECISION_LOG)
        self._confidence_history: Dict[str, List[bool]] = {}  # tool_id → recent outcomes

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, tool: ToolDefinition) -> None:
        """Register or overwrite a tool definition."""
        with self._lock:
            prev = self._tools.get(tool.tool_id)
            self._tools[tool.tool_id] = tool
            if prev:
                logger.info("Tool re-registered: %s (v%s → v%s)",
                            tool.tool_id, prev.version, tool.version)
            else:
                logger.info("Tool registered: %s v%s [%s]",
                            tool.tool_id, tool.version, tool.permission_level.value)

    def unregister(self, tool_id: str) -> ToolDefinition:
        """Remove a tool.  Raises KeyError if not found."""
        with self._lock:
            tool = self._tools.pop(tool_id)
            logger.info("Tool unregistered: %s", tool_id)
            return tool

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get(self, tool_id: str) -> ToolDefinition:
        """Get a single tool by ID.  Raises KeyError if not found."""
        with self._lock:
            return self._tools[tool_id]

    def list_all(self) -> List[ToolDefinition]:
        """Return all registered tools (snapshot)."""
        with self._lock:
            return list(self._tools.values())

    def count(self) -> int:
        """Number of registered tools."""
        with self._lock:
            return len(self._tools)

    # ------------------------------------------------------------------
    # Discovery / Search
    # ------------------------------------------------------------------

    def search(
        self,
        *,
        tags: Optional[List[str]] = None,
        provider: Optional[str] = None,
        category: Optional[str] = None,
        name_contains: Optional[str] = None,
        max_permission: Optional[PermissionLevel] = None,
        max_cost_tier: Optional[CostTier] = None,
    ) -> List[ToolDefinition]:
        """Search tools with optional filters.

        All filters are AND-combined.
        """
        _perm_order = list(PermissionLevel)
        _cost_order = list(CostTier)

        with self._lock:
            results: List[ToolDefinition] = []
            for tool in self._tools.values():
                if tags and not set(tags).intersection(tool.tags):
                    continue
                if provider and tool.provider != provider:
                    continue
                if category and tool.category != category:
                    continue
                if name_contains and name_contains.lower() not in tool.name.lower():
                    continue
                if max_permission is not None:
                    if _perm_order.index(tool.permission_level) > _perm_order.index(max_permission):
                        continue
                if max_cost_tier is not None:
                    if _cost_order.index(tool.cost_estimate.tier) > _cost_order.index(max_cost_tier):
                        continue
                results.append(tool)
            return results

    def search_by_input_field(self, field_name: str) -> List[ToolDefinition]:
        """Find tools whose input schema declares a specific field."""
        with self._lock:
            return [
                t for t in self._tools.values()
                if field_name in t.input_schema.fields
            ]

    # ------------------------------------------------------------------
    # Execution tracking (for confidence history)
    # ------------------------------------------------------------------

    def record_execution(self, result: ToolExecutionResult) -> None:
        """Record a tool execution result for confidence history."""
        with self._lock:
            self._execution_log.append(result)
            history = self._confidence_history.setdefault(result.tool_id, [])
            history.append(result.success)
            # Bounded: keep last 100 outcomes per tool
            if len(history) > 100:
                self._confidence_history[result.tool_id] = history[-100:]

    def get_confidence_history(self, tool_id: str) -> Dict[str, Any]:
        """Return confidence stats for a tool."""
        with self._lock:
            history = self._confidence_history.get(tool_id, [])
            total = len(history)
            successes = sum(history)
            return {
                "tool_id": tool_id,
                "total_executions": total,
                "successes": successes,
                "failures": total - successes,
                "success_rate": successes / total if total > 0 else 0.0,
                "consecutive_successes": self._consecutive_tail(history, True),
            }

    def get_execution_log(self) -> List[ToolExecutionResult]:
        """Return recent execution log (bounded)."""
        with self._lock:
            return list(self._execution_log)

    # ------------------------------------------------------------------
    # AionMind integration helpers
    # ------------------------------------------------------------------

    def to_capability_list(self) -> List[Dict[str, Any]]:
        """Export registry as AionMind-compatible capability dicts."""
        with self._lock:
            return [
                {
                    "capability_id": t.tool_id,
                    "name": t.name,
                    "description": t.description,
                    "provider": t.provider,
                    "input_schema": t.input_schema.model_dump(),
                    "output_schema": t.output_schema.model_dump(),
                    "tags": t.tags,
                    "risk_level": t.permission_level.value,
                    "requires_approval": t.requires_approval,
                    "max_concurrency": t.max_concurrency,
                    "timeout_seconds": t.timeout_seconds,
                    "cost_estimate": t.cost_estimate.model_dump(),
                    "metadata": t.metadata,
                }
                for t in self._tools.values()
            ]

    def get_budget_summary(self) -> Dict[str, Any]:
        """Summarise cost profile of all registered tools."""
        with self._lock:
            tiers: Dict[str, int] = {}
            total_est = 0.0
            for t in self._tools.values():
                tier = t.cost_estimate.tier.value
                tiers[tier] = tiers.get(tier, 0) + 1
                total_est += t.cost_estimate.estimated_usd
            return {
                "total_tools": len(self._tools),
                "tier_distribution": tiers,
                "total_estimated_usd": round(total_est, 6),
            }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _consecutive_tail(history: List[bool], value: bool) -> int:
        """Count consecutive *value* at the tail of *history*."""
        count = 0
        for item in reversed(history):
            if item is value:
                count += 1
            else:
                break
        return count
