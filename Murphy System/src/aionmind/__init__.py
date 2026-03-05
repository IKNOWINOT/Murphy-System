"""
AionMind Runtime Framework — Murphy System 2.0a (Embedded)

Collaborative Orchestrator-of-Orchestrators implementing six cognitive layers:
  Layer 1: Cognitive Input Layer (Context Awareness Engine)
  Layer 2: Collaborative Reasoning Engine (Orchestrator-of-Orchestrators)
  Layer 3: Recursive Stability Controller Integration
  Layer 4: Dynamic Orchestration Engine (Graph Execution)
  Layer 5: Memory Integration Layer (STM / LTM)
  Layer 6: Optimization & Feedback (Conservative Learning)

Non-negotiable constraint: NO AUTONOMY.
  - High-risk / low-confidence / irreversible operations require human approval (HITL).
  - Telemetry and learning loops never trigger execution actions directly.
  - Optimization outputs are proposals / recommendations only.
"""

from aionmind.models.context_object import ContextObject
from aionmind.models.context_graph import ContextGraph, ContextNode, ContextEdge
from aionmind.models.execution_graph import (
    ExecutionGraphObject,
    ExecutionNode,
    ExecutionEdge,
)
from aionmind.models.proposals import (
    OptimizationProposal,
    ProposalStatus,
    ProposalCategory,
)
from aionmind.context_engine import ContextEngine
from aionmind.capability_registry import CapabilityRegistry, Capability
from aionmind.reasoning_engine import ReasoningEngine
from aionmind.stability_integration import StabilityIntegration
from aionmind.orchestration_engine import OrchestrationEngine
from aionmind.memory_layer import MemoryLayer
from aionmind.optimization_engine import OptimizationEngine
from aionmind.runtime_kernel import AionMindKernel

__all__ = [
    "ContextObject",
    "ContextGraph",
    "ContextNode",
    "ContextEdge",
    "ExecutionGraphObject",
    "ExecutionNode",
    "ExecutionEdge",
    "OptimizationProposal",
    "ProposalStatus",
    "ProposalCategory",
    "ContextEngine",
    "CapabilityRegistry",
    "Capability",
    "ReasoningEngine",
    "StabilityIntegration",
    "OrchestrationEngine",
    "MemoryLayer",
    "OptimizationEngine",
    "AionMindKernel",
]
