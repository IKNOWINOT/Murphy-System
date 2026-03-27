"""
Rubix Evidence Adapter for Murphy System Runtime

Deterministic evidence lane for pre-action verification, providing:
- Confidence interval checks on sample data
- Simplified two-sample hypothesis testing (z-test approximation)
- Bayesian posterior update verification
- Monte Carlo simulation with configurable success functions
- Simple OLS linear-regression forecasting
- Evidence battery composition with aggregated verdicts
- Thread-safe history tracking and compliance-ready artifacts
"""

import logging
import math
import random
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


class EvidenceVerdict(str, Enum):
    """Outcome classification for a single evidence check."""
    PASS = "pass"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"


class EvidenceType(str, Enum):
    """Category of deterministic evidence check."""
    CONFIDENCE_INTERVAL = "confidence_interval"
    HYPOTHESIS_TEST = "hypothesis_test"
    BAYESIAN_UPDATE = "bayesian_update"
    MONTE_CARLO = "monte_carlo"
    FORECAST = "forecast"


@dataclass
class EvidenceArtifact:
    """Immutable record of a single evidence check result."""
    artifact_id: str
    evidence_type: EvidenceType
    verdict: EvidenceVerdict
    score: float
    details: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class EvidenceCheckResult:
    """Aggregated result of running an evidence battery."""
    check_id: str
    artifacts: List[EvidenceArtifact] = field(default_factory=list)
    overall_verdict: EvidenceVerdict = EvidenceVerdict.INCONCLUSIVE
    pass_count: int = 0
    fail_count: int = 0
    inconclusive_count: int = 0


class RubixEvidenceAdapter:
    """Deterministic evidence lane for high-risk action verification.

    Runs statistical and probabilistic checks, producing compliance-ready
    artifacts that can be wired into governance and HITL gates.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._history: List[EvidenceArtifact] = []
        self._check_count: int = 0

    # ------------------------------------------------------------------
    # Individual evidence checks
    # ------------------------------------------------------------------

    def check_confidence_interval(
        self,
        values: List[float],
        confidence_level: float = 0.95,
        threshold: float = 0.5,
    ) -> EvidenceArtifact:
        """Compute mean/CI and pass if *threshold* lies within the interval."""
        n = len(values)
        if n < 2:
            artifact = self._make_artifact(
                EvidenceType.CONFIDENCE_INTERVAL,
                EvidenceVerdict.INCONCLUSIVE,
                0.0,
                {"reason": "insufficient_data", "n": n},
            )
            self._record(artifact)
            return artifact

        mean = sum(values) / n
        std = math.sqrt(sum((x - mean) ** 2 for x in values) / (n - 1))

        z = _z_for_confidence(confidence_level)
        margin = z * std / math.sqrt(n)
        ci_lower = mean - margin
        ci_upper = mean + margin

        if ci_lower <= threshold <= ci_upper:
            verdict = EvidenceVerdict.PASS
        else:
            verdict = EvidenceVerdict.FAIL

        artifact = self._make_artifact(
            EvidenceType.CONFIDENCE_INTERVAL,
            verdict,
            mean,
            {
                "mean": mean,
                "std": std,
                "n": n,
                "confidence_level": confidence_level,
                "z": z,
                "ci_lower": ci_lower,
                "ci_upper": ci_upper,
                "threshold": threshold,
            },
        )
        self._record(artifact)
        return artifact

    def check_hypothesis(
        self,
        sample_a: List[float],
        sample_b: List[float],
        significance: float = 0.05,
    ) -> EvidenceArtifact:
        """Simplified two-sample z-test; pass if difference is significant."""
        n_a, n_b = len(sample_a), len(sample_b)
        if n_a < 2 or n_b < 2:
            artifact = self._make_artifact(
                EvidenceType.HYPOTHESIS_TEST,
                EvidenceVerdict.INCONCLUSIVE,
                0.0,
                {"reason": "insufficient_data", "n_a": n_a, "n_b": n_b},
            )
            self._record(artifact)
            return artifact

        mean_a = sum(sample_a) / n_a
        mean_b = sum(sample_b) / n_b
        var_a = sum((x - mean_a) ** 2 for x in sample_a) / (n_a - 1)
        var_b = sum((x - mean_b) ** 2 for x in sample_b) / (n_b - 1)

        pooled_se = math.sqrt(var_a / n_a + var_b / n_b)
        if pooled_se == 0:
            artifact = self._make_artifact(
                EvidenceType.HYPOTHESIS_TEST,
                EvidenceVerdict.INCONCLUSIVE,
                0.0,
                {"reason": "zero_variance"},
            )
            self._record(artifact)
            return artifact

        z_stat = (mean_a - mean_b) / pooled_se
        z_critical = _z_for_confidence(1.0 - significance)

        if abs(z_stat) > z_critical:
            verdict = EvidenceVerdict.PASS
        else:
            verdict = EvidenceVerdict.FAIL

        artifact = self._make_artifact(
            EvidenceType.HYPOTHESIS_TEST,
            verdict,
            abs(z_stat),
            {
                "mean_a": mean_a,
                "mean_b": mean_b,
                "var_a": var_a,
                "var_b": var_b,
                "pooled_se": pooled_se,
                "z_stat": z_stat,
                "z_critical": z_critical,
                "significance": significance,
            },
        )
        self._record(artifact)
        return artifact

    def check_bayesian_update(
        self,
        prior: float,
        likelihood: float,
        evidence: float,
    ) -> EvidenceArtifact:
        """Compute posterior via Bayes' rule; pass if posterior > 0.5."""
        if evidence == 0:
            artifact = self._make_artifact(
                EvidenceType.BAYESIAN_UPDATE,
                EvidenceVerdict.INCONCLUSIVE,
                0.0,
                {"reason": "zero_evidence"},
            )
            self._record(artifact)
            return artifact

        posterior = (prior * likelihood) / evidence
        verdict = EvidenceVerdict.PASS if posterior > 0.5 else EvidenceVerdict.FAIL

        artifact = self._make_artifact(
            EvidenceType.BAYESIAN_UPDATE,
            verdict,
            posterior,
            {
                "prior": prior,
                "likelihood": likelihood,
                "evidence": evidence,
                "posterior": posterior,
            },
        )
        self._record(artifact)
        return artifact

    def check_monte_carlo(
        self,
        trials: int,
        success_fn: Optional[Callable[[], bool]] = None,
        threshold: float = 0.5,
    ) -> EvidenceArtifact:
        """Run *trials* simulated trials; pass if success rate >= *threshold*."""
        if trials <= 0:
            artifact = self._make_artifact(
                EvidenceType.MONTE_CARLO,
                EvidenceVerdict.INCONCLUSIVE,
                0.0,
                {"reason": "no_trials"},
            )
            self._record(artifact)
            return artifact

        fn = success_fn if success_fn is not None else lambda: random.random() > 0.5
        successes = sum(1 for _ in range(trials) if fn())
        rate = successes / trials
        verdict = EvidenceVerdict.PASS if rate >= threshold else EvidenceVerdict.FAIL

        artifact = self._make_artifact(
            EvidenceType.MONTE_CARLO,
            verdict,
            rate,
            {
                "trials": trials,
                "successes": successes,
                "rate": rate,
                "threshold": threshold,
            },
        )
        self._record(artifact)
        return artifact

    def check_forecast(
        self,
        values: List[float],
        periods_ahead: int = 1,
    ) -> EvidenceArtifact:
        """Simple OLS forecast on index; pass if trend (slope) is positive."""
        n = len(values)
        if n < 2:
            artifact = self._make_artifact(
                EvidenceType.FORECAST,
                EvidenceVerdict.INCONCLUSIVE,
                0.0,
                {"reason": "insufficient_data", "n": n},
            )
            self._record(artifact)
            return artifact

        x_vals = list(range(n))
        x_mean = sum(x_vals) / n
        y_mean = sum(values) / n

        ss_xy = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_vals, values))
        ss_xx = sum((x - x_mean) ** 2 for x in x_vals)

        if ss_xx == 0:
            artifact = self._make_artifact(
                EvidenceType.FORECAST,
                EvidenceVerdict.INCONCLUSIVE,
                0.0,
                {"reason": "zero_variance_x"},
            )
            self._record(artifact)
            return artifact

        slope = ss_xy / ss_xx
        intercept = y_mean - slope * x_mean
        forecast = slope * (n + periods_ahead) + intercept
        verdict = EvidenceVerdict.PASS if slope > 0 else EvidenceVerdict.FAIL

        artifact = self._make_artifact(
            EvidenceType.FORECAST,
            verdict,
            forecast,
            {
                "slope": slope,
                "intercept": intercept,
                "periods_ahead": periods_ahead,
                "forecast": forecast,
                "n": n,
            },
        )
        self._record(artifact)
        return artifact

    # ------------------------------------------------------------------
    # Battery / composition
    # ------------------------------------------------------------------

    _CHECK_MAP = {
        "confidence_interval": "check_confidence_interval",
        "hypothesis": "check_hypothesis",
        "bayesian_update": "check_bayesian_update",
        "monte_carlo": "check_monte_carlo",
        "forecast": "check_forecast",
    }

    def run_evidence_battery(
        self,
        checks: List[Tuple[str, Dict[str, Any]]],
    ) -> EvidenceCheckResult:
        """Run multiple named checks and aggregate results."""
        result = EvidenceCheckResult(check_id=f"battery-{uuid.uuid4().hex[:8]}")

        for name, kwargs in checks:
            method_name = self._CHECK_MAP.get(name)
            if method_name is None:
                logger.warning("Unknown evidence check: %s", name)
                continue
            method = getattr(self, method_name)
            artifact = method(**kwargs)
            result.artifacts.append(artifact)

            if artifact.verdict == EvidenceVerdict.PASS:
                result.pass_count += 1
            elif artifact.verdict == EvidenceVerdict.FAIL:
                result.fail_count += 1
            else:
                result.inconclusive_count += 1

        if result.fail_count > 0:
            result.overall_verdict = EvidenceVerdict.FAIL
        elif result.pass_count > 0 and result.inconclusive_count == 0:
            result.overall_verdict = EvidenceVerdict.PASS
        else:
            result.overall_verdict = EvidenceVerdict.INCONCLUSIVE

        logger.info(
            "Evidence battery %s: %s (pass=%d fail=%d inconclusive=%d)",
            result.check_id,
            result.overall_verdict.value,
            result.pass_count,
            result.fail_count,
            result.inconclusive_count,
        )
        return result

    # ------------------------------------------------------------------
    # History / status
    # ------------------------------------------------------------------

    def get_history(self, limit: int = 100) -> List[EvidenceArtifact]:
        """Return recent evidence artifacts (most recent first)."""
        with self._lock:
            return list(reversed(self._history[-limit:]))

    def get_status(self) -> Dict[str, Any]:
        """Return current adapter status."""
        with self._lock:
            total = len(self._history)
            passes = sum(1 for a in self._history if a.verdict == EvidenceVerdict.PASS)
            fails = sum(1 for a in self._history if a.verdict == EvidenceVerdict.FAIL)
            inconclusives = sum(
                1 for a in self._history if a.verdict == EvidenceVerdict.INCONCLUSIVE
            )
            check_count = self._check_count

        return {
            "total_checks": check_count,
            "total_artifacts": total,
            "pass_count": passes,
            "fail_count": fails,
            "inconclusive_count": inconclusives,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _make_artifact(
        self,
        evidence_type: EvidenceType,
        verdict: EvidenceVerdict,
        score: float,
        details: Dict[str, Any],
    ) -> EvidenceArtifact:
        with self._lock:
            self._check_count += 1
        return EvidenceArtifact(
            artifact_id=f"ea-{uuid.uuid4().hex[:8]}",
            evidence_type=evidence_type,
            verdict=verdict,
            score=score,
            details=details,
        )

    def _record(self, artifact: EvidenceArtifact) -> None:
        with self._lock:
            capped_append(self._history, artifact)
        logger.debug(
            "Recorded artifact %s: %s %s",
            artifact.artifact_id,
            artifact.evidence_type.value,
            artifact.verdict.value,
        )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _z_for_confidence(confidence: float) -> float:
    """Return approximate z-value for common confidence levels."""
    _table = {
        0.90: 1.645,
        0.95: 1.96,
        0.99: 2.576,
    }
    return _table.get(round(confidence, 2), 1.96)
