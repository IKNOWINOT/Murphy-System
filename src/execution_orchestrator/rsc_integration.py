"""
RSC Integration for Execution Orchestrator

Adds endpoints and enforcement for Recursive Stability Controller integration.
"""

import logging
from datetime import datetime

from flask import jsonify, request

logger = logging.getLogger(__name__)

# Global control signal from RSC
_current_control_signal = {
    'mode': 'normal',
    'allow_agent_spawn': True,
    'allow_gate_synthesis': True,
    'allow_planning': True,
    'allow_execution': True,
    'require_verification': True,
    'require_deterministic': False,
    'max_authority': 'medium',
    'timestamp': 0,
    'cycle_id': 0
}


def add_rsc_endpoints(app, executor, executions):
    """
    Add RSC integration endpoints to Flask app.

    Args:
        app: Flask application
        executor: Executor instance
        executions: Executions dict
    """

    @app.route('/telemetry', methods=['GET'])
    def get_system_telemetry():
        """Get system-wide telemetry for Recursive Stability Controller"""
        # Get all packets by status
        executing_packets = 0
        queued_packets = 0
        failed_packets = 0
        planning_packets = 0

        # Count by authority level
        authority_levels = {'none': 0, 'low': 0, 'medium': 0, 'high': 0, 'full': 0}

        for execution_state in executions.values():
            status = execution_state.status.value if hasattr(execution_state.status, 'value') else str(execution_state.status)

            if status == 'executing':
                executing_packets += 1
            elif status == 'queued':
                queued_packets += 1
            elif status == 'failed':
                failed_packets += 1
            elif status == 'planning':
                planning_packets += 1

            # Count authority (if available)
            if hasattr(execution_state, 'authority_level'):
                auth = execution_state.authority_level
                if auth in authority_levels:
                    authority_levels[auth] += 1

        # Active agents = packets in planning or executing with authority > none
        active_agents = executing_packets + planning_packets

        return jsonify({
            'active_agents': active_agents,
            'executing_packets': executing_packets,
            'queued_packets': queued_packets,
            'failed_packets': failed_packets,
            'planning_packets': planning_packets,
            'authority_levels': authority_levels,
            'total_packets': len(executions)
        })


    @app.route('/control-signal', methods=['POST'])
    def receive_control_signal():
        """Receive control signal from Recursive Stability Controller"""
        global _current_control_signal

        data = request.json
        _current_control_signal = data

        logger.info(f"[RSC] Control signal received: mode={data.get('mode')}, "
              f"spawn={data.get('allow_agent_spawn')}, "
              f"gates={data.get('allow_gate_synthesis')}")

        return jsonify({
            'status': 'received',
            'control_signal': _current_control_signal
        })


    @app.route('/control-signal', methods=['GET'])
    def get_control_signal():
        """Get current control signal"""
        return jsonify(_current_control_signal)


def check_control_signal(operation: str) -> tuple:
    """
    Check if operation is allowed by current control signal.

    Args:
        operation: Operation type ('spawn', 'gate', 'planning', 'execution')

    Returns:
        (allowed, reason)
    """
    signal = _current_control_signal

    if operation == 'spawn' and not signal['allow_agent_spawn']:
        return False, f"Agent spawn blocked by RSC (mode: {signal['mode']})"

    if operation == 'gate' and not signal['allow_gate_synthesis']:
        return False, f"Gate synthesis blocked by RSC (mode: {signal['mode']})"

    if operation == 'planning' and not signal['allow_planning']:
        return False, f"Planning blocked by RSC (mode: {signal['mode']})"

    if operation == 'execution' and not signal['allow_execution']:
        return False, f"Execution blocked by RSC (mode: {signal['mode']})"

    return True, "Allowed"


def get_current_control_signal():
    """Get current control signal"""
    return _current_control_signal
