"""
No-Code Workflow Librarian Terminal
====================================
Conversational interface for building workflows through natural language.
The Librarian infers configuration, creates steps in real-time, and shows
the automation being built step by step. Each agent's role and monitoring
status is visible throughout the process.

Modes
-----
The Librarian operates in one of four **modes** that shape its guidance level:

* ``ASK``        — Direct answers, no guiding questions. Escalation to Triage
                   available at any point.
* ``ONBOARDING`` — Wizard-style guided flow with step-by-step prompts.
* ``PRODUCTION`` — Minimal friction; assumes the user knows what they want.
* ``ASSISTANT``  — Personality-driven; each assistant surface can supply its
                   own guidance profile.

Triage Escalation
-----------------
Any conversation can be escalated to **Triage** — Murphy's equivalent of
promoting a chat into an actionable task.  Triage analyses the session
context, generates a structured workflow via ``AIWorkflowGenerator``, and
returns a ``TriageResult`` ready for the execution engine.
"""

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ConversationState(Enum):
    """States of the librarian conversation."""
    GREETING = "greeting"
    GATHERING_REQUIREMENTS = "gathering_requirements"
    INFERRING_WORKFLOW = "inferring_workflow"
    BUILDING_STEPS = "building_steps"
    REVIEWING = "reviewing"
    CONFIGURING_AGENTS = "configuring_agents"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    TRIAGE = "triage"  # escalated to execution analysis


class LibrarianMode(Enum):
    """Operating mode that controls guidance level and conversational behaviour.

    Attributes:
        ASK:        No guiding questions.  The Librarian answers directly and
                    can escalate to Triage at any moment.
        ONBOARDING: Full wizard-style guided flow with step-by-step prompts.
        PRODUCTION: Minimal friction; assumes the operator knows what they
                    want — skips confirmatory questions.
        ASSISTANT:  Personality-driven surface (e.g. sales assistant, HR
                    assistant).  The caller supplies an ``assistant_profile``
                    dict to customise tone and focus area.
    """
    ASK = "ask"
    ONBOARDING = "onboarding"
    PRODUCTION = "production"
    ASSISTANT = "assistant"


class TriageStatus(Enum):
    """Outcome of a triage escalation attempt."""
    READY = "ready"          # workflow generated, ready for execution
    NEEDS_INFO = "needs_info"  # not enough context to generate a workflow
    ESCALATED = "escalated"  # already submitted to execution engine
    FAILED = "failed"        # triage analysis failed


@dataclass
class TriageResult:
    """Result of escalating a Librarian session to Triage.

    Attributes:
        triage_id:   Unique identifier for this triage event.
        session_id:  Source Librarian session.
        status:      :class:`TriageStatus` outcome.
        workflow_def: Generated workflow definition dict (from
                      ``AIWorkflowGenerator``), or ``None``.
        command:     Best-matching slash command from the Librarian's
                     ``generate_command()``, if available.
        setpoints:   Extracted parameter values.
        confidence:  Confidence that the workflow represents user intent.
        summary:     Human-readable summary of what will be executed.
        missing_info: List of fields the user needs to supply before
                      execution can proceed (populated when
                      ``status == NEEDS_INFO``).
        created_at:  ISO-8601 timestamp.
    """
    triage_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    session_id: str = ""
    status: TriageStatus = TriageStatus.NEEDS_INFO
    workflow_def: Optional[Dict[str, Any]] = None
    command: str = ""
    setpoints: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    summary: str = ""
    missing_info: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "triage_id": self.triage_id,
            "session_id": self.session_id,
            "status": self.status.value,
            "workflow_def": self.workflow_def,
            "command": self.command,
            "setpoints": self.setpoints,
            "confidence": round(self.confidence, 4),
            "summary": self.summary,
            "missing_info": self.missing_info,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# Per-mode behaviour profiles
# ---------------------------------------------------------------------------

#: How many guided questions each mode asks before building steps.
#: ``None`` means unlimited — the wizard keeps asking until the user
#: explicitly finishes or all required categories are covered.
_MODE_QUESTION_BUDGET: Dict[str, Optional[int]] = {
    LibrarianMode.ASK.value:        0,      # zero — answer directly
    LibrarianMode.ONBOARDING.value: None,   # unlimited — as many as needed
    LibrarianMode.PRODUCTION.value: None,   # unlimited — deliverable wizard
    LibrarianMode.ASSISTANT.value:  2,      # moderate
}

#: Whether each mode skips the GATHERING_REQUIREMENTS state entirely.
_MODE_SKIP_GATHERING: Dict[str, bool] = {
    LibrarianMode.ASK.value:        True,
    LibrarianMode.ONBOARDING.value: False,
    LibrarianMode.PRODUCTION.value: False,
    LibrarianMode.ASSISTANT.value:  False,
}

_MODE_GREETINGS: Dict[str, str] = {
    LibrarianMode.ASK.value: (
        "Ready. I'm your Librarian — describe what you need and I'll generate "
        "the command or workflow directly. "
        "Say 'triage' at any point to escalate to execution."
    ),
    LibrarianMode.ONBOARDING.value: (
        "Welcome! I'm your Librarian. I'll guide you through setting up your Murphy System — "
        "this may take a few questions so I can build the right automations for you. "
        "Let's start: what is your name?"
    ),
    LibrarianMode.PRODUCTION.value: (
        "Production Wizard ready. What would you like to produce today? "
        "(report / dashboard / workflow / document / api_integration / analysis / automation / org_chart)"
    ),
    LibrarianMode.ASSISTANT.value: (
        "Hello! I'm your Murphy assistant. How can I help you today?"
    ),
}

#: Triage trigger words — any of these in a message signal an escalation request.
#: Deliberately specific to avoid false positives on common words.
#: Single-word triggers must appear as whole words (checked with word-boundary logic
#: in send_message); multi-word triggers require the full phrase.
_TRIAGE_TRIGGERS = frozenset([
    "triage",
    "execute now",
    "run it now",
    "run now",
    "deploy now",
    "make it happen",
    "start execution",
    "go ahead and execute",
    "escalate to execution",
    "escalate this",
    "submit for execution",
    "approve and run",
])


class StepVisibility(Enum):
    """Visibility of workflow step creation."""
    CREATING = "creating"
    CONFIGURED = "configured"
    AGENT_ASSIGNED = "agent_assigned"
    MONITORING_ACTIVE = "monitoring_active"
    VALIDATED = "validated"


# ---------------------------------------------------------------------------
# Triage confidence weighting policy
# ---------------------------------------------------------------------------

#: Weight of the workflow-generation score in the combined triage confidence.
_TRIAGE_WORKFLOW_WEIGHT: float = 0.6
#: Weight of the Librarian command-match score in the combined triage confidence.
_TRIAGE_COMMAND_WEIGHT: float = 0.4


@dataclass
class WorkflowStep:
    """A single step in the workflow being built."""
    step_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    step_type: str = "action"
    description: str = ""
    config: dict = field(default_factory=dict)
    agent_assigned: Optional[str] = None
    monitoring_config: dict = field(default_factory=dict)
    visibility: StepVisibility = StepVisibility.CREATING
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    dependencies: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id,
            "name": self.name,
            "step_type": self.step_type,
            "description": self.description,
            "config": self.config,
            "agent_assigned": self.agent_assigned,
            "monitoring_config": self.monitoring_config,
            "visibility": self.visibility.value,
            "created_at": self.created_at,
            "dependencies": self.dependencies,
        }


@dataclass
class AgentAssignment:
    """Agent assignment for monitoring a workflow step."""
    agent_id: str = field(default_factory=lambda: f"agent-{str(uuid.uuid4())[:8]}")
    agent_role: str = "monitor"
    step_id: str = ""
    monitoring_type: str = "passive"
    metrics_tracked: list = field(default_factory=list)
    alert_thresholds: dict = field(default_factory=dict)
    status: str = "assigned"

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "agent_role": self.agent_role,
            "step_id": self.step_id,
            "monitoring_type": self.monitoring_type,
            "metrics_tracked": self.metrics_tracked,
            "alert_thresholds": self.alert_thresholds,
            "status": self.status,
        }


@dataclass
class ConversationTurn:
    """A single turn in the conversation."""
    turn_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    role: str = "user"  # user or librarian
    message: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    actions_taken: list = field(default_factory=list)
    steps_created: list = field(default_factory=list)
    inferences_made: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "turn_id": self.turn_id,
            "role": self.role,
            "message": self.message,
            "timestamp": self.timestamp,
            "actions_taken": self.actions_taken,
            "steps_created": self.steps_created,
            "inferences_made": self.inferences_made,
        }


@dataclass
class LibrarianSession:
    """A complete session with the Librarian."""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    state: ConversationState = ConversationState.GREETING
    mode: LibrarianMode = LibrarianMode.ASK
    assistant_profile: Dict[str, Any] = field(default_factory=dict)
    workflow_name: str = ""
    workflow_description: str = ""
    steps: list = field(default_factory=list)
    agent_assignments: list = field(default_factory=list)
    conversation_history: list = field(default_factory=list)
    requirements_gathered: dict = field(default_factory=dict)
    inferences: list = field(default_factory=list)
    triage_history: List[Dict[str, Any]] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Onboarding / Production wizard fields
    # ------------------------------------------------------------------

    #: Snapshot of onboarding answers — injected when a PRODUCTION session
    #: is created so the production wizard can skip redundant questions.
    onboarding_context: Dict[str, Any] = field(default_factory=dict)

    #: Structured Q&A captured during ONBOARDING or PRODUCTION wizard flows.
    #: Keys are question ``category`` values; values are answer strings.
    wizard_answers: Dict[str, str] = field(default_factory=dict)

    #: Categories the ONBOARDING wizard has fully covered.
    onboarding_categories_done: List[str] = field(default_factory=list)

    #: DeliverableWizard session_id — populated when PRODUCTION mode starts.
    deliverable_session_id: Optional[str] = None

    #: OrgChartGenerator session_id — populated when org_chart deliverable chosen.
    org_chart_session_id: Optional[str] = None

    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "state": self.state.value,
            "mode": self.mode.value,
            "workflow_name": self.workflow_name,
            "workflow_description": self.workflow_description,
            "steps": [s.to_dict() if hasattr(s, 'to_dict') else s for s in self.steps],
            "agent_assignments": [a.to_dict() if hasattr(a, 'to_dict') else a for a in self.agent_assignments],
            "conversation_history": [c.to_dict() if hasattr(c, 'to_dict') else c for c in self.conversation_history],
            "requirements_gathered": self.requirements_gathered,
            "inferences": self.inferences,
            "triage_history": self.triage_history,
            "wizard_answers": self.wizard_answers,
            "onboarding_context": self.onboarding_context,
            "onboarding_categories_done": self.onboarding_categories_done,
            "deliverable_session_id": self.deliverable_session_id,
            "org_chart_session_id": self.org_chart_session_id,
            "created_at": self.created_at,
        }


# --- Intent and inference keywords ---
INTENT_KEYWORDS = {
    "data_processing": ["process", "transform", "etl", "pipeline", "data", "extract", "load", "clean", "parse", "csv", "json", "database"],
    "notification": ["notify", "alert", "email", "send", "message", "slack", "teams", "sms", "webhook"],
    "monitoring": ["monitor", "watch", "track", "observe", "check", "health", "status", "uptime"],
    "scheduling": ["schedule", "cron", "daily", "weekly", "hourly", "recurring", "timer", "periodic"],
    "api_integration": ["api", "rest", "endpoint", "integrate", "connect", "fetch", "request", "webhook"],
    "content_generation": ["generate", "create", "write", "report", "document", "template", "pdf"],
    "security": ["security", "scan", "audit", "compliance", "encrypt", "protect", "firewall", "access"],
    "deployment": ["deploy", "release", "build", "ci", "cd", "container", "docker", "kubernetes"],
    "approval": ["approve", "review", "sign-off", "authorize", "validate", "confirm"],
    "onboarding": ["onboard", "welcome", "new hire", "employee", "setup", "account", "provision"],
}

STEP_TEMPLATES = {
    "data_processing": {
        "name": "Data Processing",
        "step_type": "transform",
        "config": {"operation": "transform", "format": "auto"},
        "monitoring": {"metrics": ["records_processed", "error_rate", "throughput"], "type": "active"},
    },
    "notification": {
        "name": "Send Notification",
        "step_type": "action",
        "config": {"channel": "auto", "template": "default"},
        "monitoring": {"metrics": ["delivery_rate", "response_time"], "type": "passive"},
    },
    "monitoring": {
        "name": "System Monitor",
        "step_type": "action",
        "config": {"interval": "5m", "targets": []},
        "monitoring": {"metrics": ["availability", "latency", "error_count"], "type": "active"},
    },
    "scheduling": {
        "name": "Scheduled Task",
        "step_type": "action",
        "config": {"schedule": "auto", "timezone": "UTC"},
        "monitoring": {"metrics": ["execution_count", "success_rate", "drift"], "type": "active"},
    },
    "api_integration": {
        "name": "API Integration",
        "step_type": "connector",
        "config": {"method": "GET", "url": "", "auth": "auto"},
        "monitoring": {"metrics": ["response_time", "status_code", "payload_size"], "type": "active"},
    },
    "content_generation": {
        "name": "Content Generator",
        "step_type": "action",
        "config": {"output_format": "auto", "template": ""},
        "monitoring": {"metrics": ["generation_time", "quality_score"], "type": "passive"},
    },
    "security": {
        "name": "Security Check",
        "step_type": "action",
        "config": {"scan_type": "auto", "severity_threshold": "medium"},
        "monitoring": {"metrics": ["vulnerabilities_found", "scan_duration", "compliance_score"], "type": "active"},
    },
    "deployment": {
        "name": "Deployment Step",
        "step_type": "action",
        "config": {"target": "auto", "strategy": "rolling"},
        "monitoring": {"metrics": ["deployment_time", "rollback_count", "health_check"], "type": "active"},
    },
    "approval": {
        "name": "Approval Gate",
        "step_type": "condition",
        "config": {"approvers": [], "timeout": "24h"},
        "monitoring": {"metrics": ["approval_time", "rejection_rate"], "type": "passive"},
    },
    "onboarding": {
        "name": "Onboarding Step",
        "step_type": "action",
        "config": {"tasks": [], "role_based": True},
        "monitoring": {"metrics": ["completion_rate", "time_to_complete"], "type": "passive"},
    },
}


class NoCodeWorkflowTerminal:
    """
    Conversational terminal for building workflows through natural language.
    The Librarian infers what to build, shows each step being created,
    assigns agents for monitoring, and provides real-time visibility.

    Modes control guidance level (see :class:`LibrarianMode`):

    * ``ASK`` — no guided questions, direct answers, triage on request.
    * ``ONBOARDING`` — full wizard flow.
    * ``PRODUCTION`` — one clarifying question maximum.
    * ``ASSISTANT`` — personality-driven; pass ``assistant_profile`` to
      :meth:`create_session`.
    """

    def __init__(self):
        self.sessions: dict[str, LibrarianSession] = {}
        self.max_sessions = 100
        self._deliverable_wizards: Dict[str, Any] = {}
        self._org_chart_generators: Dict[str, Any] = {}

    def create_session(
        self,
        mode: LibrarianMode = LibrarianMode.ASK,
        assistant_profile: Optional[Dict[str, Any]] = None,
        onboarding_context: Optional[Dict[str, Any]] = None,
    ) -> LibrarianSession:
        """Create a new Librarian session.

        Args:
            mode: Operating mode that controls guidance behaviour.
            assistant_profile: Optional personality dict for
                ``ASSISTANT`` mode (e.g. ``{"name": "HR Bot", "focus": "hr"}``).
            onboarding_context: Optional dict of onboarding answers to inject
                into a PRODUCTION session so already-answered questions are
                pre-filled (e.g. ``{"tools": "github,slack", "position": "engineer"}``).

        Returns:
            A fresh :class:`LibrarianSession`.
        """
        if len(self.sessions) >= self.max_sessions:
            oldest_key = min(self.sessions, key=lambda k: self.sessions[k].created_at)
            del self.sessions[oldest_key]

        session = LibrarianSession(
            mode=mode,
            assistant_profile=assistant_profile or {},
            onboarding_context=onboarding_context or {},
        )
        self.sessions[session.session_id] = session

        greeting_text = _MODE_GREETINGS.get(mode.value, _MODE_GREETINGS[LibrarianMode.ASK.value])
        # ASSISTANT mode can override the greeting from the profile
        if mode == LibrarianMode.ASSISTANT and assistant_profile:
            name = assistant_profile.get("name", "Murphy Assistant")
            focus = assistant_profile.get("focus", "")
            focus_suffix = f" I specialise in {focus}." if focus else ""
            greeting_text = f"Hello! I'm {name}.{focus_suffix} How can I help you today?"

        greeting = ConversationTurn(role="librarian", message=greeting_text)
        session.conversation_history.append(greeting)

        # For PRODUCTION mode: pre-create a DeliverableWizard session so
        # onboarding context can be injected immediately.
        if mode == LibrarianMode.PRODUCTION:
            try:
                from production_deliverable_wizard import DeliverableWizard  # type: ignore[import]
                dw = DeliverableWizard()
                dw_session = dw.create_session(onboarding_context=session.onboarding_context)
                session.deliverable_session_id = dw_session.session_id
                # Store the wizard in a simple registry on this terminal instance
                if not hasattr(self, "_deliverable_wizards"):
                    self._deliverable_wizards: Dict[str, Any] = {}
                self._deliverable_wizards[session.session_id] = dw
            except Exception as exc:
                logger.debug("Could not initialise DeliverableWizard: %s", exc)

        return session

    def get_session(self, session_id: str) -> Optional[LibrarianSession]:
        """Retrieve an existing session."""
        return self.sessions.get(session_id)

    def send_message(self, session_id: str, user_message: str) -> dict:
        """
        Process a user message and return the Librarian's response
        along with any workflow steps created.

        In **ASK** mode the Librarian skips guided questions and answers
        directly.  Any message containing a triage trigger word (e.g.
        ``"triage"``, ``"execute"``, ``"run it"``) automatically escalates
        to :meth:`triage` and includes the ``TriageResult`` in the response.
        """
        session = self.sessions.get(session_id)
        if not session:
            return {"error": "Session not found", "session_id": session_id}

        # Detect triage escalation trigger
        msg_lower = user_message.lower().strip()
        triage_triggered = any(trigger in msg_lower for trigger in _TRIAGE_TRIGGERS)

        # Record user turn
        user_turn = ConversationTurn(role="user", message=user_message)
        session.conversation_history.append(user_turn)

        if triage_triggered:
            triage_result = self.triage(session_id)
            triage_msg = (
                f"Triage initiated. Status: **{triage_result.status.value}**. "
                f"{triage_result.summary}"
            )
            if triage_result.missing_info:
                triage_msg += f" Missing: {', '.join(triage_result.missing_info)}."
            librarian_turn = ConversationTurn(
                role="librarian",
                message=triage_msg,
                actions_taken=["triage_escalation"],
            )
            session.conversation_history.append(librarian_turn)
            response_dict = {
                "session_id": session_id,
                "state": session.state.value,
                "mode": session.mode.value,
                "message": triage_msg,
                "steps_created": [],
                "workflow_snapshot": self._get_workflow_snapshot(session),
                "agent_status": self._get_agent_status(session),
                "inferences": ["triage_escalation_triggered"],
                "triage": triage_result.to_dict(),
            }
            return response_dict

        # Process based on current state (mode-aware)
        response = self._process_message(session, user_message)

        # Record librarian response
        librarian_turn = ConversationTurn(
            role="librarian",
            message=response["message"],
            actions_taken=response.get("actions", []),
            steps_created=response.get("steps_created", []),
            inferences_made=response.get("inferences", []),
        )
        session.conversation_history.append(librarian_turn)

        return {
            "session_id": session_id,
            "state": session.state.value,
            "mode": session.mode.value,
            "message": response["message"],
            "steps_created": response.get("steps_created", []),
            "workflow_snapshot": self._get_workflow_snapshot(session),
            "agent_status": self._get_agent_status(session),
            "inferences": response.get("inferences", []),
        }

    def _process_message(self, session: LibrarianSession, message: str) -> dict:
        """Route message processing based on conversation state and mode.

        * **ASK** — skips all guided questions; infers and builds immediately.
        * **ONBOARDING** — unlimited guided wizard; ask as many questions as
          needed until all required categories are covered.
        * **PRODUCTION** — unlimited deliverable wizard; routes through
          :class:`production_deliverable_wizard.DeliverableWizard`.
        * **ASSISTANT** — moderate guided questions, then build.
        """
        mode = session.mode

        # ONBOARDING mode: drive the unlimited onboarding wizard
        if mode == LibrarianMode.ONBOARDING:
            return self._handle_onboarding_wizard(session, message)

        # PRODUCTION mode: drive the deliverable wizard
        if mode == LibrarianMode.PRODUCTION:
            return self._handle_production_wizard(session, message)

        # ASK mode: always go straight to description handling (no questions)
        if mode == LibrarianMode.ASK and session.state in (
            ConversationState.GREETING,
            ConversationState.GATHERING_REQUIREMENTS,
        ):
            return self._handle_initial_description(session, message)

        # Handle state transitions (ASSISTANT + fallback)
        if session.state == ConversationState.GREETING:
            return self._handle_initial_description(session, message)
        elif session.state == ConversationState.GATHERING_REQUIREMENTS:
            return self._handle_requirements(session, message)
        elif session.state == ConversationState.BUILDING_STEPS:
            return self._handle_building(session, message)
        elif session.state == ConversationState.REVIEWING:
            return self._handle_review(session, message)
        elif session.state == ConversationState.CONFIGURING_AGENTS:
            return self._handle_agent_config(session, message)
        elif session.state == ConversationState.FINALIZING:
            return self._handle_finalization(session, message)
        elif session.state == ConversationState.TRIAGE:
            return {
                "message": (
                    "This session has been escalated to triage. "
                    "Check the triage result or create a new session."
                ),
                "actions": [],
            }
        elif session.state == ConversationState.COMPLETED:
            return {
                "message": "This workflow has been finalized. Create a new session to build another workflow.",
                "actions": [],
            }
        else:
            return self._handle_initial_description(session, message)

    def _handle_initial_description(self, session: LibrarianSession, message: str) -> dict:
        """Handle the initial workflow description from the user."""
        # Infer intents from the description
        intents = self._infer_intents(message)
        inferences = []
        steps_created = []

        if not intents:
            # No clear intent — ask for clarification regardless of mode.
            # Even in ASK mode, vague messages need more detail before we
            # can build a meaningful workflow.
            session.state = ConversationState.GATHERING_REQUIREMENTS
            return {
                "message": (
                    "I'd like to understand more about what you need. "
                    "Could you describe the specific tasks or processes you want to automate? "
                    "For example: data processing, notifications, API integrations, "
                    "monitoring, deployments, or onboarding workflows."
                ),
                "inferences": ["No clear intent detected - requesting clarification"],
                "actions": ["state_transition:gathering_requirements"],
            }

        # Set workflow metadata
        session.workflow_name = self._generate_workflow_name(message, intents)
        session.workflow_description = message
        session.requirements_gathered["intents"] = intents
        session.requirements_gathered["original_description"] = message

        # Create steps from inferred intents
        for intent in intents:
            step = self._create_step_from_intent(intent, message)
            session.steps.append(step)
            steps_created.append(step.to_dict())
            inferences.append(f"Inferred '{intent}' step from your description")

            # Assign monitoring agent
            agent = self._assign_agent(session, step)
            inferences.append(f"Assigned {agent.agent_role} agent to monitor '{step.name}'")

        session.state = ConversationState.BUILDING_STEPS
        session.inferences.extend(inferences)

        step_summary = "\n".join(
            [f"  • [{s.visibility.value}] {s.name} (Agent: {s.agent_assigned})"
             for s in session.steps]
        )

        return {
            "message": (
                f"I've analyzed your description and created the following workflow "
                f"'{session.workflow_name}':\n\n{step_summary}\n\n"
                f"Each step has a monitoring agent assigned. "
                f"Would you like to:\n"
                f"  1. Add more steps\n"
                f"  2. Configure any step in detail\n"
                f"  3. Review agent monitoring setup\n"
                f"  4. Finalize the workflow"
            ),
            "steps_created": steps_created,
            "inferences": inferences,
            "actions": [f"created_step:{s.step_id}" for s in session.steps],
        }

    def _handle_requirements(self, session: LibrarianSession, message: str) -> dict:
        """Handle additional requirements gathering."""
        intents = self._infer_intents(message)

        if not intents:
            return {
                "message": (
                    "I'm still not sure what to build. Try describing it like:\n"
                    "  • 'I need to process CSV files and send email notifications'\n"
                    "  • 'Monitor our API endpoints and alert on failures'\n"
                    "  • 'Set up an onboarding workflow for new employees'\n"
                    "What specific automation do you need?"
                ),
                "inferences": ["Still gathering requirements"],
                "actions": [],
            }

        # Now we have intents, create the workflow
        session.requirements_gathered["intents"] = intents
        session.requirements_gathered["refined_description"] = message
        return self._handle_initial_description(session, message)

    # ------------------------------------------------------------------
    # ONBOARDING wizard — unlimited structured Q&A
    # ------------------------------------------------------------------

    # The onboarding wizard is driven by these question categories, in order.
    # It asks all required ones plus optional ones that are relevant to the
    # answers already given.  There is NO question budget — it asks as many
    # as needed until all required categories are covered.
    _ONBOARDING_WIZARD_QUESTIONS: List[Dict[str, Any]] = [
        {
            "id": "ob_name",
            "category": "personal",
            "question": "What is your full name?",
            "required": True,
            "help": "This personalises your shadow agent.",
        },
        {
            "id": "ob_role",
            "category": "role",
            "question": "What is your job title or role?",
            "required": True,
            "help": "E.g. 'Software Engineer', 'CEO', 'Sales Manager'.",
        },
        {
            "id": "ob_department",
            "category": "department",
            "question": "Which department are you in?",
            "required": True,
            "options": ["engineering", "product", "sales", "marketing", "finance", "hr", "operations", "legal", "customer_success", "executive", "other"],
            "help": "Determines which workflow templates are pre-loaded for you.",
        },
        {
            "id": "ob_company",
            "category": "company",
            "question": "What is your company name and what does it do?",
            "required": True,
            "help": "E.g. 'Acme Corp — B2B SaaS for HR teams'. Used to seed your shadow agent's context.",
        },
        {
            "id": "ob_manager",
            "category": "reporting",
            "question": "Who is your direct manager? (name or email)",
            "required": True,
            "help": "Sets up the reporting chain for your shadow agent.",
        },
        {
            "id": "ob_responsibilities",
            "category": "responsibilities",
            "question": "What are your 3-5 primary job responsibilities?",
            "required": True,
            "help": "Describe what you actually do day-to-day. Your shadow agent will learn from these.",
        },
        {
            "id": "ob_tools",
            "category": "tools",
            "question": "Which tools and systems do you use regularly?",
            "required": False,
            "options": ["GitHub", "Jira", "Slack", "Salesforce", "HubSpot", "Confluence", "Figma", "Excel", "Google Workspace", "AWS", "Azure", "Custom CRM", "Other"],
            "help": "Your shadow agent will be pre-wired with integrations for these tools.",
        },
        {
            "id": "ob_automation",
            "category": "automation",
            "question": "What repetitive tasks do you want to automate first?",
            "required": False,
            "help": "E.g. 'weekly status reports, lead follow-up emails, ticket triage'. No limit — list as many as you like.",
        },
        {
            "id": "ob_communication",
            "category": "communication_preference",
            "question": "How do you prefer to receive notifications and updates?",
            "required": False,
            "options": ["Slack", "Email", "SMS", "In-app notification", "Dashboard only", "Teams"],
            "help": "Your shadow agent will use this channel for alerts and reports.",
        },
        {
            "id": "ob_compliance",
            "category": "compliance",
            "question": "Are there any compliance or security requirements for your role?",
            "required": False,
            "options": ["HIPAA", "SOC 2", "GDPR", "PCI-DSS", "ISO 27001", "None specific"],
            "help": "Enables compliance gates in your workflows.",
        },
        {
            "id": "ob_goals",
            "category": "goals",
            "question": "What does success look like for you in the next 90 days?",
            "required": False,
            "help": "Your shadow agent will track progress toward these goals and surface relevant automations.",
        },
    ]

    # Required categories that must be answered before ONBOARDING completes
    _ONBOARDING_REQUIRED_CATEGORIES: set = {
        "personal", "role", "department", "company", "reporting", "responsibilities",
    }

    def _handle_onboarding_wizard(
        self,
        session: LibrarianSession,
        message: str,
    ) -> dict:
        """Drive the unlimited ONBOARDING wizard.

        Every call:
        1. Records the user's answer to the last question asked.
        2. Checks which required categories are still uncovered.
        3. Asks the next unanswered question.
        4. When all required categories are done, offers to continue to
           optional questions or transition to the workflow builder.

        The user can type ``done`` at any point to skip remaining optional
        questions and proceed.
        """
        msg_lower = message.lower().strip()

        # Determine which question was last asked (last librarian turn with a "?")
        last_question_id = session.requirements_gathered.get("_last_ob_question_id")

        # Record the answer if a question was pending
        if last_question_id:
            q_def = next(
                (q for q in self._ONBOARDING_WIZARD_QUESTIONS if q["id"] == last_question_id),
                None,
            )
            if q_def:
                category = q_def["category"]
                session.wizard_answers[category] = message
                session.requirements_gathered[f"ob_{category}"] = message
                if category not in session.onboarding_categories_done:
                    session.onboarding_categories_done.append(category)

        # Check if user wants to skip remaining optional questions
        done_words = {"done", "finish", "proceed", "next", "continue", "skip", "build it", "let's go"}
        user_wants_to_proceed = any(w in msg_lower for w in done_words)

        required_remaining = [
            cat for cat in self._ONBOARDING_REQUIRED_CATEGORIES
            if cat not in session.onboarding_categories_done
        ]

        if required_remaining and not user_wants_to_proceed:
            # Find the next required question
            next_q = next(
                (q for q in self._ONBOARDING_WIZARD_QUESTIONS
                 if q["category"] in required_remaining and q["category"] not in session.onboarding_categories_done),
                None,
            )
            if next_q:
                session.requirements_gathered["_last_ob_question_id"] = next_q["id"]
                options_text = ""
                if next_q.get("options"):
                    options_text = f"\n  Options: {', '.join(next_q['options'])}"
                session.state = ConversationState.GATHERING_REQUIREMENTS
                return {
                    "message": f"{next_q['question']}{options_text}\n_{next_q.get('help', '')}_",
                    "inferences": [f"Onboarding: asking '{next_q['category']}' question"],
                    "actions": [f"ob_question:{next_q['id']}"],
                }

        # All required done — try optional questions unless user said done
        if not user_wants_to_proceed:
            optional_q = next(
                (q for q in self._ONBOARDING_WIZARD_QUESTIONS
                 if not q["required"] and q["category"] not in session.onboarding_categories_done),
                None,
            )
            if optional_q:
                session.requirements_gathered["_last_ob_question_id"] = optional_q["id"]
                options_text = ""
                if optional_q.get("options"):
                    options_text = f"\n  Options: {', '.join(optional_q['options'])}"
                session.state = ConversationState.GATHERING_REQUIREMENTS
                return {
                    "message": (
                        f"(Optional — type 'done' to skip) {optional_q['question']}{options_text}\n"
                        f"_{optional_q.get('help', '')}_"
                    ),
                    "inferences": [f"Onboarding: asking optional '{optional_q['category']}' question"],
                    "actions": [f"ob_optional_question:{optional_q['id']}"],
                }

        # Onboarding complete — build shadow agent context and transition
        shadow_capabilities = self._infer_capabilities_from_wizard(session.wizard_answers)
        session.requirements_gathered["shadow_capabilities"] = shadow_capabilities
        session.requirements_gathered["_last_ob_question_id"] = None
        session.state = ConversationState.BUILDING_STEPS

        # Generate a starter workflow description from what we learned
        name = session.wizard_answers.get("personal", "you")
        role = session.wizard_answers.get("role", "your role")
        automation = session.wizard_answers.get("automation", "")
        description = (
            automation
            or f"Workflow for {role} in {session.wizard_answers.get('department', 'your department')}"
        )
        session.workflow_description = description
        session.workflow_name = f"{name}'s {role} Automation"

        # Build steps from capabilities
        intents = self._infer_intents(description) or ["onboarding"]
        for intent in intents:
            step = self._create_step_from_intent(intent, description)
            session.steps.append(step)
            self._assign_agent(session, step)

        categories_summary = ", ".join(session.onboarding_categories_done)
        return {
            "message": (
                f"Onboarding complete! Here's what I've learned about you:\n"
                f"  • Categories captured: {categories_summary}\n"
                f"  • Shadow agent capabilities: {', '.join(shadow_capabilities) or 'configuring...'}\n\n"
                f"I've created an initial workflow based on your answers. "
                f"You can refine it by describing more automation needs, "
                f"say 'review' to inspect it, or 'triage' to send it straight to execution."
            ),
            "inferences": [f"Onboarding wizard complete — {len(session.onboarding_categories_done)} categories captured"],
            "actions": ["onboarding_complete", "shadow_agent_configured"],
            "wizard_answers": dict(session.wizard_answers),
            "shadow_capabilities": shadow_capabilities,
        }

    def _infer_capabilities_from_wizard(self, wizard_answers: Dict[str, str]) -> List[str]:
        """Infer automation capabilities from ONBOARDING wizard answers.

        Mirrors ``OnboardingFlow._infer_capabilities()`` but operates on
        the richer wizard_answers dict.
        """
        capabilities: List[str] = []
        tools = wizard_answers.get("tools", "").lower()
        if "github" in tools:
            capabilities.append("code_management")
        if "jira" in tools:
            capabilities.append("project_tracking")
        if "slack" in tools:
            capabilities.append("communication_automation")
        if "salesforce" in tools or "hubspot" in tools:
            capabilities.append("crm_automation")
        if "excel" in tools or "google" in tools:
            capabilities.append("data_processing")
        if "aws" in tools or "azure" in tools:
            capabilities.append("cloud_operations")

        automation = wizard_answers.get("automation", "").lower()
        if any(w in automation for w in ["email", "message", "notify", "report"]):
            capabilities.append("notification_automation")
        if any(w in automation for w in ["dashboard", "analytics", "metric", "kpi"]):
            capabilities.append("reporting_automation")
        if any(w in automation for w in ["schedule", "meeting", "calendar", "reminder"]):
            capabilities.append("scheduling_automation")
        if any(w in automation for w in ["lead", "customer", "deal", "pipeline"]):
            capabilities.append("crm_automation")
        if any(w in automation for w in ["ticket", "issue", "bug", "incident"]):
            capabilities.append("incident_management")

        dept = wizard_answers.get("department", "").lower()
        if dept in ("engineering", "it"):
            capabilities.extend(["build_monitoring", "deployment_automation"])
        elif dept in ("sales", "marketing"):
            capabilities.extend(["pipeline_tracking", "lead_scoring"])
        elif dept == "finance":
            capabilities.extend(["financial_reporting", "invoice_processing"])
        elif dept in ("hr", "operations"):
            capabilities.extend(["onboarding_automation", "policy_distribution"])

        return list(dict.fromkeys(capabilities))  # deduplicate, preserve order

    # ------------------------------------------------------------------
    # PRODUCTION wizard — deliverable-driven Q&A
    # ------------------------------------------------------------------

    def _handle_production_wizard(
        self,
        session: LibrarianSession,
        message: str,
    ) -> dict:
        """Drive the PRODUCTION deliverable wizard.

        Delegates to :class:`production_deliverable_wizard.DeliverableWizard`.
        Uses onboarding context to skip redundant questions.
        When the wizard has enough information, generates a
        :class:`~production_deliverable_wizard.DeliverableSpec` and
        returns it in the response.
        """
        try:
            from production_deliverable_wizard import DeliverableWizard  # type: ignore[import]
        except ImportError:
            logger.warning("ProductionWizard: DeliverableWizard not available")
            return self._handle_initial_description(session, message)

        # Retrieve or create the deliverable wizard
        if not hasattr(self, "_deliverable_wizards"):
            self._deliverable_wizards = {}

        dw: Optional[Any] = self._deliverable_wizards.get(session.session_id)
        if dw is None:
            dw = DeliverableWizard()
            dw_session = dw.create_session(onboarding_context=session.onboarding_context)
            session.deliverable_session_id = dw_session.session_id
            self._deliverable_wizards[session.session_id] = dw

        dw_session_id = session.deliverable_session_id
        if not dw_session_id:
            return {"message": "Production wizard could not start. Please try again.", "actions": []}

        # Record the user's answer to the pending question
        pending_qid = session.requirements_gathered.get("_last_prod_question_id")
        if pending_qid:
            result = dw.answer(dw_session_id, pending_qid, message)
            session.requirements_gathered["_last_prod_question_id"] = None

            # If the deliverable type is org_chart, also launch OrgChartGenerator
            dw_sess = dw.get_session(dw_session_id)
            if dw_sess and dw_sess.deliverable_type == "org_chart" and not session.org_chart_session_id:
                try:
                    from org_chart_generator import OrgChartGenerator  # type: ignore[import]
                    if not hasattr(self, "_org_chart_generators"):
                        self._org_chart_generators: Dict[str, Any] = {}
                    ocg = OrgChartGenerator()
                    oc_session = ocg.create_session()
                    session.org_chart_session_id = oc_session.session_id
                    self._org_chart_generators[session.session_id] = ocg
                except Exception as exc:
                    logger.debug("OrgChartGenerator init failed: %s", exc)

            # If deliverable is manufacturing/industrial/BAS-related, also instantiate IndustryAutomationWizard
            if dw_sess and dw_sess.industry_type and dw_sess.deliverable_type in ["workflow", "automation"]:
                try:
                    from industry_automation_wizard import IndustryAutomationWizard  # type: ignore[import]
                    if not hasattr(self, "_industry_wizards"):
                        self._industry_wizards: Dict[str, Any] = {}
                    iaw = IndustryAutomationWizard()
                    # Pre-populate industry from onboarding or detected industry_type
                    industry_str = dw_sess.industry_type or session.onboarding_context.get("industry", "")
                    ia_session = iaw.create_session(
                        industry=industry_str,
                        onboarding_context=session.onboarding_context
                    )
                    session.requirements_gathered["_industry_automation_session_id"] = ia_session.session_id
                    self._industry_wizards[session.session_id] = iaw
                    logger.debug("IndustryAutomationWizard initialized for industry: %s", industry_str)
                except Exception as exc:
                    logger.debug("IndustryAutomationWizard init failed: %s", exc)

        # Get the next question
        next_q = dw.next_question(dw_session_id)

        if next_q is None:
            # All questions answered — generate the spec
            spec = dw.generate_spec(dw_session_id)
            if spec:
                session.workflow_description = spec.description or spec.title
                session.workflow_name = spec.title
                session.state = ConversationState.BUILDING_STEPS

                # Build workflow steps from the spec
                for step_def in spec.workflow_steps:
                    intent = self._map_step_type_to_intent(step_def.get("type", ""))
                    step = self._create_step_from_intent(intent, spec.description)
                    step.name = step_def.get("name", step.name)
                    session.steps.append(step)
                    self._assign_agent(session, step)

                ctx_summary = ""
                if spec.onboarding_context_used:
                    n = spec.onboarding_context_used.get("pre_filled_questions", 0)
                    if n:
                        ctx_summary = f" ({n} question(s) pre-filled from your onboarding profile)"

                return {
                    "message": (
                        f"Production spec complete{ctx_summary}!\n\n"
                        f"  Deliverable: {spec.deliverable_type}\n"
                        f"  Title: {spec.title}\n"
                        f"  Format: {spec.output_format}\n"
                        f"  Audience: {spec.audience or 'not specified'}\n"
                        f"  Steps: {len(spec.workflow_steps)}\n\n"
                        f"Workflow has been built. Say 'review' to inspect, "
                        f"'refine' to adjust, or 'triage' to send to execution."
                    ),
                    "inferences": ["Production wizard complete — spec generated"],
                    "actions": ["production_spec_generated"],
                    "spec": spec.to_dict(),
                }
            else:
                return {
                    "message": "Spec generation failed. Please describe what you need.",
                    "actions": [],
                }

        # Ask the next question
        session.requirements_gathered["_last_prod_question_id"] = next_q["question_id"]
        options_text = ""
        if next_q.get("options"):
            options_text = f"\n  Options: {', '.join(next_q['options'])}"

        dw_sess = dw.get_session(dw_session_id)
        prefilled_note = ""
        if dw_sess and next_q["question_id"] in (dw_sess.pre_filled or {}):
            prefilled_note = " _(pre-filled from your onboarding profile — press Enter to accept or type to override)_"

        session.state = ConversationState.GATHERING_REQUIREMENTS
        return {
            "message": f"{next_q['question']}{options_text}{prefilled_note}\n_{next_q.get('help_text', '')}_",
            "inferences": [f"Production wizard: asking '{next_q['category']}' question"],
            "actions": [f"prod_question:{next_q['question_id']}"],
        }

    def _map_step_type_to_intent(self, step_type: str) -> str:
        """Map a DeliverableWizard step type string to an INTENT_KEYWORDS key."""
        mapping = {
            "data_fetch": "data_processing",
            "transform": "data_processing",
            "content_generation": "content_generation",
            "notification": "notification",
            "connector": "api_integration",
            "deployment": "deployment",
            "approval": "approval",
            "trigger": "scheduling",
            "action": "data_processing",
        }
        return mapping.get(step_type, "data_processing")

    def _handle_building(self, session: LibrarianSession, message: str) -> dict:
        """Handle building phase - add/modify steps."""
        msg_lower = message.lower().strip()

        # Check for finalization request
        if any(word in msg_lower for word in ["finalize", "done", "finish", "complete", "looks good", "perfect"]):
            session.state = ConversationState.FINALIZING
            return self._handle_finalization(session, message)

        # Check for review request
        if any(word in msg_lower for word in ["review", "show", "status", "agents", "monitor"]):
            session.state = ConversationState.REVIEWING
            return self._handle_review(session, message)

        # Try to add more steps
        new_intents = self._infer_intents(message)
        existing_intents = session.requirements_gathered.get("intents", [])
        novel_intents = [i for i in new_intents if i not in existing_intents]

        if novel_intents:
            steps_created = []
            inferences = []
            for intent in novel_intents:
                step = self._create_step_from_intent(intent, message)
                # Add dependencies to previous steps
                if session.steps:
                    step.dependencies.append(session.steps[-1].step_id)
                session.steps.append(step)
                steps_created.append(step.to_dict())
                inferences.append(f"Added '{intent}' step based on your input")

                agent = self._assign_agent(session, step)
                inferences.append(f"Assigned {agent.agent_role} agent to '{step.name}'")

            existing_intents.extend(novel_intents)
            session.requirements_gathered["intents"] = existing_intents
            session.inferences.extend(inferences)

            step_summary = "\n".join(
                [f"  • [{s.visibility.value}] {s.name} (Agent: {s.agent_assigned})"
                 for s in session.steps]
            )
            return {
                "message": (
                    f"Added new steps to the workflow. Current state:\n\n{step_summary}\n\n"
                    f"Would you like to add more, review agents, or finalize?"
                ),
                "steps_created": steps_created,
                "inferences": inferences,
                "actions": [f"added_step:{s['step_id']}" for s in steps_created],
            }
        else:
            return {
                "message": (
                    "I see. Could you describe what additional functionality you need? "
                    "Or say 'finalize' to complete the workflow, or 'review' to see the current state."
                ),
                "inferences": ["No new intents detected from message"],
                "actions": [],
            }

    def _handle_review(self, session: LibrarianSession, message: str) -> dict:
        """Handle review state - show workflow and agent details."""
        msg_lower = message.lower().strip()

        # Check if user wants to go back to building
        if any(word in msg_lower for word in ["add", "more", "another", "new step"]):
            session.state = ConversationState.BUILDING_STEPS
            return self._handle_building(session, message)

        if any(word in msg_lower for word in ["finalize", "done", "finish", "complete"]):
            session.state = ConversationState.FINALIZING
            return self._handle_finalization(session, message)

        # Show detailed review
        step_details = []
        for step in session.steps:
            agents_for_step = [a for a in session.agent_assignments if a.step_id == step.step_id]
            agent_info = agents_for_step[0] if agents_for_step else None
            step_details.append(
                f"  Step: {step.name} [{step.visibility.value}]\n"
                f"    Type: {step.step_type}\n"
                f"    Agent: {agent_info.agent_id if agent_info else 'none'} "
                f"({agent_info.monitoring_type if agent_info else 'n/a'})\n"
                f"    Metrics: {', '.join(agent_info.metrics_tracked) if agent_info else 'none'}"
            )

        review_text = "\n".join(step_details) if step_details else "  No steps created yet."

        session.state = ConversationState.REVIEWING
        return {
            "message": (
                f"Workflow Review — '{session.workflow_name}'\n"
                f"{'=' * 40}\n{review_text}\n\n"
                f"Would you like to add more steps, configure agents, or finalize?"
            ),
            "inferences": ["Displaying workflow review"],
            "actions": ["display_review"],
        }

    def _handle_agent_config(self, session: LibrarianSession, message: str) -> dict:
        """Handle agent configuration."""
        session.state = ConversationState.BUILDING_STEPS
        return {
            "message": (
                "Agent configuration noted. All agents are set to monitor their "
                "assigned steps. You can continue building or finalize the workflow."
            ),
            "inferences": ["Agent configuration updated"],
            "actions": ["agents_configured"],
        }

    def _handle_finalization(self, session: LibrarianSession, message: str) -> dict:
        """Handle workflow finalization."""
        if not session.steps:
            session.state = ConversationState.GATHERING_REQUIREMENTS
            return {
                "message": "There are no steps to finalize. Please describe what you'd like to build first.",
                "inferences": ["Cannot finalize empty workflow"],
                "actions": [],
            }

        # Mark all steps as validated
        for step in session.steps:
            step.visibility = StepVisibility.VALIDATED

        # Mark all agents as active
        for agent in session.agent_assignments:
            agent.status = "active"

        session.state = ConversationState.COMPLETED

        compiled = self.compile_workflow(session.session_id)

        return {
            "message": (
                f"Workflow '{session.workflow_name}' has been finalized!\n\n"
                f"  Steps: {len(session.steps)}\n"
                f"  Agents: {len(session.agent_assignments)}\n"
                f"  Status: Compiled and ready\n\n"
                f"All monitoring agents are now active. "
                f"You can view the compiled workflow or create a new one."
            ),
            "inferences": ["Workflow finalized and compiled"],
            "actions": ["workflow_finalized", "agents_activated"],
        }

    def _infer_intents(self, message: str) -> list[str]:
        """Infer workflow intents from natural language."""
        msg_lower = message.lower()
        detected = []
        for intent, keywords in INTENT_KEYWORDS.items():
            for keyword in keywords:
                if keyword in msg_lower:
                    if intent not in detected:
                        detected.append(intent)
                    break
        return detected

    def _generate_workflow_name(self, description: str, intents: list[str]) -> str:
        """Generate a descriptive workflow name."""
        if len(intents) == 1:
            return f"{intents[0].replace('_', ' ').title()} Workflow"
        elif len(intents) <= 3:
            names = [i.replace("_", " ").title() for i in intents[:3]]
            return f"{' + '.join(names)} Workflow"
        else:
            return f"Multi-Step Automation ({len(intents)} stages)"

    def _create_step_from_intent(self, intent: str, context: str) -> WorkflowStep:
        """Create a workflow step from an inferred intent."""
        template = STEP_TEMPLATES.get(intent, STEP_TEMPLATES["data_processing"])
        step = WorkflowStep(
            name=template["name"],
            step_type=template["step_type"],
            description=f"Auto-generated from: {context[:100]}",
            config=dict(template["config"]),
            monitoring_config=dict(template["monitoring"]),
            visibility=StepVisibility.CONFIGURED,
        )
        return step

    def _assign_agent(self, session: LibrarianSession, step: WorkflowStep) -> AgentAssignment:
        """Assign a monitoring agent to a step."""
        monitoring = step.monitoring_config
        agent = AgentAssignment(
            agent_role=f"{step.step_type}_monitor",
            step_id=step.step_id,
            monitoring_type=monitoring.get("type", "passive"),
            metrics_tracked=monitoring.get("metrics", []),
            alert_thresholds={"error_rate": 0.05, "latency_ms": 5000},
            status="assigned",
        )
        session.agent_assignments.append(agent)
        step.agent_assigned = agent.agent_id
        step.visibility = StepVisibility.AGENT_ASSIGNED
        return agent

    def _get_workflow_snapshot(self, session: LibrarianSession) -> dict:
        """Get a snapshot of the current workflow state."""
        return {
            "name": session.workflow_name,
            "description": session.workflow_description,
            "step_count": len(session.steps),
            "agent_count": len(session.agent_assignments),
            "state": session.state.value,
            "steps": [s.to_dict() for s in session.steps],
        }

    def _get_agent_status(self, session: LibrarianSession) -> list[dict]:
        """Get status of all agents in the session."""
        return [a.to_dict() for a in session.agent_assignments]

    def compile_workflow(self, session_id: str) -> Optional[dict]:
        """Compile the session's workflow into a deployable format."""
        session = self.sessions.get(session_id)
        if not session or not session.steps:
            return None

        nodes = []
        edges = []
        for i, step in enumerate(session.steps):
            nodes.append({
                "id": step.step_id,
                "type": step.step_type,
                "name": step.name,
                "config": step.config,
                "x": 100 + (i * 200),
                "y": 100 + (i % 2 * 80),
            })
            if step.dependencies:
                for dep in step.dependencies:
                    edges.append({"from": dep, "to": step.step_id})
            elif i > 0:
                edges.append({"from": session.steps[i - 1].step_id, "to": step.step_id})

        return {
            "workflow_id": session.session_id,
            "name": session.workflow_name,
            "description": session.workflow_description,
            "nodes": nodes,
            "edges": edges,
            "agents": [a.to_dict() for a in session.agent_assignments],
            "compiled_at": datetime.now(timezone.utc).isoformat(),
            "version": "1.0",
        }

    def get_agent_detail(self, session_id: str, agent_id: str) -> Optional[dict]:
        """Drill down into a specific agent's activity."""
        session = self.sessions.get(session_id)
        if not session:
            return None

        for agent in session.agent_assignments:
            if agent.agent_id == agent_id:
                # Find the step this agent monitors
                step = next((s for s in session.steps if s.step_id == agent.step_id), None)
                return {
                    "agent": agent.to_dict(),
                    "monitored_step": step.to_dict() if step else None,
                    "activity_log": [
                        {
                            "event": "assigned",
                            "timestamp": step.created_at if step else "",
                            "details": f"Assigned to monitor '{step.name}'" if step else "",
                        }
                    ],
                }
        return None

    def list_sessions(self) -> list[dict]:
        """List all active sessions."""
        return [
            {
                "session_id": s.session_id,
                "state": s.state.value,
                "mode": s.mode.value,
                "workflow_name": s.workflow_name,
                "step_count": len(s.steps),
                "created_at": s.created_at,
            }
            for s in self.sessions.values()
        ]

    def set_mode(self, session_id: str, mode: LibrarianMode) -> bool:
        """Change the operating mode of an existing session.

        Args:
            session_id: Target session.
            mode: New :class:`LibrarianMode`.

        Returns:
            ``True`` if the session was found and updated, ``False`` otherwise.
        """
        session = self.sessions.get(session_id)
        if not session:
            return False
        session.mode = mode
        logger.info("Session %s mode changed to %s", session_id, mode.value)
        return True

    def triage(self, session_id: str) -> TriageResult:
        """Escalate a Librarian session to Triage — the bridge between
        conversation and execution.

        Triage analyses the session's conversation history and current workflow
        state to produce a structured :class:`TriageResult` containing:

        * A fully generated workflow definition (via :class:`AIWorkflowGenerator`)
        * The best-matching slash command (via :class:`SystemLibrarian`)
        * Extracted setpoints from the user's descriptions
        * A human-readable summary and confidence score

        This is Murphy's equivalent of promoting a Copilot chat into an
        actionable task — the result is ready to pass directly to the
        execution engine.

        Args:
            session_id: Source Librarian session to analyse.

        Returns:
            A :class:`TriageResult`.  Check ``status`` before executing:
            ``READY`` means the workflow can be executed immediately;
            ``NEEDS_INFO`` means required parameters are missing.
        """
        session = self.sessions.get(session_id)
        if not session:
            return TriageResult(
                session_id=session_id,
                status=TriageStatus.FAILED,
                summary="Session not found.",
            )

        # Determine the description to analyse
        description = (
            session.workflow_description
            or " ".join(
                t.message
                for t in session.conversation_history
                if t.role == "user"
            )
        ).strip()

        if not description:
            result = TriageResult(
                session_id=session_id,
                status=TriageStatus.NEEDS_INFO,
                summary="No description available to generate a workflow.",
                missing_info=["workflow description"],
            )
            session.triage_history.append(result.to_dict())
            return result

        # ---- Generate workflow via AIWorkflowGenerator ----
        workflow_def: Optional[Dict[str, Any]] = None
        try:
            from ai_workflow_generator import AIWorkflowGenerator  # type: ignore[import]
            gen = AIWorkflowGenerator()
            workflow_def = gen.generate_workflow(description)
        except Exception as exc:
            logger.warning("triage: workflow generation failed: %s", exc)

        # ---- Generate command via SystemLibrarian ----
        command_str = ""
        setpoints: Dict[str, Any] = {}
        cmd_confidence = 0.0
        try:
            from system_librarian import SystemLibrarian  # type: ignore[import]
            lib = SystemLibrarian()
            gen_cmd = lib.generate_command(
                description,
                context={
                    "mode": session.mode.value,
                    "session_id": session_id,
                },
            )
            if gen_cmd:
                command_str = gen_cmd.command
                setpoints = gen_cmd.setpoints
                cmd_confidence = gen_cmd.confidence
        except Exception as exc:
            logger.warning("triage: command generation failed: %s", exc)

        # ---- Determine status ----
        has_workflow = workflow_def is not None and len(workflow_def.get("steps", [])) > 0
        missing_info: List[str] = []

        if not has_workflow:
            missing_info.append("executable workflow steps")

        # Confidence: blend workflow presence with command confidence
        wf_confidence = 0.8 if has_workflow else 0.0
        combined_confidence = (wf_confidence * _TRIAGE_WORKFLOW_WEIGHT + cmd_confidence * _TRIAGE_COMMAND_WEIGHT)

        if missing_info:
            status = TriageStatus.NEEDS_INFO
        else:
            status = TriageStatus.READY

        step_count = len(workflow_def.get("steps", [])) if workflow_def else 0
        summary = (
            f"Workflow '{session.workflow_name or 'unnamed'}' with "
            f"{step_count} step(s) generated via "
            f"{workflow_def.get('strategy', 'unknown') if workflow_def else 'N/A'} strategy. "
            f"Command: {command_str or 'N/A'}. "
            f"Confidence: {combined_confidence:.0%}."
        )

        result = TriageResult(
            session_id=session_id,
            status=status,
            workflow_def=workflow_def,
            command=command_str,
            setpoints=setpoints,
            confidence=combined_confidence,
            summary=summary,
            missing_info=missing_info,
        )

        # Record in session and advance state
        session.triage_history.append(result.to_dict())
        session.state = ConversationState.TRIAGE
        logger.info(
            "Triage [%s] session=%s status=%s confidence=%.2f",
            result.triage_id, session_id, status.value, combined_confidence,
        )
        return result
