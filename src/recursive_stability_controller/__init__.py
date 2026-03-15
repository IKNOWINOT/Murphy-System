"""
Recursive Stability & Agentic Feedback Control
Control-Plane Grade Implementation

This module implements formal, provably stable control over:
- Recursive generation
- Agent spawning
- Gate synthesis
- Feedback evaluation

Guarantees:
- Recursion cannot self-amplify
- Hallucination cannot become a stable attractor
- Agents cannot validate themselves
- Control-plane stability is preserved under stress
"""

from .control_signals import ControlSignalGenerator
from .feedback_isolation import FeedbackIsolationRouter
from .gate_damping import GateDampingController
from .lyapunov_monitor import LyapunovMonitor
from .recursion_energy import RecursionEnergyEstimator
from .rsc_service import RecursiveStabilityController
from .spawn_controller import SpawnRateController
from .stability_score import StabilityScoreCalculator
from .state_variables import NormalizedState, StateVariables
from .telemetry import StabilityTelemetry

__all__ = [
    'StateVariables',
    'NormalizedState',
    'RecursionEnergyEstimator',
    'StabilityScoreCalculator',
    'LyapunovMonitor',
    'SpawnRateController',
    'GateDampingController',
    'FeedbackIsolationRouter',
    'ControlSignalGenerator',
    'StabilityTelemetry',
    'RecursiveStabilityController'
]

__version__ = '1.0.0'
