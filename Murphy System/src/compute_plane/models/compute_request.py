"""
Compute Request Model

Defines the input contract for computation requests.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Literal

logger = logging.getLogger(__name__)


@dataclass
class ComputeRequest:
    """
    Request for deterministic computation.

    Attributes:
        request_id: Unique identifier for this request
        expression: Mathematical expression to evaluate
        language: Computation language (wolfram, sympy, lp, sat)
        assumptions: Assumptions about variables (e.g., {"x": "real", "x > 0"})
        precision: Numeric precision (decimal places)
        timeout: Maximum execution time in seconds
        timestamp: When request was created
        metadata: Additional metadata for tracking
    """

    SUPPORTED_LANGUAGES = ("wolfram", "sympy", "lp", "sat")

    expression: str
    language: Literal["wolfram", "sympy", "lp", "sat"]
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    assumptions: Dict[str, Any] = field(default_factory=dict)
    precision: int = 10
    timeout: int = 30
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate request parameters"""
        if not self.expression:
            raise ValueError("Expression cannot be empty")

        if self.language not in self.SUPPORTED_LANGUAGES:
            raise ValueError(f"Unsupported language: {self.language}")

        if self.precision < 1 or self.precision > 50:
            raise ValueError("Precision must be between 1 and 50")

        if self.timeout < 1 or self.timeout > 300:
            raise ValueError("Timeout must be between 1 and 300 seconds")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'request_id': self.request_id,
            'expression': self.expression,
            'language': self.language,
            'assumptions': self.assumptions,
            'precision': self.precision,
            'timeout': self.timeout,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ComputeRequest':
        """Create from dictionary"""
        data = data.copy()
        if 'timestamp' in data and isinstance(data['timestamp'], str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)
