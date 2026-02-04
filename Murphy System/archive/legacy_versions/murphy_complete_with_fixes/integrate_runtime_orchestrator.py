"""
Murphy System - Runtime Orchestrator Integration

Integrates the Runtime Orchestrator with the existing backend system.
Connects existing components to the orchestrator and provides API endpoints.
"""

import asyncio
import logging
from flask import Flask, request, jsonify
from datetime import datetime

# Import our new runtime components
from runtime_orchestrator import (
    RuntimeOrchestrator,
    ComponentBus,
    ComponentRegistry,
    StateManager,
    WorkflowEngine,
    Task,
    TaskStatus,
    TaskPriority,
    get_orchestrator
)
from base_component import BaseComponent, ComponentAdapter

# Import existing backend systems (these will be wrapped as components)
import sys
sys.path.append('/workspace')

try:
    from murphy_backend_complete import (
        db_manager,
        shadow_agent_system,
        artifact_manager,
        monitoring_system
    )
    BACKEND_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Could not import backend systems: {e}")
    BACKEND_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RuntimeBackendIntegrator:
    """Integrates Runtime Orchestrator with Flask backend"""
    
    def __init__(self, app: Flask):
        self.app = app
        self.orchestrator = get_orchestrator()
        self.app_context = None
        
    def register_flask_routes(self):
        """Register Flask API routes for runtime operations"""
        
        @self.app.route('/api/runtime/status', methods=['GET'])
        def runtime_status():
            """Get runtime orchestrator status"""
            return jsonify(self.orchestrator.get_status())
            
        @self.app.route('/api/runtime/workflows', methods=['POST'])
        def execute_workflow():
            """Execute a workflow"""
            data = request.json
            workflow = data.get('workflow')
            
            if not workflow:
                return jsonify({'error': 'Workflow definition required'}), 400
                
            # Create async task to execute workflow
            async def run_workflow():
                return await self.orchestrator.execute_workflow(workflow)
                
            # Run in async context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(run_workflow())
                return jsonify(result)
            finally:
                loop.close()
                
        @self.app.route('/api/runtime/components', methods=['GET'])
        def list_components():
            """List all registered components"""
            return jsonify(self.orchestrator.component_registry.get_status())
            
        @self.app.route('/api/runtime/state', methods=['GET'])
        def get_runtime_state():
            """Get runtime state"""
            key = request.args.get('key')
            if key:
                state = self.orchestrator.state_manager.get_global_state(key)
            else:
                state = self.orchestrator.state_manager.get_global_state()
            return jsonify(state)
            
        @self.app.route('/api/runtime/tasks', methods=['GET', 'POST'])
        def manage_tasks():
            """Manage runtime tasks"""
            if request.method == 'POST':
                # Add new task
                data = request.json
                task = Task(
                    name=data.get('name', ''),
                    description=data.get('description', ''),
                    component=data.get('component', ''),
                    action=data.get('action', ''),
                    params=data.get('params', {}),
                    priority=TaskPriority[data.get('priority', 'MEDIUM').upper()]
                )
                self.orchestrator.add_task(task)
                return jsonify({'task_id': task.id, 'status': 'queued'})
            else:
                # List tasks
                return jsonify({
                    'active': len(self.orchestrator.active_tasks),
                    'queued': len(self.orchestrator.task_queue)
                })
                
        @self.app.route('/api/runtime/optimize', methods=['POST'])
        def optimize_execution():
            """Trigger AI Director optimization"""
            async def optimize():
                await self.orchestrator.optimize_execution()
                
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(optimize())
                return jsonify({'status': 'optimized'})
            finally:
                loop.close()
                
        @self.app.route('/api/runtime/events', methods=['GET'])
        def get_events():
            """Get recent events from component bus"""
            limit = request.args.get('limit', 50, type=int)
            events = self.orchestrator.component_bus.event_queue[-limit:]
            return jsonify(events)
            
        logger.info("Flask routes registered for runtime orchestrator")
        
    def register_existing_components(self):
        """Register existing backend components with orchestrator"""
        
        if not BACKEND_AVAILABLE:
            logger.warning("Backend systems not available, skipping component registration")
            return
            
        # Register Database Manager
        if db_manager:
            db_adapter = ComponentAdapter('database', db_manager)
            db_adapter.add_command('initialize', 'initialize')
            db_adapter.add_command('get_states', 'get_states')
            db_adapter.add_command('get_agents', 'get_agents')
            db_adapter.add_command('create_state', 'create_state')
            self.orchestrator.component_registry.register('database', db_adapter, {
                'description': 'Database management system',
                'version': '1.0'
            })
            
        # Register Shadow Agent System
        if shadow_agent_system:
            shadow_adapter = ComponentAdapter('shadow_agents', shadow_agent_system)
            shadow_adapter.add_command('learn', 'run_learning_cycle')
            shadow_adapter.add_command('get_proposals', 'get_proposals')
            shadow_adapter.add_command('get_agents', 'get_agents')
            self.orchestrator.component_registry.register('shadow_agents', shadow_adapter, {
                'description': 'Shadow agent learning system',
                'version': '1.0'
            })
            
        # Register Artifact Manager
        if artifact_manager:
            artifact_adapter = ComponentAdapter('artifacts', artifact_manager)
            artifact_adapter.add_command('generate', 'generate_artifact')
            artifact_adapter.add_command('list', 'list_artifacts')
            artifact_adapter.add_command('get', 'get_artifact')
            self.orchestrator.component_registry.register('artifacts', artifact_adapter, {
                'description': 'Artifact generation system',
                'version': '1.0'
            })
            
        # Register Monitoring System
        if monitoring_system:
            monitor_adapter = ComponentAdapter('monitoring', monitoring_system)
            monitor_adapter.add_command('health', 'get_health')
            monitor_adapter.add_command('metrics', 'get_metrics')
            monitor_adapter.add_command('analyze', 'run_analysis')
            self.orchestrator.component_registry.register('monitoring', monitor_adapter, {
                'description': 'System monitoring',
                'version': '1.0'
            })
            
        logger.info("Existing backend components registered with orchestrator")
        
    def initialize_orchestrator(self):
        """Initialize the runtime orchestrator"""
        self.orchestrator.initialize()
        logger.info("Runtime orchestrator initialized")
        
        # Initialize all components
        for name, component in self.orchestrator.component_registry.get_all().items():
            try:
                if asyncio.iscoroutinefunction(component.initialize):
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(component.initialize())
                    loop.close()
                else:
                    component.initialize()
                logger.info(f"Component initialized: {name}")
            except Exception as e:
                logger.error(f"Failed to initialize component {name}: {e}")
        
        # Set initial runtime state
        self.orchestrator.state_manager.set_global_state('initialized_at', datetime.now().isoformat())
        self.orchestrator.state_manager.set_global_state('version', '2.0.0-runtime')
        self.orchestrator.state_manager.set_global_state('mode', 'autonomous')
        
        # Publish initialization event
        self.orchestrator.component_bus.publish('runtime_initialized', {
            'timestamp': datetime.now().isoformat(),
            'components': list(self.orchestrator.component_registry.get_all().keys())
        })


def integrate_runtime_into_backend(app: Flask):
    """
    Integrate runtime orchestrator into existing Flask backend.
    
    Args:
        app: Flask application instance
        
    Returns:
        RuntimeBackendIntegrator instance
    """
    integrator = RuntimeBackendIntegrator(app)
    
    # Register routes
    integrator.register_flask_routes()
    
    # Register existing components
    integrator.register_existing_components()
    
    # Initialize orchestrator
    integrator.initialize_orchestrator()
    
    logger.info("Runtime orchestrator integrated into backend")
    
    return integrator


# Example workflow templates
WORKFLOW_TEMPLATES = {
    'business_proposal_generation': {
        'name': 'Business Proposal Generation',
        'version': '1.0',
        'steps': [
            {
                'name': 'Analyze Requirements',
                'component': 'librarian',
                'action': 'analyze',
                'params': {
                    'domain': 'business'
                }
            },
            {
                'name': 'Generate Content',
                'component': 'swarm',
                'action': 'execute',
                'params': {
                    'swarm_type': 'hybrid',
                    'task': 'create business proposal'
                }
            },
            {
                'name': 'Review Quality',
                'component': 'gates',
                'action': 'validate',
                'params': {
                    'gate_type': 'quality'
                }
            },
            {
                'name': 'Generate Artifacts',
                'component': 'artifacts',
                'action': 'generate',
                'params': {
                    'types': ['pdf', 'docx']
                }
            }
        ]
    },
    
    'system_health_check': {
        'name': 'System Health Check',
        'version': '1.0',
        'steps': [
            {
                'name': 'Check Component Health',
                'component': 'monitoring',
                'action': 'health',
                'params': {}
            },
            {
                'name': 'Run Learning Cycle',
                'component': 'shadow_agents',
                'action': 'learn',
                'params': {}
            },
            {
                'name': 'Optimize Execution',
                'action': 'optimize',
                'params': {}
            }
        ]
    }
}


def get_workflow_template(template_name: str) -> dict:
    """
    Get a workflow template by name.
    
    Args:
        template_name: Name of the template
        
    Returns:
        Workflow template definition
    """
    return WORKFLOW_TEMPLATES.get(template_name)