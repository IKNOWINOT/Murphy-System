"""
Data Models for Execution

Defines execution results, status, and phase results.
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class ExecutionStatus(str, Enum):
    """Execution status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    AWAITING_HUMAN = "awaiting_human"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PhaseResult(BaseModel):
    """Result of a single phase execution"""

    phase: str = Field(..., description="Phase name")
    status: ExecutionStatus = Field(..., description="Phase status")
    confidence: float = Field(..., description="Confidence score for this phase")
    gate_allowed: bool = Field(..., description="Whether Murphy Gate allowed this phase")
    output: Dict[str, Any] = Field(default_factory=dict, description="Phase output")
    duration_seconds: float = Field(..., description="Phase execution duration")
    timestamp: datetime = Field(default_factory=datetime.now, description="Phase completion time")

    model_config = ConfigDict(json_schema_extra={
        "examples": [{
            "phase": "expand",
            "status": "completed",
            "confidence": 0.85,
            "gate_allowed": True,
            "output": {"possibilities": ["option1", "option2", "option3"]},
            "duration_seconds": 2.5
        }]
    })


class ExecutionResult(BaseModel):
    """Complete execution result"""

    task_id: str = Field(..., description="Task ID")
    execution_id: str = Field(..., description="Unique execution ID")
    status: ExecutionStatus = Field(..., description="Overall execution status")
    phase_results: List[PhaseResult] = Field(
        default_factory=list,
        description="Results from each phase"
    )
    final_output: Optional[Dict[str, Any]] = Field(
        None,
        description="Final execution output"
    )
    final_confidence: Optional[float] = Field(
        None,
        description="Final confidence score"
    )
    human_interventions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Human interventions that occurred"
    )
    assumptions_tracked: List[str] = Field(
        default_factory=list,
        description="Assumptions tracked during execution"
    )
    assumptions_invalidated: List[str] = Field(
        default_factory=list,
        description="Assumptions that were invalidated"
    )
    audit_trail: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Complete audit trail"
    )
    error_message: Optional[str] = Field(
        None,
        description="Error message if execution failed"
    )
    started_at: datetime = Field(
        default_factory=datetime.now,
        description="Execution start time"
    )
    completed_at: Optional[datetime] = Field(
        None,
        description="Execution completion time"
    )
    total_duration_seconds: Optional[float] = Field(
        None,
        description="Total execution duration"
    )

    model_config = ConfigDict(json_schema_extra={
        "examples": [{
            "task_id": "task_001",
            "execution_id": "exec_20250202_120000",
            "status": "completed",
            "phase_results": [
                {
                    "phase": "expand",
                    "status": "completed",
                    "confidence": 0.85,
                    "gate_allowed": True,
                    "output": {},
                    "duration_seconds": 2.5
                }
            ],
            "final_output": {"result": "success"},
            "final_confidence": 0.85,
            "human_interventions": [],
            "assumptions_tracked": ["assumption1", "assumption2"],
            "assumptions_invalidated": [],
            "audit_trail": []
        }]
    })
