# Murphy System — API Reference

**Version:** 1.0.0  
**Base URL:** `http://localhost:8000`  
**Auth:** Session cookie (`murphy_session`) or Bearer token — see Authentication below  
**License:** BSL 1.1

---

## Authentication

Murphy System uses **session-based authentication** managed by `src/fastapi_security.py`.
Sessions are created by `/api/auth/signup` and `/api/auth/login` and validated on every
protected request via the `SecurityMiddleware`.

### How it works

| Client type | Auth mechanism |
|-------------|----------------|
| Browser (HTML pages) | `murphy_session` HttpOnly cookie — sent automatically with every request |
| SPA / JS API calls | `Authorization: Bearer <session_token>` header |
| Server-to-server | `X-API-Key: <key>` header (or Bearer for JWT-signed tokens) |

The middleware checks credentials in this order:
1. `X-API-Key` header
2. `Authorization: Bearer` header (JWT → session token → API key fallback)
3. `murphy_session` cookie

### Obtaining a session token

**Email / password flow**

```
POST /api/auth/signup   → 200 { session_token, account_id, … } + Set-Cookie: murphy_session
POST /api/auth/login    → 200 { session_token, account_id, … } + Set-Cookie: murphy_session
```

Store `session_token` in `localStorage` (`murphy_session_token`) so that the
`MurphyAPI` JavaScript class can attach it as a Bearer header on subsequent
AJAX requests.

**OAuth flow**

```
GET /api/auth/oauth/{provider}   → redirects to provider
GET /api/auth/callback           → sets murphy_session cookie, redirects to /ui/terminal-unified?oauth_success=1
GET /api/auth/session-token      → 200 { session_token }   (called by murphy_auth.js after the redirect)
```

### Using the token

```
Authorization: Bearer <session_token>
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
  "llm_provider": "deepinfra",
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
  "provider": "deepinfra",
  "model": "meta-llama/Meta-Llama-3.1-70B-Instruct",
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
  "provider": "deepinfra",
  "api_key": "gsk_your_key_here"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `provider` | string | ✅ | One of: `deepinfra`, `openai`, `anthropic`, `local` |
| `api_key` | string | ✅ | API key for the chosen provider |

**Response 200**
```json
{ "success": true, "provider": "deepinfra", "model": "meta-llama/Meta-Llama-3.1-70B-Instruct" }
```

**Response 400** — Invalid provider or key format
```json
{ "success": false, "error": "Invalid API key format for provider 'deepinfra'" }
```

---

### `POST /api/llm/test`

Test LLM connectivity with the currently configured key.

**Auth:** Required  
**Rate limit:** 10 req/min per user

**Response 200 — success**
```json
{ "success": true, "provider": "deepinfra", "model": "meta-llama/Meta-Llama-3.1-70B-Instruct", "latency_ms": 312 }
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
{ "reorder_needed": [{ "item_id": "api-quota-deepinfra", "current": 500, "threshold": 1000 }] }
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

---

## Crypto Trading Subsystem

> All trading and transfer operations require HITL (Human-in-the-Loop) approval by default.
> Bots start in `MANUAL` mode; auto-approval requires explicit graduation to `SUPERVISED` or `AUTOMATED`.

---

### `POST /api/trading/bots`

Create a new trading bot.

**Auth:** Required  
**Body:**
```json
{
  "exchange_id": "coinbase",
  "pair": "BTC/USDT",
  "strategy_id": "momentum_btc",
  "hitl_mode": "manual",
  "stake_amount_usd": 500,
  "stop_loss_pct": 0.03,
  "take_profit_pct": 0.05,
  "dry_run": true
}
```
**Response 201:** `{ "bot_id": "uuid", "status": "created", "hitl_mode": "manual" }`

---

### `POST /api/trading/bots/{bot_id}/start`

Start a bot's tick loop.

**Auth:** Required  
**Response 200:** `{ "bot_id": "uuid", "status": "running" }`

---

### `POST /api/trading/bots/{bot_id}/pause`

Pause a running bot (preserves open position).

**Response 200:** `{ "bot_id": "uuid", "status": "paused" }`

---

### `POST /api/trading/bots/{bot_id}/stop`

Gracefully stop a bot.

**Response 200:** `{ "bot_id": "uuid", "status": "stopped" }`

---

### `POST /api/trading/emergency_stop`

Emergency stop all running bots.

**Auth:** Required  
**Response 200:** `{ "stopped_count": 3 }`

---

### `GET /api/trading/bots/dashboard`

Live summary of all bots, P&L, and status.

**Response 200:**
```json
{
  "total_bots": 3,
  "running": 2,
  "paused": 0,
  "stopped": 1,
  "total_pnl_usd": 142.50,
  "bots": [...]
}
```

---

### `GET /api/trading/hitl/pending`

List all trades awaiting human approval.

**Auth:** Required  
**Response 200:**
```json
[
  {
    "request_id": "uuid",
    "bot_id": "uuid",
    "pair": "BTC/USDT",
    "action": "buy",
    "confidence": 0.87,
    "murphy_index": 0.04,
    "suggested_price": 50000,
    "suggested_size": 0.01,
    "reasoning": "momentum rsi=28.3 macd_hist=0.002",
    "hitl_mode": "manual",
    "created_at": "2026-03-08T09:00:00Z"
  }
]
```

---

### `POST /api/trading/hitl/{request_id}/approve`

Approve a pending trade.

**Auth:** Required  
**Body:** `{ "approver": "trader_alice", "notes": "looks good" }`  
**Response 200:** `{ "placed": true, "request_id": "uuid" }`

---

### `POST /api/trading/hitl/{request_id}/reject`

Reject a pending trade.

**Auth:** Required  
**Body:** `{ "approver": "trader_bob", "notes": "price too high" }`  
**Response 200:** `{ "rejected": true }`

---

### `POST /api/trading/hitl/{request_id}/modify`

Modify and approve a pending trade with adjusted parameters.

**Auth:** Required  
**Body:**
```json
{
  "approver": "trader_carol",
  "new_size": 0.005,
  "new_price": 49800,
  "new_stop": 48500
}
```
**Response 200:** `{ "placed": true }`

---

### `GET /api/trading/hitl/audit`

Retrieve the immutable HITL decision audit log.

**Auth:** Required (admin)  
**Query:** `?limit=500`  
**Response 200:** `[ { "audit_id": "uuid", "decision": "approved", "auto": false, "confidence": 0.87, ... } ]`

---

### `GET /api/trading/portfolio`

Full portfolio snapshot with risk metrics.

**Auth:** Required  
**Response 200:**
```json
{
  "snapshot_id": "uuid",
  "total_value_usd": 15430.22,
  "cash_usd": 8200.00,
  "invested_usd": 7000.00,
  "unrealized_pnl": 230.22,
  "realized_pnl": 1142.50,
  "open_positions": [...],
  "risk_metrics": {
    "total_trades": 87,
    "win_rate": 0.61,
    "profit_factor": 1.82,
    "max_drawdown": 0.08,
    "sharpe_ratio": 1.34
  }
}
```

---

### `GET /api/trading/risk/summary`

Current risk manager state including circuit breakers.

**Auth:** Required  
**Response 200:**
```json
{
  "open_circuit_breakers": 0,
  "daily_loss_usd": 45.20,
  "daily_loss_limit_usd": 500,
  "open_trades": 2,
  "consecutive_losses": 0,
  "sizing_method": "percent_risk"
}
```

---

### `POST /api/trading/risk/reset_breakers`

Manually reset open circuit breakers (requires senior approval).

**Auth:** Required (admin)  
**Response 200:** `{ "resolved_count": 1 }`

---

### `GET /api/trading/market/{exchange}/{pair}/candles`

OHLCV candle history for a pair.

**Auth:** Required  
**Query:** `?granularity=ONE_HOUR&limit=200`  
**Response 200:** `{ "candles": [{ "open_time": 1700000000, "open": 50000, "high": 51000, ... }] }`

---

### `GET /api/trading/market/{exchange}/{pair}/indicators`

Computed technical indicators for a pair.

**Auth:** Required  
**Response 200:**
```json
{
  "pair": "BTC/USDT",
  "rsi_14": 42.3,
  "macd": 123.4,
  "macd_signal": 118.2,
  "bb_upper": 52000,
  "bb_mid": 50000,
  "bb_lower": 48000,
  "ema_9": 50200,
  "ema_21": 49800,
  "vwap": 49950,
  "atr_14": 850
}
```

---

### `GET /api/trading/wallets`

List all registered wallets with balances.

**Auth:** Required  
**Response 200:**
```json
{
  "total_usd": 18500.0,
  "wallet_count": 3,
  "assets": [
    { "symbol": "BTC", "total_balance": 0.15, "total_usd": 7500 },
    { "symbol": "ETH", "total_balance": 2.0,  "total_usd": 5000 }
  ]
}
```

---

### `POST /api/trading/wallets/transfer`

Request a wallet transfer (always requires HITL approval).

**Auth:** Required  
**Body:**
```json
{
  "from_wallet_id": "sw::ethereum::0xdead",
  "to_address": "0xrecipient",
  "asset": "ETH",
  "amount": 0.5,
  "chain": "ethereum",
  "notes": "payment to vendor"
}
```
**Response 202:** `{ "queued": true, "request_id": "uuid", "requires_approval": true }`

---

*Copyright © 2020 Inoni Limited Liability Company | Creator: Corey Post | License: BSL 1.1*

---

## Shadow Learning System

> Shadow bots run paper simulations against live prices 24/7.  
> **No real money is ever used.**  
> Winning weekly patterns are saved for human review before being promoted to influence future strategy hints.

### Real-Money Safety Rule

All real bots (`dry_run=False`) are **permanently forced to `MANUAL` mode** regardless of the `hitl_mode` setting.  
This is enforced unconditionally in the `TradingHITLGateway` — no configuration or API can override it.

---

### `POST /api/trading/shadow/bots`

Register a new shadow (paper-only) bot.

**Auth:** Required  
**Body:**
```json
{
  "strategy_id": "momentum_btc",
  "pair": "BTC/USDT",
  "exchange_id": "paper",
  "initial_paper_usd": 10000.0
}
```
**Response 201:** `{ "bot_id": "uuid", "initial_paper_usd": 10000.0 }`

---

### `GET /api/trading/shadow/bots`

List all shadow bots and their current-week performance.

**Auth:** Required  
**Response 200:**
```json
[
  {
    "bot_id": "uuid",
    "pair": "BTC/USDT",
    "strategy_id": "momentum_btc",
    "start_equity": 10000.0,
    "current_equity": 10340.0,
    "gain_pct": 0.034,
    "total_sells": 8,
    "wins": 6,
    "win_rate": 0.75,
    "pct_complete": 0.65
  }
]
```

---

### `POST /api/trading/shadow/check_week`

Trigger a manual week-end evaluation for all shadow bots whose week window has elapsed.

**Auth:** Required (admin)  
**Response 200:**
```json
{
  "evaluated": 3,
  "winning_weeks_saved": 2,
  "pattern_ids": ["uuid1", "uuid2"]
}
```

---

### `GET /api/trading/shadow/patterns`

List saved winning-week patterns.

**Auth:** Required  
**Query:** `?status=pending|reviewed|promoted|rejected&strategy_id=…&pair=…`  
**Response 200:**
```json
[
  {
    "pattern_id": "uuid",
    "strategy_id": "momentum_btc",
    "pair": "BTC/USDT",
    "week_start": "2026-03-01T00:00:00Z",
    "week_end": "2026-03-08T00:00:00Z",
    "gain_pct": 0.034,
    "win_rate": 0.75,
    "total_trades": 8,
    "status": "pending",
    "avg_winning_indicators": { "rsi_14": 31.2, "macd_hist": 0.0021 }
  }
]
```

---

### `POST /api/trading/shadow/patterns/{pattern_id}/review`

Mark a pattern as reviewed (human has looked at it).

**Auth:** Required  
**Body:** `{ "notes": "Win rate consistent with expectations" }`  
**Response 200:** `{ "pattern_id": "uuid", "status": "reviewed" }`

---

### `POST /api/trading/shadow/patterns/{pattern_id}/promote`

Promote a pattern — its indicator averages will bias future strategy hints.

**Auth:** Required (senior)  
**Body:** `{ "notes": "Promote for next week's BTC/USDT trading" }`  
**Response 200:** `{ "pattern_id": "uuid", "status": "promoted" }`

---

### `POST /api/trading/shadow/patterns/{pattern_id}/reject`

Reject a pattern as noise (it will not be promoted).

**Auth:** Required  
**Body:** `{ "notes": "Anomalous week, not representative" }`  
**Response 200:** `{ "pattern_id": "uuid", "status": "rejected" }`

---

### `GET /api/trading/shadow/hints`

Retrieve promoted pattern hints for a given strategy and pair.

**Auth:** Required  
**Query:** `?strategy_id=momentum_btc&pair=BTC/USDT`  
**Response 200:**
```json
[
  {
    "pattern_id": "uuid",
    "week_start": "2026-03-01",
    "gain_pct": 0.034,
    "win_rate": 0.75,
    "indicators": { "rsi_14": 31.2, "macd_hist": 0.0021, "ema_9": 49500 }
  }
]
```

---

## Self-Marketing & Revenue Generation API

### `POST /api/marketing/content-cycle`

Trigger a content generation cycle. Returns `ContentCycleResult` with vertical-specific topic enrichment sourced from `MarketPositioningEngine` (MPE-001).

**Auth:** Required  
**Body:** `{}` (optional `{ "vertical": "factory_automation" }` to target a specific vertical)  
**Response 200:** `{ "cycle_id": "uuid", "topics_generated": 5, "vertical": "factory_automation", "status": "complete" }`

---

### `POST /api/marketing/b2b-cycle`

Run a B2B partnership outreach cycle across all 22 configured partners. `_commission_system()` gate fires automatically before execution and emits `system_commissioned` to the audit trail.

**Auth:** Required  
**Body:** `{}` (optional `{ "partner_ids": ["rockwell_automation"] }` to target specific partners)  
**Response 200:** `{ "cycle_id": "uuid", "partners_contacted": 22, "commissioned": true, "status": "complete" }`

---

### `GET /api/marketing/dashboard`

Return the full marketing dashboard including a `market_position` section with `MarketPositioningEngine` data (10 verticals, 17 capabilities, positioning statement, tagline, target segments, differentiation pillars).

**Auth:** Required  
**Response 200:**
```json
{
  "market_position": {
    "positioning_statement": "...",
    "tagline": "...",
    "target_segments": ["...", "..."],
    "differentiation_pillars": ["...", "..."],
    "competitive_moats": ["...", "..."]
  },
  "verticals_count": 10,
  "capabilities_count": 17,
  "partners_count": 22
}
```

---

### `GET /api/marketing/pipeline`

Return the B2B partnership pipeline (22 partners).

**Auth:** Required  
**Response 200:** `{ "partners": [ { "id": "rockwell_automation", "vertical": "factory_automation", "status": "active" }, ... ] }`

---

### `GET /api/marketing/partners/{partner_id}/pitch`

Generate a B2B pitch for a specific partner, enriched with industry context via MPE-001.

**Auth:** Required  
**Path param:** `partner_id` — partner identifier (e.g. `rockwell_automation`)  
**Response 200:** `{ "partner_id": "rockwell_automation", "pitch": "...", "vertical": "factory_automation" }`

---

### `POST /api/marketing/partners/{partner_id}/contact`

Set or update the salesperson contact for a partner (PII-safe storage).

**Auth:** Required  
**Path param:** `partner_id`  
**Body:**
```json
{
  "salesperson_name": "Jane Smith",
  "salesperson_title": "VP Partnerships",
  "salesperson_email": "jane@example.com",
  "salesperson_linkedin": "https://linkedin.com/in/janesmith"
}
```
**Response 200:** `{ "partner_id": "rockwell_automation", "contact_updated": true }`

---

## Market Positioning API (MPE-001)

### `GET /api/positioning/market-position`

Return Murphy's market position (positioning statement, tagline, 6 differentiation pillars, 6 target segments, 8 competitive moats).

**Auth:** Required  
**Response 200:** `{ "positioning_statement": "...", "tagline": "...", "differentiation_pillars": [...], "target_segments": [...], "competitive_moats": [...] }`

---

### `GET /api/positioning/capabilities`

List all 17 Murphy capabilities with maturity scores and relevant verticals.

**Auth:** Required  
**Response 200:** `{ "capabilities": [ { "id": "...", "name": "...", "maturity": 0.9, "verticals": [...] }, ... ] }`

---

### `GET /api/positioning/capabilities/{capability_id}`

Get a specific capability by ID.

**Auth:** Required  
**Response 200:** `{ "id": "...", "name": "...", "maturity": 0.9, "description": "...", "verticals": [...] }`  
**Response 404:** `{ "error": "capability_not_found" }`

---

### `GET /api/positioning/verticals`

List all 10 industry verticals: `healthcare`, `financial_services`, `manufacturing`, `technology`, `professional_services`, `government`, `iot_building_automation`, `energy_management`, `additive_manufacturing`, `factory_automation`.

**Auth:** Required  
**Response 200:** `{ "verticals": ["healthcare", "financial_services", "manufacturing", "technology", "professional_services", "government", "iot_building_automation", "energy_management", "additive_manufacturing", "factory_automation"] }`

---

### `GET /api/positioning/verticals/{vertical_id}`

Get full vertical detail (ICP, pain points, regulatory context, value props, content topics, B2B pitch hook).

**Auth:** Required  
**Response 200:** `{ "id": "factory_automation", "icp": {...}, "pain_points": [...], "regulatory_context": [...], "value_props": [...], "content_topics": [...], "b2b_pitch_hook": "..." }`  
**Response 404:** `{ "error": "vertical_not_found" }`

---

### `GET /api/positioning/verticals/{vertical_id}/icp`

Get the Ideal Customer Profile for a vertical.

**Auth:** Required  
**Response 200:** `{ "vertical": "factory_automation", "icp": { "company_size": "...", "titles": [...], "tech_stack": [...] } }`

---

### `GET /api/positioning/verticals/{vertical_id}/topics`

Get content topics for a vertical.

**Auth:** Required  
**Response 200:** `{ "vertical": "factory_automation", "topics": ["ISA-95 orchestration", "IEC 13849 safety", ...] }`

---

### `GET /api/positioning/score-fit`

Score partner fit against Murphy's vertical and capability profile.

**Auth:** Required  
**Query params:** `company` (string), `offerings` (comma-separated offering types)  
**Response 200:** `{ "company": "Rockwell Automation", "fit_score": 0.87 }`

---

## Energy Audit API (EAE-001)

### `POST /api/energy-audit/audits`

Create a new energy audit.

**Auth:** Required  
**Body:**
```json
{
  "facility_id": "fac-001",
  "facility_name": "Main Campus",
  "sqft": 120000,
  "audit_level": "LEVEL_II",
  "compliance_frameworks": ["iso_50001", "ashrae_90_1"]
}
```
**Response 201:** `{ "audit_id": "uuid", "status": "created" }`

---

### `GET /api/energy-audit/audits/{audit_id}`

Get audit details.

**Auth:** Required  
**Response 200:** `{ "audit_id": "...", "facility_name": "...", "audit_level": "LEVEL_II", "status": "in_progress" }`

---

### `POST /api/energy-audit/audits/{audit_id}/readings`

Ingest energy meter readings.

**Auth:** Required  
**Body:** `{ "readings": [ { "timestamp": "2026-01-01T00:00:00Z", "kwh": 4521.3, "meter_id": "M-001" } ] }`  
**Response 200:** `{ "readings_accepted": 1 }`

---

### `GET /api/energy-audit/audits/{audit_id}/summary`

Compute energy cost summary (EUI, monthly average, carbon estimate).

**Auth:** Required  
**Response 200:** `{ "eui": 68.2, "monthly_avg_kwh": 87500, "annual_cost_usd": 105000, "carbon_tons_co2e": 48.3 }`

---

### `POST /api/energy-audit/audits/{audit_id}/ecms`

Add an Energy Conservation Measure.

**Auth:** Required  
**Body:**
```json
{
  "name": "LED Retrofit",
  "category": "lighting",
  "annual_savings_usd": 18000,
  "implementation_cost_usd": 54000,
  "priority": "high"
}
```
**Response 201:** `{ "ecm_id": "uuid", "payback_years": 3.0 }`

---

### `GET /api/energy-audit/audits/{audit_id}/ecms`

List ECMs with optional filters.

**Auth:** Required  
**Query params:** `category` (string), `priority` (string), `max_payback_years` (float)  
**Response 200:** `{ "ecms": [ { "ecm_id": "...", "name": "LED Retrofit", "payback_years": 3.0 } ] }`

---

### `GET /api/energy-audit/audits/{audit_id}/prioritise`

Return optimal ECM set within budget using greedy-knapsack algorithm.

**Auth:** Required  
**Query params:** `budget_usd` (float)  
**Response 200:** `{ "selected_ecms": [...], "total_cost_usd": 120000, "total_annual_savings_usd": 42000, "aggregate_payback_years": 2.86 }`

---

### `GET /api/energy-audit/audits/{audit_id}/compliance/{framework}`

Generate compliance checklist. `framework` is one of: `ashrae_90_1`, `iso_50001`, `iso_50002`, `energy_star`, `leed`, `breeam`.

**Auth:** Required  
**Response 200:** `{ "framework": "iso_50001", "checklist": [ { "item": "...", "status": "pass" } ] }`

---

### `GET /api/energy-audit/audits/{audit_id}/export`

Export full audit as JSON (facility metadata, readings summary, ECMs, compliance checklists, prioritised ECM set).

**Auth:** Required  
**Response 200:** Full audit JSON.

---

### `GET /api/energy-audit/benchmark`

Benchmark an EUI value against CBECS medians for a given facility type (12 types supported: `office`, `hospital`, `warehouse`, `retail`, `school`, `hotel`, `multifamily`, `food_service`, `laboratory`, `data_center`, `religious`, `other`).

**Auth:** Required  
**Query params:** `facility_type` (string), `eui` (float)  
**Response 200:** `{ "facility_type": "office", "submitted_eui": 68.2, "cbecs_median_eui": 72.0, "percentile": 45, "rating": "below_median" }`

---

## Factory Automation Connector API (FAC-001)

### `GET /api/factory/connectors`

List all registered factory automation connectors.

**Auth:** Required  
**Response 200:** `{ "connectors": [ { "key": "rockwell_factorytalk", "vendor": "Rockwell", "protocol": "EtherNet/IP", "isa95_layer": "CONTROL", "safety_category": "CAT_3" }, ... ] }`

---

### `POST /api/factory/connectors`

Register a new connector.

**Auth:** Required  
**Body:** `{ "key": "custom_plc", "vendor": "Acme", "protocol": "Modbus", "isa95_layer": "FIELD", "safety_category": "CAT_1" }`  
**Response 201:** `{ "key": "custom_plc", "status": "registered" }`

---

### `GET /api/factory/connectors/{key}`

Get connector details.

**Auth:** Required  
**Response 200:** `{ "key": "rockwell_factorytalk", "vendor": "Rockwell", "protocol": "EtherNet/IP" }`  
**Response 404:** `{ "error": "connector_not_found" }`

---

### `GET /api/factory/connectors/{key}/health`

Health-check a connector.

**Auth:** Required  
**Response 200:** `{ "key": "rockwell_factorytalk", "health": "ok", "latency_ms": 12 }`

---

### `POST /api/factory/connectors/{key}/execute`

Execute an action on a connector. Supported actions: `read_sensor`, `write_tag`, `start_cycle`, `stop_cycle`, `e_stop`, `get_alarms`.

**Auth:** Required  
**Body:** `{ "action": "read_sensor", "params": { "tag": "Line1.Speed" } }`  
**Response 200:** `{ "key": "rockwell_factorytalk", "action": "read_sensor", "result": { "tag": "Line1.Speed", "value": 120.5 } }`

---

### `GET /api/factory/sequences`

List all automation sequences.

**Auth:** Required  
**Response 200:** `{ "sequences": [ { "sequence_id": "uuid", "name": "Assembly Line Start", "steps": 4 } ] }`

---

### `POST /api/factory/sequences`

Create a new ISA-95 layer-aware automation sequence.

**Auth:** Required  
**Body:**
```json
{
  "name": "Assembly Line Start",
  "steps": [
    { "connector_key": "siemens_simatic_s7", "action": "start_cycle", "isa95_layer": "CONTROL" },
    { "connector_key": "rockwell_factorytalk", "action": "read_sensor", "isa95_layer": "CONTROL" },
    { "connector_key": "ptc_thingworx", "action": "get_alarms", "isa95_layer": "MES" }
  ]
}
```
**Response 201:** `{ "sequence_id": "uuid", "name": "Assembly Line Start", "status": "created" }`

---

### `POST /api/factory/sequences/{sequence_id}/execute`

Execute a sequence. Steps execute in ISA-95 order: `FIELD → CONTROL → SUPERVISORY → MES`. Sub-CAT_2 connectors are blocked by the IEC 13849 safety gate unless `override_safety: true` is provided.

**Auth:** Required  
**Body:** `{ "override_safety": false }` (optional)  
**Response 200:** `{ "sequence_id": "uuid", "steps_executed": 3, "safety_gate_triggered": false, "status": "complete" }`  
**Response 403:** `{ "error": "iec13849_safety_gate", "detail": "Sub-CAT_2 connector requires override" }`

---

*Copyright © 2020 Inoni Limited Liability Company | Creator: Corey Post | License: BSL 1.1*
