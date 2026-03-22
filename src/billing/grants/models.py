"""Pydantic v2 models for grants and financing module."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ProgramType(str, Enum):
    federal_tax_credit = "federal_tax_credit"
    federal_grant = "federal_grant"
    sba_loan = "sba_loan"
    usda_program = "usda_program"
    state_incentive = "state_incentive"
    utility_program = "utility_program"
    pace_financing = "pace_financing"
    green_bank = "green_bank"
    espc = "espc"
    rd_tax_credit = "rd_tax_credit"


class GrantTrack(str, Enum):
    track_a_murphy = "track_a_murphy"
    track_b_customer = "track_b_customer"


class ApplicationStatus(str, Enum):
    draft = "draft"
    in_review = "in_review"
    submitted = "submitted"
    accepted = "accepted"
    rejected = "rejected"


class TaskType(str, Enum):
    auto_filled = "auto_filled"
    needs_review = "needs_review"
    blocked_human_required = "blocked_human_required"
    waiting_on_external = "waiting_on_external"


class PrereqStatus(str, Enum):
    not_started = "not_started"
    in_progress = "in_progress"
    waiting_on_external = "waiting_on_external"
    completed = "completed"


class Grant(BaseModel):
    """A financing or grant program available to Murphy System or its customers."""

    id: str
    name: str
    program_type: ProgramType
    agency: str
    description: str
    min_amount: float
    max_amount: float
    eligible_entity_types: List[str] = Field(default_factory=list)
    eligible_verticals: List[str] = Field(default_factory=list)
    eligible_states: List[str] = Field(default_factory=list)
    application_url: str = ""
    deadline_pattern: str = ""
    longevity_years: int = 5
    requirements: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


class GrantSession(BaseModel):
    """Isolated session for a tenant working through grant applications."""

    session_id: str
    tenant_id: str
    track: GrantTrack
    created_at: datetime
    updated_at: datetime
    profile_data: Dict[str, Any] = Field(default_factory=dict)
    completed_tasks: List[str] = Field(default_factory=list)
    pending_tasks: List[str] = Field(default_factory=list)


class Application(BaseModel):
    """A grant application under construction or submitted."""

    application_id: str
    grant_id: str
    session_id: str
    status: ApplicationStatus = ApplicationStatus.draft
    form_data: Dict[str, Any] = Field(default_factory=dict)
    confidence_score: float = 0.0
    hitl_notes: str = ""
    submitted_at: Optional[datetime] = None


class HitlTask(BaseModel):
    """A human-in-the-loop task required to advance a grant application."""

    task_id: str
    session_id: str
    task_type: TaskType
    title: str
    description: str
    target_url: str = ""
    form_fields: Dict[str, Any] = Field(default_factory=dict)
    depends_on: List[str] = Field(default_factory=list)
    status: str = "pending"
    priority: int = 50
    estimated_minutes: int = 30


class Prerequisite(BaseModel):
    """A registration or compliance prerequisite that unlocks grant eligibility."""

    prereq_id: str
    name: str
    description: str
    verification_url: str
    status: PrereqStatus = PrereqStatus.not_started
    blocks: List[str] = Field(default_factory=list)
    estimated_days: int = 1


class EligibilityResult(BaseModel):
    """Result of matching a grant against a company/project profile."""

    grant_id: str
    eligible: bool
    confidence: float
    reasons: List[str]
    estimated_value: float
    action_items: List[str]
