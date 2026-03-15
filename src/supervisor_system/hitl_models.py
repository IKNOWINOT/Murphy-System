"""
Data Models for Human-in-the-Loop

Defines intervention requests, responses, and types.
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class InterventionType(str, Enum):
    """Types of human interventions"""
    APPROVAL = "approval"
    REVIEW = "review"
    CORRECTION = "correction"
    VALIDATION = "validation"
    DECISION = "decision"
    CLARIFICATION = "clarification"


class InterventionUrgency(str, Enum):
    """Urgency levels for interventions"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class InterventionStatus(str, Enum):
    """Status of intervention requests"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class InterventionRequest(BaseModel):
    """Request for human intervention"""

    request_id: str = Field(..., description="Unique request ID")
    intervention_type: InterventionType = Field(..., description="Type of intervention needed")
    urgency: InterventionUrgency = Field(default=InterventionUrgency.MEDIUM, description="Urgency level")

    task_id: str = Field(..., description="Task requiring intervention")
    phase: Optional[str] = Field(None, description="Phase where intervention is needed")

    reason: str = Field(..., description="Why intervention is needed")
    context: Dict[str, Any] = Field(default_factory=dict, description="Context for intervention")

    blocking: bool = Field(default=True, description="Whether execution blocks until intervention")
    timeout_seconds: Optional[int] = Field(None, description="Timeout for intervention")

    required_role: Optional[str] = Field(None, description="Role required to respond")

    status: InterventionStatus = Field(default=InterventionStatus.PENDING, description="Request status")

    created_at: datetime = Field(default_factory=datetime.now, description="Request creation time")
    expires_at: Optional[datetime] = Field(None, description="Request expiration time")

    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    model_config = ConfigDict(json_schema_extra={
        "examples": [{
            "request_id": "req_001",
            "intervention_type": "approval",
            "urgency": "high",
            "task_id": "task_001",
            "phase": "execute",
            "reason": "Confidence below threshold, requires human approval",
            "context": {
                "confidence": 0.65,
                "threshold": 0.7,
                "risk_level": "medium"
            },
            "blocking": True,
            "required_role": "manager"
        }]
    })


class InterventionResponse(BaseModel):
    """Response to intervention request"""

    response_id: str = Field(..., description="Unique response ID")
    request_id: str = Field(..., description="Request being responded to")

    approved: bool = Field(..., description="Whether request was approved")
    decision: str = Field(..., description="Decision made (approve/reject/modify)")

    feedback: Optional[str] = Field(None, description="Human feedback")
    corrections: Optional[Dict[str, Any]] = Field(None, description="Corrections made")
    modifications: Optional[Dict[str, Any]] = Field(None, description="Modifications requested")

    responded_by: str = Field(..., description="User who responded")
    responded_at: datetime = Field(default_factory=datetime.now, description="Response time")

    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    model_config = ConfigDict(json_schema_extra={
        "examples": [{
            "response_id": "resp_001",
            "request_id": "req_001",
            "approved": True,
            "decision": "approve",
            "feedback": "Approved with recommendation to add monitoring",
            "responded_by": "user_123"
        }]
    })
