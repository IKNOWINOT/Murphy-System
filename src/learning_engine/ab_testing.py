"""
A/B Testing Framework

This module implements A/B testing for shadow agent vs Murphy Gate.
"""

import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


class VariantType(str, Enum):
    """Types of variants in A/B test"""
    SHADOW_AGENT = "shadow_agent"
    MURPHY_GATE = "murphy_gate"
    HYBRID = "hybrid"


@dataclass
class ABTestConfig:
    """Configuration for A/B test"""
    name: str = ""
    description: str = ""

    # Variants
    variants: Dict[VariantType, float] = field(default_factory=dict)  # variant -> traffic %

    # Duration
    start_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_date: Optional[datetime] = None

    # Metrics to track
    primary_metric: str = "accuracy"
    secondary_metrics: List[str] = field(default_factory=list)

    # Sample size
    min_samples_per_variant: int = 1000

    # Statistical significance
    confidence_level: float = 0.95

    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ABTestResult:
    """Result of A/B test"""
    variant: VariantType

    # Outcome
    prediction: Any = None
    actual_outcome: Any = None
    was_correct: bool = False

    # Metrics
    confidence: float = 0.0
    response_time_ms: float = 0.0

    # Context
    task_id: Optional[UUID] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ABTestSummary:
    """Summary of A/B test results"""
    test_name: str = ""

    # Results by variant
    results_by_variant: Dict[VariantType, List[ABTestResult]] = field(default_factory=dict)

    # Metrics
    accuracy_by_variant: Dict[VariantType, float] = field(default_factory=dict)
    avg_confidence_by_variant: Dict[VariantType, float] = field(default_factory=dict)
    avg_response_time_by_variant: Dict[VariantType, float] = field(default_factory=dict)

    # Statistical significance
    is_significant: bool = False
    p_value: float = 1.0
    winner: Optional[VariantType] = None

    # Sample sizes
    samples_by_variant: Dict[VariantType, int] = field(default_factory=dict)

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ABTestFramework:
    """Framework for running A/B tests"""

    def __init__(self, config: ABTestConfig):
        self.config = config
        self.results: List[ABTestResult] = []
        self.is_active = True

    def assign_variant(self, task_id: Optional[UUID] = None) -> VariantType:
        """Assign a variant for this request"""

        if not self.is_active:
            return VariantType.MURPHY_GATE  # Default

        # Check if test has ended
        if self.config.end_date and datetime.now(timezone.utc) > self.config.end_date:
            self.is_active = False
            return VariantType.MURPHY_GATE

        # Random assignment based on traffic split
        rand = random.random()
        cumulative = 0.0

        for variant, traffic_pct in self.config.variants.items():
            cumulative += traffic_pct
            if rand <= cumulative:
                return variant

        # Default fallback
        return VariantType.MURPHY_GATE

    def record_result(self, result: ABTestResult):
        """Record result of A/B test"""

        self.results.append(result)

        logger.debug(
            f"Recorded result: variant={result.variant.value}, "
            f"correct={result.was_correct}, confidence={result.confidence:.2f}"
        )

    def get_summary(self) -> ABTestSummary:
        """Get summary of A/B test results"""

        summary = ABTestSummary(test_name=self.config.name)

        # Group results by variant
        for result in self.results:
            if result.variant not in summary.results_by_variant:
                summary.results_by_variant[result.variant] = []
            summary.results_by_variant[result.variant].append(result)

        # Calculate metrics for each variant
        for variant, results in summary.results_by_variant.items():
            if not results:
                continue

            # Sample size
            summary.samples_by_variant[variant] = len(results)

            # Accuracy
            correct = sum(1 for r in results if r.was_correct)
            summary.accuracy_by_variant[variant] = correct / (len(results) or 1)

            # Average confidence
            avg_confidence = sum(r.confidence for r in results) / (len(results) or 1)
            summary.avg_confidence_by_variant[variant] = avg_confidence

            # Average response time
            avg_time = sum(r.response_time_ms for r in results) / (len(results) or 1)
            summary.avg_response_time_by_variant[variant] = avg_time

        # Check statistical significance
        summary.is_significant, summary.p_value = self._check_significance(summary)

        # Determine winner
        if summary.is_significant:
            summary.winner = max(
                summary.accuracy_by_variant.keys(),
                key=lambda v: summary.accuracy_by_variant[v]
            )

        return summary

    def _check_significance(self, summary: ABTestSummary) -> tuple[bool, float]:
        """Check if results are statistically significant"""

        # Simple chi-square test for significance
        # In production, would use proper statistical tests

        if len(summary.results_by_variant) < 2:
            return False, 1.0

        # Check minimum sample size
        for variant, count in summary.samples_by_variant.items():
            if count < self.config.min_samples_per_variant:
                return False, 1.0

        # Calculate p-value (simplified)
        accuracies = list(summary.accuracy_by_variant.values())
        if len(accuracies) < 2:
            return False, 1.0

        # Simple difference test
        diff = abs(accuracies[0] - accuracies[1])

        # Rough approximation: larger differences are more significant
        if diff > 0.05:  # 5% difference
            p_value = 0.01
        elif diff > 0.03:  # 3% difference
            p_value = 0.05
        else:
            p_value = 0.5

        is_significant = p_value < (1.0 - self.config.confidence_level)

        return is_significant, p_value

    def should_stop_test(self) -> bool:
        """Determine if test should be stopped early"""

        summary = self.get_summary()

        # Stop if statistically significant and minimum samples reached
        if summary.is_significant:
            min_samples = min(summary.samples_by_variant.values())
            if min_samples >= self.config.min_samples_per_variant:
                return True

        # Stop if end date reached
        if self.config.end_date and datetime.now(timezone.utc) > self.config.end_date:
            return True

        return False

    def get_recommendation(self) -> str:
        """Get recommendation based on test results"""

        summary = self.get_summary()

        if not summary.is_significant:
            return "Continue testing - results not yet statistically significant"

        if summary.winner:
            winner_accuracy = summary.accuracy_by_variant[summary.winner]
            return (
                f"Deploy {summary.winner.value} - "
                f"significantly better accuracy ({winner_accuracy:.2%})"
            )

        return "Results inconclusive"


class GradualRollout:
    """Manages gradual rollout of shadow agent"""

    def __init__(self, initial_traffic: float = 0.1):
        self.current_traffic = initial_traffic
        self.rollout_history: List[Dict[str, Any]] = []

    def should_use_shadow_agent(self) -> bool:
        """Determine if shadow agent should be used for this request"""
        return random.random() < self.current_traffic

    def increase_traffic(self, increment: float = 0.1):
        """Increase traffic to shadow agent"""

        old_traffic = self.current_traffic
        self.current_traffic = min(1.0, self.current_traffic + increment)

        self.rollout_history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "old_traffic": old_traffic,
            "new_traffic": self.current_traffic,
            "action": "increase"
        })

        logger.info(
            f"Increased shadow agent traffic: {old_traffic:.1%} -> {self.current_traffic:.1%}"
        )

    def decrease_traffic(self, decrement: float = 0.1):
        """Decrease traffic to shadow agent"""

        old_traffic = self.current_traffic
        self.current_traffic = max(0.0, self.current_traffic - decrement)

        self.rollout_history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "old_traffic": old_traffic,
            "new_traffic": self.current_traffic,
            "action": "decrease"
        })

        logger.info(
            f"Decreased shadow agent traffic: {old_traffic:.1%} -> {self.current_traffic:.1%}"
        )

    def auto_adjust(self, performance_metrics: Dict[str, float]):
        """Automatically adjust traffic based on performance"""

        accuracy = performance_metrics.get("accuracy", 0.0)
        error_rate = performance_metrics.get("error_rate", 0.0)

        # Increase traffic if performing well
        if accuracy > 0.9 and error_rate < 0.05:
            self.increase_traffic(0.1)

        # Decrease traffic if performing poorly
        elif accuracy < 0.7 or error_rate > 0.1:
            self.decrease_traffic(0.1)

    def get_rollout_status(self) -> Dict[str, Any]:
        """Get current rollout status"""

        return {
            "current_traffic": self.current_traffic,
            "rollout_stage": self._get_rollout_stage(),
            "history_length": len(self.rollout_history),
            "latest_change": self.rollout_history[-1] if self.rollout_history else None,
        }

    def _get_rollout_stage(self) -> str:
        """Get current rollout stage"""

        if self.current_traffic == 0.0:
            return "not_started"
        elif self.current_traffic < 0.25:
            return "canary"
        elif self.current_traffic < 0.5:
            return "early_rollout"
        elif self.current_traffic < 0.75:
            return "mid_rollout"
        elif self.current_traffic < 1.0:
            return "late_rollout"
        else:
            return "full_deployment"
