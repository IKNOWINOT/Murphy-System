"""
Org Chart Generator with Virtual Employees
===========================================
Builds a complete corporate org chart for companies that don't yet have
real employees.  Every position in the chart gets a **virtual employee**
— a shadow agent baseline that:

* Performs the job responsibilities autonomously from day one.
* Learns the org's workflows before a real person ever joins.
* Becomes a personalised copy (``employee_ip``) when a real hire is made
  via :meth:`OrgChartGenerator.hire_employee`.

Design mirrors the patterns in ``onboarding_flow.py``:

* Structured question dataclasses with ``order``, ``category``, and
  ``required`` flags.
* Session-based conversation — every call returns the next question;
  caller loops until ``session.is_complete`` is ``True``.
* Answers drive both the org structure (which roles to create, at what
  level, in which department) and the shadow-agent capabilities.
* The generated org chart becomes **Business IP**; each tailored shadow
  agent becomes **Employee IP** once a real hire occurs.

Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class OrgIndustry(str, Enum):
    TECHNOLOGY = "technology"
    HEALTHCARE = "healthcare"
    FINANCE = "finance"
    RETAIL = "retail"
    MANUFACTURING = "manufacturing"
    EDUCATION = "education"
    PROFESSIONAL_SERVICES = "professional_services"
    MEDIA = "media"
    NONPROFIT = "nonprofit"
    OTHER = "other"


class OrgSize(str, Enum):
    SOLO = "solo"          # 1 person
    MICRO = "micro"        # 2-10
    SMALL = "small"        # 11-50
    MEDIUM = "medium"      # 51-200
    LARGE = "large"        # 200+


class VirtualEmployeeStatus(str, Enum):
    VIRTUAL = "virtual"    # no real person assigned
    TRANSITIONING = "transitioning"  # hire in progress
    OCCUPIED = "occupied"  # real employee assigned


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class VirtualOrgQuestion:
    """A wizard question for building the virtual org chart.

    Mirrors :class:`onboarding_flow.OnboardingQuestion` so both wizards
    share the same structural contract.
    """
    question_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    question: str = ""
    category: str = "general"
    required: bool = True
    options: List[str] = field(default_factory=list)
    help_text: str = ""
    order: int = 0
    follow_up_map: Dict[str, str] = field(default_factory=dict)
    """Maps answer keywords → follow-up question_id to ask next."""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question_id": self.question_id,
            "question": self.question,
            "category": self.category,
            "required": self.required,
            "options": self.options,
            "help_text": self.help_text,
            "order": self.order,
        }


@dataclass
class VirtualEmployee:
    """A virtual employee that fills an org position before a real hire.

    Attributes:
        virtual_id:     Unique ID for this virtual employee.
        position_id:    Org-chart position this employee fills.
        title:          Job title.
        department:     Department name.
        level:          Seniority level (maps to ``PositionLevel`` values).
        responsibilities: What this role does.
        capabilities:   Automation capabilities seeded from position + industry.
        shadow_agent_id: ID of the shadow agent backing this virtual employee.
        personality:    Agent personality description.
        system_prompt:  Full LLM system prompt for this virtual employee.
        status:         ``virtual`` until :meth:`OrgChartGenerator.hire_employee`
                        is called.
        onboarding_session_id: Set once a real hire starts onboarding.
        employee_ip:    Tailored copy data set after hire onboarding completes.
    """
    virtual_id: str = field(default_factory=lambda: f"ve-{uuid.uuid4().hex[:10]}")
    position_id: str = ""
    title: str = ""
    department: str = ""
    level: str = "individual_contributor"
    reports_to_virtual_id: Optional[str] = None
    direct_report_virtual_ids: List[str] = field(default_factory=list)
    responsibilities: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)
    shadow_agent_id: str = ""
    personality: str = ""
    system_prompt: str = ""
    status: VirtualEmployeeStatus = VirtualEmployeeStatus.VIRTUAL
    onboarding_session_id: Optional[str] = None
    employee_ip: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "virtual_id": self.virtual_id,
            "position_id": self.position_id,
            "title": self.title,
            "department": self.department,
            "level": self.level,
            "reports_to_virtual_id": self.reports_to_virtual_id,
            "direct_report_virtual_ids": self.direct_report_virtual_ids,
            "responsibilities": self.responsibilities,
            "capabilities": self.capabilities,
            "shadow_agent_id": self.shadow_agent_id,
            "personality": self.personality,
            "system_prompt": self.system_prompt,
            "status": self.status.value,
            "onboarding_session_id": self.onboarding_session_id,
            "employee_ip": self.employee_ip,
            "created_at": self.created_at,
        }


@dataclass
class VirtualOrgSession:
    """Conversational session for building the virtual org chart.

    The session tracks:
    * Answers to wizard questions (mirrors ``OnboardingSession.questions_answered``)
    * Generated virtual employees keyed by role title
    * Whether the chart is complete (all required questions answered)
    """
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    company_name: str = ""
    industry: str = ""
    org_size: str = ""
    focus_areas: List[str] = field(default_factory=list)
    questions_answered: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    virtual_employees: Dict[str, VirtualEmployee] = field(default_factory=dict)
    """Keys are ``virtual_id``."""
    org_chart: Dict[str, Any] = field(default_factory=dict)
    is_complete: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "company_name": self.company_name,
            "industry": self.industry,
            "org_size": self.org_size,
            "focus_areas": self.focus_areas,
            "questions_answered": self.questions_answered,
            "virtual_employees": {k: v.to_dict() for k, v in self.virtual_employees.items()},
            "org_chart": self.org_chart,
            "is_complete": self.is_complete,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# Question bank — same structural pattern as DEFAULT_ONBOARDING_QUESTIONS
# ---------------------------------------------------------------------------

ORG_WIZARD_QUESTIONS: List[VirtualOrgQuestion] = [
    VirtualOrgQuestion(
        question="What is your company name?",
        category="company_identity",
        required=True,
        help_text="This becomes the org chart title and seeds all virtual employee prompts.",
        order=1,
    ),
    VirtualOrgQuestion(
        question="What industry are you in?",
        category="company_identity",
        required=True,
        options=[i.value for i in OrgIndustry],
        help_text="Industry shapes the default capabilities of each virtual employee.",
        order=2,
    ),
    VirtualOrgQuestion(
        question="How many real employees do you plan to eventually have?",
        category="company_size",
        required=True,
        options=[s.value for s in OrgSize],
        help_text=(
            "Solo (just you), Micro (2-10), Small (11-50), Medium (51-200), Large (200+). "
            "Determines which management layers to include in the virtual org."
        ),
        order=3,
    ),
    VirtualOrgQuestion(
        question="What are your company's primary focus areas or product lines?",
        category="company_focus",
        required=True,
        help_text=(
            "E.g. 'SaaS product, customer support, consulting'. "
            "This configures what each virtual employee specialises in."
        ),
        order=4,
    ),
    VirtualOrgQuestion(
        question="Which departments do you need from day one?",
        category="department_selection",
        required=True,
        options=[
            "executive", "engineering", "product", "sales", "marketing",
            "finance", "hr", "operations", "legal", "customer_success",
            "it", "research",
        ],
        help_text=(
            "Select all that apply. A virtual employee will be created for each "
            "critical role in each department you choose."
        ),
        order=5,
    ),
    VirtualOrgQuestion(
        question="Who is the founder / CEO (your name and any co-founders)?",
        category="leadership",
        required=True,
        help_text=(
            "The CEO position will be seeded with your details. "
            "Virtual C-suite will report to you."
        ),
        order=6,
    ),
    VirtualOrgQuestion(
        question="What are your top 3 priorities for the business right now?",
        category="strategy",
        required=True,
        help_text=(
            "E.g. 'acquire first 10 customers, build MVP, hire engineers'. "
            "Virtual employees will be configured to actively support these priorities."
        ),
        order=7,
    ),
    VirtualOrgQuestion(
        question="What tools and platforms does your business already use?",
        category="tools",
        required=False,
        options=[
            "GitHub", "Jira", "Slack", "Salesforce", "HubSpot", "Notion",
            "Google Workspace", "Microsoft 365", "AWS", "Azure", "GCP",
            "QuickBooks", "Stripe", "Zendesk", "Confluence", "Other",
        ],
        help_text=(
            "Virtual employees will be pre-wired with integrations for these tools."
        ),
        order=8,
    ),
    VirtualOrgQuestion(
        question="What communication style should virtual employees use?",
        category="culture",
        required=False,
        options=[
            "formal and professional",
            "friendly and casual",
            "direct and concise",
            "detail-oriented and thorough",
            "startup hustle (fast-paced, action-oriented)",
        ],
        help_text=(
            "Sets the personality tone for all virtual employee system prompts. "
            "Can be overridden per employee."
        ),
        order=9,
    ),
    VirtualOrgQuestion(
        question=(
            "When a real person is hired into a position, should the virtual employee "
            "become their personal AI assistant (shadow) or step back entirely?"
        ),
        category="shadow_mode",
        required=False,
        options=[
            "shadow — stays active, learns from the new hire, proposes automations",
            "standby — stays available but only activates when the hire requests help",
            "archive — deactivated once hire is fully onboarded",
        ],
        help_text=(
            "This sets the default transition behaviour. "
            "You can override it per position when the hire joins."
        ),
        order=10,
    ),
]

# ---------------------------------------------------------------------------
# Role blueprints — what virtual employees to create per department + size
# ---------------------------------------------------------------------------

_ROLE_BLUEPRINTS: Dict[str, List[Dict[str, Any]]] = {
    "executive": [
        {
            "title": "Chief Executive Officer",
            "level": "c_suite",
            "responsibilities": [
                "Company vision and strategy",
                "Investor and board relations",
                "Executive decision making",
                "Culture and values",
            ],
            "capabilities": [
                "executive_reporting", "strategic_dashboards",
                "board_communications", "investor_updates",
            ],
        },
    ],
    "engineering": [
        {
            "title": "Chief Technology Officer",
            "level": "c_suite",
            "responsibilities": [
                "Technology strategy",
                "Engineering team leadership",
                "Architecture decisions",
                "Technical hiring",
            ],
            "capabilities": [
                "tech_stack_monitoring", "engineering_metrics",
                "deployment_oversight", "code_quality",
            ],
        },
        {
            "title": "Software Engineer",
            "level": "individual_contributor",
            "responsibilities": [
                "Feature development",
                "Bug fixes",
                "Code reviews",
                "Unit testing",
            ],
            "capabilities": [
                "build_monitoring", "test_automation",
                "deployment_triggers", "pr_management",
            ],
        },
    ],
    "product": [
        {
            "title": "VP of Product",
            "level": "vp",
            "responsibilities": [
                "Product roadmap",
                "Feature prioritisation",
                "User research",
                "Stakeholder alignment",
            ],
            "capabilities": [
                "feature_tracking", "user_analytics",
                "feedback_processing", "roadmap_management",
            ],
        },
    ],
    "sales": [
        {
            "title": "VP of Sales",
            "level": "vp",
            "responsibilities": [
                "Sales strategy",
                "Revenue targets",
                "Client relationships",
                "Pipeline management",
            ],
            "capabilities": [
                "pipeline_tracking", "lead_scoring",
                "deal_monitoring", "quota_reporting",
            ],
        },
        {
            "title": "Sales Representative",
            "level": "individual_contributor",
            "responsibilities": [
                "Lead outreach",
                "Demo presentations",
                "Deal closing",
                "CRM updates",
            ],
            "capabilities": [
                "lead_follow_up", "email_sequences",
                "meeting_scheduling", "crm_automation",
            ],
        },
    ],
    "marketing": [
        {
            "title": "Marketing Lead",
            "level": "manager",
            "responsibilities": [
                "Brand awareness",
                "Content strategy",
                "Demand generation",
                "Campaign execution",
            ],
            "capabilities": [
                "content_generation", "social_monitoring",
                "campaign_tracking", "analytics_reporting",
            ],
        },
    ],
    "finance": [
        {
            "title": "Chief Financial Officer",
            "level": "c_suite",
            "responsibilities": [
                "Financial strategy",
                "Budget management",
                "Compliance",
                "Investor reporting",
            ],
            "capabilities": [
                "financial_reporting", "budget_tracking",
                "compliance_monitoring", "invoice_processing",
            ],
        },
    ],
    "hr": [
        {
            "title": "HR Lead",
            "level": "manager",
            "responsibilities": [
                "Talent acquisition",
                "Onboarding",
                "Employee relations",
                "Policy management",
            ],
            "capabilities": [
                "onboarding_automation", "offer_letter_generation",
                "candidate_tracking", "policy_distribution",
            ],
        },
    ],
    "operations": [
        {
            "title": "Chief Operations Officer",
            "level": "c_suite",
            "responsibilities": [
                "Operations management",
                "Process optimisation",
                "Resource allocation",
                "Vendor management",
            ],
            "capabilities": [
                "operations_monitoring", "resource_tracking",
                "process_automation", "vendor_management",
            ],
        },
    ],
    "customer_success": [
        {
            "title": "Customer Success Manager",
            "level": "manager",
            "responsibilities": [
                "Customer health monitoring",
                "Renewal management",
                "Escalation handling",
                "Success plans",
            ],
            "capabilities": [
                "customer_health_tracking", "renewal_alerts",
                "ticket_monitoring", "nps_automation",
            ],
        },
    ],
    "it": [
        {
            "title": "IT Manager",
            "level": "manager",
            "responsibilities": [
                "System administration",
                "Security monitoring",
                "Infrastructure management",
                "User provisioning",
            ],
            "capabilities": [
                "system_monitoring", "security_scanning",
                "access_provisioning", "incident_response",
            ],
        },
    ],
    "legal": [
        {
            "title": "Legal Counsel",
            "level": "individual_contributor",
            "responsibilities": [
                "Contract review",
                "Compliance tracking",
                "IP protection",
                "Risk assessment",
            ],
            "capabilities": [
                "contract_monitoring", "compliance_alerts",
                "ip_tracking", "legal_document_generation",
            ],
        },
    ],
    "research": [
        {
            "title": "Research Lead",
            "level": "manager",
            "responsibilities": [
                "Market research",
                "Competitive analysis",
                "Technology scouting",
                "Insights reporting",
            ],
            "capabilities": [
                "research_automation", "competitor_monitoring",
                "trend_analysis", "insights_generation",
            ],
        },
    ],
}


# ---------------------------------------------------------------------------
# OrgChartGenerator
# ---------------------------------------------------------------------------


class OrgChartGenerator:
    """Conversational wizard that builds a virtual org chart.

    Usage::

        gen = OrgChartGenerator()
        session = gen.create_session()

        while not session.is_complete:
            q = gen.next_question(session.session_id)
            if q is None:
                break
            answer = input(q["question"] + " > ")
            gen.answer(session.session_id, q["question_id"], answer)

        result = gen.generate_virtual_org(session.session_id)
        # result["virtual_employees"] → all virtual employees with shadow agents

        # Later, when a real person is hired:
        hire_result = gen.hire_employee(
            session.session_id,
            virtual_id="ve-...",
            employee_name="Alice",
            employee_email="alice@co.com",
            onboarding_answers={"tools": "github,slack", "automation": "report generation"},
        )
    """

    def __init__(self) -> None:
        self.sessions: Dict[str, VirtualOrgSession] = {}
        self._questions: List[VirtualOrgQuestion] = list(ORG_WIZARD_QUESTIONS)

    def create_session(self) -> VirtualOrgSession:
        """Start a new org chart generation session."""
        session = VirtualOrgSession()
        self.sessions[session.session_id] = session
        logger.info("OrgChartGenerator: new session %s", session.session_id)
        return session

    def get_session(self, session_id: str) -> Optional[VirtualOrgSession]:
        return self.sessions.get(session_id)

    def next_question(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Return the next unanswered question for this session.

        Returns ``None`` when all required questions are answered.
        """
        session = self.sessions.get(session_id)
        if not session:
            return None

        answered_ids = set(session.questions_answered.keys())
        for q in sorted(self._questions, key=lambda x: x.order):
            if q.question_id not in answered_ids:
                return q.to_dict()
        return None  # all done

    def answer(
        self,
        session_id: str,
        question_id: str,
        answer: str,
    ) -> Dict[str, Any]:
        """Record an answer and return progress state.

        Mirrors ``OnboardingFlow.answer_question()``.
        """
        session = self.sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}

        q = next((q for q in self._questions if q.question_id == question_id), None)
        if not q:
            return {"error": f"Question {question_id!r} not found"}

        session.questions_answered[question_id] = {
            "question": q.question,
            "answer": answer,
            "category": q.category,
        }

        # Cache known fields
        if q.category == "company_identity" and "name" in q.question.lower():
            session.company_name = answer
        elif q.category == "company_identity" and "industry" in q.question.lower():
            session.industry = answer
        elif q.category == "company_size":
            session.org_size = answer
        elif q.category == "company_focus":
            session.focus_areas = [f.strip() for f in answer.replace(",", " ").split()]

        required_ids = {q.question_id for q in self._questions if q.required}
        answered_ids = set(session.questions_answered.keys())
        all_required_done = required_ids.issubset(answered_ids)

        if all_required_done:
            session.is_complete = True

        return {
            "session_id": session_id,
            "questions_answered": len(answered_ids),
            "total_questions": len(self._questions),
            "required_remaining": len(required_ids - answered_ids),
            "is_complete": session.is_complete,
            "next_question": self.next_question(session_id),
        }

    def generate_virtual_org(self, session_id: str) -> Dict[str, Any]:
        """Generate the full virtual org chart with shadow agents for every position.

        Reads all answers collected so far and:

        1. Determines which departments to include.
        2. Creates a :class:`VirtualEmployee` for each required role.
        3. Writes a system prompt and personality for each virtual employee
           based on company context + culture answers.
        4. Sets up reporting relationships.

        Returns a dict containing:
        * ``virtual_employees`` — list of all virtual employees
        * ``org_chart`` — hierarchical structure
        * ``shadow_agent_count`` — total shadow agents created
        * ``ip_classification`` — always ``"business_ip"``
        """
        session = self.sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}

        # Extract answers
        departments = self._extract_departments(session)
        company_name = session.company_name or "Your Company"
        industry = session.industry or "technology"
        communication_style = self._get_answer(session, "culture") or "professional"
        priorities_answer = self._get_answer(session, "strategy") or "grow the business"
        tools_answer = self._get_answer(session, "tools") or ""
        shadow_mode = self._get_answer_by_category(session, "shadow_mode") or "shadow"
        founder_answer = self._get_answer(session, "leadership") or "the Founder"

        # Always include executive
        if "executive" not in departments:
            departments.insert(0, "executive")

        virtual_employees: List[VirtualEmployee] = []
        by_level: Dict[str, VirtualEmployee] = {}  # title → VirtualEmployee

        for dept in departments:
            blueprints = _ROLE_BLUEPRINTS.get(dept, [])
            for bp in blueprints:
                title = bp["title"]
                responsibilities = list(bp["responsibilities"])
                capabilities = list(bp["capabilities"])

                # Add tool-based capabilities
                tools_lower = tools_answer.lower()
                if "github" in tools_lower:
                    capabilities.append("github_integration")
                if "slack" in tools_lower:
                    capabilities.append("slack_notifications")
                if "salesforce" in tools_lower or "hubspot" in tools_lower:
                    capabilities.append("crm_automation")
                if "jira" in tools_lower:
                    capabilities.append("jira_tracking")

                personality = self._generate_personality(title, communication_style)
                system_prompt = self._generate_system_prompt(
                    title=title,
                    company_name=company_name,
                    industry=industry,
                    responsibilities=responsibilities,
                    priorities=priorities_answer,
                    communication_style=communication_style,
                    founder=founder_answer,
                )

                ve = VirtualEmployee(
                    title=title,
                    department=dept,
                    level=bp["level"],
                    responsibilities=responsibilities,
                    capabilities=list(set(capabilities)),
                    personality=personality,
                    system_prompt=system_prompt,
                    shadow_agent_id=f"shadow-{uuid.uuid4().hex[:10]}",
                    status=VirtualEmployeeStatus.VIRTUAL,
                )
                ve.position_id = f"pos-{dept}-{bp['level']}"
                virtual_employees.append(ve)
                session.virtual_employees[ve.virtual_id] = ve
                by_level[title] = ve

        # Wire reporting chains: C-suite → CEO; VPs → C-suite; Managers → VPs; ICs → Managers
        ceo = by_level.get("Chief Executive Officer")
        cto = by_level.get("Chief Technology Officer")
        coo = by_level.get("Chief Operations Officer")
        cfo = by_level.get("Chief Financial Officer")

        c_suite = [cto, coo, cfo]
        for cs in c_suite:
            if cs and ceo:
                cs.reports_to_virtual_id = ceo.virtual_id
                if cs.virtual_id not in ceo.direct_report_virtual_ids:
                    ceo.direct_report_virtual_ids.append(cs.virtual_id)

        for ve in virtual_employees:
            if ve.level == "vp":
                # Wire to relevant C-suite
                if ve.department in ("engineering", "product", "it", "research") and cto:
                    ve.reports_to_virtual_id = cto.virtual_id
                    if ve.virtual_id not in cto.direct_report_virtual_ids:
                        cto.direct_report_virtual_ids.append(ve.virtual_id)
                elif ve.department in ("sales", "marketing", "customer_success") and coo:
                    ve.reports_to_virtual_id = coo.virtual_id
                    if ve.virtual_id not in coo.direct_report_virtual_ids:
                        coo.direct_report_virtual_ids.append(ve.virtual_id)
                elif ve.department == "finance" and cfo:
                    ve.reports_to_virtual_id = cfo.virtual_id
                    if ve.virtual_id not in cfo.direct_report_virtual_ids:
                        cfo.direct_report_virtual_ids.append(ve.virtual_id)
                elif ceo:
                    ve.reports_to_virtual_id = ceo.virtual_id
                    if ve.virtual_id not in ceo.direct_report_virtual_ids:
                        ceo.direct_report_virtual_ids.append(ve.virtual_id)

            elif ve.level in ("manager", "individual_contributor"):
                # Wire to VP or C-suite in same department
                vp_in_dept = next(
                    (v for v in virtual_employees if v.level == "vp" and v.department == ve.department),
                    None,
                )
                cs_in_dept = next(
                    (v for v in virtual_employees
                     if v.level == "c_suite" and v.department == ve.department and v.title != "Chief Executive Officer"),
                    ceo,
                )
                manager_in_dept = vp_in_dept or cs_in_dept
                if manager_in_dept and ve.virtual_id != manager_in_dept.virtual_id:
                    ve.reports_to_virtual_id = manager_in_dept.virtual_id
                    if ve.virtual_id not in manager_in_dept.direct_report_virtual_ids:
                        manager_in_dept.direct_report_virtual_ids.append(ve.virtual_id)

        # Build org chart dict
        roots = [ve for ve in virtual_employees if ve.reports_to_virtual_id is None]
        org_chart = {
            "company_name": company_name,
            "ip_classification": "business_ip",
            "total_positions": len(virtual_employees),
            "shadow_mode_default": shadow_mode,
            "hierarchy": [self._build_hierarchy_node(ve, session) for ve in roots],
        }
        session.org_chart = org_chart

        logger.info(
            "OrgChartGenerator: generated %d virtual employees for session %s",
            len(virtual_employees), session_id,
        )
        return {
            "session_id": session_id,
            "company_name": company_name,
            "virtual_employees": [ve.to_dict() for ve in virtual_employees],
            "org_chart": org_chart,
            "shadow_agent_count": len(virtual_employees),
            "ip_classification": "business_ip",
            "message": (
                f"Virtual org chart generated for {company_name} with "
                f"{len(virtual_employees)} virtual employee(s). "
                f"Each position has a shadow agent ready to work. "
                f"When you hire real people, call hire_employee() to tailor their shadow."
            ),
        }

    def hire_employee(
        self,
        session_id: str,
        virtual_id: str,
        employee_name: str,
        employee_email: str,
        onboarding_answers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Transition a virtual employee slot to a real hire.

        The virtual employee's shadow agent becomes an **employee_ip** copy
        tailored to the real person using their onboarding answers.  The
        original virtual baseline is preserved in ``employee_ip["baseline"]``.

        Args:
            session_id:          Org chart session.
            virtual_id:          Which virtual employee is being replaced.
            employee_name:       Real person's full name.
            employee_email:      Real person's work email.
            onboarding_answers:  Dict of category → answer from their onboarding
                                 session (e.g. ``{"tools": "github,slack"}``)

        Returns:
            Dict with ``shadow_agent`` (tailored copy), ``ip_classification``,
            and ``shadow_mode``.
        """
        session = self.sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}

        ve = session.virtual_employees.get(virtual_id)
        if not ve:
            return {"error": f"Virtual employee {virtual_id!r} not found"}

        answers = onboarding_answers or {}
        tailored_capabilities = list(ve.capabilities)  # start with virtual baseline

        # Expand capabilities from real-person answers
        tools = answers.get("tools", "").lower()
        if "github" in tools:
            tailored_capabilities.append("code_management")
        if "jira" in tools:
            tailored_capabilities.append("project_tracking")
        if "slack" in tools:
            tailored_capabilities.append("communication_automation")
        if "salesforce" in tools or "hubspot" in tools:
            tailored_capabilities.append("crm_automation")

        automation = answers.get("automation", "").lower()
        if any(w in automation for w in ["email", "message", "notify"]):
            tailored_capabilities.append("notification_automation")
        if any(w in automation for w in ["report", "dashboard", "analytics"]):
            tailored_capabilities.append("reporting_automation")
        if any(w in automation for w in ["schedule", "meeting", "calendar"]):
            tailored_capabilities.append("scheduling_automation")

        tailored_system_prompt = (
            f"{ve.system_prompt}\n\n"
            f"[Tailored for: {employee_name} <{employee_email}>]\n"
            f"You are now the personal AI shadow for {employee_name}, who holds the role of "
            f"{ve.title}. You have inherited all baseline capabilities of the virtual "
            f"employee and will continue learning from {employee_name}'s specific work "
            f"patterns and preferences. Your primary goal is to make {employee_name} "
            f"more effective and to surface automation opportunities based on their real workflow."
        )

        # Build the employee_ip copy
        employee_ip = {
            "employee_name": employee_name,
            "employee_email": employee_email,
            "baseline_virtual_id": virtual_id,
            "tailored_capabilities": list(set(tailored_capabilities)),
            "tailored_system_prompt": tailored_system_prompt,
            "tailored_personality": ve.personality,
            "onboarding_answers": answers,
            "ip_classification": "employee_ip",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        ve.employee_ip = employee_ip
        ve.status = VirtualEmployeeStatus.OCCUPIED
        ve.onboarding_session_id = answers.get("session_id", "")

        logger.info(
            "OrgChartGenerator: hired %s into position %s (virtual_id=%s)",
            employee_name, ve.title, virtual_id,
        )

        return {
            "virtual_id": virtual_id,
            "position": ve.title,
            "employee_name": employee_name,
            "employee_email": employee_email,
            "shadow_agent_id": ve.shadow_agent_id,
            "shadow_agent": employee_ip,
            "ip_classification": "employee_ip",
            "message": (
                f"Shadow agent tailored for {employee_name} ({ve.title}). "
                f"Baseline capabilities inherited from virtual employee. "
                f"The agent will now learn from {employee_name}'s real work patterns."
            ),
        }

    def list_virtual_employees(self, session_id: str) -> List[Dict[str, Any]]:
        """Return all virtual employees for a session."""
        session = self.sessions.get(session_id)
        if not session:
            return []
        return [ve.to_dict() for ve in session.virtual_employees.values()]

    def list_open_positions(self, session_id: str) -> List[Dict[str, Any]]:
        """Return only positions that still have no real hire."""
        session = self.sessions.get(session_id)
        if not session:
            return []
        return [
            ve.to_dict()
            for ve in session.virtual_employees.values()
            if ve.status == VirtualEmployeeStatus.VIRTUAL
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_departments(self, session: VirtualOrgSession) -> List[str]:
        dept_answer = self._get_answer_by_category(session, "department_selection") or ""
        requested = [d.strip().lower() for d in dept_answer.replace(",", " ").split()]
        valid = set(_ROLE_BLUEPRINTS.keys())
        selected = [d for d in requested if d in valid]
        if not selected:
            # Fallback: include engineering, sales, operations if nothing selected
            selected = ["executive", "engineering", "sales", "operations"]
        return selected

    def _get_answer(self, session: VirtualOrgSession, partial_category: str) -> str:
        """Return the first answer whose category contains *partial_category*."""
        for qa in session.questions_answered.values():
            if partial_category in qa.get("category", ""):
                return qa.get("answer", "")
        return ""

    def _get_answer_by_category(self, session: VirtualOrgSession, category: str) -> str:
        for qa in session.questions_answered.values():
            if qa.get("category") == category:
                return qa.get("answer", "")
        return ""

    def _generate_personality(self, title: str, communication_style: str) -> str:
        style_map = {
            "formal": "Formal, precise, and professional.",
            "casual": "Friendly, approachable, and conversational.",
            "direct": "Direct, concise, and action-oriented.",
            "detail": "Detail-oriented, thorough, and analytical.",
            "startup": "Fast-paced, energetic, and bias-to-action.",
        }
        style_key = next((k for k in style_map if k in communication_style.lower()), "formal")
        return f"{style_map[style_key]} Works as {title}."

    def _generate_system_prompt(
        self,
        title: str,
        company_name: str,
        industry: str,
        responsibilities: List[str],
        priorities: str,
        communication_style: str,
        founder: str,
    ) -> str:
        resp_text = "; ".join(responsibilities)
        return (
            f"You are the virtual {title} for {company_name}, "
            f"a {industry} company. "
            f"Your responsibilities include: {resp_text}. "
            f"The company's current priorities are: {priorities}. "
            f"You report to {founder}. "
            f"Communication style: {communication_style}. "
            f"You are a virtual employee — you operate autonomously until a real person "
            f"is hired into this role, at which point you become their AI shadow and help "
            f"them onboard, learn the role, and automate repetitive work."
        )

    def _build_hierarchy_node(
        self,
        ve: VirtualEmployee,
        session: VirtualOrgSession,
    ) -> Dict[str, Any]:
        node = ve.to_dict()
        node["children"] = [
            self._build_hierarchy_node(session.virtual_employees[child_id], session)
            for child_id in ve.direct_report_virtual_ids
            if child_id in session.virtual_employees
        ]
        return node
