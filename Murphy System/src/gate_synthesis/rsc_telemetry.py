"""
RSC Telemetry for Gate Synthesis Engine

Provides telemetry endpoint for Recursive Stability Controller integration.
"""

import logging

from flask import jsonify

logger = logging.getLogger(__name__)


def add_telemetry_endpoint(app, gate_lifecycle_manager):
    """
    Add telemetry endpoint to Gate Synthesis Engine.

    Args:
        app: Flask application
        gate_lifecycle_manager: Gate lifecycle manager instance
    """

    @app.route('/telemetry', methods=['GET'])
    def get_telemetry():
        """Get system telemetry for Recursive Stability Controller"""
        # Get all gates
        all_gates = gate_lifecycle_manager.get_all_gates()

        # Count active gates (currently restricting state transitions)
        active_gates = len([g for g in all_gates if g.status == 'active'])

        # Count by type
        gates_by_type = {}
        for gate in all_gates:
            gate_type = gate.gate_type
            gates_by_type[gate_type] = gates_by_type.get(gate_type, 0) + 1

        # Check if any gates are blocking execution
        blocking_execution = any(
            g.status == 'active' and g.gate_type in ['safety', 'authority', 'verification']
            for g in all_gates
        )

        # Get last triggered gate
        triggered_gates = [g for g in all_gates if hasattr(g, 'last_triggered') and g.last_triggered]
        last_triggered = None
        if triggered_gates:
            last_triggered = max(triggered_gates, key=lambda g: g.last_triggered).last_triggered

        return jsonify({
            'active_gates': active_gates,
            'total_gates': len(all_gates),
            'gates_by_type': gates_by_type,
            'blocking_execution': blocking_execution,
            'last_triggered': last_triggered.isoformat() if last_triggered else None
        })
