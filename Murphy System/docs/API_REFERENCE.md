# Murphy System — API Reference

**Version:** 1.0.0  
**Base URL:** `http://localhost:8000`  
**Auth:** Bearer token via `Authorization: Bearer <token>` header (see Authentication below)  
**License:** BSL 1.1

---

## Authentication

All endpoints except `/api/health` require a valid Bearer token.  Tokens are
issued by the auth subsystem (`src/flask_security.py` / `src/fastapi_security.py`).

```
Authorization: Bearer <your-token>
```

Rate limiting: 100 requests/minute per IP for anonymous; 1 000 requests/minute
for authenticated users (configurable via `MURPHY_RATE_LIMIT` env var).

---

## Core Endpoints

### `GET /api/health`

Liveness probe — returns 200 if the process is alive.

**Auth:** None required  
**Rate limit:** Exempt

**Response 200**
```json
{ "status": "ok", "version": "1.0.0", "uptime_seconds": 12345 }
```

---

### `GET /api/status`

System status dashboard — includes module registry, LLM state, active gates.

**Auth:** Required  
**Rate limit:** Standard

**Response 200**
```json
{
  "status": "operational",
  "modules_loaded": 625,
  "llm_enabled": true,
  "llm_provider": "groq",
  "active_gates": ["security", "compliance", "governance"],
  "uptime_seconds": 12345,
  "version": "1.0.0"
}
```

---

### `POST /api/execute`

Execute a task through the Murphy orchestration pipeline.

**Auth:** Required  
**Rate limit:** 60 req/min per user  
**Content-Type:** `application/json`

**Request Body**
```json
{
  "task": "string — natural language task description",
  "context": { "key": "value" },
  "timeout_seconds": 30,
  "use_llm": true
}
```

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `task` | string | ✅ | — | Natural language task description |
| `context` | object | ❌ | `{}` | Additional context key-value pairs |
| `timeout_seconds` | integer | ❌ | `30` | Max execution time (1–300) |
| `use_llm` | boolean | ❌ | `true` | Whether to route through LLM if available |

**Response 200**
```json
{
  "success": true,
  "result": "...",
  "confidence": 0.92,
  "execution_time_ms": 342,
  "gate_results": { "security": "pass", "compliance": "pass" },
  "audit_id": "uuid-v4"
}
```

**Response 422** — Validation error
```json
{ "detail": [{ "loc": ["body", "task"], "msg": "field required", "type": "value_error.missing" }] }
```

**Response 429** — Rate limit exceeded
```json
{ "detail": "Rate limit exceeded. Retry after 42 seconds." }
```

---

## LLM Endpoints

### `GET /api/llm/configure`

Returns the current LLM configuration (provider, model, key mask).

**Auth:** Required  
**Rate limit:** Standard

**Response 200**
```json
{
  "provider": "groq",
  "model": "llama3-70b-8192",
  "key_configured": true,
  "key_mask": "gsk_...xxxx"
}
```

---

### `POST /api/llm/configure`

Configure the LLM provider and API key (hot-reload, no restart needed).

**Auth:** Required (admin scope)  
**Rate limit:** 10 req/min per user  
**Content-Type:** `application/json`

**Request Body**
```json
{
  "provider": "groq",
  "api_key": "gsk_your_key_here"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `provider` | string | ✅ | One of: `groq`, `openai`, `anthropic`, `local` |
| `api_key` | string | ✅ | API key for the chosen provider |

**Response 200**
```json
{ "success": true, "provider": "groq", "model": "llama3-70b-8192" }
```

**Response 400** — Invalid provider or key format
```json
{ "success": false, "error": "Invalid API key format for provider 'groq'" }
```

---

### `POST /api/llm/test`

Test LLM connectivity with the currently configured key.

**Auth:** Required  
**Rate limit:** 10 req/min per user

**Response 200 — success**
```json
{ "success": true, "provider": "groq", "model": "llama3-70b-8192", "latency_ms": 312 }
```

**Response 200 — failure**
```json
{ "success": false, "error": "Authentication failed: invalid API key" }
```

---

## Gate Endpoints

### `GET /api/gates`

List all registered gates and their current status.

**Auth:** Required  
**Rate limit:** Standard

**Response 200**
```json
{
  "gates": [
    { "name": "security", "enabled": true, "policy": "strict" },
    { "name": "compliance", "enabled": true, "policy": "gdpr_soc2" },
    { "name": "governance", "enabled": true, "policy": "rbac_v2" }
  ]
}
```

---

### `GET /api/gates/{gate_name}`

Get details for a specific gate.

**Auth:** Required  
**Path Parameter:** `gate_name` — gate identifier string

**Response 200**
```json
{
  "name": "security",
  "enabled": true,
  "policy": "strict",
  "last_evaluation": "2026-03-07T05:44:56Z",
  "pass_count": 1234,
  "fail_count": 7
}
```

**Response 404**
```json
{ "detail": "Gate 'unknown' not found" }
```

---

### `POST /api/gates/{gate_name}/evaluate`

Run a gate evaluation against a payload without executing the full task.

**Auth:** Required  
**Content-Type:** `application/json`

**Request Body**
```json
{ "payload": { "task": "...", "context": {} } }
```

**Response 200**
```json
{ "gate": "security", "result": "pass", "score": 0.98, "reasons": [] }
```

---

## Confidence Engine Endpoints

### `GET /api/confidence/status`

Returns the current confidence engine calibration state.

**Auth:** Required

**Response 200**
```json
{
  "calibrated": true,
  "gdh_score": 0.87,
  "uncertainty_5d": { "epistemic": 0.05, "aleatoric": 0.08, "model": 0.03, "data": 0.06, "domain": 0.04 },
  "last_calibration": "2026-03-07T00:00:00Z"
}
```

---

### `POST /api/confidence/evaluate`

Score a candidate response against the confidence engine.

**Auth:** Required  
**Content-Type:** `application/json`

**Request Body**
```json
{
  "response": "string — candidate output to score",
  "context": { "domain": "finance", "task_type": "classification" }
}
```

**Response 200**
```json
{
  "confidence": 0.91,
  "gdh_breakdown": { "generative": 0.88, "discriminative": 0.93, "hybrid": 0.91 },
  "uncertainty_5d": { "epistemic": 0.04, "aleatoric": 0.06, "model": 0.02, "data": 0.05, "domain": 0.03 },
  "recommendation": "accept"
}
```

---

## Orchestrator Endpoints

### `GET /api/orchestrator/status`

Returns the orchestrator pipeline status.

**Auth:** Required

**Response 200**
```json
{
  "active_tasks": 3,
  "queued_tasks": 7,
  "completed_today": 142,
  "failed_today": 2,
  "average_latency_ms": 420
}
```

---

### `GET /api/orchestrator/tasks`

List recent tasks with their status.

**Auth:** Required  
**Query Parameters:**
- `limit` (int, default 20, max 100) — number of tasks to return
- `status` (string, optional) — filter by `pending`, `running`, `completed`, `failed`

**Response 200**
```json
{
  "tasks": [
    {
      "audit_id": "uuid-v4",
      "task": "Generate weekly sales report",
      "status": "completed",
      "created_at": "2026-03-07T05:00:00Z",
      "completed_at": "2026-03-07T05:00:01Z",
      "confidence": 0.94
    }
  ],
  "total": 142,
  "page": 1
}
```

---

## Module Endpoints

### `GET /api/modules`

Returns status for all registered modules.

**Auth:** Required

**Response 200**
```json
{
  "total": 625,
  "loaded": 620,
  "failed": 5,
  "modules": [
    { "name": "llm_controller", "status": "ok", "version": "1.0.0" }
  ]
}
```

---

### `GET /api/modules/{name}/status`

Get per-module status.

**Auth:** Required

**Response 200**
```json
{ "name": "llm_controller", "status": "ok", "last_check": "2026-03-07T05:44:00Z" }
```

---

## Feedback Endpoint

### `POST /api/feedback`

Submit a feedback signal to improve confidence calibration.

**Auth:** Required  
**Content-Type:** `application/json`

**Request Body**
```json
{
  "audit_id": "uuid-v4 — the task audit ID",
  "signal": "positive",
  "score": 0.95,
  "notes": "optional free text"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `audit_id` | string | ✅ | UUID of the task execution |
| `signal` | string | ✅ | One of: `positive`, `negative`, `neutral` |
| `score` | float | ❌ | 0.0–1.0 human quality rating |
| `notes` | string | ❌ | Free text feedback |

**Response 200**
```json
{ "accepted": true, "recalibrating": false }
```

---

## Error Codes

| HTTP Status | Meaning |
|---|---|
| 200 | Success |
| 400 | Bad request — invalid parameters |
| 401 | Unauthorized — missing or invalid token |
| 403 | Forbidden — insufficient scope |
| 404 | Not found |
| 422 | Unprocessable entity — schema validation failed |
| 429 | Rate limit exceeded |
| 500 | Internal server error |
| 503 | Service unavailable — LLM or dependency offline |

---

*Copyright © 2020 Inoni Limited Liability Company | Creator: Corey Post | License: BSL 1.1*
