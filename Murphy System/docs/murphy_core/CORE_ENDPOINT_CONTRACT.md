# Murphy Core Endpoint Contract

This document defines the canonical endpoint contract for Murphy Core.

## Canonical endpoints

### GET `/api/health`
Returns liveness information.

### GET `/api/readiness`
Returns readiness and adapter availability.

### GET `/api/capabilities/effective`
Returns truthful effective capability state.

### GET `/api/registry/modules`
Returns merged module registry records.

### GET `/api/system/map`
Returns the canonical request path and adapter hints.

### POST `/api/chat`
Canonical chat entrypoint.

Request:
```json
{
  "message": "help me route this task",
  "session_id": "optional",
  "context": {}
}
```

Response includes:
- `trace_id`
- `request_id`
- `route`
- `gate_results`
- `result`

### POST `/api/execute`
Canonical execution entrypoint.

Request:
```json
{
  "task_description": "generate a workflow",
  "session_id": "optional",
  "parameters": {}
}
```

Response includes:
- `trace_id`
- `request_id`
- `route`
- `gate_results`
- `result`

### GET `/api/traces/recent`
Returns recent traces.

### GET `/api/traces/{trace_id}`
Returns one trace.

## Response truth rules

The response must tell the truth about:
- selected route
- gate outcomes
- execution status
- whether execution was blocked
- whether execution used legacy adapters

## Migration rule

If legacy endpoints remain, they should either:
- forward into this contract, or
- be marked compatibility only
