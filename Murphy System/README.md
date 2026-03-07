# Murphy System — Runtime Directory

This is the primary runtime directory for the Murphy System. It contains the
FastAPI server, 625 source modules across 56 packages in `src/`, web interfaces,
tests, and deployment configuration.

---

## Quick Start

```bash
pip install -r requirements_murphy_1.0.txt   # install dependencies
python murphy_system_1.0_runtime.py           # FastAPI server on :8000
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

Full auto-generated docs: **http://localhost:8000/docs**

---

## Web Interfaces

Eight static HTML files are served by the runtime or a local HTTP server:

| File | Purpose |
|---|---|
| `onboarding_wizard.html` | Step-by-step new-user onboarding |
| `murphy_landing_page.html` | Main landing / dashboard page |
| `murphy_ui_integrated.html` | Integrated management UI |
| `murphy_ui_integrated_terminal.html` | Terminal-style integrated UI |
| `terminal_architect.html` | Architect-role terminal |
| `terminal_enhanced.html` | Enhanced terminal with extra tooling |
| `terminal_integrated.html` | Integrated terminal view |
| `terminal_worker.html` | Worker-role terminal |

---

## Configuration

| Source | Description |
|---|---|
| `.env` | Environment variables (secrets, feature flags, ports) |
| `src/config.py` | Pydantic `BaseSettings` — loads `.env` and provides typed config |
| `pyproject.toml` | Tool configurations (pytest, linters, etc.) |

Copy `.env.example` to `.env` (if provided) and edit values before starting.

---

## Testing

Tests live in the `tests/` directory.

```bash
python -m pytest tests/
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
├── src/                           # 625 modules, 56 packages
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
└── *.html                         # 8 web interface files
```
