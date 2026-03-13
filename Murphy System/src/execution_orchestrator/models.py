"""
Execution Orchestrator - Core Data Models
==========================================

Data structures for execution state, telemetry, safety monitoring, and completion.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ExecutionStatus(Enum):
    """Execution status enumeration"""
    PENDING = "pending"
    VALIDATING = "validating"
    RUNNING = "running"
    PAUSED = "paused"
    ROLLING_BACK = "rolling_back"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


class StepType(Enum):
    """Execution step type enumeration"""
    REST_CALL = "rest_call"
    RPC_CALL = "rpc_call"
    MATH_COMPUTATION = "math_computation"
    FILESYSTEM_OP = "filesystem_op"
    ACTUATOR_COMMAND = "actuator_command"
    VERIFICATION = "verification"
    CHECKPOINT = "checkpoint"


class TelemetryEventType(Enum):
    """Telemetry event type enumeration"""
    EXECUTION_START = "execution_start"
    STEP_START = "step_start"
    STEP_COMPLETE = "step_complete"
    STEP_FAILED = "step_failed"
    RISK_THRESHOLD_BREACH = "risk_threshold_breach"
    CONFIDENCE_DROP = "confidence_drop"
    INTERFACE_FAILURE = "interface_failure"
    ROLLBACK_START = "rollback_start"
    ROLLBACK_COMPLETE = "rollback_complete"
    EXECUTION_PAUSED = "execution_paused"
    EXECUTION_RESUMED = "execution_resumed"
    EXECUTION_COMPLETE = "execution_complete"
    EXECUTION_FAILED = "execution_failed"


class StopReason(Enum):
    """Reason for execution stop"""
    RISK_THRESHOLD = "risk_threshold"
    CONFIDENCE_DROP = "confidence_drop"
    INTERFACE_FAILURE = "interface_failure"
    VERIFICATION_FAILURE = "verification_failure"
    ROLLBACK_FAILURE = "rollback_failure"
    USER_ABORT = "user_abort"
    TIMEOUT = "timeout"


@dataclass
class ExecutionState:
    """
    Current state of packet execution

    Tracks:
    - Packet being executed
    - Current step index
    - Execution status
    - Start/end times
    - Results collected
    """
    packet_id: str
    packet_signature: str
    status: ExecutionStatus
    current_step: int
    total_steps: int
    start_time: datetime
    end_time: Optional[datetime] = None
    results: List['StepResult'] = field(default_factory=list)
    error: Optional[str] = None
    stop_reason: Optional[StopReason] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'packet_id': self.packet_id,
            'packet_signature': self.packet_signature,
            'status': self.status.value,
            'current_step': self.current_step,
            'total_steps': self.total_steps,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'results': [r.to_dict() for r in self.results],
            'error': self.error,
            'stop_reason': self.stop_reason.value if self.stop_reason else None
        }


@dataclass
class StepResult:
    """
    Result of executing a single step

    Contains:
    - Step identification
    - Execution outcome
    - Output data
    - Timing information
    - Risk metrics
    """
    step_id: str
    step_type: StepType
    success: bool
    output: Any
    start_time: datetime
    end_time: datetime
    duration_ms: float
    risk_delta: float
    confidence_delta: float
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'step_id': self.step_id,
            'step_type': self.step_type.value,
            'success': self.success,
            'output': self.output,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat(),
            'duration_ms': self.duration_ms,
            'risk_delta': self.risk_delta,
            'confidence_delta': self.confidence_delta,
            'error': self.error
        }


@dataclass
class TelemetryEvent:
    """
    Single telemetry event emitted during execution

    Captures:
    - Event type and timestamp
    - Associated data
    - Risk and confidence metrics
    """
    event_type: TelemetryEventType
    timestamp: datetime
    packet_id: str
    step_id: Optional[str]
    data: Dict[str, Any]
    risk_score: float
    confidence_score: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            'event_type': self.event_type.value,
            'timestamp': self.timestamp.isoformat(),
            'packet_id': self.packet_id,
            'step_id': self.step_id,
            'data': self.data,
            'risk_score': self.risk_score,
            'confidence_score': self.confidence_score
        }


@dataclass
class TelemetryStream:
    """
    Stream of telemetry events for an execution

    Provides:
    - Event history
    - Real-time streaming
    - Aggregated metrics
    """
    packet_id: str
    events: List[TelemetryEvent] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)

    def add_event(self, event: TelemetryEvent):
        """Add event to stream"""
        self.events.append(event)

    def get_events_by_type(self, event_type: TelemetryEventType) -> List[TelemetryEvent]:
        """Get all events of a specific type"""
        return [e for e in self.events if e.event_type == event_type]

    def get_latest_risk(self) -> float:
        """Get latest risk score"""
        if not self.events:
            return 0.0
        return self.events[-1].risk_score

    def get_latest_confidence(self) -> float:
        """Get latest confidence score"""
        if not self.events:
            return 0.0
        return self.events[-1].confidence_score

    def to_dict(self) -> Dict[str, Any]:
        return {
            'packet_id': self.packet_id,
            'events': [e.to_dict() for e in self.events],
            'start_time': self.start_time.isoformat(),
            'event_count': len(self.events)
        }


@dataclass
class SafetyState:
    """
    Current safety state during execution

    Monitors:
    - Risk levels
    - Confidence levels
    - Stop conditions
    - Safety thresholds
    """
    current_risk: float
    risk_threshold: float
    current_confidence: float
    confidence_threshold: float
    stop_conditions: List['StopCondition'] = field(default_factory=list)
    is_safe: bool = True

    def check_safety(self) -> bool:
        """Check if execution is still safe"""
        self.is_safe = (
            self.current_risk <= self.risk_threshold and
            self.current_confidence >= self.confidence_threshold and
            len(self.stop_conditions) == 0
        )
        return self.is_safe

    def to_dict(self) -> Dict[str, Any]:
        return {
            'current_risk': self.current_risk,
            'risk_threshold': self.risk_threshold,
            'current_confidence': self.current_confidence,
            'confidence_threshold': self.confidence_threshold,
            'stop_conditions': [sc.to_dict() for sc in self.stop_conditions],
            'is_safe': self.is_safe
        }


@dataclass
class RuntimeRisk:
    """
    Runtime risk calculation during execution

    Computes:
    - Base risk from packet
    - Accumulated risk from steps
    - Risk deltas per step
    - Risk projections
    """
    base_risk: float
    accumulated_risk: float
    risk_deltas: List[float] = field(default_factory=list)
    projected_risk: float = 0.0

    def add_step_risk(self, risk_delta: float):
        """Add risk from a completed step"""
        self.risk_deltas.append(risk_delta)
        self.accumulated_risk += risk_delta
        self._update_projection()

    def _update_projection(self):
        """Update projected final risk"""
        if len(self.risk_deltas) > 0:
            avg_delta = sum(self.risk_deltas) / len(self.risk_deltas)
            self.projected_risk = self.accumulated_risk + avg_delta
        else:
            self.projected_risk = self.base_risk

    def get_total_risk(self) -> float:
        """Get total current risk"""
        return self.base_risk + self.accumulated_risk

    def to_dict(self) -> Dict[str, Any]:
        return {
            'base_risk': self.base_risk,
            'accumulated_risk': self.accumulated_risk,
            'risk_deltas': self.risk_deltas,
            'projected_risk': self.projected_risk,
            'total_risk': self.get_total_risk()
        }


@dataclass
class StopCondition:
    """
    Condition that requires execution to stop

    Specifies:
    - Reason for stop
    - Severity level
    - Required action
    """
    reason: StopReason
    severity: str  # 'warning', 'error', 'critical'
    message: str
    timestamp: datetime
    requires_rollback: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            'reason': self.reason.value,
            'severity': self.severity,
            'message': self.message,
            'timestamp': self.timestamp.isoformat(),
            'requires_rollback': self.requires_rollback
        }


@dataclass
class InterfaceHealth:
    """
    Health status of an external interface

    Tracks:
    - Interface availability
    - Response times
    - Error rates
    - Last check time
    """
    interface_id: str
    is_available: bool
    response_time_ms: float
    error_rate: float
    last_check: datetime
    error_message: Optional[str] = None

    def is_healthy(self) -> bool:
        """Check if interface is healthy"""
        return (
            self.is_available and
            self.response_time_ms < 5000 and  # 5 second timeout
            self.error_rate < 0.1  # Less than 10% error rate
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'interface_id': self.interface_id,
            'is_available': self.is_available,
            'response_time_ms': self.response_time_ms,
            'error_rate': self.error_rate,
            'last_check': self.last_check.isoformat(),
            'error_message': self.error_message,
            'is_healthy': self.is_healthy()
        }


@dataclass
class InterfaceStatus:
    """
    Overall status of all interfaces

    Aggregates:
    - Health of all interfaces
    - Overall availability
    - Critical failures
    """
    interfaces: Dict[str, InterfaceHealth] = field(default_factory=dict)

    def add_interface(self, health: InterfaceHealth):
        """Add interface health status"""
        self.interfaces[health.interface_id] = health

    def get_unhealthy_interfaces(self) -> List[str]:
        """Get list of unhealthy interface IDs"""
        return [
            iid for iid, health in self.interfaces.items()
            if not health.is_healthy()
        ]

    def all_healthy(self) -> bool:
        """Check if all interfaces are healthy"""
        return len(self.get_unhealthy_interfaces()) == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'interfaces': {
                iid: health.to_dict()
                for iid, health in self.interfaces.items()
            },
            'unhealthy_interfaces': self.get_unhealthy_interfaces(),
            'all_healthy': self.all_healthy()
        }


@dataclass
class CompletionCertificate:
    """
    Certificate issued upon successful execution completion

    Contains:
    - Execution summary
    - Cryptographic signature
    - Artifact updates
    - Verification proofs
    """
    packet_id: str
    execution_id: str
    status: ExecutionStatus
    start_time: datetime
    end_time: datetime
    total_steps: int
    successful_steps: int
    failed_steps: int
    final_risk: float
    final_confidence: float
    artifacts_created: List[str]
    artifacts_modified: List[str]
    signature: str
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'packet_id': self.packet_id,
            'execution_id': self.execution_id,
            'status': self.status.value,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat(),
            'total_steps': self.total_steps,
            'successful_steps': self.successful_steps,
            'failed_steps': self.failed_steps,
            'final_risk': self.final_risk,
            'final_confidence': self.final_confidence,
            'artifacts_created': self.artifacts_created,
            'artifacts_modified': self.artifacts_modified,
            'signature': self.signature,
            'timestamp': self.timestamp.isoformat()
        }
