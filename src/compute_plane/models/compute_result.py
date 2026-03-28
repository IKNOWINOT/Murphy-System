"""
Compute Result Model

Defines the output contract for computation results.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Tuple

logger = logging.getLogger(__name__)


class ComputeStatus(str, Enum):
    """Status of computation"""
    SUCCESS = "SUCCESS"
    FAIL = "FAIL"
    TIMEOUT = "TIMEOUT"
    UNSUPPORTED = "UNSUPPORTED"
    PENDING = "PENDING"


@dataclass
class ComputeResult:
    """
    Result of deterministic computation.

    Attributes:
        request_id: ID of original request
        status: Computation status
        result: Computed result (if successful)
        derivation_steps: Step-by-step derivation (for symbolic)
        numeric_bounds: Lower and upper bounds for numeric result
        confidence_score: Confidence in result (0.0 to 1.0)
        stability_estimate: How stable is result to input perturbations
        sensitivity_to_assumptions: Sensitivity to each assumption
        error_message: Error message (if failed)
        execution_time: Time taken to compute (seconds)
        timestamp: When result was computed
        metadata: Additional metadata
    """

    request_id: str
    status: ComputeStatus
    result: Any = None
    derivation_steps: List[str] = field(default_factory=list)
    numeric_bounds: Tuple[float, float] = (float('-inf'), float('inf'))
    confidence_score: float = 0.0
    stability_estimate: float = 0.0
    sensitivity_to_assumptions: Dict[str, float] = field(default_factory=dict)
    error_message: str = ""
    execution_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate result parameters"""
        if not isinstance(self.status, ComputeStatus):
            self.status = ComputeStatus(self.status)

        if self.confidence_score < 0.0 or self.confidence_score > 1.0:
            raise ValueError("Confidence score must be between 0.0 and 1.0")

        if self.stability_estimate < 0.0 or self.stability_estimate > 1.0:
            raise ValueError("Stability estimate must be between 0.0 and 1.0")

    def is_successful(self) -> bool:
        """Check if computation was successful"""
        return self.status == ComputeStatus.SUCCESS

    def is_deterministic(self) -> bool:
        """Check if result is highly deterministic"""
        return self.stability_estimate > 0.8 and self.confidence_score > 0.8

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'request_id': self.request_id,
            'status': self.status.value,
            'result': str(self.result) if self.result is not None else None,
            'derivation_steps': self.derivation_steps,
            'numeric_bounds': list(self.numeric_bounds),
            'confidence_score': self.confidence_score,
            'stability_estimate': self.stability_estimate,
            'sensitivity_to_assumptions': self.sensitivity_to_assumptions,
            'error_message': self.error_message,
            'execution_time': self.execution_time,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ComputeResult':
        """Create from dictionary"""
        data = data.copy()
        if 'status' in data and isinstance(data['status'], str):
            data['status'] = ComputeStatus(data['status'])
        if 'timestamp' in data and isinstance(data['timestamp'], str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        if 'numeric_bounds' in data and isinstance(data['numeric_bounds'], list):
            data['numeric_bounds'] = tuple(data['numeric_bounds'])
        return cls(**data)
