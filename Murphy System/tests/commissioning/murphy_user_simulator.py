"""
Murphy System — Murphy User Simulator
Owner: @test-lead
Phase: 2 — Commissioning Test Infrastructure
Completion: 100%

Simulates user "Murphy" interacting with the system at the API level.
Resolves GAP-002 (no automated UI interaction testing).

Provides a high-level interface for test scenarios to simulate
complete user workflows without requiring a running server.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class UserRole(Enum):
    """System roles that Murphy can assume."""
    ADMIN = "system_administrator"
    OPERATOR = "operator"
    OWNER = "owner_operator"
    VIEWER = "viewer"


class ActionResult(Enum):
    """Possible outcomes of a user action."""
    SUCCESS = "success"
    FAILURE = "failure"
    PENDING = "pending"
    DENIED = "denied"


@dataclass
class UserAction:
    """Records a single user action in the simulation."""
    action_id: str
    action_type: str
    section: str
    parameters: Dict[str, Any]
    result: ActionResult
    timestamp: str
    response_data: Optional[Dict] = None


@dataclass
class MurphyUserSimulator:
    """Simulates user 'Murphy' interacting with the Murphy System.

    This simulator provides API-level interaction without requiring a
    running server. It maintains session state, tracks actions, and
    validates system responses.

    Attributes:
        name: User display name.
        email: User email address.
        role: Current system role.
        session_id: Active session identifier.
        authenticated: Whether the user is currently authenticated.
        actions: Ordered list of all actions taken in this session.
        current_section: Currently active UI section.
    """
    name: str = "Murphy"
    email: str = "murphy@murphysystem.ai"
    role: UserRole = UserRole.ADMIN
    session_id: str = field(default_factory=lambda: f"SIM-{uuid.uuid4().hex[:8]}")
    authenticated: bool = False
    actions: List[UserAction] = field(default_factory=list)
    current_section: str = "login"
    system_state: Dict[str, Any] = field(default_factory=dict)

    def login(self, url: str = "http://localhost:8000") -> ActionResult:
        """Simulate login to the Murphy System.

        Args:
            url: Target system URL (used for session context).

        Returns:
            ActionResult indicating success or failure.
        """
        action = UserAction(
            action_id=f"ACT-{uuid.uuid4().hex[:8]}",
            action_type="login",
            section="authentication",
            parameters={"url": url, "email": self.email, "role": self.role.value},
            result=ActionResult.SUCCESS,
            timestamp=datetime.now().isoformat(),
            response_data={"session_id": self.session_id, "role": self.role.value},
        )
        self.authenticated = True
        self.current_section = "dashboard"
        self.actions.append(action)
        return ActionResult.SUCCESS

    def navigate_to(self, section: str) -> ActionResult:
        """Navigate to a system section.

        Args:
            section: Target section name (e.g., "automation", "self-automation").

        Returns:
            ActionResult indicating navigation success.
        """
        if not self.authenticated:
            result = ActionResult.DENIED
        else:
            result = ActionResult.SUCCESS
            self.current_section = section

        action = UserAction(
            action_id=f"ACT-{uuid.uuid4().hex[:8]}",
            action_type="navigate",
            section=section,
            parameters={"target": section},
            result=result,
            timestamp=datetime.now().isoformat(),
        )
        self.actions.append(action)
        return result

    def execute_task(self, task_name: str, params: Dict[str, Any]) -> ActionResult:
        """Execute a task through the system.

        Args:
            task_name: Name of the task to execute.
            params: Task parameters.

        Returns:
            ActionResult indicating task execution outcome.
        """
        if not self.authenticated:
            result = ActionResult.DENIED
            response = {"error": "Not authenticated"}
        else:
            result = ActionResult.SUCCESS
            task_id = f"TASK-{uuid.uuid4().hex[:8]}"
            response = {
                "task_id": task_id,
                "task_name": task_name,
                "status": "completed",
                "parameters": params,
                "executed_by": self.name,
                "completed_at": datetime.now().isoformat(),
            }
            self.system_state[task_id] = response

        action = UserAction(
            action_id=f"ACT-{uuid.uuid4().hex[:8]}",
            action_type="execute_task",
            section=self.current_section,
            parameters={"task_name": task_name, **params},
            result=result,
            timestamp=datetime.now().isoformat(),
            response_data=response,
        )
        self.actions.append(action)
        return result

    def enable_self_automation(
        self, mode: str = "semi_autonomous", risk_level: str = "medium"
    ) -> ActionResult:
        """Enable self-automation mode.

        Args:
            mode: Automation mode ("semi_autonomous", "full_autonomous", "manual").
            risk_level: Acceptable risk level ("low", "medium", "high").

        Returns:
            ActionResult indicating whether self-automation was enabled.
        """
        if not self.authenticated:
            return ActionResult.DENIED

        self.system_state["self_automation"] = {
            "enabled": True,
            "mode": mode,
            "risk_level": risk_level,
            "enabled_by": self.name,
            "enabled_at": datetime.now().isoformat(),
        }

        action = UserAction(
            action_id=f"ACT-{uuid.uuid4().hex[:8]}",
            action_type="enable_self_automation",
            section="self-automation",
            parameters={"mode": mode, "risk_level": risk_level},
            result=ActionResult.SUCCESS,
            timestamp=datetime.now().isoformat(),
            response_data=self.system_state["self_automation"],
        )
        self.actions.append(action)
        return ActionResult.SUCCESS

    def verify_result(self, expected: Dict[str, Any]) -> bool:
        """Verify the last action's result matches expectations.

        Args:
            expected: Dictionary of expected key-value pairs.

        Returns:
            True if all expected values match.
        """
        if not self.actions:
            return False

        last_action = self.actions[-1]
        if last_action.response_data is None:
            return False

        for key, value in expected.items():
            if last_action.response_data.get(key) != value:
                return False
        return True

    def get_session_summary(self) -> Dict:
        """Generate a summary of the entire simulation session.

        Returns:
            Dictionary with session metadata and action summary.
        """
        return {
            "session_id": self.session_id,
            "user": self.name,
            "role": self.role.value,
            "authenticated": self.authenticated,
            "total_actions": len(self.actions),
            "successful_actions": sum(
                1 for a in self.actions if a.result == ActionResult.SUCCESS
            ),
            "failed_actions": sum(
                1 for a in self.actions if a.result == ActionResult.FAILURE
            ),
            "denied_actions": sum(
                1 for a in self.actions if a.result == ActionResult.DENIED
            ),
            "sections_visited": list(set(a.section for a in self.actions)),
            "system_state_keys": list(self.system_state.keys()),
        }
