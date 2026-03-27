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
| POST | /api/credentials/store | Yes | Store an integration credential as a platform secret · Body: `{"integration":"groq","credential":"gsk_…"}` |
| GET | /api/credentials/profiles | Yes | List credential profiles |
| POST | /api/credentials/profiles | Yes | Create a credential profile |
| GET | /api/credentials/metrics | Yes | Credential usage metrics |

## LLM / AI

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/llm/status | Yes | LLM provider configuration and health |
| POST | /api/llm/configure | Yes | Set active LLM provider · Body: `{"provider":"groq","api_key":"…"}` |
| POST | /api/llm/test | Yes | Make a test call to verify the configured provider |
| GET | /api/llm/providers | Yes | List all available LLM providers with status |

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

*451 total routes implemented · 52 UI pages · 706 test files*  
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post — BSL 1.1*
