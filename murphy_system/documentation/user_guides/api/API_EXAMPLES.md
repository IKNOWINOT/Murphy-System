# API Examples (User Guide)

Quick-start examples for the five most common Murphy System API interactions.
For the full example catalogue see [API Examples (reference)](../../api/API_EXAMPLES.md).

---

## 1. Health Check

Verify the system is running and responsive.

```bash
curl http://localhost:8000/health
```

**Response:**

```json
{
  "status": "ok",
  "version": "1.0.0",
  "uptime_seconds": 3421
}
```

---

## 2. Execute a Task

Submit a natural-language task for execution through the automation pipeline.

```bash
curl -X POST http://localhost:8000/api/forms/task-execution \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "task": "Generate a weekly sales summary report",
    "domain": "business",
    "priority": "normal"
  }'
```

**Response:**

```json
{
  "execution_id": "exec-a1b2c3",
  "status": "running",
  "phase": "EXPAND",
  "confidence": 0.45,
  "message": "Task accepted — entering generative setup phase."
}
```

---

## 3. Check System Status

Retrieve system information including loaded modules and current phase.

```bash
curl http://localhost:8000/api/system/info \
  -H "Authorization: Bearer $API_KEY"
```

**Response:**

```json
{
  "system": "Murphy System 1.0",
  "phase": "CONSTRAIN",
  "modules_loaded": 12,
  "engines_active": ["sensor", "database", "content", "agent"],
  "memory_artifacts": 24,
  "db_available": true,
  "cache_available": true
}
```

---

## 4. Chat / Cognitive Execute

Send a message through the AionMind cognitive pipeline.

```bash
curl -X POST http://localhost:8000/api/aionmind/execute \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "prompt": "What is the current status of the sales pipeline?",
    "context": {"workspace": "default"}
  }'
```

**Response:**

```json
{
  "result": "The sales pipeline currently has 42 open deals...",
  "confidence": 0.87,
  "sources": ["crm_module", "board_system"],
  "execution_graph": "graph-x7y8z9"
}
```

---

## 5. Submit a Form (Plan Generation)

Generate an automation plan from a natural-language description.

```bash
curl -X POST http://localhost:8000/api/forms/plan-generation \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "description": "Monitor server CPU and alert when above 90%",
    "engines": ["sensor", "agent"]
  }'
```

**Response:**

```json
{
  "plan_id": "plan-d4e5f6",
  "steps": [
    {"step": 1, "action": "Configure sensor polling", "engine": "sensor"},
    {"step": 2, "action": "Set threshold rule", "engine": "agent"},
    {"step": 3, "action": "Wire alert notification", "engine": "agent"}
  ],
  "confidence": 0.72,
  "requires_hitl": false
}
```

---

## See Also

- [API Overview](../../api/API_OVERVIEW.md)
- [Full API Examples](../../api/API_EXAMPLES.md)
- [API Reference](../API_REFERENCE.md)
