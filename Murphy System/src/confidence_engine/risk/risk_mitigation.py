"""
Risk Mitigation Recommendation System
Provides intelligent mitigation strategies and recommendations.
"""

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from src.confidence_engine.risk.risk_database import MitigationStrategy, RiskCategory, RiskPattern, RiskSeverity

logger = logging.getLogger(__name__)


class MitigationPriority(str, Enum):
    """Priority levels for mitigation."""
    IMMEDIATE = "immediate"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    OPTIONAL = "optional"


class MitigationApproach(str, Enum):
    """Approaches to risk mitigation."""
    AVOID = "avoid"  # Eliminate the risk
    REDUCE = "reduce"  # Reduce likelihood or impact
    TRANSFER = "transfer"  # Transfer risk to third party
    ACCEPT = "accept"  # Accept the risk
    MONITOR = "monitor"  # Monitor and respond


class MitigationRecommendation(BaseModel):
    """A specific mitigation recommendation."""
    id: str
    risk_pattern_id: str
    strategy: MitigationStrategy
    priority: MitigationPriority
    approach: MitigationApproach
    estimated_risk_reduction: float = Field(ge=0.0, le=1.0)
    cost_benefit_ratio: float
    implementation_complexity: str  # "low", "medium", "high"
    prerequisites_met: bool = True
    reasoning: str
    alternatives: List[str] = Field(default_factory=list)


class MitigationPlan(BaseModel):
    """Complete mitigation plan for identified risks."""
    plan_id: str
    risk_patterns: List[str]  # Risk pattern IDs
    recommendations: List[MitigationRecommendation]
    total_estimated_cost: float
    total_estimated_time_hours: float
    expected_risk_reduction: float = Field(ge=0.0, le=1.0)
    priority_order: List[str]  # Recommendation IDs in priority order
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MitigationStrategySelector:
    """
    Selects appropriate mitigation strategies for risks.
    """

    def select_strategies(
        self,
        pattern: RiskPattern,
        context: Optional[Dict[str, Any]] = None
    ) -> List[MitigationStrategy]:
        """
        Select appropriate mitigation strategies for a risk pattern.

        Args:
            pattern: Risk pattern to mitigate
            context: Optional context (budget, time constraints, etc.)

        Returns:
            List of suitable mitigation strategies
        """
        context = context or {}

        # Get all strategies for this pattern
        available_strategies = pattern.mitigation_strategies

        if not available_strategies:
            # Generate default strategies if none exist
            available_strategies = self._generate_default_strategies(pattern)

        # Filter based on context
        suitable_strategies = self._filter_by_context(
            available_strategies,
            context
        )

        # Sort by effectiveness and cost
        suitable_strategies.sort(
            key=lambda s: (s.effectiveness, -s.cost if s.cost else 0),
            reverse=True
        )

        return suitable_strategies

    def _generate_default_strategies(
        self,
        pattern: RiskPattern
    ) -> List[MitigationStrategy]:
        """Generate default mitigation strategies based on risk category."""
        strategies = []

        if pattern.category == RiskCategory.TECHNICAL:
            strategies.extend([
                MitigationStrategy(
                    id=f"mit_{pattern.id}_1",
                    name="Implement Error Handling",
                    description="Add comprehensive error handling and recovery mechanisms",
                    effectiveness=0.7,
                    cost=500,
                    implementation_time_hours=8,
                    steps=[
                        "Identify error scenarios",
                        "Implement try-catch blocks",
                        "Add logging",
                        "Test error paths"
                    ]
                ),
                MitigationStrategy(
                    id=f"mit_{pattern.id}_2",
                    name="Add Monitoring",
                    description="Implement monitoring and alerting for early detection",
                    effectiveness=0.6,
                    cost=300,
                    implementation_time_hours=4,
                    steps=[
                        "Set up monitoring tools",
                        "Define metrics",
                        "Configure alerts",
                        "Test alerting"
                    ]
                )
            ])

        elif pattern.category == RiskCategory.SECURITY:
            strategies.extend([
                MitigationStrategy(
                    id=f"mit_{pattern.id}_1",
                    name="Implement Access Controls",
                    description="Add authentication and authorization mechanisms",
                    effectiveness=0.9,
                    cost=1000,
                    implementation_time_hours=16,
                    steps=[
                        "Design access control model",
                        "Implement authentication",
                        "Add authorization checks",
                        "Audit access logs"
                    ]
                ),
                MitigationStrategy(
                    id=f"mit_{pattern.id}_2",
                    name="Enable Encryption",
                    description="Encrypt sensitive data at rest and in transit",
                    effectiveness=0.85,
                    cost=800,
                    implementation_time_hours=12,
                    steps=[
                        "Identify sensitive data",
                        "Choose encryption method",
                        "Implement encryption",
                        "Test and verify"
                    ]
                )
            ])

        elif pattern.category == RiskCategory.RESOURCE:
            strategies.extend([
                MitigationStrategy(
                    id=f"mit_{pattern.id}_1",
                    name="Implement Resource Limits",
                    description="Set and enforce resource usage limits",
                    effectiveness=0.8,
                    cost=200,
                    implementation_time_hours=4,
                    steps=[
                        "Analyze resource usage",
                        "Define limits",
                        "Implement enforcement",
                        "Monitor usage"
                    ]
                ),
                MitigationStrategy(
                    id=f"mit_{pattern.id}_2",
                    name="Add Auto-Scaling",
                    description="Implement automatic resource scaling",
                    effectiveness=0.75,
                    cost=1500,
                    implementation_time_hours=20,
                    steps=[
                        "Set up scaling infrastructure",
                        "Define scaling rules",
                        "Test scaling behavior",
                        "Monitor performance"
                    ]
                )
            ])

        else:
            # Generic strategies
            strategies.append(
                MitigationStrategy(
                    id=f"mit_{pattern.id}_1",
                    name="Implement Safeguards",
                    description="Add general safeguards and validation",
                    effectiveness=0.6,
                    cost=400,
                    implementation_time_hours=8,
                    steps=[
                        "Identify risk points",
                        "Design safeguards",
                        "Implement controls",
                        "Test effectiveness"
                    ]
                )
            )

        return strategies

    def _filter_by_context(
        self,
        strategies: List[MitigationStrategy],
        context: Dict[str, Any]
    ) -> List[MitigationStrategy]:
        """Filter strategies based on context constraints."""
        filtered = strategies

        # Budget constraint
        max_budget = context.get("max_budget")
        if max_budget:
            filtered = [
                s for s in filtered
                if not s.cost or s.cost <= max_budget
            ]

        # Time constraint
        max_time = context.get("max_time_hours")
        if max_time:
            filtered = [
                s for s in filtered
                if not s.implementation_time_hours or s.implementation_time_hours <= max_time
            ]

        # Minimum effectiveness
        min_effectiveness = context.get("min_effectiveness", 0.5)
        filtered = [
            s for s in filtered
            if s.effectiveness >= min_effectiveness
        ]

        return filtered


class MitigationRecommender:
    """
    Generates mitigation recommendations with priorities and reasoning.
    """

    def __init__(self, strategy_selector: MitigationStrategySelector):
        self.strategy_selector = strategy_selector

    def generate_recommendations(
        self,
        pattern: RiskPattern,
        context: Optional[Dict[str, Any]] = None
    ) -> List[MitigationRecommendation]:
        """
        Generate mitigation recommendations for a risk pattern.

        Args:
            pattern: Risk pattern to mitigate
            context: Optional context

        Returns:
            List of mitigation recommendations
        """
        context = context or {}

        # Select appropriate strategies
        strategies = self.strategy_selector.select_strategies(pattern, context)

        recommendations = []

        for strategy in strategies:
            # Determine priority
            priority = self._determine_priority(pattern, strategy)

            # Determine approach
            approach = self._determine_approach(pattern, strategy)

            # Calculate risk reduction
            risk_reduction = self._calculate_risk_reduction(pattern, strategy)

            # Calculate cost-benefit ratio
            cost_benefit = self._calculate_cost_benefit(strategy, risk_reduction, pattern.risk_score)

            # Determine complexity
            complexity = self._determine_complexity(strategy)

            # Check prerequisites
            prerequisites_met = self._check_prerequisites(strategy, context)

            # Generate reasoning
            reasoning = self._generate_reasoning(pattern, strategy, priority, approach)

            # Find alternatives
            alternatives = self._find_alternatives(strategies, strategy)

            recommendation = MitigationRecommendation(
                id=f"rec_{pattern.id}_{strategy.id}",
                risk_pattern_id=pattern.id,
                strategy=strategy,
                priority=priority,
                approach=approach,
                estimated_risk_reduction=risk_reduction,
                cost_benefit_ratio=cost_benefit,
                implementation_complexity=complexity,
                prerequisites_met=prerequisites_met,
                reasoning=reasoning,
                alternatives=alternatives
            )

            recommendations.append(recommendation)

        # Sort by priority
        priority_order = {
            MitigationPriority.IMMEDIATE: 5,
            MitigationPriority.HIGH: 4,
            MitigationPriority.MEDIUM: 3,
            MitigationPriority.LOW: 2,
            MitigationPriority.OPTIONAL: 1
        }

        recommendations.sort(
            key=lambda r: (
                priority_order.get(r.priority, 0),
                r.estimated_risk_reduction,
                -r.cost_benefit_ratio
            ),
            reverse=True
        )

        return recommendations

    def _determine_priority(
        self,
        pattern: RiskPattern,
        strategy: MitigationStrategy
    ) -> MitigationPriority:
        """Determine priority for a mitigation strategy."""
        # Critical severity = immediate priority
        if pattern.severity == RiskSeverity.CRITICAL:
            return MitigationPriority.IMMEDIATE

        # High risk score = high priority
        if pattern.risk_score >= 7.0:
            return MitigationPriority.HIGH

        # Medium risk score = medium priority
        if pattern.risk_score >= 4.0:
            return MitigationPriority.MEDIUM

        # Low risk score but high effectiveness = medium priority
        if strategy.effectiveness >= 0.8:
            return MitigationPriority.MEDIUM

        # Low risk score = low priority
        if pattern.risk_score >= 2.0:
            return MitigationPriority.LOW

        return MitigationPriority.OPTIONAL

    def _determine_approach(
        self,
        pattern: RiskPattern,
        strategy: MitigationStrategy
    ) -> MitigationApproach:
        """Determine mitigation approach."""
        # High effectiveness suggests reduction
        if strategy.effectiveness >= 0.9:
            return MitigationApproach.AVOID

        if strategy.effectiveness >= 0.7:
            return MitigationApproach.REDUCE

        # Low effectiveness suggests monitoring
        if strategy.effectiveness < 0.5:
            return MitigationApproach.MONITOR

        # Default to reduce
        return MitigationApproach.REDUCE

    def _calculate_risk_reduction(
        self,
        pattern: RiskPattern,
        strategy: MitigationStrategy
    ) -> float:
        """Calculate expected risk reduction."""
        # Risk reduction = current risk × strategy effectiveness
        current_risk = pattern.risk_score / 10.0
        reduction = current_risk * strategy.effectiveness
        return min(reduction, 1.0)

    def _calculate_cost_benefit(
        self,
        strategy: MitigationStrategy,
        risk_reduction: float,
        current_risk_score: float
    ) -> float:
        """Calculate cost-benefit ratio."""
        if not strategy.cost or strategy.cost == 0:
            return float('inf')  # Infinite benefit if no cost

        # Benefit = risk reduction × risk score
        benefit = risk_reduction * current_risk_score * 1000  # Scale to dollars

        return benefit / strategy.cost

    def _determine_complexity(self, strategy: MitigationStrategy) -> str:
        """Determine implementation complexity."""
        if not strategy.implementation_time_hours:
            return "medium"

        if strategy.implementation_time_hours <= 4:
            return "low"
        elif strategy.implementation_time_hours <= 16:
            return "medium"
        else:
            return "high"

    def _check_prerequisites(
        self,
        strategy: MitigationStrategy,
        context: Dict[str, Any]
    ) -> bool:
        """Check if prerequisites are met."""
        if not strategy.prerequisites:
            return True

        available_resources = context.get("available_resources", [])

        for prereq in strategy.prerequisites:
            if prereq not in available_resources:
                return False

        return True

    def _generate_reasoning(
        self,
        pattern: RiskPattern,
        strategy: MitigationStrategy,
        priority: MitigationPriority,
        approach: MitigationApproach
    ) -> str:
        """Generate reasoning for the recommendation."""
        parts = []

        # Risk context
        parts.append(
            f"Risk '{pattern.name}' has {pattern.severity.value} severity "
            f"with risk score of {pattern.risk_score:.1f}/10."
        )

        # Strategy effectiveness
        parts.append(
            f"Strategy '{strategy.name}' has {strategy.effectiveness:.0%} effectiveness "
            f"and can reduce risk by approximately {strategy.effectiveness * pattern.risk_score:.1f} points."
        )

        # Priority reasoning
        if priority == MitigationPriority.IMMEDIATE:
            parts.append("Immediate action required due to critical severity.")
        elif priority == MitigationPriority.HIGH:
            parts.append("High priority due to significant risk score.")

        # Approach reasoning
        if approach == MitigationApproach.AVOID:
            parts.append("Recommended approach: Eliminate the risk entirely.")
        elif approach == MitigationApproach.REDUCE:
            parts.append("Recommended approach: Reduce likelihood or impact.")

        return " ".join(parts)

    def _find_alternatives(
        self,
        all_strategies: List[MitigationStrategy],
        current_strategy: MitigationStrategy
    ) -> List[str]:
        """Find alternative strategies."""
        alternatives = []

        for strategy in all_strategies:
            if strategy.id != current_strategy.id:
                # Similar effectiveness
                if abs(strategy.effectiveness - current_strategy.effectiveness) < 0.2:
                    alternatives.append(strategy.name)

        return alternatives[:3]  # Return top 3 alternatives


class MitigationPlanGenerator:
    """
    Generates comprehensive mitigation plans for multiple risks.
    """

    def __init__(self, recommender: MitigationRecommender):
        self.recommender = recommender

    def generate_plan(
        self,
        patterns: List[RiskPattern],
        context: Optional[Dict[str, Any]] = None
    ) -> MitigationPlan:
        """
        Generate a comprehensive mitigation plan.

        Args:
            patterns: List of risk patterns to mitigate
            context: Optional context

        Returns:
            Complete mitigation plan
        """
        context = context or {}

        # Generate recommendations for each pattern
        all_recommendations = []
        for pattern in patterns:
            recommendations = self.recommender.generate_recommendations(pattern, context)
            all_recommendations.extend(recommendations)

        # Calculate totals
        total_cost = sum(
            r.strategy.cost for r in all_recommendations
            if r.strategy.cost
        )

        total_time = sum(
            r.strategy.implementation_time_hours for r in all_recommendations
            if r.strategy.implementation_time_hours
        )

        # Calculate expected risk reduction
        expected_reduction = sum(
            r.estimated_risk_reduction for r in all_recommendations
        ) / (len(all_recommendations) or 1) if all_recommendations else 0.0

        # Determine priority order
        priority_order = [r.id for r in all_recommendations]

        plan = MitigationPlan(
            plan_id=f"plan_{datetime.now(timezone.utc).timestamp()}",
            risk_patterns=[p.id for p in patterns],
            recommendations=all_recommendations,
            total_estimated_cost=total_cost,
            total_estimated_time_hours=total_time,
            expected_risk_reduction=expected_reduction,
            priority_order=priority_order
        )

        return plan

    def optimize_plan(
        self,
        plan: MitigationPlan,
        constraints: Dict[str, Any]
    ) -> MitigationPlan:
        """
        Optimize mitigation plan based on constraints.

        Args:
            plan: Original mitigation plan
            constraints: Budget, time, or other constraints

        Returns:
            Optimized mitigation plan
        """
        max_budget = constraints.get("max_budget")
        max_time = constraints.get("max_time_hours")

        # Filter recommendations
        optimized_recommendations = plan.recommendations

        if max_budget:
            # Select recommendations within budget
            optimized_recommendations = self._select_within_budget(
                optimized_recommendations,
                max_budget
            )

        if max_time:
            # Select recommendations within time constraint
            optimized_recommendations = self._select_within_time(
                optimized_recommendations,
                max_time
            )

        # Recalculate totals
        total_cost = sum(
            r.strategy.cost for r in optimized_recommendations
            if r.strategy.cost
        )

        total_time = sum(
            r.strategy.implementation_time_hours for r in optimized_recommendations
            if r.strategy.implementation_time_hours
        )

        expected_reduction = sum(
            r.estimated_risk_reduction for r in optimized_recommendations
        ) / (len(optimized_recommendations) or 1) if optimized_recommendations else 0.0

        return MitigationPlan(
            plan_id=f"optimized_{plan.plan_id}",
            risk_patterns=plan.risk_patterns,
            recommendations=optimized_recommendations,
            total_estimated_cost=total_cost,
            total_estimated_time_hours=total_time,
            expected_risk_reduction=expected_reduction,
            priority_order=[r.id for r in optimized_recommendations]
        )

    def _select_within_budget(
        self,
        recommendations: List[MitigationRecommendation],
        max_budget: float
    ) -> List[MitigationRecommendation]:
        """Select recommendations within budget using greedy algorithm."""
        # Sort by cost-benefit ratio
        sorted_recs = sorted(
            recommendations,
            key=lambda r: r.cost_benefit_ratio,
            reverse=True
        )

        selected = []
        current_cost = 0

        for rec in sorted_recs:
            rec_cost = rec.strategy.cost or 0
            if current_cost + rec_cost <= max_budget:
                selected.append(rec)
                current_cost += rec_cost

        return selected

    def _select_within_time(
        self,
        recommendations: List[MitigationRecommendation],
        max_time: float
    ) -> List[MitigationRecommendation]:
        """Select recommendations within time constraint."""
        # Sort by priority and risk reduction
        sorted_recs = sorted(
            recommendations,
            key=lambda r: (r.priority.value, r.estimated_risk_reduction),
            reverse=True
        )

        selected = []
        current_time = 0

        for rec in sorted_recs:
            rec_time = rec.strategy.implementation_time_hours or 0
            if current_time + rec_time <= max_time:
                selected.append(rec)
                current_time += rec_time

        return selected


class RiskMitigationSystem:
    """
    Complete risk mitigation recommendation system.
    """

    def __init__(self):
        self.strategy_selector = MitigationStrategySelector()
        self.recommender = MitigationRecommender(self.strategy_selector)
        self.plan_generator = MitigationPlanGenerator(self.recommender)

    def get_recommendations(
        self,
        pattern: RiskPattern,
        context: Optional[Dict[str, Any]] = None
    ) -> List[MitigationRecommendation]:
        """Get mitigation recommendations for a risk pattern."""
        return self.recommender.generate_recommendations(pattern, context)

    def generate_plan(
        self,
        patterns: List[RiskPattern],
        context: Optional[Dict[str, Any]] = None
    ) -> MitigationPlan:
        """Generate mitigation plan for multiple risks."""
        return self.plan_generator.generate_plan(patterns, context)

    def optimize_plan(
        self,
        plan: MitigationPlan,
        constraints: Dict[str, Any]
    ) -> MitigationPlan:
        """Optimize mitigation plan based on constraints."""
        return self.plan_generator.optimize_plan(plan, constraints)
