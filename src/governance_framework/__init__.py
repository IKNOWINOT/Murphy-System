"""
Murphy System Governance Framework

This package implements the formal governance framework including:
- Agent Descriptor management and validation
- Governance artifact ingestion and validation
- Stability monitoring and refusal semantics
- Scheduler rules and system invariants enforcement
"""

from .agent_descriptor_complete import ActionType, AgentDescriptor, AgentDescriptorValidator, AuthorityBand
from .artifact_ingestion import ArtifactRegistry, ArtifactType, ArtifactValidator, GovernanceArtifact
from .refusal_handler import RefusalHandler as RefusalHandlerImpl
from .refusal_handler import RefusalRecord
from .scheduler import GovernanceScheduler, SchedulingDecision
from .stability_controller import ExecutionOutcome, RefusalHandler, StabilityController, StabilityMetrics

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
