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
