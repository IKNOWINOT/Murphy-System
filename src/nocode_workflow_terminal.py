"""
No-Code Workflow Librarian Terminal
====================================
Conversational interface for building workflows through natural language.
The Librarian infers configuration, creates steps in real-time, and shows
the automation being built step by step. Each agent's role and monitoring
status is visible throughout the process.
"""

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

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


class StepVisibility(Enum):
    """Visibility of workflow step creation."""
    CREATING = "creating"
    CONFIGURED = "configured"
    AGENT_ASSIGNED = "agent_assigned"
    MONITORING_ACTIVE = "monitoring_active"
    VALIDATED = "validated"


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
    workflow_name: str = ""
    workflow_description: str = ""
    steps: list = field(default_factory=list)
    agent_assignments: list = field(default_factory=list)
    conversation_history: list = field(default_factory=list)
    requirements_gathered: dict = field(default_factory=dict)
    inferences: list = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "state": self.state.value,
            "workflow_name": self.workflow_name,
            "workflow_description": self.workflow_description,
            "steps": [s.to_dict() if hasattr(s, 'to_dict') else s for s in self.steps],
            "agent_assignments": [a.to_dict() if hasattr(a, 'to_dict') else a for a in self.agent_assignments],
            "conversation_history": [c.to_dict() if hasattr(c, 'to_dict') else c for c in self.conversation_history],
            "requirements_gathered": self.requirements_gathered,
            "inferences": self.inferences,
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
    """

    def __init__(self):
        self.sessions: dict[str, LibrarianSession] = {}
        self.max_sessions = 100

    def create_session(self) -> LibrarianSession:
        """Create a new Librarian session."""
        if len(self.sessions) >= self.max_sessions:
            oldest_key = min(self.sessions, key=lambda k: self.sessions[k].created_at)
            del self.sessions[oldest_key]

        session = LibrarianSession()
        self.sessions[session.session_id] = session

        greeting = ConversationTurn(
            role="librarian",
            message=(
                "Welcome to the Murphy No-Code Workflow Builder. "
                "I'm your Librarian — describe what you'd like to automate "
                "and I'll build it step by step. You'll see each step being "
                "created and which agents are monitoring them. "
                "What would you like to build today?"
            ),
        )
        session.conversation_history.append(greeting)
        return session

    def get_session(self, session_id: str) -> Optional[LibrarianSession]:
        """Retrieve an existing session."""
        return self.sessions.get(session_id)

    def send_message(self, session_id: str, user_message: str) -> dict:
        """
        Process a user message and return the Librarian's response
        along with any workflow steps created.
        """
        session = self.sessions.get(session_id)
        if not session:
            return {"error": "Session not found", "session_id": session_id}

        # Record user turn
        user_turn = ConversationTurn(role="user", message=user_message)
        session.conversation_history.append(user_turn)

        # Process based on current state
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
            "message": response["message"],
            "steps_created": response.get("steps_created", []),
            "workflow_snapshot": self._get_workflow_snapshot(session),
            "agent_status": self._get_agent_status(session),
            "inferences": response.get("inferences", []),
        }

    def _process_message(self, session: LibrarianSession, message: str) -> dict:
        """Route message processing based on conversation state."""
        msg_lower = message.lower().strip()

        # Handle state transitions
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
                "workflow_name": s.workflow_name,
                "step_count": len(s.steps),
                "created_at": s.created_at,
            }
            for s in self.sessions.values()
        ]
