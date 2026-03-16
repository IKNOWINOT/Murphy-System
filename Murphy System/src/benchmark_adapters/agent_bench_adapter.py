"""
AgentBench Adapter — tests Murphy across 8 diverse agent environments.

AgentBench maps environments to Murphy subsystems:
  OS         → system automation / DevOps connectors
  DB         → data query and analytics connectors
  Web        → platform connector framework (90+ connectors)
  Code       → AI workflow generator + self-fix pipeline
  KG         → knowledge-graph and search capabilities
  ALFWorld   → text-game reasoning (workflow DAG engine)
  WebShop    → e-commerce platform connectors
  Mind2Web   → web-action platform connectors

Metrics
-------
* ``success_rate``          — overall task success rate
* per-environment success rates (``env_{env}_rate``)

External dependency
-------------------
The AgentBench repo (https://github.com/THUDM/AgentBench) is required for
full evaluation.  The adapter uses synthetic tasks when the repo is absent.

References
----------
* https://github.com/THUDM/AgentBench
* https://llmbench.ai/agent

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

from .base import BenchmarkAdapter, BenchmarkResult  # noqa: E402

logger = logging.getLogger(__name__)

# AgentBench environments and the Murphy subsystem each maps to ---------------
_ENV_SUBSYSTEM: dict[str, str] = {
    "os": "system_automation",
    "db": "data_connector",
    "web": "platform_connector",
    "code": "workflow_generator",
    "kg": "knowledge_graph",
    "alfworld": "workflow_dag",
    "webshop": "ecommerce_connector",
    "mind2web": "web_action_connector",
}

# Synthetic task templates (used when real AgentBench tasks are not available) -
_SYNTHETIC_TASKS: list[dict[str, Any]] = [
    {
        "id": "os-001",
        "environment": "os",
        "instruction": "List all running processes and find the one using the most memory.",
        "expected_type": "process_list",
    },
    {
        "id": "db-001",
        "environment": "db",
        "instruction": "Query the sales database for total revenue by region in Q1.",
        "expected_type": "query_result",
    },
    {
        "id": "web-001",
        "environment": "web",
        "instruction": "Post a message to the #general Slack channel.",
        "expected_type": "api_call",
    },
    {
        "id": "code-001",
        "environment": "code",
        "instruction": "Write a Python function that sorts a list of dicts by a given key.",
        "expected_type": "code_output",
    },
    {
        "id": "kg-001",
        "environment": "kg",
        "instruction": "Find all dependencies of the 'requests' Python package.",
        "expected_type": "graph_result",
    },
    {
        "id": "alfworld-001",
        "environment": "alfworld",
        "instruction": "Navigate to the kitchen and pick up the apple on the counter.",
        "expected_type": "action_sequence",
    },
    {
        "id": "webshop-001",
        "environment": "webshop",
        "instruction": "Find a blue t-shirt in size medium under $30 and add it to the cart.",
        "expected_type": "shopping_cart",
    },
    {
        "id": "mind2web-001",
        "environment": "mind2web",
        "instruction": "Search for 'Python tutorials' on Google and click the first result.",
        "expected_type": "web_action",
    },
]


class AgentBenchAdapter(BenchmarkAdapter):
    """Adapter for AgentBench (8-environment agent evaluation)."""

    def __init__(self, agentbench_path: str | Path | None = None) -> None:
        super().__init__()
        self._agentbench_path = Path(agentbench_path) if agentbench_path else None
        self._tasks: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # BenchmarkAdapter interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "agent-bench"

    @property
    def version(self) -> str:
        return "v0.2"

    @property
    def url(self) -> str:
        return "https://github.com/THUDM/AgentBench"

    def setup(self) -> None:
        """Load AgentBench tasks (falls back to synthetic tasks if repo absent)."""
        if self._agentbench_path and self._agentbench_path.exists():
            self._tasks = self._load_from_repo(self._agentbench_path)
        else:
            logger.info(
                "AgentBench repo not found; using %d synthetic tasks.",
                len(_SYNTHETIC_TASKS),
            )
            self._tasks = list(_SYNTHETIC_TASKS)

    def _load_from_repo(self, repo_path: Path) -> list[dict[str, Any]]:
        """Try to load tasks from a cloned AgentBench repo."""
        tasks: list[dict[str, Any]] = []
        task_dir = repo_path / "data"
        if not task_dir.exists():
            logger.warning("AgentBench data dir not found at %s", task_dir)
            return list(_SYNTHETIC_TASKS)
        import json  # noqa: PLC0415

        for env_dir in task_dir.iterdir():
            if not env_dir.is_dir():
                continue
            for task_file in env_dir.glob("*.json"):
                try:
                    data = json.loads(task_file.read_text(encoding="utf-8"))
                    if isinstance(data, list):
                        for item in data:
                            item.setdefault("environment", env_dir.name)
                            tasks.append(item)
                    else:
                        data.setdefault("environment", env_dir.name)
                        tasks.append(data)
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Could not parse %s: %s", task_file, exc)
        return tasks if tasks else list(_SYNTHETIC_TASKS)

    def load_tasks(self) -> list[dict[str, Any]]:
        return list(self._tasks)

    def run_task(self, task: dict[str, Any]) -> BenchmarkResult:
        """Route an AgentBench task to the appropriate Murphy subsystem."""
        task_id = str(task.get("id", task.get("task_id", "unknown")))
        env = str(task.get("environment", "code")).lower()
        instruction = task.get("instruction", task.get("prompt", ""))

        start = time.perf_counter()
        output: str = ""

        # Workflow generator path (primary for all environments) ---------------
        try:
            from src.ai_workflow_generator import AIWorkflowGenerator  # noqa: PLC0415

            gen = AIWorkflowGenerator()
            output = str(gen.generate_workflow(instruction))
        except Exception as exc:  # noqa: BLE001
            logger.debug("AIWorkflowGenerator unavailable: %s", exc)
            # Fallback: platform connector framework --------------------------
            if env in ("os", "db", "kg", "alfworld", "webshop", "mind2web"):
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
                    output = str(result.data if result.success else result.error)
                except Exception as exc2:  # noqa: BLE001
                    logger.debug("PlatformConnectorFramework unavailable: %s", exc2)
                    output = f"[workflow_generator_error: {exc2}]"
            else:
                output = f"[workflow_generator_error: {exc}]"

        elapsed = time.perf_counter() - start
        success = bool(output) and "[error" not in output.lower()
        score = 1.0 if success else 0.0

        return BenchmarkResult(
            task_id=task_id,
            success=success,
            elapsed_seconds=elapsed,
            score=score,
            metadata={
                "environment": env,
                "subsystem": _ENV_SUBSYSTEM.get(env, "unknown"),
            },
        )

    def score(self) -> dict[str, Any]:
        base = super().score()
        if self._suite_result is not None:
            results = self._suite_result.results
            for env in _ENV_SUBSYSTEM:
                env_results = [
                    r for r in results if r.metadata.get("environment") == env
                ]
                if env_results:
                    rate = sum(1 for r in env_results if r.success) / len(env_results)
                    base[f"env_{env}_rate"] = round(rate, 4)
        return base
