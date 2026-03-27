"""
Telemetry & Learning Loops System

Enterprise telemetry collection with conservative learning loops that harden
gates, tune phase schedules, detect bottlenecks, and invalidate assumptions.

SAFETY CONSTRAINTS:
- Telemetry NEVER generates execution actions directly
- All gate changes require Control Plane authorization
- Default trajectory is towards caution
- Relaxation requires deterministic evidence
"""

__version__ = "1.0.0"

# Try to import the full module, fall back to simple wrapper if dependencies missing
try:
    from .ingestion import (
        TelemetryBus,
        TelemetryIngester,
    )
    from .learning import (
        AssumptionInvalidator,
        BottleneckDetector,
        GateStrengtheningEngine,
        HardeningPolicyEngine,
        PhaseTuningEngine,
    )
    from .models import (
        ControlTelemetry,
        GateEvolutionArtifact,
        HumanTelemetry,
        InsightArtifact,
        MarketTelemetry,
        OperationalTelemetry,
        SafetyTelemetry,
        TelemetryArtifact,
        TelemetryDomain,
    )
    from .shadow_mode import (
        AuthorizationInterface,
        ShadowModeController,
    )

    __all__ = [
        # Models
        "TelemetryDomain",
        "OperationalTelemetry",
        "HumanTelemetry",
        "ControlTelemetry",
        "SafetyTelemetry",
        "MarketTelemetry",
        "TelemetryArtifact",
        "GateEvolutionArtifact",
        "InsightArtifact",

        # Ingestion
        "TelemetryBus",
        "TelemetryIngester",

        # Learning
        "GateStrengtheningEngine",
        "PhaseTuningEngine",
        "BottleneckDetector",
        "AssumptionInvalidator",
        "HardeningPolicyEngine",

        # Shadow Mode
        "ShadowModeController",
        "AuthorizationInterface",

        # Simple wrapper (always available)
        "TelemetryLearningEngine",
        "SimpleTelemetryLearningEngine",
    ]

    # Also make the simple wrapper available when full imports succeed
    from .simple_wrapper import (
        SimpleTelemetryLearningEngine,
        TelemetryLearningEngine,
    )
except ImportError as exc:
    # Fall back to simple wrapper without external dependencies
    import logging
    logging.getLogger(__name__).warning(
        "Using simplified telemetry learning engine due to missing dependencies: %s", exc,
    )

    from .simple_wrapper import SimpleTelemetryLearningEngine, TelemetryLearningEngine

    __all__ = [
        "TelemetryLearningEngine",
        "SimpleTelemetryLearningEngine"
    ]
