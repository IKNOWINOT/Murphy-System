"""
Playwright Task Definitions — Murphy System

Structured JSON task specs that a Playwright (or compatible) browser
automation runner can interpret.  These are NOT Playwright code — they are
declarative task definitions that describe what to do and how to verify it.

Each ``PlaywrightTask`` includes:
  - task_id, task_type, description
  - preconditions — assertions that must be true before execution
  - steps          — ordered list of actions (navigate/click/fill/wait/assert)
  - success_criteria — what proves the task worked
  - failure_handling — what to do if a step fails

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from thread_safe_operations import capped_append

logger = logging.getLogger(__name__)

_MAX_LOG = 5_000


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TaskType(str, Enum):
    OPEN_TERMINAL = "open_terminal"
    VERIFY_UI_LOADED = "verify_ui_loaded"
    FILL_ONBOARDING_WIZARD = "fill_onboarding_wizard"
    SIGN_EULA = "sign_eula"
    VERIFY_API_CONNECTION = "verify_api_connection"
    TAKE_SCREENSHOT = "take_screenshot"
    CUSTOM = "custom"


class ActionType(str, Enum):
    NAVIGATE = "navigate"
    CLICK = "click"
    FILL = "fill"
    WAIT_FOR_SELECTOR = "wait_for_selector"
    WAIT_FOR_TEXT = "wait_for_text"
    ASSERT_TEXT = "assert_text"
    ASSERT_VISIBLE = "assert_visible"
    SCROLL_TO_BOTTOM = "scroll_to_bottom"
    SCREENSHOT = "screenshot"
    WAIT_MS = "wait_ms"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


# ---------------------------------------------------------------------------
# Step & Task dataclasses
# ---------------------------------------------------------------------------


@dataclass
class TaskStep:
    """A single browser action within a task."""

    action: ActionType = ActionType.NAVIGATE
    target: str = ""                # selector, URL, or text depending on action
    value: str = ""                 # fill value or assertion text
    timeout_ms: int = 10_000
    optional: bool = False          # if True, failure does not abort the task
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action.value,
            "target": self.target,
            "value": self.value,
            "timeout_ms": self.timeout_ms,
            "optional": self.optional,
            "description": self.description,
        }


@dataclass
class PlaywrightTask:
    """A complete browser automation task definition."""

    task_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    task_type: TaskType = TaskType.CUSTOM
    description: str = ""
    preconditions: List[str] = field(default_factory=list)
    steps: List[TaskStep] = field(default_factory=list)
    success_criteria: List[str] = field(default_factory=list)
    failure_handling: str = "log_and_continue"   # log_and_continue | abort | retry
    status: TaskStatus = TaskStatus.PENDING
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type.value,
            "description": self.description,
            "preconditions": self.preconditions,
            "steps": [s.to_dict() for s in self.steps],
            "success_criteria": self.success_criteria,
            "failure_handling": self.failure_handling,
            "status": self.status.value,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    def check_preconditions(self, context: Dict[str, Any]) -> List[str]:
        """Return a list of unmet preconditions given a context dict.

        Each precondition is a dot-path key that must be truthy in *context*.
        Example: "profile.email_validated"
        """
        unmet: List[str] = []
        for cond in self.preconditions:
            parts = cond.split(".")
            val: Any = context
            try:
                for part in parts:
                    val = val[part]
            except (KeyError, TypeError):
                unmet.append(cond)
                continue
            if not val:
                unmet.append(cond)
        return unmet


# ---------------------------------------------------------------------------
# Task factory
# ---------------------------------------------------------------------------


class PlaywrightTaskFactory:
    """Creates standard Playwright task definitions for Murphy System.

    Usage::

        factory = PlaywrightTaskFactory(base_url="http://localhost:8000")
        tasks = factory.full_onboarding_suite(profile_data={...})
    """

    def __init__(self, base_url: str = "http://localhost:8000") -> None:
        self.base_url = base_url.rstrip("/")
        self._lock = threading.Lock()
        self._task_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Individual task builders
    # ------------------------------------------------------------------

    def open_terminal(self, terminal: str = "worker", api_port: int = 8000) -> PlaywrightTask:
        """Navigate to the correct terminal URL."""
        terminal_map = {
            "worker": "terminal_worker.html",
            "architect": "terminal_architect.html",
            "integrated": "terminal_integrated.html",
            "enhanced": "terminal_enhanced.html",
        }
        filename = terminal_map.get(terminal, "terminal_worker.html")
        url = f"{self.base_url}/{filename}?apiPort={api_port}"

        task = PlaywrightTask(
            task_type=TaskType.OPEN_TERMINAL,
            description=f"Open {terminal} terminal at {url}",
            preconditions=["session.user_id", "session.eula_accepted"],
            steps=[
                TaskStep(
                    action=ActionType.NAVIGATE,
                    target=url,
                    description=f"Navigate to {terminal} terminal",
                ),
                TaskStep(
                    action=ActionType.WAIT_FOR_SELECTOR,
                    target="body",
                    timeout_ms=15_000,
                    description="Wait for page body to load",
                ),
            ],
            success_criteria=[
                "Page title contains 'Murphy'",
                "No redirect to landing page",
            ],
            failure_handling="abort",
        )
        self._log_task(task)
        return task

    def verify_ui_loaded(self) -> PlaywrightTask:
        """Wait for key terminal selectors to be visible."""
        task = PlaywrightTask(
            task_type=TaskType.VERIFY_UI_LOADED,
            description="Verify terminal UI is fully loaded",
            preconditions=["session.terminal_open"],
            steps=[
                TaskStep(
                    action=ActionType.WAIT_FOR_SELECTOR,
                    target="#terminalOutput",
                    timeout_ms=10_000,
                    description="Wait for terminal output area",
                ),
                TaskStep(
                    action=ActionType.WAIT_FOR_SELECTOR,
                    target="#messageInput",
                    timeout_ms=10_000,
                    description="Wait for message input field",
                ),
                TaskStep(
                    action=ActionType.ASSERT_VISIBLE,
                    target="#terminalOutput",
                    description="Assert terminal output is visible",
                ),
            ],
            success_criteria=[
                "#terminalOutput is visible",
                "#messageInput is visible",
            ],
        )
        self._log_task(task)
        return task

    def fill_onboarding_wizard(self, profile_data: Dict[str, Any]) -> PlaywrightTask:
        """Fill in the onboarding wizard from profile data."""
        steps = [
            TaskStep(
                action=ActionType.NAVIGATE,
                target=f"{self.base_url}/onboarding_wizard.html",
                description="Navigate to onboarding wizard",
            ),
            TaskStep(
                action=ActionType.WAIT_FOR_SELECTOR,
                target="#onboarding-form",
                timeout_ms=10_000,
                description="Wait for onboarding form",
            ),
        ]

        field_map = {
            "name": "#input-name",
            "email": "#input-email",
            "position": "#input-position",
            "department": "#input-department",
            "justification": "#input-justification",
            "employee_letter": "#input-employee-letter",
        }

        for field_name, selector in field_map.items():
            value = profile_data.get(field_name, "")
            if value:
                steps.append(
                    TaskStep(
                        action=ActionType.FILL,
                        target=selector,
                        value=str(value),
                        description=f"Fill {field_name}",
                    )
                )

        steps.append(
            TaskStep(
                action=ActionType.CLICK,
                target="#btn-submit-onboarding",
                description="Submit onboarding form",
            )
        )

        task = PlaywrightTask(
            task_type=TaskType.FILL_ONBOARDING_WIZARD,
            description="Fill and submit onboarding wizard",
            preconditions=["session.user_id"],
            steps=steps,
            success_criteria=[
                "Form submitted successfully",
                "Redirect to EULA page or dashboard",
            ],
            metadata={"profile_fields": list(profile_data.keys())},
        )
        self._log_task(task)
        return task

    def sign_eula(self) -> PlaywrightTask:
        """Navigate to EULA, scroll to bottom, and click accept."""
        task = PlaywrightTask(
            task_type=TaskType.SIGN_EULA,
            description="Navigate to EULA, scroll to bottom, and click accept",
            preconditions=["session.email_validated"],
            steps=[
                TaskStep(
                    action=ActionType.NAVIGATE,
                    target=f"{self.base_url}/murphy_landing_page.html#eula",
                    description="Navigate to EULA section",
                ),
                TaskStep(
                    action=ActionType.WAIT_FOR_SELECTOR,
                    target="#eula-content",
                    timeout_ms=10_000,
                    description="Wait for EULA content",
                ),
                TaskStep(
                    action=ActionType.SCROLL_TO_BOTTOM,
                    target="#eula-content",
                    description="Scroll to bottom of EULA",
                ),
                TaskStep(
                    action=ActionType.CLICK,
                    target="#btn-accept-eula",
                    description="Click 'I Accept' button",
                ),
                TaskStep(
                    action=ActionType.WAIT_FOR_TEXT,
                    target="EULA accepted",
                    timeout_ms=5_000,
                    description="Wait for acceptance confirmation",
                ),
            ],
            success_criteria=[
                "EULA accepted confirmation shown",
                "eula_accepted flag set in profile",
            ],
            failure_handling="abort",
        )
        self._log_task(task)
        return task

    def verify_api_connection(self, api_port: int = 8000) -> PlaywrightTask:
        """Check that the terminal shows 'Connected' status."""
        task = PlaywrightTask(
            task_type=TaskType.VERIFY_API_CONNECTION,
            description=f"Verify API connection on port {api_port}",
            preconditions=["session.terminal_open"],
            steps=[
                TaskStep(
                    action=ActionType.WAIT_FOR_TEXT,
                    target="Connected",
                    timeout_ms=15_000,
                    description="Wait for 'Connected' status indicator",
                ),
                TaskStep(
                    action=ActionType.ASSERT_TEXT,
                    target="#connection-status",
                    value="Connected",
                    optional=True,
                    description="Assert connection status text",
                ),
            ],
            success_criteria=["Terminal shows 'Connected' status"],
            metadata={"api_port": api_port},
        )
        self._log_task(task)
        return task

    def take_screenshot(
        self,
        filename: str = "screenshot.png",
        description: str = "Capture current state",
    ) -> PlaywrightTask:
        """Capture the current state for audit/verification."""
        task = PlaywrightTask(
            task_type=TaskType.TAKE_SCREENSHOT,
            description=description,
            preconditions=[],
            steps=[
                TaskStep(
                    action=ActionType.SCREENSHOT,
                    target=filename,
                    description=f"Save screenshot to {filename}",
                ),
            ],
            success_criteria=[f"Screenshot saved as {filename}"],
            metadata={"filename": filename},
        )
        self._log_task(task)
        return task

    # ------------------------------------------------------------------
    # Suite builders
    # ------------------------------------------------------------------

    def full_onboarding_suite(
        self,
        profile_data: Dict[str, Any],
        api_port: int = 8000,
        terminal: str = "worker",
    ) -> List[PlaywrightTask]:
        """Return the complete ordered suite of tasks for a new user."""
        return [
            self.fill_onboarding_wizard(profile_data),
            self.sign_eula(),
            self.open_terminal(terminal=terminal, api_port=api_port),
            self.verify_ui_loaded(),
            self.verify_api_connection(api_port=api_port),
            self.take_screenshot(filename="onboarding_complete.png", description="Onboarding complete screenshot"),
        ]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _log_task(self, task: PlaywrightTask) -> None:
        entry = {
            "task_id": task.task_id,
            "task_type": task.task_type.value,
            "created_at": task.created_at,
        }
        with self._lock:
            capped_append(self._task_log, entry, max_size=_MAX_LOG)
        logger.debug("Task created: %s (%s)", task.task_id, task.task_type.value)

    def get_task_log(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._task_log)
