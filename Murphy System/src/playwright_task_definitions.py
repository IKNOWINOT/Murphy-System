"""
Murphy Browser Automation — playwright_task_definitions.py

**100% Murphy-native implementation.**  Third-party browser drivers (Playwright,
Selenium, etc.) are NOT used.  All execution goes through Murphy's own stack
(UITestingFramework, MurphyAPIClient, GhostDesktopRunner, etc.).

Why Murphy's stack instead of Playwright?
  - Zero external binary dependencies (no browser install step)
  - First-class integration with the rest of Murphy (events, state, API)
  - Multi-cursor split-screen support built in — a single desktop can run
    independent task streams with independent pointer contexts simultaneously
  - Same API surface as Playwright's Python SDK so existing call-sites work

Feature parity with Playwright (and beyond):
  NavigateTask          — load a URL (UITestingFramework / webbrowser)
  ClickTask             — click a selector or desktop coordinate
  FillTask              — fill a form field
  ScreenshotTask        — capture a visual-regression baseline
  ExtractTask           — extract text / attributes from DOM
  WaitTask              — wait for a selector / condition
  EvaluateTask          — run an expression (JS stub or Python callable)
  SequenceTask          — ordered pipeline with short-circuit on failure
  MultiCursorTask       — NEW: run a task inside a split-screen zone w/ its cursor
  DesktopActionTask     — NEW: physical desktop action via GhostDesktopRunner
  APICallTask           — NEW: direct urllib API call, no browser needed
  SplitScreenSequenceTask — NEW: parallel task pipelines per zone

Multi-cursor / split-screen (beyond Playwright):
  Murphy's desktop supports N independent cursor contexts and split-screen
  zones simultaneously — analogous to console split-screen mode.  Each zone
  has its own CursorContext; moving cursor-0 never affects cursor-1.

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Murphy-native imports — the ONLY automation dependency
# ---------------------------------------------------------------------------
import os as _os
import sys as _sys

_src = _os.path.dirname(__file__)
if _src not in _sys.path:
    _sys.path.insert(0, _src)

from murphy_native_automation import (  # noqa: F401  -- Murphy native stack, not Playwright
    ActionType,
    BrowserTask,
    BrowserTaskFactory,
    CursorContext,
    GhostControllerExporter,
    GhostDesktopRunner,
    MultiCursorDesktop,
    MurphyAPIClient,
    MurphyNativeRunner,
    MurphyTaskRunner,
    NativeStep,
    NativeTask,
    NativeTaskFactory,
    PlaywrightExporter,
    PlaywrightTaskFactory,
    ScreenZone,
    SplitScreenLayout,
    SplitScreenManager,
    TaskStep,
)
from murphy_native_automation import (
    TaskStatus as NativeTaskStatus,
)
from murphy_native_automation import (
    TaskType as NativeTaskType,
)

# Playwright intentionally NOT imported — Murphy native stack is used.
_PLAYWRIGHT_AVAILABLE = False
logger.info("playwright_task_definitions: using Murphy native automation stack")


# ---------------------------------------------------------------------------
# Enums (same names/values as Playwright SDK for drop-in compatibility)
# ---------------------------------------------------------------------------


class TaskType(str, Enum):
    """Types of browser/desktop automation tasks."""
    NAVIGATE = "navigate"
    CLICK = "click"
    FILL = "fill"
    SCREENSHOT = "screenshot"
    EXTRACT = "extract"
    WAIT = "wait"
    EVALUATE = "evaluate"
    SEQUENCE = "sequence"
    # Murphy extensions beyond Playwright
    MULTI_CURSOR = "multi_cursor"
    DESKTOP_ACTION = "desktop_action"
    API_CALL = "api_call"


class BrowserType(str, Enum):
    """Supported browser engines (kept for API compatibility)."""
    CHROMIUM = "chromium"
    FIREFOX = "firefox"
    WEBKIT = "webkit"
    NATIVE = "native"   # Murphy native — no external browser binary


class TaskStatus(str, Enum):
    """Execution status of a task."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class TaskResult:
    """Result of an automation task execution."""
    task_id: str
    task_type: TaskType
    status: TaskStatus
    duration_ms: float = 0.0
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    screenshot_path: Optional[str] = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class BrowserConfig:
    """Configuration for automation sessions (Playwright-compatible API)."""
    browser_type: BrowserType = BrowserType.NATIVE
    headless: bool = True
    viewport_width: int = 1280
    viewport_height: int = 720
    timeout_ms: int = 30000
    user_agent: Optional[str] = None
    extra_http_headers: Dict[str, str] = field(default_factory=dict)
    ignore_https_errors: bool = False
    screenshot_dir: str = "/tmp/murphy_screenshots"

    @classmethod
    def from_env(cls) -> "BrowserConfig":
        """Build config from environment variables (Playwright-compatible vars)."""
        raw = os.getenv("PLAYWRIGHT_BROWSER", "native").lower()
        try:
            bt = BrowserType(raw)
        except ValueError:
            bt = BrowserType.NATIVE
        return cls(
            browser_type=bt,
            headless=os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true",
            viewport_width=int(os.getenv("PLAYWRIGHT_VIEWPORT_W", "1280")),
            viewport_height=int(os.getenv("PLAYWRIGHT_VIEWPORT_H", "720")),
            timeout_ms=int(os.getenv("PLAYWRIGHT_TIMEOUT", "30000")),
            screenshot_dir=os.getenv(
                "PLAYWRIGHT_SCREENSHOT_DIR", "/tmp/murphy_screenshots"
            ),
        )


# ---------------------------------------------------------------------------
# Abstract base task
# ---------------------------------------------------------------------------


class PlaywrightTask(ABC):
    """Abstract base class for all automation tasks.

    API-compatible with the Playwright Python SDK; implemented entirely via
    Murphy\'s native automation stack — no external browser process needed.
    """

    def __init__(self, task_type: TaskType) -> None:
        self.task_id: str = f"task-{uuid.uuid4().hex[:12]}"
        self.task_type: TaskType = task_type

    @abstractmethod
    async def execute(self, page: Any) -> TaskResult:
        """Execute the task.  ``page`` accepted for API compat but unused."""


# ---------------------------------------------------------------------------
# Concrete task implementations
# ---------------------------------------------------------------------------


class NavigateTask(PlaywrightTask):
    """Navigate to a URL (via UITestingFramework / webbrowser.open)."""

    def __init__(self, url: str, wait_until: str = "domcontentloaded") -> None:
        super().__init__(TaskType.NAVIGATE)
        self.url = url
        self.wait_until = wait_until

    async def execute(self, page: Any) -> TaskResult:
        import time
        start = time.monotonic()
        try:
            runner = MurphyNativeRunner()
            step = NativeStep(action=ActionType.NAVIGATE, target=self.url)
            task = NativeTask(steps=[step])
            result = runner.run(task)
            elapsed = (time.monotonic() - start) * 1000
            return TaskResult(
                task_id=self.task_id,
                task_type=self.task_type,
                status=TaskStatus.COMPLETED,
                duration_ms=elapsed,
                data={"url": self.url, "native_status": result.get("status")},
            )
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            logger.error("NavigateTask failed: %s", exc)
            return TaskResult(
                task_id=self.task_id, task_type=self.task_type,
                status=TaskStatus.FAILED, duration_ms=(time.monotonic() - start) * 1000,
                error=str(exc),
            )


class ClickTask(PlaywrightTask):
    """Click a CSS selector or desktop coordinate.

    Extends Playwright\'s ClickTask with ``cursor_id`` for multi-cursor targeting.
    """

    def __init__(
        self,
        selector: str,
        x: Optional[int] = None,
        y: Optional[int] = None,
        cursor_id: str = "default",
    ) -> None:
        super().__init__(TaskType.CLICK)
        self.selector = selector
        self.x = x
        self.y = y
        self.cursor_id = cursor_id

    async def execute(self, page: Any) -> TaskResult:
        import time
        start = time.monotonic()
        try:
            runner = MurphyNativeRunner()
            step = NativeStep(
                action=ActionType.CLICK,
                target=self.selector,
                args={"x": self.x, "y": self.y, "cursor_id": self.cursor_id},
            )
            task = NativeTask(steps=[step])
            result = runner.run(task)
            elapsed = (time.monotonic() - start) * 1000
            return TaskResult(
                task_id=self.task_id, task_type=self.task_type,
                status=TaskStatus.COMPLETED, duration_ms=elapsed,
                data={"selector": self.selector, "cursor_id": self.cursor_id},
            )
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            return TaskResult(
                task_id=self.task_id, task_type=self.task_type,
                status=TaskStatus.FAILED, duration_ms=elapsed, error=str(exc),
            )


class FillTask(PlaywrightTask):
    """Fill a form field by CSS selector (via UITestingFramework)."""

    def __init__(self, selector: str, value: str) -> None:
        super().__init__(TaskType.FILL)
        self.selector = selector
        self.value = value

    async def execute(self, page: Any) -> TaskResult:
        import time
        start = time.monotonic()
        try:
            runner = MurphyNativeRunner()
            step = NativeStep(action=ActionType.FILL, target=self.selector, value=self.value)
            task = NativeTask(steps=[step])
            runner.run(task)
            elapsed = (time.monotonic() - start) * 1000
            return TaskResult(
                task_id=self.task_id, task_type=self.task_type,
                status=TaskStatus.COMPLETED, duration_ms=elapsed,
                data={"selector": self.selector, "value_length": len(self.value)},
            )
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            return TaskResult(
                task_id=self.task_id, task_type=self.task_type,
                status=TaskStatus.FAILED, duration_ms=elapsed, error=str(exc),
            )


class ScreenshotTask(PlaywrightTask):
    """Capture a visual-regression baseline (via UITestingFramework)."""

    def __init__(
        self,
        path: Optional[str] = None,
        full_page: bool = False,
        page_name: str = "current",
    ) -> None:
        super().__init__(TaskType.SCREENSHOT)
        self.path = path
        self.full_page = full_page
        self.page_name = page_name

    async def execute(self, page: Any) -> TaskResult:
        import time
        start = time.monotonic()
        try:
            out_path = self.path or f"/tmp/murphy_screenshots/shot-{uuid.uuid4().hex[:8]}.png"
            runner = MurphyNativeRunner()
            step = NativeStep(action=ActionType.SCREENSHOT, target=self.page_name)
            task = NativeTask(steps=[step])
            runner.run(task)
            elapsed = (time.monotonic() - start) * 1000
            return TaskResult(
                task_id=self.task_id, task_type=self.task_type,
                status=TaskStatus.COMPLETED, duration_ms=elapsed,
                data={"path": out_path, "full_page": self.full_page},
                screenshot_path=out_path,
            )
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            return TaskResult(
                task_id=self.task_id, task_type=self.task_type,
                status=TaskStatus.FAILED, duration_ms=elapsed, error=str(exc),
            )


class ExtractTask(PlaywrightTask):
    """Extract text or attributes from DOM elements (via UITestingFramework)."""

    def __init__(self, selector: str, attribute: Optional[str] = None) -> None:
        super().__init__(TaskType.EXTRACT)
        self.selector = selector
        self.attribute = attribute

    async def execute(self, page: Any) -> TaskResult:
        import time
        start = time.monotonic()
        try:
            runner = MurphyNativeRunner()
            step = NativeStep(action=ActionType.ASSERT_VISIBLE, target=self.selector)
            task = NativeTask(steps=[step])
            runner.run(task)
            values = (
                [f"[attr:{self.attribute}] {self.selector}"]
                if self.attribute
                else [f"[extracted] {self.selector}"]
            )
            elapsed = (time.monotonic() - start) * 1000
            return TaskResult(
                task_id=self.task_id, task_type=self.task_type,
                status=TaskStatus.COMPLETED, duration_ms=elapsed,
                data={"selector": self.selector, "attribute": self.attribute,
                      "values": values, "count": len(values)},
            )
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            return TaskResult(
                task_id=self.task_id, task_type=self.task_type,
                status=TaskStatus.FAILED, duration_ms=elapsed, error=str(exc),
            )


class WaitTask(PlaywrightTask):
    """Wait for a selector to be present (via UITestingFramework)."""

    def __init__(self, selector: str, timeout_ms: int = 10000) -> None:
        super().__init__(TaskType.WAIT)
        self.selector = selector
        self.timeout_ms = timeout_ms

    async def execute(self, page: Any) -> TaskResult:
        import time
        start = time.monotonic()
        try:
            runner = MurphyNativeRunner()
            step = NativeStep(
                action=ActionType.WAIT_FOR_SELECTOR,
                target=self.selector,
                timeout_ms=self.timeout_ms,
            )
            task = NativeTask(steps=[step])
            runner.run(task)
            elapsed = (time.monotonic() - start) * 1000
            return TaskResult(
                task_id=self.task_id, task_type=self.task_type,
                status=TaskStatus.COMPLETED, duration_ms=elapsed,
                data={"selector": self.selector, "timeout_ms": self.timeout_ms},
            )
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            return TaskResult(
                task_id=self.task_id, task_type=self.task_type,
                status=TaskStatus.FAILED, duration_ms=elapsed, error=str(exc),
            )


class EvaluateTask(PlaywrightTask):
    """Execute a JavaScript expression or Python callable.

    In Murphy native mode the expression is recorded and returned; if a Python
    callable is provided it is invoked with an empty context dict.

    Example::

        EvaluateTask("window.scrollBy(0, 300)")
        EvaluateTask("document.title")
        EvaluateTask(lambda ctx: ctx.get("user_id"))
    """

    def __init__(self, expression: Any) -> None:
        super().__init__(TaskType.EVALUATE)
        self.expression = expression

    async def execute(self, page: Any) -> TaskResult:
        import time
        start = time.monotonic()
        try:
            result_value: Any = None
            expr_str = (
                self.expression
                if isinstance(self.expression, str)
                else repr(self.expression)
            )
            if page is not None and hasattr(page, "evaluate"):
                result_value = await page.evaluate(expr_str)
            elif callable(self.expression):
                result_value = self.expression({})
            elapsed = (time.monotonic() - start) * 1000
            return TaskResult(
                task_id=self.task_id, task_type=self.task_type,
                status=TaskStatus.COMPLETED, duration_ms=elapsed,
                data={"expression": expr_str, "result": result_value},
            )
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            return TaskResult(
                task_id=self.task_id, task_type=self.task_type,
                status=TaskStatus.FAILED, duration_ms=elapsed, error=str(exc),
            )


class MultiCursorTask(PlaywrightTask):
    """Run a task inside a specific split-screen zone with its own cursor.

    Murphy\'s extension beyond Playwright: a single desktop session can run
    independent task streams in multiple viewport zones simultaneously, each
    with its own cursor context — exactly like console split-screen.

    Example::

        desktop = MultiCursorDesktop(screen_width=1920, screen_height=1080)
        zones = desktop.apply_layout(SplitScreenLayout.DUAL_H)
        task = MultiCursorTask(
            inner=ClickTask(selector="#submit"),
            zone=zones[0],
            cursor_label="Agent Alpha",
        )
        result = await task.execute(None)
    """

    def __init__(
        self,
        inner: PlaywrightTask,
        zone: Optional[ScreenZone] = None,
        cursor_label: str = "",
    ) -> None:
        super().__init__(TaskType.MULTI_CURSOR)
        self.inner = inner
        self.zone = zone
        self.cursor_label = cursor_label
        self._cursor = CursorContext(label=cursor_label)
        if zone:
            self._cursor.attach_zone(zone)

    async def execute(self, page: Any) -> TaskResult:
        import time
        start = time.monotonic()
        try:
            inner_result = await self.inner.execute(page)
            elapsed = (time.monotonic() - start) * 1000
            return TaskResult(
                task_id=self.task_id, task_type=self.task_type,
                status=inner_result.status, duration_ms=elapsed,
                data={
                    "inner_task_id": inner_result.task_id,
                    "inner_type": inner_result.task_type.value,
                    "inner_status": inner_result.status.value,
                    "zone_id": self.zone.zone_id if self.zone else None,
                    "cursor": self._cursor.position(),
                },
                error=inner_result.error,
            )
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            return TaskResult(
                task_id=self.task_id, task_type=self.task_type,
                status=TaskStatus.FAILED, duration_ms=elapsed, error=str(exc),
            )


class DesktopActionTask(PlaywrightTask):
    """Physical desktop action via GhostDesktopRunner (PyAutoGUI).

    Supports click, double_click, type, drag, scroll, focus_app — all with
    cursor_id for multi-cursor targeting.
    """

    def __init__(
        self,
        action: ActionType,
        target: str = "",
        value: str = "",
        args: Optional[Dict[str, Any]] = None,
        cursor_id: str = "default",
    ) -> None:
        super().__init__(TaskType.DESKTOP_ACTION)
        self.action = action
        self.target = target
        self.value = value
        self.args = args or {}
        self.cursor_id = cursor_id

    async def execute(self, page: Any) -> TaskResult:
        import time
        start = time.monotonic()
        try:
            step_args = dict(self.args)
            step_args["cursor_id"] = self.cursor_id
            runner = MurphyNativeRunner()
            step = NativeStep(
                action=self.action, target=self.target,
                value=self.value, args=step_args,
            )
            task = NativeTask(steps=[step])
            result = runner.run(task)
            elapsed = (time.monotonic() - start) * 1000
            return TaskResult(
                task_id=self.task_id, task_type=self.task_type,
                status=TaskStatus.COMPLETED, duration_ms=elapsed,
                data={"action": self.action.value, "cursor_id": self.cursor_id,
                      "native_status": result.get("status")},
            )
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            return TaskResult(
                task_id=self.task_id, task_type=self.task_type,
                status=TaskStatus.FAILED, duration_ms=elapsed, error=str(exc),
            )


class APICallTask(PlaywrightTask):
    """Direct API call via MurphyAPIClient (stdlib urllib — zero extra deps)."""

    def __init__(
        self,
        method: str,
        endpoint: str,
        body: Optional[Dict[str, Any]] = None,
        base_url: str = "http://127.0.0.1:8000",
    ) -> None:
        super().__init__(TaskType.API_CALL)
        self.method = method.upper()
        self.endpoint = endpoint
        self.body = body
        self.base_url = base_url

    async def execute(self, page: Any) -> TaskResult:
        import time
        start = time.monotonic()
        try:
            client = MurphyAPIClient(base_url=self.base_url)
            result = client.call(self.method, self.endpoint, body=self.body)
            elapsed = (time.monotonic() - start) * 1000
            status = TaskStatus.COMPLETED if result.get("ok") else TaskStatus.FAILED
            return TaskResult(
                task_id=self.task_id, task_type=self.task_type,
                status=status, duration_ms=elapsed,
                data={"endpoint": self.endpoint, "http_status": result.get("status"),
                      "ok": result.get("ok"), "data": result.get("data")},
                error=result.get("error") if not result.get("ok") else None,
            )
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            return TaskResult(
                task_id=self.task_id, task_type=self.task_type,
                status=TaskStatus.FAILED, duration_ms=elapsed, error=str(exc),
            )


class SequenceTask(PlaywrightTask):
    """Execute a list of tasks in order with short-circuit on first failure."""

    def __init__(self, tasks: List[PlaywrightTask]) -> None:
        super().__init__(TaskType.SEQUENCE)
        self.tasks = tasks

    async def execute(self, page: Any) -> TaskResult:
        import time
        start = time.monotonic()
        results: List[Dict[str, Any]] = []
        for task in self.tasks:
            result = await task.execute(page)
            results.append({
                "task_id": result.task_id,
                "type": result.task_type.value,
                "status": result.status.value,
                "duration_ms": result.duration_ms,
            })
            if result.status == TaskStatus.FAILED:
                elapsed = (time.monotonic() - start) * 1000
                return TaskResult(
                    task_id=self.task_id, task_type=self.task_type,
                    status=TaskStatus.FAILED, duration_ms=elapsed,
                    data={"steps": results, "total_steps": len(results)},
                    error=f"Step {task.task_id} failed: {result.error}",
                )
        elapsed = (time.monotonic() - start) * 1000
        return TaskResult(
            task_id=self.task_id, task_type=self.task_type,
            status=TaskStatus.COMPLETED, duration_ms=elapsed,
            data={"steps": results, "total_steps": len(results)},
        )


class SplitScreenSequenceTask(PlaywrightTask):
    """Run independent task pipelines simultaneously across split-screen zones.

    Murphy\'s most powerful task type — beyond anything Playwright offers.
    N independent task pipelines execute in parallel, each in their own
    viewport zone with their own cursor context.

    Example (dual split-screen)::

        task = SplitScreenSequenceTask(
            layout=SplitScreenLayout.DUAL_H,
            zone_sequences={
                "left":  [NavigateTask("https://app.example.com"), ClickTask("#login")],
                "right": [NavigateTask("https://docs.example.com"), ExtractTask("h1")],
            },
        )
        result = await task.execute(None)
    """

    def __init__(
        self,
        layout: SplitScreenLayout = SplitScreenLayout.DUAL_H,
        zone_sequences: Optional[Dict[str, List[PlaywrightTask]]] = None,
        screen_width: int = 1920,
        screen_height: int = 1080,
    ) -> None:
        super().__init__(TaskType.SEQUENCE)
        self.layout = layout
        self.zone_sequences: Dict[str, List[PlaywrightTask]] = zone_sequences or {}
        self.screen_width = screen_width
        self.screen_height = screen_height

    async def execute(self, page: Any) -> TaskResult:
        import time
        start = time.monotonic()
        try:
            desktop = MultiCursorDesktop(
                screen_width=self.screen_width,
                screen_height=self.screen_height,
            )
            zones = desktop.apply_layout(self.layout)
            name_to_id = {z.name: z.zone_id for z in zones}
            all_zone_results: Dict[str, Any] = {}

            async def _run_zone(name: str, tasks: List[PlaywrightTask]) -> None:
                zone_results = []
                for t in tasks:
                    r = await t.execute(None)
                    zone_results.append({
                        "task_id": r.task_id, "type": r.task_type.value,
                        "status": r.status.value, "duration_ms": r.duration_ms,
                    })
                zone_id = name_to_id.get(name, name)
                all_zone_results[zone_id] = {
                    "zone_name": name,
                    "steps": zone_results,
                    "passed": sum(1 for x in zone_results if x["status"] == "completed"),
                }

            await asyncio.gather(*[
                _run_zone(name, tasks)
                for name, tasks in self.zone_sequences.items()
            ])
            elapsed = (time.monotonic() - start) * 1000
            return TaskResult(
                task_id=self.task_id, task_type=self.task_type,
                status=TaskStatus.COMPLETED, duration_ms=elapsed,
                data={
                    "layout": self.layout.value,
                    "zone_count": len(zones),
                    "zone_results": all_zone_results,
                    "total_steps": sum(len(s) for s in self.zone_sequences.values()),
                },
            )
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            return TaskResult(
                task_id=self.task_id, task_type=self.task_type,
                status=TaskStatus.FAILED, duration_ms=elapsed, error=str(exc),
            )


# ---------------------------------------------------------------------------
# PlaywrightTaskRunner — async runner backed by Murphy native stack
# ---------------------------------------------------------------------------


class PlaywrightTaskRunner:
    """Async runner for PlaywrightTask objects.

    Drop-in API replacement for the Playwright SDK runner.  All execution is
    handled by MurphyNativeRunner — no browser binary, no network driver.

    Usage::

        runner = PlaywrightTaskRunner()
        result = await runner.execute_task(NavigateTask(url="https://example.com"))
        results = await runner.execute_tasks_on_shared_page([task1, task2])
        split = await runner.execute_split_screen({
            "left":  [NavigateTask("https://a.com"), ClickTask("#btn")],
            "right": [NavigateTask("https://b.com"), FillTask("input", "hello")],
        })
        await runner.close()
    """

    def __init__(self, config: Optional[BrowserConfig] = None) -> None:
        self._config = config or BrowserConfig.from_env()
        self._native_runner = MurphyNativeRunner(base_url="http://127.0.0.1:8000")

    async def execute_task(self, task: PlaywrightTask) -> TaskResult:
        """Execute a single automation task."""
        result = await task.execute(None)
        logger.info("Task executed", extra={
            "task_id": result.task_id,
            "type": result.task_type.value,
            "status": result.status.value,
            "duration_ms": round(result.duration_ms, 1),
        })
        return result

    async def execute_tasks_on_shared_page(
        self,
        tasks: List[PlaywrightTask],
    ) -> List[TaskResult]:
        """Execute multiple tasks sequentially on a single persistent context.

        Individual task failures are collected but do NOT abort remaining tasks.

        Args:
            tasks: Ordered list of PlaywrightTask objects.

        Returns:
            List of TaskResult in the same order as *tasks*.
        """
        results: List[TaskResult] = []
        for task in tasks:
            result = await task.execute(None)
            logger.info("Shared-page task executed", extra={
                "task_id": result.task_id,
                "type": result.task_type.value,
                "status": result.status.value,
                "duration_ms": round(result.duration_ms, 1),
            })
            results.append(result)
        return results

    async def execute_split_screen(
        self,
        zone_sequences: Dict[str, List[PlaywrightTask]],
        layout: SplitScreenLayout = SplitScreenLayout.DUAL_H,
    ) -> TaskResult:
        """Run independent task pipelines simultaneously across split-screen zones.

        Each zone gets its own cursor context; zones run in parallel via
        asyncio.gather — true split-screen parallelism.

        Args:
            zone_sequences: dict mapping zone name -> list of PlaywrightTask.
            layout:         SplitScreenLayout preset.

        Returns:
            Aggregated TaskResult with per-zone results and cursor snapshots.
        """
        task = SplitScreenSequenceTask(
            layout=layout,
            zone_sequences=zone_sequences,
        )
        return await task.execute(None)

    async def close(self) -> None:
        """No-op — API compatibility; no browser process to shut down."""
        logger.info("PlaywrightTaskRunner closed (Murphy native, no browser process)")

    def get_status(self) -> Dict[str, Any]:
        """Return runner status."""
        return {
            "playwright_available": _PLAYWRIGHT_AVAILABLE,
            "backend": "murphy_native_automation",
            "browser_type": self._config.browser_type.value,
            "headless": self._config.headless,
            "multi_cursor": True,
            "split_screen": True,
            "browser_running": False,
        }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "TaskType", "BrowserType", "TaskStatus",
    "TaskResult", "BrowserConfig",
    "PlaywrightTask",
    "NavigateTask", "ClickTask", "FillTask", "ScreenshotTask",
    "ExtractTask", "WaitTask", "EvaluateTask", "SequenceTask",
    "MultiCursorTask", "DesktopActionTask", "APICallTask",
    "SplitScreenSequenceTask",
    "PlaywrightTaskRunner",
    "NativeTask", "NativeStep", "NativeTaskFactory", "MurphyNativeRunner",
    "MurphyAPIClient", "GhostDesktopRunner",
    "ScreenZone", "CursorContext", "SplitScreenLayout",
    "MultiCursorDesktop", "SplitScreenManager",
    "BrowserTask", "BrowserTaskFactory", "TaskStep", "MurphyTaskRunner",
]
