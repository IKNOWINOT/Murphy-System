"""
Murphy System Governance Framework

This package implements the formal governance framework including:
- Agent Descriptor management and validation
- Governance artifact ingestion and validation
- Stability monitoring and refusal semantics
- Scheduler rules and system invariants enforcement
"""

from .agent_descriptor_complete import AgentDescriptor, AgentDescriptorValidator, AuthorityBand, ActionType
from .artifact_ingestion import GovernanceArtifact, ArtifactRegistry, ArtifactValidator, ArtifactType
from .stability_controller import StabilityController, StabilityMetrics, RefusalHandler, ExecutionOutcome
from .scheduler import GovernanceScheduler, SchedulingDecision
from .refusal_handler import RefusalHandler as RefusalHandlerImpl, RefusalRecord

__version__ = "1.0.0"
__all__ = [
    "AgentDescriptor",
    "AgentDescriptorValidator",
    "AuthorityBand",
    "ActionType",
    "GovernanceArtifact",
    "ArtifactRegistry",
    "ArtifactValidator",
    "ArtifactType",
    "StabilityController",
    "StabilityMetrics",
    "RefusalHandler",
    "ExecutionOutcome",
    "GovernanceScheduler",
    "SchedulingDecision",
    "RefusalHandlerImpl",
    "RefusalRecord"
]
