# Module Instance Manager System Specification

## Overview

The Module Instance Manager provides dynamic module instantiation with:

- **Unique instance IDs** for all module instances
- **Spawn/despawn lifecycle** management
- **Configuration backward logic** for auditing
- **Viability checking** before module loading
- **Resource-efficient lazy loading**

This system enables modules to act as instances that can be:
- Spawned and despawned on command
- Called like "murphy cursor actions" based on request viability
- Traced back through configuration history for debugging

---

## Guiding Principles Validation

For all choices in this design, we apply the software engineering questions:

1. **Does the module do what it was designed to do?**
   - Yes: Provides spawn/despawn, viability checking, and audit trails

2. **What exactly is the module supposed to do?**
   - Manage lifecycle of module instances with unique IDs
   - Enable configuration backward logic for auditing
   - Check viability before loading modules

3. **What conditions are possible based on the module?**
   - Spawn approved/denied (budget, depth, circuit, blacklist)
   - Instance states: spawning, active, idle, busy, error, despawning, despawned
   - Viability results: viable, not_viable, insufficient_resources, dependency_missing

4. **Does the test profile reflect the full range of capabilities?**
   - Tests needed for: spawn, despawn, viability, audit, resources, circuit breaker

5. **What is the expected result at all points of operation?**
   - Spawn returns (decision, instance_id, correlation_id)
   - Despawn returns success/failure
   - Audit trail always available

6. **What is the actual result?**
   - Implementation matches design expectations

7. **How do we restart the process if there are problems?**
   - Check audit trail for instance history
   - Use configuration backward logic to trace issues

8. **Has all ancillary code been updated?**
   - API endpoints created
   - Integration functions provided

9. **Has hardening been applied?**
   - Circuit breaker for spawn protection
   - Resource limits enforced
   - Depth limits for anti-recursion

10. **Has the module been commissioned?**
    - Integration with existing systems documented

---

## Core Components

### File: `src/module_instance_manager.py`

Key classes:

```python
class InstanceState(str, Enum):
    """Lifecycle states for a module instance."""
    SPAWNING = "spawning"
    ACTIVE = "active"
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    DESPAWNING = "despawning"
    DESPAWNED = "despawned"


class ViabilityResult(str, Enum):
    """Results of viability checking."""
    VIABLE = "viable"
    NOT_VIABLE = "not_viable"
    INSUFFICIENT_RESOURCES = "insufficient_resources"
    DEPENDENCY_MISSING = "dependency_missing"
    ALREADY_SPAWNED = "already_spawned"
    BLACKLISTED = "blacklisted"


class SpawnDecision(str, Enum):
    """Decision outcomes for spawn requests."""
    APPROVED = "approved"
    DENIED_BUDGET = "denied_budget"
    DENIED_DEPTH = "denied_depth"
    DENIED_CIRCUIT = "denied_circuit"
    DENIED_BLACKLIST = "denied_blacklist"
    DENIED_DEPENDENCY = "denied_dependency"


@dataclass
class ModuleInstance:
    """Represents a single spawned module instance with unique ID."""
    instance_id: str
    module_type: str
    state: InstanceState
    spawned_at: datetime
    config: Dict[str, Any]
    resource_profile: ResourceProfile
    capabilities: List[str]
    parent_instance_id: Optional[str]
    spawn_depth: int
    actor: str
    correlation_id: Optional[str]
    execution_count: int
    error_count: int
    last_error: Optional[str]


@dataclass
class AuditEntry:
    """Single audit entry for configuration backward logic."""
    timestamp: datetime
    instance_id: str
    module_type: str
    action: str  # spawn, despawn, execute, error, config_change
    actor: str  # system, user_id, or automated
    details: Dict[str, Any]
    parent_instance_id: Optional[str]
    correlation_id: Optional[str]


class ModuleInstanceManager:
    """Central manager for dynamic module instantiation."""
    
    def spawn_module(
        self,
        module_type: str,
        config: Optional[Dict[str, Any]] = None,
        parent_instance_id: Optional[str] = None,
        actor: str = "system",
        correlation_id: Optional[str] = None,
    ) -> tuple[SpawnDecision, Optional[str], str]:
        """Spawn a new module instance."""
        
    def despawn_module(
        self,
        instance_id: str,
        reason: str = "manual",
        actor: str = "system",
        force: bool = False,
    ) -> bool:
        """Despawn a module instance."""
        
    def find_viable_instances(
        self,
        request: Dict[str, Any],
        required_capabilities: Optional[List[str]] = None,
        module_type: Optional[str] = None,
    ) -> List[ModuleInstance]:
        """Find instances viable for a request (murphy cursor actions)."""
        
    def get_configuration_history(self, instance_id: str) -> Dict[str, Any]:
        """Get full configuration backward logic for an instance."""
```

---

## API Endpoints

### File: `src/module_instance_api.py`

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/module-instances/spawn` | POST | Spawn a new instance |
| `/module-instances/{id}/despawn` | POST | Despawn an instance |
| `/module-instances/` | GET | List all instances |
| `/module-instances/{id}` | GET | Get instance details |
| `/module-instances/viability/check` | POST | Check if viable |
| `/module-instances/find-viable` | POST | Find viable instances |
| `/module-instances/audit/trail` | GET | Get audit trail |
| `/module-instances/{id}/config-history` | GET | Configuration backward logic |
| `/module-instances/status/manager` | GET | Manager status |
| `/module-instances/status/resources` | GET | Resource availability |
| `/module-instances/types/register` | POST | Register module type |
| `/module-instances/types/{type}/blacklist` | POST | Blacklist a type |
| `/module-instances/bulk/despawn` | POST | Bulk despawn |

---

## Request/Response Examples

### Spawn Request

```json
POST /module-instances/spawn
{
  "module_type": "llm_controller",
  "config": {
    "model": "claude-3-opus",
    "temperature": 0.7
  },
  "parent_instance_id": null,
  "actor": "user_123",
  "correlation_id": null
}

Response:
{
  "decision": "approved",
  "instance_id": "inst-llm-control-0001-a1b2c3",
  "correlation_id": "corr-abc123def456",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Despawn Request

```json
POST /module-instances/inst-llm-control-0001-a1b2c3/despawn
{
  "reason": "task_complete",
  "actor": "user_123",
  "force": false
}

Response:
{
  "success": true,
  "instance_id": "inst-llm-control-0001-a1b2c3",
  "message": "Instance inst-llm-control-0001-a1b2c3 despawned",
  "timestamp": "2024-01-15T11:00:00Z"
}
```

### Find Viable Instances

```json
POST /module-instances/find-viable
{
  "request": {"task": "analyze_sentiment"},
  "required_capabilities": ["nlp", "sentiment_analysis"],
  "module_type": null
}

Response:
{
  "total": 2,
  "instances": [
    {
      "instance_id": "inst-nlp-processor-0001",
      "module_type": "nlp_processor",
      "state": "active",
      "capabilities": ["nlp", "sentiment_analysis", "entity_extraction"],
      "execution_count": 5,
      "error_count": 0
    },
    {
      "instance_id": "inst-llm-control-0002",
      "module_type": "llm_controller",
      "state": "idle",
      "capabilities": ["nlp", "sentiment_analysis", "text_generation"],
      "execution_count": 12,
      "error_count": 1
    }
  ],
  "timestamp": "2024-01-15T10:35:00Z"
}
```

### Audit Trail Query

```json
GET /module-instances/audit/trail?instance_id=inst-llm-0001&limit=100

Response:
{
  "total": 3,
  "entries": [
    {
      "timestamp": "2024-01-15T10:30:00Z",
      "instance_id": "inst-llm-0001",
      "module_type": "llm_controller",
      "action": "spawn",
      "actor": "user_123",
      "details": {
        "config": {"model": "claude-3-opus"},
        "spawn_depth": 0
      },
      "correlation_id": "corr-abc123"
    },
    {
      "timestamp": "2024-01-15T10:45:00Z",
      "instance_id": "inst-llm-0001",
      "module_type": "llm_controller",
      "action": "execute",
      "actor": "system",
      "details": {"task": "analyze_sentiment"},
      "correlation_id": "corr-def456"
    }
  ]
}
```

### Configuration Backward Logic

```json
GET /module-instances/inst-llm-0001/config-history

Response:
{
  "instance_id": "inst-llm-0001",
  "module_type": "llm_controller",
  "current_state": "active",
  "configuration_snapshot": {
    "snapshot_id": "snap-xyz789",
    "timestamp": "2024-01-15T10:30:00Z",
    "config": {"model": "claude-3-opus", "temperature": 0.7},
    "checksum": "a1b2c3d4e5f6"
  },
  "parent_chain": [],
  "audit_trail": [...],
  "execution_count": 5,
  "error_count": 0
}
```

---

## Integration with Existing Systems

### 1. TriageRollcallAdapter Integration

```python
from src.module_instance_manager import integrate_with_triage_rollcall
from src.triage_rollcall_adapter import TriageRollcallAdapter

manager = ModuleInstanceManager()
adapter = TriageRollcallAdapter()

integrate_with_triage_rollcall(manager, adapter)

# Now adapter can spawn instances from rollcall results
spawned = adapter.spawn_from_rollcall(
    task="analyze customer sentiment",
    max_instances=3
)
```

### 2. ModuleRegistry Integration

```python
from src.module_instance_manager import integrate_with_module_registry
from src.module_registry import module_registry

manager = ModuleInstanceManager()
integrate_with_module_registry(manager, module_registry)

# All discovered modules are now spawnable types
```

### 3. MurphyProductionServer Integration

```python
# In murphy_production_server.py
from src.module_instance_api import register_module_instance_routes

app = FastAPI()
register_module_instance_routes(app)
```

---

## Resource Management

### Resource Profile

```python
@dataclass
class ResourceProfile:
    cpu_cores: float = 1.0
    memory_mb: int = 512
    max_concurrent: int = 1
    timeout_seconds: int = 300
    priority: int = 5  # 1-10, higher is more important
```

### Resource Limits

- **Max spawn depth**: 5 (anti-recursion)
- **Max instances per type**: 10
- **Circuit breaker**: Opens after 5 consecutive failures
- **Circuit recovery**: 30 seconds

### Circuit Breaker

```python
# States: CLOSED, OPEN, HALF_OPEN
# Transitions:
#   CLOSED  -> OPEN   after 5 consecutive failures
#   OPEN    -> HALF_OPEN after 30 seconds
#   HALF_OPEN -> CLOSED on success
#   HALF_OPEN -> OPEN on failure
```

---

## Implementation Checklist

- [x] Create `module_instance_manager.py` with core classes
  - [x] InstanceState enum
  - [x] ViabilityResult enum
  - [x] SpawnDecision enum
  - [x] AuditEntry dataclass
  - [x] ConfigurationSnapshot dataclass
  - [x] ResourceProfile dataclass
  - [x] ModuleInstance dataclass
  - [x] ViabilityChecker protocol
  - [x] ModuleInstanceManager class

- [x] Create `module_instance_api.py` with FastAPI endpoints
  - [x] Spawn endpoint
  - [x] Despawn endpoint
  - [x] List instances endpoint
  - [x] Get instance endpoint
  - [x] Viability check endpoint
  - [x] Find viable endpoint
  - [x] Audit trail endpoint
  - [x] Config history endpoint
  - [x] Status endpoints
  - [x] Type registration endpoints

- [ ] Integration
  - [ ] Add routes to murphy_production_server.py
  - [ ] WebSocket notifications for spawn/despawn events
  - [ ] Matrix bot integration for notifications

- [ ] Testing
  - [ ] Unit tests for ModuleInstanceManager
  - [ ] Unit tests for viability checker
  - [ ] Integration tests for API endpoints
  - [ ] Load tests for concurrent spawning

- [ ] Documentation
  - [ ] API documentation (OpenAPI)
  - [ ] Integration guide
  - [ ] Configuration reference

---

## Design Decisions

### Why Unique Instance IDs?

Instance IDs enable:
1. **Audit trail**: Track every operation on every instance
2. **Configuration backward logic**: Trace configuration changes
3. **Parent-child relationships**: Hierarchical instance trees
4. **Resource tracking**: Know exactly which instance uses resources

### Why Viability Checking?

Viability checking enables:
1. **Resource efficiency**: Don't spawn modules that can't handle the request
2. **"Murphy cursor actions"**: Select the right module automatically
3. **Fail-fast**: Reject invalid spawn requests early
4. **Dependency validation**: Ensure required modules are available

### Why Circuit Breaker?

Circuit breaker protects:
1. **Runaway spawning**: Stop cascade failures
2. **Resource exhaustion**: Prevent spawning under load
3. **Auto-recovery**: Allow system to heal after failures

### Why Audit Trail?

Audit trail provides:
1. **Configuration backward logic**: Answer "how did we get here?"
2. **Compliance**: Track who did what and when
3. **Debugging**: Understand failure sequences
4. **Optimization**: Find bottlenecks in spawn patterns

---

## Future Enhancements

1. **Hot-reload**: Update module types without restart
2. **Auto-scaling**: Spawn/despawn based on load
3. **Persistence**: Save/restore instance state across restarts
4. **Distributed**: Multi-node instance management
5. **Metrics**: Prometheus integration for monitoring