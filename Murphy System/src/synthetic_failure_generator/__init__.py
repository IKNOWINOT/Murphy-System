"""
Synthetic Failure Generator - Training & Stress Plane
======================================================

Manufactures disasters safely for anti-fragile learning.

Key Responsibilities:
- Generate synthetic failures across all dimensions
- Create training data for confidence models
- Generate gate policy learning datasets
- Simulate execution stress tests
- Replay historical disasters

Design Principles:
1. Never touch production interfaces
2. Never emit real execution packets
3. Only produce training artifacts
4. Generate structurally realistic failures
5. Enable anti-fragile learning
"""

from .control_failures import ControlPlaneFailureGenerator
from .injection_pipeline import FailureInjectionPipeline
from .interface_failures import InterfaceFailureGenerator
from .models import (
    BaseScenario,
    ConfidenceProfile,
    FailureCase,
    FailureManifold,
    FailureType,
    PerturbationOperator,
    SimulationResult,
    TelemetryOutcome,
    TrainingArtifact,
)
from .organizational_failures import OrganizationalFailureGenerator
from .safety_enforcer import SafetyEnforcer
from .semantic_failures import SemanticFailureGenerator
from .test_modes import TestModeExecutor
from .training_output import TrainingOutputGenerator

__all__ = [
    # Models
    'FailureCase',
    'FailureType',
    'FailureManifold',
    'BaseScenario',
    'PerturbationOperator',
    'TrainingArtifact',
    'ConfidenceProfile',
    'SimulationResult',
    'TelemetryOutcome',

    # Generators
    'SemanticFailureGenerator',
    'ControlPlaneFailureGenerator',
    'InterfaceFailureGenerator',
    'OrganizationalFailureGenerator',

    # Pipeline
    'FailureInjectionPipeline',
    'TrainingOutputGenerator',
    'TestModeExecutor',
    'SafetyEnforcer'
]
# Re-export the MFGC learning system's SyntheticFailureGenerator
try:
    from src.learning_system import SyntheticFailureGenerator
except ImportError:
    SyntheticFailureGenerator = None
