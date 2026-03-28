"""
Automated Chaos Scenario Pilot.

Design Label: CHAOS-007 — Automation Pilot
Owner: Platform Engineering
Dependencies:
  - src.chaos.swarm_chaos_coordinator (SwarmChaosCoordinator)
  - src.ml.training_pipeline (TrainingPipeline) — optional

Runs chaos scenarios continuously / on-schedule and feeds outcomes directly
into the ML training pipeline.  SHADOW mode logs outcomes without affecting
the live system.  Requires HITL confirmation to start any non-shadow mode.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MAX_LOG = 10_000


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PilotMode(Enum):
    CONTINUOUS = "continuous"
    SCHEDULED = "scheduled"
    ON_DEMAND = "on_demand"
    SHADOW = "shadow"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class PilotJob:
    job_id: str
    mode: PilotMode
    scenarios_per_cycle: int
    cycle_interval_seconds: int
    last_run: Optional[float]
    next_run: Optional[float]
    total_runs: int
    status: str  # idle | running | stopped | error
    stats: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# AutomationPilot — CHAOS-007
# ---------------------------------------------------------------------------

class AutomationPilot:
    """CHAOS-007 — Automation Pilot.

    Drives continuous chaos scenario generation and feeds training data to
    the ML pipeline.  HITL-gated for any mode other than SHADOW.
    """

    def __init__(
        self,
        mode: PilotMode = PilotMode.SHADOW,
        scenarios_per_cycle: int = 10,
        cycle_interval_seconds: int = 3600,
    ) -> None:
        self._mode = mode
        self._scenarios_per_cycle = scenarios_per_cycle
        self._cycle_interval = cycle_interval_seconds
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._daemon_thread: Optional[threading.Thread] = None
        self._training_pipeline = None
        self._coordinator = None

        self._job = PilotJob(
            job_id=str(uuid.uuid4()),
            mode=mode,
            scenarios_per_cycle=scenarios_per_cycle,
            cycle_interval_seconds=cycle_interval_seconds,
            last_run=None,
            next_run=None,
            total_runs=0,
            status="idle",
            stats={
                "total_scenarios_run": 0,
                "training_examples_generated": 0,
                "cycles_completed": 0,
                "errors": 0,
            },
        )

        self._outcome_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self, hitl_required: bool = True) -> Dict[str, Any]:
        """Start the automation pilot.  HITL gated for non-SHADOW modes."""
        if hitl_required and self._mode != PilotMode.SHADOW:
            logger.warning(
                "AutomationPilot.start() blocked: HITL required for mode=%s. "
                "Call start(hitl_required=False) to override.",
                self._mode.value,
            )
            return {
                "started": False,
                "reason": f"HITL confirmation required for mode={self._mode.value}",
                "job_id": self._job.job_id,
            }

        with self._lock:
            if self._job.status == "running":
                return {"started": False, "reason": "pilot already running", "job_id": self._job.job_id}

            self._stop_event.clear()
            self._job.status = "running"
            self._job.next_run = time.time()

        self._daemon_thread = threading.Thread(
            target=self._run_loop, name="chaos-pilot", daemon=True
        )
        self._daemon_thread.start()

        logger.info("AutomationPilot started: mode=%s scenarios_per_cycle=%d interval=%ds",
                    self._mode.value, self._scenarios_per_cycle, self._cycle_interval)
        return {"started": True, "job_id": self._job.job_id, "mode": self._mode.value}

    def stop(self) -> Dict[str, Any]:
        """Stop the automation pilot gracefully."""
        self._stop_event.set()
        with self._lock:
            self._job.status = "stopped"
        logger.info("AutomationPilot stop requested for job=%s", self._job.job_id)
        return {"stopped": True, "job_id": self._job.job_id, "stats": dict(self._job.stats)}

    def run_cycle(self) -> Dict[str, Any]:
        """Execute a single cycle: generate → simulate → collect → feed to ML."""
        cycle_start = time.time()
        coordinator = self._get_coordinator()

        try:
            results = coordinator.run_full_chaos_battery(intensity="moderate")
            outcomes = results.get("aggregate_stats", {})
            total_new = results.get("total_scenarios_run", self._scenarios_per_cycle)

            if self._mode != PilotMode.SHADOW:
                training_count = self._feed_to_training_pipeline(results)
            else:
                training_count = 0
                logger.debug("SHADOW mode: outcomes logged but not fed to training pipeline")

            with self._lock:
                self._job.stats["total_scenarios_run"] += total_new
                self._job.stats["training_examples_generated"] += training_count
                self._job.stats["cycles_completed"] += 1
                self._job.last_run = cycle_start
                self._job.next_run = cycle_start + self._cycle_interval
                self._job.total_runs += 1

                log_entry = {
                    "cycle": self._job.total_runs,
                    "timestamp": cycle_start,
                    "scenarios_run": total_new,
                    "training_examples": training_count,
                    "mode": self._mode.value,
                    "outcomes": outcomes,
                }
                if len(self._outcome_log) < _MAX_LOG:
                    self._outcome_log.append(log_entry)

            return log_entry

        except Exception as exc:
            logger.error("AutomationPilot cycle error: %s", exc)
            with self._lock:
                self._job.stats["errors"] += 1
            return {"error": str(exc), "cycle": self._job.total_runs}

    def get_status(self) -> Dict[str, Any]:
        """Return the current PilotJob status as a dictionary."""
        with self._lock:
            return {
                "job_id": self._job.job_id,
                "mode": self._job.mode.value,
                "status": self._job.status,
                "scenarios_per_cycle": self._job.scenarios_per_cycle,
                "cycle_interval_seconds": self._job.cycle_interval_seconds,
                "last_run": self._job.last_run,
                "next_run": self._job.next_run,
                "total_runs": self._job.total_runs,
            }

    def get_stats(self) -> Dict[str, Any]:
        """Return cumulative stats for the pilot."""
        with self._lock:
            return dict(self._job.stats)

    # ------------------------------------------------------------------
    # Internal methods
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        """Background daemon loop: run cycles at the configured interval."""
        while not self._stop_event.is_set():
            with self._lock:
                next_run = self._job.next_run or time.time()

            wait_secs = max(0.0, next_run - time.time())
            interrupted = self._stop_event.wait(timeout=wait_secs)
            if interrupted:
                break

            try:
                self.run_cycle()
            except Exception as exc:
                logger.error("Pilot loop error: %s", exc)
                with self._lock:
                    self._job.stats["errors"] += 1

            if self._mode == PilotMode.ON_DEMAND:
                break  # run exactly one cycle then stop

        with self._lock:
            if self._job.status == "running":
                self._job.status = "idle"

    def _feed_to_training_pipeline(self, cycle_results: Any) -> int:
        """Feed chaos outcomes into the ML TrainingPipeline.  Returns examples fed."""
        try:
            if self._training_pipeline is None:
                from src.ml.training_pipeline import TrainingPipeline  # type: ignore
                self._training_pipeline = TrainingPipeline()

            coordinator = self._get_coordinator()
            examples = coordinator.generate_augmented_training_data(
                total_examples=self._scenarios_per_cycle * 10
            )

            # TrainingPipeline may have add_examples, queue_batch, or similar
            pipeline = self._training_pipeline
            if hasattr(pipeline, "add_examples"):
                pipeline.add_examples(examples)
            elif hasattr(pipeline, "queue_batch"):
                pipeline.queue_batch(examples)
            elif hasattr(pipeline, "train"):
                pipeline.train(examples)

            return len(examples)

        except Exception as exc:
            logger.warning("Training pipeline feed failed (non-fatal): %s", exc)
            return 0

    def _get_coordinator(self):
        if self._coordinator is None:
            from src.chaos.swarm_chaos_coordinator import SwarmChaosCoordinator  # type: ignore
            self._coordinator = SwarmChaosCoordinator(
                max_cursors=8, max_agents=16
            )
        return self._coordinator
