"""
Risk Scoring Algorithms
Advanced algorithms for calculating and updating risk scores.
"""

import logging
import statistics
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

logger = logging.getLogger("confidence_engine.risk.risk_scoring")

from src.confidence_engine.risk.risk_database import (
    RiskCategory,
    RiskIncident,
    RiskLikelihood,
    RiskPattern,
    RiskSeverity,
)


class ScoringMethod(str, Enum):
    """Methods for calculating risk scores."""
    BASIC = "basic"  # Impact × Probability
    WEIGHTED = "weighted"  # Weighted factors
    HISTORICAL = "historical"  # Based on historical data
    DYNAMIC = "dynamic"  # Adjusts based on context
    COMPOSITE = "composite"  # Combines multiple methods


class RiskFactor(BaseModel):
    """A factor that contributes to risk score."""
    name: str
    value: float = Field(ge=0.0, le=1.0)
    weight: float = Field(ge=0.0, le=1.0)
    description: str


class RiskScoreBreakdown(BaseModel):
    """Detailed breakdown of risk score calculation."""
    total_score: float = Field(ge=0.0, le=10.0)
    impact_score: float = Field(ge=0.0, le=10.0)
    probability_score: float = Field(ge=0.0, le=1.0)
    factors: List[RiskFactor] = Field(default_factory=list)
    method_used: ScoringMethod
    confidence: float = Field(ge=0.0, le=1.0)
    calculated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BasicRiskScorer:
    """
    Basic risk scoring using Impact × Probability formula.
    """

    def calculate_score(
        self,
        impact_score: float,
        probability_score: float
    ) -> RiskScoreBreakdown:
        """
        Calculate basic risk score.

        Args:
            impact_score: Impact score (0-10)
            probability_score: Probability score (0-1)

        Returns:
            RiskScoreBreakdown with calculation details
        """
        total_score = impact_score * probability_score

        return RiskScoreBreakdown(
            total_score=total_score,
            impact_score=impact_score,
            probability_score=probability_score,
            method_used=ScoringMethod.BASIC,
            confidence=1.0,
            factors=[
                RiskFactor(
                    name="impact",
                    value=impact_score / 10.0,
                    weight=1.0,
                    description="Direct impact of risk occurrence"
                ),
                RiskFactor(
                    name="probability",
                    value=probability_score,
                    weight=1.0,
                    description="Likelihood of risk occurrence"
                )
            ]
        )


class WeightedRiskScorer:
    """
    Weighted risk scoring considering multiple factors.
    """

    def __init__(self):
        # Default weights for different factors
        self.default_weights = {
            "impact": 0.35,
            "probability": 0.25,
            "detectability": 0.15,
            "controllability": 0.15,
            "velocity": 0.10
        }

    def calculate_score(
        self,
        impact_score: float,
        probability_score: float,
        detectability: float = 0.5,
        controllability: float = 0.5,
        velocity: float = 0.5,
        custom_weights: Optional[Dict[str, float]] = None
    ) -> RiskScoreBreakdown:
        """
        Calculate weighted risk score.

        Args:
            impact_score: Impact score (0-10)
            probability_score: Probability score (0-1)
            detectability: How easily the risk can be detected (0-1)
            controllability: How easily the risk can be controlled (0-1)
            velocity: How quickly the risk can escalate (0-1)
            custom_weights: Optional custom weights for factors

        Returns:
            RiskScoreBreakdown with calculation details
        """
        weights = custom_weights or self.default_weights

        # Normalize impact to 0-1 scale for calculation
        normalized_impact = impact_score / 10.0

        # Calculate weighted score
        factors = [
            RiskFactor(
                name="impact",
                value=normalized_impact,
                weight=weights.get("impact", 0.35),
                description="Severity of consequences if risk occurs"
            ),
            RiskFactor(
                name="probability",
                value=probability_score,
                weight=weights.get("probability", 0.25),
                description="Likelihood of risk occurrence"
            ),
            RiskFactor(
                name="detectability",
                value=1.0 - detectability,  # Lower detectability = higher risk
                weight=weights.get("detectability", 0.15),
                description="Difficulty in detecting the risk early"
            ),
            RiskFactor(
                name="controllability",
                value=1.0 - controllability,  # Lower controllability = higher risk
                weight=weights.get("controllability", 0.15),
                description="Difficulty in controlling the risk"
            ),
            RiskFactor(
                name="velocity",
                value=velocity,
                weight=weights.get("velocity", 0.10),
                description="Speed at which risk can escalate"
            )
        ]

        # Calculate weighted sum
        weighted_sum = sum(f.value * f.weight for f in factors)

        # Scale to 0-10
        total_score = weighted_sum * 10.0

        return RiskScoreBreakdown(
            total_score=total_score,
            impact_score=impact_score,
            probability_score=probability_score,
            factors=factors,
            method_used=ScoringMethod.WEIGHTED,
            confidence=0.9
        )


class HistoricalRiskScorer:
    """
    Risk scoring based on historical incident data.
    """

    def calculate_score(
        self,
        pattern: RiskPattern,
        incidents: List[RiskIncident],
        base_impact: float,
        base_probability: float
    ) -> RiskScoreBreakdown:
        """
        Calculate risk score adjusted by historical data.

        Args:
            pattern: Risk pattern to score
            incidents: Historical incidents for this pattern
            base_impact: Base impact score
            base_probability: Base probability score

        Returns:
            RiskScoreBreakdown with historical adjustments
        """
        if not incidents:
            # No historical data, use base scores
            return BasicRiskScorer().calculate_score(base_impact, base_probability)

        # Calculate historical impact (average of actual impacts)
        historical_impacts = [i.actual_impact for i in incidents]
        avg_historical_impact = statistics.mean(historical_impacts)

        # Calculate historical probability (frequency of occurrence)
        days_span = 365  # Look at last year
        occurrence_rate = len(incidents) / days_span
        historical_probability = min(occurrence_rate * 30, 1.0)  # Monthly probability

        # Blend base and historical scores
        blended_impact = 0.6 * base_impact + 0.4 * avg_historical_impact
        blended_probability = 0.6 * base_probability + 0.4 * historical_probability

        # Calculate trend factor
        trend_factor = self._calculate_trend_factor(incidents)

        # Adjust probability based on trend
        adjusted_probability = blended_probability * trend_factor

        total_score = blended_impact * adjusted_probability

        factors = [
            RiskFactor(
                name="base_impact",
                value=base_impact / 10.0,
                weight=0.6,
                description="Base impact assessment"
            ),
            RiskFactor(
                name="historical_impact",
                value=avg_historical_impact / 10.0,
                weight=0.4,
                description=f"Average impact from {len(incidents)} incidents"
            ),
            RiskFactor(
                name="base_probability",
                value=base_probability,
                weight=0.6,
                description="Base probability assessment"
            ),
            RiskFactor(
                name="historical_frequency",
                value=historical_probability,
                weight=0.4,
                description="Historical occurrence frequency"
            ),
            RiskFactor(
                name="trend_adjustment",
                value=trend_factor,
                weight=1.0,
                description="Trend-based adjustment factor"
            )
        ]

        return RiskScoreBreakdown(
            total_score=total_score,
            impact_score=blended_impact,
            probability_score=adjusted_probability,
            factors=factors,
            method_used=ScoringMethod.HISTORICAL,
            confidence=0.85
        )

    def _calculate_trend_factor(self, incidents: List[RiskIncident]) -> float:
        """Calculate trend adjustment factor."""
        if len(incidents) < 2:
            return 1.0

        # Sort by date
        sorted_incidents = sorted(incidents, key=lambda i: i.occurred_at)

        # Compare first half to second half
        mid = len(sorted_incidents) // 2
        first_half = sorted_incidents[:mid]
        second_half = sorted_incidents[mid:]

        if len(second_half) > len(first_half) * 1.5:
            return 1.3  # Increasing trend
        elif len(second_half) < len(first_half) * 0.5:
            return 0.7  # Decreasing trend
        else:
            return 1.0  # Stable


class DynamicRiskScorer:
    """
    Dynamic risk scoring that adjusts based on context.
    """

    def calculate_score(
        self,
        base_impact: float,
        base_probability: float,
        context: Dict[str, Any]
    ) -> RiskScoreBreakdown:
        """
        Calculate risk score with dynamic context adjustments.

        Args:
            base_impact: Base impact score
            base_probability: Base probability score
            context: Context information for adjustments

        Returns:
            RiskScoreBreakdown with context adjustments
        """
        # Extract context factors
        environment = context.get("environment", "production")
        user_role = context.get("user_role", "user")
        time_of_day = context.get("time_of_day", "business_hours")
        system_load = context.get("system_load", 0.5)

        # Calculate adjustment factors
        factors = []

        # Environment factor
        env_factor = 1.0
        if environment == "production":
            env_factor = 1.3
        elif environment == "staging":
            env_factor = 0.8
        elif environment == "development":
            env_factor = 0.5

        factors.append(RiskFactor(
            name="environment",
            value=env_factor,
            weight=0.3,
            description=f"Environment: {environment}"
        ))

        # User role factor
        role_factor = 1.0
        if user_role == "admin":
            role_factor = 1.2
        elif user_role == "power_user":
            role_factor = 1.1

        factors.append(RiskFactor(
            name="user_role",
            value=role_factor,
            weight=0.2,
            description=f"User role: {user_role}"
        ))

        # Time factor
        time_factor = 1.0
        if time_of_day == "off_hours":
            time_factor = 1.2  # Higher risk during off-hours

        factors.append(RiskFactor(
            name="time_of_day",
            value=time_factor,
            weight=0.2,
            description=f"Time: {time_of_day}"
        ))

        # System load factor
        load_factor = 0.8 + (system_load * 0.4)  # 0.8 to 1.2

        factors.append(RiskFactor(
            name="system_load",
            value=load_factor,
            weight=0.3,
            description=f"System load: {system_load:.1%}"
        ))

        # Calculate overall adjustment
        total_adjustment = sum(f.value * f.weight for f in factors)

        # Apply adjustments
        adjusted_impact = base_impact * total_adjustment
        adjusted_probability = base_probability * total_adjustment

        # Ensure within bounds
        adjusted_impact = min(adjusted_impact, 10.0)
        adjusted_probability = min(adjusted_probability, 1.0)

        total_score = adjusted_impact * adjusted_probability

        return RiskScoreBreakdown(
            total_score=total_score,
            impact_score=adjusted_impact,
            probability_score=adjusted_probability,
            factors=factors,
            method_used=ScoringMethod.DYNAMIC,
            confidence=0.8
        )


class CompositeRiskScorer:
    """
    Composite scoring that combines multiple scoring methods.
    """

    def __init__(self):
        self.basic_scorer = BasicRiskScorer()
        self.weighted_scorer = WeightedRiskScorer()
        self.historical_scorer = HistoricalRiskScorer()
        self.dynamic_scorer = DynamicRiskScorer()

    def calculate_score(
        self,
        pattern: RiskPattern,
        incidents: Optional[List[RiskIncident]] = None,
        context: Optional[Dict[str, Any]] = None,
        weights: Optional[Dict[str, float]] = None
    ) -> RiskScoreBreakdown:
        """
        Calculate composite risk score using multiple methods.

        Args:
            pattern: Risk pattern to score
            incidents: Historical incidents
            context: Context information
            weights: Weights for combining methods

        Returns:
            RiskScoreBreakdown with composite calculation
        """
        default_weights = {
            "basic": 0.2,
            "weighted": 0.3,
            "historical": 0.3,
            "dynamic": 0.2
        }
        method_weights = weights or default_weights

        # Calculate scores using different methods
        basic_score = self.basic_scorer.calculate_score(
            pattern.impact_score,
            pattern.probability_score
        )

        weighted_score = self.weighted_scorer.calculate_score(
            pattern.impact_score,
            pattern.probability_score
        )

        # Historical score (if data available)
        if incidents:
            historical_score = self.historical_scorer.calculate_score(
                pattern,
                incidents,
                pattern.impact_score,
                pattern.probability_score
            )
        else:
            historical_score = basic_score
            method_weights["historical"] = 0
            # Redistribute weight
            method_weights["basic"] += 0.15
            method_weights["weighted"] += 0.15

        # Dynamic score (if context available)
        if context:
            dynamic_score = self.dynamic_scorer.calculate_score(
                pattern.impact_score,
                pattern.probability_score,
                context
            )
        else:
            dynamic_score = basic_score
            method_weights["dynamic"] = 0
            # Redistribute weight
            method_weights["basic"] += 0.1
            method_weights["weighted"] += 0.1

        # Combine scores
        composite_total = (
            basic_score.total_score * method_weights["basic"] +
            weighted_score.total_score * method_weights["weighted"] +
            historical_score.total_score * method_weights["historical"] +
            dynamic_score.total_score * method_weights["dynamic"]
        )

        # Combine impacts
        composite_impact = (
            basic_score.impact_score * method_weights["basic"] +
            weighted_score.impact_score * method_weights["weighted"] +
            historical_score.impact_score * method_weights["historical"] +
            dynamic_score.impact_score * method_weights["dynamic"]
        )

        # Combine probabilities
        composite_probability = (
            basic_score.probability_score * method_weights["basic"] +
            weighted_score.probability_score * method_weights["weighted"] +
            historical_score.probability_score * method_weights["historical"] +
            dynamic_score.probability_score * method_weights["dynamic"]
        )

        # Combine all factors
        all_factors = []
        for method_name, score in [
            ("basic", basic_score),
            ("weighted", weighted_score),
            ("historical", historical_score),
            ("dynamic", dynamic_score)
        ]:
            weight = method_weights.get(method_name, 0)
            if weight > 0:
                all_factors.append(RiskFactor(
                    name=f"{method_name}_method",
                    value=score.total_score / 10.0,
                    weight=weight,
                    description=f"Score from {method_name} method"
                ))

        # Calculate confidence (average of method confidences)
        confidences = [
            basic_score.confidence * method_weights["basic"],
            weighted_score.confidence * method_weights["weighted"],
            historical_score.confidence * method_weights["historical"],
            dynamic_score.confidence * method_weights["dynamic"]
        ]
        composite_confidence = sum(confidences)

        return RiskScoreBreakdown(
            total_score=composite_total,
            impact_score=composite_impact,
            probability_score=composite_probability,
            factors=all_factors,
            method_used=ScoringMethod.COMPOSITE,
            confidence=composite_confidence
        )


class RiskScoringSystem:
    """
    Complete risk scoring system.
    Provides unified interface for all scoring methods.
    """

    def __init__(self):
        self.basic_scorer = BasicRiskScorer()
        self.weighted_scorer = WeightedRiskScorer()
        self.historical_scorer = HistoricalRiskScorer()
        self.dynamic_scorer = DynamicRiskScorer()
        self.composite_scorer = CompositeRiskScorer()

    def calculate_score(
        self,
        pattern: RiskPattern,
        method: ScoringMethod = ScoringMethod.COMPOSITE,
        incidents: Optional[List[RiskIncident]] = None,
        context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> RiskScoreBreakdown:
        """
        Calculate risk score using specified method.

        Args:
            pattern: Risk pattern to score
            method: Scoring method to use
            incidents: Historical incidents (for historical/composite methods)
            context: Context information (for dynamic/composite methods)
            **kwargs: Additional method-specific parameters

        Returns:
            RiskScoreBreakdown with calculation details
        """
        if method == ScoringMethod.BASIC:
            return self.basic_scorer.calculate_score(
                pattern.impact_score,
                pattern.probability_score
            )

        elif method == ScoringMethod.WEIGHTED:
            return self.weighted_scorer.calculate_score(
                pattern.impact_score,
                pattern.probability_score,
                **kwargs
            )

        elif method == ScoringMethod.HISTORICAL:
            if not incidents:
                # Fall back to basic if no incidents
                return self.basic_scorer.calculate_score(
                    pattern.impact_score,
                    pattern.probability_score
                )
            return self.historical_scorer.calculate_score(
                pattern,
                incidents,
                pattern.impact_score,
                pattern.probability_score
            )

        elif method == ScoringMethod.DYNAMIC:
            if not context:
                context = {}
            return self.dynamic_scorer.calculate_score(
                pattern.impact_score,
                pattern.probability_score,
                context
            )

        else:  # COMPOSITE
            return self.composite_scorer.calculate_score(
                pattern,
                incidents,
                context,
                kwargs.get("weights")
            )

    def recalculate_pattern_score(
        self,
        pattern: RiskPattern,
        method: ScoringMethod = ScoringMethod.COMPOSITE,
        incidents: Optional[List[RiskIncident]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> float:
        """
        Recalculate and update pattern's risk score.

        Args:
            pattern: Risk pattern to update
            method: Scoring method to use
            incidents: Historical incidents
            context: Context information

        Returns:
            New risk score
        """
        breakdown = self.calculate_score(pattern, method, incidents, context)

        # Update pattern
        pattern.risk_score = breakdown.total_score
        pattern.impact_score = breakdown.impact_score
        pattern.probability_score = breakdown.probability_score
        pattern.updated_at = datetime.now(timezone.utc)

        return breakdown.total_score

    def compare_scoring_methods(
        self,
        pattern: RiskPattern,
        incidents: Optional[List[RiskIncident]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, RiskScoreBreakdown]:
        """
        Compare scores from all methods.

        Args:
            pattern: Risk pattern to score
            incidents: Historical incidents
            context: Context information

        Returns:
            Dictionary mapping method names to score breakdowns
        """
        results = {}

        for method in ScoringMethod:
            try:
                results[method.value] = self.calculate_score(
                    pattern,
                    method,
                    incidents,
                    context
                )
            except Exception as exc:
                logger.info(f"Error calculating {method.value} score: {exc}")
                continue

        return results
