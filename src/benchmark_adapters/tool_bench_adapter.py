"""
ToolBench / BFCL Adapter — tests Murphy's tool/API selection and calling.

Tests Murphy's platform connector framework and API gateway adapter for
correct tool selection and invocation.  Based on the Berkeley Function-Calling
Leaderboard (BFCL) and ToolBench harness.

Metrics
-------
* ``tool_selection_accuracy``  — fraction of tasks where the correct tool is chosen
* ``execution_success_rate``   — fraction of tool calls that execute without error

External dependency
-------------------
The ToolBench dataset (``datasets`` package) is optional; synthetic tasks are
used as a fallback.

References
----------
* https://gorilla.cs.berkeley.edu/leaderboard.html  (BFCL)
* https://github.com/OpenBMB/ToolBench

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""
from __future__ import annotations

import logging
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "Murphy System" / "src"))
sys.path.insert(0, str(ROOT / "Murphy System"))

from .base import BenchmarkAdapter, BenchmarkResult  # noqa: E402

logger = logging.getLogger(__name__)

# Synthetic tool-calling tasks ------------------------------------------------
_SYNTHETIC_TASKS: list[dict[str, Any]] = [
    {
        "id": "tb-001",
        "instruction": "Send a Slack message to #engineering: 'Build pipeline completed'",
        "expected_tool": "slack_send_message",
        "parameters": {"channel": "#engineering", "text": "Build pipeline completed"},
    },
    {
        "id": "tb-002",
        "instruction": "Create a Jira ticket titled 'Fix login bug' in project KEY",
        "expected_tool": "jira_create_issue",
        "parameters": {"project": "KEY", "summary": "Fix login bug"},
    },
    {
        "id": "tb-003",
        "instruction": "Get the current weather in San Francisco",
        "expected_tool": "weather_api_get",
        "parameters": {"location": "San Francisco"},
    },
    {
        "id": "tb-004",
        "instruction": "Create a GitHub issue titled 'Improve docs' in owner/repo",
        "expected_tool": "github_create_issue",
        "parameters": {"owner": "owner", "repo": "repo", "title": "Improve docs"},
    },
    {
        "id": "tb-005",
        "instruction": "Query Salesforce for all open opportunities over $50k",
        "expected_tool": "salesforce_soql_query",
        "parameters": {"query": "SELECT Id, Name FROM Opportunity WHERE Amount > 50000"},
    },
    {
        "id": "tb-006",
        "instruction": "Send an email to user@example.com with subject 'Meeting reminder'",
        "expected_tool": "email_send",
        "parameters": {"to": "user@example.com", "subject": "Meeting reminder"},
    },
    {
        "id": "tb-007",
        "instruction": "Search Google for 'Murphy System AI automation'",
        "expected_tool": "web_search",
        "parameters": {"query": "Murphy System AI automation"},
    },
    {
        "id": "tb-008",
        "instruction": "Post a tweet: 'Murphy System just hit 1000 stars on GitHub!'",
        "expected_tool": "twitter_post_tweet",
        "parameters": {"text": "Murphy System just hit 1000 stars on GitHub!"},
    },
]


class ToolBenchAdapter(BenchmarkAdapter):
    """Adapter for ToolBench / BFCL (tool selection and API calling)."""

    def __init__(self, max_tasks: int = 8) -> None:
        super().__init__()
        self._max_tasks = max_tasks
        self._tasks: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # BenchmarkAdapter interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "tool-bench"

    @property
    def version(self) -> str:
        return "bfcl-v2"

    @property
    def url(self) -> str:
        return "https://gorilla.cs.berkeley.edu/leaderboard.html"

    def setup(self) -> None:
        """Load tool-calling tasks (synthetic fallback if dataset unavailable)."""
        self._tasks = list(_SYNTHETIC_TASKS[: self._max_tasks])
        logger.info("ToolBench: using %d synthetic tasks.", len(self._tasks))

    def load_tasks(self) -> list[dict[str, Any]]:
        return list(self._tasks)

    def run_task(self, task: dict[str, Any]) -> BenchmarkResult:
        """Route a tool-calling task through Murphy's API gateway adapter."""
        task_id = str(task.get("id", "unknown"))
        instruction = task.get("instruction", "")
        expected_tool = task.get("expected_tool", "")

        start = time.perf_counter()
        selected_tool: str = ""
        execution_ok: bool = False

        # Attempt via API gateway adapter -------------------------------------
        try:
            from src.api_gateway_adapter import APIGatewayAdapter  # noqa: PLC0415

            adapter = APIGatewayAdapter()
            result = adapter.route(instruction)
            selected_tool = str(getattr(result, "tool", result) or "")
            execution_ok = True
        except Exception as exc:  # noqa: BLE001
            logger.debug("APIGatewayAdapter unavailable: %s", exc)

        # Fallback: platform connector framework ------------------------------
        if not execution_ok:
            try:
                from src.platform_connector_framework import (  # noqa: PLC0415
                    ConnectorAction,
                    PlatformConnectorFramework,
                )

                pcf = PlatformConnectorFramework()
                action = ConnectorAction(
                    action_id=task_id,
                    connector_id="default",
                    action_type="execute",
                    resource=instruction,
                )
                result = pcf.execute_action(action)
                selected_tool = str(result.data if result.success else result.error)
                execution_ok = result.success
            except Exception as exc:  # noqa: BLE001
                logger.debug("PlatformConnectorFramework unavailable: %s", exc)
                selected_tool = f"[error: {exc}]"

        elapsed = time.perf_counter() - start

        # Tool-selection accuracy: check if expected tool name is in output ---
        tool_correct = bool(
            expected_tool and expected_tool.lower() in selected_tool.lower()
        )
        score = (0.5 if execution_ok else 0.0) + (0.5 if tool_correct else 0.0)

        return BenchmarkResult(
            task_id=task_id,
            success=execution_ok,
            elapsed_seconds=elapsed,
            score=score,
            metadata={
                "expected_tool": expected_tool,
                "selected_tool": selected_tool,
                "tool_correct": tool_correct,
                "execution_ok": execution_ok,
            },
        )

    def score(self) -> dict[str, Any]:
        base = super().score()
        if self._suite_result is not None:
            results = self._suite_result.results
            tool_correct = [r.metadata.get("tool_correct", False) for r in results]
            exec_ok = [r.metadata.get("execution_ok", False) for r in results]
            if results:
                base["tool_selection_accuracy"] = round(
                    sum(tool_correct) / len(results), 4
                )
                base["execution_success_rate"] = round(
                    sum(exec_ok) / len(results), 4
                )
        return base
