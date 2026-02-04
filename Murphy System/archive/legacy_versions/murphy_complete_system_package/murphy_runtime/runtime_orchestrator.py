# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Murphy System - Runtime Orchestrator

Central coordinator for all Murphy System components.
Provides orchestration, coordination, and management of component workflows.
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import uuid
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Task execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    """Task priority levels"""
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3


@dataclass
class Task:
    """Task definition"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    component: str = ""
    action: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    subtasks: List['Task'] = field(default_factory=list)


class ComponentBus:
    """Event bus for component communication"""
    
    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = {}
        self.event_queue: List[Dict[str, Any]] = []
        self.shared_state: Dict[str, Any] = {}
        self.locks: Dict[str, asyncio.Lock] = {}
        self.websocket_clients: List[Any] = []
        
    def subscribe(self, component: str, event_type: str, handler: Callable):
        """Subscribe component to events"""
        key = f"{component}:{event_type}"
        if key not in self.subscribers:
            self.subscribers[key] = []
        self.subscribers[key].append(handler)
        logger.info(f"Component {component} subscribed to {event_type}")
        
    def publish(self, event_type: str, data: Dict[str, Any]):
        """Publish event to all subscribers"""
        event = {
            'type': event_type,
            'data': data,
            'timestamp': datetime.now().isoformat()
        }
        
        # Add to queue
        self.event_queue.append(event)
        
        # Notify subscribers
        for key, handlers in self.subscribers.items():
            _, subscribed_event = key.split(':')
            if subscribed_event == event_type or subscribed_event == '*':
                for handler in handlers:
                    try:
                        handler(event)
                    except Exception as e:
                        logger.error(f"Error in event handler: {e}")
                        
        # Broadcast to WebSocket clients
        self._broadcast_to_websockets(event)
        
    def get_shared_state(self, key: str, default: Any = None) -> Any:
        """Access shared state"""
        return self.shared_state.get(key, default)
        
    def set_shared_state(self, key: str, value: Any):
        """Update shared state"""
        self.shared_state[key] = value
        self.publish('state_update', {'key': key, 'value': value})
        
    async def acquire_lock(self, resource: str) -> asyncio.Lock:
        """Acquire lock on resource"""
        if resource not in self.locks:
            self.locks[resource] = asyncio.Lock()
        return self.locks[resource]
        
    def _broadcast_to_websockets(self, event: Dict[str, Any]):
        """Broadcast event to WebSocket clients"""
        event_json = json.dumps(event)
        for client in self.websocket_clients:
            try:
                client.send(event_json)
            except Exception as e:
                logger.error(f"Error broadcasting to WebSocket client: {e}")
                
    def add_websocket_client(self, client):
        """Add WebSocket client"""
        self.websocket_clients.append(client)
        
    def remove_websocket_client(self, client):
        """Remove WebSocket client"""
        if client in self.websocket_clients:
            self.websocket_clients.remove(client)


class ComponentRegistry:
    """Registry of all system components"""
    
    def __init__(self):
        self.components: Dict[str, Any] = {}
        self.component_status: Dict[str, Dict[str, Any]] = {}
        
    def register(self, name: str, component: Any, metadata: Dict[str, Any] = None):
        """Register a component"""
        self.components[name] = component
        self.component_status[name] = {
            'name': name,
            'status': 'active',
            'registered_at': datetime.now().isoformat(),
            'metadata': metadata or {}
        }
        logger.info(f"Component registered: {name}")
        
    def get(self, name: str) -> Optional[Any]:
        """Get component by name"""
        return self.components.get(name)
        
    def get_all(self) -> Dict[str, Any]:
        """Get all components"""
        return self.components.copy()
        
    def get_status(self, name: str = None) -> Dict[str, Any]:
        """Get component status"""
        if name:
            return self.component_status.get(name, {})
        return self.component_status.copy()
        
    def update_status(self, name: str, status: str):
        """Update component status"""
        if name in self.component_status:
            self.component_status[name]['status'] = status
            self.component_status[name]['updated_at'] = datetime.now().isoformat()


class StateManager:
    """Manages state across components"""
    
    def __init__(self):
        self.global_state: Dict[str, Any] = {}
        self.component_states: Dict[str, Dict[str, Any]] = {}
        self.state_history: List[Dict[str, Any]] = []
        
    def get_global_state(self, key: str = None) -> Any:
        """Get global state"""
        if key:
            return self.global_state.get(key)
        return self.global_state.copy()
        
    def set_global_state(self, key: str, value: Any):
        """Set global state"""
        old_value = self.global_state.get(key)
        self.global_state[key] = value
        
        # Log state change
        self.state_history.append({
            'type': 'global',
            'key': key,
            'old_value': old_value,
            'new_value': value,
            'timestamp': datetime.now().isoformat()
        })
        
    def get_component_state(self, component: str, key: str = None) -> Any:
        """Get component state"""
        if component not in self.component_states:
            return None
        
        if key:
            return self.component_states[component].get(key)
        return self.component_states[component].copy()
        
    def set_component_state(self, component: str, key: str, value: Any):
        """Set component state"""
        if component not in self.component_states:
            self.component_states[component] = {}
            
        old_value = self.component_states[component].get(key)
        self.component_states[component][key] = value
        
        # Log state change
        self.state_history.append({
            'type': 'component',
            'component': component,
            'key': key,
            'old_value': old_value,
            'new_value': value,
            'timestamp': datetime.now().isoformat()
        })
        
    def get_state_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get state history"""
        return self.state_history[-limit:]


class WorkflowEngine:
    """Executes multi-component workflows"""
    
    def __init__(self, component_registry: ComponentRegistry, component_bus: ComponentBus):
        self.component_registry = component_registry
        self.component_bus = component_bus
        self.active_workflows: Dict[str, Dict[str, Any]] = {}
        
    async def execute_workflow(self, workflow_definition: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a workflow"""
        workflow_id = str(uuid.uuid4())
        workflow_name = workflow_definition.get('name', 'Unnamed Workflow')
        
        logger.info(f"Starting workflow: {workflow_name} (ID: {workflow_id})")
        
        workflow = {
            'id': workflow_id,
            'name': workflow_name,
            'definition': workflow_definition,
            'status': 'running',
            'started_at': datetime.now().isoformat(),
            'steps': workflow_definition.get('steps', []),
            'current_step': 0,
            'results': []
        }
        
        self.active_workflows[workflow_id] = workflow
        self.component_bus.publish('workflow_started', {'workflow_id': workflow_id, 'name': workflow_name})
        
        try:
            # Execute each step
            for i, step in enumerate(workflow['steps']):
                workflow['current_step'] = i
                self.component_bus.publish('workflow_step', {
                    'workflow_id': workflow_id,
                    'step': i,
                    'total_steps': len(workflow['steps'])
                })
                
                result = await self._execute_step(step)
                workflow['results'].append({
                    'step': i,
                    'component': step.get('component'),
                    'action': step.get('action'),
                    'result': result
                })
                
            workflow['status'] = 'completed'
            workflow['completed_at'] = datetime.now().isoformat()
            
            self.component_bus.publish('workflow_completed', {
                'workflow_id': workflow_id,
                'name': workflow_name,
                'results': workflow['results']
            })
            
            logger.info(f"Workflow completed: {workflow_name}")
            return workflow
            
        except Exception as e:
            logger.error(f"Workflow failed: {workflow_name} - {e}")
            workflow['status'] = 'failed'
            workflow['error'] = str(e)
            workflow['completed_at'] = datetime.now().isoformat()
            
            self.component_bus.publish('workflow_failed', {
                'workflow_id': workflow_id,
                'name': workflow_name,
                'error': str(e)
            })
            
            return workflow
            
    async def _execute_step(self, step: Dict[str, Any]) -> Any:
        """Execute a single workflow step"""
        component_name = step.get('component')
        action = step.get('action')
        params = step.get('params', {})
        
        component = self.component_registry.get(component_name)
        
        if not component:
            raise ValueError(f"Component not found: {component_name}")
            
        # Call component action
        if hasattr(component, action):
            method = getattr(component, action)
            if asyncio.iscoroutinefunction(method):
                result = await method(**params)
            else:
                result = method(**params)
            return result
        else:
            raise ValueError(f"Component {component_name} has no action {action}")


class RuntimeOrchestrator:
    """Central coordinator for all Murphy System components"""
    
    def __init__(self):
        self.ai_director = None  # Will be set later
        self.workflow_engine = None
        self.component_registry = ComponentRegistry()
        self.component_bus = ComponentBus()
        self.state_manager = StateManager()
        self.task_queue: List[Task] = []
        self.active_tasks: Dict[str, Task] = {}
        
        logger.info("Runtime Orchestrator initialized")
        
    def set_ai_director(self, ai_director):
        """Set AI Director"""
        self.ai_director = ai_director
        logger.info("AI Director set")
        
    def initialize(self):
        """Initialize the orchestrator"""
        # Initialize workflow engine
        self.workflow_engine = WorkflowEngine(
            self.component_registry,
            self.component_bus
        )
        
        logger.info("Runtime Orchestrator fully initialized")
        
    async def execute_workflow(self, workflow_definition: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a multi-step workflow across components"""
        return await self.workflow_engine.execute_workflow(workflow_definition)
        
    async def coordinate_components(self, task: Task) -> Any:
        """Coordinate multiple components to complete a task"""
        logger.info(f"Coordinating components for task: {task.name}")
        
        try:
            # Get component
            component = self.component_registry.get(task.component)
            
            if not component:
                raise ValueError(f"Component not found: {task.component}")
                
            # Execute action
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()
            
            if hasattr(component, task.action):
                method = getattr(component, task.action)
                
                if asyncio.iscoroutinefunction(method):
                    result = await method(**task.params)
                else:
                    result = method(**task.params)
                    
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.now()
                task.result = result
                
                self.component_bus.publish('task_completed', {
                    'task_id': task.id,
                    'task_name': task.name,
                    'result': result
                })
                
                return result
            else:
                raise ValueError(f"Component {task.component} has no action {task.action}")
                
        except Exception as e:
            logger.error(f"Task failed: {task.name} - {e}")
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = datetime.now()
            
            self.component_bus.publish('task_failed', {
                'task_id': task.id,
                'task_name': task.name,
                'error': str(e)
            })
            
            raise
            
    def add_task(self, task: Task):
        """Add task to queue"""
        self.task_queue.append(task)
        # Sort by priority
        self.task_queue.sort(key=lambda t: t.priority.value)
        logger.info(f"Task added to queue: {task.name} (priority: {task.priority.name})")
        
    async def process_task_queue(self):
        """Process tasks from queue"""
        while self.task_queue:
            task = self.task_queue.pop(0)
            self.active_tasks[task.id] = task
            
            try:
                await self.coordinate_components(task)
            except Exception as e:
                logger.error(f"Error processing task {task.id}: {e}")
                
            del self.active_tasks[task.id]
            
    async def optimize_execution(self):
        """AI Director optimizes task execution order"""
        if self.ai_director:
            # Let AI Director analyze and optimize
            await self.ai_director.optimize_task_queue(self.task_queue)
        else:
            logger.warning("AI Director not set, skipping optimization")
            
    def get_status(self) -> Dict[str, Any]:
        """Get orchestrator status"""
        return {
            'active_tasks': len(self.active_tasks),
            'queued_tasks': len(self.task_queue),
            'components': self.component_registry.get_status(),
            'workflows': {
                'active': len(self.workflow_engine.active_workflows) if self.workflow_engine else 0
            },
            'state': {
                'global_keys': len(self.state_manager.get_global_state()),
                'component_states': len(self.state_manager.component_states)
            }
        }


# Singleton instance
_orchestrator_instance: Optional[RuntimeOrchestrator] = None


def get_orchestrator() -> RuntimeOrchestrator:
    """Get the singleton orchestrator instance"""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = RuntimeOrchestrator()
    return _orchestrator_instance


def reset_orchestrator():
    """Reset the orchestrator instance"""
    global _orchestrator_instance
    _orchestrator_instance = None