# Murphy Production System — Master Prompt
## A Repeatable Specification for the Current State of the Main Branch Repository

---

# SECTION I: GUIDING PRINCIPLES

**Act as a team of software engineers trying to finish what exists for production.** For all choices, ask these questions and build plans from the answers:

## The Ten Validation Questions

### 1. Does the module do what it was designed to do?
- Verify the implementation matches the stated purpose
- Confirm all entry points produce expected behavior
- Validate edge cases are handled correctly

### 2. What exactly is the module supposed to do, knowing that this may change as design decisions evolve?
- Document the current scope clearly
- Identify areas subject to change
- Maintain flexibility for future requirements
- Update documentation as design evolves

### 3. What conditions are possible based on the module?
- Enumerate all input states and combinations
- Identify external dependencies and their states
- Consider concurrent access patterns
- Document error conditions and recovery paths

### 4. Does the test profile actually reflect the full range of capabilities and possible conditions?
- Ensure test coverage includes happy path and error paths
- Verify boundary conditions are tested
- Include integration tests for external dependencies
- Test concurrent and sequential access patterns

### 5. What is the expected result at all points of operation?
- Define success criteria for each operation
- Document intermediate states and transitions
- Specify timing and performance expectations
- Clarify side effects and their visibility

### 6. What is the actual result?
- Measure and compare against expected results
- Log discrepancies for analysis
- Track metrics over time for trend analysis
- Use observability tools to verify behavior

### 7. If there are still problems, how do we restart the process from the symptoms and work back through validation again?
- Establish debugging workflows from symptoms to root cause
- Use audit trails and logs to trace execution history
- Implement configuration backward logic for state reconstruction
- Document common failure modes and their resolutions

### 8. Has all ancillary code and documentation been updated to reflect the changes made, including as-builts?
- Update API documentation for all changes
- Revise README and setup instructions
- Generate as-built documentation
- Update configuration files and environment documentation

### 9. Has hardening been applied?
- Input validation and sanitization
- Rate limiting and resource quotas
- Circuit breakers for external dependencies
- Security scanning and vulnerability assessment
- Error handling that doesn't leak sensitive information

### 10. Has the module been commissioned again after those steps?
- Run full integration tests
- Verify deployment in staging environment
- Confirm monitoring and alerting are active
- Document the commissioning process and results

---

# SECTION II: SYSTEM ARCHITECTURE OVERVIEW

## 2.1 System Purpose

The Murphy System is a full-stack automation commons designed to provide intelligent community workflow with Member Validation (HITL) safety mechanisms. The system operates across 10 verticals: marketing, proposals, crm, monitoring, finance, security, content, comms, pipeline, and industrial.

## 2.2 Core Architectural Components

### MFGC (Multi-Factor Gate Controller)
A 7-phase control system:
1. **INTAKE**: Receive and validate input
2. **ANALYSIS**: Parse and understand context
3. **SCORING**: Calculate confidence and priority
4. **GATING**: Apply decision thresholds
5. **MURPHY_INDEX**: Determine automation risk level
6. **ENRICHMENT**: Add contextual metadata
7. **OUTPUT**: Generate final result

### MSS (Magnify-Simplify-Solidify)
Information transformation pipeline with optimal sequence "MMSMM":
1. **MAGNIFY**: Expand context
2. **MINIFY**: Compress to essentials
3. **SOLIDIFY**: Lock in decisions
4. **MAGNIFY**: Expand implications
5. **MINIFY**: Final compression

### HITL (Human-in-the-Loop)
Safety layer requiring human approval for high-risk operations:
- Real state machine that blocks until approved/rejected
- Mandatory rejection reasons (minimum 10 characters)
- LLM-generated follow-up questions
- Example upload support for clarification

---

# SECTION III: MODULE INSTANCE MANAGER SYSTEM

## 3.1 Overview

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

## 3.2 Source Files

### File: `src/module_instance_manager.py`
**Lines**: 1,132 (41,868 bytes)

**Key Classes**:

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
class ResourceProfile:
    """Resource requirements for a module instance."""
    cpu_cores: float = 1.0
    memory_mb: int = 512
    max_concurrent: int = 1
    timeout_seconds: int = 300
    priority: int = 5  # 1-10, higher is more important


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


@dataclass
class ConfigurationSnapshot:
    """Snapshot of instance configuration at a point in time."""
    snapshot_id: str
    instance_id: str
    timestamp: datetime
    config: Dict[str, Any]
    checksum: str


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
        """Spawn a new module instance with viability pre-flight checks."""
        
    def despawn_module(
        self,
        instance_id: str,
        reason: str = "manual",
        actor: str = "system",
        force: bool = False,
    ) -> bool:
        """Despawn a module instance with optional force cleanup."""
        
    def find_viable_instances(
        self,
        request: Dict[str, Any],
        required_capabilities: Optional[List[str]] = None,
        module_type: Optional[str] = None,
    ) -> List[ModuleInstance]:
        """Find instances viable for a request (murphy cursor actions)."""
        
    def get_configuration_history(self, instance_id: str) -> Dict[str, Any]:
        """Get full configuration backward logic for an instance."""
        
    def check_viability(
        self,
        module_type: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> ViabilityResult:
        """Check if a module type can be spawned."""
```

### File: `src/module_instance_api.py`
**Lines**: 548 (18,010 bytes)

## 3.3 API Endpoints

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

## 3.4 Request/Response Schemas

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

## 3.5 Resource Management

### Resource Limits
- **Max spawn depth**: 5 (anti-recursion)
- **Max instances per type**: 10
- **Circuit breaker**: Opens after 5 consecutive failures
- **Circuit recovery**: 30 seconds

### Circuit Breaker States
```
States: CLOSED, OPEN, HALF_OPEN

Transitions:
  CLOSED  -> OPEN   after 5 consecutive failures
  OPEN    -> HALF_OPEN after 30 seconds
  HALF_OPEN -> CLOSED on success
  HALF_OPEN -> OPEN on failure
```

## 3.6 Integration Patterns

### TriageRollcallAdapter Integration

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

### ModuleRegistry Integration

```python
from src.module_instance_manager import integrate_with_module_registry
from src.module_registry import module_registry

manager = ModuleInstanceManager()
integrate_with_module_registry(manager, module_registry)

# All discovered modules are now spawnable types
```

### MurphyProductionServer Integration

```python
# In murphy_production_server.py
from src.module_instance_api import register_module_instance_routes

app = FastAPI()
register_module_instance_routes(app)
```

---

# SECTION IV: DEMO CONFIGURATION ENDPOINTS

## 4.1 GET /api/demo/config

**Purpose**: Expose the complete configuration of the demo deliverable generator for debugging and transparency.

**Response Schema**:
```json
{
  "scenarios": {
    "count": 10,
    "templates": [
      {
        "id": "onboarding",
        "name": "Employee Onboarding",
        "keywords": ["employee", "onboarding", "new hire", "orientation", "welcome"],
        "has_template_structure": true
      }
    ]
  },
  "keywords": {
    "count": 97,
    "mapping": {
      "employee": "onboarding",
      "invoice": "invoice",
      "budget": "finance"
    }
  },
  "pipeline_steps": [
    {"step": 1, "name": "parse_query", "description": "Parse natural language query"},
    {"step": 2, "name": "detect_scenario", "description": "Match to scenario template"},
    {"step": 3, "name": "generate_content", "description": "Create deliverable content"},
    {"step": 4, "name": "format_output", "description": "Format final deliverable"}
  ],
  "mfgc_phases": [
    "INTAKE", "ANALYSIS", "SCORING", "GATING", 
    "MURPHY_INDEX", "ENRICHMENT", "OUTPUT"
  ]
}
```

## 4.2 POST /api/demo/inspect

**Purpose**: Trace how a query is processed through the demo pipeline for debugging.

**Request Schema**:
```json
{
  "query": "Create an employee onboarding checklist"
}
```

**Response Schema**:
```json
{
  "query": "Create an employee onboarding checklist",
  "trace": {
    "detected_scenario": "onboarding",
    "confidence": 0.85,
    "matched_keywords": ["employee", "onboarding"],
    "processing_steps": [
      {
        "step": "parse_query",
        "status": "complete",
        "duration_ms": 12
      },
      {
        "step": "detect_scenario",
        "status": "complete",
        "matched_template": "onboarding",
        "duration_ms": 8
      }
    ],
    "mfgc_trace": {
      "phase": "OUTPUT",
      "score": 0.85,
      "gates_passed": ["confidence_threshold", "keyword_match"]
    }
  },
  "would_generate": {
    "type": "checklist",
    "estimated_sections": 5,
    "template_used": "onboarding"
  }
}
```

---

# SECTION V: HITL SYSTEM ENHANCEMENTS

## 5.1 Enhanced HITLRejectionRequest Model

**Purpose**: Ensure rejections are meaningful and actionable with mandatory documentation.

**Schema**:
```python
class HITLRejectionRequest(BaseModel):
    """Enhanced rejection with mandatory reason and follow-up support."""
    reason: str = Field(
        ..., 
        min_length=10,
        description="Mandatory rejection reason (minimum 10 characters)"
    )
    follow_up_questions: List[str] = Field(
        default_factory=list,
        description="LLM-generated questions for clarification"
    )
    example_upload_url: Optional[str] = Field(
        None,
        description="URL to example of desired output"
    )
    example_description: Optional[str] = Field(
        None,
        description="Description of what the example demonstrates"
    )
    desired_outcome: Optional[str] = Field(
        None,
        description="Description of the desired outcome"
    )
```

## 5.2 Enhanced POST /api/hitl/{hitl_id}/reject

**Purpose**: Process rejection with intelligent follow-up generation.

**Enhanced Response Schema**:
```json
{
  "status": "rejected",
  "hitl_id": "hitl-abc12345",
  "rejected_at": "2024-01-15T10:30:00Z",
  "rejection": {
    "reason": "The generated proposal lacks specific pricing details for enterprise tier",
    "follow_up_questions": [
      "What pricing structure would you prefer for the enterprise tier?",
      "Should the proposal include volume discounts?",
      "Do you need custom pricing for different regions?"
    ],
    "ambiguity_flags": [
      {
        "field": "pricing",
        "issue": "unclear_requirements",
        "suggestion": "Provide pricing template or example"
      }
    ],
    "example_request": {
      "url_provided": false,
      "description_provided": false,
      "suggested_action": "Upload an example proposal with desired pricing format"
    }
  },
  "llm_enhanced": true,
  "processing_metadata": {
    "questions_generated": 3,
    "ambiguities_detected": 1
  }
}
```

## 5.3 GET /api/hitl/{hitl_id}/inspect

**Purpose**: Provide detailed inspection of a HITL deliverable for debugging and transparency.

**Response Schema**:
```json
{
  "hitl_id": "hitl-abc12345",
  "state": "pending_approval",
  "deliverable": {
    "type": "proposal",
    "created_at": "2024-01-15T10:00:00Z",
    "content_preview": "...",
    "changes_made": [
      {
        "section": "pricing",
        "change": "added_enterprise_tier",
        "timestamp": "2024-01-15T10:05:00Z"
      }
    ],
    "effect": {
      "improved_confidence": 0.15,
      "gates_passed": 3,
      "mfgc_phase": "OUTPUT"
    }
  },
  "context": {
    "original_request": "Create a sales proposal for enterprise client",
    "scenario_detected": "proposal",
    "mfgc_trace": {...}
  }
}
```

---

# SECTION VI: INFRASTRUCTURE ENDPOINTS

## 6.1 GET /api/infrastructure/status

**Purpose**: Compare current server configuration with hetzner_load.sh infrastructure requirements.

**Response Schema**:
```json
{
  "server_status": {
    "host": "murphy-production.local",
    "uptime_seconds": 864000,
    "python_version": "3.11.0"
  },
  "services": {
    "postgresql": {"status": "running", "version": "15.0"},
    "redis": {"status": "running", "version": "7.0"},
    "nginx": {"status": "running", "version": "1.24"},
    "supervisor": {"status": "running", "version": "4.2"}
  },
  "missing_from_hetzner": [
    {
      "component": "docker",
      "required": true,
      "status": "not_installed"
    }
  ],
  "environment_variables": {
    "DATABASE_URL": "configured",
    "REDIS_URL": "configured",
    "SECRET_KEY": "configured"
  }
}
```

## 6.2 POST /api/infrastructure/compare

**Purpose**: Detailed comparison between production and hetzner_load.sh configuration.

**Request Schema**:
```json
{
  "compare_file": "scripts/hetzner_load.sh",
  "check_packages": true,
  "check_services": true
}
```

---

# SECTION VII: MATRIX SERVER INTEGRATION

## 7.1 Matrix Configuration

**Purpose**: Enable real-time Matrix messaging for HITL notifications.

**Configuration Schema**:
```python
class MatrixConfig(BaseModel):
    homeserver_url: str = "https://matrix.org"
    user_id: str
    access_token: str
    default_room_id: Optional[str] = None
    notification_templates: Dict[str, str] = {
        "hitl_pending": "🚨 HITL approval required: {hitl_id}",
        "hitl_approved": "✅ HITL approved: {hitl_id}",
        "hitl_rejected": "❌ HITL rejected: {hitl_id}"
    }
```

## 7.2 Matrix Notification Endpoints

**POST /api/matrix/notify**:
```json
{
  "room_id": "!room:matrix.org",
  "event_type": "hitl_pending",
  "data": {
    "hitl_id": "hitl-abc12345",
    "deliverable_type": "proposal",
    "requestor": "user_123"
  }
}
```

---

# SECTION VIII: UI SPECIFICATIONS WITH BACKEND WIRING

## 8.1 Module Instance Dashboard UI

### HTML Structure
```html
<!-- module_instances.html -->
<div id="module-instance-dashboard">
  <!-- Status Panel -->
  <div class="status-panel">
    <div class="metric-card" id="active-instances">
      <span class="metric-value">0</span>
      <span class="metric-label">Active Instances</span>
    </div>
    <div class="metric-card" id="resource-usage">
      <span class="metric-value">0%</span>
      <span class="metric-label">Resource Usage</span>
    </div>
    <div class="metric-card" id="circuit-status">
      <span class="metric-value">CLOSED</span>
      <span class="metric-label">Circuit Breaker</span>
    </div>
  </div>
  
  <!-- Instance List -->
  <div class="instance-list">
    <table id="instances-table">
      <thead>
        <tr>
          <th>Instance ID</th>
          <th>Module Type</th>
          <th>State</th>
          <th>Capabilities</th>
          <th>Spawned At</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody id="instances-body"></tbody>
    </table>
  </div>
  
  <!-- Spawn Form -->
  <div class="spawn-form">
    <select id="module-type-select"></select>
    <textarea id="config-input" placeholder="JSON configuration"></textarea>
    <button id="spawn-btn">Spawn Instance</button>
  </div>
</div>
```

### JavaScript Wiring
```javascript
// module_instances.js

const API_BASE = '/module-instances';

// Fetch all instances
async function loadInstances() {
  const response = await fetch(`${API_BASE}/`);
  const data = await response.json();
  renderInstances(data.instances);
  updateMetrics(data);
}

// Spawn new instance
async function spawnInstance() {
  const moduleType = document.getElementById('module-type-select').value;
  const configText = document.getElementById('config-input').value;
  const config = configText ? JSON.parse(configText) : {};
  
  const response = await fetch(`${API_BASE}/spawn`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      module_type: moduleType,
      config: config,
      actor: getCurrentUser()
    })
  });
  
  const result = await response.json();
  if (result.decision === 'approved') {
    showNotification(`Instance ${result.instance_id} spawned`);
    loadInstances();
  } else {
    showError(`Spawn denied: ${result.decision}`);
  }
}

// Despawn instance
async function despawnInstance(instanceId, force = false) {
  const response = await fetch(`${API_BASE}/${instanceId}/despawn`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      reason: 'manual',
      actor: getCurrentUser(),
      force: force
    })
  });
  
  const result = await response.json();
  if (result.success) {
    showNotification(`Instance ${instanceId} despawned`);
    loadInstances();
  }
}

// Find viable instances
async function findViable(capabilities) {
  const response = await fetch(`${API_BASE}/find-viable`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      request: {},
      required_capabilities: capabilities
    })
  });
  
  return await response.json();
}

// View audit trail
async function viewAuditTrail(instanceId) {
  const response = await fetch(
    `${API_BASE}/audit/trail?instance_id=${instanceId}&limit=100`
  );
  const data = await response.json();
  showAuditModal(data.entries);
}

// View config history
async function viewConfigHistory(instanceId) {
  const response = await fetch(`${API_BASE}/${instanceId}/config-history`);
  const data = await response.json();
  showConfigHistoryModal(data);
}

// WebSocket for real-time updates
function connectWebSocket() {
  const ws = new WebSocket(`ws://${location.host}/ws/module-instances`);
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    handleInstanceEvent(data);
  };
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  loadInstances();
  connectWebSocket();
  setInterval(loadInstances, 30000); // Refresh every 30s
});
```

## 8.2 HITL Dashboard UI

### HTML Structure
```html
<!-- hitl_dashboard.html -->
<div id="hitl-dashboard">
  <!-- Pending Approvals -->
  <div class="pending-approvals">
    <h2>Pending Approvals</h2>
    <div id="pending-list"></div>
  </div>
  
  <!-- Approval Modal -->
  <div id="approval-modal" class="modal">
    <div class="modal-content">
      <h3>Review Deliverable</h3>
      <div id="deliverable-preview"></div>
      
      <div class="action-buttons">
        <button id="approve-btn" class="btn-success">Approve</button>
        <button id="reject-btn" class="btn-danger">Reject</button>
      </div>
      
      <!-- Rejection Form -->
      <div id="rejection-form" class="hidden">
        <textarea id="rejection-reason" 
                  placeholder="Enter rejection reason (min 10 characters)"
                  minlength="10"></textarea>
        <input type="url" id="example-url" placeholder="Example URL (optional)">
        <textarea id="example-description" 
                  placeholder="Example description (optional)"></textarea>
        <div id="follow-up-questions"></div>
        <button id="submit-rejection">Submit Rejection</button>
      </div>
    </div>
  </div>
</div>
```

### JavaScript Wiring
```javascript
// hitl_dashboard.js

const API_BASE = '/api/hitl';

// Load pending HITL items
async function loadPendingHITL() {
  const response = await fetch(`${API_BASE}/pending`);
  const data = await response.json();
  renderPendingList(data.items);
}

// Inspect HITL item
async function inspectHITL(hitlId) {
  const response = await fetch(`${API_BASE}/${hitlId}/inspect`);
  const data = await response.json();
  showInspectionModal(data);
}

// Approve HITL
async function approveHITL(hitlId) {
  const response = await fetch(`${API_BASE}/${hitlId}/approve`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ actor: getCurrentUser() })
  });
  
  const result = await response.json();
  showNotification(`HITL ${hitlId} approved`);
  loadPendingHITL();
}

// Reject HITL with enhanced feedback
async function rejectHITL(hitlId) {
  const reason = document.getElementById('rejection-reason').value;
  const exampleUrl = document.getElementById('example-url').value;
  const exampleDesc = document.getElementById('example-description').value;
  
  if (reason.length < 10) {
    showError('Rejection reason must be at least 10 characters');
    return;
  }
  
  const response = await fetch(`${API_BASE}/${hitlId}/reject`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      reason: reason,
      example_upload_url: exampleUrl || null,
      example_description: exampleDesc || null
    })
  });
  
  const result = await response.json();
  
  // Display follow-up questions if generated
  if (result.rejection.follow_up_questions.length > 0) {
    showFollowUpQuestions(result.rejection.follow_up_questions);
  }
  
  showNotification(`HITL ${hitlId} rejected`);
  loadPendingHITL();
}

// Matrix notification
async function sendMatrixNotification(hitlId, eventType) {
  await fetch('/api/matrix/notify', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      room_id: getMatrixRoom(),
      event_type: eventType,
      data: { hitl_id: hitlId }
    })
  });
}
```

## 8.3 Demo Configuration UI

### HTML Structure
```html
<!-- demo_config.html -->
<div id="demo-config-panel">
  <div class="config-section">
    <h3>Scenarios</h3>
    <div id="scenario-list"></div>
  </div>
  
  <div class="config-section">
    <h3>Keywords</h3>
    <div id="keyword-cloud"></div>
  </div>
  
  <div class="inspect-section">
    <h3>Query Inspector</h3>
    <input type="text" id="query-input" placeholder="Enter query to inspect">
    <button id="inspect-btn">Inspect</button>
    <div id="inspect-results"></div>
  </div>
</div>
```

### JavaScript Wiring
```javascript
// demo_config.js

// Load configuration
async function loadDemoConfig() {
  const response = await fetch('/api/demo/config');
  const config = await response.json();
  renderScenarios(config.scenarios);
  renderKeywords(config.keywords);
}

// Inspect query
async function inspectQuery(query) {
  const response = await fetch('/api/demo/inspect', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ query })
  });
  
  const result = await response.json();
  renderInspectionResult(result);
}
```

---

# SECTION IX: IMPLEMENTATION CHECKLISTS

## 9.1 Module Instance Manager

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

## 9.2 HITL Enhancements

- [ ] Implement enhanced rejection model
- [ ] Add LLM-generated follow-up questions
- [ ] Support example uploads
- [ ] Create deliverable inspection endpoint

## 9.3 Infrastructure

- [ ] Compare with hetzner_load.sh
- [ ] Add infrastructure status endpoints
- [ ] Configure Matrix server integration

## 9.4 UI Components

- [ ] Module Instance Dashboard
- [ ] HITL Dashboard with enhanced rejection
- [ ] Demo Configuration Panel
- [ ] Matrix notification integration

---

# SECTION X: FILES CREATED IN SESSION

| File | Lines | Size | Purpose |
|------|-------|------|---------|
| `src/module_instance_manager.py` | 1,132 | 41,868 bytes | Core manager with spawn/despawn, viability checking, audit trails |
| `src/module_instance_api.py` | 548 | 18,010 bytes | FastAPI REST endpoints for all operations |
| `MODULE_INSTANCE_MANAGER_SPEC.md` | 494 | 13,352 bytes | Complete specification with examples |
| `MURPHY_PRODUCTION_COMPLETE_SPEC.md` | 778 | 23,616 bytes | Comprehensive integrated specification |
| `MASTER_PROMPT.md` | - | - | This master prompt document |

---

# SECTION XI: KEY FEATURES IMPLEMENTED

## 11.1 Unique Instance IDs

Every spawned module gets a unique ID like `inst-llm-control-0001-a1b2c3`:
- Enables tracking through the entire lifecycle
- Supports configuration backward logic for debugging
- Parent-child relationships for hierarchical tracking

## 11.2 Spawn/Despawn Lifecycle

- `spawn_module()` with viability pre-flight checks
- `despawn_module()` with force option for cleanup
- Circuit breaker protection against cascade failures
- Depth limits for anti-recursion protection

## 11.3 Configuration Backward Logic (Audit Trail)

Every operation logged with:
- Timestamp
- Actor (user or system)
- Correlation ID
- Parent instance ID

`get_configuration_history()` traces full instance lineage.

## 11.4 Viability Checking ("Murphy Cursor Actions")

`find_viable_instances()` selects modules based on:
- Capabilities matching
- Resource availability
- Dependency status
- Blacklist status

Returns sorted list of best candidates.

## 11.5 Resource Management

- CPU and memory budgets
- Max spawn depth (anti-recursion)
- Max instances per type
- Circuit breaker with auto-recovery

---

# SECTION XII: COPILOT INSTRUCTIONS

When implementing this specification:

1. **Follow the Ten Validation Questions** for every module
2. **Maintain all code examples and JSON schemas exactly as specified**
3. **Preserve the hierarchical instance tracking** for configuration backward logic
4. **Implement viability checking** before spawning any module instance
5. **Ensure all audit trails** capture timestamp, actor, and correlation ID
6. **Apply hardening** including input validation, rate limiting, and circuit breakers
7. **Update documentation** after all changes including as-builts
8. **Commission modules** after implementation following the validation process

---

# SECTION XIII: REPOSITORY CONTEXT

## Current Branch: main

## Key Directories
- `src/` - Core source code
- `bots/` - Bot implementations
- `config/` - Configuration files
- `tests/` - Test suites
- `docs/` - Documentation

## Key Files
- `murphy_production_server.py` - Main production server
- `src/module_registry.yaml` - Module definitions
- `src/demo_deliverable_generator.py` - Demo generation logic
- `src/triage_rollcall_adapter.py` - Capability registry
- `src/durable_swarm_orchestrator.py` - Swarm spawning patterns

## Integration Points
- ModuleRegistry → ModuleInstanceManager
- TriageRollcallAdapter → spawn_from_rollcall()
- MurphyProductionServer → register_module_instance_routes()

---

**END OF MASTER PROMPT**

*This document is designed to be repeatable for the current state of the main branch repository. Use it as the authoritative specification for continuing development on the Murphy Production System.*