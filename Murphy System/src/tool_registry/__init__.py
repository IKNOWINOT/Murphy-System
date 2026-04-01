"""
Tool Registry — Universal self-describing tool registration system.

Design Label: TR-001
Module ID:    src.tool_registry

Every bot, engine, and integration self-registers with:
  • A Pydantic input/output schema
  • A permission level (maps to HITL confidence gates)
  • A cost estimate (maps to cost-tracker concept)
  • Discovery metadata for AionMind reasoning

Commissioning answers
─────────────────────
Q: Does the module do what it was designed to do?
A: Provides a thread-safe, in-process registry for tools with schema
   validation, permission gating, cost estimation, and discovery search.

Q: What conditions are possible?
A: Register / unregister / lookup / search / list.  Duplicate IDs
   overwrite.  Missing IDs raise KeyError.  Bounded decision log (200).

Q: What is the expected result at all points of operation?
A: Every registered tool is discoverable by AionMind via tag/provider/
   permission search.  Cost estimates flow to orchestrator budgets.

Q: Has hardening been applied?
A: Thread-safe via threading.Lock, bounded collections, Pydantic
   validation on all inputs, no bare except.
"""

from __future__ import annotations

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

__all__ = [
    "CostEstimate",
    "CostTier",
    "PermissionLevel",
    "ToolDefinition",
    "ToolExecutionResult",
    "ToolInputSchema",
    "ToolOutputSchema",
    "UniversalToolRegistry",
]
