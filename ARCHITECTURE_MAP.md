# Murphy System 1.0 - Architecture Map

**Date:** February 4, 2025  
**Version:** 1.0.0  
**Audit Phase:** 1 - Discovery & Inventory  
**Owner:** Inoni Limited Liability Company

---

## Table of Contents

1. [Component Relationships](#component-relationships)
2. [Data Flows](#data-flows)
3. [Integration Points](#integration-points)
4. [System Layers](#system-layers)
5. [Execution Flows](#execution-flows)

---

## Component Relationships

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     MURPHY SYSTEM 1.0                               │
│                  Universal Control Plane                            │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
        ┌─────────────────────┴─────────────────────┐
        ↓                                           ↓
┌───────────────────┐                  ┌──────────────────┐
│  PHASE 1: SETUP   │                  │ PHASE 2: EXECUTE │
│  (Generative)     │                  │  (Production)    │
└───────────────────┘                  └──────────────────┘
        ↓                                           ↓
┌─────────────────────────────────────────────────────────────────────┐
│                         MODULAR ENGINES                             │
├─────────────────────────────────────────────────────────────────────┤
│ Sensor Engine    │ Actuator Engine  │ Database Engine              │
│ API Engine       │ Content Engine   │ Command Engine               │
│ Agent Engine     │ Compute Engine   │ Reasoning Engine             │
└─────────────────────────────────────────────────────────────────────┘
        ↓
┌─────────────────────────────────────────────────────────────────────┐
│                      CORE SUBSYSTEMS                                │
├─────────────────────────────────────────────────────────────────────┤
│ Murphy Validation │ Confidence Engine │ Learning Engine            │
│ Supervisor System │ Correction Capture│ Shadow Agent               │
│ HITL Monitor      │ Integration Engine│ Module Manager             │
│ TrueSwarmSystem   │ Telemetry Learning│ Governance Framework       │
└─────────────────────────────────────────────────────────────────────┘
        ↓
┌─────────────────────────────────────────────────────────────────────┐
│                   INONI BUSINESS AUTOMATION                         │
├─────────────────────────────────────────────────────────────────────┤
│ Sales Engine      │ Marketing Engine  │ R&D Engine (Self-Improve)  │
│ Business Mgmt     │ Production Mgmt   │                            │
└─────────────────────────────────────────────────────────────────────┘
```

### Core Component Dependencies

#### 1. Murphy System 1.0 Runtime
**File:** `murphy_system_1.0_runtime.py`

**Dependencies:**
```
murphy_system_1.0_runtime.py
├── src.module_manager (ModuleManager)
├── src.modular_runtime (ModularRuntime)
├── universal_control_plane (UniversalControlPlane)
├── inoni_business_automation (InoniBusinessAutomation)
├── src.integration_engine.unified_engine (UnifiedIntegrationEngine)
├── two_phase_orchestrator (TwoPhaseOrchestrator)
├── src.form_intake.handlers (FormHandler)
├── src.confidence_engine.unified_confidence_engine (UnifiedConfidenceEngine)
├── src.execution_engine.integrated_form_executor (IntegratedFormExecutor)
├── src.learning_engine.integrated_correction_system (IntegratedCorrectionSystem)
├── src.supervisor_system.integrated_hitl_monitor (IntegratedHITLMonitor)
├── src.system_librarian (SystemLibrarian) [optional]
├── src.true_swarm_system (TrueSwarmSystem) [optional]
├── src.governance_framework.scheduler (GovernanceScheduler) [optional]
└── src.telemetry_learning.ingestion (TelemetryIngester, TelemetryBus) [optional]
```

**Provides:**
- Main system orchestration
- FastAPI REST API (30+ endpoints)
- Integration of all subsystems
- Session management
- Repository management

#### 2. Universal Control Plane
**File:** `universal_control_plane.py`

**Components:**
```
UniversalControlPlane
├── ControlTypeAnalyzer (determines automation type)
├── EngineRegistry (maps control types to engines)
├── SessionManager (isolates sessions)
└── Engines:
    ├── SensorEngine (read sensors)
    ├── ActuatorEngine (control actuators)
    ├── DatabaseEngine (query databases)
    ├── APIEngine (call external APIs)
    ├── ContentEngine (generate content)
    ├── CommandEngine (execute commands)
    └── AgentEngine (spawn agents)
```

**Control Types:**
1. SENSOR_ACTUATOR (factory/IoT)
2. CONTENT_API (publishing)
3. DATABASE_COMPUTE (data processing)
4. AGENT_REASONING (complex tasks)
5. COMMAND_SYSTEM (DevOps)
6. HYBRID (multiple types)

#### 3. Form Intake System
**Location:** `src/form_intake/`

**Components:**
```
form_intake/
├── schemas.py (5 form schemas with Pydantic validation)
│   ├── PlanUploadForm
│   ├── PlanGenerationForm
│   ├── TaskExecutionForm
│   ├── ValidationForm
│   └── CorrectionForm
├── handlers.py (form submission processing)
├── plan_decomposer.py (task decomposition)
├── plan_models.py (data models)
└── api.py (REST API endpoints)
```

**Data Flow:**
```
User Input → Form Validation → Plan Decomposition → Task Creation → Execution
```

#### 4. Confidence Engine
**Location:** `src/confidence_engine/`

**Components:**
```
confidence_engine/
├── unified_confidence_engine.py (main interface)
├── murphy_calculator.py (G/D/H formula)
├── uncertainty_calculator.py (UD/UA/UI/UR/UG)
├── murphy_gate.py (threshold validation)
├── murphy_validator.py (validation layer)
├── credential_verifier.py (credential checking)
├── external_validator.py (external validation)
├── performance_optimization.py (caching, parallel processing)
└── risk/ (risk management)
    ├── risk_database.py
    ├── pattern_matcher.py
    └── scoring_engine.py
```

**Confidence Calculation:**
```
G/D/H Formula (Original):
- G (Goodness): Quality of solution
- D (Domain): Domain expertise
- H (Hazard): Risk assessment

5D Uncertainty (Enhanced):
- UD (Uncertainty in Data): Historical data quality
- UA (Uncertainty in Assumptions): Domain expertise
- UI (Uncertainty in Information): Information quality
- UR (Uncertainty in Resources): Resource availability
- UG (Uncertainty in Goals): Goal clarity

Final Confidence = weighted_average(G/D/H, UD/UA/UI/UR/UG)
```

#### 5. Execution Engine
**Location:** `src/execution_engine/`

**Components:**
```
execution_engine/
├── integrated_form_executor.py (main executor)
├── form_executor.py (form-driven execution)
├── state_manager.py (execution state)
├── context.py (execution context)
├── phase_executor.py (7-phase execution)
└── resource_manager.py (resource allocation)
```

**7-Phase Execution:**
```
1. EXPAND    → Expand task into subtasks
2. TYPE      → Determine task types
3. ENUMERATE → List all actions
4. CONSTRAIN → Apply constraints
5. COLLAPSE  → Merge similar actions
6. BIND      → Bind to resources
7. EXECUTE   → Execute actions
```

#### 6. Learning Engine
**Location:** `src/learning_engine/`

**Components:**
```
learning_engine/
├── integrated_correction_system.py (main interface)
├── correction_capture.py (4 capture methods)
├── correction_storage.py (storage with 6 indexes)
├── correction_metadata.py (metadata enrichment)
├── pattern_extraction.py (5 pattern types)
├── feedback_system.py (7 feedback types)
├── training_data_transformer.py (feature engineering)
├── training_pipeline.py (model training)
├── shadow_agent.py (prediction system)
├── shadow_evaluation.py (performance evaluation)
└── shadow_monitoring.py (monitoring dashboard)
```

**Learning Flow:**
```
Correction → Capture → Validate → Extract Patterns → Train Shadow Agent → Improve
```

#### 7. Supervisor System
**Location:** `src/supervisor_system/`

**Components:**
```
supervisor_system/
├── integrated_hitl_monitor.py (main interface)
├── hitl_models.py (data models)
├── checkpoint_manager.py (checkpoint management)
├── intervention_system.py (intervention requests)
├── approval_workflow.py (approval process)
└── notification_system.py (notifications)
```

**HITL Checkpoints:**
1. HIGH_RISK_OPERATION
2. DATA_DELETION
3. ROLE_CHANGE
4. FINANCIAL_TRANSACTION
5. EXTERNAL_API_CALL
6. CONFIGURATION_CHANGE

#### 8. Integration Engine
**Location:** `src/integration_engine/`

**Components:**
```
integration_engine/
├── unified_engine.py (main orchestrator)
├── hitl_approval.py (human approval with LLM risk analysis)
├── capability_extractor.py (30+ capability types)
├── module_generator.py (generates Murphy modules)
├── agent_generator.py (generates Murphy agents)
└── safety_tester.py (5-category testing)
```

**Integration Flow:**
```
GitHub URL → Clone → Analyze → Extract Capabilities → Generate Module/Agent 
→ Test Safety → Request HITL Approval → Load if Approved
```

---

## Data Flows

### 1. Task Execution Flow

```
┌──────────────┐
│  User Input  │
└──────┬───────┘
       ↓
┌──────────────────────┐
│  Form Validation     │ (form_intake)
└──────┬───────────────┘
       ↓
┌──────────────────────┐
│  Plan Decomposition  │ (plan_decomposer)
└──────┬───────────────┘
       ↓
┌──────────────────────┐
│  Murphy Validation   │ (confidence_engine)
└──────┬───────────────┘
       ↓
┌──────────────────────┐
│  HITL Checkpoint?    │ (supervisor_system)
└──────┬───────────────┘
       ↓ (if approved)
┌──────────────────────┐
│  7-Phase Execution   │ (execution_engine)
└──────┬───────────────┘
       ↓
┌──────────────────────┐
│  Deliver Results     │
└──────┬───────────────┘
       ↓
┌──────────────────────┐
│  Capture Telemetry   │ (telemetry_learning)
└──────────────────────┘
```

### 2. Correction Learning Flow

```
┌──────────────┐
│  Correction  │
└──────┬───────┘
       ↓
┌──────────────────────┐
│  Capture Method      │ (interactive/batch/API/inline)
└──────┬───────────────┘
       ↓
┌──────────────────────┐
│  Validate Correction │
└──────┬───────────────┘
       ↓
┌──────────────────────┐
│  Extract Patterns    │ (pattern_extraction)
└──────┬───────────────┘
       ↓
┌──────────────────────┐
│  Transform to        │
│  Training Data       │ (training_data_transformer)
└──────┬───────────────┘
       ↓
┌──────────────────────┐
│  Train Shadow Agent  │ (training_pipeline)
└──────┬───────────────┘
       ↓
┌──────────────────────┐
│  Evaluate Performance│ (shadow_evaluation)
└──────┬───────────────┘
       ↓
┌──────────────────────┐
│  Deploy if Improved  │
└──────────────────────┘
```

### 3. Integration Flow

```
┌──────────────┐
│  GitHub URL  │
└──────┬───────┘
       ↓
┌──────────────────────┐
│  SwissKiss Loader    │ (clone & analyze)
└──────┬───────────────┘
       ↓
┌──────────────────────┐
│  Capability Extract  │ (capability_extractor)
└──────┬───────────────┘
       ↓
┌──────────────────────┐
│  Generate Module/    │
│  Agent               │ (module/agent_generator)
└──────┬───────────────┘
       ↓
┌──────────────────────┐
│  Safety Testing      │ (safety_tester)
└──────┬───────────────┘
       ↓
┌──────────────────────┐
│  LLM Risk Analysis   │ (hitl_approval)
└──────┬───────────────┘
       ↓
┌──────────────────────┐
│  HITL Approval       │ (human decision)
└──────┬───────────────┘
       ↓ (if approved)
┌──────────────────────┐
│  Load Module/Agent   │
└──────────────────────┘
```

---

## Integration Points

### Internal Integration Points

1. **Module Manager ↔ All Subsystems**
   - Dynamic module loading
   - Module registration
   - Dependency resolution

2. **Confidence Engine ↔ Execution Engine**
   - Pre-execution validation
   - Murphy Gate threshold checking
   - Confidence scoring

3. **Learning Engine ↔ Execution Engine**
   - Correction capture during execution
   - Shadow agent predictions
   - Performance feedback

4. **Supervisor System ↔ Execution Engine**
   - HITL checkpoint triggering
   - Intervention requests
   - Approval workflows

5. **Telemetry Learning ↔ All Subsystems**
   - Event capture
   - Metric collection
   - Learning data aggregation

### External Integration Points

1. **LLM APIs**
   - Groq (primary)
   - OpenAI (optional)
   - Anthropic (optional)
   - Local models (fallback)

2. **Database**
   - PostgreSQL (primary storage)
   - SQLAlchemy ORM
   - Alembic migrations

3. **Cache & Queue**
   - Redis (caching)
   - Celery (task queue)
   - Redis (message broker)

4. **Monitoring**
   - Prometheus (metrics)
   - Grafana (dashboards)
   - Custom metrics exporters

5. **Cloud Providers**
   - AWS (S3, EC2, Lambda)
   - GCP (Storage, Compute)
   - Azure (Blob, VMs)

6. **External Services**
   - Stripe (payments)
   - Twilio (communications)
   - SendGrid (email)
   - GitHub (version control)

---

## System Layers

### Layer 1: Presentation Layer
- **UI Components:** terminal_integrated.html, murphy_ui_integrated.html
- **REST API:** FastAPI endpoints (30+)
- **CLI:** Command-line interface

### Layer 2: Application Layer
- **Runtime Orchestrators:** murphy_system_1.0_runtime.py, murphy_final_runtime.py
- **Business Logic:** Inoni Business Automation
- **Control Plane:** Universal Control Plane

### Layer 3: Service Layer
- **Form Intake:** Form processing and validation
- **Execution Engine:** Task execution
- **Learning Engine:** Correction capture and learning
- **Supervisor System:** Oversight and HITL
- **Integration Engine:** External system integration

### Layer 4: Core Layer
- **Confidence Engine:** Validation and uncertainty
- **Module Manager:** Dynamic module loading
- **Governance Framework:** Authority-based scheduling
- **Telemetry Learning:** Event capture and learning

### Layer 5: Infrastructure Layer
- **Database:** PostgreSQL
- **Cache:** Redis
- **Queue:** Celery
- **Monitoring:** Prometheus/Grafana
- **Container:** Docker/Kubernetes

---

## Execution Flows

### Two-Phase Execution Model

#### Phase 1: Generative Setup (Carving from Infinity)

```
1. Receive Request
   ↓
2. Analyze Request (determine automation type)
   ↓
3. Determine Control Type (sensor/actuator, content/API, etc.)
   ↓
4. Select Required Engines (only load what's needed)
   ↓
5. Discover Constraints (APIs, rate limits, regulations)
   ↓
6. Compile ExecutionPacket (immutable instruction bundle)
   ↓
7. Create Session (isolated execution environment)
```

#### Phase 2: Production Execution (Automated Repeat)

```
1. Load Session Configuration
   ↓
2. Load Selected Engines
   ↓
3. Execute Actions (with appropriate engines)
   ↓
4. Produce Deliverables (URLs, files, reports)
   ↓
5. Store Execution History
   ↓
6. Learn from Execution (capture telemetry)
   ↓
7. Repeat on Schedule/Trigger
```

### 7-Phase Task Execution

```
Phase 1: EXPAND
├── Input: High-level task
├── Process: Decompose into subtasks
└── Output: Task tree

Phase 2: TYPE
├── Input: Task tree
├── Process: Classify each task
└── Output: Typed tasks

Phase 3: ENUMERATE
├── Input: Typed tasks
├── Process: List all required actions
└── Output: Action list

Phase 4: CONSTRAIN
├── Input: Action list
├── Process: Apply constraints (Murphy Gate)
└── Output: Constrained actions

Phase 5: COLLAPSE
├── Input: Constrained actions
├── Process: Merge similar actions
└── Output: Optimized actions

Phase 6: BIND
├── Input: Optimized actions
├── Process: Bind to resources
└── Output: Executable actions

Phase 7: EXECUTE
├── Input: Executable actions
├── Process: Execute with engines
└── Output: Results + telemetry
```

---

## Component Interaction Patterns

### 1. Request-Response Pattern
- **Used by:** REST API endpoints
- **Flow:** Client → API → Service → Response

### 2. Event-Driven Pattern
- **Used by:** Telemetry Learning, Monitoring
- **Flow:** Event → Bus → Subscribers → Actions

### 3. Pipeline Pattern
- **Used by:** 7-Phase Execution, Correction Learning
- **Flow:** Input → Stage 1 → Stage 2 → ... → Output

### 4. Observer Pattern
- **Used by:** Supervisor System, HITL Monitor
- **Flow:** Subject → Notify → Observers → React

### 5. Strategy Pattern
- **Used by:** Universal Control Plane (engine selection)
- **Flow:** Context → Select Strategy → Execute

### 6. Factory Pattern
- **Used by:** Module Manager, Agent Generator
- **Flow:** Request → Factory → Create Instance

---

## Next Steps (Phase 2)

1. **Dependency Graph Creation** - Visualize all import dependencies
2. **Circular Dependency Detection** - Identify and resolve circular imports
3. **Data Flow Validation** - Verify data flows match intended architecture
4. **Integration Point Testing** - Test all external integrations
5. **Performance Bottleneck Identification** - Identify slow components
6. **Security Boundary Analysis** - Verify security at integration points

---

**Document Status:** DRAFT - Phase 1 Discovery  
**Last Updated:** February 4, 2025  
**Next Review:** After dependency analysis completion