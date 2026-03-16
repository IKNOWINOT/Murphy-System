"""
Gate Synthesis Engine API Server
REST API for dynamic gate generation and lifecycle management
"""

import logging

# Import from confidence engine
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, request

from .failure_mode_enumerator import FailureModeEnumerator
from .gate_generator import GateGenerator
from .gate_lifecycle_manager import GateLifecycleManager
from .models import (
    ExposureSignal,
    FailureMode,
    FailureModeType,
    Gate,
    GateCategory,
    GateState,
    GateType,
    RetirementCondition,
    RiskVector,
)
from .murphy_estimator import MurphyProbabilityEstimator

from src.confidence_engine.models import (
    ArtifactGraph,
    ArtifactNode,
    ArtifactSource,
    ArtifactType,
    AuthorityBand,
    ConfidenceState,
    Phase,
)
from flask_security import configure_secure_app, is_debug_mode

# Initialize Flask app
app = Flask(__name__)
configure_secure_app(app, service_name="gate-synthesis")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize components
failure_mode_enumerator = FailureModeEnumerator()
murphy_estimator = MurphyProbabilityEstimator()
gate_generator = GateGenerator()
gate_lifecycle_manager = GateLifecycleManager()

# Global state
current_artifact_graph = ArtifactGraph()


# ============================================================================
# FAILURE MODE ENDPOINTS
# ============================================================================

@app.route('/api/gate-synthesis/failure-modes/enumerate', methods=['POST'])
def enumerate_failure_modes():
    """Enumerate failure modes for current state"""
    try:
        data = request.json

        # Parse confidence state
        confidence_state = ConfidenceState(
            confidence=data['confidence_state']['confidence'],
            generative_score=data['confidence_state']['generative_score'],
            deterministic_score=data['confidence_state']['deterministic_score'],
            epistemic_instability=data['confidence_state']['epistemic_instability'],
            phase=Phase(data['confidence_state']['phase'])
        )
        confidence_state.verified_artifacts = data['confidence_state'].get('verified_artifacts', 0)
        confidence_state.total_artifacts = data['confidence_state'].get('total_artifacts', 0)

        # Parse authority band
        authority_band = AuthorityBand(data['authority_band'])

        # Parse exposure signal (optional)
        exposure_signal = None
        if 'exposure_signal' in data:
            exp_data = data['exposure_signal']
            exposure_signal = ExposureSignal(
                signal_id=exp_data.get('signal_id', 'default'),
                external_side_effects=exp_data['external_side_effects'],
                reversibility=exp_data['reversibility'],
                blast_radius_estimate=exp_data['blast_radius_estimate'],
                affected_systems=exp_data.get('affected_systems', [])
            )

        # Enumerate failure modes
        failure_modes = failure_mode_enumerator.enumerate_failure_modes(
            current_artifact_graph,
            confidence_state,
            authority_band,
            exposure_signal
        )

        logger.info(f"Enumerated {len(failure_modes)} failure modes")

        return jsonify({
            'success': True,
            'failure_modes': [fm.to_dict() for fm in failure_modes],
            'count': len(failure_modes)
        })

    except Exception as exc:
        logger.error(f"Error enumerating failure modes: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


# ============================================================================
# MURPHY PROBABILITY ENDPOINTS
# ============================================================================

@app.route('/api/gate-synthesis/murphy/estimate', methods=['POST'])
def estimate_murphy_probability():
    """Estimate Murphy probability for risk vector"""
    try:
        data = request.json

        risk_vector = RiskVector(
            H=data['risk_vector']['H'],
            one_minus_D=data['risk_vector']['one_minus_D'],
            exposure=data['risk_vector']['exposure'],
            authority_risk=data['risk_vector']['authority_risk']
        )

        murphy_prob = murphy_estimator.estimate_murphy_probability(risk_vector)
        gate_required = murphy_estimator.requires_gate(murphy_prob)
        high_risk = murphy_estimator.is_high_risk(murphy_prob)

        return jsonify({
            'success': True,
            'murphy_probability': murphy_prob,
            'gate_required': gate_required,
            'high_risk': high_risk,
            'risk_vector': risk_vector.to_dict()
        })

    except Exception as exc:
        logger.error(f"Error estimating Murphy probability: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


@app.route('/api/gate-synthesis/murphy/analyze-exposure', methods=['POST'])
def analyze_exposure():
    """Analyze exposure signal"""
    try:
        data = request.json

        exposure_signal = ExposureSignal(
            signal_id=data.get('signal_id', 'default'),
            external_side_effects=data['external_side_effects'],
            reversibility=data['reversibility'],
            blast_radius_estimate=data['blast_radius_estimate'],
            affected_systems=data.get('affected_systems', [])
        )

        analysis = murphy_estimator.analyze_exposure(exposure_signal)

        return jsonify({
            'success': True,
            'analysis': analysis
        })

    except Exception as exc:
        logger.error("Error analyzing exposure: %s", exc, exc_info=True)
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


# ============================================================================
# GATE GENERATION ENDPOINTS
# ============================================================================

@app.route('/api/gate-synthesis/gates/generate', methods=['POST'])
def generate_gates():
    """Generate gates for failure modes"""
    try:
        data = request.json

        # Parse failure modes
        failure_modes = []
        for fm_data in data['failure_modes']:
            risk_vector = RiskVector(
                H=fm_data['risk_vector']['H'],
                one_minus_D=fm_data['risk_vector']['one_minus_D'],
                exposure=fm_data['risk_vector']['exposure'],
                authority_risk=fm_data['risk_vector']['authority_risk']
            )

            failure_mode = FailureMode(
                id=fm_data['id'],
                type=FailureModeType(fm_data['type']),
                probability=fm_data['probability'],
                impact=fm_data['impact'],
                risk_vector=risk_vector,
                description=fm_data['description'],
                affected_artifacts=fm_data.get('affected_artifacts', [])
            )
            failure_modes.append(failure_mode)

        # Parse current state
        current_phase = Phase(data['current_phase'])
        current_authority = AuthorityBand(data['current_authority'])

        # Calculate Murphy probabilities
        murphy_probabilities = {}
        for fm in failure_modes:
            murphy_prob = murphy_estimator.estimate_failure_mode_probability(fm)
            murphy_probabilities[fm.id] = murphy_prob

        # Generate gates
        gates = gate_generator.generate_gates(
            failure_modes,
            current_phase,
            current_authority,
            murphy_probabilities
        )

        # Add gates to lifecycle manager
        for gate in gates:
            gate_lifecycle_manager.add_gate(gate)

        logger.info(f"Generated {len(gates)} gates")

        return jsonify({
            'success': True,
            'gates': [gate.to_dict() for gate in gates],
            'count': len(gates)
        })

    except Exception as exc:
        logger.error(f"Error generating gates: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


# ============================================================================
# GATE LIFECYCLE ENDPOINTS
# ============================================================================

@app.route('/api/gate-synthesis/gates/activate/<gate_id>', methods=['POST'])
def activate_gate(gate_id: str):
    """Activate a specific gate"""
    try:
        success = gate_lifecycle_manager.activate_gate(gate_id)

        if success:
            return jsonify({
                'success': True,
                'gate_id': gate_id,
                'message': 'Gate activated'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Gate not found or cannot be activated'
            }), 404

    except Exception as exc:
        logger.error(f"Error activating gate: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


@app.route('/api/gate-synthesis/gates/activate-all', methods=['POST'])
def activate_all_gates():
    """Activate all proposed gates"""
    try:
        activated = gate_lifecycle_manager.activate_all_proposed_gates()

        return jsonify({
            'success': True,
            'activated_gates': activated,
            'count': len(activated)
        })

    except Exception as exc:
        logger.error(f"Error activating gates: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


@app.route('/api/gate-synthesis/gates/retire/<gate_id>', methods=['POST'])
def retire_gate(gate_id: str):
    """Retire a specific gate"""
    try:
        data = request.json or {}
        reason = data.get('reason', '')

        success = gate_lifecycle_manager.retire_gate(gate_id, reason)

        if success:
            return jsonify({
                'success': True,
                'gate_id': gate_id,
                'message': 'Gate retired'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Gate not found or cannot be retired'
            }), 404

    except Exception as exc:
        logger.error(f"Error retiring gate: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


@app.route('/api/gate-synthesis/gates/check-expiry', methods=['POST'])
def check_expiry():
    """Check and retire expired gates"""
    try:
        expired = gate_lifecycle_manager.check_and_retire_expired_gates()

        return jsonify({
            'success': True,
            'expired_gates': expired,
            'count': len(expired)
        })

    except Exception as exc:
        logger.error(f"Error checking expiry: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


@app.route('/api/gate-synthesis/gates/update-retirement-conditions', methods=['POST'])
def update_retirement_conditions():
    """Update retirement conditions for gates"""
    try:
        data = request.json

        retired = gate_lifecycle_manager.check_all_retirement_conditions(
            data['condition_values']
        )

        return jsonify({
            'success': True,
            'retired_gates': retired,
            'count': len(retired)
        })

    except Exception as exc:
        logger.error(f"Error updating retirement conditions: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


# ============================================================================
# GATE QUERY ENDPOINTS
# ============================================================================

@app.route('/api/gate-synthesis/gates/list', methods=['GET'])
def list_gates():
    """List all gates"""
    try:
        state_filter = request.args.get('state')
        category_filter = request.args.get('category')

        gates = list(gate_lifecycle_manager.registry.gates.values())

        # Apply filters
        if state_filter:
            state = GateState(state_filter)
            gates = [g for g in gates if g.state == state]

        if category_filter:
            category = GateCategory(category_filter)
            gates = [g for g in gates if g.category == category]

        return jsonify({
            'success': True,
            'gates': [gate.to_dict() for gate in gates],
            'count': len(gates)
        })

    except Exception as exc:
        logger.error(f"Error listing gates: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


@app.route('/api/gate-synthesis/gates/<gate_id>', methods=['GET'])
def get_gate(gate_id: str):
    """Get specific gate"""
    try:
        gate = gate_lifecycle_manager.registry.get_gate(gate_id)

        if gate:
            return jsonify({
                'success': True,
                'gate': gate.to_dict()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Gate not found'
            }), 404

    except Exception as exc:
        logger.error(f"Error getting gate: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


@app.route('/api/gate-synthesis/gates/active', methods=['GET'])
def get_active_gates():
    """Get all active gates"""
    try:
        active_gates = gate_lifecycle_manager.registry.get_active_gates()

        return jsonify({
            'success': True,
            'gates': [gate.to_dict() for gate in active_gates],
            'count': len(active_gates)
        })

    except Exception as exc:
        logger.error(f"Error getting active gates: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


@app.route('/api/gate-synthesis/gates/by-target/<target>', methods=['GET'])
def get_gates_by_target(target: str):
    """Get gates for specific target"""
    try:
        gates = gate_lifecycle_manager.get_active_gates_for_target(target)

        return jsonify({
            'success': True,
            'target': target,
            'gates': [gate.to_dict() for gate in gates],
            'count': len(gates)
        })

    except Exception as exc:
        logger.error(f"Error getting gates by target: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


# ============================================================================
# STATISTICS ENDPOINTS
# ============================================================================

@app.route('/api/gate-synthesis/statistics', methods=['GET'])
def get_statistics():
    """Get gate statistics"""
    try:
        stats = gate_lifecycle_manager.get_gate_statistics()

        return jsonify({
            'success': True,
            'statistics': stats
        })

    except Exception as exc:
        logger.error(f"Error getting statistics: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


@app.route('/api/gate-synthesis/logs/activation', methods=['GET'])
def get_activation_log():
    """Get activation log"""
    try:
        limit = request.args.get('limit', type=int)
        log = gate_lifecycle_manager.get_activation_log(limit)

        return jsonify({
            'success': True,
            'log': log,
            'count': len(log)
        })

    except Exception as exc:
        logger.error(f"Error getting activation log: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


@app.route('/api/gate-synthesis/logs/retirement', methods=['GET'])
def get_retirement_log():
    """Get retirement log"""
    try:
        limit = request.args.get('limit', type=int)
        log = gate_lifecycle_manager.get_retirement_log(limit)

        return jsonify({
            'success': True,
            'log': log,
            'count': len(log)
        })

    except Exception as exc:
        logger.error(f"Error getting retirement log: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


# ============================================================================
# ARTIFACT GRAPH ENDPOINTS (for testing)
# ============================================================================

@app.route('/api/gate-synthesis/artifacts/add', methods=['POST'])
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


# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.route('/api/gate-synthesis/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'gate-synthesis-engine',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'components': {
            'failure_mode_enumerator': 'operational',
            'murphy_estimator': 'operational',
            'gate_generator': 'operational',
            'gate_lifecycle_manager': 'operational'
        }
    })


# ============================================================================
# RESET ENDPOINT (for testing)
# ============================================================================

@app.route('/api/gate-synthesis/reset', methods=['POST'])
def reset_state():
    """Reset all state (for testing)"""
    global current_artifact_graph, gate_lifecycle_manager

    current_artifact_graph = ArtifactGraph()
    gate_lifecycle_manager = GateLifecycleManager()

    logger.info("Reset gate synthesis engine state")

    return jsonify({
        'success': True,
        'message': 'State reset successfully'
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8056, debug=is_debug_mode())
