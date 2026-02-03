# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Murphy System Backend Server
Integrates the actual Murphy System runtime with the web frontend
"""

import os
import sys
import json
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit

# Add murphy_system to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'murphy_system', 'src'))

# Import Murphy System components
try:
    from mfgc_core import Phase, MFGCSystemState
    from advanced_swarm_system import SwarmType, AdvancedSwarmGenerator, SwarmCandidate
    from constraint_system import ConstraintType, ConstraintSeverity, Constraint, ConstraintSystem
    from gate_builder import GateBuilder
    from organization_chart_system import OrganizationChart, Department
    from llm_integration import LLMProvider, OllamaLLM
    MURPHY_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import Murphy System components: {e}")
    MURPHY_AVAILABLE = False

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Global system state
class MurphySystemRuntime:
    def __init__(self):
        self.initialized = False
        self.states = []
        self.artifacts = []
        self.gates = []
        self.swarms = []
        self.constraints = []
        self.state_counter = 0
        self.artifact_counter = 0
        
        # Initialize Murphy components if available
        if MURPHY_AVAILABLE:
            self.mfgc_state = MFGCSystemState()
            self.swarm_generator = AdvancedSwarmGenerator()
            self.constraint_system = ConstraintSystem()
            self.gate_builder = GateBuilder()
            self.org_chart = OrganizationChart()
        else:
            self.mfgc_state = None
            self.swarm_generator = None
            self.constraint_system = None
            self.gate_builder = None
            self.org_chart = None
        
        # LLM integrations
        self.llms = {
            'groq': {'active': False, 'provider': None},
            'aristotle': {'active': False, 'provider': None},
            'onboard': {'active': False, 'provider': None}
        }
    
    def create_state(self, name: str, description: str, parent_id: Optional[str] = None, 
                    swarm_type: str = 'hybrid') -> Dict[str, Any]:
        """Create a new state in the system"""
        state = {
            'id': f'STATE-{self.state_counter}',
            'name': name,
            'description': description,
            'parent_id': parent_id,
            'children': [],
            'confidence': 0.5 + (0.3 * (self.state_counter / 10)),  # Gradually increase
            'swarm_type': swarm_type,
            'phase': self.mfgc_state.p_t.value if self.mfgc_state else 'expand',
            'artifacts': [],
            'gates': [],
            'timestamp': datetime.now().isoformat()
        }
        
        self.state_counter += 1
        self.states.append(state)
        
        # Update parent's children
        if parent_id:
            parent = next((s for s in self.states if s['id'] == parent_id), None)
            if parent:
                parent['children'].append(state['id'])
        
        # Emit state creation event
        socketio.emit('state_created', state)
        
        return state
    
    def create_artifact(self, name: str, artifact_type: str, state_id: str, 
                       content: str) -> Dict[str, Any]:
        """Create an artifact"""
        artifact = {
            'id': f'ARTIFACT-{self.artifact_counter}',
            'name': name,
            'type': artifact_type,
            'state_id': state_id,
            'content': content,
            'confidence': 0.7 + (0.2 * (self.artifact_counter / 10)),
            'timestamp': datetime.now().isoformat()
        }
        
        self.artifact_counter += 1
        self.artifacts.append(artifact)
        
        # Update state's artifacts
        state = next((s for s in self.states if s['id'] == state_id), None)
        if state:
            state['artifacts'].append(artifact['id'])
        
        # Emit artifact creation event
        socketio.emit('artifact_created', artifact)
        
        return artifact
    
    def create_gate(self, gate_key: str, state_id: str) -> Dict[str, Any]:
        """Create a safety gate"""
        gate_templates = {
            'data_loss': {'name': 'Data Loss Prevention', 'severity': 0.8},
            'security_breach': {'name': 'Security Gate', 'severity': 0.9},
            'invalid_input': {'name': 'Input Validation', 'severity': 0.7},
            'system_overload': {'name': 'Load Balancing', 'severity': 0.6},
            'data_corruption': {'name': 'Data Integrity', 'severity': 0.8},
            'unauthorized_action': {'name': 'Authorization', 'severity': 0.9},
            'performance_degradation': {'name': 'Performance', 'severity': 0.5},
            'compliance_violation': {'name': 'Compliance', 'severity': 0.9},
            'resource_exhaustion': {'name': 'Resource', 'severity': 0.7},
            'dependency_failure': {'name': 'Dependency', 'severity': 0.6}
        }
        
        template = gate_templates.get(gate_key, {'name': 'Unknown Gate', 'severity': 0.5})
        
        gate = {
            'id': f'GATE-{len(self.gates)}',
            'key': gate_key,
            'name': template['name'],
            'severity': template['severity'],
            'state_id': state_id,
            'active': True,
            'timestamp': datetime.now().isoformat()
        }
        
        self.gates.append(gate)
        
        # Update state's gates
        state = next((s for s in self.states if s['id'] == state_id), None)
        if state:
            state['gates'].append(gate['id'])
        
        # Emit gate creation event
        socketio.emit('gate_created', gate)
        
        return gate
    
    def create_swarm(self, swarm_type: str, state_id: str, purpose: str) -> Dict[str, Any]:
        """Create a swarm"""
        swarm = {
            'id': f'SWARM-{len(self.swarms)}',
            'type': swarm_type,
            'state_id': state_id,
            'purpose': purpose,
            'progress': 0,
            'active': True,
            'timestamp': datetime.now().isoformat()
        }
        
        self.swarms.append(swarm)
        
        # Emit swarm creation event
        socketio.emit('swarm_created', swarm)
        
        # Start swarm progress simulation
        asyncio.create_task(self.simulate_swarm_progress(swarm['id']))
        
        return swarm
    
    async def simulate_swarm_progress(self, swarm_id: str):
        """Simulate swarm progress"""
        swarm = next((s for s in self.swarms if s['id'] == swarm_id), None)
        if not swarm:
            return
        
        while swarm['progress'] < 100 and swarm['active']:
            await asyncio.sleep(1)
            swarm['progress'] += 10 + (20 * (1 - swarm['progress'] / 100))
            
            if swarm['progress'] >= 100:
                swarm['progress'] = 100
                swarm['active'] = False
                
                # Create artifact when swarm completes
                artifact = self.create_artifact(
                    f"{swarm['type'].title()} Analysis",
                    'analysis',
                    swarm['state_id'],
                    f"Generated by {swarm['type']} swarm"
                )
                
                socketio.emit('swarm_completed', {
                    'swarm': swarm,
                    'artifact': artifact
                })
            else:
                socketio.emit('swarm_progress', swarm)
    
    def create_constraint(self, constraint_type: str, name: str, value: str) -> Dict[str, Any]:
        """Create a constraint"""
        constraint = {
            'id': f'CONSTRAINT-{len(self.constraints)}',
            'type': constraint_type,
            'name': name,
            'value': value,
            'active': True,
            'timestamp': datetime.now().isoformat()
        }
        
        self.constraints.append(constraint)
        
        # Emit constraint creation event
        socketio.emit('constraint_created', constraint)
        
        return constraint
    
    def toggle_llm(self, llm_name: str) -> Dict[str, Any]:
        """Toggle LLM on/off"""
        if llm_name not in self.llms:
            return {'error': 'Unknown LLM'}
        
        self.llms[llm_name]['active'] = not self.llms[llm_name]['active']
        
        # Initialize LLM if activating
        if self.llms[llm_name]['active'] and not self.llms[llm_name]['provider']:
            if llm_name == 'onboard' and MURPHY_AVAILABLE:
                try:
                    self.llms[llm_name]['provider'] = OllamaLLM()
                except Exception as e:
                    print(f"Could not initialize {llm_name}: {e}")
        
        return {
            'llm': llm_name,
            'active': self.llms[llm_name]['active']
        }
    
    def advance_phase(self) -> Dict[str, Any]:
        """Advance to next phase"""
        if not self.mfgc_state:
            return {'error': 'MFGC not available'}
        
        current_phase = self.mfgc_state.p_t
        current_confidence = self.mfgc_state.c_t
        
        # Check if we can advance
        if current_confidence >= current_phase.confidence_threshold:
            self.mfgc_state.advance_phase()
            
            return {
                'success': True,
                'old_phase': current_phase.value,
                'new_phase': self.mfgc_state.p_t.value,
                'confidence': current_confidence
            }
        else:
            return {
                'success': False,
                'reason': f'Confidence {current_confidence:.2f} < {current_phase.confidence_threshold}',
                'current_phase': current_phase.value
            }
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get complete system status"""
        return {
            'initialized': self.initialized,
            'phase': self.mfgc_state.p_t.value if self.mfgc_state else 'expand',
            'confidence': self.mfgc_state.c_t if self.mfgc_state else 0.0,
            'murphy_index': self.mfgc_state.M_t if self.mfgc_state else 0.0,
            'states_count': len(self.states),
            'artifacts_count': len(self.artifacts),
            'gates_count': len([g for g in self.gates if g['active']]),
            'swarms_count': len([s for s in self.swarms if s['active']]),
            'constraints_count': len(self.constraints),
            'llms': {k: v['active'] for k, v in self.llms.items()}
        }

# Global runtime instance
runtime = MurphySystemRuntime()

# REST API Endpoints

@app.route('/api/initialize', methods=['POST'])
def initialize_system():
    """Initialize the Murphy System"""
    if runtime.initialized:
        return jsonify({'error': 'Already initialized'}), 400
    
    # Create root state
    root = runtime.create_state(
        'System Initialization',
        'Root state for Murphy System runtime',
        None,
        'analytical'
    )
    
    # Create initial constraints
    runtime.create_constraint('budget', 'Project Budget', '$100,000')
    runtime.create_constraint('time', 'Timeline', '6 months')
    runtime.create_constraint('security', 'Security Level', 'High')
    
    # Create initial gates
    runtime.create_gate('security_breach', root['id'])
    runtime.create_gate('invalid_input', root['id'])
    runtime.create_gate('resource_exhaustion', root['id'])
    
    # Create initial swarms
    runtime.create_swarm('analytical', root['id'], 'Analyze system requirements')
    runtime.create_swarm('creative', root['id'], 'Generate innovative solutions')
    
    # Create child states
    child_states = [
        'Requirements Analysis',
        'Architecture Design',
        'Implementation Planning',
        'Testing Strategy',
        'Deployment Plan'
    ]
    
    for name in child_states:
        state = runtime.create_state(name, f'{name} for the system', root['id'], 'hybrid')
        runtime.create_swarm('hybrid', state['id'], f'Process {name}')
    
    runtime.initialized = True
    
    return jsonify({
        'success': True,
        'root_state': root,
        'status': runtime.get_system_status()
    })

@app.route('/api/status', methods=['GET'])
def get_status():
    """Get system status"""
    return jsonify(runtime.get_system_status())

@app.route('/api/states', methods=['GET'])
def get_states():
    """Get all states"""
    return jsonify(runtime.states)

@app.route('/api/states/<state_id>', methods=['GET'])
def get_state(state_id):
    """Get specific state"""
    state = next((s for s in runtime.states if s['id'] == state_id), None)
    if not state:
        return jsonify({'error': 'State not found'}), 404
    return jsonify(state)

@app.route('/api/states/<state_id>/evolve', methods=['POST'])
def evolve_state(state_id):
    """Evolve a state"""
    parent = next((s for s in runtime.states if s['id'] == state_id), None)
    if not parent:
        return jsonify({'error': 'State not found'}), 404
    
    # Create child state
    child = runtime.create_state(
        f"Evolution of {parent['name']}",
        f"Evolved from {parent['id']} with enhanced capabilities",
        parent['id'],
        'hybrid'
    )
    
    # Create swarm for new state
    runtime.create_swarm('hybrid', child['id'], 'Analyze evolved state')
    
    # Create gate for new state
    runtime.create_gate('invalid_input', child['id'])
    
    return jsonify({
        'success': True,
        'parent': parent,
        'child': child
    })

@app.route('/api/states/<state_id>/regenerate', methods=['POST'])
def regenerate_state(state_id):
    """Regenerate a state"""
    state = next((s for s in runtime.states if s['id'] == state_id), None)
    if not state:
        return jsonify({'error': 'State not found'}), 404
    
    # Update confidence
    import random
    state['confidence'] = random.random() * 0.3 + 0.6
    
    # Create new swarm
    runtime.create_swarm('creative', state['id'], 'Regenerate with creative approach')
    
    socketio.emit('state_updated', state)
    
    return jsonify({
        'success': True,
        'state': state
    })

@app.route('/api/llm/<llm_name>/toggle', methods=['POST'])
def toggle_llm(llm_name):
    """Toggle LLM on/off"""
    result = runtime.toggle_llm(llm_name)
    return jsonify(result)

@app.route('/api/phase/advance', methods=['POST'])
def advance_phase():
    """Advance to next phase"""
    result = runtime.advance_phase()
    return jsonify(result)

@app.route('/api/constraints', methods=['POST'])
def create_constraint():
    """Create a constraint"""
    data = request.json
    constraint = runtime.create_constraint(
        data.get('type', 'business'),
        data.get('name', 'Unnamed Constraint'),
        data.get('value', 'N/A')
    )
    return jsonify(constraint)

@app.route('/api/artifacts', methods=['GET'])
def get_artifacts():
    """Get all artifacts"""
    return jsonify(runtime.artifacts)

@app.route('/api/gates', methods=['GET'])
def get_gates():
    """Get all gates"""
    return jsonify(runtime.gates)

@app.route('/api/swarms', methods=['GET'])
def get_swarms():
    """Get all swarms"""
    return jsonify(runtime.swarms)

@app.route('/api/constraints', methods=['GET'])
def get_constraints():
    """Get all constraints"""
    return jsonify(runtime.constraints)

@app.route('/')
def index():
    """Serve the frontend"""
    return app.send_static_file('index.html')

# Serve static files
import os
app.static_folder = '/workspace'
app.static_url_path = ''

# WebSocket Events

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    emit('connected', {'status': 'Connected to Murphy System Backend'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print('Client disconnected')

@socketio.on('execute_command')
def handle_command(data):
    """Handle command execution"""
    command = data.get('command', '').strip().lower()
    
    if command == 'status':
        emit('command_result', runtime.get_system_status())
    elif command == 'advance':
        result = runtime.advance_phase()
        emit('command_result', result)
    elif command.startswith('evolve '):
        state_id = command.split(' ')[1]
        # Execute evolve
        emit('command_result', {'message': f'Evolving {state_id}'})
    else:
        emit('command_result', {'error': 'Unknown command'})

if __name__ == '__main__':
    print("=" * 60)
    print("Murphy System Backend Server")
    print("=" * 60)
    print(f"Murphy System Available: {MURPHY_AVAILABLE}")
    print("Starting server on http://localhost:6666")
    print("=" * 60)
    
    socketio.run(app, host='0.0.0.0', port=6666, debug=False, allow_unsafe_werkzeug=True)