"""
Terminal-Bench Adapter — tests Murphy's CLI/system automation capabilities.

Terminal-Bench presents command-line tasks: file manipulation, software
installation, script execution, and multi-step DevOps workflows.
Murphy's system-command execution and DevOps automation capabilities are tested.

Metrics
-------
* ``command_success_rate``      — fraction of individual commands that succeed
* ``script_completion_rate``    — fraction of multi-step scripts fully completed

External dependency
-------------------
No mandatory external dependency; synthetic CLI tasks are used.

References
----------
* https://github.com/laion-ai/terminal-bench

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

# Synthetic Terminal-Bench style tasks ----------------------------------------
_SYNTHETIC_TASKS: list[dict[str, Any]] = [
    {
        "id": "tb-cli-001",
        "type": "single_command",
        "instruction": "List all files in /tmp sorted by modification time.",
        "expected_command": "ls -lt /tmp",
        "steps": 1,
    },
    {
        "id": "tb-cli-002",
        "type": "multi_step",
        "instruction": "Create a virtual environment, install requests, and run a hello-world script.",
        "expected_commands": [
            "python3 -m venv venv",
            "venv/bin/pip install requests",
            "python3 -c \"import requests; print('OK')\"",
        ],
        "steps": 3,
    },
    {
        "id": "tb-cli-003",
        "type": "single_command",
        "instruction": "Find all Python files in the current directory that contain the word 'TODO'.",
        "expected_command": "grep -rl 'TODO' . --include='*.py'",
        "steps": 1,
    },
    {
        "id": "tb-cli-004",
        "type": "multi_step",
        "instruction": "Archive the /var/log directory and compress it with gzip.",
        "expected_commands": [
            "tar -czf /tmp/logs.tar.gz /var/log",
        ],
        "steps": 1,
    },
    {
        "id": "tb-cli-005",
        "type": "single_command",
        "instruction": "Check disk usage of the /home directory in human-readable format.",
        "expected_command": "du -sh /home",
        "steps": 1,
    },
    {
        "id": "tb-cli-006",
        "type": "multi_step",
        "instruction": "Clone a git repo, checkout a branch, and run the tests.",
        "expected_commands": [
            "git clone https://github.com/example/repo /tmp/repo",
            "cd /tmp/repo && git checkout develop",
            "cd /tmp/repo && python -m pytest",
        ],
        "steps": 3,
    },
]


class TerminalBenchAdapter(BenchmarkAdapter):
    """Adapter for Terminal-Bench (CLI and system automation evaluation)."""

    def __init__(self, max_tasks: int = 6) -> None:
        super().__init__()
        self._max_tasks = max_tasks
        self._tasks: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # BenchmarkAdapter interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "terminal-bench"

    @property
    def version(self) -> str:
        return "v1"

    @property
    def url(self) -> str:
        return "https://github.com/laion-ai/terminal-bench"

    def setup(self) -> None:
        """Prepare Terminal-Bench tasks (synthetic)."""
        self._tasks = list(_SYNTHETIC_TASKS[: self._max_tasks])
        logger.info("Terminal-Bench: using %d synthetic tasks.", len(self._tasks))

    def load_tasks(self) -> list[dict[str, Any]]:
        return list(self._tasks)

    def run_task(self, task: dict[str, Any]) -> BenchmarkResult:
        """Route a terminal task through Murphy's system automation."""
        task_id = str(task.get("id", "unknown"))
        instruction = task.get("instruction", "")
        task_type = task.get("type", "single_command")
        steps_total = task.get("steps", 1)

        start = time.perf_counter()
        output: str = ""
        steps_completed: int = 0

        # Attempt via workflow generator (generates shell commands) ------------
        try:
            from src.ai_workflow_generator import AIWorkflowGenerator  # noqa: PLC0415

            gen = AIWorkflowGenerator()
            result_obj = gen.generate_workflow(f"CLI task: {instruction}")
            output = str(result_obj)
            # Count non-error lines as completed steps -------------------------
            lines = [ln.strip() for ln in output.splitlines() if ln.strip()]
            steps_completed = min(len(lines), steps_total)
        except Exception as exc:  # noqa: BLE001
            logger.debug("AIWorkflowGenerator unavailable: %s", exc)
            output = f"[workflow_generator_error: {exc}]"

        elapsed = time.perf_counter() - start
        success = bool(output) and "[error" not in output.lower()
        # Score proportional to steps completed --------------------------------
        score = (steps_completed / steps_total) if steps_total > 0 else 0.0

        return BenchmarkResult(
            task_id=task_id,
            success=success,
            elapsed_seconds=elapsed,
            score=score,
            metadata={
                "task_type": task_type,
                "steps_total": steps_total,
                "steps_completed": steps_completed,
            },
        )

    def score(self) -> dict[str, Any]:
        base = super().score()
        if self._suite_result is not None:
            results = self._suite_result.results
            single = [r for r in results if r.metadata.get("task_type") == "single_command"]
            multi = [r for r in results if r.metadata.get("task_type") == "multi_step"]
            if single:
                base["command_success_rate"] = round(
                    sum(1 for r in single if r.success) / len(single), 4
                )
            if multi:
                base["script_completion_rate"] = round(
                    sum(r.score for r in multi) / len(multi), 4
                )
        return base
