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

from aionmind.bot_capability_bridge import load_bot_capabilities_into_registry
from aionmind.capability_registry import Capability, CapabilityRegistry
from aionmind.context_engine import ContextEngine
from aionmind.dag_bridge import compile_to_workflow_dag
from aionmind.memory_layer import MemoryLayer
from aionmind.models.context_graph import ContextEdge, ContextGraph, ContextNode
from aionmind.models.context_object import ContextObject
from aionmind.models.execution_graph import (
    ExecutionEdge,
    ExecutionGraphObject,
    ExecutionNode,
)
from aionmind.models.proposals import (
    OptimizationProposal,
    ProposalCategory,
    ProposalStatus,
)
from aionmind.optimization_engine import OptimizationEngine
from aionmind.orchestration_engine import OrchestrationEngine
from aionmind.reasoning_engine import ReasoningEngine
from aionmind.rsc_client_adapter import RSCClientAdapter, create_rsc_adapter
from aionmind.runtime_kernel import AionMindKernel
from aionmind.stability_integration import StabilityIntegration

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
    "load_bot_capabilities_into_registry",
    "RSCClientAdapter",
    "create_rsc_adapter",
    "compile_to_workflow_dag",
]
