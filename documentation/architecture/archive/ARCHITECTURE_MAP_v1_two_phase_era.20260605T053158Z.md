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
        │          REST API (FastAPI - Port 8000)             │
        │     src/runtime/app.py                              │
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

### AionMind 2.0a Cognitive Pipeline (Embedded)

```
┌───────────────────────────────────────────────────────────────────┐
│                 AIONMIND 2.0a COGNITIVE PIPELINE                  │
│                  (Orchestrator-of-Orchestrators)                   │
├───────────────────────────────────────────────────────────────────┤
│  Layer 1: Context Engine     → ContextObject (structured input)   │
│  Layer 2: Capability Registry → 20+ bot capabilities auto-bridged │
│           Reasoning Engine   → Candidate ExecutionGraphObjects     │
│  Layer 3: RSC Integration    → Stability-gated expansion          │
│  Layer 4: Orchestration      → Graph execution with HITL gates    │
│  Layer 5: Memory (STM/LTM)  → Similarity search, archival        │
│  Layer 6: Optimization       → Conservative proposals only        │
├───────────────────────────────────────────────────────────────────┤
│  /api/execute  ──→  cognitive_execute() ──→  legacy fallback      │
│  /api/forms/*  ──→  cognitive_execute() ──→  legacy fallback      │
│  /api/aionmind/* ──→ dedicated 2.0 endpoints                     │
└───────────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
  Bot Inventory       RSC Controller      WorkflowDAGEngine
  (capability bridge)  (live wiring)       (backward compat)
```

---

## Core Components

### 1. REST API Layer

**Component:** `src/runtime/app.py`

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

**Component:** `control_plane/__init__.py` *(was: universal_control_plane.py)*

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

**Component:** `runtime/app.py` *(was: inoni_business_automation.py)*

**Responsibilities:**
- Autonomous with HITL safety gates operation of Inoni LLC
- 5 business automation engines
- Self-operation capabilities with human-in-the-loop approval for high-risk actions
- Business process automation

#### Safety Model
Inoni business automation runs autonomously for routine operations (content generation,
monitoring, analytics, bug detection). Operations involving financial transactions,
external outreach, production deployments, and code modifications require HITL gate
approval when confidence is below the configured threshold (default: 0.7).
This is by design — Murphy's safety-first architecture treats HITL as a feature, not a limitation.

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

**Component:** `execution_orchestrator/__init__.py` *(was: two_phase_orchestrator.py)*

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

### 6. Generative Automation System (GAP-001)

**Components:** 
- `src/voice_command_interface.py` — Voice/typed command processing
- `src/ai_workflow_generator.py` — Natural language to workflow DAG
- `strategic/gap_closure/text_to_automation/text_to_automation.py` — Core "Describe → Execute" engine
- `src/org_build_plan/workflow_templates.py` — Template library and industry presets

**Responsibilities:**
- Convert natural language descriptions into governed automation workflows
- Template matching for common automation patterns (ETL, CI/CD, monitoring)
- Keyword inference to map action verbs to step types
- Dependency resolution and DAG construction
- Automatic governance gate injection at critical points
- Role-aware execution respecting RBAC permissions

**Generative Automation Flow:**
```
┌─────────────────────────────────────────────────────────────────────┐
│                    DESCRIBE → EXECUTE PIPELINE                       │
├─────────────────────────────────────────────────────────────────────┤
│  1. USER INPUT                                                       │
│     Voice Command (/api/vci/process) or Typed (/api/workflows)      │
│                           │                                          │
│  2. NATURAL LANGUAGE PROCESSING                                      │
│     Template Matching → Keyword Inference → Step Type Mapping        │
│                           │                                          │
│  3. DAG GENERATION                                                   │
│     Dependency Resolution → Topological Sort → Parallel Markers      │
│                           │                                          │
│  4. GOVERNANCE INJECTION                                             │
│     Auto-insert HITL gates before deploy/output/approval steps       │
│                           │                                          │
│  5. EXECUTION                                                        │
│     WorkflowDAGEngine (24 handlers) → Connector Framework            │
└─────────────────────────────────────────────────────────────────────┘
```

**Built-in Templates (12+):**

| Template | Pattern | Steps |
|----------|---------|-------|
| `etl_pipeline` | Extract-Transform-Load | 4 |
| `ci_cd` | CI/CD Pipeline | 6 |
| `incident_response` | Incident Handling | 5 |
| `monitoring_alert` | Metric Monitoring | 3 |
| `report_generation` | Report & Distribute | 4 |
| `order_fulfillment` | E-commerce | 7 |
| `invoice_processing` | AP Automation | 6 |
| `lead_nurture` | CRM Lead Management | 6 |
| `employee_onboarding` | HR Onboarding | 6 |
| `content_publishing` | Content Pipeline | 5 |

**User Role Permissions:**

| Role | Capabilities |
|------|-------------|
| Platform Admin | System-wide presets, global governance |
| Tenant Owner | Tenant presets, user management |
| Operator | Execute scoped, approve gates |
| Viewer | Read-only metrics |
| HITL Operator | Credential-gated approvals |

**Documentation:** [Generative Automation Presets](documentation/features/GENERATIVE_AUTOMATION_PRESETS.md)

### 7. Confidence Engine (Murphy Validation)

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

### 8. Execution Engine

**Component:** `src/execution_engine/`

**Responsibilities:**
- Execute validated tasks
- Workflow orchestration
- Decision engine
- State machine management

**Key Modules:**
- `form_intake/__init__.py` *(was: integrated_form_executor.py)* - Main executor
- `adaptive_decision_engine.py` *(was: decision_engine.py)* - Decision logic
- `execution_orchestrator/__init__.py` *(was: workflow_orchestrator.py)* - Workflow management
- `state_machine.py` - State transitions

**Features:**
- Parallel task execution
- Dependency resolution
- Error handling and recovery
- Execution telemetry

### 9. Learning Engine (Correction System)

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

### 10. Supervisor System (HITL)

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

#### Freelancer Validator (`src/freelancer_validator/`)

Extends the HITL system to hire external human validators on freelance
platforms (Fiverr, Upwork, or a generic self-hosted queue).

**Components:**
- `rosetta/rosetta_models.py` *(was: models.py)* — FreelancerTask, FreelancerResponse, ValidationCriteria, BudgetConfig, Credential, CredentialRequirement, ValidatorCredentialProfile
- `bridge_layer/__init__.py` *(was: platform_client.py)* — Abstract client + Fiverr/Upwork/Generic adapters
- `billing/__init__.py` *(was: budget_manager.py)* — Org-level monthly + per-task budget enforcement
- `gate_synthesis/__init__.py` *(was: criteria_engine.py)* — Build criteria, format instructions, score responses
- `credential_verifier.py` — Verifies validator credentials against public records (BBB, state license boards), checks for complaints/disciplinary actions
- `hitl_bridge.py` — Orchestrates dispatch → credential gate → ingest → HITL monitor wiring

**Credential Verification:**
- 7 credential types: professional license, industry certification, academic degree, government clearance, trade certification, language proficiency, platform verified
- Pluggable public-record sources: BBB, state/provincial license boards, generic registries
- Complaint/disciplinary-action lookup across all registered sources
- Country/region filtering, authority validation, expiry checks
- Tasks can require specific credentials; validators are verified before response acceptance

**Flow:**
1. **Dispatch** — HITL monitor flags low-confidence/high-risk task
2. **Budget Gate** — BudgetManager verifies org can afford the task
3. **Post** — Task + structured criteria + credential requirements posted to freelance platform
4. **Validate** — Freelancer evaluates against per-criterion rubric (boolean/scale/text)
5. **Credential Gate** — CredentialVerifier checks validator credentials against public databases and complaint registries
6. **Ingest** — CriteriaEngine scores the response, derives verdict
7. **Wire** — FreelancerHITLBridge calls `respond_to_intervention()` on HITL monitor

### 11. Security Plane

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

### 12. Integration Engine (SwissKiss)

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

### 13. Bot System

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
| **DeepInfra** | REST API + Key Rotation | Primary LLM provider |
| **Aristotle** | REST API | Alternative LLM |
| **Stripe** | Python SDK | Payment processing |
| **Twilio** | REST API | SMS/Voice |
| **SendGrid** | REST API | Email |
| **GitHub** | REST API + GitPython | Code integration |
| **AWS** | boto3 SDK | Cloud storage |
| **GCP** | google-cloud SDK | Cloud storage |
| **Azure** | azure SDK | Cloud storage |
| **Fiverr** | REST API (Business) | Freelancer HITL validation |
| **Upwork** | REST API | Freelancer HITL validation |

### Internal Integrations

| Component A | Component B | Integration Type |
|-------------|-------------|------------------|
| REST API | All Systems | Function calls |
| Form Intake | Confidence Engine | Validation pipeline |
| Confidence Engine | HITL System | Approval workflow |
| Freelancer Validator | HITL System | External human validation → InterventionResponse |
| Freelancer Validator | Budget Manager | Org-level spend authorization |
| Freelancer Validator | Credential Verifier | Public-record verification (BBB, license boards) |
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
- LLM API rate limits (DeepInfra key rotation)
- CPU/Memory limits (no explicit limits)
- Concurrent execution (asyncio-based)

**Storage:**
- Database (PostgreSQL)
- File system (logs, workspaces)
- Redis (caching - optional)

**Network:**
- Inbound: REST API (port 8000)
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
    ├─ Requires: src/runtime/app.py
    └─ Requires: All src/ modules

universal_control_plane.py
    ├─ Requires: 7 engines (sensor, actuator, database, api, content, command, agent)
    └─ Requires: Module manager

src/runtime/app.py
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

### Forge Deliverable Pipeline  (labels: WIRE-*)

The Swarm Forge generates deliverables through a 5-phase enrichment pipeline.
Each phase feeds forward; fallbacks ensure output even when modules are unavailable.

```
  ┌──────────────┐   ┌────────────────────┐   ┌───────────────────┐
  │ Phase 1       │   │ Phase 2            │   │ Phase 3           │
  │ MFGC Gate     │──▶│ Workflow Resolution│──▶│ MSS Pipeline      │
  │ WIRE-MFGC-001 │   │ WIRE-WF-001        │   │ WIRE-MSS-001..004 │
  └──────────────┘   └────────────────────┘   └────────┬──────────┘
                                                        │
                     ┌───────────────────┐              │
                     │ Domain Expert     │──────────────┤ (concurrent)
                     │ WIRE-EXPERT-001   │              │
                     └───────────────────┘              │
                                                        ▼
  ┌────────────────────┐   ┌──────────────────────┐   ┌──────────────────┐
  │ Phase 4            │   │ Librarian Lookup      │   │ Automation Spec  │
  │ LLM Content Gen    │◀──│ WIRE-LIB-001          │   │ WIRE-SPEC-001    │
  │ WIRE-LLM-001       │   └──────────────────────┘   └──────────────────┘
  └────────┬───────────┘
           │
           ▼
  ┌──────────────────────┐
  │ Phase 5              │
  │ HITL Review          │
  │ FORGE-HITL-001       │
  └──────────────────────┘
```

**Data surfaced per wire:**
- **WIRE-MSS-001**: CQI, IQS, resolution level, risk indicators, simulation impact (cost/complexity/compliance/performance), engineering hours, regulatory implications
- **WIRE-MSS-002**: Architecture mapping (components, data flows, control logic, validation methods)
- **WIRE-MSS-003**: Module specification (name, purpose, dependencies, interfaces), existing module analysis
- **WIRE-MSS-004**: Resolution progression (RM0 → RMn) for both Magnify and Solidify
- **WIRE-MFGC-001**: Confidence score, Murphy Index, gate list, phases completed
- **WIRE-LIB-001**: Librarian knowledge context (streaming + non-streaming endpoints)
- **WIRE-LLM-001**: Full DeepInfra context window (131,072 tokens) for async methods
- **WIRE-SPEC-001**: ROI/competitor automation specification in streaming pipeline
- **WIRE-EXPERT-001**: Domain expert team, time/cost estimates, artifacts, collaboration map
- **WIRE-WF-001**: Workflow steps as intentional descriptive metadata (not dynamic dispatch)

---

## Foundation-Layer Automation Wiring

The following components implement the self-automation foundation (Phase 0 + Phase 1). Each item is labelled with a design ticket and team owner.

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
| MKT-001      | ContentPipelineEngine        | PersistenceManager   | save_document (content)    |
| MKT-001      | ContentPipelineEngine        | EventBackbone        | publish(LEARNING_FEEDBACK) |
| MKT-002      | SEOOptimisationEngine        | PersistenceManager   | save_document (analyses)   |
| MKT-002      | SEOOptimisationEngine        | EventBackbone        | publish(LEARNING_FEEDBACK) |
| MKT-003      | CampaignOrchestrator         | PersistenceManager   | save_document (campaigns)  |
| MKT-003      | CampaignOrchestrator         | EventBackbone        | publish(LEARNING_FEEDBACK) |
| ADV-003      | SelfOptimisationEngine       | SelfImprovementEngine| inject ImprovementProposal |
| ADV-003      | SelfOptimisationEngine       | PersistenceManager   | save_document (cycles)     |
| ADV-003      | SelfOptimisationEngine       | EventBackbone        | publish(LEARNING_FEEDBACK) |
| ADV-004      | ResourceScalingController    | PersistenceManager   | save_document (decisions)  |
| ADV-004      | ResourceScalingController    | EventBackbone        | publish(LEARNING_FEEDBACK) |
| DEV-003      | AutoDocumentationEngine      | PersistenceManager   | save_document (docs)       |
| DEV-003      | AutoDocumentationEngine      | EventBackbone        | publish(LEARNING_FEEDBACK) |
| DEV-004      | BugPatternDetector           | SelfImprovementEngine| inject ImprovementProposal |
| DEV-004      | BugPatternDetector           | PersistenceManager   | save_document (reports)    |
| DEV-004      | BugPatternDetector           | EventBackbone        | publish(LEARNING_FEEDBACK) |
| SUP-003      | FAQGenerationEngine          | PersistenceManager   | save_document (FAQs)       |
| SUP-003      | FAQGenerationEngine          | EventBackbone        | publish(LEARNING_FEEDBACK) |
| SEC-001      | SecurityAuditScanner         | PersistenceManager   | save_document (reports)    |
| SEC-001      | SecurityAuditScanner         | EventBackbone        | publish(LEARNING_FEEDBACK) |
| INT-001      | AutomationIntegrationHub     | All registered modules| route_event via handlers   |
| INT-001      | AutomationIntegrationHub     | PersistenceManager   | save_document (reports)    |
| INT-001      | AutomationIntegrationHub     | EventBackbone        | publish(LEARNING_FEEDBACK) |
| DEV-005      | DependencyAuditEngine        | PersistenceManager   | save_document (reports)    |
| DEV-005      | DependencyAuditEngine        | EventBackbone        | publish(LEARNING_FEEDBACK) |
| SUP-004      | CustomerCommunicationManager | PersistenceManager   | save_document (templates)  |
| SUP-004      | CustomerCommunicationManager | EventBackbone        | publish(LEARNING_FEEDBACK) |
| MKT-004      | SocialMediaScheduler         | PersistenceManager   | save_document (posts)      |
| MKT-004      | SocialMediaScheduler         | EventBackbone        | publish(LEARNING_FEEDBACK) |
| MKT-005      | MarketingAnalyticsAggregator | PersistenceManager   | save_document (reports)    |
| MKT-005      | MarketingAnalyticsAggregator | EventBackbone        | publish(LEARNING_FEEDBACK) |
| BIZ-004      | ComplianceReportAggregator   | PersistenceManager   | save_document (reports)    |
| BIZ-004      | ComplianceReportAggregator   | EventBackbone        | publish(LEARNING_FEEDBACK) |
| BIZ-005      | StrategicPlanningEngine      | PersistenceManager   | save_document (plans)      |
| BIZ-005      | StrategicPlanningEngine      | EventBackbone        | publish(LEARNING_FEEDBACK) |
| INTRO-001    | SelfIntrospectionEngine      | EventBackbone        | publish(introspection_completed, metric_recorded) |
| SCS-001      | SelfCodebaseSwarm            | EventBackbone        | publish(task_completed, task_submitted) |
| CSE-001      | CutSheetEngine               | EventBackbone        | publish(task_completed, metric_recorded) |
| VSB-001      | VisualSwarmBuilder           | EventBackbone        | publish(task_completed) |
| CEO-002      | CEOBranchActivation          | EventBackbone        | publish(ceo_branch_activated, ceo_directive_issued, metric_recorded) |
| PROD-ENG-001 | ProductionAssistantEngine    | EventBackbone        | publish(gate_evaluated, task_submitted, task_completed) |

### CEO Branch ↔ ActivatedHeartbeatRunner Wiring

```
 [CEO-002] CEOBranchActivation ↔ ActivatedHeartbeatRunner
   Owner: Platform Engineering / Autonomous Operations
   File:  src/ceo_branch_activation.py + src/activated_heartbeat_runner.py
   Purpose: CEOBranchActivation drives the top-level autonomous decision
            cycle; ActivatedHeartbeatRunner.tick() invokes the CEO plan
            loop on a configurable cadence.
   Wiring: ActivatedHeartbeatRunner calls CEOBranchActivation.run_cycle()
           on each tick. CEOBranchActivation emits metric_recorded and
           ceo_directive_issued to EventBackbone after each planning cycle.
   Safety: Bounded directive queue; planning errors are logged and the
           runner continues without halting the heartbeat loop.
```

### Production Assistant ↔ EventBackbone Wiring

```
 [PROD-ENG-001] ProductionAssistantEngine ↔ EventBackbone
   Owner: Platform Engineering / Operations
   File:  src/production_assistant_engine.py
   Purpose: Manages the full request lifecycle (7 stages) with deliverable
            gate validation (99% confidence threshold via SafetyGate).
   Wiring: ProductionAssistantOrchestrator accepts event_backbone param.
           Publishes gate_evaluated on each DeliverableGateValidator call,
           task_submitted when a production request enters the queue,
           task_completed when the 7-stage lifecycle finishes.
   Safety: DeliverableGateValidator enforces COMPLIANCE-type SafetyGate;
           non-compliant items fail closed (request halted, not skipped).
```

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

### Phase 4 Marketing Automation Wiring

```
┌─────────────────────────────────────────────────────────────────────┐
│     MARKETING & CONTENT AUTOMATION LAYER                            │
└─────────────────────────────────────────────────────────────────────┘

 [MKT-001] ContentPipelineEngine
   Owner: Marketing Team
   File:  src/content_pipeline_engine.py
   Purpose: Automated content lifecycle management.
            - Create content briefs (topic, type, channels, keywords, tone)
            - Draft → review → approve → schedule → publish lifecycle
            - Multi-channel publish (blog, social, email, copy)
            - Performance metric tracking per content piece
   Wiring: Writes to PersistenceManager.
           Publishes LEARNING_FEEDBACK events to EventBackbone.
   Safety: All content requires review before publish.
           Immutable: published content cannot be modified.
           Bounded content store with eviction policy.

 [MKT-002] SEOOptimisationEngine
   Owner: Marketing Team
   File:  src/seo_optimisation_engine.py
   Purpose: SEO analysis and content scoring.
            - Keyword extraction via frequency analysis
            - Meta-tag generation (title, description, keyword tags)
            - Content scoring (0–100) against SEO best practices
            - Issue detection (title length, body length, keyword coverage)
   Wiring: Writes to PersistenceManager.
           Publishes LEARNING_FEEDBACK events to EventBackbone.
   Safety: Non-destructive: analyses are append-only.
           Bounded analysis store with eviction policy.

 [MKT-003] CampaignOrchestrator
   Owner: Marketing Team
   File:  src/campaign_orchestrator.py
   Purpose: End-to-end marketing campaign management.
            - Create campaigns with budget, channels, date range
            - Per-channel budget allocation and spend tracking
            - Lifecycle: planned → active → paused → completed/cancelled
            - ROI indicators (CPC, CPA) per channel
   Wiring: Writes to PersistenceManager.
           Publishes LEARNING_FEEDBACK events to EventBackbone.
   Safety: Budget enforcement: spend cannot exceed allocation.
           Immutable: completed campaigns cannot be modified.
           Bounded campaign store with eviction policy.
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

### Phase 6 Continued — Self-Optimisation & Scaling Wiring

```
┌─────────────────────────────────────────────────────────────────────┐
│     ADVANCED SELF-OPTIMISATION & RESOURCE SCALING LAYER             │
└─────────────────────────────────────────────────────────────────────┘

 [ADV-003] SelfOptimisationEngine
   Owner: AI Team
   File:  src/self_optimisation_engine.py
   Purpose: Performance bottleneck detection and auto-tuning proposals.
            - Record performance samples (metric, value, component)
            - Detect bottlenecks via p95 threshold analysis
            - Severity classification: critical/high/medium/low
            - Generate tuning proposals for SelfImprovementEngine
            - Track optimisation cycle history
   Wiring: Writes to PersistenceManager.
           Injects ImprovementProposals into SelfImprovementEngine.
           Publishes LEARNING_FEEDBACK events to EventBackbone.
   Safety: Conservative: only flags metrics consistently above threshold.
           Non-destructive: proposals are suggestions, require approval.
           Bounded sample store with eviction policy.

 [ADV-004] ResourceScalingController
   Owner: DevOps Team
   File:  src/resource_scaling_controller.py
   Purpose: Capacity prediction, scaling decisions and cost tracking.
            - Record resource utilisation snapshots (cpu, memory, disk)
            - Analyse utilisation trends (moving average, growth rate)
            - Predict future utilisation via linear projection
            - Recommend scaling actions (scale_up, scale_down, no_action)
            - Track scaling decisions with cost estimates
   Wiring: Writes to PersistenceManager.
           Publishes LEARNING_FEEDBACK events to EventBackbone.
   Safety: Cost-aware: all scaling decisions include cost estimates.
           Human-in-the-loop: scale-up above cost threshold requires approval.
           Conservative: scale-up only when consistently above threshold.
           Bounded snapshot and decision stores with eviction.
```

---

### Phase 2 Continued — Development Automation Wiring

```
┌─────────────────────────────────────────────────────────────────────┐
│     DEVELOPMENT AUTOMATION — DOCUMENTATION & BUG DETECTION          │
└─────────────────────────────────────────────────────────────────────┘

 [DEV-003] AutoDocumentationEngine
   Owner: Documentation Team
   File:  src/auto_documentation_engine.py
   Purpose: Automated documentation generation from Python source analysis.
            - Scan Python files via ast module for classes, functions, docstrings
            - Extract design labels and owner annotations
            - Generate structured ModuleDoc artifacts
            - Build design-label inventory across the codebase
            - Persist documentation artifacts for downstream consumption
   Wiring: Writes to PersistenceManager.
           Publishes LEARNING_FEEDBACK events to EventBackbone.
   Safety: Read-only analysis: never modifies source files.
           Pure stdlib: uses ast module, no external dependencies.
           Bounded artifact store with eviction policy.

 [DEV-004] BugPatternDetector
   Owner: Backend Team / QA Team
   File:  src/bug_pattern_detector.py
   Purpose: Automated bug pattern detection from error data analysis.
            - Ingest error records (message, stack trace, component)
            - Fingerprint errors for deduplication and pattern matching
            - Detect recurring patterns via frequency analysis
            - Classify severity: critical/high/medium/low by occurrence count
            - Generate fix suggestions from error characteristics
            - Inject improvement proposals into SelfImprovementEngine
   Wiring: Writes to PersistenceManager.
           Injects proposals into SelfImprovementEngine.
           Publishes LEARNING_FEEDBACK events to EventBackbone.
   Safety: Read-only: never modifies source code.
           Conservative: only flags patterns above frequency threshold.
           Bounded error and pattern stores with eviction policy.
```

### Phase 3 Continued — Customer Support Wiring

```
┌─────────────────────────────────────────────────────────────────────┐
│     CUSTOMER SUPPORT — FAQ GENERATION                               │
└─────────────────────────────────────────────────────────────────────┘

 [SUP-003] FAQGenerationEngine
   Owner: Support Team
   File:  src/faq_generation_engine.py
   Purpose: Automated FAQ generation from ticket patterns and knowledge base.
            - Record customer questions for frequency analysis
            - Manage FAQ entries with versioning and view tracking
            - Detect knowledge gaps (frequent questions with no FAQ)
            - Search FAQs by keyword matching
            - Track FAQ effectiveness (views, helpfulness votes)
   Wiring: Writes to PersistenceManager.
           Publishes LEARNING_FEEDBACK events to EventBackbone.
   Safety: Non-destructive: FAQs are versioned, never deleted.
           Bounded FAQ and question stores with eviction policy.
```

### Phase 2 Continued — Dependency Management Wiring

```
┌─────────────────────────────────────────────────────────────────────┐
│     DEVELOPMENT AUTOMATION — DEPENDENCY SECURITY AUDITING           │
└─────────────────────────────────────────────────────────────────────┘

 [DEV-005] DependencyAuditEngine
   Owner: QA Team
   File:  src/dependency_audit_engine.py
   Purpose: Automated dependency security auditing and update tracking.
            - Register project dependencies (name, version, ecosystem)
            - Ingest vulnerability advisories (CVE/advisory data)
            - Run audit cycle: match advisories against dependencies
            - Classify findings by severity (critical/high/medium/low)
            - Lightweight semver range matching (stdlib only)
   Wiring: Writes to PersistenceManager.
           Publishes LEARNING_FEEDBACK events to EventBackbone.
   Safety: Read-only analysis: never modifies actual dependency files.
           Conservative: flags any version overlap as potentially affected.
           Bounded dependency, advisory, and report stores with eviction.
```

### Phase 3 Continued — Customer Communication Wiring

```
┌─────────────────────────────────────────────────────────────────────┐
│     CUSTOMER SUPPORT — PERSONALISED COMMUNICATION                   │
└─────────────────────────────────────────────────────────────────────┘

 [SUP-004] CustomerCommunicationManager
   Owner: Support Team
   File:  src/customer_communication_manager.py
   Purpose: Personalised response templates and satisfaction tracking.
            - Create and version response templates with {{variable}} placeholders
            - Render personalised responses via variable substitution
            - Record customer interactions (inbound, outbound, channel)
            - Collect and aggregate satisfaction ratings (1-5)
            - Compute per-customer and aggregate satisfaction metrics
   Wiring: Writes to PersistenceManager.
           Publishes LEARNING_FEEDBACK events to EventBackbone.
   Safety: Non-destructive: templates are versioned, never deleted.
           Bounded template and interaction stores with eviction.
```

### Phase 4 Continued — Social Media & Analytics Wiring

```
┌─────────────────────────────────────────────────────────────────────┐
│     MARKETING — SOCIAL MEDIA SCHEDULING & ANALYTICS                 │
└─────────────────────────────────────────────────────────────────────┘

 [MKT-004] SocialMediaScheduler
   Owner: Marketing Team
   File:  src/social_media_scheduler.py
   Purpose: Multi-platform post scheduling and engagement monitoring.
            - Create posts with platform, content, campaign linkage
            - Schedule posts for future publishing
            - Record publish events and engagement metrics
            - Track per-platform engagement (likes, shares, comments, reach)
            - Generate platform summary analytics
   Wiring: Writes to PersistenceManager.
           Publishes LEARNING_FEEDBACK events to EventBackbone.
   Safety: Non-destructive: posts are immutable once published.
           Bounded post and metric stores with eviction.

 [MKT-005] MarketingAnalyticsAggregator
   Owner: Marketing Team
   File:  src/marketing_analytics_aggregator.py
   Purpose: Cross-channel metric collection, trend detection, and attribution.
            - Ingest channel metrics (source, metric_name, value, tags)
            - Aggregate metrics by channel and time window
            - Detect trends (growth, decline, stable) via linear slope analysis
            - Generate summary reports with trend annotations
            - Minimum-sample-size guard for trend confidence
   Wiring: Writes to PersistenceManager.
           Publishes LEARNING_FEEDBACK events to EventBackbone.
   Safety: Read-only analysis: never modifies source channel data.
           Conservative: trend detection requires minimum sample size.
           Bounded data point and report stores with eviction.
```

### Phase 5 Continued — Compliance & Strategic Planning Wiring

```
┌─────────────────────────────────────────────────────────────────────┐
│     BUSINESS OPS — COMPLIANCE AGGREGATION & STRATEGIC PLANNING      │
└─────────────────────────────────────────────────────────────────────┘

 [BIZ-004] ComplianceReportAggregator
   Owner: Compliance Team
   File:  src/compliance_report_aggregator.py
   Purpose: Multi-framework compliance collection and violation detection.
            - Ingest compliance check results (framework, control, pass/fail)
            - Support GDPR, SOC2, HIPAA, PCI-DSS, ISO27001 frameworks
            - Detect violations (failed checks)
            - Compute posture score per framework (passed / total)
            - Generate compliance summary reports
   Wiring: Writes to PersistenceManager.
           Publishes LEARNING_FEEDBACK events to EventBackbone.
   Safety: Read-only analysis: never modifies compliance sources.
           Conservative: any failed check is flagged as a violation.
           Bounded check and report stores with eviction.

 [BIZ-005] StrategicPlanningEngine
   Owner: Strategy Team
   File:  src/strategic_planning_engine.py
   Purpose: Market analysis, opportunity scoring, and strategic plan generation.
            - Ingest market signals (category, description, impact score)
            - Score opportunities via weighted criteria (impact + volume)
            - Rank opportunities by composite score
            - Generate strategic plan documents with top opportunities
            - Minimum-signal threshold for opportunity qualification
   Wiring: Writes to PersistenceManager.
           Publishes LEARNING_FEEDBACK events to EventBackbone.
   Safety: Read-only analysis: never modifies external data sources.
           Conservative: opportunities require minimum supporting signals.
           Bounded signal, opportunity, and plan stores with eviction.
```

### Phase 0 Foundation — Security Wiring

```
┌─────────────────────────────────────────────────────────────────────┐
│     FOUNDATION SECURITY — AUTOMATED AUDIT SCANNING                  │
└─────────────────────────────────────────────────────────────────────┘

 [SEC-001] SecurityAuditScanner
   Owner: Security Team
   File:  src/security_audit_scanner.py
   Purpose: Automated security vulnerability scanning and hardening validation.
            - Scan Python files for security anti-patterns (eval, exec, etc.)
            - Detect hardcoded secrets, wildcard CORS, debug mode
            - Validate against pickle, SQL injection, and shell injection patterns
            - Classify findings by severity: critical/high/medium/low
            - Generate structured SecurityAuditReport
   Wiring: Writes to PersistenceManager.
           Publishes LEARNING_FEEDBACK events to EventBackbone.
   Safety: Read-only: never modifies scanned files.
           Conservative: flags potential issues for human review.
           Bounded finding and report stores with eviction policy.
```

### Phase 7 — Integration Orchestration Wiring

```
┌─────────────────────────────────────────────────────────────────────┐
│     INTEGRATION ORCHESTRATION LAYER                                 │
└─────────────────────────────────────────────────────────────────────┘

 [INT-001] AutomationIntegrationHub
   Owner: Platform Engineering / Architecture Team
   File:  src/automation_integration_hub.py
   Purpose: Master orchestration layer connecting all Phase 0–6 modules.
            - Register modules by design label with phase classification
            - Subscribe to EventBackbone events for cross-module routing
            - Route events to registered module handlers
            - Track integration health and event flow metrics
            - Detect broken integration links (modules not responding)
            - Generate IntegrationHealthReport
   Wiring: Subscribes to EventBackbone for all event types.
           Routes events to registered module handlers.
           Writes IntegrationHealthReport to PersistenceManager.
           Publishes LEARNING_FEEDBACK events to EventBackbone.
   Safety: Non-destructive: routes events, does not modify them.
           Graceful degradation: missing modules logged but not fatal.
           Bounded route history with eviction policy.

 Phase 7 Module Registry:
   ┌──────────────┬──────────────────────────────────┬──────────────┐
   │ Phase        │ Design Labels                    │ Count        │
   ├──────────────┼──────────────────────────────────┼──────────────┤
   │ Foundation   │ ARCH-001, ARCH-002, GATE-001,    │ 4            │
   │              │ SEC-001                          │              │
   │ Observability│ OBS-001, OBS-002, OBS-003, OBS-004│ 4           │
   │ Development  │ DEV-001, DEV-002, DEV-003,       │ 5            │
   │              │ DEV-004, DEV-005                 │              │
   │ Support      │ SUP-001, SUP-002, SUP-003,       │ 4            │
   │              │ SUP-004                          │              │
   │ Compliance   │ CMP-001                          │ 1            │
   │ Marketing    │ MKT-001, MKT-002, MKT-003,       │ 5            │
   │              │ MKT-004, MKT-005                 │              │
   │ Business     │ BIZ-001, BIZ-002, BIZ-003,       │ 5            │
   │              │ BIZ-004, BIZ-005                 │              │
   │ Advanced     │ ADV-001, ADV-002, ADV-003, ADV-004│ 4           │
   │ Integration  │ INT-001                          │ 1            │
   │ Operations   │ OPS-001, OPS-002, OPS-003, OPS-004│ 4           │
   │ Safety       │ SAF-001, SAF-002, SAF-003,       │ 5            │
   │              │ SAF-004, SAF-005                 │              │
   │ Orchestration│ ORCH-001, ORCH-002, ORCH-003,    │ 4            │
   │              │ ORCH-004                         │              │
   │ New Modules  │ INTRO-001, SCS-001, CSE-001, VSB-001, │ 6            │
   │              │ CEO-002, PROD-ENG-001                  │              │
   ├──────────────┼──────────────────────────────────┼──────────────┤
   │ TOTAL        │                                  │ 52           │
   └──────────────┴──────────────────────────────────┴──────────────┘
```

### Phase 8 — Operational Readiness & Autonomy Governance Wiring

```
┌─────────────────────────────────────────────────────────────────────┐
│     OPERATIONAL READINESS & AUTONOMY GOVERNANCE                     │
└─────────────────────────────────────────────────────────────────────┘

 [OPS-001] AutomationReadinessEvaluator
   Owner: Platform Engineering / Architecture Team
   File:  src/automation_readiness_evaluator.py
   Purpose: Cross-phase readiness assessment and wiring validation.
            - Registers expected modules per phase (all 33 design labels)
            - Checks each module's status via health callable
            - Scores each phase (healthy / expected)
            - Computes overall readiness with go/no-go verdict
            - Produces ReadinessReport with per-phase PhaseScore breakdown
   Wiring: Writes ReadinessReport to PersistenceManager.
           Publishes LEARNING_FEEDBACK events to EventBackbone.
   Safety: Read-only: never modifies module state.
           Conservative: READY requires ≥80% healthy, PARTIAL ≥50%.
           Bounded report store with eviction policy.

 [OPS-002] KPITracker
   Owner: Platform Engineering / Strategy Team
   File:  src/kpi_tracker.py
   Purpose: Automation KPI tracking and target monitoring (Part 7 of Plan).
            - Defines 8 default KPIs: automation rate, success rate, uptime,
              error rate, response time, time savings, cost savings, test coverage
            - Records observed values with EMA-based current calculation
            - Compares current values against targets (higher/lower is better)
            - Generates KPISnapshot with met/not_met/no_data classification
   Wiring: Writes KPISnapshot to PersistenceManager.
           Publishes LEARNING_FEEDBACK events to EventBackbone.
   Safety: Read-only analysis: never modifies source data.
           Bounded observation and snapshot stores with eviction.

 [OPS-003] AutomationModeController
   Owner: AI Team / Governance Team
   File:  src/automation_mode_controller.py
   Purpose: Risk-based automation mode progression (Part 6 of Plan).
            - 5 automation levels: MANUAL → SUPERVISED → AUTO_LOW → AUTO_HIGH → FULL
            - Records task outcomes and computes EMA success rate
            - Upgrades mode when EMA exceeds threshold with minimum observations
            - Downgrades mode automatically when EMA falls below hold threshold
            - Supports manual override with audit trail
   Wiring: Writes ModeTransition to PersistenceManager.
           Publishes LEARNING_FEEDBACK events to EventBackbone.
   Safety: Conservative: upgrades require sustained success, not single spikes.
           Automatic downgrade on failure as safety degradation.
           Bounded outcome and transition stores with eviction.

 [OPS-004] EmergencyStopController
   Owner: DevOps Team / Security Team
   File:  src/emergency_stop_controller.py
   Purpose: Global and per-tenant emergency stop (Part 6 of Plan).
            - Manual activation/resumption (global or per-tenant scope)
            - Automatic triggers: consecutive failure threshold, error rate threshold
            - Blocks all autonomous operations while stopped
            - Controlled resume with reason logging and counter reset
   Wiring: Writes StopEvent to PersistenceManager.
           Publishes SYSTEM_HEALTH events to EventBackbone.
   Safety: Fail-safe: defaults to stopped on ambiguity.
           Non-destructive: stop blocks operations, does not destroy state.
           Bounded event history with eviction policy.
```

### Phase 9 — Safety Governance & Risk Controls Wiring

```
┌─────────────────────────────────────────────────────────────────────┐
│     SAFETY GOVERNANCE & RISK CONTROLS                               │
└─────────────────────────────────────────────────────────────────────┘

 [SAF-001] SafetyValidationPipeline
   Owner: Security Team / AI Safety Team
   File:  src/safety_validation_pipeline.py
   Purpose: Three-stage safety validation for autonomous actions (Plan §6.1).
            - PRE_EXECUTION: authorization, input validation, risk assessment,
              rate-limit check, budget verification
            - EXECUTION: progress monitoring, anomaly detection, resource usage
            - POST_EXECUTION: output correctness, side-effect detection,
              metrics update, audit trail
            - Produces ValidationResult (PASSED / FAILED / WARNING) per action
            - Fail-closed: any check failure → overall FAILED
   Wiring: Writes ValidationResult to PersistenceManager.
           Publishes SYSTEM_HEALTH events to EventBackbone.
   Safety: Fail-closed: errors in checks default to FAILED.
           Pluggable: checks registered per stage as callables.
           Bounded result history with eviction policy.

 [SAF-002] AutomationRBACController
   Owner: Security Team / Governance Team
   File:  src/automation_rbac_controller.py
   Purpose: Role-based access control for automation operations (Plan §6.2).
            - 4 roles: ADMIN, OWNER, OPERATOR, VIEWER
            - 4 permissions: TOGGLE_FULL_AUTOMATION, VIEW_AUTOMATION_METRICS,
              APPROVE_AUTONOMOUS_ACTION, OVERRIDE_AUTOMATION
            - Only ADMIN/OWNER may toggle full automation
            - Default-deny: unknown users are always denied
            - Immutable audit trail for every authorization decision
   Wiring: Writes AuditEntry to PersistenceManager.
           Publishes AUDIT_LOGGED events to EventBackbone.
   Safety: Default-deny: any unknown user/permission is denied.
           Fail-closed: errors in permission checks → denied.
           Per-tenant isolation: roles scoped to (user, tenant) pairs.

 [SAF-003] TenantResourceGovernor
   Owner: Platform Engineering / Security Team
   File:  src/tenant_resource_governor.py
   Purpose: Per-tenant resource limits and enforcement (Plan §6.2).
            - 4 resource dimensions: API calls, CPU seconds, memory MB, budget USD
            - Real-time usage tracking with cumulative and peak modes
            - Pre-execution limit check (allowed / denied_over_limit / denied_unknown)
            - Usage snapshot generation for monitoring dashboards
            - Billing-cycle reset capability
   Wiring: Writes UsageSnapshot to PersistenceManager.
           Publishes SYSTEM_HEALTH events to EventBackbone on breaches.
   Safety: Fail-closed: unknown tenant → request denied.
           Per-tenant isolation: no cross-tenant data access.
           Bounded snapshot store with eviction policy.

 [SAF-004] AlertRulesEngine
   Owner: DevOps Team / Platform Engineering
   File:  src/alert_rules_engine.py
   Purpose: Configurable alert rules with severity and cooldown (Plan §6.3).
            - 3 severity levels: CRITICAL, WARNING, INFO
            - 5 comparators: GT, LT, GTE, LTE, EQ
            - 5 default rules: system down, high error rate, slow response,
              low success rate, automation mode change
            - Per-rule cooldown to prevent alert storms
            - Enable/disable rules at runtime
   Wiring: Writes FiredAlert to PersistenceManager.
           Publishes SYSTEM_HEALTH events to EventBackbone.
   Safety: Cooldown-based deduplication prevents alert fatigue.
           Bounded alert history with eviction policy.
           All comparisons are purely numeric (no code eval).

 [SAF-005] RiskMitigationTracker
   Owner: Strategy Team / Security Team
   File:  src/risk_mitigation_tracker.py
   Purpose: Technical, operational, and business risk tracking (Plan §8).
            - 9 default risks from Part 8 of the Self-Automation Plan
            - Risk scoring: Likelihood × Impact (1–9 scale)
            - 5 status levels: OPEN → MITIGATING → MITIGATED → ACCEPTED → CLOSED
            - Status change history with audit trail
            - RiskSummary with counts by category, status, likelihood, impact
   Wiring: Writes StatusChange and RiskSummary to PersistenceManager.
           Publishes LEARNING_FEEDBACK events to EventBackbone.
   Safety: Non-destructive: risks are never deleted, only status-changed.
           Bounded status history with eviction policy.
```

### Phase 10 — Cross-Module Orchestration & Operational Bootstrap Wiring

```
┌─────────────────────────────────────────────────────────────────────┐
│     CROSS-MODULE ORCHESTRATION & OPERATIONAL BOOTSTRAP              │
└─────────────────────────────────────────────────────────────────────┘

 [ORCH-001] SafetyGatewayIntegrator
   Owner: Platform Engineering / Security Team
   File:  src/safety_gateway_integrator.py
   Purpose: Wires SAF-001 SafetyValidationPipeline into API request lifecycle.
            - Per-route risk classification (CRITICAL/HIGH/MEDIUM/LOW/MINIMAL)
            - Bypass list for health/monitoring endpoints
            - Pre-execution validation via SAF-001 pipeline
            - Fail-closed: unclassified routes default to HIGH risk
            - Records gateway decisions (ALLOWED / BLOCKED / BYPASSED)
   Wiring: Writes GatewayDecision to PersistenceManager.
           Publishes SYSTEM_HEALTH events to EventBackbone.
   Safety: Fail-closed: unclassified routes default to HIGH risk.
           Bypass list for health-check endpoints.
           Bounded decision history with eviction policy.

 [ORCH-002] ReadinessBootstrapOrchestrator
   Owner: Platform Engineering / DevOps Team
   File:  src/readiness_bootstrap_orchestrator.py
   Purpose: Seeds initial operational data across all subsystems.
            - KPI baselines for all 8 default KPIs (OPS-002)
            - RBAC roles for initial deployment team (SAF-002)
            - Tenant resource limits for default tenants (SAF-003)
            - Alert rule validation (SAF-004)
            - Risk register verification (SAF-005)
            - Idempotent: running twice does not duplicate data
   Wiring: Writes BootstrapReport to PersistenceManager.
           Publishes LEARNING_FEEDBACK events to EventBackbone.
   Safety: Idempotent: safe to re-run without side effects.
           Non-destructive: only seeds data, never deletes.
           Bounded report store with eviction policy.

 [ORCH-003] OperationalDashboardAggregator
   Owner: Platform Engineering / DevOps Team
   File:  src/operational_dashboard_aggregator.py
   Purpose: Unified operational view aggregating status from all modules.
            - Module registration by design label with status callable
            - On-demand status collection across all modules
            - Health classification: HEALTHY / DEGRADED / UNREACHABLE
            - System-wide health derivation with threshold logic
            - DashboardSnapshot with per-module and aggregate stats
   Wiring: Writes DashboardSnapshot to PersistenceManager.
           Publishes SYSTEM_HEALTH events to EventBackbone.
   Safety: Non-destructive: read-only status collection.
           Graceful degradation: unreachable modules logged, not fatal.
           Bounded snapshot store with eviction policy.

 [ORCH-004] ComplianceOrchestrationBridge
   Owner: Compliance Team / Security Team
   File:  src/compliance_orchestration_bridge.py
   Purpose: Cross-module compliance validation pipeline (Plan §6.2).
            - 5 default frameworks: GDPR, SOC2, HIPAA, PCI-DSS, ISO27001
            - Per-framework controls with evidence source registration
            - Assessment produces per-framework COMPLIANT/NON_COMPLIANT/PARTIAL
            - Conservative: unknown control status counts as NOT_MET
            - ComplianceAssessment with aggregate and per-framework results
   Wiring: Writes ComplianceAssessment to PersistenceManager.
           Publishes LEARNING_FEEDBACK events to EventBackbone.
   Safety: Conservative: unknown evidence defaults to NOT_MET.
           Non-destructive: read-only evidence collection.
           Bounded assessment store with eviction policy.
```

---

## Next Steps

This architecture map documents Phases 0–10 of the self-automation plan (46 design labels):

1. **Readiness Assessment:** Run OPS-001 to validate wiring across all 46 modules
2. **Safety Pipeline Integration:** Wire SAF-001 into API gateway for pre/post validation
3. **RBAC Bootstrap:** Configure SAF-002 roles/users for initial deployment team
4. **Tenant Onboarding:** Configure SAF-003 limits for first production tenants
5. **Alert Baseline:** Tune SAF-004 thresholds per environment (dev/staging/prod)
6. **Risk Review Cycle:** Schedule quarterly SAF-005 risk register reviews
7. **KPI Baseline:** Seed OPS-002 with initial metric observations for all 8 default KPIs
8. **Mode Configuration:** Configure OPS-003 thresholds per environment
9. **Emergency Stop Integration:** Wire OPS-004 into API gateway for global stop capability
10. **End-to-End Integration Testing:** Exercise INT-001 with all 46 registered modules
11. **Security Baseline:** Run SEC-001 across entire src/ directory for initial audit
12. **Dependency Audit:** Run DEV-005 against requirements.txt to flag vulnerable packages
13. **Documentation Generation:** Run DEV-003 across src/ to build label inventory
14. **Bug Pattern Analysis:** Feed DEV-004 with historical error data from OBS-003
15. **Compliance Baseline:** Run BIZ-004 against GDPR/SOC2/HIPAA controls
16. **Strategic Plan Generation:** Seed BIZ-005 with market signals for Q2 planning
17. **Performance Analysis:** Run ADV-003 SelfOptimisationEngine against live telemetry
18. **Capacity Planning:** Run ADV-004 ResourceScalingController against production metrics

See `FILE_CLASSIFICATION.md` for complete file inventory and `SYSTEM_OVERVIEW.md` for system statistics.

---

## Self-Fix Loop (ARCH-005)

### Overview

The **Autonomous Self-Fix Loop** (`src/self_fix_loop.py`) closes the remediation gap by implementing a closed-loop cycle that detects, plans, executes, tests, and verifies runtime fixes — with no human intervention required for runtime-adjustable issues.

```
┌─────────────────────────────────────────────────────────────────┐
│                    SELF-FIX LOOP  (ARCH-005)                    │
│                                                                 │
│  1. DIAGNOSE  → Scan system for errors/gaps/bugs               │
│  2. PLAN      → Generate structured remediation plan            │
│  3. EXECUTE   → Apply fixes (config changes, runtime patches,  │
│  │               parameter adjustments, recovery procedures)    │
│  4. TEST      → Run targeted tests proving the fix works       │
│  5. VERIFY    → Confirm gap is closed, no regressions          │
│  6. REPEAT    → If gaps remain, go to step 1                   │
│  7. REPORT    → Generate final verification report             │
└─────────────────────────────────────────────────────────────────┘
```

### Component Wiring

| Dependency | Integration Point |
|---|---|
| `SelfImprovementEngine` (ARCH-001) | `diagnose()` calls `get_remediation_backlog()`, `generate_proposals()`; `plan()` calls `generate_executable_fix()` |
| `SelfHealingCoordinator` (OBS-004) | `execute()` registers new `RecoveryProcedure` objects for unhandled failure categories |
| `BugPatternDetector` (DEV-004) | `diagnose()` calls `run_detection_cycle()` and `get_patterns()` |
| `EventBackbone` | Publishes `SELF_FIX_STARTED`, `SELF_FIX_PLAN_CREATED`, `SELF_FIX_EXECUTED`, `SELF_FIX_TESTED`, `SELF_FIX_VERIFIED`, `SELF_FIX_COMPLETED`, `SELF_FIX_ROLLED_BACK` |
| `PersistenceManager` | Every `FixPlan`, `FixExecution`, and `LoopReport` is durably saved |

### Fix Types

| `fix_type` | Description | Autonomous? |
|---|---|---|
| `threshold_tuning` | Adjusts confidence thresholds, timeout values | ✅ Yes |
| `recovery_registration` | Registers new `RecoveryProcedure` handlers | ✅ Yes |
| `route_optimization` | Applies routing weight changes from engine data | ✅ Yes |
| `config_adjustment` | Modifies runtime configuration values | ✅ Yes |
| `code_proposal` | Code-level change — logged for human review | ❌ Human review |

### Safety Invariants

1. **Never modifies source files on disk** — all fixes operate at the runtime level.
2. **Bounded iterations** — `max_iterations` (default 10) prevents infinite loops.
3. **Mutex enforcement** — `RuntimeError` raised if a second loop is started concurrently.
4. **Rollback on failure** — every `FixPlan` carries `rollback_steps`; on test failure, all steps are reversed.
5. **Full audit trail** — every plan, execution, test, and report is persisted and published as events.
6. **Code proposals require human approval** — source files are never touched autonomously.

---

## Murphy Immune Engine (ARCH-014)

**Module:** `src/murphy_immune_engine.py`  
**Tests:** `tests/modules/test_murphy_immune_engine.py`  
**Docs:** `docs/IMMUNE_ENGINE.md`

Next-generation autonomous self-coding system that wraps and extends all existing self-healing components.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                      MURPHY IMMUNE ENGINE  (ARCH-014)                        │
│                                                                              │
│  DesiredStateReconciler ──▶ PredictiveFailureAnalyzer ──▶ ImmunityMemory    │
│          ↓                          ↓                          ↓             │
│  CascadeAnalyzer ◄──────── MurphyImmuneEngine ──────▶ ChaosHardenedValidator│
│          ↓                          ↓                                        │
│  SelfFixLoop (ARCH-005)      EventBackbone / PersistenceManager              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Integration Points

| Component | Integration |
|---|---|
| `SelfFixLoop` (ARCH-005) | Delegates `diagnose()`, `plan()`, `execute()`, `test()`, `rollback()` |
| `SelfImprovementEngine` (ARCH-001) | Injected into `SelfFixLoop` |
| `SelfHealingCoordinator` (OBS-004) | State queried by `DesiredStateReconciler` |
| `BugPatternDetector` (DEV-004) | Patterns fed to `PredictiveFailureAnalyzer` |
| `EventBackbone` | Publishes 7 new event types |
| `PersistenceManager` | Stores `ImmuneReport` per cycle |
| `FailureInjectionPipeline` | Used by `ChaosHardenedValidator` |

### Novel Capabilities

| Capability | Component |
|---|---|
| Kubernetes-style desired-state reconciliation | `DesiredStateReconciler` |
| Statistical predictive failure analysis | `PredictiveFailureAnalyzer` |
| Biological immune memory (instant replay) | `ImmunityMemory` |
| Chaos-hardened fix validation | `ChaosHardenedValidator` |
| Cascade-aware fix planning | `CascadeAnalyzer` |

### Safety Invariants

1. **Never modifies source files on disk.**
2. **Bounded by max_iterations** (default 20).
3. **Mutex enforcement** — `RuntimeError` if cycle already running.
4. **Rollback on test failure.**
5. **Chaos validation required** before ImmunityMemory promotion.
6. **Cascade check required** before ImmunityMemory promotion.
7. **Full audit trail** via EventBackbone + PersistenceManager.

---

## Communication Hub (COMMS-001)

**Location:** `src/communication_hub.py`, `src/comms_hub_routes.py`  
**UI:** `communication_hub.html` at `/ui/comms-hub`  
**Database:** 8 SQLAlchemy ORM models in `src/db.py` (tables prefixed `comms_`)

### Purpose
Unified onboard communication layer providing instant messaging, voice/video calling
(WebRTC signalling), email, per-channel automation rules, and a Discord-style moderator
console capable of broadcasting to multiple external platforms simultaneously.

### Store Components

| Class | Table(s) | Responsibility |
|-------|----------|----------------|
| `IMStore` | `comms_im_threads`, `comms_im_messages` | Thread/message CRUD, automod, reactions |
| `CallSessionStore` | `comms_call_sessions` | Voice/video session lifecycle, SDP/ICE, duration |
| `EmailStore` | `comms_emails` | Compose, inbox/outbox, mark-read, automod |
| `AutomationRuleStore` | `comms_automation_rules` | Rule CRUD, trigger evaluation, fire-count tracking |
| `ModeratorConsole` | `comms_user_profiles`, `comms_mod_audit`, `comms_broadcasts` | Moderation actions, blocked-word lists, multi-platform broadcast, audit log |

### API Surface

| Prefix | Count | Description |
|--------|-------|-------------|
| `/api/comms/im/*` | 6 | IM threads and messages |
| `/api/comms/voice/*` | 8 | Voice call sessions |
| `/api/comms/video/*` | 5 | Video call sessions |
| `/api/comms/email/*` | 5 | Email send, inbox, outbox |
| `/api/comms/automate/*` | 6 | Automation rules |
| `/api/moderator/*` | 18 | Moderator console |

### Persistence Model

```
         ┌─────────────────────────────────────────┐
         │           SQLite (murphy_logs.db)        │
         │   comms_im_threads  comms_im_messages    │
         │   comms_call_sessions  comms_emails      │
         │   comms_automation_rules                 │
         │   comms_user_profiles  comms_mod_audit   │
         │   comms_broadcasts                       │
         └─────────────────────────────────────────┘
                            ▲
              ┌─────────────┴──────────────┐
              │       Store Layer           │
              │  IMStore  CallSessionStore  │
              │  EmailStore  AutomRule…     │
              │  ModeratorConsole           │
              └─────────────┬──────────────┘
                            ▲
              ┌─────────────┴──────────────┐
              │     FastAPI Router          │
              │  /api/comms/*               │
              │  /api/moderator/*           │
              └────────────────────────────┘
```

### Fallback Behaviour
When SQLAlchemy is unavailable (import error, DB connection failure), every store
automatically falls back to in-process dicts.  The server continues to function; data
is not persisted between restarts.

### Auto-Moderation
- Default blocked-word list: `spam`, `scam`, `phishing`, `malware`, `ransomware`
- Custom words configurable per-deployment via `POST /api/moderator/automod/words`
- Every message and email is checked before storage; automod result attached to record
- Flagged messages trigger the `auto-moderate flagged IM` automation rule by default

### Broadcast Platforms
Supported: `im`, `voice`, `video`, `email`, `slack`, `discord`, `matrix`, `sms`

### Default Seeds (on startup)
- 3 automation rules: auto-reply missed call, escalate urgent email, automod-delete flagged IM
- 3 broadcast targets: `im#general`, `email#all-staff`, `matrix#murphy-general`

### Integration Points
- `src/db.py` — SQLAlchemy engine, session factory, `create_tables()`
- `src/runtime/app.py` — router registration, `/ui/comms-hub` HTML route
- `tests/communication/test_communication_hub.py` — 83 tests

---

## Founder Update Engine (ARCH-007)

**Location:** `src/founder_update_engine/`  
**Tests:** `tests/org_management/test_founder_update_engine.py` (133 tests)  
**Design Label:** ARCH-007

### Purpose
Central intelligence layer that monitors how Murphy updates and maintains itself.
Provides the Founder with a live operating picture (health scores, bug patterns,
vulnerability counts, recovery rates) and generates actionable recommendations for
SDK updates, security patches, maintenance tasks, and bug responses.  All actions
are proposals — execution always requires explicit approval unless flagged
`auto_applicable=True`.

### Modules

| Module | Class | Responsibility |
|--------|-------|----------------|
| `recommendation_engine.py` | `RecommendationEngine` | Central recommendation store — 9 types, 5 priorities, persistence, 6 query methods |
| `subsystem_registry.py` | `SubsystemRegistry` | Auto-discovers Murphy subsystems; tracks health, update history, pending recs |
| `update_coordinator.py` | `UpdateCoordinator` | Applies updates within maintenance windows; rate-limits changes; full audit trail |
| `sdk_update_scanner.py` | `SdkUpdateScanner` | Scans requirements files; detects patch/minor/major bumps; integrates vulnerability data |
| `auto_update_applicator.py` | `AutoUpdateApplicator` | Applies auto-applicable recs with health gates, rate limiting, dry-run mode |
| `bug_response_handler.py` | `BugResponseHandler` | Classifies bug reports; generates response drafts + BUG_RESPONSE/SECURITY recs |
| `operating_analysis_dashboard.py` | `OperatingAnalysisDashboard` | Aggregates fleet health, bug patterns, recovery rates, vuln counts → snapshots + recs |

### Recommendation Types

| Type | Source | Auto-Applicable |
|------|--------|----------------|
| `SDK_UPDATE` (patch bump) | `SdkUpdateScanner` | ✅ Yes |
| `SDK_UPDATE` (minor/major bump) | `SdkUpdateScanner` | ❌ No |
| `SECURITY` | `SdkUpdateScanner`, `BugResponseHandler`, `OperatingAnalysisDashboard` | ❌ No |
| `AUTO_UPDATE` | `SdkUpdateScanner` | ✅ Yes |
| `BUG_RESPONSE` | `BugResponseHandler` | ❌ No |
| `PERFORMANCE` | `OperatingAnalysisDashboard` | ❌ No |
| `MAINTENANCE` | `OperatingAnalysisDashboard` | ❌ No |

### Operating Analysis Thresholds

| Metric | Warning Threshold | Action |
|--------|-------------------|--------|
| Fleet health score | < 80% | `PERFORMANCE` recommendation (HIGH) |
| Fleet health score | < 50% | `MAINTENANCE` recommendation (CRITICAL) |
| Active bug patterns | > 5 | `MAINTENANCE` recommendation |
| Self-healing recovery rate | < 70% | `MAINTENANCE` recommendation |
| Open vulnerabilities | > 3 | `SECURITY` recommendation |

### Data Flow

```
External Inputs                  Founder Update Engine
─────────────────────────────────────────────────────────────────
requirements*.txt ──────────────▶ SdkUpdateScanner
                                       │ SDK_UPDATE / SECURITY / AUTO_UPDATE recs
                                       ▼
Incoming bug reports ────────────▶ BugResponseHandler
                                       │ BUG_RESPONSE / SECURITY recs
                                       ▼
SubsystemRegistry   ─────────────▶ OperatingAnalysisDashboard
BugPatternDetector  ─────────────▶       │ DashboardSnapshot
SelfHealingCoord.   ─────────────▶       │ PERFORMANCE / MAINTENANCE / SECURITY recs
DependencyAudit     ─────────────▶       │
                                         ▼
                               RecommendationEngine (central store)
                                         │
                                         ▼
                               UpdateCoordinator (applies auto_applicable recs)
                                         │
                               AutoUpdateApplicator (health-gated execution)
```

### Subsystem Health States

```
healthy ──▶ degraded ──▶ failed
   ▲                        │
   └─────── recovered ───────┘
unknown (initial state for auto-discovered subsystems)
```

### Safety Invariants

1. **Never modifies source files on disk** — all actions are proposals only.
2. **Health gate** — `AutoUpdateApplicator` aborts a cycle if any subsystem is FAILED.
3. **Rate limiting** — configurable max applications per maintenance window.
4. **Dry-run mode** — full simulation without execution; all outcomes logged as `SKIPPED_DRY_RUN`.
5. **Founder approval required** for CRITICAL/HIGH security and all major version bumps.
6. **Thread-safe** — all shared state guarded by `threading.Lock`.
7. **Bounded history** — all stores cap their history (responses: 1000, snapshots: 200, records: 500).

### Integration Points

| Component | How Used |
|-----------|---------|
| `BugPatternDetector` (DEV-004) | `BugResponseHandler` feeds errors in; `OperatingAnalysisDashboard` reads active pattern counts |
| `SelfHealingCoordinator` (OBS-004) | `OperatingAnalysisDashboard` reads recovery history and success rate |
| `DependencyAuditEngine` (DEV-005) | `SdkUpdateScanner` reads vulnerability findings; `OperatingAnalysisDashboard` reads open vuln count |
| `SubsystemRegistry` (ARCH-007) | `UpdateCoordinator`, `OperatingAnalysisDashboard` iterate registered subsystems |
| `PersistenceManager` | All modules persist state via `save_document` / `load_document` |
| `EventBackbone` | Publishes `LEARNING_FEEDBACK` and `SYSTEM_HEALTH` events on key actions |

---

## Appendix: Test Coverage Matrix (Commissioning Status)

_Last updated: 2026-04-02 — Phase 0A baseline_

### Crown Jewel Modules — Test File Status

| Module | Source File | Test File | Tests | G4 Status |
|--------|------------|-----------|-------|-----------|
| LCM Engine | `src/lcm_engine.py` | `tests/modules/test_lcm_engine.py` | 35 | ✅ PASS |
| LLM Provider | `src/llm_provider.py` | `tests/llm/test_llm_provider.py` | 22 | ✅ PASS |
| LCM Integration Bridge | `src/lcm_integration_bridge.py` | `tests/modules/test_lcm_integration_bridge.py` | 39 | ✅ PASS |
| Tool Registry | `src/tool_registry/` | `tests/modules/test_tool_registry.py` | 27 | ✅ PASS |
| Multi-Agent Coordinator | `src/multi_agent_coordinator/` | `tests/agents/test_multi_agent_coordinator.py` | 24 | ✅ PASS |
| Persistent Memory | `src/persistent_memory/` | `tests/modules/test_persistent_memory.py` | 29 | ✅ PASS |
| Skill System | `src/skill_system/` | `tests/runtime_core/test_skill_system.py` | ~20 | ✅ PASS |
| MCP Plugin | `src/mcp_plugin/` | `tests/integration_connector/test_mcp_plugin.py` | ~20 | ✅ PASS |
| Feature Flags | `src/feature_flags/` | `tests/platform_config/test_feature_flags.py` | ~20 | ✅ PASS |
| Swarm Rate Governor | `src/swarm_rate_governor.py` | `tests/execution/test_swarm_rate_governor.py` | 21 | ✅ PASS |
| Gate Bypass Controller | `src/gate_bypass_controller.py` | `tests/modules/test_gate_bypass_controller.py` | 18 | ✅ PASS |
| Error System | `src/errors/` | `tests/modules/test_error_system.py` | 20 | ✅ PASS |
| CEO Branch | `src/ceo_branch_activation.py` | `tests/runtime_core/test_ceo_branch.py` | 73 | ✅ PASS |
| Heartbeat Runner | `src/activated_heartbeat_runner.py` | `tests/runtime_core/test_activated_heartbeat_runner.py` | 29 | ✅ PASS |
| Rosetta Manager | `src/rosetta/` | `tests/runtime_core/test_rosetta.py` | 57 | ✅ PASS |
| Manifold Projection | `src/control_theory/manifold_projection.py` | `tests/modules/test_modular_manifolds.py` | 87 | ✅ PASS |
| Confidence Manifold Router | `src/control_theory/confidence_manifold.py` | `tests/modules/test_modular_manifolds.py` | (shared) | ✅ PASS |
| Swarm Manifold Optimizer | `src/swarm_manifold_optimizer.py` | `tests/modules/test_modular_manifolds.py` | (shared) | ✅ PASS |
| LLM Output Manifold | `src/llm_output_manifold.py` | `tests/modules/test_modular_manifolds.py` | (shared) | ✅ PASS |
| Manifold Drift Detector | `src/control_theory/drift_detector.py` | `tests/modules/test_modular_manifolds.py` | (shared) | ✅ PASS |
| Stiefel Optimizer | `src/ml/manifold_optimizer.py` | `tests/modules/test_modular_manifolds.py` | (shared) | ✅ PASS |

### Commissioning Gate Legend

| Gate | Description |
|------|-------------|
| G1 | Module does what it was designed to do |
| G2 | Spec documented (may evolve) |
| G3 | All possible conditions identified and handled |
| G4 | Test profile reflects full range of capabilities |
| G5 | Expected vs actual results verified |
| G6 | Regression loop available (re-run from symptoms) |
| G7 | All ancillary code and documentation updated |
| G8 | Hardening applied (error handling, rate limiting, thread safety) |
| G9 | Module re-commissioned after all above steps |

---

## Test Suite Structure

All test files are organized into **38 domain directories** under `tests/`.
No flat `test_*.py` files exist at the `tests/` root.
Each domain directory has:
- `__init__.py` — domain label
- `conftest.py` — auto-applied `pytest.mark.<domain>` marker

### Selective Execution

```bash
# Run a single domain
pytest -m compliance
pytest tests/compliance/

# Run everything except a domain
pytest -m "not game_creative"

# Run only core module tests
pytest -m modules

# Run CI-excluded domains separately
pytest tests/e2e/ tests/benchmarks/ tests/commissioning/
```

### Domain Directory Map

| Directory | Focus | Files |
|-----------|-------|-------|
| `tests/account_auth/` | Account, tenant, subscription, credentials | 9 |
| `tests/agents/` | Agent system, multi-agent, CI automation agents | 25 |
| `tests/auar/` | Automated User Acceptance Review | 3 |
| `tests/automation/` | Automation engines, scheduling | 12 |
| `tests/benchmarks/` | Performance benchmarks | 4 |
| `tests/bots/` | Bot framework, governance, telemetry | 4 |
| `tests/commissioning/` | Commissioning wave tests | 14 |
| `tests/communication/` | Communication hub, Matrix, email | 7 |
| `tests/competitive/` | Competitive intelligence, alignment | 4 |
| `tests/compliance/` | Audit, compliance, security hardening | 40 |
| `tests/content_media/` | Content creation, video, YouTube, social | 5 |
| `tests/cost_economics/` | Cost optimization, budget, unit economics | 4 |
| `tests/crm_sales/` | CRM, sales, marketing, customer lifecycle | 20 |
| `tests/data_persistence/` | Database, migration, schema, data pipelines | 16 |
| `tests/devops/` | CI/CD, deployment, containers, infrastructure | 12 |
| `tests/digital_twin/` | Digital twin, fleet management | 2 |
| `tests/document_export/` | Document generation, PDF, cutsheet, export | 5 |
| `tests/documentation_qa/` | Doc completeness, gap closure, surface tests | 59 |
| `tests/e2e/` | End-to-end integration tests | 8 |
| `tests/execution/` | Execution engine, orchestration, swarms | 9 |
| `tests/finance/` | Billing, grants, trading, financial reporting | 16 |
| `tests/game_creative/` | EQ game systems, creative engine, storyline | 17 |
| `tests/governance/` | Governance framework, authority gates, policy | 4 |
| `tests/hardening/` | Code hardening, quality, deficiency fixes | 13 |
| `tests/industrial/` | Robotics, building automation, energy mgmt | 4 |
| `tests/integration/` | Integration tests | 8 |
| `tests/integration_connector/` | Connectors, adapters, bridges, APIs | 21 |
| `tests/learning_analytics/` | ML, analytics, telemetry, learning engines | 26 |
| `tests/llm/` | LLM provider integration and routing | 12 |
| `tests/modules/` | Core module unit tests (catch-all) | 224 |
| `tests/notification_alert/` | Notifications, alerts, voice, announcements | 7 |
| `tests/onboarding/` | Onboarding flow, commissioning, setup | 16 |
| `tests/org_management/` | Organization, team, founder, management | 15 |
| `tests/platform_config/` | Configuration, feature flags, environment | 4 |
| `tests/resilience/` | Chaos, resilience, repair, recovery | 7 |
| `tests/runtime_core/` | Core runtime, boot, heartbeat, librarian | 69 |
| `tests/scheduling/` | Scheduler, planning, capacity | 8 |
| `tests/sla/` | SLA enforcement | 1 |
| `tests/submission_ticketing/` | Submissions, ticketing, triage adapters | 6 |
| `tests/system/` | System-level tests | 1 |
| `tests/testing_meta/` | Test mode controller, test vector generator | 2 |
| `tests/ui/` | UI screenshot/visual tests | 2 |
| `tests/ui_frontend/` | UI, dashboards, terminals, frontend wiring | 20 |
| `tests/wiring_validation/` | Cross-module wiring, structural audit | 22 |
| `tests/workflow_task/` | Workflow DAG, task pipelines, processes | 10 |

### Pytest Markers

All 38 domain markers are registered in `pyproject.toml`.
CI runs with `--ignore=tests/e2e --ignore=tests/commissioning --ignore=tests/integration --ignore=tests/sla --ignore=tests/benchmarks`.
