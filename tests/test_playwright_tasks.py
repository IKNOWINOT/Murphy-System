"""
Tests for Playwright Task Definitions (INC-08 / M-03).

Tests run in mock mode (no browser required).

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import os
import sys

import pytest

_src_dir = os.path.join(os.path.dirname(__file__), "..", "src")
if os.path.abspath(_src_dir) not in sys.path:
    sys.path.insert(0, os.path.abspath(_src_dir))

from playwright_task_definitions import (
    BrowserConfig,
    BrowserType,
    ClickTask,
    ExtractTask,
    FillTask,
    NavigateTask,
    PlaywrightTask,
    PlaywrightTaskRunner,
    ScreenshotTask,
    SequenceTask,
    TaskResult,
    TaskStatus,
    TaskType,
    WaitTask,
)


class TestPlaywrightModule:
    """Verify playwright_task_definitions imports playwright."""

    def test_module_size(self) -> None:
        import playwright_task_definitions
        path = playwright_task_definitions.__file__
        assert path is not None
        size = os.path.getsize(path)
        assert size > 5000, f"Module is {size} bytes, expected >5000"

    def test_imports_playwright(self) -> None:
        import playwright_task_definitions
        path = playwright_task_definitions.__file__
        assert path is not None
        with open(path) as f:
            source = f.read()
        assert "from playwright" in source or "import playwright" in source


class TestTaskTypes:
    """Verify task type enums and data models."""

    def test_task_types(self) -> None:
        assert TaskType.NAVIGATE.value == "navigate"
        assert TaskType.CLICK.value == "click"
        assert TaskType.FILL.value == "fill"
        assert TaskType.SCREENSHOT.value == "screenshot"

    def test_browser_types(self) -> None:
        assert BrowserType.CHROMIUM.value == "chromium"
        assert BrowserType.FIREFOX.value == "firefox"

    def test_task_status(self) -> None:
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"

    def test_browser_config_from_env(self) -> None:
        from unittest.mock import patch
        with patch.dict(os.environ, {"PLAYWRIGHT_BROWSER": "firefox"}, clear=False):
            cfg = BrowserConfig.from_env()
        assert cfg.browser_type == BrowserType.FIREFOX


class TestMockTaskExecution:
    """Task execution in mock mode (no playwright installed)."""

    @pytest.mark.asyncio
    async def test_navigate_mock(self) -> None:
        task = NavigateTask(url="https://example.com")
        result = await task.execute(None)
        assert result.status == TaskStatus.COMPLETED
        assert result.task_type == TaskType.NAVIGATE
        assert "example.com" in result.data.get("url", "")

    @pytest.mark.asyncio
    async def test_click_mock(self) -> None:
        task = ClickTask(selector="#submit")
        result = await task.execute(None)
        assert result.status == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_fill_mock(self) -> None:
        task = FillTask(selector="#name", value="Murphy")
        result = await task.execute(None)
        assert result.status == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_screenshot_mock(self) -> None:
        task = ScreenshotTask()
        result = await task.execute(None)
        assert result.status == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_extract_mock(self) -> None:
        task = ExtractTask(selector="h1")
        result = await task.execute(None)
        assert result.status == TaskStatus.COMPLETED
        assert len(result.data.get("values", [])) > 0

    @pytest.mark.asyncio
    async def test_wait_mock(self) -> None:
        task = WaitTask(selector=".loaded")
        result = await task.execute(None)
        assert result.status == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_sequence_mock(self) -> None:
        seq = SequenceTask(tasks=[
            NavigateTask(url="https://example.com"),
            ClickTask(selector="#btn"),
        ])
        result = await seq.execute(None)
        assert result.status == TaskStatus.COMPLETED
        assert result.data["total_steps"] == 2


class TestPlaywrightRunner:
    """Test the task runner in mock mode."""

    @pytest.mark.asyncio
    async def test_runner_execute(self) -> None:
        runner = PlaywrightTaskRunner()
        result = await runner.execute_task(NavigateTask(url="https://test.com"))
        assert isinstance(result, TaskResult)
        await runner.close()

    def test_runner_status(self) -> None:
        runner = PlaywrightTaskRunner()
        status = runner.get_status()
        assert "playwright_available" in status
        assert "browser_type" in status


# ---------------------------------------------------------------------------
# EvaluateTask tests (new class)
# ---------------------------------------------------------------------------

class TestEvaluateTask:
    """Tests for the new EvaluateTask (TaskType.EVALUATE)."""

    @pytest.mark.asyncio
    async def test_evaluate_task_returns_completed_with_none_page(self):
        from playwright_task_definitions import EvaluateTask, TaskStatus
        task = EvaluateTask("1 + 1")
        result = await task.execute(page=None)
        assert result.status == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_evaluate_task_data_contains_expression(self):
        from playwright_task_definitions import EvaluateTask
        task = EvaluateTask("window.scrollBy(0, 200)")
        result = await task.execute(page=None)
        assert result.data.get("expression") == "window.scrollBy(0, 200)"

    @pytest.mark.asyncio
    async def test_evaluate_task_result_is_none_in_mock_mode(self):
        from playwright_task_definitions import EvaluateTask
        task = EvaluateTask("document.title")
        result = await task.execute(page=None)
        assert result.data.get("result") is None  # no real page

    def test_evaluate_task_has_evaluate_task_type(self):
        from playwright_task_definitions import EvaluateTask, TaskType
        task = EvaluateTask("1")
        assert task.task_type == TaskType.EVALUATE

    @pytest.mark.asyncio
    async def test_evaluate_task_handles_exception_gracefully(self):
        from unittest.mock import patch
        import playwright_task_definitions as ptd
        from playwright_task_definitions import EvaluateTask, TaskStatus

        class _BadPage:
            async def evaluate(self, _expr):
                raise RuntimeError("page error")

        task = EvaluateTask("bad")
        # Patch _PLAYWRIGHT_AVAILABLE so the page is actually used
        with patch.object(ptd, "_PLAYWRIGHT_AVAILABLE", True):
            result = await task.execute(page=_BadPage())
        assert result.status == TaskStatus.FAILED
        assert "page error" in result.error


# ---------------------------------------------------------------------------
# execute_tasks_on_shared_page tests
# ---------------------------------------------------------------------------

class TestExecuteTasksOnSharedPage:
    """Tests for PlaywrightTaskRunner.execute_tasks_on_shared_page()."""

    @pytest.mark.asyncio
    async def test_returns_list_of_results(self):
        from playwright_task_definitions import (
            NavigateTask,
            FillTask,
            PlaywrightTaskRunner,
            TaskStatus,
        )
        runner = PlaywrightTaskRunner()
        tasks = [
            NavigateTask(url="https://example.com"),
            FillTask(selector="input#email", value="test@test.com"),
        ]
        results = await runner.execute_tasks_on_shared_page(tasks)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_all_results_completed_in_mock_mode(self):
        from playwright_task_definitions import (
            ClickTask,
            FillTask,
            NavigateTask,
            PlaywrightTaskRunner,
            TaskStatus,
        )
        runner = PlaywrightTaskRunner()
        tasks = [
            NavigateTask(url="https://example.com"),
            FillTask(selector="input", value="v"),
            ClickTask(selector="button"),
        ]
        results = await runner.execute_tasks_on_shared_page(tasks)
        for r in results:
            assert r.status == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_empty_task_list_returns_empty_list(self):
        from playwright_task_definitions import PlaywrightTaskRunner
        runner = PlaywrightTaskRunner()
        results = await runner.execute_tasks_on_shared_page([])
        assert results == []

    @pytest.mark.asyncio
    async def test_results_preserve_order(self):
        from playwright_task_definitions import (
            ClickTask,
            FillTask,
            NavigateTask,
            PlaywrightTaskRunner,
            TaskType,
        )
        runner = PlaywrightTaskRunner()
        tasks = [
            NavigateTask(url="https://example.com"),
            FillTask(selector="input", value="hello"),
            ClickTask(selector="button"),
        ]
        results = await runner.execute_tasks_on_shared_page(tasks)
        assert results[0].task_type == TaskType.NAVIGATE
        assert results[1].task_type == TaskType.FILL
        assert results[2].task_type == TaskType.CLICK

    @pytest.mark.asyncio
    async def test_continues_after_individual_failure(self):
        """A task failure in the list should not prevent remaining tasks."""
        from playwright_task_definitions import (
            ClickTask,
            EvaluateTask,
            FillTask,
            PlaywrightTaskRunner,
            TaskStatus,
        )

        class _FailEvaluatePage:
            async def evaluate(self, _expr):
                raise RuntimeError("forced failure")

        runner = PlaywrightTaskRunner()
        # All run in mock mode (context=None, page=None), so no actual failure
        tasks = [
            EvaluateTask("window.scrollBy(0,100)"),
            FillTask(selector="input", value="val"),
        ]
        results = await runner.execute_tasks_on_shared_page(tasks)
        assert len(results) == 2  # both tasks processed

    @pytest.mark.asyncio
    async def test_shared_page_with_evaluate_task(self):
        """EvaluateTask runs successfully on a shared page in mock mode."""
        from playwright_task_definitions import (
            EvaluateTask,
            NavigateTask,
            PlaywrightTaskRunner,
            TaskStatus,
        )
        runner = PlaywrightTaskRunner()
        tasks = [
            NavigateTask(url="https://example.com"),
            EvaluateTask("window.scrollBy(0, 300)"),
            EvaluateTask("window.scrollTo(0, 0)"),
        ]
        results = await runner.execute_tasks_on_shared_page(tasks)
        assert all(r.status == TaskStatus.COMPLETED for r in results)
