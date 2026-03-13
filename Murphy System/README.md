# Murphy System — Runtime Directory

> **📖 Canonical documentation:** See the [root README](../README.md) for full
> project documentation, architecture, and getting-started instructions.

This is the primary runtime directory for the Murphy System. It contains the
FastAPI server, 750+ source modules across 60 packages in `src/`, web interfaces,
tests, and deployment configuration.

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
Murphy System/
├── murphy_system_1.0_runtime.py   # Entry point — FastAPI server
├── murphy_terminal.py             # Optional Textual TUI
├── src/                           # 753 modules, 60 packages
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
