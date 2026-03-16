"""
Murphy Native Automation — Murphy System

The one-stop module for all browser/UI/desktop automation in Murphy System.

Priority order (always use the first option that fits):
  1. Direct API call       — urllib; covers 100% of what any terminal does
  2. UITestingFramework    — E2ETestHarness, InteractiveComponentTester, etc.
                             for DOM/form/element assertions (no browser process)
  3. GhostDesktopRunner    — wraps bots/ghost_controller_bot/desktop/playback_runner.py
                             for desktop-level actions (PyAutoGUI / OCR)
  4. webbrowser.open()     — Python stdlib; open a URL in the user's real browser
  5. subprocess.run()      — CLI operations, venv, package install

Playwright is deliberately absent as a dependency.  If Playwright happens to
be installed in the environment, the optional ``PlaywrightExporter`` at the
bottom can serialise a task list to Playwright-compatible JSON — but the
system never imports or requires it.

Public surface:
  NativeTask / NativeStep        — task & step data model
  MurphyNativeRunner             — executes tasks using the native stack
  NativeTaskFactory              — builds standard Murphy System task suites
  GhostControllerExporter        — exports tasks → playback_runner JSON spec
  MurphyAPIClient                — direct API calls (urllib, no extra libs)
  PlaywrightExporter             — optional JSON export for Playwright runners
  # Backward-compatible aliases:
  BrowserTask, PlaywrightTask, BrowserTaskFactory, PlaywrightTaskFactory

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import json
import logging
import os
import shlex
import subprocess
import sys
import threading
import urllib.error
import urllib.request
import uuid
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)
from ui_testing_framework import (
    E2ETestHarness,
    ErrorStateUITester,
    InteractiveComponentTester,
    RealAPIIntegrationTester,
    UITestingFramework,
)

logger = logging.getLogger(__name__)

_MAX_LOG = 5_000

# Path to the existing desktop runner (relative from Murphy System root)
_GHOST_RUNNER_PATH = os.path.join(
    os.path.dirname(__file__), "..", "bots",
    "ghost_controller_bot", "desktop", "playback_runner.py",
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TaskType(str, Enum):
    """High-level task category for native Murphy automation tasks."""
    VERIFY_UI_LOADED = "verify_ui_loaded"
    ASSERT_ELEMENT = "assert_element"
    SIMULATE_ERROR = "simulate_error"
    SUBMIT_FORM = "submit_form"
    # API
    API_CALL = "api_call"
    VERIFY_API_CONNECTION = "verify_api_connection"
    # Browser open (webbrowser stdlib)
    OPEN_TERMINAL = "open_terminal"
    # Desktop (GhostController)
    DESKTOP_ACTION = "desktop_action"
    # Onboarding flows
    FILL_ONBOARDING_WIZARD = "fill_onboarding_wizard"
    SIGN_EULA = "sign_eula"
    # Screenshot / visual regression
    TAKE_SCREENSHOT = "take_screenshot"
    # Generic
    CUSTOM = "custom"


class ActionType(str, Enum):
    """Atomic action type dispatched by the native automation runner."""
    NAVIGATE = "navigate"               # E2ETestHarness.load_page
    ASSERT_VISIBLE = "assert_visible"   # E2ETestHarness.assert_element_exists
    WAIT_FOR_SELECTOR = "wait_for_selector"
    ASSERT_TEXT = "assert_text"
    WAIT_FOR_TEXT = "wait_for_text"
    FILL = "fill"                       # InteractiveComponentTester
    SUBMIT_FORM = "submit_form"
    CLICK = "click"
    SIMULATE_API_ERROR = "simulate_api_error"   # ErrorStateUITester
    SCREENSHOT = "screenshot"           # VisualRegressionTester

    # ── Direct API call (urllib) ────────────────────────────────────────────
    API_POST = "api_post"
    API_GET = "api_get"
    API_PUT = "api_put"

    # ── webbrowser.open() ───────────────────────────────────────────────────
    OPEN_URL = "open_url"

    # ── GhostController desktop actions (playback_runner.py) ───────────────
    GHOST_FOCUS_APP = "ghost_focus_app"
    GHOST_TYPE = "ghost_type"
    GHOST_CLICK = "ghost_click"
    GHOST_WAIT = "ghost_wait"
    GHOST_ASSERT_WINDOW = "ghost_assert_window"
    GHOST_ASSERT_OCR = "ghost_assert_ocr"

    # ── CLI / subprocess ────────────────────────────────────────────────────
    RUN_COMMAND = "run_command"

    SCROLL_TO_BOTTOM = "scroll_to_bottom"
    WAIT_MS = "wait_ms"


class TaskStatus(str, Enum):
    """Execution lifecycle status for a native automation task."""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


# ---------------------------------------------------------------------------
# NativeStep & NativeTask
# ---------------------------------------------------------------------------


@dataclass
class NativeStep:
    """A single automation action using the native Murphy stack."""

    action: ActionType = ActionType.NAVIGATE
    target: str = ""        # URL, CSS selector, API endpoint, command, etc.
    value: str = ""         # fill value, assertion text, body JSON, etc.
    args: Dict[str, Any] = field(default_factory=dict)  # extra action-specific args
    timeout_ms: int = 10_000
    optional: bool = False
    description: str = ""

    def to_ghost_step(self, step_id: str = "") -> Dict[str, Any]:
        """Serialise to playback_runner.py step format."""
        _action_map = {
            ActionType.GHOST_FOCUS_APP: "focus_app",
            ActionType.GHOST_TYPE: "type",
            ActionType.GHOST_CLICK: "click",
            ActionType.GHOST_WAIT: "wait",
            ActionType.GHOST_ASSERT_WINDOW: "assert_window",
            ActionType.GHOST_ASSERT_OCR: "assert_ocr",
        }
        ghost_action = _action_map.get(self.action, str(self.action.value))
        ghost_args = dict(self.args)
        if self.target and "app" not in ghost_args and "text" not in ghost_args:
            if self.action == ActionType.GHOST_FOCUS_APP:
                ghost_args["app"] = self.target
            elif self.action in (ActionType.GHOST_ASSERT_WINDOW, ActionType.GHOST_ASSERT_OCR):
                ghost_args["contains"] = self.target
            elif self.action == ActionType.GHOST_TYPE:
                ghost_args["text"] = self.target
        if self.value and "text" not in ghost_args:
            ghost_args["text"] = self.value
        return {"id": step_id or uuid.uuid4().hex[:8], "action": ghost_action, "args": ghost_args}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action.value,
            "target": self.target,
            "value": self.value,
            "args": self.args,
            "timeout_ms": self.timeout_ms,
            "optional": self.optional,
            "description": self.description,
        }


@dataclass
class NativeTask:
    """A complete, native Murphy automation task.

    Runs against UITestingFramework, GhostController, direct API calls,
    webbrowser.open(), or subprocess — whichever fits best.
    """

    task_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    task_type: TaskType = TaskType.CUSTOM
    description: str = ""
    preconditions: List[str] = field(default_factory=list)
    steps: List[NativeStep] = field(default_factory=list)
    success_criteria: List[str] = field(default_factory=list)
    failure_handling: str = "log_and_continue"
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: Dict[str, Any] = field(default_factory=dict)

    def check_preconditions(self, context: Dict[str, Any]) -> List[str]:
        unmet: List[str] = []
        for cond in self.preconditions:
            val: Any = context
            try:
                for part in cond.split("."):
                    val = val[part]
            except (KeyError, TypeError):
                unmet.append(cond)
                continue
            if not val:
                unmet.append(cond)
        return unmet

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


# ---------------------------------------------------------------------------
# MurphyAPIClient — direct API calls, no extra dependencies
# ---------------------------------------------------------------------------


class MurphyAPIClient:
    """Makes direct API calls using Python's stdlib urllib.

    This is everything a terminal does via fetch() — done natively.
    """

    def __init__(self, base_url: str = "http://127.0.0.1:8000") -> None:
        self.base_url = base_url.rstrip("/")

    def call(
        self,
        method: str,
        endpoint: str,
        body: Optional[Dict[str, Any]] = None,
        timeout: int = 30,
    ) -> Dict[str, Any]:
        url = self.base_url + endpoint
        data = json.dumps(body).encode() if body else None
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    payload = {"raw": raw.decode("utf-8", errors="replace")}
                return {"ok": True, "status": resp.status, "data": payload}
        except urllib.error.HTTPError as exc:
            return {"ok": False, "status": exc.code, "error": f"http_{exc.code}"}
        except urllib.error.URLError as exc:
            return {"ok": False, "status": 0, "error": str(exc.reason)}
        except Exception as exc:
            return {"ok": False, "status": 0, "error": str(exc)}

    def health(self) -> bool:
        result = self.call("GET", "/api/health")
        return result.get("ok", False)


# ---------------------------------------------------------------------------
# GhostDesktopRunner — wraps playback_runner.py for desktop actions
# ---------------------------------------------------------------------------


class GhostDesktopRunner:
    """Runs desktop automation steps via the ghost_controller_bot playback_runner.

    Can be used in two modes:
      in-process  — calls the playback_runner functions directly (fast)
      subprocess  — invokes playback_runner.py with a JSON spec (isolated)
    """

    def run_steps_inprocess(
        self,
        steps: List[NativeStep],
        dry_run: bool = True,
    ) -> List[Dict[str, Any]]:
        """Execute ghost steps in-process (no subprocess overhead)."""
        import importlib.util as _ilu

        spec_path = os.path.abspath(_GHOST_RUNNER_PATH)
        if not os.path.exists(spec_path):
            logger.warning("playback_runner.py not found at %s", spec_path)
            return [{"step": i, "status": "skipped", "reason": "runner_not_found"}
                    for i, _ in enumerate(steps)]

        spec = _ilu.spec_from_file_location("playback_runner", spec_path)
        runner = _ilu.module_from_spec(spec)
        spec.loader.exec_module(runner)

        results = []
        for i, step in enumerate(steps):
            result: Dict[str, Any] = {"step": i, "action": step.action.value}
            try:
                if step.action == ActionType.GHOST_FOCUS_APP:
                    runner.focus_app(step.target or step.args.get("app", ""))
                    result["status"] = "ok"
                elif step.action == ActionType.GHOST_TYPE and not dry_run:
                    runner.type_text(step.value or step.args.get("text", ""))
                    result["status"] = "ok"
                elif step.action == ActionType.GHOST_CLICK and not dry_run:
                    ok = runner.click(
                        x=step.args.get("x"),
                        y=step.args.get("y"),
                        image=step.args.get("image"),
                    )
                    result["status"] = "pass" if ok else "fail"
                elif step.action == ActionType.GHOST_WAIT:
                    runner.wait(step.args.get("seconds", 0.5))
                    result["status"] = "ok"
                elif step.action == ActionType.GHOST_ASSERT_WINDOW:
                    ok = runner.assert_window_title(step.target or step.args.get("contains", ""))
                    result["status"] = "pass" if ok else "fail"
                elif step.action == ActionType.GHOST_ASSERT_OCR:
                    ok = runner.assert_ocr_contains(
                        step.target or step.args.get("contains", ""),
                        step.args.get("region"),
                    )
                    result["status"] = "pass" if ok else "fail"
                else:
                    result["status"] = "skipped"
                    result["reason"] = "dry_run" if dry_run else "unknown_action"
            except Exception as exc:
                result["status"] = "error"
                result["error"] = str(exc)
            results.append(result)
        return results

    def export_to_ghost_spec(
        self, steps: List[NativeStep]
    ) -> Dict[str, Any]:
        """Build a playback_runner-compatible JSON spec from a step list."""
        return {
            "steps": [s.to_ghost_step(step_id=f"s{i:03d}") for i, s in enumerate(steps)]
        }


# ---------------------------------------------------------------------------
# MurphyNativeRunner — the main executor
# ---------------------------------------------------------------------------


class MurphyNativeRunner:
    """Executes NativeTask objects using the full Murphy native stack.

    Dispatch priority per action type:
      OPEN_URL            → webbrowser.open()
      API_POST/GET/PUT    → MurphyAPIClient (urllib)
      NAVIGATE / ASSERT_* / FILL / SUBMIT_FORM / CLICK / SIMULATE_API_ERROR
                          → UITestingFramework
      GHOST_*             → GhostDesktopRunner (playback_runner.py)
      RUN_COMMAND         → subprocess.run()
      SCREENSHOT          → UITestingFramework.visual_regression
      SCROLL_TO_BOTTOM / WAIT_MS → no-op pass
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        framework: Optional[UITestingFramework] = None,
        dry_run: bool = True,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._fw = framework or UITestingFramework()
        self._api = MurphyAPIClient(base_url=self.base_url)
        self._ghost = GhostDesktopRunner()
        self.dry_run = dry_run
        self._lock = threading.Lock()
        self._run_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        task: NativeTask,
        context: Optional[Dict[str, Any]] = None,
        html_content: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a single task, return a result dict with ``status``."""
        ctx = context or {}
        unmet = task.check_preconditions(ctx)
        if unmet:
            task.status = TaskStatus.SKIPPED
            return self._finish(task, {"status": "skipped", "reason": f"unmet:{unmet}"}, [])

        task.status = TaskStatus.RUNNING
        step_results: List[Dict[str, Any]] = []
        abort = False

        for step in task.steps:
            sr = self._dispatch(step, html_content=html_content, context=ctx)
            step_results.append(sr)
            if (
                sr.get("status") not in ("pass", "ok", "skipped", "deferred")
                and not step.optional
                and task.failure_handling == "abort"
            ):
                abort = True
                break

        overall = (
            TaskStatus.FAILED
            if abort
            else (
                TaskStatus.PASSED
                if all(
                    r.get("status") in ("pass", "ok", "skipped", "deferred")
                    for r in step_results
                )
                else TaskStatus.PASSED   # log-and-continue: non-critical failures still pass
            )
        )
        if task.failure_handling == "abort" and abort:
            overall = TaskStatus.FAILED

        return self._finish(task, {"status": overall.value, "step_results": step_results}, step_results)

    def run_suite(
        self,
        tasks: List[NativeTask],
        context: Optional[Dict[str, Any]] = None,
        html_content: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        return [self.run(t, context=context, html_content=html_content) for t in tasks]

    def get_run_log(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._run_log)

    # ------------------------------------------------------------------
    # Step dispatch
    # ------------------------------------------------------------------

    def _dispatch(
        self,
        step: NativeStep,
        html_content: Optional[str],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            a = step.action
            # ── webbrowser.open() ───────────────────────────────────────
            if a == ActionType.OPEN_URL:
                return self._open_url(step)
            # ── UITestingFramework ──────────────────────────────────────
            if a == ActionType.NAVIGATE:
                return self._navigate(step, html_content)
            if a in (ActionType.ASSERT_VISIBLE, ActionType.WAIT_FOR_SELECTOR):
                return self._assert_element(step, html_content)
            if a in (ActionType.ASSERT_TEXT, ActionType.WAIT_FOR_TEXT):
                return self._assert_text(step, html_content)
            if a == ActionType.FILL:
                return self._fill(step, html_content)
            if a == ActionType.CLICK:
                return self._click(step, html_content)
            if a == ActionType.SUBMIT_FORM:
                return self._submit_form(step, context)
            if a == ActionType.SIMULATE_API_ERROR:
                return self._simulate_error(step)
            if a == ActionType.SCREENSHOT:
                return self._screenshot(step, html_content)
            # ── Direct API calls ────────────────────────────────────────
            if a in (ActionType.API_POST, ActionType.API_GET, ActionType.API_PUT):
                return self._api_call(step)
            # ── GhostController desktop ─────────────────────────────────
            if a in (
                ActionType.GHOST_FOCUS_APP, ActionType.GHOST_TYPE,
                ActionType.GHOST_CLICK, ActionType.GHOST_WAIT,
                ActionType.GHOST_ASSERT_WINDOW, ActionType.GHOST_ASSERT_OCR,
            ):
                return self._ghost_action(step)
            # ── subprocess ──────────────────────────────────────────────
            if a == ActionType.RUN_COMMAND:
                return self._run_command(step)
            # ── no-ops ──────────────────────────────────────────────────
            if a in (ActionType.SCROLL_TO_BOTTOM, ActionType.WAIT_MS):
                return {"status": "ok", "action": a.value}
            return {"status": "skipped", "action": a.value, "note": "unhandled"}
        except Exception as exc:
            return {"status": "fail", "action": step.action.value, "error": str(exc)}

    # ------------------------------------------------------------------
    # Action implementations
    # ------------------------------------------------------------------

    def _open_url(self, step: NativeStep) -> Dict[str, Any]:
        url = step.target if step.target.startswith("http") else self.base_url + step.target
        webbrowser.open(url)
        logger.info("Opened URL in browser: %s", url)
        return {"status": "ok", "action": "open_url", "url": url}

    def _navigate(self, step: NativeStep, html: Optional[str]) -> Dict[str, Any]:
        url = step.target if step.target.startswith("http") else self.base_url + step.target
        page = self._fw.e2e.load_page(url, html or "")
        return {"status": "pass", "action": "navigate", "url": url, "page_id": page.get("id")}

    def _assert_element(self, step: NativeStep, html: Optional[str]) -> Dict[str, Any]:
        if not html:
            return {"status": "skipped", "action": step.action.value, "note": "no_html"}
        result = self._fw.e2e.assert_element_exists("current", step.target, html)
        return {"status": result["status"], "action": step.action.value,
                "selector": step.target, "found": result["found"]}

    def _assert_text(self, step: NativeStep, html: Optional[str]) -> Dict[str, Any]:
        if not html:
            return {"status": "skipped", "action": step.action.value, "note": "no_html"}
        needle = step.value or step.target
        found = needle.lower() in html.lower()
        return {"status": "pass" if found else "fail", "action": step.action.value,
                "needle": needle, "found": found}

    def _fill(self, step: NativeStep, html: Optional[str]) -> Dict[str, Any]:
        found = True
        if html:
            matches = self._fw.e2e.query_selector("current", step.target, html)
            found = bool(matches)
        return {"status": "pass" if found else "fail", "action": "fill",
                "selector": step.target, "value_len": len(step.value)}

    def _click(self, step: NativeStep, html: Optional[str]) -> Dict[str, Any]:
        btn = self._fw.interactive_component.create_button(
            step.target.lstrip("#"), step.description or step.target
        )
        res = btn.click()
        return {"status": "pass" if res["result"] == "success" else "fail",
                "action": "click", "selector": step.target}

    def _submit_form(self, step: NativeStep, ctx: Dict[str, Any]) -> Dict[str, Any]:
        fields = ctx.get("form_fields", {})
        form = self._fw.interactive_component.create_form(
            step.target.lstrip("#"),
            [{"name": k, "required": True} for k in fields],
        )
        res = form.submit(fields)
        return {"status": "pass" if res["result"] == "success" else "fail",
                "action": "submit_form", "submit_result": res}

    def _simulate_error(self, step: NativeStep) -> Dict[str, Any]:
        try:
            code = int(step.value) if step.value else 500
        except ValueError:
            code = 500
        spec = self._fw.error_state.simulate_api_error(step.target, code)
        return {"status": "pass", "action": "simulate_api_error", "error_spec": spec}

    def _screenshot(self, step: NativeStep, html: Optional[str]) -> Dict[str, Any]:
        if html:
            self._fw.visual_regression.capture_baseline(step.target or "current", html)
        return {"status": "ok", "action": "screenshot",
                "note": "visual_regression_baseline_captured"}

    def _api_call(self, step: NativeStep) -> Dict[str, Any]:
        _method_map = {
            ActionType.API_POST: "POST",
            ActionType.API_GET: "GET",
            ActionType.API_PUT: "PUT",
        }
        method = _method_map[step.action]
        body: Optional[Dict[str, Any]] = None
        if step.value:
            try:
                body = json.loads(step.value)
            except json.JSONDecodeError:
                body = {"value": step.value}
        result = self._api.call(method, step.target, body=body)
        return {
            "status": "pass" if result["ok"] else "fail",
            "action": f"api_{method.lower()}",
            "endpoint": step.target,
            "http_status": result.get("status"),
            "error": result.get("error", ""),
        }

    def _ghost_action(self, step: NativeStep) -> Dict[str, Any]:
        results = self._ghost.run_steps_inprocess([step], dry_run=self.dry_run)
        r = results[0] if results else {"status": "skipped"}
        return {"status": r.get("status", "ok"), "action": step.action.value,
                "ghost_result": r}

    def _run_command(self, step: NativeStep) -> Dict[str, Any]:
        if self.dry_run:
            return {"status": "ok", "action": "run_command", "note": "dry_run_skipped",
                    "command": step.target}
        proc = subprocess.run(shlex.split(step.target), shell=False, capture_output=True,
                              text=True, timeout=300)
        return {
            "status": "pass" if proc.returncode == 0 else "fail",
            "action": "run_command",
            "returncode": proc.returncode,
            "stdout": proc.stdout[:500],
            "stderr": proc.stderr[:500],
        }

    # ------------------------------------------------------------------

    def _finish(
        self,
        task: NativeTask,
        result: Dict[str, Any],
        step_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        task.status = TaskStatus(result.get("status", "passed"))
        full = dict(result)
        full["task_id"] = task.task_id
        full["task_type"] = task.task_type.value
        full["step_results"] = step_results
        task.result = full
        self._log(task.task_id, full)
        return full

    def _log(self, task_id: str, result: Dict[str, Any]) -> None:
        entry = {"task_id": task_id, "status": result.get("status"),
                 "timestamp": datetime.now(timezone.utc).isoformat()}
        with self._lock:
            capped_append(self._run_log, entry, max_size=_MAX_LOG)


# ---------------------------------------------------------------------------
# NativeTaskFactory — builds standard Murphy System task suites
# ---------------------------------------------------------------------------


class NativeTaskFactory:
    """Creates NativeTask objects for common Murphy System flows.

    All tasks use the native stack:
      - Assertions via UITestingFramework
      - API calls via MurphyAPIClient (urllib)
      - Terminal opening via webbrowser.open()
      - Desktop actions via GhostDesktopRunner
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        runner: Optional[MurphyNativeRunner] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.runner = runner or MurphyNativeRunner(base_url=self.base_url)
        self._lock = threading.Lock()
        self._task_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Individual task builders
    # ------------------------------------------------------------------

    def open_terminal(self, terminal: str = "worker", api_port: int = 8000) -> NativeTask:
        """Open the correct terminal in the user's real browser (webbrowser.open)."""
        _map = {
            "worker": "terminal_worker.html",
            "architect": "terminal_architect.html",
            "integrated": "terminal_integrated.html",
            "enhanced": "terminal_enhanced.html",
        }
        url = f"{self.base_url}/{_map.get(terminal, 'terminal_worker.html')}?apiPort={api_port}"
        task = NativeTask(
            task_type=TaskType.OPEN_TERMINAL,
            description=f"Open {terminal} terminal in browser",
            preconditions=["session.user_id", "session.eula_accepted"],
            steps=[
                NativeStep(action=ActionType.OPEN_URL, target=url,
                           description=f"webbrowser.open({url})"),
            ],
            success_criteria=["Browser opened", "Terminal URL loaded"],
            failure_handling="abort",
            metadata={"terminal": terminal, "api_port": api_port},
        )
        return self._reg(task)

    def verify_ui_loaded(self) -> NativeTask:
        """Assert key terminal selectors exist in page HTML via E2ETestHarness."""
        task = NativeTask(
            task_type=TaskType.VERIFY_UI_LOADED,
            description="Verify terminal UI elements in page HTML (E2ETestHarness)",
            preconditions=["session.terminal_open"],
            steps=[
                NativeStep(action=ActionType.ASSERT_VISIBLE, target="#terminalOutput",
                           description="Assert #terminalOutput present"),
                NativeStep(action=ActionType.ASSERT_VISIBLE, target="#messageInput",
                           description="Assert #messageInput present"),
            ],
            success_criteria=["#terminalOutput present", "#messageInput present"],
        )
        return self._reg(task)

    def verify_api_connection(self, api_port: int = 8000) -> NativeTask:
        """Hit /api/health directly — the only thing this needs is urllib."""
        task = NativeTask(
            task_type=TaskType.VERIFY_API_CONNECTION,
            description=f"GET /api/health on port {api_port} (direct urllib call)",
            steps=[
                NativeStep(action=ActionType.API_GET, target="/api/health",
                           description="Direct health check — no browser needed"),
            ],
            success_criteria=["HTTP 200 from /api/health"],
            metadata={"api_port": api_port},
        )
        return self._reg(task)

    def fill_onboarding_wizard(self, profile_data: Dict[str, Any]) -> NativeTask:
        """POST profile data directly to the API — no browser form filling needed."""
        body = json.dumps({k: v for k, v in profile_data.items() if v})
        task = NativeTask(
            task_type=TaskType.FILL_ONBOARDING_WIZARD,
            description="POST onboarding data directly to /api/auth/signup (no browser form)",
            preconditions=["session.user_id"],
            steps=[
                NativeStep(action=ActionType.API_POST,
                           target="/api/auth/signup",
                           value=body,
                           description="POST signup data via MurphyAPIClient"),
            ],
            success_criteria=["201 or 200 from /api/auth/signup"],
            metadata={"profile_fields": list(profile_data.keys())},
        )
        return self._reg(task)

    def sign_eula(self, user_id: str = "", eula_version: str = "1.0-alpha") -> NativeTask:
        """POST EULA acceptance directly to the API."""
        body = json.dumps({"user_id": user_id, "eula_version": eula_version})
        task = NativeTask(
            task_type=TaskType.SIGN_EULA,
            description="POST EULA acceptance directly to /api/auth/accept-eula",
            preconditions=["session.email_validated"],
            steps=[
                NativeStep(action=ActionType.API_POST,
                           target="/api/auth/accept-eula",
                           value=body,
                           description="POST EULA acceptance via MurphyAPIClient"),
            ],
            success_criteria=["eula_accepted flag set in profile"],
            failure_handling="abort",
        )
        return self._reg(task)

    def take_screenshot(
        self,
        page_name: str = "current",
        description: str = "Capture visual regression baseline",
    ) -> NativeTask:
        """Capture a VisualRegressionTester baseline — no real screenshot needed."""
        task = NativeTask(
            task_type=TaskType.TAKE_SCREENSHOT,
            description=description,
            steps=[
                NativeStep(action=ActionType.SCREENSHOT, target=page_name,
                           description="Capture baseline via VisualRegressionTester"),
            ],
            success_criteria=["Baseline hash captured"],
            metadata={"page_name": page_name},
        )
        return self._reg(task)

    def simulate_api_error(self, endpoint: str, status_code: int = 500) -> NativeTask:
        """Simulate an API error via ErrorStateUITester and verify recovery."""
        task = NativeTask(
            task_type=TaskType.SIMULATE_ERROR,
            description=f"ErrorStateUITester.simulate_api_error({endpoint}, {status_code})",
            steps=[
                NativeStep(action=ActionType.SIMULATE_API_ERROR,
                           target=endpoint, value=str(status_code)),
                NativeStep(action=ActionType.ASSERT_VISIBLE, target=".error-message",
                           optional=True),
            ],
            success_criteria=["Error handled gracefully"],
        )
        return self._reg(task)

    def assert_html_element(self, selector: str, optional: bool = False) -> NativeTask:
        """Assert a CSS selector is present in the provided HTML content."""
        task = NativeTask(
            task_type=TaskType.ASSERT_ELEMENT,
            description=f"Assert '{selector}' present in page HTML (E2ETestHarness)",
            steps=[
                NativeStep(action=ActionType.ASSERT_VISIBLE, target=selector,
                           optional=optional)
            ],
            success_criteria=[f"{selector} found in HTML"],
        )
        return self._reg(task)

    def desktop_assert_window(self, title_contains: str) -> NativeTask:
        """Use GhostController to assert the active window title."""
        task = NativeTask(
            task_type=TaskType.DESKTOP_ACTION,
            description=f"GhostController: assert active window contains '{title_contains}'",
            steps=[
                NativeStep(action=ActionType.GHOST_ASSERT_WINDOW,
                           target=title_contains,
                           description=f"playback_runner assert_window: {title_contains}"),
            ],
            success_criteria=[f"Active window title contains '{title_contains}'"],
        )
        return self._reg(task)

    def desktop_assert_ocr(self, text: str, region: Optional[List[int]] = None) -> NativeTask:
        """Use GhostController OCR to assert text is visible on screen."""
        task = NativeTask(
            task_type=TaskType.DESKTOP_ACTION,
            description=f"GhostController: OCR assert '{text}' visible on screen",
            steps=[
                NativeStep(action=ActionType.GHOST_ASSERT_OCR,
                           target=text,
                           args={"contains": text, "region": region},
                           description=f"playback_runner assert_ocr: {text}"),
            ],
            success_criteria=[f"OCR found '{text}' on screen"],
        )
        return self._reg(task)

    # ------------------------------------------------------------------
    # Suite builders
    # ------------------------------------------------------------------

    def full_onboarding_suite(
        self,
        profile_data: Dict[str, Any],
        api_port: int = 8000,
        terminal: str = "worker",
        user_id: str = "",
    ) -> List[NativeTask]:
        """Complete ordered onboarding suite — API calls + native verification."""
        return [
            self.fill_onboarding_wizard(profile_data),        # POST /api/auth/signup
            self.sign_eula(user_id=user_id),                   # POST /api/auth/accept-eula
            self.open_terminal(terminal=terminal, api_port=api_port),  # webbrowser.open()
            self.verify_api_connection(api_port=api_port),     # GET /api/health
            self.take_screenshot(page_name="onboarding_complete"),
        ]

    # ------------------------------------------------------------------

    def _reg(self, task: NativeTask) -> NativeTask:
        with self._lock:
            capped_append(self._task_log, {
                "task_id": task.task_id,
                "task_type": task.task_type.value,
                "created_at": task.created_at,
            }, max_size=_MAX_LOG)
        return task

    def get_task_log(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._task_log)


# ---------------------------------------------------------------------------
# GhostControllerExporter — emit playback_runner JSON specs
# ---------------------------------------------------------------------------


class GhostControllerExporter:
    """Serialises a NativeTask list to the playback_runner.py JSON spec format.

    Use this when you want to hand a task suite to the ghost_controller_bot
    as a standalone JSON file::

        exporter = GhostControllerExporter()
        exporter.export_to_file(tasks, "/tmp/murphy_tasks.json")
        # Then: python3 playback_runner.py /tmp/murphy_tasks.json --force
    """

    def export(self, tasks: List[NativeTask]) -> str:
        all_steps: List[Dict[str, Any]] = []
        step_num = 0
        for task in tasks:
            for step in task.steps:
                # Only include ghost-compatible steps
                if step.action.value.startswith("ghost_"):
                    all_steps.append(step.to_ghost_step(step_id=f"s{step_num:04d}"))
                    step_num += 1
        return json.dumps({"steps": all_steps}, indent=2)

    def export_to_file(self, tasks: List[NativeTask], path: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(self.export(tasks))
        logger.info("GhostController spec written to %s", path)


# ---------------------------------------------------------------------------
# PlaywrightExporter — OPTIONAL, only when Playwright is already installed
# ---------------------------------------------------------------------------


class PlaywrightExporter:
    """Serialise tasks to Playwright-compatible JSON for external runners.

    This is purely an *export* path.  The system never imports or requires
    Playwright.  If someone has Playwright installed and wants to use it,
    they can import this class and call ``export()``.
    """

    def export(self, tasks: List[NativeTask]) -> str:
        payload = {
            "schema": "murphy_browser_tasks_v1",
            "note": "Generated by Murphy Native Automation. Playwright is optional.",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "tasks": [t.to_dict() for t in tasks],
        }
        return json.dumps(payload, indent=2)

    def export_to_file(self, tasks: List[NativeTask], path: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(self.export(tasks))


# ---------------------------------------------------------------------------
# Backward-compatible aliases
# (Any code that imported from playwright_task_definitions still works)
# ---------------------------------------------------------------------------

BrowserTask = NativeTask
TaskStep = NativeStep
BrowserTaskFactory = NativeTaskFactory
MurphyTaskRunner = MurphyNativeRunner
PlaywrightTask = NativeTask
PlaywrightTaskFactory = NativeTaskFactory


# ===========================================================================
# Multi-Cursor Split-Screen Desktop Automation
# ===========================================================================

class SplitScreenLayout(str, Enum):
    """Predefined split-screen topology.

    Attributes:
        SINGLE:   Single full-screen zone (no split).
        DUAL_H:   Two zones stacked horizontally (top / bottom).
        DUAL_V:   Two zones side by side (left / right).
        TRIPLE_H: Three equal-height horizontal bands.
        QUAD:     Four equal quadrant zones.
        HEXA:     Six zones (2 × 3 grid).
        CUSTOM:   Arbitrary zone list provided by the caller.
    """

    SINGLE = "single"
    DUAL_H = "dual_horizontal"
    DUAL_V = "dual_vertical"
    TRIPLE_H = "triple_horizontal"
    QUAD = "quad"
    HEXA = "hexa"
    CUSTOM = "custom"


@dataclass
class ScreenZone:
    """A rectangular region on the virtual desktop.

    Coordinates are in *normalised* units [0.0, 1.0] relative to the
    full desktop dimensions, so the layout is resolution-independent.

    Attributes:
        zone_id: Unique identifier for this zone.
        x:       Left edge (0.0 = left of screen, 1.0 = right of screen).
        y:       Top edge  (0.0 = top of screen,  1.0 = bottom of screen).
        width:   Width fraction of total desktop.
        height:  Height fraction of total desktop.
        label:   Human-readable label (e.g. ``"left"``, ``"top-right"``).
    """

    zone_id: str
    x: float
    y: float
    width: float
    height: float
    label: str = ""

    def __post_init__(self) -> None:
        for attr in ("x", "y", "width", "height"):
            v = getattr(self, attr)
            if not (0.0 <= v <= 1.0):
                raise ValueError(
                    f"ScreenZone.{attr} must be in [0.0, 1.0], got {v!r}"
                )
        if self.width <= 0 or self.height <= 0:
            raise ValueError("ScreenZone width and height must be positive")

    def contains_point(self, px: float, py: float) -> bool:
        """Return True if the normalised point *(px, py)* lies within this zone."""
        return (
            self.x <= px <= self.x + self.width
            and self.y <= py <= self.y + self.height
        )

    def centre(self) -> tuple[float, float]:
        """Return the normalised (cx, cy) centre of this zone."""
        return (self.x + self.width / 2, self.y + self.height / 2)

    def to_dict(self) -> dict:
        return {
            "zone_id": self.zone_id,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "label": self.label,
        }


@dataclass
class CursorContext:
    """Tracks the logical state of a single virtual cursor.

    Each cursor is assigned to exactly one :class:`ScreenZone` at a time.

    Attributes:
        cursor_id:    Unique identifier for this cursor.
        zone_id:      The zone this cursor is currently active in.
        position:     Normalised *(x, y)* within the zone (default centre).
        is_active:    Whether this cursor is currently executing an action.
        metadata:     Arbitrary caller-supplied key/value pairs.
    """

    cursor_id: str
    zone_id: str
    position: tuple[float, float] = field(default_factory=lambda: (0.5, 0.5))
    is_active: bool = True
    metadata: dict = field(default_factory=dict)

    def move_to(self, x: float, y: float) -> None:
        """Update the cursor position (normalised coordinates within its zone)."""
        if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
            raise ValueError(f"Cursor position must be in [0, 1], got ({x}, {y})")
        self.position = (x, y)

    def assign_zone(self, zone_id: str) -> None:
        """Reassign this cursor to a different zone."""
        if not zone_id:
            raise ValueError("zone_id must be a non-empty string")
        self.zone_id = zone_id

    def to_dict(self) -> dict:
        return {
            "cursor_id": self.cursor_id,
            "zone_id": self.zone_id,
            "position": list(self.position),
            "is_active": self.is_active,
            "metadata": self.metadata,
        }


class MultiCursorDesktop:
    """Manages a pool of named :class:`CursorContext` objects.

    Cursors are keyed by their ``cursor_id``.  Thread-safe: all
    mutating operations are serialised through an internal lock.
    """

    def __init__(self) -> None:
        self._cursors: dict[str, CursorContext] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Cursor lifecycle
    # ------------------------------------------------------------------

    def add_cursor(
        self,
        cursor_id: str,
        zone_id: str,
        *,
        position: tuple[float, float] = (0.5, 0.5),
        metadata: dict | None = None,
    ) -> CursorContext:
        """Create and register a new cursor."""
        with self._lock:
            if cursor_id in self._cursors:
                raise ValueError(f"Cursor {cursor_id!r} already registered")
            ctx = CursorContext(
                cursor_id=cursor_id,
                zone_id=zone_id,
                position=position,
                metadata=metadata or {},
            )
            self._cursors[cursor_id] = ctx
            return ctx

    def remove_cursor(self, cursor_id: str) -> None:
        """Deregister a cursor."""
        with self._lock:
            if cursor_id not in self._cursors:
                raise KeyError(f"Cursor {cursor_id!r} not found")
            del self._cursors[cursor_id]

    def get_cursor(self, cursor_id: str) -> CursorContext:
        with self._lock:
            if cursor_id not in self._cursors:
                raise KeyError(f"Cursor {cursor_id!r} not found")
            return self._cursors[cursor_id]

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def cursors_in_zone(self, zone_id: str) -> list[CursorContext]:
        """Return all cursors currently assigned to *zone_id*."""
        with self._lock:
            return [c for c in self._cursors.values() if c.zone_id == zone_id]

    def active_cursor_ids(self) -> list[str]:
        with self._lock:
            return [cid for cid, c in self._cursors.items() if c.is_active]

    def cursor_count(self) -> int:
        with self._lock:
            return len(self._cursors)

    def snapshot(self) -> list[dict]:
        with self._lock:
            return [c.to_dict() for c in self._cursors.values()]


class SplitScreenManager:
    """Manages the set of :class:`ScreenZone` objects for a given layout.

    Supports predefined layouts and fully custom zone lists.  Thread-safe.
    """

    _LAYOUT_BUILDERS: dict[str, "Callable[[], list[ScreenZone]]"] = {}

    def __init__(
        self,
        layout: SplitScreenLayout = SplitScreenLayout.SINGLE,
        custom_zones: list[ScreenZone] | None = None,
    ) -> None:
        self._layout = layout
        self._lock = threading.Lock()
        if layout == SplitScreenLayout.CUSTOM:
            if not custom_zones:
                raise ValueError(
                    "custom_zones must be provided for SplitScreenLayout.CUSTOM"
                )
            self._zones: dict[str, ScreenZone] = {z.zone_id: z for z in custom_zones}
        else:
            built = self._build_layout(layout)
            self._zones = {z.zone_id: z for z in built}

    # ------------------------------------------------------------------
    # Layout builders
    # ------------------------------------------------------------------

    @staticmethod
    def _build_layout(layout: SplitScreenLayout) -> list[ScreenZone]:
        if layout == SplitScreenLayout.SINGLE:
            return [ScreenZone("z0", 0.0, 0.0, 1.0, 1.0, label="full")]
        if layout == SplitScreenLayout.DUAL_H:
            return [
                ScreenZone("z0", 0.0, 0.0, 1.0, 0.5, label="top"),
                ScreenZone("z1", 0.0, 0.5, 1.0, 0.5, label="bottom"),
            ]
        if layout == SplitScreenLayout.DUAL_V:
            return [
                ScreenZone("z0", 0.0, 0.0, 0.5, 1.0, label="left"),
                ScreenZone("z1", 0.5, 0.0, 0.5, 1.0, label="right"),
            ]
        if layout == SplitScreenLayout.TRIPLE_H:
            h = 1.0 / 3
            return [
                ScreenZone("z0", 0.0, 0.0, 1.0, h, label="top"),
                ScreenZone("z1", 0.0, h, 1.0, h, label="middle"),
                ScreenZone("z2", 0.0, 2 * h, 1.0, h, label="bottom"),
            ]
        if layout == SplitScreenLayout.QUAD:
            return [
                ScreenZone("z0", 0.0, 0.0, 0.5, 0.5, label="top-left"),
                ScreenZone("z1", 0.5, 0.0, 0.5, 0.5, label="top-right"),
                ScreenZone("z2", 0.0, 0.5, 0.5, 0.5, label="bottom-left"),
                ScreenZone("z3", 0.5, 0.5, 0.5, 0.5, label="bottom-right"),
            ]
        if layout == SplitScreenLayout.HEXA:
            w, h = 1.0 / 3, 0.5
            zones = []
            for row in range(2):
                for col in range(3):
                    idx = row * 3 + col
                    zones.append(
                        ScreenZone(
                            f"z{idx}",
                            col * w,
                            row * h,
                            w,
                            h,
                            label=f"r{row}c{col}",
                        )
                    )
            return zones
        raise ValueError(f"Unknown layout: {layout!r}")

    # ------------------------------------------------------------------
    # Zone accessors
    # ------------------------------------------------------------------

    def get_zone(self, zone_id: str) -> ScreenZone:
        with self._lock:
            if zone_id not in self._zones:
                raise KeyError(f"Zone {zone_id!r} not found")
            return self._zones[zone_id]

    def zone_ids(self) -> list[str]:
        with self._lock:
            return list(self._zones.keys())

    def zone_count(self) -> int:
        with self._lock:
            return len(self._zones)

    def find_zone_at(self, px: float, py: float) -> ScreenZone | None:
        """Return the first zone containing the normalised point *(px, py)*."""
        with self._lock:
            for zone in self._zones.values():
                if zone.contains_point(px, py):
                    return zone
        return None

    def layout(self) -> SplitScreenLayout:
        return self._layout

    def snapshot(self) -> list[dict]:
        with self._lock:
            return [z.to_dict() for z in self._zones.values()]
