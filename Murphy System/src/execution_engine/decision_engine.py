"""
Decision Engine - Autonomous decision making with rules and conditions
"""

import logging
import threading
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DecisionType(Enum):
    """Types of decisions"""
    CONDITIONAL = "conditional"
    RULE_BASED = "rule_based"
    MACHINE_LEARNING = "machine_learning"
    HYBRID = "hybrid"


class Rule:
    """Decision rule"""

    def __init__(
        self,
        rule_id: Optional[str] = None,
        name: str = "",
        description: str = "",
        conditions: Optional[List[Dict]] = None,
        actions: Optional[List[Dict]] = None,
        priority: int = 0,
        confidence: float = 1.0
    ):
        self.rule_id = rule_id or str(uuid.uuid4())
        self.name = name
        self.description = description
        self.conditions = conditions or []
        self.actions = actions or []
        self.priority = priority
        self.confidence = confidence
        self.created_at = datetime.now(timezone.utc)
        self.usage_count = 0
        self.last_used_at: Optional[datetime] = None

    def evaluate_conditions(self, context: Dict) -> bool:
        """Evaluate if conditions are met"""
        for condition in self.conditions:
            if not self._evaluate_condition(condition, context):
                return False
        return True

    def _evaluate_condition(self, condition: Dict, context: Dict) -> bool:
        """Evaluate a single condition"""
        condition_type = condition.get('type')

        if condition_type == 'equals':
            variable = condition.get('variable')
            expected_value = condition.get('value')
            actual_value = context.get(variable)
            return actual_value == expected_value

        elif condition_type == 'not_equals':
            variable = condition.get('variable')
            expected_value = condition.get('value')
            actual_value = context.get(variable)
            return actual_value != expected_value

        elif condition_type == 'greater_than':
            variable = condition.get('variable')
            threshold = condition.get('value')
            actual_value = context.get(variable)
            return actual_value is not None and actual_value > threshold

        elif condition_type == 'less_than':
            variable = condition.get('variable')
            threshold = condition.get('value')
            actual_value = context.get(variable)
            return actual_value is not None and actual_value < threshold

        elif condition_type == 'contains':
            variable = condition.get('variable')
            expected_value = condition.get('value')
            actual_value = str(context.get(variable, ''))
            return expected_value in actual_value

        elif condition_type == 'custom':
            custom_function = condition.get('function')
            if custom_function and callable(custom_function):
                return custom_function(context)

        return True

    def execute_actions(self, context: Dict) -> List[Dict]:
        """Execute rule actions"""
        results = []
        for action in self.actions:
            result = self._execute_action(action, context)
            results.append(result)
        return results

    def _execute_action(self, action: Dict, context: Dict) -> Dict:
        """Execute a single action"""
        action_type = action.get('type')

        if action_type == 'set_variable':
            variable = action.get('variable')
            value = action.get('value')
            return {
                'type': 'set_variable',
                'variable': variable,
                'value': value,
                'success': True
            }

        elif action_type == 'execute_function':
            function = action.get('function')
            parameters = action.get('parameters', {})
            if function and callable(function):
                result = function(**parameters)
                return {
                    'type': 'execute_function',
                    'result': result,
                    'success': True
                }

        elif action_type == 'send_notification':
            message = action.get('message')
            return {
                'type': 'send_notification',
                'message': message,
                'success': True
            }

        elif action_type == 'custom':
            custom_function = action.get('function')
            if custom_function and callable(custom_function):
                return custom_function(context)

        return {'type': action_type, 'success': False}

    def to_dict(self) -> Dict:
        """Convert rule to dictionary"""
        return {
            'rule_id': self.rule_id,
            'name': self.name,
            'description': self.description,
            'conditions': self.conditions,
            'actions': self.actions,
            'priority': self.priority,
            'confidence': self.confidence,
            'usage_count': self.usage_count,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None
        }


class Decision:
    """Decision result"""

    def __init__(
        self,
        decision_id: Optional[str] = None,
        decision_type: DecisionType = DecisionType.RULE_BASED,
        rule_applied: Optional[Rule] = None,
        conditions_met: List[Dict] = None,
        actions_taken: List[Dict] = None,
        confidence: float = 1.0,
        context: Optional[Dict] = None
    ):
        self.decision_id = decision_id or str(uuid.uuid4())
        self.decision_type = decision_type
        self.rule_applied = rule_applied
        self.conditions_met = conditions_met or []
        self.actions_taken = actions_taken or []
        self.confidence = confidence
        self.context = context or {}
        self.timestamp = datetime.now(timezone.utc)
        self.success = True
        self.error: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert decision to dictionary"""
        return {
            'decision_id': self.decision_id,
            'decision_type': self.decision_type.value,
            'rule_id': self.rule_applied.rule_id if self.rule_applied else None,
            'rule_name': self.rule_applied.name if self.rule_applied else None,
            'conditions_met': self.conditions_met,
            'actions_taken': self.actions_taken,
            'confidence': self.confidence,
            'context': self.context,
            'timestamp': self.timestamp.isoformat(),
            'success': self.success,
            'error': self.error
        }


class DecisionEngine:
    """Make autonomous decisions based on rules and conditions"""

    def __init__(self):
        self.rules: Dict[str, Rule] = {}
        self.decision_history: List[Decision] = []
        self._lock = threading.Lock()

    def add_rule(self, rule: Rule) -> str:
        """Add a rule to the engine"""
        with self._lock:
            self.rules[rule.rule_id] = rule
            logger.info(f"Rule added: {rule.rule_id} - {rule.name}")
            return rule.rule_id

    def remove_rule(self, rule_id: str) -> bool:
        """Remove a rule from the engine"""
        with self._lock:
            if rule_id in self.rules:
                del self.rules[rule_id]
                logger.info(f"Rule removed: {rule_id}")
                return True
            return False

    def get_rule(self, rule_id: str) -> Optional[Rule]:
        """Get a rule by ID"""
        return self.rules.get(rule_id)

    def get_all_rules(self) -> List[Rule]:
        """Get all rules"""
        return list(self.rules.values())

    def make_decision(
        self,
        context: Dict,
        rule_id: Optional[str] = None,
        decision_type: DecisionType = DecisionType.RULE_BASED
    ) -> Decision:
        """Make a decision based on rules and context"""
        try:
            if rule_id:
                # Use specific rule
                rule = self.get_rule(rule_id)
                if not rule:
                    raise ValueError(f"Rule not found: {rule_id}")

                return self._apply_rule(rule, context)

            else:
                # Find matching rule
                matching_rule = self._find_matching_rule(context)
                if not matching_rule:
                    # No rule matched, return default decision
                    return Decision(
                        decision_type=decision_type,
                        confidence=0.0,
                        context=context
                    )

                return self._apply_rule(matching_rule, context)

        except Exception as exc:
            logger.error(f"Error making decision: {exc}")
            decision = Decision(
                decision_type=decision_type,
                confidence=0.0,
                context=context
            )
            decision.success = False
            decision.error = str(exc)
            return decision

    def _find_matching_rule(self, context: Dict) -> Optional[Rule]:
        """Find the highest priority matching rule"""
        matching_rules = []

        for rule in self.rules.values():
            if rule.evaluate_conditions(context):
                matching_rules.append(rule)

        if not matching_rules:
            return None

        # Sort by priority (higher priority first)
        matching_rules.sort(key=lambda r: r.priority, reverse=True)

        # Return highest priority rule
        return matching_rules[0]

    def _apply_rule(self, rule: Rule, context: Dict) -> Decision:
        """Apply a rule to make a decision"""
        # Check conditions
        conditions_met = []
        for condition in rule.conditions:
            if rule._evaluate_condition(condition, context):
                conditions_met.append(condition)

        # Execute actions
        actions_taken = rule.execute_actions(context)

        # Update rule usage stats
        with self._lock:
            rule.usage_count += 1
            rule.last_used_at = datetime.now(timezone.utc)

        # Create decision
        decision = Decision(
            decision_type=DecisionType.RULE_BASED,
            rule_applied=rule,
            conditions_met=conditions_met,
            actions_taken=actions_taken,
            confidence=rule.confidence,
            context=context
        )

        # Add to history
        with self._lock:
            self.decision_history.append(decision)

        logger.info(f"Decision made: {decision.decision_id} using rule: {rule.rule_id}")

        return decision

    def evaluate_condition(self, condition: Dict, context: Dict) -> bool:
        """Evaluate a condition in isolation"""
        rule = Rule(conditions=[condition])
        return rule.evaluate_conditions(context)

    def apply_rule(self, rule_id: str, context: Dict) -> Decision:
        """Apply a specific rule"""
        rule = self.get_rule(rule_id)
        if not rule:
            raise ValueError(f"Rule not found: {rule_id}")

        return self._apply_rule(rule, context)

    def get_decision_history(self, limit: int = 100) -> List[Dict]:
        """Get decision history"""
        with self._lock:
            history = self.decision_history[-limit:]
            return [decision.to_dict() for decision in history]

    def get_decision(self, decision_id: str) -> Optional[Dict]:
        """Get a specific decision"""
        with self._lock:
            for decision in self.decision_history:
                if decision.decision_id == decision_id:
                    return decision.to_dict()
            return None

    def get_statistics(self) -> Dict:
        """Get decision engine statistics"""
        with self._lock:
            total_decisions = len(self.decision_history)
            successful_decisions = len([d for d in self.decision_history if d.success])

            rule_usage = {}
            for decision in self.decision_history:
                if decision.rule_applied:
                    rule_id = decision.rule_applied.rule_id
                    rule_usage[rule_id] = rule_usage.get(rule_id, 0) + 1

            return {
                'total_rules': len(self.rules),
                'total_decisions': total_decisions,
                'successful_decisions': successful_decisions,
                'success_rate': successful_decisions / total_decisions if total_decisions > 0 else 0.0,
                'rule_usage': rule_usage
            }

    def clear_history(self) -> None:
        """Clear decision history"""
        with self._lock:
            self.decision_history.clear()
            logger.info("Decision history cleared")


# Convenience functions

def create_rule(
    name: str,
    conditions: Optional[List[Dict]] = None,
    actions: Optional[List[Dict]] = None,
    **kwargs
) -> Rule:
    """Create a rule"""
    return Rule(
        name=name,
        conditions=conditions,
        actions=actions,
        **kwargs
    )


def make_decision(
    engine: DecisionEngine,
    context: Dict,
    rule_id: Optional[str] = None
) -> Dict:
    """Make a decision"""
    decision = engine.make_decision(context, rule_id)
    return decision.to_dict()
