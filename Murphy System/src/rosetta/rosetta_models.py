"""
Pydantic models for the Rosetta State Management System.

Defines the full agent state schema used by Murphy System agents,
including identity, system health, goals, tasks, automation progress,
recalibration tracking, archival, improvement proposals, and workflow patterns.

Extended in this version with:
  - AgentType / EmployeeContract  — shadow vs automation agent; the agent's
    "employee contract" encoding its role, authority, and shadowed user (if any)
  - IndustryTerminology           — locked vocabulary for the customer's industry,
    preventing agents from reasoning outside their domain
  - StateFeedEntry / StateFeed    — live business metric stream (pipeline fill,
    conversion rate, capacity, revenue gap) that agents read before acting
  - BusinessPlanMath              — onboarding-derived revenue math: goal → unit
    price → required volume → cost adjustment → monthly pace → conversion gap →
    inverse prospect reach
  - HITLThroughputModel           — human-in-the-loop throughput model per task
    type: validators, tasks/day, day-of-week factors, holiday buffer, HITL toggle
  - MagnifySimplifyTask / TaskPipeline — task list built through the
    Magnify×3 → Simplify → Magnify×2 → domain filter → Solidify pipeline
  - RosettaDocument               — the full enriched per-agent document that
    combines all of the above; agents read this before every action
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

logger = logging.getLogger(__name__)


# ==================== Enums ====================

class GoalStatus(str, Enum):
    """Goal status (str subclass)."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    DEFERRED = "deferred"


class TaskStatus(str, Enum):
    """Task status (str subclass)."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class RecalibrationStatus(str, Enum):
    """Recalibration status (str subclass)."""
    IDLE = "idle"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# ==================== Sub-models ====================

class Identity(BaseModel):
    """Agent identity information."""
    agent_id: str
    name: str
    role: str = ""
    version: str = "1.0.0"
    organization: str = ""


class SystemState(BaseModel):
    """System health snapshot."""
    model_config = ConfigDict(use_enum_values=True)

    status: str = "idle"  # idle, active, paused, error
    uptime_seconds: float = 0.0
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    active_tasks: int = 0
    last_heartbeat: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))


class Goal(BaseModel):
    """An agent goal."""
    model_config = ConfigDict(use_enum_values=True)

    goal_id: str
    title: str
    description: str = ""
    status: GoalStatus = GoalStatus.PENDING
    priority: int = Field(default=3, ge=1, le=5)
    progress_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    dependencies: List[str] = Field(default_factory=list)


class Task(BaseModel):
    """An agent task linked to a goal."""
    model_config = ConfigDict(use_enum_values=True)

    task_id: str
    goal_id: str
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.QUEUED
    assigned_to: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None


class AgentState(BaseModel):
    """Aggregated agent operational state."""
    current_phase: str = "idle"
    active_goals: List[Goal] = Field(default_factory=list)
    task_queue: List[Task] = Field(default_factory=list)


class AutomationProgress(BaseModel):
    """Progress tracking for an automation category."""
    category: str
    total_items: int = 0
    completed_items: int = 0
    coverage_percent: float = 0.0
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Recalibration(BaseModel):
    """Recalibration cycle tracking."""
    model_config = ConfigDict(use_enum_values=True)

    status: RecalibrationStatus = RecalibrationStatus.IDLE
    last_run: Optional[datetime] = None
    next_scheduled: Optional[datetime] = None
    cycle_count: int = 0
    findings: List[str] = Field(default_factory=list)


class ArchiveEntry(BaseModel):
    """A single archived item."""
    entry_id: str
    archived_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reason: str = ""
    category: str = "manual"
    data: Dict[str, Any] = Field(default_factory=dict)


class ArchiveLog(BaseModel):
    """Collection of archived entries."""
    entries: List[ArchiveEntry] = Field(default_factory=list)
    total_archived: int = 0


class ImprovementProposal(BaseModel):
    """A proposed improvement for the system."""
    proposal_id: str
    title: str
    description: str = ""
    priority: int = Field(default=3, ge=1, le=5)
    status: str = "proposed"
    estimated_effort_hours: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    category: str = "general"


class WorkflowPattern(BaseModel):
    """A reusable workflow pattern."""
    pattern_id: str
    name: str
    steps: List[str] = Field(default_factory=list)
    success_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    avg_duration_seconds: float = 0.0
    usage_count: int = 0


class Metadata(BaseModel):
    """Document metadata."""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: str = "1.0.0"
    schema_version: str = "1.0"


# ==================== Main Model ====================

class RosettaAgentState(BaseModel):
    """
    Complete Rosetta agent state document.

    Combines identity, system health, operational state, automation tracking,
    recalibration, archival, improvement proposals, and workflow patterns.
    """
    model_config = ConfigDict(use_enum_values=True)

    identity: Identity
    system_state: SystemState = Field(default_factory=SystemState)
    agent_state: AgentState = Field(default_factory=AgentState)
    automation_progress: List[AutomationProgress] = Field(default_factory=list)
    recalibration: Recalibration = Field(default_factory=Recalibration)
    archive_log: ArchiveLog = Field(default_factory=ArchiveLog)
    improvement_proposals: List[ImprovementProposal] = Field(default_factory=list)
    workflow_patterns: List[WorkflowPattern] = Field(default_factory=list)
    metadata: Metadata = Field(default_factory=Metadata)


# ===========================================================================
# Extended Rosetta — RosettaDocument
#
# These models enrich the base RosettaAgentState with everything an agent
# needs to know BEFORE it takes any action:
#
#   1. AgentType / EmployeeContract  — "who am I, what kind of agent am I"
#   2. IndustryTerminology           — "what vocabulary do I operate in"
#   3. StateFeed                     — "what is the business's live state"
#   4. BusinessPlanMath              — "what are the numbers I'm optimising for"
#   5. HITLThroughputModel           — "how fast can humans validate my work"
#   6. TaskPipeline                  — "what tasks have been generated for me"
#   7. RosettaDocument               — combines all of the above
# ===========================================================================


# ---------------------------------------------------------------------------
# 1. AgentType and EmployeeContract
# ---------------------------------------------------------------------------

class AgentType(str, Enum):
    """
    Fundamental distinction between the two agent modes.

    SHADOW      A hybrid assistant that observes a specific user, learns to do
                work the way that user does it, and gradually proposes automations
                based on those learned patterns.  It has a 'shadowed_user_id'.

    AUTOMATION  A role-filling agent that executes a defined set of tasks
                autonomously.  No observation — it just does the role.
    """
    SHADOW = "shadow"
    AUTOMATION = "automation"


class ManagementLayer(str, Enum):
    """Where this role sits in the org hierarchy."""
    EXECUTIVE = "executive"       # Strategic goals, budget authority, cross-department
    MIDDLE_MANAGEMENT = "middle"  # Project management, job numbers, trench vs strategy
    INDIVIDUAL = "individual"     # Work orders, actual task execution


class EmployeeContract(BaseModel):
    """
    The agent's 'employee contract' — its role definition in the organisation.

    This is the first thing an agent reads before acting.  It tells the agent:
      - What kind of agent it is (shadow vs automation)
      - What its role is and what it is authorised to do
      - Which management layer it belongs to
      - Which user it shadows (shadow agents only)
      - What its work-order scope is (projects, job numbers, or open tasks)

    Shadow agents shadow a specific user and learn their work patterns.
    Automation agents just do a defined role.
    """
    model_config = ConfigDict(use_enum_values=True)

    agent_type: AgentType
    role_title: str
    role_description: str = ""
    management_layer: ManagementLayer = ManagementLayer.INDIVIDUAL
    department: str = ""
    location: str = ""           # physical or virtual location shared across all agents
    organisation_id: str = ""
    shadowed_user_id: Optional[str] = None   # shadow agents only
    shadowed_user_name: Optional[str] = None
    authorised_actions: List[str] = Field(default_factory=list)
    work_order_scope: str = "assigned"  # "assigned" | "project" | "job_number" | "open"
    reports_to: Optional[str] = None    # role title of direct manager
    direct_reports: List[str] = Field(default_factory=list)

    @field_validator("shadowed_user_id")
    @classmethod
    def shadow_requires_user(cls, v: Optional[str], info: Any) -> Optional[str]:
        """Shadow agents must have a shadowed_user_id."""
        # Validation runs before the full object is built so we use info.data
        agent_type = info.data.get("agent_type")
        if agent_type == AgentType.SHADOW and not v:
            raise ValueError("Shadow agents require a shadowed_user_id")
        return v


# ---------------------------------------------------------------------------
# 2. IndustryTerminology
# ---------------------------------------------------------------------------

class TermDefinition(BaseModel):
    """A single term in the agent's locked vocabulary."""
    term: str
    definition: str
    aliases: List[str] = Field(default_factory=list)
    category: str = "general"   # e.g. "metric", "process", "role", "product"


class IndustryTerminology(BaseModel):
    """
    The locked vocabulary for a specific customer's industry.

    Agents use this to:
      - Interpret incoming task descriptions correctly
      - Generate domain-appropriate output (a plumbing company's
        agents use plumbing terminology, not aerospace terminology)
      - Filter generated content against domain_keywords to reject
        off-domain output before it reaches the user

    Built from InferenceDomainGateEngine.infer_via_llm() output and
    locked into the RosettaDocument during onboarding.
    """
    industry: str
    business_type: str = ""
    location: str = ""
    domain_keywords: List[str] = Field(default_factory=list)
    terms: List[TermDefinition] = Field(default_factory=list)
    off_limits_topics: List[str] = Field(default_factory=list)

    def is_on_domain(self, text: str) -> bool:
        """Return True if *text* contains at least one domain keyword, or if no keywords are locked."""
        if not self.domain_keywords:
            return True  # no domain constraint registered — everything is on-domain
        text_lower = text.lower()
        return any(kw.lower() in text_lower for kw in self.domain_keywords)

    def find_term(self, term: str) -> Optional[TermDefinition]:
        term_lower = term.lower()
        for t in self.terms:
            if t.term.lower() == term_lower or term_lower in [a.lower() for a in t.aliases]:
                return t
        return None


# ---------------------------------------------------------------------------
# 3. StateFeed — live business metric stream
# ---------------------------------------------------------------------------

class MetricDirection(str, Enum):
    """Whether the metric is moving toward or away from its target."""
    ON_TRACK = "on_track"
    AHEAD = "ahead"
    BEHIND = "behind"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class StateFeedEntry(BaseModel):
    """
    A single timestamped observation in the business state feed.

    These are the numbers the agent reads before deciding what to do next.
    Examples:
      - pipeline_fill_rate: 0.42   (42 % of monthly quota in pipeline)
      - conversion_rate_actual: 0.2999
      - conversion_rate_goal: 0.9999
      - capacity_utilisation: 0.87
      - revenue_gap_dollars: 150000
      - lead_velocity_per_week: 12
      - open_work_orders: 7
      - overdue_invoices: 3
    """
    metric_name: str
    value: float
    unit: str = ""
    target: Optional[float] = None
    direction: MetricDirection = MetricDirection.UNKNOWN
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = "system"   # "crm" | "erp" | "sensor" | "llm_inference" | "manual"
    notes: str = ""

    @property
    def gap(self) -> Optional[float]:
        """Signed gap between value and target (positive = ahead, negative = behind)."""
        if self.target is None:
            return None
        return self.value - self.target

    @property
    def gap_percent(self) -> Optional[float]:
        if self.target is None or self.target == 0:
            return None
        # Rounded to 4 dp here because this is a display/summary property only.
        # All decision-making math uses exact float values from UnitEconomics.
        return round((self.value - self.target) / abs(self.target) * 100, 4)


class StateFeed(BaseModel):
    """
    The agent's live business state feed.

    Agents read this section of their Rosetta before every action.
    It is updated by sensors, CRM integrations, and LLM inference.
    The feed is an ordered list — most recent entries first.
    """
    entries: List[StateFeedEntry] = Field(default_factory=list)
    last_updated: Optional[datetime] = None
    update_source: str = "system"

    def get(self, metric_name: str) -> Optional[StateFeedEntry]:
        """Return the most recent entry for *metric_name*."""
        for entry in self.entries:
            if entry.metric_name == metric_name:
                return entry
        return None

    def latest_value(self, metric_name: str) -> Optional[float]:
        entry = self.get(metric_name)
        return entry.value if entry else None

    def push(self, entry: StateFeedEntry) -> None:
        """Prepend a new entry (most-recent-first order)."""
        self.entries.insert(0, entry)
        self.last_updated = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# 4. BusinessPlanMath
# ---------------------------------------------------------------------------

class UnitEconomics(BaseModel):
    """
    The math that connects a revenue goal to daily/monthly operational targets.

    All division uses exact float arithmetic — no rounding at any intermediate
    step.  The system never rounds a business ratio because rounding introduces
    systematic error in long-running forecasts.

    Example (SaaS at $5,000/seat, target $2M ARR):
      revenue_goal_dollars      = 2_000_000
      unit_price_dollars        = 5_000
      gross_units_needed        = 2_000_000 / 5_000 = 400.0
      annual_cost_dollars       = 600_000   (infra, salaries, etc.)
      adjusted_revenue_target   = 2_000_000 + 600_000 = 2_600_000
      adjusted_units_needed     = 2_600_000 / 5_000 = 520.0
      timeline_months           = 12
      units_per_month           = 520.0 / 12 = 43.333...

    Conversion math (Q2 start, goal 99.99 %, actual 29.99 %):
      conversion_rate_goal      = 0.9999
      conversion_rate_actual    = 0.2999
      inverse_ratio             = (0.9999 × 100) / 0.2999 = 333.411...
      → prospect_reach_needed   = units_per_month × inverse_ratio
    """
    revenue_goal_dollars: float
    unit_price_dollars: float
    annual_cost_dollars: float = 0.0
    timeline_months: float = 12.0
    conversion_rate_goal: float = Field(default=1.0, gt=0.0, le=1.0)
    conversion_rate_actual: float = Field(default=1.0, gt=0.0, le=1.0)

    @property
    def gross_units_needed(self) -> float:
        """Units needed to hit the revenue goal before costs."""
        return self.revenue_goal_dollars / self.unit_price_dollars

    @property
    def adjusted_revenue_target(self) -> float:
        """Revenue goal plus total costs."""
        return self.revenue_goal_dollars + self.annual_cost_dollars

    @property
    def adjusted_units_needed(self) -> float:
        """Units needed to cover revenue goal AND costs."""
        return self.adjusted_revenue_target / self.unit_price_dollars

    @property
    def units_per_month(self) -> float:
        """Exact monthly pace — never rounded."""
        return self.adjusted_units_needed / self.timeline_months

    @property
    def conversion_inverse_ratio(self) -> float:
        """
        Inverse ratio of actual-to-goal conversion rate.

        Formula: (goal × 100) / actual
        This answers: "how many prospects do we need to reach to achieve
        the same outcome at our current conversion rate?"

        If goal=99.99% and actual=29.99%:
          (0.9999 × 100) / 0.2999 = 333.411...
        """
        return (self.conversion_rate_goal * 100.0) / self.conversion_rate_actual

    @property
    def prospect_reach_needed_per_month(self) -> float:
        """
        Prospects to contact each month given the current conversion gap.

        = units_per_month × conversion_inverse_ratio
        """
        return self.units_per_month * self.conversion_inverse_ratio

    def as_recommendation(self) -> str:
        """
        Return a plain-English recommendation summarising the math.
        Used by the executive Rosetta agent to brief upper management.
        """
        return (
            f"To reach ${self.revenue_goal_dollars:,.2f} ARR at "
            f"${self.unit_price_dollars:,.2f}/unit over {self.timeline_months} months "
            f"(including ${self.annual_cost_dollars:,.2f} in costs), "
            f"you need {self.adjusted_units_needed:.4f} units total, "
            f"or {self.units_per_month:.4f} per month. "
            f"With a current conversion rate of {self.conversion_rate_actual * 100:.4f}% "
            f"(goal: {self.conversion_rate_goal * 100:.4f}%), "
            f"marketing must reach {self.prospect_reach_needed_per_month:.4f} "
            f"prospects per month."
        )


class BusinessPlanMath(BaseModel):
    """
    The full business plan mathematics section of a RosettaDocument.

    Combines unit economics with time-boxed milestones and current-quarter
    progress.  The executive-layer agent reads this to decide whether to
    trigger more marketing, adjust pricing, or revise the goal.
    """
    unit_economics: UnitEconomics
    current_quarter: int = Field(default=1, ge=1, le=4)
    quarters_elapsed: float = 0.0
    units_closed_to_date: float = 0.0
    pipeline_units: float = 0.0   # units currently in pipeline (not yet closed)

    @property
    def units_remaining(self) -> float:
        """Units still needed to hit the adjusted target."""
        return max(0.0, self.unit_economics.adjusted_units_needed - self.units_closed_to_date)

    @property
    def months_remaining(self) -> float:
        """Months left in the plan."""
        elapsed_months = self.quarters_elapsed * 3.0
        return max(0.0, self.unit_economics.timeline_months - elapsed_months)

    @property
    def required_pace_remaining(self) -> float:
        """Units per month needed over remaining months to hit target."""
        if self.months_remaining == 0:
            return 0.0
        return self.units_remaining / self.months_remaining

    @property
    def on_track(self) -> bool:
        """True if current pace equals or exceeds original plan pace."""
        return self.units_closed_to_date >= (
            self.unit_economics.units_per_month * self.quarters_elapsed * 3.0
        )

    def summary(self) -> Dict[str, Any]:
        ue = self.unit_economics
        return {
            "revenue_goal": ue.revenue_goal_dollars,
            "unit_price": ue.unit_price_dollars,
            "adjusted_revenue_target": ue.adjusted_revenue_target,
            "gross_units_needed": ue.gross_units_needed,
            "adjusted_units_needed": ue.adjusted_units_needed,
            "units_per_month_plan": ue.units_per_month,
            "units_closed_to_date": self.units_closed_to_date,
            "units_remaining": self.units_remaining,
            "months_remaining": self.months_remaining,
            "required_pace_remaining": self.required_pace_remaining,
            "on_track": self.on_track,
            "conversion_rate_actual": ue.conversion_rate_actual,
            "conversion_rate_goal": ue.conversion_rate_goal,
            "conversion_inverse_ratio": ue.conversion_inverse_ratio,
            "prospect_reach_needed_per_month": ue.prospect_reach_needed_per_month,
            "recommendation": ue.as_recommendation(),
        }


# ---------------------------------------------------------------------------
# 5. HITLThroughputModel
# ---------------------------------------------------------------------------

# Average working days per month (Mon–Fri, 4.33 weeks).
# Named constant so scheduling math is explicit throughout.
AVERAGE_WORKING_DAYS_PER_MONTH: float = 22.0


class DayOfWeekFactor(BaseModel):
    """Throughput multiplier for a specific day of the week (0=Monday … 6=Sunday)."""
    day: int = Field(ge=0, le=6)
    factor: float = Field(default=1.0, ge=0.0)  # ge=0 allows weekends (factor=0.0)
    label: str = ""


class HITLThroughputModel(BaseModel):
    """
    Human-in-the-loop throughput model for a single task type.

    Used to estimate how many HITL validations can be completed in a given
    period so that automation schedules stay realistic.

    Key concepts:
      - base_tasks_per_day: average completions when fully staffed, normal day
      - validator_count: number of people doing this type of review
      - day_of_week_factors: Monday and Friday are typically lower throughput
      - holiday_buffer_days: average days per month lost to holidays/time-off
      - avg_task_duration_minutes: average time for a human to complete one
        validation of this type
      - hitl_enabled: operator toggle — when False, automations in this category
        do not pause for human review

    LLM peer review note: for simple content checks, a higher-grade LLM can
    substitute for a human reviewer (at a lower confidence cost).  This is
    captured in llm_peer_review_eligible and llm_confidence_threshold.
    """
    task_type: str
    base_tasks_per_day: float = Field(gt=0.0)
    validator_count: int = Field(default=1, ge=1)
    avg_task_duration_minutes: float = Field(default=15.0, gt=0.0)
    day_of_week_factors: List[DayOfWeekFactor] = Field(default_factory=list)
    holiday_buffer_days_per_month: float = Field(default=2.0, ge=0.0)
    hitl_enabled: bool = True
    llm_peer_review_eligible: bool = False
    llm_confidence_threshold: float = Field(default=0.85, ge=0.0, le=1.0)

    @property
    def effective_working_days_per_month(self) -> float:
        """Working days per month after subtracting holiday buffer."""
        return AVERAGE_WORKING_DAYS_PER_MONTH - self.holiday_buffer_days_per_month

    @property
    def daily_capacity(self) -> float:
        """
        Maximum tasks per day across all validators.
        Applies no day-of-week factor — that's for scheduling.
        """
        return self.base_tasks_per_day * self.validator_count

    @property
    def monthly_capacity(self) -> float:
        """
        Realistic monthly capacity accounting for holidays and time off.
        Does not account for day-of-week variance (use weekly_schedule for that).
        """
        return self.daily_capacity * self.effective_working_days_per_month

    def day_capacity(self, weekday: int) -> float:
        """
        Tasks achievable on a specific weekday (0=Monday, 6=Sunday).
        Applies the matching DayOfWeekFactor if registered.
        """
        for dow in self.day_of_week_factors:
            if dow.day == weekday:
                return self.daily_capacity * dow.factor
        return self.daily_capacity

    def weeks_to_clear(self, backlog: float) -> float:
        """
        Estimate how many weeks it takes to clear *backlog* items.
        Uses average daily capacity × 5 working days per week.
        Returns 0.0 if HITL is disabled (automations don't need clearing).
        """
        if not self.hitl_enabled:
            return 0.0
        weekly = self.daily_capacity * 5.0
        return backlog / weekly if weekly > 0 else float("inf")


# ---------------------------------------------------------------------------
# 6. MagnifySimplifyTask and TaskPipeline
# ---------------------------------------------------------------------------

class TaskPipelineStage(str, Enum):
    """Which stage of the Magnify → Simplify → Solidify pipeline a task is in."""
    MAGNIFY_1 = "magnify_1"
    MAGNIFY_2 = "magnify_2"
    MAGNIFY_3 = "magnify_3"
    SIMPLIFY = "simplify"
    MAGNIFY_4 = "magnify_4"
    MAGNIFY_5 = "magnify_5"
    DOMAIN_FILTER = "domain_filter"
    SOLIDIFIED = "solidified"
    REJECTED = "rejected"     # failed domain filter


class MagnifySimplifyTask(BaseModel):
    """
    A task that has been generated by the Magnify×3 → Simplify → Magnify×2
    → domain filter → Solidify pipeline.

    The pipeline stages ensure tasks are:
      Magnify×3    — fully expanded into concrete, measurable sub-tasks
      Simplify     — filtered down to only what is relevant to this role
      Magnify×2    — re-expanded with implementation detail
      Domain filter— confirmed on-domain for this industry/role
      Solidify     — locked as executable work units the Librarian can act on

    Domain fitness:
      domain_fit_score 0.0–1.0 — how strongly the task matches the agent's
      IndustryTerminology domain_keywords.  Tasks below domain_fit_threshold
      are rejected at the DOMAIN_FILTER stage.

    Measurability:
      success_metric is always expressed as a measurable quantity so
      the system can track goal progress numerically.
    """
    task_id: str
    title: str
    description: str = ""
    stage: TaskPipelineStage = TaskPipelineStage.MAGNIFY_1
    assigned_role: str = ""        # role title this task is assigned to
    management_layer: ManagementLayer = ManagementLayer.INDIVIDUAL
    project_id: Optional[str] = None
    job_number: Optional[str] = None
    work_order_id: Optional[str] = None
    success_metric: str = ""       # e.g. "send 34 proposals this month"
    success_value: Optional[float] = None   # numeric target
    success_unit: str = ""         # e.g. "proposals", "dollars", "conversions"
    domain_fit_score: float = Field(default=1.0, ge=0.0, le=1.0)
    domain_fit_threshold: float = Field(default=0.3, ge=0.0, le=1.0)
    priority: int = Field(default=3, ge=1, le=5)
    estimated_hours: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    solidified_at: Optional[datetime] = None
    source_goal_id: Optional[str] = None

    @property
    def is_on_domain(self) -> bool:
        return self.domain_fit_score >= self.domain_fit_threshold

    @property
    def is_actionable(self) -> bool:
        return self.stage == TaskPipelineStage.SOLIDIFIED


class TaskPipeline(BaseModel):
    """
    The full task pipeline for an agent.

    Contains tasks at every stage of the Magnify → Simplify → Solidify
    process.  Only SOLIDIFIED tasks are visible to the Librarian for
    routing and execution.  Tasks at earlier stages are still being
    processed by the pipeline.

    The Librarian reads `actionable_tasks()` before deciding what to
    execute next.  The executive agent reads `pending_tasks_by_layer()`
    to understand the overall work backlog across management layers.
    """
    tasks: List[MagnifySimplifyTask] = Field(default_factory=list)
    domain_fit_threshold: float = Field(default=0.3, ge=0.0, le=1.0)

    def actionable_tasks(self) -> List[MagnifySimplifyTask]:
        """Solidified, on-domain tasks ready for Librarian routing."""
        return [t for t in self.tasks if t.is_actionable and t.is_on_domain]

    def pending_tasks_by_layer(self) -> Dict[str, List[MagnifySimplifyTask]]:
        """All tasks (not solidified) grouped by management layer."""
        result: Dict[str, List[MagnifySimplifyTask]] = {
            "executive": [],
            "middle": [],
            "individual": [],
        }
        for t in self.tasks:
            if not t.is_actionable:
                result[t.management_layer].append(t)
        return result

    def tasks_by_stage(self) -> Dict[str, int]:
        """Count of tasks at each pipeline stage."""
        counts: Dict[str, int] = {}
        for t in self.tasks:
            counts[t.stage] = counts.get(t.stage, 0) + 1
        return counts

    def add(self, task: MagnifySimplifyTask) -> None:
        self.tasks.append(task)

    def solidify(self, task_id: str) -> bool:
        """Mark a task as solidified. Returns True if found."""
        for t in self.tasks:
            if t.task_id == task_id:
                t.stage = TaskPipelineStage.SOLIDIFIED
                t.solidified_at = datetime.now(timezone.utc)
                return True
        return False

    def reject(self, task_id: str) -> bool:
        """Reject a task (failed domain filter). Returns True if found."""
        for t in self.tasks:
            if t.task_id == task_id:
                t.stage = TaskPipelineStage.REJECTED
                return True
        return False


# ---------------------------------------------------------------------------
# 7. RosettaDocument — the full enriched per-agent document
# ---------------------------------------------------------------------------

class RosettaDocument(BaseModel):
    """
    The complete enriched Rosetta document for a single agent.

    This is what every agent reads before taking any action.  It combines:
      - EmployeeContract  — who the agent is and what kind it is
      - IndustryTerminology — what vocabulary it operates in
      - StateFeed         — live business state metrics
      - BusinessPlanMath  — the numbers it is optimising toward
      - TaskPipeline      — the Magnify→Simplify→Solidify task queue
      - HITLThroughputModels — how fast humans can validate its work
      - base state        — identity, system health, goals, workflow patterns

    Shadow agents additionally carry:
      - the shadowed user's identity (via EmployeeContract.shadowed_user_id)
      - the full observation history (via shadow_observations)

    The Librarian reads this document to understand:
      - What the agent is allowed to do (EmployeeContract)
      - What vocabulary to use (IndustryTerminology)
      - What business pressure exists right now (StateFeed + BusinessPlanMath)
      - What the agent should do next (TaskPipeline.actionable_tasks())
      - How fast validations can be scheduled (HITLThroughputModels)
    """
    model_config = ConfigDict(use_enum_values=True)

    # Core identity
    agent_id: str
    agent_name: str

    # Role + agent type contract
    contract: EmployeeContract

    # Domain lock — the agent's industry-specific vocabulary
    terminology: IndustryTerminology = Field(default_factory=lambda: IndustryTerminology(
        industry="general",
        domain_keywords=[],
    ))

    # Live business state feed
    state_feed: StateFeed = Field(default_factory=StateFeed)

    # Business plan math (optional — present only on executive-layer agents
    # and agents with access to the business plan)
    business_plan: Optional[BusinessPlanMath] = None

    # Task pipeline — Magnify×3 → Simplify → Magnify×2 → filter → Solidify
    task_pipeline: TaskPipeline = Field(default_factory=TaskPipeline)

    # HITL throughput models per task type
    hitl_models: List[HITLThroughputModel] = Field(default_factory=list)

    # Underlying base state (system health, workflow patterns, etc.)
    base_state: Optional[RosettaAgentState] = None

    # Shadow observations (shadow agents only)
    shadow_observations: List[Dict[str, Any]] = Field(default_factory=list)

    # Document metadata
    document_version: str = "2.0"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # ------------------------------------------------------------------ #
    # Convenience accessors for the Librarian                             #
    # ------------------------------------------------------------------ #

    def is_shadow(self) -> bool:
        return self.contract.agent_type == AgentType.SHADOW

    def is_automation(self) -> bool:
        return self.contract.agent_type == AgentType.AUTOMATION

    def next_tasks(self, limit: int = 10) -> List[MagnifySimplifyTask]:
        """Return up to *limit* solidified, on-domain tasks, highest priority first."""
        tasks = self.task_pipeline.actionable_tasks()
        tasks.sort(key=lambda t: t.priority)
        return tasks[:limit]

    def get_hitl_model(self, task_type: str) -> Optional[HITLThroughputModel]:
        for m in self.hitl_models:
            if m.task_type == task_type:
                return m
        return None

    def state_metric(self, name: str) -> Optional[float]:
        """Quick read of a live metric from the state feed."""
        return self.state_feed.latest_value(name)

    def business_recommendation(self) -> Optional[str]:
        """Plain-English business plan recommendation, or None if no plan."""
        if self.business_plan is None:
            return None
        return self.business_plan.unit_economics.as_recommendation()

