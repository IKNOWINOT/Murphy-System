"""
Murphy System - Complete Backend Server
Integrates all systems: Monitoring, Artifacts, Shadow Agents, Cooperative Swarm, LLM
"""

from flask import Flask, request, jsonify, g, send_file
from flask_socketio import SocketIO, emit
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import logging
from datetime import datetime
import uuid
import threading
import os

# LLM Providers
from llm_providers import LLMManager
from librarian_system import LibrarianSystem

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# PASS-THROUGH DECORATORS (for when auth is not available)
# ============================================================================

def pass_through_decorator(*args, **kwargs):
    """Decorator that passes through when auth is not available"""
    def decorator(func):
        return func
    return decorator

# Initialize rate limiter
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)
logger.info("✓ Rate limiter initialized")

# ============================================================================
# AUTHENTICATION SYSTEM
# ============================================================================

try:
    from auth_system import init_auth_system, get_auth_system
    from auth_middleware import (
        require_auth, 
        optional_auth, 
        validate_input, 
        rate_limit,
        validate_login_request,
        validate_init_request,
        validate_artifact_request
    )
    AUTH_AVAILABLE = True
    auth_system = init_auth_system()
    logger.info("✓ Authentication System loaded successfully")
except ImportError as e:
    logger.error(f"✗ Failed to load Authentication System: {e}")
    AUTH_AVAILABLE = False
    auth_system = None

# ============================================================================
# DATABASE INTEGRATION
# ============================================================================

try:
    from database_integration import get_database_manager
    db_manager = get_database_manager()
    DB_AVAILABLE = True
    logger.info("✓ Database Integration loaded successfully")

except ImportError as e:
    logger.error(f"✗ Failed to load Database Integration: {e}")
    DB_AVAILABLE = False
    db_manager = None

# Global system state
system_initialized = False
agents = []
states = []
components = []
gates = []

# Thread safety locks
state_lock = threading.Lock()
agents_lock = threading.Lock()
components_lock = threading.Lock()
gates_lock = threading.Lock()

# ============================================================================
# MONITORING SYSTEM INTEGRATION
# ============================================================================

try:
    from monitoring_system import MonitoringSystem
    from health_monitor import HealthMonitor
    from anomaly_detector import AnomalyDetector
    from optimization_engine import OptimizationEngine
    MONITORING_AVAILABLE = True
    logger.info("✓ Monitoring components loaded successfully")
except ImportError as e:
    logger.error(f"✗ Failed to load Monitoring components: {e}")
    MONITORING_AVAILABLE = False

# Initialize Monitoring System
monitoring_system = None
health_monitor = None
anomaly_detector = None
optimization_engine = None

if MONITORING_AVAILABLE:
    try:
        # Initialize in correct order: monitoring_system -> health_monitor -> anomaly_detector -> optimization_engine
        monitoring_system = MonitoringSystem()
        health_monitor = HealthMonitor(monitoring_system)
        anomaly_detector = AnomalyDetector(monitoring_system)
        optimization_engine = OptimizationEngine(monitoring_system)
        logger.info("✓ Monitoring systems initialized")
    except Exception as e:
        logger.error(f"✗ Failed to initialize monitoring systems: {e}")

# ============================================================================
# STABILITY-BASED ATTENTION SYSTEM INTEGRATION
# ============================================================================

try:
    from STABILITY_BASED_ATTENTION_SYSTEM import (
        StabilityBasedAttentionSystem,
        InternalRepresentation,
        CognitiveRole,
        create_candidate_representations
    )
    ATTENTION_AVAILABLE = True
    logger.info("✓ Stability-Based Attention System loaded successfully")
except ImportError as e:
    logger.error(f"✗ Failed to load Attention components: {e}")
    ATTENTION_AVAILABLE = False

# Initialize Attention System
attention_system = None

if ATTENTION_AVAILABLE:
    try:
        attention_system = StabilityBasedAttentionSystem(
            window_size=10,
            agreement_threshold=0.3
        )
        logger.info("✓ Attention system initialized")
    except Exception as e:
        logger.error(f"✗ Failed to initialize attention system: {e}")

# ============================================================================
# ARTIFACT GENERATION SYSTEM INTEGRATION
# ============================================================================

try:
    from artifact_generation_system import ArtifactGenerationSystem, ArtifactType
    from artifact_manager import ArtifactManager
    ARTIFACTS_AVAILABLE = True
    logger.info("✓ Artifact components loaded successfully")
except ImportError as e:
    logger.error(f"✗ Failed to load Artifact components: {e}")
    ARTIFACTS_AVAILABLE = False

try:
    # Import integrated module system
    from integrated_module_system import (
        IntegratedModuleCompiler,
        ModuleRegistry,
        ModuleManager,
        ModuleSpec,
        GitHubRepoAnalyzer,
        StaticCodeAnalyzer
    )
    MODULES_AVAILABLE = True
    logger.info("✓ Module System loaded successfully")
except ImportError as e:
    logger.error(f"✗ Failed to load Module System: {e}")
    MODULES_AVAILABLE = False

# ============================================================================
# COMMAND SYSTEM & LIBRARIAN INTEGRATION
# ============================================================================

try:
    from command_system import (
        get_command_registry,
        execute_command
    )
    from librarian_adapter import get_librarian_adapter
    
    command_registry = get_command_registry()
    librarian_adapter = get_librarian_adapter()
    
    # Initialize librarian
    librarian_adapter.initialize()
    
    # Connect command registry with librarian
    command_registry.librarian_adapter = librarian_adapter
    
    COMMAND_SYSTEM_AVAILABLE = True
    logger.info("✓ Command System and Librarian loaded successfully")
except ImportError as e:
    logger.error(f"✗ Failed to load Command System: {e}")
    COMMAND_SYSTEM_AVAILABLE = False
    command_registry = None
    librarian_adapter = None

if ARTIFACTS_AVAILABLE:
    try:
        artifact_generation_system = ArtifactGenerationSystem()
        
        # Initialize module system
        module_compiler = IntegratedModuleCompiler()
        module_registry = ModuleRegistry()
        module_manager = ModuleManager(module_registry, command_registry=get_command_registry() if COMMAND_SYSTEM_AVAILABLE else None)
        artifact_manager = ArtifactManager()
        logger.info("✓ Artifact systems initialized")
    except Exception as e:
        logger.error(f"✗ Failed to initialize artifact systems: {e}")

# ============================================================================
# SHADOW AGENT SYSTEM INTEGRATION
# ============================================================================

try:
    from shadow_agent_system import ShadowAgentSystem, ObservationType
    from learning_engine import LearningEngine
    SHADOW_AGENTS_AVAILABLE = True
    
    # Module system
    try:
        from integrated_module_system import IntegratedModuleCompiler, ModuleRegistry, ModuleManager
        MODULES_AVAILABLE = True
    except ImportError:
        MODULES_AVAILABLE = False
    logger.info("✓ Shadow Agent components loaded successfully")
except ImportError as e:
    logger.error(f"✗ Failed to load Shadow Agent components: {e}")
    SHADOW_AGENTS_AVAILABLE = False
    
    # Module system
    MODULES_AVAILABLE = False

# Initialize Shadow Agent System
shadow_agent_system = None
learning_engine = None

if SHADOW_AGENTS_AVAILABLE:
    try:
        shadow_agent_system = ShadowAgentSystem()
        learning_engine = LearningEngine()
        logger.info("✓ Shadow Agent systems initialized")
    except Exception as e:
        logger.error(f"✗ Failed to initialize shadow agent systems: {e}")

# ============================================================================
# COOPERATIVE SWARM SYSTEM INTEGRATION
# ============================================================================

try:
    from cooperative_swarm_system import CooperativeSwarmSystem, Task, TaskStatus, HandoffType
    from agent_handoff_manager import AgentHandoffManager, HandoffContext
    from workflow_orchestrator import WorkflowOrchestrator, WorkflowDefinition, WorkflowExecution
    COOPERATIVE_SWARM_AVAILABLE = True
    logger.info("✓ Cooperative Swarm components loaded successfully")
except ImportError as e:
    logger.error(f"✗ Failed to load Cooperative Swarm components: {e}")
    COOPERATIVE_SWARM_AVAILABLE = False

# Initialize Cooperative Swarm System
cooperative_swarm = None
handoff_manager = None
workflow_orchestrator = None

if COOPERATIVE_SWARM_AVAILABLE:
    try:
        # Initialize in correct order: cooperative_swarm -> handoff_manager -> orchestrator
        cooperative_swarm = CooperativeSwarmSystem()
        handoff_manager = AgentHandoffManager(cooperative_swarm)
        workflow_orchestrator = WorkflowOrchestrator(cooperative_swarm, handoff_manager)
        logger.info("✓ Cooperative Swarm systems initialized")
    except Exception as e:
        logger.error(f"✗ Failed to initialize cooperative swarm systems: {e}")

# ============================================================================
# LLM INTEGRATION
# ============================================================================

LLM_AVAILABLE = False  # Will try to load later

LIBRARIAN_AVAILABLE = False  # Will try to load later
librarian_system = None

# ============================================================================
# FRONTEND SERVING
# ============================================================================

@app.route('/')
def serve_frontend():
    """Serve the frontend HTML page."""
    try:
        return send_file('/workspace/murphy_complete_v2.html')
    except Exception as e:
        logger.error(f"Error serving frontend: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/murphy_complete_v2.html')
def serve_frontend_explicit():
    """Serve the frontend HTML page explicitly."""
    try:
        return send_file('/workspace/murphy_complete_v2.html')
    except Exception as e:
        logger.error(f"Error serving frontend: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ============================================================================
# ============================================================================
# SERVE JAVASCRIPT PANEL FILES
# ============================================================================

@app.route('/artifact_panel.js')
def serve_artifact_panel():
    """Serve the artifact panel JavaScript file."""
    try:
        return send_file('/workspace/artifact_panel.js', mimetype='application/javascript')
    except Exception as e:
        logger.error(f"Error serving artifact_panel.js: {e}")
        return jsonify({'success': False, 'error': str(e)}), 404

@app.route('/shadow_agent_panel.js')
def serve_shadow_agent_panel():
    """Serve the shadow agent panel JavaScript file."""
    try:
        return send_file('/workspace/shadow_agent_panel.js', mimetype='application/javascript')
    except Exception as e:
        logger.error(f"Error serving shadow_agent_panel.js: {e}")
        return jsonify({'success': False, 'error': str(e)}), 404

@app.route('/document_editor_panel.js')
def serve_document_editor_panel():
    """Serve the document editor panel JavaScript file."""
    try:
        return send_file('/workspace/document_editor_panel.js', mimetype='application/javascript')
    except Exception as e:
        logger.error(f"Error serving document_editor_panel.js: {e}")
        return jsonify({'success': False, 'error': str(e)}), 404

@app.route('/monitoring_panel.js')
def serve_monitoring_panel():
    """Serve the monitoring panel JavaScript file."""
    try:
        return send_file('/workspace/monitoring_panel.js', mimetype='application/javascript')
    except Exception as e:
        logger.error(f"Error serving monitoring_panel.js: {e}")
        return jsonify({'success': False, 'error': str(e)}), 404

@app.route('/plan_review_panel.js')
def serve_plan_review_panel():
    """Serve the plan review panel JavaScript file."""
    try:
        return send_file('/workspace/plan_review_panel.js', mimetype='application/javascript')
    except Exception as e:
        logger.error(f"Error serving plan_review_panel.js: {e}")
        return jsonify({'success': False, 'error': str(e)}), 404

@app.route('/librarian_panel.js')
def serve_librarian_panel():
    """Serve the librarian panel JavaScript file."""
    try:
        return send_file('/workspace/librarian_panel.js', mimetype='application/javascript')
    except Exception as e:
        logger.error(f"Error serving librarian_panel.js: {e}")
        return jsonify({'success': False, 'error': str(e)}), 404

# EXISTING ENDPOINTS (from murphy_backend_v2.py)
# ============================================================================

@app.route('/api/status', methods=['GET'])
def get_status():
    """Get system status"""
    
    # Get LLM status details
    llms_info = {
        'groq': {
            'status': 'inactive',
            'model': 'None',
            'keys': 0
        },
        'aristotle': {
            'status': 'inactive',
            'model': 'None'
        },
        'onboard': {
            'status': 'inactive'
        }
    }
    
    if LLM_AVAILABLE and llm_manager:
        status = llm_manager.get_status()
        llms_info['groq']['status'] = 'active' if status.get('available_providers', 0) > 0 else 'inactive'
        llms_info['groq']['model'] = 'llama-3.3-70b-versatile'
        llms_info['groq']['keys'] = len(groq_keys) if 'groq_keys' in globals() else 0
    
    response = {
        'success': True,
        'message': 'Murphy System Complete Backend',
        'version': '3.0.0',
        'status': 'Operational' if system_initialized else 'Not Initialized',
        'initialized': system_initialized,
        'components': {
            'monitoring': MONITORING_AVAILABLE,
            'artifacts': ARTIFACTS_AVAILABLE,
            'shadow_agents': SHADOW_AGENTS_AVAILABLE,
            'cooperative_swarm': COOPERATIVE_SWARM_AVAILABLE,
            'llm': LLM_AVAILABLE,
            'librarian': LIBRARIAN_AVAILABLE,
            'authentication': AUTH_AVAILABLE,
            'database': DB_AVAILABLE,
            'modules': MODULES_AVAILABLE,
            'command_system': COMMAND_SYSTEM_AVAILABLE
        },
        'llms': llms_info,
        'systems_initialized': system_initialized,
        'timestamp': datetime.now().isoformat()
    }
    
    # Add metrics if available
    if DB_AVAILABLE and db_manager:
        try:
            stats = db_manager.get_statistics()
            response['metrics'] = {
                'states': stats.get('states', 0),
                'agents': stats.get('agents', 0),
                'gates': stats.get('gates', 0),
                'artifacts': stats.get('artifacts', 0)
            }
        except:
            pass
    
    return jsonify(response)

@app.route('/api/initialize', methods=['POST'])
@validate_input(validate_init_request)
def initialize_system():
    """Initialize the system with demo data (NO AUTHENTICATION REQUIRED)"""
    global system_initialized
    
    if system_initialized:
        # Return current database statistics
        if DB_AVAILABLE and db_manager:
            stats = db_manager.get_statistics()
            return jsonify({
                'success': True,
                'message': 'System already initialized',
                'agents_count': stats['agents_count'],
                'states_count': stats['states_count']
            })
        else:
            return jsonify({
                'success': True,
                'message': 'System already initialized (in-memory mode)',
                'agents_count': len(agents),
                'states_count': len(states)
            })
    
    try:
        # Use database if available
        if DB_AVAILABLE and db_manager:
            result = db_manager.initialize_system_data()
            system_initialized = True
            return jsonify(result)
        
        # Fall back to in-memory initialization
        else:
            # Acquire locks for thread safety
            with state_lock, agents_lock, components_lock, gates_lock:
                # Create demo agents
                agents = [
                    {'id': 'agent-1', 'name': 'Executive Agent', 'role': 'planning', 'status': 'active'},
                    {'id': 'agent-2', 'name': 'Engineering Agent', 'role': 'technical', 'status': 'active'},
                    {'id': 'agent-3', 'name': 'Financial Agent', 'role': 'finance', 'status': 'active'},
                    {'id': 'agent-4', 'name': 'Legal Agent', 'role': 'legal', 'status': 'active'},
                    {'id': 'agent-5', 'name': 'Operations Agent', 'role': 'operations', 'status': 'active'}
                ]
                
                # Create initial state
                states = [
                    {
                        'id': 'state-1',
                        'name': 'Initial State',
                        'description': 'System initialization state',
                        'confidence': 0.85,
                        'parent_id': None,
                        'children': [],
                        'created_at': datetime.now().isoformat()
                    }
                ]
                
                # Create components
                components = [
                    {'id': 'comp-1', 'name': 'LLM Router', 'status': 'active'},
                    {'id': 'comp-2', 'name': 'State Machine', 'status': 'active'},
                    {'id': 'comp-3', 'name': 'Agent Manager', 'status': 'active'}
                ]
                
                # Create gates
                gates = [
                    {'id': 'gate-1', 'name': 'Safety Gate 1', 'status': 'active', 'threshold': 0.85},
                    {'id': 'gate-2', 'name': 'Quality Gate 1', 'status': 'active', 'threshold': 0.90}
                ]
                
                system_initialized = True
        
        # Shadow agents are automatically initialized in __init__ via _create_default_agents()
        # No additional initialization needed
        
        # Broadcast initialization event
        socketio.emit('system_initialized', {
            'agents': agents,
            'states': states,
            'components': components,
            'gates': gates
        })
        
        logger.info(f"✓ System initialized by user: {getattr(g, 'user', {}).get('username', 'unknown')}")
        
        return jsonify({
            'success': True,
            'message': 'System initialized successfully',
            'agents_count': len(agents),
            'states_count': len(states),
            'components_count': len(components),
            'gates_count': len(gates)
        })
    except Exception as e:
        logger.error(f"Error initializing system: {e}")
        return jsonify({
            'success': False,
            'message': f'Failed to initialize: {str(e)}'
        }), 500

@app.route('/api/states', methods=['GET'])
def get_states():
    """Get all states"""
    if DB_AVAILABLE and db_manager:
        return jsonify({
            'success': True,
            'states': db_manager.get_states()
        })
    return jsonify({
        'success': True,
        'states': states
    })

@app.route('/api/states/<state_id>/evolve', methods=['POST'])
def evolve_state_endpoint(state_id):
    """Evolve state into child states"""
    if DB_AVAILABLE and db_manager:
        children = db_manager.evolve_state(state_id)
        
        # Broadcast update via WebSocket
        if hasattr(socketio, 'emit'):
            socketio.emit('state_evolved', {
                'state_id': state_id,
                'children': children
            })
        
        return jsonify({
            'success': True,
            'state_id': state_id,
            'children': children,
            'message': f'Evolved {len(children)} child states'
        })
    
    # Fallback to in-memory
    state = states.get(state_id)
    if not state:
        return jsonify({'success': False, 'error': 'State not found'}), 404
    
    return jsonify({
        'success': False,
        'error': 'Database not available for state evolution'
    }), 503

@app.route('/api/states/<state_id>/regenerate', methods=['POST'])
def regenerate_state_endpoint(state_id):
    """Regenerate state with new confidence"""
    if DB_AVAILABLE and db_manager:
        new_state = db_manager.regenerate_state(state_id)
        
        if not new_state:
            return jsonify({'success': False, 'error': 'State not found'}), 404
        
        # Broadcast update via WebSocket
        if hasattr(socketio, 'emit'):
            socketio.emit('state_regenerated', {
                'state_id': state_id,
                'state': new_state
            })
        
        return jsonify({
            'success': True,
            'state_id': state_id,
            'state': new_state,
            'message': 'State regenerated successfully'
        })
    
    # Fallback to in-memory
    return jsonify({
        'success': False,
        'error': 'Database not available for state regeneration'
    }), 503

@app.route('/api/states/<state_id>/rollback', methods=['POST'])
def rollback_state_endpoint(state_id):
    """Rollback state to parent"""
    if DB_AVAILABLE and db_manager:
        parent_state = db_manager.rollback_state(state_id)
        
        if not parent_state:
            if not db_manager.get_state_by_id(state_id):
                return jsonify({'success': False, 'error': 'State not found'}), 404
            return jsonify({'success': False, 'error': 'Cannot rollback - no parent'}), 400
        
        # Broadcast update via WebSocket
        if hasattr(socketio, 'emit'):
            socketio.emit('state_rolledback', {
                'state_id': state_id,
                'parent_state': parent_state
            })
        
        return jsonify({
            'success': True,
            'state_id': state_id,
            'parent_state': parent_state,
            'message': 'Rolled back to parent state'
        })
    
    # Fallback to in-memory
    return jsonify({
        'success': False,
        'error': 'Database not available for state rollback'
    }), 503

@app.route('/api/agents', methods=['GET'])
def get_agents():
    """Get all agents"""
    if DB_AVAILABLE and db_manager:
        return jsonify({
            'success': True,
            'agents': db_manager.get_agents()
        })
    return jsonify({
        'success': True,
        'agents': agents
    })
    return jsonify({
        'success': True,
        'agents': agents
    })


# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@app.route('/api/auth/login', methods=['POST'])
@rate_limit(limit=5, per=60)  # 5 login attempts per minute
@validate_input(validate_login_request)
def login():
    """Authenticate user and return JWT token"""
    if not AUTH_AVAILABLE:
        return jsonify({
            'success': False,
            'message': 'Authentication system not available'
        }), 503
    
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({
                'success': False,
                'error': 'missing_credentials',
                'message': 'Username and password are required'
            }), 400
        
        # Verify credentials
        if not auth_system.verify_password(username, password):
            logger.warning(f"Failed login attempt for user: {username}")
            return jsonify({
                'success': False,
                'error': 'invalid_credentials',
                'message': 'Invalid username or password'
            }), 401
        
        # Generate token
        token = auth_system.generate_token(username)
        
        logger.info(f"Successful login for user: {username}")
        
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'token': token,
            'user': {
                'username': username,
                'role': auth_system.get_user_role(username)
            }
        })
    except Exception as e:
        logger.error(f"Error during login: {e}")
        return jsonify({
            'success': False,
            'message': 'Login failed'
        }), 500


@app.route('/api/auth/logout', methods=['POST'])
@require_auth(auth_system if AUTH_AVAILABLE else None)
def logout():
    """Logout user by revoking token"""
    if not AUTH_AVAILABLE:
        return jsonify({
            'success': False,
            'message': 'Authentication system not available'
        }), 503
    
    try:
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header[7:]
            auth_system.revoke_token(token)
        
        logger.info(f"User logged out: {getattr(g, 'user', {}).get('username', 'unknown')}")
        
        return jsonify({
            'success': True,
            'message': 'Logout successful'
        })
    except Exception as e:
        logger.error(f"Error during logout: {e}")
        return jsonify({
            'success': False,
            'message': 'Logout failed'
        }), 500


@app.route('/api/auth/verify', methods=['POST'])
@optional_auth(auth_system if AUTH_AVAILABLE else None)
def verify_token():
    """Verify if current token is valid"""
    if not AUTH_AVAILABLE:
        return jsonify({
            'success': True,
            'authenticated': False,
            'message': 'Authentication system not available'
        })
    
    try:
        if hasattr(g, 'user'):
            return jsonify({
                'success': True,
                'authenticated': True,
                'user': g.user
            })
        else:
            return jsonify({
                'success': True,
                'authenticated': False,
                'message': 'No valid token provided'
            })
    except Exception as e:
        logger.error(f"Error during token verification: {e}")
        return jsonify({
            'success': False,
            'message': 'Verification failed'
        }), 500


@app.route('/api/auth/stats', methods=['GET'])
@require_auth(auth_system if AUTH_AVAILABLE else None, roles=['admin'])
def get_auth_stats():
    """Get authentication statistics (admin only)"""
    if not AUTH_AVAILABLE:
        return jsonify({
            'success': False,
            'message': 'Authentication system not available'
        }), 503
    
    try:
        stats = auth_system.get_stats()
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        logger.error(f"Error getting auth stats: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to get statistics'
        }), 500

# ============================================================================
# MONITORING ENDPOINTS (7 endpoints)
# ============================================================================

@app.route('/api/monitoring/health', methods=['GET'])
def get_monitoring_health():
    """Get system health status"""
    if not MONITORING_AVAILABLE or not health_monitor:
        return jsonify({
            'success': False,
            'message': 'Monitoring system not available'
        }), 503
    
    try:
        # CRITICAL: Execute health checks before getting summary
        health_monitor.check_all_components()
        health_summary = health_monitor.get_health_summary()
        return jsonify({
            'success': True,
            'health': health_summary
        })
    except Exception as e:
        logger.error(f"Error getting health: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/monitoring/metrics', methods=['GET'])
def get_monitoring_metrics():
    """Get performance metrics"""
    if not MONITORING_AVAILABLE or not monitoring_system:
        return jsonify({
            'success': False,
            'message': 'Monitoring system not available'
        }), 503
    
    try:
        metrics = monitoring_system.get_all_metrics()
        return jsonify({
            'success': True,
            'metrics': [m.to_dict() if hasattr(m, 'to_dict') else m for m in metrics]
        })
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/monitoring/anomalies', methods=['GET'])
def get_monitoring_anomalies():
    """Get detected anomalies"""
    if not MONITORING_AVAILABLE or not anomaly_detector:
        return jsonify({
            'success': False,
            'message': 'Anomaly detector not available'
        }), 503
    
    try:
        anomalies = anomaly_detector.get_detected_anomalies()
        return jsonify({
            'success': True,
            'anomalies': [a.to_dict() if hasattr(a, 'to_dict') else a for a in anomalies]
        })
    except Exception as e:
        logger.error(f"Error getting anomalies: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/monitoring/recommendations', methods=['GET'])
def get_monitoring_recommendations():
    """Get optimization recommendations"""
    if not MONITORING_AVAILABLE or not optimization_engine:
        return jsonify({
            'success': False,
            'message': 'Optimization engine not available'
        }), 503
    
    try:
        recommendations = optimization_engine.get_recommendations()
        return jsonify({
            'success': True,
            'recommendations': [r.to_dict() if hasattr(r, 'to_dict') else r for r in recommendations]
        })
    except Exception as e:
        logger.error(f"Error getting recommendations: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/monitoring/analyze', methods=['POST'])
@require_auth(auth_system if AUTH_AVAILABLE else None)
def run_monitoring_analysis():
    """Run monitoring analysis"""
    if not MONITORING_AVAILABLE:
        return jsonify({
            'success': False,
            'message': 'Monitoring system not available'
        }), 503
    
    try:
        # Run analysis
        results = {
            'health': 'healthy',
            'anomalies_count': 0,
            'recommendations_count': 0,
            'timestamp': datetime.now().isoformat()
        }
        
        if health_monitor:
            results['health'] = str(health_monitor.get_overall_health())
        
        if anomaly_detector:
            results['anomalies_count'] = len(anomaly_detector.get_detected_anomalies())
        
        if optimization_engine:
            results['recommendations_count'] = len(optimization_engine.get_recommendations())
        
        return jsonify({
            'success': True,
            'results': results
        })
    except Exception as e:
        logger.error(f"Error running analysis: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/monitoring/alerts', methods=['GET'])
def get_monitoring_alerts():
    """Get active alerts"""
    if not MONITORING_AVAILABLE:
        return jsonify({
            'success': False,
            'message': 'Monitoring system not available'
        }), 503
    
    try:
        alerts = []
        if anomaly_detector:
            anomalies = anomaly_detector.get_detected_anomalies()
            # Convert anomalies to alerts
            for anomaly in anomalies:
                alerts.append({
                    'id': str(uuid.uuid4()),
                    'type': 'anomaly',
                    'severity': str(getattr(anomaly, 'severity', 'unknown')),
                    'message': str(getattr(anomaly, 'description', 'Anomaly detected')),
                    'timestamp': datetime.now().isoformat()
                })
        
        return jsonify({
            'success': True,
            'alerts': alerts
        })
    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# ============================================================================
# ARTIFACT GENERATION ENDPOINTS (11 endpoints)
# ============================================================================

@app.route('/api/artifacts/types', methods=['GET'])
def get_artifact_types():
    """Get all supported artifact types"""
    if not ARTIFACTS_AVAILABLE or not artifact_generation_system:
        return jsonify({
            'success': False,
            'message': 'Artifact system not available'
        }), 503
    
    try:
        types = artifact_generation_system.get_supported_types()
        return jsonify({
            'success': True,
            'types': types
        })
    except Exception as e:
        logger.error(f"Error getting artifact types: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/artifacts/generate', methods=['POST'])
@require_auth(auth_system if AUTH_AVAILABLE else None)
def generate_artifact():
    """Generate a new artifact"""
    if not ARTIFACTS_AVAILABLE or not artifact_generation_system:
        return jsonify({
            'success': False,
            'message': 'Artifact system not available'
        }), 503
    
    try:
        data = request.get_json()
        artifact_type = data.get('type')
        document = data.get('document', {})
        prompts = data.get('prompts', [])
        swarm_results = data.get('swarm_results', [])
        
        if not artifact_type:
            return jsonify({
                'success': False,
                'message': 'Artifact type is required'
            }), 400
        
        # Generate artifact (async method, but we'll call it synchronously for now)
        import asyncio
        
        try:
            # Try to call async method
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            artifact = loop.run_until_complete(
                artifact_generation_system.generate_artifact(
                    artifact_type=artifact_type,
                    document=document,
                    prompts=prompts,
                    swarm_results=swarm_results
                )
            )
            loop.close()
        except Exception as async_error:
            logger.warning(f"Async generation failed, trying sync fallback: {async_error}")
            # Fallback: create a simple artifact
            from artifact_generation_system import Artifact
            
            artifact = Artifact(
                artifact_type=artifact_type.upper(),
                name=f"Generated {artifact_type}",
                source_doc_id=document.get('id', 'unknown'),
                content=f"# Generated {artifact_type}\n\nGenerated from document: {document.get('id', 'unknown')}",
                metadata=document.get('metadata', {})
            )
        
        # Store in manager
        if artifact_manager:
            artifact_manager.add_artifact(artifact)
        
        return jsonify({
            'success': True,
            'artifact': artifact.to_dict() if hasattr(artifact, 'to_dict') else artifact,
            'message': 'Artifact generated successfully'
        })
    except Exception as e:
        logger.error(f"Error generating artifact: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/artifacts/list', methods=['GET'])
def list_artifacts():
    """List all artifacts with optional filters"""
    if not ARTIFACTS_AVAILABLE or not artifact_manager:
        return jsonify({
            'success': False,
            'message': 'Artifact system not available'
        }), 503
    
    try:
        artifact_type = request.args.get('type')
        status = request.args.get('status')
        
        artifacts = artifact_manager.list_artifacts(
            artifact_type=artifact_type,
            status=status
        )
        
        return jsonify({
            'success': True,
            'artifacts': artifacts,
            'count': len(artifacts)
        })
    except Exception as e:
        logger.error(f"Error listing artifacts: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/artifacts/<artifact_id>', methods=['GET'])
def get_artifact(artifact_id):
    """Get specific artifact details"""
    if not ARTIFACTS_AVAILABLE or not artifact_manager:
        return jsonify({
            'success': False,
            'message': 'Artifact system not available'
        }), 503
    
    try:
        artifact = artifact_manager.get_artifact(artifact_id)
        
        if not artifact:
            return jsonify({
                'success': False,
                'message': 'Artifact not found'
            }), 404
        
        return jsonify({
            'success': True,
            'artifact': artifact.to_dict() if hasattr(artifact, 'to_dict') else artifact
        })
    except Exception as e:
        logger.error(f"Error getting artifact: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/artifacts/<artifact_id>', methods=['PUT'])
@require_auth(auth_system if AUTH_AVAILABLE else None)
def update_artifact(artifact_id):
    """Update an existing artifact"""
    if not ARTIFACTS_AVAILABLE or not artifact_manager:
        return jsonify({
            'success': False,
            'message': 'Artifact system not available'
        }), 503
    
    try:
        data = request.get_json()
        
        artifact = artifact_manager.get_artifact(artifact_id)
        if not artifact:
            return jsonify({
                'success': False,
                'message': 'Artifact not found'
            }), 404
        
        # Update artifact fields
        if 'content' in data:
            artifact.content = data['content']
        if 'metadata' in data:
            artifact.metadata.update(data['metadata'])
        
        artifact.updated_at = datetime.now()
        
        return jsonify({
            'success': True,
            'artifact': artifact.to_dict() if hasattr(artifact, 'to_dict') else artifact,
            'message': 'Artifact updated successfully'
        })
    except Exception as e:
        logger.error(f"Error updating artifact: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/artifacts/<artifact_id>', methods=['DELETE'])
@require_auth(auth_system if AUTH_AVAILABLE else None)
def delete_artifact(artifact_id):
    """Delete an artifact"""
    if not ARTIFACTS_AVAILABLE or not artifact_manager:
        return jsonify({
            'success': False,
            'message': 'Artifact system not available'
        }), 503
    
    try:
        success = artifact_manager.delete_artifact(artifact_id)
        
        if not success:
            return jsonify({
                'success': False,
                'message': 'Artifact not found'
            }), 404
        
        return jsonify({
            'success': True,
            'message': 'Artifact deleted successfully'
        })
    except Exception as e:
        logger.error(f"Error deleting artifact: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/artifacts/<artifact_id>/versions', methods=['GET'])
def get_artifact_versions(artifact_id):
    """Get version history for an artifact"""
    if not ARTIFACTS_AVAILABLE or not artifact_manager:
        return jsonify({
            'success': False,
            'message': 'Artifact system not available'
        }), 503
    
    try:
        versions = artifact_manager.get_version_history(artifact_id)
        
        if versions is None:
            return jsonify({
                'success': False,
                'message': 'Artifact not found'
            }), 404
        
        return jsonify({
            'success': True,
            'versions': [v.to_dict() if hasattr(v, 'to_dict') else v for v in versions],
            'count': len(versions)
        })
    except Exception as e:
        logger.error(f"Error getting artifact versions: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/artifacts/<artifact_id>/convert', methods=['POST'])
@require_auth(auth_system if AUTH_AVAILABLE else None)
def convert_artifact(artifact_id):
    """Convert artifact to different format"""
    if not ARTIFACTS_AVAILABLE or not artifact_manager:
        return jsonify({
            'success': False,
            'message': 'Artifact system not available'
        }), 503
    
    try:
        data = request.get_json()
        target_format = data.get('format')
        
        if not target_format:
            return jsonify({
                'success': False,
                'message': 'Target format is required'
            }), 400
        
        result = artifact_manager.convert_format(artifact_id, target_format)
        
        if not result:
            return jsonify({
                'success': False,
                'message': 'Artifact not found or conversion failed'
            }), 404
        
        return jsonify({
            'success': True,
            'artifact': result.to_dict() if hasattr(result, 'to_dict') else result,
            'message': f'Artifact converted to {target_format} successfully'
        })
    except Exception as e:
        logger.error(f"Error converting artifact: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/artifacts/search', methods=['GET'])
def search_artifacts():
    """Search artifacts by name, content, or metadata"""
    if not ARTIFACTS_AVAILABLE or not artifact_manager:
        return jsonify({
            'success': False,
            'message': 'Artifact system not available'
        }), 503
    
    try:
        query = request.args.get('q', '')
        
        if not query:
            return jsonify({
                'success': False,
                'message': 'Search query is required'
            }), 400
        
        results = artifact_manager.search_artifacts(query)
        
        return jsonify({
            'success': True,
            'results': results,
            'count': len(results),
            'query': query
        })
    except Exception as e:
        logger.error(f"Error searching artifacts: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/artifacts/stats', methods=['GET'])
def get_artifact_stats():
    """Get artifact statistics"""
    if not ARTIFACTS_AVAILABLE or not artifact_manager:
        return jsonify({
            'success': False,
            'message': 'Artifact system not available'
        }), 503
    
    try:
        stats = artifact_manager.get_statistics()
        
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        logger.error(f"Error getting artifact stats: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/artifacts/<artifact_id>/download', methods=['GET'])
def download_artifact(artifact_id):
    """Download artifact file"""
    if not ARTIFACTS_AVAILABLE or not artifact_manager:
        return jsonify({
            'success': False,
            'message': 'Artifact system not available'
        }), 503
    
    try:
        artifact = artifact_manager.get_artifact(artifact_id)
        
        if not artifact:
            return jsonify({
                'success': False,
                'message': 'Artifact not found'
            }), 404
        
        # Generate file content
        file_content = artifact_manager.generate_file(artifact_id)
        
        if not file_content:
            return jsonify({
                'success': False,
                'message': 'Failed to generate file'
            }), 500
        
        # Determine file extension based on type
        extension_map = {
            'PDF': '.pdf',
            'DOCX': '.docx',
            'CODE': '.txt',
            'DESIGN': '.json',
            'DATA': '.csv',
            'REPORT': '.html',
            'PRESENTATION': '.pptx',
            'CONTRACT': '.docx'
        }
        
        artifact_type = getattr(artifact, 'type', 'CODE')
        extension = extension_map.get(artifact_type, '.txt')
        
        # Create a temporary file
        import io
        buffer = io.BytesIO()
        
        if isinstance(file_content, str):
            buffer.write(file_content.encode('utf-8'))
        else:
            buffer.write(file_content)
        
        buffer.seek(0)
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"artifact_{artifact_id}{extension}",
            mimetype='application/octet-stream'
        )
    except Exception as e:
        logger.error(f"Error downloading artifact: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# ============================================================================
# Shadow Agent System Endpoints
# ============================================================================

@app.route('/api/shadow/agents', methods=['GET'])
def list_shadow_agents():
    """List all shadow agents"""
    if not SHADOW_AGENTS_AVAILABLE or not shadow_agent_system:
        return jsonify({
            'success': False,
            'message': 'Shadow agent system not available'
        }), 503
    
    try:
        agents = shadow_agent_system.list_agents()
        return jsonify({
            'success': True,
            'agents': agents,
            'count': len(agents)
        })
    except Exception as e:
        logger.error(f"Error listing shadow agents: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error listing shadow agents: {str(e)}'
        }), 500

@app.route('/api/shadow/agents/<agent_id>', methods=['GET'])
def get_shadow_agent(agent_id):
    """Get details of a specific shadow agent"""
    if not SHADOW_AGENTS_AVAILABLE or not shadow_agent_system:
        return jsonify({
            'success': False,
            'message': 'Shadow agent system not available'
        }), 503
    
    try:
        agent = shadow_agent_system.get_agent(agent_id)
        if not agent:
            return jsonify({
                'success': False,
                'message': 'Agent not found'
            }), 404
        
        return jsonify({
            'success': True,
            'agent': agent.to_dict()
        })
    except Exception as e:
        logger.error(f"Error getting shadow agent: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error getting shadow agent: {str(e)}'
        }), 500

@app.route('/api/shadow/observe', methods=['POST'])
@require_auth(auth_system if AUTH_AVAILABLE else None)
def record_observation():
    """Record an observation for shadow agents"""
    if not SHADOW_AGENTS_AVAILABLE or not shadow_agent_system:
        return jsonify({
            'success': False,
            'message': 'Shadow agent system not available'
        }), 503
    
    try:
        from shadow_agent_system import ObservationType
        
        data = request.get_json()
        domain = data.get('domain', 'general')
        obs_type_str = data.get('obs_type', 'COMMAND')
        action = data.get('action', '')
        context = data.get('context', {})
        
        if not action:
            return jsonify({
                'success': False,
                'message': 'Action is required'
            }), 400
        
        # Convert string to ObservationType enum
        try:
            obs_type = ObservationType(obs_type_str)
        except ValueError:
            return jsonify({
                'success': False,
                'message': f'Invalid obs_type: {obs_type_str}. Must be one of: {[e.value for e in ObservationType]}'
            }), 400
        
        shadow_agent_system.observe(domain, obs_type, action, context)
        
        return jsonify({
            'success': True,
            'message': 'Observation recorded'
        })
    except Exception as e:
        logger.error(f"Error recording observation: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error recording observation: {str(e)}'
        }), 500

@app.route('/api/shadow/observations', methods=['GET'])
def get_observations():
    """Get recent observations"""
    if not SHADOW_AGENTS_AVAILABLE or not shadow_agent_system:
        return jsonify({
            'success': False,
            'message': 'Shadow agent system not available'
        }), 503
    
    try:
        # Access global observations from shadow agent system
        observations = shadow_agent_system.global_observations[-50:]  # Last 50
        
        return jsonify({
            'success': True,
            'observations': observations,
            'count': len(observations)
        })
    except Exception as e:
        logger.error(f"Error getting observations: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error getting observations: {str(e)}'
        }), 500

@app.route('/api/shadow/learn', methods=['POST'])
@require_auth(auth_system if AUTH_AVAILABLE else None)
def run_learning_cycle():
    """Run a learning cycle for shadow agents"""
    if not SHADOW_AGENTS_AVAILABLE or not shadow_agent_system:
        return jsonify({
            'success': False,
            'message': 'Shadow agent system not available'
        }), 503
    
    try:
        result = shadow_agent_system.run_learning_cycle()
        
        return jsonify({
            'success': True,
            'result': result
        })
    except Exception as e:
        logger.error(f"Error running learning cycle: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error running learning cycle: {str(e)}'
        }), 500

@app.route('/api/shadow/proposals', methods=['GET'])
def get_proposals():
    """Get automation proposals"""
    if not SHADOW_AGENTS_AVAILABLE or not shadow_agent_system:
        return jsonify({
            'success': False,
            'message': 'Shadow agent system not available'
        }), 503
    
    try:
        proposals = shadow_agent_system.get_pending_proposals()
        
        return jsonify({
            'success': True,
            'proposals': proposals,
            'count': len(proposals)
        })
    except Exception as e:
        logger.error(f"Error getting proposals: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error getting proposals: {str(e)}'
        }), 500

@app.route('/api/shadow/proposals/<agent_id>/<proposal_id>/approve', methods=['POST'])
@require_auth(auth_system if AUTH_AVAILABLE else None)
def approve_proposal(agent_id, proposal_id):
    """Approve an automation proposal"""
    if not SHADOW_AGENTS_AVAILABLE or not shadow_agent_system:
        return jsonify({
            'success': False,
            'message': 'Shadow agent system not available'
        }), 503
    
    try:
        success = shadow_agent_system.approve_proposal(agent_id, proposal_id)
        
        if not success:
            return jsonify({
                'success': False,
                'message': 'Proposal or agent not found'
            }), 404
        
        return jsonify({
            'success': True,
            'message': 'Proposal approved'
        })
    except Exception as e:
        logger.error(f"Error approving proposal: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error approving proposal: {str(e)}'
        }), 500

@app.route('/api/shadow/proposals/<agent_id>/<proposal_id>/reject', methods=['POST'])
@require_auth(auth_system if AUTH_AVAILABLE else None)
def reject_proposal(agent_id, proposal_id):
    """Reject an automation proposal"""
    if not SHADOW_AGENTS_AVAILABLE or not shadow_agent_system:
        return jsonify({
            'success': False,
            'message': 'Shadow agent system not available'
        }), 503
    
    try:
        data = request.get_json()
        reason = data.get('reason', 'User rejected')
        
        success = shadow_agent_system.reject_proposal(agent_id, proposal_id, reason)
        
        if not success:
            return jsonify({
                'success': False,
                'message': 'Proposal or agent not found'
            }), 404
        
        return jsonify({
            'success': True,
            'message': 'Proposal rejected'
        })
    except Exception as e:
        logger.error(f"Error rejecting proposal: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error rejecting proposal: {str(e)}'
        }), 500

@app.route('/api/shadow/automations', methods=['GET'])
def get_automations():
    """Get active automations"""
    if not SHADOW_AGENTS_AVAILABLE or not shadow_agent_system:
        return jsonify({
            'success': False,
            'message': 'Shadow agent system not available'
        }), 503
    
    try:
        automations = shadow_agent_system.get_active_automations()
        
        return jsonify({
            'success': True,
            'automations': [automation.to_dict() for automation in automations],
            'count': len(automations)
        })
    except Exception as e:
        logger.error(f"Error getting automations: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error getting automations: {str(e)}'
        }), 500

@app.route('/api/shadow/stats', methods=['GET'])
def get_shadow_stats():
    """Get shadow agent statistics"""
    if not SHADOW_AGENTS_AVAILABLE or not shadow_agent_system:
        return jsonify({
            'success': False,
            'message': 'Shadow agent system not available'
        }), 503
    
    try:
        stats = shadow_agent_system.get_statistics()
        
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        logger.error(f"Error getting shadow stats: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error getting shadow stats: {str(e)}'
        }), 500

@app.route('/api/shadow/analyze', methods=['POST'])
@require_auth(auth_system if AUTH_AVAILABLE else None)
def analyze_patterns():
    """Run pattern analysis - this is part of the learning cycle"""
    if not SHADOW_AGENTS_AVAILABLE or not shadow_agent_system:
        return jsonify({
            'success': False,
            'message': 'Shadow agent system not available'
        }), 503
    
    try:
        # Run learning cycle which includes pattern analysis
        result = shadow_agent_system.run_learning_cycle()
        
        return jsonify({
            'success': True,
            'result': result
        })
    except Exception as e:
        logger.error(f"Error analyzing patterns: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error analyzing patterns: {str(e)}'
        }), 500

# ============================================================================
# Cooperative Swarm System Endpoints
# ============================================================================

@app.route('/api/cooperative/workflows', methods=['GET'])
def list_workflows():
    """List all workflows"""
    if not COOPERATIVE_SWARM_AVAILABLE or not cooperative_swarm:
        return jsonify({
            'success': False,
            'message': 'Cooperative swarm system not available'
        }), 503
    
    try:
        # Workflows are stored in active_workflows
        workflows = cooperative_swarm.active_workflows
        return jsonify({
            'success': True,
            'workflows': workflows,
            'count': len(workflows)
        })
    except Exception as e:
        logger.error(f"Error listing workflows: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error listing workflows: {str(e)}'
        }), 500

@app.route('/api/cooperative/workflows/<workflow_id>', methods=['GET'])
def get_workflow(workflow_id):
    """Get details of a specific workflow"""
    if not COOPERATIVE_SWARM_AVAILABLE or not cooperative_swarm:
        return jsonify({
            'success': False,
            'message': 'Cooperative swarm system not available'
        }), 503
    
    try:
        status = cooperative_swarm.get_workflow_status(workflow_id)
        
        if not status or not status.get('found', False):
            return jsonify({
                'success': False,
                'message': 'Workflow not found'
            }), 404
        
        return jsonify({
            'success': True,
            'workflow': status
        })
    except Exception as e:
        logger.error(f"Error getting workflow: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error getting workflow: {str(e)}'
        }), 500

@app.route('/api/cooperative/workflows', methods=['POST'])
@require_auth(auth_system if AUTH_AVAILABLE else None)
def create_workflow():
    """Create a new workflow"""
    if not COOPERATIVE_SWARM_AVAILABLE or not cooperative_swarm:
        return jsonify({
            'success': False,
            'message': 'Cooperative swarm system not available'
        }), 503
    
    try:
        data = request.get_json()
        workflow_definition = data
        
        if not workflow_definition:
            return jsonify({
                'success': False,
                'message': 'Workflow definition is required'
            }), 400
        
        # Execute workflow creation asynchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                cooperative_swarm.execute_cooperative_workflow(workflow_definition)
            )
            return jsonify({
                'success': True,
                'workflow': result
            })
        except Exception as e:
            logger.error(f"Async error: {e}")
            raise
    except Exception as e:
        logger.error(f"Error creating workflow: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error creating workflow: {str(e)}'
        }), 500

@app.route('/api/cooperative/workflows/<workflow_id>/execute', methods=['POST'])
@require_auth(auth_system if AUTH_AVAILABLE else None)
def execute_workflow(workflow_id):
    """Execute a workflow"""
    if not COOPERATIVE_SWARM_AVAILABLE or not cooperative_swarm:
        return jsonify({
            'success': False,
            'message': 'Cooperative swarm system not available'
        }), 503
    
    try:
        status = cooperative_swarm.get_workflow_status(workflow_id)
        
        if not status or not status.get('found', False):
            return jsonify({
                'success': False,
                'message': 'Workflow not found'
            }), 404
        
        # Return current status
        return jsonify({
            'success': True,
            'workflow': status,
            'message': 'Workflow status retrieved'
        })
    except Exception as e:
        logger.error(f"Error executing workflow: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error executing workflow: {str(e)}'
        }), 500

@app.route('/api/cooperative/handoffs', methods=['POST'])
@require_auth(auth_system if AUTH_AVAILABLE else None)
def initiate_handoff():
    """Initiate an agent handoff"""
    if not COOPERATIVE_SWARM_AVAILABLE or not cooperative_swarm:
        return jsonify({
            'success': False,
            'message': 'Cooperative swarm system not available'
        }), 503
    
    try:
        data = request.get_json()
        from_agent = data.get('from_agent')
        to_agent = data.get('to_agent')
        handoff_type = data.get('handoff_type', 'DELEGATE')
        task = data.get('task', {})
        context = data.get('context', {})
        
        if not from_agent or not to_agent:
            return jsonify({
                'success': False,
                'message': 'Both from_agent and to_agent are required'
            }), 400
        
        # Execute handoff asynchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            handoff = loop.run_until_complete(
                cooperative_swarm.agent_handoff_manager.initiate_handoff(
                    from_agent=from_agent,
                    to_agent=to_agent,
                    handoff_type=handoff_type,
                    task=task,
                    context=context
                )
            )
            return jsonify({
                'success': True,
                'handoff': handoff
            })
        except Exception as e:
            logger.error(f"Async error: {e}")
            raise
    except Exception as e:
        logger.error(f"Error initiating handoff: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error initiating handoff: {str(e)}'
        }), 500

@app.route('/api/cooperative/handoffs/<handoff_id>/confirm', methods=['POST'])
@require_auth(auth_system if AUTH_AVAILABLE else None)
def confirm_handoff(handoff_id):
    """Confirm a handoff"""
    if not COOPERATIVE_SWARM_AVAILABLE or not cooperative_swarm:
        return jsonify({
            'success': False,
            'message': 'Cooperative swarm system not available'
        }), 503
    
    try:
        data = request.get_json()
        timeout = data.get('timeout', 30)
        
        # Execute confirmation asynchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                cooperative_swarm.agent_handoff_manager.await_handoff_confirmation(
                    handoff_id=handoff_id,
                    timeout=timeout
                )
            )
            
            if not result.get('confirmed', False):
                return jsonify({
                    'success': False,
                    'message': 'Handoff confirmation failed or timed out'
                }), 404
            
            return jsonify({
                'success': True,
                'message': 'Handoff confirmed',
                'result': result
            })
        except Exception as e:
            logger.error(f"Async error: {e}")
            raise
    except Exception as e:
        logger.error(f"Error confirming handoff: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error confirming handoff: {str(e)}'
        }), 500

@app.route('/api/cooperative/messages', methods=['GET'])
def get_messages():
    """Get agent-to-agent messages"""
    if not COOPERATIVE_SWARM_AVAILABLE or not cooperative_swarm:
        return jsonify({
            'success': False,
            'message': 'Cooperative swarm system not available'
        }), 503
    
    try:
        agent_id = request.args.get('agent_id')
        unread_only = request.args.get('unread_only', 'false').lower() == 'true'
        
        if not agent_id:
            return jsonify({
                'success': False,
                'message': 'agent_id is required'
            }), 400
        
        messages = cooperative_swarm.get_agent_messages(agent_id, unread_only)
        
        return jsonify({
            'success': True,
            'messages': [msg.to_dict() for msg in messages],
            'count': len(messages)
        })
    except Exception as e:
        logger.error(f"Error getting messages: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error getting messages: {str(e)}'
        }), 500

@app.route('/api/cooperative/messages', methods=['POST'])
@require_auth(auth_system if AUTH_AVAILABLE else None)
def send_message():
    """Send an agent-to-agent message"""
    if not COOPERATIVE_SWARM_AVAILABLE or not cooperative_swarm:
        return jsonify({
            'success': False,
            'message': 'Cooperative swarm system not available'
        }), 503
    
    try:
        data = request.get_json()
        from_agent = data.get('from_agent')
        to_agent = data.get('to_agent')
        message_type = data.get('message_type', 'INFO')
        content = data.get('content', {})
        
        if not from_agent or not to_agent:
            return jsonify({
                'success': False,
                'message': 'from_agent and to_agent are required'
            }), 400
        
        msg = cooperative_swarm.send_message(
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=message_type,
            content=content
        )
        
        return jsonify({
            'success': True,
            'message': msg.to_dict()
        })
    except Exception as e:
        logger.error(f"Error sending message: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error sending message: {str(e)}'
        }), 500

# ============================================================================
# Stability-Based Attention System Endpoints
# ============================================================================

@app.route('/api/attention/form', methods=['POST'])
@require_auth(auth_system if AUTH_AVAILABLE else None)
def form_attention():
    """Form attention for the current state, memory, and goal"""
    if not ATTENTION_AVAILABLE or not attention_system:
        return jsonify({
            'success': False,
            'message': 'Attention system not available'
        }), 503
    
    try:
        data = request.get_json()
        state = data.get('state', {})
        memory = data.get('memory', {})
        goal = data.get('goal', {})
        candidates_data = data.get('candidates', [])
        
        # Create candidate representations
        candidates = []
        for cand in candidates_data:
            rep = InternalRepresentation(
                id=cand.get('id', str(uuid.uuid4())),
                vector=cand.get('vector', []),
                abstraction_level=cand.get('abstraction_level', 0),
                metadata=cand.get('metadata', {})
            )
            candidates.append(rep)
        
        # If no candidates provided, generate from state/memory/goal
        if not candidates:
            candidates = create_candidate_representations(state, memory, goal, count=10)
        
        # Form attention
        chosen_representation, log_entry = attention_system.form_attention(
            state=state,
            memory=memory,
            goal=goal,
            candidates=candidates
        )
        
        # Prepare response
        result = {
            'success': True,
            'status': log_entry.status.value,
            'decision_reason': log_entry.decision_reason,
            'role': log_entry.role.value,
            'timestamp': log_entry.timestamp.isoformat()
        }
        
        if chosen_representation:
            result['chosen_representation'] = {
                'id': chosen_representation.id,
                'abstraction_level': chosen_representation.abstraction_level,
                'vector_length': len(chosen_representation.vector),
                'metadata': chosen_representation.metadata
            }
        
        if log_entry.subsystem_scores:
            result['subsystem_scores'] = {
                st.value: score
                for st, score in log_entry.subsystem_scores.items()
            }
        
        if log_entry.temporal_scores:
            result['temporal_scores'] = log_entry.temporal_scores
        
        if log_entry.failure_reason:
            result['failure_reason'] = log_entry.failure_reason.value
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error forming attention: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error forming attention: {str(e)}'
        }), 500

@app.route('/api/attention/history', methods=['GET'])
def get_attention_history():
    """Get attention history"""
    if not ATTENTION_AVAILABLE or not attention_system:
        return jsonify({
            'success': False,
            'message': 'Attention system not available'
        }), 503
    
    try:
        history = attention_system.get_attention_history()
        
        return jsonify({
            'success': True,
            'history': [
                {
                    'id': rep.id,
                    'abstraction_level': rep.abstraction_level,
                    'vector_length': len(rep.vector),
                    'metadata': rep.metadata
                }
                for rep in history
            ],
            'count': len(history)
        })
    
    except Exception as e:
        logger.error(f"Error getting attention history: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error getting attention history: {str(e)}'
        }), 500

@app.route('/api/attention/stats', methods=['GET'])
def get_attention_statistics():
    """Get attention statistics"""
    if not ATTENTION_AVAILABLE or not attention_system:
        return jsonify({
            'success': False,
            'message': 'Attention system not available'
        }), 503
    
    try:
        stats = attention_system.get_attention_statistics()
        
        return jsonify({
            'success': True,
            'statistics': stats
        })
    
    except Exception as e:
        logger.error(f"Error getting attention statistics: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error getting attention statistics: {str(e)}'
        }), 500

@app.route('/api/attention/set-role', methods=['POST'])
@require_auth(auth_system if AUTH_AVAILABLE else None)
def set_attention_role():
    """Set the current cognitive role"""
    if not ATTENTION_AVAILABLE or not attention_system:
        return jsonify({
            'success': False,
            'message': 'Attention system not available'
        }), 503
    
    try:
        data = request.get_json()
        role_str = data.get('role', 'SUPERVISOR')
        
        # Convert string to enum
        try:
            role = CognitiveRole(role_str)
        except ValueError:
            return jsonify({
                'success': False,
                'message': f'Invalid role: {role_str}. Must be one of: {[r.value for r in CognitiveRole]}'
            }), 400
        
        attention_system.set_role(role)
        
        return jsonify({
            'success': True,
            'message': f'Role set to {role.value}',
            'role': role.value
        })
    
    except Exception as e:
        logger.error(f"Error setting attention role: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error setting attention role: {str(e)}'
        }), 500

@app.route('/api/attention/reset', methods=['POST'])
@require_auth(auth_system if AUTH_AVAILABLE else None)
def reset_attention_system():
    """Reset the attention system"""
    if not ATTENTION_AVAILABLE or not attention_system:
        return jsonify({
            'success': False,
            'message': 'Attention system not available'
        }), 503
    
    try:
        attention_system.reset()
        
        return jsonify({
            'success': True,
            'message': 'Attention system reset successfully'
        })
    
    except Exception as e:
        logger.error(f"Error resetting attention system: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error resetting attention system: {str(e)}'
        }), 500

# ============================================================================
# MODULE SYSTEM ENDPOINTS
# ============================================================================

@app.route('/api/modules/compile/github', methods=['POST'])
@require_auth(auth_system if AUTH_AVAILABLE else None)
def compile_module_from_github():
    """Compile module from GitHub repository"""
    if not module_compiler or not module_registry:
        return jsonify({
            'success': False,
            'message': 'Module system not available'
        }), 503
    
    try:
        data = request.get_json()
        github_url = data.get('github_url')
        file_path = data.get('file_path')
        category = data.get('category', 'general')
        
        if not github_url:
            return jsonify({
                'success': False,
                'message': 'GitHub URL is required'
            }), 400
        
        # Compile module
        module_spec = module_compiler.compile_from_github(
            github_url=github_url,
            file_path=file_path,
            category=category
        )
        
        # Register module
        registered = module_registry.register(module_spec)
        
        if not registered:
            return jsonify({
                'success': False,
                'message': 'Failed to register module'
            }), 500
        
        # Broadcast WebSocket event
        socketio.emit('module_compiled', {
            'module_id': module_spec.module_id,
            'module_name': module_spec.module_name,
            'github_url': module_spec.github_url,
            'capabilities': len(module_spec.capabilities),
            'verification_status': module_spec.verification_status
        })
        
        return jsonify({
            'success': True,
            'message': 'Module compiled and registered successfully',
            'module': module_spec.to_dict()
        })
        
    except ValueError as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Compilation failed: {str(e)}'
        }), 500


@app.route('/api/modules/compile/file', methods=['POST'])
@require_auth(auth_system if AUTH_AVAILABLE else None)
def compile_module_from_file():
    """Compile module from local file"""
    if not module_compiler or not module_registry:
        return jsonify({
            'success': False,
            'message': 'Module system not available'
        }), 503
    
    try:
        data = request.get_json()
        source_path = data.get('source_path')
        category = data.get('category', 'general')
        
        if not source_path:
            return jsonify({
                'success': False,
                'message': 'Source path is required'
            }), 400
        
        # Check if file exists
        if not os.path.exists(source_path):
            return jsonify({
                'success': False,
                'message': 'Source file not found'
            }), 404
        
        # Compile module
        module_spec = module_compiler.compile_from_file(
            source_path=source_path,
            category=category
        )
        
        # Register module
        registered = module_registry.register(module_spec)
        
        if not registered:
            return jsonify({
                'success': False,
                'message': 'Failed to register module'
            }), 500
        
        # Broadcast WebSocket event
        socketio.emit('module_compiled', {
            'module_id': module_spec.module_id,
            'module_name': module_spec.module_name,
            'source_path': module_spec.source_path,
            'capabilities': len(module_spec.capabilities),
            'verification_status': module_spec.verification_status
        })
        
        return jsonify({
            'success': True,
            'message': 'Module compiled and registered successfully',
            'module': module_spec.to_dict()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Compilation failed: {str(e)}'
        }), 500


@app.route('/api/modules/<module_id>', methods=['GET'])
def get_module_spec(module_id):
    """Get module specification"""
    if not module_registry:
        return jsonify({
            'success': False,
            'message': 'Module system not available'
        }), 503
    
    try:
        module_spec = module_registry.get(module_id)
        
        if not module_spec:
            return jsonify({
                'success': False,
                'message': 'Module not found'
            }), 404
        
        return jsonify({
            'success': True,
            'module': module_spec.to_dict()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to get module: {str(e)}'
        }), 500


@app.route('/api/modules', methods=['GET'])
def list_modules():
    """List all registered modules"""
    if not module_registry:
        return jsonify({
            'success': False,
            'message': 'Module system not available'
        }), 503
    
    try:
        modules = module_registry.list_all()
        
        return jsonify({
            'success': True,
            'modules': modules,
            'count': len(modules)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to list modules: {str(e)}'
        }), 500


@app.route('/api/modules/search', methods=['GET'])
def search_modules():
    """Search modules by capability"""
    if not module_registry:
        return jsonify({
            'success': False,
            'message': 'Module system not available'
        }), 503
    
    try:
        capability_name = request.args.get('capability')
        
        if not capability_name:
            return jsonify({
                'success': False,
                'message': 'Capability name is required'
            }), 400
        
        modules = module_registry.search_capabilities(capability_name)
        
        return jsonify({
            'success': True,
            'modules': modules,
            'count': len(modules)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Search failed: {str(e)}'
        }), 500


@app.route('/api/modules/<module_id>/load', methods=['POST'])
@require_auth(auth_system if AUTH_AVAILABLE else None)
def load_module(module_id):
    """Load module into runtime"""
    if not module_manager:
        return jsonify({
            'success': False,
            'message': 'Module manager not available'
        }), 503
    
    try:
        loaded = module_manager.load_module(module_id)
        
        if not loaded:
            return jsonify({
                'success': False,
                'message': 'Failed to load module'
            }), 400
        
        # Get module spec
        module_spec = module_registry.get(module_id)
        
        # Broadcast WebSocket event
        socketio.emit('module_loaded', {
            'module_id': module_id,
            'module_name': module_spec.module_name if module_spec else 'unknown',
            'capabilities': module_manager.loaded_capabilities.get(module_id, [])
        })
        
        return jsonify({
            'success': True,
            'message': 'Module loaded successfully',
            'module_id': module_id
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to load module: {str(e)}'
        }), 500


@app.route('/api/modules/<module_id>/unload', methods=['POST'])
@require_auth(auth_system if AUTH_AVAILABLE else None)
def unload_module(module_id):
    """Unload module from runtime"""
    if not module_manager:
        return jsonify({
            'success': False,
            'message': 'Module manager not available'
        }), 503
    
    try:
        unloaded = module_manager.unload_module(module_id)
        
        if not unloaded:
            return jsonify({
                'success': False,
                'message': 'Failed to unload module'
            }), 400
        
        # Broadcast WebSocket event
        socketio.emit('module_unloaded', {
            'module_id': module_id
        })
        
        return jsonify({
            'success': True,
            'message': 'Module unloaded successfully',
            'module_id': module_id
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to unload module: {str(e)}'
        }), 500


@app.route('/api/modules/loaded', methods=['GET'])
def list_loaded_modules():
    """List all loaded modules"""
    if not module_manager:
        return jsonify({
            'success': False,
            'message': 'Module manager not available'
        }), 503
    
    try:
        loaded = module_manager.list_loaded()
        
        return jsonify({
            'success': True,
            'modules': loaded,
            'count': len(loaded)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to list loaded modules: {str(e)}'
        }), 500


@app.route('/api/github/analyze', methods=['POST'])
def analyze_github_repo():
    """Analyze GitHub repository without compiling"""
    if not module_compiler or not module_compiler.github_analyzer:
        return jsonify({
            'success': False,
            'message': 'GitHub analyzer not available'
        }), 503
    
    try:
        data = request.get_json()
        github_url = data.get('github_url')
        
        if not github_url:
            return jsonify({
                'success': False,
                'message': 'GitHub URL is required'
            }), 400
        
        # Parse URL
        repo_info = module_compiler.github_analyzer.parse_github_url(github_url)
        if not repo_info:
            return jsonify({
                'success': False,
                'message': 'Invalid GitHub URL'
            }), 400
        
        owner, repo = repo_info['owner'], repo_info['repo']
        
        # Analyze repository
        readme = module_compiler.github_analyzer.analyze_readme(owner, repo)
        license_type, license_allowed = module_compiler.github_analyzer.detect_license(owner, repo)
        dependencies = module_compiler.github_analyzer.parse_requirements(owner, repo)
        languages = module_compiler.github_analyzer.get_languages(owner, repo)
        risk_issues, risk_score = module_compiler.github_analyzer.scan_risks(owner, repo)
        
        return jsonify({
            'success': True,
            'analysis': {
                'repo_url': github_url,
                'owner': owner,
                'repo': repo,
                'readme_summary': readme,
                'license_type': license_type.value if isinstance(license_type, str) else license_type,
                'license_allowed': license_allowed,
                'dependencies': dependencies,
                'languages': languages,
                'risk_issues': [issue.to_dict() for issue in risk_issues],
                'risk_score': risk_score,
                'safe_to_use': risk_score < 0.5 and license_allowed
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Analysis failed: {str(e)}'
        }), 500


# ============================================================================
# WEBSOCKET EVENTS
# ============================================================================

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    logger.info(f"Client connected: {request.sid}")
    emit('connected', {'message': 'Connected to Murphy System Backend'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    logger.info(f"Client disconnected: {request.sid}")

# ============================================================================
# COMMAND SYSTEM API ENDPOINTS
# ============================================================================

@app.route('/api/commands', methods=['GET'])
def get_commands():
    """Get all available commands, optionally filtered by module"""
    if not COMMAND_SYSTEM_AVAILABLE:
        return jsonify({"success": False, "error": "Command system not available"}), 503
    
    module_id = request.args.get('module')
    
    if module_id:
        # Get commands for specific module
        commands = command_registry.get_commands_by_module(module_id)
    else:
        # Get all implemented commands
        commands = command_registry.get_implemented_commands()
    
    return jsonify({
        "success": True,
        "count": len(commands),
        "commands": [cmd.to_dict() for cmd in commands]
    })


@app.route('/api/help', methods=['GET'])
def get_help():
    """Get help text for commands"""
    if not COMMAND_SYSTEM_AVAILABLE:
        return jsonify({"success": False, "error": "Command system not available"}), 503
    
    module_id = request.args.get('module')
    
    # Get help text
    help_text = command_registry.get_help_text(module_id=module_id)
    
    # Get librarian context if available
    context = None
    if librarian_adapter and librarian_adapter.enabled:
        context = librarian_adapter.get_help_context(module_id)
    
    return jsonify({
        "success": True,
        "help_text": help_text,
        "context": context,
        "module": module_id
    })


@app.route('/api/commands/execute', methods=['POST'])
def execute_command_endpoint():
    """Execute a command"""
    if not COMMAND_SYSTEM_AVAILABLE:
        return jsonify({"success": False, "error": "Command system not available"}), 503
    
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No JSON data provided"}), 400
    
    command_name = data.get('command')
    if not command_name:
        return jsonify({"success": False, "error": "Command name required"}), 400
    
    # Remove leading slash if present
    if command_name.startswith('/'):
        command_name = command_name[1:]
    
    args = data.get('args', {})
    
    # Execute command
    result = execute_command(command_name, args)
    
    return jsonify(result)


@app.route('/api/commands/<command_name>', methods=['GET'])
def get_command_details(command_name):
    """Get details for a specific command"""
    if not COMMAND_SYSTEM_AVAILABLE:
        return jsonify({"success": False, "error": "Command system not available"}), 503
    
    # Remove leading slash if present
    if command_name.startswith('/'):
        command_name = command_name[1:]
    
    command = command_registry.get_command(command_name)
    
    if not command:
        return jsonify({
            "success": False,
            "error": f"Command not found: /{command_name}"
        }), 404
    
    # Get librarian context for this command
    context = None
    if librarian_adapter and librarian_adapter.enabled:
        context = librarian_adapter.get_command_context(command_name)
    
    return jsonify({
        "success": True,
        "command": command.to_dict(),
        "context": context
    })


# ============================================================================
# ============================================================================
# LLM SYSTEM INTEGRATION
# ============================================================================

try:
    # Load Groq API keys from file
    groq_keys = []
    try:
        with open('/workspace/groq_keys.txt', 'r') as f:
            groq_keys = [line.strip() for line in f if line.strip()]
        logger.info(f"Loaded {len(groq_keys)} Groq API keys")
    except FileNotFoundError:
        logger.warning("No Groq API keys found, using demo mode")
    
    # Initialize LLM Manager
    llm_manager = LLMManager(groq_api_keys=groq_keys)
    LLM_AVAILABLE = True
    if len(groq_keys) > 0:
        logger.info(f"LLM Manager initialized with {len(groq_keys)} real Groq API keys")
    else:
        logger.info("LLM Manager initialized (demo mode)")
except Exception as e:
    logger.error(f"Failed to initialize LLM Manager: {e}")
    LLM_AVAILABLE = False
    llm_manager = None

# ============================================================================
# LIBRARIAN SYSTEM INTEGRATION
# ============================================================================

try:
    # Initialize Librarian System with real LLM
    librarian_system = LibrarianSystem(llm_client=llm_manager if LLM_AVAILABLE else None)
    LIBRARIAN_AVAILABLE = True
    logger.info("Librarian System initialized")
except Exception as e:
    logger.error(f"✗ Librarian System initialization failed: {e}")
    LIBRARIAN_AVAILABLE = False
    librarian_system = None
    hybrid_command_system = HybridCommandSystem()

except Exception as e:
    logger.error(f"Failed to initialize Librarian System: {e}")
    LIBRARIAN_AVAILABLE = False
    librarian_system = None





# ============================================================================
# LIBRARIAN API ENDPOINTS
# ============================================================================

@app.route('/api/librarian/ask', methods=['POST'])
def librarian_ask():
    """Process user input and get intelligent response with command suggestions."""
    try:
        if not LIBRARIAN_AVAILABLE or not librarian_system:
            return jsonify({
                'success': False,
                'error': 'Librarian system not available'
            }), 500
        
        data = request.get_json()
        user_input = data.get('input', '')
        
        if not user_input:
            return jsonify({
                'success': False,
                'error': 'No input provided'
            }), 400
        
        # Use the LibrarianSystem to process input
        import asyncio
        
        try:
            response = asyncio.run(librarian_system.ask(user_input))
            
            return jsonify({
                'success': True,
                'intent': {
                    'category': response.intent.category.value,
                    'confidence': response.intent.confidence,
                    'keywords': response.intent.keywords,
                    'suggested_commands': response.intent.suggested_commands
                },
                'message': response.message,
                'commands': response.commands,
                'workflow': response.workflow,
                'follow_up_questions': response.follow_up_questions,
                'confidence_level': response.confidence_level.value
            })
        except Exception as e:
            logger.error(f"Async error: {e}")
            raise
    
    except Exception as e:
        logger.error(f"Librarian ask error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# LLM API ENDPOINTS
# ============================================================================

@app.route('/api/llm/generate', methods=['POST'])
def llm_generate():
    """Generate LLM response."""
    try:
        data = request.get_json()
        prompt = data.get('prompt', '')
        
        if not prompt:
            return jsonify({
                'success': False,
                'error': 'No prompt provided'
            }), 400
        
        if not LLM_AVAILABLE or not llm_manager:
            return jsonify({
                'success': False,
                'error': 'LLM system not available'
            }), 500
        
        result = llm_manager.generate(prompt)
        
        return jsonify({
            'success': result['success'],
            'response': result['response'],
            'provider': result['provider'],
            'demo_mode': result['demo_mode']
        })
    
    except Exception as e:
        logger.error(f"LLM generate error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/llm/status', methods=['GET'])
def llm_status():
    """Get LLM system status."""
    try:
        if not LLM_AVAILABLE or not llm_manager:
            return jsonify({
                'success': False,
                'available': False,
                'providers': []
            })
        
        status = llm_manager.get_status()
        
        return jsonify({
            'success': True,
            'available': True,
            'total_providers': status['total_providers'],
            'available_providers': status['available_providers'],
            'providers': status['providers']
        })
    
    except Exception as e:
        logger.error(f"LLM status error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# SERVER STARTUP
# ============================================================================

if __name__ == '__main__':
    logger.info("="*60)
    logger.info("Murphy System Complete Backend Server v3.0")
    logger.info("="*60)
    logger.info(f"Monitoring: {'✓' if MONITORING_AVAILABLE else '✗'}")
    logger.info(f"Artifacts: {'✓' if ARTIFACTS_AVAILABLE else '✗'}")
    logger.info(f"Shadow Agents: {'✓' if SHADOW_AGENTS_AVAILABLE else '✗'}")
    logger.info(f"Cooperative Swarm: {'✓' if COOPERATIVE_SWARM_AVAILABLE else '✗'}")
    logger.info("="*60)
    
    logger.info(f"Command System: {'✓' if COMMAND_SYSTEM_AVAILABLE else '✗'}")
    logger.info("="*60)
    
    socketio.run(app, host='0.0.0.0', port=3002, debug=True, allow_unsafe_werkzeug=True)

# ==================== ENHANCED LIBRARIAN ENDPOINTS (Option C) ====================

@app.route('/api/librarian/enhanced', methods=['POST'])
@require_auth(auth_system if AUTH_AVAILABLE else None)
def librarian_enhanced_ask():
    """Enhanced librarian endpoint with discovery workflow"""
    try:
        data = request.get_json()
        user_input = data.get('input', '')
        
        if not user_input:
            return jsonify({
                'success': False,
                'message': 'Input is required'
            }), 400
        
        result = enhanced_librarian_system.ask(user_input)
        
        return jsonify({
            'success': True,
            'data': result
        })
    
    except Exception as e:
        logger.error(f"Enhanced librarian error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/librarian/interpret', methods=['POST'])
@require_auth(auth_system if AUTH_AVAILABLE else None)
def librarian_interpret_command():
    """Interpret a command in natural language"""
    try:
        data = request.get_json()
        command = data.get('command', '')
        
        if not command:
            return jsonify({
                'success': False,
                'message': 'Command is required'
            }), 400
        
        result = hybrid_command_system.interpret_command(command)
        
        return jsonify({
            'success': True,
            'data': result.__dict__ if hasattr(result, '__dict__') else result
        })
    
    except Exception as e:
        logger.error(f"Command interpretation error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/librarian/natural-to-command', methods=['POST'])
@require_auth(auth_system if AUTH_AVAILABLE else None)
def librarian_natural_to_command():
    """Convert natural language to command"""
    try:
        data = request.get_json()
        natural = data.get('natural', '')
        
        if not natural:
            return jsonify({
                'success': False,
                'message': 'Natural language text is required'
            }), 400
        
        hybrid = hybrid_command_system.natural_to_command(natural)
        
        return jsonify({
            'success': True,
            'data': hybrid.__dict__ if hasattr(hybrid, '__dict__') else hybrid
        })
    
    except Exception as e:
        logger.error(f"Natural to command error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


# ==================== EXECUTIVE BOT ENDPOINTS (Option C) ====================

@app.route('/api/executive/bots', methods=['GET'])
def get_executive_bots():
    """Get all executive bots"""
    try:
        bots = executive_bot_manager.get_all_bots()
        
        return jsonify({
            'success': True,
            'bots': bots
        })
    
    except Exception as e:
        logger.error(f"Get executive bots error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/executive/execute', methods=['POST'])
@require_auth(auth_system if AUTH_AVAILABLE else None)
def execute_executive_command():
    """Execute a command on an executive bot"""
    try:
        data = request.get_json()
        bot_role = data.get('bot', '')
        command = data.get('command', '')
        context = data.get('context', '')
        
        if not bot_role or not command:
            return jsonify({
                'success': False,
                'message': 'Bot role and command are required'
            }), 400
        
        result = executive_bot_manager.execute_command(bot_role, command, context)
        
        return jsonify({
            'success': True,
            'data': result
        })
    
    except Exception as e:
        logger.error(f"Execute executive command error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/executive/workflow/<workflow_name>', methods=['POST'])
@require_auth(auth_system if AUTH_AVAILABLE else None)
def execute_executive_workflow(workflow_name):
    """Execute an executive workflow"""
    try:
        result = executive_bot_manager.coordinate_workflow(workflow_name)
        
        return jsonify({
            'success': True,
            'data': result
        })
    
    except Exception as e:
        logger.error(f"Execute executive workflow error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/executive/terminology/<bot_role>', methods=['GET'])
def get_bot_terminology(bot_role):
    """Get domain terminology for a bot"""
    try:
        terminology = executive_bot_manager.get_bot_terminology(bot_role)
        
        return jsonify({
            'success': True,
            'terminology': terminology
        })
    
    except Exception as e:
        logger.error(f"Get bot terminology error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


# ==================== HYBRID COMMAND ENDPOINTS (Option C) ====================

@app.route('/api/commands/parse', methods=['POST'])
@require_auth(auth_system if AUTH_AVAILABLE else None)
def parse_hybrid_command():
    """Parse a hybrid command"""
    try:
        data = request.get_json()
        command = data.get('command', '')
        
        if not command:
            return jsonify({
                'success': False,
                'message': 'Command is required'
            }), 400
        
        hybrid = hybrid_command_system.parse_hybrid_command(command)
        
        return jsonify({
            'success': True,
            'data': hybrid.__dict__ if hasattr(hybrid, '__dict__') else hybrid
        })
    
    except Exception as e:
        logger.error(f"Parse hybrid command error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/commands/dropdown-data', methods=['GET'])
def get_command_dropdown_data():
    """Get data for command dropdown interface"""
    try:
        data = hybrid_command_system.get_command_dropdown_data()
        
        return jsonify({
            'success': True,
            'data': data
        })
    
    except Exception as e:
        logger.error(f"Get command dropdown data error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/commands/workflows', methods=['GET'])
def get_workflows():
    """Get all available workflows"""
    try:
        workflows = hybrid_command_system.get_available_workflows()
        
        return jsonify({
            'success': True,
            'workflows': workflows
        })
    
    except Exception as e:
        logger.error(f"Get workflows error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/commands/validate', methods=['POST'])
@require_auth(auth_system if AUTH_AVAILABLE else None)
def validate_command():
    """Validate command syntax"""
    try:
        data = request.get_json()
        command = data.get('command', '')
        
        if not command:
            return jsonify({
                'success': False,
                'message': 'Command is required'
            }), 400
        
        validation = hybrid_command_system.validate_command_syntax(command)
        
        return jsonify({
            'success': True,
            'data': validation
        })
    
    except Exception as e:
        logger.error(f"Validate command error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
