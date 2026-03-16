"""
System A → System B Bridge Layer

Provides a safe, explicit, typed, and logged bridge between:
- System A: Sandbox hypotheses with zero execution rights
- System B: Control Plane with gate synthesis and packet compilation

SAFETY CONSTRAINTS:
- System A outputs are sandbox-only artifacts
- System B is the only system that can compile ExecutionPackets
- No hidden execution paths
- All bridging is explicit, typed, logged, and testable
"""

__version__ = "1.0.0"

from .compilation import (
    CompilationGate,
    ExecutionPacketCompiler,
)
from .intake import (
    ClaimExtractor,
    HypothesisIntakeService,
    VerificationRequestGenerator,
)
from .models import (
    BlockingReason,
    CompilationResult,
    HypothesisArtifact,
    VerificationArtifact,
    VerificationRequest,
    VerificationStatus,
)
from .ux import (
    BlockingFeedback,
    ExecutabilityExplainer,
)

__all__ = [
    # Models
    "HypothesisArtifact",
    "VerificationArtifact",
    "VerificationRequest",
    "VerificationStatus",
    "CompilationResult",
    "BlockingReason",

    # Intake
    "HypothesisIntakeService",
    "ClaimExtractor",
    "VerificationRequestGenerator",

    # Compilation
    "ExecutionPacketCompiler",
    "CompilationGate",

    # UX
    "ExecutabilityExplainer",
    "BlockingFeedback",
]
