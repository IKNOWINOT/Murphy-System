"""
Confidence Engine API Server
REST API for confidence, risk, and authority computation
"""

from flask import Flask, request, jsonify, g
from flask_cors import CORS
from typing import Dict, Any, List
import logging
from datetime import datetime

from confidence_engine.models import (
    ArtifactNode,
    ArtifactGraph,
    ArtifactType,
    ArtifactSource,
    VerificationEvidence,
    VerificationResult,
    SourceTrust,
    TrustModel,
    Phase
)
from confidence_engine.graph_analyzer import GraphAnalyzer
from confidence_engine.confidence_calculator import ConfidenceCalculator
from confidence_engine.murphy_calculator import MurphyCalculator
from confidence_engine.authority_mapper import AuthorityMapper
from confidence_engine.phase_controller import PhaseController
from src.security_plane.middleware import AuthenticationMiddleware, SecurityMiddlewareConfig, SecurityContext
from src.config import settings


# Initialize Flask app
app = Flask(__name__)

# Configure CORS with specific origins from config
cors_origins = settings.cors_origins.split(",") if settings.cors_origins != "*" else "*"
CORS(app, origins=cors_origins)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize security middleware
security_config = SecurityMiddlewareConfig(
    require_authentication=True,
    allow_human_auth=True,
    allow_machine_auth=True,
    enable_audit_logging=True
)
auth_middleware = AuthenticationMiddleware(security_config)

# Initialize components
graph_analyzer = GraphAnalyzer()
confidence_calculator = ConfidenceCalculator()
murphy_calculator = MurphyCalculator()
authority_mapper = AuthorityMapper()
phase_controller = PhaseController()

# Per-tenant state management (fixes ARCH-003 - tenant isolation)
tenant_graphs: Dict[str, ArtifactGraph] = {}
tenant_trust_models: Dict[str, TrustModel] = {}
tenant_verification_evidence: Dict[str, List[VerificationEvidence]] = {}

# Helper function to get tenant-specific state
def get_tenant_state(tenant_id: str) -> tuple:
    &quot;&quot;&quot;Get or create tenant-specific state&quot;&quot;&quot;
    if tenant_id not in tenant_graphs:
        tenant_graphs[tenant_id] = ArtifactGraph()
        tenant_trust_models[tenant_id] = TrustModel()
        tenant_verification_evidence[tenant_id] = []
    return (
        tenant_graphs[tenant_id],
        tenant_trust_models[tenant_id],
        tenant_verification_evidence[tenant_id]
    )

# Helper function to extract tenant_id from request
def get_tenant_id_from_request() -> str:
    &quot;&quot;&quot;Extract tenant_id from authenticated request context&quot;&quot;&quot;
    # In production, this would extract from JWT token or session
    # For now, use a default or extract from request headers
    return request.headers.get('X-Tenant-ID', 'default')

# Authentication before_request hook
@app.before_request
def authenticate_request():
    &quot;&quot;&quot;Authenticate all incoming requests&quot;&quot;&quot;
    # Skip authentication for health checks
    if request.path == '/health':
        return None
    
    # Create security context
    context = SecurityContext()
    
    # Prepare request data for authentication
    request_data = {
        'auth_type': request.headers.get('X-Auth-Type'),
        'credentials': {
            'user_id': request.headers.get('X-User-ID'),
            'machine_id': request.headers.get('X-Machine-ID'),
            'token': request.headers.get('Authorization', '').replace('Bearer ', '')
        }
    }
    
    # Authenticate request
    if not auth_middleware.authenticate_request(request_data, context):
        logger.warning(f'Authentication failed for {request.path}')
        return jsonify({
            'error': 'Authentication required',
            'message': 'Please provide valid authentication credentials'
        }), 401
    
    # Store authenticated context in Flask g object
    g.authenticated = context.authenticated
    g.identity = context.identity
    g.tenant_id = get_tenant_id_from_request()
    
    return None


# ============================================================================
# ARTIFACT GRAPH ENDPOINTS
# ============================================================================

@app.route('/api/confidence-engine/artifacts/add', methods=['POST'])
def add_artifact():
    """Add artifact to graph"""
    try:
        data = request.json
        
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
        tenant_graphs[g.tenant_id].add_node(node)
        
        # Validate DAG
        is_valid, errors = graph_analyzer.validate_dag(tenant_graphs[g.tenant_id])
        
        if not is_valid:
            # Remove node if it breaks DAG
            del tenant_graphs[g.tenant_id].nodes[node.id]
            return jsonify({
                'success': False,
                'error': 'Adding this artifact would break DAG structure',
                'details': errors
            }), 400
        
        logger.info(f"Added artifact {node.id} to graph")
        
        return jsonify({
            'success': True,
            'artifact_id': node.id,
            'graph_stats': {
                'total_nodes': len(tenant_graphs[g.tenant_id].nodes),
                'is_dag': is_valid
            }
        })
    
    except Exception as e:
        logger.error(f"Error adding artifact: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/confidence-engine/artifacts/graph', methods=['GET'])
def get_graph():
    """Get complete artifact graph"""
    try:
        return jsonify({
            'success': True,
            'graph': tenant_graphs[g.tenant_id].to_dict()
        })
    except Exception as e:
        logger.error(f"Error getting graph: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/confidence-engine/artifacts/analyze', methods=['GET'])
def analyze_graph():
    """Analyze graph structure"""
    try:
        # Validate DAG
        is_valid, errors = graph_analyzer.validate_dag(tenant_graphs[g.tenant_id])
        
        # Detect contradictions
        contradictions = graph_analyzer.detect_contradictions(tenant_graphs[g.tenant_id])
        
        # Calculate entropy
        entropy = graph_analyzer.calculate_entropy(tenant_graphs[g.tenant_id])
        
        # Analyze dependencies
        dep_analysis = graph_analyzer.analyze_dependencies(tenant_graphs[g.tenant_id])
        
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
    except Exception as e:
        logger.error(f"Error analyzing graph: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# VERIFICATION ENDPOINTS
# ============================================================================

@app.route('/api/confidence-engine/verification/add', methods=['POST'])
def add_verification():
    """Add verification evidence"""
    try:
        data = request.json
        
        evidence = VerificationEvidence(
            artifact_id=data['artifact_id'],
            result=VerificationResult(data['result']),
            stability_score=data['stability_score'],
            confidence_boost=data.get('confidence_boost', 0.0),
            details=data.get('details', {})
        )
        
        tenant_verification_evidence[g.tenant_id].append(evidence)
        
        logger.info(f"Added verification evidence for artifact {evidence.artifact_id}")
        
        return jsonify({
            'success': True,
            'evidence_count': len(tenant_verification_evidence[g.tenant_id])
        })
    
    except Exception as e:
        logger.error(f"Error adding verification: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/confidence-engine/verification/list', methods=['GET'])
def list_verification():
    """List all verification evidence"""
    try:
        return jsonify({
            'success': True,
            'evidence': [e.to_dict() for e in tenant_verification_evidence[g.tenant_id]],
            'count': len(tenant_verification_evidence[g.tenant_id])
        })
    except Exception as e:
        logger.error(f"Error listing verification: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# TRUST MODEL ENDPOINTS
# ============================================================================

@app.route('/api/confidence-engine/trust/add-source', methods=['POST'])
def add_trust_source():
    """Add or update trust source"""
    try:
        data = request.json
        
        source = SourceTrust(
            source_id=data['source_id'],
            source_type=ArtifactSource(data['source_type']),
            trust_weight=data['trust_weight'],
            volatility=data.get('volatility', 0.1)
        )
        
        tenant_trust_models[g.tenant_id].add_source(source)
        
        logger.info(f"Added trust source {source.source_id}")
        
        return jsonify({
            'success': True,
            'source_id': source.source_id,
            'trust_weight': source.trust_weight
        })
    
    except Exception as e:
        logger.error(f"Error adding trust source: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/confidence-engine/trust/update', methods=['POST'])
def update_trust():
    """Update trust based on outcome"""
    try:
        data = request.json
        source_id = data['source_id']
        success = data['success']
        
        tenant_trust_models[g.tenant_id].update_source(source_id, success)
        
        logger.info(f"Updated trust for {source_id}: success={success}")
        
        return jsonify({
            'success': True,
            'source_id': source_id,
            'new_trust': tenant_trust_models[g.tenant_id].get_trust(source_id)
        })
    
    except Exception as e:
        logger.error(f"Error updating trust: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/confidence-engine/trust/model', methods=['GET'])
def get_trust_model():
    """Get complete trust model"""
    try:
        return jsonify({
            'success': True,
            'trust_model': tenant_trust_models[g.tenant_id].to_dict()
        })
    except Exception as e:
        logger.error(f"Error getting trust model: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# CONFIDENCE COMPUTATION ENDPOINTS
# ============================================================================

@app.route('/api/confidence-engine/confidence/compute', methods=['POST'])
def compute_confidence():
    """Compute confidence state"""
    try:
        data = request.json
        phase = Phase(data.get('phase', 'expand'))
        
        # Compute confidence
        confidence_state = confidence_calculator.compute_confidence(
            tenant_graphs[g.tenant_id],
            phase,
            tenant_verification_evidence[g.tenant_id],
            tenant_trust_models[g.tenant_id]
        )
        
        logger.info(f"Computed confidence: {confidence_state.confidence:.3f}")
        
        return jsonify({
            'success': True,
            'confidence_state': confidence_state.to_dict()
        })
    
    except Exception as e:
        logger.error(f"Error computing confidence: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# MURPHY INDEX ENDPOINTS
# ============================================================================

@app.route('/api/confidence-engine/murphy/compute', methods=['POST'])
def compute_murphy():
    """Compute Murphy index"""
    try:
        data = request.json
        phase = Phase(data.get('phase', 'expand'))
        
        # First compute confidence
        confidence_state = confidence_calculator.compute_confidence(
            tenant_graphs[g.tenant_id],
            phase,
            tenant_verification_evidence[g.tenant_id],
            tenant_trust_models[g.tenant_id]
        )
        
        # Compute Murphy index
        murphy_index = murphy_calculator.calculate_murphy_index(
            tenant_graphs[g.tenant_id],
            confidence_state,
            phase
        )
        
        # Get failure mode details
        failure_modes = murphy_calculator.get_failure_mode_details(
            tenant_graphs[g.tenant_id],
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
    
    except Exception as e:
        logger.error(f"Error computing Murphy index: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# AUTHORITY ENDPOINTS
# ============================================================================

@app.route('/api/confidence-engine/authority/compute', methods=['POST'])
def compute_authority():
    """Compute authority state"""
    try:
        data = request.json
        phase = Phase(data.get('phase', 'expand'))
        gate_satisfaction = data.get('gate_satisfaction', 0.0)
        unknowns = data.get('unknowns', 0)
        
        # Compute confidence
        confidence_state = confidence_calculator.compute_confidence(
            tenant_graphs[g.tenant_id],
            phase,
            tenant_verification_evidence[g.tenant_id],
            tenant_trust_models[g.tenant_id]
        )
        
        # Compute Murphy index
        murphy_index = murphy_calculator.calculate_murphy_index(
            tenant_graphs[g.tenant_id],
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
    
    except Exception as e:
        logger.error(f"Error computing authority: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# PHASE CONTROL ENDPOINTS
# ============================================================================

@app.route('/api/confidence-engine/phase/check-transition', methods=['POST'])
def check_phase_transition():
    """Check if phase transition should occur"""
    try:
        data = request.json
        current_phase = Phase(data['current_phase'])
        
        # Compute confidence
        confidence_state = confidence_calculator.compute_confidence(
            tenant_graphs[g.tenant_id],
            current_phase,
            tenant_verification_evidence[g.tenant_id],
            tenant_trust_models[g.tenant_id]
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
    
    except Exception as e:
        logger.error(f"Error checking phase transition: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


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
    
    except Exception as e:
        logger.error(f"Error getting phase progress: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


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
    
    except Exception as e:
        logger.error(f"Error getting phase history: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# COMPLETE STATE ENDPOINT
# ============================================================================

@app.route('/api/confidence-engine/state/complete', methods=['POST'])
def get_complete_state():
    """Get complete confidence engine state"""
    try:
        data = request.json
        phase = Phase(data.get('phase', 'expand'))
        gate_satisfaction = data.get('gate_satisfaction', 0.0)
        unknowns = data.get('unknowns', 0)
        
        # Compute all components
        confidence_state = confidence_calculator.compute_confidence(
            tenant_graphs[g.tenant_id],
            phase,
            tenant_verification_evidence[g.tenant_id],
            tenant_trust_models[g.tenant_id]
        )
        
        murphy_index = murphy_calculator.calculate_murphy_index(
            tenant_graphs[g.tenant_id],
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
        is_valid, errors = graph_analyzer.validate_dag(tenant_graphs[g.tenant_id])
        contradictions = graph_analyzer.detect_contradictions(tenant_graphs[g.tenant_id])
        
        return jsonify({
            'success': True,
            'timestamp': datetime.now().isoformat(),
            'confidence_state': confidence_state.to_dict(),
            'murphy_index': murphy_index,
            'authority_state': authority_state.to_dict(),
            'graph_stats': {
                'total_nodes': len(tenant_graphs[g.tenant_id].nodes),
                'is_valid_dag': is_valid,
                'contradiction_count': len(contradictions),
                'verified_artifacts': confidence_state.verified_artifacts
            }
        })
    
    except Exception as e:
        logger.error(f"Error getting complete state: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.route('/api/confidence-engine/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'confidence-engine',
        'timestamp': datetime.now().isoformat(),
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
        &quot;&quot;&quot;Reset all state (for testing)&quot;&quot;&quot;
        tenant_id = g.tenant_id
        tenant_graphs[tenant_id] = ArtifactGraph()
        tenant_trust_models[tenant_id] = TrustModel()
        tenant_verification_evidence[tenant_id] = []
        
        logger.info(f&quot;Reset confidence engine state for tenant {tenant_id}&quot;)
        
        return jsonify({
            'success': True,
            'message': 'State reset successfully'
        })
        'message': 'State reset successfully'
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8055, debug=True)