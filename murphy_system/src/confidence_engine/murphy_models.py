"""
Data Models for Murphy Validation

Defines uncertainty scores, gate results, and confidence reports.
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class Phase(str, Enum):
    """Execution phases"""
    EXPAND = "expand"
    TYPE = "type"
    ENUMERATE = "enumerate"
    CONSTRAIN = "constrain"
    COLLAPSE = "collapse"
    BIND = "bind"
    EXECUTE = "execute"


class GateAction(str, Enum):
    """Murphy Gate actions"""
    PROCEED_AUTOMATICALLY = "proceed_automatically"
    PROCEED_WITH_MONITORING = "proceed_with_monitoring"
    PROCEED_WITH_CAUTION = "proceed_with_caution"
    REQUEST_HUMAN_REVIEW = "request_human_review"
    REQUIRE_HUMAN_APPROVAL = "require_human_approval"
    BLOCK_EXECUTION = "block_execution"


class UncertaintyScores(BaseModel):
    """
    Murphy uncertainty scores

    All scores are in range [0, 1] where:
    - 0 = no uncertainty (perfect certainty)
    - 1 = maximum uncertainty (complete uncertainty)
    """

    UD: float = Field(
        ...,
        description="Data Uncertainty: quality and completeness of data",
        ge=0.0,
        le=1.0
    )

    UA: float = Field(
        ...,
        description="Authority Uncertainty: credibility of sources",
        ge=0.0,
        le=1.0
    )

    UI: float = Field(
        ...,
        description="Intent Uncertainty: clarity of goals and requirements",
        ge=0.0,
        le=1.0
    )

    UR: float = Field(
        ...,
        description="Risk Uncertainty: potential negative consequences",
        ge=0.0,
        le=1.0
    )

    UG: float = Field(
        ...,
        description="Disagreement Uncertainty: conflicting information",
        ge=0.0,
        le=1.0
    )

    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="When scores were computed"
    )

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary"""
        return {
            'UD': self.UD,
            'UA': self.UA,
            'UI': self.UI,
            'UR': self.UR,
            'UG': self.UG
        }

    model_config = ConfigDict(json_schema_extra={
        "examples": [{
            "UD": 0.2,
            "UA": 0.15,
            "UI": 0.1,
            "UR": 0.25,
            "UG": 0.05
        }]
    })


class GateResult(BaseModel):
    """Result of Murphy Gate evaluation"""

    allowed: bool = Field(
        ...,
        description="Whether execution is allowed to proceed"
    )

    confidence: float = Field(
        ...,
        description="Confidence score that triggered this decision",
        ge=0.0,
        le=1.0
    )

    threshold: float = Field(
        ...,
        description="Threshold used for decision",
        ge=0.0,
        le=1.0
    )

    margin: float = Field(
        ...,
        description="Margin between confidence and threshold (can be negative)"
    )

    action: GateAction = Field(
        ...,
        description="Recommended action"
    )

    rationale: str = Field(
        ...,
        description="Human-readable explanation of decision"
    )

    phase: Optional[Phase] = Field(
        None,
        description="Phase this decision applies to"
    )

    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="When decision was made"
    )

    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional decision metadata"
    )

    model_config = ConfigDict(json_schema_extra={
        "examples": [{
            "allowed": True,
            "confidence": 0.82,
            "threshold": 0.7,
            "margin": 0.12,
            "action": "proceed_with_monitoring",
            "rationale": "Confidence 0.82 exceeds threshold 0.70 in execute phase. Proceeding with monitoring.",
            "phase": "execute"
        }]
    })


class ConfidenceReport(BaseModel):
    """Complete confidence assessment report"""

    uncertainty_scores: UncertaintyScores = Field(
        ...,
        description="Individual uncertainty component scores"
    )

    confidence: float = Field(
        ...,
        description="Aggregate confidence score",
        ge=0.0,
        le=1.0
    )

    confidence_v1: Optional[float] = Field(
        None,
        description="Confidence from existing G/D/H formula (for comparison)",
        ge=0.0,
        le=1.0
    )

    gate_result: Optional[GateResult] = Field(
        None,
        description="Murphy Gate decision (if evaluated)"
    )

    factors: Dict[str, Any] = Field(
        default_factory=dict,
        description="Detailed factors contributing to scores"
    )

    recommendations: List[str] = Field(
        default_factory=list,
        description="Recommendations for improving confidence"
    )

    warnings: List[str] = Field(
        default_factory=list,
        description="Warnings about potential issues"
    )

    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="When report was generated"
    )

    model_config = ConfigDict(json_schema_extra={
        "examples": [{
            "uncertainty_scores": {
                "UD": 0.2,
                "UA": 0.15,
                "UI": 0.1,
                "UR": 0.25,
                "UG": 0.05
            },
            "confidence": 0.82,
            "confidence_v1": 0.85,
            "gate_result": {
                "allowed": True,
                "confidence": 0.82,
                "threshold": 0.7,
                "margin": 0.12,
                "action": "proceed_with_monitoring",
                "rationale": "Confidence exceeds threshold"
            },
            "factors": {
                "data_quality": "high",
                "source_credibility": "verified",
                "goal_clarity": "clear"
            },
            "recommendations": [
                "Consider additional data validation",
                "Review risk mitigation strategies"
            ],
            "warnings": []
        }]
    })
