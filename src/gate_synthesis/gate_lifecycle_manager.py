"""
Gate Lifecycle Manager
Manages gate activation, persistence, retirement, and conflict resolution
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

from .models import Gate, GateCategory, GateRegistry, GateState, RetirementCondition

logger = logging.getLogger(__name__)


class GateLifecycleManager:
    """
    Manages complete gate lifecycle:
    - Activation
    - Persistence tracking
    - Retirement
    - Conflict resolution

    Gates are not permanent. Each gate must specify:
    - Activation conditions
    - Persistence duration
    - Retirement conditions
    """

    def __init__(self):
        self.registry = GateRegistry()
        self.activation_log: List[Dict[str, Any]] = []
        self.retirement_log: List[Dict[str, Any]] = []

    def add_gate(self, gate: Gate) -> None:
        """
        Add gate to registry

        Args:
            gate: Gate to add
        """
        self.registry.add_gate(gate)

        capped_append(self.activation_log, {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'action': 'gate_added',
            'gate_id': gate.id,
            'category': gate.category.value,
            'state': gate.state.value
        })

    def activate_gate(self, gate_id: str) -> bool:
        """
        Activate a gate

        Args:
            gate_id: ID of gate to activate

        Returns:
            True if activated successfully
        """
        gate = self.registry.get_gate(gate_id)

        if not gate:
            return False

        if gate.state != GateState.PROPOSED:
            return False

        gate.activate()

        capped_append(self.activation_log, {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'action': 'gate_activated',
            'gate_id': gate.id,
            'category': gate.category.value
        })

        return True

    def activate_all_proposed_gates(self) -> List[str]:
        """
        Activate all proposed gates

        Returns:
            List of activated gate IDs
        """
        activated = []

        for gate in self.registry.gates.values():
            if gate.state == GateState.PROPOSED:
                if self.activate_gate(gate.id):
                    activated.append(gate.id)

        return activated

    def update_retirement_conditions(
        self,
        gate_id: str,
        condition_values: Dict[str, float]
    ) -> bool:
        """
        Update retirement condition values

        Args:
            gate_id: ID of gate
            condition_values: Dict mapping condition types to current values

        Returns:
            True if gate can be retired
        """
        gate = self.registry.get_gate(gate_id)

        if not gate or not gate.is_active():
            return False

        # Update each retirement condition
        for condition in gate.retirement_conditions:
            if condition.condition_type in condition_values:
                current_value = condition_values[condition.condition_type]
                condition.check(current_value)

        # Check if all conditions satisfied
        return gate.check_retirement_conditions()

    def retire_gate(
        self,
        gate_id: str,
        reason: str = ""
    ) -> bool:
        """
        Retire a gate

        Args:
            gate_id: ID of gate to retire
            reason: Reason for retirement

        Returns:
            True if retired successfully
        """
        gate = self.registry.get_gate(gate_id)

        if not gate:
            return False

        if not gate.can_retire():
            return False

        gate.retire(reason)

        capped_append(self.retirement_log, {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'action': 'gate_retired',
            'gate_id': gate.id,
            'category': gate.category.value,
            'reason': reason
        })

        return True

    def check_and_retire_expired_gates(self) -> List[str]:
        """
        Check for expired gates and retire them

        Returns:
            List of retired gate IDs
        """
        expired_ids = self.registry.retire_expired_gates()

        for gate_id in expired_ids:
            capped_append(self.retirement_log, {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'action': 'gate_expired',
                'gate_id': gate_id
            })

        return expired_ids

    def check_all_retirement_conditions(
        self,
        condition_values: Dict[str, Dict[str, float]]
    ) -> List[str]:
        """
        Check retirement conditions for all active gates

        Args:
            condition_values: Dict mapping gate IDs to condition values

        Returns:
            List of retired gate IDs
        """
        retired = []

        for gate_id, values in condition_values.items():
            if self.update_retirement_conditions(gate_id, values):
                if self.retire_gate(gate_id, "Conditions satisfied"):
                    retired.append(gate_id)

        return retired

    def resolve_conflicts(
        self,
        gates: List[Gate]
    ) -> List[Gate]:
        """
        Resolve conflicts between gates

        Conflict resolution rules:
        1. Higher priority gates take precedence
        2. More restrictive gates take precedence
        3. Newer gates replace older gates of same type/target

        Args:
            gates: List of potentially conflicting gates

        Returns:
            List of gates after conflict resolution
        """
        if len(gates) <= 1:
            return gates

        # Group by target
        by_target: Dict[str, List[Gate]] = {}
        for gate in gates:
            if gate.target not in by_target:
                by_target[gate.target] = []
            by_target[gate.target].append(gate)

        resolved = []

        for target, target_gates in by_target.items():
            if len(target_gates) == 1:
                resolved.extend(target_gates)
                continue

            # Sort by priority (descending) then by created_at (descending)
            sorted_gates = sorted(
                target_gates,
                key=lambda g: (g.priority, g.created_at),
                reverse=True
            )

            # Keep highest priority gate
            resolved.append(sorted_gates[0])

            # Log conflicts
            for gate in sorted_gates[1:]:
                capped_append(self.activation_log, {
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'action': 'gate_conflict_resolved',
                    'gate_id': gate.id,
                    'superseded_by': sorted_gates[0].id,
                    'reason': 'Lower priority'
                })

        return resolved

    def get_active_gates_for_target(
        self,
        target: str
    ) -> List[Gate]:
        """
        Get all active gates for a specific target

        Args:
            target: Target identifier

        Returns:
            List of active gates
        """
        target_gates = self.registry.get_gates_by_target(target)
        return [gate for gate in target_gates if gate.is_active()]

    def get_gates_by_category(
        self,
        category: GateCategory
    ) -> List[Gate]:
        """
        Get all gates of a specific category

        Args:
            category: Gate category

        Returns:
            List of gates
        """
        return self.registry.get_gates_by_category(category)

    def get_gate_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about gates

        Returns:
            Statistics dictionary
        """
        all_gates = list(self.registry.gates.values())

        if not all_gates:
            return {
                'total_gates': 0,
                'active_gates': 0,
                'retired_gates': 0,
                'expired_gates': 0,
                'by_category': {},
                'by_state': {},
                'average_priority': 0.0
            }

        # Count by state
        by_state = {}
        for state in GateState:
            count = sum(1 for g in all_gates if g.state == state)
            by_state[state.value] = count

        # Count by category
        by_category = {}
        for category in GateCategory:
            count = sum(1 for g in all_gates if g.category == category)
            by_category[category.value] = count

        # Calculate average priority
        avg_priority = sum(g.priority for g in all_gates) / (len(all_gates) or 1)

        return {
            'total_gates': len(all_gates),
            'active_gates': by_state.get(GateState.ACTIVE.value, 0),
            'retired_gates': by_state.get(GateState.RETIRED.value, 0),
            'expired_gates': by_state.get(GateState.EXPIRED.value, 0),
            'by_category': by_category,
            'by_state': by_state,
            'average_priority': avg_priority
        }

    def get_activation_log(
        self,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get activation log

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of log entries
        """
        if limit:
            return self.activation_log[-limit:]
        return self.activation_log.copy()

    def get_retirement_log(
        self,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get retirement log

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of log entries
        """
        if limit:
            return self.retirement_log[-limit:]
        return self.retirement_log.copy()
