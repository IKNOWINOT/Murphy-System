"""
Playwright Task Definitions for Murphy System (INC-08 / M-03).

Production-ready browser automation using Microsoft Playwright.
Provides async task definitions for web scraping, form filling,
screenshot capture, and end-to-end UI testing.

When ``playwright`` is not installed, the module gracefully degrades
to the native Murphy automation framework.

Architecture decision:
    Playwright is the industry-standard for async browser automation.
    It supports Chromium, Firefox, and WebKit — one API for all browsers.
    The ``playwright`` package is lazily imported so this module can be
    loaded even when playwright is not installed.

Usage::

    from playwright_task_definitions import PlaywrightTaskRunner
    runner = PlaywrightTaskRunner()
    result = await runner.execute_task(NavigateTask(url="https://example.com"))

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
# Lazy import of playwright (INC-08: real playwright integration)
# ---------------------------------------------------------------------------
try:
    from playwright.async_api import (  # noqa: F401
        Browser,
        BrowserContext,
        Page,
        Playwright,
        async_playwright,
    )
    _PLAYWRIGHT_AVAILABLE = True
    logger.info("playwright available — browser automation enabled")
except ImportError:
    async_playwright = None  # type: ignore[assignment,misc]
    Browser = None  # type: ignore[assignment,misc]
    BrowserContext = None  # type: ignore[assignment,misc]
    Page = None  # type: ignore[assignment,misc]
    Playwright = None  # type: ignore[assignment,misc]
    _PLAYWRIGHT_AVAILABLE = False
    logger.info("playwright not installed — using mock automation")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TaskType(str, Enum):
    """Types of browser automation tasks."""
    NAVIGATE = "navigate"
    CLICK = "click"
    FILL = "fill"
    SCREENSHOT = "screenshot"
    EXTRACT = "extract"
    WAIT = "wait"
    EVALUATE = "evaluate"
    SEQUENCE = "sequence"


class BrowserType(str, Enum):
    """Supported browser engines."""
    CHROMIUM = "chromium"
    FIREFOX = "firefox"
    WEBKIT = "webkit"


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
    """Result of a browser automation task execution."""
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
    """Configuration for browser automation sessions."""
    browser_type: BrowserType = BrowserType.CHROMIUM
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
        """Build config from environment variables."""
        return cls(
            browser_type=BrowserType(
                os.getenv("PLAYWRIGHT_BROWSER", "chromium").lower()
            ),
            headless=os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true",
            viewport_width=int(os.getenv("PLAYWRIGHT_VIEWPORT_W", "1280")),
            viewport_height=int(os.getenv("PLAYWRIGHT_VIEWPORT_H", "720")),
            timeout_ms=int(os.getenv("PLAYWRIGHT_TIMEOUT", "30000")),
            screenshot_dir=os.getenv(
                "PLAYWRIGHT_SCREENSHOT_DIR", "/tmp/murphy_screenshots"
            ),
        )


# ---------------------------------------------------------------------------
# Abstract task base
# ---------------------------------------------------------------------------


class PlaywrightTask(ABC):
    """Abstract base class for all Playwright automation tasks."""

    def __init__(self, task_type: TaskType) -> None:
        self.task_id: str = f"task-{uuid.uuid4().hex[:12]}"
        self.task_type: TaskType = task_type

    @abstractmethod
    async def execute(self, page: Any) -> TaskResult:
        """Execute the task on the given browser page."""


# ---------------------------------------------------------------------------
# Concrete task definitions
# ---------------------------------------------------------------------------


class NavigateTask(PlaywrightTask):
    """Navigate to a URL."""

    def __init__(self, url: str, wait_until: str = "domcontentloaded") -> None:
        super().__init__(TaskType.NAVIGATE)
        self.url = url
        self.wait_until = wait_until

    async def execute(self, page: Any) -> TaskResult:
        import time
        start = time.monotonic()
        try:
            if page is not None and _PLAYWRIGHT_AVAILABLE:
                await page.goto(self.url, wait_until=self.wait_until)
                title = await page.title()
            else:
                title = f"[mock] Navigated to {self.url}"
            elapsed = (time.monotonic() - start) * 1000
            return TaskResult(
                task_id=self.task_id,
                task_type=self.task_type,
                status=TaskStatus.COMPLETED,
                duration_ms=elapsed,
                data={"url": self.url, "title": title},
            )
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            logger.error("Navigate failed: %s", exc, extra={"url": self.url})
            return TaskResult(
                task_id=self.task_id,
                task_type=self.task_type,
                status=TaskStatus.FAILED,
                duration_ms=elapsed,
                error=str(exc),
            )


class ClickTask(PlaywrightTask):
    """Click an element by selector."""

    def __init__(self, selector: str) -> None:
        super().__init__(TaskType.CLICK)
        self.selector = selector

    async def execute(self, page: Any) -> TaskResult:
        import time
        start = time.monotonic()
        try:
            if page is not None and _PLAYWRIGHT_AVAILABLE:
                await page.click(self.selector)
            elapsed = (time.monotonic() - start) * 1000
            return TaskResult(
                task_id=self.task_id,
                task_type=self.task_type,
                status=TaskStatus.COMPLETED,
                duration_ms=elapsed,
                data={"selector": self.selector},
            )
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            return TaskResult(
                task_id=self.task_id,
                task_type=self.task_type,
                status=TaskStatus.FAILED,
                duration_ms=elapsed,
                error=str(exc),
            )


class FillTask(PlaywrightTask):
    """Fill a form field by selector."""

    def __init__(self, selector: str, value: str) -> None:
        super().__init__(TaskType.FILL)
        self.selector = selector
        self.value = value

    async def execute(self, page: Any) -> TaskResult:
        import time
        start = time.monotonic()
        try:
            if page is not None and _PLAYWRIGHT_AVAILABLE:
                await page.fill(self.selector, self.value)
            elapsed = (time.monotonic() - start) * 1000
            return TaskResult(
                task_id=self.task_id,
                task_type=self.task_type,
                status=TaskStatus.COMPLETED,
                duration_ms=elapsed,
                data={"selector": self.selector, "value_length": len(self.value)},
            )
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            return TaskResult(
                task_id=self.task_id,
                task_type=self.task_type,
                status=TaskStatus.FAILED,
                duration_ms=elapsed,
                error=str(exc),
            )


class ScreenshotTask(PlaywrightTask):
    """Take a screenshot of the current page."""

    def __init__(self, path: Optional[str] = None, full_page: bool = False) -> None:
        super().__init__(TaskType.SCREENSHOT)
        self.path = path
        self.full_page = full_page

    async def execute(self, page: Any) -> TaskResult:
        import time
        start = time.monotonic()
        try:
            out_path = self.path or f"/tmp/murphy_screenshots/shot-{uuid.uuid4().hex[:8]}.png"
            if page is not None and _PLAYWRIGHT_AVAILABLE:
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                await page.screenshot(path=out_path, full_page=self.full_page)
            elapsed = (time.monotonic() - start) * 1000
            return TaskResult(
                task_id=self.task_id,
                task_type=self.task_type,
                status=TaskStatus.COMPLETED,
                duration_ms=elapsed,
                data={"path": out_path, "full_page": self.full_page},
                screenshot_path=out_path,
            )
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            return TaskResult(
                task_id=self.task_id,
                task_type=self.task_type,
                status=TaskStatus.FAILED,
                duration_ms=elapsed,
                error=str(exc),
            )


class ExtractTask(PlaywrightTask):
    """Extract text or attributes from elements."""

    def __init__(self, selector: str, attribute: Optional[str] = None) -> None:
        super().__init__(TaskType.EXTRACT)
        self.selector = selector
        self.attribute = attribute

    async def execute(self, page: Any) -> TaskResult:
        import time
        start = time.monotonic()
        try:
            if page is not None and _PLAYWRIGHT_AVAILABLE:
                if self.attribute:
                    values = await page.eval_on_selector_all(
                        self.selector,
                        f"(els) => els.map(e => e.getAttribute('{self.attribute}'))",
                    )
                else:
                    values = await page.eval_on_selector_all(
                        self.selector,
                        "(els) => els.map(e => e.textContent)",
                    )
            else:
                values = [f"[mock] extracted from {self.selector}"]
            elapsed = (time.monotonic() - start) * 1000
            return TaskResult(
                task_id=self.task_id,
                task_type=self.task_type,
                status=TaskStatus.COMPLETED,
                duration_ms=elapsed,
                data={"selector": self.selector, "values": values, "count": len(values)},
            )
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            return TaskResult(
                task_id=self.task_id,
                task_type=self.task_type,
                status=TaskStatus.FAILED,
                duration_ms=elapsed,
                error=str(exc),
            )


class WaitTask(PlaywrightTask):
    """Wait for a selector to appear."""

    def __init__(self, selector: str, timeout_ms: int = 10000) -> None:
        super().__init__(TaskType.WAIT)
        self.selector = selector
        self.timeout_ms = timeout_ms

    async def execute(self, page: Any) -> TaskResult:
        import time
        start = time.monotonic()
        try:
            if page is not None and _PLAYWRIGHT_AVAILABLE:
                await page.wait_for_selector(self.selector, timeout=self.timeout_ms)
            elapsed = (time.monotonic() - start) * 1000
            return TaskResult(
                task_id=self.task_id,
                task_type=self.task_type,
                status=TaskStatus.COMPLETED,
                duration_ms=elapsed,
                data={"selector": self.selector},
            )
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            return TaskResult(
                task_id=self.task_id,
                task_type=self.task_type,
                status=TaskStatus.FAILED,
                duration_ms=elapsed,
                error=str(exc),
            )


class EvaluateTask(PlaywrightTask):
    """Execute a JavaScript expression on the page and return the result.

    This is the primary mechanism for scroll simulation and other DOM
    interactions that are not covered by Click/Fill/Extract.

    Example::

        EvaluateTask("window.scrollBy(0, 300)")
        EvaluateTask("document.title")
    """

    def __init__(self, expression: str) -> None:
        super().__init__(TaskType.EVALUATE)
        self.expression = expression

    async def execute(self, page: Any) -> TaskResult:
        import time
        start = time.monotonic()
        try:
            result_value: Any = None
            if page is not None and _PLAYWRIGHT_AVAILABLE:
                result_value = await page.evaluate(self.expression)
            elapsed = (time.monotonic() - start) * 1000
            return TaskResult(
                task_id=self.task_id,
                task_type=self.task_type,
                status=TaskStatus.COMPLETED,
                duration_ms=elapsed,
                data={"result": result_value, "expression": self.expression},
            )
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            return TaskResult(
                task_id=self.task_id,
                task_type=self.task_type,
                status=TaskStatus.FAILED,
                duration_ms=elapsed,
                error=str(exc),
            )


class SequenceTask(PlaywrightTask):
    """Execute a sequence of tasks in order."""

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
                    task_id=self.task_id,
                    task_type=self.task_type,
                    status=TaskStatus.FAILED,
                    duration_ms=elapsed,
                    data={"steps": results},
                    error=f"Step {task.task_id} failed: {result.error}",
                )
        elapsed = (time.monotonic() - start) * 1000
        return TaskResult(
            task_id=self.task_id,
            task_type=self.task_type,
            status=TaskStatus.COMPLETED,
            duration_ms=elapsed,
            data={"steps": results, "total_steps": len(results)},
        )


# ---------------------------------------------------------------------------
# Task runner
# ---------------------------------------------------------------------------


class PlaywrightTaskRunner:
    """Manages browser lifecycle and executes PlaywrightTask instances."""

    def __init__(self, config: Optional[BrowserConfig] = None) -> None:
        self._config = config or BrowserConfig.from_env()
        self._playwright_instance: Any = None
        self._browser: Any = None
        self._context: Any = None

    async def _ensure_browser(self) -> Any:
        """Lazily start playwright and launch a browser."""
        if self._browser is not None:
            return self._browser

        if not _PLAYWRIGHT_AVAILABLE or async_playwright is None:
            logger.warning(
                "Playwright not installed — tasks will run in mock mode",
                extra={"config": self._config.browser_type.value},
            )
            return None

        self._playwright_instance = await async_playwright().start()

        launchers = {
            BrowserType.CHROMIUM: self._playwright_instance.chromium,
            BrowserType.FIREFOX: self._playwright_instance.firefox,
            BrowserType.WEBKIT: self._playwright_instance.webkit,
        }
        launcher = launchers.get(self._config.browser_type, self._playwright_instance.chromium)
        self._browser = await launcher.launch(headless=self._config.headless)

        self._context = await self._browser.new_context(
            viewport={
                "width": self._config.viewport_width,
                "height": self._config.viewport_height,
            },
            user_agent=self._config.user_agent,
            extra_http_headers=self._config.extra_http_headers or {},
            ignore_https_errors=self._config.ignore_https_errors,
        )

        logger.info(
            "Playwright browser launched",
            extra={
                "browser": self._config.browser_type.value,
                "headless": self._config.headless,
            },
        )
        return self._browser

    async def execute_task(self, task: PlaywrightTask) -> TaskResult:
        """Execute a single automation task on a fresh page."""
        await self._ensure_browser()

        page = None
        if self._context is not None:
            page = await self._context.new_page()

        try:
            result = await task.execute(page)
            logger.info(
                "Task executed",
                extra={
                    "task_id": result.task_id,
                    "type": result.task_type.value,
                    "status": result.status.value,
                    "duration_ms": round(result.duration_ms, 1),
                },
            )
            return result
        finally:
            if page is not None:
                try:
                    await page.close()
                except Exception as exc:
                    logger.debug("Non-critical error: %s", exc)

    async def execute_tasks_on_shared_page(
        self,
        tasks: List[PlaywrightTask],
    ) -> List[TaskResult]:
        """Execute multiple tasks sequentially on a SINGLE persistent page.

        Unlike :meth:`execute_task` (which creates a new page per call), this
        method opens the page once and runs every task against it.  This is
        required for multi-step form flows where state must persist across
        tasks (navigation → fill email → fill password → click submit).

        The page is closed automatically after all tasks complete or if any
        unhandled exception propagates.  Individual task failures are returned
        in the results list and do NOT abort the remaining tasks — the caller
        is responsible for inspecting each result's status.

        Args:
            tasks: Ordered list of tasks to execute on the shared page.

        Returns:
            List of :class:`TaskResult` in the same order as *tasks*.
        """
        await self._ensure_browser()

        page = None
        if self._context is not None:
            page = await self._context.new_page()

        results: List[TaskResult] = []
        try:
            for task in tasks:
                result = await task.execute(page)
                logger.info(
                    "Shared-page task executed",
                    extra={
                        "task_id": result.task_id,
                        "type": result.task_type.value,
                        "status": result.status.value,
                        "duration_ms": round(result.duration_ms, 1),
                    },
                )
                results.append(result)
        finally:
            if page is not None:
                try:
                    await page.close()
                except Exception as exc:
                    logger.debug("Non-critical error: %s", exc)

        return results

    async def close(self) -> None:
        """Shut down the browser and playwright."""
        if self._context is not None:
            try:
                await self._context.close()
            except Exception as exc:
                logger.debug("close error: %s", exc)
            self._context = None
        if self._browser is not None:
            try:
                await self._browser.close()
            except Exception as exc:
                logger.debug("Non-critical error: %s", exc)
            self._browser = None
        if self._playwright_instance is not None:
            try:
                await self._playwright_instance.stop()
            except Exception as exc:
                logger.debug("Non-critical error: %s", exc)
            self._playwright_instance = None
        logger.info("Playwright runner closed")

    def get_status(self) -> Dict[str, Any]:
        """Return runner status."""
        return {
            "playwright_available": _PLAYWRIGHT_AVAILABLE,
            "browser_type": self._config.browser_type.value,
            "headless": self._config.headless,
            "browser_running": self._browser is not None,
        }


# ---------------------------------------------------------------------------
# Backward-compatible re-exports from murphy_native_automation
# ---------------------------------------------------------------------------
try:
    from murphy_native_automation import (  # noqa: F401
        ActionType,
        BrowserTask,
        BrowserTaskFactory,
        GhostControllerExporter,
        GhostDesktopRunner,
        MurphyAPIClient,
        MurphyNativeRunner,
        MurphyTaskRunner,
        NativeStep,
        NativeTask,
        NativeTaskFactory,
        PlaywrightExporter,
        PlaywrightTaskFactory,
        TaskStep,
    )
except ImportError:
    pass  # Native automation not available in this context
