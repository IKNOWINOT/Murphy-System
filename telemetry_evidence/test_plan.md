# Murphy System — Advanced Operations & Telemetry Test Plan

## Goal

Boot Murphy System 1.0 from cold-start, systematically exercise every feature
via the UI and API, capture telemetry evidence with screenshots into a dedicated
folder, diagnose and fix any failures, re-test, and repeat until the system
demonstrates autonomous sales-readiness.

## Evidence Output

All screenshots, logs, and telemetry are saved to:

```
telemetry_evidence/
├── 01_install/          — Environment snapshots
├── 02_boot/             — Server boot logs and PID
├── 03_health/           — Health endpoint responses
├── 04_api_core/         — API sweep results
├── 05_forms_intake/     — Form submission tests
├── 06_confidence_engine/— Confidence scoring evidence
├── 07_gate_execution/   — Gate enforcement evidence
├── 08_delivery_channels/— Delivery adapter tests
├── 09_persistence_replay/— Persistence/WAL tests
├── 10_event_backbone/   — Event pub/sub tests
├── 11_self_improvement/ — Self-healing & pytest results
├── 12_compliance_engine/— GDPR/SOC2/HIPAA/PCI
├── 13_wingman_protocol/ — Executor/validator pairs
├── 14_causality_sandbox/— Causal inference tests
├── 15_hitl_graduation/  — Human-in-the-loop tests
├── 16_orchestrators/    — Orchestration flow tests
├── 17_ui_interfaces/    — UI file & HTTP tests
├── 18_security_plane/   — Security validation
├── 19_integrations/     — Platform connector tests
├── 20_self_automation/  — Automation type registry
├── 21_sales_demo/       — Sales readiness demo
├── 22_fixes_applied/    — Diagnose/fix/retest loop
├── telemetry_log.jsonl  — Streaming event log
├── test_plan.md         — This plan
└── FINAL_REPORT.md      — Generated summary
```

## Phases

### Phase 0: Environment Setup & Cold Boot (`00_setup.sh`)

- Verify repository structure and required files
- Create/activate Python virtual environment
- Install dependencies from `requirements.txt`
- Initialize `.env` configuration
- Cold-boot the Murphy server (background process)
- Capture environment snapshot

**Files Used:**
- `setup_and_start.sh` — One-step venv + deps + .env + server launch
- `install.sh` — Curl-pipe installer (alternative)
- `requirements.txt` — Core dependencies
- `murphy_system/murphy_system_1.0_runtime.py` — FastAPI entry point
- `murphy_system/src/runtime/app.py` — `create_app()` factory
- `murphy_system/src/config.py` — Pydantic BaseSettings

### Phase 1: Health & Telemetry Baseline (`test_phase1_health.py`)

- Hit `/api/health`, `/api/status`, `/api/info`, `/api/readiness`
- Capture telemetry baseline from `/api/telemetry`
- Introspect loaded modules via `/api/modules`
- Save all responses as evidence JSON

### Phase 2: Core API Feature Sweep (`test_phase2_api_core.py`)

- Exercise 60+ GET endpoints (agents, documents, integrations, etc.)
- Exercise 10+ POST endpoints with minimal safe payloads
- Record response codes, latencies, and body previews
- Track pass/fail for every endpoint

**Files Tested:**
- `murphy_system/src/runtime/app.py` — All route handlers
- `murphy_system/src/form_intake/handlers.py` — `/api/forms/*`

### Phase 3: UI Interface Testing (`test_phase3_ui.py`)

- Verify 16 HTML files exist on disk with non-zero size
- Check each for design system CSS, components JS, skip links
- Test HTTP access to each UI file via the running server
- Test static asset accessibility (CSS, JS, SVG)

### Phase 4: Security Plane Validation (`test_phase4_security.py`)

- Import-test 12 security modules from `security_plane/`
- Test `InputSanitizer` against XSS, SQLi, path traversal payloads
- Verify HTTP security headers on API responses

**Files Tested:**
- `murphy_system/src/security_hardening_config.py`
- `murphy_system/src/security_plane/*.py` (18 modules)

### Phase 5: Self-Healing & Test Suite (`test_phase5_self_healing.sh`)

- Run `pytest tests/` with JUnit XML output
- Extract failure summary
- Test self-fix module imports
- Generate test suite statistics

**Files Tested:**
- `murphy_system/tests/` — 568+ test files
- `murphy_system/src/self_fix_loop.py`
- `murphy_system/src/murphy_immune_engine.py`
- `murphy_system/src/bug_pattern_detector.py`

### Phase 6: Sales Readiness Demo (`test_phase6_sales_demo.py`)

Simulates a prospective customer's first experience through 7 demos:
1. First Impression — landing page, health, UI links
2. Chat Interaction — conversational AI
3. Task Execution — submit and execute a task
4. Onboarding Flow — wizard questions and answers
5. Integration Showcase — available services and categories
6. Analytics Overview — costs, orchestrator, telemetry
7. Security & Compliance — readiness, health, UCP

### Phase 7: Diagnose → Fix → Retest Loop (`test_phase7_fix_loop.py`)

- Read all failures from `telemetry_log.jsonl`
- Classify by category: server_down, missing_module, route_missing, etc.
- Produce diagnosis with root cause and recommendation
- Re-test failed endpoints
- Save diagnoses and retest results

### Phase 8: Final Report (`generate_final_report.py`)

- Aggregate all telemetry events
- Compute pass/fail/warning counts
- Compile phase-by-phase summaries
- List all failure details
- Write `FINAL_REPORT.md`

## Running

Execute the complete sequence:

```bash
bash telemetry_evidence/run_all.sh
```

Or run individual phases:

```bash
# Phase 0: Setup
bash telemetry_evidence/00_setup.sh

# Phase 1: Health
python3 telemetry_evidence/test_phase1_health.py

# Phase 2: API
python3 telemetry_evidence/test_phase2_api_core.py

# Phase 3: UI
python3 telemetry_evidence/test_phase3_ui.py

# Phase 4: Security
python3 telemetry_evidence/test_phase4_security.py

# Phase 5: Tests
bash telemetry_evidence/test_phase5_self_healing.sh

# Phase 6: Demo
python3 telemetry_evidence/test_phase6_sales_demo.py

# Phase 7: Fix loop
python3 telemetry_evidence/test_phase7_fix_loop.py

# Phase 8: Report
python3 telemetry_evidence/generate_final_report.py
```

## Complete File Map

| Category | File Path | Purpose |
|----------|-----------|---------|
| Entry Point | `murphy_system/murphy_system_1.0_runtime.py` | FastAPI server bootstrap |
| App Factory | `murphy_system/src/runtime/app.py` | `create_app()` + route registration |
| Config | `murphy_system/src/config.py` | Pydantic BaseSettings |
| Setup | `setup_and_start.sh` | One-step installer |
| Confidence | `murphy_system/src/confidence_engine/` | G/D/H + 5D uncertainty |
| Execution | `murphy_system/src/execution_engine/` | Task execution pipeline |
| Forms | `murphy_system/src/form_intake/handlers.py` | Form intake handlers |
| Learning | `murphy_system/src/learning_engine/` | Shadow agent training |
| HITL | `murphy_system/src/supervisor_system/` | Human-in-the-loop monitor |
| Governance | `murphy_system/src/governance_framework/` | Scheduler + authority |
| Gate Wiring | `murphy_system/src/gate_execution_wiring.py` | Runtime gate enforcement |
| Persistence | `murphy_system/src/persistence_manager.py` | Durable JSON storage |
| Events | `murphy_system/src/event_backbone.py` | Pub/sub + circuit breaker |
| Delivery | `murphy_system/src/delivery_adapters.py` | Doc/email/chat/voice |
| Self-Improve | `murphy_system/src/self_improvement_engine.py` | Feedback loops |
| Self-Fix | `murphy_system/src/self_fix_loop.py` | Autonomous fix cycle |
| Immune | `murphy_system/src/murphy_immune_engine.py` | 11-phase immune cycle |
| Bug Detect | `murphy_system/src/bug_pattern_detector.py` | Pattern classification |
| SLO | `murphy_system/src/operational_slo_tracker.py` | Latency + success rate |
| Compliance | `murphy_system/src/compliance_engine.py` | GDPR/SOC2/HIPAA/PCI |
| RBAC | `murphy_system/src/rbac_governance.py` | Multi-tenant RBAC |
| Wingman | `murphy_system/src/wingman_protocol.py` | Executor/validator pairs |
| Routing | `murphy_system/src/deterministic_routing_engine.py` | Policy routing |
| Connectors | `murphy_system/src/platform_connector_framework.py` | 20 platforms |
| DAG | `murphy_system/src/workflow_dag_engine.py` | Workflow execution |
| Templates | `murphy_system/src/automation_type_registry.py` | 16 automation types |
| ML | `murphy_system/src/ml_strategy_engine.py` | Anomaly/forecast/RL |
| Analytics | `murphy_system/src/analytics_dashboard.py` | Metrics dashboard |
| Security | `murphy_system/src/security_hardening_config.py` | XSS/SQLi/CORS |
| Auth | `murphy_system/src/security_plane/authorization_enhancer.py` | Ownership |
| PII | `murphy_system/src/security_plane/log_sanitizer.py` | Redaction |
| Quotas | `murphy_system/src/security_plane/bot_resource_quotas.py` | Bot limits |
| Cycles | `murphy_system/src/security_plane/swarm_communication_monitor.py` | DFS |
| Identity | `murphy_system/src/security_plane/bot_identity_verifier.py` | HMAC |
| Anomaly | `murphy_system/src/security_plane/bot_anomaly_detector.py` | Z-score |
| Dashboard | `murphy_system/src/security_plane/security_dashboard.py` | Unified view |
| Tests | `murphy_system/tests/` | 568 files, 8,843+ test functions |
| UIs | `murphy_system/*.html` | 16 web interfaces |
| Design | `murphy_system/static/murphy-design-system.css` | CSS tokens |
| Components | `murphy_system/static/murphy-components.js` | JS components |
| Canvas | `murphy_system/static/murphy-canvas.js` | Graphical renderer |
| Icons | `murphy_system/static/murphy-icons.svg` | 42 SVG icons |
