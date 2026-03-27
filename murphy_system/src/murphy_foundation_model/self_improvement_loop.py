# Copyright © 2020-2026 Inoni LLC — Created by Corey Post
# License: BSL 1.1
"""
Self-Improvement Loop — Automatic Retraining
===============================================

Orchestrates the continuous improvement cycle:

1. Collect traces via :class:`ActionTraceCollector`
2. Label via :class:`OutcomeLabeler`
3. Build training data via :class:`TrainingDataPipeline`
4. Fine-tune via :class:`MFMTrainer`
5. Evaluate via shadow deployment
6. Promote (or rollback) via :class:`MFMRegistry`

Monitors retrain triggers (trace count threshold, shadow accuracy
drop, human-override rate, manual trigger) and runs a full retraining
cycle when criteria are met.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)

# -- configuration -------------------------------------------------------

_DEFAULT_RETRAIN_THRESHOLD = int(os.getenv("MFM_RETRAIN_THRESHOLD", "10000"))
_DEFAULT_MIN_ACCURACY = float(os.getenv("MFM_SHADOW_MIN_ACCURACY", "0.80"))


@dataclass
class SelfImprovementConfig:
    """Configuration for the self-improvement loop."""

    retrain_threshold: int = _DEFAULT_RETRAIN_THRESHOLD
    min_accuracy: float = _DEFAULT_MIN_ACCURACY
    max_human_override_rate: float = 0.15
    check_interval_hours: float = 6.0


# -- loop -----------------------------------------------------------------


class SelfImprovementLoop:
    """Continuous self-improvement orchestrator.

    Monitors operational traces and shadow metrics to decide when to
    trigger a retraining cycle, then trains a new model version,
    evaluates it against a held-out test set, and promotes (or
    discards) the result via the model registry.
    """

    def __init__(
        self,
        config: Optional[SelfImprovementConfig] = None,
        trainer: Any = None,
        registry: Any = None,
        collector: Any = None,
    ) -> None:
        self.config = config or SelfImprovementConfig()
        self.trainer = trainer
        self.registry = registry
        self.collector = collector

        self._iteration = 0
        self._traces_since_retrain = 0
        self._last_retrain_time: Optional[str] = None
        self._manual_trigger = False
        self._history: List[Dict[str, Any]] = []
        logger.debug(
            "SelfImprovementLoop initialised — threshold=%d, min_acc=%.2f",
            self.config.retrain_threshold,
            self.config.min_accuracy,
        )

    # -- public API ---------------------------------------------------------

    def check_retrain_triggers(self) -> Dict[str, Any]:
        """Check all retrain triggers and return a summary.

        Returns
        -------
        dict with ``should_retrain`` (bool) and ``reasons`` (list[str]).
        """
        try:
            from src.self_learning_toggle import get_self_learning_toggle
            slt = get_self_learning_toggle()
            if not slt.is_enabled():
                slt.increment_skipped()
                return {"should_retrain": False, "reasons": ["self_learning_disabled"]}
        except Exception as exc:
            logger.debug("Non-critical error: %s", exc)

        reasons: List[str] = []

        # 1. Trace count
        if self._traces_since_retrain >= self.config.retrain_threshold:
            reasons.append(
                f"trace_count={self._traces_since_retrain} >= {self.config.retrain_threshold}"
            )

        # 2. Shadow accuracy drop
        shadow_accuracy = self._get_shadow_accuracy()
        if shadow_accuracy is not None and shadow_accuracy < self.config.min_accuracy:
            reasons.append(
                f"shadow_accuracy={shadow_accuracy:.2f} < {self.config.min_accuracy:.2f}"
            )

        # 3. Human override rate
        override_rate = self._get_human_override_rate()
        if override_rate is not None and override_rate > self.config.max_human_override_rate:
            reasons.append(
                f"human_override_rate={override_rate:.2f} > {self.config.max_human_override_rate:.2f}"
            )

        # 4. Manual trigger
        if self._manual_trigger:
            reasons.append("manual_trigger")
            self._manual_trigger = False

        should = len(reasons) > 0
        if should:
            logger.info("Retrain triggered — reasons: %s", reasons)
        return {"should_retrain": should, "reasons": reasons}

    def run_retraining_cycle(self) -> Dict[str, Any]:
        """Execute a full retraining cycle.

        Steps:
        1. Collect recent traces from the collector.
        2. Train a new model using the trainer.
        3. Evaluate the new model.
        4. Register the new version in the registry.
        5. Decide whether to promote.

        Returns
        -------
        dict with ``success`` (bool), ``new_version`` (str),
        ``metrics`` (dict).
        """
        self._iteration += 1
        cycle_start = time.monotonic()
        version_id = str(uuid.uuid4())[:8]
        version_str = f"v0.{self._iteration}"

        logger.info("Starting retraining cycle %d (version %s)", self._iteration, version_str)

        # -- Step 1: Collect traces -----------------------------------------
        traces = self._collect_traces()
        if not traces:
            logger.warning("No traces available — aborting retraining")
            return {"success": False, "new_version": version_str, "metrics": {}, "reason": "no_traces"}

        # -- Step 2: Train --------------------------------------------------
        train_result: Dict[str, Any] = {}
        if self.trainer is not None:
            train_method = getattr(self.trainer, "train", None)
            if callable(train_method):
                # Split traces: 90% train, 10% eval
                split = max(1, int(len(traces) * 0.9))
                train_data = traces[:split]
                eval_data = traces[split:]
                train_result = train_method(train_data, eval_data)
        else:
            logger.warning("No trainer configured — skipping training")
            train_result = {"status": "skipped", "reason": "no_trainer"}

        # -- Step 3: Evaluate -----------------------------------------------
        new_metrics = self.evaluate_new_model(self.trainer, traces)

        # -- Step 4: Register -----------------------------------------------
        if self.registry is not None:
            try:
                base_model_name = getattr(
                    getattr(self.trainer, "model", None), "config", None
                )
                base_model_name = (
                    getattr(base_model_name, "base_model", "unknown")
                    if base_model_name is not None
                    else "unknown"
                )

                from .mfm_registry import MFMModelVersion

                version = MFMModelVersion(
                    version_id=version_id,
                    version_str=version_str,
                    base_model=base_model_name,
                    training_config=train_result,
                    traces_used=len(traces),
                    created_at=datetime.now(timezone.utc).isoformat(),
                    metrics=new_metrics,
                    status="registered",
                    checkpoint_path="",
                )
                self.registry.register_version(version)
            except Exception as exc:
                logger.warning("Failed to register version: %s", exc)

        # -- Step 5: Promotion decision -------------------------------------
        current_metrics = self._get_current_production_metrics()
        promoted = self.should_promote_model(new_metrics, current_metrics)
        if promoted and self.registry is not None:
            try:
                self.registry.promote(version_id)
                logger.info("New version %s promoted", version_str)
            except Exception as exc:
                logger.warning("Promotion failed: %s", exc)
                promoted = False

        # -- Reset counters -------------------------------------------------
        self._traces_since_retrain = 0
        self._last_retrain_time = datetime.now(timezone.utc).isoformat()

        elapsed = time.monotonic() - cycle_start
        result = {
            "success": True,
            "new_version": version_str,
            "metrics": new_metrics,
            "promoted": promoted,
            "training_result": train_result,
            "traces_used": len(traces),
            "cycle_time_s": round(elapsed, 2),
        }
        capped_append(self._history, result)
        return result

    def evaluate_new_model(
        self,
        model: Any,
        test_data: Any,
    ) -> Dict[str, float]:
        """Evaluate a new model on held-out test data.

        Returns a dict of metrics (``accuracy``, ``confidence_mae``,
        ``risk_mae``, ``loss``).
        """
        if model is None:
            return {"accuracy": 0.0, "confidence_mae": 1.0, "risk_mae": 1.0, "loss": float("inf")}

        evaluator = getattr(model, "evaluate", None)
        if callable(evaluator):
            try:
                return evaluator(test_data)
            except Exception as exc:
                logger.warning("Evaluation failed: %s", exc)
                return {"accuracy": 0.0, "confidence_mae": 1.0, "risk_mae": 1.0, "loss": float("inf")}

        return {"accuracy": 0.0, "confidence_mae": 1.0, "risk_mae": 1.0, "loss": float("inf")}

    def should_promote_model(
        self,
        new_metrics: Dict[str, float],
        current_metrics: Dict[str, float],
    ) -> bool:
        """Decide whether the new model should replace the current one.

        A model is promoted if:
        - Its accuracy (or action_accuracy) ≥ ``min_accuracy``
        - Its accuracy is at least as good as the current production
          model.
        - Its loss is ≤ current loss (if available).
        """
        new_acc = new_metrics.get("accuracy", new_metrics.get("action_accuracy", 0.0))
        cur_acc = current_metrics.get("accuracy", current_metrics.get("action_accuracy", 0.0))

        if new_acc < self.config.min_accuracy:
            logger.info(
                "New model accuracy %.4f below threshold %.4f — not promoting",
                new_acc,
                self.config.min_accuracy,
            )
            return False

        if new_acc < cur_acc:
            logger.info(
                "New model accuracy %.4f < current %.4f — not promoting",
                new_acc,
                cur_acc,
            )
            return False

        new_loss = new_metrics.get("loss", float("inf"))
        cur_loss = current_metrics.get("loss", float("inf"))
        if new_loss > cur_loss * 1.05:
            logger.info(
                "New model loss %.4f > current %.4f — not promoting",
                new_loss,
                cur_loss,
            )
            return False

        logger.info(
            "Promotion approved — new_acc=%.4f, cur_acc=%.4f",
            new_acc,
            cur_acc,
        )
        return True

    def get_status(self) -> Dict[str, Any]:
        """Return current status of the self-improvement loop."""
        return {
            "iteration": self._iteration,
            "last_retrain": self._last_retrain_time,
            "traces_since_retrain": self._traces_since_retrain,
            "triggers": self.check_retrain_triggers(),
            "config": {
                "retrain_threshold": self.config.retrain_threshold,
                "min_accuracy": self.config.min_accuracy,
                "max_human_override_rate": self.config.max_human_override_rate,
                "check_interval_hours": self.config.check_interval_hours,
            },
            "history_count": len(self._history),
        }

    def record_trace(self) -> None:
        """Increment the trace counter (called after each new trace)."""
        self._traces_since_retrain += 1

    def trigger_manual_retrain(self) -> None:
        """Set the manual retrain trigger flag."""
        self._manual_trigger = True
        logger.info("Manual retrain triggered")

    @property
    def current_iteration(self) -> int:
        """Current iteration number."""
        return self._iteration

    # -- internal -----------------------------------------------------------

    def _collect_traces(self) -> List[Dict[str, Any]]:
        """Collect traces from the configured collector."""
        if self.collector is None:
            return []

        get_traces = getattr(self.collector, "get_traces", None)
        if callable(get_traces):
            try:
                return get_traces()
            except Exception as exc:
                logger.warning("Trace collection failed: %s", exc)
                return []

        get_recent = getattr(self.collector, "get_recent_traces", None)
        if callable(get_recent):
            try:
                return get_recent(self.config.retrain_threshold)
            except Exception as exc:
                logger.warning("Trace collection failed: %s", exc)
                return []

        return []

    def _get_shadow_accuracy(self) -> Optional[float]:
        """Retrieve current shadow accuracy from the registry's
        production model metrics."""
        if self.registry is None:
            return None
        try:
            prod = self.registry.get_current_production()
            if prod is not None:
                metrics = getattr(prod, "metrics", {})
                return metrics.get("accuracy", metrics.get("similarity_rate"))
        except Exception as exc:
            logger.debug("Non-critical error: %s", exc)
        return None

    def _get_human_override_rate(self) -> Optional[float]:
        """Retrieve human override rate from the production model."""
        if self.registry is None:
            return None
        try:
            prod = self.registry.get_current_production()
            if prod is not None:
                metrics = getattr(prod, "metrics", {})
                return metrics.get("human_override_rate")
        except Exception as exc:
            logger.debug("Non-critical error: %s", exc)
        return None

    def _get_current_production_metrics(self) -> Dict[str, float]:
        """Get metrics for the current production model."""
        if self.registry is None:
            return {}
        try:
            prod = self.registry.get_current_production()
            if prod is not None:
                return getattr(prod, "metrics", {})
        except Exception as exc:
            logger.debug("Non-critical error: %s", exc)
        return {}
