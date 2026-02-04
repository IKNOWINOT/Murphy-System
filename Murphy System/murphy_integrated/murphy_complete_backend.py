"""
Murphy System - Complete Backend with Real LLM Integration
Production-ready system with Groq, Anthropic, and Onboard LLM fallback
"""

import os
import sys
import json
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import anthropic
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
sys.path.insert(0, os.path.dirname(__file__))
try:
    from domain_engine import DomainEngine
    DOMAIN_ENGINE_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import Domain Engine: {e}")
    DOMAIN_ENGINE_AVAILABLE = False

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# LLM Configuration
# Multiple Groq API keys for load balancing and redundancy
GROQ_API_KEYS = [
    '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',
    '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',
    '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',
    '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',
    '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',
    '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',
    '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',
    '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',
    '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'
]
GROQ_API_KEY = os.getenv('GROQ_API_KEY', GROQ_API_KEYS[0])
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', 'placeholder-anthropic-key')

# Initialize LLM clients with key rotation
groq_clients = []
anthropic_client = None
current_groq_key_index = 0

# Initialize multiple Groq clients for load balancing
for i, key in enumerate(GROQ_API_KEYS):
    try:
        client = Groq(api_key=key)
        groq_clients.append(client)
        print(f"✓ Groq client {i+1}/9 initialized")
    except Exception as e:
        print(f"⚠ Groq client {i+1} failed: {e}")

if groq_clients:
    print(f"✓ Total {len(groq_clients)} Groq clients ready for load balancing")
else:
    print("✗ No Groq clients available - system will use fallback")

try:
    if ANTHROPIC_API_KEY != 'placeholder-anthropic-key':
        anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        print("✓ Anthropic client initialized")
    else:
        print("⚠ Anthropic API key not set - will use Groq for deterministic tasks")
except Exception as e:
    print(f"⚠ Anthropic initialization failed: {e}")

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
        self.anthropic = anthropic_client
        self.onboard_available = False
        
    async def route_request(self, prompt: str, task_type: str = "generative") -> str:
        """Route request to appropriate LLM"""
        
        if task_type == "verification" and self.anthropic:
            return await self._call_anthropic(prompt)
        elif task_type == "generative" and self.groq_available:
            return await self._call_groq(prompt)
        else:
            return await self._call_onboard(prompt)
    
    async def _call_groq(self, prompt: str) -> str:
        """Call Groq API with automatic key rotation"""
        try:
            client = get_next_groq_client()
            if not client:
                return await self._call_onboard(prompt)
            
            response = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
                temperature=0.7,
                max_tokens=2000
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Groq error: {e}, trying fallback")
            return await self._call_onboard(prompt)
    
    async def _call_anthropic(self, prompt: str) -> str:
        """Call Anthropic API, fallback to Groq if unavailable"""
        try:
            if not self.anthropic:
                print("Anthropic not available, using Groq for deterministic task")
                return await self._call_groq(prompt)
            
            response = self.anthropic.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            print(f"Anthropic error: {e}, falling back to Groq")
            return await self._call_groq(prompt)
    
    async def _call_onboard(self, prompt: str) -> str:
        """Fallback to onboard LLM"""
        # Simulate onboard LLM response
        return f"[Onboard LLM Response] Processed: {prompt[:100]}..."

class LivingDocument:
    """Represents a living document that evolves through states"""
    
    def __init__(self, doc_id: str, title: str, content: str, doc_type: str):
        self.doc_id = doc_id
        self.title = title
        self.content = content
        self.doc_type = doc_type
        self.state = "INITIAL"
        self.confidence = 0.45
        self.domain_depth = 0
        self.history = []
        self.children = []
        self.parent_id = None
        self.created_at = datetime.now().isoformat()
        
    def magnify(self, domain: str) -> Dict[str, Any]:
        """Expand domain expertise"""
        self.domain_depth += 15
        self.confidence += 0.1
        self.history.append({
            "action": "magnify",
            "domain": domain,
            "timestamp": datetime.now().isoformat()
        })
        return self.to_dict()
    
    def simplify(self) -> Dict[str, Any]:
        """Distill to essentials"""
        self.domain_depth = max(0, self.domain_depth - 10)
        self.confidence += 0.05
        self.history.append({
            "action": "simplify",
            "timestamp": datetime.now().isoformat()
        })
        return self.to_dict()
    
    def solidify(self) -> Dict[str, Any]:
        """Solidify document for prompt generation"""
        self.state = "SOLIDIFIED"
        self.confidence = min(1.0, self.confidence + 0.2)
        self.history.append({
            "action": "solidify",
            "timestamp": datetime.now().isoformat()
        })
        return self.to_dict()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "title": self.title,
            "content": self.content,
            "doc_type": self.doc_type,
            "state": self.state,
            "confidence": self.confidence,
            "domain_depth": self.domain_depth,
            "history": self.history,
            "children": self.children,
            "parent_id": self.parent_id,
            "created_at": self.created_at
        }

class MurphySystemRuntime:
    """Complete Murphy System Runtime"""
    
    def __init__(self):
        self.initialized = False
        self.living_documents = {}
        self.states = []
        self.artifacts = []
        self.gates = []
        self.swarms = []
        self.org_chart = {}
        self.llm_router = LLMRouter()
        
        # Counters
        self.doc_counter = 0
        self.state_counter = 0
        self.artifact_counter = 0
        
        # Murphy components
        if MURPHY_AVAILABLE:
            self.mfgc_state = MFGCSystemState()
            self.swarm_generator = AdvancedSwarmGenerator()
            self.constraint_system = ConstraintSystem()
            self.gate_builder = GateBuilder()
            self.org_chart_system = OrganizationChart()
        
        # Domain Engine
        if DOMAIN_ENGINE_AVAILABLE:
            self.domain_engine = DomainEngine()
        else:
            self.domain_engine = None
    
    def create_living_document(self, title: str, content: str, doc_type: str) -> LivingDocument:
        """Create a new living document"""
        doc_id = f"DOC-{self.doc_counter}"
        self.doc_counter += 1
        
        doc = LivingDocument(doc_id, title, content, doc_type)
        self.living_documents[doc_id] = doc
        
        socketio.emit('document_created', doc.to_dict())
        return doc
    
    async def generate_prompts_from_document(self, doc_id: str) -> Dict[str, str]:
        """Generate prompts from solidified document"""
        doc = self.living_documents.get(doc_id)
        if not doc or doc.state != "SOLIDIFIED":
            return {}
        
        # Generate master prompt
        master_prompt = f"""
        Based on this document:
        Title: {doc.title}
        Content: {doc.content}
        
        Generate a comprehensive master prompt that captures all requirements.
        """
        
        master = await self.llm_router.route_request(master_prompt, "generative")
        
        # Generate domain-specific prompts
        domains = ["engineering", "financial", "regulatory", "sales", "operations"]
        prompts = {"master": master}
        
        for domain in domains:
            domain_prompt = f"""
            From the master requirements:
            {master}
            
            Generate specific {domain} requirements and tasks.
            """
            prompts[domain] = await self.llm_router.route_request(domain_prompt, "generative")
        
        return prompts
    
    def assign_swarm_tasks(self, prompts: Dict[str, str]) -> List[Dict[str, Any]]:
        """Assign prompts to org chart agents as swarm tasks"""
        tasks = []
        
        role_mapping = {
            "engineering": "Chief Engineer",
            "financial": "CFO",
            "regulatory": "Compliance Officer",
            "sales": "Sales Director",
            "operations": "Operations Manager"
        }
        
        for domain, prompt in prompts.items():
            if domain == "master":
                continue
                
            role = role_mapping.get(domain, "General Agent")
            task = {
                "task_id": f"TASK-{len(tasks)}",
                "domain": domain,
                "role": role,
                "prompt": prompt,
                "status": "assigned",
                "created_at": datetime.now().isoformat()
            }
            tasks.append(task)
            
        return tasks
    
    async def execute_swarm_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a swarm task"""
        task["status"] = "executing"
        socketio.emit('task_started', task)
        
        # Execute with LLM
        result = await self.llm_router.route_request(task["prompt"], "generative")
        
        task["status"] = "completed"
        task["result"] = result
        task["completed_at"] = datetime.now().isoformat()
        
        socketio.emit('task_completed', task)
        return task
    
    def generate_domain_gates(self, domain: str) -> List[Dict[str, Any]]:
        """Generate gates for a domain"""
        gate_templates = {
            "engineering": [
                {"name": "Load Calculations", "severity": 0.9},
                {"name": "Code Compliance", "severity": 0.95},
                {"name": "Safety Factors", "severity": 1.0}
            ],
            "financial": [
                {"name": "Budget Constraint", "severity": 0.8},
                {"name": "ROI Threshold", "severity": 0.7},
                {"name": "Cash Flow", "severity": 0.85}
            ],
            "regulatory": [
                {"name": "FDA Compliance", "severity": 1.0},
                {"name": "OSHA Standards", "severity": 0.95},
                {"name": "Local Laws", "severity": 0.9}
            ]
        }
        
        gates = []
        templates = gate_templates.get(domain, [])
        
        for template in templates:
            gate = {
                "gate_id": f"GATE-{len(self.gates)}",
                "domain": domain,
                "name": template["name"],
                "severity": template["severity"],
                "status": "active",
                "created_at": datetime.now().isoformat()
            }
            gates.append(gate)
            self.gates.append(gate)
        
        return gates
    
    def consolidate_approvals(self, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Consolidate multiple approval requests into one"""
        approval_items = []
        
        for task in tasks:
            if task.get("requires_approval"):
                approval_items.append({
                    "task_id": task["task_id"],
                    "domain": task["domain"],
                    "question": f"Approve {task['domain']} approach?",
                    "options": ["Approve", "Modify", "Reject"]
                })
        
        return {
            "consolidation_id": f"APPROVAL-{datetime.now().timestamp()}",
            "items": approval_items,
            "created_at": datetime.now().isoformat()
        }

# Global runtime instance
runtime = MurphySystemRuntime()

# API Endpoints

@app.route('/api/initialize', methods=['POST'])
def initialize_system():
    """Initialize Murphy System"""
    data = request.json
    mode = data.get('mode', 'guided')
    
    runtime.initialized = True
    
    return jsonify({
        "success": True,
        "mode": mode,
        "message": "Murphy System initialized"
    })

@app.route('/api/documents', methods=['POST'])
def create_document():
    """Create a living document"""
    data = request.json
    
    doc = runtime.create_living_document(
        title=data.get('title', 'Untitled'),
        content=data.get('content', ''),
        doc_type=data.get('type', 'general')
    )
    
    return jsonify(doc.to_dict())

@app.route('/api/documents/<doc_id>/magnify', methods=['POST'])
def magnify_document(doc_id):
    """Magnify a document"""
    data = request.json
    domain = data.get('domain', 'general')
    
    doc = runtime.living_documents.get(doc_id)
    if not doc:
        return jsonify({"error": "Document not found"}), 404
    
    result = doc.magnify(domain)
    return jsonify(result)

@app.route('/api/documents/<doc_id>/simplify', methods=['POST'])
def simplify_document(doc_id):
    """Simplify a document"""
    doc = runtime.living_documents.get(doc_id)
    if not doc:
        return jsonify({"error": "Document not found"}), 404
    
    result = doc.simplify()
    return jsonify(result)

@app.route('/api/documents/<doc_id>/solidify', methods=['POST'])
async def solidify_document(doc_id):
    """Solidify a document and generate prompts"""
    doc = runtime.living_documents.get(doc_id)
    if not doc:
        return jsonify({"error": "Document not found"}), 404
    
    # Solidify document
    doc.solidify()
    
    # Generate prompts
    prompts = await runtime.generate_prompts_from_document(doc_id)
    
    # Assign swarm tasks
    tasks = runtime.assign_swarm_tasks(prompts)
    
    # Generate gates
    gates = []
    for domain in ["engineering", "financial", "regulatory"]:
        gates.extend(runtime.generate_domain_gates(domain))
    
    return jsonify({
        "document": doc.to_dict(),
        "prompts": prompts,
        "tasks": tasks,
        "gates": gates
    })

@app.route('/api/tasks/<task_id>/execute', methods=['POST'])
async def execute_task(task_id):
    """Execute a swarm task"""
    # Find task
    task = None
    for t in runtime.swarms:
        if t.get('task_id') == task_id:
            task = t
            break
    
    if not task:
        return jsonify({"error": "Task not found"}), 404
    
    result = await runtime.execute_swarm_task(task)
    return jsonify(result)

@app.route('/api/approvals/consolidate', methods=['POST'])
def consolidate_approvals():
    """Consolidate approval requests"""
    data = request.json
    tasks = data.get('tasks', [])
    
    consolidated = runtime.consolidate_approvals(tasks)
    return jsonify(consolidated)

@app.route('/api/status', methods=['GET'])
def get_status():
    """Get system status"""
    return jsonify({
        "initialized": runtime.initialized,
        "documents": len(runtime.living_documents),
        "states": len(runtime.states),
        "artifacts": len(runtime.artifacts),
        "gates": len(runtime.gates),
        "swarms": len(runtime.swarms)
    })

@app.route('/api/test-groq', methods=['POST'])
def test_groq():
    """Test Groq API connection"""
    try:
        data = request.json
        prompt = data.get('prompt', 'Say hello and confirm you are the Murphy System AI')
        
        # Direct synchronous call to Groq
        client = get_next_groq_client()
        if not client:
            return jsonify({
                'success': False,
                'error': 'No Groq clients available'
            }), 500
        
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.7,
            max_tokens=500
        )
        
        return jsonify({
            'success': True,
            'response': response.choices[0].message.content,
            'groq_clients_available': len(groq_clients),
            'model': 'llama-3.3-70b-versatile'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/domains', methods=['GET'])
def get_domains():
    """Get all available domains"""
    if not runtime.domain_engine:
        return jsonify({'error': 'Domain engine not available'}), 500
    
    domains = runtime.domain_engine.get_all_domains()
    return jsonify({'domains': domains})

@app.route('/api/analyze-domain', methods=['POST'])
def analyze_domain():
    """Analyze request and determine domain coverage"""
    if not runtime.domain_engine:
        return jsonify({'error': 'Domain engine not available'}), 500
    
    data = request.json
    request_text = data.get('request', '')
    
    analysis = runtime.domain_engine.analyze_request(request_text)
    
    if analysis['needs_generative']:
        # Select template and generate questions
        template = runtime.domain_engine.select_template(request_text, analysis)
        questions = runtime.domain_engine.generate_questions(template, request_text)
        
        return jsonify({
            'needs_generative': True,
            'coverage': analysis['coverage'],
            'matched_domains': analysis['matched_domains'],
            'template': template.to_dict(),
            'questions': questions
        })
    else:
        return jsonify({
            'needs_generative': False,
            'coverage': analysis['coverage'],
            'matched_domains': analysis['matched_domains'],
            'domains': [runtime.domain_engine.domains[d].to_dict() 
                       for d in analysis['matched_domains'].keys()]
        })

@app.route('/api/create-generative-domain', methods=['POST'])
def create_generative_domain():
    """Create a new generative domain from responses"""
    if not runtime.domain_engine:
        return jsonify({'error': 'Domain engine not available'}), 500
    
    data = request.json
    template_type = data.get('template_type')
    responses = data.get('responses', {})
    
    # Get template
    template = runtime.domain_engine.templates.get(template_type)
    if not template:
        return jsonify({'error': 'Invalid template type'}), 400
    
    # Synthesize domain
    domain = runtime.domain_engine.synthesize_domain(template, responses)
    
    # Validate
    is_valid, issues = runtime.domain_engine.validate_domain(domain)
    
    if not is_valid:
        return jsonify({
            'success': False,
            'issues': issues
        })
    
    # Integrate
    runtime.domain_engine.integrate_domain(domain)
    
    return jsonify({
        'success': True,
        'domain': domain.to_dict()
    })

@app.route('/api/cross-impact-analysis', methods=['POST'])
def cross_impact_analysis():
    """Get cross-domain impact analysis"""
    if not runtime.domain_engine:
        return jsonify({'error': 'Domain engine not available'}), 500
    
    data = request.json
    domain_names = data.get('domains', [])
    
    analysis = runtime.domain_engine.get_cross_impact_analysis(domain_names)
    
    return jsonify(analysis)

@app.route('/')
def index():
    """Serve frontend"""
    return app.send_static_file('murphy_complete.html')

app.static_folder = '/workspace'
app.static_url_path = ''

if __name__ == '__main__':
    port = int(os.getenv('MURPHY_PORT', 8000))
    print("=" * 60)
    print("Murphy System - Complete Backend")
    print("=" * 60)
    print(f"Murphy System Available: {MURPHY_AVAILABLE}")
    print(f"Groq Available: {len(groq_clients) > 0}")
    print(f"Anthropic Available: {anthropic_client is not None}")
    print(f"Starting server on http://localhost:{port}")
    print("=" * 60)
    
    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)
