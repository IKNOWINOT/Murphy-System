"""
Training Pipeline — collects labelled data from multiple sources and fine-tunes the MFM.

Sources: CORRECTION_LOOP, WORKFLOW_HISTORY, CHAOS_SCENARIOS, SYNTHETIC, HUMAN_FEEDBACK.

Safety: all training runs require a HITL gate unless explicitly bypassed in tests.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MAX_JOBS = 200  # bounded job history


# ---------------------------------------------------------------------------
# Enums / dataclasses
# ---------------------------------------------------------------------------

class TrainingSource(str, Enum):
    CORRECTION_LOOP = "correction_loop"
    WORKFLOW_HISTORY = "workflow_history"
    CHAOS_SCENARIOS = "chaos_scenarios"
    SYNTHETIC = "synthetic"
    HUMAN_FEEDBACK = "human_feedback"


class JobStatus(str, Enum):
    PENDING = "pending"
    AWAITING_HITL = "awaiting_hitl"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TrainingJob:
    job_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    source: List[TrainingSource] = field(default_factory=list)
    status: JobStatus = JobStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "source": [s.value for s in self.source],
            "status": self.status.value,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "metrics": self.metrics,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class TrainingPipeline:
    """Collects training data from multiple sources and dispatches fine-tuning jobs."""

    def __init__(self, config: Optional[Any] = None, trace_dir: str = "./data/action_traces") -> None:
        self._config = config
        self._trace_dir = trace_dir
        self._lock = threading.Lock()
        self._jobs: List[TrainingJob] = []
        self._event_bus: Optional[Any] = None
        self._mfm_trainer: Optional[Any] = None

        # Try to wire up event bus for job lifecycle events.
        try:
            from src.event_backbone import EventBackbone  # type: ignore
            self._event_bus = EventBackbone()
        except Exception:
            try:
                from event_backbone import EventBackbone  # type: ignore
                self._event_bus = EventBackbone()
            except Exception:
                logger.debug("EventBackbone unavailable; training events will not be published")

    # ------------------------------------------------------------------
    # Data collection
    # ------------------------------------------------------------------

    def collect_training_data(
        self, sources: Optional[List[TrainingSource]] = None
    ) -> List[Dict[str, Any]]:
        """Aggregate training examples from all requested *sources*."""
        if sources is None:
            sources = list(TrainingSource)

        all_examples: List[Dict[str, Any]] = []
        collectors = {
            TrainingSource.CORRECTION_LOOP: self._collect_from_corrections,
            TrainingSource.WORKFLOW_HISTORY: self._collect_from_workflow_history,
            TrainingSource.CHAOS_SCENARIOS: self._collect_from_chaos_scenarios,
            TrainingSource.SYNTHETIC: self._collect_synthetic,
            TrainingSource.HUMAN_FEEDBACK: self._collect_human_feedback,
        }

        for source in sources:
            fn = collectors.get(source)
            if fn is None:
                continue
            try:
                examples = fn()
                logger.info("Collected %d examples from %s", len(examples), source.value)
                all_examples.extend(examples)
            except Exception as exc:
                logger.warning("Failed to collect from %s: %s", source.value, exc)

        return all_examples

    def _collect_from_corrections(self) -> List[Dict[str, Any]]:
        """Pull labelled correction pairs from the MFM training-data pipeline."""
        examples: List[Dict[str, Any]] = []

        try:
            from src.murphy_foundation_model.training_data_pipeline import (  # type: ignore
                TrainingDataPipeline,
            )
            pipeline = TrainingDataPipeline(trace_dir=self._trace_dir)
            splits = pipeline.run_pipeline()
            output_dir = getattr(pipeline, "_output_dir", "./data/mfm_training")
            train_path = os.path.join(output_dir, "train.jsonl")
            if os.path.isfile(train_path):
                with open(train_path, "r", encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if line:
                            examples.append(json.loads(line))
            logger.debug("Loaded %d MFM training examples (splits=%s)", len(examples), splits)
        except Exception as exc:
            logger.debug("MFM training-data pipeline unavailable: %s", exc)
            # Graceful fallback: scan trace_dir for raw JSONL files.
            examples.extend(self._scan_jsonl_dir(self._trace_dir))

        return examples

    def _collect_from_chaos_scenarios(self) -> List[Dict[str, Any]]:
        """Generate training data from economic chaos scenarios."""
        examples: List[Dict[str, Any]] = []

        try:
            from src.lcm_chaos_simulation import LCMChaosSimulation  # type: ignore
        except ImportError:
            try:
                from lcm_chaos_simulation import LCMChaosSimulation  # type: ignore
            except ImportError:
                logger.debug("lcm_chaos_simulation unavailable; skipping chaos scenarios")
                return examples

        try:
            sim = LCMChaosSimulation()
            # Run a lightweight simulation and convert results to training examples.
            results = sim.run_all() if hasattr(sim, "run_all") else {}
            for epoch_name, domain_results in (results.items() if isinstance(results, dict) else []):
                for domain, outcome in (domain_results.items() if isinstance(domain_results, dict) else []):
                    examples.append({
                        "instruction": f"Handle chaos scenario: epoch={epoch_name}, domain={domain}",
                        "input": {"epoch": epoch_name, "domain": domain, "outcome": outcome},
                        "output": {"response": "adapt_strategy", "confidence": 0.7},
                        "source": TrainingSource.CHAOS_SCENARIOS.value,
                    })
        except Exception as exc:
            logger.warning("Chaos scenario collection failed: %s", exc)

        return examples

    def _collect_from_workflow_history(self) -> List[Dict[str, Any]]:
        """Load workflow execution history from the orchestrator store."""
        examples: List[Dict[str, Any]] = []

        # Attempt to import orchestration history.
        history_paths = [
            "./data/workflow_history.jsonl",
            "./data/execution_history.jsonl",
            "./logs/workflow_history.jsonl",
        ]
        for path in history_paths:
            if os.path.isfile(path):
                examples.extend(self._scan_jsonl_dir(os.path.dirname(path)))
                break

        # Also try to pull from orchestrator module.
        try:
            from src.orchestration import get_execution_history  # type: ignore
            for record in get_execution_history(limit=500):
                examples.append({
                    "instruction": "Complete workflow step",
                    "input": record,
                    "output": {"result": record.get("result", "ok")},
                    "source": TrainingSource.WORKFLOW_HISTORY.value,
                })
        except Exception:
            logger.debug("Suppressed exception in training_pipeline")

        return examples

    def _collect_synthetic(self) -> List[Dict[str, Any]]:
        """Generate lightweight synthetic examples for bootstrapping."""
        templates = [
            ("Summarise this document.", "summary", "Provide a concise summary."),
            ("Extract action items.", "extract", "List all action items."),
            ("Classify the intent.", "classify", "The intent is: task_execution."),
            ("Generate a plan.", "plan", "Step 1: analyse, Step 2: execute, Step 3: verify."),
        ]
        return [
            {
                "instruction": instr,
                "input": {"task_type": t_type},
                "output": {"response": resp, "confidence": 0.9},
                "source": TrainingSource.SYNTHETIC.value,
            }
            for instr, t_type, resp in templates
        ]

    def _collect_human_feedback(self) -> List[Dict[str, Any]]:
        """Load human-validated corrections from the feedback store."""
        examples: List[Dict[str, Any]] = []
        feedback_path = "./data/human_feedback.jsonl"
        if os.path.isfile(feedback_path):
            examples.extend(self._scan_jsonl_dir(os.path.dirname(feedback_path)))
        return examples

    def _scan_jsonl_dir(self, directory: str) -> List[Dict[str, Any]]:
        """Read all *.jsonl files in *directory* and return parsed objects."""
        results: List[Dict[str, Any]] = []
        if not os.path.isdir(directory):
            return results
        for fname in os.listdir(directory):
            if not fname.endswith(".jsonl"):
                continue
            path = os.path.join(directory, fname)
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if line:
                            results.append(json.loads(line))
            except Exception as exc:
                logger.debug("Could not read %s: %s", path, exc)
        return results

    # ------------------------------------------------------------------
    # Job scheduling
    # ------------------------------------------------------------------

    def schedule_training_run(
        self,
        sources: Optional[List[TrainingSource]] = None,
        hitl_required: bool = True,
    ) -> TrainingJob:
        """Create a TrainingJob and optionally gate it behind a HITL review."""
        if sources is None:
            sources = [TrainingSource.CORRECTION_LOOP, TrainingSource.WORKFLOW_HISTORY]

        job = TrainingJob(source=sources)
        if hitl_required:
            job.status = JobStatus.AWAITING_HITL
            logger.info("Training job %s awaiting HITL approval", job.job_id)
        else:
            job.status = JobStatus.PENDING

        self._append_job(job)
        self._publish_event("training.job.scheduled", job.to_dict())
        return job

    def run_training_job(self, job_id: str) -> TrainingJob:
        """Execute the training job identified by *job_id*."""
        job = self._find_job(job_id)
        if job is None:
            raise ValueError(f"Unknown job_id: {job_id}")

        if job.status == JobStatus.AWAITING_HITL:
            raise RuntimeError(f"Job {job_id} is awaiting HITL approval before it can run")

        with self._lock:
            job.status = JobStatus.RUNNING
        self._publish_event("training.job.started", {"job_id": job_id})

        try:
            examples = self.collect_training_data(job.source)
            metrics = self._dispatch_to_trainer(examples)
            with self._lock:
                job.status = JobStatus.COMPLETED
                job.completed_at = datetime.now(timezone.utc).isoformat()
                job.metrics = metrics
            self._publish_event("training.job.completed", job.to_dict())
            logger.info("Training job %s completed: %s", job_id, metrics)
        except Exception as exc:
            with self._lock:
                job.status = JobStatus.FAILED
                job.error = str(exc)
                job.completed_at = datetime.now(timezone.utc).isoformat()
            self._publish_event("training.job.failed", {"job_id": job_id, "error": str(exc)})
            logger.error("Training job %s failed: %s", job_id, exc)

        return job

    def approve_hitl(self, job_id: str) -> TrainingJob:
        """Mark an AWAITING_HITL job as PENDING so it can be run."""
        job = self._find_job(job_id)
        if job is None:
            raise ValueError(f"Unknown job_id: {job_id}")
        with self._lock:
            if job.status != JobStatus.AWAITING_HITL:
                raise RuntimeError(f"Job {job_id} is not awaiting HITL (status={job.status})")
            job.status = JobStatus.PENDING
        self._publish_event("training.job.hitl_approved", {"job_id": job_id})
        return job

    # ------------------------------------------------------------------
    # Job queries
    # ------------------------------------------------------------------

    def get_job_status(self, job_id: str) -> Optional[TrainingJob]:
        return self._find_job(job_id)

    def list_jobs(self, limit: int = 50) -> List[TrainingJob]:
        with self._lock:
            return list(self._jobs[-limit:])

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _dispatch_to_trainer(self, examples: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Send collected examples to MFMTrainer if available, else no-op."""
        try:
            from src.murphy_foundation_model.mfm_trainer import MFMTrainer, load_training_data  # type: ignore
            trainer = MFMTrainer()
            trainer.prepare_model()
            # Persist examples as a transient JSONL and pass path to trainer.
            os.makedirs("./data/mfm_training", exist_ok=True)
            tmp_path = "./data/mfm_training/_pipeline_train.jsonl"
            with open(tmp_path, "w", encoding="utf-8") as fh:
                for ex in examples:
                    fh.write(json.dumps(ex) + "\n")
            train_data, eval_data = load_training_data("./data/mfm_training")
            result = trainer.train(train_data, eval_data)
            return {"examples": len(examples), "trainer_metrics": result}
        except Exception as exc:
            logger.info("MFMTrainer unavailable (%s); recording collection stats only", exc)
            return {"examples": len(examples), "trainer_metrics": None}

    def _append_job(self, job: TrainingJob) -> None:
        with self._lock:
            self._jobs.append(job)
            if len(self._jobs) > _MAX_JOBS:
                self._jobs = self._jobs[-_MAX_JOBS:]

    def _find_job(self, job_id: str) -> Optional[TrainingJob]:
        with self._lock:
            for job in reversed(self._jobs):
                if job.job_id == job_id:
                    return job
        return None

    def _publish_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        if self._event_bus is None:
            return
        try:
            self._event_bus.publish(event_type, payload)  # type: ignore[arg-type]
        except Exception as exc:
            logger.debug("Could not publish event %s: %s", event_type, exc)
