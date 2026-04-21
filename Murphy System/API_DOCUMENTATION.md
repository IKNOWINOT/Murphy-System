# Murphy System — API Documentation

> **Canonical REST API reference for the Murphy System platform.**  
> Server: `https://murphy.systems` (production) · `http://localhost:8000` (local)  
> All `/api/*` routes require `X-API-Key: <key>` when `MURPHY_API_KEY` env var is set.  
> All responses: `{"success": bool, "data": ..., "error": {"code": "...", "message": "..."}}`  
> Full route list: **[API_ROUTES.md](API_ROUTES.md)** · Full reference: **[docs/API_REFERENCE.md](docs/API_REFERENCE.md)**

---

## System

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/health | No | System health check — `{"status":"ok"}` |
| GET | /api/status | Yes | Full system status with engine states |
| GET | /api/readiness | Yes | Pre-flight deployment readiness report |
| GET | /api/manifest | No | Machine-readable list of all registered API endpoints |
| GET | /api/info | No | System info (version, uptime) |
| GET | /api/system/info | Yes | Detailed system information |
| GET | /api/config | Yes | Get system configuration |
| POST | /api/config | Yes | Update system configuration |

## Authentication

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/auth/login | No | Login with email + password |
| POST | /api/auth/logout | Yes | Logout current session |
| GET | /api/auth/me | Yes | Get current user profile |
| POST | /api/auth/change-password | Yes | Change account password |
| POST | /api/auth/request-password-reset | No | Request password reset email |
| POST | /api/auth/reset-password | No | Complete password reset with token |

## Credentials & API Keys

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/credentials/list | Yes | List all integration credentials and their configured status (secrets never returned) |
| POST | /api/credentials/store | Yes | Store an integration credential as a platform secret · Body: `{"integration":"deepinfra","credential":"di_…"}` |
| GET | /api/credentials/profiles | Yes | List credential profiles |
| POST | /api/credentials/profiles | Yes | Create a credential profile |
| GET | /api/credentials/metrics | Yes | Credential usage metrics |

## LLM / AI

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/llm/status | Yes | LLM provider configuration and health |
| POST | /api/llm/configure | Yes | Set active LLM provider · Body: `{"provider":"deepinfra","api_key":"…"}` |
| POST | /api/llm/test | Yes | Make a test call to verify the configured provider |
| GET | /api/llm/providers | Yes | List all available LLM providers with status |
| GET | /api/llm/selfcheck | No  | **LLM-SELFCHECK-001** — last startup self-inference result (provider that actually answered, latency, retry count, schema-verification outcome).  Surfaces silent onboard-fallback when a real API key is set. |
| POST | /api/llm/selfcheck/run | No  | **LLM-SELFCHECK-001** — re-run the self-check on demand. |
| GET | /api/rate-governor/prompt-status | No | **PROMPT-RATE-001** — per-tenant prompt rate-limiter diagnostics (human + swarm tiers). |

## Setup & Integrations

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/setup/checklist | Yes | Integration setup checklist with completion percentage |
| GET | /api/setup/api-collection/guide/{id} | Yes | Step-by-step guide for a specific integration |
| GET | /api/integrations | Yes | List all available integrations |

## Execution & Agents

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/execute | Yes | Submit a task for execution |
| GET | /api/agents | Yes | List active agents |
| GET | /api/agents/{agent_id} | Yes | Get agent detail |
| POST | /api/chat | Yes | Chat with the Murphy assistant |

## Governance & Gates

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/gates | Yes | List all governance gates |
| POST | /api/gates/{gate_id}/arm | Yes | Arm a governance gate |
| POST | /api/gates/{gate_id}/disarm | Yes | Disarm a governance gate |

## HITL (Human-in-the-Loop)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/hitl/queue | Yes | View HITL approval queue |
| POST | /api/hitl/qc/submit | Yes | Submit a deliverable for QC review |
| POST | /api/hitl/acceptance/submit | Yes | Submit for customer acceptance |

## Platform Self-Modification (PSM-001..PSM-004)

Distinct from per-tenant `/api/hitl/*`: this surface controls **Murphy
modifying its own code**. Operator-token-gated, RSC-Lyapunov-gated,
every outcome recorded in an immutable hash-chained ledger.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET  | /api/platform/self-modification/console | Operator token | HTML "operator-approved button" page (PSM-004) |
| POST | /api/platform/self-modification/launch  | Operator token | Launch a self-modification cycle (PSM-003); returns 202 + cycle_id |
| GET  | /api/platform/self-modification/ledger  | Operator token | Tail of the immutable ledger; verifies hash chain on every read |

**Auth header:** `X-Murphy-Platform-Operator: <token>` matched constant-time
against env var `MURPHY_PLATFORM_OPERATOR_TOKEN`. **Unconfigured token →
all requests refused (401).**

**Status codes** — `POST /launch`:
- `202` Accepted: cycle handed to orchestrator. Body has `cycle_id`,
  `proposal_id`, `ledger_seq`. Ledger entries written: `REQUESTED → APPROVED → LAUNCHED`.
- `409` RSC veto (Lyapunov unstable or consecutive-violation streak).
  Ledger: `REQUESTED → VETOED`.
- `503` RSC source missing or orchestrator unwired. Ledger:
  `REQUESTED → VETOED`/`FAILED`.
- `500` Orchestrator raised. Ledger: `REQUESTED → APPROVED → FAILED`.
- `422` Body validation failure. No partial writes.
- `401` Missing/invalid operator token. No partial writes.

**Ledger location:** `data/platform_self_edit_ledger.jsonl` (override
via `MURPHY_PLATFORM_SELF_EDIT_LEDGER_PATH`). Append-only; SHA-256 chain
detects tamper, sequence gaps, and broken `prev_hash` links.

## Trading

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/trading/start | Yes | Start the live trading engine |
| POST | /api/trading/stop | Yes | Stop the live trading engine |
| GET | /api/trading/status | Yes | Trading engine status |
| GET | /api/trading/portfolio | Yes | Current portfolio snapshot |
| GET | /api/trading/positions | Yes | Open positions |
| POST | /api/trading/sweep | Yes | Trigger profit sweep |

## Safety & Emergency

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/safety/status | Yes | Safety monitoring score and active alerts |
| POST | /api/emergency/stop | Yes | Emergency stop — halts all active automations |
| GET | /api/emergency/status | Yes | Emergency stop status |

## Admin

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/admin/stats | Admin | Platform statistics |
| GET | /api/admin/users | Admin | List all users |
| GET | /api/admin/organizations | Admin | List all organizations |
| GET | /api/admin/audit-log | Admin | Platform audit log |

---

## Module Instance Manager

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /module-instances/spawn | Yes | Spawn a new module instance |
| POST | /module-instances/{id}/despawn | Yes | Despawn an instance |
| GET | /module-instances/ | Yes | List all instances (filter by type/state) |
| GET | /module-instances/{id} | Yes | Get instance details |
| POST | /module-instances/viability/check | Yes | Pre-spawn viability check |
| POST | /module-instances/find-viable | Yes | Find viable instances by type/capabilities |
| GET | /module-instances/audit/trail | Yes | Audit trail (filter by instance_id) |
| GET | /module-instances/{id}/config-history | Yes | Configuration backward logic |
| GET | /module-instances/status/manager | Yes | Manager status overview |
| GET | /module-instances/status/resources | Yes | Resource availability |
| POST | /module-instances/types/register | Yes | Register a module type |
| POST | /module-instances/types/{type}/blacklist | Yes | Blacklist a module type |
| POST | /module-instances/bulk/despawn | Yes | Bulk despawn instances |

## Infrastructure (Extended)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/infrastructure/compare | Yes | Compare env against hetzner_load.sh requirements |

## Matrix Notifications

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/matrix/notify | Yes | Send Matrix notification for HITL events |

---

*464 total routes implemented · 55 UI pages · 708 test files*  
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post — BSL 1.1*
