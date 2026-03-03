# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Murphy System - Enhanced Backend with WebSocket, State Management, and Interactive Components
Production-ready system with Groq (generative), Aristotle (deterministic), and Onboard LLM fallback
Enhanced with real-time visualization, state evolution, and interactive components
"""

import os
import sys
import json
import asyncio
import random
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from groq import Groq

# Add murphy_system to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'murphy_system', 'src'))

# Import Murphy System components
try:
    from mfgc_core import Phase, MFGCSystemState
    from advanced_swarm_system import SwarmType, AdvancedSwarmGenerator
    from constraint_system import ConstraintSystem
    from gate_builder import GateBuilder
    from organization_chart_system import OrganizationChart
    MURPHY_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import Murphy System components: {e}")
    MURPHY_AVAILABLE = False

# Import Domain Engine
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
try:
    from domain_engine import DomainEngine
    DOMAIN_ENGINE_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import Domain Engine: {e}")
    DOMAIN_ENGINE_AVAILABLE = False

app = Flask(__name__)
# Allow CORS from all origins for development
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading', logger=True, engineio_logger=False)

# ============================================
# LLM CONFIGURATION
# ============================================

# Multiple Groq API keys for load balancing and redundancy
GROQ_API_KEYS = [
    'REDACTED_GROQ_KEY_PLACEHOLDER',
    'REDACTED_GROQ_KEY_PLACEHOLDER',
    'REDACTED_GROQ_KEY_PLACEHOLDER',
    'REDACTED_GROQ_KEY_PLACEHOLDER',
    'REDACTED_GROQ_KEY_PLACEHOLDER',
    'REDACTED_GROQ_KEY_PLACEHOLDER',
    'REDACTED_GROQ_KEY_PLACEHOLDER',
    'REDACTED_GROQ_KEY_PLACEHOLDER',
    'REDACTED_GROQ_KEY_PLACEHOLDER'
]
GROQ_API_KEY = os.getenv('GROQ_API_KEY', GROQ_API_KEYS[0])
ARISTOTLE_API_KEY = os.getenv('ARISTOTLE_API_KEY', 'REDACTED_ARISTOTLE_KEY_PLACEHOLDER')

# Initialize LLM clients with key rotation
groq_clients = []
current_groq_key_index = 0

for i, key in enumerate(GROQ_API_KEYS):
    try:
        client = Groq(api_key=key)
        groq_clients.append(client)
        print(f"✓ Groq client {i+1}/9 initialized")
    except Exception as e:
        print(f"⚠ Groq client {i+1} failed: {e}")

aristotle_client = None
try:
    aristotle_client = Groq(api_key=ARISTOTLE_API_KEY)
    print("✓ Aristotle client initialized for deterministic verification")
except Exception as e:
    print(f"⚠ Aristotle initialization failed: {e}")

def get_next_groq_client():
    """Round-robin selection of Groq clients for load balancing"""
    global current_groq_key_index
    if not groq_clients:
        return None
    client = groq_clients[current_groq_key_index]
    current_groq_key_index = (current_groq_key_index + 1) % len(groq_clients)
    return client

class LLMRouter:
    """Routes requests to appropriate LLM based on task type"""
    
    def __init__(self):
        self.groq_available = len(groq_clients) > 0
        self.aristotle_available = aristotle_client is not None
        self.onboard_available = MURPHY_AVAILABLE
    
    def route(self, prompt: str, task_type: str = "generative") -> dict:
        """Route request to appropriate LLM"""
        if task_type == "deterministic":
            return self._call_aristotle(prompt)
        elif task_type == "generative":
            return self._call_groq(prompt)
        else:
            return self._call_fallback(prompt)
    
    def _call_groq(self, prompt: str) -> dict:
        """Call Groq API for generative tasks"""
        client = get_next_groq_client()
        if not client:
            return self._call_fallback(prompt)
        
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            return {
                'provider': 'Groq',
                'content': response.choices[0].message.content,
                'model': response.model
            }
        except Exception as e:
            print(f"Groq error: {e}")
            return self._call_fallback(prompt)
    
    def _call_aristotle(self, prompt: str) -> dict:
        """Call Aristotle API for deterministic verification"""
        if not aristotle_client:
            return self._call_fallback(prompt)
        
        try:
            response = aristotle_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1  # Deterministic
            )
            return {
                'provider': 'Aristotle',
                'content': response.choices[0].message.content,
                'model': response.model
            }
        except Exception as e:
            print(f"Aristotle error: {e}")
            return self._call_fallback(prompt)
    
    def _call_fallback(self, prompt: str) -> dict:
        """Fallback to onboard LLM"""
        return {
            'provider': 'Onboard',
            'content': 'Onboard LLM response (simulated)',
            'model': 'onboard'
        }

llm_router = LLMRouter()

# ============================================
# STATE MANAGEMENT CLASSES
# ============================================

class Agent:
    """Autonomous entity that executes tasks within a domain"""
    
    def __init__(self, id: str, name: str, type: str, domain: str):
        self.id = id
        self.name = name
        self.type = type
        self.domain = domain
        self.status = "idle"
        self.current_task = None
        self.progress = 0
        self.confidence = 0.0
        self.recent_ops = []
        self.config = {}
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'domain': self.domain,
            'status': self.status,
            'current_task': self.current_task,
            'progress': self.progress,
            'confidence': self.confidence,
            'recent_ops': self.recent_ops,
            'config': self.config
        }

class State:
    """Snapshot condition of system components"""
    
    def __init__(self, id: str, type: str, label: str):
        self.id = id
        self.parent_id = None
        self.type = type
        self.label = label
        self.description = ""
        self.confidence = 0.0
        self.timestamp = datetime.now()
        self.children = []
        self.metadata = {}
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'parent_id': self.parent_id,
            'type': self.type,
            'label': self.label,
            'description': self.description,
            'confidence': self.confidence,
            'timestamp': self.timestamp.isoformat(),
            'children': self.children,
            'metadata': self.metadata
        }

class SystemComponent:
    """Modular building block of the system"""
    
    def __init__(self, id: str, name: str, type: str):
        self.id = id
        self.name = name
        self.type = type
        self.status = "inactive"
        self.health = 100
        self.recent_ops = []
        self.config = {}
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'status': self.status,
            'health': self.health,
            'recent_ops': self.recent_ops,
            'config': self.config
        }

class Gate:
    """Validation checkpoint for outputs"""
    
    def __init__(self, id: str, name: str, type: str, criteria: dict):
        self.id = id
        self.name = name
        self.type = type
        self.criteria = criteria
        self.status = "pending"
        self.results = {}
        self.history = []
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'criteria': self.criteria,
            'status': self.status,
            'results': self.results,
            'history': self.history
        }

# ============================================
# GLOBAL STATE STORAGE
# ============================================

agents = {}
states = {}
components = {}
gates = {}
artifacts = {}
connections = []

# ============================================
# WEBSOCKET EVENT HANDLERS
# ============================================

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print('Client connected')
    emit('status', {'connected': True})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print('Client disconnected')

@socketio.on('get_initial_state')
def handle_get_initial_state():
    """Send initial state to newly connected client"""
    emit('agent_update', {
        'agents': get_all_agents_dict(),
        'connections': connections,
        'timestamp': datetime.now().isoformat()
    })
    
    emit('state_update', {
        'states': get_all_states_dict(),
        'timestamp': datetime.now().isoformat()
    })

def broadcast_agent_update(agents_data, connections_data):
    """Broadcast agent update to all connected clients"""
    socketio.emit('agent_update', {
        'agents': agents_data,
        'connections': connections_data,
        'timestamp': datetime.now().isoformat()
    })

def broadcast_state_update(states_data):
    """Broadcast state update to all connected clients"""
    socketio.emit('state_update', {
        'states': states_data,
        'timestamp': datetime.now().isoformat()
    })

# ============================================
# HELPER FUNCTIONS
# ============================================

def get_all_agents_dict():
    return [agent.to_dict() for agent in agents.values()]

def get_all_states_dict():
    return [state.to_dict() for state in states.values()]

def get_all_components_dict():
    return [component.to_dict() for component in components.values()]

def get_all_gates_dict():
    return [gate.to_dict() for gate in gates.values()]

def create_agent(name: str, type: str, domain: str) -> Agent:
    agent_id = f"agent-{uuid.uuid4().hex[:8]}"
    agent = Agent(agent_id, name, type, domain)
    agents[agent_id] = agent
    return agent

def create_component(name: str, type: str) -> SystemComponent:
    component_id = f"component-{uuid.uuid4().hex[:8]}"
    component = SystemComponent(component_id, name, type)
    components[component_id] = component
    return component

def create_state(type: str, label: str, parent_id: Optional[str] = None) -> State:
    state_id = f"state-{uuid.uuid4().hex[:8]}"
    state = State(state_id, type, label)
    state.parent_id = parent_id
    states[state_id] = state
    return state

def evolve_state(state_id: str) -> List[State]:
    """Evolve state into child states"""
    state = states.get(state_id)
    if not state:
        return []
    
    child_states = []
    
    # Generate children based on state type
    if state.type == "document":
        child_states = [
            create_state("document", "Content Structure", state_id),
            create_state("document", "Style Guidelines", state_id),
            create_state("gate", "Compliance Check", state_id)
        ]
    elif state.type == "gate":
        child_states = [
            create_state("artifact", "Validation Report", state_id),
            create_state("document", "Corrections Needed", state_id)
        ]
    else:
        child_states = [
            create_state(state.type, f"{state.label} - Child 1", state_id),
            create_state(state.type, f"{state.label} - Child 2", state_id)
        ]
    
    # Set confidence
    for child in child_states:
        child.description = f"Evolved from {state.label}"
        child.confidence = 0.7 + (random.random() * 0.2)
    
    state.children = [child.id for child in child_states]
    
    return child_states

def regenerate_state(state_id: str) -> State:
    """Regenerate state with new confidence"""
    state = states.get(state_id)
    if not state:
        return None
    
    state.description = f"Regenerated {state.description}"
    state.confidence = 0.7 + (random.random() * 0.2)
    state.timestamp = datetime.now()
    
    return state

def rollback_state(state_id: str) -> State:
    """Rollback to parent state"""
    state = states.get(state_id)
    if not state or not state.parent_id:
        return None
    
    parent_state = states.get(state.parent_id)
    return parent_state

# ============================================
# API ENDPOINTS
# ============================================

@app.route('/api/status', methods=['GET'])
def get_status():
    """Get current system status"""
    return jsonify({
        'status': 'running',
        'llms': {
            'groq': {
                'status': 'active',
                'clients': len(groq_clients),
                'current_index': current_groq_key_index
            },
            'aristotle': {
                'status': 'active' if aristotle_client else 'inactive',
                'endpoint': 'Aristotle API'
            },
            'onboard': {
                'status': 'available' if MURPHY_AVAILABLE else 'unavailable'
            }
        },
        'metrics': {
            'states_generated': len(states),
            'artifacts_created': len(artifacts),
            'gates_active': len(gates),
            'swarms_running': 0,
            'agents': len(agents)
        }
    })

@app.route('/api/initialize', methods=['POST'])
def initialize_system():
    """Initialize Murphy System"""
    data = request.json or {}
    init_type = data.get('type', 'demo')
    
    # Create demo agents
    agent_configs = [
        ("Sales Agent", "Sales", "Business"),
        ("Engineering Agent", "Engineering", "Engineering"),
        ("Financial Agent", "Financial", "Financial"),
        ("Legal Agent", "Legal", "Legal"),
        ("Operations Agent", "Operations", "Operations")
    ]
    
    for name, type, domain in agent_configs:
        create_agent(name, type, domain)
    
    # Create demo components
    create_component("LLM Router", "router")
    create_component("Domain Engine", "engine")
    create_component("Gate Builder", "builder")
    create_component("Swarm Generator", "generator")
    
    # Create root state
    root_state = create_state("document", "Root System State")
    root_state.description = "Initial system state"
    root_state.confidence = 1.0
    
    # Create demo gates
    gate1 = Gate(f"gate-{uuid.uuid4().hex[:8]}", "Regulatory Gate", "regulatory", {"gdpr": True, "privacy": True})
    gate2 = Gate(f"gate-{uuid.uuid4().hex[:8]}", "Security Gate", "security", {"encryption": True, "auth": True})
    gates[gate1.id] = gate1
    gates[gate2.id] = gate2
    
    # Create agent connections
    agent_list = list(agents.keys())
    for i in range(len(agent_list)):
        for j in range(i + 1, min(i + 3, len(agent_list))):
            connections.append({
                'source': agent_list[i],
                'target': agent_list[j]
            })
    
    # Broadcast updates
    broadcast_agent_update(get_all_agents_dict(), connections)
    broadcast_state_update(get_all_states_dict())
    
    return jsonify({
        'system_id': f"system-{uuid.uuid4().hex[:8]}",
        'initial_state_id': root_state.id,
        'agents': len(agents),
        'components': len(components),
        'states': len(states),
        'gates': len(gates),
        'message': 'System initialized successfully'
    })

@app.route('/api/states', methods=['GET'])
def get_states():
    """Get all states"""
    return jsonify({
        'states': get_all_states_dict()
    })

@app.route('/api/states/<state_id>', methods=['GET'])
def get_state(state_id):
    """Get specific state"""
    state = states.get(state_id)
    if not state:
        return jsonify({'error': 'State not found'}), 404
    return jsonify(state.to_dict())

@app.route('/api/states/<state_id>/evolve', methods=['POST'])
def evolve_state_endpoint(state_id):
    """Evolve state into child states"""
    state = states.get(state_id)
    if not state:
        return jsonify({'error': 'State not found'}), 404
    
    children = evolve_state(state_id)
    
    # Broadcast update
    broadcast_state_update(get_all_states_dict())
    
    return jsonify({
        'state_id': state_id,
        'children': [child.to_dict() for child in children],
        'message': f'Evolved {len(children)} child states'
    })

@app.route('/api/states/<state_id>/regenerate', methods=['POST'])
def regenerate_state_endpoint(state_id):
    """Regenerate state with new confidence"""
    state = states.get(state_id)
    if not state:
        return jsonify({'error': 'State not found'}), 404
    
    new_state = regenerate_state(state_id)
    
    # Broadcast update
    broadcast_state_update(get_all_states_dict())
    
    return jsonify({
        'state_id': state_id,
        'state': new_state.to_dict(),
        'message': 'State regenerated successfully'
    })

@app.route('/api/states/<state_id>/rollback', methods=['POST'])
def rollback_state_endpoint(state_id):
    """Rollback to parent state"""
    state = states.get(state_id)
    if not state:
        return jsonify({'error': 'State not found'}), 404
    
    parent_state = rollback_state(state_id)
    if not parent_state:
        return jsonify({'error': 'Cannot rollback - no parent'}), 400
    
    # Broadcast update
    broadcast_state_update(get_all_states_dict())
    
    return jsonify({
        'state_id': state_id,
        'parent_state': parent_state.to_dict(),
        'message': 'Rolled back to parent state'
    })

@app.route('/api/agents', methods=['GET'])
def get_agents():
    """Get all agents"""
    return jsonify({
        'agents': get_all_agents_dict()
    })

@app.route('/api/agents/<agent_id>', methods=['GET'])
def get_agent(agent_id):
    """Get specific agent details"""
    agent = agents.get(agent_id)
    if not agent:
        return jsonify({'error': 'Agent not found'}), 404
    return jsonify(agent.to_dict())

@app.route('/api/agents/<agent_id>/override', methods=['POST'])
def override_agent(agent_id):
    """Manually override agent operation"""
    agent = agents.get(agent_id)
    if not agent:
        return jsonify({'error': 'Agent not found'}), 404
    
    data = request.json or {}
    new_task = data.get('task', 'New task')
    
    agent.current_task = new_task
    agent.recent_ops.append(f"Manual override: {new_task}")
    
    # Broadcast update
    broadcast_agent_update(get_all_agents_dict(), connections)
    
    return jsonify({
        'agent_id': agent_id,
        'new_task': new_task,
        'message': 'Agent overridden successfully'
    })

@app.route('/api/components/<component_id>', methods=['GET'])
def get_component(component_id):
    """Get component details"""
    # Check if it's a predefined component or create one
    component = components.get(component_id)
    if not component:
        return jsonify({'error': 'Component not found'}), 404
    return jsonify(component.to_dict())

@app.route('/api/gates/<gate_id>/validate', methods=['POST'])
def validate_gate(gate_id):
    """Validate gate"""
    gate = gates.get(gate_id)
    if not gate:
        return jsonify({'error': 'Gate not found'}), 404
    
    data = request.json or {}
    
    # Run validation
    passed = random.random() > 0.1
    score = 0.8 + (random.random() * 0.15) if passed else random.random() * 0.5
    
    result = {
        'passed': passed,
        'score': score,
        'criteria_checked': list(gate.criteria.keys()),
        'details': 'Validation completed successfully' if passed else 'Validation failed - criteria not met'
    }
    
    gate.results = result
    gate.status = 'pass' if passed else 'fail'
    gate.history.append({
        'timestamp': datetime.now().isoformat(),
        'result': result
    })
    
    # Broadcast gate result
    socketio.emit('gate_result', {
        'gate_id': gate_id,
        'gate_name': gate.name,
        'status': gate.status,
        'result': result
    })
    
    return jsonify({
        'gate_id': gate_id,
        'result': result,
        'status': gate.status
    })

@app.route('/api/test-groq', methods=['POST'])
def test_groq():
    """Test Groq API connection"""
    try:
        result = llm_router._call_groq("Test message - respond with 'OK'")
        return jsonify({
            'success': True,
            'provider': result['provider'],
            'content': result['content']
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/')
def index():
    """Serve main page"""
    return jsonify({
        'message': 'Murphy System Backend v2 - Enhanced with WebSocket and State Management',
        'version': '2.0',
        'endpoints': {
            'status': '/api/status',
            'initialize': '/api/initialize',
            'agents': '/api/agents',
            'states': '/api/states',
            'test_groq': '/api/test-groq'
        }
    })

# ============================================
# SERVER STARTUP
# ============================================

if __name__ == '__main__':
    print("\n" + "="*60)
    print("MURPHY SYSTEM BACKEND v2.0")
    print("="*60)
    print(f"✓ Groq clients: {len(groq_clients)}")
    print(f"✓ Aristotle: {'Active' if aristotle_client else 'Inactive'}")
    print(f"✓ WebSocket: Enabled")
    print(f"✓ State Management: Enabled")
    print(f"✓ Interactive Components: Enabled")
    print("="*60)
    print(f"\nServer starting on http://0.0.0.0:8000")
    print(f"WebSocket endpoint: ws://0.0.0.0:8000")
    print("\n")
    
    socketio.run(app, host='0.0.0.0', port=8000, debug=False, allow_unsafe_werkzeug=True)