# Getting Started with Murphy System

**License:** BSL 1.1 — *Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post*

---

## System Architecture Overview

Murphy System is a **Universal AI Automation System** built around a single paradigm:

```
DESCRIBE → EXECUTE → REFINE
```

1. **DESCRIBE** — Tell Murphy what you want in plain English via the Librarian terminal
   (`POST /api/workflow-terminal/message`, powered by [`nocode_workflow_terminal.py`](src/nocode_workflow_terminal.py))

2. **EXECUTE** — [`ai_workflow_generator.py`](src/ai_workflow_generator.py) converts your description into a governed
   DAG workflow (`POST /api/forms/plan-generation`) using a 3-tier strategy: template
   matching → keyword inference → generic fallback. The workflow then runs through
   [`workflow_orchestrator.py`](src/execution_engine/workflow_orchestrator.py) with full gate enforcement
   ([`gate_execution_wiring.py`](src/gate_execution_wiring.py)) across six gates:
   EXECUTIVE / OPERATIONS / QA / HITL / COMPLIANCE / BUDGET.

3. **REFINE** *(optional)* — [`workflow_canvas.html`](workflow_canvas.html) lets you visually tweak any
   step of the generated DAG before or after execution.

**Key supporting subsystems:** Event Backbone (pub/sub, retry, circuit breakers),
Self-Healing Coordinator (5 recovery handlers), Confidence Engine (Bayesian scoring,
Murphy Index), Learning Engine (full ML closed loop → threshold auto-adjustment),
and the AionMind Kernel (cognitive execution with legacy fallback).

**Voice/Typed Command Automation:** Murphy supports natural language automation via 
Voice Command Interface (VCI) and generative preset activation. See the comprehensive
[Generative Automation Presets Guide](documentation/features/GENERATIVE_AUTOMATION_PRESETS.md)
for details on template matching, industry presets, role-based execution, and HITL governance.

See the full [README](README.md) for the complete module map and completion status,
and [ROADMAP.md](ROADMAP.md) for the sprint plan.

---

## 1. Quick Start

### Prerequisites

| Requirement | Minimum | Notes |
|---|---|---|
| Python | 3.10+ | `python3 --version` must show ≥ 3.10 |
| RAM | 4 GB | 8 GB recommended for LLM-enabled mode |
| Disk | 2 GB free | For dependencies and logs |
| OS | Linux, macOS, or Windows | All three are supported |

### Clone and start

```bash
git clone https://github.com/IKNOWINOT/Murphy-System.git
cd Murphy-System
bash setup_and_start.sh
```

On Windows:

```cmd
git clone https://github.com/IKNOWINOT/Murphy-System.git
cd Murphy-System
setup_and_start.bat
```

`setup_and_start.sh` handles everything:

1. Checks Python 3.10+ and pip
2. Creates a virtual environment and installs dependencies from `requirements_murphy_1.0.txt`
3. Generates a default `.env` with `MURPHY_LLM_PROVIDER=local` (no API key required)
4. Creates runtime directories (logs, data, modules, sessions)
5. Starts the backend server

Expected output:

```
INFO:     Murphy System 1.0 starting...
INFO:     Module registry: 1,122 modules loaded
INFO:     Governance kernel: active
INFO:     HITL gates: enabled
INFO:     Librarian: capability map loaded (610 capabilities)
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

---

## 1b. Configure (Optional)

The `Murphy System/config/` directory contains YAML files with sensible defaults for all runtime settings. You can customise them before starting:

```bash
# Edit main system settings (LLM provider, thresholds, logging, tenant limits):
nano "Murphy System/config/murphy.yaml"

# Edit engine settings (swarm parameters, gate thresholds, orchestrator timeouts):
nano "Murphy System/config/engines.yaml"
```

Environment variables **always override YAML values** — so you can also override individual settings without touching any file:

```bash
export MURPHY_LLM_PROVIDER=groq   # override LLM provider
export LOG_LEVEL=DEBUG             # override log level
export MURPHY_API__PORT=9000       # override API port (namespaced syntax)
```

See `Murphy System/config/murphy.yaml.example` and `Murphy System/config/engines.yaml.example` for a fully-annotated reference of every available setting.

> **Secrets** (API keys, passwords) must never go in YAML files. Add them to `Murphy System/.env` or use a secrets manager.

---

## 2. What You Get

Murphy System is a universal AI-governed automation platform that applies formal control theory — confidence scoring, safety gates, and human-in-the-loop checkpoints — to any operational domain.

It is not a simple API wrapper or task queue. It is a control plane.

Every action Murphy takes passes through a governance pipeline that scores confidence, validates against domain-specific safety gates, optionally routes to a human operator for approval, and records a cryptographic audit trail. The same architecture that governs a low-stakes content generation task also governs a high-stakes trading order or a Kubernetes deployment rollout.

Out of the box you get:

- **1,122 modules** across 71 packages — AI orchestration, governance gates, business automation, trading, enterprise ops, compliance, robotics, and self-healing
- **90 audit categories** covering security, compliance, performance, data integrity, access control, financial, operational, and infrastructure concerns
- A two-phase execution model (Generative Setup → Production Execute) with the Wingman Protocol
- A full suite of web-based terminals and dashboards (see [§ 5. Terminal](#5-terminal))
- A FastAPI-based REST API on port 8000 with interactive Swagger docs (see [§ 4. REST API](#4-rest-api))

**Commercial goal:** Murphy System is designed to be licensed as a SaaS product under BSL 1.1. Operators embed it into their business operations as a supervised automation layer — not a black-box agent, but an AI executive assistant with verifiable decision provenance.

---

## 3. The Real Architecture

### Core runtime

The heart of Murphy System is `murphy_system_1.0_runtime.py` — a 700+ KB single Python file that implements the full server, orchestration layer, and control plane. It is large by design: the runtime is the integration surface. All domain logic lives in the module library (`src/`), which the runtime loads, governs, and orchestrates.

### Two-phase execution model

Every task moves through two phases:

```
Phase 1 — Generative Setup
  - Librarian identifies which capabilities match the task
  - Solution paths are ranked (Librarian score × historical performance)
  - Gates pre-screen each path (budget, compliance, security)
  - HITL checkpoint if confidence is below threshold or gate requires it

Phase 2 — Production Execute
  - Selected path executes via the Wingman Protocol (executor + validator pair)
  - Confidence Engine monitors execution and raises alerts
  - Audit trail written to BlockchainAuditTrail or local ledger
  - Outcome fed back to FeedbackIntegrator for future routing improvement
```

### 1,100+ source modules

`src/` contains 922 Python modules across 77 packages. A representative selection:

**AI and LLM orchestration**
- `llm_controller.py` — routes prompts to the configured LLM provider
- `enhanced_local_llm.py` — onboard inference (no API key required)
- `inference_gate_engine.py` — validates LLM outputs before use
- `safe_llm_wrapper.py` — sanitisation and safety filters

**Governance gates**
- `governance_kernel.py` — master gate orchestrator
- `gate_builder.py` — declarative gate composition
- `gate_bypass_controller.py` — controlled bypass with audit trail
- `authority_gate.py` — RBAC-based execution authority
- `niche_viability_gate.py` — business viability pre-screening
- `cost_explosion_gate.py` — budget runaway prevention

**Business automation**
- `inoni_business_automation.py` — end-to-end business process automation
- `niche_business_generator.py` — domain-specific business workflow generation
- `business_scaling_engine.py` — automated scaling decision-making
- `sales_automation.py` — CRM and pipeline automation
- `invoice_processing_pipeline.py` — accounts receivable automation

**Trading and finance**
- `trading_bot_engine.py` — strategy execution engine
- `trading_strategy_engine.py` — multi-strategy portfolio management
- `crypto_exchange_connector.py` — unified exchange interface
- `coinbase_connector.py` — Coinbase-specific integration
- `crypto_wallet_manager.py` — wallet and key management

**Enterprise operations**
- `kubernetes_deployment.py` — K8s cluster management
- `docker_containerization.py` — container lifecycle management
- `multi_cloud_orchestrator.py` — multi-provider cloud control
- `ci_cd_pipeline_manager.py` — pipeline creation and monitoring

**Compliance and security**
- `compliance_engine.py` — multi-framework compliance checking
- `compliance_as_code_engine.py` — policy-as-code enforcement
- `rbac_governance.py` — role-based access control
- `security_audit_scanner.py` — continuous security assessment
- `blockchain_audit_trail.py` — immutable execution ledger

**Robotics, IoT, and physical systems**
- `murphy_sensor_fusion.py` — multi-sensor data fusion
- `building_automation_connectors.py` — BACnet/Modbus connectors
- `energy_management_connectors.py` — energy monitoring and control
- `additive_manufacturing_connectors.py` — 3D printer fleet management

**Self-healing and resilience**
- `self_fix_loop.py` — autonomous error detection and repair
- `autonomous_repair_system.py` — multi-layer fault recovery
- `murphy_code_healer.py` — runtime code patch application
- `self_healing_coordinator.py` — repair sequencing and prioritisation
- `chaos_resilience_loop.py` — chaos engineering and blast radius control

---

## 4. REST API

Murphy System exposes a FastAPI server on **port 8000**. All endpoints return JSON. While the server is running, interactive Swagger documentation is available at `http://localhost:8000/docs`.

### Health check

```bash
curl http://localhost:8000/api/health
```

Expected (shallow probe, always 200):

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "db_mode": "stub"
}
```

The `db_mode` field shows the current database mode (`stub` by default; `live` when `DATABASE_URL` is set with `MURPHY_DB_MODE=live`).

For a full deep readiness check:

```bash
curl "http://localhost:8000/api/health?deep=true"
```

Returns all subsystem states including database connectivity and connection-pool metrics:

```json
{
  "status": "healthy",
  "checks": {
    "runtime":        "ok",
    "persistence":    "ok",
    "database":       "ok",
    "db_mode":        "live",
    "db_pool":        {"pool_size": 5, "checked_in": 5, "checked_out": 0, "overflow": 0, "invalid": 0},
    "redis":          "not_configured",
    "llm":            "ok",
    "event_backbone": "ok",
    "modules_loaded": 1122,
    "version":        "1.0.0"
  },
  "critical_failures": []
}
```

### System status

```bash
curl http://localhost:8000/api/status
```

Returns runtime metrics including loaded module count, active gates, uptime, and resource usage.

### Gate status

```bash
curl http://localhost:8000/api/gates/status
```

Expected:

```json
{
  "active_gates": [
    {"name": "security",    "state": "armed"},
    {"name": "compliance",  "state": "armed"},
    {"name": "authority",   "state": "armed"},
    {"name": "budget",      "state": "armed"},
    {"name": "hitl",        "state": "armed"}
  ],
  "governance_mode": "strict"
}
```

### Librarian query

Ask the Librarian what capabilities match a task description:

```bash
curl -X POST http://localhost:8000/api/librarian/query \
     -H "Content-Type: application/json" \
     -d '{"query": "generate an invoice for a consulting project"}'
```

Expected:

```json
{
  "query": "generate an invoice for a consulting project",
  "matches": [
    {
      "capability_id": "invoice_processing_pipeline",
      "score": 0.94,
      "cost_estimate": "low",
      "determinism": "deterministic",
      "match_reasons": ["domain:finance", "keyword:invoice", "keyword:generate"]
    },
    {
      "capability_id": "niche_business_generator",
      "score": 0.71,
      "cost_estimate": "medium",
      "determinism": "stochastic",
      "match_reasons": ["domain:business", "keyword:generate"]
    }
  ]
}
```

### Execute a task

```bash
curl -X POST http://localhost:8000/api/execute \
     -H "Content-Type: application/json" \
     -d '{
       "task": "generate invoice",
       "amount": 5000,
       "client": "Acme Corp",
       "description": "Q1 consulting services"
     }'
```

Expected:

```json
{
  "success": true,
  "task_id": "7f3a1b2c-...",
  "solution_path": "invoice_processing_pipeline",
  "confidence": 0.94,
  "execution_time_ms": 312,
  "gate_results": {
    "security":   "pass",
    "compliance": "pass",
    "authority":  "pass",
    "budget":     "pass"
  },
  "wingman": {
    "executor": "invoice_processing_pipeline",
    "validator": "invoice_validator",
    "validator_result": "pass"
  },
  "audit_id": "a1b2c3d4-..."
}
```

### Send a chat message

```bash
curl -X POST http://localhost:8000/api/chat \
     -H "Content-Type: application/json" \
     -d '{"message": "What capabilities do you have for finance automation?"}'
```

Expected:

```json
{
  "response": "Murphy System includes the following finance automation capabilities: ...",
  "capabilities_referenced": ["invoice_processing_pipeline", "sales_automation", "trading_bot_engine"],
  "confidence": 0.88
}
```

### Additional endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/schedule` | POST | Register scheduled or one-time tasks |
| `/api/rules` | POST | Create alert-based trigger rules |
| `/api/gates/define` | POST | Declaratively define a governance gate |
| `/api/gates/generate` | POST | Auto-generate domain gate specifications |
| `/docs` | GET | Interactive Swagger UI |

---

## 5. Terminal

Murphy System ships with a set of browser-based HTML interfaces. All interfaces share a single design system (`static/murphy-design-system.css`, `static/murphy-components.js`) with a dark-only theme (`#0C1017` base, teal/cyan accents). No light mode.

Serve any interface by opening it directly or via the backend static route while the server is running on port 8000.

| Interface | User / Role | Type |
|---|---|---|
| `murphy_landing_page.html` | Public front door | Landing page |
| `onboarding_wizard.html` | New user (zero jargon) | Conversational (Librarian-powered) |
| `terminal_unified.html` | Admin / Multi-role hub | Dashboard + All views |
| `terminal_architect.html` | System Architect | Dashboard + Terminal |
| `terminal_enhanced.html` | Power User | Dashboard + Terminal |
| `terminal_integrated.html` | Operations Manager | Dashboard |
| `terminal_worker.html` | Delivery Worker | Dashboard |
| `terminal_costs.html` | Finance / Budget | Dashboard |
| `terminal_orgchart.html` | HR / Admin | Dashboard |
| `terminal_integrations.html` | DevOps | Dashboard |
| `workflow_canvas.html` | Workflow Designer | Graphical canvas + Terminal |
| `system_visualizer.html` | System Topology | Graphical canvas + Terminal |
| `murphy-smoke-test.html` | Developer / QA | API smoke test |
| `murphy_ui_integrated.html` | Legacy → redirects to `terminal_unified.html` | — |
| `murphy_ui_integrated_terminal.html` | Legacy → redirects to `terminal_unified.html` | — |

---

## 6. Schedules, Conditions, and Domain Generative Gates

This is the layer of Murphy System that makes it *proactive* rather than purely reactive. Three building blocks work together to allow you to define the rules of your domain — and have the system enforce and route around them automatically.

### Schedules

Tasks can be triggered on a schedule, not just by inbound API calls. The `AutomationScheduler` and `AutonomousScheduler` handle two scheduling modes:

**Cron-based recurring tasks** — run at a fixed interval or time of day:

```bash
curl -X POST http://localhost:8000/api/schedule \
     -H "Content-Type: application/json" \
     -d '{
       "project_id": "daily-invoice-reconciliation",
       "task_description": "Reconcile outstanding invoices",
       "task_type": "invoice_processing_pipeline",
       "priority": "medium",
       "cron_expression": "0 6 * * *",
       "parameters": { "account": "AR", "currency": "USD" }
     }'
```

This registers a `ProjectSchedule` that fires every day at 06:00, passes through the Librarian for capability matching, and executes via the normal gate + Wingman pipeline.

**Priority-queued one-time tasks** — submit tasks with explicit priorities so the scheduler dispatches them in order when capacity is available:

```bash
curl -X POST http://localhost:8000/api/schedule \
     -H "Content-Type: application/json" \
     -d '{
       "project_id": "eod-trading-report",
       "task_description": "Generate end-of-day trading summary",
       "task_type": "trading_strategy_engine",
       "priority": "high"
     }'
```

**Condition-triggered tasks** — the `AlertRulesEngine` watches metric values and fires tasks when thresholds are crossed:

```bash
curl -X POST http://localhost:8000/api/rules \
     -H "Content-Type: application/json" \
     -d '{
       "rule_id": "cpu-overload-scale-out",
       "name": "Scale out when CPU > 85%",
       "severity": "critical",
       "metric": "cpu_utilization",
       "comparator": "gt",
       "threshold": 85,
       "cooldown_seconds": 300,
       "action": {
         "task_type": "kubernetes_deployment",
         "parameters": { "operation": "scale_out", "replicas_delta": 2 }
       }
     }'
```

When the metric crosses the threshold, the rule fires: the action task is submitted to the scheduler at `critical` priority, goes through the Librarian, passes gates, and executes. The `cooldown_seconds` field prevents the same rule from re-firing until the cooldown expires — preventing alert storms.

The `GovernanceScheduler` wraps all scheduling decisions with governance enforcement: authority precedence (higher-authority tasks pre-empt lower), resource containment (no task can exceed its declared resource envelope), and dependency resolution (tasks with declared dependencies wait until their prerequisites complete).

---

### Conditions and Rules

A **condition** is a predicate over a named parameter: `parameter operator expected_value`. Conditions are the atomic unit of decision logic throughout Murphy System.

`GateCondition` examples:

| `parameter` | `operator` | `expected_value` | Meaning |
|---|---|---|---|
| `confidence_score` | `>=` | `0.85` | Execution confidence must meet threshold |
| `cost_estimate_usd` | `<=` | `500` | Task cost must stay under budget |
| `compliance_domain` | `==` | `"healthcare"` | Task is in a healthcare context |
| `change_type` | `in` | `["schema_drop", "data_delete"]` | Destructive change types |
| `test_coverage_pct` | `>=` | `80` | Minimum test coverage |

Conditions can be assembled into a **gate** declaratively:

```bash
curl -X POST http://localhost:8000/api/gates/define \
     -H "Content-Type: application/json" \
     -d '{
       "name": "healthcare_compliance_gate",
       "gate_type": "compliance",
       "severity": "critical",
       "conditions": [
         {
           "parameter": "compliance_domain",
           "operator": "==",
           "expected_value": "healthcare"
         },
         {
           "parameter": "data_contains_phi",
           "operator": "==",
           "expected_value": true
         }
       ],
       "wired_function": "validate_compliance_hipaa",
       "fail_actions": [{ "action_type": "block", "target": "execution" }],
       "pass_actions": [{ "action_type": "proceed", "target": "execution" }]
     }'
```

This defines a gate that fires whenever PHI data is present in a healthcare context and invokes the `validate_compliance_hipaa` function. The gate is now live — every task that matches those conditions will be checked before execution.

Conditions can also drive alert rules (metric threshold → task trigger), trigger conditions in the `macro_trigger_engine` (combat state or agent state predicates → behavior trigger), or serve as retry/escalation logic inside `GateAction` definitions.

---

### Domain Generative Gates

Rather than defining every gate by hand, the `DomainGateGenerator` can **generate a complete gate specification for an entire domain from a requirements dict**. It pulls domain knowledge from the `LibrarianKnowledgeBase`, applies templates for best practices and regulatory standards, and returns a set of `DomainGate` objects fully wired to their validator functions.

```bash
curl -X POST http://localhost:8000/api/gates/generate \
     -H "Content-Type: application/json" \
     -d '{
       "domain": "healthcare",
       "complexity": "complex",
       "regulatory_requirements": ["hipaa", "soc2"],
       "security_focus": true,
       "performance_requirements": {
         "max_latency_ms": 200,
         "max_error_rate": 0.001
       }
     }'
```

What happens internally:

```
DomainGateGenerator.generate_gates_for_system(requirements)
  │
  ├── LibrarianKnowledgeBase.get_gate_templates("healthcare")
  │     Returns: HIPAA data handling, PHI access controls, audit logging,
  │              breach notification, minimum necessary access, ...
  │
  ├── _generate_domain_specific_gates("healthcare", requirements)
  │     Adds: PHI encryption gate, identity verification gate,
  │           consent verification gate
  │
  ├── _generate_complexity_gates("complex", requirements)
  │     Adds: integration testing gate, load testing gate,
  │           dependency graph validation gate
  │
  ├── _generate_security_gates(requirements)
  │     Adds: vulnerability scan gate, penetration test gate
  │
  └── _generate_performance_gates(requirements)
        Adds: latency gate (≤200ms), error rate gate (≤0.1%)
```

The result is a complete domain specification — a set of named, typed, severity-ranked gates each wired to a validation function. This specification is then registered with the `GovernanceKernel` and becomes the live gate policy for any task operating in that domain.

**The Librarian uses this specification when ranking solution paths.** If the Librarian sees that the active domain is `healthcare`, it filters the capability list using the generated gate specification: capabilities that structurally cannot satisfy the `hipaa` gate (e.g., a module that has no HIPAA compliance annotation) are ranked down or excluded entirely before the routing result is returned. The operator never sees a suggestion that would fail before it even starts.

Supported domains for gate generation:
- `software` — code review, test coverage, documentation, security scanning
- `infrastructure` — change management, backup verification, availability, scalability
- `data` — data quality, lineage, retention policy, access controls
- `healthcare` — HIPAA, PHI handling, audit logging, consent
- `finance` — PCI-DSS, AML, fraud detection, audit trail
- `trading` — order validation, risk limits, market data integrity, circuit breakers
- Any custom domain — define your own knowledge base entries and templates

**The full pipeline:**

```
1. You define your domain requirements (regulatory, architectural, budget, performance)
2. DomainGateGenerator generates the gate spec from LibrarianKnowledgeBase templates
3. Gates are registered with GovernanceKernel — they are now live
4. Schedules register recurring tasks (cron) or condition-triggered tasks (AlertRules)
5. When a task arrives (scheduled or on-demand):
     a. TaskRouter asks SystemLibrarian for capability matches
     b. Librarian filters against the active gate spec for the domain
     c. Only gate-compatible paths are returned as SolutionPaths
     d. GovernanceKernel validates each path through the actual gates
     e. Best approved path executes via Wingman Protocol
6. Outcome recorded → FeedbackIntegrator → next routing improved
```

This is the closed loop: your domain rules produce gates → gates produce a specification → the Librarian tailors the automation to only what your rules allow.

---

## 7. First-Class Concepts

**The Librarian**
The `SystemLibrarian` is the routing brain. It consumes the live `ModuleRegistry.get_capabilities()` feed and scores every registered capability against an incoming task. No capability can be invoked without passing through the Librarian's ranking (or an explicit HITL override). The Librarian works with the `librarian_bot` TypeScript semantic search service for higher-quality matching.

**The Confidence Engine**
The `ConfidenceEngine` assigns a numerical confidence score (0.0–1.0) to every proposed execution. Scores below a configurable threshold (`MURPHY_CONFIDENCE_THRESHOLD`, default 0.75) are automatically routed to the HITL queue rather than executed autonomously. The confidence score incorporates gate pre-screening, historical performance from the `FeedbackIntegrator`, and the Librarian's match quality.

**The Gate System**
Gates are composable validation checkpoints. Each gate checks a specific concern: budget (`cost_explosion_gate.py`), authority (`authority_gate.py`), compliance (`compliance_engine.py`), security (`security_audit_scanner.py`). The `GovernanceKernel` orchestrates gate execution and enforces the gate policy. Gates can return `pass`, `fail`, or `hitl_required`. A `fail` blocks execution immediately. A `hitl_required` suspends execution and routes to a human operator.

**The Wingman Protocol**
Every task that executes in production does so as a Wingman pair: an Executor module performs the action, and a Validator module independently verifies the result before the execution is marked complete. Neither half can mark success without the other. This prevents silent failures.

**HITL Graduation Engine**
The `HITLGraduationEngine` manages the human-to-automation handoff pipeline. Capabilities start supervised (every execution requires human approval). As a capability accumulates a successful track record (configurable success rate and minimum run count), the engine automatically graduates it to semi-autonomous or fully autonomous execution. Graduation can be revoked if the success rate drops.

**The Solution Path Registry**
When the Librarian finds multiple ways to complete a task, all alternatives are stored in the `SolutionPathRegistry`. This enables HITL operators to see all options ("I found 3 ways to do this"), the system to fall back to alternative paths if the primary fails, and the `FeedbackIntegrator` to learn which paths work best over time.

---

## 8. Authentication

In development mode (`MURPHY_ENV=development`, the default), all endpoints are accessible without an API key.

For production deployments, `SecureKeyManager` auto-generates API keys on first boot. Use as a Bearer token:

```bash
curl -H "Authorization: Bearer <your-generated-key>" \
     http://localhost:8000/api/status
```

### What to explore next

| Resource | Purpose |
|---|---|
| `docs/LIBRARIAN_ROUTING_SPEC.md` | Technical spec for Librarian-driven task routing |
| `docs/FLATTENING_PLAN.md` | Phased plan for upcoming structural improvements |
| `Murphy System/docs/API_REFERENCE.md` | Complete API reference |
| `Murphy System/docs/DESIGN_SYSTEM.md` | UI design system documentation |
| `Murphy System/docs/WINGMAN_PROTOCOL.md` | Wingman executor/validator protocol |
| `Murphy System/docs/MODULE_REGISTRY.md` | Full module capability registry |
| `Murphy System/ARCHITECTURE_MAP.md` | System architecture overview |
| `http://localhost:8000/docs` | Interactive Swagger UI (while server is running) |
| `http://localhost:8000` | Murphy landing page |

---

## 9. Troubleshooting

### `python3 --version` shows 3.9 or lower

Install Python 3.10 or later:

```bash
# Ubuntu / Debian
sudo apt install python3.10

# macOS (Homebrew)
brew install python@3.10

# Windows — download installer from python.org
```

### `Address already in use` on port 8000

Another process is using port 8000. Stop it or use a different port:

```bash
MURPHY_PORT=8001 bash setup_and_start.sh
```

### Health check returns connection refused

Murphy is still starting (usually under 5 seconds) or failed to start. Check the server terminal for errors. Common cause: a dependency failed to install — re-run `bash setup_and_start.sh`.

### Gates reporting `fail` in execute response

A governance gate blocked the request. Check the `gate_results` field for which gate failed. For local testing, you can temporarily set `GOVERNANCE_STRICT=false` in `.env`.

### Librarian returns empty matches

The module registry may not have loaded correctly. Check for errors in the server log with `INFO: Module registry:`. If the count is 0, ensure `src/` exists relative to the working directory.

---

## 10. Database Setup

> **Important:** Murphy System runs in **stub mode** by default — all SQL
> operations return fake fixture data and nothing is persisted.  Follow
> the steps below to connect a real database.

### Quick start (SQLite — zero config)

Add two lines to your `.env` file (in the `Murphy-System/` directory):

```bash
DATABASE_URL=sqlite:///murphy_logs.db
MURPHY_DB_MODE=live
```

Restart the server.  A real SQLite database file will be created automatically.

### PostgreSQL (recommended for production)

```bash
DATABASE_URL=postgresql://username:password@localhost:5432/murphy
MURPHY_DB_MODE=live
MURPHY_ENV=production
MURPHY_AUTO_MIGRATE=false   # Run migrations explicitly in production
```

### Running Alembic migrations

Auto-migration is **on by default** in development/test (controlled by `MURPHY_AUTO_MIGRATE`).
In production, run migrations manually before each deploy:

```bash
cd Murphy-System
bash Murphy\ System/scripts/db_migrate.sh              # Apply all pending
bash Murphy\ System/scripts/db_migrate.sh status       # Check current state
bash Murphy\ System/scripts/db_migrate.sh history      # Full history
bash Murphy\ System/scripts/db_migrate.sh downgrade -1 # Revert last
```

### Database modes

| Mode | `MURPHY_DB_MODE` | Behaviour |
|------|-----------------|-----------|
| **Stub** (default) | `stub` | All SQL returns fake data; large WARNING in logs |
| **Live / SQLite** | `live` | Real DB, no server required |
| **Live / PostgreSQL** | `live` | Real DB, production-grade |

> Stub mode is **rejected at startup** in `production` and `staging`
> environments with a `RuntimeError`.

### Database troubleshooting

**Server logs show stub mode banner:** Set `DATABASE_URL` and `MURPHY_DB_MODE=live` in `.env`.

**Migration error at startup:** Check that `DATABASE_URL` is reachable and run
`bash Murphy\ System/scripts/db_migrate.sh status` to inspect the current state.

**Pool exhaustion (`checked_out` equals `pool_size` in health check):** Increase
`MURPHY_DB_POOL_SIZE` (default 5) and `MURPHY_DB_MAX_OVERFLOW` (default 10).

---

## 11. Test Suite

The project includes 118 gap-closure test files and 14,800+ total tests.
Run the full suite with `python -m pytest tests/ -v` from the `Murphy System/` directory.

---

*Murphy System v1.0 — BSL 1.1 — Inoni LLC*
