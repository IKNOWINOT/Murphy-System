"""
Supervisor Feedback Loops & Assumption Correction System

Prevents overconfident automation by:
- Requiring explicit assumption declaration
- Tracking assumption validity through telemetry and supervisor feedback
- Automatically correcting when assumptions are invalidated
- Preventing self-justification through anti-recursion protection

Components:
- schemas: Core data models with safety constraints
- assumption_management: Registry, validator, binding manager, lifecycle manager
- supervisor_loop: Supervisor interface, feedback processor (Phase 3)
- correction_loop: Invalidation detector, confidence/authority decayers (Phase 4)
- anti_recursion: Self-validation blocker, circular dependency detector (Phase 5)
"""

from .anti_recursion import (
    AntiRecursionSystem,
    CircularDependencyDetector,
    SelfValidationBlocker,
    ValidationSourceTracker,
)
from .assumption_management import (
    AssumptionBindingManager,
    AssumptionLifecycleManager,
    AssumptionRegistry,
    AssumptionValidator,
)
from .correction_loop import (
    AuthorityDecayer,
    ConfidenceDecayer,
    ExecutionFreezer,
    InvalidationDetector,
    ReExpansionTrigger,
)
from .schemas import (
    AssumptionArtifact,
    AssumptionBinding,
    AssumptionStatus,
    ConfidenceTrend,
    CorrectionAction,
    CorrectionActionType,
    FeedbackType,
    InvalidationSignal,
    InvalidationSource,
    MurphyIndexTrend,
    SupervisorFeedbackArtifact,
    ValidationEvidence,
)
from .supervisor_loop import FeedbackProcessor, FeedbackRouter, SupervisorAuditLogger, SupervisorInterface

__all__ = [
    # Schemas
    "AssumptionArtifact",
    "AssumptionStatus",
    "SupervisorFeedbackArtifact",
    "FeedbackType",
    "InvalidationSignal",
    "InvalidationSource",
    "CorrectionAction",
    "CorrectionActionType",
    "AssumptionBinding",
    "ConfidenceTrend",
    "MurphyIndexTrend",
    "ValidationEvidence",

    # Assumption Management
    "AssumptionRegistry",
    "AssumptionValidator",
    "AssumptionBindingManager",
    "AssumptionLifecycleManager",

    # Supervisor Loop
    "SupervisorInterface",
    "FeedbackProcessor",
    "FeedbackRouter",
    "SupervisorAuditLogger",

    # Correction Loop
    "InvalidationDetector",
    "ConfidenceDecayer",
    "AuthorityDecayer",
    "ExecutionFreezer",
    "ReExpansionTrigger",

    # Anti-Recursion
    "ValidationSourceTracker",
    "SelfValidationBlocker",
    "CircularDependencyDetector",
    "AntiRecursionSystem",
]
