#!/usr/bin/env python3
"""
Murphy System Unified Server
Runs both backend API and serves frontend from the same process on port 3000
"""

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from groq import Groq
import os
import sys
import uuid
import time
from datetime import datetime
from threading import Lock
import asyncio
from librarian_system import LibrarianSystem, IntentCategory, ConfidenceLevel

# Initialize Flask app
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# ===== GROQ API KEYS =====
GROQ_API_KEYS = [
    "REDACTED_GROQ_KEY_PLACEHOLDER",
    "REDACTED_GROQ_KEY_PLACEHOLDER",
    "REDACTED_GROQ_KEY_PLACEHOLDER",
    "REDACTED_GROQ_KEY_PLACEHOLDER",
    "REDACTED_GROQ_KEY_PLACEHOLDER",
    "REDACTED_GROQ_KEY_PLACEHOLDER",
    "REDACTED_GROQ_KEY_PLACEHOLDER",
    "REDACTED_GROQ_KEY_PLACEHOLDER",
    "REDACTED_GROQ_KEY_PLACEHOLDER"
]

ARISTOTLE_API_KEY = "REDACTED_ARISTOTLE_KEY_PLACEHOLDER"

# ===== LLM CLIENTS =====
class LLMRouter:
    def __init__(self):
        # Groq clients (round-robin)
        self.groq_clients = []
        for key in GROQ_API_KEYS:
            try:
                self.groq_clients.append(Groq(api_key=key))
            except Exception as e:
                print(f"Failed to initialize Groq client: {e}")
        
        self.groq_index = 0
        self.groq_lock = Lock()
        
        # Aristotle client (using Groq with deterministic settings)
        try:
            self.aristotle_client = Groq(api_key=ARISTOTLE_API_KEY)
            self.aristotle_available = True
        except Exception as e:
            print(f"Failed to initialize Aristotle client: {e}")
            self.aristotle_available = False
        
        # Onboard LLM (simulated fallback)
        self.onboard_available = True
    
    def get_groq_client(self):
        """Get next Groq client with round-robin"""
        with self.groq_lock:
            if not self.groq_clients:
                return None
            client = self.groq_clients[self.groq_index]
            self.groq_index = (self.groq_index + 1) % len(self.groq_clients)
            return client
    
    def call_groq(self, messages, temperature=0.7):
        """Call Groq API"""
        client = self.get_groq_client()
        if not client:
            raise Exception("No Groq clients available")
        
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=temperature,
            max_tokens=1024
        )
        return response.choices[0].message.content
    
    def call_aristotle(self, messages):
        """Call Aristotle API (deterministic)"""
        if not self.aristotle_available:
            raise Exception("Aristotle client not available")
        
        response = self.aristotle_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.1,  # Deterministic
            max_tokens=1024
        )
        return response.choices[0].message.content
    
    def call_onboard(self, messages):
        """Call onboard LLM (fallback)"""
        # Simulated response for now
        return "Onboard LLM response (fallback mode)"

# Initialize LLM router
llm_router = LLMRouter()

# ===== MURPHY SYSTEM STATE =====
system_state = {
    'initialized': False,
    'system_id': None,
    'states': {},
    'agents': {},
    'gates': {},
    'components': {}
}

# ===== DEMO DATA =====
def create_demo_agents():
    agents = [
        {"id": "agent-1", "name": "Sales Agent", "type": "Sales", "domain": "Business", "status": "idle", "progress": 0, "confidence": 0.0},
        {"id": "agent-2", "name": "Engineering Agent", "type": "Engineering", "domain": "Engineering", "status": "idle", "progress": 0, "confidence": 0.0},
        {"id": "agent-3", "name": "Financial Agent", "type": "Financial", "domain": "Financial", "status": "idle", "progress": 0, "confidence": 0.0},
        {"id": "agent-4", "name": "Legal Agent", "type": "Legal", "domain": "Legal", "status": "idle", "progress": 0, "confidence": 0.0},
        {"id": "agent-5", "name": "Operations Agent", "type": "Operations", "domain": "Operations", "status": "idle", "progress": 0, "confidence": 0.0}
    ]
    for agent in agents:
        system_state['agents'][agent['id']] = agent
    return agents

def create_demo_gates():
    gates = [
        {"id": "gate-1", "name": "Quality Gate", "type": "quality", "status": "active", "threshold": 0.8},
        {"id": "gate-2", "name": "Compliance Gate", "type": "compliance", "status": "active", "threshold": 0.9}
    ]
    for gate in gates:
        system_state['gates'][gate['id']] = gate
    return gates

def create_demo_components():
    components = [
        {"id": "comp-1", "name": "LLM Router", "type": "component", "status": "active"},
        {"id": "comp-2", "name": "State Manager", "type": "component", "status": "active"},
        {"id": "comp-3", "name": "Gate Builder", "type": "component", "status": "active"}
    ]
    for comp in components:
        system_state['components'][comp['id']] = comp
    return components

def create_state(state_type, label, parent_id=None, state_id=None):
    if state_id is None:
        state_id = f"state-{uuid.uuid4().hex[:8]}"
    
    state = {
        "id": state_id,
        "label": label,
        "type": state_type,
        "description": f"Generated state for {label}",
        "confidence": 0.95,
        "parent_id": parent_id,
        "children": [],
        "metadata": {},
        "timestamp": datetime.now().isoformat()
    }
    
    system_state['states'][state_id] = state
    
    # Add to parent's children list
    if parent_id and parent_id in system_state['states']:
        system_state['states'][parent_id]['children'].append(state_id)
    
    return state

# ===== API ROUTES =====

@app.route('/')
def index():
    """Serve the frontend HTML"""
    try:
        return send_file('murphy_complete_v2.html')
    except Exception as e:
        return f"Error loading frontend: {e}", 500

@app.route('/index.html')
def index_html():
    """Serve index.html for backwards compatibility"""
    try:
        return send_file('index.html')
    except Exception as e:
        return f"Error loading frontend: {e}", 500

@app.route('/command_enhancements.js')
def serve_command_enhancements():
    """Serve command enhancements JavaScript"""
    try:
        return send_file('command_enhancements.js', mimetype='application/javascript')
    except Exception as e:
        return f"Error loading command_enhancements.js: {e}", 500

@app.route('/terminal_enhancements_integration.js')
def serve_terminal_enhancements():
    """Serve terminal enhancements integration JavaScript"""
    try:
        return send_file('terminal_enhancements_integration.js', mimetype='application/javascript')
    except Exception as e:
        return f"Error loading terminal_enhancements_integration.js: {e}", 500

@app.route('/api/status')
def get_status():
    """Get system status"""
    return jsonify({
        "status": "running",
        "initialized": system_state['initialized'],
        "llms": {
            "groq": {
                "clients": len(llm_router.groq_clients),
                "current_index": llm_router.groq_index,
                "status": "active"
            },
            "aristotle": {
                "endpoint": "Aristotle API",
                "status": "active" if llm_router.aristotle_available else "unavailable"
            },
            "onboard": {
                "status": "available" if llm_router.onboard_available else "unavailable"
            }
        },
        "metrics": {
            "agents": len(system_state['agents']),
            "states_generated": len(system_state['states']),
            "artifacts_created": 0,
            "gates_active": len([g for g in system_state['gates'].values() if g['status'] == 'active']),
            "swarms_running": 0
        }
    })

@app.route('/api/initialize', methods=['POST'])
def initialize_system():
    """Initialize Murphy System"""
    system_state['initialized'] = True
    system_state['system_id'] = f"system-{uuid.uuid4().hex[:8]}"
    
    # Create demo data
    agents = create_demo_agents()
    gates = create_demo_gates()
    components = create_demo_components()
    
    # Create root state
    root_state = create_state("document", "Root System State")
    
    # Broadcast via WebSocket
    socketio.emit('system_initialized', {
        'system_id': system_state['system_id'],
        'agents': agents,
        'gates': gates,
        'components': components
    })
    
    return jsonify({
        "message": "System initialized successfully",
        "system_id": system_state['system_id'],
        "initial_state_id": root_state['id'],
        "states": len(system_state['states']),
        "agents": len(agents),
        "components": len(components),
        "gates": len(gates)
    })

@app.route('/api/states')
def get_states():
    """Get all states"""
    return jsonify({
        "states": list(system_state['states'].values())
    })

@app.route('/api/states/<state_id>')
def get_state(state_id):
    """Get specific state"""
    state = system_state['states'].get(state_id)
    if not state:
        return jsonify({"error": "State not found"}), 404
    return jsonify(state)

@app.route('/api/states/<state_id>/evolve', methods=['POST'])
def evolve_state(state_id):
    """Evolve a state into child states"""
    parent_state = system_state['states'].get(state_id)
    if not parent_state:
        return jsonify({"error": "Parent state not found"}), 404
    
    # Create child states
    children = []
    for i in range(3):
        child_state = create_state(
            "document",
            f"Child State {i+1}",
            parent_id=state_id
        )
        children.append(child_state)
    
    # Broadcast via WebSocket
    socketio.emit('state_evolved', {
        'parent_id': state_id,
        'children': children
    })
    
    return jsonify({
        "parent_id": state_id,
        "children": children
    })

@app.route('/api/states/<state_id>/regenerate', methods=['POST'])
def regenerate_state(state_id):
    """Regenerate a state"""
    state = system_state['states'].get(state_id)
    if not state:
        return jsonify({"error": "State not found"}), 404
    
    # Update state with new confidence
    state['confidence'] = min(1.0, state['confidence'] + 0.05)
    state['timestamp'] = datetime.now().isoformat()
    
    socketio.emit('state_regenerated', state)
    
    return jsonify(state)

@app.route('/api/states/<state_id>/rollback', methods=['POST'])
def rollback_state(state_id):
    """Rollback a state to its parent"""
    state = system_state['states'].get(state_id)
    if not state:
        return jsonify({"error": "State not found"}), 404
    
    if not state['parent_id']:
        return jsonify({"error": "Cannot rollback root state"}), 400
    
    parent = system_state['states'].get(state['parent_id'])
    if not parent:
        return jsonify({"error": "Parent state not found"}), 404
    
    socketio.emit('state_rolledback', {
        'state_id': state_id,
        'parent_id': state['parent_id']
    })
    
    return jsonify({
        "rolled_back_from": state_id,
        "rolled_back_to": state['parent_id']
    })

@app.route('/api/agents')
def get_agents():
    """Get all agents"""
    return jsonify({
        "agents": list(system_state['agents'].values())
    })

@app.route('/api/gates')
def get_gates():
    """Get all gates"""
    return jsonify({
        "gates": list(system_state['gates'].values())
    })

# ===== LIBRARIAN SYSTEM =====
# Initialize Librarian with real LLM clients
class SimpleLLMClient:
    """Simple wrapper for Groq client to work with Librarian"""
    def __init__(self, groq_clients):
        self.groq_clients = groq_clients
        self.current_index = 0
    
    async def generate(self, prompt, temperature=0.7):
        """Generate response using Groq"""
        try:
            client = self.groq_clients[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.groq_clients)
            
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=1000
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"LLM generation error: {e}")
            return None

llm_client = SimpleLLMClient(llm_router.groq_clients)
librarian = LibrarianSystem(llm_client=llm_client, groq_client=llm_client, aristotle_client=None)

# ===== PLAN REVIEW SYSTEM =====
from plan_review_system import PlanReviewer
plan_reviewer = PlanReviewer(llm_client=llm_client)

# ===== LIVING DOCUMENT SYSTEM =====
from living_document_system import LivingDocumentSystem
document_system = LivingDocumentSystem(llm_client=llm_client)

@app.route('/api/librarian/ask', methods=['POST'])
def librarian_ask():
    """Ask the Librarian a question"""
    data = request.json
    user_input = data.get('query', '')
    context = data.get('context', {})
    
    if not user_input:
        return jsonify({'error': 'Query is required'}), 400
    
    # Run async function in sync context
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    response = loop.run_until_complete(librarian.ask(user_input, context))
    loop.close()
    
    return jsonify({
        'intent': {
            'category': response.intent.category.value,
            'confidence': response.intent.confidence,
            'keywords': response.intent.keywords,
            'entities': response.intent.entities,
        },
        'message': response.message,
        'commands': response.commands,
        'workflow': response.workflow,
        'follow_up_questions': response.follow_up_questions,
        'confidence_level': response.confidence_level.value,
    })

@app.route('/api/librarian/search', methods=['POST'])
def librarian_search():
    """Search Librarian knowledge base"""
    data = request.json
    query = data.get('query', '')
    
    if not query:
        return jsonify({'error': 'Query is required'}), 400
    
    results = librarian.search_knowledge(query)
    
    return jsonify({
        'query': query,
        'results': results,
        'count': len(results)
    })

@app.route('/api/librarian/transcripts')
def librarian_transcripts():
    """Get conversation transcripts"""
    limit = request.args.get('limit', 10, type=int)
    transcripts = librarian.get_transcripts(limit)
    
    # Convert to serializable format
    serialized = []
    for entry in transcripts:
        serialized.append({
            'user_input': entry['user_input'],
            'intent_category': entry['response'].intent.category.value,
            'confidence': entry['response'].intent.confidence,
            'message': entry['response'].message,
            'commands': entry['response'].commands,
            'timestamp': entry['timestamp'].isoformat()
        })
    
    return jsonify({
        'transcripts': serialized,
        'count': len(serialized)
    })

@app.route('/api/librarian/overview')
def librarian_overview():
    """Get Librarian system overview"""
    overview = librarian.get_overview()
    return jsonify(overview)

# ===== PLAN REVIEW SYSTEM =====

@app.route('/api/plans', methods=['POST'])
def create_plan():
    """Create a new plan"""
    data = request.json
    try:
        plan = plan_reviewer.create_plan(
            name=data.get('name'),
            plan_type=data.get('plan_type', 'custom'),
            description=data.get('description'),
            initial_content=data.get('content'),
            initial_steps=data.get('steps', []),
            domains=data.get('domains', []),
            constraints=data.get('constraints', [])
        )
        return jsonify({
            'success': True,
            'plan': plan.to_dict()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/plans')
def list_plans():
    """List all plans"""
    filters = {}
    if request.args.get('state'):
        filters['state'] = request.args.get('state')
    if request.args.get('plan_type'):
        filters['plan_type'] = request.args.get('plan_type')
    if request.args.get('domain'):
        filters['domain'] = request.args.get('domain')
    
    plans = plan_reviewer.list_plans(filters)
    return jsonify({
        'plans': [p.to_dict() for p in plans],
        'count': len(plans)
    })

@app.route('/api/plans/<plan_id>')
def get_plan(plan_id):
    """Get a specific plan"""
    plan = plan_reviewer.get_plan(plan_id)
    if not plan:
        return jsonify({'error': 'Plan not found'}), 404
    return jsonify({'plan': plan.to_dict()})

@app.route('/api/plans/<plan_id>/magnify', methods=['POST'])
def magnify_plan(plan_id):
    """Magnify a plan with domain expertise"""
    data = request.json
    domain = data.get('domain')
    
    if not domain:
        return jsonify({'error': 'Domain is required'}), 400
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(plan_reviewer.magnify(plan_id, domain))
        loop.close()
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/plans/<plan_id>/simplify', methods=['POST'])
def simplify_plan(plan_id):
    """Simplify a plan to essentials"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(plan_reviewer.simplify(plan_id))
        loop.close()
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/plans/<plan_id>/edit', methods=['POST'])
def edit_plan(plan_id):
    """Edit a plan"""
    data = request.json
    try:
        result = plan_reviewer.edit(plan_id, data)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/plans/<plan_id>/solidify', methods=['POST'])
def solidify_plan(plan_id):
    """Solidify a plan for execution"""
    try:
        result = plan_reviewer.solidify(plan_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/plans/<plan_id>/approve', methods=['POST'])
def approve_plan(plan_id):
    """Approve a plan"""
    data = request.json
    user_id = data.get('user_id', 'user')
    try:
        result = plan_reviewer.approve(plan_id, user_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/plans/<plan_id>/reject', methods=['POST'])
def reject_plan(plan_id):
    """Reject a plan"""
    data = request.json
    reason = data.get('reason', 'No reason provided')
    user_id = data.get('user_id', 'user')
    try:
        result = plan_reviewer.reject(plan_id, reason, user_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/plans/<plan_id>/diff')
def get_plan_diff(plan_id):
    """Get diff between two versions"""
    version1 = request.args.get('version1', type=int)
    version2 = request.args.get('version2', type=int)
    
    if not version1 or not version2:
        return jsonify({'error': 'Both version1 and version2 are required'}), 400
    
    try:
        diff = plan_reviewer.get_diff(plan_id, version1, version2)
        return jsonify(diff)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# ===== LIVING DOCUMENT SYSTEM =====

@app.route('/api/documents', methods=['POST'])
def create_document():
    """Create a new living document"""
    data = request.json
    try:
        document = document_system.create_document(
            name=data.get('name'),
            doc_type=data.get('doc_type', 'custom'),
            description=data.get('description'),
            initial_content=data.get('content'),
            domains=data.get('domains', []),
            constraints=data.get('constraints', []),
            tags=data.get('tags', [])
        )
        return jsonify({
            'success': True,
            'document': document.to_dict()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/documents')
def list_documents():
    """List all documents"""
    filters = {}
    if request.args.get('state'):
        filters['state'] = request.args.get('state')
    if request.args.get('doc_type'):
        filters['doc_type'] = request.args.get('doc_type')
    if request.args.get('domain'):
        filters['domain'] = request.args.get('domain')
    if request.args.get('tag'):
        filters['tag'] = request.args.get('tag')
    
    documents = document_system.list_documents(filters)
    return jsonify({
        'documents': [d.to_dict() for d in documents],
        'count': len(documents)
    })

@app.route('/api/documents/<doc_id>')
def get_document(doc_id):
    """Get a specific document"""
    document = document_system.get_document(doc_id)
    if not document:
        return jsonify({'error': 'Document not found'}), 404
    return jsonify({'document': document.to_dict()})

@app.route('/api/documents/<doc_id>/magnify', methods=['POST'])
def magnify_document(doc_id):
    """Magnify a document with domain expertise"""
    data = request.json
    domain = data.get('domain')
    
    if not domain:
        return jsonify({'error': 'Domain is required'}), 400
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(document_system.magnify(doc_id, domain))
        loop.close()
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/documents/<doc_id>/simplify', methods=['POST'])
def simplify_document(doc_id):
    """Simplify a document to essentials"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(document_system.simplify(doc_id))
        loop.close()
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/documents/<doc_id>/edit', methods=['POST'])
def edit_document(doc_id):
    """Edit a document"""
    data = request.json
    new_content = data.get('content')
    summary = data.get('summary')
    
    if not new_content:
        return jsonify({'error': 'Content is required'}), 400
    
    try:
        result = document_system.edit(doc_id, new_content, summary)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/documents/<doc_id>/solidify', methods=['POST'])
def solidify_document(doc_id):
    """Solidify a document into generative prompts"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(document_system.solidify(doc_id))
        loop.close()
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/documents/<doc_id>/template', methods=['POST'])
def save_document_as_template(doc_id):
    """Save document as template"""
    data = request.json
    template_name = data.get('name')
    
    if not template_name:
        return jsonify({'error': 'Template name is required'}), 400
    
    try:
        result = document_system.save_as_template(doc_id, template_name)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/templates')
def list_templates():
    """List all templates"""
    templates = document_system.list_templates()
    return jsonify({
        'templates': [t.to_dict() for t in templates],
        'count': len(templates)
    })

@app.route('/api/templates/<template_id>/create', methods=['POST'])
def create_from_template(template_id):
    """Create document from template"""
    data = request.json
    name = data.get('name')
    
    if not name:
        return jsonify({'error': 'Document name is required'}), 400
    
    try:
        result = document_system.create_from_template(template_id, name)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

# ===== WEBSOCKET EVENTS =====

@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")
    emit('connected', {'message': 'Connected to Murphy System'})

@socketio.on('disconnect')
def handle_disconnect():
    print(f"Client disconnected: {request.sid}")

# ===== MAIN =====
if __name__ == '__main__':
    print("=" * 60)
    print("MURPHY SYSTEM UNIFIED SERVER")
    print("=" * 60)
    print(f"Starting server on port 3000...")
    print(f"Frontend: http://localhost:3000/")
    print(f"API: http://localhost:3000/api/")
    print(f"Groq Clients: {len(llm_router.groq_clients)}")
    print(f"Aristotle: {'Active' if llm_router.aristotle_available else 'Unavailable'}")
    print(f"Onboard LLM: {'Available' if llm_router.onboard_available else 'Unavailable'}")
    print("=" * 60)
    
    # Kill existing processes on port 3000
    os.system("fuser -k 3000/tcp 2>/dev/null")
    time.sleep(1)
    
    # Start unified server
    socketio.run(app, host='0.0.0.0', port=3000, debug=False, allow_unsafe_werkzeug=True)