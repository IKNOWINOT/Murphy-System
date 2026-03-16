"""
Adaptive Decision Engine for Murphy System Runtime

This module provides adaptive decision-making capabilities that learn from experience:
- Make decisions based on learning and feedback
- Adapt decision strategies over time
- Optimize for better outcomes
- Balance exploration and exploitation
"""

import logging
import random
import statistics
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class DecisionOutcome:
    """Represents the outcome of a decision"""
    decision_id: str
    decision_type: str
    action: str
    success: bool
    confidence: float
    utility: float  # -1.0 to 1.0, higher is better
    timestamp: datetime
    context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DecisionPolicy:
    """Represents a decision policy"""
    policy_id: str
    policy_name: str
    policy_type: str  # 'deterministic', 'probabilistic', 'adaptive'
    decision_type: str
    actions: List[str]
    action_utilities: Dict[str, float]  # utility of each action
    exploration_rate: float  # 0.0 to 1.0
    total_decisions: int
    total_successes: int
    average_utility: float
    last_updated: datetime


@dataclass
class AdaptiveDecision:
    """Represents an adaptive decision"""
    decision_id: str
    decision_type: str
    selected_action: str
    confidence: float
    utility_estimate: float
    rationale: str
    timestamp: datetime
    policy_used: str


class DecisionHistory:
    """Tracks decision history and outcomes"""

    def __init__(self, max_history_size: int = 10000):
        self.max_history_size = max_history_size
        self.outcomes: List[DecisionOutcome] = []
        self.outcomes_by_type: Dict[str, List[DecisionOutcome]] = defaultdict(list)
        self.outcomes_by_action: Dict[str, List[DecisionOutcome]] = defaultdict(list)
        self.lock = threading.Lock()

    def record_outcome(self, outcome: DecisionOutcome) -> None:
        """Record a decision outcome"""
        with self.lock:
            # Keep only recent history
            if len(self.outcomes) >= self.max_history_size:
                # Remove oldest entries
                oldest = self.outcomes[:100]
                for o in oldest:
                    self.outcomes_by_type[o.decision_type].remove(o)
                    self.outcomes_by_action[o.action].remove(o)
                self.outcomes = self.outcomes[100:]

            self.outcomes.append(outcome)
            self.outcomes_by_type[outcome.decision_type].append(outcome)
            self.outcomes_by_action[outcome.action].append(outcome)

    def get_outcomes_by_type(self, decision_type: str,
                            limit: int = 100) -> List[DecisionOutcome]:
        """Get outcomes for a decision type"""
        with self.lock:
            outcomes = self.outcomes_by_type.get(decision_type, [])
            return outcomes[-limit:]

    def get_outcomes_by_action(self, action: str,
                              limit: int = 100) -> List[DecisionOutcome]:
        """Get outcomes for an action"""
        with self.lock:
            outcomes = self.outcomes_by_action.get(action, [])
            return outcomes[-limit:]

    def get_action_statistics(self, action: str) -> Dict[str, float]:
        """Get statistics for an action"""
        outcomes = self.get_outcomes_by_action(action)

        if not outcomes:
            return {
                'count': 0,
                'success_rate': 0.0,
                'average_utility': 0.0,
                'average_confidence': 0.0
            }

        successes = sum(1 for o in outcomes if o.success)
        utilities = [o.utility for o in outcomes]
        confidences = [o.confidence for o in outcomes]

        return {
            'count': len(outcomes),
            'success_rate': successes / (len(outcomes) or 1),
            'average_utility': statistics.mean(utilities),
            'average_confidence': statistics.mean(confidences)
        }


class PolicyManager:
    """Manages decision policies"""

    def __init__(self):
        self.policies: Dict[str, DecisionPolicy] = {}
        self.lock = threading.Lock()

    def create_policy(self, policy_name: str, decision_type: str,
                     actions: List[str], policy_type: str = 'adaptive',
                     exploration_rate: float = 0.1) -> DecisionPolicy:
        """Create a new decision policy"""
        policy_id = f"{decision_type}_{policy_name}"

        policy = DecisionPolicy(
            policy_id=policy_id,
            policy_name=policy_name,
            policy_type=policy_type,
            decision_type=decision_type,
            actions=actions,
            action_utilities={action: 0.5 for action in actions},
            exploration_rate=exploration_rate,
            total_decisions=0,
            total_successes=0,
            average_utility=0.0,
            last_updated=datetime.now(timezone.utc)
        )

        with self.lock:
            self.policies[policy_id] = policy

        return policy

    def get_policy(self, policy_id: str) -> Optional[DecisionPolicy]:
        """Get a policy by ID"""
        return self.policies.get(policy_id)

    def update_policy(self, policy_id: str, action: str,
                     success: bool, utility: float) -> None:
        """Update policy based on outcome"""
        policy = self.policies.get(policy_id)
        if not policy:
            return

        with self.lock:
            policy.total_decisions += 1
            if success:
                policy.total_successes += 1

            # Update action utility using exponential moving average
            learning_rate = 0.1
            current_utility = policy.action_utilities.get(action, 0.5)
            new_utility = current_utility + learning_rate * (utility - current_utility)
            policy.action_utilities[action] = new_utility

            # Update average utility
            policy.average_utility = sum(policy.action_utilities.values()) / (len(policy.action_utilities) or 1)

            # Decrease exploration rate over time
            policy.exploration_rate = max(0.01, policy.exploration_rate * 0.999)

            policy.last_updated = datetime.now(timezone.utc)

    def select_action(self, policy_id: str,
                     context: Optional[Dict[str, Any]] = None) -> Tuple[str, float]:
        """Select an action based on policy"""
        policy = self.policies.get(policy_id)
        if not policy:
            return "", 0.0

        if policy.policy_type == 'deterministic':
            # Select action with highest utility
            action = max(policy.actions, key=lambda a: policy.action_utilities[a])
            utility = policy.action_utilities[action]
            return action, utility

        elif policy.policy_type == 'probabilistic':
            # Select action based on utility probabilities
            utilities = [policy.action_utilities[a] for a in policy.actions]
            total = sum(utilities)
            probs = [u / total for u in utilities]
            action = random.choices(policy.actions, weights=probs, k=1)[0]
            utility = policy.action_utilities[action]
            return action, utility

        elif policy.policy_type == 'adaptive':
            # Epsilon-greedy: explore sometimes, exploit usually
            if random.random() < policy.exploration_rate:
                # Explore: random action
                action = random.choice(policy.actions)
                utility = policy.action_utilities[action]
                return action, utility
            else:
                # Exploit: best action
                action = max(policy.actions, key=lambda a: policy.action_utilities[a])
                utility = policy.action_utilities[action]
                return action, utility

        return "", 0.0


class AdaptiveDecisionEngine:
    """
    Main adaptive decision engine that makes decisions based on learning

    The adaptive decision engine:
    - Makes decisions based on learned policies
    - Adapts policies based on outcomes
    - Balances exploration and exploitation
    - Provides decision rationale
    """

    def __init__(self, enable_adaptation: bool = True):
        self.enable_adaptation = enable_adaptation
        self.history = DecisionHistory()
        self.policy_manager = PolicyManager()
        self.decision_counter = 0
        self.lock = threading.Lock()

        # Initialize common policies
        self._initialize_default_policies()

    def _initialize_default_policies(self) -> None:
        """Initialize default decision policies"""
        # Task execution policy
        self.policy_manager.create_policy(
            policy_name="task_execution",
            decision_type="task_execution",
            actions=["execute_immediately", "defer", "delegate", "skip"],
            policy_type="adaptive",
            exploration_rate=0.15
        )

        # Workflow branching policy
        self.policy_manager.create_policy(
            policy_name="workflow_branch",
            decision_type="workflow_branch",
            actions=["take_branch_a", "take_branch_b", "parallel_execute", "skip_both"],
            policy_type="adaptive",
            exploration_rate=0.1
        )

        # Risk mitigation policy
        self.policy_manager.create_policy(
            policy_name="risk_mitigation",
            decision_type="risk_mitigation",
            actions=["accept_risk", "mitigate_risk", "escalate_risk", "avoid_risk"],
            policy_type="adaptive",
            exploration_rate=0.05
        )

        # Resource allocation policy
        self.policy_manager.create_policy(
            policy_name="resource_allocation",
            decision_type="resource_allocation",
            actions=["allocate_high", "allocate_medium", "allocate_low", "defer_allocation"],
            policy_type="adaptive",
            exploration_rate=0.1
        )

    def make_decision(self, decision_type: str,
                     context: Optional[Dict[str, Any]] = None,
                     policy_id: Optional[str] = None) -> AdaptiveDecision:
        """Make an adaptive decision"""
        if not self.enable_adaptation:
            # Default behavior if adaptation disabled
            return AdaptiveDecision(
                decision_id=f"decision_{int(time.time())}",
                decision_type=decision_type,
                selected_action="default",
                confidence=0.5,
                utility_estimate=0.5,
                rationale="Adaptation disabled, using default action",
                timestamp=datetime.now(timezone.utc),
                policy_used="none"
            )

        with self.lock:
            self.decision_counter += 1
            decision_id = f"decision_{self.decision_counter}"

        # Determine policy to use
        if policy_id is None:
            policy_id = f"{decision_type}_{decision_type}"

        policy = self.policy_manager.get_policy(policy_id)

        if not policy:
            # Create default policy for this decision type
            policy = self.policy_manager.create_policy(
                policy_name=decision_type,
                decision_type=decision_type,
                actions=["option_a", "option_b", "option_c"],
                policy_type="adaptive",
                exploration_rate=0.1
            )

        # Select action
        action, utility_estimate = self.policy_manager.select_action(
            policy_id, context
        )

        # Calculate confidence
        if policy.total_decisions > 10:
            confidence = min(0.95, 0.5 + policy.total_successes / policy.total_decisions * 0.45)
        else:
            confidence = 0.5

        # Generate rationale
        rationale = self._generate_rationale(policy, action, utility_estimate, context)

        return AdaptiveDecision(
            decision_id=decision_id,
            decision_type=decision_type,
            selected_action=action,
            confidence=confidence,
            utility_estimate=utility_estimate,
            rationale=rationale,
            timestamp=datetime.now(timezone.utc),
            policy_used=policy_id
        )

    def _generate_rationale(self, policy: DecisionPolicy, action: str,
                           utility_estimate: float,
                           context: Optional[Dict[str, Any]]) -> str:
        """Generate rationale for decision"""
        rationale_parts = []

        # Base rationale
        rationale_parts.append(
            f"Selected action '{action}' based on policy '{policy.policy_name}'"
        )

        # Add utility information
        rationale_parts.append(
            f"Estimated utility: {utility_estimate:.3f} (policy average: {policy.average_utility:.3f})"
        )

        # Add policy statistics
        if policy.total_decisions > 0:
            success_rate = policy.total_successes / policy.total_decisions
            rationale_parts.append(
                f"Policy has {policy.total_decisions} decisions with {success_rate:.1%} success rate"
            )

        # Add exploration information
        if policy.exploration_rate > 0.05:
            rationale_parts.append(
                f"Exploration rate: {policy.exploration_rate:.1%} (discovering new strategies)"
            )

        # Add context if available
        if context:
            rationale_parts.append(f"Context: {len(context)} factors considered")

        return ". ".join(rationale_parts)

    def record_outcome(self, decision: AdaptiveDecision,
                      success: bool, confidence: float,
                      utility: float, context: Optional[Dict[str, Any]] = None) -> None:
        """Record the outcome of a decision"""
        if not self.enable_adaptation:
            return

        # Record outcome in history
        outcome = DecisionOutcome(
            decision_id=decision.decision_id,
            decision_type=decision.decision_type,
            action=decision.selected_action,
            success=success,
            confidence=confidence,
            utility=utility,
            timestamp=datetime.now(timezone.utc),
            context=context or {},
            metadata={}
        )

        self.history.record_outcome(outcome)

        # Update policy
        self.policy_manager.update_policy(
            decision.policy_used,
            decision.selected_action,
            success,
            utility
        )

    def get_decision_statistics(self, decision_type: Optional[str] = None) -> Dict[str, Any]:
        """Get decision statistics"""
        if decision_type:
            outcomes = self.history.get_outcomes_by_type(decision_type)
        else:
            with self.lock:
                outcomes = self.history.outcomes

        if not outcomes:
            return {
                'total_decisions': 0,
                'success_rate': 0.0,
                'average_utility': 0.0,
                'average_confidence': 0.0,
                'by_action': {}
            }

        total = len(outcomes)
        successes = sum(1 for o in outcomes if o.success)
        utilities = [o.utility for o in outcomes]
        confidences = [o.confidence for o in outcomes]

        # Group by action
        by_action = {}
        for outcome in outcomes:
            if outcome.action not in by_action:
                by_action[outcome.action] = {
                    'count': 0,
                    'successes': 0,
                    'utilities': []
                }
            by_action[outcome.action]['count'] += 1
            if outcome.success:
                by_action[outcome.action]['successes'] += 1
            by_action[outcome.action]['utilities'].append(outcome.utility)

        # Calculate per-action statistics
        for action, stats in by_action.items():
            stats['success_rate'] = stats['successes'] / stats['count']
            stats['average_utility'] = statistics.mean(stats['utilities'])
            del stats['successes']
            del stats['utilities']

        return {
            'total_decisions': total,
            'success_rate': successes / total,
            'average_utility': statistics.mean(utilities),
            'average_confidence': statistics.mean(confidences),
            'by_action': by_action
        }

    def get_policy_status(self, policy_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific policy"""
        policy = self.policy_manager.get_policy(policy_id)
        if not policy:
            return None

        return {
            'policy_id': policy.policy_id,
            'policy_name': policy.policy_name,
            'policy_type': policy.policy_type,
            'decision_type': policy.decision_type,
            'actions': policy.actions,
            'action_utilities': policy.action_utilities,
            'exploration_rate': policy.exploration_rate,
            'total_decisions': policy.total_decisions,
            'total_successes': policy.total_successes,
            'average_utility': policy.average_utility,
            'last_updated': policy.last_updated.isoformat()
        }

    def get_all_policies(self) -> List[Dict[str, Any]]:
        """Get status of all policies"""
        return [
            self.get_policy_status(policy_id)
            for policy_id in self.policy_manager.policies.keys()
        ]

    def reset_learning(self) -> None:
        """Reset all learning data"""
        self.history = DecisionHistory()
        self.policy_manager = PolicyManager()
        self.decision_counter = 0
        self._initialize_default_policies()

    def export_decision_data(self) -> Dict[str, Any]:
        """Export decision data for analysis"""
        return {
            'statistics': self.get_decision_statistics(),
            'policies': self.get_all_policies()
        }
