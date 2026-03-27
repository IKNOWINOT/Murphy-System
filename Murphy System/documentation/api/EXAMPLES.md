# API Examples

Practical, copy-paste examples of using the Murphy System REST API.

**Base URL:** `http://localhost:8000`  
**Auth:** `Authorization: Bearer <token>` or `X-API-Key: <key>` (all endpoints except `/api/health`)  
**License:** BSL 1.1 — *Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post*

---

## Table of Contents

1. [Health Check](#1-health-check)
2. [Authentication](#2-authentication)
3. [Execute a Task](#3-execute-a-task)
4. [Check Task Status](#4-check-task-status)
5. [LLM Configuration](#5-llm-configuration)
6. [System Status](#6-system-status)
7. [Orchestrator — List Tasks](#7-orchestrator--list-tasks)
8. [Confidence Scoring](#8-confidence-scoring)
9. [Feedback Submission](#9-feedback-submission)
10. [Error Handling](#10-error-handling)

---

## 1. Health Check

The health endpoint requires no authentication and is safe to use as a liveness probe.

**curl**
```bash
curl -s http://localhost:8000/api/health
```

**Response 200**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "uptime_seconds": 12345
}
```

**Python (`requests`)**
```python
import requests

resp = requests.get("http://localhost:8000/api/health")
resp.raise_for_status()
print(resp.json())
# {'status': 'ok', 'version': '1.0.0', 'uptime_seconds': 12345}
```

---

## 2. Authentication

### 2a. Development Mode (no key required)

When `MURPHY_ENV=development` (the default), the server accepts requests without an API key.
All endpoints are accessible without a `Authorization` header.

```bash
curl -s http://localhost:8000/api/status
```

### 2b. Production Mode (API key required)

Configure one or more keys in `.env`:

```bash
MURPHY_ENV=production
MURPHY_API_KEYS=murphy_key_abc123,murphy_key_def456
```

Pass the key as a Bearer token or via the `X-API-Key` header:

**Bearer token (curl)**
```bash
export MURPHY_KEY="murphy_key_abc123"

curl -s http://localhost:8000/api/status \
  -H "Authorization: Bearer ${MURPHY_KEY}"
```

**X-API-Key header (curl)**
```bash
curl -s http://localhost:8000/api/status \
  -H "X-API-Key: ${MURPHY_KEY}"
```

**Python (`requests`) — reusable session**
```python
import requests

BASE_URL = "http://localhost:8000"
API_KEY  = "murphy_key_abc123"

session = requests.Session()
session.headers.update({
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
})

resp = session.get(f"{BASE_URL}/api/status")
resp.raise_for_status()
print(resp.json())
```

**Response 401 (missing / invalid key)**
```json
{
  "detail": "Unauthorized: missing or invalid API key"
}
```

---

## 3. Execute a Task

`POST /api/execute` routes a natural-language task through the full Murphy orchestration pipeline (AUAR, AionMind, gate checks, LLM if enabled).

### Minimal request

**curl**
```bash
curl -s -X POST http://localhost:8000/api/execute \
  -H "Authorization: Bearer ${MURPHY_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"task": "Summarize Q1 sales data and flag anomalies"}'
```

### Full request (all optional fields)

**curl**
```bash
curl -s -X POST http://localhost:8000/api/execute \
  -H "Authorization: Bearer ${MURPHY_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Summarize Q1 sales data and flag anomalies",
    "context": {
      "region": "EMEA",
      "fiscal_year": 2026,
      "threshold_pct": 15
    },
    "timeout_seconds": 60,
    "use_llm": true
  }'
```

**Response 200**
```json
{
  "success": true,
  "result": "Q1 EMEA revenue was $4.2M (+12% YoY). Three anomalies detected: SKU-9912 spike (+87%), SKU-0043 drop (-22%), refund cluster on 2026-02-14.",
  "confidence": 0.92,
  "execution_time_ms": 342,
  "gate_results": {
    "security": "pass",
    "compliance": "pass",
    "governance": "pass"
  },
  "audit_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Python**
```python
import requests

resp = session.post(
    f"{BASE_URL}/api/execute",
    json={
        "task": "Summarize Q1 sales data and flag anomalies",
        "context": {"region": "EMEA"},
        "timeout_seconds": 60,
    },
)
resp.raise_for_status()
data = resp.json()

if data["success"]:
    print(f"Result:     {data['result']}")
    print(f"Confidence: {data['confidence']:.0%}")
    print(f"Audit ID:   {data['audit_id']}")
else:
    print("Task failed")
```

---

## 4. Check Task Status

After submitting a task you receive an `audit_id`. Use it to retrieve the task record from the orchestrator.

**curl**
```bash
AUDIT_ID="550e8400-e29b-41d4-a716-446655440000"

curl -s http://localhost:8000/api/orchestrator/tasks \
  -H "Authorization: Bearer ${MURPHY_KEY}"
```

Filter by status:

```bash
curl -s "http://localhost:8000/api/orchestrator/tasks?status=completed&limit=10" \
  -H "Authorization: Bearer ${MURPHY_KEY}"
```

**Response 200**
```json
{
  "tasks": [
    {
      "audit_id": "550e8400-e29b-41d4-a716-446655440000",
      "task": "Summarize Q1 sales data and flag anomalies",
      "status": "completed",
      "created_at": "2026-03-07T05:00:00Z",
      "completed_at": "2026-03-07T05:00:00.342Z",
      "confidence": 0.92
    }
  ],
  "total": 142,
  "page": 1
}
```

**Python — poll until done**
```python
import time

def wait_for_task(session, base_url, audit_id, poll_interval=2, max_wait=120):
    deadline = time.time() + max_wait
    while time.time() < deadline:
        resp = session.get(f"{base_url}/api/orchestrator/tasks")
        resp.raise_for_status()
        tasks = resp.json()["tasks"]
        match = next((t for t in tasks if t["audit_id"] == audit_id), None)
        if match and match["status"] in ("completed", "failed"):
            return match
        time.sleep(poll_interval)
    raise TimeoutError(f"Task {audit_id} did not finish within {max_wait}s")

task = wait_for_task(session, BASE_URL, data["audit_id"])
print(task)
```

---

## 5. LLM Configuration

### Read current configuration

```bash
curl -s http://localhost:8000/api/llm/configure \
  -H "Authorization: Bearer ${MURPHY_KEY}"
```

**Response 200**
```json
{
  "provider": "deepinfra",
  "model": "meta-llama/Meta-Llama-3.1-70B-Instruct",
  "key_configured": true,
  "key_mask": "gsk_...xxxx"
}
```

### Update LLM provider (hot-reload — no restart needed)

```bash
curl -s -X POST http://localhost:8000/api/llm/configure \
  -H "Authorization: Bearer ${MURPHY_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "openai",
    "api_key": "sk-your-openai-key"
  }'
```

**Response 200**
```json
{
  "provider": "openai",
  "model": "gpt-4o",
  "key_configured": true,
  "key_mask": "sk-...xxxx"
}
```

**Python**
```python
resp = session.post(
    f"{BASE_URL}/api/llm/configure",
    json={"provider": "deepinfra", "api_key": "gsk_your_key"},
)
resp.raise_for_status()
print(resp.json())
```

---

## 6. System Status

```bash
curl -s http://localhost:8000/api/status \
  -H "Authorization: Bearer ${MURPHY_KEY}"
```

**Response 200**
```json
{
  "status": "operational",
  "modules_loaded": 625,
  "llm_enabled": true,
  "llm_provider": "deepinfra",
  "active_gates": ["security", "compliance", "governance"],
  "uptime_seconds": 86400,
  "version": "1.0.0"
}
```

---

## 7. Orchestrator — List Tasks

```bash
# Last 20 tasks (default)
curl -s http://localhost:8000/api/orchestrator/tasks \
  -H "Authorization: Bearer ${MURPHY_KEY}"

# Last 5 failed tasks
curl -s "http://localhost:8000/api/orchestrator/tasks?status=failed&limit=5" \
  -H "Authorization: Bearer ${MURPHY_KEY}"
```

**Orchestrator status summary**
```bash
curl -s http://localhost:8000/api/orchestrator/status \
  -H "Authorization: Bearer ${MURPHY_KEY}"
```

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

## 8. Confidence Scoring

Request a confidence score for a discrete decision without full task execution.

```bash
curl -s -X POST http://localhost:8000/api/confidence/score \
  -H "Authorization: Bearer ${MURPHY_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "decision": "Approve $250k contract renewal for Acme Corp",
    "evidence": ["3-year relationship", "zero payment defaults", "NPS 9/10"],
    "domain": "finance"
  }'
```

**Response 200**
```json
{
  "confidence": 0.91,
  "gdh_breakdown": {
    "generative": 0.88,
    "discriminative": 0.93,
    "hybrid": 0.91
  },
  "uncertainty_5d": {
    "epistemic": 0.04,
    "aleatoric": 0.06,
    "model": 0.02,
    "data": 0.05,
    "domain": 0.03
  },
  "recommendation": "accept"
}
```

---

## 9. Feedback Submission

Submit a human quality signal to improve confidence calibration. Use the `audit_id` from a previous `POST /api/execute` response.

```bash
curl -s -X POST http://localhost:8000/api/feedback \
  -H "Authorization: Bearer ${MURPHY_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "audit_id": "550e8400-e29b-41d4-a716-446655440000",
    "signal": "positive",
    "score": 0.95,
    "notes": "Anomaly detection was accurate; all three flagged SKUs confirmed by analyst"
  }'
```

**Response 200**
```json
{
  "accepted": true,
  "recalibrating": false
}
```

**Python**
```python
resp = session.post(
    f"{BASE_URL}/api/feedback",
    json={
        "audit_id": data["audit_id"],
        "signal": "positive",
        "score": 0.95,
    },
)
resp.raise_for_status()
print(resp.json())  # {'accepted': True, 'recalibrating': False}
```

---

## 10. Error Handling

### Common error responses

| Status | Meaning | Example cause |
|--------|---------|---------------|
| 400 | Bad request | Malformed JSON body |
| 401 | Unauthorized | Missing / invalid API key in production mode |
| 403 | Forbidden | Key valid but lacks required scope |
| 422 | Validation error | Missing required `task` field |
| 429 | Rate limit | Exceeded 60 req/min on `/api/execute` |
| 500 | Server error | Unhandled exception in pipeline |
| 503 | Unavailable | LLM provider offline or unreachable |

### Validation error (422)

```json
{
  "detail": [
    {
      "loc": ["body", "task"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### Rate limit (429)

```json
{
  "detail": "Rate limit exceeded. Retry after 42 seconds."
}
```

### Robust Python wrapper

```python
import time
import requests
from requests.exceptions import HTTPError

def execute_task(session, base_url, task, context=None, retries=3):
    payload = {"task": task, "context": context or {}}
    for attempt in range(1, retries + 1):
        try:
            resp = session.post(f"{base_url}/api/execute", json=payload)
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 5))
                print(f"Rate limited — retrying in {retry_after}s")
                time.sleep(retry_after)
                continue
            resp.raise_for_status()
            return resp.json()
        except HTTPError as exc:
            if attempt == retries:
                raise
            print(f"Attempt {attempt} failed: {exc}")
            time.sleep(2 ** attempt)
    return None
```

---

## See Also

- [Endpoints Reference](ENDPOINTS.md)
- [Authentication](AUTHENTICATION.md)
- [API Overview](API_OVERVIEW.md)
- [Full API Reference](../../docs/API_REFERENCE.md)

---

*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*
