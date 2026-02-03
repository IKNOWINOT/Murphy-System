# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Murphy System - Complete Integration
All systems working together as an automation operating system
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import logging
import subprocess
import os
import uuid
from datetime import datetime

# Knowledge Pipeline System
from generative_gate_system import (
    GenerativeGateSystem, get_generative_gate_system,
    SensorAgent, QualitySensorAgent, CostSensorAgent, ComplianceSensorAgent,
    GateTypeEnum, ConfidenceLevelEnum, GateSpecModel, RuleModel, ObservationModel
)

from agent_communication_system import (
    AgentCommunicationHub, get_communication_hub,
    MessageType, ConfidenceLevel, AgentMessage, AgentTaskReview
)

from swarm_knowledge_pipeline import (
    initialize_knowledge_pipeline,
    KnowledgeBucket,
    Block,
    ConfidenceLevel,
    BlockAction,
    GlobalStateManager,
    InformationSourceDecider,
    BlockVerification,
    OrgChartLibrary,
    LibrarianCommandGenerator,
    MasterScheduler
)

# Enhanced Runtime Orchestrator with Dynamic Agent Generation
# Runtime orchestrator - optional, comment out if not needed
try:
    from runtime_orchestrator_enhanced import (
        get_orchestrator,
        reset_orchestrator,
        RuntimeOrchestrator,
        DynamicAgentGenerator,
        CollectiveMind,
        ParallelExecutor,
        GeneratedAgent
    )
    RUNTIME_ORCHESTRATOR_AVAILABLE = True
except ImportError:
    RUNTIME_ORCHESTRATOR_AVAILABLE = False
    print("⚠ runtime_orchestrator_enhanced not available - some features disabled")

# Multi-Agent Book Generation System
from multi_agent_book_generator import (
    generate_book_multi_agent,
    WritingStyle,
    MultiAgentBookGenerator
)
import json
from dataclasses import asdict
import sys

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'murphy-complete-integrated'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# ============================================================================
# SYSTEM INITIALIZATION - Load ALL modules
# ============================================================================

# Track what's available
SYSTEMS_AVAILABLE = {
    'llm': False,
    'librarian': False,
    'monitoring': False,
    'artifacts': False,
    'shadow_agents': False,
    'swarm': False,
    'commands': False,
    'learning': False,
    'workflow': False,
    'database': False
}

# Global variables
_communication_hub_instance = None

def get_comm_hub():
    """Get the communication hub instance"""
    return _communication_hub_instance

# LLM Manager
try:
    from llm_providers_enhanced import EnhancedLLMManager
    # EnhancedLLMManager expects file paths
    llm_manager = EnhancedLLMManager(
        groq_keys_file='groq_keys.txt',
        aristotle_key_file='aristotle_key.txt'
    )
    SYSTEMS_AVAILABLE['llm'] = True
    logger.info(f"✓ LLM Manager initialized with key rotation")
except Exception as e:
    logger.error(f"✗ LLM Manager failed: {e}")
    llm_manager = None

# Librarian System
try:
    from librarian_system import LibrarianSystem
    librarian_system = LibrarianSystem(llm_client=llm_manager if llm_manager else None)
    SYSTEMS_AVAILABLE['librarian'] = True
    logger.info("✓ Librarian System initialized")
except Exception as e:
    logger.error(f"✗ Librarian System failed: {e}")
    librarian_system = None

# Monitoring System
try:
    from monitoring_system import MonitoringSystem
    monitoring_system = MonitoringSystem()
    SYSTEMS_AVAILABLE['monitoring'] = True
    logger.info("✓ Monitoring System initialized")
except Exception as e:
    logger.error(f"✗ Monitoring System failed: {e}")
    monitoring_system = None

# Artifact System
try:
    from artifact_generation_system import ArtifactGenerationSystem
    from artifact_manager import ArtifactManager
    artifact_generator = ArtifactGenerationSystem(llm_router=llm_manager if llm_manager else None)
    artifact_manager = ArtifactManager()
    SYSTEMS_AVAILABLE['artifacts'] = True
    logger.info("✓ Artifact Systems initialized")
except Exception as e:
    logger.error(f"✗ Artifact Systems failed: {e}")
    artifact_generator = None
    artifact_manager = None

# Shadow Agent System
try:
    from shadow_agent_system import ShadowAgentSystem
    shadow_agent_system = ShadowAgentSystem()
    SYSTEMS_AVAILABLE['shadow_agents'] = True
    logger.info("✓ Shadow Agent System initialized")
except Exception as e:
    logger.error(f"✗ Shadow Agent System failed: {e}")
    shadow_agent_system = None

# Cooperative Swarm System
try:
    from cooperative_swarm_system import CooperativeSwarmSystem
    swarm_system = CooperativeSwarmSystem()
    SYSTEMS_AVAILABLE['swarm'] = True
    logger.info("✓ Cooperative Swarm System initialized")
except Exception as e:
    logger.error(f"✗ Cooperative Swarm System failed: {e}")
    swarm_system = None

# Command System
try:
    from command_system import CommandRegistry, execute_command
    from register_all_commands import register_all_system_commands, get_command_summary
    command_registry = CommandRegistry()
    
    # Register ALL commands from ALL systems
    total_commands = register_all_system_commands(command_registry)
    
    # Get command summary
    cmd_summary = get_command_summary(command_registry)
    
    SYSTEMS_AVAILABLE['commands'] = True
    logger.info(f"✓ Command System initialized with {total_commands} commands")
    logger.info(f"  Modules: {', '.join(cmd_summary['modules'])}")
    logger.info(f"  By module: {cmd_summary['by_module']}")
except Exception as e:
    logger.error(f"✗ Command System failed: {e}")
    command_registry = None

# Learning Engine
try:
    from learning_engine import LearningEngine
    learning_engine = LearningEngine()
    SYSTEMS_AVAILABLE['learning'] = True
    logger.info("✓ Learning Engine initialized")
except Exception as e:
    logger.error(f"✗ Learning Engine failed: {e}")
    learning_engine = None

# Workflow Orchestrator (needs swarm and handoff manager)
try:
    from workflow_orchestrator import WorkflowOrchestrator
    from agent_handoff_manager import AgentHandoffManager
    
    # Only initialize if swarm is available
    if swarm_system:
        handoff_manager = AgentHandoffManager(cooperative_swarm=swarm_system)
        workflow_orchestrator = WorkflowOrchestrator(
            cooperative_swarm=swarm_system,
            handoff_manager=handoff_manager
        )
        SYSTEMS_AVAILABLE['workflow'] = True
        logger.info("✓ Workflow Orchestrator initialized")
    else:
        workflow_orchestrator = None
        logger.warning("⚠ Workflow Orchestrator skipped (swarm not available)")
except Exception as e:
    logger.error(f"✗ Workflow Orchestrator failed: {e}")
    workflow_orchestrator = None

# Database
try:
    from database_integration import get_database_manager
    db_manager = get_database_manager()
    SYSTEMS_AVAILABLE['database'] = True
    logger.info("✓ Database initialized")
except Exception as e:
    logger.error(f"✗ Database failed: {e}")
    db_manager = None

# Business Integrations
try:
    from business_integrations import get_business_automation
    business_automation = get_business_automation(llm_manager=llm_manager if llm_manager else None)
    SYSTEMS_AVAILABLE['business'] = True
    logger.info("✓ Business Automation initialized")
except Exception as e:
    logger.error(f"✗ Business Automation failed: {e}")
    business_automation = None

# Production Setup
try:
    from production_setup import get_production_readiness
    production_readiness = get_production_readiness()
    SYSTEMS_AVAILABLE['production'] = True
    logger.info("✓ Production Readiness initialized")
except Exception as e:
    logger.error(f"✗ Production Readiness failed: {e}")
    production_readiness = None

# Payment Verification System
try:
    from payment_verification_system import get_payment_verification
    payment_verification = get_payment_verification()
    SYSTEMS_AVAILABLE['payment_verification'] = True
    logger.info("✓ Payment Verification System initialized")
except Exception as e:
    logger.error(f"✗ Payment Verification System failed: {e}")
    payment_verification = None

# Artifact Download System
try:
    from artifact_download_system import get_artifact_download_system
    artifact_download = get_artifact_download_system(
        payment_verification=payment_verification if payment_verification else None,
        artifact_manager=artifact_manager if artifact_manager else None
    )
    SYSTEMS_AVAILABLE['artifact_download'] = True
    logger.info("✓ Artifact Download System initialized")
except Exception as e:
    logger.error(f"✗ Artifact Download System failed: {e}")
    artifact_download = None

# Scheduled Automation System
try:
    from scheduled_automation_system import get_automation_system
    automation_system = get_automation_system(
        command_registry=command_registry if command_registry else None,
        librarian=librarian_system if librarian_system else None
    )
    SYSTEMS_AVAILABLE['automation'] = True
    logger.info("✓ Scheduled Automation System initialized")
except Exception as e:
    logger.error(f"✗ Scheduled Automation System failed: {e}")
    automation_system = None

# Librarian Command Integration
try:
    from librarian_command_integration import get_librarian_command_integration
    librarian_integration = get_librarian_command_integration(
        librarian_system=librarian_system if librarian_system else None,
        command_registry=command_registry if command_registry else None,
        llm_manager=llm_manager if llm_manager else None
    )
    
    # Store all commands in Librarian
    if librarian_integration:
        store_result = librarian_integration.store_all_commands()
        logger.info(f"✓ Stored {store_result.get('stored_count', 0)} commands in Librarian")
    
    SYSTEMS_AVAILABLE['librarian_integration'] = True
    logger.info("✓ Librarian Command Integration initialized")
except Exception as e:
    logger.error(f"✗ Librarian Command Integration failed: {e}")
    librarian_integration = None

# Agent Communication Hub - Initialize at module level
try:
    _communication_hub_instance = get_communication_hub(librarian_system, llm_manager)
    if _communication_hub_instance:
        SYSTEMS_AVAILABLE['agent_communication'] = True
        logger.info("✓ Agent Communication Hub initialized at module level")
except Exception as e:
    logger.error(f"✗ Agent Communication Hub failed: {e}")

# Generative Decision Gate System - Initialize at module level
try:
    generative_gate_system = get_generative_gate_system()
    SYSTEMS_AVAILABLE['generative_gates'] = True
    logger.info("✓ Generative Decision Gate System initialized at module level")
except Exception as e:
    logger.error(f"✗ Generative Decision Gate System failed: {e}")
    generative_gate_system = None

# Enhanced Gate Integration - Initialize at module level
try:
    from enhanced_gate_integration import integrate_enhanced_gates
    enhanced_gate_integration = None  # Will be initialized after app creation
    SYSTEMS_AVAILABLE['enhanced_gates'] = True
    logger.info("✓ Enhanced Gate Integration module loaded")
except Exception as e:
    logger.error(f"✗ Enhanced Gate Integration failed: {e}")
    enhanced_gate_integration = None

# Dynamic Projection Gate System - Initialize at module level
try:
    from dynamic_projection_gates import integrate_dynamic_projection_gates
    dynamic_projection_gates = None  # Will be initialized after app creation
    SYSTEMS_AVAILABLE['dynamic_projection_gates'] = True
    logger.info("✓ Dynamic Projection Gate System module loaded")
except Exception as e:
    logger.error(f"✗ Dynamic Projection Gate System failed: {e}")
    dynamic_projection_gates = None

# Autonomous Business Development System - Initialize at module level
try:
    from autonomous_business_dev_implementation import AutonomousBusinessDevelopment
    autonomous_bd_system = None  # Will be initialized after app creation
    SYSTEMS_AVAILABLE['autonomous_bd'] = True
    logger.info("✓ Autonomous Business Development System module loaded")
except Exception as e:
    logger.error(f"✗ Autonomous Business Development System failed: {e}")
    autonomous_bd_system = None

# Global state
system_initialized = False
artifacts = []
tasks = []
workflows = []
products = []
customers = []

# ============================================================================
# UNIFIED API - All systems accessible through one interface
# ============================================================================

@app.route('/')
def index():
    return send_from_directory('.', 'murphy_ui_final.html')

@app.route('/api/status', methods=['GET'])
def status():
    """Get complete system status"""
    
    # Get command statistics if available
    command_stats = {}
    if command_registry:
        from register_all_commands import get_command_summary
        command_stats = get_command_summary(command_registry)
    
    return jsonify({
        'status': 'running',
        'initialized': system_initialized,
        'systems': SYSTEMS_AVAILABLE,
        'commands': command_stats,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/initialize', methods=['POST'])
def initialize():
    """Initialize all systems"""
    global system_initialized
    system_initialized = True
    
    # Initialize each available system
    results = {}
    
    if monitoring_system:
        results['monitoring'] = 'initialized'
    
    if shadow_agent_system:
        results['shadow_agents'] = 'initialized'
    
    if swarm_system:
        results['swarm'] = 'initialized'
    
    return jsonify({
        'status': 'initialized',
        'systems': results,
        'timestamp': datetime.now().isoformat()
    })

# ============================================================================
# LLM ENDPOINTS
# ============================================================================

@app.route('/api/llm/generate', methods=['POST'])
def llm_generate():
    """Generate content using LLM"""
    if not llm_manager:
        return jsonify({'error': 'LLM not available'}), 503
    
    data = request.json
    prompt = data.get('prompt', '')
    
    try:
        response = llm_manager.generate(prompt)
        return jsonify({
            'success': True,
            'response': response,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# LIBRARIAN ENDPOINTS
# ============================================================================

@app.route('/api/librarian/ask', methods=['POST'])
def librarian_ask():
    """Ask the librarian system"""
    if not librarian_system:
        return jsonify({'error': 'Librarian not available'}), 503
    
    data = request.json
    query = data.get('query', '')
    
    try:
        # Use asyncio.run to handle async properly
        import asyncio
        response = asyncio.run(librarian_system.ask(query))
        
        # Convert response to JSON-serializable format
        def make_serializable(obj):
            if hasattr(obj, 'value'):  # Handle Enums
                return obj.value
            elif hasattr(obj, '__dict__'):
                return {k: make_serializable(v) for k, v in obj.__dict__.items()}
            elif isinstance(obj, list):
                return [make_serializable(item) for item in obj]
            elif isinstance(obj, dict):
                return {k: make_serializable(v) for k, v in obj.items()}
            else:
                return obj
        
        response = make_serializable(response)
        
        return jsonify({
            'success': True,
            'response': response,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Librarian error: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# ARTIFACT ENDPOINTS
# ============================================================================

@app.route('/api/artifacts/generate', methods=['POST'])
def generate_artifact():
    """Generate artifact using AI"""
    if not artifact_generator:
        return jsonify({'error': 'Artifact generator not available'}), 503
    
    data = request.json
    artifact_type = data.get('type', 'document')
    description = data.get('description', '')
    
    try:
        artifact = artifact_generator.generate(artifact_type, description)
        artifacts.append(artifact)
        
        socketio.emit('artifact_created', artifact)
        
        return jsonify({
            'success': True,
            'artifact': artifact,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/artifacts', methods=['GET'])
def list_artifacts():
    return jsonify({'artifacts': artifacts})

# ============================================================================
# COMMAND EXECUTION ENDPOINTS
# ============================================================================

@app.route('/api/command/execute', methods=['POST'])
def execute_command_endpoint():
    """Execute terminal command"""
    data = request.json
    command = data.get('command', '')
    
    if not command:
        return jsonify({'error': 'No command provided'}), 400
    
    # Security filter
    dangerous = ['rm -rf', 'sudo ', 'mkfs', 'dd ', 'format']
    if any(d in command for d in dangerous):
        return jsonify({'error': 'Command not allowed'}), 403
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        return jsonify({
            'success': True,
            'output': result.stdout,
            'error': result.stderr,
            'return_code': result.returncode
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# SWARM ENDPOINTS
# ============================================================================

@app.route('/api/swarm/task/create', methods=['POST'])
def create_swarm_task():
    """Create a task for the swarm"""
    if not swarm_system:
        return jsonify({'error': 'Swarm not available'}), 503
    
    data = request.json
    task_description = data.get('description', '')
    
    try:
        task = swarm_system.create_task(task_description)
        tasks.append(task)
        
        socketio.emit('task_created', task)
        
        return jsonify({
            'success': True,
            'task': task,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/swarm/tasks', methods=['GET'])
def list_tasks():
    return jsonify({'tasks': tasks})

# ============================================================================
# WORKFLOW ENDPOINTS
# ============================================================================

@app.route('/api/workflow/create', methods=['POST'])
def create_workflow():
    """Create a workflow"""
    if not workflow_orchestrator:
        return jsonify({'error': 'Workflow orchestrator not available'}), 503
    
    data = request.json
    workflow_def = data.get('definition', {})
    
    try:
        workflow = workflow_orchestrator.create_workflow(workflow_def)
        workflows.append(workflow)
        
        return jsonify({
            'success': True,
            'workflow': workflow,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/workflow/execute/<workflow_id>', methods=['POST'])
def execute_workflow(workflow_id):
    """Execute a workflow"""
    if not workflow_orchestrator:
        return jsonify({'error': 'Workflow orchestrator not available'}), 503
    
    try:
        result = workflow_orchestrator.execute(workflow_id)
        
        socketio.emit('workflow_executed', result)
        
        return jsonify({
            'success': True,
            'result': result,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# MONITORING ENDPOINTS
# ============================================================================

@app.route('/api/monitoring/health', methods=['GET'])
def monitoring_health():
    """Get system health"""
    if not monitoring_system:
        return jsonify({'error': 'Monitoring not available'}), 503
    
    try:
        health = monitoring_system.get_health_status()
        return jsonify({
            'success': True,
            'health': health,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# BUSINESS AUTOMATION ENDPOINTS
# ============================================================================

@app.route('/api/business/autonomous-textbook', methods=['POST'])
def create_autonomous_textbook_business():
    """Complete autonomous textbook business - does EVERYTHING"""
    data = request.json
    topic = data.get('topic', 'Spiritual Direction')
    title = data.get('title', f'The Complete Guide to {topic}')
    price = data.get('price', 29.99)
    
    try:
        logger.info(f"Creating autonomous textbook business for: {title}")
        
        # Step 1: Generate textbook
        textbook_prompt = f"Write a comprehensive textbook on {topic} with 10 chapters"
        textbook_content = llm_manager.generate(textbook_prompt) if llm_manager else {'response': 'Demo content'}
        
        # Step 2: Save textbook
        textbook_file = f"{title.replace(' ', '_')}.txt"
        with open(textbook_file, 'w') as f:
            f.write(textbook_content.get('response', ''))
        
        # Step 3: Generate marketing
        marketing_prompt = f"Create marketing copy for textbook: {title}"
        marketing = llm_manager.generate(marketing_prompt) if llm_manager else {'response': 'Demo marketing'}
        
        # Step 4: Create website
        website_prompt = f"Create HTML sales page for {title}"
        website = llm_manager.generate(website_prompt) if llm_manager else {'response': '<html>Demo</html>'}
        
        website_file = f"{title.replace(' ', '_')}_sales.html"
        with open(website_file, 'w') as f:
            f.write(website.get('response', ''))
        
        # Step 5: Setup payment
        payment = business_automation.create_product_launch(title, price, topic) if business_automation else {'payment_link': 'demo'}
        
        # Step 6: Social media
        social = business_automation.social_media.post_to_all(f"New: {title}!") if business_automation else {'success': True}
        
        # Step 7: Store product
        product = {
            'id': str(uuid.uuid4()),
            'title': title,
            'price': price,
            'textbook_file': textbook_file,
            'website_file': website_file,
            'payment_link': payment.get('payment_link', 'demo'),
            'created_at': datetime.now().isoformat()
        }
        products.append(product)
        
        return jsonify({
            'success': True,
            'product': product,
            'message': 'Autonomous textbook business created!'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/business/products', methods=['GET'])
def list_products():
    return jsonify({'products': products})

# ============================================================================
# PRODUCTION SETUP ENDPOINTS
# ============================================================================

@app.route('/api/production/readiness', methods=['GET'])
def check_production_readiness():
    """Check if system is ready for production"""
    if not production_readiness:
        return jsonify({'error': 'Production readiness not available'}), 503
    
    try:
        result = production_readiness.check_all()
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/production/setup', methods=['POST'])
def setup_production():
    """Run complete production setup"""
    if not production_readiness:
        return jsonify({'error': 'Production readiness not available'}), 503
    
    try:
        result = production_readiness.setup_production()
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/production/ssl/status', methods=['GET'])
def check_ssl_status():
    """Check SSL certificate status"""
    if not production_readiness:
        return jsonify({'error': 'Production readiness not available'}), 503
    
    try:
        has_ssl = production_readiness.ssl_configurator.check_ssl_installed()
        return jsonify({
            'ssl_installed': has_ssl,
            'domain': production_readiness.ssl_configurator.domain
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/production/schema/check', methods=['GET'])
def check_schema():
    """Check database schema compatibility"""
    if not production_readiness:
        return jsonify({'error': 'Production readiness not available'}), 503
    
    try:
        result = production_readiness.schema_manager.check_schema_compatibility()
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/production/schema/migrate', methods=['POST'])
def migrate_schema():
    """Create and apply unified schema"""
    if not production_readiness:
        return jsonify({'error': 'Production readiness not available'}), 503
    
    try:
        # Create unified schema
        create_result = production_readiness.schema_manager.create_unified_schema()
        if not create_result['success']:
            return jsonify(create_result), 500
        
        return jsonify({
            'success': True,
            'message': 'Unified schema created',
            'schema_file': create_result['schema_file'],
            'note': 'Schema file created. Apply manually with: psql < murphy_unified_schema.sql'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# WEBSOCKET EVENTS
# ============================================================================

@socketio.on('connect')
def handle_connect():
    emit('connected', {
        'message': 'Connected to Murphy Complete System',
        'systems': SYSTEMS_AVAILABLE
    })

@socketio.on('execute_task')
def handle_task(data):
    """Execute a task across all systems"""
    task_type = data.get('type', '')
    task_data = data.get('data', {})
    
    result = {
        'task_type': task_type,
        'timestamp': datetime.now().isoformat()
    }
    
    # Route to appropriate system
    if task_type == 'generate' and llm_manager:
        result['output'] = llm_manager.generate(task_data.get('prompt', ''))
    elif task_type == 'command':
        # Execute command
        pass
    elif task_type == 'artifact' and artifact_generator:
        # Generate artifact
        pass
    
    emit('task_result', result)

# ============================================================================
# PAYMENT VERIFICATION ENDPOINTS
# ============================================================================

@app.route('/api/payment/create-sale', methods=['POST'])
def create_sale():
    """Create a new sale record"""
    if not payment_verification:
        return jsonify({'error': 'Payment verification not available'}), 503
    
    data = request.json
    result = payment_verification.create_sale(
        product_id=data.get('product_id'),
        customer_email=data.get('customer_email'),
        amount=data.get('amount'),
        payment_provider=data.get('payment_provider'),
        payment_id=data.get('payment_id')
    )
    return jsonify(result)

@app.route('/api/payment/verify', methods=['POST'])
def verify_payment():
    """Verify a payment"""
    if not payment_verification:
        return jsonify({'error': 'Payment verification not available'}), 503
    
    data = request.json
    result = payment_verification.verify_payment(
        sale_id=data.get('sale_id'),
        payment_provider=data.get('payment_provider'),
        payment_id=data.get('payment_id')
    )
    return jsonify(result)

@app.route('/api/payment/sale/<sale_id>', methods=['GET'])
def get_sale(sale_id):
    """Get sale information"""
    if not payment_verification:
        return jsonify({'error': 'Payment verification not available'}), 503
    
    sale = payment_verification.get_sale(sale_id)
    if sale:
        return jsonify({'success': True, 'sale': sale})
    return jsonify({'success': False, 'error': 'Sale not found'}), 404

@app.route('/api/payment/customer/<email>', methods=['GET'])
def get_customer_purchases(email):
    """Get customer purchase history"""
    if not payment_verification:
        return jsonify({'error': 'Payment verification not available'}), 503
    
    purchases = payment_verification.get_customer_purchases(email)
    return jsonify({'success': True, 'purchases': purchases, 'count': len(purchases)})

@app.route('/api/payment/sales', methods=['GET'])
def get_all_sales():
    """Get all sales"""
    if not payment_verification:
        return jsonify({'error': 'Payment verification not available'}), 503
    
    status = request.args.get('status')
    sales = payment_verification.get_all_sales(status=status)
    return jsonify({'success': True, 'sales': sales, 'count': len(sales)})

@app.route('/api/payment/stats', methods=['GET'])
def get_payment_stats():
    """Get payment statistics"""
    if not payment_verification:
        return jsonify({'error': 'Payment verification not available'}), 503
    
    stats = payment_verification.get_sales_stats()
    return jsonify({'success': True, 'stats': stats})

# ============================================================================
# ARTIFACT DOWNLOAD ENDPOINTS
# ============================================================================

@app.route('/api/download/<download_token>', methods=['GET'])
def download_artifact(download_token):
    """Download artifact with payment verification"""
    if not artifact_download:
        return jsonify({'error': 'Download system not available'}), 503
    
    result = artifact_download.download_artifact(download_token)
    
    if not result['success']:
        return jsonify(result), 403
    
    # Send file
    try:
        return send_file(
            result['file_path'],
            as_attachment=True,
            download_name=os.path.basename(result['file_path'])
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download/url/<product_id>/<sale_id>', methods=['GET'])
def get_download_url(product_id, sale_id):
    """Get download URL for a product"""
    if not artifact_download:
        return jsonify({'error': 'Download system not available'}), 503
    
    result = artifact_download.get_download_url(product_id, sale_id)
    return jsonify(result)

@app.route('/api/download/customer/<email>', methods=['GET'])
def list_customer_downloads(email):
    """List customer's available downloads"""
    if not artifact_download:
        return jsonify({'error': 'Download system not available'}), 503
    
    result = artifact_download.list_customer_downloads(email)
    return jsonify(result)

@app.route('/api/download/info/<product_id>', methods=['GET'])
def get_artifact_info(product_id):
    """Get artifact information"""
    if not artifact_download:
        return jsonify({'error': 'Download system not available'}), 503
    
    result = artifact_download.get_artifact_info(product_id)
    return jsonify(result)

@app.route('/api/download/stats', methods=['GET'])
def get_download_stats():
    """Get download statistics"""
    if not artifact_download:
        return jsonify({'error': 'Download system not available'}), 503
    
    result = artifact_download.get_download_stats()
    return jsonify(result)

# ============================================================================
# SCHEDULED AUTOMATION ENDPOINTS
# ============================================================================

@app.route('/api/automation/create', methods=['POST'])
def create_automation():
    """Create a new automation"""
    if not automation_system:
        return jsonify({'error': 'Automation system not available'}), 503
    
    data = request.json
    result = automation_system.create_automation(
        name=data.get('name'),
        automation_type=data.get('type'),
        command=data.get('command'),
        schedule=data.get('schedule'),
        metadata=data.get('metadata')
    )
    return jsonify(result)

@app.route('/api/automation/list', methods=['GET'])
def list_automations():
    """List all automations"""
    if not automation_system:
        return jsonify({'error': 'Automation system not available'}), 503
    
    automation_type = request.args.get('type')
    enabled_only = request.args.get('enabled_only', 'false').lower() == 'true'
    
    automations = automation_system.list_automations(
        automation_type=automation_type,
        enabled_only=enabled_only
    )
    return jsonify({'success': True, 'automations': automations, 'count': len(automations)})

@app.route('/api/automation/get/<automation_id>', methods=['GET'])
def get_automation(automation_id):
    """Get automation details"""
    if not automation_system:
        return jsonify({'error': 'Automation system not available'}), 503
    
    automation = automation_system.get_automation(automation_id)
    if automation:
        return jsonify({'success': True, 'automation': automation})
    return jsonify({'success': False, 'error': 'Automation not found'}), 404

@app.route('/api/automation/execute/<automation_id>', methods=['POST'])
def execute_automation(automation_id):
    """Execute an automation"""
    if not automation_system:
        return jsonify({'error': 'Automation system not available'}), 503
    
    result = automation_system.execute_automation(automation_id)
    return jsonify(result)

@app.route('/api/automation/enable/<automation_id>', methods=['POST'])
def enable_automation(automation_id):
    """Enable an automation"""
    if not automation_system:
        return jsonify({'error': 'Automation system not available'}), 503
    
    result = automation_system.enable_automation(automation_id)
    return jsonify(result)

@app.route('/api/automation/disable/<automation_id>', methods=['POST'])
def disable_automation(automation_id):
    """Disable an automation"""
    if not automation_system:
        return jsonify({'error': 'Automation system not available'}), 503
    
    result = automation_system.disable_automation(automation_id)
    return jsonify(result)

@app.route('/api/automation/delete/<automation_id>', methods=['DELETE'])
def delete_automation(automation_id):
    """Delete an automation"""
    if not automation_system:
        return jsonify({'error': 'Automation system not available'}), 503
    
    result = automation_system.delete_automation(automation_id)
    return jsonify(result)

@app.route('/api/automation/history', methods=['GET'])
def get_automation_history():
    """Get automation execution history"""
    if not automation_system:
        return jsonify({'error': 'Automation system not available'}), 503
    
    automation_id = request.args.get('automation_id')
    limit = int(request.args.get('limit', 50))
    
    history = automation_system.get_execution_history(
        automation_id=automation_id,
        limit=limit
    )
    return jsonify({'success': True, 'history': history, 'count': len(history)})

@app.route('/api/automation/stats', methods=['GET'])
def get_automation_stats():
    """Get automation statistics"""
    if not automation_system:
        return jsonify({'error': 'Automation system not available'}), 503
    
    stats = automation_system.get_stats()
    return jsonify({'success': True, 'stats': stats})

@app.route('/api/automation/scheduler/start', methods=['POST'])
def start_scheduler():
    """Start automation scheduler"""
    if not automation_system:
        return jsonify({'error': 'Automation system not available'}), 503
    
    result = automation_system.start_scheduler()
    return jsonify(result)

@app.route('/api/automation/scheduler/stop', methods=['POST'])
def stop_scheduler():
    """Stop automation scheduler"""
    if not automation_system:
        return jsonify({'error': 'Automation system not available'}), 503
    
    result = automation_system.stop_scheduler()
    return jsonify(result)

# ============================================================================
# LIBRARIAN COMMAND INTEGRATION ENDPOINTS
# ============================================================================

@app.route('/api/librarian/store-commands', methods=['POST'])
def store_commands_in_librarian():
    """Store all commands in Librarian"""
    if not librarian_integration:
        return jsonify({'error': 'Librarian integration not available'}), 503
    
    result = librarian_integration.store_all_commands()
    return jsonify(result)

@app.route('/api/librarian/search-commands', methods=['GET'])
def search_commands():
    """Search for commands"""
    if not librarian_integration:
        return jsonify({'error': 'Librarian integration not available'}), 503
    
    query = request.args.get('query', '')
    limit = int(request.args.get('limit', 5))
    
    result = librarian_integration.search_commands(query, limit)
    return jsonify(result)

@app.route('/api/librarian/generate-command', methods=['POST'])
def generate_command():
    """Generate command for a task"""
    if not librarian_integration:
        return jsonify({'error': 'Librarian integration not available'}), 503
    
    data = request.json
    task = data.get('task', '')
    
    result = librarian_integration.generate_command_for_task(task)
    return jsonify(result)

@app.route('/api/librarian/command-stats', methods=['GET'])
def get_command_stats():
    """Get command usage statistics"""
    if not librarian_integration:
        return jsonify({'error': 'Librarian integration not available'}), 503
    
    result = librarian_integration.get_command_usage_stats()
    return jsonify(result)

@app.route('/api/librarian/suggest-commands', methods=['POST'])
def suggest_commands():
    """Suggest commands for context"""
    if not librarian_integration:
        return jsonify({'error': 'Librarian integration not available'}), 503
    
    data = request.json
    context = data.get('context', '')
    
    result = librarian_integration.suggest_commands_for_context(context)
    return jsonify(result)



# ============================================================================
# MULTI-AGENT BOOK GENERATION ENDPOINTS
# ============================================================================

@app.route('/api/book/generate-multi-agent', methods=['POST'])
def generate_book_multi_agent_endpoint():
    """
    Generate a book using multi-agent parallel processing
    
    Request body:
    {
        "topic": "AI Automation for Small Business",
        "title": "The Complete Guide to AI Automation",
        "num_chapters": 9,
        "writing_style": "conversational"  // optional, defaults to "auto"
    }
    """
    if not llm_manager:
        return jsonify({'error': 'LLM not available'}), 503
    
    data = request.json
    topic = data.get('topic', '')
    title = data.get('title', '')
    num_chapters = data.get('num_chapters', 9)
    writing_style = data.get('writing_style', 'auto')
    
    if not topic or not title:
        return jsonify({'error': 'topic and title are required'}), 400
    
    try:
        # Run async function in sync context
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            generate_book_multi_agent(llm_manager, topic, title, num_chapters)
        )
        
        loop.close()
        
        # Save the book
        filename = title.replace(' ', '_') + '.txt'
        with open(filename, 'w') as f:
            f.write(result['content'])
        
        return jsonify({
            'success': True,
            'book': result,
            'filename': filename,
            'message': f'Book generated with {num_chapters} chapters using multi-agent system'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/book/writing-styles', methods=['GET'])
def get_writing_styles():
    """Get available writing styles"""
    styles = [style.value for style in WritingStyle]
    return jsonify({
        'styles': styles,
        'default': 'auto',
        'description': {
            'academic': 'Formal, research-based, citations',
            'conversational': 'Friendly, engaging, accessible',
            'technical': 'Precise, detailed, expert-level',
            'storytelling': 'Narrative-driven, examples, stories',
            'practical': 'Action-oriented, how-to, hands-on',
            'inspirational': 'Motivational, uplifting, aspirational',
            'humorous': 'Light, entertaining, witty',
            'auto': 'LLM decides best style for topic'
        }
    })

@app.route('/api/book/multi-agent/status', methods=['GET'])
def multi_agent_status():
    """Get status of multi-agent book generation system"""
    return jsonify({
        'available': True,
        'features': [
            'Parallel chapter writing (up to 9 simultaneous)',
            'Collective mind coordination',
            'Three-stage processing (Magnify/Simplify/Solidify)',
            'Multiple writing styles',
            'Agent profile customization',
            'Context consistency checking',
            'Cross-chapter reference tracking'
        ],
        'max_parallel_chapters': 9,
        'processing_stages': ['magnify', 'simplify', 'solidify']
    })



# ============================================================================
# ENHANCED RUNTIME ORCHESTRATOR ENDPOINTS
# ============================================================================

@app.route('/api/runtime/process', methods=['POST'])
def process_request_runtime():
    """Runtime orchestrator endpoint"""
    if not RUNTIME_ORCHESTRATOR_AVAILABLE:
        return jsonify({'error': 'Runtime orchestrator not available'}), 503

    """
    Process any request using enhanced runtime orchestrator with dynamic agent generation
    
    This works for ANY task type:
    - Books, articles, content
    - Software development
    - Research projects
    - Marketing campaigns
    - Business operations
    - Data analysis
    - etc.
    
    Request body:
    {
        "task": "Write a complete book about AI automation for small businesses",
        "capacity_limit": 9,  // optional, default 9
        "max_parallel": 9     // optional, default 9
    }
    
    The runtime will:
    1. Analyze the task
    2. Determine optimal number of agents
    3. Generate specialized agents dynamically
    4. Execute in parallel with collective mind
    5. Ensure consistency across all outputs
    6. Synthesize final coherent result
    """
    if not llm_manager:
        return jsonify({'error': 'LLM not available'}), 503
    
    data = request.json
    task = data.get('task', '')
    capacity_limit = data.get('capacity_limit', 9)
    max_parallel = data.get('max_parallel', 9)
    
    if not task:
        return jsonify({'error': 'task is required'}), 400
    
    try:
        # Update capacity if specified
        if capacity_limit != 9:
            enhanced_orchestrator.set_capacity_limit(capacity_limit)
        if max_parallel != 9:
            enhanced_orchestrator.set_max_parallel(max_parallel)
        
        # Run async function in sync context
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            enhanced_orchestrator.process_request(task)
        )
        
        loop.close()
        
        # Save output to file
        task_id = result.get('task_id')
        filename = f"runtime_task_{task_id}.txt"
        with open(filename, 'w') as f:
            f.write(result.get('final_output', ''))
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'result': result,
            'filename': filename,
            'message': f'Task completed with {result.get("num_agents", 0)} agents'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/runtime/task/<task_id>', methods=['GET'])
def get_runtime_task_status(task_id):
    """Runtime orchestrator endpoint"""
    if not RUNTIME_ORCHESTRATOR_AVAILABLE:
        return jsonify({'error': 'Runtime orchestrator not available'}), 503

    """Get status of a specific runtime task"""
    try:
        status = enhanced_orchestrator.get_task_status(task_id)
        if status:
            return jsonify({'success': True, 'task': status})
        else:
            return jsonify({'error': 'Task not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/runtime/tasks', methods=['GET'])
def get_all_runtime_tasks():
    """Runtime orchestrator endpoint"""
    if not RUNTIME_ORCHESTRATOR_AVAILABLE:
        return jsonify({'error': 'Runtime orchestrator not available'}), 503

    """Get all runtime task history"""
    try:
        tasks = enhanced_orchestrator.get_all_tasks()
        return jsonify({'success': True, 'tasks': tasks})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/runtime/capacity', methods=['POST'])
def set_runtime_capacity():
    """Runtime orchestrator endpoint"""
    if not RUNTIME_ORCHESTRATOR_AVAILABLE:
        return jsonify({'error': 'Runtime orchestrator not available'}), 503

    """
    Update runtime capacity limits
    
    Use for rate limiting or adjusting to available resources
    
    Request body:
    {
        "capacity_limit": 9,  // Max agents to generate
        "max_parallel": 9     // Max simultaneous executions
    }
    """
    try:
        data = request.json
        capacity_limit = data.get('capacity_limit')
        max_parallel = data.get('max_parallel')
        
        if capacity_limit:
            enhanced_orchestrator.set_capacity_limit(capacity_limit)
        if max_parallel:
            enhanced_orchestrator.set_max_parallel(max_parallel)
        
        return jsonify({
            'success': True,
            'message': 'Capacity limits updated',
            'capacity_limit': enhanced_orchestrator.capacity_limit,
            'max_parallel': enhanced_orchestrator.max_parallel
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/runtime/status', methods=['GET'])
def get_runtime_status():
    """Runtime orchestrator endpoint"""
    if not RUNTIME_ORCHESTRATOR_AVAILABLE:
        return jsonify({'error': 'Runtime orchestrator not available'}), 503

    """Get enhanced runtime orchestrator status"""
    try:
        return jsonify({
            'available': True,
            'type': 'enhanced_runtime_orchestrator',
            'features': [
                'Dynamic agent generation from any request',
                'Automatic task breakdown and parallelization',
                'Collective mind coordination',
                'Capacity and rate limit aware scaling',
                'Works for ANY task type',
                'Context consistency checking',
                'Cross-agent knowledge sharing'
            ],
            'capacity_limit': enhanced_orchestrator.capacity_limit,
            'max_parallel': enhanced_orchestrator.max_parallel,
            'active_tasks': len(enhanced_orchestrator.active_tasks),
            'total_tasks_completed': len(enhanced_orchestrator.task_history)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500



# ============================================================================
# ENHANCED LLM MANAGEMENT ENDPOINTS
# ============================================================================

@app.route('/api/llm/status', methods=['GET'])
def get_llm_status():
    """Get detailed LLM provider status"""
    if not llm_manager:
        return jsonify({'error': 'LLM manager not available'}), 503
    
    try:
        return jsonify({
            'success': True,
            'status': llm_manager.get_status()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/llm/usage', methods=['GET'])
def get_llm_usage():
    """Get LLM usage statistics"""
    if not llm_manager:
        return jsonify({'error': 'LLM manager not available'}), 503
    
    try:
        return jsonify({
            'success': True,
            'usage': llm_manager.get_usage_stats()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/llm/test-rotation', methods=['GET'])
def test_llm_rotation():
    """Test key rotation by making multiple calls"""
    if not llm_manager:
        return jsonify({'error': 'LLM manager not available'}), 503
    
    try:
        num_calls = 10
        results = []
        
        for i in range(num_calls):
            result = llm_manager.generate(f"Test call {i+1}: What is 2+2?")
            results.append({
                'call': i+1,
                'provider': result['provider'],
                'key_index': result['key_index'],
                'success': result['success']
            })
        
        # Analyze distribution
        key_counts = {}
        for r in results:
            if r['key_index'] is not None:
                key_counts[r['key_index']] = key_counts.get(r['key_index'], 0) + 1
        
        return jsonify({
            'success': True,
            'calls': num_calls,
            'results': results,
            'key_distribution': key_counts,
            'unique_keys_used': len(key_counts)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/llm/test-math', methods=['POST'])
def test_llm_math():
    """Test math routing to Aristotle"""
    if not llm_manager:
        return jsonify({'error': 'LLM manager not available'}), 503
    
    try:
        data = request.json
        prompt = data.get('prompt', 'Calculate 2+2')
        
        result = llm_manager.generate(prompt)
        
        return jsonify({
            'success': True,
            'prompt': prompt,
            'provider': result['provider'],
            'math_detected': result['math_task'],
            'response': result.get('response', '')[:500],  # First 500 chars
            'key_index': result['key_index']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500



# ============================================================================
# KNOWLEDGE PIPELINE ENDPOINTS
# ============================================================================

@app.route('/api/pipeline/explode', methods=['POST'])
def explode_request():
    """
    Explode vague request into complete automation plan
    
    Librarian generates 80% automatically, identifies what needs human input
    
    Request body:
    {
        "request": "Automate my publishing business"
    }
    """
    if not knowledge_pipeline:
        return jsonify({'error': 'Knowledge pipeline not available'}), 503
    
    data = request.json
    user_request = data.get('request', '')
    
    if not user_request:
        return jsonify({'error': 'request is required'}), 400
    
    try:
        librarian = knowledge_pipeline['librarian_commands']
        plan = librarian.explode_request(user_request)
        
        return jsonify({
            'success': True,
            'plan': plan,
            'auto_generated': f"{plan.get('auto_generated_percentage', 0)}%",
            'human_input_needed': plan.get('requires_human_input', [])
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/pipeline/org-chart', methods=['POST'])
def generate_org_chart():
    """
    Generate org chart from business description
    
    Matches to template library, adapts public strategies, solidifies for Murphy
    
    Request body:
    {
        "business_description": "Spiritual book publishing company",
        "public_strategies": ["content_first", "niche_targeting"]
    }
    """
    if not knowledge_pipeline:
        return jsonify({'error': 'Knowledge pipeline not available'}), 503
    
    data = request.json
    description = data.get('business_description', '')
    strategies = data.get('public_strategies', [])
    
    if not description:
        return jsonify({'error': 'business_description is required'}), 400
    
    try:
        org_chart_lib = knowledge_pipeline['org_chart_library']
        org_chart = org_chart_lib.match_org_chart(description, strategies)
        
        return jsonify({
            'success': True,
            'org_chart': org_chart
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/pipeline/block/verify', methods=['POST'])
def verify_block():
    """
    Verify a block and get Magnify/Simplify/Solidify recommendations
    
    Request body:
    {
        "block_id": "block_123",
        "block_name": "Market Research",
        "block_content": "Research spiritual book market...",
        "confidence": "yellow",
        "action": "magnify"  // or "simplify" or "solidify"
    }
    """
    if not knowledge_pipeline:
        return jsonify({'error': 'Knowledge pipeline not available'}), 503
    
    data = request.json
    block_id = data.get('block_id', '')
    block_name = data.get('block_name', '')
    block_content = data.get('block_content', '')
    confidence = data.get('confidence', 'yellow')
    action = data.get('action', 'solidify')
    
    if not all([block_id, block_name, block_content]):
        return jsonify({'error': 'block_id, block_name, and block_content are required'}), 400
    
    try:
        # Create block
        block = Block(
            block_id=block_id,
            name=block_name,
            content=block_content,
            confidence=ConfidenceLevel(confidence)
        )
        
        # Get verification
        verifier = knowledge_pipeline['block_verification']
        
        if action == 'magnify':
            result = verifier.magnify(block)
        elif action == 'simplify':
            result = verifier.simplify(block)
        else:  # solidify
            result = verifier.solidify(block)
        
        return jsonify({
            'success': True,
            'action': action,
            'result': result
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/pipeline/block/update', methods=['POST'])
def update_block_cascade():
    """
    Update a block and get cascade effects
    
    Shows which downstream blocks need regeneration
    
    Request body:
    {
        "block_id": "block_123",
        "new_content": "Updated content..."
    }
    """
    if not knowledge_pipeline:
        return jsonify({'error': 'Knowledge pipeline not available'}), 503
    
    data = request.json
    block_id = data.get('block_id', '')
    new_content = data.get('new_content', '')
    
    if not all([block_id, new_content]):
        return jsonify({'error': 'block_id and new_content are required'}), 400
    
    try:
        global_state = knowledge_pipeline['global_state']
        affected = global_state.update_block(block_id, new_content)
        
        # Get regeneration order
        regen_order = global_state.get_regeneration_order(affected)
        
        return jsonify({
            'success': True,
            'updated': block_id,
            'affected_blocks': affected,
            'regeneration_order': regen_order,
            'message': f'{len(affected)} blocks need regeneration'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/pipeline/info-source', methods=['POST'])
def decide_info_source():
    """
    Decide where information should come from
    
    Determines: user provides, AI generates, or hire external
    
    Request body:
    {
        "information_needed": "Brand guidelines and color schemes",
        "user_has_capability": true
    }
    """
    if not knowledge_pipeline:
        return jsonify({'error': 'Knowledge pipeline not available'}), 503
    
    data = request.json
    info_needed = data.get('information_needed', '')
    user_capability = data.get('user_has_capability', False)
    
    if not info_needed:
        return jsonify({'error': 'information_needed is required'}), 400
    
    try:
        decider = knowledge_pipeline['info_decider']
        decision = decider.decide_source(info_needed, user_capability)
        
        return jsonify({
            'success': True,
            'decision': decision
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/pipeline/schedule', methods=['POST'])
def schedule_tasks():
    """
    Schedule tasks with master scheduler
    
    Aligns priority, respects dependencies, manages feedback loops
    
    Request body:
    {
        "blocks": [
            {
                "block_id": "block_1",
                "name": "Research",
                "content": "...",
                "confidence": "green",
                "dependencies": [],
                "affects": ["block_2", "block_3"]
            }
        ]
    }
    """
    if not knowledge_pipeline:
        return jsonify({'error': 'Knowledge pipeline not available'}), 503
    
    data = request.json
    blocks_data = data.get('blocks', [])
    
    if not blocks_data:
        return jsonify({'error': 'blocks are required'}), 400
    
    try:
        global_state = knowledge_pipeline['global_state']
        scheduler = knowledge_pipeline['master_scheduler']
        
        # Create blocks and register
        blocks = []
        for block_data in blocks_data:
            block = Block(
                block_id=block_data.get('block_id'),
                name=block_data.get('name'),
                content=block_data.get('content', ''),
                confidence=ConfidenceLevel(block_data.get('confidence', 'yellow')),
                dependencies=block_data.get('dependencies', []),
                affects=block_data.get('affects', [])
            )
            blocks.append(block)
            global_state.register_block(block)
        
        # Schedule
        execution_order = scheduler.schedule_tasks(blocks)
        
        return jsonify({
            'success': True,
            'execution_order': execution_order,
            'total_tasks': len(execution_order)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/pipeline/status', methods=['GET'])
def pipeline_status():
    """Get knowledge pipeline system status"""
    if not knowledge_pipeline:
        return jsonify({'error': 'Knowledge pipeline not available'}), 503
    
    try:
        global_state = knowledge_pipeline['global_state']
        
        return jsonify({
            'success': True,
            'available': True,
            'components': {
                'global_state': True,
                'info_decider': True,
                'block_verification': True,
                'org_chart_library': True,
                'librarian_commands': True,
                'master_scheduler': True
            },
            'stats': {
                'registered_blocks': len(global_state.state),
                'timeline_events': len(global_state.timeline),
                'cascade_queue': len(global_state.cascade_queue)
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500



# ============================================================================
# AGENT COMMUNICATION ENDPOINTS
# ============================================================================

@app.route('/api/agent/message/send', methods=['POST'])
def send_agent_message():
    """Send a message from one agent to another"""
    if not get_comm_hub():
        return jsonify({'success': False, 'error': 'Communication hub not initialized'}), 503
    try:
        data = request.json
        message = get_comm_hub().send_message(
            from_agent=data['from_agent'],
            to_agent=data['to_agent'],
            message_type=MessageType[data['message_type']],
            subject=data['subject'],
            body=data['body'],
            thread_id=data.get('thread_id'),
            requires_response=data.get('requires_response', False),
            attachments=data.get('attachments', [])
        )
        return jsonify({
            'success': True,
            'message': message.to_dict()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/agent/inbox/<agent_name>', methods=['GET'])
def get_agent_inbox(agent_name):
    """Get all messages for an agent"""
    if not get_comm_hub():
        return jsonify({'success': False, 'error': 'Communication hub not initialized'}), 503
    try:
        messages = get_comm_hub().get_agent_inbox(agent_name)
        return jsonify({
            'success': True,
            'agent': agent_name,
            'message_count': len(messages),
            'messages': [msg.to_dict() for msg in messages]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/agent/thread/<thread_id>', methods=['GET'])
def get_message_thread(thread_id):
    """Get all messages in a thread"""
    if not get_comm_hub():
        return jsonify({'success': False, 'error': 'Communication hub not initialized'}), 503
    try:
        messages = get_comm_hub().get_thread(thread_id)
        return jsonify({
            'success': True,
            'thread_id': thread_id,
            'message_count': len(messages),
            'messages': [msg.to_dict() for msg in messages]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/task/review/create', methods=['POST'])
def create_task_review():
    """Create a complete review state for an agent task"""
    if not get_comm_hub():
        return jsonify({'success': False, 'error': 'Communication hub not initialized'}), 503
    try:
        data = request.json
        review = get_comm_hub().create_task_review(
            task_id=data['task_id'],
            agent_name=data['agent_name'],
            agent_role=data['agent_role'],
            user_request=data['user_request']
        )
        return jsonify({
            'success': True,
            'review': review.to_dict()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/task/review/<task_id>', methods=['GET'])
def get_task_review(task_id):
    """Get the complete review state for a task"""
    if not get_comm_hub():
        return jsonify({'success': False, 'error': 'Communication hub not initialized'}), 503
    try:
        review = get_comm_hub().get_task_review(task_id)
        if not review:
            return jsonify({'success': False, 'error': 'Task not found'}), 404
        
        return jsonify({
            'success': True,
            'review': review.to_dict()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/task/review/all', methods=['GET'])
def get_all_task_reviews():
    """Get all task reviews"""
    if not get_comm_hub():
        return jsonify({'success': False, 'error': 'Communication hub not initialized'}), 503
    try:
        reviews = get_comm_hub().get_all_task_reviews()
        return jsonify({
            'success': True,
            'count': len(reviews),
            'reviews': [review.to_dict() for review in reviews]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/task/review/<task_id>/answer', methods=['POST'])
def answer_clarifying_question(task_id):
    """Answer a clarifying question to boost confidence"""
    if not get_comm_hub():
        return jsonify({'success': False, 'error': 'Communication hub not initialized'}), 503
    try:
        data = request.json
        review = get_comm_hub().update_task_with_answer(
            task_id=task_id,
            question_index=data['question_index'],
            answer=data['answer']
        )
        
        if not review:
            return jsonify({'success': False, 'error': 'Task not found'}), 404
        
        return jsonify({
            'success': True,
            'review': review.to_dict(),
            'new_confidence': review.librarian_confidence,
            'confidence_level': review.overall_confidence.value
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/librarian/deliverable/communicate', methods=['POST'])
def librarian_deliverable_communication():
    """Handle communication between Librarian and Deliverable Function"""
    if not get_comm_hub():
        return jsonify({'success': False, 'error': 'Communication hub not initialized'}), 503
    try:
        data = request.json
        result = get_comm_hub().librarian_deliverable_communication(
            task_id=data['task_id'],
            deliverable_request=data['request']
        )
        return jsonify({
            'success': True,
            'communication': result
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/task/review/<task_id>/gates', methods=['GET'])
def get_task_gates(task_id):
    """Get all decision gates for a task"""
    if not get_comm_hub():
        return jsonify({'success': False, 'error': 'Communication hub not initialized'}), 503
    try:
        review = get_comm_hub().get_task_review(task_id)
        if not review:
            return jsonify({'success': False, 'error': 'Task not found'}), 404
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'gates': [asdict(gate) for gate in review.gates],
            'overall_confidence': review.overall_confidence.value
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/task/review/<task_id>/cost-analysis', methods=['GET'])
def get_task_cost_analysis(task_id):
    """Get cost analysis for a task"""
    if not get_comm_hub():
        return jsonify({'success': False, 'error': 'Communication hub not initialized'}), 503
    try:
        review = get_comm_hub().get_task_review(task_id)
        if not review:
            return jsonify({'success': False, 'error': 'Task not found'}), 404
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'token_cost': review.token_cost,
            'revenue_potential': review.revenue_potential,
            'cost_benefit_ratio': review.cost_benefit_ratio,
            'recommendation': 'Proceed' if review.cost_benefit_ratio > 1 else 'Review Required'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500




# ============================================================================
# GENERATIVE DECISION GATE ENDPOINTS
# ============================================================================

@app.route('/api/gates/generate', methods=['POST'])
def generate_gates_for_task():
    """Generate decision gates dynamically for a task"""
    if not generative_gate_system:
        return jsonify({'success': False, 'error': 'Generative gate system not initialized'}), 503
    
    try:
        data = request.json
        task = data.get('task', {})
        business_context = data.get('business_context', {})
        
        # Analyze task
        analysis = generative_gate_system.analyze_task(task, business_context)
        
        # Generate gates
        context = {**task, **business_context}
        gates = generative_gate_system.generate_gates(analysis, context)
        
        return jsonify({
            'success': True,
            'analysis': analysis,
            'gates': [gate.dict() for gate in gates],
            'gate_count': len(gates)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/gates/sensors/status', methods=['GET'])
def get_sensors_status():
    """Get status of all sensor agents"""
    if not generative_gate_system:
        return jsonify({'success': False, 'error': 'Generative gate system not initialized'}), 503
    
    try:
        status = generative_gate_system.get_system_status()
        return jsonify({
            'success': True,
            'status': status
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/gates/sensors/<sensor_id>', methods=['GET'])
def get_sensor_details(sensor_id):
    """Get details of a specific sensor"""
    if not generative_gate_system:
        return jsonify({'success': False, 'error': 'Generative gate system not initialized'}), 503
    
    try:
        sensor = next((s for s in generative_gate_system.sensors if s.sensor_id == sensor_id), None)
        if not sensor:
            return jsonify({'success': False, 'error': 'Sensor not found'}), 404
        
        return jsonify({
            'success': True,
            'sensor': sensor.get_status()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/gates/learn', methods=['POST'])
def learn_from_outcome():
    """Learn from task outcome to improve future gate generation"""
    if not generative_gate_system:
        return jsonify({'success': False, 'error': 'Generative gate system not initialized'}), 503
    
    try:
        data = request.json
        task_id = data.get('task_id')
        gates = [GateSpecModel(**g) for g in data.get('gates', [])]
        outcome = data.get('outcome', {})
        
        generative_gate_system.learn_from_outcome(task_id, gates, outcome)
        
        return jsonify({
            'success': True,
            'message': 'Learning recorded',
            'patterns_count': len(generative_gate_system.historical_patterns)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/gates/capabilities', methods=['GET'])
def get_capabilities():
    """Get list of available capabilities"""
    if not generative_gate_system:
        return jsonify({'success': False, 'error': 'Generative gate system not initialized'}), 503
    
    try:
        from generative_gate_system import CapabilityRegistry
        capabilities = list(CapabilityRegistry._capabilities.keys())
        
        return jsonify({
            'success': True,
            'capabilities': capabilities,
            'count': len(capabilities)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/gates/capabilities/verify', methods=['POST'])
def verify_capability():
    """Verify if a capability exists"""
    if not generative_gate_system:
        return jsonify({'success': False, 'error': 'Generative gate system not initialized'}), 503
    
    try:
        data = request.json
        capability = data.get('capability')
        
        from generative_gate_system import CapabilityRegistry
        exists = CapabilityRegistry.verify_capability(capability)
        alternatives = CapabilityRegistry.suggest_alternatives(capability) if not exists else []
        
        return jsonify({
            'success': True,
            'capability': capability,
            'exists': exists,
            'alternatives': alternatives
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    # Initialize Enhanced Gate Integration after app is created
    if enhanced_gate_integration is None and librarian_system and generative_gate_system:
        try:
            enhanced_gate_integration = integrate_enhanced_gates(app, librarian_system, generative_gate_system)
            logger.info("✓ Enhanced Gate Integration initialized with app")
        except Exception as e:
            logger.error(f"✗ Failed to initialize Enhanced Gate Integration: {e}")
    
    # Initialize Dynamic Projection Gates after app is created
    if dynamic_projection_gates is None and librarian_system:
        try:
            dynamic_projection_gates = integrate_dynamic_projection_gates(app, librarian_system)
            logger.info("✓ Dynamic Projection Gate System initialized with app")
        except Exception as e:
            logger.error(f"✗ Failed to initialize Dynamic Projection Gates: {e}")
    
    # Initialize Autonomous Business Development System
    if autonomous_bd_system is None:
        try:
            autonomous_bd_system = AutonomousBusinessDevelopment(murphy_api_base="http://localhost:3002")
            logger.info("✓ Autonomous Business Development System initialized")
            
            # Add API endpoints for autonomous BD
            @app.route('/api/bd/research', methods=['POST'])
            def bd_research():
                """Research potential customers"""
                from flask import request, jsonify
                try:
                    data = request.json
                    leads = autonomous_bd_system.research_potential_customers(
                        target_industry=data.get('industry', 'SaaS'),
                        company_size=data.get('size', '50-500'),
                        location=data.get('location', 'United States'),
                        count=data.get('count', 50)
                    )
                    return jsonify({'success': True, 'leads': leads, 'count': len(leads)})
                except Exception as e:
                    return jsonify({'success': False, 'error': str(e)}), 500
            
            @app.route('/api/bd/email/generate', methods=['POST'])
            def bd_generate_email():
                """Generate personalized email for lead"""
                from flask import request, jsonify
                try:
                    data = request.json
                    lead_id = data.get('lead_id')
                    if lead_id not in autonomous_bd_system.lead_database:
                        return jsonify({'success': False, 'error': 'Lead not found'}), 404
                    
                    lead = autonomous_bd_system.lead_database[lead_id]
                    email = autonomous_bd_system.generate_personalized_email(lead)
                    return jsonify({'success': True, 'email': email})
                except Exception as e:
                    return jsonify({'success': False, 'error': str(e)}), 500
            
            @app.route('/api/bd/email/send', methods=['POST'])
            def bd_send_email():
                """Send cold email to lead"""
                from flask import request, jsonify
                try:
                    data = request.json
                    email = data.get('email')
                    lead_id = data.get('lead_id')
                    result = autonomous_bd_system.send_cold_email(email, lead_id)
                    return jsonify({'success': True, 'result': result})
                except Exception as e:
                    return jsonify({'success': False, 'error': str(e)}), 500
            
            @app.route('/api/bd/responses', methods=['GET'])
            def bd_get_responses():
                """Get email responses"""
                from flask import jsonify
                try:
                    responses = autonomous_bd_system.monitor_email_responses()
                    return jsonify({'success': True, 'responses': responses, 'count': len(responses)})
                except Exception as e:
                    return jsonify({'success': False, 'error': str(e)}), 500
            
            @app.route('/api/bd/calendar/availability', methods=['POST'])
            def bd_check_availability():
                """Check calendar availability"""
                from flask import request, jsonify
                from datetime import datetime, timedelta
                try:
                    data = request.json
                    start_date = datetime.now() + timedelta(days=1)
                    end_date = start_date + timedelta(days=data.get('days', 14))
                    duration = data.get('duration', 30)
                    
                    slots = autonomous_bd_system.check_calendar_availability(start_date, end_date, duration)
                    return jsonify({'success': True, 'slots': slots, 'count': len(slots)})
                except Exception as e:
                    return jsonify({'success': False, 'error': str(e)}), 500
            
            @app.route('/api/bd/meeting/schedule', methods=['POST'])
            def bd_schedule_meeting():
                """Schedule meeting with lead"""
                from flask import request, jsonify
                from datetime import datetime
                try:
                    data = request.json
                    lead_id = data.get('lead_id')
                    preferred_time = datetime.fromisoformat(data.get('time'))
                    duration = data.get('duration', 30)
                    
                    if lead_id not in autonomous_bd_system.lead_database:
                        return jsonify({'success': False, 'error': 'Lead not found'}), 404
                    
                    lead = autonomous_bd_system.lead_database[lead_id]
                    meeting = autonomous_bd_system.schedule_meeting(lead, preferred_time, duration)
                    prep = autonomous_bd_system.generate_meeting_prep(meeting, lead)
                    
                    return jsonify({
                        'success': True,
                        'meeting': meeting,
                        'prep': prep
                    })
                except Exception as e:
                    return jsonify({'success': False, 'error': str(e)}), 500
            
            @app.route('/api/bd/campaign/run', methods=['POST'])
            def bd_run_campaign():
                """Run autonomous business development campaign"""
                from flask import request, jsonify
                try:
                    data = request.json
                    campaign = autonomous_bd_system.run_autonomous_campaign(
                        target_industry=data.get('industry', 'SaaS'),
                        lead_count=data.get('lead_count', 50),
                        auto_schedule=data.get('auto_schedule', True)
                    )
                    return jsonify({'success': True, 'campaign': campaign})
                except Exception as e:
                    return jsonify({'success': False, 'error': str(e)}), 500
            
            @app.route('/api/bd/leads', methods=['GET'])
            def bd_get_leads():
                """Get all researched leads"""
                from flask import jsonify
                try:
                    leads = list(autonomous_bd_system.lead_database.values())
                    return jsonify({'success': True, 'leads': leads, 'count': len(leads)})
                except Exception as e:
                    return jsonify({'success': False, 'error': str(e)}), 500
            
            @app.route('/api/bd/shadow/insights', methods=['POST'])
            def bd_get_shadow_insights():
                """Get shadow agent insights"""
                from flask import request, jsonify
                try:
                    data = request.json
                    context = data.get('context', 'general')
                    insights = autonomous_bd_system.get_shadow_agent_insights(context)
                    return jsonify({'success': True, 'insights': insights})
                except Exception as e:
                    return jsonify({'success': False, 'error': str(e)}), 500
            
            logger.info("✓ Added 10 Autonomous BD API endpoints")
            
        except Exception as e:
            logger.error(f"✗ Failed to initialize Autonomous BD System: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    logger.info("=" * 60)
    logger.info("Murphy Complete Integrated System")
    logger.info("=" * 60)
    logger.info("Systems Status:")
    for system, available in SYSTEMS_AVAILABLE.items():
        status = "✓" if available else "✗"
        logger.info(f"  {status} {system.upper()}")
    
    logger.info("=" * 60)
    logger.info("Starting server on port 3002...")
    
    socketio.run(app, host='0.0.0.0', port=3002, debug=False, allow_unsafe_werkzeug=True)