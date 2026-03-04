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

from .state_variables import StateVariables, NormalizedState
from .recursion_energy import RecursionEnergyEstimator
from .stability_score import StabilityScoreCalculator
from .lyapunov_monitor import LyapunovMonitor
from .spawn_controller import SpawnRateController
from .gate_damping import GateDampingController
from .feedback_isolation import FeedbackIsolationRouter
from .control_signals import ControlSignalGenerator
from .telemetry import StabilityTelemetry
from .rsc_service import RecursiveStabilityController

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
