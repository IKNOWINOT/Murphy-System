"""
Confidence Engine API Server
REST API for confidence, risk, and authority computation
"""

import logging
import os
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, request

from confidence_engine.authority_mapper import AuthorityMapper
from confidence_engine.confidence_calculator import ConfidenceCalculator
from confidence_engine.graph_analyzer import GraphAnalyzer
from confidence_engine.models import (
    ArtifactGraph,
    ArtifactNode,
    ArtifactSource,
    ArtifactType,
    Phase,
    SourceTrust,
    TrustModel,
    VerificationEvidence,
    VerificationResult,
)
from confidence_engine.murphy_calculator import MurphyCalculator
from confidence_engine.phase_controller import PhaseController
from flask_security import configure_secure_app, is_debug_mode

# Initialize Flask app
app = Flask(__name__)
configure_secure_app(app, service_name="confidence-engine")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize components (stateless — safe to share across tenants)
graph_analyzer = GraphAnalyzer()
confidence_calculator = ConfidenceCalculator()
murphy_calculator = MurphyCalculator()
authority_mapper = AuthorityMapper()
phase_controller = PhaseController()

# Per-tenant state stores (ARCH-003: tenant isolation)
# Each tenant gets its own ArtifactGraph, TrustModel, and evidence store
# Thread lock protects concurrent creation of tenant entries
_tenant_lock = threading.Lock()
_tenant_graphs: Dict[str, ArtifactGraph] = {}
_tenant_trust_models: Dict[str, TrustModel] = {}
_tenant_evidence: Dict[str, List[VerificationEvidence]] = {}
_tenant_last_access: Dict[str, datetime] = {}
_TENANT_TTL_SECONDS = 3600  # 1 hour — evict idle tenants


def _get_tenant_id() -> str:
    """
    Extract tenant ID from the request.

    Uses X-Tenant-ID header, falling back to 'default' for
    backward compatibility during migration.
    """
    return request.headers.get('X-Tenant-ID', 'default')


def _require_tenant_id():
    """
    Require X-Tenant-ID header; return (tenant_id, None) on success or
    (None, 401-response) when the header is absent.
    """
    tenant_id = request.headers.get('X-Tenant-ID')
    if not tenant_id:
        return None, (jsonify({'error': 'X-Tenant-ID header required'}), 401)
    _tenant_last_access[tenant_id] = datetime.now(tz=timezone.utc)
    return tenant_id, None


def evict_idle_tenants() -> int:
    """
    Evict tenant state that has been idle for longer than _TENANT_TTL_SECONDS.

    Returns the number of tenants evicted.
    """
    with _tenant_lock:
        now = datetime.now(tz=timezone.utc)
        idle = [
            tid for tid, last in _tenant_last_access.items()
            if (now - last).total_seconds() > _TENANT_TTL_SECONDS
        ]
        for tid in idle:
            _tenant_graphs.pop(tid, None)
            _tenant_trust_models.pop(tid, None)
            _tenant_evidence.pop(tid, None)
            del _tenant_last_access[tid]
    return len(idle)


def _get_tenant_graph(tenant_id: str) -> ArtifactGraph:
    """Get or create the ArtifactGraph for a tenant."""
    with _tenant_lock:
        if tenant_id not in _tenant_graphs:
            _tenant_graphs[tenant_id] = ArtifactGraph()
        return _tenant_graphs[tenant_id]


def _get_tenant_trust_model(tenant_id: str) -> TrustModel:
    """Get or create the TrustModel for a tenant."""
    with _tenant_lock:
        if tenant_id not in _tenant_trust_models:
            _tenant_trust_models[tenant_id] = TrustModel()
        return _tenant_trust_models[tenant_id]


def _get_tenant_evidence(tenant_id: str) -> List[VerificationEvidence]:
    """Get or create the evidence store for a tenant."""
    with _tenant_lock:
        if tenant_id not in _tenant_evidence:
            _tenant_evidence[tenant_id] = []
        return _tenant_evidence[tenant_id]


@app.before_request
def _enforce_tenant_id():
    """Require X-Tenant-ID header on all non-health API endpoints."""
    if request.method == 'OPTIONS':
        return None
    path = request.path.rstrip('/')
    if path in ('/health', '/healthz', '/ready', '/metrics'):
        return None
    if not request.headers.get('X-Tenant-ID'):
        return jsonify({'error': 'X-Tenant-ID header required'}), 401
    return None


# ============================================================================
# ARTIFACT GRAPH ENDPOINTS
# ============================================================================

@app.route('/api/confidence-engine/artifacts/add', methods=['POST'])
def add_artifact():
    """Add artifact to graph"""
    try:
        data = request.json
        tenant_id = _get_tenant_id()
        current_graph = _get_tenant_graph(tenant_id)

        # Create artifact node
        node = ArtifactNode(
            id=data.get('id', ''),
            type=ArtifactType(data['type']),
            source=ArtifactSource(data['source']),
            content=data['content'],
            confidence_weight=data.get('confidence_weight', 1.0),
            dependencies=data.get('dependencies', []),
            metadata=data.get('metadata', {})
        )

        # Add to graph
        current_graph.add_node(node)

        # Validate DAG
        is_valid, errors = graph_analyzer.validate_dag(current_graph)

        if not is_valid:
            # Remove node if it breaks DAG
            del current_graph.nodes[node.id]
            return jsonify({
                'success': False,
                'error': 'Adding this artifact would break DAG structure',
                'details': errors
            }), 400

        logger.info(f"Added artifact {node.id} to graph (tenant={tenant_id})")

        return jsonify({
            'success': True,
            'artifact_id': node.id,
            'graph_stats': {
                'total_nodes': len(current_graph.nodes),
                'is_dag': is_valid
            }
        })

    except Exception as exc:
        logger.error(f"Error adding artifact: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


@app.route('/api/confidence-engine/artifacts/graph', methods=['GET'])
def get_graph():
    """Get complete artifact graph"""
    try:
        tenant_id = _get_tenant_id()
        current_graph = _get_tenant_graph(tenant_id)
        return jsonify({
            'success': True,
            'graph': current_graph.to_dict()
        })
    except Exception as exc:
        logger.error(f"Error getting graph: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


@app.route('/api/confidence-engine/artifacts/analyze', methods=['GET'])
def analyze_graph():
    """Analyze graph structure"""
    try:
        tenant_id = _get_tenant_id()
        current_graph = _get_tenant_graph(tenant_id)
        # Validate DAG
        is_valid, errors = graph_analyzer.validate_dag(current_graph)

        # Detect contradictions
        contradictions = graph_analyzer.detect_contradictions(current_graph)

        # Calculate entropy
        entropy = graph_analyzer.calculate_entropy(current_graph)

        # Analyze dependencies
        dep_analysis = graph_analyzer.analyze_dependencies(current_graph)

        return jsonify({
            'success': True,
            'analysis': {
                'is_valid_dag': is_valid,
                'errors': errors,
                'contradictions': contradictions,
                'entropy': entropy,
                'dependencies': dep_analysis
            }
        })
    except Exception as exc:
        logger.error(f"Error analyzing graph: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


# ============================================================================
# VERIFICATION ENDPOINTS
# ============================================================================

@app.route('/api/confidence-engine/verification/add', methods=['POST'])
def add_verification():
    """Add verification evidence"""
    try:
        data = request.json
        tenant_id = _get_tenant_id()
        verification_evidence_store = _get_tenant_evidence(tenant_id)

        evidence = VerificationEvidence(
            artifact_id=data['artifact_id'],
            result=VerificationResult(data['result']),
            stability_score=data['stability_score'],
            confidence_boost=data.get('confidence_boost', 0.0),
            details=data.get('details', {})
        )

        verification_evidence_store.append(evidence)

        logger.info(f"Added verification evidence for artifact {evidence.artifact_id}")

        return jsonify({
            'success': True,
            'evidence_count': len(verification_evidence_store)
        })

    except Exception as exc:
        logger.error(f"Error adding verification: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


@app.route('/api/confidence-engine/verification/list', methods=['GET'])
def list_verification():
    """List all verification evidence"""
    try:
        tenant_id = _get_tenant_id()
        verification_evidence_store = _get_tenant_evidence(tenant_id)
        return jsonify({
            'success': True,
            'evidence': [e.to_dict() for e in verification_evidence_store],
            'count': len(verification_evidence_store)
        })
    except Exception as exc:
        logger.error(f"Error listing verification: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


# ============================================================================
# TRUST MODEL ENDPOINTS
# ============================================================================

@app.route('/api/confidence-engine/trust/add-source', methods=['POST'])
def add_trust_source():
    """Add or update trust source"""
    try:
        data = request.json
        tenant_id = _get_tenant_id()
        current_trust_model = _get_tenant_trust_model(tenant_id)

        source = SourceTrust(
            source_id=data['source_id'],
            source_type=ArtifactSource(data['source_type']),
            trust_weight=data['trust_weight'],
            volatility=data.get('volatility', 0.1)
        )

        current_trust_model.add_source(source)

        logger.info(f"Added trust source {source.source_id}")

        return jsonify({
            'success': True,
            'source_id': source.source_id,
            'trust_weight': source.trust_weight
        })

    except Exception as exc:
        logger.error(f"Error adding trust source: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


@app.route('/api/confidence-engine/trust/update', methods=['POST'])
def update_trust():
    """Update trust based on outcome"""
    try:
        data = request.json
        tenant_id = _get_tenant_id()
        current_trust_model = _get_tenant_trust_model(tenant_id)
        source_id = data['source_id']
        success = data['success']

        current_trust_model.update_source(source_id, success)

        logger.info(f"Updated trust for {source_id}: success={success}")

        return jsonify({
            'success': True,
            'source_id': source_id,
            'new_trust': current_trust_model.get_trust(source_id)
        })

    except Exception as exc:
        logger.error(f"Error updating trust: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


@app.route('/api/confidence-engine/trust/model', methods=['GET'])
def get_trust_model():
    """Get complete trust model"""
    try:
        tenant_id = _get_tenant_id()
        current_trust_model = _get_tenant_trust_model(tenant_id)
        return jsonify({
            'success': True,
            'trust_model': current_trust_model.to_dict()
        })
    except Exception as exc:
        logger.error(f"Error getting trust model: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


# ============================================================================
# CONFIDENCE COMPUTATION ENDPOINTS
# ============================================================================

@app.route('/api/confidence-engine/confidence/compute', methods=['POST'])
def compute_confidence():
    """Compute confidence state"""
    try:
        data = request.json
        tenant_id = _get_tenant_id()
        current_graph = _get_tenant_graph(tenant_id)
        current_trust_model = _get_tenant_trust_model(tenant_id)
        verification_evidence_store = _get_tenant_evidence(tenant_id)
        phase = Phase(data.get('phase', 'expand'))

        # Compute confidence
        confidence_state = confidence_calculator.compute_confidence(
            current_graph,
            phase,
            verification_evidence_store,
            current_trust_model
        )

        logger.info(f"Computed confidence: {confidence_state.confidence:.3f}")

        return jsonify({
            'success': True,
            'confidence_state': confidence_state.to_dict()
        })

    except Exception as exc:
        logger.error(f"Error computing confidence: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


# ============================================================================
# MURPHY INDEX ENDPOINTS
# ============================================================================

@app.route('/api/confidence-engine/murphy/compute', methods=['POST'])
def compute_murphy():
    """Compute Murphy index"""
    try:
        data = request.json
        tenant_id = _get_tenant_id()
        current_graph = _get_tenant_graph(tenant_id)
        current_trust_model = _get_tenant_trust_model(tenant_id)
        verification_evidence_store = _get_tenant_evidence(tenant_id)
        phase = Phase(data.get('phase', 'expand'))

        # First compute confidence
        confidence_state = confidence_calculator.compute_confidence(
            current_graph,
            phase,
            verification_evidence_store,
            current_trust_model
        )

        # Compute Murphy index
        murphy_index = murphy_calculator.calculate_murphy_index(
            current_graph,
            confidence_state,
            phase
        )

        # Get failure mode details
        failure_modes = murphy_calculator.get_failure_mode_details(
            current_graph,
            confidence_state,
            phase
        )

        logger.info(f"Computed Murphy index: {murphy_index:.3f}")

        return jsonify({
            'success': True,
            'murphy_index': murphy_index,
            'failure_modes': failure_modes,
            'confidence': confidence_state.confidence
        })

    except Exception as exc:
        logger.error(f"Error computing Murphy index: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


# ============================================================================
# AUTHORITY ENDPOINTS
# ============================================================================

@app.route('/api/confidence-engine/authority/compute', methods=['POST'])
def compute_authority():
    """Compute authority state"""
    try:
        data = request.json
        tenant_id = _get_tenant_id()
        current_graph = _get_tenant_graph(tenant_id)
        current_trust_model = _get_tenant_trust_model(tenant_id)
        verification_evidence_store = _get_tenant_evidence(tenant_id)
        phase = Phase(data.get('phase', 'expand'))
        gate_satisfaction = data.get('gate_satisfaction', 0.0)
        unknowns = data.get('unknowns', 0)

        # Compute confidence
        confidence_state = confidence_calculator.compute_confidence(
            current_graph,
            phase,
            verification_evidence_store,
            current_trust_model
        )

        # Compute Murphy index
        murphy_index = murphy_calculator.calculate_murphy_index(
            current_graph,
            confidence_state,
            phase
        )

        # Map to authority
        authority_state = authority_mapper.map_authority(
            confidence_state,
            murphy_index,
            gate_satisfaction,
            unknowns
        )

        # Get execution blockers
        blockers = authority_mapper.get_execution_blockers(
            confidence_state.confidence,
            murphy_index,
            gate_satisfaction,
            unknowns,
            phase
        )

        logger.info(f"Computed authority: {authority_state.authority_band.value}")

        return jsonify({
            'success': True,
            'authority_state': authority_state.to_dict(),
            'execution_blockers': blockers
        })

    except Exception as exc:
        logger.error(f"Error computing authority: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


# ============================================================================
# PHASE CONTROL ENDPOINTS
# ============================================================================

@app.route('/api/confidence-engine/phase/check-transition', methods=['POST'])
def check_phase_transition():
    """Check if phase transition should occur"""
    try:
        data = request.json
        tenant_id = _get_tenant_id()
        current_graph = _get_tenant_graph(tenant_id)
        current_trust_model = _get_tenant_trust_model(tenant_id)
        verification_evidence_store = _get_tenant_evidence(tenant_id)
        current_phase = Phase(data['current_phase'])

        # Compute confidence
        confidence_state = confidence_calculator.compute_confidence(
            current_graph,
            current_phase,
            verification_evidence_store,
            current_trust_model
        )

        # Check transition
        new_phase, transitioned, reason = phase_controller.check_phase_transition(
            current_phase,
            confidence_state
        )

        logger.info(f"Phase transition check: {reason}")

        return jsonify({
            'success': True,
            'current_phase': current_phase.value,
            'new_phase': new_phase.value,
            'transitioned': transitioned,
            'reason': reason,
            'confidence': confidence_state.confidence,
            'threshold': current_phase.confidence_threshold
        })

    except Exception as exc:
        logger.error(f"Error checking phase transition: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


@app.route('/api/confidence-engine/phase/progress', methods=['GET'])
def get_phase_progress():
    """Get phase progress"""
    try:
        phase_str = request.args.get('phase', 'expand')
        phase = Phase(phase_str)

        progress = phase_controller.get_phase_progress(phase)

        return jsonify({
            'success': True,
            'progress': progress
        })

    except Exception as exc:
        logger.error(f"Error getting phase progress: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


@app.route('/api/confidence-engine/phase/history', methods=['GET'])
def get_phase_history():
    """Get phase transition history"""
    try:
        history = phase_controller.get_phase_history()

        return jsonify({
            'success': True,
            'history': history,
            'transition_count': len(history)
        })

    except Exception as exc:
        logger.error(f"Error getting phase history: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


# ============================================================================
# COMPLETE STATE ENDPOINT
# ============================================================================

@app.route('/api/confidence-engine/state/complete', methods=['POST'])
def get_complete_state():
    """Get complete confidence engine state"""
    try:
        data = request.json
        tenant_id = _get_tenant_id()
        current_graph = _get_tenant_graph(tenant_id)
        current_trust_model = _get_tenant_trust_model(tenant_id)
        verification_evidence_store = _get_tenant_evidence(tenant_id)
        phase = Phase(data.get('phase', 'expand'))
        gate_satisfaction = data.get('gate_satisfaction', 0.0)
        unknowns = data.get('unknowns', 0)

        # Compute all components
        confidence_state = confidence_calculator.compute_confidence(
            current_graph,
            phase,
            verification_evidence_store,
            current_trust_model
        )

        murphy_index = murphy_calculator.calculate_murphy_index(
            current_graph,
            confidence_state,
            phase
        )

        authority_state = authority_mapper.map_authority(
            confidence_state,
            murphy_index,
            gate_satisfaction,
            unknowns
        )

        # Graph analysis
        is_valid, errors = graph_analyzer.validate_dag(current_graph)
        contradictions = graph_analyzer.detect_contradictions(current_graph)

        return jsonify({
            'success': True,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'confidence_state': confidence_state.to_dict(),
            'murphy_index': murphy_index,
            'authority_state': authority_state.to_dict(),
            'graph_stats': {
                'total_nodes': len(current_graph.nodes),
                'is_valid_dag': is_valid,
                'contradiction_count': len(contradictions),
                'verified_artifacts': confidence_state.verified_artifacts
            }
        })

    except Exception as exc:
        logger.error(f"Error getting complete state: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.route('/api/confidence-engine/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'confidence-engine',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'components': {
            'graph_analyzer': 'operational',
            'confidence_calculator': 'operational',
            'murphy_calculator': 'operational',
            'authority_mapper': 'operational',
            'phase_controller': 'operational'
        }
    })


# ============================================================================
# RESET ENDPOINT (for testing)
# ============================================================================

@app.route('/api/confidence-engine/reset', methods=['POST'])
def reset_state():
    """Reset all state (for testing)"""
    tenant_id = _get_tenant_id()
    with _tenant_lock:
        _tenant_graphs[tenant_id] = ArtifactGraph()
        _tenant_trust_models[tenant_id] = TrustModel()
        _tenant_evidence[tenant_id] = []

    logger.info(f"Reset confidence engine state (tenant={tenant_id})")

    return jsonify({
        'success': True,
        'message': 'State reset successfully'
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8055, debug=is_debug_mode())
