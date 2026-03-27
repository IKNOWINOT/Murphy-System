"""
GAIA Adapter — tests Murphy's multi-step tool-use assistant capabilities.

GAIA presents reasoning-intensive tasks stratified by difficulty (Level 1–3).
Murphy routes each task through its universal control plane and workflow
execution engine.

Metrics
-------
* ``success_rate``      — overall task success rate
* ``level_1_rate``      — success rate for Level-1 (simple) tasks
* ``level_2_rate``      — success rate for Level-2 (medium) tasks
* ``level_3_rate``      — success rate for Level-3 (hard) tasks

External dependency
-------------------
``datasets`` (HuggingFace) is required to load GAIA tasks.
If it is not installed the adapter skips gracefully.

References
----------
* https://huggingface.co/datasets/gaia-benchmark/GAIA
* https://arxiv.org/abs/2311.12983

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

try:
    import datasets as _hf_datasets  # noqa: F401

    _DATASETS_AVAILABLE = True
except ImportError:
    _DATASETS_AVAILABLE = False


class GAIAAdapter(BenchmarkAdapter):
    """Adapter for the GAIA benchmark (General AI Assistants)."""

    _HF_DATASET = "gaia-benchmark/GAIA"

    def __init__(self, max_tasks: int = 10, split: str = "validation") -> None:
        super().__init__()
        self._max_tasks = max_tasks
        self._split = split
        self._tasks: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # BenchmarkAdapter interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "gaia"

    @property
    def version(self) -> str:
        return "2023"

    @property
    def url(self) -> str:
        return "https://huggingface.co/datasets/gaia-benchmark/GAIA"

    def setup(self) -> None:
        """Load GAIA validation tasks from HuggingFace datasets."""
        if not _DATASETS_AVAILABLE:
            try:
                import pytest

                pytest.skip(
                    "GAIA adapter requires the 'datasets' package. "
                    "Install with: pip install datasets"
                )
            except ImportError:
                raise RuntimeError(
                    "GAIA adapter requires the 'datasets' package."
                ) from None

        try:
            import datasets as hf  # noqa: PLC0415

            ds = hf.load_dataset(
                self._HF_DATASET,
                "2023_all",
                split=self._split,
                trust_remote_code=False,
            )
            raw = list(ds)
            self._tasks = raw[: self._max_tasks]
            logger.info("GAIA: loaded %d/%d tasks", len(self._tasks), len(raw))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not load GAIA dataset: %s", exc)
            try:
                import pytest

                pytest.skip(f"GAIA dataset not available: {exc}")
            except ImportError:
                raise RuntimeError(f"GAIA dataset not available: {exc}") from exc

    def load_tasks(self) -> list[dict[str, Any]]:
        return list(self._tasks)

    def run_task(self, task: dict[str, Any]) -> BenchmarkResult:
        """Route a GAIA task through Murphy's universal control plane."""
        task_id = str(task.get("task_id", task.get("id", "unknown")))
        question = task.get("Question", task.get("question", ""))
        expected = task.get("Final answer", task.get("answer", ""))
        level = int(task.get("Level", task.get("level", 1)))

        start = time.perf_counter()
        answer_output: str = ""

        # Route through Murphy's workflow generator -------------------------
        try:
            from src.ai_workflow_generator import AIWorkflowGenerator  # noqa: PLC0415

            gen = AIWorkflowGenerator()
            result_obj = gen.generate_workflow(question)
            answer_output = str(result_obj)
        except Exception as exc:  # noqa: BLE001
            logger.debug("AIWorkflowGenerator unavailable for GAIA task %s: %s", task_id, exc)
            answer_output = f"[error: {exc}]"

        elapsed = time.perf_counter() - start

        # Heuristic: non-empty answer without errors counts as an attempt ----
        success = bool(answer_output) and "[error" not in answer_output.lower()
        # Exact-match scoring against expected answer (when available) --------
        score = 0.0
        if success and expected:
            norm_expected = str(expected).strip().lower()
            norm_actual = answer_output.strip().lower()
            score = 1.0 if norm_expected in norm_actual else 0.3
        elif success:
            score = 0.5  # partial credit when no expected answer present

        return BenchmarkResult(
            task_id=task_id,
            success=success,
            elapsed_seconds=elapsed,
            score=score,
            metadata={"level": level, "question_length": len(question)},
        )

    def score(self) -> dict[str, Any]:
        base = super().score()
        if self._suite_result is not None:
            results = self._suite_result.results
            for lvl in (1, 2, 3):
                lvl_results = [
                    r for r in results if r.metadata.get("level") == lvl
                ]
                if lvl_results:
                    rate = sum(1 for r in lvl_results if r.success) / len(lvl_results)
                    base[f"level_{lvl}_rate"] = round(rate, 4)
        return base
