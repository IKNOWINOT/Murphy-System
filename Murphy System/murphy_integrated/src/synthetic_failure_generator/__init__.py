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

from .models import (
    FailureCase,
    FailureType,
    FailureManifold,
    BaseScenario,
    PerturbationOperator,
    TrainingArtifact,
    ConfidenceProfile,
    SimulationResult,
    TelemetryOutcome
)

from .semantic_failures import SemanticFailureGenerator
from .control_failures import ControlPlaneFailureGenerator
from .interface_failures import InterfaceFailureGenerator
from .organizational_failures import OrganizationalFailureGenerator
from .injection_pipeline import FailureInjectionPipeline
from .training_output import TrainingOutputGenerator
from .test_modes import TestModeExecutor
from .safety_enforcer import SafetyEnforcer
from .synthetic_failure_generator import SyntheticFailureGenerator

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
    'SafetyEnforcer',
    'SyntheticFailureGenerator'
]
