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

Rate limiting: 100 requests/minute per IP for anonymous; 1,000 requests/minute
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

## Wingman Protocol Endpoints

### `POST /api/wingman/pairs`

Create a new executor/validator pair.

**Auth:** Required  
**Content-Type:** `application/json`

**Request Body**
```json
{
  "subject": "invoice-processing",
  "executor_id": "agent-001",
  "validator_id": "agent-002",
  "runbook_id": "runbook-finance-v1"
}
```

**Response 201**
```json
{ "pair_id": "uuid-v4", "subject": "invoice-processing", "created_at": "2026-03-08T08:00:00Z" }
```

---

### `POST /api/wingman/validate`

Run validation for a given pair against an output payload.

**Auth:** Required

**Request Body**
```json
{ "pair_id": "uuid-v4", "output": { "data": "..." }, "context": {} }
```

**Response 200**
```json
{
  "passed": true,
  "blocked": false,
  "warnings": [],
  "results": [
    { "rule_id": "r-001", "passed": true, "severity": "block", "message": "Output present" }
  ]
}
```

---

### `GET /api/wingman/pairs/{pair_id}/status`

Get current status and recent history for a pair.

**Auth:** Required

**Response 200**
```json
{ "pair_id": "uuid-v4", "subject": "invoice-processing", "history_count": 42 }
```

---

## Causality Sandbox Endpoints

### `POST /api/causality/cycle`

Submit a what-if scenario for causal simulation.

**Auth:** Required  
**Content-Type:** `application/json`

**Request Body**
```json
{ "scenario": "What happens if throughput drops 20%?", "context": {}, "depth": 3 }
```

**Response 200**
```json
{
  "cycle_id": "uuid-v4",
  "root_cause": "Throughput reduction",
  "causal_chain": ["queue_depth_increases", "latency_spikes", "timeout_rate_rises"],
  "confidence": 0.87
}
```

---

### `GET /api/causality/results/{cycle_id}`

Retrieve simulation results for a completed cycle.

**Auth:** Required

**Response 200**
```json
{ "cycle_id": "uuid-v4", "status": "complete", "summary": "...", "confidence": 0.87 }
```

---

## HITL Graduation Endpoints

### `POST /api/hitl-graduation/register`

Register a task or workflow item for HITL graduation evaluation.

**Auth:** Required  
**Content-Type:** `application/json`

**Request Body**
```json
{ "item_id": "task-001", "category": "invoice-approval", "metadata": {} }
```

**Response 201**
```json
{ "item_id": "task-001", "graduation_status": "pending", "registered_at": "2026-03-08T08:00:00Z" }
```

---

### `POST /api/hitl-graduation/evaluate/{item_id}`

Trigger evaluation of a registered item against graduation criteria.

**Auth:** Required

**Response 200**
```json
{ "item_id": "task-001", "score": 0.91, "criteria_met": true, "ready_for_graduation": true }
```

---

### `POST /api/hitl-graduation/graduate/{item_id}`

Graduate an item from human oversight to automated handling.

**Auth:** Required

**Response 200**
```json
{ "item_id": "task-001", "graduation_status": "graduated", "graduated_at": "2026-03-08T08:05:00Z" }
```

---

### `POST /api/hitl-graduation/rollback/{item_id}`

Rollback a graduated item back to human oversight.

**Auth:** Required

**Request Body**
```json
{ "reason": "Confidence threshold dropped below 0.80" }
```

**Response 200**
```json
{ "item_id": "task-001", "graduation_status": "rolled_back", "reason": "Confidence threshold dropped below 0.80" }
```

---

### `GET /api/hitl-graduation/dashboard`

Overview of all registered items, graduation rates, and recent activity.

**Auth:** Required

**Response 200**
```json
{
  "total": 120, "graduated": 88, "pending": 20, "rolled_back": 12,
  "graduation_rate": 0.73
}
```

---

## Functionality Heatmap Endpoints

### `POST /api/heatmap/activity`

Record an activity event for heatmap tracking.

**Auth:** Required  
**Content-Type:** `application/json`

**Request Body**
```json
{ "module": "invoice_processor", "function": "parse_invoice", "duration_ms": 42 }
```

**Response 200**
```json
{ "recorded": true }
```

---

### `GET /api/heatmap`

Retrieve the full functionality heatmap.

**Auth:** Required

**Response 200**
```json
{
  "generated_at": "2026-03-08T08:00:00Z",
  "modules": [
    { "module": "invoice_processor", "call_count": 5421, "avg_duration_ms": 38, "temperature": "hot" }
  ]
}
```

---

### `GET /api/heatmap/cold-spots`

List modules with low or zero activity (coverage gaps).

**Auth:** Required

**Response 200**
```json
{ "cold_spots": [{ "module": "archive_exporter", "call_count": 0, "last_called": null }] }
```

---

### `GET /api/heatmap/hot-spots`

List the most actively used modules.

**Auth:** Required

**Response 200**
```json
{ "hot_spots": [{ "module": "invoice_processor", "call_count": 5421 }] }
```

---

### `GET /api/heatmap/coverage`

Return overall module coverage metrics.

**Auth:** Required

**Response 200**
```json
{ "total_modules": 650, "active_modules": 498, "coverage_pct": 76.6 }
```

---

## Safety Orchestrator Endpoints

### `POST /api/safety/check`

Run a safety check against a proposed action or payload.

**Auth:** Required  
**Content-Type:** `application/json`

**Request Body**
```json
{ "action": "deploy_to_production", "payload": {}, "context": {} }
```

**Response 200**
```json
{ "safe": true, "checks_passed": 12, "checks_failed": 0, "report": [] }
```

---

### `GET /api/safety/dashboard`

Safety posture overview: recent checks, failure rates, compliance status.

**Auth:** Required

**Response 200**
```json
{ "checks_today": 482, "failures_today": 3, "failure_rate": 0.006, "status": "green" }
```

---

### `GET /api/safety/compliance`

Compliance summary across configured frameworks.

**Auth:** Required

**Response 200**
```json
{
  "frameworks": ["gdpr", "soc2", "hipaa", "pci_dss"],
  "aligned": ["gdpr", "soc2"],
  "gaps": ["hipaa", "pci_dss"]
}
```

---

## Efficiency Orchestrator Endpoints

### `POST /api/efficiency/readings`

Record an efficiency reading for a module or pipeline stage.

**Auth:** Required  
**Content-Type:** `application/json`

**Request Body**
```json
{ "module": "invoice_processor", "metric": "throughput", "value": 120.5, "unit": "tasks/min" }
```

**Response 200**
```json
{ "recorded": true }
```

---

### `GET /api/efficiency/scores`

Retrieve efficiency scores for all tracked modules.

**Auth:** Required

**Response 200**
```json
{
  "scores": [
    { "module": "invoice_processor", "score": 0.91, "trend": "improving" }
  ]
}
```

---

### `GET /api/efficiency/optimisations`

Get recommended optimisation actions based on current efficiency data.

**Auth:** Required

**Response 200**
```json
{
  "recommendations": [
    { "module": "archive_exporter", "recommendation": "Enable async processing", "estimated_gain": 0.25 }
  ]
}
```

---

## Supply Orchestrator Endpoints

### `POST /api/supply/register`

Register a supply item (hardware, software license, API quota, etc.).

**Auth:** Required  
**Content-Type:** `application/json`

**Request Body**
```json
{ "item_id": "gpu-node-01", "category": "compute", "quantity": 4, "unit": "nodes" }
```

**Response 201**
```json
{ "item_id": "gpu-node-01", "registered": true }
```

---

### `POST /api/supply/usage`

Record usage of a supply item.

**Auth:** Required

**Request Body**
```json
{ "item_id": "gpu-node-01", "quantity_used": 1, "task_id": "task-001" }
```

**Response 200**
```json
{ "recorded": true, "remaining": 3 }
```

---

### `POST /api/supply/receipts`

Record receipt of new supply stock.

**Auth:** Required

**Request Body**
```json
{ "item_id": "gpu-node-01", "quantity_received": 2, "received_at": "2026-03-08T08:00:00Z" }
```

**Response 200**
```json
{ "recorded": true, "new_total": 5 }
```

---

### `GET /api/supply/reorder`

List items that have fallen below their reorder threshold.

**Auth:** Required

**Response 200**
```json
{ "reorder_needed": [{ "item_id": "api-quota-groq", "current": 500, "threshold": 1000 }] }
```

---

### `GET /api/supply/dashboard`

Supply chain overview: inventory levels, recent transactions, reorder alerts.

**Auth:** Required

**Response 200**
```json
{
  "total_items": 38,
  "below_threshold": 2,
  "recent_transactions": 14,
  "status": "yellow"
}
```

---

*Copyright © 2020 Inoni Limited Liability Company | Creator: Corey Post | License: BSL 1.1*
