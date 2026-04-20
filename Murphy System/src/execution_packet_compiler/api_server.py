"""
Execution Packet Compiler API Server
REST API for compiling sealed execution packets
"""

import logging
import os

# Import from confidence engine
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, request

from .dependency_resolver import DependencyResolver
from .determinism_enforcer import DeterminismEnforcer
from .models import (
    ExecutionGraph,
    ExecutionPacket,
    ExecutionScope,
    ExecutionStep,
    InterfaceBinding,
    InterfaceMap,
    InterfaceType,
    PacketState,
    RollbackPlan,
    RollbackStep,
    StepType,
    TelemetryConfig,
    TelemetryPlan,
)
from .packet_sealer import PacketSealer
from .post_compilation_enforcer import PostCompilationEnforcer
from .risk_bounder import RiskBounder
from .scope_freezer import ScopeFreezer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from confidence_engine.models import ArtifactGraph, ArtifactNode, ArtifactSource, ArtifactType
from flask_security import configure_secure_app, is_debug_mode

# Initialize Flask app
app = Flask(__name__)
configure_secure_app(app, service_name="execution-packet-compiler")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize components
scope_freezer = ScopeFreezer()
dependency_resolver = DependencyResolver()
determinism_enforcer = DeterminismEnforcer()
risk_bounder = RiskBounder()
packet_sealer = PacketSealer()
post_compilation_enforcer = PostCompilationEnforcer()

# Global state
current_artifact_graph = ArtifactGraph()
active_gates: List[Dict[str, Any]] = []


# ============================================================================
# COMPILATION ENDPOINTS
# ============================================================================

@app.route('/api/epc/compile', methods=['POST'])
def compile_packet():
    """Compile execution packet from artifact graph"""
    try:
        data = request.json

        packet_id = data.get('packet_id', f"packet_{datetime.now(timezone.utc).timestamp()}")
        parameters = data.get('parameters', {})

        # Step 1: Create and freeze scope
        scope, scope_errors = scope_freezer.create_scope(
            f"scope_{packet_id}",
            current_artifact_graph,
            active_gates,
            parameters
        )

        if scope_errors:
            return jsonify({
                'success': False,
                'stage': 'scope_creation',
                'errors': scope_errors
            }), 400

        success, scope_hash, freeze_errors = scope_freezer.freeze_scope(scope)

        if not success:
            return jsonify({
                'success': False,
                'stage': 'scope_freezing',
                'errors': freeze_errors
            }), 400

        # Step 2: Resolve dependencies
        execution_graph, dep_errors = dependency_resolver.resolve_dependencies(
            scope,
            current_artifact_graph
        )

        if dep_errors:
            return jsonify({
                'success': False,
                'stage': 'dependency_resolution',
                'errors': dep_errors
            }), 400

        # Step 3: Enforce determinism
        is_deterministic, det_violations = determinism_enforcer.enforce_determinism(
            execution_graph
        )

        if not is_deterministic:
            return jsonify({
                'success': False,
                'stage': 'determinism_enforcement',
                'violations': det_violations
            }), 400

        # Step 4: Bound risk
        within_threshold, risk_report = risk_bounder.enforce_risk_bounds(
            execution_graph,
            scope
        )

        if not within_threshold:
            return jsonify({
                'success': False,
                'stage': 'risk_bounding',
                'risk_report': risk_report
            }), 400

        # Step 5: Create interface map (placeholder)
        interfaces = InterfaceMap()

        # Step 6: Create rollback plan (placeholder)
        rollback_plan = RollbackPlan(plan_id=f"rollback_{packet_id}")
        rollback_plan.add_step(RollbackStep(
            step_id="rollback_1",
            description="Emergency stop",
            action="stop_all"
        ))

        # Step 7: Create telemetry plan (placeholder)
        telemetry_plan = TelemetryPlan(plan_id=f"telemetry_{packet_id}")
        telemetry_plan.add_config(TelemetryConfig(
            metric_name="execution_progress",
            collection_interval=1.0
        ))

        # Step 8: Create packet
        packet = packet_sealer.create_packet(
            packet_id,
            scope,
            execution_graph,
            interfaces,
            rollback_plan,
            telemetry_plan
        )

        logger.info(f"Compiled packet {packet_id}")

        return jsonify({
            'success': True,
            'packet_id': packet_id,
            'scope_hash': scope_hash,
            'execution_order': execution_graph.get_execution_order(),
            'step_count': len(execution_graph.steps),
            'risk_report': risk_report,
            'state': packet.state.value
        })

    except Exception as exc:
        logger.error(f"Error compiling packet: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


@app.route('/api/epc/packets/<packet_id>/seal', methods=['POST'])
def seal_packet(packet_id: str):
    """Seal execution packet"""
    try:
        data = request.json

        confidence = data['confidence']
        authority_band = data['authority_band']
        phase = data['phase']

        # Get packet
        packet = packet_sealer.get_sealed_packet(packet_id)

        if not packet:
            return jsonify({
                'success': False,
                'error': 'Packet not found'
            }), 404

        # Seal packet
        success, signature, errors = packet_sealer.seal_packet(
            packet,
            confidence,
            authority_band,
            phase
        )

        if not success:
            return jsonify({
                'success': False,
                'errors': errors
            }), 400

        # Lock compilation
        lock_id = post_compilation_enforcer.lock_compilation(packet)

        logger.info(f"Sealed packet {packet_id}")

        return jsonify({
            'success': True,
            'packet_id': packet_id,
            'signature': signature,
            'lock_id': lock_id,
            'state': packet.state.value
        })

    except Exception as exc:
        logger.error(f"Error sealing packet: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


@app.route('/api/epc/packets/<packet_id>/verify', methods=['POST'])
def verify_packet(packet_id: str):
    """Verify packet signature and integrity"""
    try:
        packet = packet_sealer.get_sealed_packet(packet_id)

        if not packet:
            return jsonify({
                'success': False,
                'error': 'Packet not found'
            }), 404

        is_valid, violations = packet_sealer.verify_packet(packet)

        return jsonify({
            'success': True,
            'packet_id': packet_id,
            'is_valid': is_valid,
            'violations': violations,
            'signature': packet.signature
        })

    except Exception as exc:
        logger.error(f"Error verifying packet: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


@app.route('/api/epc/packets/<packet_id>/invalidate', methods=['POST'])
def invalidate_packet(packet_id: str):
    """Invalidate packet"""
    try:
        data = request.json
        reason = data.get('reason', 'Manual invalidation')

        packet = packet_sealer.get_sealed_packet(packet_id)

        if not packet:
            return jsonify({
                'success': False,
                'error': 'Packet not found'
            }), 404

        packet_sealer.invalidate_packet(packet, reason)

        logger.info(f"Invalidated packet {packet_id}: {reason}")

        return jsonify({
            'success': True,
            'packet_id': packet_id,
            'reason': reason,
            'state': packet.state.value
        })

    except Exception as exc:
        logger.error(f"Error invalidating packet: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


# ============================================================================
# QUERY ENDPOINTS
# ============================================================================

@app.route('/api/epc/packets/<packet_id>', methods=['GET'])
def get_packet(packet_id: str):
    """Get packet details"""
    try:
        packet = packet_sealer.get_sealed_packet(packet_id)

        if not packet:
            return jsonify({
                'success': False,
                'error': 'Packet not found'
            }), 404

        return jsonify({
            'success': True,
            'packet': packet.to_dict()
        })

    except Exception as exc:
        logger.error(f"Error getting packet: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


@app.route('/api/epc/packets/list', methods=['GET'])
def list_packets():
    """List all packets"""
    try:
        packet_ids = packet_sealer.list_sealed_packets()

        packets = []
        for packet_id in packet_ids:
            packet = packet_sealer.get_sealed_packet(packet_id)
            if packet:
                packets.append({
                    'packet_id': packet.packet_id,
                    'state': packet.state.value,
                    'created_at': packet.created_at.isoformat(),
                    'sealed_at': packet.sealed_at.isoformat() if packet.sealed_at else None
                })

        return jsonify({
            'success': True,
            'packets': packets,
            'count': len(packets)
        })

    except Exception as exc:
        logger.error(f"Error listing packets: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


@app.route('/api/epc/packets/<packet_id>/can-execute', methods=['GET'])
def can_execute(packet_id: str):
    """Check if packet can be executed"""
    try:
        packet = packet_sealer.get_sealed_packet(packet_id)

        if not packet:
            return jsonify({
                'success': False,
                'error': 'Packet not found'
            }), 404

        can_exec, blockers = packet.can_execute()

        return jsonify({
            'success': True,
            'packet_id': packet_id,
            'can_execute': can_exec,
            'blockers': blockers
        })

    except Exception as exc:
        logger.error(f"Error checking execution: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


@app.route('/api/epc/packets/<packet_id>/lock-status', methods=['GET'])
def get_lock_status(packet_id: str):
    """Get lock status for packet"""
    try:
        status = post_compilation_enforcer.get_lock_status(packet_id)

        return jsonify({
            'success': True,
            'lock_status': status
        })

    except Exception as exc:
        logger.error(f"Error getting lock status: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


# ============================================================================
# ARTIFACT GRAPH ENDPOINTS (for testing)
# ============================================================================

@app.route('/api/epc/artifacts/add', methods=['POST'])
def add_artifact():
    """Add artifact to graph (for testing)"""
    try:
        data = request.json

        node = ArtifactNode(
            id=data.get('id', ''),
            type=ArtifactType(data['type']),
            source=ArtifactSource(data['source']),
            content=data['content'],
            confidence_weight=data.get('confidence_weight', 1.0),
            dependencies=data.get('dependencies', [])
        )

        current_artifact_graph.add_node(node)

        return jsonify({
            'success': True,
            'artifact_id': node.id
        })

    except Exception as exc:
        logger.error(f"Error adding artifact: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


@app.route('/api/epc/gates/add', methods=['POST'])
def add_gate():
    """Add gate (for testing)"""
    try:
        data = request.json
        active_gates.append(data)

        return jsonify({
            'success': True,
            'gate_count': len(active_gates)
        })

    except Exception as exc:
        logger.error(f"Error adding gate: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.route('/api/epc/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'execution-packet-compiler',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'components': {
            'scope_freezer': 'operational',
            'dependency_resolver': 'operational',
            'determinism_enforcer': 'operational',
            'risk_bounder': 'operational',
            'packet_sealer': 'operational',
            'post_compilation_enforcer': 'operational'
        }
    })


# ============================================================================
# RESET ENDPOINT (for testing)
# ============================================================================

@app.route('/api/epc/reset', methods=['POST'])
def reset_state():
    """Reset all state (for testing)"""
    global current_artifact_graph, active_gates

    current_artifact_graph = ArtifactGraph()
    active_gates = []

    logger.info("Reset EPC state")

    return jsonify({
        'success': True,
        'message': 'State reset successfully'
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8057, debug=is_debug_mode())
