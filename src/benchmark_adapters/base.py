"""
Base classes and dataclasses for the Murphy System benchmark adapter framework.

Defines the abstract ``BenchmarkAdapter`` interface and the ``BenchmarkResult``
/ ``BenchmarkSuiteResult`` dataclasses used by every concrete adapter.

Design goals
------------
* All adapters work even when external benchmark repos are NOT cloned —
  missing data → ``pytest.skip()`` with a clear message.
* Results are serialisable to JSON for CI artifact upload.
* Thread-safe aggregation via ``threading.Lock``.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""
from __future__ import annotations

import json
import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class BenchmarkResult:
    """Result for a single benchmark task."""

    task_id: str
    success: bool
    elapsed_seconds: float
    score: float = 0.0  # normalised 0‥1
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BenchmarkSuiteResult:
    """Aggregated results for a full benchmark suite."""

    benchmark_name: str
    benchmark_version: str
    run_timestamp: str = field(
        default_factory=lambda: datetime.now(tz=timezone.utc).isoformat()
    )
    tasks_total: int = 0
    tasks_succeeded: int = 0
    tasks_failed: int = 0
    tasks_skipped: int = 0
    total_elapsed_seconds: float = 0.0
    mean_elapsed_seconds: float = 0.0
    success_rate: float = 0.0
    mean_score: float = 0.0
    results: list[BenchmarkResult] = field(default_factory=list)
    extra_metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["results"] = [r.to_dict() for r in self.results]
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    # ------------------------------------------------------------------
    # Derived helpers
    # ------------------------------------------------------------------

    def compute_aggregates(self) -> None:
        """Recompute aggregate fields from ``self.results``."""
        completed = [r for r in self.results if not r.metadata.get("skipped")]
        self.tasks_total = len(self.results)
        self.tasks_succeeded = sum(1 for r in completed if r.success)
        self.tasks_failed = sum(1 for r in completed if not r.success)
        self.tasks_skipped = sum(
            1 for r in self.results if r.metadata.get("skipped")
        )
        elapsed_values = [r.elapsed_seconds for r in completed]
        self.total_elapsed_seconds = sum(elapsed_values)
        self.mean_elapsed_seconds = (
            self.total_elapsed_seconds / len(elapsed_values) if elapsed_values else 0.0
        )
        scores = [r.score for r in completed]
        self.mean_score = sum(scores) / len(scores) if scores else 0.0
        self.success_rate = (
            self.tasks_succeeded / len(completed) if completed else 0.0
        )


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------


class BenchmarkAdapter(ABC):
    """Abstract base for all Murphy benchmark adapters.

    Subclasses must implement :py:meth:`name`, :py:meth:`version`,
    :py:meth:`url`, :py:meth:`setup`, and :py:meth:`run_task`.
    The :py:meth:`run_suite` and :py:meth:`score` methods have default
    implementations that can be overridden for benchmark-specific logic.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._suite_result: BenchmarkSuiteResult | None = None

    # ------------------------------------------------------------------
    # Abstract properties
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier, e.g. ``"swe-bench"``."""

    @property
    @abstractmethod
    def version(self) -> str:
        """Dataset / harness version string."""

    @property
    @abstractmethod
    def url(self) -> str:
        """Official benchmark URL for reference."""

    # ------------------------------------------------------------------
    # Abstract methods
    # ------------------------------------------------------------------

    @abstractmethod
    def setup(self) -> None:
        """Download or prepare benchmark data.

        Raise ``RuntimeError`` if setup fails unrecoverably.
        Call ``pytest.skip()`` (imported lazily) if optional deps are absent.
        """

    @abstractmethod
    def run_task(self, task: dict[str, Any]) -> BenchmarkResult:
        """Execute a single benchmark task and return a :class:`BenchmarkResult`."""

    # ------------------------------------------------------------------
    # Concrete helpers with sensible defaults
    # ------------------------------------------------------------------

    def load_tasks(self) -> list[dict[str, Any]]:  # noqa: D401
        """Return the list of task dicts for this benchmark.

        Default implementation returns an empty list (no tasks available).
        Override in subclasses to load real tasks.
        """
        return []

    def run_suite(
        self,
        tasks: list[dict[str, Any]] | None = None,
        max_workers: int = 1,
    ) -> BenchmarkSuiteResult:
        """Run all tasks and aggregate results.

        Parameters
        ----------
        tasks:
            Override the default task list (useful for testing subsets).
        max_workers:
            Number of parallel worker threads.  Defaults to 1 (sequential)
            to be safe on resource-constrained CI runners.

        Returns
        -------
        BenchmarkSuiteResult
            Aggregated results with all individual task outcomes.
        """
        if tasks is None:
            tasks = self.load_tasks()

        suite = BenchmarkSuiteResult(
            benchmark_name=self.name,
            benchmark_version=self.version,
        )

        if max_workers <= 1:
            for task in tasks:
                result = self._safe_run_task(task)
                with self._lock:
                    suite.results.append(result)
        else:
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(
                max_workers=max_workers
            ) as executor:
                futures = {executor.submit(self._safe_run_task, t): t for t in tasks}
                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    with self._lock:
                        suite.results.append(result)

        suite.compute_aggregates()
        with self._lock:
            self._suite_result = suite
        return suite

    def score(self) -> dict[str, Any]:
        """Return standardised metrics dict after :py:meth:`run_suite`.

        Returns a minimal dict if no suite has been run yet.
        """
        if self._suite_result is None:
            return {"benchmark": self.name, "run": False}
        s = self._suite_result
        return {
            "benchmark": self.name,
            "version": self.version,
            "run_timestamp": s.run_timestamp,
            "tasks_total": s.tasks_total,
            "tasks_succeeded": s.tasks_succeeded,
            "tasks_failed": s.tasks_failed,
            "tasks_skipped": s.tasks_skipped,
            "success_rate": round(s.success_rate, 4),
            "mean_score": round(s.mean_score, 4),
            "mean_elapsed_seconds": round(s.mean_elapsed_seconds, 3),
            **s.extra_metrics,
        }

    def export_results(self, path: str | Path) -> Path:
        """Write the suite result as a JSON file.

        Parameters
        ----------
        path:
            Destination path.  Parent directories are created automatically.

        Returns
        -------
        Path
            The resolved path of the written file.
        """
        out = Path(path).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        if self._suite_result is None:
            data: dict[str, Any] = {
                "benchmark": self.name,
                "run": False,
                "message": "No suite has been run yet.",
            }
        else:
            data = self._suite_result.to_dict()
        out.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info("Benchmark results written to %s", out)
        return out

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _safe_run_task(self, task: dict[str, Any]) -> BenchmarkResult:
        """Wrap :py:meth:`run_task` with exception handling."""
        task_id = str(task.get("id", task.get("task_id", "unknown")))
        start = time.perf_counter()
        try:
            result = self.run_task(task)
            result.elapsed_seconds = time.perf_counter() - start
            return result
        except Exception as exc:  # noqa: BLE001
            elapsed = time.perf_counter() - start
            logger.warning("Task %s failed with error: %s", task_id, exc)
            return BenchmarkResult(
                task_id=task_id,
                success=False,
                elapsed_seconds=elapsed,
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r} version={self.version!r}>"
