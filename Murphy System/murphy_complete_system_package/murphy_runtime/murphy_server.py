# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Murphy System - Minimal Working Backend Server
A simplified, functional backend for the Murphy System
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import logging
import threading
import uuid
import time
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'murphy-minimal-secret-key'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Global system state
system_initialized = False
agents = []
states = []
artifacts = []
components = []
system_lock = threading.Lock()

# ============================================================================
# BASIC ENDPOINTS
# ============================================================================

@app.route('/')
def index():
    """Serve the main HTML file"""
    return send_from_directory('.', 'murphy_complete_v2.html')

@app.route('/<path:filename>')
def serve_static(filename):
    """Serve static files"""
    return send_from_directory('.', filename)

@app.route('/api/status', methods=['GET'])
def get_status():
    """Get system status"""
    with system_lock:
        return jsonify({
            'status': 'running',
            'initialized': system_initialized,
            'agents_count': len(agents),
            'states_count': len(states),
            'artifacts_count': len(artifacts),
            'timestamp': datetime.now().isoformat()
        })

@app.route('/api/initialize', methods=['POST'])
def initialize_system():
    """Initialize the system"""
    global system_initialized
    
    try:
        with system_lock:
            if system_initialized:
                return jsonify({'status': 'already_initialized', 'message': 'System is already initialized'}), 200
            
            # Create initial agents
            agents.extend([
                {'id': 'agent-1', 'name': 'Director', 'status': 'active', 'role': 'orchestration'},
                {'id': 'agent-2', 'name': 'Researcher', 'status': 'active', 'role': 'research'},
                {'id': 'agent-3', 'name': 'Analyst', 'status': 'active', 'role': 'analysis'}
            ])
            
            # Create initial states
            states.append({
                'id': 'state-1',
                'name': 'Initial State',
                'description': 'System initialized successfully',
                'timestamp': datetime.now().isoformat(),
                'components': [],
                'metrics': {}
            })
            
            system_initialized = True
            logger.info("System initialized successfully")
            
            # Emit initialization event via WebSocket
            socketio.emit('system_initialized', {
                'agents': agents,
                'states': states
            })
            
            return jsonify({
                'status': 'initialized',
                'agents': agents,
                'states': states,
                'timestamp': datetime.now().isoformat()
            }), 200
    except Exception as e:
        logger.error(f"Error initializing system: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ============================================================================
# AGENT ENDPOINTS
# ============================================================================

@app.route('/api/agents', methods=['GET'])
def get_agents():
    """Get all agents"""
    with system_lock:
        return jsonify({'agents': agents})

@app.route('/api/agents/<agent_id>', methods=['GET'])
def get_agent(agent_id):
    """Get specific agent"""
    with system_lock:
        agent = next((a for a in agents if a['id'] == agent_id), None)
        if agent:
            return jsonify({'agent': agent})
        return jsonify({'error': 'Agent not found'}), 404

@app.route('/api/agents', methods=['POST'])
def create_agent():
    """Create a new agent"""
    try:
        data = request.json
        new_agent = {
            'id': f"agent-{uuid.uuid4().hex[:8]}",
            'name': data.get('name', 'New Agent'),
            'status': 'active',
            'role': data.get('role', 'general'),
            'created_at': datetime.now().isoformat()
        }
        
        with system_lock:
            agents.append(new_agent)
        
        socketio.emit('agent_created', new_agent)
        logger.info(f"Created new agent: {new_agent['name']}")
        
        return jsonify({'agent': new_agent, 'status': 'created'}), 201
    except Exception as e:
        logger.error(f"Error creating agent: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# STATE ENDPOINTS
# ============================================================================

@app.route('/api/states', methods=['GET'])
def get_states():
    """Get all states"""
    with system_lock:
        return jsonify({'states': states})

@app.route('/api/states/<state_id>', methods=['GET'])
def get_state(state_id):
    """Get specific state"""
    with system_lock:
        state = next((s for s in states if s['id'] == state_id), None)
        if state:
            return jsonify({'state': state})
        return jsonify({'error': 'State not found'}), 404

@app.route('/api/states', methods=['POST'])
def create_state():
    """Create a new state"""
    try:
        data = request.json
        new_state = {
            'id': f"state-{uuid.uuid4().hex[:8]}",
            'name': data.get('name', 'New State'),
            'description': data.get('description', ''),
            'timestamp': datetime.now().isoformat(),
            'components': data.get('components', []),
            'metrics': data.get('metrics', {})
        }
        
        with system_lock:
            states.append(new_state)
        
        socketio.emit('state_created', new_state)
        logger.info(f"Created new state: {new_state['name']}")
        
        return jsonify({'state': new_state, 'status': 'created'}), 201
    except Exception as e:
        logger.error(f"Error creating state: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# ARTIFACT ENDPOINTS
# ============================================================================

@app.route('/api/artifacts', methods=['GET'])
def get_artifacts():
    """Get all artifacts"""
    with system_lock:
        return jsonify({'artifacts': artifacts})

@app.route('/api/artifacts', methods=['POST'])
def create_artifact():
    """Create a new artifact"""
    try:
        data = request.json
        new_artifact = {
            'id': f"artifact-{uuid.uuid4().hex[:8]}",
            'name': data.get('name', 'New Artifact'),
            'type': data.get('type', 'document'),
            'content': data.get('content', ''),
            'metadata': data.get('metadata', {}),
            'created_at': datetime.now().isoformat()
        }
        
        with system_lock:
            artifacts.append(new_artifact)
        
        socketio.emit('artifact_created', new_artifact)
        logger.info(f"Created new artifact: {new_artifact['name']}")
        
        return jsonify({'artifact': new_artifact, 'status': 'created'}), 201
    except Exception as e:
        logger.error(f"Error creating artifact: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# WEBSOCKET EVENTS
# ============================================================================

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    logger.info(f"Client connected: {request.sid}")
    emit('connected', {'message': 'Connected to Murphy System'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    logger.info(f"Client disconnected: {request.sid}")

@socketio.on('ping')
def handle_ping():
    """Handle ping from client"""
    emit('pong', {'timestamp': datetime.now().isoformat()})

@socketio.on('terminal_command')
def handle_terminal_command(data):
    """Handle terminal command from client"""
    try:
        command = data.get('command', '')
        logger.info(f"Terminal command received: {command}")
        
        # Simulate command execution
        result = {
            'command': command,
            'output': f"Executed: {command}\nTimestamp: {datetime.now().isoformat()}",
            'timestamp': datetime.now().isoformat()
        }
        
        emit('terminal_output', result)
    except Exception as e:
        logger.error(f"Error handling terminal command: {e}")
        emit('terminal_error', {'error': str(e)})

# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f"Internal error: {error}")
    return jsonify({'error': 'Internal server error'}), 500

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    logger.info("Starting Murphy Minimal Server...")
    logger.info("Server will be available at http://0.0.0.0:3002")
    
    # Run the server
    socketio.run(app, host='0.0.0.0', port=3002, debug=True, allow_unsafe_werkzeug=True)