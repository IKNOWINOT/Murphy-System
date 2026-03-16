"""
τ-Bench (Tau-Bench) Adapter — tests Murphy's multi-turn HITL workflows.

τ-Bench evaluates multi-turn, long-horizon workflows that require
human-in-the-loop collaboration.  Murphy's HITL graduation pipeline,
wingman protocol, and multi-turn orchestration are directly exercised.

Metrics
-------
* ``completion_rate``           — fraction of workflows completed
* ``hitl_escalation_rate``      — fraction of tasks that required human approval
* ``mean_turns``                — average turns per completed workflow

External dependency
-------------------
No mandatory external dependency; synthetic multi-turn tasks are used.

References
----------
* https://github.com/sierra-research/tau-bench
* https://arxiv.org/abs/2406.12045

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

# Synthetic multi-turn τ-Bench style tasks ------------------------------------
_SYNTHETIC_TASKS: list[dict[str, Any]] = [
    {
        "id": "tau-001",
        "domain": "retail",
        "turns": [
            {"role": "user", "content": "I need to return my order #12345."},
            {"role": "agent", "content": "I'll look up your order."},
            {"role": "user", "content": "The item was defective."},
        ],
        "expected_action": "initiate_return",
        "requires_hitl": True,
    },
    {
        "id": "tau-002",
        "domain": "airline",
        "turns": [
            {"role": "user", "content": "I want to change my flight from NYC to LA."},
            {"role": "agent", "content": "When would you like to travel?"},
            {"role": "user", "content": "Next Monday, morning preferred."},
            {"role": "agent", "content": "I found available flights."},
            {"role": "user", "content": "Book the 9am flight please."},
        ],
        "expected_action": "book_flight",
        "requires_hitl": False,
    },
    {
        "id": "tau-003",
        "domain": "finance",
        "turns": [
            {"role": "user", "content": "Transfer $5000 to account 987654."},
            {"role": "agent", "content": "I need to verify your identity first."},
            {"role": "user", "content": "My PIN is 1234."},
        ],
        "expected_action": "initiate_transfer",
        "requires_hitl": True,
    },
    {
        "id": "tau-004",
        "domain": "it_support",
        "turns": [
            {"role": "user", "content": "My laptop won't connect to VPN."},
            {"role": "agent", "content": "Have you tried restarting the VPN client?"},
            {"role": "user", "content": "Yes, still not working."},
            {"role": "agent", "content": "Let me check your network configuration."},
        ],
        "expected_action": "escalate_ticket",
        "requires_hitl": False,
    },
    {
        "id": "tau-005",
        "domain": "hr",
        "turns": [
            {"role": "user", "content": "I want to request 5 days of PTO starting Monday."},
            {"role": "agent", "content": "I'll check your balance and availability."},
            {"role": "user", "content": "Please submit the request."},
        ],
        "expected_action": "submit_pto_request",
        "requires_hitl": True,
    },
]


class TauBenchAdapter(BenchmarkAdapter):
    """Adapter for τ-Bench (multi-turn HITL workflow evaluation)."""

    def __init__(self, max_tasks: int = 5) -> None:
        super().__init__()
        self._max_tasks = max_tasks
        self._tasks: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # BenchmarkAdapter interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "tau-bench"

    @property
    def version(self) -> str:
        return "v1"

    @property
    def url(self) -> str:
        return "https://github.com/sierra-research/tau-bench"

    def setup(self) -> None:
        """Prepare τ-Bench tasks (synthetic)."""
        self._tasks = list(_SYNTHETIC_TASKS[: self._max_tasks])
        logger.info("τ-Bench: using %d synthetic tasks.", len(self._tasks))

    def load_tasks(self) -> list[dict[str, Any]]:
        return list(self._tasks)

    def run_task(self, task: dict[str, Any]) -> BenchmarkResult:
        """Execute a multi-turn HITL workflow via Murphy's orchestration layer."""
        task_id = str(task.get("id", "unknown"))
        turns = task.get("turns", [])
        requires_hitl = task.get("requires_hitl", False)
        expected_action = task.get("expected_action", "")
        domain = task.get("domain", "unknown")

        start = time.perf_counter()
        output: str = ""
        hitl_triggered: bool = False
        turns_completed: int = 0

        # Attempt via Murphy's durable swarm orchestrator ----------------------
        try:
            from src.durable_swarm_orchestrator import (  # noqa: PLC0415
                DurableSwarmOrchestrator,
            )

            orchestrator = DurableSwarmOrchestrator()
            conversation = "\n".join(
                f"{t['role'].upper()}: {t['content']}" for t in turns
            )
            result = orchestrator.run(conversation)
            output = str(result)
            turns_completed = len(turns)
        except Exception as exc:  # noqa: BLE001
            logger.debug("DurableSwarmOrchestrator unavailable: %s", exc)
            # Fallback: workflow generator ----------------------------------------
            try:
                from src.ai_workflow_generator import AIWorkflowGenerator  # noqa: PLC0415

                gen = AIWorkflowGenerator()
                conversation = "\n".join(
                    f"{t['role'].upper()}: {t['content']}" for t in turns
                )
                output = str(gen.generate_workflow(conversation))
                turns_completed = len(turns)
            except Exception as exc2:  # noqa: BLE001
                output = f"[error: {exc2}]"

        # Check if HITL gate was invoked ---------------------------------------
        if requires_hitl:
            try:
                from src.gate_execution_wiring import (  # noqa: PLC0415
                    GateExecutionWiring,
                )

                wiring = GateExecutionWiring()
                hitl_result = wiring.evaluate_hitl(output)
                hitl_triggered = bool(hitl_result)
            except Exception as exc:  # noqa: BLE001
                hitl_triggered = False

        elapsed = time.perf_counter() - start
        success = bool(output) and "[error" not in output.lower()
        # Score: completion (0.5) + correct HITL handling (0.5) ---------------
        hitl_score = 0.5 if (not requires_hitl or hitl_triggered) else 0.0
        score = (0.5 if success else 0.0) + hitl_score

        return BenchmarkResult(
            task_id=task_id,
            success=success,
            elapsed_seconds=elapsed,
            score=score,
            metadata={
                "domain": domain,
                "turns_total": len(turns),
                "turns_completed": turns_completed,
                "requires_hitl": requires_hitl,
                "hitl_triggered": hitl_triggered,
                "expected_action": expected_action,
            },
        )

    def score(self) -> dict[str, Any]:
        base = super().score()
        if self._suite_result is not None:
            results = self._suite_result.results
            if results:
                completed = [r for r in results if r.success]
                hitl_results = [
                    r for r in results if r.metadata.get("requires_hitl")
                ]
                hitl_triggered = [
                    r for r in hitl_results if r.metadata.get("hitl_triggered")
                ]
                turns_list = [
                    r.metadata.get("turns_completed", 0) for r in completed
                ]
                base["completion_rate"] = round(len(completed) / len(results), 4)
                base["hitl_escalation_rate"] = (
                    round(len(hitl_triggered) / len(hitl_results), 4)
                    if hitl_results
                    else 0.0
                )
                base["mean_turns"] = (
                    round(sum(turns_list) / len(turns_list), 2) if turns_list else 0.0
                )
        return base
