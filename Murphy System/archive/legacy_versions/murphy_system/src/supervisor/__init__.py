"""
Supervisor Feedback Loops & Assumption Correction

This module provides assumption tracking, supervisor feedback processing,
and automatic correction when assumptions are invalidated.

CRITICAL PRINCIPLES:
- Every plan/hypothesis must declare assumptions
- Telemetry + supervisor feedback can invalidate assumptions
- When assumptions break: confidence decays, authority decays, re-expansion triggered
- No component may "explain away" invalidation without new evidence
- Agents cannot validate their own assumptions

Components:
- schemas: Core data models (AssumptionArtifact, SupervisorFeedbackArtifact, etc.)
- assumptions: Assumption management and validation
- supervisor: Supervisor feedback processing
- correction: Automatic correction on invalidation
- anti_recursion: Self-validation prevention
"""

from .schemas import (
    AssumptionArtifact,
    SupervisorFeedbackArtifact,
    InvalidationSignal,
    CorrectionAction,
    AssumptionStatus,
    FeedbackType,
)

__all__ = [
    "AssumptionArtifact",
    "SupervisorFeedbackArtifact",
    "InvalidationSignal",
    "CorrectionAction",
    "AssumptionStatus",
    "FeedbackType",
]