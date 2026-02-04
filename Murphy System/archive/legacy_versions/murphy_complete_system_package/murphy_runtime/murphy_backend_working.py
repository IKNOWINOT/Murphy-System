# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Murphy System - Working Backend with LLM Integration
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import logging
import subprocess
import os
import uuid
from datetime import datetime
import json

# Try to import LLM providers
try:
    from llm_providers import LLMManager
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'murphy-working-secret'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize LLM Manager if available
llm_manager = None
if LLM_AVAILABLE:
    try:
        groq_keys = []
        if os.path.exists('groq_keys.txt'):
            with open('groq_keys.txt', 'r') as f:
                groq_keys = [line.strip() for line in f if line.strip()]
        llm_manager = LLMManager(groq_api_keys=groq_keys)
        logger.info(f"✓ LLM Manager initialized with {len(groq_keys)} keys")
    except Exception as e:
        logger.error(f"Failed to initialize LLM Manager: {e}")
        llm_manager = None

# Global state
system_initialized = False
artifacts = []
commands_history = []

# ============================================================================
# ACTUAL WORKING ENDPOINTS
# ============================================================================

@app.route('/')
def index():
    return send_from_directory('.', 'murphy_complete_v2.html')

@app.route('/api/status', methods=['GET'])
def status():
    return jsonify({
        'status': 'running',
        'initialized': system_initialized,
        'llm_available': LLM_AVAILABLE,
        'artifacts_count': len(artifacts),
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/initialize', methods=['POST'])
def initialize():
    global system_initialized
    system_initialized = True
    return jsonify({'status': 'initialized', 'message': 'System ready'})

@app.route('/api/llm/generate', methods=['POST'])
def llm_generate():
    """Actually generate content using LLM"""
    if not llm_manager:
        return jsonify({'error': 'LLM not available'}), 503
    
    data = request.json
    prompt = data.get('prompt', '')
    if not prompt:
        return jsonify({'error': 'No prompt provided'}), 400
    
    try:
        # Generate using LLM
        response = llm_manager.generate(prompt)
        return jsonify({
            'success': True,
            'response': response,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"LLM error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/command/execute', methods=['POST'])
def execute_command():
    """Actually execute terminal commands"""
    data = request.json
    command = data.get('command', '')
    
    if not command:
        return jsonify({'error': 'No command provided'}), 400
    
    # Security: Only allow safe commands
    dangerous = ['rm ', 'sudo ', 'mkfs', 'dd ', '>', '|']
    if any(d in command for d in dangerous):
        return jsonify({'error': 'Command not allowed for security'}), 403
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        commands_history.append({
            'command': command,
            'output': result.stdout,
            'error': result.stderr,
            'return_code': result.returncode,
            'timestamp': datetime.now().isoformat()
        })
        
        socketio.emit('command_executed', {
            'command': command,
            'output': result.stdout
        })
        
        return jsonify({
            'success': True,
            'output': result.stdout,
            'error': result.stderr,
            'return_code': result.returncode
        })
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Command timed out'}), 408
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/artifacts/create', methods=['POST'])
def create_artifact():
    """Actually create files/artifacts"""
    data = request.json
    content = data.get('content', '')
    filename = data.get('filename', f'artifact_{uuid.uuid4().hex[:8]}.txt')
    
    if not content:
        return jsonify({'error': 'No content provided'}), 400
    
    try:
        filepath = os.path.join('/workspace', filename)
        with open(filepath, 'w') as f:
            f.write(content)
        
        artifact = {
            'id': str(uuid.uuid4()),
            'filename': filename,
            'path': filepath,
            'created_at': datetime.now().isoformat()
        }
        artifacts.append(artifact)
        
        socketio.emit('artifact_created', artifact)
        
        return jsonify({
            'success': True,
            'artifact': artifact
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/artifacts', methods=['GET'])
def list_artifacts():
    return jsonify({'artifacts': artifacts})

@app.route('/api/artifacts/<artifact_id>', methods=['GET'])
def get_artifact(artifact_id):
    artifact = next((a for a in artifacts if a['id'] == artifact_id), None)
    if not artifact:
        return jsonify({'error': 'Not found'}), 404
    
    try:
        with open(artifact['path'], 'r') as f:
            content = f.read()
        return jsonify({'artifact': artifact, 'content': content})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# WEBSOCKET EVENTS
# ============================================================================

@socketio.on('connect')
def handle_connect():
    emit('connected', {'message': 'Connected to working Murphy System'})

@socketio.on('execute_command')
def handle_command(data):
    command = data.get('command', '')
    if command:
        # Execute via the endpoint
        result = execute_command_endpoint(command)
        emit('command_result', result)

def execute_command_endpoint(command):
    """Helper to execute commands"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        return {
            'success': True,
            'output': result.stdout,
            'error': result.stderr
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

if __name__ == '__main__':
    logger.info("Starting Murphy Working Backend...")
    logger.info("LLM Available: " + str(LLM_AVAILABLE))
    logger.info("This backend CAN actually create and execute things!")
    socketio.run(app, host='0.0.0.0', port=3002, debug=False, allow_unsafe_werkzeug=True)
