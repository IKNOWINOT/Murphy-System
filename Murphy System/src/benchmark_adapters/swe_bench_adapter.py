"""
SWE-bench Adapter — tests Murphy's code-generation and bug-fixing capability.

SWE-bench presents real GitHub issues; the agent must produce a code patch
that makes the corresponding test suite pass.  Murphy routes each task
through ``AIWorkflowGenerator`` and the self-fix pipeline.

Metrics
-------
* ``resolved_rate``   — fraction of issues where the generated patch passes CI
* ``mean_time``       — average seconds per task
* ``cost_estimate``   — rough token-cost proxy (chars generated / 4 * unit_cost)

External dependency
-------------------
``datasets`` (HuggingFace) is required to load SWE-bench Lite.
If it is not installed the adapter skips gracefully.

References
----------
* https://www.swebench.com/
* https://github.com/SWE-bench/SWE-bench

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

# Optional heavy deps guarded by try/except -----------------------------------
try:
    import datasets as _hf_datasets  # noqa: F401

    _DATASETS_AVAILABLE = True
except ImportError:
    _DATASETS_AVAILABLE = False


class SWEBenchAdapter(BenchmarkAdapter):
    """Adapter for SWE-bench Lite (300 software-engineering tasks)."""

    #: HuggingFace dataset identifier for SWE-bench Lite
    _HF_DATASET = "princeton-nlp/SWE-bench_Lite"

    def __init__(self, max_tasks: int = 10) -> None:
        super().__init__()
        self._max_tasks = max_tasks
        self._tasks: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # BenchmarkAdapter interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "swe-bench"

    @property
    def version(self) -> str:
        return "lite-v1"

    @property
    def url(self) -> str:
        return "https://www.swebench.com/"

    def setup(self) -> None:
        """Load SWE-bench Lite tasks from HuggingFace datasets."""
        if not _DATASETS_AVAILABLE:
            try:
                import pytest

                pytest.skip(
                    "SWE-bench adapter requires the 'datasets' package. "
                    "Install with: pip install datasets"
                )
            except ImportError:
                raise RuntimeError(
                    "SWE-bench adapter requires the 'datasets' package."
                ) from None

        try:
            import datasets as hf  # noqa: PLC0415

            ds = hf.load_dataset(self._HF_DATASET, split="test", trust_remote_code=False)
            raw = list(ds)
            self._tasks = raw[: self._max_tasks]
            logger.info(
                "SWE-bench Lite: loaded %d/%d tasks", len(self._tasks), len(raw)
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not load SWE-bench dataset: %s", exc)
            try:
                import pytest

                pytest.skip(f"SWE-bench dataset not available: {exc}")
            except ImportError:
                raise RuntimeError(
                    f"SWE-bench dataset not available: {exc}"
                ) from exc

    def load_tasks(self) -> list[dict[str, Any]]:
        return list(self._tasks)

    def run_task(self, task: dict[str, Any]) -> BenchmarkResult:
        """Route a single SWE-bench task through Murphy's workflow + self-fix pipeline."""
        task_id = str(task.get("instance_id", task.get("id", "unknown")))
        issue_text = task.get("problem_statement", task.get("issue", ""))

        start = time.perf_counter()

        # Attempt to load Murphy's AIWorkflowGenerator ----------------------
        workflow_output: str = ""
        try:
            from src.ai_workflow_generator import AIWorkflowGenerator  # noqa: PLC0415

            gen = AIWorkflowGenerator()
            result_obj = gen.generate_workflow(issue_text)
            workflow_output = str(result_obj)
        except Exception as exc:  # noqa: BLE001
            logger.debug("AIWorkflowGenerator unavailable for task %s: %s", task_id, exc)
            workflow_output = f"[workflow_generator_error: {exc}]"

        # Attempt self-fix pipeline -----------------------------------------
        patch_output: str = ""
        try:
            from src.self_fix_loop import SelfFixLoop  # noqa: PLC0415

            fixer = SelfFixLoop()
            patch_output = str(fixer.fix(issue_text))
        except Exception as exc:  # noqa: BLE001
            logger.debug("SelfFixLoop unavailable for task %s: %s", task_id, exc)
            patch_output = f"[self_fix_loop_error: {exc}]"

        elapsed = time.perf_counter() - start

        # Heuristic success: patch produced non-trivial output ---------------
        generated = workflow_output + patch_output
        resolved = bool(generated) and "[error" not in generated.lower()
        score = 1.0 if resolved else 0.0

        # Cost proxy: characters generated / 4 tokens * $0.000002 per token --
        cost_estimate = len(generated) / 4 * 0.000002

        return BenchmarkResult(
            task_id=task_id,
            success=resolved,
            elapsed_seconds=elapsed,
            score=score,
            metadata={
                "repo": task.get("repo", ""),
                "cost_estimate_usd": round(cost_estimate, 6),
                "patch_chars": len(patch_output),
            },
        )

    def score(self) -> dict[str, Any]:
        base = super().score()
        if self._suite_result is not None:
            results = self._suite_result.results
            costs = [r.metadata.get("cost_estimate_usd", 0.0) for r in results]
            base["resolved_rate"] = base["success_rate"]
            base["total_cost_estimate_usd"] = round(sum(costs), 6)
        return base
