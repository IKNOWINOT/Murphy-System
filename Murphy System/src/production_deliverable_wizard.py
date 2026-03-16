"""
Production Deliverable Wizard
==============================
Conversational wizard for PRODUCTION mode that guides a user from a
high-level deliverable request to a structured, executable spec.

Unlike the Onboarding wizard (which captures *who the user is*), this
wizard captures *what the user needs to produce* — the deliverable type,
its output format, audience, data sources, and success criteria.

Key design principles (mirroring ``onboarding_flow.py``):

* Structured :class:`DeliverableQuestion` dataclasses with ``order``,
  ``category``, ``required``, and ``deliverable_type`` scoping.
* Session-based state — every :meth:`DeliverableWizard.next_question`
  call returns the next relevant question based on what the user has
  already answered.
* **Onboarding context injection** — if the caller provides an
  ``onboarding_context`` dict (captured during onboarding), answers are
  pre-filled where available (e.g. if they said "I use Slack" during
  onboarding, the notification channel defaults to Slack without asking
  again).
* Output is a :class:`DeliverableSpec` — a fully structured definition
  ready to hand to ``AIWorkflowGenerator`` or the execution engine.

Deliverable types
-----------------
* ``REPORT``          — Scheduled or on-demand document (PDF/Markdown/HTML)
* ``DASHBOARD``       — Live metrics dashboard with charts and KPIs
* ``WORKFLOW``        — Automated multi-step process
* ``DOCUMENT``        — One-off document (proposal, contract, spec)
* ``API_INTEGRATION`` — Connect two systems via REST/webhook
* ``ANALYSIS``        — Data analysis with findings and recommendations
* ``AUTOMATION``      — Background automation (ETL, alerts, cron tasks)
* ``ORG_CHART``       — Org chart with virtual employees (routes to
                        OrgChartGenerator)

Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class DeliverableType(str, Enum):
    REPORT = "report"
    DASHBOARD = "dashboard"
    WORKFLOW = "workflow"
    DOCUMENT = "document"
    API_INTEGRATION = "api_integration"
    ANALYSIS = "analysis"
    AUTOMATION = "automation"
    ORG_CHART = "org_chart"
    UNKNOWN = "unknown"


class OutputFormat(str, Enum):
    PDF = "pdf"
    HTML = "html"
    MARKDOWN = "markdown"
    JSON = "json"
    CSV = "csv"
    SLACK_MESSAGE = "slack_message"
    EMAIL = "email"
    DASHBOARD_WIDGET = "dashboard_widget"
    LIVE_FEED = "live_feed"
    API_RESPONSE = "api_response"
    WORD_DOC = "word_doc"
    SPREADSHEET = "spreadsheet"


class DeliverableStatus(str, Enum):
    GATHERING = "gathering"
    READY = "ready"
    ESCALATED = "escalated"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class DeliverableQuestion:
    """A wizard question for specifying a deliverable.

    ``deliverable_types`` scopes this question: if set, the question is
    only asked when the session's deliverable type is in that set.
    An empty set means the question applies to **all** deliverable types.
    """
    question_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    question: str = ""
    category: str = "general"
    required: bool = True
    options: List[str] = field(default_factory=list)
    help_text: str = ""
    order: int = 0
    deliverable_types: Set[str] = field(default_factory=set)
    """If empty → applies to all types.  If non-empty → only for listed types."""
    onboarding_key: str = ""
    """If set, pull this key from onboarding_context to pre-fill / skip."""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question_id": self.question_id,
            "question": self.question,
            "category": self.category,
            "required": self.required,
            "options": self.options,
            "help_text": self.help_text,
            "order": self.order,
            "deliverable_types": list(self.deliverable_types),
        }


@dataclass
class DeliverableSpec:
    """Structured specification of a deliverable, ready for execution.

    Produced by :meth:`DeliverableWizard.generate_spec`.
    """
    spec_id: str = field(default_factory=lambda: f"spec-{uuid.uuid4().hex[:10]}")
    session_id: str = ""
    deliverable_type: str = DeliverableType.UNKNOWN.value
    title: str = ""
    description: str = ""
    output_format: str = OutputFormat.PDF.value
    audience: str = ""
    data_sources: List[str] = field(default_factory=list)
    schedule: str = ""
    notification_channel: str = ""
    success_criteria: str = ""
    workflow_steps: List[Dict[str, Any]] = field(default_factory=list)
    onboarding_context_used: Dict[str, Any] = field(default_factory=dict)
    raw_answers: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "spec_id": self.spec_id,
            "session_id": self.session_id,
            "deliverable_type": self.deliverable_type,
            "title": self.title,
            "description": self.description,
            "output_format": self.output_format,
            "audience": self.audience,
            "data_sources": self.data_sources,
            "schedule": self.schedule,
            "notification_channel": self.notification_channel,
            "success_criteria": self.success_criteria,
            "workflow_steps": self.workflow_steps,
            "onboarding_context_used": self.onboarding_context_used,
            "raw_answers": self.raw_answers,
            "created_at": self.created_at,
        }


@dataclass
class DeliverableSession:
    """State for a single production deliverable wizard conversation.

    Mirrors ``OnboardingSession`` / ``VirtualOrgSession`` structure:
    * ``questions_answered`` tracks every Q+A pair.
    * ``onboarding_context`` carries knowledge from the user's prior
      onboarding session so questions that were already answered don't
      need to be repeated.
    """
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    deliverable_type: str = DeliverableType.UNKNOWN.value
    questions_answered: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    onboarding_context: Dict[str, Any] = field(default_factory=dict)
    """Onboarding answers injected at session creation."""
    pre_filled: Dict[str, str] = field(default_factory=dict)
    """Questions pre-filled from onboarding context (question_id → answer)."""
    status: DeliverableStatus = DeliverableStatus.GATHERING
    spec: Optional[DeliverableSpec] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "deliverable_type": self.deliverable_type,
            "questions_answered": self.questions_answered,
            "pre_filled": self.pre_filled,
            "status": self.status.value,
            "spec": self.spec.to_dict() if self.spec else None,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# Question bank
# ---------------------------------------------------------------------------

# --- Universal questions (apply to every deliverable type) ---
_UNIVERSAL_QUESTIONS: List[DeliverableQuestion] = [
    DeliverableQuestion(
        question=(
            "What would you like to produce? "
            "(report / dashboard / workflow / document / api_integration / analysis / automation / org_chart)"
        ),
        category="deliverable_type",
        required=True,
        options=[t.value for t in DeliverableType if t != DeliverableType.UNKNOWN],
        help_text="This determines which questions follow.",
        order=1,
    ),
    DeliverableQuestion(
        question="Give this deliverable a short title or name.",
        category="title",
        required=True,
        help_text="E.g. 'Weekly Sales Report', 'Customer Health Dashboard', 'Lead Follow-Up Automation'.",
        order=2,
    ),
    DeliverableQuestion(
        question="Describe in one or two sentences what this deliverable should do.",
        category="description",
        required=True,
        help_text="The more specific you are, the better the generated workflow.",
        order=3,
    ),
    DeliverableQuestion(
        question="Who is the audience for this deliverable?",
        category="audience",
        required=True,
        options=[
            "just me", "my team", "management / executives",
            "customers", "external stakeholders", "automated system (no human audience)",
        ],
        help_text="Audience determines tone, format, and access controls.",
        order=4,
        onboarding_key="position",
    ),
    DeliverableQuestion(
        question="What data sources should this pull from?",
        category="data_sources",
        required=True,
        options=[
            "database / SQL", "CSV / Excel file", "REST API",
            "Google Sheets", "Salesforce", "HubSpot", "Jira",
            "GitHub", "AWS CloudWatch", "Manual input",
        ],
        help_text="Select all that apply.",
        order=5,
        onboarding_key="tools",
    ),
    DeliverableQuestion(
        question="What format should the output be in?",
        category="output_format",
        required=True,
        options=[f.value for f in OutputFormat],
        help_text="The format the deliverable will be delivered in.",
        order=6,
    ),
]

# --- Type-specific questions ---
_TYPE_SPECIFIC_QUESTIONS: List[DeliverableQuestion] = [
    # ---- REPORT ----
    DeliverableQuestion(
        question="How often should this report be generated?",
        category="schedule",
        required=True,
        options=["on demand", "daily", "weekly", "monthly", "quarterly", "event-triggered"],
        help_text="Determines whether to generate a cron-based or event-triggered workflow.",
        order=7,
        deliverable_types={DeliverableType.REPORT.value, DeliverableType.AUTOMATION.value},
    ),
    DeliverableQuestion(
        question="Where should the report be delivered when ready?",
        category="notification_channel",
        required=False,
        options=["email", "Slack", "Teams", "dashboard widget", "S3 / cloud storage", "print queue"],
        help_text="Delivery channel for the finished report.",
        order=8,
        deliverable_types={DeliverableType.REPORT.value},
        onboarding_key="communication_preference",
    ),
    DeliverableQuestion(
        question="What metrics or KPIs must appear in the report?",
        category="content_requirements",
        required=True,
        help_text="E.g. 'revenue, churn rate, NPS score'. List comma-separated.",
        order=9,
        deliverable_types={DeliverableType.REPORT.value, DeliverableType.ANALYSIS.value},
    ),
    # ---- DASHBOARD ----
    DeliverableQuestion(
        question="Should the dashboard update in real-time or on a schedule?",
        category="refresh_policy",
        required=True,
        options=["real-time (live stream)", "every minute", "every 5 minutes", "hourly", "daily refresh"],
        help_text="Real-time dashboards use SSE or websockets; scheduled ones use batch jobs.",
        order=7,
        deliverable_types={DeliverableType.DASHBOARD.value},
    ),
    DeliverableQuestion(
        question="What chart types do you need?",
        category="chart_types",
        required=False,
        options=["line chart", "bar chart", "pie chart", "table", "KPI tile", "map", "funnel"],
        help_text="Select all that apply.",
        order=8,
        deliverable_types={DeliverableType.DASHBOARD.value},
    ),
    DeliverableQuestion(
        question="Who needs access to this dashboard?",
        category="access_control",
        required=False,
        options=["only me", "my team", "whole company", "specific roles", "public / embedded"],
        help_text="Determines authentication requirements.",
        order=9,
        deliverable_types={DeliverableType.DASHBOARD.value},
    ),
    # ---- WORKFLOW / AUTOMATION ----
    DeliverableQuestion(
        question="What triggers this workflow?",
        category="trigger",
        required=True,
        options=[
            "manual (user starts it)",
            "schedule (cron)",
            "event (webhook / API call)",
            "data threshold (e.g. metric exceeds limit)",
            "file upload",
            "new record in CRM / database",
        ],
        help_text="The trigger determines the entry point of the workflow.",
        order=7,
        deliverable_types={DeliverableType.WORKFLOW.value, DeliverableType.AUTOMATION.value},
    ),
    DeliverableQuestion(
        question="Does this workflow require human approval at any step?",
        category="hitl_gates",
        required=False,
        options=["yes — approve before sending", "yes — approve before processing data",
                 "yes — executive sign-off required", "no — fully automated"],
        help_text="HITL gates ensure humans stay in the loop for critical decisions.",
        order=8,
        deliverable_types={DeliverableType.WORKFLOW.value, DeliverableType.AUTOMATION.value},
    ),
    DeliverableQuestion(
        question="What happens when the workflow completes?",
        category="completion_action",
        required=False,
        options=["send notification", "save output to storage", "trigger another workflow",
                 "update a record", "nothing — fire and forget"],
        help_text="Post-completion action.",
        order=9,
        deliverable_types={DeliverableType.WORKFLOW.value, DeliverableType.AUTOMATION.value},
    ),
    # ---- DOCUMENT ----
    DeliverableQuestion(
        question="What type of document is this?",
        category="document_type",
        required=True,
        options=["proposal", "contract", "specification", "policy", "onboarding guide",
                 "SOW / statement of work", "executive summary", "other"],
        help_text="Document type determines the template and required sections.",
        order=7,
        deliverable_types={DeliverableType.DOCUMENT.value},
    ),
    DeliverableQuestion(
        question="Should the document be auto-generated from a template or created from scratch?",
        category="generation_method",
        required=True,
        options=["from template", "AI-generated from brief", "merged from data + template"],
        help_text=(
            "'From template' fills in variable placeholders. "
            "'AI-generated' writes the full document. "
            "'Merged' combines structured data with a template."
        ),
        order=8,
        deliverable_types={DeliverableType.DOCUMENT.value},
    ),
    # ---- API INTEGRATION ----
    DeliverableQuestion(
        question="Which two systems do you want to connect?",
        category="integration_endpoints",
        required=True,
        help_text="E.g. 'Salesforce → Slack', 'GitHub → Jira', 'our database → customer portal'.",
        order=7,
        deliverable_types={DeliverableType.API_INTEGRATION.value},
    ),
    DeliverableQuestion(
        question="What data flows between the systems?",
        category="data_flow",
        required=True,
        help_text="E.g. 'new deal created in Salesforce → post summary to #sales Slack channel'.",
        order=8,
        deliverable_types={DeliverableType.API_INTEGRATION.value},
    ),
    DeliverableQuestion(
        question="Should this integration be one-way or bidirectional?",
        category="sync_direction",
        required=True,
        options=["one-way (source → target)", "bidirectional (keep both in sync)"],
        order=9,
        deliverable_types={DeliverableType.API_INTEGRATION.value},
    ),
    # ---- ANALYSIS ----
    DeliverableQuestion(
        question="What question should this analysis answer?",
        category="analysis_question",
        required=True,
        help_text="E.g. 'Why did churn increase last quarter?' or 'Which campaigns drive the most revenue?'",
        order=7,
        deliverable_types={DeliverableType.ANALYSIS.value},
    ),
    DeliverableQuestion(
        question="What time period should the analysis cover?",
        category="time_period",
        required=True,
        options=["last 7 days", "last 30 days", "last quarter", "last year",
                 "year-to-date", "custom range"],
        order=8,
        deliverable_types={DeliverableType.ANALYSIS.value},
    ),
    DeliverableQuestion(
        question="How should the findings be presented?",
        category="output_presentation",
        required=False,
        options=["executive summary only", "detailed report with charts",
                 "bullet points with recommendations", "raw data export"],
        order=9,
        deliverable_types={DeliverableType.ANALYSIS.value},
    ),
    # ---- ORG CHART ----
    DeliverableQuestion(
        question="Does your company currently have any real employees, or is it just you?",
        category="org_starting_point",
        required=True,
        options=["just me (start fresh)", "a few people (under 10)", "a team (10-50)", "already established (50+)"],
        help_text="This determines how many virtual employees to create as placeholders.",
        order=7,
        deliverable_types={DeliverableType.ORG_CHART.value},
    ),
    DeliverableQuestion(
        question="Which departments are most critical for your business right now?",
        category="priority_departments",
        required=True,
        options=["engineering", "sales", "marketing", "operations", "finance",
                 "hr", "customer_success", "product", "legal", "research"],
        help_text="Virtual employees will be created for these departments first.",
        order=8,
        deliverable_types={DeliverableType.ORG_CHART.value},
    ),
    # ---- SUCCESS CRITERIA (universal, low priority) ----
    DeliverableQuestion(
        question="How will you know this deliverable is successful?",
        category="success_criteria",
        required=False,
        help_text="E.g. 'saves 2 hours per week', 'report delivered by 9am every Monday', 'zero manual data entry'.",
        order=20,
    ),
]


# ---------------------------------------------------------------------------
# Workflow step templates per deliverable type
# ---------------------------------------------------------------------------

_WORKFLOW_TEMPLATES: Dict[str, List[Dict[str, Any]]] = {
    DeliverableType.REPORT.value: [
        {"name": "Fetch Data", "type": "data_fetch", "description": "Collect data from source(s)"},
        {"name": "Process & Aggregate", "type": "transform", "description": "Clean and aggregate data"},
        {"name": "Generate Report", "type": "content_generation", "description": "Render output in requested format"},
        {"name": "Deliver Report", "type": "notification", "description": "Send to audience via chosen channel"},
    ],
    DeliverableType.DASHBOARD.value: [
        {"name": "Connect Data Source", "type": "connector", "description": "Wire live data feeds"},
        {"name": "Define Metrics", "type": "transform", "description": "Compute KPIs and aggregations"},
        {"name": "Render Charts", "type": "content_generation", "description": "Build dashboard widgets"},
        {"name": "Publish Dashboard", "type": "deployment", "description": "Deploy to dashboard platform"},
    ],
    DeliverableType.WORKFLOW.value: [
        {"name": "Trigger Detection", "type": "trigger", "description": "Listen for trigger event"},
        {"name": "Data Preparation", "type": "transform", "description": "Prepare input data"},
        {"name": "Execute Logic", "type": "action", "description": "Run core workflow logic"},
        {"name": "Completion Action", "type": "action", "description": "Perform post-completion step"},
    ],
    DeliverableType.DOCUMENT.value: [
        {"name": "Gather Inputs", "type": "data_fetch", "description": "Collect required fields and data"},
        {"name": "Generate Document", "type": "content_generation", "description": "Generate document from template/AI"},
        {"name": "Review Gate", "type": "approval", "description": "HITL review before sending"},
        {"name": "Deliver Document", "type": "action", "description": "Send or store the document"},
    ],
    DeliverableType.API_INTEGRATION.value: [
        {"name": "Source Trigger", "type": "trigger", "description": "Detect new data in source system"},
        {"name": "Fetch from Source", "type": "connector", "description": "Pull data via API"},
        {"name": "Transform Data", "type": "transform", "description": "Map fields between systems"},
        {"name": "Write to Target", "type": "connector", "description": "Push data to target system"},
        {"name": "Confirm Sync", "type": "action", "description": "Verify write succeeded"},
    ],
    DeliverableType.ANALYSIS.value: [
        {"name": "Data Extraction", "type": "data_fetch", "description": "Pull historical data"},
        {"name": "Clean & Normalise", "type": "transform", "description": "Prepare data for analysis"},
        {"name": "Run Analysis", "type": "action", "description": "Statistical analysis + ML models"},
        {"name": "Generate Findings", "type": "content_generation", "description": "Produce insights report"},
        {"name": "Deliver Findings", "type": "notification", "description": "Share analysis with audience"},
    ],
    DeliverableType.AUTOMATION.value: [
        {"name": "Trigger", "type": "trigger", "description": "Event or schedule trigger"},
        {"name": "Validate Inputs", "type": "action", "description": "Pre-condition checks"},
        {"name": "Execute Automation", "type": "action", "description": "Core automated task"},
        {"name": "Notify Completion", "type": "notification", "description": "Alert stakeholders"},
    ],
    DeliverableType.ORG_CHART.value: [
        {"name": "Gather Org Info", "type": "action", "description": "Collect company structure via wizard"},
        {"name": "Generate Positions", "type": "content_generation", "description": "Create virtual employee positions"},
        {"name": "Assign Shadow Agents", "type": "action", "description": "Wire shadow agents to each position"},
        {"name": "Publish Org Chart", "type": "deployment", "description": "Deploy interactive org chart"},
    ],
}


# ---------------------------------------------------------------------------
# DeliverableWizard
# ---------------------------------------------------------------------------


class DeliverableWizard:
    """Conversational wizard that produces a structured :class:`DeliverableSpec`.

    Design mirrors ``OnboardingFlow``:

    * :meth:`create_session` — start a session, optionally injecting
      onboarding context so already-answered questions are pre-filled.
    * :meth:`next_question` — returns the next relevant, unanswered question.
    * :meth:`answer` — records an answer and returns progress state.
    * :meth:`generate_spec` — compile all answers into a ``DeliverableSpec``.
    """

    def __init__(self) -> None:
        self.sessions: Dict[str, DeliverableSession] = {}
        self._universal_questions = list(_UNIVERSAL_QUESTIONS)
        self._type_questions = list(_TYPE_SPECIFIC_QUESTIONS)

    def create_session(
        self,
        onboarding_context: Optional[Dict[str, Any]] = None,
    ) -> DeliverableSession:
        """Start a new deliverable wizard session.

        Args:
            onboarding_context: Data from a completed onboarding session.
                Keys expected: ``tools`` (str), ``position`` (str),
                ``department`` (str), ``communication_preference`` (str).
                Pre-fills compatible questions so the user isn't asked
                things they already answered during onboarding.
        """
        ctx = onboarding_context or {}
        session = DeliverableSession(onboarding_context=ctx)
        self.sessions[session.session_id] = session

        # Pre-fill from onboarding context
        all_questions = self._universal_questions + self._type_questions
        for q in all_questions:
            if q.onboarding_key and q.onboarding_key in ctx:
                pre_answer = str(ctx[q.onboarding_key])
                if pre_answer:
                    session.pre_filled[q.question_id] = pre_answer
                    session.questions_answered[q.question_id] = {
                        "question": q.question,
                        "answer": pre_answer,
                        "category": q.category,
                        "source": "onboarding_context",
                    }

        logger.info("DeliverableWizard: new session %s", session.session_id)
        return session

    def get_session(self, session_id: str) -> Optional[DeliverableSession]:
        return self.sessions.get(session_id)

    def next_question(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Return the next unanswered question for this session.

        Questions are scoped by:

        1. Whether the question's ``deliverable_types`` includes the
           session's currently-known deliverable type (or is universal).
        2. Whether the question has not yet been answered (including
           pre-fills from onboarding).

        Returns ``None`` when all required questions are answered.
        """
        session = self.sessions.get(session_id)
        if not session:
            return None

        answered_ids = set(session.questions_answered.keys())
        all_q = sorted(
            self._universal_questions + self._type_questions,
            key=lambda x: x.order,
        )

        for q in all_q:
            if q.question_id in answered_ids:
                continue
            # Scope check
            if q.deliverable_types and session.deliverable_type not in q.deliverable_types:
                continue
            return q.to_dict()

        return None  # all answered

    def answer(
        self,
        session_id: str,
        question_id: str,
        answer: str,
    ) -> Dict[str, Any]:
        """Record an answer and return progress state.

        Mirrors ``OnboardingFlow.answer_question()`` and
        ``OrgChartGenerator.answer()``.
        """
        session = self.sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}

        all_q = self._universal_questions + self._type_questions
        q = next((q for q in all_q if q.question_id == question_id), None)
        if not q:
            return {"error": f"Question {question_id!r} not found"}

        session.questions_answered[question_id] = {
            "question": q.question,
            "answer": answer,
            "category": q.category,
        }

        # Update deliverable type as soon as we know it
        if q.category == "deliverable_type":
            dt = answer.strip().lower()
            valid = {t.value for t in DeliverableType}
            session.deliverable_type = dt if dt in valid else DeliverableType.UNKNOWN.value

        # Calculate remaining required questions for the current type
        required_remaining = self._count_required_remaining(session)
        is_ready = required_remaining == 0

        if is_ready:
            session.status = DeliverableStatus.READY

        return {
            "session_id": session_id,
            "questions_answered": len(session.questions_answered),
            "deliverable_type": session.deliverable_type,
            "required_remaining": required_remaining,
            "status": session.status.value,
            "next_question": self.next_question(session_id),
        }

    def generate_spec(self, session_id: str) -> Optional[DeliverableSpec]:
        """Compile all answers into a structured :class:`DeliverableSpec`.

        Can be called at any point (even before all questions are answered);
        unanswered fields default to empty strings or empty lists.
        """
        session = self.sessions.get(session_id)
        if not session:
            return None

        def _get(cat: str) -> str:
            for qa in session.questions_answered.values():
                if qa.get("category") == cat:
                    return qa.get("answer", "")
            return ""

        deliverable_type = session.deliverable_type or DeliverableType.UNKNOWN.value
        title = _get("title")
        description = _get("description")
        output_format = _get("output_format") or OutputFormat.PDF.value
        audience = _get("audience")
        data_sources_raw = _get("data_sources")
        data_sources = [s.strip() for s in data_sources_raw.replace(",", " ").split() if s.strip()]
        schedule = _get("schedule")
        success_criteria = _get("success_criteria")

        # Notification channel: use onboarding context if available
        notification_channel = _get("notification_channel")
        if not notification_channel:
            tools = session.onboarding_context.get("tools", "").lower()
            if "slack" in tools:
                notification_channel = "slack"
            elif "teams" in tools:
                notification_channel = "teams"
            elif "email" in tools:
                notification_channel = "email"

        # Workflow steps from template
        steps = _WORKFLOW_TEMPLATES.get(deliverable_type, _WORKFLOW_TEMPLATES.get(DeliverableType.WORKFLOW.value, []))

        # Track which onboarding context was used
        onboarding_context_used = {
            k: v
            for k, v in session.onboarding_context.items()
            if any(
                qa.get("source") == "onboarding_context" and k in str(qa.get("answer", ""))
                for qa in session.questions_answered.values()
            )
        }
        if session.pre_filled:
            onboarding_context_used["pre_filled_questions"] = len(session.pre_filled)

        spec = DeliverableSpec(
            session_id=session_id,
            deliverable_type=deliverable_type,
            title=title or f"{deliverable_type.replace('_', ' ').title()} Deliverable",
            description=description,
            output_format=output_format,
            audience=audience,
            data_sources=data_sources,
            schedule=schedule,
            notification_channel=notification_channel,
            success_criteria=success_criteria,
            workflow_steps=list(steps),
            onboarding_context_used=onboarding_context_used,
            raw_answers=dict(session.questions_answered),
        )

        session.spec = spec
        session.status = DeliverableStatus.READY
        logger.info(
            "DeliverableWizard: spec generated session=%s type=%s",
            session_id, deliverable_type,
        )
        return spec

    def get_all_questions(self, deliverable_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return all questions, optionally scoped to a deliverable type."""
        all_q = sorted(
            self._universal_questions + self._type_questions,
            key=lambda x: x.order,
        )
        if deliverable_type is None:
            return [q.to_dict() for q in all_q]
        return [
            q.to_dict()
            for q in all_q
            if not q.deliverable_types or deliverable_type in q.deliverable_types
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _count_required_remaining(self, session: DeliverableSession) -> int:
        answered_ids = set(session.questions_answered.keys())
        required_unanswered = 0
        all_q = self._universal_questions + self._type_questions
        for q in all_q:
            if not q.required:
                continue
            if q.question_id in answered_ids:
                continue
            if q.deliverable_types and session.deliverable_type not in q.deliverable_types:
                continue
            required_unanswered += 1
        return required_unanswered
