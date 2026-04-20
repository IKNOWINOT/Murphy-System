# API Reference

Complete reference for the Murphy System REST API — endpoint groups, HTTP methods, and descriptions.

---

## Base URL

```
http://localhost:8000
```

The FastAPI application is created by `create_app()` in `src/runtime/app.py` and served
via uvicorn on port 8000 by default. Override with environment variables `MURPHY_HOST`
and `MURPHY_PORT` (see `.env.example` for all configuration options).

---

## Core Endpoint Groups

### Health & System Info

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/system/info` | System version, uptime, and loaded modules |
| `GET` | `/health` | Liveness / readiness probe |

### Forms & Execution

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/forms/plan-upload` | Upload a pre-existing automation plan |
| `POST` | `/api/forms/plan-generation` | Generate a plan from natural language |
| `POST` | `/api/forms/task-execution` | Execute a validated task |
| `POST` | `/api/forms/validation` | Validate an execution packet |
| `POST` | `/api/forms/correction` | Submit a correction to an execution |

### Human-in-the-Loop (HITL)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/hitl/queue` | Return HITL approval queue |
| `GET` | `/api/hitl/pending` | Alias for pending items (terminal UI) |
| `GET` | `/api/hitl/interventions/pending` | Get pending HITL interventions |
| `POST` | `/api/hitl/interventions/{id}/respond` | Respond to intervention (approved/rejected/resolved/deferred/escalated) |
| `GET` | `/api/hitl/statistics` | Get HITL statistics |
| `POST` | `/api/hitl/qc/submit` | Submit for Quality Control review |
| `POST` | `/api/hitl/acceptance/submit` | Submit for User Acceptance review |
| `POST` | `/api/hitl/{tid}/decide` | Accept/reject/request revisions on QC or acceptance item |

### Corrections

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/corrections/*` | List correction history |
| `POST` | `/api/corrections/*` | Submit a new correction |

### Platform Self-Automation

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/platform/automation-status` | Unified overview of all 5 self-automation systems |
| `GET` | `/api/self-fix/status` | SelfFixLoop status |
| `POST` | `/api/self-fix/run` | Trigger self-fix cycle |
| `GET` | `/api/repair/status` | AutonomousRepairSystem status |
| `POST` | `/api/repair/scan` | Run repair scan |
| `GET` | `/api/scheduler/status` | MurphyScheduler status |
| `POST` | `/api/scheduler/run` | Execute scheduled tasks |
| `GET` | `/api/self-automation/status` | SelfAutomationOrchestrator status |
| `POST` | `/api/self-automation/cycle` | Run automation cycle |
| `GET` | `/api/self-improvement/status` | SelfImprovementEngine status |
| `POST` | `/api/self-improvement/analyse` | Run self-improvement analysis |

### Workflows

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/workflows/generate` | Generate workflow from natural language description |
| `POST` | `/api/workflows/{id}/execute` | Execute a workflow (tier-gated) |

### Compliance

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/compliance/toggles` | Get compliance framework toggles |
| `POST` | `/api/compliance/toggles` | Save compliance toggles (tier-gated enforcement, conflict detection) |

### Organisation & Agents

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/orgchart/inoni-agents` | Inoni LLC agent org chart (23 agents, 8 departments, 70+ automations) |

### Creator Moderation

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/creator/moderation/check` | Free content moderation — spam detection, toxicity scoring |

### SDK & Platform

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/sdk/status` | SDK availability and language support |
| `GET` | `/api/platform/capabilities` | 12 licensable platform capabilities |
| `GET` | `/api/demo/export` | Demo export bundle (BSL-1.1 licensed) |

### Authentication

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/auth/signup` | Create account (bcrypt hashed, sets session cookie) |
| `POST` | `/api/auth/login` | Sign in (sets HttpOnly murphy_session cookie) |
| `POST` | `/api/auth/logout` | Sign out (clears session) |
| `GET` | `/api/auth/providers` | List available OAuth providers |
| `GET` | `/api/profiles/me` | Get current user profile |

### Onboarding Wizard

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/onboarding/wizard/questions` | Get all setup wizard questions |
| `POST` | `/api/onboarding/wizard/answer` | Submit answer to a wizard question |
| `GET` | `/api/onboarding/wizard/profile` | Get current wizard profile state |
| `POST` | `/api/onboarding/wizard/validate` | Validate the profile |
| `POST` | `/api/onboarding/wizard/generate-config` | Generate Murphy config from answers |
| `GET` | `/api/onboarding/wizard/summary` | Get human-readable summary |
| `POST` | `/api/onboarding/wizard/reset` | Reset wizard to start over |

### Librarian & Chat

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/chat` | Send natural-language message to Murphy |
| `POST` | `/api/librarian/ask` | Ask the Librarian (modes: ask, execute) |
| `GET` | `/api/librarian/status` | Librarian health status |
| `GET` | `/api/llm/status` | LLM provider config & health |
| `POST` | `/api/llm/configure` | Hot-reload LLM configuration |
| `POST` | `/api/llm/test` | Test LLM connectivity |

### AionMind 2.0 Cognitive Pipeline

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/aionmind/status` | Cognitive pipeline status |
| `POST` | `/api/aionmind/context` | Push structured context |
| `POST` | `/api/aionmind/orchestrate` | Orchestrate a cognitive task |
| `POST` | `/api/aionmind/execute` | Execute via cognitive pipeline |
| `GET` | `/api/aionmind/proposals` | List pending proposals |
| `GET` | `/api/aionmind/memory` | Query STM/LTM memory |

### Module Routers (Monday.com Parity)

| Phase | Path Prefix | Description |
|-------|-------------|-------------|
| 1 | `/api/boards` | Board system — items, groups, columns |
| 2 | `/api/collaboration` | Real-time collaboration features |
| 3 | `/api/dashboards` | Dashboard widgets and views |
| 4 | `/api/portfolio` | Portfolio management |
| 5 | `/api/workdocs` | Collaborative documents |
| 6 | `/api/time-tracking` | Time tracking entries |
| 7 | `/api/automations` | Automation rules and triggers |
| 8 | `/api/crm` | CRM contacts, deals, pipelines |
| 9 | `/api/dev` | Developer tools and integrations |
| 10 | `/api/service` | Service desk and tickets |
| 11 | `/api/guest` | Guest collaboration |
| 12 | `/api/mobile` | Mobile-optimised endpoints |

---

## Authentication & Security

The API tier is secured by `src/fastapi_security.py` which provides:

- **CORS allowlist** — configured via `MURPHY_CORS_ORIGINS` environment variable.
- **API key authentication** — required for sensitive endpoints.
- **RBAC enforcement** — role-based permission checks on execute/configure actions.
- **Rate limiting** — per-client request throttling.

```bash
# Example: authenticated request
curl -H "Authorization: Bearer $API_KEY" http://localhost:8000/api/system/info
```

---

## Error Response Format

All errors follow a consistent JSON envelope:

```json
{
  "error": "Human-readable error message",
  "code": "ERROR_CODE"
}
```

---

## See Also

- [User Guide](USER_GUIDE.md)
- [API Overview](../api/API_OVERVIEW.md)
- [Endpoints](../api/ENDPOINTS.md)
- [API Examples](api/API_EXAMPLES.md)
