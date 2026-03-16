# MURPHY SYSTEM — SPECIFICATIONS, GAP ANALYSIS & COMPLETION ROADMAP

```
================================================================================
  MURPHY SYSTEM — SPECIFICATIONS, GAP ANALYSIS & COMPLETION ROADMAP
  Repository: IKNOWINOT/Murphy-System
  Generated:  2026-03-09
  Analyst:    GitHub Copilot (recursive repo walkthrough)
================================================================================

TABLE OF CONTENTS
─────────────────
  1.  EXECUTIVE SUMMARY
  2.  SYSTEM OVERVIEW — HOW IT WORKS TODAY
  3.  ARCHITECTURE DEEP-DIVE
  4.  USER JOURNEY NARRATIVE (Attempted Automation Walkthrough)
  5.  GAP ANALYSIS — WHAT BREAKS FOR A REAL USER
  6.  DETAILED FINDINGS BY CATEGORY
  7.  RECOMMENDED INCORPORATIONS & CHANGES
  8.  PRIORITIZED COMPLETION ROADMAP
  9.  APPENDIX: FILE INVENTORY

================================================================================
1. EXECUTIVE SUMMARY
================================================================================

Murphy System is an ambitious, ~200+ module Python-based automation platform
created by Inoni LLC (Corey Post). It aims to be a universal automation system
that takes plain-English descriptions of what a user wants automated, builds
the agents and safety gates required to do it, then runs those agents in a
sandboxed production environment — learning from every execution.

CURRENT STATE:
- The repository contains ~649 Python modules + 56 packages in src/
- Core runtime is `murphy_system_1.0_runtime.py` — a thin entry-point that delegates to `src/runtime/` (INC-13 ✅ CLOSED)
- FastAPI server on port 8000 with documented endpoints
- Extensive documentation (README, User Manual, Architecture Map, Storyline)
- Language composition: 92.8% Python, 3.5% TypeScript, 2.4% HTML, 0.7% JS

OVERALL VERDICT:
The system has extraordinary architectural breadth — governance, compliance,
swarm intelligence, blockchain audit trails, multi-tenant workspaces, trading
bots, IoT connectors, content engines, and more. However, as a user attempting
to actually CREATE and RUN an automation end-to-end, the system falls short in
several critical areas. Many modules are structurally defined but lack the live
wiring, real credential management, actual external API connections, and
integration testing needed to produce working automation.

The system is best described as: "Architecture complete, integration incomplete."

================================================================================
2. SYSTEM OVERVIEW — HOW IT WORKS TODAY
================================================================================

2.1 CORE RUNTIME
────────────────
Entry point: murphy_system_1.0_runtime.py (FastAPI server)
Start command: cd "Murphy System" && ./start_murphy_1.0.sh
Port: 8000 (configurable via MURPHY_PORT env var)

The runtime loads all modules from src/, initializes the governance kernel,
sets up HITL (Human-in-the-Loop) gates, loads the Librarian capability map,
and exposes REST API endpoints.

2.2 TWO-PHASE EXECUTION MODEL
──────────────────────────────
Every task moves through two phases:

  Phase 1 — Generative Setup:
    • Librarian identifies which capabilities match the task
    • Solution paths are ranked (Librarian score × historical performance)
    • Gates pre-screen each path (budget, compliance, security)
    • HITL checkpoint if confidence is below threshold or gate requires it

  Phase 2 — Production Execute:
    • Selected path executes via the Wingman Protocol (executor + validator pair)
    • Confidence Engine monitors execution and raises alerts
    • Audit trail written to BlockchainAuditTrail or local ledger
    • Outcome fed back to FeedbackIntegrator for future routing improvement

2.3 KEY API ENDPOINTS
─────────────────────
  GET  /api/health                              Health check
  GET  /api/status                              Full system status and metrics
  GET  /api/info                                System info (version, modules)
  POST /api/execute                             Execute a task (universal)
  POST /api/forms/plan-upload                   Upload execution plan
  POST /api/forms/plan-generation               Generate plan from NL
  POST /api/sessions/create                     Create session
  POST /api/automation/content/generate          Content automation
  POST /api/automation/sensor/read              IoT sensor read
  POST /api/automation/actuator/execute         IoT actuator control
  POST /api/automation/database/query           Data automation
  POST /api/automation/command/execute          System automation
  POST /api/automation/agent/swarm              Agent swarm task
  POST /api/automation/sales/generate_leads     Sales automation
  POST /api/automation/marketing/create_content Marketing automation
  POST /api/integrations/add                    Add integration (SwissKiss)
  GET  /api/onboarding/wizard/questions         Onboarding wizard

2.4 SIX AUTOMATION DOMAINS
───────────────────────────
  1. Factory/IoT:  Sensors, actuators, HVAC, robotics, PLC control
  2. Content:      Blog posts, social media, documentation
  3. Data:         Databases, analytics, ETL pipelines
  4. System:       Shell commands, DevOps, infrastructure
  5. Agent:        AI swarms, complex reasoning tasks
  6. Business:     Sales, marketing, finance, support (Inoni Suite)

2.5 SAFETY FRAMEWORK
─────────────────────
  • Six gate types: EXECUTIVE, OPERATIONS, QA, HITL, COMPLIANCE, BUDGET
  • Confidence Engine using Murphy Formula
  • Murphy Index (quantifying what can go wrong)
  • Emergency stop controller
  • Governance kernel with RBAC
  • Authority Gate checking user roles

2.6 STARTUP SEQUENCE (Documented)
──────────────────────────────────
  1. setup_and_start.sh checks Python 3.10+ and pip
  2. Creates venv, installs from requirements_murphy_1.0.txt
  3. Generates default .env (MURPHY_LLM_PROVIDER=local)
  4. Creates runtime directories (logs, data, modules, sessions)
  5. Starts FastAPI server
  6. ReadinessBootstrapOrchestrator seeds KPI baselines, RBAC roles, etc.
  7. AutomationReadinessEvaluator checks all core modules (8 phases)

================================================================================
3. ARCHITECTURE DEEP-DIVE
================================================================================

3.1 MODULE CATEGORIES (from src/ directory)
───────────────────────────────────────────

CORE ORCHESTRATION:
  - murphy_system_1.0_runtime.py    Main server entry point
  - modular_runtime.py              Modular runtime loader
  - system_integrator.py            Master system integrator (~53KB)
  - system_builder.py               System construction
  - full_automation_controller.py   Full automation orchestration
  - automation_mode_controller.py   Mode switching
  - automation_scheduler.py         Scheduling

CONVERSATION & NL:
  - conversation_handler.py         NL conversation routing
  - conversation_manager.py         Session management
  - command_parser.py               Command parsing
  - command_system.py               Command registration
  - natural_language_query.py       NL query processing

LLM LAYER:
  - llm_controller.py               LLM provider management
  - llm_integration.py              LLM integration
  - llm_integration_layer.py        Advanced LLM layer
  - llm_routing_completeness.py     LLM routing validation
  - local_llm_fallback.py           Local model fallback
  - enhanced_local_llm.py           Enhanced local LLM
  - local_inference_engine.py       Local inference
  - local_model_layer.py            Local model abstraction
  - safe_llm_wrapper.py             Safe LLM wrapper
  - groq_key_rotator.py             API key rotation

DOMAIN ENGINES:
  - domain_engine.py                Domain classification
  - domain_expert_system.py         Domain expertise
  - domain_gate_generator.py        Gate generation per domain
  - domain_swarms.py                Domain-specific swarms

EXECUTION & WORKFLOW:
  - workflow_dag_engine.py          DAG-based workflow execution
  - task_executor.py                Task execution
  - execution_compiler.py           Execution compilation (stub: 173 bytes!)
  - murphy_action_engine.py         Action execution
  - ai_workflow_generator.py        AI-powered workflow generation

SAFETY & GOVERNANCE:
  - governance_kernel.py            Core governance
  - authority_gate.py               Authority checking
  - gate_builder.py                 Gate creation
  - gate_bypass_controller.py       Controlled gate bypass
  - gate_execution_wiring.py        Gate-to-execution wiring
  - safety_orchestrator.py          Safety coordination
  - safety_validation_pipeline.py   Validation pipeline
  - emergency_stop_controller.py    Emergency stop

COMPLIANCE:
  - compliance_engine.py            Core compliance
  - compliance_automation_bridge.py Bridge to automation
  - compliance_as_code_engine.py    Compliance as code
  - compliance_region_validator.py  Regional compliance

BUSINESS AUTOMATION:
  - sales_automation.py             Sales workflows
  - campaign_orchestrator.py        Campaign management
  - marketing_analytics_aggregator  Marketing analytics
  - content_pipeline_engine.py      Content production
  - invoice_processing_pipeline.py  Invoice processing
  - financial_reporting_engine.py   Financial reports

INTEGRATIONS:
  - enterprise_integrations.py      Enterprise system connectors
  - platform_connector_framework.py Platform connectors
  - universal_integration_adapter.py Universal adapter (~67KB)
  - automation_integration_hub.py   Integration orchestration
  - coinbase_connector.py           Crypto exchange
  - crypto_exchange_connector.py    Exchange connector
  - trading_bot_engine.py           Trading automation

OBSERVABILITY:
  - unified_observability_engine.py Unified observability
  - prometheus_metrics_exporter.py  Prometheus metrics
  - telemetry_adapter.py            Telemetry
  - logging_system.py               Logging
  - health_monitor.py               Health monitoring

SUBDIRECTORIES (packages):
  - account_management/             User accounts
  - adapter_framework/              Adapter patterns
  - aionmind/                       AI-on-Mind subsystem
  - auar/                           AUAR subsystem
  - autonomous_systems/             Autonomous operation
  - avatar/                         Avatar system
  - base_governance_runtime/        Governance runtime
  - bridge_layer/                   Bridge layer
  - comms/ + comms_system/          Communications
  - communication_system/           Communication
  - compute_plane/                  Compute plane
  - confidence_engine/              Confidence scoring
  - control_plane/                  Control plane
  - control_theory/                 Control theory models
  - deterministic_compute_plane/    Deterministic compute
  - eq/                             EQ subsystem
  - execution/                      Execution subsystem
  - execution_engine/               Execution engine
  - execution_orchestrator/         Execution orchestration
  - execution_packet_compiler/      Execution packets
  - form_intake/                    Form processing
  - freelancer_validator/           Freelancer validation
  - gate_synthesis/                 Gate synthesis
  - governance_framework/           Governance
  - integration_engine/             Integration engine
  - integrations/                   Integration modules
  - learning_engine/                Learning/correction
  - librarian/                      Capability librarian
  - module_compiler/                Module compilation
  - neuro_symbolic_models/          Neuro-symbolic AI
  - org_compiler/                   Organization compilation
  - recursive_stability_controller/ Stability control
  - robotics/                       Robotics connectors
  - rosetta/                        Rosetta translation
  - schema_registry/                Schema management
  - security_plane/                 Security subsystem
  - shim_compiler/                  Shim compilation
  - supervisor/ + supervisor_system/ Supervisor layer
  - synthetic_failure_generator/    Failure simulation
  - telemetry_learning/             Telemetry-based learning
  - telemetry_system/               Telemetry system

================================================================================
4. USER JOURNEY NARRATIVE — Attempting to Create Automations
================================================================================

Below is a walk-through of what happens when a real user tries to use Murphy
System. Each step is annotated with what works and what breaks.

─── STEP 1: INSTALLATION ───

User runs:
  git clone https://github.com/IKNOWINOT/Murphy-System.git
  Murphy\ System
  bash ../setup_and_start.sh

WHAT HAPPENS:
  ✅ Clone works fine
  ⚠️ setup_and_start.sh referenced in docs, also start_murphy_1.0.sh exists
  ⚠️ Multiple conflicting start commands documented:
     - setup_and_start.sh (GETTING_STARTED.md)
     - start_murphy_1.0.sh (README.md)
     - start_murphy.py (LAUNCH_AUTOMATION_PLAN.md)
     - python murphy_system_1.0_runtime.py (Dockerfile)
  ⚠️ requirements_murphy_1.0.txt needed — unclear if all 200+ modules'
     dependencies are fully captured
  ❌ BLOCKER: No verified dependency resolution test exists

─── STEP 2: SERVER STARTS ───

Expected output:
  INFO: Murphy System 1.0 starting...
  INFO: Module registry: 610 modules loaded
  INFO: Governance kernel: active
  INFO: HITL gates: enabled
  INFO: Uvicorn running on http://0.0.0.0:8000

WHAT HAPPENS:
  ✅ FastAPI server structure exists
  ✅ Health endpoint at /api/health
  ✅ Runtime refactored into `src/runtime/` package (INC-13 closed) — import errors no longer kill the whole file
  ⚠️ If ANY module in src/ has an import error, server may fail to start
  ❌ BLOCKER: No CI/CD pipeline validates that the server actually starts
     successfully from a clean checkout

─── STEP 3: USER CHECKS HEALTH ───

  curl http://localhost:8000/api/health

WHAT HAPPENS:
  ✅ Endpoint is documented and likely works (simple health check)
  ✅ Dockerfile HEALTHCHECK configured for this endpoint

─── STEP 4: USER TRIES TO CREATE FIRST AUTOMATION ───

User sends:
  POST /api/execute
  {
    "task_description": "Automate our sales pipeline. When a lead comes in,
     score them, qualify them, generate a personalized demo script, and
     create a proposal if they're qualified.",
    "task_type": "automation"
  }

WHAT SHOULD HAPPEN (per docs):
  1. ConversationHandler classifies the request
  2. DomainEngine identifies domains (Sales, Operations)
  3. OrgCompiler checks authority
  4. TwoPhaseOrchestrator.create_automation() begins Phase 1
  5. Librarian identifies matching capabilities
  6. Gates pre-screen paths
  7. HITL checkpoint if needed
  8. Phase 2 executes via Wingman Protocol

WHAT ACTUALLY HAPPENS:
  ❌ GAP: No verified end-to-end test proves this full chain works
  ❌ GAP: execution_compiler.py is a 173-byte stub — not implemented
  ❌ GAP: TwoPhaseOrchestrator is referenced in storyline docs but not
     found as a standalone module in src/ — it lives inside the runtime
  ❌ GAP: No real LLM is configured by default (MURPHY_LLM_PROVIDER=local)
     — the "local" LLM is mock_compatible_local_llm.py (400 bytes!)
  ❌ GAP: Without a real LLM, NL understanding, domain classification,
     and content generation ALL produce mock/stub responses
  ❌ GAP: No actual CRM integration exists to receive leads
  ❌ GAP: Sales automation (sales_automation.py, 8.7KB) defines structures
     but has no live API connections to Salesforce, HubSpot, etc.

─── STEP 5: USER TRIES CONTENT AUTOMATION ───

  POST /api/automation/content/generate
  {
    "type": "blog_post",
    "topic": "AI in Manufacturing",
    "tone": "professional",
    "word_count": 1200
  }

WHAT HAPPENS:
  ⚠️ Endpoint likely routes to content pipeline engine
  ❌ GAP: Without a real LLM provider configured, content generation
     returns mock/placeholder content
  ❌ GAP: No publishing integration (WordPress, Medium, etc.) is wired
  ❌ GAP: Content review/approval workflow exists in theory (HITL gates)
     but the reviewer UI (terminal_architect.html) connects to API
     that may not have the full approval flow wired

─── STEP 6: USER TRIES IoT AUTOMATION ───

  POST /api/automation/sensor/read
  {"sensor_id": "temp-floor-3", "protocol": "modbus"}

WHAT HAPPENS:
  ❌ GAP: No actual Modbus/OPC-UA hardware connection exists
  ❌ GAP: building_automation_connectors.py (28KB) defines the interface
     but doesn't include real hardware drivers
  ❌ GAP: energy_management_connectors.py similar — interface only

─── STEP 7: USER TRIES TRADING BOT ───

  The trading_bot_engine.py (54KB) is one of the largest modules.

WHAT HAPPENS:
  ⚠️ Extensive strategy definitions exist
  ❌ GAP: coinbase_connector.py requires real API credentials
  ❌ GAP: No paper-trading mode verified to work end-to-end
  ❌ GAP: crypto_risk_manager.py defines risk limits but no test proves
     the emergency stop actually halts trades

─── STEP 8: USER TRIES SWARM AGENT ───

  POST /api/automation/agent/swarm
  {
    "objective": "Research competitor pricing strategies",
    "agent_count": 3,
    "coordination": "collaborative"
  }

WHAT HAPPENS:
  ⚠️ advanced_swarm_system.py (27KB) and true_swarm_system.py (38KB) exist
  ❌ GAP: Swarm agents need LLM calls to reason — falls back to mock
  ❌ GAP: No web research capability actually implemented (no Playwright
     browser automation wired, though playwright_task_definitions.py
     exists as a 1.2KB stub)

─── STEP 9: USER TRIES THE TERMINAL UI ───

  python murphy_terminal.py

WHAT HAPPENS:
  ✅ Textual TUI exists with session management
  ⚠️ Requires 'textual' package installed
  ⚠️ Connects to http://localhost:8000 — server must be running
  ❌ GAP: Conversational flow depends on LLM for NL understanding
  ❌ GAP: No verified flow from terminal → automation creation → execution

================================================================================
5. GAP ANALYSIS — WHAT BREAKS FOR A REAL USER
================================================================================

CRITICAL GAPS (System cannot function without fixing these):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

C-01  NO WORKING LLM BY DEFAULT
      mock_compatible_local_llm.py is 400 bytes of stub.
      enhanced_local_llm.py (62KB) exists but requires model files.
      Without a working LLM, ALL NL-dependent features fail:
      conversation understanding, domain classification, content
      generation, reasoning, swarm agent thinking.

C-02  EXECUTION COMPILER IS A STUB
      execution_compiler.py is 173 bytes. It's supposed to compile
      execution plans from Phase 1 output. Without it, the two-phase
      model cannot transition from planning to execution.

C-03  NO END-TO-END INTEGRATION TESTS
      No CI pipeline. No test that starts the server from clean state,
      sends a request, and verifies a complete automation cycle.
      test_planning_execution_wiring.py and test_operational_wiring.py
      exist but test individual components, not the full flow.

C-04  NO REAL EXTERNAL API CONNECTIONS
      Every integration module (Salesforce, Slack, Stripe, HVAC, etc.)
      defines interfaces and data structures but contains no verified
      live API calls. The universal_integration_adapter.py (67KB) is
      the largest module — it's framework-only.

C-05  CONFLICTING START COMMANDS
      Four different documented start methods. A new user cannot
      determine which is canonical without reading multiple docs.

HIGH PRIORITY GAPS:
━━━━━━━━━━━━━━━━━━

H-01  CREDENTIAL MANAGEMENT NOT OPERATIONAL
      .env.example exists but unclear which keys are needed for which
      features. env_manager.py (5.4KB) handles reading, but there's
      no validation on startup that tells the user "You need X key
      for Y feature."

H-02  ONBOARDING FLOW INCOMPLETE
      The storyline describes a rich onboarding interview, but the
      actual onboarding_flow.py (27KB) and agentic_onboarding_engine.py
      (21KB) need LLM to function — circular dependency with C-01.

H-03  ROSETTA STATE MANAGEMENT UNWIRED
      Per docs/state_management/ROSETTA_STATE_MANAGEMENT_SYSTEM.md,
      6+ "Priority 3" wiring tasks are unchecked:
      - SelfImprovementEngine → RosettaStateManager
      - SelfAutomationOrchestrator → automation_progress
      - RAGVectorIntegration → RosettaStateManager
      - EventBackbone subscriptions in RosettaStateManager
      - StateManager sync to Rosetta document

H-04  FRONTEND-BACKEND WIRING GAPS
      autonomous_repair_system.py contains WiringDiagnosisLayer that
      checks for frontend→backend endpoint mismatches. This implies
      known wiring gaps exist. The HTML terminals (terminal_architect.html,
      terminal_integrated.html, terminal_worker.html) may call endpoints
      that don't exist or have different signatures.

H-05  PERSISTENCE NOT VERIFIED
      persistence_manager.py (17KB) implements file-based JSON storage.
      persistence_replay_completeness.py (32KB) checks completeness.
      But no test verifies that a task persisted in one session can be
      replayed/resumed in another.

MEDIUM PRIORITY GAPS:
━━━━━━━━━━━━━━━━━━━━

M-01  DOCKER BUILD NOT TESTED
      Dockerfile exists (CMD python murphy_system_1.0_runtime.py) but
      no Docker Compose or CI verification that the image builds and
      runs correctly.

M-02  PORT INCONSISTENCIES
      - Runtime uses port 8000
      - LAUNCH_AUTOMATION_PLAN.md references port 5000
      - documentation/README.md references port 8052
      - A user following different docs will get different ports.

M-03  PLAYWRIGHT/BROWSER AUTOMATION STUB
      playwright_task_definitions.py is 1.2KB — a stub. The system
      cannot perform real web automation (form filling, scraping, etc.)
      without this being implemented.

M-04  NO DEPENDENCY PINNING
      requirements_murphy_1.0.txt exists but unclear if versions are
      pinned. With 200+ modules, any dependency conflict could break
      the entire system.

M-05  TESTING COVERAGE
      Tests exist (test_documentation.py, test_planning_execution_wiring.py,
      test_operational_wiring.py, test_multi_loop_schedule_snapshot.py)
      but coverage is thin relative to 649 modules.

M-06  WEBSOCKET/REAL-TIME NOT VERIFIED
      websocket_event_server.py (21KB) exists but no test or doc
      confirms WebSocket connections work for real-time updates.

LOW PRIORITY GAPS:
━━━━━━━━━━━━━━━━━━

L-01  MODULE DUPLICATION/OVERLAP
      Multiple modules cover similar ground:
      - comms/ vs comms_system/ vs communication_system/
      - supervisor/ vs supervisor_system/
      - execution/ vs execution_engine/ vs execution_orchestrator/
      This creates confusion about which is canonical.

L-02  LARGE FILE RISK (✅ RESOLVED — INC-13)
      `murphy_system_1.0_runtime.py` has been refactored into the `src/runtime/`
      package (`app.py`, `murphy_system_core.py`, `living_document.py`, `_deps.py`).
      The entry-point file is now a thin ~1 KB shim.

L-03  DOCUMENTATION SPRAWL
      Multiple README files, GETTING_STARTED files, QUICK_START files
      at different directory levels with slightly different information.
      A canonical "single source of truth" is needed.

================================================================================
6. DETAILED FINDINGS BY CATEGORY
================================================================================

6.1 LLM INTEGRATION LAYER
──────────────────────────
FILES: llm_controller.py, llm_integration.py, llm_integration_layer.py,
       llm_routing_completeness.py, safe_llm_wrapper.py, groq_key_rotator.py,
       local_llm_fallback.py, enhanced_local_llm.py, local_model_layer.py,
       local_inference_engine.py, mock_compatible_local_llm.py

FINDING: Extensive abstraction exists for multiple LLM providers (Groq, local
models, etc.) with routing, fallback, and safety wrapping. However:
  • Default config uses "local" provider → mock 400-byte stub
  • Groq key rotation exists but requires valid API keys
  • No OpenAI/Anthropic/Azure connector found
  • llm_routing_completeness.py (35KB) validates routing logic but
    the routing targets are largely theoretical without real providers

RECOMMENDATION: Implement at minimum ONE working LLM provider out of the box.
Best candidate: OpenAI-compatible API (works with OpenAI, Azure, Groq, local
Ollama servers). Add MURPHY_OPENAI_API_KEY / MURPHY_OPENAI_BASE_URL to .env.

6.2 GATE SYSTEM
───────────────
FILES: gate_builder.py, gate_bypass_controller.py, gate_execution_wiring.py,
       gate_synthesis/, domain_gate_generator.py, inference_gate_engine.py

FINDING: The gate system is one of the most complete subsystems. GateBuilder
can create safety gates. GateExecutionWiring connects gates to execution.
DomainGateGenerator (49KB!) generates domain-specific gates. The concept is
sound and well-architected.

REMAINING WORK: Gate evaluation at runtime needs to be verified with real
data flowing through. The bypass controller needs audit logging confirmation.

6.3 SWARM / MULTI-AGENT
────────────────────────
FILES: advanced_swarm_system.py, true_swarm_system.py, domain_swarms.py,
       durable_swarm_orchestrator.py, llm_swarm_integration.py,
       murphy_crew_system.py, swarm_proposal_generator.py

FINDING: Two separate swarm systems exist (advanced vs true). Both define
agent coordination patterns, proposal generation, and durability. The
murphy_crew_system.py (27KB) appears to be a CrewAI-style implementation.

REMAINING WORK: All swarm agents need a working LLM (back to C-01).
No test proves that 3+ agents can actually coordinate on a task.

6.4 BUSINESS AUTOMATION (INONI SUITE)
──────────────────────────────────────
FILES: sales_automation.py, campaign_orchestrator.py, self_selling_engine.py,
       niche_business_generator.py, niche_viability_gate.py (125KB!),
       business_scaling_engine.py, rosetta_selling_bridge.py,
       competitive_intelligence_engine.py

FINDING: The Inoni business automation suite is extensive. The
niche_viability_gate.py at 125KB is the largest single module — it
evaluates business niche viability across multiple dimensions. self_selling_engine.py
(47KB) is designed to let Murphy sell itself.

REMAINING WORK: None of these can produce real business outcomes without:
  • Working LLM for content/analysis generation
  • Real CRM/email integrations
  • Payment processing integration (Stripe, etc.)
  • Real web scraping for competitive intelligence

6.5 TRADING / CRYPTO
─────────────────────
FILES: trading_bot_engine.py, trading_strategy_engine.py,
       trading_shadow_learner.py, trading_hitl_gateway.py,
       trading_bot_lifecycle.py, crypto_exchange_connector.py,
       coinbase_connector.py, crypto_wallet_manager.py,
       crypto_portfolio_tracker.py, crypto_risk_manager.py,
       market_data_feed.py, ml_strategy_engine.py

FINDING: The trading subsystem is the most fleshed-out domain vertically.
It has strategy engines, shadow learning (paper trading), HITL gateways
for human approval of trades, lifecycle management, and risk management.

REMAINING WORK:
  • Real exchange API credentials and connections
  • Verified paper-trading mode
  • Emergency stop tested with real market data
  • Regulatory compliance verification for automated trading

6.6 IoT / MANUFACTURING
────────────────────────
FILES: building_automation_connectors.py, energy_management_connectors.py,
       manufacturing_automation_standards.py, additive_manufacturing_connectors.py,
       murphy_sensor_fusion.py, robotics/

FINDING: Interface definitions exist for Modbus, OPC-UA, BACnet, and other
industrial protocols. Manufacturing standards (ISA-95, etc.) are referenced.

REMAINING WORK: No actual hardware driver or protocol library is imported.
These are all framework/interface code. Real IoT automation would need:
  • pymodbus, opcua, or similar actual protocol libraries
  • Real hardware or simulator for testing
  • Safety-critical testing for actuator control

================================================================================
7. RECOMMENDED INCORPORATIONS & CHANGES
================================================================================

7.1 IMMEDIATE (Must-do before any user can use the system)
──────────────────────────────────────────────────────────

[INC-01] IMPLEMENT WORKING LLM PROVIDER
  Action: Create src/openai_compatible_provider.py that:
    • Reads MURPHY_LLM_API_KEY and MURPHY_LLM_BASE_URL from .env
    • Supports OpenAI API format (works with OpenAI, Azure, Groq, Ollama)
    • Replaces mock_compatible_local_llm.py as default when key is present
    • Falls back to deterministic routing when no key is configured
  Files to modify:
    • llm_controller.py — add OpenAI-compatible provider
    • .env.example — add MURPHY_LLM_API_KEY, MURPHY_LLM_BASE_URL
    • config.py — add LLM config validation
  Estimated effort: 2-3 days

[INC-02] IMPLEMENT EXECUTION COMPILER
  Action: Replace the 173-byte stub with a real implementation that:
    • Takes Phase 1 plan output (capability list, gate results, routing)
    • Compiles it into an execution packet for Phase 2
    • Validates all required resources/credentials are available
    • Returns a structured ExecutionPlan object
  Files to modify:
    • execution_compiler.py — full implementation
    • execution_packet_compiler/ — connect to the existing package
  Estimated effort: 3-5 days

[INC-03] CANONICALIZE STARTUP
  Action: Make ONE start command that works everywhere:
    • Remove/consolidate setup_and_start.sh, start_murphy_1.0.sh,
      start_murphy.py into a single canonical entry point
    • Update ALL documentation to reference the same command
    • Add a Makefile or invoke taskfile for common operations
  Files to modify:
    • Root-level Makefile or Justfile
    • All README/GETTING_STARTED files
  Estimated effort: 1 day

[INC-04] ADD END-TO-END SMOKE TEST
  Action: Create tests/test_e2e_smoke.py that:
    • Starts the server programmatically
    • Calls /api/health
    • Creates a session
    • Submits a simple automation request
    • Verifies response structure
    • Shuts down
  Also add GitHub Actions CI workflow
  Estimated effort: 2 days

[INC-05] FIX PORT INCONSISTENCIES
  Action: Standardize on port 8000 everywhere:
    • Grep for ports 5000, 8052, 8090 and update to 8000
    • Or use MURPHY_PORT consistently
  Estimated effort: 0.5 days

7.2 SHORT-TERM (Within 2 weeks — enables basic automation)
──────────────────────────────────────────────────────────

[INC-06] IMPLEMENT CREDENTIAL VALIDATION ON STARTUP
  Action: On server start, scan which features require which credentials,
  report to the user:
  "⚠️ MURPHY_LLM_API_KEY not set → NL features disabled"
  "⚠️ COINBASE_API_KEY not set → Trading features disabled"
  This lets users know what's available without reading all docs.
  Estimated effort: 2 days

[INC-07] WIRE ROSETTA STATE MANAGEMENT
  Action: Complete the 6 unchecked wiring tasks from the Rosetta
  State Management checklist (P3-001 through P3-006).
  Estimated effort: 3-5 days

[INC-08] IMPLEMENT PLAYWRIGHT BROWSER AUTOMATION
  Action: Replace the 1.2KB stub with real Playwright integration:
    • Web scraping for competitive intelligence
    • Form filling for integration testing
    • Screenshot/evidence capture for audit
  Estimated effort: 3-5 days

[INC-09] CREATE DOCKER COMPOSE STACK
  Action: docker-compose.yml with:
    • Murphy System runtime
    • Optional Redis for event backbone
    • Optional PostgreSQL for persistence
    • Health check dependencies
  Estimated effort: 2 days

[INC-10] CONSOLIDATE DUPLICATE DIRECTORIES
  Action: Merge:
    • comms/ + comms_system/ + communication_system/ → communications/
    • supervisor/ + supervisor_system/ → supervisor/
    • execution/ + execution_engine/ + execution_orchestrator/ → execution/
  Estimated effort: 2-3 days (careful refactoring)

7.3 MEDIUM-TERM (Within 1 month — enables real-world automation)
────────────────────���───────────────────────────────────────────

[INC-11] IMPLEMENT FIRST REAL INTEGRATION
  Best candidate: Email (SMTP/SendGrid). Low complexity, high value.
  This proves the entire chain: NL request → plan → gate check → execute
  → deliver email → audit log.
  Estimated effort: 3-5 days

[INC-12] IMPLEMENT WEBHOOK RECEIVER
  Action: Real inbound webhook handling so external events can trigger
  automations. webhook_dispatcher.py (28KB) and webhook_event_processor.py
  (42KB) exist — need to be verified and tested end-to-end.
  Estimated effort: 3-5 days

[INC-13] REFACTOR RUNTIME FILE ✅ COMPLETE
  The refactor is done. `murphy_system_1.0_runtime.py` is now a thin entry-point.
  Implementation is in:
    • src/runtime/app.py (FastAPI app, all routes & endpoints)
    • src/runtime/murphy_system_core.py (MurphySystem orchestration class)
    • src/runtime/living_document.py (LivingDocument block-command model)
    • src/runtime/_deps.py (shared dependency imports)

[INC-14] ADD COMPREHENSIVE TEST SUITE
  Target: 80%+ coverage on core paths:
    • Conversation → domain classification → gate check → execute
    • Gate builder → gate evaluation → pass/fail
    • Swarm creation → agent coordination → result aggregation
  Estimated effort: 2-3 weeks ongoing

[INC-15] IMPLEMENT RAG / KNOWLEDGE BASE
  Action: rag_vector_integration.py (24KB) and knowledge_base_manager.py
  (14KB) exist but need a real vector store (ChromaDB, Pinecone, etc.).
  This enables the Librarian to actually match capabilities by meaning.
  Estimated effort: 3-5 days

7.4 LONG-TERM (1-3 months — production readiness)
──────────────────────────────────────────────────

[INC-16] IMPLEMENT MULTI-TENANT ISOLATION
  multi_tenant_workspace.py (29KB) exists. Needs real testing with
  multiple users, RBAC enforcement, and resource limits.

[INC-17] PRODUCTION PERSISTENCE LAYER
  Replace file-based JSON with PostgreSQL or similar for production.
  Implement the blockchain audit trail for real (or use append-only log).

[INC-18] SECURITY HARDENING
  • Rate limiting on API endpoints
  • JWT/OAuth token validation (oauth_oidc_provider.py exists)
  • Input sanitization verification
  • Penetration testing

[INC-19] REAL IoT PROTOCOL INTEGRATION
  Add pymodbus, asyncua, or similar for real HVAC/sensor automation.
  Test with simulation tools (e.g., ModRSsim).

[INC-20] MONITORING & ALERTING
  Connect prometheus_metrics_exporter.py to real Prometheus/Grafana.
  Set up alerting for SLO violations, error rate spikes, etc.

================================================================================
8. PRIORITIZED COMPLETION ROADMAP
================================================================================

WEEK 1: Foundation
──────────────────
  □ INC-01: Working LLM provider (OpenAI-compatible)
  □ INC-03: Canonicalize startup command
  □ INC-05: Fix port inconsistencies
  □ INC-04: E2E smoke test + GitHub Actions CI

WEEK 2: Core Wiring
────────────────────
  □ INC-02: Implement execution compiler
  □ INC-06: Credential validation on startup
  □ INC-10: Consolidate duplicate directories

WEEK 3-4: First Real Automation
────────────────────────────────
  □ INC-07: Wire Rosetta state management
  □ INC-11: First real integration (email)
  □ INC-09: Docker Compose stack
  □ INC-12: Webhook receiver verification

MONTH 2: Robustness
────────────────────
  ☑ INC-13: Refactor runtime file ✅ COMPLETE
  □ INC-14: Comprehensive test suite
  □ INC-15: RAG/vector knowledge base
  □ INC-08: Playwright browser automation

MONTH 3: Production
───────────────────
  □ INC-16: Multi-tenant isolation testing
  □ INC-17: Production persistence layer
  □ INC-18: Security hardening
  □ INC-19: Real IoT protocols
  □ INC-20: Monitoring & alerting

================================================================================
9. APPENDIX: FILE INVENTORY SUMMARY
================================================================================

TOTAL FILES IN src/:
  • ~200+ standalone Python modules (.py files)
  • ~56 subdirectory packages
  • Total estimated code: 3-4 MB of Python

LARGEST MODULES (by file size):
  1. niche_viability_gate.py           125,104 bytes
  2. agent_persona_library.py           83,954 bytes
  3. murphy_code_healer.py              66,317 bytes
  4. universal_integration_adapter.py   66,858 bytes
  5. enhanced_local_llm.py              61,861 bytes
  6. unified_mfgc.py                    61,860 bytes
  7. inference_gate_engine.py           60,719 bytes
  8. murphy_immune_engine.py            57,006 bytes
  9. niche_business_generator.py        58,271 bytes
  10. trading_bot_engine.py             53,790 bytes

SMALLEST MODULES (potential stubs):
  1. __init__.py                           166 bytes
  2. execution_compiler.py                 173 bytes  ← STUB
  3. deterministic_compute.py              188 bytes  ← STUB
  4. mock_compatible_local_llm.py          400 bytes  ← STUB

DOCUMENTATION FILES:
  • README.md (repository root)
  • GETTING_STARTED.md (repository root)
  • USER_MANUAL.md
  • ARCHITECTURE_MAP.md
  • MURPHY_SYSTEM_1.0_SPECIFICATION.md
  • MURPHY_1.0_QUICK_START.md
  • MURPHY_SYSTEM_STORYLINE.md
  • LAUNCH_AUTOMATION_PLAN.md
  • REMEDIATION_PLAN.md
  • INSTALLATION.md (documentation/getting_started/)
  • QUICK_START.md (documentation/getting_started/)
  • ROSETTA_STATE_MANAGEMENT_SYSTEM.md

HTML UIs:
  • terminal_architect.html     Architect planning + gate review
  • terminal_integrated.html    Operations execution
  • terminal_worker.html        Delivery worker

TESTS:
  • test_documentation.py
  • test_planning_execution_wiring.py
  • test_operational_wiring.py
  • test_multi_loop_schedule_snapshot.py

================================================================================
END OF DOCUMENT
================================================================================

Prepared by GitHub Copilot via recursive repository analysis.
This document should be treated as a living specification — update it as
gaps are closed and new requirements emerge.

© 2020-2026 Inoni LLC | Murphy System | Created by Corey Post
Analysis performed: 2026-03-09
```