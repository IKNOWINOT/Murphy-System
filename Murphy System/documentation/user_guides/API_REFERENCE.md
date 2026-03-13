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
| `GET` | `/api/hitl/*` | List pending HITL interventions |
| `POST` | `/api/hitl/*` | Approve or reject a HITL gate |

### Corrections

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/corrections/*` | List correction history |
| `POST` | `/api/corrections/*` | Submit a new correction |

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
