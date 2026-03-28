# Murphy System — Execution Engine Architecture

**Copyright © 2020 Inoni Limited Liability Company — BSL-1.1**
**Commissioned: Wave 5 Production Readiness Audit (2026-03)**

## Overview

The Execution Engine is a three-layer orchestration system that transforms user requests
into verified, auditable, production-grade automation workflows. It comprises three
independent orchestrators unified under a single FastAPI API surface.

```
┌─────────────────────────────────────────────────────────────────┐
│                    Unified FastAPI Server                        │
│                  src/runtime/app.py (create_app)                │
│                                                                 │
│  ┌─────────────────┐  ┌──────────────────┐  ┌───────────────┐  │
│  │ Production       │  │ Execution Router │  │ Runtime       │  │
│  │ Router (58 rts)  │  │ (14 routes)      │  │ Routes (1059) │  │
│  └────────┬────────┘  └────────┬─────────┘  └───────────────┘  │
│           │                    │                                 │
│           ▼                    ▼                                 │
│  murphy_production_     ┌──────────────┐                        │
│  server.py (standalone) │ /api/execution/*                      │
│                         ├──────────────┤                        │
│                         │ Two-Phase    │ → two_phase_orchestrator.py      │
│                         │ UCP          │ → universal_control_plane.py     │
│                         │ Packet Exec  │ → src/execution_orchestrator/    │
│                         └──────────────┘                        │
└─────────────────────────────────────────────────────────────────┘
```

## Architecture Components

### 1. Two-Phase Orchestrator (`two_phase_orchestrator.py`)

A generative-then-execute pipeline for complex automation workflows.

**Phase 1 — Generative Setup:**
- `InformationGatheringAgent` — Collects domain context and requirements
- `RegulationDiscoveryAgent` — Discovers applicable regulations and constraints
- `ConstraintCompiler` — Compiles constraints into enforceable rules
- `AgentGenerator` — Dynamically generates specialized agents for the task
- `SandboxManager` — Creates isolated execution environments

**Phase 2 — Production Execution:**
- Executes the generated workflow with constraint enforcement
- Produces deliverables (reports, documents, configurations)
- Captures learning data for future improvement

**API Routes:**

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/execution/two-phase/create` | Create a new automation |
| POST | `/api/execution/two-phase/run` | Execute an automation |
| GET | `/api/execution/two-phase/{automation_id}` | Get automation status |
| GET | `/api/execution/two-phase/` | List all automations |

### 2. Universal Control Plane (`universal_control_plane.py`)

Session-based control with isolated engine sets per workflow type.

**Engine Types:**
- `SensorEngine` — Data collection and monitoring
- `ActuatorEngine` — Physical/logical state changes
- `DatabaseEngine` — Persistent storage operations
- `APIEngine` — External service integration
- `ContentEngine` — Content generation and management
- `CommandEngine` — System command execution
- `AgentEngine` — AI agent orchestration

**Session Isolation:**
Each session loads only the engines relevant to its domain:
- HVAC workflows → Sensor + Actuator engines
- Blog workflows → Content + API engines
- Manufacturing → Sensor + Actuator + Database engines

**API Routes:**

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/execution/ucp/create` | Create a control session |
| POST | `/api/execution/ucp/run` | Execute within a session |
| GET | `/api/execution/ucp/{session_id}` | Get session details |
| GET | `/api/execution/ucp/` | List all sessions |
| DELETE | `/api/execution/ucp/{session_id}` | Teardown a session |

### 3. Execution Orchestrator (`src/execution_orchestrator/`)

Packet-based execution with cryptographic signature validation,
replay prevention, and authority-based approval routing.

**Core Classes:**
- `ExecutionOrchestrator` — Main orchestration logic
- `RiskMonitor` — Real-time risk assessment
- `RollbackManager` — Transaction rollback on failure
- `TelemetryCollector` — Execution telemetry
- `Validator` — Input/output validation
- `CompletionTracker` — Tracks execution completion

**Security Features:**
- Packet signatures via `security_plane/cryptography.py`
- Replay prevention (single-use packet IDs)
- Authority band enforcement (NONE → LOW → MEDIUM → HIGH → CRITICAL)
- Automatic approval routing based on risk level

**API Routes:**

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/execution/packet/execute` | Execute a signed packet |
| POST | `/api/execution/packet/approve` | Approve a pending packet |
| GET | `/api/execution/packet/pending` | List pending approvals |
| GET | `/api/execution/packet/history` | Execution history |

**Standalone Flask API** (`src/execution_orchestrator/api.py`):
Also available as a standalone Flask service for independent deployment.
Not wired to the unified FastAPI server — use for microservice architectures.

### 4. Execution Engine Package (`src/execution_engine/`)

Low-level execution primitives shared across orchestrators:

| Module | Purpose |
|--------|---------|
| `decision_engine.py` | Decision tree evaluation |
| `execution_context.py` | Execution state and context |
| `execution_orchestrator.py` | Core orchestration primitives |
| `form_execution_models.py` | Form-based execution data models |
| `form_executor.py` | Form workflow execution |
| `integrated_form_executor.py` | Integrated form + workflow execution |
| `state_manager.py` | Execution state persistence |
| `task_executor.py` | Individual task execution |
| `workflow_orchestrator.py` | Workflow DAG execution (used by UCP) |

## Wiring

### Router: `src/execution_router.py`

The execution router is a FastAPI `APIRouter` that:
1. Lazy-initializes all three orchestrators on first startup
2. Exposes 14 routes under `/api/execution/*`
3. Handles initialization failures gracefully (503 with error details)
4. Reports health status of all orchestrators

### Integration: `src/runtime/app.py`

The execution router is included in `create_app()` after the production router:

```python
from src.execution_router import router as _exec_router
from src.execution_router import execution_router_startup as _exec_startup
app.include_router(_exec_router)

@app.on_event("startup")
async def _run_execution_startup():
    await _exec_startup()
```

### Authentication

All execution routes require API key authentication via `src/auth_middleware.py`.
The `/api/execution/health` endpoint also requires authentication (unlike `/api/health`).

## Security Integration

The execution system integrates with the security plane:

- **Packet Signing**: `security_plane/cryptography.py` → `PacketSigner`
  - ECDSA P-256 (real) + Dilithium (simulated via HMAC)
  - `KeyManager` handles key lifecycle and rotation
- **Authority Bands**: `security_plane/schemas.py` → `AuthorityBand`
  - NONE, LOW, MEDIUM, HIGH, CRITICAL
  - Higher bands require explicit human approval
- **Lightweight Auth**: `src/auth_middleware.py` (production default)
- **Advanced Security**: `security_plane/middleware.py` (optional, for high-security deployments)

## Docker

The Dockerfile copies both root-level orchestrator files:
```dockerfile
COPY two_phase_orchestrator.py universal_control_plane.py ./
```

The `src/` directory (containing execution_engine/, execution_orchestrator/, security_plane/)
is copied via:
```dockerfile
COPY src/ ./src/
```

## Testing

Commissioning tests in `tests/commissioning/`:

| File | Tests | Coverage |
|------|-------|---------|
| `test_wave5_execution_router.py` | 16 | Route registration, auth, imports, instantiation |
| `test_wave6_security_plane.py` | 37 | Crypto lifecycle, all 17 modules |
| `test_wave8_docker_k8s.py` | 31 | Docker/K8s manifest validation |

Pre-existing tests:
- `tests/test_two_phase_orchestrator_execution.py` — Phase 1+2 lifecycle via runtime
- `tests/test_execution_orchestrator.py` — Packet execution, risk, telemetry
- `tests/test_security_cryptography.py` — Full crypto test suite
- `tests/test_control_plane.py` — Control plane integration