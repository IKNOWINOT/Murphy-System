# Murphy System 1.0 - Architecture Map

**Created:** February 4, 2026  
**Version:** 1.0.0

---

## Table of Contents

1. [High-Level Architecture](#high-level-architecture)
2. [Core Components](#core-components)
3. [Data Flows](#data-flows)
4. [Integration Points](#integration-points)
5. [System Boundaries](#system-boundaries)
6. [Component Interactions](#component-interactions)
7. [Processing Pipelines](#processing-pipelines)

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        MURPHY SYSTEM 1.0                            │
│                   Universal AI Automation System                     │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
        ┌─────────────────────────────────────────────────────┐
        │          REST API (FastAPI - Port 6666)             │
        │     murphy_complete_backend_extended.py             │
        └─────────────────────────────────────────────────────┘
                                  │
                ┌─────────────────┴─────────────────┐
                ▼                                   ▼
┌───────────────────────────┐        ┌─────────────────────────────┐
│   UNIVERSAL CONTROL PLANE │        │  INONI BUSINESS AUTOMATION  │
│  universal_control_plane.py│        │ inoni_business_automation.py│
├───────────────────────────┤        ├─────────────────────────────┤
│ • Sensor Engine           │        │ • Sales Engine              │
│ • Actuator Engine         │        │ • Marketing Engine          │
│ • Database Engine         │        │ • R&D Engine                │
│ • API Engine              │        │ • Business Management       │
│ • Content Engine          │        │ • Production Management     │
│ • Command Engine          │        └─────────────────────────────┘
│ • Agent Engine            │
└───────────────────────────┘
                │
                ▼
┌───────────────────────────────────────────────────────────────┐
│             TWO-PHASE ORCHESTRATOR                            │
│              two_phase_orchestrator.py                        │
├───────────────────────────────────────────────────────────────┤
│  PHASE 1 (Generative Setup)    │  PHASE 2 (Production)       │
│  • Analyze request             │  • Load session             │
│  • Determine control type      │  • Execute with engines     │
│  • Select engines              │  • Deliver results          │
│  • Discover constraints        │  • Learn from execution     │
│  • Create ExecutionPacket      │  • Repeat on schedule       │
│  • Create session              │                             │
└───────────────────────────────────────────────────────────────┘
                │
                ▼
┌───────────────────────────────────────────────────────────────┐
│                    CORE SYSTEMS LAYER                         │
└───────────────────────────────────────────────────────────────┘
    │           │           │           │           │
    ▼           ▼           ▼           ▼           ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────────┐
│ Form   │ │Confid- │ │Execu-  │ │Learning│ │Supervisor  │
│ Intake │ │ence    │ │tion    │ │Engine  │ │System      │
│        │ │Engine  │ │Engine  │ │        │ │(HITL)      │
└────────┘ └────────┘ └────────┘ └────────┘ └────────────┘
                │
                ▼
┌───────────────────────────────────────────────────────────────┐
│                  SPECIALIZED SYSTEMS                          │
└───────────────────────────────────────────────────────────────┘
    │           │           │           │           │
    ▼           ▼           ▼           ▼           ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────────┐
│Security│ │Integra-│ │Govern- │ │Module  │ │Swarm       │
│Plane   │ │tion    │ │ance    │ │Compiler│ │System      │
│        │ │Engine  │ │        │ │        │ │            │
└────────┘ └────────┘ └────────┘ └────────┘ └────────────┘
                │
                ▼
┌───────────────────────────────────────────────────────────────┐
│              SUPPORT INFRASTRUCTURE                           │
└───────────────────────────────────────────────────────────────┘
    │           │           │           │           │
    ▼           ▼           ▼           ▼           ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────────┐
│LLM     │ │Logging │ │Memory  │ │Domain  │ │70+ Bots    │
│Integr. │ │System  │ │System  │ │Expert  │ │            │
└────────┘ └────────┘ └────────┘ └────────┘ └────────────┘
```

---

## Core Components

### 1. REST API Layer

**Component:** `murphy_complete_backend_extended.py`

**Responsibilities:**
- Exposes 30+ REST endpoints for system interaction
- Handles HTTP requests and responses
- Integrates Flask (legacy) and FastAPI functionality
- Manages WebSocket connections for real-time updates
- Provides CORS middleware for cross-origin requests

**Key Endpoints:**
- `/api/forms/plan-upload` - Upload pre-existing plans
- `/api/forms/plan-generation` - Generate plans from natural language
- `/api/forms/task-execution` - Execute tasks with validation
- `/api/forms/validation` - Validate execution packets
- `/api/forms/correction` - Submit corrections
- `/api/corrections/*` - Correction management
- `/api/hitl/*` - Human-in-the-loop interventions
- `/api/system/info` - System information

**Dependencies:**
- Flask, FastAPI, Flask-CORS, Flask-SocketIO
- Pydantic for request/response validation
- All form handlers and execution systems

### 2. Universal Control Plane

**Component:** `universal_control_plane.py`

**Responsibilities:**
- Unified interface for all 6 automation types
- Modular engine system with dynamic loading
- Session-based isolation between automation types
- Engine selection based on task requirements
- State management across sessions

**7 Engines:**

| Engine | Purpose | Use Cases |
|--------|---------|-----------|
| **Sensor** | Read IoT sensors | Temperature, pressure, motion |
| **Actuator** | Control IoT devices | HVAC, motors, locks |
| **Database** | Data operations | CRUD, queries, ETL |
| **API** | External API calls | REST, GraphQL, webhooks |
| **Content** | Content generation | Blog posts, social media |
| **Command** | System commands | Shell, DevOps, scripts |
| **Agent** | AI agent tasks | Reasoning, swarms, complex |

**Key Features:**
- Engine hot-swapping without restart
- Per-session engine configuration
- Automatic resource cleanup
- Engine dependency resolution

### 3. Inoni Business Automation

**Component:** `inoni_business_automation.py`

**Responsibilities:**
- Autonomous operation of Inoni LLC
- 5 business automation engines
- Self-operation capabilities
- Business process automation

**5 Business Engines:**

#### Sales Engine
- Lead generation (web scraping, API integration)
- Lead qualification (scoring, filtering)
- Outreach automation (email, LinkedIn)
- Demo scheduling (calendar integration)
- CRM integration (HubSpot, Salesforce)

#### Marketing Engine
- Content creation (blog posts, social media)
- SEO optimization (keyword research, backlinking)
- Social media automation (posting, engagement)
- Analytics (traffic, conversions, ROI)
- A/B testing

#### R&D Engine
- Bug detection (automated testing, monitoring)
- Code fixes (automated PRs, deployments)
- Testing (unit, integration, e2e)
- Documentation (auto-generated docs)
- Performance optimization

#### Business Management Engine
- Finance (invoicing, expense tracking, reporting)
- Support (ticket management, auto-responses)
- Project management (task tracking, milestones)
- Documentation (internal wikis, procedures)

#### Production Management Engine
- Releases (versioning, changelogs, deployments)
- QA (automated testing, manual review coordination)
- Deployment (CI/CD pipeline management)
- Monitoring (uptime, performance, alerts)

### 4. Two-Phase Orchestrator

**Component:** `two_phase_orchestrator.py`

**Responsibilities:**
- Coordinates execution flow
- Implements two-phase execution pattern
- Session lifecycle management
- State persistence and recovery

**Phase 1: Generative Setup**
1. **Request Analysis** - Parse and understand request
2. **Control Type Determination** - Identify automation type
3. **Engine Selection** - Choose appropriate engines
4. **Constraint Discovery** - Identify limitations and requirements
5. **ExecutionPacket Creation** - Generate encrypted execution plan
6. **Session Creation** - Initialize isolated session

**Phase 2: Production Execution**
1. **Session Loading** - Restore execution context
2. **Engine Execution** - Run selected engines
3. **Result Delivery** - Return outputs to user
4. **Learning** - Capture execution data for improvement
5. **Scheduling** - Setup recurring execution if needed

**Key Features:**
- Session persistence across restarts
- Failure recovery and retry logic
- Execution telemetry collection
- Schedule-based automation

### 5. Form Intake System

**Component:** `src/form_intake/`

**Responsibilities:**
- Process user inputs (JSON, YAML, natural language)
- Validate input schemas with Pydantic
- Convert inputs to ExecutionPackets
- Handle 5 form types

**5 Form Types:**

| Form Type | Purpose | Schema |
|-----------|---------|--------|
| **Plan Upload** | Pre-existing plans | `PlanUploadForm` |
| **Plan Generation** | NL → Plan | `PlanGenerationForm` |
| **Task Execution** | Execute task | `TaskExecutionForm` |
| **Validation** | Validate packet | `ValidationForm` |
| **Correction** | Submit correction | `CorrectionForm` |

**Handler:** `FormHandler` class
- Routes forms to appropriate processors
- Validates against schemas
- Generates submission IDs
- Stores submissions for tracking

### 6. Confidence Engine (Murphy Validation)

**Component:** `src/confidence_engine/`

**Responsibilities:**
- Implements Murphy Validation formula
- Calculates 5D uncertainty scores
- Gate-based validation
- Risk assessment

**Murphy Validation Formula:**
```
murphy_index = (G - D) / H

Where:
- G = Guardrails satisfied (0.0 - 1.0)
- D = Danger score (0.0 - 1.0)
- H = Human oversight intensity (0.0 - 1.0)

Safe if: murphy_index > threshold (default 0.5)
```

**5D Uncertainty:**
- **UD** - Data Uncertainty (incomplete/noisy data)
- **UA** - Aleatoric Uncertainty (inherent randomness)
- **UI** - Input Uncertainty (ambiguous requests)
- **UR** - Representation Uncertainty (model limitations)
- **UG** - Generalization Uncertainty (out-of-distribution)

**Gate System:**
- Domain-specific validation rules
- Threshold-based approval/rejection
- Multi-gate validation chains
- Dynamic gate generation

### 7. Execution Engine

**Component:** `src/execution_engine/`

**Responsibilities:**
- Execute validated tasks
- Workflow orchestration
- Decision engine
- State machine management

**Key Modules:**
- `integrated_form_executor.py` - Main executor
- `decision_engine.py` - Decision logic
- `workflow_orchestrator.py` - Workflow management
- `state_machine.py` - State transitions

**Features:**
- Parallel task execution
- Dependency resolution
- Error handling and recovery
- Execution telemetry

### 8. Learning Engine (Correction System)

**Component:** `src/learning_engine/`

**Responsibilities:**
- Capture corrections from humans
- Extract patterns from correction data
- Train shadow agents
- Improve system accuracy over time

**4 Correction Methods:**

| Method | Usage | Example |
|--------|-------|---------|
| **Interactive** | Real-time chat | User corrects during conversation |
| **Batch** | Bulk upload | CSV of corrections |
| **API** | Programmatic | POST /api/corrections/submit |
| **Inline** | Code comments | `# CORRECTION: should be X` |

**Shadow Agent Training:**
1. **Data Collection** - Capture (task, prediction, correction) triples
2. **Pattern Extraction** - Identify common error patterns
3. **Model Training** - Train shadow agent on corrections
4. **A/B Testing** - Compare original vs shadow agent
5. **Gradual Rollout** - Increase shadow agent usage as accuracy improves

**Expected Improvement:**
- Initial accuracy: ~80%
- After corrections: 95%+
- Continuous improvement over time

### 9. Supervisor System (HITL)

**Component:** `src/supervisor_system/`

**Responsibilities:**
- Human-in-the-loop monitoring
- Intervention management
- Approval workflows
- Authority-based scheduling

**6 Checkpoint Types:**

| Checkpoint | Trigger | Example |
|-----------|---------|---------|
| **Integration** | New integration | GitHub repo added |
| **High-Risk Action** | murphy_index > threshold | Delete database |
| **Low Confidence** | confidence < threshold | Uncertain task |
| **First-Time Task** | New task type | Never seen before |
| **Scheduled Review** | Time-based | Daily review |
| **User-Requested** | Manual trigger | Explicit approval needed |

**Intervention Flow:**
1. **Detection** - System identifies checkpoint
2. **Request Creation** - Generate approval request
3. **Notification** - Alert human supervisors
4. **Human Review** - Human examines context
5. **Decision** - Approve/Reject/Modify
6. **Execution** - Continue or abort based on decision

### 10. Security Plane

**Component:** `src/security_plane/`

**Responsibilities:**
- Authentication and authorization
- Cryptography and encryption
- Data leak prevention
- Access control
- Security hardening

**Modules:**

| Module | Purpose |
|--------|---------|
| `authentication.py` | User auth, JWT, sessions |
| `access_control.py` | RBAC, permissions |
| `cryptography.py` | Encryption, key management |
| `data_leak_prevention.py` | DLP rules, scanning |
| `middleware.py` | Security middleware |
| `hardening.py` | Security best practices |
| `adaptive_defense.py` | Threat detection |
| `anti_surveillance.py` | Privacy protection |
| `packet_protection.py` | Execution packet encryption |

**Current Status:**
⚠️ **Implemented but not integrated into API** - Priority 1 security gap

### 11. Integration Engine (SwissKiss)

**Component:** `src/integration_engine/`

**Responsibilities:**
- Automatic GitHub repository ingestion
- Capability extraction from code
- Module/agent generation
- Safety testing
- HITL approval workflow

**SwissKiss Integration Flow:**
1. **Clone Repository** - Git clone to local workspace
2. **Analyze Code** - AST parsing, dependency analysis
3. **Extract Capabilities** - Identify functions, APIs, features
4. **Generate Module** - Create Murphy-compatible wrapper
5. **Safety Testing** - Run in sandbox, check for malicious code
6. **Human Approval** - Request HITL approval
7. **Integration** - Load module if approved

**Supported Integrations:**
- GitHub repositories
- External REST APIs
- Hardware devices (sensors, actuators)
- Payment providers (Stripe, PayPal)
- Communication services (Twilio, SendGrid)
- Cloud services (AWS, GCP, Azure)

### 12. Bot System

**Component:** `bots/` (70+ specialized bots)

**Responsibilities:**
- Specialized task handling
- Domain expertise
- Reusable capabilities
- Plugin architecture

**Major Bot Categories:**

| Category | Bots | Purpose |
|----------|------|---------|
| **Analysis** | AnalysisBot, ResearchBot | Data analysis, research |
| **Engineering** | EngineeringBot, CADBot | Technical tasks |
| **Knowledge** | Librarian, SystemLibrarian | Knowledge management |
| **Data** | JSONBot, Polyglot | Data transformation |
| **Optimization** | OptimizationBot, EfficiencyOptimizer | Performance tuning |
| **Communication** | CommsHub, FeedbackBot | Communication tasks |
| **Infrastructure** | KeyManagerBot, SchedulerBot | System management |

**Bot Architecture:**
- Base class: `bot_base.py`
- Plugin loader: `plugin_loader.py`
- Configuration: `config_loader.py`
- Common utilities: `utils/`

---

## Data Flows

### 1. Task Execution Flow

```
User Request (JSON/YAML/NL)
    ↓
REST API Endpoint (/api/forms/task-execution)
    ↓
Form Validation (Pydantic)
    ↓
Form Handler (FormHandler.handle_task_execution)
    ↓
Confidence Engine (Murphy Validation)
    ├─ Calculate murphy_index
    ├─ Assess 5D uncertainty
    └─ Check gates
    ↓
HITL Check (if needed)
    ├─ Create intervention request
    ├─ Wait for human approval
    └─ Continue if approved
    ↓
Two-Phase Orchestrator
    ├─ Phase 1: Generative Setup
    │   ├─ Analyze request
    │   ├─ Select engines
    │   └─ Create ExecutionPacket
    └─ Phase 2: Production
        ├─ Load session
        ├─ Execute with engines
        └─ Deliver results
    ↓
Execution Engine (Execute Task)
    ├─ Universal Control Plane
    │   └─ Engine(s) execution
    └─ Inoni Business Automation (if business task)
        └─ Business engine(s) execution
    ↓
Result Collection
    ↓
Learning Engine (Capture telemetry)
    ↓
Response to User
```

### 2. Correction Learning Flow

```
User Submits Correction
    ↓
REST API (/api/corrections/submit)
    ↓
Correction Form Validation
    ↓
IntegratedCorrectionSystem.capture_correction
    ↓
Store Correction
    ├─ task_id
    ├─ original_output
    ├─ corrected_output
    ├─ correction_type
    └─ timestamp
    ↓
Pattern Extraction (batch process)
    ├─ Analyze correction patterns
    ├─ Identify common errors
    └─ Extract training data
    ↓
Shadow Agent Training
    ├─ Prepare training dataset
    ├─ Train shadow model
    └─ Evaluate accuracy
    ↓
A/B Testing
    ├─ Route % traffic to shadow agent
    ├─ Compare performance
    └─ Increase % if better
    ↓
Gradual Rollout (80% → 95%+ accuracy)
```

### 3. Integration Flow (SwissKiss)

```
User Requests Integration (e.g., Stripe)
    ↓
REST API (/api/integrations/add)
    ↓
Integration Request Validation
    ↓
SwissKiss Loader
    ↓
Clone Repository
    ├─ Git clone stripe-python
    └─ Store in workspace
    ↓
Code Analysis
    ├─ Parse AST
    ├─ Extract functions/classes
    ├─ Identify dependencies
    └─ Map API endpoints
    ↓
Capability Extraction
    ├─ List capabilities
    ├─ Document parameters
    └─ Identify risks
    ↓
Module Generation
    ├─ Create Murphy wrapper
    ├─ Add validation
    └─ Implement safety checks
    ↓
Safety Testing
    ├─ Run in sandbox
    ├─ Test for malicious code
    └─ Verify functionality
    ↓
HITL Approval
    ├─ Generate approval request
    ├─ Present to human
    └─ Wait for decision
    ↓
Integration (if approved)
    ├─ Load module
    ├─ Register with system
    └─ Make available to engines
```

### 4. Business Automation Flow

```
Inoni Business Task
    ↓
Inoni Business Automation System
    ↓
Determine Business Engine
    ├─ Sales → SalesEngine
    ├─ Marketing → MarketingEngine
    ├─ R&D → R&DEngine
    ├─ Business → BusinessManagementEngine
    └─ Production → ProductionManagementEngine
    ↓
Engine Execution
    ├─ Sales: Lead gen, qualification, outreach
    ├─ Marketing: Content creation, SEO, social
    ├─ R&D: Bug fixes, testing, deployment
    ├─ Business: Finance, support, projects
    └─ Production: Releases, QA, monitoring
    ↓
External Integrations
    ├─ CRM (HubSpot, Salesforce)
    ├─ Payment (Stripe)
    ├─ Communication (Twilio, SendGrid)
    ├─ Social Media (Twitter, LinkedIn)
    ├─ Analytics (Google Analytics)
    └─ DevOps (GitHub, CircleCI)
    ↓
Result Delivery & Scheduling
```

---

## Integration Points

### External APIs

| Service | Integration Method | Purpose |
|---------|-------------------|---------|
| **Groq** | REST API + Key Rotation | Primary LLM provider |
| **Aristotle** | REST API | Alternative LLM |
| **Stripe** | Python SDK | Payment processing |
| **Twilio** | REST API | SMS/Voice |
| **SendGrid** | REST API | Email |
| **GitHub** | REST API + GitPython | Code integration |
| **AWS** | boto3 SDK | Cloud storage |
| **GCP** | google-cloud SDK | Cloud storage |
| **Azure** | azure SDK | Cloud storage |

### Internal Integrations

| Component A | Component B | Integration Type |
|-------------|-------------|------------------|
| REST API | All Systems | Function calls |
| Form Intake | Confidence Engine | Validation pipeline |
| Confidence Engine | HITL System | Approval workflow |
| Execution Engine | Universal Control Plane | Engine execution |
| Execution Engine | Inoni Business | Business execution |
| Learning Engine | Execution Engine | Telemetry collection |
| Integration Engine | HITL System | Safety approval |
| Security Plane | REST API | Middleware |

### Database Schema

**Primary Tables:**
- `submissions` - Form submissions
- `execution_packets` - Encrypted execution plans
- `corrections` - User corrections
- `hitl_interventions` - HITL approval requests
- `sessions` - Execution sessions
- `integrations` - Registered integrations
- `shadow_agent_training` - Training data
- `telemetry` - Execution metrics

**Relationships:**
- `submissions` → `execution_packets` (1:1)
- `submissions` → `corrections` (1:many)
- `execution_packets` → `hitl_interventions` (1:many)
- `sessions` → `telemetry` (1:many)

---

## System Boundaries

### Input Boundaries

**Accepted Inputs:**
- JSON requests (validated with Pydantic)
- YAML plans
- Natural language descriptions
- File uploads (plans, configurations)
- WebSocket messages
- CLI commands

**Input Validation:**
- Schema validation (Pydantic)
- Size limits (configurable)
- Type checking
- Sanitization (basic)

⚠️ **Security Gap:** No advanced input sanitization beyond Pydantic

### Output Boundaries

**Generated Outputs:**
- JSON responses
- Generated plans
- Execution results
- Correction patterns
- System metrics
- Logs and telemetry

**Output Formats:**
- REST API responses (JSON)
- WebSocket events
- Log files
- Database records
- File artifacts

### Resource Boundaries

**Compute:**
- LLM API rate limits (Groq key rotation)
- CPU/Memory limits (no explicit limits)
- Concurrent execution (asyncio-based)

**Storage:**
- Database (PostgreSQL)
- File system (logs, workspaces)
- Redis (caching - optional)

**Network:**
- Inbound: REST API (port 6666)
- Outbound: External APIs, LLMs

⚠️ **Security Gap:** No rate limiting on API endpoints

---

## Component Interactions

### Critical Dependencies

```
murphy_system_1.0_runtime.py
    ├─ Requires: universal_control_plane.py
    ├─ Requires: inoni_business_automation.py
    ├─ Requires: two_phase_orchestrator.py
    ├─ Requires: murphy_complete_backend_extended.py
    └─ Requires: All src/ modules

universal_control_plane.py
    ├─ Requires: 7 engines (sensor, actuator, database, api, content, command, agent)
    └─ Requires: Module manager

murphy_complete_backend_extended.py
    ├─ Requires: murphy_complete_backend.py (base)
    ├─ Requires: Form handlers (src/form_intake)
    ├─ Requires: Confidence engine
    ├─ Requires: Execution engine
    ├─ Requires: Learning engine
    └─ Requires: HITL system

two_phase_orchestrator.py
    ├─ Requires: Universal Control Plane
    ├─ Requires: Inoni Business Automation
    └─ Requires: Session manager

src/execution_engine/
    ├─ Requires: Confidence engine
    ├─ Requires: Workflow orchestrator
    └─ Requires: State machine

src/learning_engine/
    ├─ Requires: Correction storage
    ├─ Requires: Pattern extractor
    └─ Requires: Shadow agent trainer
```

### Circular Dependencies

⚠️ **Potential Issues:**
- Some modules may have circular imports
- Needs investigation in Phase 2

### Tight Coupling

⚠️ **Areas of Concern:**
- REST API tightly coupled to all form handlers
- Execution engine tightly coupled to control plane
- Some bots have direct database access

---

## Processing Pipelines

### Task Processing Pipeline

```
Request → Validation → Confidence → HITL → Orchestration → Execution → Learning → Response
  (API)   (Pydantic)    (Murphy)   (Human)   (2-Phase)    (Engines)   (Capture)  (JSON)
```

### Correction Pipeline

```
Correction → Storage → Pattern Analysis → Shadow Training → A/B Test → Rollout
  (User)     (DB)      (ML)               (PyTorch)        (Compare)   (Deploy)
```

### Integration Pipeline

```
Request → Clone → Analyze → Extract → Generate → Test → HITL → Load
 (API)    (Git)   (AST)     (Parse)   (Code)    (Sandbox) (Human) (Register)
```

### Business Automation Pipeline

```
Schedule → Engine Select → Execute → External API → Result → Next Schedule
 (Cron)    (5 Engines)     (Task)   (Integration)  (Store)  (Repeat)
```

---

## Foundation-Layer Automation Wiring

The following components implement the self-automation foundation described in
`MURPHY_SELF_AUTOMATION_PLAN.md` (Phase 0 + Phase 1). Each item is labelled
with a design ticket and team owner.

```
┌─────────────────────────────────────────────────────────────────────┐
│                  SELF-AUTOMATION FOUNDATION LAYER                    │
└─────────────────────────────────────────────────────────────────────┘

 [ARCH-001] SelfImprovementEngine ──save/load──▶ PersistenceManager
   Owner: Backend Team
   File:  src/self_improvement_engine.py
   Purpose: Outcomes, proposals, patterns now persist across restarts.

 [ARCH-002] SelfAutomationOrchestrator ──save/load──▶ PersistenceManager
   Owner: Backend Team
   File:  src/self_automation_orchestrator.py
   Purpose: Tasks, cycles, gaps, queue order now persist across restarts.

 [OBS-001] HealthMonitor
   Owner: DevOps Team
   File:  src/health_monitor.py
   Purpose: Registers subsystem health checks, produces aggregate
            HealthReports (HEALTHY / DEGRADED / UNHEALTHY).

 [OBS-002] HealthMonitor ──SYSTEM_HEALTH──▶ EventBackbone
   Owner: DevOps Team
   Wiring: HealthMonitor publishes to EventType.SYSTEM_HEALTH on
           every check_all() cycle for reactive automation.

 [GATE-001] GateBypassController
   Owner: AI Team
   File:  src/gate_bypass_controller.py
   Purpose: Risk-based confidence-gate bypass.
            CRITICAL/HIGH → never bypassed.
            LOW → bypass after 3 consecutive successes.
            MINIMAL → bypass immediately.
```

### Phase 1–2 Automation Wiring

```
┌─────────────────────────────────────────────────────────────────────┐
│         OBSERVABILITY & DEVELOPMENT AUTOMATION LAYER                │
└─────────────────────────────────────────────────────────────────────┘

 [OBS-003] LogAnalysisEngine
   Owner: Backend Team
   File:  src/log_analysis_engine.py
   Purpose: Ingests structured log entries, detects recurring error
            patterns via frequency analysis, generates error reports.
   Wiring: Publishes LEARNING_FEEDBACK events to EventBackbone
           when patterns are detected.
   Optional: RAGVectorIntegration for semantic log search.

 [OBS-004] SelfHealingCoordinator
   Owner: DevOps Team
   File:  src/self_healing_coordinator.py
   Purpose: Registers recovery procedures per failure category,
            auto-executes on TASK_FAILED / SYSTEM_HEALTH events.
   Safety: Cooldown periods, max-attempt limits, exponential back-off.
   Wiring: Subscribes to EventBackbone (TASK_FAILED, SYSTEM_HEALTH),
           publishes LEARNING_FEEDBACK on recovery outcomes.

 [DEV-001] AutomationLoopConnector
   Owner: Platform Engineering
   File:  src/automation_loop_connector.py
   Purpose: Closed-loop feedback wiring:
            1. EventBackbone → record outcomes → SelfImprovementEngine
            2. Extract patterns → generate proposals
            3. Convert high-priority proposals → orchestrator tasks
            4. Persist state automatically.
   Wiring: Subscribes to TASK_COMPLETED / TASK_FAILED.
           Writes to SelfImprovementEngine + SelfAutomationOrchestrator.

 [DEV-002] SLORemediationBridge
   Owner: QA Team
   File:  src/slo_remediation_bridge.py
   Purpose: Checks SLO compliance via OperationalSLOTracker,
            creates ImprovementProposals in SelfImprovementEngine
            for each violated SLO target.
   Wiring: Reads from OperationalSLOTracker, writes to
           SelfImprovementEngine, publishes LEARNING_FEEDBACK.
```

### Component Interaction Summary

| Design Label | Source                       | Target               | Mechanism           |
|--------------|------------------------------|----------------------|---------------------|
| ARCH-001     | SelfImprovementEngine        | PersistenceManager   | save/load_document  |
| ARCH-002     | SelfAutomationOrchestrator   | PersistenceManager   | save/load_document  |
| OBS-001      | HealthMonitor                | Any subsystem        | Callable check fn   |
| OBS-002      | HealthMonitor                | EventBackbone        | publish(SYSTEM_HEALTH) |
| GATE-001     | GateBypassController         | Confidence gates     | evaluate() → BypassDecision |
| OBS-003      | LogAnalysisEngine            | EventBackbone        | publish(LEARNING_FEEDBACK) |
| OBS-003      | LogAnalysisEngine            | RAGVectorIntegration | ingest_document / search |
| OBS-004      | SelfHealingCoordinator       | EventBackbone        | subscribe(TASK_FAILED, SYSTEM_HEALTH) |
| OBS-004      | SelfHealingCoordinator       | EventBackbone        | publish(LEARNING_FEEDBACK) |
| DEV-001      | AutomationLoopConnector      | SelfImprovementEngine| record_outcome / extract / generate |
| DEV-001      | AutomationLoopConnector      | SelfAutomationOrchestrator | create_task |
| DEV-001      | AutomationLoopConnector      | EventBackbone        | subscribe(TASK_COMPLETED, TASK_FAILED) |
| DEV-002      | SLORemediationBridge         | OperationalSLOTracker| check_slo_compliance |
| DEV-002      | SLORemediationBridge         | SelfImprovementEngine| inject ImprovementProposal |
| DEV-002      | SLORemediationBridge         | EventBackbone        | publish(LEARNING_FEEDBACK) |
| SUP-001      | TicketTriageEngine           | TicketingAdapter     | create_ticket (enriched)   |
| SUP-001      | TicketTriageEngine           | RAGVectorIntegration | search (semantic classify) |
| SUP-001      | TicketTriageEngine           | EventBackbone        | publish(LEARNING_FEEDBACK) |
| SUP-002      | KnowledgeBaseManager         | RAGVectorIntegration | ingest_document / search   |
| SUP-002      | KnowledgeBaseManager         | EventBackbone        | publish(LEARNING_FEEDBACK) |
| CMP-001      | ComplianceAutomationBridge   | ComplianceEngine     | check_deliverable / is_release_ready |
| CMP-001      | ComplianceAutomationBridge   | SelfImprovementEngine| inject ImprovementProposal |
| CMP-001      | ComplianceAutomationBridge   | EventBackbone        | subscribe(DELIVERY_COMPLETED) |
| CMP-001      | ComplianceAutomationBridge   | EventBackbone        | publish(LEARNING_FEEDBACK) |
| BIZ-001      | FinancialReportingEngine     | PersistenceManager   | save_document (reports)    |
| BIZ-001      | FinancialReportingEngine     | EventBackbone        | publish(LEARNING_FEEDBACK) |
| BIZ-002      | InvoiceProcessingPipeline    | PersistenceManager   | save_document (invoices)   |
| BIZ-002      | InvoiceProcessingPipeline    | EventBackbone        | publish(LEARNING_FEEDBACK) |
| BIZ-003      | OnboardingAutomationEngine   | PersistenceManager   | save_document (profiles)   |
| BIZ-003      | OnboardingAutomationEngine   | EventBackbone        | publish(LEARNING_FEEDBACK) |
| ADV-001      | CodeGenerationGateway        | PersistenceManager   | save_document (artifacts)  |
| ADV-001      | CodeGenerationGateway        | EventBackbone        | publish(LEARNING_FEEDBACK) |
| ADV-002      | DeploymentAutomationController | PersistenceManager | save_document (deployments)|
| ADV-002      | DeploymentAutomationController | EventBackbone      | publish(LEARNING_FEEDBACK) |

### Phase 3–4 Automation Wiring

```
┌─────────────────────────────────────────────────────────────────────┐
│     CUSTOMER SUPPORT & COMPLIANCE AUTOMATION LAYER                  │
└─────────────────────────────────────────────────────────────────────┘

 [SUP-001] TicketTriageEngine
   Owner: Support Team
   File:  src/ticket_triage_engine.py
   Purpose: Analyses incoming tickets using keyword heuristics and
            optional RAG semantic classification. Auto-assigns
            severity (critical/high/medium/low), category
            (incident/service_request/change_request/problem),
            and suggested team routing.
   Wiring: Creates enriched tickets in TicketingAdapter.
           Optionally uses RAGVectorIntegration for context.
           Publishes LEARNING_FEEDBACK events to EventBackbone.
   Safety: Conservative defaults (MEDIUM priority for unknowns).
           P1/P2 tickets flagged for human review.

 [SUP-002] KnowledgeBaseManager
   Owner: Support Team
   File:  src/knowledge_base_manager.py
   Purpose: RAG-powered knowledge base for customer support.
            - Article CRUD with versioning and view tracking
            - Keyword + RAG semantic search
            - Knowledge gap detection from search log analysis
            - Automatic knowledge extraction from resolved tickets
   Wiring: Ingests articles into RAGVectorIntegration.
           Publishes knowledge gap events to EventBackbone.
   Safety: Bounded article store with eviction policy.
           Non-destructive: articles are versioned, never deleted.

 [CMP-001] ComplianceAutomationBridge
   Owner: Compliance Team
   File:  src/compliance_automation_bridge.py
   Purpose: Continuous compliance monitoring wired into the
            automation pipeline. Validates deliverables against
            applicable compliance frameworks (GDPR, SOC2, HIPAA,
            PCI-DSS, ISO27001). Non-compliant findings auto-generate
            ImprovementProposals in SelfImprovementEngine.
   Wiring: Subscribes to DELIVERY_COMPLETED events.
           Reads from ComplianceEngine.
           Writes proposals to SelfImprovementEngine.
           Publishes LEARNING_FEEDBACK events.
   Safety: Deduplication for tracked violations.
           CRITICAL findings require manual approval.
```

### Phase 5–6 Automation Wiring

```
┌─────────────────────────────────────────────────────────────────────┐
│     BUSINESS OPERATIONS & ADVANCED SELF-AUTOMATION LAYER            │
└─────────────────────────────────────────────────────────────────────┘

 [BIZ-001] FinancialReportingEngine
   Owner: Finance Team
   File:  src/financial_reporting_engine.py
   Purpose: Automated financial data collection and report generation.
            - Record financial entries (revenue, expense, refund, investment)
            - Generate summary reports with period labels
            - Compute trend indicators (profit margin, revenue/expense ratio)
            - Persist reports via PersistenceManager
   Wiring: Writes to PersistenceManager.
           Publishes LEARNING_FEEDBACK events to EventBackbone.
   Safety: Immutable entries (append-only). Bounded history with eviction.

 [BIZ-002] InvoiceProcessingPipeline
   Owner: Finance Team
   File:  src/invoice_processing_pipeline.py
   Purpose: Automated invoice extraction, validation, and approval routing.
            - Submit invoices with vendor, amount, line items
            - Validate: required fields, amount consistency, line item match
            - Auto-approve below configurable threshold; escalate above
            - Full lifecycle: submitted → validated → approved → paid
   Wiring: Writes to PersistenceManager.
           Publishes LEARNING_FEEDBACK events to EventBackbone.
   Safety: Amount threshold for auto-approval. Immutable audit trail.
           Human-in-the-loop for high-value invoices.

 [BIZ-003] OnboardingAutomationEngine
   Owner: HR Team
   File:  src/onboarding_automation_engine.py
   Purpose: Automated HR onboarding workflow management.
            - Create onboarding profiles with role-based task checklists
            - Track task completion with timestamps and progress percentage
            - Support for engineering, support, and default templates
            - Publish milestone events for downstream automation
   Wiring: Writes to PersistenceManager.
           Publishes LEARNING_FEEDBACK events on task completion.
   Safety: Immutable history (completed tasks cannot be uncompleted).
           Bounded profiles with eviction.

 [ADV-001] CodeGenerationGateway
   Owner: AI Team
   File:  src/code_generation_gateway.py
   Purpose: Safe, template-based code generation with validation.
            - Built-in templates: python_module, python_function, python_test
            - Custom template registration
            - Safety validation: forbidden pattern scan (eval, exec, subprocess)
            - Python syntax verification via ast.parse
   Wiring: Writes to PersistenceManager.
           Publishes LEARNING_FEEDBACK events to EventBackbone.
   Safety: No arbitrary code execution. Forbidden patterns blocked.
           Template-only generation with safe string interpolation.

 [ADV-002] DeploymentAutomationController
   Owner: DevOps Team
   File:  src/deployment_automation_controller.py
   Purpose: CI/CD pipeline integration with safety gates and rollback.
            - Configurable pre-deployment gates (callable checkers)
            - Environment-aware: production always requires approval
            - Automatic rollback on health check failure
            - Full lifecycle: requested → gates → deploy → health → healthy/rolled_back
   Wiring: Writes to PersistenceManager.
           Publishes LEARNING_FEEDBACK events to EventBackbone.
   Safety: Production deployments require human approval.
           Automatic rollback on unhealthy deployment.
           Immutable deployment history and audit trail.
```

---

## Next Steps

This architecture map documents Phases 0–6 of the self-automation plan:

1. **Phase 6 (continued):** Self-Optimization — Performance analysis, bottleneck detection, auto-tuning
2. **Phase 6 (continued):** Self-Scaling — Resource monitoring, capacity prediction, cost optimization
3. **Security Review:** Map attack surfaces and vulnerabilities across all modules
4. **Performance Analysis:** Identify bottlenecks via SLO tracking and telemetry learning
5. **Test Strategy:** Map testing boundaries across all modules
6. **Integration Testing:** End-to-end flows across Phase 1-6 modules

See `FILE_CLASSIFICATION.md` for complete file inventory and `SYSTEM_OVERVIEW.md` for system statistics.
