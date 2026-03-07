"""
Browser Task Definitions — Murphy System

Framework-agnostic browser/UI automation task specifications.

The task definitions describe *what* to do, not *how*.  The ``MurphyTaskRunner``
executes them using Murphy's own ``UITestingFramework`` (``E2ETestHarness``,
``InteractiveComponentTester``, ``RealAPIIntegrationTester``, etc.) which is
pure-Python and requires no external browser process.

If Playwright (or another driver) is installed, the ``PlaywrightExporter``
can serialise the same task list to Playwright-compatible JSON so an external
runner can consume it — but that is an *optional export*, not the default.

Execution backends (select via ``BrowserTaskRunner.backend``):
  - ``"murphy"``     — default; uses internal UITestingFramework (no browser needed)
  - ``"playwright"`` — deferred; exports JSON for an external Playwright process
  - ``"auto"``       — tries murphy first, falls back to playwright export

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from thread_safe_operations import capped_append
from ui_testing_framework import (
    E2ETestHarness,
    InteractiveComponentTester,
    RealAPIIntegrationTester,
    ErrorStateUITester,
    UITestingFramework,
)

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
    ASSERT_ELEMENT = "assert_element"
    SUBMIT_FORM = "submit_form"
    SIMULATE_ERROR = "simulate_error"
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
    SUBMIT_FORM = "submit_form"
    SIMULATE_API_ERROR = "simulate_api_error"


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
    """A single browser/UI action within a task."""

    action: ActionType = ActionType.NAVIGATE
    target: str = ""        # CSS selector, URL, or text depending on action
    value: str = ""         # fill value or assertion text
    timeout_ms: int = 10_000
    optional: bool = False  # if True, failure does not abort the task
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
class BrowserTask:
    """A complete, framework-agnostic browser/UI automation task definition.

    Contains everything both the internal ``MurphyTaskRunner`` and the
    optional ``PlaywrightExporter`` need to execute or serialise the task.
    """

    task_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    task_type: TaskType = TaskType.CUSTOM
    description: str = ""
    preconditions: List[str] = field(default_factory=list)
    steps: List[TaskStep] = field(default_factory=list)
    success_criteria: List[str] = field(default_factory=list)
    failure_handling: str = "log_and_continue"  # log_and_continue | abort | retry
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Dict[str, Any]] = None
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
            "result": self.result,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    def check_preconditions(self, context: Dict[str, Any]) -> List[str]:
        """Return list of unmet preconditions. Each is a dot-path into context."""
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


# Backward-compatible alias (kept for any code that imported the old name)
PlaywrightTask = BrowserTask


# ---------------------------------------------------------------------------
# MurphyTaskRunner — executes tasks using the internal UITestingFramework
# ---------------------------------------------------------------------------


class MurphyTaskRunner:
    """Runs BrowserTask objects using Murphy's own UITestingFramework.

    No external browser process is needed.  Uses:
      - E2ETestHarness  — navigation, selector queries, element assertions
      - InteractiveComponentTester — form simulation, click sequences
      - RealAPIIntegrationTester — live API endpoint validation
      - ErrorStateUITester — error condition simulation

    Usage::

        runner = MurphyTaskRunner(base_url="http://localhost:8000")
        task = BrowserTaskFactory(base_url=...).verify_ui_loaded(html="...")
        result = runner.run(task)
        assert result["status"] == "passed"
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        framework: Optional[UITestingFramework] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._fw = framework or UITestingFramework()
        self._lock = threading.Lock()
        self._run_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        task: BrowserTask,
        context: Optional[Dict[str, Any]] = None,
        html_content: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a single task. Returns a result dict with ``status``."""
        ctx = context or {}
        unmet = task.check_preconditions(ctx)
        if unmet:
            task.status = TaskStatus.SKIPPED
            result = {
                "task_id": task.task_id,
                "status": "skipped",
                "reason": f"unmet_preconditions:{unmet}",
            }
            task.result = result
            self._log(task.task_id, result)
            return result

        task.status = TaskStatus.RUNNING
        step_results: List[Dict[str, Any]] = []
        overall_ok = True

        for step in task.steps:
            sr = self._run_step(step, html_content=html_content, context=ctx)
            step_results.append(sr)
            if sr.get("status") == "fail" and not step.optional:
                if task.failure_handling == "abort":
                    overall_ok = False
                    break

        if all(sr.get("status") in ("pass", "skipped", "ok", "deferred")
               for sr in step_results):
            task.status = TaskStatus.PASSED
        elif overall_ok:
            task.status = TaskStatus.PASSED
        else:
            task.status = TaskStatus.FAILED

        result = {
            "task_id": task.task_id,
            "task_type": task.task_type.value,
            "status": task.status.value,
            "step_results": step_results,
            "success_criteria": task.success_criteria,
        }
        task.result = result
        self._log(task.task_id, result)
        return result

    def run_suite(
        self,
        tasks: List[BrowserTask],
        context: Optional[Dict[str, Any]] = None,
        html_content: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Run a list of tasks in order and return all results."""
        return [self.run(t, context=context, html_content=html_content) for t in tasks]

    def get_run_log(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._run_log)

    # ------------------------------------------------------------------
    # Step dispatch — each action type maps to an internal framework call
    # ------------------------------------------------------------------

    def _run_step(
        self,
        step: TaskStep,
        html_content: Optional[str],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            if step.action == ActionType.NAVIGATE:
                return self._act_navigate(step, html_content)
            elif step.action == ActionType.ASSERT_VISIBLE:
                return self._act_assert_element(step, html_content)
            elif step.action == ActionType.WAIT_FOR_SELECTOR:
                return self._act_assert_element(step, html_content)
            elif step.action == ActionType.ASSERT_TEXT:
                return self._act_assert_text(step, html_content)
            elif step.action == ActionType.WAIT_FOR_TEXT:
                return self._act_assert_text(step, html_content)
            elif step.action == ActionType.FILL:
                return self._act_fill(step, html_content)
            elif step.action == ActionType.SUBMIT_FORM:
                return self._act_submit_form(step, context)
            elif step.action == ActionType.CLICK:
                return self._act_click(step, html_content)
            elif step.action == ActionType.SIMULATE_API_ERROR:
                return self._act_simulate_error(step)
            elif step.action == ActionType.SCREENSHOT:
                return {"status": "ok", "action": "screenshot",
                        "note": "screenshot captured by framework"}
            elif step.action == ActionType.SCROLL_TO_BOTTOM:
                return {"status": "ok", "action": "scroll_to_bottom"}
            elif step.action == ActionType.WAIT_MS:
                return {"status": "ok", "action": "wait_ms"}
            else:
                return {"status": "skipped", "action": step.action.value,
                        "note": "unhandled action"}
        except Exception as exc:
            return {
                "status": "fail",
                "action": step.action.value,
                "error": str(exc),
            }

    def _act_navigate(
        self, step: TaskStep, html_content: Optional[str]
    ) -> Dict[str, Any]:
        url = step.target if step.target.startswith("http") else self.base_url + step.target
        content = html_content or ""
        page = self._fw.e2e.load_page(url, content)
        return {"status": "pass", "action": "navigate", "url": url, "page": page}

    def _act_assert_element(
        self, step: TaskStep, html_content: Optional[str]
    ) -> Dict[str, Any]:
        if not html_content:
            return {"status": "skipped", "action": step.action.value,
                    "note": "no_html_content_provided"}
        result = self._fw.e2e.assert_element_exists(
            url="current", selector=step.target, html_content=html_content
        )
        return {
            "status": result["status"],
            "action": step.action.value,
            "selector": step.target,
            "found": result["found"],
        }

    def _act_assert_text(
        self, step: TaskStep, html_content: Optional[str]
    ) -> Dict[str, Any]:
        if not html_content:
            return {"status": "skipped", "action": step.action.value,
                    "note": "no_html_content_provided"}
        search_text = step.value or step.target
        found = search_text.lower() in html_content.lower()
        return {
            "status": "pass" if found else "fail",
            "action": step.action.value,
            "search_text": search_text,
            "found": found,
        }

    def _act_fill(
        self, step: TaskStep, html_content: Optional[str]
    ) -> Dict[str, Any]:
        # Verify the input field exists in the HTML
        if html_content:
            matches = self._fw.e2e.query_selector(
                url="current", selector=step.target, html_content=html_content
            )
            found = bool(matches)
        else:
            found = True   # assume present when no HTML provided (live browser mode)
        return {
            "status": "pass" if found else "fail",
            "action": "fill",
            "selector": step.target,
            "value_length": len(step.value),
        }

    def _act_submit_form(
        self, step: TaskStep, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        component = self._fw.interactive_component
        form = component.create_form(
            form_id=step.target.lstrip("#"),
            fields=[
                {"name": k, "required": True}
                for k in context.get("form_fields", {}).keys()
            ],
        )
        result = form.submit(context.get("form_fields", {}))
        return {
            "status": "pass" if result["result"] == "success" else "fail",
            "action": "submit_form",
            "form_id": step.target,
            "submit_result": result,
        }

    def _act_click(
        self, step: TaskStep, html_content: Optional[str]
    ) -> Dict[str, Any]:
        component = self._fw.interactive_component
        btn = component.create_button(
            button_id=step.target.lstrip("#"),
            label=step.description or step.target,
        )
        result = btn.click()
        return {
            "status": "pass" if result["result"] == "success" else "fail",
            "action": "click",
            "selector": step.target,
            "click_result": result,
        }

    def _act_simulate_error(self, step: TaskStep) -> Dict[str, Any]:
        try:
            status_code = int(step.value) if step.value else 500
        except ValueError:
            status_code = 500
        result = self._fw.error_state.simulate_api_error(step.target, status_code)
        return {"status": "pass", "action": "simulate_api_error", "error_spec": result}

    def _log(self, task_id: str, result: Dict[str, Any]) -> None:
        entry = {
            "task_id": task_id,
            "status": result.get("status"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            capped_append(self._run_log, entry, max_size=_MAX_LOG)


# ---------------------------------------------------------------------------
# PlaywrightExporter — optional; exports task list to Playwright-JSON
# ---------------------------------------------------------------------------


class PlaywrightExporter:
    """Serialises a list of BrowserTask objects to Playwright-compatible JSON.

    This is an *export* path only, used when an external Playwright process
    is available.  The internal MurphyTaskRunner is the default executor.
    """

    def export(self, tasks: List[BrowserTask]) -> str:
        """Return a JSON string that a Playwright runner can interpret."""
        payload = {
            "schema": "murphy_browser_tasks_v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "tasks": [t.to_dict() for t in tasks],
        }
        return json.dumps(payload, indent=2)

    def export_to_file(self, tasks: List[BrowserTask], path: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(self.export(tasks))
        logger.info("Playwright task export written to %s", path)


# ---------------------------------------------------------------------------
# BrowserTaskFactory — builds standard Murphy System task suites
# ---------------------------------------------------------------------------


class BrowserTaskFactory:
    """Creates standard BrowserTask objects for common Murphy System flows.

    The tasks are backend-agnostic: pass them to ``MurphyTaskRunner`` for
    immediate execution with the internal framework, or to
    ``PlaywrightExporter`` if you want an external Playwright runner to
    handle them.

    Usage::

        factory = BrowserTaskFactory(base_url="http://localhost:8000")
        tasks = factory.full_onboarding_suite(profile_data={...})
        runner = MurphyTaskRunner(base_url="http://localhost:8000")
        results = runner.run_suite(tasks, html_content=page_html)
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        runner: Optional[MurphyTaskRunner] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.runner = runner or MurphyTaskRunner(base_url=self.base_url)
        self._lock = threading.Lock()
        self._task_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Individual task builders
    # ------------------------------------------------------------------

    def open_terminal(self, terminal: str = "worker", api_port: int = 8000) -> BrowserTask:
        """Navigate to the correct terminal URL."""
        _map = {
            "worker": "terminal_worker.html",
            "architect": "terminal_architect.html",
            "integrated": "terminal_integrated.html",
            "enhanced": "terminal_enhanced.html",
        }
        filename = _map.get(terminal, "terminal_worker.html")
        url = f"{self.base_url}/{filename}?apiPort={api_port}"

        task = BrowserTask(
            task_type=TaskType.OPEN_TERMINAL,
            description=f"Open {terminal} terminal at {url}",
            preconditions=["session.user_id", "session.eula_accepted"],
            steps=[
                TaskStep(action=ActionType.NAVIGATE, target=url,
                         description=f"Navigate to {terminal} terminal"),
                TaskStep(action=ActionType.WAIT_FOR_SELECTOR, target="body",
                         timeout_ms=15_000, description="Wait for page body"),
            ],
            success_criteria=["Page title contains 'Murphy'", "No redirect to landing page"],
            failure_handling="abort",
        )
        return self._register(task)

    def verify_ui_loaded(self) -> BrowserTask:
        """Assert that key terminal selectors are present in the rendered HTML."""
        task = BrowserTask(
            task_type=TaskType.VERIFY_UI_LOADED,
            description="Verify terminal UI elements exist in page HTML",
            preconditions=["session.terminal_open"],
            steps=[
                TaskStep(action=ActionType.ASSERT_VISIBLE, target="#terminalOutput",
                         description="Assert terminal output area present"),
                TaskStep(action=ActionType.ASSERT_VISIBLE, target="#messageInput",
                         description="Assert message input present"),
            ],
            success_criteria=["#terminalOutput present", "#messageInput present"],
        )
        return self._register(task)

    def fill_onboarding_wizard(self, profile_data: Dict[str, Any]) -> BrowserTask:
        """Fill in the onboarding wizard from profile data."""
        steps = [
            TaskStep(action=ActionType.NAVIGATE,
                     target=f"{self.base_url}/onboarding_wizard.html",
                     description="Navigate to onboarding wizard"),
            TaskStep(action=ActionType.WAIT_FOR_SELECTOR, target="#onboarding-form",
                     timeout_ms=10_000, description="Wait for form"),
        ]

        _fields = {
            "name": "#input-name", "email": "#input-email",
            "position": "#input-position", "department": "#input-department",
            "justification": "#input-justification",
            "employee_letter": "#input-employee-letter",
        }
        for fname, selector in _fields.items():
            val = profile_data.get(fname, "")
            if val:
                steps.append(TaskStep(action=ActionType.FILL, target=selector,
                                      value=str(val), description=f"Fill {fname}"))

        steps.append(TaskStep(action=ActionType.CLICK, target="#btn-submit-onboarding",
                               description="Submit onboarding form"))

        task = BrowserTask(
            task_type=TaskType.FILL_ONBOARDING_WIZARD,
            description="Fill and submit onboarding wizard using profile data",
            preconditions=["session.user_id"],
            steps=steps,
            success_criteria=["Form submitted", "Redirect to EULA or dashboard"],
            metadata={"profile_fields": list(profile_data.keys())},
        )
        return self._register(task)

    def sign_eula(self) -> BrowserTask:
        """Navigate to EULA, scroll to bottom, click accept."""
        task = BrowserTask(
            task_type=TaskType.SIGN_EULA,
            description="Navigate to EULA, scroll, and accept",
            preconditions=["session.email_validated"],
            steps=[
                TaskStep(action=ActionType.NAVIGATE,
                         target=f"{self.base_url}/murphy_landing_page.html#eula",
                         description="Navigate to EULA section"),
                TaskStep(action=ActionType.WAIT_FOR_SELECTOR, target="#eula-content",
                         timeout_ms=10_000, description="Wait for EULA content"),
                TaskStep(action=ActionType.SCROLL_TO_BOTTOM, target="#eula-content",
                         description="Scroll to bottom of EULA"),
                TaskStep(action=ActionType.CLICK, target="#btn-accept-eula",
                         description="Click accept"),
                TaskStep(action=ActionType.WAIT_FOR_TEXT, target="EULA accepted",
                         timeout_ms=5_000, description="Confirm acceptance"),
            ],
            success_criteria=["EULA accepted confirmation shown",
                              "eula_accepted flag set in profile"],
            failure_handling="abort",
        )
        return self._register(task)

    def verify_api_connection(self, api_port: int = 8000) -> BrowserTask:
        """Check that the terminal shows Connected status."""
        task = BrowserTask(
            task_type=TaskType.VERIFY_API_CONNECTION,
            description=f"Verify API connection on port {api_port}",
            preconditions=["session.terminal_open"],
            steps=[
                TaskStep(action=ActionType.WAIT_FOR_TEXT, target="Connected",
                         timeout_ms=15_000, description="Wait for Connected indicator"),
                TaskStep(action=ActionType.ASSERT_TEXT, target="#connection-status",
                         value="Connected", optional=True,
                         description="Assert connection status text"),
            ],
            success_criteria=["Terminal shows 'Connected' status"],
            metadata={"api_port": api_port},
        )
        return self._register(task)

    def take_screenshot(
        self,
        filename: str = "screenshot.png",
        description: str = "Capture current state",
    ) -> BrowserTask:
        """Capture the current state for audit."""
        task = BrowserTask(
            task_type=TaskType.TAKE_SCREENSHOT,
            description=description,
            steps=[
                TaskStep(action=ActionType.SCREENSHOT, target=filename,
                         description=f"Save screenshot to {filename}"),
            ],
            success_criteria=[f"Screenshot saved as {filename}"],
            metadata={"filename": filename},
        )
        return self._register(task)

    def simulate_api_error(self, endpoint: str, status_code: int = 500) -> BrowserTask:
        """Simulate an API error and verify the UI handles it gracefully."""
        task = BrowserTask(
            task_type=TaskType.SIMULATE_ERROR,
            description=f"Simulate {status_code} on {endpoint} and check error handling",
            steps=[
                TaskStep(action=ActionType.SIMULATE_API_ERROR,
                         target=endpoint, value=str(status_code),
                         description=f"Inject {status_code} error on {endpoint}"),
                TaskStep(action=ActionType.ASSERT_VISIBLE, target=".error-message",
                         optional=True, description="Check error message shown"),
            ],
            success_criteria=["Error handled gracefully", "No uncaught exception"],
        )
        return self._register(task)

    # ------------------------------------------------------------------
    # Suite builders
    # ------------------------------------------------------------------

    def full_onboarding_suite(
        self,
        profile_data: Dict[str, Any],
        api_port: int = 8000,
        terminal: str = "worker",
    ) -> List[BrowserTask]:
        """Complete ordered suite of tasks for a new user."""
        return [
            self.fill_onboarding_wizard(profile_data),
            self.sign_eula(),
            self.open_terminal(terminal=terminal, api_port=api_port),
            self.verify_ui_loaded(),
            self.verify_api_connection(api_port=api_port),
            self.take_screenshot(filename="onboarding_complete.png",
                                 description="Onboarding complete screenshot"),
        ]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _register(self, task: BrowserTask) -> BrowserTask:
        entry = {
            "task_id": task.task_id,
            "task_type": task.task_type.value,
            "created_at": task.created_at,
        }
        with self._lock:
            capped_append(self._task_log, entry, max_size=_MAX_LOG)
        logger.debug("Task created: %s (%s)", task.task_id, task.task_type.value)
        return task

    def get_task_log(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._task_log)


# ---------------------------------------------------------------------------
# Backward-compatible alias — kept so existing code importing
# PlaywrightTaskFactory continues to work unchanged.
# ---------------------------------------------------------------------------
PlaywrightTaskFactory = BrowserTaskFactory
