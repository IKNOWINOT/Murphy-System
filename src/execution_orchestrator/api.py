"""
Execution Orchestrator REST API
================================

Flask API server for the Execution Orchestrator service.

Endpoints:
- POST /execute - Execute sealed packet
- GET /execution/{packet_id} - Get execution status
- POST /pause/{packet_id} - Pause execution
- POST /resume/{packet_id} - Resume execution
- POST /abort/{packet_id} - Abort execution
- GET /telemetry/{packet_id} - Get telemetry stream
- GET /risk/{packet_id} - Get runtime risk
- GET /certificate/{packet_id} - Get completion certificate
- GET /interfaces - Get interface status
- POST /interfaces/register - Register interface
- GET /health - Health check
"""

import re
import threading
from datetime import datetime, timezone
from typing import Dict, Optional

from flask import Flask, jsonify, request

from flask_security import configure_secure_app

from .completion import CompletionCertifier
from .executor import StepwiseExecutor
from .models import ExecutionState, ExecutionStatus, InterfaceHealth, StepResult, TelemetryEventType
from .risk_monitor import RuntimeRiskMonitor
from .rollback import RollbackEnforcer
from .telemetry import TelemetryStreamer
from .validator import PreExecutionValidator

# Allowed authority levels for execution packets
_VALID_AUTHORITY_LEVELS = frozenset({
    'none', 'low', 'medium', 'standard', 'high', 'full'
})

# Pattern for safe identifiers (packet_id, interface_id)
_SAFE_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_\-.:]+$')
_MAX_ID_LENGTH = 256


def _validate_identifier(value: str, field_name: str):
    """
    Validate an identifier (packet_id, interface_id, etc.).

    Returns None if valid, or a (response, status_code) tuple if invalid.
    """
    if not value or not _SAFE_ID_PATTERN.match(value):
        return jsonify({'error': f'Invalid or missing {field_name}'}), 400
    if len(value) > _MAX_ID_LENGTH:
        return jsonify({'error': f'{field_name} too long'}), 400
    return None


app = Flask(__name__)
configure_secure_app(app, service_name="execution-orchestrator")

# Initialize components
validator = PreExecutionValidator()
executor = StepwiseExecutor()
telemetry = TelemetryStreamer()
risk_monitor = RuntimeRiskMonitor()
rollback_enforcer = RollbackEnforcer()
completion_certifier = CompletionCertifier()

# Mount Artifact Viewport API for content inspection
import logging

from artifact_viewport import ArtifactViewport
from artifact_viewport_api import mount_viewport_api
from viewport_content_resolver import ViewportContentResolver

logger = logging.getLogger(__name__)

_viewport = ArtifactViewport()
_viewport_resolver = ViewportContentResolver()
mount_viewport_api(app, _viewport, _viewport_resolver.resolve)

# Execution state registry
executions: Dict[str, ExecutionState] = {}
execution_locks: Dict[str, threading.Lock] = {}
execution_owners: Dict[str, str] = {}  # packet_id -> owner identity


def _get_caller_identity() -> str:
    """
    Extract the caller identity from request headers.

    Uses X-Tenant-ID or X-API-Key as the ownership identifier.
    Falls back to client IP for backward compatibility.
    """
    tenant = request.headers.get('X-Tenant-ID', '')
    if tenant:
        return tenant
    api_key = request.headers.get('X-API-Key', '')
    if api_key:
        return api_key
    return request.remote_addr or 'unknown'


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'execution_orchestrator',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'active_executions': len(executions),
        'components': {
            'validator': 'operational',
            'executor': 'operational',
            'telemetry': 'operational',
            'risk_monitor': 'operational',
            'rollback_enforcer': 'operational',
            'completion_certifier': 'operational'
        }
    })


@app.route('/execute', methods=['POST'])
def execute_packet():
    """
    Execute sealed packet

    Request body:
    {
        "packet": {...},
        "authority_level": "standard"
    }
    """
    data = request.json
    if not data or not isinstance(data, dict):
        return jsonify({'error': 'Invalid request body'}), 400

    packet = data.get('packet', {})
    if not isinstance(packet, dict):
        return jsonify({'error': 'Invalid packet format'}), 400

    authority_level = data.get('authority_level', 'standard')
    if authority_level not in _VALID_AUTHORITY_LEVELS:
        return jsonify({
            'error': 'Invalid authority_level',
            'valid_values': sorted(_VALID_AUTHORITY_LEVELS)
        }), 400

    packet_id = packet.get('packet_id', '')
    invalid = _validate_identifier(packet_id, 'packet_id')
    if invalid:
        return invalid

    expected_signature = packet.get('signature', '')

    # Check if already executing
    if packet_id in executions:
        return jsonify({
            'error': 'Packet is already being executed'
        }), 400

    # Validate packet
    all_valid, errors = validator.validate_all(
        packet,
        expected_signature,
        authority_level
    )

    if not all_valid:
        return jsonify({
            'error': 'Validation failed',
            'errors': errors
        }), 400

    # Create execution state
    execution_state = ExecutionState(
        packet_id=packet_id,
        packet_signature=expected_signature,
        status=ExecutionStatus.PENDING,
        current_step=0,
        total_steps=len(packet.get('execution_graph', {}).get('steps', [])),
        start_time=datetime.now(timezone.utc)
    )

    executions[packet_id] = execution_state
    execution_locks[packet_id] = threading.Lock()
    execution_owners[packet_id] = _get_caller_identity()

    # Start execution in background thread
    thread = threading.Thread(
        target=_execute_packet_async,
        args=(packet, execution_state)
    )
    thread.daemon = True
    thread.start()

    return jsonify({
        'packet_id': packet_id,
        'status': 'started',
        'execution_state': execution_state.to_dict()
    })


def _execute_packet_async(packet: Dict, execution_state: ExecutionState):
    """Execute packet asynchronously"""
    packet_id = packet['packet_id']

    try:
        # Initialize monitoring
        base_risk = packet.get('expected_loss', 0.0)
        initial_confidence = packet.get('confidence', 0.8)

        risk_monitor.initialize_monitoring(
            packet_id,
            base_risk,
            initial_confidence
        )

        # Create telemetry stream
        telemetry.create_stream(packet_id)

        # Emit execution start
        telemetry.emit_execution_start(
            packet_id,
            execution_state.total_steps,
            base_risk,
            initial_confidence
        )

        # Update status
        execution_state.status = ExecutionStatus.RUNNING

        # Execute steps
        steps = packet.get('execution_graph', {}).get('steps', [])
        context = {}

        for i, step in enumerate(steps):
            # Check if should pause
            if risk_monitor.should_pause(packet_id):
                execution_state.status = ExecutionStatus.PAUSED
                stop_conditions = risk_monitor.get_stop_conditions(packet_id)

                telemetry.emit_execution_paused(
                    packet_id,
                    f"Safety threshold breached: {len(stop_conditions)} conditions",
                    risk_monitor.get_safety_state(packet_id).current_risk,
                    risk_monitor.get_safety_state(packet_id).current_confidence
                )

                # Execute rollback
                _execute_rollback(packet, execution_state)
                return

            # Emit step start
            telemetry.emit_step_start(
                packet_id,
                step.get('step_id', ''),
                i,
                step.get('type', ''),
                risk_monitor.get_safety_state(packet_id).current_risk,
                risk_monitor.get_safety_state(packet_id).current_confidence
            )

            # Execute step
            step_result = executor.execute_step(step, context)
            execution_state.results.append(step_result)
            execution_state.current_step = i + 1

            # Update context with step output
            if step_result.success and step_result.output:
                output_var = step.get('output_variable')
                if output_var:
                    context[output_var] = step_result.output

            # Update monitoring
            new_confidence = initial_confidence + step_result.confidence_delta
            safety_state = risk_monitor.update_after_step(
                packet_id,
                step_result,
                new_confidence
            )

            # Emit step complete/failed
            if step_result.success:
                telemetry.emit_step_complete(
                    packet_id,
                    step_result,
                    safety_state.current_risk,
                    safety_state.current_confidence
                )
            else:
                telemetry.emit_step_failed(
                    packet_id,
                    step_result,
                    safety_state.current_risk,
                    safety_state.current_confidence
                )

                # Step failed - execute rollback
                execution_state.status = ExecutionStatus.FAILED
                execution_state.error = step_result.error
                _execute_rollback(packet, execution_state)
                return

        # All steps completed successfully
        execution_state.status = ExecutionStatus.COMPLETED
        execution_state.end_time = datetime.now(timezone.utc)

        # Get final metrics
        final_risk = risk_monitor.get_safety_state(packet_id).current_risk
        final_confidence = risk_monitor.get_safety_state(packet_id).current_confidence

        # Generate completion certificate
        artifacts_created = packet.get('artifacts_created', [])
        artifacts_modified = packet.get('artifacts_modified', [])

        certificate = completion_certifier.generate_certificate(
            execution_state,
            final_risk,
            final_confidence,
            artifacts_created,
            artifacts_modified
        )

        # Emit execution complete
        telemetry.emit_execution_complete(
            packet_id,
            execution_state.total_steps,
            sum(1 for r in execution_state.results if r.success),
            final_risk,
            final_confidence
        )

    except Exception as exc:
        logger.debug("Caught exception: %s", exc)
        execution_state.status = ExecutionStatus.FAILED
        execution_state.error = str(exc)
        execution_state.end_time = datetime.now(timezone.utc)

        telemetry.emit_execution_failed(
            packet_id,
            str(exc),
            risk_monitor.get_safety_state(packet_id).current_risk if packet_id in risk_monitor.safety_states else 0.0,
            risk_monitor.get_safety_state(packet_id).current_confidence if packet_id in risk_monitor.safety_states else 0.0
        )


def _execute_rollback(packet: Dict, execution_state: ExecutionState):
    """Execute rollback for failed execution"""
    packet_id = packet['packet_id']

    # Emit rollback start
    telemetry.emit_rollback_start(
        packet_id,
        execution_state.error or "Unknown error",
        risk_monitor.get_safety_state(packet_id).current_risk,
        risk_monitor.get_safety_state(packet_id).current_confidence
    )

    # Execute rollback
    rollback_plan = packet.get('rollback_plan', {})
    success, errors = rollback_enforcer.execute_rollback(
        packet_id,
        execution_state.results,
        rollback_plan
    )

    # Emit rollback complete
    telemetry.emit_rollback_complete(
        packet_id,
        success,
        risk_monitor.get_safety_state(packet_id).current_risk,
        risk_monitor.get_safety_state(packet_id).current_confidence
    )

    if not success:
        execution_state.error = f"Rollback failed: {', '.join(errors)}"


def _check_ownership(packet_id: str):
    """
    Check if the caller owns the execution.

    Admins (X-Role: admin) bypass the ownership check.
    Returns None if authorized, or a (response, status_code) tuple if denied.
    """
    # Admin users may manage any execution
    if request.headers.get('X-Role') == 'admin':
        return None
    caller = _get_caller_identity()
    owner = execution_owners.get(packet_id, '')
    if owner and caller != owner:
        return jsonify({'error': 'Forbidden: you do not own this execution'}), 403
    return None


@app.route('/execution/<packet_id>', methods=['GET'])
def get_execution_status(packet_id: str):
    """Get execution status (only by owner)"""
    if packet_id not in executions:
        return jsonify({'error': 'Execution not found'}), 404

    # ARCH-004: Ownership check — prevent IDOR
    denied = _check_ownership(packet_id)
    if denied:
        return denied

    execution_state = executions[packet_id]

    return jsonify({
        'execution_state': execution_state.to_dict(),
        'safety_state': risk_monitor.get_safety_state(packet_id).to_dict() if packet_id in risk_monitor.safety_states else None,
        'runtime_risk': risk_monitor.get_runtime_risk(packet_id).to_dict() if packet_id in risk_monitor.runtime_risks else None
    })


@app.route('/telemetry/<packet_id>', methods=['GET'])
def get_telemetry(packet_id: str):
    """Get telemetry stream"""
    stream = telemetry.get_stream(packet_id)

    if not stream:
        return jsonify({'error': 'Telemetry stream not found'}), 404

    return jsonify({
        'stream': stream.to_dict(),
        'metrics': telemetry.get_aggregated_metrics(packet_id)
    })


@app.route('/telemetry', methods=['GET'])
def get_system_telemetry():
    """Get system-wide telemetry for Recursive Stability Controller"""
    # Get all active packets
    active_packets = [p for p in executor.packets.values()
                     if p.status in ['planning', 'executing']]

    # Count by authority level
    authority_levels = {'none': 0, 'low': 0, 'medium': 0, 'high': 0, 'full': 0}
    for packet in active_packets:
        auth = packet.authority_level
        if auth in authority_levels:
            authority_levels[auth] += 1

    # Count by status
    executing_packets = sum(1 for p in executor.packets.values() if p.status == 'executing')
    queued_packets = sum(1 for p in executor.packets.values() if p.status == 'queued')
    failed_packets = sum(1 for p in executor.packets.values() if p.status == 'failed')

    # Active agents = packets with authority > none
    active_agents = sum(1 for p in active_packets if p.authority_level != 'none')

    return jsonify({
        'active_agents': active_agents,
        'executing_packets': executing_packets,
        'queued_packets': queued_packets,
        'failed_packets': failed_packets,
        'authority_levels': authority_levels,
        'total_packets': len(executor.packets)
    })


@app.route('/risk/<packet_id>', methods=['GET'])
def get_runtime_risk(packet_id: str):
    """Get runtime risk"""
    summary = risk_monitor.get_monitoring_summary(packet_id)

    if not summary:
        return jsonify({'error': 'Risk monitoring not found'}), 404

    return jsonify(summary)


@app.route('/certificate/<packet_id>', methods=['GET'])
def get_certificate(packet_id: str):
    """Get completion certificate"""
    certificate = completion_certifier.get_certificate(packet_id)

    if not certificate:
        return jsonify({'error': 'Certificate not found'}), 404

    return jsonify({
        'certificate': certificate.to_dict(),
        'verified': completion_certifier.verify_certificate(certificate)
    })


@app.route('/interfaces', methods=['GET'])
def get_interfaces():
    """Get interface status"""
    status = validator.get_interface_status()

    return jsonify(status.to_dict())


@app.route('/interfaces/register', methods=['POST'])
def register_interface():
    """Register interface"""
    data = request.json
    if not data or not isinstance(data, dict):
        return jsonify({'error': 'Invalid request body'}), 400

    interface_id = data.get('interface_id', '')
    invalid = _validate_identifier(interface_id, 'interface_id')
    if invalid:
        return invalid

    health = InterfaceHealth(
        interface_id=interface_id,
        is_available=bool(data.get('is_available', True)),
        response_time_ms=float(data.get('response_time_ms', 0.0)),
        error_rate=float(data.get('error_rate', 0.0)),
        last_check=datetime.now(timezone.utc)
    )

    validator.register_interface(health)

    return jsonify({
        'status': 'registered',
        'interface': health.to_dict()
    })


@app.route('/pause/<packet_id>', methods=['POST'])
def pause_execution(packet_id: str):
    """Pause execution (only by owner)"""
    if packet_id not in executions:
        return jsonify({'error': 'Execution not found'}), 404

    # ARCH-004: Ownership check — prevent IDOR
    denied = _check_ownership(packet_id)
    if denied:
        return denied

    execution_state = executions[packet_id]
    if execution_state.status != ExecutionStatus.RUNNING:
        return jsonify({'error': 'Execution is not running'}), 400

    execution_state.status = ExecutionStatus.PAUSED

    return jsonify({
        'status': 'paused',
        'execution_state': execution_state.to_dict()
    })


@app.route('/resume/<packet_id>', methods=['POST'])
def resume_execution(packet_id: str):
    """Resume execution (only by owner)"""
    if packet_id not in executions:
        return jsonify({'error': 'Execution not found'}), 404

    # ARCH-004: Ownership check — prevent IDOR
    denied = _check_ownership(packet_id)
    if denied:
        return denied

    execution_state = executions[packet_id]
    if execution_state.status != ExecutionStatus.PAUSED:
        return jsonify({'error': 'Execution is not paused'}), 400

    execution_state.status = ExecutionStatus.RUNNING

    return jsonify({
        'status': 'resumed',
        'execution_state': execution_state.to_dict()
    })


@app.route('/abort/<packet_id>', methods=['POST'])
def abort_execution(packet_id: str):
    """Abort execution (only by owner)"""
    if packet_id not in executions:
        return jsonify({'error': 'Execution not found'}), 404

    # ARCH-004: Ownership check — prevent IDOR
    denied = _check_ownership(packet_id)
    if denied:
        return denied

    execution_state = executions[packet_id]
    execution_state.status = ExecutionStatus.ABORTED
    execution_state.end_time = datetime.now(timezone.utc)

    return jsonify({
        'status': 'aborted',
        'execution_state': execution_state.to_dict()
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8058, debug=False)
