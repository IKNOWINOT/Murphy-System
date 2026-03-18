# Murphy Core Webapp Production Target

This document defines the production target for Murphy Core as the backend of a real web application.

## Objective

Run Murphy Core as the canonical production webapp server for Murphy System.

## Canonical backend entrypoint

Preferred canonical backend entrypoint:
- `src/murphy_core/app.py`

Any legacy runtime wrapper must clearly forward into this app and be marked as compatibility only.

## Required API surface

Murphy Core should provide at minimum:
- `GET /api/health`
- `GET /api/readiness`
- `GET /api/capabilities/effective`
- `GET /api/registry/modules`
- `GET /api/system/map`
- `POST /api/chat`
- `POST /api/execute`
- `GET /api/traces/recent`
- `GET /api/traces/{trace_id}`

## Production characteristics

The server should support:
- FastAPI lifespan startup/shutdown
- structured logs
- trace IDs per request
- readiness checks for provider layer, registry layer, gates, and adapters
- graceful degradation for optional modules
- truthful capability reporting
- typed request/response models

## Required behavior

### Chat requests
- accept conversational input
- run centralized inference
- normalize via Rosetta
- apply gates and route selection
- return response with route metadata and trace ID

### Execute requests
- accept typed or natural-language intent
- compile into typed execution plan
- apply gates
- execute through deterministic/specialist/swarm/adapter paths
- return outcome, gate results, route, and trace ID

## UI contract expectations

The frontend must be able to:
- query health and readiness
- display live module/capability status
- inspect recent traces
- inspect why a request was blocked
- surface HITL requirements
- show route type and execution provenance

## Capability truth rules

Never surface a capability as production-ready unless:
- runtime wiring exists
- dependencies are present or gracefully degraded
- registry status is not `declared_only`
- endpoint returns real structured output

## Deployment assumptions

Murphy Core should be designed to run under:
- uvicorn/gunicorn
- reverse proxy
- environment-based configuration
- optional worker/background systems where available

But the app itself must remain understandable and bootable as a single canonical service.

## Health model

### Health
Basic liveness:
- app process alive
- core services constructed

### Readiness
Operational readiness:
- registry loaded
- core contracts available
- provider layer configured
- gates initialized
- execution adapters registered
- optional modules reported honestly

## Observability target

Every request should produce:
- request ID
- trace ID
- selected route
- gate outcome summary
- execution status
- latency summary

## Migration rule

As production path is formalized, legacy endpoints may remain temporarily, but they must:
- forward into Murphy Core, or
- be clearly marked deprecated and excluded from the production surface

## Done criteria

This production target is satisfied when:
- Murphy Core app is the canonical server
- UI can inspect real system state
- execution path is typed and gated
- registry and capabilities endpoints tell the truth
- runtime authority is no longer ambiguous
