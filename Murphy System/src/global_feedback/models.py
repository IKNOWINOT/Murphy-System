# Copyright 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Module: global_feedback/models.py
Subsystem: Global Feedback System
Design Label: GFB-001
Purpose: Pydantic models for global feedback submissions, remediation plans,
         and GitHub patch dispatch payloads.
Status: Production
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class FeedbackSeverity(str, Enum):
    """Severity classification for incoming feedback."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class FeedbackSource(str, Enum):
    """Origin surface of the feedback."""
    WEBSITE_WIDGET = "website_widget"
    API_DIRECT = "api_direct"
    BOT_REPORT = "bot_report"
    INTERNAL_MONITOR = "internal_monitor"
    CLI = "cli"


class GlobalFeedbackStatus(str, Enum):
    """Lifecycle status of a global feedback ticket."""
    SUBMITTED = "submitted"
    VALIDATED = "validated"
    ANALYZING = "analyzing"
    REMEDIATION_PLANNED = "remediation_planned"
    DISPATCHED_TO_GITHUB = "dispatched_to_github"
    PATCH_IN_PROGRESS = "patch_in_progress"
    RESOLVED = "resolved"
    REJECTED = "rejected"
    DEFERRED = "deferred"


# ---------------------------------------------------------------------------
# Core submission model
# ---------------------------------------------------------------------------

class GlobalFeedbackSubmission(BaseModel):
    """
    A single piece of feedback submitted through the global feedback system.

    Design Label: GFB-001
    Covers: bugs, negative-respect signals, UX complaints, security concerns,
    and any condition the user perceives as wrong.
    """
    id: str = Field(default_factory=lambda: f"gfb-{uuid.uuid4().hex[:12]}")
    status: GlobalFeedbackStatus = GlobalFeedbackStatus.SUBMITTED

    # --- Who ---------------------------------------------------------------
    user_id: str = Field(..., min_length=1, max_length=256,
                         description="Submitter identifier (email, user-id, or anonymous token)")
    user_agent: Optional[str] = Field(None, max_length=512)
    tenant_id: Optional[str] = Field(None, max_length=128)

    # --- What --------------------------------------------------------------
    title: str = Field(..., min_length=5, max_length=256,
                       description="Short summary of the problem")
    description: str = Field(..., min_length=10, max_length=8192,
                             description="Detailed description of the issue")
    severity: FeedbackSeverity = FeedbackSeverity.MEDIUM
    source: FeedbackSource = FeedbackSource.WEBSITE_WIDGET

    # --- Where / When ------------------------------------------------------
    page_url: Optional[str] = Field(None, max_length=2048,
                                    description="URL where the issue occurred")
    component: Optional[str] = Field(None, max_length=256,
                                     description="UI component or module name")
    submitted_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc))

    # --- Reproduction context ----------------------------------------------
    steps_to_reproduce: Optional[str] = Field(None, max_length=4096)
    expected_behavior: Optional[str] = Field(None, max_length=2048)
    actual_behavior: Optional[str] = Field(None, max_length=2048)
    screenshot_refs: List[str] = Field(default_factory=list)
    console_errors: Optional[str] = Field(None, max_length=4096)

    # --- Classification tags -----------------------------------------------
    tags: List[str] = Field(default_factory=list)
    category: Optional[str] = None
    affected_modules: List[str] = Field(default_factory=list)

    # --- Lifecycle ---------------------------------------------------------
    remediation_plan_id: Optional[str] = None
    github_issue_url: Optional[str] = None
    resolved_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("title")
    @classmethod
    def _sanitise_title(cls, v: str) -> str:
        """Strip leading/trailing whitespace; reject empty after strip."""
        v = v.strip()
        if len(v) < 5:
            raise ValueError("Title must be at least 5 characters after trimming")
        return v

    @field_validator("description")
    @classmethod
    def _sanitise_description(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 10:
            raise ValueError("Description must be at least 10 characters after trimming")
        return v


# ---------------------------------------------------------------------------
# Remediation plan
# ---------------------------------------------------------------------------

class RemediationStep(BaseModel):
    """A single actionable step in a remediation plan."""
    step_number: int
    action: str
    rationale: str
    guiding_question: str  # Which of the 7 questions this step answers
    estimated_impact: str = "medium"


class RemediationPlan(BaseModel):
    """
    Structured fix plan generated from feedback analysis.

    Design Label: GFB-003
    Built using the seven guiding-principle questions.
    """
    id: str = Field(default_factory=lambda: f"rem-{uuid.uuid4().hex[:12]}")
    feedback_id: str
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc))

    # Analysis results
    root_cause: str
    affected_subsystem: str
    severity_assessment: FeedbackSeverity
    conditions_identified: List[str] = Field(default_factory=list)
    expected_vs_actual: Optional[str] = None

    # Remediation steps
    steps: List[RemediationStep] = Field(default_factory=list)
    hardening_applied: bool = False
    documentation_updated: bool = False
    recommission_required: bool = False

    # Guiding principle answers
    guiding_answers: Dict[str, str] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# GitHub dispatch payload
# ---------------------------------------------------------------------------

class GitHubPatchPayload(BaseModel):
    """
    Payload dispatched to GitHub Actions via repository_dispatch.

    Design Label: GFB-002
    Event type: ``feedback_patch_request``
    """
    feedback_id: str
    remediation_plan_id: str
    title: str
    description: str
    severity: FeedbackSeverity
    root_cause: str
    affected_subsystem: str
    steps: List[Dict[str, Any]]
    labels: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
