# Murphy System - Module Connection Map

## DISCOVERED MODULES & THEIR PURPOSES

### 1. FORM INTAKE (6 files)
**Purpose:** Handle form submissions and convert to structured plans

**Key Classes:**
- `PlanUploadFormHandler` - Handles uploaded plans
- `PlanGenerationFormHandler` - Generates plans from descriptions
- `TaskExecutionFormHandler` - Handles task execution requests
- `ValidationFormHandler` - Validates forms
- `CorrectionFormHandler` - Handles corrections
- `PlanDecomposer` - Breaks plans into tasks
- `FormHandlerRegistry` - Registers all form handlers

**Data Models:**
- `Plan`, `Task`, `Dependency`, `ValidationCriterion`, `HumanCheckpoint`
- `PlanUploadForm`, `PlanGenerationForm`, `TaskExecutionForm`, `ValidationForm`, `CorrectionForm`

### 2. CONFIDENCE ENGINE (17 files)
**Purpose:** Calculate confidence scores and validate operations

**Key Classes:**
- `UnifiedConfidenceEngine` - **INTEGRATION CLASS** (combines G/D/H with UD/UA/UI/UR/UG)
- `MurphyGate` - Decision gate based on confidence thresholds
- `MurphyValidator` - Validates operations using Murphy scores
- `UncertaintyCalculator` - Calculates 5D uncertainty (UD/UA/UI/UR/UG)
- `ConfidenceCalculator` - Calculates G/D/H confidence
- `CredentialVerifier` - Verifies credentials
- `ExternalValidator` - Validates against external sources
- `PerformanceOptimizationSystem` - Caching and optimization

### 3. EXECUTION ENGINE (9 files)
**Purpose:** Execute tasks and manage workflow

**Key Classes:**
- `IntegratedFormExecutor` - **INTEGRATION CLASS** (form-driven execution)
- `FormExecutor` - Executes form-based tasks
- `TaskExecutor` - Executes individual tasks
- `WorkflowOrchestrator` - Orchestrates multi-task workflows
- `DecisionEngine` - Makes execution decisions
- `StateManager` - Manages execution state
- `ExecutionContext` - Tracks execution context

### 4. SUPERVISOR SYSTEM (9 files)
**Purpose:** Supervise execution and handle corrections

**Key Classes:**
- `IntegratedHITLMonitor` - **INTEGRATION CLASS** (human-in-the-loop)
- `HITLMonitor` - Monitors for human intervention needs
- `CorrectionLoop` - Handles correction feedback
- `AssumptionManagement` - Manages assumptions
- `AntiRecursion` - Prevents infinite loops
- `SupervisorLoop` - Main supervision loop

### 5. LEARNING ENGINE (22 files)
**Purpose:** Learn from corrections and improve over time

**Key Classes:**
- `IntegratedCorrectionSystem` - **INTEGRATION CLASS** (connects corrections to learning)
- `CorrectionCapture` - Captures corrections
- `CorrectionStorage` - Stores corrections
- `CorrectionMetadata` - Enriches corrections with metadata
- `PatternExtraction` - Extracts patterns from corrections
- `FeedbackSystem` - Collects human feedback
- `ShadowAgent` - Learns from corrections
- `TrainingPipeline` - Trains models
- `FeatureEngineering` - Engineers features
- `ModelRegistry` - Manages trained models
- `LearningEngine` - Main learning orchestrator

### 6. LIBRARIAN (5 files)
**Purpose:** Knowledge management and semantic search

**Key Classes:**
- `LibrarianModule` - Main librarian interface
- `KnowledgeBase` - Stores knowledge
- `DocumentManager` - Manages documents
- `SemanticSearch` - Semantic search capabilities

## CONNECTION POINTS (What Connects to What)

### Flow 1: Form Submission → Execution
```
User submits form
  ↓
form_intake/handlers.py (FormHandlerRegistry)
  ↓
form_intake/plan_decomposer.py (PlanDecomposer) - breaks into tasks
  ↓
execution_engine/integrated_form_executor.py (IntegratedFormExecutor)
  ↓
execution_engine/task_executor.py (TaskExecutor)
```

### Flow 2: Confidence Validation
```
Task ready to execute
  ↓
confidence_engine/unified_confidence_engine.py (UnifiedConfidenceEngine)
  ↓
confidence_engine/murphy_gate.py (MurphyGate) - checks thresholds
  ↓
If PASS → execute
If FAIL → supervisor_system/hitl_monitor.py (request human intervention)
```

### Flow 3: Correction & Learning
```
Human provides correction
  ↓
learning_engine/correction_capture.py (CorrectionCapture)
  ↓
learning_engine/correction_storage.py (CorrectionStorage)
  ↓
learning_engine/pattern_extraction.py (PatternExtraction)
  ↓
learning_engine/training_pipeline.py (TrainingPipeline)
  ↓
learning_engine/shadow_agent.py (ShadowAgent) - learns and improves
```

### Flow 4: Knowledge Management
```
System needs information
  ↓
librarian/librarian_module.py (LibrarianModule)
  ↓
librarian/semantic_search.py (SemanticSearch)
  ↓
librarian/knowledge_base.py (KnowledgeBase)
```

## INTEGRATION CLASSES (The Bridges)

These 4 classes were created to connect the systems:

1. **UnifiedConfidenceEngine** (`confidence_engine/unified_confidence_engine.py`)
   - Merges original G/D/H with new UD/UA/UI/UR/UG
   - Used by: MurphyGate, MurphyValidator

2. **IntegratedFormExecutor** (`execution_engine/integrated_form_executor.py`)
   - Connects form intake to execution
   - Uses: PlanDecomposer, TaskExecutor, UnifiedConfidenceEngine

3. **IntegratedHITLMonitor** (`supervisor_system/integrated_hitl_monitor.py`)
   - Connects supervision to human intervention
   - Uses: HITLMonitor, CorrectionCapture

4. **IntegratedCorrectionSystem** (`learning_engine/integrated_correction_system.py`)
   - Connects corrections to learning
   - Uses: CorrectionCapture, PatternExtraction, TrainingPipeline

## WHAT'S CONNECTED ✅

- ✅ Form intake → Execution engine
- ✅ Confidence engine → Murphy gate
- ✅ Supervisor → HITL monitor
- ✅ Corrections → Learning engine
- ✅ Learning → Shadow agent

## WHAT'S MISSING ❌

### 1. Authentication & User Management
- **Status:** ✅ FOUND! `security_plane/authentication.py`
- **Classes:** `HumanAuthenticator`, `Identity`, `AuthenticationSession`, `ContextualVerification`
- **Need:** Connect to backend API and UI
- **Impact:** Can enable user accounts and sessions

### 2. Session Management
- **Status:** NOT FOUND
- **Need:** Session creation, isolation, tracking
- **Impact:** Librarian can't be session-partitioned

### 3. Universal Question Framework
- **Status:** NOT FOUND
- **Need:** Ambiguity removal question system
- **Impact:** Can't do intelligent onboarding

### 4. Agent Carving System
- **Status:** NOT FOUND
- **Need:** Dynamic agent generation from questions
- **Impact:** Can't create function-specific agents

### 5. Instruments/Gates/Sensors
- **Status:** ✅ FOUND! `gate_synthesis/` module
- **Classes:** `GateGenerator`, `GateLifecycleManager`, `FailureModeEnumerator`, `MurphyProbabilityEstimator`
- **Features:** Dynamic gate generation, failure mode analysis, risk assessment
- **Need:** Connect to session management
- **Impact:** Can create dynamic gates and sensors per session

### 6. Repository/Instance Structure
- **Status:** NOT FOUND
- **Need:** Containers for automations
- **Impact:** Can't organize multiple automations per user

### 7. Backend API Exposure
- **Status:** PARTIAL
- **Need:** Expose all modules via murphy_complete_integrated.py
- **Impact:** UI can't access all functionality

## BACKEND API ENDPOINTS (murphy_complete_integrated.py)

### Currently Exposed (50+ endpoints):
- /api/status - System status
- /api/initialize - System initialization
- /api/llm/generate - LLM generation
- /api/librarian/ask - Librarian queries
- /api/librarian/store-commands - Store commands
- /api/librarian/search-commands - Search commands
- /api/librarian/generate-command - Generate commands
- /api/command/execute - Execute commands
- /api/artifacts/generate - Generate artifacts
- /api/swarm/task/create - Create swarm tasks
- /api/workflow/create - Create workflows
- /api/monitoring/health - Health checks
- /api/automation/* - Automation management (9 endpoints)
- /api/business/* - Business operations
- /api/production/* - Production setup
- /api/payment/* - Payment processing (7 endpoints)
- /api/download/* - Download management (5 endpoints)
- /api/runtime/* - Runtime processing (4 endpoints)

### Missing from API (Need to Expose):
- Form intake endpoints (form submission, plan decomposition)
- Confidence engine endpoints (uncertainty calculation, Murphy gate)
- Execution engine endpoints (task execution, workflow orchestration)
- Supervisor endpoints (HITL, corrections)
- Learning engine endpoints (correction capture, pattern extraction)
- Gate synthesis endpoints (gate generation, failure modes)
- Security endpoints (authentication, access control)
- Autonomous systems endpoints (scheduling, risk management)