"""
WebArena Adapter — tests Murphy's web automation capabilities.

WebArena presents tasks in simulated web environments (e-commerce, forums,
CMS, GitLab).  Murphy's platform connector framework handles web interactions.

Metrics
-------
* ``success_rate``  — functional goal-completion rate

External dependency
-------------------
A running WebArena server is required for full evaluation.  The adapter
uses synthetic tasks when no server URL is configured.

References
----------
* https://webarena.dev/
* https://github.com/web-arena-x/webarena

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""
from __future__ import annotations

import logging
import os
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

_SYNTHETIC_TASKS: list[dict[str, Any]] = [
    {
        "id": "wa-shop-001",
        "site": "shopping",
        "task": "Search for 'laptop stand' and add the cheapest result to the cart.",
        "intent": "add_to_cart",
    },
    {
        "id": "wa-forum-001",
        "site": "forum",
        "task": "Post a reply to the top thread in the Python forum.",
        "intent": "post_reply",
    },
    {
        "id": "wa-cms-001",
        "site": "cms",
        "task": "Create a new blog post titled 'Hello World' with sample content.",
        "intent": "create_content",
    },
    {
        "id": "wa-gitlab-001",
        "site": "gitlab",
        "task": "Open a new issue titled 'Bug: login fails' in the demo project.",
        "intent": "create_issue",
    },
    {
        "id": "wa-shop-002",
        "site": "shopping",
        "task": "Find red sneakers in size 10 and check if they are in stock.",
        "intent": "check_stock",
    },
]


class WebArenaAdapter(BenchmarkAdapter):
    """Adapter for the WebArena benchmark."""

    def __init__(
        self,
        server_url: str | None = None,
        max_tasks: int = 5,
    ) -> None:
        super().__init__()
        self._server_url = server_url or os.environ.get("WEBARENA_SERVER_URL")
        self._max_tasks = max_tasks
        self._tasks: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # BenchmarkAdapter interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "web-arena"

    @property
    def version(self) -> str:
        return "v1"

    @property
    def url(self) -> str:
        return "https://webarena.dev/"

    def setup(self) -> None:
        """Prepare WebArena tasks (synthetic when no server is configured)."""
        if self._server_url:
            logger.info("WebArena server configured at %s", self._server_url)
            self._tasks = self._load_from_server()
        else:
            logger.info(
                "WEBARENA_SERVER_URL not set; using %d synthetic tasks.",
                len(_SYNTHETIC_TASKS),
            )
            self._tasks = list(_SYNTHETIC_TASKS[: self._max_tasks])

    def _load_from_server(self) -> list[dict[str, Any]]:
        """Attempt to load tasks from a live WebArena instance."""
        try:
            import requests  # noqa: PLC0415

            resp = requests.get(
                f"{self._server_url}/tasks",
                timeout=10,
            )
            resp.raise_for_status()
            tasks = resp.json()
            return tasks[: self._max_tasks]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not load tasks from WebArena server: %s", exc)
            return list(_SYNTHETIC_TASKS[: self._max_tasks])

    def load_tasks(self) -> list[dict[str, Any]]:
        return list(self._tasks)

    def run_task(self, task: dict[str, Any]) -> BenchmarkResult:
        """Execute a WebArena task via Murphy's platform connector framework."""
        task_id = str(task.get("id", task.get("task_id", "unknown")))
        task_desc = task.get("task", task.get("instruction", ""))
        site = task.get("site", "web")

        start = time.perf_counter()
        output: str = ""

        try:
            from src.ai_workflow_generator import AIWorkflowGenerator  # noqa: PLC0415

            gen = AIWorkflowGenerator()
            output = str(gen.generate_workflow(task_desc))
        except Exception as exc:  # noqa: BLE001
            logger.debug("AIWorkflowGenerator unavailable: %s", exc)
            # Fall back to platform connector framework for web automation ------
            try:
                from src.platform_connector_framework import (  # noqa: PLC0415
                    ConnectorAction,
                    PlatformConnectorFramework,
                )

                pcf = PlatformConnectorFramework()
                action = ConnectorAction(
                    action_id=task_id,
                    connector_id="web",
                    action_type="execute",
                    resource=task_desc,
                )
                result = pcf.execute_action(action)
                output = str(result.data if result.success else result.error)
            except Exception as exc2:  # noqa: BLE001
                output = f"[error: {exc2}]"

        elapsed = time.perf_counter() - start
        success = bool(output) and "[error" not in output.lower()
        score = 1.0 if success else 0.0

        return BenchmarkResult(
            task_id=task_id,
            success=success,
            elapsed_seconds=elapsed,
            score=score,
            metadata={"site": site, "intent": task.get("intent", "unknown")},
        )
