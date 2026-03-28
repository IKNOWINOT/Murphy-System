"""
Gate Synthesis Engine - Control Policy Generator
Dynamically generates gates to prevent Murphy paths before they occur
"""

from .failure_mode_enumerator import FailureModeEnumerator
from .gate_generator import GateGenerator
from .gate_lifecycle_manager import GateLifecycleManager
from .models import (
    BlastRadius,
    ExposureSignal,
    FailureMode,
    Gate,
    GateCategory,
    GateState,
    GateType,
    RetirementCondition,
    RiskPath,
    RiskVector,
)
from .murphy_estimator import MurphyProbabilityEstimator

__all__ = [
    'Gate',
    'GateType',
    'GateCategory',
    'GateState',
    'RiskVector',
    'RiskPath',
    'FailureMode',
    'ExposureSignal',
    'BlastRadius',
    'RetirementCondition',
    'FailureModeEnumerator',
    'MurphyProbabilityEstimator',
    'GateGenerator',
    'GateLifecycleManager',
    'GateSynthesisEngine'
]
# Alias: tests import GateSynthesisEngine as the public API
GateSynthesisEngine = GateGenerator
