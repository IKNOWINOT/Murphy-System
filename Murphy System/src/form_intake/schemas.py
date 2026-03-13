"""
Form Schema Definitions for Murphy System

This module defines all form schemas using JSON Schema format.
Each form type has validation rules, field types, and constraints.
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

logger = logging.getLogger(__name__)


class FormType(str, Enum):
    """Enumeration of form types"""
    PLAN_UPLOAD = "plan_upload"
    PLAN_GENERATION = "plan_generation"
    TASK_EXECUTION = "task_execution"
    VALIDATION = "validation"
    CORRECTION = "correction"


class ExpansionLevel(str, Enum):
    """Plan expansion detail level"""
    MINIMAL = "minimal"
    MODERATE = "moderate"
    COMPREHENSIVE = "comprehensive"


class CheckpointType(str, Enum):
    """Human-in-the-loop checkpoint types"""
    BEFORE_EXECUTION = "before_execution"
    AFTER_EACH_PHASE = "after_each_phase"
    ON_HIGH_RISK = "on_high_risk"
    ON_LOW_CONFIDENCE = "on_low_confidence"
    FINAL_REVIEW = "final_review"


class DomainType(str, Enum):
    """Domain categories for plan generation"""
    SOFTWARE_DEVELOPMENT = "software_development"
    BUSINESS_STRATEGY = "business_strategy"
    MARKETING_CAMPAIGN = "marketing_campaign"
    RESEARCH_PROJECT = "research_project"
    COMPLIANCE_AUDIT = "compliance_audit"
    SYSTEM_INTEGRATION = "system_integration"
    CUSTOM = "custom"


class RiskTolerance(str, Enum):
    """Risk tolerance levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ExecutionMode(str, Enum):
    """Task execution modes"""
    AUTOMATIC = "automatic"
    SUPERVISED = "supervised"
    MANUAL = "manual"


class ValidationResult(str, Enum):
    """Validation outcomes"""
    APPROVED = "approved"
    APPROVED_WITH_CHANGES = "approved_with_changes"
    REJECTED = "rejected"


class CorrectionType(str, Enum):
    """Types of corrections"""
    FACTUAL_ERROR = "factual_error"
    LOGIC_ERROR = "logic_error"
    FORMATTING_ISSUE = "formatting_issue"
    INCOMPLETE = "incomplete"
    WRONG_APPROACH = "wrong_approach"
    MISSING_CONTEXT = "missing_context"
    OTHER = "other"


class Severity(str, Enum):
    """Error severity levels"""
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    CRITICAL = "critical"


# ============================================================================
# FORM 1: PLAN UPLOAD FORM
# ============================================================================

class PlanUploadForm(BaseModel):
    """
    Form for uploading existing plans for expansion and validation

    User uploads a plan document, system expands it with additional detail,
    validates assumptions, and creates executable task breakdown.
    """

    form_type: FormType = Field(
        default=FormType.PLAN_UPLOAD,
        description="Form type identifier"
    )

    plan_document: str = Field(
        ...,
        description="Path to uploaded plan document (PDF, DOCX, TXT, MD)",
        min_length=1
    )

    plan_context: str = Field(
        ...,
        description="What is this plan for? Provide business context.",
        min_length=10,
        max_length=5000
    )

    expansion_level: ExpansionLevel = Field(
        default=ExpansionLevel.MODERATE,
        description="How much detail should Murphy add?"
    )

    constraints: List[str] = Field(
        default_factory=list,
        description="Any constraints or requirements (budget, timeline, resources, etc.)"
    )

    validation_criteria: List[str] = Field(
        ...,
        description="How will you know the plan is executed correctly?",
        min_length=1
    )

    human_checkpoints: List[CheckpointType] = Field(
        default_factory=lambda: [CheckpointType.BEFORE_EXECUTION, CheckpointType.FINAL_REVIEW],
        description="When should humans review progress?"
    )

    submitted_at: datetime = Field(
        default_factory=datetime.now,
        description="Form submission timestamp"
    )

    submitted_by: Optional[str] = Field(
        None,
        description="User ID who submitted the form"
    )

    @field_validator('plan_document')
    @classmethod
    def validate_document_format(cls, v):
        """Validate document format"""
        allowed_extensions = ['.pdf', '.docx', '.txt', '.md']
        if not any(v.lower().endswith(ext) for ext in allowed_extensions):
            raise ValueError(f"Document must be one of: {', '.join(allowed_extensions)}")
        return v

    @field_validator('validation_criteria')
    @classmethod
    def validate_criteria_not_empty(cls, v):
        """Ensure validation criteria are not empty strings"""
        if any(not criterion.strip() for criterion in v):
            raise ValueError("Validation criteria cannot be empty")
        return v

    model_config = ConfigDict(json_schema_extra={
        "examples": [{
            "form_type": "plan_upload",
            "plan_document": "plans/q1_marketing_strategy.pdf",
            "plan_context": "Q1 2025 marketing strategy for product launch. Need to expand with specific tactics, timelines, and resource allocation.",
            "expansion_level": "comprehensive",
            "constraints": [
                "Budget: $50,000",
                "Timeline: 90 days",
                "Team size: 5 people"
            ],
            "validation_criteria": [
                "All tactics have assigned owners",
                "Budget allocation adds up to $50,000",
                "Timeline fits within 90 days",
                "Success metrics defined for each tactic"
            ],
            "human_checkpoints": ["before_execution", "after_each_phase", "final_review"]
        }]
    })


# ============================================================================
# FORM 2: PLAN GENERATION FORM
# ============================================================================

class PlanGenerationForm(BaseModel):
    """
    Form for generating new plans from goals

    User describes a goal, system generates complete plan with tasks,
    dependencies, risks, and validation criteria.
    """

    form_type: FormType = Field(
        default=FormType.PLAN_GENERATION,
        description="Form type identifier"
    )

    goal: str = Field(
        ...,
        description="What do you want to accomplish?",
        min_length=50,
        max_length=10000
    )

    domain: DomainType = Field(
        ...,
        description="What domain does this goal belong to?"
    )

    timeline: str = Field(
        ...,
        description="When does this need to be done? (e.g., '30 days', '3 months', '2025-06-30')",
        min_length=1
    )

    budget: Optional[float] = Field(
        None,
        description="Budget in USD (optional)",
        ge=0
    )

    team_size: Optional[int] = Field(
        None,
        description="How many people are available?",
        ge=1
    )

    success_criteria: List[str] = Field(
        ...,
        description="How will you measure success?",
        min_length=1
    )

    known_constraints: List[str] = Field(
        default_factory=list,
        description="Any known limitations or requirements?"
    )

    risk_tolerance: RiskTolerance = Field(
        default=RiskTolerance.MEDIUM,
        description="How much risk can you accept?"
    )

    submitted_at: datetime = Field(
        default_factory=datetime.now,
        description="Form submission timestamp"
    )

    submitted_by: Optional[str] = Field(
        None,
        description="User ID who submitted the form"
    )

    @field_validator('goal')
    @classmethod
    def validate_goal_substance(cls, v):
        """Ensure goal has substance"""
        if len(v.split()) < 10:
            raise ValueError("Goal must be at least 10 words to provide sufficient context")
        return v

    @field_validator('success_criteria')
    @classmethod
    def validate_criteria_measurable(cls, v):
        """Ensure success criteria are not empty"""
        if any(not criterion.strip() for criterion in v):
            raise ValueError("Success criteria cannot be empty")
        return v

    model_config = ConfigDict(json_schema_extra={
        "examples": [{
            "form_type": "plan_generation",
            "goal": "Launch a new SaaS product for project management targeting small businesses. The product should have core features like task management, team collaboration, and reporting. We need to go from concept to beta launch with 100 users.",
            "domain": "software_development",
            "timeline": "6 months",
            "budget": 150000.0,
            "team_size": 8,
            "success_criteria": [
                "Beta product launched with core features",
                "100 active beta users acquired",
                "User satisfaction score > 4.0/5.0",
                "Less than 5 critical bugs reported"
            ],
            "known_constraints": [
                "Must comply with GDPR and SOC 2",
                "Must integrate with Slack and Microsoft Teams",
                "Must support mobile devices"
            ],
            "risk_tolerance": "medium"
        }]
    })


# ============================================================================
# FORM 3: TASK EXECUTION FORM
# ============================================================================

class TaskExecutionForm(BaseModel):
    """
    Form for executing specific tasks from a plan

    Executes a task through Murphy's phase-based execution with
    validation and human-in-the-loop checkpoints.
    """

    form_type: FormType = Field(
        default=FormType.TASK_EXECUTION,
        description="Form type identifier"
    )

    plan_id: str = Field(
        ...,
        description="ID of the plan this task belongs to",
        min_length=1
    )

    task_id: str = Field(
        ...,
        description="ID of the task to execute",
        min_length=1
    )

    execution_mode: ExecutionMode = Field(
        default=ExecutionMode.SUPERVISED,
        description="How should Murphy execute this task?"
    )

    confidence_threshold: float = Field(
        default=0.7,
        description="Minimum confidence to proceed automatically",
        ge=0.0,
        le=1.0
    )

    additional_context: Optional[str] = Field(
        None,
        description="Any additional information for this task?",
        max_length=5000
    )

    submitted_at: datetime = Field(
        default_factory=datetime.now,
        description="Form submission timestamp"
    )

    submitted_by: Optional[str] = Field(
        None,
        description="User ID who submitted the form"
    )

    model_config = ConfigDict(json_schema_extra={
        "examples": [{
            "form_type": "task_execution",
            "plan_id": "plan_2025_q1_marketing_001",
            "task_id": "task_social_media_campaign_setup",
            "execution_mode": "supervised",
            "confidence_threshold": 0.75,
            "additional_context": "Focus on LinkedIn and Twitter. Budget allocated is $5,000 for ads."
        }]
    })


# ============================================================================
# FORM 4: VALIDATION FORM
# ============================================================================

class ValidationForm(BaseModel):
    """
    Form for human validation of Murphy's outputs

    Human reviews Murphy's output and provides quality score,
    feedback, and any corrections needed.
    """

    form_type: FormType = Field(
        default=FormType.VALIDATION,
        description="Form type identifier"
    )

    task_id: str = Field(
        ...,
        description="ID of the task being validated",
        min_length=1
    )

    output_id: str = Field(
        ...,
        description="ID of the output to validate",
        min_length=1
    )

    validation_result: ValidationResult = Field(
        ...,
        description="Validation outcome"
    )

    quality_score: int = Field(
        ...,
        description="Rate the quality (0-10)",
        ge=0,
        le=10
    )

    feedback: str = Field(
        ...,
        description="What was good? What needs improvement?",
        min_length=10,
        max_length=5000
    )

    corrections: Optional[Dict[str, Any]] = Field(
        None,
        description="Specific corrections made (if any)"
    )

    submitted_at: datetime = Field(
        default_factory=datetime.now,
        description="Form submission timestamp"
    )

    submitted_by: Optional[str] = Field(
        None,
        description="User ID who submitted the form"
    )

    @field_validator('feedback')
    @classmethod
    def validate_feedback_substance(cls, v):
        """Ensure feedback has substance"""
        if len(v.split()) < 5:
            raise ValueError("Feedback must be at least 5 words")
        return v

    model_config = ConfigDict(json_schema_extra={
        "examples": [{
            "form_type": "validation",
            "task_id": "task_social_media_campaign_setup",
            "output_id": "output_campaign_plan_v1",
            "validation_result": "approved_with_changes",
            "quality_score": 8,
            "feedback": "Overall excellent work. The campaign structure is solid and the targeting is well thought out. However, the budget allocation needs adjustment - too much on Twitter, not enough on LinkedIn given our B2B focus. Also, the timeline for content creation is too aggressive.",
            "corrections": {
                "budget_allocation": {
                    "original": {"linkedin": 2000, "twitter": 3000},
                    "corrected": {"linkedin": 3500, "twitter": 1500}
                },
                "timeline": {
                    "content_creation_days": {"original": 7, "corrected": 14}
                }
            }
        }]
    })


# ============================================================================
# FORM 5: CORRECTION FORM
# ============================================================================

class CorrectionForm(BaseModel):
    """
    Form for capturing human corrections for training

    When human corrects Murphy's output, this form captures the
    before/after for shadow agent training.
    """

    form_type: FormType = Field(
        default=FormType.CORRECTION,
        description="Form type identifier"
    )

    task_id: str = Field(
        ...,
        description="ID of the task being corrected",
        min_length=1
    )

    output_id: str = Field(
        ...,
        description="ID of the output being corrected",
        min_length=1
    )

    correction_type: List[CorrectionType] = Field(
        ...,
        description="Types of corrections being made",
        min_length=1
    )

    original_output: Dict[str, Any] = Field(
        ...,
        description="Murphy's original output (auto-filled, read-only)"
    )

    corrected_output: Dict[str, Any] = Field(
        ...,
        description="Your corrected version"
    )

    correction_rationale: str = Field(
        ...,
        description="Why did you make these changes?",
        min_length=20,
        max_length=5000
    )

    severity: Severity = Field(
        ...,
        description="How serious was the error?"
    )

    submitted_at: datetime = Field(
        default_factory=datetime.now,
        description="Form submission timestamp"
    )

    submitted_by: Optional[str] = Field(
        None,
        description="User ID who submitted the form"
    )

    @field_validator('correction_rationale')
    @classmethod
    def validate_rationale_substance(cls, v):
        """Ensure rationale has substance"""
        if len(v.split()) < 10:
            raise ValueError("Correction rationale must be at least 10 words to provide learning context")
        return v

    model_config = ConfigDict(json_schema_extra={
        "examples": [{
            "form_type": "correction",
            "task_id": "task_social_media_campaign_setup",
            "output_id": "output_campaign_plan_v1",
            "correction_type": ["factual_error", "wrong_approach"],
            "original_output": {
                "budget_allocation": {"linkedin": 2000, "twitter": 3000},
                "target_audience": "small business owners",
                "content_strategy": "promotional posts"
            },
            "corrected_output": {
                "budget_allocation": {"linkedin": 3500, "twitter": 1500},
                "target_audience": "B2B decision makers in small businesses",
                "content_strategy": "thought leadership and case studies"
            },
            "correction_rationale": "The original allocation favored Twitter too heavily for a B2B campaign. LinkedIn is more effective for reaching business decision makers. The target audience definition was too broad - we need to focus on decision makers specifically. The content strategy should emphasize thought leadership rather than direct promotion to build trust in the B2B space.",
            "severity": "moderate"
        }]
    })


# ============================================================================
# FORM REGISTRY
# ============================================================================

FORM_REGISTRY: Dict[FormType, type] = {
    FormType.PLAN_UPLOAD: PlanUploadForm,
    FormType.PLAN_GENERATION: PlanGenerationForm,
    FormType.TASK_EXECUTION: TaskExecutionForm,
    FormType.VALIDATION: ValidationForm,
    FormType.CORRECTION: CorrectionForm
}


def get_form_class(form_type: FormType) -> type:
    """Get form class by type"""
    return FORM_REGISTRY[form_type]


def validate_form(form_type: FormType, form_data: Dict[str, Any]) -> BaseModel:
    """
    Validate form data against schema

    Args:
        form_type: Type of form to validate
        form_data: Form data to validate

    Returns:
        Validated form instance

    Raises:
        ValidationError: If form data is invalid
    """
    form_class = get_form_class(form_type)
    return form_class(**form_data)
