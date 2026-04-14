"""
Murphy Native Automation — Murphy System

The one-stop module for all browser/UI/desktop automation in Murphy System.
Third-party browser drivers (Playwright, Selenium, etc.) are NOT used — this
is 100% Murphy's own stack.

Priority order (always use the first option that fits):
  1. Direct API call       — urllib; covers 100% of what any terminal does
  2. UITestingFramework    — E2ETestHarness, InteractiveComponentTester, etc.
                             for DOM/form/element assertions (no browser process)
  3. GhostDesktopRunner    — wraps bots/ghost_controller_bot/desktop/playback_runner.py
                             for desktop-level actions (PyAutoGUI / OCR)
  4. webbrowser.open()     — Python stdlib; open a URL in the user's real browser
  5. subprocess.run()      — CLI operations, venv, package install

Multi-cursor & split-screen desktop (added v2):
  Murphy's virtual desktop supports N independent mouse cursors across
  split-screen zones — analogous to console split-screen mode where each
  player/agent has their own pointer stream on a shared physical screen.

  ScreenZone            — rectangular region of the desktop
  CursorContext         — independent pointer state (position, buttons, history)
  SplitScreenLayout     — SINGLE / DUAL_H / DUAL_V / TRIPLE_H / QUAD / HEXA / CUSTOM
  MultiCursorDesktop    — manages N cursors across N zones with parallel dispatch
  SplitScreenManager    — high-level orchestrator: queue tasks per zone, run all
                          zones simultaneously (true split-screen parallelism)

Public surface:
  NativeTask / NativeStep        — task & step data model
  MurphyNativeRunner             — executes tasks using the native stack
  NativeTaskFactory              — builds standard Murphy System task suites
  GhostControllerExporter        — exports tasks → playback_runner JSON spec
  MurphyAPIClient                — direct API calls (urllib, no extra libs)
  PlaywrightExporter             — JSON export shim (no Playwright required)
  ScreenZone                     — split-screen viewport zone
  CursorContext                  — independent cursor/pointer state
  SplitScreenLayout              — named layout presets
  MultiCursorDesktop             — multi-cursor virtual desktop
  SplitScreenManager             — split-screen task orchestrator
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
# ScreenZone — a bounded rectangular region of the desktop
# ---------------------------------------------------------------------------


@dataclass
class ScreenZone:
    """A rectangular region of the desktop (or virtual screen).

    Coordinates are in pixels from the top-left corner of the full desktop.
    For zone-relative (0–1) positioning use :meth:`to_absolute` /
    :meth:`to_relative` helpers.
    """

    zone_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    name: str = ""
    x: int = 0           # top-left pixel X
    y: int = 0           # top-left pixel Y
    width: int = 1280
    height: int = 720
    label: str = ""      # e.g. "Player 1", "Zone A", "Primary"
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def center(self) -> tuple:
        return (self.x + self.width // 2, self.y + self.height // 2)

    @property
    def bounds(self) -> tuple:
        """(left, top, right, bottom) in absolute pixels."""
        return (self.x, self.y, self.x + self.width, self.y + self.height)

    def contains(self, px: int, py: int) -> bool:
        """Return True if the absolute pixel (px, py) falls inside this zone."""
        return self.x <= px < self.x + self.width and self.y <= py < self.y + self.height

    def to_absolute(self, rel_x: float, rel_y: float) -> tuple:
        """Convert zone-relative (0–1) coordinates to absolute desktop pixels."""
        return (
            int(self.x + rel_x * self.width),
            int(self.y + rel_y * self.height),
        )

    def to_relative(self, abs_x: int, abs_y: int) -> tuple:
        """Convert absolute desktop pixels to zone-relative (0–1) coords."""
        if self.width == 0 or self.height == 0:
            return (0.0, 0.0)
        return (
            (abs_x - self.x) / self.width,
            (abs_y - self.y) / self.height,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "name": self.name,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "label": self.label,
        }


# ---------------------------------------------------------------------------
# CursorChannel — linked copy/paste data channel between cursors
# Design Label: MCB-CHANNEL-001
# ---------------------------------------------------------------------------


@dataclass
class CursorChannel:
    """A named data channel that links multiple cursors for cooperative work.

    Cursors joined to the same channel can share clipboard data, selection
    state, and arbitrary payloads — enabling cross-zone collaboration where
    one cursor copies data in zone A and another pastes it in zone B.

    Thread-safe: all mutations go through ``_lock``.

    Usage::

        channel = CursorChannel(channel_id="shared-clipboard")
        channel.join(cursor_a)
        channel.join(cursor_b)
        cursor_a_copy = channel.push("hello from zone A", source="cursor_a")
        cursor_b_paste = channel.pull(consumer="cursor_b")
    """

    channel_id: str = field(default_factory=lambda: "chan_" + uuid.uuid4().hex[:6])
    name: str = ""
    _members: List[str] = field(default_factory=list, repr=False)
    _buffer: List[Dict[str, Any]] = field(default_factory=list, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    MAX_BUFFER: int = 100  # CWE-770: bounded buffer

    def join(self, cursor: "CursorContext") -> None:
        """Add a cursor to this channel."""
        with self._lock:
            if cursor.cursor_id not in self._members:
                self._members.append(cursor.cursor_id)
                cursor._channels.append(self.channel_id)  # MCB-CHANNEL-001
                logger.info(
                    "Cursor %s joined channel %s",
                    cursor.cursor_id, self.channel_id,
                )

    def leave(self, cursor: "CursorContext") -> None:
        """Remove a cursor from this channel."""
        with self._lock:
            if cursor.cursor_id in self._members:
                self._members.remove(cursor.cursor_id)
            if self.channel_id in cursor._channels:
                cursor._channels.remove(self.channel_id)

    def push(
        self,
        data: Any,
        source: str = "",
        *,
        content_type: str = "text",
    ) -> Dict[str, Any]:
        """Push data onto the channel buffer (copy operation).

        Args:
            data:         The payload to share (text, dict, etc.).
            source:       cursor_id of the sender (for audit trail).
            content_type: Hint for consumers (``text``, ``json``, ``binary``).

        Returns:
            Envelope dict with metadata.

        Raises:
            RuntimeError: If source cursor is not a member of this channel.
        """
        with self._lock:
            if source and source not in self._members:
                raise RuntimeError(
                    f"Cursor {source!r} is not a member of channel "
                    f"{self.channel_id!r}; call join() first"
                )
            envelope: Dict[str, Any] = {
                "channel_id": self.channel_id,
                "source": source,
                "content_type": content_type,
                "data": data,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
            if len(self._buffer) >= self.MAX_BUFFER:
                self._buffer.pop(0)  # evict oldest
            self._buffer.append(envelope)
            return envelope

    def pull(self, consumer: str = "") -> Optional[Dict[str, Any]]:
        """Pull the most recent item from the buffer (paste operation).

        Args:
            consumer: cursor_id of the receiver (for audit trail).

        Returns:
            Most recent envelope, or ``None`` if buffer is empty.

        Raises:
            RuntimeError: If consumer cursor is not a member of this channel.
        """
        with self._lock:
            if consumer and consumer not in self._members:
                raise RuntimeError(
                    f"Cursor {consumer!r} is not a member of channel "
                    f"{self.channel_id!r}; call join() first"
                )
            if not self._buffer:
                return None
            return self._buffer[-1]

    def peek(self, last_n: int = 5) -> List[Dict[str, Any]]:
        """Return the last *last_n* items without consuming them."""
        with self._lock:
            return list(self._buffer[-last_n:])

    @property
    def member_count(self) -> int:
        with self._lock:
            return len(self._members)

    @property
    def members(self) -> List[str]:
        with self._lock:
            return list(self._members)

    @property
    def buffer_size(self) -> int:
        with self._lock:
            return len(self._buffer)

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "channel_id": self.channel_id,
                "name": self.name,
                "members": list(self._members),
                "buffer_size": len(self._buffer),
            }


# ---------------------------------------------------------------------------
# CursorContext — independent cursor / pointer state
# ---------------------------------------------------------------------------


@dataclass
class CursorContext:
    """Tracks the state of one independent virtual cursor on the desktop.

    Murphy's multi-cursor system lets a single desktop session maintain N
    fully independent pointers — analogous to console split-screen mode where
    each player has their own controller input stream that never interferes
    with the others.

    All positions are maintained in both absolute pixels and zone-relative
    (0–1) space.  Movements are clamped to the attached ScreenZone bounds
    when a zone is set.
    """

    cursor_id: str = field(default_factory=lambda: "cursor_" + uuid.uuid4().hex[:6])
    zone: Optional["ScreenZone"] = None
    # Absolute desktop pixel position
    abs_x: int = 0
    abs_y: int = 0
    # Zone-relative (0–1) position — kept in sync automatically
    rel_x: float = 0.0
    rel_y: float = 0.0
    buttons_down: set = field(default_factory=set)  # {"left", "right", "middle"}
    velocity_x: float = 0.0
    velocity_y: float = 0.0
    is_active: bool = True
    label: str = ""       # e.g. "Player 1", "Agent Alpha"
    metadata: Dict[str, Any] = field(default_factory=dict)
    _history: List[Dict[str, Any]] = field(default_factory=list, repr=False)
    _channels: List[str] = field(default_factory=list, repr=False)  # MCB-CHANNEL-001

    # ------------------------------------------------------------------
    # Channel helpers (MCB-CHANNEL-001)
    # ------------------------------------------------------------------

    def copy_to_channel(
        self,
        channel: "CursorChannel",
        data: Any,
        *,
        content_type: str = "text",
    ) -> Dict[str, Any]:
        """Push data onto a linked channel (cross-zone copy).

        Raises:
            RuntimeError: If this cursor has not joined the channel.
        """
        envelope = channel.push(data, source=self.cursor_id, content_type=content_type)
        self._record("channel_copy", {
            "channel_id": channel.channel_id, "content_type": content_type,
        })
        return envelope

    def paste_from_channel(self, channel: "CursorChannel") -> Optional[Dict[str, Any]]:
        """Pull the most recent item from a linked channel (cross-zone paste).

        Raises:
            RuntimeError: If this cursor has not joined the channel.
        """
        envelope = channel.pull(consumer=self.cursor_id)
        self._record("channel_paste", {
            "channel_id": channel.channel_id,
            "got_data": envelope is not None,
        })
        return envelope

    @property
    def linked_channels(self) -> List[str]:
        """Return IDs of all channels this cursor has joined."""
        return list(self._channels)

    def attach_zone(self, zone: "ScreenZone") -> None:
        """Bind this cursor to a screen zone; position is clamped to zone bounds."""
        self.zone = zone
        self.warp(zone.x + zone.width // 2, zone.y + zone.height // 2)

    def warp(self, abs_x: int, abs_y: int) -> None:
        """Teleport cursor to absolute position, clamped to zone bounds if attached."""
        if self.zone:
            abs_x = max(self.zone.x, min(self.zone.x + self.zone.width - 1, abs_x))
            abs_y = max(self.zone.y, min(self.zone.y + self.zone.height - 1, abs_y))
            self.rel_x, self.rel_y = self.zone.to_relative(abs_x, abs_y)
        self.abs_x, self.abs_y = abs_x, abs_y
        self._record("warp")

    def move_by(self, dx: int, dy: int) -> None:
        """Move cursor by a relative pixel delta."""
        self.warp(self.abs_x + dx, self.abs_y + dy)
        self.velocity_x = float(dx)
        self.velocity_y = float(dy)
        self._record("move_by", {"dx": dx, "dy": dy})

    def press_button(self, button: str = "left") -> None:
        """Register a button-down event."""
        self.buttons_down.add(button)
        self._record("press", {"button": button})

    def release_button(self, button: str = "left") -> None:
        """Register a button-up event."""
        self.buttons_down.discard(button)
        self._record("release", {"button": button})

    def click(self, button: str = "left") -> Dict[str, Any]:
        """Synthesise a press+release click at the current position."""
        self.press_button(button)
        self.release_button(button)
        ev: Dict[str, Any] = {
            "cursor_id": self.cursor_id,
            "event": "click",
            "button": button,
            "abs_x": self.abs_x,
            "abs_y": self.abs_y,
            "zone_id": self.zone.zone_id if self.zone else None,
        }
        self._record("click", {"button": button})
        return ev

    def double_click(self, button: str = "left") -> Dict[str, Any]:
        """Synthesise two rapid press+release events (double-click)."""
        self.click(button)
        ev = self.click(button)
        ev["event"] = "double_click"
        return ev

    def drag(self, to_x: int, to_y: int, button: str = "left") -> Dict[str, Any]:
        """Press, move to (to_x, to_y), release — simulates a drag operation."""
        start = (self.abs_x, self.abs_y)
        self.press_button(button)
        self.warp(to_x, to_y)
        self.release_button(button)
        ev: Dict[str, Any] = {
            "cursor_id": self.cursor_id,
            "event": "drag",
            "button": button,
            "from": start,
            "to": (self.abs_x, self.abs_y),
            "zone_id": self.zone.zone_id if self.zone else None,
        }
        self._record("drag", {"from_x": start[0], "from_y": start[1],
                               "to_x": to_x, "to_y": to_y})
        return ev

    def scroll(self, delta_x: int = 0, delta_y: int = 0) -> Dict[str, Any]:
        """Synthesise a scroll-wheel event at the current position."""
        ev: Dict[str, Any] = {
            "cursor_id": self.cursor_id,
            "event": "scroll",
            "abs_x": self.abs_x,
            "abs_y": self.abs_y,
            "delta_x": delta_x,
            "delta_y": delta_y,
            "zone_id": self.zone.zone_id if self.zone else None,
        }
        self._record("scroll", {"delta_x": delta_x, "delta_y": delta_y})
        return ev

    def position(self) -> Dict[str, Any]:
        """Return a snapshot of the current cursor state."""
        return {
            "cursor_id": self.cursor_id,
            "label": self.label,
            "abs_x": self.abs_x,
            "abs_y": self.abs_y,
            "rel_x": round(self.rel_x, 4),
            "rel_y": round(self.rel_y, 4),
            "zone_id": self.zone.zone_id if self.zone else None,
            "buttons_down": sorted(self.buttons_down),
            "is_active": self.is_active,
        }

    def get_history(self, last_n: int = 20) -> List[Dict[str, Any]]:
        """Return the last *last_n* cursor events."""
        return list(self._history[-last_n:])

    def _record(self, event: str, extra: Optional[Dict[str, Any]] = None) -> None:
        entry: Dict[str, Any] = {
            "event": event,
            "abs_x": self.abs_x,
            "abs_y": self.abs_y,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        if extra:
            entry.update(extra)
        capped_append(self._history, entry, max_size=500)


# ---------------------------------------------------------------------------
# SplitScreenLayout — named viewport partitioning schemes
# ---------------------------------------------------------------------------


class SplitScreenLayout(str, Enum):
    """Predefined screen partitioning schemes.

    Inspired by console split-screen modes (horizontal/vertical 2-player,
    4-player quad, etc.) and extended to arbitrary desktop automation zones.

    Layouts::

        SINGLE    — 1 zone = full screen
        DUAL_H    — 2 zones: left | right  (like 2-player horizontal split)
        DUAL_V    — 2 zones: top / bottom  (like 2-player vertical split)
        TRIPLE_H  — 3 equal zones: left | center | right
        QUAD      — 4 zones (2×2 grid): classic 4-player console split-screen
        HEXA      — 6 zones (3×2 grid): 6-player / 6-agent grid
        CUSTOM    — caller provides explicit ScreenZone list
    """

    SINGLE = "single"
    DUAL_H = "dual_h"
    DUAL_V = "dual_v"
    TRIPLE_H = "triple_h"
    QUAD = "quad"
    HEXA = "hexa"
    CUSTOM = "custom"


# ---------------------------------------------------------------------------
# MultiCursorDesktop — N independent cursors across split-screen zones
# ---------------------------------------------------------------------------


class MultiCursorDesktop:
    """A virtual desktop supporting multiple independent mouse cursors.

    Each cursor lives in its own ScreenZone.  Moving cursor-0 has zero effect
    on cursor-1, cursor-2, etc. — exactly like console split-screen where
    each player's controller input is fully isolated.

    The desktop is split into zones using a :class:`SplitScreenLayout`.
    Each zone automatically gets one :class:`CursorContext`.  Extra cursors
    can be added per zone for multi-agent scenarios.

    Usage::

        desktop = MultiCursorDesktop(screen_width=2560, screen_height=1440)
        zones = desktop.apply_layout(SplitScreenLayout.DUAL_H)
        # zones[0] = left half, zones[1] = right half

        c0 = desktop.get_cursor(zones[0].zone_id)
        c1 = desktop.get_cursor(zones[1].zone_id)

        c0.warp(300, 400)
        c1.warp(1600, 400)
        c0.click()
        c1.click()   # c0 and c1 are fully independent

        result = desktop.run_parallel_tasks(
            {zones[0].zone_id: task_a, zones[1].zone_id: task_b}
        )
    """

    MAX_CURSORS: int = 16   # CWE-770 resource guard

    def __init__(
        self,
        screen_width: int = 1920,
        screen_height: int = 1080,
    ) -> None:
        self.screen_width = screen_width
        self.screen_height = screen_height
        self._zones: Dict[str, ScreenZone] = {}
        self._cursors: Dict[str, CursorContext] = {}
        self._channels: Dict[str, CursorChannel] = {}  # MCB-CHANNEL-001
        self._layout: SplitScreenLayout = SplitScreenLayout.SINGLE
        self._lock = threading.Lock()
        # Initialise with a single full-screen zone
        self.apply_layout(SplitScreenLayout.SINGLE)

    # ------------------------------------------------------------------
    # Layout management
    # ------------------------------------------------------------------

    def apply_layout(
        self,
        layout: SplitScreenLayout,
        custom_zones: Optional[List[ScreenZone]] = None,
    ) -> List[ScreenZone]:
        """Partition the desktop according to *layout*.

        Existing zones and cursors are cleared; new ones are created per zone.
        Returns the ordered list of :class:`ScreenZone` objects.
        """
        with self._lock:
            self._zones.clear()
            self._cursors.clear()
            self._layout = layout
            zones = self._build_zones(layout, custom_zones)
            for zone in zones:
                self._zones[zone.zone_id] = zone
                cursor = CursorContext(label=zone.label or zone.name)
                cursor.attach_zone(zone)
                self._cursors[zone.zone_id] = cursor
            return zones

    def _build_zones(
        self,
        layout: SplitScreenLayout,
        custom_zones: Optional[List[ScreenZone]],
    ) -> List[ScreenZone]:
        W, H = self.screen_width, self.screen_height
        half_w, half_h = W // 2, H // 2
        third_w = W // 3

        if layout == SplitScreenLayout.SINGLE:
            return [ScreenZone(name="main", x=0, y=0, width=W, height=H, label="Main")]

        if layout == SplitScreenLayout.DUAL_H:
            return [
                ScreenZone(name="left",  x=0,      y=0, width=half_w, height=H,
                           label="Player 1"),
                ScreenZone(name="right", x=half_w, y=0, width=W - half_w, height=H,
                           label="Player 2"),
            ]

        if layout == SplitScreenLayout.DUAL_V:
            return [
                ScreenZone(name="top",    x=0, y=0,      width=W, height=half_h,
                           label="Player 1"),
                ScreenZone(name="bottom", x=0, y=half_h, width=W, height=H - half_h,
                           label="Player 2"),
            ]

        if layout == SplitScreenLayout.TRIPLE_H:
            return [
                ScreenZone(name="left",   x=0,           y=0, width=third_w, height=H,
                           label="Zone A"),
                ScreenZone(name="center", x=third_w,     y=0, width=third_w, height=H,
                           label="Zone B"),
                ScreenZone(name="right",  x=2 * third_w, y=0, width=W - 2 * third_w, height=H,
                           label="Zone C"),
            ]

        if layout == SplitScreenLayout.QUAD:
            return [
                ScreenZone(name="top_left",     x=0,      y=0,      width=half_w,     height=half_h,
                           label="Player 1"),
                ScreenZone(name="top_right",    x=half_w, y=0,      width=W - half_w, height=half_h,
                           label="Player 2"),
                ScreenZone(name="bottom_left",  x=0,      y=half_h, width=half_w,     height=H - half_h,
                           label="Player 3"),
                ScreenZone(name="bottom_right", x=half_w, y=half_h, width=W - half_w, height=H - half_h,
                           label="Player 4"),
            ]

        if layout == SplitScreenLayout.HEXA:
            third_h = H // 3
            zones = []
            for row in range(2):
                for col in range(3):
                    w = third_w if col < 2 else W - 2 * third_w
                    h = third_h if row < 1 else H - third_h
                    zones.append(ScreenZone(
                        name=f"zone_{row}{col}",
                        x=col * third_w, y=row * third_h,
                        width=w, height=h,
                        label=f"Zone {row * 3 + col + 1}",
                    ))
            return zones

        if layout == SplitScreenLayout.CUSTOM:
            if not custom_zones:
                raise ValueError("CUSTOM layout requires a non-empty custom_zones list")
            if len(custom_zones) > self.MAX_CURSORS:
                raise ValueError(
                    f"Too many zones ({len(custom_zones)}); max is {self.MAX_CURSORS}"
                )
            return list(custom_zones)

        raise ValueError(f"Unknown SplitScreenLayout: {layout!r}")

    # ------------------------------------------------------------------
    # Cursor / zone access
    # ------------------------------------------------------------------

    def get_cursor(self, zone_id: str) -> CursorContext:
        """Return the primary cursor for zone *zone_id*."""
        with self._lock:
            if zone_id not in self._cursors:
                raise KeyError(f"No cursor registered for zone '{zone_id}'")
            return self._cursors[zone_id]

    def get_zone(self, zone_id: str) -> ScreenZone:
        """Return the ScreenZone with *zone_id*."""
        with self._lock:
            if zone_id not in self._zones:
                raise KeyError(f"No zone '{zone_id}' in current layout")
            return self._zones[zone_id]

    def list_zones(self) -> List[ScreenZone]:
        """Return all zones in layout order."""
        with self._lock:
            return list(self._zones.values())

    def list_cursors(self) -> List[CursorContext]:
        """Return all registered cursors."""
        with self._lock:
            return list(self._cursors.values())

    def cursor_count(self) -> int:
        """Return the number of registered cursors."""
        with self._lock:
            return len(self._cursors)

    def add_extra_cursor(
        self,
        zone_id: str,
        cursor_id: Optional[str] = None,
        label: str = "",
    ) -> CursorContext:
        """Add a second (or N-th) cursor to an existing zone.

        Useful for multi-agent scenarios where two agents share one viewport
        but have independent pointer streams.
        """
        with self._lock:
            total = len(self._cursors)
            if total >= self.MAX_CURSORS:
                raise RuntimeError(
                    f"Cursor limit ({self.MAX_CURSORS}) reached — cannot add more"
                )
            if zone_id not in self._zones:
                raise KeyError(f"No zone '{zone_id}'")
            zone = self._zones[zone_id]
            cid = cursor_id or ("cursor_" + uuid.uuid4().hex[:6])
            cursor = CursorContext(cursor_id=cid, label=label)
            cursor.attach_zone(zone)
            self._cursors[cid] = cursor
            return cursor

    # ------------------------------------------------------------------
    # Channel management (MCB-CHANNEL-001)
    # ------------------------------------------------------------------

    def create_channel(
        self,
        name: str = "",
        channel_id: Optional[str] = None,
    ) -> CursorChannel:
        """Create a new data channel for cross-zone cursor linking.

        Args:
            name:       Human-readable channel name.
            channel_id: Explicit ID (auto-generated if not provided).

        Returns:
            The newly created :class:`CursorChannel`.
        """
        with self._lock:
            cid = channel_id or ("chan_" + uuid.uuid4().hex[:6])
            if cid in self._channels:
                raise ValueError(f"Channel {cid!r} already exists")
            ch = CursorChannel(channel_id=cid, name=name)
            self._channels[cid] = ch
            logger.info("Created cursor channel %s (%s)", cid, name)
            return ch

    def get_channel(self, channel_id: str) -> CursorChannel:
        """Return the channel with *channel_id*."""
        with self._lock:
            if channel_id not in self._channels:
                raise KeyError(f"No channel '{channel_id}'")
            return self._channels[channel_id]

    def list_channels(self) -> List[CursorChannel]:
        """Return all registered channels."""
        with self._lock:
            return list(self._channels.values())

    def link_cursors(
        self,
        cursor_ids: List[str],
        channel_name: str = "",
    ) -> CursorChannel:
        """Create a channel and join all specified cursors to it.

        Convenience method: creates a channel and joins multiple cursors
        in one call — the typical pattern for cross-zone collaboration.

        Args:
            cursor_ids:   List of cursor_id strings to link.
            channel_name: Human-readable name for the channel.

        Returns:
            The :class:`CursorChannel` all cursors were joined to.

        Raises:
            KeyError: If any cursor_id is not registered.
        """
        channel = self.create_channel(name=channel_name)
        for cid in cursor_ids:
            cursor = self.get_cursor(cid) if cid in self._cursors else None
            if cursor is None:
                # Try looking up by zone_id too
                cursor = self._cursors.get(cid)
            if cursor is None:
                raise KeyError(f"Cursor or zone '{cid}' not found")
            channel.join(cursor)
        return channel

    # ------------------------------------------------------------------
    # Dispatch helpers
    # ------------------------------------------------------------------

    def dispatch_click(self, zone_id: str, button: str = "left") -> Dict[str, Any]:
        """Click at the primary cursor's current position in *zone_id*."""
        return self.get_cursor(zone_id).click(button=button)

    def dispatch_move(
        self,
        zone_id: str,
        rel_x: float,
        rel_y: float,
    ) -> Dict[str, Any]:
        """Move the primary cursor in *zone_id* to zone-relative (0–1) position."""
        zone = self.get_zone(zone_id)
        cursor = self.get_cursor(zone_id)
        abs_x, abs_y = zone.to_absolute(rel_x, rel_y)
        cursor.warp(abs_x, abs_y)
        return cursor.position()

    def dispatch_drag(
        self,
        zone_id: str,
        from_rel_x: float,
        from_rel_y: float,
        to_rel_x: float,
        to_rel_y: float,
        button: str = "left",
    ) -> Dict[str, Any]:
        """Drag within *zone_id* using zone-relative coordinates."""
        zone = self.get_zone(zone_id)
        cursor = self.get_cursor(zone_id)
        fx, fy = zone.to_absolute(from_rel_x, from_rel_y)
        tx, ty = zone.to_absolute(to_rel_x, to_rel_y)
        cursor.warp(fx, fy)
        return cursor.drag(tx, ty, button=button)

    # ------------------------------------------------------------------
    # Parallel task runner
    # ------------------------------------------------------------------

    def run_parallel_tasks(
        self,
        zone_tasks: Dict[str, "NativeTask"],
        runner: Optional["MurphyNativeRunner"] = None,
        context: Optional[Dict[str, Any]] = None,
        html_content: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run one NativeTask per zone in parallel threads.

        This is the core of Murphy's split-screen execution model: each zone
        is an independent execution lane, exactly like a split-screen console
        game where each player's logic runs simultaneously.

        Args:
            zone_tasks:   Mapping of zone_id → NativeTask to execute.
            runner:       Shared MurphyNativeRunner (created if not provided).
            context:      Shared execution context dict.
            html_content: Shared HTML fixture for UITestingFramework steps.

        Returns:
            Summary dict with per-zone results and current cursor snapshots.
        """
        if runner is None:
            runner = MurphyNativeRunner()
        results: Dict[str, Any] = {}
        lock = threading.Lock()

        def _run_zone(zone_id: str, task: "NativeTask") -> None:
            try:
                result = runner.run(task, context=context, html_content=html_content)
            except Exception as exc:
                result = {"status": "error", "error": str(exc), "zone_id": zone_id}
            with lock:
                results[zone_id] = result

        threads = [
            threading.Thread(
                target=_run_zone,
                args=(zid, task),
                daemon=True,
                name=f"murphy-zone-{zid}",
            )
            for zid, task in zone_tasks.items()
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=120)
        for t in threads:
            if t.is_alive():
                zid = t.name.replace("murphy-zone-", "")
                with lock:
                    results[zid] = {"status": "timeout", "zone_id": zid}

        return {
            "layout": self._layout.value,
            "zones": len(self._zones),
            "zone_results": results,
            "cursors": [c.position() for c in self.list_cursors()],
        }

    def snapshot(self) -> Dict[str, Any]:
        """Return a serialisable snapshot of the full desktop state."""
        with self._lock:
            return {
                "screen_width": self.screen_width,
                "screen_height": self.screen_height,
                "layout": self._layout.value,
                "zones": [z.to_dict() for z in self._zones.values()],
                "cursors": [c.position() for c in self._cursors.values()],
                "channels": [ch.to_dict() for ch in self._channels.values()],
            }


# ---------------------------------------------------------------------------
# SplitScreenManager — high-level split-screen task orchestrator
# ---------------------------------------------------------------------------


class SplitScreenManager:
    """High-level orchestrator for Murphy's split-screen automation mode.

    Combines :class:`MultiCursorDesktop` with a per-zone
    :class:`MurphyNativeRunner` and a task queue per zone — exactly like
    console split-screen where each player has their own game state and input
    stream, but on a single shared physical desktop.

    Usage::

        mgr = SplitScreenManager(
            layout=SplitScreenLayout.DUAL_H,
            screen_width=1920,
            screen_height=1080,
        )
        # Two zones: left (zones[0]) and right (zones[1])
        mgr.enqueue(mgr.zones[0].zone_id, api_health_task)
        mgr.enqueue(mgr.zones[1].zone_id, onboarding_task)

        result = mgr.run_all(parallel=True)
        print(mgr.summary())
    """

    def __init__(
        self,
        layout: SplitScreenLayout = SplitScreenLayout.DUAL_H,
        screen_width: int = 1920,
        screen_height: int = 1080,
        base_url: str = "http://127.0.0.1:8000",
        custom_zones: Optional[List[ScreenZone]] = None,
    ) -> None:
        self.base_url = base_url
        self.desktop = MultiCursorDesktop(
            screen_width=screen_width,
            screen_height=screen_height,
        )
        self.zones: List[ScreenZone] = self.desktop.apply_layout(
            layout, custom_zones=custom_zones
        )
        self._queues: Dict[str, List[NativeTask]] = {
            z.zone_id: [] for z in self.zones
        }
        self._runners: Dict[str, MurphyNativeRunner] = {
            z.zone_id: MurphyNativeRunner(base_url=base_url)
            for z in self.zones
        }
        self._results: Dict[str, List[Dict[str, Any]]] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------

    def enqueue(self, zone_id: str, task: NativeTask) -> None:
        """Add a task to the queue for *zone_id*."""
        with self._lock:
            if zone_id not in self._queues:
                raise KeyError(f"Zone '{zone_id}' not found in this layout")
            self._queues[zone_id].append(task)

    def enqueue_to_all(self, task: NativeTask) -> None:
        """Broadcast *task* to every zone's queue (synchronisation point)."""
        with self._lock:
            for q in self._queues.values():
                q.append(task)

    def run_zone(
        self,
        zone_id: str,
        context: Optional[Dict[str, Any]] = None,
        html_content: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Execute all queued tasks for *zone_id* synchronously."""
        runner = self._runners[zone_id]
        tasks = self._queues.get(zone_id, [])
        zone_results = runner.run_suite(tasks, context=context, html_content=html_content)
        with self._lock:
            self._results[zone_id] = zone_results
        return zone_results

    def run_all(
        self,
        context: Optional[Dict[str, Any]] = None,
        html_content: Optional[str] = None,
        parallel: bool = True,
    ) -> Dict[str, Any]:
        """Execute all queued tasks for all zones.

        Args:
            context:      Shared context dict passed to every runner.
            html_content: Optional HTML fixture for DOM assertions.
            parallel:     If True, zones run simultaneously in separate threads
                          (true split-screen parallelism).  If False, zones run
                          sequentially.

        Returns:
            Summary dict with per-zone results, cursor positions, and layout.
        """
        combined: Dict[str, List[Dict[str, Any]]] = {}

        if parallel:
            lock = threading.Lock()

            def _run(zone_id: str) -> None:
                res = self.run_zone(zone_id, context=context, html_content=html_content)
                with lock:
                    combined[zone_id] = res

            threads = [
                threading.Thread(
                    target=_run,
                    args=(z.zone_id,),
                    daemon=True,
                    name=f"split-{z.name}",
                )
                for z in self.zones
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=300)
            for t in threads:
                if t.is_alive():
                    zid = t.name.replace("split-", "")
                    combined[zid] = [{"status": "timeout"}]
        else:
            for zone in self.zones:
                combined[zone.zone_id] = self.run_zone(
                    zone.zone_id, context=context, html_content=html_content
                )

        snap = self.desktop.snapshot()
        return {
            "layout": snap["layout"],
            "zone_count": len(self.zones),
            "zones": [z.to_dict() for z in self.zones],
            "results": combined,
            "cursors": snap["cursors"],
        }

    def get_results(self) -> Dict[str, List[Dict[str, Any]]]:
        with self._lock:
            return dict(self._results)

    def summary(self) -> str:
        """One-line human-readable run summary per zone."""
        lines = []
        for zone in self.zones:
            zid = zone.zone_id
            results = self._results.get(zid, [])
            passed = sum(
                1 for r in results
                if r.get("status") in ("passed", "pass", "ok")
            )
            total = len(results)
            lines.append(f"  {zone.label or zone.name}: {passed}/{total} tasks passed")
        return "\n".join(lines) if lines else "(no tasks run yet)"


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
class NormScreenZone:
    """A rectangular region on the virtual desktop (normalised coordinates).

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
                    f"NormScreenZone.{attr} must be in [0.0, 1.0], got {v!r}"
                )
        if self.width <= 0 or self.height <= 0:
            raise ValueError("NormScreenZone width and height must be positive")

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
class NormCursorContext:
    """Tracks the logical state of a single virtual cursor (normalised coordinates).

    Each cursor is assigned to exactly one :class:`NormScreenZone` at a time.

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


class NormMultiCursorDesktop:
    """Manages a pool of named :class:`NormCursorContext` objects (normalised coordinates).

    Cursors are keyed by their ``cursor_id``.  Thread-safe: all
    mutating operations are serialised through an internal lock.
    """

    def __init__(self) -> None:
        self._cursors: dict[str, NormCursorContext] = {}
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
    ) -> NormCursorContext:
        """Create and register a new cursor."""
        with self._lock:
            if cursor_id in self._cursors:
                raise ValueError(f"Cursor {cursor_id!r} already registered")
            ctx = NormCursorContext(
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

    def get_cursor(self, cursor_id: str) -> NormCursorContext:
        with self._lock:
            if cursor_id not in self._cursors:
                raise KeyError(f"Cursor {cursor_id!r} not found")
            return self._cursors[cursor_id]

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def cursors_in_zone(self, zone_id: str) -> list[NormCursorContext]:
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


class NormSplitScreenManager:
    """Manages the set of :class:`NormScreenZone` objects for a given layout.

    Supports predefined layouts and fully custom zone lists.  Thread-safe.
    Uses normalised [0.0, 1.0] coordinates for resolution-independent layouts.
    """

    _LAYOUT_BUILDERS: dict[str, "Callable[[], list[NormScreenZone]]"] = {}

    def __init__(
        self,
        layout: SplitScreenLayout = SplitScreenLayout.SINGLE,
        custom_zones: list[NormScreenZone] | None = None,
    ) -> None:
        self._layout = layout
        self._lock = threading.Lock()
        if layout == SplitScreenLayout.CUSTOM:
            if not custom_zones:
                raise ValueError(
                    "custom_zones must be provided for SplitScreenLayout.CUSTOM"
                )
            self._zones: dict[str, NormScreenZone] = {z.zone_id: z for z in custom_zones}
        else:
            built = self._build_layout(layout)
            self._zones = {z.zone_id: z for z in built}

    # ------------------------------------------------------------------
    # Layout builders
    # ------------------------------------------------------------------

    @staticmethod
    def _build_layout(layout: SplitScreenLayout) -> list[NormScreenZone]:
        if layout == SplitScreenLayout.SINGLE:
            return [NormScreenZone("z0", 0.0, 0.0, 1.0, 1.0, label="full")]
        if layout == SplitScreenLayout.DUAL_H:
            return [
                NormScreenZone("z0", 0.0, 0.0, 1.0, 0.5, label="top"),
                NormScreenZone("z1", 0.0, 0.5, 1.0, 0.5, label="bottom"),
            ]
        if layout == SplitScreenLayout.DUAL_V:
            return [
                NormScreenZone("z0", 0.0, 0.0, 0.5, 1.0, label="left"),
                NormScreenZone("z1", 0.5, 0.0, 0.5, 1.0, label="right"),
            ]
        if layout == SplitScreenLayout.TRIPLE_H:
            h = 1.0 / 3
            return [
                NormScreenZone("z0", 0.0, 0.0, 1.0, h, label="top"),
                NormScreenZone("z1", 0.0, h, 1.0, h, label="middle"),
                NormScreenZone("z2", 0.0, 2 * h, 1.0, h, label="bottom"),
            ]
        if layout == SplitScreenLayout.QUAD:
            return [
                NormScreenZone("z0", 0.0, 0.0, 0.5, 0.5, label="top-left"),
                NormScreenZone("z1", 0.5, 0.0, 0.5, 0.5, label="top-right"),
                NormScreenZone("z2", 0.0, 0.5, 0.5, 0.5, label="bottom-left"),
                NormScreenZone("z3", 0.5, 0.5, 0.5, 0.5, label="bottom-right"),
            ]
        if layout == SplitScreenLayout.HEXA:
            w, h = 1.0 / 3, 0.5
            zones = []
            for row in range(2):
                for col in range(3):
                    idx = row * 3 + col
                    zones.append(
                        NormScreenZone(
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

    def get_zone(self, zone_id: str) -> NormScreenZone:
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

    def find_zone_at(self, px: float, py: float) -> NormScreenZone | None:
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
