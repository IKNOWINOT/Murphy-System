# Murphy System 1.0 - File Classification

**Created:** February 4, 2026  
**Version:** 1.0.0  
**Total Files Analyzed:** 538 Python files, 254 directories

---

## Classification Legend

| Category | Description |
|----------|-------------|
| **ACTIVE** | Currently used in production/main execution flow |
| **LEGACY** | Outdated but potentially referenced elsewhere |
| **TEST** | Test files, fixtures, and test utilities |
| **CONFIG** | Configuration, environment, and settings files |
| **DOCS** | Documentation files (markdown) |
| **UNCLEAR** | Requires investigation or clarification |

---

## Table of Contents

1. [Entry Points](#entry-points)
2. [Core System Files](#core-system-files)
3. [Source Directory (src/)](#source-directory-src)
4. [Bot System (bots/)](#bot-system-bots)
5. [Test Suite (tests/)](#test-suite-tests)
6. [Documentation](#documentation)
7. [Scripts and Utilities](#scripts-and-utilities)
8. [Summary Statistics](#summary-statistics)

---

## Entry Points

### PRIMARY ENTRY POINTS (ACTIVE)

| File | Purpose | Classification | Dependencies |
|------|---------|----------------|--------------|
| `murphy_system_1.0_runtime.py` | Main entry point for Murphy System 1.0. Integrates all components (Universal Control Plane, Business Automation, Two-Phase Orchestrator, Integration Engine). | **ACTIVE** | FastAPI, all core modules |
| `murphy_complete_backend_extended.py` | Extended REST API backend (port 6666). Adds Phase 1-5 form endpoints to original backend. | **ACTIVE** | murphy_complete_backend.py, form handlers |
| `universal_control_plane.py` | Modular control plane with 7 engines (Sensor, Actuator, Database, API, Content, Command, Agent). | **ACTIVE** | Engine modules, module_manager |
| `inoni_business_automation.py` | Business automation system with 5 engines (Sales, Marketing, R&D, Business Management, Production). | **ACTIVE** | External APIs (Stripe, Twilio, etc.) |
| `two_phase_orchestrator.py` | Two-phase execution orchestrator (Generative Setup → Production Execution). | **ACTIVE** | Universal Control Plane, session manager |

### SECONDARY ENTRY POINTS (ACTIVE)

| File | Purpose | Classification |
|------|---------|----------------|
| `murphy_complete_backend.py` | Original backend implementation (imported by extended backend). | **ACTIVE** |
| `murphy_final_runtime.py` | Alternative runtime entry point. | **ACTIVE** |
| `start_murphy_1.0.sh` | Linux/Mac startup script. | **ACTIVE** |
| `start_murphy_1.0.bat` | Windows startup script. | **ACTIVE** |

### PACKAGING AND TESTING (ACTIVE)

| File | Purpose | Classification |
|------|---------|----------------|
| `create_murphy_1.0_package.py` | Package builder for distribution. | **ACTIVE** |
| `test_integration_engine.py` | Integration testing for the integration engine. | **TEST** |
| `setup.py` | Python package configuration (mfgc-ai v0.1.0). | **CONFIG** |

---

## Core System Files

### TOP-LEVEL PYTHON FILES (10 files)

| File | Lines | Purpose | Classification |
|------|-------|---------|----------------|
| `murphy_system_1.0_runtime.py` | ~500 | Main system runtime | **ACTIVE** |
| `murphy_complete_backend_extended.py` | ~450 | Extended REST API | **ACTIVE** |
| `murphy_complete_backend.py` | ~1200 | Original REST API | **ACTIVE** |
| `universal_control_plane.py` | ~800 | Universal control plane | **ACTIVE** |
| `inoni_business_automation.py` | ~900 | Business automation | **ACTIVE** |
| `two_phase_orchestrator.py` | ~600 | Execution orchestrator | **ACTIVE** |
| `murphy_final_runtime.py` | ~400 | Alternative runtime | **ACTIVE** |
| `create_murphy_1.0_package.py` | ~300 | Package builder | **ACTIVE** |
| `test_integration_engine.py` | ~250 | Integration tests | **TEST** |
| `setup.py` | ~56 | Package setup | **CONFIG** |

**Total Lines:** ~38,717 in src/*.py files

---

## Source Directory (src/)

### Execution Engine (src/execution_engine/) - **ACTIVE**

Critical path for task execution and orchestration.

| File | Purpose | Dependencies |
|------|---------|--------------|
| `__init__.py` | Module initialization | - |
| `decision_engine.py` | Decision-making logic for task routing | LLM integration |
| `execution_context.py` | Execution context management | State manager |
| `form_execution_models.py` | Pydantic models for form execution | Pydantic |
| `form_executor.py` | Form-based task executor | Confidence engine |
| `integrated_form_executor.py` | **Primary executor** integrating all form types | All form handlers |
| `state_manager.py` | State machine for execution flow | State machine |
| `task_executor.py` | Low-level task execution | Engine modules |
| `workflow_orchestrator.py` | Workflow orchestration and dependency management | Task executor |

**Classification:** All **ACTIVE** - Core execution path

### Learning Engine (src/learning_engine/) - **ACTIVE**

Machine learning and correction capture system.

| File | Purpose | Key Features |
|------|---------|--------------|
| `__init__.py` | Module initialization | - |
| `ab_testing.py` | A/B testing for shadow agent | Statistical comparison |
| `adaptive_decision_engine.py` | Adaptive decision-making | Reinforcement learning |
| `correction_capture.py` | **4-method correction capture** | Interactive, batch, API, inline |
| `correction_metadata.py` | Metadata for corrections | Timestamps, user info |
| `correction_models.py` | Pydantic models for corrections | Validation schemas |
| `correction_storage.py` | Database storage for corrections | SQLAlchemy |
| `feature_engineering.py` | Feature extraction from corrections | ML preprocessing |
| `feedback_system.py` | User feedback collection | User ratings |
| `hyperparameter_tuning.py` | Model hyperparameter optimization | Grid search |
| `integrated_correction_system.py` | **Primary correction system** | End-to-end pipeline |
| `learning_engine.py` | Core learning engine | Pattern extraction |
| `model_architecture.py` | Neural network architectures | PyTorch |
| `model_registry.py` | Model versioning and storage | MLflow-style |
| `pattern_extraction.py` | Pattern extraction from corrections | NLP, clustering |
| `shadow_agent.py` | **Shadow agent implementation** | Alternative model |
| `shadow_evaluation.py` | Shadow agent evaluation | Metrics, comparison |
| `shadow_integration.py` | Shadow agent integration | Traffic routing |
| `shadow_models.py` | Pydantic models for shadow agent | Configuration |
| `shadow_monitoring.py` | Shadow agent monitoring | Performance tracking |
| `training_data_transformer.py` | Data transformation for training | Feature engineering |
| `training_data_validator.py` | Training data validation | Quality checks |
| `training_pipeline.py` | **End-to-end training pipeline** | Data → Model |

**Classification:** All **ACTIVE** - Core learning path (80% → 95%+ accuracy improvement)

### Integration Engine (src/integration_engine/) - **ACTIVE**

SwissKiss loader for automatic integration.

| File | Purpose | Key Features |
|------|---------|--------------|
| `__init__.py` | Module initialization | - |
| `agent_generator.py` | Generate agents from code | AST parsing |
| `capability_extractor.py` | Extract capabilities from repositories | Code analysis |
| `hitl_approval.py` | **Human-in-the-loop approval** | Safety checkpoint |
| `module_generator.py` | Generate Murphy modules | Code generation |
| `safety_tester.py` | Safety testing in sandbox | Malicious code detection |
| `unified_engine.py` | **Primary integration engine** | End-to-end flow |

**Classification:** All **ACTIVE** - Critical for self-integration capability

### Form Intake System (src/form_intake/) - **ACTIVE**

Form-driven task submission (JSON/YAML/NL).

| File | Purpose | Forms Handled |
|------|---------|---------------|
| `__init__.py` | Module initialization | - |
| `api.py` | REST API endpoints for forms | Form submission |
| `handlers.py` | **Primary form handler** | 5 form types |
| `plan_decomposer.py` | Decompose plans into tasks | Task breakdown |
| `plan_models.py` | Pydantic models for plans | Plan schemas |
| `schemas.py` | **Form schemas** (PlanUpload, PlanGeneration, TaskExecution, Validation, Correction) | Input validation |

**Classification:** All **ACTIVE** - Primary input interface

### Confidence Engine (src/confidence_engine/) - **ACTIVE**

Murphy Validation (G/D/H + 5D uncertainty).

| File | Purpose | Implements |
|------|---------|------------|
| `__init__.py` | Module initialization | - |
| `api_server.py` | REST API for validation | Endpoints |
| `authority_mapper.py` | Authority level mapping | Permission levels |
| `confidence_calculator.py` | Confidence score calculation | Statistical methods |
| `credential_interface.py` | Credential management interface | Abstract base |
| `credential_verifier.py` | Credential verification | Auth checks |
| `external_validator.py` | External validation services | Third-party APIs |
| `graph_analyzer.py` | Dependency graph analysis | NetworkX |
| `models.py` | Pydantic models | Data structures |
| `murphy_calculator.py` | **Murphy index calculation** | (G-D)/H formula |
| `murphy_gate.py` | **Gate-based validation** | Threshold checks |
| `murphy_models.py` | Murphy-specific models | ValidationResult |
| `murphy_validator.py` | **Primary validator** | G/D/H + 5D |
| `performance_optimization.py` | Performance optimization | Caching |
| `phase_controller.py` | Phase-based validation | Phase 1/2 logic |
| `risk/risk_database.py` | Risk database | Known risks |
| `risk/risk_lookup.py` | Risk lookup service | Query risks |
| `risk/risk_mitigation.py` | Risk mitigation strategies | Remediation |
| `risk/risk_scoring.py` | Risk scoring | Quantitative |
| `risk/risk_storage.py` | Risk storage | Persistence |
| `rsc_telemetry.py` | Telemetry for RSC | Metrics |
| `uncertainty_calculator.py` | **5D uncertainty** (UD, UA, UI, UR, UG) | Uncertainty types |
| `unified_confidence_engine.py` | **Primary confidence engine** | Complete validation |

**Classification:** All **ACTIVE** - Core safety feature (Murphy Validation)

### Supervisor System (src/supervisor_system/) - **ACTIVE**

Human-in-the-loop (HITL) monitoring and oversight.

| File | Purpose | Key Features |
|------|---------|--------------|
| `__init__.py` | Module initialization | - |
| `anti_recursion.py` | Prevent infinite recursion | Loop detection |
| `assumption_management.py` | Manage system assumptions | Assumption tracking |
| `correction_loop.py` | Correction feedback loop | Human corrections |
| `hitl_models.py` | HITL Pydantic models | InterventionRequest |
| `hitl_monitor.py` | HITL monitoring system | 6 checkpoint types |
| `integrated_hitl_monitor.py` | **Primary HITL monitor** | Complete HITL flow |
| `schemas.py` | HITL schemas | Request/Response |
| `supervisor_loop.py` | Supervisor control loop | Monitoring |

**Classification:** All **ACTIVE** - Core safety feature (HITL)

**6 HITL Checkpoint Types:**
1. Integration (new integrations)
2. High-Risk Action (murphy_index > threshold)
3. Low Confidence (confidence < threshold)
4. First-Time Task (new task type)
5. Scheduled Review (time-based)
6. User-Requested (manual trigger)

### Security Plane (src/security_plane/) - **ACTIVE**

Security and cryptography infrastructure.

| File | Purpose | Status |
|------|---------|--------|
| `__init__.py` | Module initialization | ✅ |
| `access_control.py` | RBAC, permissions | ⚠️ Not integrated to API |
| `adaptive_defense.py` | Threat detection, IDS | ⚠️ Not integrated |
| `anti_surveillance.py` | Privacy protection | ⚠️ Not integrated |
| `authentication.py` | User auth, JWT, sessions | ⚠️ Not integrated to API |
| `cryptography.py` | Encryption, key management | ✅ Used for packets |
| `data_leak_prevention.py` | DLP rules, scanning | ⚠️ Not integrated |
| `hardening.py` | Security best practices | ⚠️ Not integrated |
| `middleware.py` | Security middleware | ⚠️ Not integrated to API |
| `packet_protection.py` | Execution packet encryption | ✅ Active |
| `schemas.py` | Security schemas | ✅ |

**Classification:** All **ACTIVE** but ⚠️ **Priority 1 Issue**: Security plane implemented but not integrated into REST API. Critical security gap.

### Governance Framework (src/governance_framework/) - **ACTIVE**

Control, oversight, and compliance.

| File | Purpose |
|------|---------|
| `__init__.py` | Module initialization |
| `agent_descriptor.py` | Agent metadata and descriptions |
| `agent_descriptor_complete.py` | Complete agent descriptor |
| `artifact_ingestion.py` | Artifact management |
| `refusal_handler.py` | Handle refusals gracefully |
| `scheduler.py` | Task scheduling |
| `stability_controller.py` | System stability monitoring |

**Classification:** All **ACTIVE**

### Module Compiler (src/module_compiler/) - **ACTIVE**

Dynamic code generation and module compilation.

| File | Purpose |
|------|---------|
| `compiler.py` | Main module compiler |
| `analyzers/capability_extractor.py` | Extract capabilities |
| `analyzers/determinism_classifier.py` | Classify determinism |
| `analyzers/failure_mode_detector.py` | Detect failure modes |
| `analyzers/sandbox_generator.py` | Generate sandboxes |
| `analyzers/static_analyzer.py` | Static code analysis |
| `analyzers/test_vector_generator.py` | Generate test vectors |
| `api/endpoints.py` | REST API endpoints |
| `integration/murphy_helpers.py` | Murphy integration |
| `models/module_spec.py` | Module specifications |
| `registry/module_registry.py` | Module registry |

**Classification:** All **ACTIVE** - Critical for dynamic module generation

### Neuro-Symbolic Models (src/neuro_symbolic_models/) - **ACTIVE**

Neural-symbolic hybrid reasoning.

| File | Purpose |
|------|---------|
| `__init__.py` | Module initialization |
| `data.py` | Data loading and preprocessing |
| `inference.py` | Model inference |
| `integration.py` | Integration with Murphy |
| `models.py` | Neural network models (PyTorch) |
| `simple_wrapper.py` | Simplified API wrapper |
| `training.py` | Model training |

**Classification:** All **ACTIVE** - Advanced reasoning capability

### Additional Core Modules (src/) - **ACTIVE**

| Module | Files | Purpose | Classification |
|--------|-------|---------|----------------|
| **Adapter Framework** | 9 files | Integration adapters (HTTP, mock, safety hooks) | **ACTIVE** |
| **Autonomous Systems** | 4 files | Autonomous scheduling, risk management | **ACTIVE** |
| **Base Governance Runtime** | 6 files | Governance runtime, compliance monitoring | **ACTIVE** |
| **Bridge Layer** | 6 files | Compilation, intake, UX layer | **ACTIVE** |
| **Compute Plane** | 11 files | Advanced computation (symbolic/numeric solvers) | **ACTIVE** |
| **Control Plane** | 3 files | Execution packet management | **ACTIVE** |
| **Execution Orchestrator** | 10 files | Execution orchestration, rollback, telemetry | **ACTIVE** |
| **Execution Packet Compiler** | 9 files | Packet compilation, sealing, risk bounding | **ACTIVE** |
| **Gate Synthesis** | 7 files | Dynamic gate generation | **ACTIVE** |
| **Librarian** | 5 files | Knowledge base, semantic search | **ACTIVE** |
| **Org Compiler** | 9 files | Organization chart compilation | **ACTIVE** |
| **Recursive Stability Controller** | 11 files | Stability monitoring, feedback control | **ACTIVE** |
| **Synthetic Failure Generator** | 11 files | Failure injection for testing | **ACTIVE** |
| **Telemetry Learning** | 8 files | Telemetry ingestion and learning | **ACTIVE** |
| **Comms** | 6 files | Communication pipeline | **ACTIVE** |
| **Integrations** | 3 files | Database connectors, integration framework | **ACTIVE** |
| **Supervisor** | 2 files | Supervisor schemas | **ACTIVE** |

### Standalone Modules (src/) - **ACTIVE**

| File | Purpose | Classification |
|------|---------|----------------|
| `config.py` | **Centralized configuration** (Pydantic settings) | **CONFIG** |
| `llm_integration.py` | **LLM orchestration** (Groq, Aristotle, onboard) | **ACTIVE** |
| `llm_integration_layer.py` | LLM abstraction layer | **ACTIVE** |
| `llm_controller.py` | LLM controller | **ACTIVE** |
| `llm_swarm_integration.py` | Multi-agent swarm LLM integration | **ACTIVE** |
| `local_llm_fallback.py` | Local LLM for offline operation | **ACTIVE** |
| `enhanced_local_llm.py` | Enhanced local LLM | **ACTIVE** |
| `local_model_layer.py` | Local model layer | **ACTIVE** |
| `safe_llm_wrapper.py` | Safety wrapper for LLM calls | **ACTIVE** |
| `mock_compatible_local_llm.py` | Mock LLM for testing | **TEST** |
| `groq_key_rotator.py` | Groq API key rotation | **ACTIVE** |
| `secure_key_manager.py` | Secure key management | **ACTIVE** |
| `logging_system.py` | Structured logging system | **ACTIVE** |
| `domain_engine.py` | Domain expertise engine | **ACTIVE** |
| `domain_expert_system.py` | Domain expert system | **ACTIVE** |
| `domain_expert_integration.py` | Domain expert integration | **ACTIVE** |
| `domain_gate_generator.py` | Domain-specific gate generation | **ACTIVE** |
| `domain_swarms.py` | Domain-specific swarms | **ACTIVE** |
| `swarm_proposal_generator.py` | Multi-agent swarm proposal generation | **ACTIVE** |
| `true_swarm_system.py` | Complete swarm system | **ACTIVE** |
| `advanced_swarm_system.py` | Advanced swarm capabilities | **ACTIVE** |
| `system_librarian.py` | System knowledge librarian | **ACTIVE** |
| `memory_artifact_system.py` | Persistent memory system | **ACTIVE** |
| `memory_management.py` | Memory management | **ACTIVE** |
| `state_machine.py` | State machine implementation | **ACTIVE** |
| `authority_gate.py` | Authority-based gating | **ACTIVE** |
| `gate_builder.py` | Dynamic gate builder | **ACTIVE** |
| `verification_layer.py` | Safety verification layer | **ACTIVE** |
| `modular_runtime.py` | Modular runtime system | **ACTIVE** |
| `module_manager.py` | Module management | **ACTIVE** |
| `module_compiler_adapter.py` | Module compiler adapter | **ACTIVE** |
| `system_builder.py` | System builder | **ACTIVE** |
| `system_integrator.py` | System integration | **ACTIVE** |
| `task_executor.py` | Task execution | **ACTIVE** |
| `command_system.py` | Command execution system | **ACTIVE** |
| `command_parser.py` | Command parsing | **ACTIVE** |
| `dynamic_command_discovery.py` | Dynamic command discovery | **ACTIVE** |
| `document_processor.py` | Document processing | **ACTIVE** |
| `advanced_reports.py` | Advanced reporting | **ACTIVE** |
| `advanced_research.py` | Advanced research capabilities | **ACTIVE** |
| `research_engine.py` | Research engine | **ACTIVE** |
| `multi_source_research.py` | Multi-source research | **ACTIVE** |
| `reasoning_engine.py` | Reasoning engine | **ACTIVE** |
| `conversation_handler.py` | Conversation handling | **ACTIVE** |
| `conversation_manager.py` | Conversation management | **ACTIVE** |
| `input_validation.py` | Input validation | **ACTIVE** |
| `response_composer.py` | Response composition | **ACTIVE** |
| `response_formatter.py` | Response formatting | **ACTIVE** |
| `question_manager.py` | Question management | **ACTIVE** |
| `inquisitory_engine.py` | Inquisitory engine | **ACTIVE** |
| `constraint_system.py` | Constraint management | **ACTIVE** |
| `contractual_audit.py` | Contract auditing | **ACTIVE** |
| `bot_inventory_library.py` | Bot inventory | **ACTIVE** |
| `librarian_adapter.py` | Librarian adapter | **ACTIVE** |
| `librarian_integration.py` | Librarian integration | **ACTIVE** |
| `telemetry_adapter.py` | Telemetry adapter | **ACTIVE** |
| `security_plane_adapter.py` | Security plane adapter | **ACTIVE** |
| `neuro_symbolic_adapter.py` | Neuro-symbolic adapter | **ACTIVE** |
| `mfgc_adapter.py` | MFGC adapter | **ACTIVE** |
| `mfgc_core.py` | MFGC core | **ACTIVE** |
| `mfgc_metrics.py` | MFGC metrics | **ACTIVE** |
| `unified_mfgc.py` | Unified MFGC system | **ACTIVE** |
| `probabilistic_layer.py` | Probabilistic reasoning | **ACTIVE** |
| `organization_chart_system.py` | Org chart system | **ACTIVE** |
| `organizational_context_system.py` | Organizational context | **ACTIVE** |
| `multi_language_codegen.py` | Multi-language code generation | **ACTIVE** |
| `smart_codegen.py` | Smart code generation | **ACTIVE** |
| `dynamic_expert_generator.py` | Dynamic expert generation | **ACTIVE** |
| `infinity_expansion_system.py` | Infinity expansion | **ACTIVE** |
| `knowledge_gap_system.py` | Knowledge gap identification | **ACTIVE** |
| `learning_system.py` | Learning system | **ACTIVE** |
| `shutdown_manager.py` | Graceful shutdown | **ACTIVE** |
| `thread_safe_operations.py` | Thread-safe operations | **ACTIVE** |
| `statistics_collector.py` | Statistics collection | **ACTIVE** |
| `ui_data_service.py` | UI data service | **ACTIVE** |
| `murphy_repl.py` | Murphy REPL | **ACTIVE** |

**Total:** 63 standalone modules, all **ACTIVE**

---

## Bot System (bots/)

### Bot Architecture

**Total Bots:** 70+ specialized agents  
**Base System:** `bot_base/`  
**Classification:** All **ACTIVE** (primary implementations in murphy_integrated/bots/)

### Bot Categories

| Category | Examples | Count | Purpose |
|----------|----------|-------|---------|
| **Analysis** | analysisbot, anomaly_watcher_bot, research_bot | 3 | Data analysis and research |
| **Engineering** | engineering_bot, cad_bot, commissioning_bot | 3 | Technical tasks |
| **Knowledge** | librarian_bot, memory_manager_bot, kaia, kiren | 4 | Knowledge management |
| **Data** | json_bot, polyglot_bot, multimodal_describer_bot | 3 | Data transformation |
| **Optimization** | optimization_bot, optimizer_core_bot, efficiency_optimizer, deduplication_refiner_bot | 4 | Performance tuning |
| **Communication** | comms_hub_bot, feedback_bot, meeting_notes_bot | 3 | Communication |
| **Infrastructure** | key_manager_bot, scaling_bot, container_runner, scheduler | 4 | System management |
| **Planning** | plan_structurer_bot, goldenpath_generator, CRMLeadGenerator_bot | 3 | Planning and strategy |
| **Specialized** | ghost_controller_bot, rubixcube_bot, vallon, veritas, osmosis, triage_bot, clarifier_bot, code_translator_bot, visualization_bot | 9+ | Domain-specific |
| **Utilities** | utils/ (typed_event, fuzzy_prompt, etc.) | Multiple | Shared utilities |
| **Integration** | swisskiss_loader | 1 | Repository integration |

### Key Bot Files

| Bot | File | Purpose | Classification |
|-----|------|---------|----------------|
| **SwissKiss** | `swisskiss_loader/` | GitHub repository integration | **ACTIVE** |
| **Librarian** | `librarian_bot/` | Knowledge base management | **ACTIVE** |
| **JSON** | `json_bot/` | JSON processing and transformation | **ACTIVE** |
| **Polyglot** | `polyglot_bot/` | Multi-language support | **ACTIVE** |
| **Optimization** | `optimization_bot/` | Optimization tasks | **ACTIVE** |
| **Analysis** | `analysisbot/` | Analysis capabilities | **ACTIVE** |
| **Engineering** | `engineering_bot/` | Engineering tasks | **ACTIVE** |
| **CAD** | `cad_bot/` | CAD operations | **ACTIVE** |
| **Vallon** | `vallon/` | ML core operations | **ACTIVE** |
| **Research** | `research_bot/` | Research tasks | **ACTIVE** |

### Bot Support Files

| File | Purpose | Classification |
|------|---------|----------------|
| `bot_base.py` | Base class for all bots | **ACTIVE** |
| `plugin_loader.py` | Plugin loading system | **ACTIVE** |
| `config_loader.py` | Configuration loading | **ACTIVE** |
| `config_manager.py` | Configuration management | **ACTIVE** |
| `config.py` | Bot configuration | **CONFIG** |
| `dashboard.py` | Bot dashboard | **ACTIVE** |
| `scheduler_ui.py` | Scheduler UI | **ACTIVE** |
| `rest_api.py` | Bot REST API | **ACTIVE** |

---

## Test Suite (tests/)

### Test Statistics

**Total Test Files:** 89 Python test files  
**Classification:** All **TEST**  
**Test Framework:** pytest with pytest-asyncio, pytest-cov, pytest-mock

### Test Organization

| Directory | Count | Purpose |
|-----------|-------|---------|
| **tests/** (root) | 60+ | Unit tests |
| **tests/integration/** | 10+ | Integration tests |
| **tests/e2e/** | 5+ | End-to-end tests |
| **tests/system/** | 5+ | System tests |

### Critical Test Files

| File | Purpose | Status |
|------|---------|--------|
| `test_basic_imports.py` | Validate imports work | ✅ Essential |
| `test_complete_system_with_execution_engines.py` | Complete system integration | ✅ Critical |
| `test_complete_system_workflow.py` | Full workflow testing | ✅ Critical |
| `test_comprehensive_system.py` | Comprehensive system tests | ✅ Critical |
| `test_integration_engine.py` | Integration engine tests | ✅ Critical |
| `test_confidence_engine.py` | Murphy validation tests | ✅ Critical |
| `test_correction_loop.py` | Correction capture tests | ✅ Critical |
| `test_security_*.py` (11 files) | Security plane tests | ⚠️ Not integrated |

### Security Test Files

All security tests exist but security plane not integrated to API:

| File | Tests |
|------|-------|
| `test_security_access_control.py` | RBAC, permissions |
| `test_security_authentication.py` | Auth, JWT |
| `test_security_cryptography.py` | Encryption |
| `test_security_dlp.py` | Data leak prevention |
| `test_security_middleware.py` | Security middleware |
| `test_security_packet_protection.py` | Packet encryption |
| `test_security_hardening.py` | Security hardening |
| `test_security_adaptive_defense.py` | Threat detection |
| `test_security_anti_surveillance.py` | Privacy |
| `test_security_schemas.py` | Security schemas |

### Integration Test Files

| File | Tests |
|------|-------|
| `test_phase1_murphy_integration.py` | Phase 1 integration |
| `test_murphy_core_integration.py` | Core system integration |
| `test_phase2_enterprise_integration.py` | Enterprise features |
| `test_enterprise_system_integration.py` | Enterprise system |

### Test Coverage Status

| Component | Test Coverage | Status |
|-----------|---------------|--------|
| **Execution Engine** | ~80% | ✅ Good |
| **Confidence Engine** | ~85% | ✅ Good |
| **Learning Engine** | ~70% | ⚠️ Needs improvement |
| **Integration Engine** | ~60% | ⚠️ Needs improvement |
| **Security Plane** | ~90% (tests exist) | ⚠️ Not integrated to API |
| **Form Intake** | ~75% | ⚠️ Needs improvement |
| **HITL System** | ~70% | ⚠️ Needs improvement |
| **Business Automation** | ~40% | ⚠️ Low coverage |
| **Two-Phase Orchestrator** | ~50% | ⚠️ Needs improvement |
| **Overall Estimated** | ~60% | ⚠️ Target is 80%+ |

---

## Documentation

### Documentation Files (DOCS)

All markdown files are classified as **DOCS**.

| File | Lines | Purpose |
|------|-------|---------|
| `README_MURPHY_1.0.md` | ~500 | Primary README |
| `MURPHY_1.0_COMPLETE_SUMMARY.md` | ~800 | Complete system summary |
| `MURPHY_1.0_QUICK_START.md` | ~400 | Quick start guide |
| `API_DOCUMENTATION.md` | ~600 | API reference |
| `DEPLOYMENT_GUIDE.md` | ~500 | Deployment procedures |
| `FINAL_DOCUMENTATION_INDEX.md` | ~200 | Documentation index |
| `MURPHY_SYSTEM_1.0_SPECIFICATION.md` | ~1000 | System specification |

**Total Documentation:** 50,000+ words across 10+ documents

### Documentation Directory Structure

```
documentation/
├── api/                    # API specifications
├── architecture/           # System design
├── components/             # Component guides
├── deployment/             # Deployment docs
├── domain_system/          # Domain system docs
└── enterprise/             # Enterprise features
```

---

## Scripts and Utilities

### Scripts Directory (scripts/)

| File | Purpose | Classification |
|------|---------|----------------|
| `security_audit.py` | Security audit script | **ACTIVE** |
| `error_handling_audit.py` | Error handling audit | **ACTIVE** |
| `performance_optimizer.py` | Performance optimization | **ACTIVE** |
| `memory_optimizer.py` | Memory optimization | **ACTIVE** |

**Classification:** All **ACTIVE** - Utility scripts for maintenance

### Examples Directory (examples/)

| File | Purpose | Classification |
|------|---------|----------------|
| `basic_usage.py` | Basic usage examples | **ACTIVE** |
| `interactive_demo.py` | Interactive demo | **ACTIVE** |
| `governance_framework_demo.py` | Governance demo | **ACTIVE** |
| `base_governance_demo.py` | Base governance demo | **ACTIVE** |
| `enhanced_demo.py` | Enhanced features demo | **ACTIVE** |
| `confidence_engine_demo.py` | Confidence engine demo | **ACTIVE** |
| `research_demo.py` | Research capabilities demo | **ACTIVE** |

**Classification:** All **ACTIVE** - Essential for understanding system usage

---

## Summary Statistics

### File Classification Breakdown

| Classification | Count | Percentage |
|----------------|-------|------------|
| **ACTIVE** | 480+ | ~89% |
| **TEST** | 89 | ~17% |
| **CONFIG** | 5 | ~1% |
| **DOCS** | 50+ | - (markdown) |
| **LEGACY** | 0 | 0% (in murphy_integrated) |
| **UNCLEAR** | 0 | 0% |

### Component Status

| Component | Status | Security Status | Test Coverage |
|-----------|--------|-----------------|---------------|
| **Entry Points** | ✅ Active | ⚠️ No auth | Low |
| **Execution Engine** | ✅ Active | ⚠️ No auth | ~80% |
| **Learning Engine** | ✅ Active | ⚠️ No auth | ~70% |
| **Integration Engine** | ✅ Active | ⚠️ No auth, has HITL | ~60% |
| **Form Intake** | ✅ Active | ⚠️ No auth | ~75% |
| **Confidence Engine** | ✅ Active | ✅ Murphy validation | ~85% |
| **Supervisor (HITL)** | ✅ Active | ✅ HITL checkpoints | ~70% |
| **Security Plane** | ⚠️ Not integrated | ❌ Critical gap | ~90% (tests exist) |
| **Governance** | ✅ Active | ⚠️ No auth | ~60% |
| **Bot System** | ✅ Active | ⚠️ No auth | ~50% |
| **Two-Phase Orchestrator** | ✅ Active | ⚠️ No auth | ~50% |
| **Business Automation** | ✅ Active | ⚠️ No auth | ~40% |

### Critical Issues Identified

| Issue | Severity | Files Affected | Priority |
|-------|----------|----------------|----------|
| **No API Authentication** | 🔴 CRITICAL | murphy_complete_backend_extended.py, all endpoints | P1 |
| **Security Plane Not Integrated** | 🔴 CRITICAL | src/security_plane/* not connected to API | P1 |
| **No Rate Limiting** | 🔴 CRITICAL | All API endpoints | P1 |
| **No Secrets Management** | 🔴 CRITICAL | API keys in environment variables | P1 |
| **No API Versioning** | 🔴 CRITICAL | All endpoints | P1 |
| **Low Test Coverage** | 🟡 IMPORTANT | Business automation, orchestrator | P2 |
| **No Input Sanitization** | 🟡 IMPORTANT | Beyond Pydantic validation | P2 |
| **Incomplete Error Handling** | 🟡 IMPORTANT | Many modules | P3 |
| **Inconsistent Logging** | 🟢 NICE-TO-HAVE | Mix of print/logger | P4 |

### Dependencies

**Key External Dependencies:**
- FastAPI, Uvicorn (REST API)
- Pydantic (validation)
- SQLAlchemy, PostgreSQL (database)
- Redis, Celery (cache/queue)
- PyTorch, scikit-learn (ML)
- Groq, Anthropic (LLM - ⚠️ Issue: spec says NO Anthropic)
- Transformers, spaCy, NLTK (NLP)
- cryptography, PyJWT, bcrypt (security)
- Prometheus, Sentry (monitoring)
- Docker, Kubernetes (deployment)

### Areas Requiring Investigation

| Area | Reason | Phase |
|------|--------|-------|
| **Circular Dependencies** | Potential import issues | Phase 2 |
| **Tight Coupling** | REST API coupled to handlers | Phase 2 |
| **Database Pooling** | Not implemented | Phase 2 |
| **Graceful Shutdown** | Incomplete | Phase 2 |
| **Async Optimization** | Blocking calls in async | Phase 2 |
| **LLM Provider Discrepancy** | Code has Anthropic, spec says no | Phase 2 |

---

## Next Steps for Phase 2

1. **Security Audit**
   - Integrate security plane into REST API
   - Implement authentication/authorization
   - Add rate limiting
   - Implement secrets management
   - Add API versioning

2. **Intent Analysis**
   - Analyze each component's intended purpose
   - Map component interactions
   - Identify circular dependencies
   - Document tight coupling issues

3. **Issue Prioritization**
   - Critical: Security gaps (P1)
   - Important: Test coverage (P2)
   - Nice-to-have: Code quality (P4)

4. **Test Strategy Development**
   - Expand test coverage to 80%+
   - Focus on critical paths
   - Add integration tests
   - Add performance tests

See `SYSTEM_OVERVIEW.md` for system statistics and `ARCHITECTURE_MAP.md` for component relationships.

---

**Last Updated:** February 4, 2026  
**Status:** Phase 1 Complete - Awaiting approval for Phase 2
