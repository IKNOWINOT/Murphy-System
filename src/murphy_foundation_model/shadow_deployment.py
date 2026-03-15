# Copyright © 2020-2026 Inoni LLC — Created by Corey Post
# License: BSL 1.1
"""
Shadow Deployment — Shadow Mode Comparison
============================================

Runs the MFM in shadow mode alongside an external / live system,
comparing outputs without affecting production behaviour.  Logs every
comparison to a JSONL file and computes aggregate metrics to decide
whether the MFM is ready for promotion.

Action similarity is measured via Jaccard similarity of action-type
sets.  Aggregate metrics include similarity rate, confidence accuracy,
latency comparison, and estimated cost savings.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# -- configuration -------------------------------------------------------


@dataclass
class ShadowConfig:
    """Configuration for the shadow deployment controller."""

    log_dir: str = "./data/mfm_shadow_logs"
    comparison_window: int = 1000
    similarity_threshold: float = 0.7


# -- comparison record ----------------------------------------------------


@dataclass
class ShadowComparison:
    """A single shadow comparison record."""

    request_id: str
    timestamp: str
    mfm_output: Dict[str, Any]
    external_output: Dict[str, Any]
    action_similarity: float
    confidence_diff: float
    mfm_latency_ms: float
    external_latency_ms: float
    mfm_correct: Optional[bool] = None


# -- shadow deployment ----------------------------------------------------


class ShadowDeployment:
    """Shadow deployment controller.

    Runs the MFM inference service alongside an external system,
    comparing their outputs on every request and accumulating metrics
    to support a promotion decision.
    """

    def __init__(
        self,
        mfm_service: Any = None,
        config: Optional[ShadowConfig] = None,
    ) -> None:
        self.mfm_service = mfm_service
        self.config = config or ShadowConfig()
        self._comparisons: List[ShadowComparison] = []
        self._active = False
        os.makedirs(self.config.log_dir, exist_ok=True)
        logger.debug(
            "ShadowDeployment initialised — log_dir=%s, window=%d",
            self.config.log_dir,
            self.config.comparison_window,
        )

    # -- public API ---------------------------------------------------------

    def start(self) -> None:
        """Activate shadow mode."""
        self._active = True
        logger.info("Shadow deployment started")

    def stop(self) -> None:
        """Deactivate shadow mode."""
        self._active = False
        logger.info("Shadow deployment stopped")

    @property
    def is_active(self) -> bool:  # noqa: D401
        """Whether shadow mode is currently active."""
        return self._active

    def compare_outputs(
        self,
        request: Dict[str, Any],
        mfm_output: Dict[str, Any],
        external_output: Dict[str, Any],
    ) -> ShadowComparison:
        """Compare MFM output against an external system's output.

        Parameters
        ----------
        request :
            The original inference request.
        mfm_output :
            Prediction from the MFM, including ``action_plan``,
            ``confidence``, ``latency_ms``.
        external_output :
            Prediction from the external / live system in the same
            schema.

        Returns
        -------
        ShadowComparison with similarity metrics.
        """
        request_id = request.get("request_id", str(uuid.uuid4()))

        action_sim = self._jaccard_action_similarity(
            mfm_output.get("action_plan", []),
            external_output.get("action_plan", []),
        )
        conf_diff = abs(
            mfm_output.get("confidence", 0.0) - external_output.get("confidence", 0.0)
        )

        comparison = ShadowComparison(
            request_id=request_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            mfm_output=mfm_output,
            external_output=external_output,
            action_similarity=round(action_sim, 4),
            confidence_diff=round(conf_diff, 4),
            mfm_latency_ms=mfm_output.get("latency_ms", 0.0),
            external_latency_ms=external_output.get("latency_ms", 0.0),
        )

        self._comparisons.append(comparison)

        # Keep only the most recent comparison_window entries
        if len(self._comparisons) > self.config.comparison_window:
            self._comparisons = self._comparisons[-self.config.comparison_window :]

        self.log_comparison(comparison)
        return comparison

    def log_comparison(self, comparison: ShadowComparison) -> None:
        """Append a comparison record to the JSONL log."""
        log_path = os.path.join(self.config.log_dir, "shadow_comparisons.jsonl")
        record = {
            "request_id": comparison.request_id,
            "timestamp": comparison.timestamp,
            "action_similarity": comparison.action_similarity,
            "confidence_diff": comparison.confidence_diff,
            "mfm_latency_ms": comparison.mfm_latency_ms,
            "external_latency_ms": comparison.external_latency_ms,
            "mfm_correct": comparison.mfm_correct,
            "mfm_output": comparison.mfm_output,
            "external_output": comparison.external_output,
        }
        try:
            with open(log_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, default=str) + "\n")
        except OSError as exc:
            logger.warning("Failed to write shadow log: %s", exc)

    def get_metrics(self) -> Dict[str, Any]:
        """Compute aggregate metrics over the comparison window.

        Returns
        -------
        dict with ``similarity_rate``, ``confidence_accuracy``,
        ``latency_comparison``, ``cost_savings``, ``total_comparisons``.
        """
        n = len(self._comparisons)
        if n == 0:
            return {
                "similarity_rate": 0.0,
                "confidence_accuracy": 0.0,
                "latency_comparison": {},
                "cost_savings": 0.0,
                "total_comparisons": 0,
            }

        sim_above = sum(
            1 for c in self._comparisons
            if c.action_similarity >= self.config.similarity_threshold
        )
        similarity_rate = sim_above / n

        avg_conf_diff = sum(c.confidence_diff for c in self._comparisons) / n
        confidence_accuracy = max(0.0, 1.0 - avg_conf_diff)

        mfm_latencies = [c.mfm_latency_ms for c in self._comparisons if c.mfm_latency_ms > 0]
        ext_latencies = [c.external_latency_ms for c in self._comparisons if c.external_latency_ms > 0]

        avg_mfm_lat = sum(mfm_latencies) / len(mfm_latencies) if mfm_latencies else 0.0
        avg_ext_lat = sum(ext_latencies) / len(ext_latencies) if ext_latencies else 0.0

        latency_comparison = {
            "mfm_avg_ms": round(avg_mfm_lat, 2),
            "external_avg_ms": round(avg_ext_lat, 2),
            "mfm_faster": avg_mfm_lat < avg_ext_lat,
            "speedup_ratio": round(avg_ext_lat / max(avg_mfm_lat, 1e-3), 2),
        }

        # Estimate cost savings: ratio of external calls that could be
        # replaced by MFM (based on similarity and correct outcomes)
        correct_count = sum(
            1 for c in self._comparisons if c.mfm_correct is True
        )
        replaceable = sum(
            1 for c in self._comparisons
            if c.action_similarity >= self.config.similarity_threshold
        )
        cost_savings = replaceable / n if n > 0 else 0.0

        return {
            "similarity_rate": round(similarity_rate, 4),
            "confidence_accuracy": round(confidence_accuracy, 4),
            "latency_comparison": latency_comparison,
            "cost_savings": round(cost_savings, 4),
            "total_comparisons": n,
            "correct_count": correct_count,
        }

    def should_promote(self) -> bool:
        """Determine whether the MFM should be promoted based on shadow
        metrics.

        Promotion criteria:
        - Enough comparisons (≥ comparison_window)
        - Similarity rate ≥ similarity_threshold
        - Confidence accuracy ≥ 0.80
        """
        metrics = self.get_metrics()

        if metrics["total_comparisons"] < self.config.comparison_window:
            logger.debug(
                "Not enough comparisons for promotion: %d / %d",
                metrics["total_comparisons"],
                self.config.comparison_window,
            )
            return False

        sim_ok = metrics["similarity_rate"] >= self.config.similarity_threshold
        conf_ok = metrics["confidence_accuracy"] >= 0.80

        should = sim_ok and conf_ok
        if should:
            logger.info(
                "Shadow promotion recommended — sim=%.2f, conf_acc=%.2f",
                metrics["similarity_rate"],
                metrics["confidence_accuracy"],
            )
        else:
            logger.debug(
                "Shadow promotion NOT recommended — sim=%.2f (need %.2f), conf_acc=%.2f (need 0.80)",
                metrics["similarity_rate"],
                self.config.similarity_threshold,
                metrics["confidence_accuracy"],
            )
        return should

    # -- internal -----------------------------------------------------------

    @staticmethod
    def _jaccard_action_similarity(
        plan_a: List[Any],
        plan_b: List[Any],
    ) -> float:
        """Compute Jaccard similarity of action types between two plans."""
        def _extract_types(plan: List[Any]) -> set:
            types: set = set()
            for step in plan:
                if isinstance(step, dict):
                    types.add(step.get("type", "unknown"))
                else:
                    types.add(str(step))
            return types

        set_a = _extract_types(plan_a)
        set_b = _extract_types(plan_b)

        if not set_a and not set_b:
            return 1.0
        if not set_a or not set_b:
            return 0.0

        intersection = set_a & set_b
        union = set_a | set_b
        return len(intersection) / (len(union) or 1)
