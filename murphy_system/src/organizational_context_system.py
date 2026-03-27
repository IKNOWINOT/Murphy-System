"""
Organizational Context System
Handles organizational pressures, incentives, and cultural factors
"""

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class OrganizationalPressure(Enum):
    """Types of organizational pressure"""
    NONE = "none"
    DEADLINE = "deadline"  # Time pressure
    BUDGET = "budget"  # Cost pressure
    COMPETITION = "competition"  # Market pressure
    REGULATION = "regulation"  # Compliance pressure
    REPUTATION = "reputation"  # Brand/image pressure
    POLITICAL = "political"  # Internal politics
    INNOVATION = "innovation"  # Innovation pressure
    EFFICIENCY = "efficiency"  # Efficiency pressure


class IncentiveStructure(Enum):
    """Types of incentive structures"""
    QUALITY_FOCUSED = "quality"  # Rewards quality
    SPEED_FOCUSED = "speed"  # Rewards speed
    COST_FOCUSED = "cost"  # Rewards cost reduction
    INNOVATION_FOCUSED = "innovation"  # Rewards innovation
    BALANCED = "balanced"  # Balanced incentives
    MISALIGNED = "misaligned"  # Incentives conflict with goals


class CultureType(Enum):
    """Organizational culture types"""
    SAFETY_FIRST = "safety_first"  # Safety is paramount
    MOVE_FAST = "move_fast"  # Move fast, break things
    CONSENSUS = "consensus"  # Consensus-driven
    HIERARCHICAL = "hierarchical"  # Top-down
    INNOVATIVE = "innovative"  # Innovation-focused
    RISK_AVERSE = "risk_averse"  # Risk-averse
    DATA_DRIVEN = "data_driven"  # Data-driven decisions
    BALANCED = "balanced"  # Balanced approach


@dataclass
class OrganizationalContext:
    """Complete organizational context"""
    pressures: List[OrganizationalPressure]
    incentives: IncentiveStructure
    culture: CultureType
    risk_tolerance: float  # 0-1, higher = more risk tolerant
    decision_authority: str  # Who makes decisions
    accountability_structure: str  # Who is accountable
    time_horizon: str  # Short-term vs long-term
    resource_constraints: Dict[str, Any]
    political_factors: List[str]
    historical_failures: List[str]  # Learn from past
    success_metrics: List[str]


class OrganizationalContextAnalyzer:
    """
    Analyzes organizational context to adjust MFGC behavior

    Key insight: Same technical solution may be right or wrong
    depending on organizational context
    """

    def __init__(self):
        self.context_history = []
        self.pressure_weights = self._initialize_pressure_weights()

    def _initialize_pressure_weights(self) -> Dict[OrganizationalPressure, float]:
        """Initialize how much each pressure increases Murphy risk"""
        return {
            OrganizationalPressure.NONE: 0.0,
            OrganizationalPressure.DEADLINE: 0.3,  # High risk
            OrganizationalPressure.BUDGET: 0.25,
            OrganizationalPressure.COMPETITION: 0.2,
            OrganizationalPressure.REGULATION: 0.15,  # Can be good
            OrganizationalPressure.REPUTATION: 0.2,
            OrganizationalPressure.POLITICAL: 0.35,  # Very high risk
            OrganizationalPressure.INNOVATION: 0.1,  # Moderate risk
            OrganizationalPressure.EFFICIENCY: 0.15
        }

    def analyze_context(
        self,
        task: str,
        stated_context: Dict[str, Any]
    ) -> OrganizationalContext:
        """
        Analyze organizational context from task and stated context

        Returns complete organizational context
        """
        # Extract pressures
        pressures = self._detect_pressures(task, stated_context)

        # Detect incentive structure
        incentives = self._detect_incentives(stated_context)

        # Detect culture
        culture = self._detect_culture(stated_context)

        # Assess risk tolerance
        risk_tolerance = self._assess_risk_tolerance(pressures, culture)

        # Build complete context
        context = OrganizationalContext(
            pressures=pressures,
            incentives=incentives,
            culture=culture,
            risk_tolerance=risk_tolerance,
            decision_authority=stated_context.get('decision_authority', 'team'),
            accountability_structure=stated_context.get('accountability', 'shared'),
            time_horizon=stated_context.get('time_horizon', 'medium'),
            resource_constraints=stated_context.get('constraints', {}),
            political_factors=stated_context.get('political_factors', []),
            historical_failures=stated_context.get('past_failures', []),
            success_metrics=stated_context.get('metrics', ['quality', 'time', 'cost'])
        )

        # Store in history
        self.context_history.append({
            'timestamp': time.time(),
            'context': context,
            'task': task
        })

        return context

    def _detect_pressures(
        self,
        task: str,
        context: Dict[str, Any]
    ) -> List[OrganizationalPressure]:
        """Detect organizational pressures from task and context"""
        pressures = []
        task_lower = task.lower()
        context_str = str(context).lower()

        # Deadline pressure
        if any(word in task_lower for word in ['urgent', 'asap', 'deadline', 'quickly', 'fast']):
            pressures.append(OrganizationalPressure.DEADLINE)

        # Budget pressure
        if any(word in task_lower for word in ['cheap', 'budget', 'cost', 'affordable']):
            pressures.append(OrganizationalPressure.BUDGET)

        # Competition pressure
        if any(word in task_lower for word in ['competitor', 'market', 'competitive']):
            pressures.append(OrganizationalPressure.COMPETITION)

        # Regulation pressure
        if any(word in task_lower for word in ['compliance', 'regulation', 'legal', 'audit']):
            pressures.append(OrganizationalPressure.REGULATION)

        # Reputation pressure
        if any(word in task_lower for word in ['reputation', 'brand', 'image', 'public']):
            pressures.append(OrganizationalPressure.REPUTATION)

        # Political pressure
        if any(word in context_str for word in ['political', 'stakeholder', 'executive']):
            pressures.append(OrganizationalPressure.POLITICAL)

        # Innovation pressure
        if any(word in task_lower for word in ['innovative', 'novel', 'breakthrough']):
            pressures.append(OrganizationalPressure.INNOVATION)

        # Efficiency pressure
        if any(word in task_lower for word in ['efficient', 'optimize', 'streamline']):
            pressures.append(OrganizationalPressure.EFFICIENCY)

        # Default to NONE if no pressures detected
        if not pressures:
            pressures.append(OrganizationalPressure.NONE)

        return pressures

    def _detect_incentives(self, context: Dict[str, Any]) -> IncentiveStructure:
        """Detect incentive structure"""
        incentive_hints = context.get('incentives', '')

        if 'quality' in str(incentive_hints).lower():
            return IncentiveStructure.QUALITY_FOCUSED
        elif 'speed' in str(incentive_hints).lower() or 'fast' in str(incentive_hints).lower():
            return IncentiveStructure.SPEED_FOCUSED
        elif 'cost' in str(incentive_hints).lower() or 'budget' in str(incentive_hints).lower():
            return IncentiveStructure.COST_FOCUSED
        elif 'innovation' in str(incentive_hints).lower():
            return IncentiveStructure.INNOVATION_FOCUSED
        else:
            return IncentiveStructure.BALANCED

    def _detect_culture(self, context: Dict[str, Any]) -> CultureType:
        """Detect organizational culture"""
        culture_hints = context.get('culture', '')

        if 'safety' in str(culture_hints).lower():
            return CultureType.SAFETY_FIRST
        elif 'move fast' in str(culture_hints).lower():
            return CultureType.MOVE_FAST
        elif 'consensus' in str(culture_hints).lower():
            return CultureType.CONSENSUS
        elif 'hierarchical' in str(culture_hints).lower():
            return CultureType.HIERARCHICAL
        elif 'innovative' in str(culture_hints).lower():
            return CultureType.INNOVATIVE
        elif 'risk averse' in str(culture_hints).lower():
            return CultureType.RISK_AVERSE
        elif 'data' in str(culture_hints).lower():
            return CultureType.DATA_DRIVEN
        else:
            return CultureType.BALANCED

    def _assess_risk_tolerance(
        self,
        pressures: List[OrganizationalPressure],
        culture: CultureType
    ) -> float:
        """Assess organizational risk tolerance"""
        # Base risk tolerance from culture
        culture_tolerance = {
            CultureType.SAFETY_FIRST: 0.2,
            CultureType.MOVE_FAST: 0.8,
            CultureType.CONSENSUS: 0.4,
            CultureType.HIERARCHICAL: 0.3,
            CultureType.INNOVATIVE: 0.7,
            CultureType.RISK_AVERSE: 0.1,
            CultureType.DATA_DRIVEN: 0.5,
            CultureType.BALANCED: 0.5
        }

        base_tolerance = culture_tolerance.get(culture, 0.5)

        # Adjust based on pressures
        pressure_adjustment = 0.0
        for pressure in pressures:
            if pressure in [OrganizationalPressure.DEADLINE, OrganizationalPressure.COMPETITION]:
                pressure_adjustment += 0.1  # Pressure increases risk-taking
            elif pressure == OrganizationalPressure.REGULATION:
                pressure_adjustment -= 0.1  # Regulation decreases risk-taking

        return max(0.0, min(1.0, base_tolerance + pressure_adjustment))

    def compute_murphy_multiplier(self, context: OrganizationalContext) -> float:
        """
        Compute Murphy risk multiplier based on organizational context

        Key insight: Organizational pressure INCREASES Murphy risk,
        it does NOT increase authority
        """
        multiplier = 1.0

        # Add pressure contributions
        for pressure in context.pressures:
            multiplier += self.pressure_weights.get(pressure, 0.0)

        # Adjust for incentive misalignment
        if context.incentives == IncentiveStructure.MISALIGNED:
            multiplier += 0.4  # Misaligned incentives are very risky
        elif context.incentives == IncentiveStructure.SPEED_FOCUSED:
            multiplier += 0.2  # Speed incentives increase risk

        # Adjust for culture
        if context.culture == CultureType.MOVE_FAST:
            multiplier += 0.2
        elif context.culture == CultureType.SAFETY_FIRST:
            multiplier -= 0.1  # Safety culture reduces risk

        # Adjust for political factors
        multiplier += len(context.political_factors) * 0.1

        return max(1.0, multiplier)  # Never less than 1.0

    def suggest_gates_for_context(
        self,
        context: OrganizationalContext
    ) -> List[Dict[str, Any]]:
        """Suggest safety gates based on organizational context"""
        gates = []

        # Gates for deadline pressure
        if OrganizationalPressure.DEADLINE in context.pressures:
            gates.append({
                'name': 'Deadline Reality Check',
                'check': 'Verify timeline is achievable',
                'rationale': 'Deadline pressure often leads to unrealistic estimates',
                'severity': 0.7
            })
            gates.append({
                'name': 'Quality Threshold',
                'check': 'Ensure minimum quality standards met',
                'rationale': 'Speed pressure can compromise quality',
                'severity': 0.8
            })

        # Gates for budget pressure
        if OrganizationalPressure.BUDGET in context.pressures:
            gates.append({
                'name': 'Hidden Cost Analysis',
                'check': 'Identify all costs including technical debt',
                'rationale': 'Budget pressure hides long-term costs',
                'severity': 0.6
            })

        # Gates for political pressure
        if OrganizationalPressure.POLITICAL in context.pressures:
            gates.append({
                'name': 'Objective Criteria',
                'check': 'Decisions based on objective criteria, not politics',
                'rationale': 'Political pressure can override technical judgment',
                'severity': 0.9
            })

        # Gates for misaligned incentives
        if context.incentives == IncentiveStructure.MISALIGNED:
            gates.append({
                'name': 'Incentive Alignment Check',
                'check': 'Verify incentives align with goals',
                'rationale': 'Misaligned incentives cause perverse outcomes',
                'severity': 0.9
            })

        # Gates for move-fast culture
        if context.culture == CultureType.MOVE_FAST:
            gates.append({
                'name': 'Break-Things Boundary',
                'check': 'Define what can and cannot be broken',
                'rationale': 'Move fast culture needs clear boundaries',
                'severity': 0.7
            })

        # Gates for historical failures
        for failure in context.historical_failures:
            gates.append({
                'name': f'Prevent Repeat: {failure}',
                'check': f'Verify we are not repeating {failure}',
                'rationale': 'Learn from past failures',
                'severity': 0.8
            })

        return gates

    def adjust_confidence_for_context(
        self,
        base_confidence: float,
        context: OrganizationalContext
    ) -> float:
        """
        Adjust confidence based on organizational context

        Key insight: Organizational pressure DECREASES confidence,
        not increases it
        """
        adjusted = base_confidence

        # Pressure decreases confidence
        for pressure in context.pressures:
            if pressure != OrganizationalPressure.NONE:
                adjusted *= 0.95  # Each pressure reduces confidence by 5%

        # Misaligned incentives decrease confidence
        if context.incentives == IncentiveStructure.MISALIGNED:
            adjusted *= 0.8

        # Risk-averse culture increases confidence (more validation)
        if context.culture == CultureType.RISK_AVERSE:
            adjusted *= 1.1
        elif context.culture == CultureType.MOVE_FAST:
            adjusted *= 0.9

        return max(0.0, min(1.0, adjusted))

    def generate_context_report(self, context: OrganizationalContext) -> str:
        """Generate human-readable context report"""
        report = []
        report.append("## Organizational Context Analysis")
        report.append("")

        # Pressures
        report.append("**Detected Pressures:**")
        for pressure in context.pressures:
            weight = self.pressure_weights.get(pressure, 0.0)
            report.append(f"  • {pressure.value}: Murphy risk +{weight:.2f}")
        report.append("")

        # Incentives
        report.append(f"**Incentive Structure:** {context.incentives.value}")
        if context.incentives == IncentiveStructure.MISALIGNED:
            report.append("  ⚠️ WARNING: Misaligned incentives detected")
        report.append("")

        # Culture
        report.append(f"**Organizational Culture:** {context.culture.value}")
        report.append(f"**Risk Tolerance:** {context.risk_tolerance:.2f}")
        report.append("")

        # Murphy multiplier
        multiplier = self.compute_murphy_multiplier(context)
        report.append(f"**Murphy Risk Multiplier:** {multiplier:.2f}x")
        if multiplier > 1.5:
            report.append("  ⚠️ HIGH RISK: Organizational factors significantly increase Murphy risk")
        report.append("")

        # Suggested gates
        gates = self.suggest_gates_for_context(context)
        if gates:
            report.append("**Recommended Safety Gates:**")
            for gate in gates:
                report.append(f"  • {gate['name']} (severity: {gate['severity']:.1f})")
                report.append(f"    Rationale: {gate['rationale']}")

        return "\n".join(report)
