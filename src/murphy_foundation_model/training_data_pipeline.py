# Copyright © 2020-2026 Inoni LLC — Created by Corey Post
# License: BSL 1.1
"""
Training Data Pipeline
======================

Converts labeled action traces into the instruction-tuning format
consumed by the MFM trainer.  Handles retention filtering, action-type
balancing, and stratified train / validation / test splits.

Output format (per example)::

    {
        "instruction": "Given the following world state and intent …",
        "input":  { "world_state": …, "intent": …, … },
        "output": { "action_plan": …, "confidence": …, … }
    }
"""

from __future__ import annotations

import json
import logging
import os
import random
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .action_trace_serializer import ActionTrace, ActionTraceCollector
from .outcome_labeler import OutcomeLabeler, OutcomeLabels

logger = logging.getLogger(__name__)


class TrainingDataPipeline:
    """End-to-end pipeline: traces → labeled → balanced → splits → JSONL.

    Parameters
    ----------
    trace_dir:
        Directory containing raw trace JSONL files.
    output_dir:
        Where to write the formatted train / validation / test splits.
    retention_days:
        Only use traces from the last *retention_days* days.
    labeler:
        An :class:`OutcomeLabeler` instance.  A default one is created
        if not supplied.
    seed:
        Random seed for reproducible splits.
    """

    def __init__(
        self,
        trace_dir: Optional[str] = None,
        output_dir: Optional[str] = None,
        retention_days: int = 90,
        labeler: Optional[OutcomeLabeler] = None,
        seed: int = 42,
    ) -> None:
        self.trace_dir = Path(
            trace_dir
            or os.environ.get("MFM_TRACE_DIR", "./data/action_traces")
        )
        self.output_dir = Path(
            output_dir
            or os.environ.get("MFM_OUTPUT_DIR", "./data/mfm_training")
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.retention_days = retention_days
        self.labeler = labeler or OutcomeLabeler()
        self.seed = seed

    # -- public API ---------------------------------------------------------

    def run_pipeline(self) -> Dict[str, int]:
        """Execute the full pipeline and return split sizes."""
        traces = self._load_traces()
        logger.info("Loaded %d traces", len(traces))

        traces = self._filter_by_retention(traces)
        logger.info("After retention filter: %d traces", len(traces))

        labeled = self._label_traces(traces)
        logger.info("Labeled %d traces", len(labeled))

        labeled = self._balance_by_action_type(labeled)
        logger.info("After balancing: %d traces", len(labeled))

        train, val, test = self._split_data(labeled)
        logger.info(
            "Split sizes — train=%d  val=%d  test=%d",
            len(train), len(val), len(test),
        )

        self._format_and_export(train, "train")
        self._format_and_export(val, "validation")
        self._format_and_export(test, "test")

        return {"train": len(train), "validation": len(val), "test": len(test)}

    # -- pipeline stages ----------------------------------------------------

    def _load_traces(self) -> List[ActionTrace]:
        """Load raw traces from JSONL files."""
        collector = ActionTraceCollector.get_instance(trace_dir=str(self.trace_dir))
        return collector.load_traces()

    def _filter_by_retention(
        self, traces: List[ActionTrace]
    ) -> List[ActionTrace]:
        """Drop traces older than *retention_days*."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.retention_days)
        result: List[ActionTrace] = []
        for t in traces:
            ts = t.timestamp
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts >= cutoff:
                result.append(t)
        return result

    def _label_traces(
        self, traces: List[ActionTrace]
    ) -> List[Tuple[ActionTrace, OutcomeLabels]]:
        """Attach quality labels to each trace."""
        labeled: List[Tuple[ActionTrace, OutcomeLabels]] = []
        for trace in traces:
            labels = self.labeler.label_trace(trace)
            # Also store labels dict on the trace itself
            trace.labels = {
                "success": float(labels.success),
                "efficiency": labels.efficiency,
                "safety_score": labels.safety_score,
                "confidence_calibration": labels.confidence_calibration,
                "human_agreement": labels.human_agreement,
                "overall_quality": labels.overall_quality,
            }
            labeled.append((trace, labels))
        return labeled

    def _balance_by_action_type(
        self,
        labeled: List[Tuple[ActionTrace, OutcomeLabels]],
        max_ratio: float = 3.0,
    ) -> List[Tuple[ActionTrace, OutcomeLabels]]:
        """Cap over-represented action types so no type exceeds *max_ratio*
        times the median count."""
        by_type: Dict[str, List[Tuple[ActionTrace, OutcomeLabels]]] = defaultdict(list)
        for item in labeled:
            key = ",".join(sorted(item[0].action_types)) or "UNKNOWN"
            by_type[key].append(item)

        if not by_type:
            return labeled

        counts = sorted(len(v) for v in by_type.values())
        median_count = counts[len(counts) // 2] if counts else 1
        cap = max(int(median_count * max_ratio), 1)

        rng = random.Random(self.seed)
        balanced: List[Tuple[ActionTrace, OutcomeLabels]] = []
        for key, items in by_type.items():
            if len(items) > cap:
                items = rng.sample(items, cap)
            balanced.extend(items)

        rng.shuffle(balanced)
        return balanced

    def _split_data(
        self,
        labeled: List[Tuple[ActionTrace, OutcomeLabels]],
        train_ratio: float = 0.8,
        val_ratio: float = 0.1,
    ) -> Tuple[
        List[Tuple[ActionTrace, OutcomeLabels]],
        List[Tuple[ActionTrace, OutcomeLabels]],
        List[Tuple[ActionTrace, OutcomeLabels]],
    ]:
        """80 / 10 / 10 split stratified by label category."""
        by_cat: Dict[str, List[Tuple[ActionTrace, OutcomeLabels]]] = defaultdict(list)
        for item in labeled:
            by_cat[item[1].label_category].append(item)

        train: List[Tuple[ActionTrace, OutcomeLabels]] = []
        val: List[Tuple[ActionTrace, OutcomeLabels]] = []
        test: List[Tuple[ActionTrace, OutcomeLabels]] = []

        rng = random.Random(self.seed)
        for cat, items in by_cat.items():
            rng.shuffle(items)
            n = len(items)
            n_train = max(int(n * train_ratio), 1) if n > 0 else 0
            n_val = max(int(n * val_ratio), 0)
            train.extend(items[:n_train])
            val.extend(items[n_train : n_train + n_val])
            test.extend(items[n_train + n_val :])

        rng.shuffle(train)
        rng.shuffle(val)
        rng.shuffle(test)
        return train, val, test

    # -- formatting & export ------------------------------------------------

    def _format_trace_for_training(
        self, trace: ActionTrace, labels: OutcomeLabels
    ) -> Dict[str, Any]:
        """Convert a trace to the instruction-tuning format."""
        return {
            "instruction": (
                "Given the following world state and intent, "
                "generate an action plan."
            ),
            "input": {
                "world_state": trace.world_state,
                "intent": trace.intent,
                "constraints": trace.constraints,
                "murphy_index": trace.murphy_index_at_decision,
                "history": [],  # empty context window (populated at inference time)
            },
            "output": {
                "action_plan": trace.actions_taken,
                "confidence": trace.confidence_at_decision,
                "predicted_murphy_index": trace.murphy_index_at_decision,
                "escalation_needed": (
                    any(c.get("escalation") for c in trace.constraints)
                    if trace.constraints
                    else False
                ),
            },
            "quality": {
                "label_category": labels.label_category,
                "overall_quality": labels.overall_quality,
            },
        }

    def _format_and_export(
        self,
        split: List[Tuple[ActionTrace, OutcomeLabels]],
        name: str,
    ) -> Path:
        """Write *split* to ``<output_dir>/<name>.jsonl``."""
        filepath = self.output_dir / f"{name}.jsonl"
        with open(filepath, "w", encoding="utf-8") as fh:
            for trace, labels in split:
                example = self._format_trace_for_training(trace, labels)
                fh.write(json.dumps(example, default=str) + "\n")
        logger.info("Wrote %d examples to %s", len(split), filepath)
        return filepath
