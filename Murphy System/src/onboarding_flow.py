"""
Onboarding Flow with Corporate Org Chart
==========================================
Manages the full onboarding journey from org chart setup through
individual onboarding to the no-code workflow builder. Implements
agentic corporate positions, shadow agent assignment, and IP
classification for employees, business, and system.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class OnboardingPhase(Enum):
    """Phases of the onboarding flow."""
    ORG_SETUP = "org_setup"
    POSITION_DEFINITION = "position_definition"
    INDIVIDUAL_ONBOARDING = "individual_onboarding"
    SHADOW_AGENT_ASSIGNMENT = "shadow_agent_assignment"
    WORKFLOW_BUILDER_TRANSITION = "workflow_builder_transition"
    COMPLETED = "completed"


class PositionLevel(Enum):
    """Corporate hierarchy levels."""
    C_SUITE = "c_suite"
    VP = "vp"
    DIRECTOR = "director"
    MANAGER = "manager"
    LEAD = "lead"
    INDIVIDUAL_CONTRIBUTOR = "individual_contributor"
    INTERN = "intern"


class DepartmentType(Enum):
    """Standard corporate departments."""
    EXECUTIVE = "executive"
    ENGINEERING = "engineering"
    PRODUCT = "product"
    SALES = "sales"
    MARKETING = "marketing"
    FINANCE = "finance"
    HR = "hr"
    OPERATIONS = "operations"
    LEGAL = "legal"
    CUSTOMER_SUCCESS = "customer_success"
    IT = "it"
    RESEARCH = "research"


@dataclass
class OrgPosition:
    """A position in the corporate org chart."""
    position_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str = ""
    level: PositionLevel = PositionLevel.INDIVIDUAL_CONTRIBUTOR
    department: DepartmentType = DepartmentType.ENGINEERING
    reports_to: Optional[str] = None  # position_id of manager
    direct_reports: list = field(default_factory=list)
    responsibilities: list = field(default_factory=list)
    automation_scope: list = field(default_factory=list)
    shadow_agent_config: dict = field(default_factory=dict)
    is_agentic: bool = True  # Whether this position has an agentic shadow

    def to_dict(self) -> dict:
        return {
            "position_id": self.position_id,
            "title": self.title,
            "level": self.level.value,
            "department": self.department.value,
            "reports_to": self.reports_to,
            "direct_reports": self.direct_reports,
            "responsibilities": self.responsibilities,
            "automation_scope": self.automation_scope,
            "shadow_agent_config": self.shadow_agent_config,
            "is_agentic": self.is_agentic,
        }


@dataclass
class OnboardingQuestion:
    """A question for onboarding an individual."""
    question_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    question: str = ""
    category: str = "general"
    required: bool = True
    answer: Optional[str] = None
    options: list = field(default_factory=list)
    help_text: str = ""
    order: int = 0

    def to_dict(self) -> dict:
        return {
            "question_id": self.question_id,
            "question": self.question,
            "category": self.category,
            "required": self.required,
            "answer": self.answer,
            "options": self.options,
            "help_text": self.help_text,
            "order": self.order,
        }


@dataclass
class ShadowAgentProfile:
    """Shadow agent assigned to an individual - becomes employee IP."""
    shadow_id: str = field(default_factory=lambda: f"shadow-{str(uuid.uuid4())[:8]}")
    employee_id: str = ""
    position_id: str = ""
    capabilities: list = field(default_factory=list)
    learning_data: dict = field(default_factory=dict)
    automation_patterns: list = field(default_factory=list)
    ip_classification: str = "employee_ip"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "shadow_id": self.shadow_id,
            "employee_id": self.employee_id,
            "position_id": self.position_id,
            "capabilities": self.capabilities,
            "learning_data": self.learning_data,
            "automation_patterns": self.automation_patterns,
            "ip_classification": self.ip_classification,
            "created_at": self.created_at,
        }


@dataclass
class OnboardingSession:
    """A complete onboarding session for an individual."""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    phase: OnboardingPhase = OnboardingPhase.ORG_SETUP
    employee_name: str = ""
    employee_email: str = ""
    position_id: Optional[str] = None
    shadow_agent: Optional[ShadowAgentProfile] = None
    questions_answered: dict = field(default_factory=dict)
    workflow_builder_session_id: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "phase": self.phase.value,
            "employee_name": self.employee_name,
            "employee_email": self.employee_email,
            "position_id": self.position_id,
            "shadow_agent": self.shadow_agent.to_dict() if self.shadow_agent else None,
            "questions_answered": self.questions_answered,
            "workflow_builder_session_id": self.workflow_builder_session_id,
            "created_at": self.created_at,
        }


# --- Default org chart positions ---
DEFAULT_ORG_POSITIONS = [
    {
        "title": "Chief Executive Officer",
        "level": PositionLevel.C_SUITE,
        "department": DepartmentType.EXECUTIVE,
        "responsibilities": ["Strategic direction", "Company vision", "Executive oversight"],
        "automation_scope": ["executive_reporting", "strategic_dashboards", "board_communications"],
    },
    {
        "title": "Chief Technology Officer",
        "level": PositionLevel.C_SUITE,
        "department": DepartmentType.ENGINEERING,
        "responsibilities": ["Technology strategy", "Engineering leadership", "Architecture decisions"],
        "automation_scope": ["tech_stack_monitoring", "engineering_metrics", "deployment_oversight"],
    },
    {
        "title": "Chief Operations Officer",
        "level": PositionLevel.C_SUITE,
        "department": DepartmentType.OPERATIONS,
        "responsibilities": ["Operations management", "Process optimization", "Resource allocation"],
        "automation_scope": ["operations_monitoring", "resource_tracking", "process_automation"],
    },
    {
        "title": "Chief Financial Officer",
        "level": PositionLevel.C_SUITE,
        "department": DepartmentType.FINANCE,
        "responsibilities": ["Financial strategy", "Budget management", "Investor relations"],
        "automation_scope": ["financial_reporting", "budget_tracking", "compliance_monitoring"],
    },
    {
        "title": "VP of Engineering",
        "level": PositionLevel.VP,
        "department": DepartmentType.ENGINEERING,
        "responsibilities": ["Engineering teams", "Technical roadmap", "Hiring"],
        "automation_scope": ["sprint_tracking", "code_quality", "team_metrics"],
    },
    {
        "title": "VP of Sales",
        "level": PositionLevel.VP,
        "department": DepartmentType.SALES,
        "responsibilities": ["Sales strategy", "Revenue targets", "Client relationships"],
        "automation_scope": ["pipeline_tracking", "lead_scoring", "deal_monitoring"],
    },
    {
        "title": "VP of Product",
        "level": PositionLevel.VP,
        "department": DepartmentType.PRODUCT,
        "responsibilities": ["Product roadmap", "Feature prioritization", "User research"],
        "automation_scope": ["feature_tracking", "user_analytics", "feedback_processing"],
    },
    {
        "title": "Engineering Manager",
        "level": PositionLevel.MANAGER,
        "department": DepartmentType.ENGINEERING,
        "responsibilities": ["Team management", "Sprint planning", "Code reviews"],
        "automation_scope": ["ci_cd_monitoring", "pr_tracking", "incident_response"],
    },
    {
        "title": "Product Manager",
        "level": PositionLevel.MANAGER,
        "department": DepartmentType.PRODUCT,
        "responsibilities": ["Feature specs", "Stakeholder management", "Release planning"],
        "automation_scope": ["backlog_management", "release_tracking", "stakeholder_updates"],
    },
    {
        "title": "Sales Manager",
        "level": PositionLevel.MANAGER,
        "department": DepartmentType.SALES,
        "responsibilities": ["Team targets", "Client meetings", "Pipeline management"],
        "automation_scope": ["crm_monitoring", "deal_tracking", "quota_reporting"],
    },
    {
        "title": "Software Engineer",
        "level": PositionLevel.INDIVIDUAL_CONTRIBUTOR,
        "department": DepartmentType.ENGINEERING,
        "responsibilities": ["Feature development", "Bug fixes", "Code quality"],
        "automation_scope": ["build_monitoring", "test_automation", "deployment_triggers"],
    },
    {
        "title": "Sales Representative",
        "level": PositionLevel.INDIVIDUAL_CONTRIBUTOR,
        "department": DepartmentType.SALES,
        "responsibilities": ["Lead outreach", "Demo presentations", "Deal closing"],
        "automation_scope": ["lead_follow_up", "email_sequences", "meeting_scheduling"],
    },
]

# --- Default onboarding questions ---
DEFAULT_ONBOARDING_QUESTIONS = [
    OnboardingQuestion(
        question="What is your full name?",
        category="personal",
        required=True,
        help_text="Enter your legal full name as it appears on official documents.",
        order=1,
    ),
    OnboardingQuestion(
        question="What is your work email?",
        category="personal",
        required=True,
        help_text="Your corporate email address for all system communications.",
        order=2,
    ),
    OnboardingQuestion(
        question="Which department will you be joining?",
        category="role",
        required=True,
        options=[d.value for d in DepartmentType],
        help_text="Select the department you'll be working in.",
        order=3,
    ),
    OnboardingQuestion(
        question="What is your position/title?",
        category="role",
        required=True,
        help_text="Your official job title.",
        order=4,
    ),
    OnboardingQuestion(
        question="Who is your direct manager?",
        category="role",
        required=True,
        help_text="Name or email of your reporting manager.",
        order=5,
    ),
    OnboardingQuestion(
        question="What are your primary responsibilities?",
        category="responsibilities",
        required=True,
        help_text="Describe your main job responsibilities in a few sentences.",
        order=6,
    ),
    OnboardingQuestion(
        question="Which tools and systems do you use regularly?",
        category="tools",
        required=False,
        options=["GitHub", "Jira", "Slack", "Salesforce", "HubSpot", "Confluence", "Figma", "Excel", "Custom CRM", "Other"],
        help_text="Select all that apply. These help configure your shadow agent.",
        order=7,
    ),
    OnboardingQuestion(
        question="What repetitive tasks would you like automated?",
        category="automation",
        required=False,
        help_text="Describe any repetitive work you'd like your shadow agent to help with.",
        order=8,
    ),
    OnboardingQuestion(
        question="What is your preferred communication style for notifications?",
        category="preferences",
        required=False,
        options=["Email", "Slack", "SMS", "In-app notification", "Dashboard only"],
        help_text="How should your shadow agent notify you of updates?",
        order=9,
    ),
    OnboardingQuestion(
        question="Do you have any compliance or security requirements for your role?",
        category="security",
        required=False,
        options=["HIPAA", "SOC2", "GDPR", "PCI-DSS", "ISO27001", "None specific"],
        help_text="Compliance frameworks that apply to your work.",
        order=10,
    ),
]


class CorporateOrgChart:
    """
    Manages the corporate org chart with agentic positions.
    The org chart structure becomes Business IP - representing
    how the organization's systems interact.
    """

    def __init__(self):
        self.positions: dict[str, OrgPosition] = {}
        self.ip_classification = "business_ip"

    def setup_default_org(self) -> list[OrgPosition]:
        """Set up the default corporate org chart."""
        created = []
        position_map = {}

        for pos_def in DEFAULT_ORG_POSITIONS:
            pos = OrgPosition(
                title=pos_def["title"],
                level=pos_def["level"],
                department=pos_def["department"],
                responsibilities=pos_def["responsibilities"],
                automation_scope=pos_def["automation_scope"],
                shadow_agent_config={
                    "monitoring_level": "full" if pos_def["level"] in [PositionLevel.C_SUITE, PositionLevel.VP] else "standard",
                    "auto_escalation": pos_def["level"] in [PositionLevel.C_SUITE, PositionLevel.VP],
                },
            )
            self.positions[pos.position_id] = pos
            position_map[pos.title] = pos.position_id
            created.append(pos)

        # Set up reporting relationships
        self._setup_reporting_chains(position_map)
        return created

    def _setup_reporting_chains(self, position_map: dict):
        """Establish reporting relationships between positions."""
        ceo_id = position_map.get("Chief Executive Officer")
        cto_id = position_map.get("Chief Technology Officer")
        coo_id = position_map.get("Chief Operations Officer")
        cfo_id = position_map.get("Chief Financial Officer")
        vp_eng_id = position_map.get("VP of Engineering")
        vp_sales_id = position_map.get("VP of Sales")
        vp_product_id = position_map.get("VP of Product")
        eng_mgr_id = position_map.get("Engineering Manager")
        prod_mgr_id = position_map.get("Product Manager")
        sales_mgr_id = position_map.get("Sales Manager")

        # C-suite reports to CEO
        for pid in [cto_id, coo_id, cfo_id]:
            if pid and ceo_id:
                self.positions[pid].reports_to = ceo_id
                self.positions[ceo_id].direct_reports.append(pid)

        # VPs report to relevant C-suite
        if vp_eng_id and cto_id:
            self.positions[vp_eng_id].reports_to = cto_id
            self.positions[cto_id].direct_reports.append(vp_eng_id)
        if vp_sales_id and coo_id:
            self.positions[vp_sales_id].reports_to = coo_id
            self.positions[coo_id].direct_reports.append(vp_sales_id)
        if vp_product_id and cto_id:
            self.positions[vp_product_id].reports_to = cto_id
            self.positions[cto_id].direct_reports.append(vp_product_id)

        # Managers report to VPs
        if eng_mgr_id and vp_eng_id:
            self.positions[eng_mgr_id].reports_to = vp_eng_id
            self.positions[vp_eng_id].direct_reports.append(eng_mgr_id)
        if prod_mgr_id and vp_product_id:
            self.positions[prod_mgr_id].reports_to = vp_product_id
            self.positions[vp_product_id].direct_reports.append(prod_mgr_id)
        if sales_mgr_id and vp_sales_id:
            self.positions[sales_mgr_id].reports_to = vp_sales_id
            self.positions[vp_sales_id].direct_reports.append(sales_mgr_id)

        # ICs report to managers
        for pos in self.positions.values():
            if pos.level == PositionLevel.INDIVIDUAL_CONTRIBUTOR:
                if pos.department == DepartmentType.ENGINEERING and eng_mgr_id:
                    pos.reports_to = eng_mgr_id
                    self.positions[eng_mgr_id].direct_reports.append(pos.position_id)
                elif pos.department == DepartmentType.SALES and sales_mgr_id:
                    pos.reports_to = sales_mgr_id
                    self.positions[sales_mgr_id].direct_reports.append(pos.position_id)

    def add_position(
        self,
        title: str,
        level: str,
        department: str,
        reports_to: Optional[str] = None,
        responsibilities: Optional[list] = None,
        automation_scope: Optional[list] = None,
    ) -> OrgPosition:
        """Add a new position to the org chart."""
        pos_level = PositionLevel.INDIVIDUAL_CONTRIBUTOR
        for l in PositionLevel:
            if l.value == level:
                pos_level = l
                break

        dept = DepartmentType.ENGINEERING
        for d in DepartmentType:
            if d.value == department:
                dept = d
                break

        pos = OrgPosition(
            title=title,
            level=pos_level,
            department=dept,
            reports_to=reports_to,
            responsibilities=responsibilities or [],
            automation_scope=automation_scope or [],
            shadow_agent_config={
                "monitoring_level": "full" if pos_level in [PositionLevel.C_SUITE, PositionLevel.VP] else "standard",
                "auto_escalation": pos_level in [PositionLevel.C_SUITE, PositionLevel.VP],
            },
        )
        self.positions[pos.position_id] = pos

        # Update reporting chain
        if reports_to and reports_to in self.positions:
            self.positions[reports_to].direct_reports.append(pos.position_id)

        return pos

    def get_position(self, position_id: str) -> Optional[OrgPosition]:
        """Get a position by ID."""
        return self.positions.get(position_id)

    def get_org_chart(self) -> dict:
        """Get the full org chart as a hierarchical dict."""
        roots = [p for p in self.positions.values() if p.reports_to is None]
        chart = {
            "ip_classification": self.ip_classification,
            "total_positions": len(self.positions),
            "hierarchy": [self._build_hierarchy(r) for r in roots],
        }
        return chart

    def _build_hierarchy(self, position: OrgPosition) -> dict:
        """Build a hierarchical representation from a position."""
        result = position.to_dict()
        result["children"] = []
        for child_id in position.direct_reports:
            child = self.positions.get(child_id)
            if child:
                result["children"].append(self._build_hierarchy(child))
        return result

    def get_department_positions(self, department: str) -> list[dict]:
        """Get all positions in a department."""
        return [
            p.to_dict() for p in self.positions.values()
            if p.department.value == department
        ]

    def list_positions(self) -> list[dict]:
        """List all positions."""
        return [p.to_dict() for p in self.positions.values()]


class OnboardingFlow:
    """
    Manages the complete onboarding flow from org chart setup
    through individual onboarding to the no-code workflow builder.
    """

    def __init__(self):
        self.org_chart = CorporateOrgChart()
        self.sessions: dict[str, OnboardingSession] = {}
        self.shadow_agents: dict[str, ShadowAgentProfile] = {}
        self.questions = list(DEFAULT_ONBOARDING_QUESTIONS)

    def initialize_org(self) -> dict:
        """Initialize the org chart with default positions."""
        positions = self.org_chart.setup_default_org()
        return {
            "phase": OnboardingPhase.ORG_SETUP.value,
            "positions_created": len(positions),
            "org_chart": self.org_chart.get_org_chart(),
            "next_phase": OnboardingPhase.INDIVIDUAL_ONBOARDING.value,
            "message": (
                f"Organization chart initialized with {len(positions)} positions. "
                f"Ready for individual onboarding."
            ),
        }

    def start_onboarding(self, employee_name: str, employee_email: str) -> OnboardingSession:
        """Start an onboarding session for a new individual."""
        session = OnboardingSession(
            employee_name=employee_name,
            employee_email=employee_email,
            phase=OnboardingPhase.INDIVIDUAL_ONBOARDING,
        )
        self.sessions[session.session_id] = session
        return session

    def get_questions(self, session_id: str) -> list[dict]:
        """Get onboarding questions for a session."""
        session = self.sessions.get(session_id)
        if not session:
            return []

        return [q.to_dict() for q in sorted(self.questions, key=lambda x: x.order)]

    def answer_question(self, session_id: str, question_id: str, answer: str) -> dict:
        """Record an answer to an onboarding question."""
        session = self.sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}

        for q in self.questions:
            if q.question_id == question_id:
                session.questions_answered[question_id] = {
                    "question": q.question,
                    "answer": answer,
                    "category": q.category,
                }
                break

        # Check if all required questions answered
        required = [q for q in self.questions if q.required]
        answered_ids = set(session.questions_answered.keys())
        required_ids = {q.question_id for q in required}
        all_required_done = required_ids.issubset(answered_ids)

        return {
            "session_id": session_id,
            "questions_answered": len(session.questions_answered),
            "total_questions": len(self.questions),
            "required_remaining": len(required_ids - answered_ids),
            "all_required_complete": all_required_done,
            "next_phase": OnboardingPhase.SHADOW_AGENT_ASSIGNMENT.value if all_required_done else None,
        }

    def assign_shadow_agent(self, session_id: str, position_id: Optional[str] = None) -> dict:
        """Assign a shadow agent to the onboarded individual."""
        session = self.sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}

        # Determine capabilities from answers
        capabilities = self._infer_capabilities(session)

        shadow = ShadowAgentProfile(
            employee_id=session.session_id,
            position_id=position_id or "",
            capabilities=capabilities,
            learning_data={
                "onboarding_answers": session.questions_answered,
                "inferred_automation": capabilities,
            },
            automation_patterns=[],
            ip_classification="employee_ip",
        )

        session.shadow_agent = shadow
        session.phase = OnboardingPhase.SHADOW_AGENT_ASSIGNMENT
        self.shadow_agents[shadow.shadow_id] = shadow

        # If position specified, link to org chart
        if position_id:
            session.position_id = position_id
            pos = self.org_chart.get_position(position_id)
            if pos:
                shadow.capabilities.extend(pos.automation_scope)

        return {
            "session_id": session_id,
            "shadow_agent": shadow.to_dict(),
            "ip_classification": "employee_ip",
            "message": (
                f"Shadow agent '{shadow.shadow_id}' assigned to {session.employee_name}. "
                f"This agent learns from {session.employee_name}'s work patterns and "
                f"becomes their intellectual property within the system."
            ),
            "next_phase": OnboardingPhase.WORKFLOW_BUILDER_TRANSITION.value,
        }

    def transition_to_workflow_builder(self, session_id: str) -> dict:
        """Transition from onboarding to the no-code workflow builder."""
        session = self.sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}

        session.phase = OnboardingPhase.WORKFLOW_BUILDER_TRANSITION

        # Generate workflow builder context from onboarding data
        builder_context = {
            "employee_name": session.employee_name,
            "position": None,
            "shadow_agent_id": session.shadow_agent.shadow_id if session.shadow_agent else None,
            "suggested_automations": [],
        }

        if session.position_id:
            pos = self.org_chart.get_position(session.position_id)
            if pos:
                builder_context["position"] = pos.to_dict()
                builder_context["suggested_automations"] = pos.automation_scope

        # Add automation suggestions from answers
        automation_answer = None
        for qa in session.questions_answered.values():
            if qa.get("category") == "automation":
                automation_answer = qa.get("answer", "")
                break

        if automation_answer:
            builder_context["user_automation_request"] = automation_answer

        session.phase = OnboardingPhase.COMPLETED

        return {
            "session_id": session_id,
            "phase": "workflow_builder_transition",
            "builder_context": builder_context,
            "message": (
                f"Onboarding complete for {session.employee_name}! "
                f"Transitioning to the No-Code Workflow Builder. "
                f"Your shadow agent is ready to learn from your work patterns."
            ),
        }

    def _infer_capabilities(self, session: OnboardingSession) -> list:
        """Infer automation capabilities from onboarding answers."""
        capabilities = []
        for qa in session.questions_answered.values():
            answer = qa.get("answer", "").lower()
            category = qa.get("category", "")

            if category == "tools":
                if "github" in answer:
                    capabilities.append("code_management")
                if "jira" in answer:
                    capabilities.append("project_tracking")
                if "slack" in answer:
                    capabilities.append("communication_automation")
                if "salesforce" in answer or "hubspot" in answer:
                    capabilities.append("crm_automation")
                if "excel" in answer:
                    capabilities.append("data_processing")

            if category == "automation":
                if any(w in answer for w in ["email", "message", "notify"]):
                    capabilities.append("notification_automation")
                if any(w in answer for w in ["report", "dashboard", "analytics"]):
                    capabilities.append("reporting_automation")
                if any(w in answer for w in ["schedule", "meeting", "calendar"]):
                    capabilities.append("scheduling_automation")

        return list(set(capabilities))

    def get_session(self, session_id: str) -> Optional[OnboardingSession]:
        """Get an onboarding session."""
        return self.sessions.get(session_id)

    def list_sessions(self) -> list[dict]:
        """List all onboarding sessions."""
        return [s.to_dict() for s in self.sessions.values()]

    def get_shadow_agents(self) -> list[dict]:
        """List all shadow agents."""
        return [s.to_dict() for s in self.shadow_agents.values()]
