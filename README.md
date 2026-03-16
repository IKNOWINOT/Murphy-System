# Murphy System

This is the Murphy System repository — the autonomous business-operations platform.
It contains the FastAPI server, 978 source modules across 81 packages in `src/`, 644 test files,
web interfaces, and deployment configuration.

## 📊 Stats

| Metric | Value |
|--------|-------|
| **Source modules** | 978 |
| **Packages** | 81 subsystem directories |
| **Test files** | 644 |
| **Test functions** | 17,368+ |
| **Web interfaces** | 16 |

---

## Quick Start

```bash
bash setup_and_start.sh                       # recommended: single canonical start
curl http://localhost:8000/api/health          # verify it's running
```

The optional Textual TUI terminal is available separately:

```bash
python murphy_terminal.py
```

Interactive API docs are served at **http://localhost:8000/docs** (Swagger UI).

---

## API Reference

All endpoints are prefixed with `/api`.

### Primary Flow: Describe → Execute

This is Murphy's hero flow — start here.

| Step | Endpoint | What Happens |
|---|---|---|
| 1. Describe | `POST /api/workflow-terminal/session` + `POST /api/workflow-terminal/message` | Start a Librarian session, describe what you want in plain English |
| 2. Generate | `POST /api/forms/plan-generation` | Murphy generates a DAG workflow from your description |
| 3. Execute | `POST /api/execute` | Run the workflow through the full orchestration pipeline |
| 4. Refine (optional) | Visual canvas at `workflow_canvas.html` | Open the visual canvas to tweak the generated workflow |

| Group | Endpoints | Description |
|---|---|---|
| **Core** | `/api/health`, `/api/status`, `/api/execute`, `/api/chat` | Health checks, system status, task execution, chat |
| **Forms** | `/api/forms/*` | Form intake and processing |
| **Onboarding** | `/api/onboarding/wizard/*` | Guided onboarding wizard |
| **Onboarding Flow** | `/api/onboarding-flow/*` | Corporate org chart, individual onboarding, shadow agent assignment |
| **Workflow Terminal** | `/api/workflow-terminal/*` | No-code Librarian terminal — describe workflows in natural language |
| **Agent Dashboard** | `/api/agent-dashboard/*` | Real-time agent monitoring with drill-down |
| **IP Classification** | `/api/ip/*` | IP asset registration, trade secret protection, licensing |
| **Credentials** | `/api/credentials/*` | HITL credential profiles and optimal automation metrics |
| **Librarian** | `/api/librarian/*` | Knowledge-base and document librarian |
| **Documents** | `/api/documents/*` | Document management |
| **Integrations** | `/api/integrations/*` | External system integrations |
| **LLM** | `/api/llm/*` | Language-model routing and inference |
| **HITL** | `/api/hitl/*` | Human-in-the-loop checkpoints and approvals |
| **MFGC** | `/api/mfgc/*` | Murphy Formula / Gate / Confidence scoring |
| **Corrections** | `/api/corrections/*` | Correction capture and learning |
| **Wingman Protocol** | `/api/wingman/*` | Executor/validator pairing, runbooks, validation history |
| **Causality Sandbox** | `/api/causality/*` | Causal simulation, what-if scenario cycles |
| **HITL Graduation** | `/api/hitl-graduation/*` | Human-in-the-loop graduation pipeline — register, evaluate, graduate, rollback |
| **Functionality Heatmap** | `/api/heatmap/*` | Activity recording, cold/hot-spot analysis, coverage dashboard |
| **Safety Orchestrator** | `/api/safety/*` | Safety checks, compliance reports, safety dashboard |
| **Efficiency Orchestrator** | `/api/efficiency/*` | Efficiency readings, scoring, optimisation recommendations |
| **Supply Orchestrator** | `/api/supply/*` | Inventory registration, usage tracking, reorder management |
| **Time Tracking — Settings** | `/api/time/settings` (GET, PUT), `/api/time/settings/validate` | Get/update time tracking settings, validate current settings |
| **Time Tracking — Billing** | `/api/time/billing/summary`, `/api/time/billing/summary/<client_id>`, `/api/time/billing/invoice`, `/api/time/billing/invoice/preview`, `/api/time/billing/rates`, `/api/time/billing/rates/<client_id>`, `/api/time/billing/audit-log` | Billing summaries, invoice generation and preview, rate management, audit log |
| **Time Tracking — Dashboard** | `/api/time/dashboard/summary/user/<user_id>`, `/api/time/dashboard/summary/team`, `/api/time/dashboard/summary/project/<project_id>`, `/api/time/dashboard/summary/system`, `/api/time/team/<manager_id>/dashboard` | User, team, project, and system dashboard summaries; team manager dashboard |

Full auto-generated docs: **http://localhost:8000/docs**

---

## Web Interfaces

Fourteen web interfaces are served by the runtime, built on a shared design system (`static/murphy-design-system.css`, `static/murphy-components.js`, `static/murphy-canvas.js`).

| File | User / Role | Type | Accent |
|---|---|---|---|
| `murphy_landing_page.html` | Public front door | Landing page | Teal `#00D4AA` |
| `onboarding_wizard.html` | New user (zero jargon) | Conversational (Librarian-powered) | Gold `#FFD166` |
| `terminal_unified.html` | Admin / Multi-role hub | Dashboard + All views | Violet `#8B6CE7` |
| `terminal_architect.html` | System Architect | Dashboard + Terminal | Teal `#00D4AA` |
| `terminal_enhanced.html` | Power User | Dashboard + Terminal | Pink `#E879F9` |
| `terminal_integrated.html` | Operations Manager | Dashboard | Blue `#3B9EFF` |
| `terminal_worker.html` | Delivery Worker | Dashboard | Amber `#FFA63E` |
| `terminal_costs.html` | Finance / Budget | Dashboard | Coral `#FF6B6B` |
| `terminal_orgchart.html` | HR / Admin | Dashboard | Green `#22C55E` |
| `terminal_integrations.html` | DevOps | Dashboard | Sky `#38BDF8` |
| `workflow_canvas.html` | Workflow Designer | Graphical canvas + Terminal | Cyan `#22D3EE` |
| `system_visualizer.html` | System Topology | Graphical canvas + Terminal | Indigo `#818CF8` |
| `murphy-smoke-test.html` | Developer / QA | API smoke test | Teal `#00D4AA` |
| `murphy_ui_integrated.html` | Legacy → redirects to `terminal_unified.html` | — | — |
| `murphy_ui_integrated_terminal.html` | Legacy → redirects to `terminal_unified.html` | — | — |

### Design System

All interfaces share a unified design system:
- **`static/murphy-design-system.css`** — CSS tokens, component classes, responsive breakpoints, dark/light themes, animations, accessibility
- **`static/murphy-components.js`** — Reusable JS components: API client, sidebar, topbar, table, chart, toast, modal, health polling, theme toggle, jargon tooltips, keyboard shortcuts, terminal panel, Librarian chat widget
- **`static/murphy-canvas.js`** — Canvas rendering engine for workflow and topology graphical UIs: nodes, edges, ports, pan/zoom, auto-layout
- **`static/murphy-icons.svg`** — 42 SVG icons (24×24, 2px stroke)
- See `docs/DESIGN_SYSTEM.md` for the complete design system reference.

---

## Configuration

| Source | Description |
|---|---|
| `.env` | Environment variables (secrets, feature flags, ports) — auto-generated by `setup_and_start.sh` |
| `src/config.py` | Pydantic `BaseSettings` — loads `.env` and provides typed config |
| `pyproject.toml` | Tool configurations (pytest, linters, etc.) |

Copy `.env.example` to `.env` (if not auto-generated by `setup_and_start.sh`) and edit values before starting. In development mode, no API key is required — the onboard LLM works out of the box.

### Backend Configuration

Murphy System supports **stub** (simulated) and **real** backends for database, connection pool, and email. The table below summarises the key environment variables that control which mode is active.

| Variable | Values | Default | Production default |
|---|---|---|---|
| `MURPHY_ENV` | `development`, `test`, `staging`, `production` | `development` | `production` |
| `MURPHY_DB_MODE` | `stub`, `live` | `stub` | **must be `live`** |
| `MURPHY_POOL_MODE` | `simulated`, `real` | `simulated` | **must be `real`** |
| `E2EE_STUB_ALLOWED` | `true`, `false` | `true` | `false` |
| `MURPHY_EMAIL_REQUIRED` | `true`, `false` | `false` | `true` |
| `MURPHY_ENABLED_PROTOCOLS` | comma-separated list | *(empty)* | set as needed |
| `MURPHY_LOG_FORMAT` | `text`, `json` | `text` | `json` |
| `MURPHY_MAX_RESPONSE_SIZE_MB` | float | `10` | `10` |

> **⚠️ Deployment note:** In `MURPHY_ENV=production` or `MURPHY_ENV=staging`, the system refuses to start with `MURPHY_DB_MODE=stub` or `MURPHY_POOL_MODE=simulated`. Set both to real values and configure the appropriate credentials before deploying.

---

## Testing

Tests live in the `tests/` directory.

```bash
python -m pytest tests/
```

### Performance Benchmarks

In-process control-plane throughput (measured 2026-03-10, 2-vCPU CI runner):

| Component | ops/s | p95 latency |
|-----------|-------|-------------|
| `UniversalControlPlane.create_automation()` | 1,242 | 1.51 ms |
| `GateExecutionWiring.evaluate_gates()` | 71,981 | 0.030 ms |
| Platform connector framework (simulated) | 248 | 21.4 ms |

HTTP throughput (1,000+ req/s target) is achieved via multi-worker uvicorn. Use the
Locust benchmark at `tests/benchmarks/locust_benchmark.py` against a running server.
Full results: `documentation/testing/BENCHMARK_RESULTS.md`.

### Integration Speed (SwissKiss Pipeline)

The SwissKiss pipeline (clone → analyze → license detect → dependency parse → risk scan → module gen → audit) completes in **under 300 seconds** per repository integration.

```bash
# Run integration speed benchmark (requires network access)
MURPHY_RUN_INTEGRATION_BENCHMARKS=1 python -m pytest tests/benchmarks/test_integration_speed.py -v
```

---

## Deployment

### Docker

```bash
docker build -t murphy-system .
docker compose up -d
```

`Dockerfile` and `docker-compose.yml` are in this directory.

### Kubernetes

Manifests are in the `k8s/` directory. Apply with:

```bash
kubectl apply -f k8s/
```

---

## Directory Structure

```
Murphy-System/
├── murphy_system_1.0_runtime.py   # Entry point — FastAPI server
├── murphy_terminal.py             # Optional Textual TUI
├── src/                           # 978 modules, 81 packages
│   ├── config.py                  # Pydantic settings
│   ├── confidence_engine/         # Murphy Formula / Gate / Confidence
│   ├── execution_engine/          # Task execution
│   ├── form_intake/               # Form processing
│   ├── learning_engine/           # Corrections & shadow-agent training
│   ├── supervisor_system/         # HITL monitoring
│   ├── nocode_workflow_terminal.py # Librarian-powered no-code workflow builder
│   ├── agent_monitor_dashboard.py  # Real-time agent monitoring dashboard
│   ├── onboarding_flow.py         # Org chart + onboarding + shadow agents
│   ├── ip_classification_engine.py # 3-tier IP classification & trade secrets
│   ├── credential_profile_system.py # HITL credential profiles & metrics
│   └── ...                        # Additional subsystem packages
├── tests/                         # Pytest test suite
├── docs/                          # Project documentation
├── scripts/                       # Utility & helper scripts
├── k8s/                           # Kubernetes manifests
├── monitoring/                    # Monitoring & observability config
├── Dockerfile                     # Container image definition
├── docker-compose.yml             # Multi-service orchestration
├── pyproject.toml                 # Tool configs (pytest, linters)
├── .env                           # Runtime environment variables
└── *.html                         # 14 web interface files + smoke test
```

---

## Subsystem Lookup

| Subsystem | Primary Module | Notes |
| --- | --- | --- |
| **Gate + Confidence** | `src/confidence_engine/` | G/D/H + 5D uncertainty |
| **Learning + Corrections** | `src/learning_engine/` | Shadow agent training pipeline |
| **Integration Engine** | `src/integration_engine/` | GitHub ingestion + HITL approvals |
| **Swarm System** | `src/true_swarm_system.py` | Dynamic swarm generation |
| **Governance** | `src/governance_framework/` | Scheduler + authority bands |
| **Persistence** | `src/persistence_manager.py`, `src/db.py` | JSON, SQLite, PostgreSQL backends; Alembic migrations |
| **Event Backbone** | `src/event_backbone.py` | Durable queues, retry, circuit breakers |
| **Delivery Adapters** | `src/delivery_adapters.py` | Document/email/chat/voice/translation |
| **Gate Execution** | `src/gate_execution_wiring.py` | Runtime gate enforcement + policy modes |
| **Self-Improvement** | `src/self_improvement_engine.py` | Feedback loops, calibration, remediation |
| **SLO Tracker** | `src/operational_slo_tracker.py` | Success rate, latency percentiles, SLO compliance |
| **Automation Scheduler** | `src/automation_scheduler.py` | Multi-project priority scheduling + load balancing |
| **Capability Map** | `src/capability_map.py` | AST-based module inventory, gap analysis, remediation |
| **Compliance Engine** | `src/compliance_engine.py` | GDPR/SOC2/HIPAA/PCI-DSS sensors, HITL approvals |
| **RBAC Governance** | `src/rbac_governance.py` | Multi-tenant RBAC, shadow agent governance |
| **Wingman Protocol** | `src/wingman_protocol.py` | Executor/validator pairing, deterministic validation |
| **Runtime Profile Compiler** | `src/runtime_profile_compiler.py` | Onboarding-to-profile, safety/autonomy controls |
| **Governance Kernel** | `src/governance_kernel.py` | Non-LLM enforcement, budget tracking, audit emission |
| **Control Plane Separation** | `src/control_plane_separation.py` | Planning/execution plane split, mode switching |
| **Durable Swarm Orchestrator** | `src/durable_swarm_orchestrator.py` | Budget-aware swarms, idempotency, circuit breaker |
| **Golden Path Bridge** | `src/golden_path_bridge.py` | Execution path capture, replay, similarity matching |
| **Org Chart Enforcement** | `src/org_chart_enforcement.py` | Role-bound permissions, escalation chains |
| **Shadow Agent Integration** | `src/shadow_agent_integration.py` | Shadow-agent org-chart parity, account/user controls |
| **Triage Rollcall Adapter** | `src/triage_rollcall_adapter.py` | Capability rollcall before swarm expansion, candidate ranking |
| **Rubix Evidence Adapter** | `src/rubix_evidence_adapter.py` | Deterministic evidence lane: CI, Bayesian, Monte Carlo, forecast |
| **HITL Autonomy Controller** | `src/hitl_autonomy_controller.py` | HITL arming/disarming, confidence-gated autonomy |
| **Freelancer Validator** | `src/freelancer_validator/` | Fiverr/Upwork adapters, org budgets, credential verification |
| **Platform Connector Framework** | `src/platform_connector_framework.py` | 90+ platform connectors (Slack, Jira, Salesforce, GitHub, AWS, …) |
| **Workflow DAG Engine** | `src/workflow_dag_engine.py` | DAG workflows: topological sort, parallel groups, conditional branching |
| **Security Hardening Config** | `src/security_hardening_config.py` | XSS/SQLi/path-traversal sanitization, CORS, rate limiting, CSP |
| **Authorization Enhancer** | `src/security_plane/authorization_enhancer.py` | Per-request ownership verification, audit trail |
| **Log Sanitizer** | `src/security_plane/log_sanitizer.py` | PII detection (8 types), automated redaction |
| **Bot Resource Quotas** | `src/security_plane/bot_resource_quotas.py` | Per-bot quotas, swarm aggregate limits, auto-suspension |
| **Swarm Communication Monitor** | `src/security_plane/swarm_communication_monitor.py` | DFS cycle detection, rate limiting, pattern detection |
| **Bot Identity Verifier** | `src/security_plane/bot_identity_verifier.py` | HMAC-SHA256 signing, identity registry, key revocation |
| **Bot Anomaly Detector** | `src/security_plane/bot_anomaly_detector.py` | Z-score anomaly detection, resource spikes |
| **Security Dashboard** | `src/security_plane/security_dashboard.py` | Unified event view, correlation, compliance reports |
| **Self-Introspection** | `src/self_introspection_module.py` | Runtime self-analysis and codebase scanning |
| **Self-Codebase Swarm** | `src/self_codebase_swarm.py` | Autonomous BMS spec generation and RFP parsing |
| **Cut Sheet Engine** | `src/cutsheet_engine.py` | Manufacturer data parsing and wiring diagram generation |
| **Visual Swarm Builder** | `src/visual_swarm_builder.py` | Visual pipeline construction for swarm workflows |
| **CEO Branch Activation** | `src/ceo_branch_activation.py` | Top-level autonomous decision-making and planning |
| **Production Assistant Engine** | `src/production_assistant_engine.py` | Request lifecycle and deliverable gate validation |

---

## Features

- **Autonomous Business Operations** — 978 source modules across 81 packages orchestrate end-to-end workflows without manual intervention
- **Multi-LLM Routing** — First-class support for Groq, OpenAI, Anthropic, Mistral, Gemini, and local models with automatic fallback
- **MFGC / 5U Gate System** — Murphy Formula Gate Confidence scoring gates every deliverable through confidence, validation, and human-review bands
- **Event-Driven Architecture** — Durable EventBackbone with retry, circuit breakers, and dead-letter queues
- **Security Hardening** — RBAC, ASGI middleware (RBACMiddleware, DLPScannerMiddleware, RiskClassification, PerUserRateLimit), HMAC signing, PII redaction
- **Self-Healing & Self-Improvement** — Autonomous repair, feedback loops, LearningEngineConnector, PatternRecognizer, PerformancePredictor
- **Compliance Engine** — GDPR, SOC2, HIPAA, PCI-DSS sensors with human-in-the-loop approvals
- **Multi-Tenant Workspaces** — Isolated tenant environments with per-user and per-bot resource quotas
- **Observability** — Prometheus metrics, Grafana dashboards, SLO tracker, alert rules
- **Kubernetes-Ready** — Helm chart, k8s manifests, Hetzner and Cloudflare deploy scripts

---

## Architecture

```
src/
├── runtime/           # FastAPI app, module loader, dependency bootstrap
│   ├── app.py         # 5 400+ line main application
│   └── murphy_system_core.py  # 11 000+ line core orchestrator
├── security_plane/    # RBAC, DLP, bot identity, anomaly detection
├── governance_kernel/ # Budget tracking, non-LLM enforcement, audit
├── event_backbone.py  # Durable pub/sub with circuit breakers
├── task_router.py     # Capability routing + SystemLibrarian
├── persistence_manager.py  # JSON / SQLite / PostgreSQL / WAL
└── ...978 modules total
```

**Request flow:**  
`POST /api/execute` → `TaskRouter` → `GovernanceKernel` → `AutomationIntegrationHub` → `EventBackbone` → workers → `FeedbackIntegrator` → `LearningEngineConnector`

---

## API Endpoints

See the [API Reference](#api-reference) section above for the full endpoint table, or visit **http://localhost:8000/docs** for the live Swagger UI.

| Category | Base Path | Description |
|---|---|---|
| Core | `/api/health`, `/api/status`, `/api/execute`, `/api/chat` | Health, status, execution, chat |
| Onboarding | `/api/onboarding/*`, `/api/onboarding-flow/*` | Wizard and corporate flow |
| Workflow | `/api/workflow-terminal/*`, `/api/forms/*` | No-code Librarian, plan generation |
| Security | `/api/credentials/*`, `/api/hitl/*` | HITL approvals, credential profiles |
| Observability | `/api/metrics`, `/api/dashboards/*` | Prometheus metrics, live dashboards |
| Swarm | `/api/swarm/*` | Founder-gated swarm orchestration |

---

## Configuration

All settings are provided via environment variables. Copy `.env.example` to `.env` and fill in values.

| Variable | Required | Description |
|---|---|---|
| `MURPHY_ENV` | yes | `development`, `staging`, or `production` |
| `MURPHY_API_KEYS` | yes | Comma-separated bearer tokens for API auth |
| `MURPHY_CORS_ORIGINS` | yes | Allowed CORS origins (comma-separated) |
| `GROQ_API_KEY` | recommended | Groq LLM API key — get free key at https://console.groq.com/keys |
| `OPENAI_API_KEY` | optional | OpenAI API key |
| `ANTHROPIC_API_KEY` | optional | Anthropic Claude API key |
| `DATABASE_URL` | optional | PostgreSQL URL — defaults to SQLite |
| `REDIS_URL` | optional | Redis URL for caching and pub/sub |
| `SECRET_KEY` | yes | HMAC signing secret (min 32 chars) |

---

## Testing

```bash
# Full test suite
python -m pytest tests/ --timeout=60 -q

# Specific module
python -m pytest tests/test_task_router.py -q

# Commissioning / launch-readiness gates
python -m pytest tests/commissioning/ -q
```

Coverage is enforced at ≥85% via `--cov-fail-under=85`.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed contribution guidelines, code style, and the PR checklist.

Quick summary:
1. Fork and create a feature branch
2. Add tests for new functionality
3. Ensure `python -m pytest tests/` passes
4. Submit a pull request — all PRs run the full CI matrix

---

## Security

Security issues should be reported privately to the maintainers — do **not** open a public issue.

Key security controls implemented:
- ASGI middleware stack: RBAC, DLP scanning, risk classification, per-user rate limiting
- HMAC-SHA256 bot identity signing with key rotation
- PII detection and automated redaction in all log statements
- Per-bot and per-swarm resource quotas with auto-suspension
- CSP headers, XSS/SQLi/path-traversal sanitization

See [security_hardening_config.py](src/security_hardening_config.py) and `src/security_plane/` for implementation details.

---

## License

Proprietary — All rights reserved. See [LICENSE](LICENSE) for terms.
