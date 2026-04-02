# Copyright 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Package: global_feedback
Subsystem: Global Feedback System
Purpose: Website-wide feedback collection, remediation planning, and GitHub
         dispatch for automated patching.
Status: Production
Design Labels: GFB-001 (models), GFB-002 (dispatcher), GFB-003 (remediation)

Provides:
    - GlobalFeedbackSubmission: Pydantic model for user-submitted feedback
    - RemediationPlan: Structured fix plan derived from guiding principles
    - GlobalFeedbackDispatcher: Orchestrates collection → validation →
      categorisation → remediation → GitHub dispatch
    - RemediationEngine: Analyses feedback signals and produces actionable
      remediation plans using the seven guiding questions
"""
from __future__ import annotations

from .models import (
    FeedbackSeverity,
    FeedbackSource,
    GlobalFeedbackStatus,
    GlobalFeedbackSubmission,
    GitHubPatchPayload,
    RemediationPlan,
    RemediationStep,
)
from .remediation_engine import RemediationEngine
from .dispatcher import GlobalFeedbackDispatcher

__all__ = [
    "FeedbackSeverity",
    "FeedbackSource",
    "GlobalFeedbackStatus",
    "GlobalFeedbackSubmission",
    "GitHubPatchPayload",
    "RemediationPlan",
    "RemediationStep",
    "RemediationEngine",
    "GlobalFeedbackDispatcher",
]
