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

### 14. MultiCursor Browser — Agent Controller (MCB)

**Component:** `src/agent_module_loader.py` — `MultiCursorBrowser`

**Role:** De-facto agent controller for all UI/browser/desktop interactions.
Every agent that performs any browser or desktop action **must** check out
an MCB controller at startup via `MultiCursorBrowser.get_controller(agent_id=...)`.
This mirrors the Copilot skill-checkout pattern: the controller is registered
once per agent identity and reused for the agent's lifetime.

**Agent startup protocol:**
```python
from src.agent_module_loader import MultiCursorBrowser

class MyAgent:
    def __init__(self):
        # Checkout MCB controller — one per agent identity
        self._mcb = MultiCursorBrowser.get_controller(agent_id="my_agent")
        # Browser is not launched until explicitly needed:
        # await self._mcb.launch()
```

**Capabilities (complete Playwright superset + Murphy extensions):**

| Layer | Actions |
|-------|---------|
| **Navigation** | navigate, go_back, go_forward, reload, wait_for_url, bring_to_front |
| **Interaction** | click, double_click, right_click, tap, fill, type, press, hover, focus, drag, scroll |
| **Forms** | select_option, check, uncheck, set_checked, file_upload, set_input_files |
| **Read** | get_text, text_content, get_inner_html, get_content, get_title, get_url, get_attribute, input_value, get_bounding_box |
| **Visibility** | is_visible, is_hidden, is_enabled, is_disabled, is_checked, is_editable |
| **Semantic Locators** | get_by_role, get_by_text, get_by_label, get_by_placeholder, get_by_alt_text, get_by_title, get_by_test_id |
| **Query** | query_selector, query_selector_all, eval_on_selector, eval_on_selector_all |
| **JavaScript** | evaluate, evaluate_handle, add_init_script, add_script_tag, expose_function, expose_binding, dispatch_event |
| **Style** | add_style_tag, emulate_media, set_viewport, set_content |
| **Network** | set_extra_headers, route_fulfill, route_abort, route_from_har, unroute, wait_for_request, wait_for_response, route_websocket |
| **Cookies/Storage** | get_cookies, set_cookies, clear_cookies, storage_state |
| **Permissions** | grant_permissions, clear_permissions, set_geolocation, set_offline |
| **Dialogs** | dialog_accept, dialog_dismiss |
| **Frames** | frame_locator, frame_navigate |
| **Keyboard** | press, keyboard_down, keyboard_up, keyboard_insert_text |
| **Mouse** | desktop_click, mouse_move, mouse_down, mouse_up, mouse_wheel |
| **Touch** | tap, touchscreen_tap |
| **Accessibility** | accessibility_snapshot |
| **Time** | clock_install, clock_set_fixed_time, clock_fast_forward, clock_run_for |
| **Inspection** | console_messages, page_errors, network_requests |
| **Screenshots** | screenshot (zone-scoped), pdf |
| **Wait** | wait_for_selector, wait_for_load_state, wait_for_function, wait_for_timeout, wait_for_navigation, wait_for_download, wait_for_popup, wait_for_event |
| **Assertions** | assert_text, assert_visible, assert_url, assert_title, assert_count, assert_enabled, assert_disabled, assert_hidden, assert_editable, assert_value, assert_attribute, assert_class, assert_checked |
| **Multi-Cursor** | cursor_create, cursor_warp, cursor_move, cursor_attach_zone, cursor_sync |
| **Zone Management** | zone_create, zone_resize, zone_split, zone_capture, auto_layout (up to 64 zones) |
| **Parallel** | parallel_start, parallel_join, parallel_all, parallel_probe |
| **Desktop** | desktop_click, desktop_type, desktop_hotkey, desktop_ocr, desktop_ocr_click, desktop_window_focus |
| **Agent** | agent_handoff, agent_checkpoint, agent_rollback, agent_clarify |
| **Recording** | record_start, record_stop, playback_start, replay |

**Controller Registry:**
```python
MultiCursorBrowser.list_controllers()   # → ["shadow_agent_xyz", "copilot_decision_learner", ...]
MultiCursorBrowser.release_controller("shadow_agent_xyz")  # on agent shutdown
```

**Agents with MCB wired:**
- `BaseSwarmAgent` (true_swarm_system.py) — base class for all swarm agents
- `ShadowAgent` (shadow_agent_integration.py) — shadow learning agents
- `DecisionLearner` (copilot_tenant/decision_learner.py) — copilot tenant
- All subclasses inherit MCB automatically via `BaseSwarmAgent.__init__`

**Commissioning Tests:** `tests/ui/commissioning/` — 69 tests covering
the full Onboarding → Production → Grant → Compliance → Partner → Pricing chain.

**Full reference:** `docs/MULTICURSOR_AGENT_CONTROLLER.md`

---


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

