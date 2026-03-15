"""
Freelancer Validator — Data Models

Defines task, response, criteria, and budget structures for the
freelancer-based HITL validation system.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    """Return a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


# ── Enums ────────────────────────────────────────────────────────────────


class PlatformType(str, Enum):
    """Supported freelance platforms."""
    FIVERR = "fiverr"
    UPWORK = "upwork"
    FREELANCER = "freelancer"
    GENERIC = "generic"


class TaskStatus(str, Enum):
    """Lifecycle status of a freelancer validation task."""
    DRAFT = "draft"
    POSTED = "posted"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class ResponseVerdict(str, Enum):
    """Validator's verdict on the item under review."""
    PASS = "pass"
    FAIL = "fail"
    NEEDS_REVISION = "needs_revision"
    INCONCLUSIVE = "inconclusive"


# ── Criteria ─────────────────────────────────────────────────────────────


class CriterionItem(BaseModel):
    """A single criterion the validator must evaluate."""
    criterion_id: str = Field(
        default_factory=lambda: f"crit_{uuid4().hex[:8]}",
        description="Unique criterion identifier",
    )
    name: str = Field(..., description="Short label (e.g. 'Accuracy')")
    description: str = Field(..., description="What the validator should check")
    scoring_type: str = Field(
        default="boolean",
        description="boolean | scale_1_5 | scale_1_10 | text",
    )
    required: bool = Field(default=True, description="Must be answered")
    weight: float = Field(default=1.0, ge=0.0, description="Relative importance")


class ValidationCriteria(BaseModel):
    """Full criteria set attached to a freelancer task."""
    criteria_id: str = Field(
        default_factory=lambda: f"vc_{uuid4().hex[:8]}",
        description="Unique criteria-set identifier",
    )
    title: str = Field(..., description="Human-readable title for the criteria set")
    description: str = Field(default="", description="Overview for validators")
    items: List[CriterionItem] = Field(
        default_factory=list,
        description="Individual criterion items",
    )
    pass_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Weighted score that constitutes a pass",
    )
    created_at: datetime = Field(default_factory=_utcnow)


# ── Budget ───────────────────────────────────────────────────────────────


class BudgetConfig(BaseModel):
    """Budget configuration for an organization's HITL spend."""
    org_id: str = Field(..., description="Organization identifier")
    monthly_limit_cents: int = Field(
        default=50_000,
        ge=0,
        description="Monthly spend cap in cents (default $500)",
    )
    per_task_limit_cents: int = Field(
        default=5_000,
        ge=0,
        description="Maximum per-task spend in cents (default $50)",
    )
    currency: str = Field(default="USD")
    alert_threshold_pct: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Alert when this % of monthly budget is consumed",
    )


class BudgetLedger(BaseModel):
    """Tracks actual spend against a BudgetConfig."""
    org_id: str
    period: str = Field(
        default_factory=lambda: _utcnow().strftime("%Y-%m"),
        description="Budget period (YYYY-MM)",
    )
    total_spent_cents: int = Field(default=0, ge=0)
    task_count: int = Field(default=0, ge=0)
    transactions: List[Dict[str, Any]] = Field(default_factory=list)

    def remaining_cents(self, config: BudgetConfig) -> int:
        """How many cents remain for the current period."""
        return max(0, config.monthly_limit_cents - self.total_spent_cents)

    def can_spend(self, amount_cents: int, config: BudgetConfig) -> bool:
        """Return True if *amount_cents* fits within budget."""
        return (
            amount_cents <= config.per_task_limit_cents
            and amount_cents <= self.remaining_cents(config)
        )

    def record_spend(self, task_id: str, amount_cents: int) -> None:
        """Record a spend event."""
        self.total_spent_cents += amount_cents
        self.task_count += 1
        self.transactions.append({
            "task_id": task_id,
            "amount_cents": amount_cents,
            "timestamp": _utcnow().isoformat(),
        })


# ── Task ─────────────────────────────────────────────────────────────────


class FreelancerTask(BaseModel):
    """A validation task to be posted on a freelance platform."""
    task_id: str = Field(
        default_factory=lambda: f"ftask_{uuid4().hex[:8]}",
        description="Unique task identifier",
    )
    hitl_request_id: str = Field(
        ..., description="ID of the originating HITL InterventionRequest",
    )
    org_id: str = Field(..., description="Organization paying for this task")
    platform: PlatformType = Field(default=PlatformType.FIVERR)

    title: str = Field(..., description="Task title shown to validators")
    instructions: str = Field(..., description="Detailed instructions")
    payload: Dict[str, Any] = Field(
        default_factory=dict,
        description="Artifact/data the validator must evaluate",
    )
    criteria: ValidationCriteria = Field(
        ..., description="Structured criteria the validator must follow",
    )

    budget_cents: int = Field(
        default=1000,
        ge=0,
        description="Payment for this task in cents",
    )
    deadline_hours: int = Field(default=24, ge=1, description="Hours to complete")

    required_credentials: List["CredentialRequirement"] = Field(
        default_factory=list,
        description="Credentials the assigned validator must hold",
    )

    status: TaskStatus = Field(default=TaskStatus.DRAFT)
    platform_task_id: Optional[str] = Field(
        None, description="ID assigned by the external platform",
    )
    assigned_to: Optional[str] = Field(
        None, description="Freelancer username/ID",
    )

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ── Response ─────────────────────────────────────────────────────────────


class CriterionScore(BaseModel):
    """A validator's score for one criterion item."""
    criterion_id: str
    value: Any = Field(
        ..., description="Boolean, int, or text depending on scoring_type",
    )
    notes: Optional[str] = None


class FreelancerResponse(BaseModel):
    """Structured response returned by a freelancer validator."""
    response_id: str = Field(
        default_factory=lambda: f"fresp_{uuid4().hex[:8]}",
        description="Unique response identifier",
    )
    task_id: str = Field(..., description="Task this responds to")
    hitl_request_id: str = Field(
        ..., description="Originating HITL request",
    )
    validator_id: str = Field(
        ..., description="Freelancer username/ID who completed the task",
    )
    platform: PlatformType

    verdict: ResponseVerdict = Field(
        ..., description="Overall verdict",
    )
    criterion_scores: List[CriterionScore] = Field(
        default_factory=list,
        description="Per-criterion evaluation",
    )
    overall_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Aggregate weighted score (0–1)",
    )
    feedback: str = Field(
        default="",
        description="Free-text feedback from the validator",
    )
    evidence: Dict[str, Any] = Field(
        default_factory=dict,
        description="Supporting evidence (URLs, screenshots, etc.)",
    )

    submitted_at: datetime = Field(default_factory=_utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ── Credentials & Certification ──────────────────────────────────────────


class CertificationType(str, Enum):
    """Categories of professional credentials."""
    PROFESSIONAL_LICENSE = "professional_license"
    INDUSTRY_CERTIFICATION = "industry_certification"
    ACADEMIC_DEGREE = "academic_degree"
    GOVERNMENT_CLEARANCE = "government_clearance"
    TRADE_CERTIFICATION = "trade_certification"
    LANGUAGE_PROFICIENCY = "language_proficiency"
    PLATFORM_VERIFIED = "platform_verified"


class CredentialStatus(str, Enum):
    """Outcome of a credential verification check."""
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    EXPIRED = "expired"
    REVOKED = "revoked"
    COMPLAINTS_FOUND = "complaints_found"
    NOT_FOUND = "not_found"
    CHECK_FAILED = "check_failed"


class Credential(BaseModel):
    """A credential presented by a freelancer."""
    credential_id: str = Field(
        default_factory=lambda: f"cred_{uuid4().hex[:8]}",
    )
    credential_type: CertificationType
    name: str = Field(..., description="Credential name (e.g. 'CPA', 'AWS Solutions Architect')")
    issuing_authority: str = Field(..., description="Body that issued the credential")
    license_number: Optional[str] = Field(None, description="License/certificate number")
    country: str = Field(default="US", description="ISO-3166 country code")
    region: Optional[str] = Field(None, description="State/province if applicable")
    issued_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CredentialRequirement(BaseModel):
    """Credentials required for a specific task type."""
    requirement_id: str = Field(
        default_factory=lambda: f"creq_{uuid4().hex[:8]}",
    )
    credential_type: CertificationType
    name: str = Field(..., description="Required credential name")
    description: str = Field(default="", description="Why this credential is needed")
    issuing_authorities: List[str] = Field(
        default_factory=list,
        description="Acceptable issuing bodies (empty = any)",
    )
    accepted_countries: List[str] = Field(
        default_factory=list,
        description="ISO-3166 codes where credential is accepted (empty = worldwide)",
    )
    must_be_current: bool = Field(default=True, description="Credential must not be expired")
    verify_complaints: bool = Field(
        default=True,
        description="Check public complaint databases (BBB, license boards, etc.)",
    )
    min_experience_years: Optional[int] = Field(
        None, description="Minimum years of experience in the credential domain",
    )


class ComplaintRecord(BaseModel):
    """A complaint found during public-record verification."""
    source: str = Field(..., description="Database where complaint was found")
    source_url: Optional[str] = None
    summary: str = Field(default="")
    severity: str = Field(default="unknown", description="low | medium | high | critical")
    date_filed: Optional[str] = None
    status: str = Field(default="open", description="open | resolved | dismissed")


class CredentialVerificationResult(BaseModel):
    """Result of verifying a single credential."""
    credential_id: str
    credential_name: str
    status: CredentialStatus
    sources_checked: List[str] = Field(
        default_factory=list,
        description="Public databases queried",
    )
    complaints: List[ComplaintRecord] = Field(default_factory=list)
    verification_notes: str = Field(default="")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    verified_at: datetime = Field(default_factory=_utcnow)


class ValidatorCredentialProfile(BaseModel):
    """Full credential profile for a freelancer/validator."""
    validator_id: str
    credentials: List[Credential] = Field(default_factory=list)
    verification_results: List[CredentialVerificationResult] = Field(
        default_factory=list,
    )
    overall_status: CredentialStatus = Field(default=CredentialStatus.UNVERIFIED)
    last_verified: Optional[datetime] = None
