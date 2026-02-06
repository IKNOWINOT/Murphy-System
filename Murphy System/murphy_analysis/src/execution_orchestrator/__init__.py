"""
Execution Orchestrator - Safe Actuation Plane
==============================================

The final actuation layer that executes sealed packets with mechanical safety enforcement.

Key Responsibilities:
- Pre-execution validation (packet verification, interface health)
- Stepwise execution engine (REST/RPC, math, filesystem, actuators)
- Telemetry streaming (real-time event emission)
- Runtime risk monitoring (continuous risk calculation)
- Rollback enforcement (automatic rollback on threshold breach)
- Completion certification (execution lock release)

Design Principles:
1. Execute only sealed packets (no generation allowed)
2. Validate before every step
3. Stream telemetry in real-time
4. Monitor risk continuously
5. Rollback automatically on threshold breach
6. Certify completion cryptographically
"""

from .models import (
    ExecutionState,
    StepResult,
    TelemetryEvent,
    TelemetryStream,
    SafetyState,
    RuntimeRisk,
    StopCondition,
    InterfaceHealth,
    InterfaceStatus,
    CompletionCertificate
)

from .validator import PreExecutionValidator
from .executor import StepwiseExecutor
from .telemetry import TelemetryStreamer
from .risk_monitor import RuntimeRiskMonitor
from .rollback import RollbackEnforcer
from .completion import CompletionCertifier
from .orchestrator import ExecutionOrchestrator

__all__ = [
    # Models
    'ExecutionState',
    'StepResult',
    'TelemetryEvent',
    'TelemetryStream',
    'SafetyState',
    'RuntimeRisk',
    'StopCondition',
    'InterfaceHealth',
    'InterfaceStatus',
    'CompletionCertificate',
    
    # Components
    'PreExecutionValidator',
    'StepwiseExecutor',
    'TelemetryStreamer',
    'RuntimeRiskMonitor',
    'RollbackEnforcer',
    'CompletionCertifier',
    'ExecutionOrchestrator'
]
