"""
Grant & Incentive Data Models — All Pydantic schemas for the grant system.

Covers:
  • Grant program definitions
  • GrantSession — tenant-isolated workspaces
  • SessionCredential — access control per session
  • SavedFormData — browser-like auto-fill scoped to tenant
  • GrantApplication — individual application within a session
  • ApplicationField — per-field status tracking
  • HitlTask / HitlTaskQueue — human-in-the-loop task model
  • Prerequisite — SAM.gov / UEI / CAGE / Grants.gov prerequisite chain

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class GrantCategory(str, Enum):
    FEDERAL_TAX_CREDIT = "federal_tax_credit"
    FEDERAL_GRANT = "federal_grant"
    SBA_FINANCING = "sba_financing"
    USDA_PROGRAM = "usda_program"
    STATE_INCENTIVE = "state_incentive"
    UTILITY_PROGRAM = "utility_program"
    PACE_FINANCING = "pace_financing"
    GREEN_BANK = "green_bank"
    ESPC = "espc"
    RD_TAX_CREDIT = "rd_tax_credit"


class GrantTrack(str, Enum):
    TRACK_A = "track_a"   # Murphy/Inoni internal
    TRACK_B = "track_b"   # Customer-facing
    BOTH = "both"


class ApplicationStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    NEEDS_REVIEW = "needs_review"
    SUBMITTED = "submitted"
    AWARDED = "awarded"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class FieldStatus(str, Enum):
    AUTO_FILLED = "auto_filled"
    NEEDS_REVIEW = "needs_review"
    BLOCKED = "blocked"
    HUMAN_COMPLETED = "human_completed"
    EMPTY = "empty"


class HitlTaskState(str, Enum):
    PENDING = "pending"
    AUTO_COMPLETED = "auto_completed"
    NEEDS_REVIEW = "needs_review"
    BLOCKED_HUMAN_REQUIRED = "blocked_human_required"
    COMPLETED = "completed"


class PrerequisiteStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    NEEDS_RENEWAL = "needs_renewal"


class GrantFlavor(str, Enum):
    RD = "rd"
    ENERGY = "energy"
    MANUFACTURING = "manufacturing"
    GENERAL = "general"


class SessionRole(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


# ---------------------------------------------------------------------------
# Grant Program Model
# ---------------------------------------------------------------------------

class GrantIRABonus(BaseModel):
    """IRA bonus multipliers available for federal tax credits."""
    prevailing_wage: bool = False
    energy_community: bool = False
    domestic_content: bool = False
    low_income: bool = False
    direct_pay_eligible: bool = False
    transferable: bool = False


class Grant(BaseModel):
    """A single grant, tax credit, or financing program."""
    id: str = Field(..., description="Unique slug identifier, e.g. 'sbir_phase1'")
    name: str
    category: GrantCategory
    track: GrantTrack = GrantTrack.BOTH
    short_description: str
    long_description: str
    agency_or_provider: str
    program_url: str
    application_url: Optional[str] = None

    # Value
    min_amount_usd: Optional[float] = None
    max_amount_usd: Optional[float] = None
    value_description: str = ""   # e.g. "Up to 30% of project cost"

    # Eligibility
    eligible_entity_types: List[str] = Field(
        default_factory=list,
        description="e.g. ['small_business','nonprofit','individual']",
    )
    eligible_project_types: List[str] = Field(
        default_factory=list,
        description="e.g. ['bas_bms','ems','scada','manufacturing']",
    )
    eligible_states: List[str] = Field(
        default_factory=list,
        description="Empty = all states eligible",
    )
    requires_existing_building: bool = False
    requires_commercial: bool = False
    requires_rd_activity: bool = False

    # Timeline
    is_recurring: bool = True
    typical_deadline: Optional[str] = None   # e.g. "Rolling" or "March 15"
    program_expiry_year: Optional[int] = None
    longevity_note: str = ""

    # Stacking
    stackable_with: List[str] = Field(
        default_factory=list,
        description="IDs of grants this can be combined with",
    )

    # IRA-specific
    ira_bonus: Optional[GrantIRABonus] = None

    # Meta
    tags: List[str] = Field(default_factory=list)
    last_updated: str = ""


# ---------------------------------------------------------------------------
# Session & Tenant Isolation Models
# ---------------------------------------------------------------------------

class GrantSession(BaseModel):
    """Isolated grant workspace per tenant account."""
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    account_id: str
    name: str
    description: str = ""
    track: GrantTrack = GrantTrack.TRACK_B
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SessionCredential(BaseModel):
    """Who has access to a specific grant session."""
    credential_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    user_id: str
    role: SessionRole = SessionRole.VIEWER
    granted_by: str
    granted_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True


class SavedFormData(BaseModel):
    """Browser-like auto-fill data, strictly scoped to a single session."""
    session_id: str
    field_key: str
    field_value: Any
    source: str = "user_input"   # user_input | auto_filled | imported
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    last_updated: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Application Models
# ---------------------------------------------------------------------------

class ApplicationField(BaseModel):
    """A single field within a grant application."""
    field_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    application_id: str
    field_name: str
    field_label: str
    value: Optional[Any] = None
    status: FieldStatus = FieldStatus.EMPTY
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source: str = ""
    notes: str = ""
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class GrantApplication(BaseModel):
    """An individual grant application within a session."""
    application_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    grant_id: str
    status: ApplicationStatus = ApplicationStatus.NOT_STARTED
    fields: List[ApplicationField] = Field(default_factory=list)
    notes: str = ""
    submitted_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    estimated_value_usd: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# HITL Task Queue Models
# ---------------------------------------------------------------------------

class HitlTask(BaseModel):
    """A single human-in-the-loop task in the grant preparation workflow."""
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    title: str
    description: str
    why_blocked: str = ""
    what_human_must_provide: str = ""
    external_link: str = ""
    state: HitlTaskState = HitlTaskState.PENDING
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Agent confidence in auto-filled data",
    )
    dependencies: List[str] = Field(
        default_factory=list,
        description="task_ids that must be COMPLETED before this task can progress",
    )
    auto_filled_data: Dict[str, Any] = Field(default_factory=dict)
    human_provided_data: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    order: int = 0


class HitlTaskQueue(BaseModel):
    """Ordered queue of HITL tasks for a session."""
    session_id: str
    tasks: List[HitlTask] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def get_blocked_tasks(self) -> List[HitlTask]:
        return [t for t in self.tasks if t.state == HitlTaskState.BLOCKED_HUMAN_REQUIRED]

    def get_pending_tasks(self) -> List[HitlTask]:
        return [t for t in self.tasks if t.state == HitlTaskState.PENDING]

    def get_completed_tasks(self) -> List[HitlTask]:
        return [t for t in self.tasks if t.state == HitlTaskState.COMPLETED]

    def progress_summary(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for state in HitlTaskState:
            counts[state.value] = sum(1 for t in self.tasks if t.state == state)
        return counts


# ---------------------------------------------------------------------------
# Prerequisite Models
# ---------------------------------------------------------------------------

class Prerequisite(BaseModel):
    """A single step in the federal grant prerequisite chain."""
    prereq_id: str
    name: str
    description: str
    why_needed: str
    external_link: str
    status: PrerequisiteStatus = PrerequisiteStatus.NOT_STARTED
    depends_on: List[str] = Field(
        default_factory=list,
        description="prereq_ids that must be COMPLETED first",
    )
    is_recurring: bool = False
    renewal_period_days: Optional[int] = None
    completed_at: Optional[datetime] = None
    notes: str = ""
    order: int = 0


# ---------------------------------------------------------------------------
# Murphy Profile Model
# ---------------------------------------------------------------------------

class GrantProfile(BaseModel):
    """A grant-optimized description of Murphy System for a specific flavor."""
    flavor: GrantFlavor
    name: str
    positioning: str
    innovation_narrative: str
    job_creation_narrative: str
    energy_impact_narrative: str
    relevant_modules: List[str] = Field(default_factory=list)
    relevant_grant_categories: List[GrantCategory] = Field(default_factory=list)
    target_grants: List[str] = Field(
        default_factory=list,
        description="Grant IDs best matched to this profile",
    )
    tech_highlights: List[str] = Field(default_factory=list)
    naics_codes: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Eligibility Request / Response
# ---------------------------------------------------------------------------

class EligibilityRequest(BaseModel):
    """Input for the eligibility matching engine."""
    project_type: str = Field(..., description="e.g. 'bas_bms', 'ems', 'scada', 'manufacturing'")
    entity_type: str = Field(..., description="e.g. 'small_business', 'nonprofit', 'individual'")
    state: str = Field(..., description="Two-letter US state code, e.g. 'OR'")
    project_cost_usd: Optional[float] = None
    zip_code: Optional[str] = None
    is_commercial: bool = True
    has_rd_activity: bool = False
    building_sqft: Optional[float] = None
    existing_building: bool = True
    tags: List[str] = Field(default_factory=list)


class EligibilityMatch(BaseModel):
    """A single matched grant with estimated value."""
    grant: Grant
    match_score: float = Field(ge=0.0, le=1.0)
    estimated_value_usd: Optional[float] = None
    match_reasons: List[str] = Field(default_factory=list)
    stacking_opportunities: List[str] = Field(default_factory=list)


class EligibilityResponse(BaseModel):
    """Ranked list of matched grants for an eligibility request."""
    request: EligibilityRequest
    matches: List[EligibilityMatch] = Field(default_factory=list)
    total_estimated_value_usd: float = 0.0
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)
