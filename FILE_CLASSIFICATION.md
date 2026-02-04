# Murphy System 1.0 - File Classification

**Date:** February 4, 2025  
**Version:** 1.0.0  
**Audit Phase:** 1 - Discovery & Inventory  
**Owner:** Inoni Limited Liability Company

---

## Classification Summary

| Category | Subcategory | Count | Purpose |
|----------|-------------|-------|---------|
| **ACTIVE** | Entry Points | 7 | Main runtime executables |
| | Core Systems | 326 | Core system modules (src/) |
| | Bots | 101 | Specialized bot implementations |
| | UI | 5 | User interface files |
| **TEST** | Unit Tests | 77 | Unit test files |
| | Integration Tests | 6 | Integration test files |
| | E2E Tests | 5 | End-to-end test files |
| | System Tests | 1 | System-level test files |
| **CONFIG** | Requirements | 3 | Python dependency files |
| | Scripts | 2 | Startup/utility scripts |
| | Other | 5 | Configuration files |
| **DOCS** | API | 5 | API documentation |
| | Architecture | 1 | Architecture documentation |
| | User Guides | 3 | User documentation |
| | Other | 76 | Other documentation |
| **UNCLEAR** | TypeScript | 467 | Bot TypeScript implementations |
| | Python | 15 | Utility/packaging scripts |
| | Other | 2 | LICENSE, archives |

**Total Files:** 1,107

---

## ACTIVE Files (439 files)

### Entry Points (7 files)

Primary runtime executables that serve as system entry points:

| File | Lines | Purpose | Status |
|------|-------|---------|--------|
| murphy_system_1.0_runtime.py | 544 | Main Murphy System 1.0 runtime | PRIMARY |
| murphy_final_runtime.py | 642 | Alternative runtime orchestrator | ALTERNATIVE |
| murphy_complete_backend.py | 655 | Complete backend API server | ALTERNATIVE |
| murphy_complete_backend_extended.py | 499 | Extended backend endpoints | EXTENSION |
| universal_control_plane.py | 641 | Universal automation control plane | COMPONENT |
| inoni_business_automation.py | 737 | Business automation engines | COMPONENT |
| two_phase_orchestrator.py | 569 | Two-phase execution system | COMPONENT |

**Recommendation:** Clarify which is the primary production entry point.

### Core Systems (326 files in src/)

Organized by subsystem:

#### Form Intake (6 files)
- `src/form_intake/__init__.py`
- `src/form_intake/api.py` - REST API endpoints (291 lines)
- `src/form_intake/handlers.py` - Form submission processing (15,244 lines)
- `src/form_intake/plan_decomposer.py` - Task decomposition (15,467 lines)
- `src/form_intake/plan_models.py` - Data models (12,705 lines)
- `src/form_intake/schemas.py` - Pydantic schemas (18,477 lines)

#### Confidence Engine (24 files)
- `src/confidence_engine/unified_confidence_engine.py` - Main interface (7,368 lines)
- `src/confidence_engine/murphy_calculator.py` - G/D/H formula (8,044 lines)
- `src/confidence_engine/uncertainty_calculator.py` - 5D uncertainty (19,306 lines)
- `src/confidence_engine/murphy_gate.py` - Threshold validation (8,514 lines)
- `src/confidence_engine/murphy_validator.py` - Validation layer (11,471 lines)
- `src/confidence_engine/credential_verifier.py` - Credential checking (16,053 lines)
- `src/confidence_engine/api_server.py` - REST API (578 lines)
- ... and 17 more files

#### Execution Engine (9 files)
- `src/execution_engine/integrated_form_executor.py` - Main executor
- `src/execution_engine/form_executor.py` - Form-driven execution
- `src/execution_engine/state_manager.py` - Execution state
- `src/execution_engine/context.py` - Execution context
- `src/execution_engine/phase_executor.py` - 7-phase execution
- ... and 4 more files

#### Learning Engine (23 files)
- `src/learning_engine/integrated_correction_system.py` - Main interface
- `src/learning_engine/correction_capture.py` - Correction recording (21,616 lines)
- `src/learning_engine/correction_storage.py` - Storage system (19,786 lines)
- `src/learning_engine/pattern_extraction.py` - Pattern mining (30,693 lines)
- `src/learning_engine/feedback_system.py` - Feedback collection (20,849 lines)
- `src/learning_engine/shadow_agent.py` - Prediction system (11,992 lines)
- ... and 17 more files

#### Supervisor System (9 files)
- `src/supervisor_system/integrated_hitl_monitor.py` - Main interface
- `src/supervisor_system/hitl_models.py` - Data models
- `src/supervisor_system/checkpoint_manager.py` - Checkpoint management
- `src/supervisor_system/intervention_system.py` - Intervention requests
- ... and 5 more files

#### Integration Engine (7 files)
- `src/integration_engine/unified_engine.py` - Main orchestrator (19,882 lines)
- `src/integration_engine/hitl_approval.py` - HITL approval (16,888 lines)
- `src/integration_engine/capability_extractor.py` - Capability extraction (10,478 lines)
- `src/integration_engine/module_generator.py` - Module generation (6,269 lines)
- `src/integration_engine/agent_generator.py` - Agent generation (4,594 lines)
- `src/integration_engine/safety_tester.py` - Safety testing (10,108 lines)
- `src/integration_engine/__init__.py`

#### Other Core Systems (247 files)
- adapter_framework/ (9 files) - Sensor/actuator adapters
- autonomous_systems/ (4 files) - Autonomous scheduling
- base_governance_runtime/ (7 files) - Governance runtime
- bridge_layer/ (6 files) - Integration bridge
- comms/ (6 files) - Communication systems
- compute_plane/ (16 files) - Computational analysis
- control_plane/ (3 files) - Execution packet system
- execution/ (2 files) - Document generation
- execution_orchestrator/ (10 files) - Orchestration
- execution_packet_compiler/ (9 files) - Packet compilation
- gate_synthesis/ (8 files) - Gate generation
- governance_framework/ (7 files) - Authority-based scheduling
- integrations/ (3 files) - External integrations
- librarian/ (5 files) - Knowledge management
- module_compiler/ (17 files) - Module compilation
- neuro_symbolic_models/ (7 files) - Hybrid AI models
- org_compiler/ (9 files) - Organization compilation
- recursive_stability_controller/ (11 files) - Stability control
- security_plane/ (11 files) - Security and authentication
- supervisor/ (2 files) - Supervisor schemas
- synthetic_failure_generator/ (11 files) - Failure testing
- telemetry_learning/ (8 files) - Telemetry and learning

#### Root-Level Core Files (78 files)
Large, complex modules in src/ root:
- `enhanced_local_llm.py` (1,729 lines) - Local LLM integration
- `unified_mfgc.py` (1,535 lines) - Manufacturing control
- `system_integrator.py` (1,478 lines) - System integration
- `true_swarm_system.py` (1,111 lines) - Agent swarm system
- `constraint_system.py` (947 lines) - Constraint management
- `domain_gate_generator.py` (940 lines) - Domain gate generation
- `domain_engine.py` (919 lines) - Domain processing
- ... and 71 more files

### Bots (101 files in bots/)

Specialized bot implementations (Python files only):

**Major Bots:**
- `memory_manager_bot.py` (499 lines) - Memory management
- `rubixcube_bot.py` (227 lines) - Probabilistic reasoning
- `swisskiss_loader.py` (223 lines) - GitHub repository loading
- `json_bot.py` (208 lines) - JSON processing
- `cad_bot.py` (191 lines) - CAD operations
- `feedback_bot.py` (175 lines) - Feedback collection
- `polyglot_bot.py` (165 lines) - Multi-language support
- `scheduler_bot.py` (159 lines) - Task scheduling
- `librarian_bot.py` (151 lines) - Knowledge management
- `key_manager_bot.py` (133 lines) - Key management
- `Ghost_Controller_Bot.py` (131 lines) - Desktop automation
- `commissioning_bot.py` (130 lines) - System commissioning
- ... and 89 more bots

**Bot Categories:**
- Knowledge Management: librarian_bot, memory_manager_bot
- Optimization: optimization_bot, efficiency_optimizer
- Engineering: engineering_bot, cad_bot, coding_bot
- Communication: comms_hub_bot, matrix_client
- Analysis: analysisbot, anomaly_watcher_bot
- Visualization: visualization_bot
- Security: security_bot, key_manager_bot
- Scheduling: scheduler_bot, task_graph_executor
- And 20+ more specialized bots

### UI Files (5 files)

User interface components:
- `terminal_integrated.html` - Terminal-style command interface
- `murphy_ui_integrated.html` - Integrated web UI
- `terminal_enhanced.html` - Enhanced terminal UI
- `terminal_worker.html` - Worker terminal UI
- `terminal_architect.html` - Architect terminal UI

---

## TEST Files (89 files)

### Unit Tests (77 files in tests/)

Core functionality tests:
- `test_basic_imports.py` - Import verification
- `test_correction_loop.py` - Correction system tests
- `test_execution_orchestrator.py` - Orchestrator tests
- `test_learning_engine.py` - Learning engine tests
- `test_confidence_engine.py` - Confidence engine tests
- `test_supervisor_loop.py` - Supervisor tests
- `test_state_machine.py` - State machine tests
- `test_risk_manager.py` - Risk management tests
- `test_adapter_framework.py` - Adapter tests
- `test_authority_gate.py` - Authority gate tests
- ... and 67 more unit tests

### Integration Tests (6 files in tests/integration/)

System integration tests:
- `test_murphy_core_integration.py` - Core integration
- `test_phase1_murphy_integration.py` - Phase 1 integration
- `test_phase2_enterprise_integration.py` - Phase 2 integration
- `test_enterprise_system_integration.py` - Enterprise integration
- `test_phase1_simple.py` - Simple integration
- `test_integration_corrected.py` - Corrected integration

### E2E Tests (5 files in tests/e2e/)

End-to-end workflow tests:
- `test_phase3_end_to_end.py` - Complete workflow
- `test_phase3_final.py` - Final phase testing
- `test_phase3_manufacturing_disaster.py` - Disaster recovery
- `test_phase3_sync.py` - Synchronization testing
- `test_phase3_simple.py` - Simple E2E test

### System Tests (1 file in tests/system/)

System-level tests:
- (1 system test file)

---

## CONFIG Files (10 files)

### Requirements (3 files)

Python dependency specifications:
- `requirements_murphy_1.0.txt` - Complete Murphy 1.0 dependencies
- `requirements.txt` - Base requirements
- (1 additional requirements file)

### Scripts (2 files)

Startup and utility scripts:
- `start_murphy_1.0.sh` - Linux/Mac startup script
- `start_murphy_1.0.bat` - Windows startup script

### Other Configuration (5 files)

Various configuration files:
- JSON, YAML, TOML configuration files
- (5 configuration files total)

---

## DOCS Files (85 files)

### API Documentation (5 files in documentation/api/)

API reference and examples:
- `API_OVERVIEW.md` - API overview
- `API_EXAMPLES.md` - Usage examples
- `ENDPOINTS.md` - Endpoint reference
- `AUTHENTICATION.md` - Authentication guide
- `EXECUTION_ENGINES_API_REFERENCE.md` - Execution engine API

### Architecture Documentation (1 file in documentation/architecture/)

System architecture:
- `ARCHITECTURE_OVERVIEW.md` - Architecture overview

### User Guides (3 files in documentation/user_guides/)

User documentation:
- `USER_GUIDE.md` - User guide
- `TROUBLESHOOTING.md` - Troubleshooting guide
- `CONTRIBUTING.md` - Contribution guidelines

### Other Documentation (76 files)

Distributed across:
- Root-level documentation (25 files)
  - README_MURPHY_1.0.md, MURPHY_SYSTEM_1.0_SPECIFICATION.md
  - API_DOCUMENTATION.md, DEPLOYMENT_GUIDE.md
  - INTEGRATION_ENGINE_COMPLETE.md, etc.
- documentation/bots/ - Bot documentation
- documentation/components/ - Component documentation
- documentation/deployment/ - Deployment guides
- documentation/domain_system/ - Domain system docs
- documentation/enterprise/ - Enterprise features
- documentation/getting_started/ - Quick start guides
- documentation/legal/ - Legal documents
- documentation/reference/ - Reference materials
- documentation/testing/ - Testing guides

---

## UNCLEAR Files (484 files)

### TypeScript Files (467 files)

Bot implementations in TypeScript:
- **Location:** bots/*/internal/*.ts, bots/*/*.ts
- **Purpose:** TypeScript implementations of bot logic
- **Examples:**
  - `bots/analysisbot/analysisbot.ts`
  - `bots/librarian_bot/internal/fetch/fetcher.ts`
  - `bots/ghost_controller_bot/internal/kaia/kaia.ts`
  - And 464 more TypeScript files

**Status:** These are legitimate bot implementations but were initially categorized as UNCLEAR because they're TypeScript, not Python. Should be reclassified as ACTIVE/bots.

### Python Utility Files (15 files)

Utility and packaging scripts:
- `create_murphy_1.0_package.py` - Package creation script
- `test_integration_engine.py` - Integration engine test
- `setup.py` - Python package setup
- And 12 more utility scripts

**Status:** Should be reclassified based on purpose:
- Packaging scripts → CONFIG
- Test files → TEST
- Utility scripts → ACTIVE or CONFIG

### Other Files (2 files)

- `LICENSE` - Apache License 2.0
- `bots/bots.zip` - Bot archive

**Status:**
- LICENSE → CONFIG
- bots.zip → Archive (investigate if needed)

---

## Dependency Relationships

### High-Level Dependencies

```
Entry Points
├── murphy_system_1.0_runtime.py
│   ├── Depends on: All core systems
│   └── Provides: Main runtime, FastAPI app
│
├── murphy_final_runtime.py
│   ├── Depends on: Core systems (subset)
│   └── Provides: Alternative runtime, Flask app
│
└── murphy_complete_backend.py
    ├── Depends on: LLM integration, core systems
    └── Provides: Backend API, LLM routing

Core Systems
├── form_intake → confidence_engine
├── confidence_engine → execution_engine
├── execution_engine → learning_engine
├── learning_engine → shadow_agent
├── supervisor_system → execution_engine
└── integration_engine → module_manager

Bots
├── Independent modules
├── Loaded dynamically by module_manager
└── Can depend on core systems
```

### Import Patterns

**murphy_system_1.0_runtime.py imports:**
- Standard library: sys, os, pathlib, typing, datetime, logging, asyncio
- Local modules: src.*, universal_control_plane, inoni_business_automation, two_phase_orchestrator
- Third-party: FastAPI (optional)

**murphy_final_runtime.py imports:**
- Standard library: sys, os, typing, datetime, logging
- Third-party: Flask, flask_cors, flask_socketio
- No local module imports (self-contained)

**murphy_complete_backend.py imports:**
- Standard library: sys, os, typing, datetime, json, asyncio
- Third-party: Flask, groq, anthropic
- No local module imports (self-contained)

---

## Files Requiring Investigation

### Priority 1: Entry Point Clarification

**Question:** Which is the primary production entry point?
- murphy_system_1.0_runtime.py (most comprehensive)
- murphy_final_runtime.py (alternative)
- murphy_complete_backend.py (backend-focused)

**Action:** Document intended use case for each entry point.

### Priority 2: TypeScript Bot Files

**Question:** Are all 467 TypeScript files actively used?
- Most bot directories contain TypeScript implementations
- Need to verify if these are legacy or current

**Action:** Audit bot TypeScript files for active use.

### Priority 3: Empty Bot Directories

**Question:** Why are most bot directories empty (0 Python files)?
- 35 bot directories exist
- Only a few contain Python files
- Most contain TypeScript files

**Action:** Document bot architecture (Python vs. TypeScript).

### Priority 4: Multiple Runtime Files

**Question:** Why multiple runtime implementations?
- murphy_system_1.0_runtime.py (FastAPI)
- murphy_final_runtime.py (Flask)
- murphy_complete_backend.py (Flask)

**Action:** Document migration path or intended use cases.

### Priority 5: Utility Script Classification

**Question:** How should utility scripts be classified?
- create_murphy_1.0_package.py
- test_integration_engine.py
- setup.py

**Action:** Reclassify based on purpose and usage.

---

## Recommendations

### Immediate Actions

1. **Clarify Primary Entry Point** - Document which runtime is production-ready
2. **Reclassify TypeScript Files** - Move 467 TypeScript files to ACTIVE/bots
3. **Reclassify Utility Scripts** - Properly categorize 15 Python utility files
4. **Document Bot Architecture** - Explain Python vs. TypeScript bot structure
5. **Archive Unused Code** - Identify and archive deprecated entry points

### Phase 2 Actions

1. **Dependency Analysis** - Map all import dependencies
2. **Circular Dependency Detection** - Identify and resolve circular imports
3. **Dead Code Detection** - Find unused functions and modules
4. **Test Coverage Analysis** - Measure test coverage percentage
5. **Documentation Audit** - Verify all components are documented

---

## File Classification Statistics

| Category | Files | Percentage |
|----------|-------|------------|
| ACTIVE | 439 | 39.7% |
| TEST | 89 | 8.0% |
| CONFIG | 10 | 0.9% |
| DOCS | 85 | 7.7% |
| UNCLEAR | 484 | 43.7% |
| **TOTAL** | **1,107** | **100%** |

**Note:** After reclassification of TypeScript files, ACTIVE will be ~906 files (81.8%) and UNCLEAR will be ~17 files (1.5%).

---

**Document Status:** DRAFT - Phase 1 Discovery  
**Last Updated:** February 4, 2025  
**Next Review:** After reclassification of UNCLEAR files