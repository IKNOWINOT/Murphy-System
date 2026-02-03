"""
Murphy Final Runtime - Unified System Orchestrator

This is the final runtime that wires together all Murphy systems:
- Agent Swarms (TrueSwarmSystem, DomainSwarms)
- MFGC Controller (orchestration)
- Confidence Engine (validation)
- Execution Engine (task execution)
- Learning Engine (improvement)
- Conversation Manager (dialogue)
- Telemetry Learning (data capture)
- Form Intake (structured input)

Copyright © 2020 Inoni Limited Liability Company
Created by: Corey Post
License: Apache License 2.0
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import all major systems
try:
    from true_swarm_system import TrueSwarmSystem, SwarmMode
    from domain_swarms import DomainDetector, DomainSwarmGenerator
    from advanced_swarm_system import AdvancedSwarmGenerator
    from mfgc_core import MFGCController
    from unified_mfgc import UnifiedMFGC
    from conversation_manager import ConversationManager, get_conversation_manager
    from comms.pipeline import MessagePipeline
    from form_intake.handlers import FormHandlerRegistry, submit_form
    from form_intake.schemas import FormType
    from confidence_engine.unified_confidence_engine import UnifiedConfidenceEngine
    from confidence_engine.murphy_gate import MurphyGate
    from execution_engine.integrated_form_executor import IntegratedFormExecutor
    from supervisor_system.integrated_hitl_monitor import IntegratedHITLMonitor
    from learning_engine.integrated_correction_system import IntegratedCorrectionSystem
    from telemetry_learning.ingestion import TelemetryIngestion
    from telemetry_learning.learning import TelemetryLearning
    from librarian.librarian_module import LibrarianModule
    from llm_integration import OllamaLLM
    from reasoning_engine import ReasoningEngine
    from two_phase_orchestrator import TwoPhaseOrchestrator
except ImportError as e:
    print(f"Import error: {e}")
    print("Some modules may not be available")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

class SessionManager:
    """Manages user sessions"""
    def __init__(self):
        self.sessions = {}
        
    def create_session(self, user_id: str, repository_id: str) -> str:
        session_id = f"session_{datetime.now().timestamp()}"
        self.sessions[session_id] = {
            'id': session_id,
            'user_id': user_id,
            'repository_id': repository_id,
            'created_at': datetime.now().isoformat(),
            'state': 'active',
            'agents': [],
            'conversations': []
        }
        return session_id
        
    def get_session(self, session_id: str) -> Optional[Dict]:
        return self.sessions.get(session_id)
        
    def end_session(self, session_id: str):
        if session_id in self.sessions:
            self.sessions[session_id]['state'] = 'ended'

class RepositoryManager:
    """Manages automation repositories"""
    def __init__(self):
        self.repositories = {}
        
    def create_repository(self, user_id: str, name: str, repo_type: str) -> str:
        repo_id = f"repo_{datetime.now().timestamp()}"
        self.repositories[repo_id] = {
            'id': repo_id,
            'user_id': user_id,
            'name': name,
            'type': repo_type,
            'created_at': datetime.now().isoformat(),
            'sessions': []
        }
        return repo_id
        
    def get_repository(self, repo_id: str) -> Optional[Dict]:
        return self.repositories.get(repo_id)
        
    def list_repositories(self, user_id: str) -> List[Dict]:
        return [r for r in self.repositories.values() if r['user_id'] == user_id]

class RuntimeOrchestrator:
    """
    Main orchestrator that coordinates all Murphy systems
    """
    def __init__(self):
        logger.info("Initializing Murphy Final Runtime...")
        
        # Core managers
        self.session_manager = SessionManager()
        self.repository_manager = RepositoryManager()
        
        # Initialize systems
        self.systems_available = {}
        
        # Swarm Systems
        try:
            self.true_swarm = TrueSwarmSystem()
            self.domain_detector = DomainDetector()
            self.advanced_swarm = AdvancedSwarmGenerator()
            self.systems_available['swarms'] = True
            logger.info("✓ Swarm Systems initialized")
        except Exception as e:
            logger.error(f"✗ Swarm Systems failed: {e}")
            self.systems_available['swarms'] = False
            
        # MFGC Controller
        try:
            self.mfgc = MFGCController()
            self.unified_mfgc = UnifiedMFGC()
            self.systems_available['mfgc'] = True
            logger.info("✓ MFGC Controller initialized")
        except Exception as e:
            logger.error(f"✗ MFGC Controller failed: {e}")
            self.systems_available['mfgc'] = False
            
        # Conversation System
        try:
            self.conversation_manager = get_conversation_manager()
            self.message_pipeline = MessagePipeline()
            self.systems_available['conversation'] = True
            logger.info("✓ Conversation System initialized")
        except Exception as e:
            logger.error(f"✗ Conversation System failed: {e}")
            self.systems_available['conversation'] = False
            
        # Form Intake
        try:
            self.form_registry = FormHandlerRegistry()
            self.systems_available['forms'] = True
            logger.info("✓ Form Intake initialized")
        except Exception as e:
            logger.error(f"✗ Form Intake failed: {e}")
            self.systems_available['forms'] = False
            
        # Confidence & Validation
        try:
            self.confidence_engine = UnifiedConfidenceEngine()
            self.murphy_gate = MurphyGate()
            self.systems_available['confidence'] = True
            logger.info("✓ Confidence Engine initialized")
        except Exception as e:
            logger.error(f"✗ Confidence Engine failed: {e}")
            self.systems_available['confidence'] = False
            
        # Execution
        try:
            self.executor = IntegratedFormExecutor()
            self.systems_available['execution'] = True
            logger.info("✓ Execution Engine initialized")
        except Exception as e:
            logger.error(f"✗ Execution Engine failed: {e}")
            self.systems_available['execution'] = False
            
        # Supervision
        try:
            self.hitl_monitor = IntegratedHITLMonitor()
            self.systems_available['supervision'] = True
            logger.info("✓ Supervisor System initialized")
        except Exception as e:
            logger.error(f"✗ Supervisor System failed: {e}")
            self.systems_available['supervision'] = False
            
        # Learning
        try:
            self.correction_system = IntegratedCorrectionSystem()
            self.systems_available['learning'] = True
            logger.info("✓ Learning Engine initialized")
        except Exception as e:
            logger.error(f"✗ Learning Engine failed: {e}")
            self.systems_available['learning'] = False
            
        # Telemetry
        try:
            self.telemetry_ingestion = TelemetryIngestion()
            self.telemetry_learning = TelemetryLearning()
            self.systems_available['telemetry'] = True
            logger.info("✓ Telemetry System initialized")
        except Exception as e:
            logger.error(f"✗ Telemetry System failed: {e}")
            self.systems_available['telemetry'] = False
            
        # Librarian
        try:
            self.librarian = LibrarianModule()
            self.systems_available['librarian'] = True
            logger.info("✓ Librarian initialized")
        except Exception as e:
            logger.error(f"✗ Librarian failed: {e}")
            self.systems_available['librarian'] = False
            
        # LLM & Reasoning
        try:
            self.llm = OllamaLLM()
            self.reasoning = ReasoningEngine()
            self.systems_available['llm'] = True
            logger.info("✓ LLM & Reasoning initialized")
        except Exception as e:
            logger.error(f"✗ LLM & Reasoning failed: {e}")
            self.systems_available['llm'] = False
            
        # Two-Phase Orchestrator
        try:
            self.two_phase = TwoPhaseOrchestrator()
            self.systems_available['two_phase'] = True
            logger.info("✓ Two-Phase Orchestrator initialized")
        except Exception as e:
            logger.error(f"✗ Two-Phase Orchestrator failed: {e}")
            self.systems_available['two_phase'] = False
            
        logger.info("=" * 60)
        logger.info("Murphy Final Runtime Initialized")
        logger.info(f"Systems Available: {sum(self.systems_available.values())}/{len(self.systems_available)}")
        logger.info("=" * 60)
        
    def process_user_input(self, message: str, session_id: str) -> Dict[str, Any]:
        """
        Main entry point for user input
        Orchestrates the complete flow:
        1. Classify intent
        2. Spawn appropriate agents
        3. Agents collaborate
        4. Validate with confidence engine
        5. Execute approved actions
        6. Capture telemetry
        7. Learn from execution
        """
        try:
            # Get session
            session = self.session_manager.get_session(session_id)
            if not session:
                return {'error': 'Invalid session'}
                
            # 1. Process message through pipeline
            if self.systems_available['conversation']:
                processed = self.message_pipeline.process(message)
                intent = processed.get('intent', 'general')
            else:
                intent = 'general'
                
            # 2. Detect domain and spawn swarm
            if self.systems_available['swarms']:
                domain = self.domain_detector.detect(message)
                swarm = self.true_swarm.spawn_swarm(
                    mode=SwarmMode.COLLABORATIVE,
                    domain=domain
                )
                session['agents'] = [agent.id for agent in swarm.agents]
            else:
                swarm = None
                
            # 3. MFGC orchestration
            if self.systems_available['mfgc']:
                orchestration_result = self.mfgc.orchestrate({
                    'message': message,
                    'intent': intent,
                    'session_id': session_id,
                    'swarm': swarm
                })
            else:
                orchestration_result = {'status': 'mfgc_unavailable'}
                
            # 4. Confidence validation
            if self.systems_available['confidence']:
                confidence = self.confidence_engine.calculate(orchestration_result)
                gate_result = self.murphy_gate.check(confidence)
            else:
                gate_result = {'action': 'PROCEED', 'confidence': 0.5}
                
            # 5. Execute if approved
            if gate_result['action'] == 'PROCEED' and self.systems_available['execution']:
                execution_result = self.executor.execute(orchestration_result)
            else:
                execution_result = {'status': 'blocked', 'reason': gate_result.get('reason')}
                
            # 6. Capture telemetry
            if self.systems_available['telemetry']:
                self.telemetry_ingestion.ingest({
                    'session_id': session_id,
                    'message': message,
                    'intent': intent,
                    'confidence': confidence if self.systems_available['confidence'] else None,
                    'execution': execution_result,
                    'timestamp': datetime.now().isoformat()
                })
                
            # 7. Store conversation
            if self.systems_available['conversation']:
                self.conversation_manager.add_message(
                    session_id=session_id,
                    role='user',
                    content=message
                )
                self.conversation_manager.add_message(
                    session_id=session_id,
                    role='assistant',
                    content=str(execution_result)
                )
                
            return {
                'success': True,
                'intent': intent,
                'confidence': confidence if self.systems_available['confidence'] else None,
                'gate_result': gate_result,
                'execution': execution_result,
                'agents': session.get('agents', [])
            }
            
        except Exception as e:
            logger.error(f"Error processing user input: {e}")
            return {'error': str(e)}

# Initialize orchestrator
orchestrator = RuntimeOrchestrator()

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route('/')
def index():
    return jsonify({'message': 'Murphy Final Runtime', 'version': '2.0'})

@app.route('/api/status', methods=['GET'])
def status():
    """Get system status"""
    return jsonify({
        'status': 'running',
        'systems': orchestrator.systems_available,
        'sessions': len(orchestrator.session_manager.sessions),
        'repositories': len(orchestrator.repository_manager.repositories),
        'timestamp': datetime.now().isoformat()
    })

# ============================================================================
# SESSION MANAGEMENT
# ============================================================================

@app.route('/api/session/create', methods=['POST'])
def create_session():
    """Create new session"""
    data = request.json
    user_id = data.get('user_id', 'default_user')
    repository_id = data.get('repository_id', 'default_repo')
    
    session_id = orchestrator.session_manager.create_session(user_id, repository_id)
    
    return jsonify({
        'success': True,
        'session_id': session_id
    })

@app.route('/api/session/<session_id>', methods=['GET'])
def get_session(session_id):
    """Get session details"""
    session = orchestrator.session_manager.get_session(session_id)
    if session:
        return jsonify(session)
    return jsonify({'error': 'Session not found'}), 404

@app.route('/api/session/<session_id>/end', methods=['POST'])
def end_session(session_id):
    """End session"""
    orchestrator.session_manager.end_session(session_id)
    return jsonify({'success': True})

# ============================================================================
# REPOSITORY MANAGEMENT
# ============================================================================

@app.route('/api/repository/create', methods=['POST'])
def create_repository():
    """Create new repository"""
    data = request.json
    user_id = data.get('user_id', 'default_user')
    name = data.get('name', 'Untitled Automation')
    repo_type = data.get('type', 'general')
    
    repo_id = orchestrator.repository_manager.create_repository(user_id, name, repo_type)
    
    return jsonify({
        'success': True,
        'repository_id': repo_id
    })

@app.route('/api/repository/list', methods=['GET'])
def list_repositories():
    """List user repositories"""
    user_id = request.args.get('user_id', 'default_user')
    repos = orchestrator.repository_manager.list_repositories(user_id)
    return jsonify({'repositories': repos})

# ============================================================================
# CONVERSATION & INPUT PROCESSING
# ============================================================================

@app.route('/api/conversation/message', methods=['POST'])
def send_message():
    """Process user message"""
    data = request.json
    message = data.get('message', '')
    session_id = data.get('session_id')
    
    if not session_id:
        return jsonify({'error': 'session_id required'}), 400
        
    result = orchestrator.process_user_input(message, session_id)
    return jsonify(result)

@app.route('/api/conversation/thread/<session_id>', methods=['GET'])
def get_conversation_thread(session_id):
    """Get conversation thread"""
    if orchestrator.systems_available['conversation']:
        messages = orchestrator.conversation_manager.get_conversation(session_id)
        return jsonify({'messages': messages})
    return jsonify({'error': 'Conversation system not available'}), 503

# ============================================================================
# SWARM SYSTEM
# ============================================================================

@app.route('/api/swarm/spawn', methods=['POST'])
def spawn_swarm():
    """Spawn agent swarm"""
    if not orchestrator.systems_available['swarms']:
        return jsonify({'error': 'Swarm system not available'}), 503
        
    data = request.json
    mode = data.get('mode', 'collaborative')
    domain = data.get('domain', 'general')
    
    try:
        swarm = orchestrator.true_swarm.spawn_swarm(
            mode=SwarmMode[mode.upper()],
            domain=domain
        )
        return jsonify({
            'success': True,
            'agents': [{'id': a.id, 'type': str(a.type)} for a in swarm.agents]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/swarm/agents', methods=['GET'])
def list_agents():
    """List active agents"""
    session_id = request.args.get('session_id')
    if session_id:
        session = orchestrator.session_manager.get_session(session_id)
        if session:
            return jsonify({'agents': session.get('agents', [])})
    return jsonify({'agents': []})

# ============================================================================
# FORM INTAKE
# ============================================================================

@app.route('/api/forms/submit', methods=['POST'])
def submit_form_endpoint():
    """Submit form"""
    if not orchestrator.systems_available['forms']:
        return jsonify({'error': 'Form system not available'}), 503
        
    data = request.json
    form_type = data.get('form_type')
    form_data = data.get('form_data', {})
    
    try:
        result = submit_form(FormType(form_type), form_data)
        return jsonify({
            'success': result.success,
            'submission_id': result.submission_id,
            'message': result.message
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# CONFIDENCE ENGINE
# ============================================================================

@app.route('/api/confidence/calculate', methods=['POST'])
def calculate_confidence():
    """Calculate confidence score"""
    if not orchestrator.systems_available['confidence']:
        return jsonify({'error': 'Confidence system not available'}), 503
        
    data = request.json
    try:
        confidence = orchestrator.confidence_engine.calculate(data)
        return jsonify({'confidence': confidence})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/confidence/murphy-gate', methods=['POST'])
def check_murphy_gate():
    """Check Murphy gate"""
    if not orchestrator.systems_available['confidence']:
        return jsonify({'error': 'Confidence system not available'}), 503
        
    data = request.json
    try:
        result = orchestrator.murphy_gate.check(data)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# TELEMETRY
# ============================================================================

@app.route('/api/telemetry/metrics', methods=['GET'])
def get_telemetry_metrics():
    """Get telemetry metrics"""
    if not orchestrator.systems_available['telemetry']:
        return jsonify({'error': 'Telemetry system not available'}), 503
        
    try:
        metrics = orchestrator.telemetry_learning.get_metrics()
        return jsonify({'metrics': metrics})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# LEARNING ENGINE
# ============================================================================

@app.route('/api/learning/patterns', methods=['GET'])
def get_learning_patterns():
    """Get learned patterns"""
    if not orchestrator.systems_available['learning']:
        return jsonify({'error': 'Learning system not available'}), 503
        
    try:
        patterns = orchestrator.correction_system.get_patterns()
        return jsonify({'patterns': patterns})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# TWO-PHASE AUTOMATION
# ============================================================================

@app.route('/api/automation/create', methods=['POST'])
def create_automation():
    """
    Phase 1: Create automation (generative setup)
    Carves from infinity to specific automation
    """
    if not orchestrator.systems_available['two_phase']:
        return jsonify({'error': 'Two-phase system not available'}), 503
        
    data = request.json
    user_request = data.get('request', '')
    domain = data.get('domain', 'general')
    
    try:
        automation_id = orchestrator.two_phase.create_automation(user_request, domain)
        config = orchestrator.two_phase.get_automation_config(automation_id)
        
        return jsonify({
            'success': True,
            'automation_id': automation_id,
            'phase': 'setup_complete',
            'agents': config['agents'],
            'constraints': config['constraints'],
            'sandbox': config['sandbox']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/automation/run/<automation_id>', methods=['POST'])
def run_automation(automation_id):
    """
    Phase 2: Run automation (production execution)
    Executes configured automation and produces deliverables
    """
    if not orchestrator.systems_available['two_phase']:
        return jsonify({'error': 'Two-phase system not available'}), 503
        
    try:
        result = orchestrator.two_phase.run_automation(automation_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/automation/<automation_id>/config', methods=['GET'])
def get_automation_config(automation_id):
    """Get automation configuration"""
    if not orchestrator.systems_available['two_phase']:
        return jsonify({'error': 'Two-phase system not available'}), 503
        
    config = orchestrator.two_phase.get_automation_config(automation_id)
    if config:
        return jsonify(config)
    return jsonify({'error': 'Automation not found'}), 404

@app.route('/api/automation/<automation_id>/history', methods=['GET'])
def get_automation_history(automation_id):
    """Get automation execution history"""
    if not orchestrator.systems_available['two_phase']:
        return jsonify({'error': 'Two-phase system not available'}), 503
        
    history = orchestrator.two_phase.get_execution_history(automation_id)
    return jsonify({'history': history})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Starting Murphy Final Runtime on port {port}")
    socketio.run(app, host='0.0.0.0', port=port, debug=True)