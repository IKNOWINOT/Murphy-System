# Murphy Production System — Complete Session Specification

## Preamble: Guiding Principles for Production Engineering

**Act as a team of software engineers trying to finish what exists for production.** For all choices, ask these questions and build plans from the answers:

### The Ten Validation Questions

1. **Does the module do what it was designed to do?**
   - Verify the implementation matches the stated purpose
   - Confirm all entry points produce expected behavior
   - Validate edge cases are handled correctly

2. **What exactly is the module supposed to do, knowing that this may change as design decisions evolve?**
   - Document the current scope clearly
   - Identify areas subject to change
   - Maintain flexibility for future requirements
   - Update documentation as design evolves

3. **What conditions are possible based on the module?**
   - Enumerate all input states and combinations
   - Identify external dependencies and their states
   - Consider concurrent access patterns
   - Document error conditions and recovery paths

4. **Does the test profile actually reflect the full range of capabilities and possible conditions?**
   - Ensure test coverage includes happy path and error paths
   - Verify boundary conditions are tested
   - Include integration tests for external dependencies
   - Test concurrent and sequential access patterns

5. **What is the expected result at all points of operation?**
   - Define success criteria for each operation
   - Document intermediate states and transitions
   - Specify timing and performance expectations
   - Clarify side effects and their visibility

6. **What is the actual result?**
   - Measure and compare against expected results
   - Log discrepancies for analysis
   - Track metrics over time for trend analysis
   - Use observability tools to verify behavior

7. **If there are still problems, how do we restart the process from the symptoms and work back through validation again?**
   - Establish debugging workflows from symptoms to root cause
   - Use audit trails and logs to trace execution history
   - Implement configuration backward logic for state reconstruction
   - Document common failure modes and their resolutions

8. **Has all ancillary code and documentation been updated to reflect the changes made, including as-builts?**
   - Update API documentation for all changes
   - Revise README and setup instructions
   - Generate as-built documentation
   - Update configuration files and environment documentation

9. **Has hardening been applied?**
   - Input validation and sanitization
   - Rate limiting and resource quotas
   - Circuit breakers for external dependencies
   - Security scanning and vulnerability assessment
   - Error handling that doesn't leak sensitive information

10. **Has the module been commissioned again after those steps?**
    - Run full integration tests
    - Verify deployment in staging environment
    - Confirm monitoring and alerting are active
    - Document the commissioning process and results

---

## Part 0: Module Instance Manager System

### 0.1 Overview

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

### 0.2 Core Components

**File: `src/module_instance_manager.py`** (1,132 lines)

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

### 0.3 API Endpoints

**File: `src/module_instance_api.py`** (548 lines)

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

### 0.4 Request/Response Examples

#### Spawn Request

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

#### Despawn Request

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

#### Find Viable Instances

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
    }
  ],
  "timestamp": "2024-01-15T10:35:00Z"
}
```

#### Audit Trail Query

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
    }
  ]
}
```

### 0.5 Resource Management

```python
@dataclass
class ResourceProfile:
    cpu_cores: float = 1.0
    memory_mb: int = 512
    max_concurrent: int = 1
    timeout_seconds: int = 300
    priority: int = 5  # 1-10, higher is more important
```

Resource limits prevent over-provisioning:
- Max spawn depth (default: 5)
- Max instances per type (default: 10)
- CPU and memory budgets
- Circuit breaker with auto-recovery (30 seconds)

---

## Part I: Project Context and Initial State

### 1.1 System Overview

The Murphy System is a full-stack automation platform designed to provide intelligent workflow automation with Human-in-the-Loop (HITL) safety mechanisms. The system operates across 10 verticals: marketing, proposals, crm, monitoring, finance, security, content, comms, pipeline, and industrial.

### 1.2 Core Architectural Components

The system is built on several foundational subsystems:

**MFGC (Multi-Factor Gate Controller)** — A 7-phase control system:
- INTAKE: Receive and validate input
- ANALYSIS: Parse and understand context
- SCORING: Calculate confidence and priority
- GATING: Apply decision thresholds
- MURPHY_INDEX: Determine automation risk level
- ENRICHMENT: Add contextual metadata
- OUTPUT: Generate final result

**MSS (Magnify-Simplify-Solidify)** — Information transformation pipeline with optimal sequence "MMSMM":
- MAGNIFY: Expand context
- MINIFY: Compress to essentials
- SOLIDIFY: Lock in decisions
- MAGNIFY: Expand implications
- MINIFY: Final compression

**HITL (Human-in-the-Loop)** — Safety layer requiring human approval for high-risk operations:
- Real state machine that blocks until approved/rejected
- Mandatory rejection reasons (minimum 10 characters)
- LLM-generated follow-up questions
- Example upload support for clarification

---

## Part II: Initial Request Specification

### 2.1 Primary Objectives

The user requested to:

1. **Integrate forge demo functionality into production server** — The demo deliverable generator needed to be properly integrated with configuration visibility
2. **Enhance HITL system** — Add mandatory rejection reasons, LLM follow-up questions, and example uploads
3. **Improve deliverable inspection** — Show what the deliverable is, changes made, and effect of changes
4. **Compare hetzner_load.sh with production server** — Identify missing infrastructure components
5. **Push to GitHub** — Version control the enhanced system
6. **Add Matrix server integration** — Real-time messaging for HITL notifications

### 2.2 Initial Analysis Tasks

Before writing code, perform these analysis steps:
- Examine `src/demo_deliverable_generator.py` to understand configuration flow
- Identify `_KEYWORD_MAP` (97 keywords) and `_SCENARIO_TEMPLATES` (10 scenarios)
- Map `_detect_scenario()` function logic
- Review `murphy_production_server.py` for existing endpoints
- Analyze `scripts/hetzner_load.sh` for infrastructure components
- Check for missing dependencies (numpy, concept_translation)

---

## Part III: Demo Configuration Endpoints Specification

### 3.1 GET /api/demo/config

**Purpose:** Expose the complete configuration of the demo deliverable generator for debugging and transparency.

**Response Schema:**
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

**Implementation Requirements:**
- Import from demo_deliverable_generator
- Access `_SCENARIO_TEMPLATES` and `_KEYWORD_MAP`
- Return static configuration data
- Handle import errors gracefully with fallback data

### 3.2 POST /api/demo/inspect

**Purpose:** Trace how a query is processed through the demo pipeline for debugging.

**Request Schema:**
```json
{
  "query": "Create an employee onboarding checklist"
}
```

**Response Schema:**
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

## Part IV: HITL System Enhancements Specification

### 4.1 Enhanced HITLRejectionRequest Model

**Purpose:** Ensure rejections are meaningful and actionable with mandatory documentation.

**Schema:**
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

### 4.2 Enhanced POST /api/hitl/{hitl_id}/reject

**Purpose:** Process rejection with intelligent follow-up generation.

**Enhanced Response Schema:**
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

**Implementation Requirements:**
- Validate reason is at least 10 characters
- Use LLM to generate 2-5 follow-up questions based on rejection reason
- Analyze original request for ambiguity flags
- Support example upload URL and description
- Log rejection for analytics

### 4.3 GET /api/hitl/{hitl_id}/inspect

**Purpose:** Provide detailed inspection of a HITL deliverable for debugging and transparency.

**Response Schema:**
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

## Part V: Infrastructure Status Endpoints

### 5.1 GET /api/infrastructure/status

**Purpose:** Compare current server configuration with hetzner_load.sh infrastructure requirements.

**Response Schema:**
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

### 5.2 POST /api/infrastructure/compare

**Purpose:** Detailed comparison between production and hetzner_load.sh configuration.

**Request Schema:**
```json
{
  "compare_file": "scripts/hetzner_load.sh",
  "check_packages": true,
  "check_services": true
}
```

---

## Part VI: Matrix Server Integration

### 6.1 Matrix Configuration

**Purpose:** Enable real-time Matrix messaging for HITL notifications.

**Configuration Schema:**
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

### 6.2 Matrix Notification Endpoints

**POST /api/matrix/notify**
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

## Summary

### Files Created

| File | Lines | Purpose |
|------|-------|---------|
| `src/module_instance_manager.py` | 1,132 | Core manager with spawn/despawn, viability checking, audit trails |
| `src/module_instance_api.py` | 548 | FastAPI REST endpoints for all operations |
| `MODULE_INSTANCE_MANAGER_SPEC.md` | 494 | Complete specification with examples |

### Key Features Implemented

#### 1. Unique Instance IDs
- Every spawned module gets a unique ID like `inst-llm-control-0001-a1b2c3`
- Enables tracking through the entire lifecycle
- Supports configuration backward logic for debugging

#### 2. Spawn/Despawn Lifecycle
- `spawn_module()` with viability pre-flight checks
- `despawn_module()` with force option for cleanup
- Circuit breaker protection against cascade failures
- Depth limits for anti-recursion protection

#### 3. Configuration Backward Logic (Audit Trail)
- Every operation logged with timestamp, actor, correlation ID
- `get_configuration_history()` traces full instance lineage
- Parent-child relationships for hierarchical tracking
- Supports debugging and compliance requirements

#### 4. Viability Checking ("Murphy Cursor Actions")
- `find_viable_instances()` selects modules based on capabilities
- Checks resources, dependencies, blacklist status
- Returns sorted list of best candidates
- Enables intelligent module selection

#### 5. Resource Management
- CPU and memory budgets
- Max spawn depth (anti-recursion)
- Max instances per type
- Circuit breaker with auto-recovery

### API Endpoints Summary

| Endpoint | Purpose |
|----------|---------|
| `POST /module-instances/spawn` | Spawn new instance |
| `POST /module-instances/{id}/despawn` | Despawn instance |
| `GET /module-instances/` | List all instances |
| `POST /module-instances/find-viable` | Find viable instances |
| `GET /module-instances/audit/trail` | Get audit trail |
| `GET /module-instances/{id}/config-history` | Configuration backward logic |
| `GET /module-instances/status/manager` | Manager status |
| `GET /module-instances/status/resources` | Resource availability |
| `POST /module-instances/types/register` | Register module type |
| `POST /module-instances/types/{type}/blacklist` | Blacklist a type |
| `POST /module-instances/bulk/despawn` | Bulk despawn |

---

## Implementation Checklist

### Module Instance Manager
- [x] Create `module_instance_manager.py` with core classes
- [x] Create `module_instance_api.py` with FastAPI endpoints
- [x] Create specification documentation
- [ ] Integrate with `murphy_production_server.py`
- [ ] Add WebSocket notifications for real-time updates
- [ ] Create unit tests
- [ ] Add Matrix bot integration for notifications

### HITL Enhancements
- [ ] Implement enhanced rejection model
- [ ] Add LLM-generated follow-up questions
- [ ] Support example uploads
- [ ] Create deliverable inspection endpoint

### Infrastructure
- [ ] Compare with hetzner_load.sh
- [ ] Add infrastructure status endpoints
- [ ] Configure Matrix server integration

---

## Copilot Instructions

When implementing this specification:

1. **Follow the Ten Validation Questions** for every module
2. **Maintain all code examples and JSON schemas exactly as specified**
3. **Preserve the hierarchical instance tracking** for configuration backward logic
4. **Implement viability checking** before spawning any module instance
5. **Ensure all audit trails** capture timestamp, actor, and correlation ID
6. **Apply hardening** including input validation, rate limiting, and circuit breakers
7. **Update documentation** after all changes including as-builts
8. **Commission modules** after implementation following the validation process

The Module Instance Manager System enables dynamic module instantiation with full audit capability, supporting the "murphy cursor actions" pattern of selecting modules based on request viability.