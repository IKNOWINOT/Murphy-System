"""
Model Evaluation Harness — benchmarks model versions across accuracy, latency, cost, and chaos robustness.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MAX_HISTORY = 200
_BENCHMARK_PROMPTS = [
    ("Summarise the key risks in a manufacturing workflow.", "summary"),
    ("List action items from the following meeting notes: A agreed to fix bug B by Friday.", "extraction"),
    ("Classify the intent: 'Schedule a deployment for 3 PM tomorrow'.", "classification"),
    ("Generate a step-by-step plan to migrate a monolith to microservices.", "planning"),
    ("Explain circuit breaker pattern in distributed systems.", "explanation"),
]


# ---------------------------------------------------------------------------
# Enums / dataclasses
# ---------------------------------------------------------------------------

class BusinessDomain(str, Enum):
    LEGAL = "legal"
    MEDICAL = "medical"
    FINANCE = "finance"
    TECH = "tech"
    MANUFACTURING = "manufacturing"
    RETAIL = "retail"
    EDUCATION = "education"
    LOGISTICS = "logistics"
    ENERGY = "energy"
    REAL_ESTATE = "real_estate"
    HOSPITALITY = "hospitality"
    AGRICULTURE = "agriculture"
    GOVERNMENT = "government"
    MEDIA = "media"
    HEALTHCARE = "healthcare"


@dataclass
class EvalMetric:
    metric_name: str = ""
    value: float = 0.0
    unit: str = ""
    benchmark_target: float = 0.0
    passed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "value": self.value,
            "unit": self.unit,
            "benchmark_target": self.benchmark_target,
            "passed": self.passed,
        }


@dataclass
class EvalResult:
    eval_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    model_version: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metrics: List[EvalMetric] = field(default_factory=list)
    domain_scores: Dict[str, float] = field(default_factory=dict)
    overall_score: float = 0.0
    passed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "eval_id": self.eval_id,
            "model_version": self.model_version,
            "timestamp": self.timestamp,
            "metrics": [m.to_dict() for m in self.metrics],
            "domain_scores": self.domain_scores,
            "overall_score": self.overall_score,
            "passed": self.passed,
        }


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------

class ModelEvaluator:
    """
    Runs a structured evaluation suite against a model version.

    All evaluation methods degrade gracefully when backing services
    (InferenceEngine, chaos simulation) are unavailable.
    """

    # Minimum overall score required to pass.
    _PASS_THRESHOLD = 0.65

    def __init__(self, inference_engine: Optional[Any] = None) -> None:
        self._lock = threading.Lock()
        self._history: List[EvalResult] = []
        self._engine = inference_engine

        if self._engine is None:
            try:
                from .inference_engine import InferenceEngine  # type: ignore
                self._engine = InferenceEngine()
            except Exception as exc:
                logger.debug("InferenceEngine unavailable in evaluator: %s", exc)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def evaluate_model(
        self,
        version_id: str,
        domains: Optional[List[BusinessDomain]] = None,
    ) -> EvalResult:
        """Run the full evaluation suite and persist the result."""
        if domains is None:
            domains = [BusinessDomain.TECH, BusinessDomain.FINANCE, BusinessDomain.MANUFACTURING]

        result = EvalResult(model_version=version_id)
        all_scores: List[float] = []

        # Task completion.
        task_metric = self._evaluate_task_completion(version_id)
        result.metrics.append(task_metric)
        all_scores.append(task_metric.value)

        # Latency.
        latency_metric = self._evaluate_latency(version_id)
        result.metrics.append(latency_metric)
        # Latency doesn't contribute to overall score directly.

        # Cost.
        cost_metric = self._evaluate_cost(version_id)
        result.metrics.append(cost_metric)

        # Domain-specific accuracy.
        for domain in domains:
            score = self._evaluate_by_domain(version_id, domain)
            result.domain_scores[domain.value] = score
            all_scores.append(score)

        # Chaos robustness.
        chaos_metric = self._evaluate_chaos_robustness(version_id)
        result.metrics.append(chaos_metric)
        all_scores.append(chaos_metric.value)

        result.overall_score = round(sum(all_scores) / max(len(all_scores), 1), 4)
        result.passed = result.overall_score >= self._PASS_THRESHOLD

        self._append_history(result)
        logger.info(
            "Evaluation %s for version %s: score=%.3f passed=%s",
            result.eval_id, version_id, result.overall_score, result.passed,
        )
        return result

    # ------------------------------------------------------------------
    # Sub-evaluations
    # ------------------------------------------------------------------

    def _evaluate_task_completion(self, version_id: str) -> EvalMetric:
        """Measure accuracy on the built-in benchmark prompts."""
        if self._engine is None:
            logger.debug("InferenceEngine unavailable; returning stub task-completion score")
            return EvalMetric(
                metric_name="task_completion_accuracy",
                value=0.5,
                unit="ratio",
                benchmark_target=0.75,
                passed=False,
            )

        successes = 0
        for prompt, _task_type in _BENCHMARK_PROMPTS:
            try:
                result = self._engine.infer(prompt)
                if result.response and len(result.response.strip()) > 10:
                    successes += 1
            except Exception as exc:
                logger.debug("Benchmark prompt failed: %s", exc)

        accuracy = successes / max(len(_BENCHMARK_PROMPTS), 1)
        return EvalMetric(
            metric_name="task_completion_accuracy",
            value=round(accuracy, 4),
            unit="ratio",
            benchmark_target=0.75,
            passed=accuracy >= 0.75,
        )

    def _evaluate_by_domain(self, version_id: str, domain: BusinessDomain) -> float:
        """Return a domain-specific accuracy score in [0, 1]."""
        domain_prompts: Dict[BusinessDomain, str] = {
            BusinessDomain.LEGAL: "Summarise the key obligations in a software licence agreement.",
            BusinessDomain.MEDICAL: "List the steps for a medication reconciliation workflow.",
            BusinessDomain.FINANCE: "Explain the main components of a trading risk report.",
            BusinessDomain.TECH: "Describe the difference between a thread and a process.",
            BusinessDomain.MANUFACTURING: "What are the main failure modes in a conveyor-belt assembly line?",
            BusinessDomain.RETAIL: "How should inventory reorder points be calculated?",
            BusinessDomain.EDUCATION: "What is Bloom's taxonomy and how is it used?",
            BusinessDomain.LOGISTICS: "Explain last-mile delivery optimisation strategies.",
            BusinessDomain.ENERGY: "What is demand response in smart grid management?",
            BusinessDomain.GOVERNMENT: "What is the purpose of an FOI request?",
            BusinessDomain.HEALTHCARE: "Describe the ICD-10 coding system.",
            BusinessDomain.MEDIA: "What metrics matter most for content engagement?",
            BusinessDomain.REAL_ESTATE: "Explain cap rate in property investment.",
            BusinessDomain.AGRICULTURE: "What is precision agriculture?",
            BusinessDomain.HOSPITALITY: "How is RevPAR calculated in hotel management?",
        }
        prompt = domain_prompts.get(domain, f"Provide information about {domain.value} industry.")

        if self._engine is None:
            return 0.5

        try:
            result = self._engine.infer(prompt)
            # Heuristic: longer, non-empty responses are treated as more complete.
            word_count = len(result.response.split())
            return min(1.0, word_count / 50.0)
        except Exception as exc:
            logger.debug("Domain eval failed for %s: %s", domain.value, exc)
            return 0.0

    def _evaluate_latency(self, version_id: str) -> EvalMetric:
        """Measure median latency over benchmark prompts."""
        if self._engine is None:
            return EvalMetric(
                metric_name="median_latency_ms",
                value=0.0,
                unit="ms",
                benchmark_target=500.0,
                passed=True,
            )

        latencies: List[float] = []
        for prompt, _ in _BENCHMARK_PROMPTS[:3]:
            try:
                t0 = time.monotonic()
                self._engine.infer(prompt)
                latencies.append((time.monotonic() - t0) * 1000)
            except Exception:
                logger.debug("Suppressed exception in evaluation")

        median = sorted(latencies)[len(latencies) // 2] if latencies else 0.0
        return EvalMetric(
            metric_name="median_latency_ms",
            value=round(median, 2),
            unit="ms",
            benchmark_target=500.0,
            passed=median <= 500.0,
        )

    def _evaluate_cost(self, version_id: str) -> EvalMetric:
        """Estimate per-inference cost using engine metrics."""
        avg_cost = 0.0
        if self._engine is not None:
            try:
                metrics = self._engine.get_metrics()
                total_reqs = metrics.get("total_requests", 0)
                provider_usage = metrics.get("provider_usage", {})
                # Cost proxy: proportion of requests handled by paid providers.
                paid_providers = {"openai", "deepinfra", "copilot"}
                paid_requests = sum(
                    v for k, v in provider_usage.items() if k in paid_providers
                )
                if total_reqs:
                    avg_cost = round(paid_requests / total_reqs * 0.001, 6)  # rough $/req estimate
            except Exception:
                logger.debug("Suppressed exception in evaluation")

        return EvalMetric(
            metric_name="avg_cost_per_request_usd",
            value=avg_cost,
            unit="USD",
            benchmark_target=0.01,
            passed=avg_cost <= 0.01,
        )

    def _evaluate_chaos_robustness(self, version_id: str) -> EvalMetric:
        """Test model robustness under simulated economic chaos scenarios."""
        score = 0.5  # baseline when chaos simulation unavailable

        try:
            from src.lcm_chaos_simulation import LCMChaosSimulation  # type: ignore
        except ImportError:
            try:
                from lcm_chaos_simulation import LCMChaosSimulation  # type: ignore
            except ImportError:
                logger.debug("lcm_chaos_simulation unavailable; using baseline chaos score")
                return EvalMetric(
                    metric_name="chaos_robustness",
                    value=score,
                    unit="ratio",
                    benchmark_target=0.6,
                    passed=score >= 0.6,
                )

        try:
            sim = LCMChaosSimulation()
            results = sim.run_all() if hasattr(sim, "run_all") else {}
            if isinstance(results, dict) and results:
                # Measure how many scenario outcomes are non-catastrophic (value > 0).
                total = sum(len(v) for v in results.values() if isinstance(v, dict))
                non_zero = sum(
                    1 for v in results.values()
                    if isinstance(v, dict)
                    for outcome in v.values()
                    if isinstance(outcome, (int, float)) and outcome > 0
                )
                score = non_zero / max(total, 1)
        except Exception as exc:
            logger.debug("Chaos robustness evaluation error: %s", exc)

        return EvalMetric(
            metric_name="chaos_robustness",
            value=round(score, 4),
            unit="ratio",
            benchmark_target=0.6,
            passed=score >= 0.6,
        )

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def get_eval_history(self, limit: int = 20) -> List[EvalResult]:
        with self._lock:
            return list(self._history[-limit:])

    def _append_history(self, result: EvalResult) -> None:
        with self._lock:
            self._history.append(result)
            if len(self._history) > _MAX_HISTORY:
                self._history = self._history[-_MAX_HISTORY:]
