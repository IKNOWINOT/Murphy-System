# Murphy System - Runtime Integration Guide

## Overview

This guide explains how to integrate the new Runtime Orchestrator into the existing Murphy System backend, transforming it from a collection of components into a fully autonomous runtime system.

---

## Architecture

### Current System
```
Frontend (HTML) -> Flask Backend -> Individual Components
```

### Target System
```
Frontend (HTML) -> Flask Backend -> Runtime Orchestrator -> Coordinated Components
```

### Key Components

#### 1. Runtime Orchestrator
**File:** `runtime_orchestrator.py`

**Purpose:** Central coordinator for all components

**Key Classes:**
- `RuntimeOrchestrator` - Main coordinator
- `ComponentBus` - Event-driven communication
- `ComponentRegistry` - Component registration
- `StateManager` - Cross-component state management
- `WorkflowEngine` - Multi-step workflow execution

#### 2. Base Component Interface
**File:** `base_component.py`

**Purpose:** Standardized interface for all components

**Key Classes:**
- `BaseComponent` - Abstract base class for new components
- `ComponentAdapter` - Adapter for existing components

#### 3. Integration Layer
**File:** `integrate_runtime_orchestrator.py`

**Purpose:** Connects runtime orchestrator with Flask backend

**Key Classes:**
- `RuntimeBackendIntegrator` - Integration manager

---

## Integration Steps

### Step 1: Import Runtime Components

Add to `murphy_backend_complete.py`:

```python
# Import runtime orchestrator components
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
from integrate_runtime_orchestrator import integrate_runtime_into_backend
```

### Step 2: Initialize Runtime Orchestrator

Add after Flask app creation in `murphy_backend_complete.py`:

```python
# Create Flask app
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize runtime orchestrator
runtime_integrator = integrate_runtime_into_backend(app)
orchestrator = runtime_integrator.orchestrator
```

### Step 3: Register WebSocket Events

Add WebSocket event handlers for runtime:

```python
@socketio.on('subscribe_runtime_events')
def handle_runtime_subscription(data):
    """Subscribe client to runtime events"""
    # Client will receive events from ComponentBus
    emit('runtime_subscribed', {'status': 'success'})
```

### Step 4: Test Integration

```bash
# Test runtime status
curl http://localhost:3002/api/runtime/status

# Test workflow execution
curl -X POST http://localhost:3002/api/runtime/workflows \
  -H "Content-Type: application/json" \
  -d '{
    "workflow": {
      "name": "Test Workflow",
      "steps": [
        {
          "component": "monitoring",
          "action": "health",
          "params": {}
        }
      ]
    }
  }'
```

---

## Creating Custom Workflows

### Workflow Definition Format

```yaml
name: "Workflow Name"
version: "1.0"
steps:
  - name: "Step 1"
    component: "component_name"
    action: "action_name"
    params:
      key: value
```

---

## Component Development

### Creating a New Component

```python
from base_component import BaseComponent
import logging

logger = logging.getLogger(__name__)

class MyCustomComponent(BaseComponent):
    """Custom component example"""
    
    def __init__(self, name: str):
        super().__init__(name)
        
    async def initialize(self) -> bool:
        """Initialize component"""
        self.initialized = True
        logger.info(f"Component initialized: {self.name}")
        return True
        
    async def execute(self, command: str, params: dict) -> any:
        """Execute command"""
        if command == 'my_command':
            result = self._do_my_work(**params)
            return result
        else:
            raise ValueError(f"Unknown command: {command}")
            
    async def health_check(self) -> dict:
        """Health check"""
        return {
            'healthy': self.initialized,
            'status': 'healthy' if self.initialized else 'unhealthy',
            'message': f"Component {self.name} is {'healthy' if self.initialized else 'unhealthy'}",
            'metrics': self.get_metrics()
        }
        
    def get_capabilities(self) -> list:
        """Get available commands"""
        return ['my_command']
        
    def _do_my_work(self, **params):
        """Actual work implementation"""
        return {'result': 'success'}
```

### Registering the Component

```python
# In your backend initialization
my_component = MyCustomComponent('my_component')

# Register with orchestrator
orchestrator.component_registry.register('my_component', my_component, {
    'description': 'My custom component',
    'version': '1.0'
})

# Initialize it
await my_component.initialize()
```

---

## Event System

### Publishing Events

```python
orchestrator.component_bus.publish('custom_event', {
    'data': 'value',
    'timestamp': datetime.now().isoformat()
})
```

### Subscribing to Events

```python
def event_handler(event):
    """Handle custom event"""
    print(f"Received event: {event['type']}")

orchestrator.component_bus.subscribe(
    component='my_component',
    event_type='custom_event',
    handler=event_handler
)
```

---

## Next Steps

1. Integrate runtime orchestrator into backend
2. Test workflow execution
3. Create custom components
4. Build autonomous execution loops
5. Deploy as production runtime system

---

## Documentation

See `MURPHY_SYSTEM_COMPLETION_PROMPT.md` for complete implementation roadmap.