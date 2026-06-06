# Murphy Reply Channels — Canonical Routes (2026-06-04)

Verified 2026-06-04 17:46 UTC. Use these exact paths.

## Primary channel — Chat
- **External:** `POST https://murphy.systems/api/chat-v2`
- **Internal:** `POST http://127.0.0.1:8084/api/chat-v2`
- **Service:** `murphy-r387-chat-v2.service` on port 8084
- **Provider chain:** ollama (phi3:latest) → DeepInfra fallback
- **Body:** `{"message": "...", "session_id": "..."}`
- **Returns:** `{"reply": str, "provider_used": str, "model": str, "tokens": {}, "cost_usd": float, "latency_ms": int, "fallback_chain": [str]}`
- **Status routes:** `/health`, `/api/chat-v2/state`

## Formal decision queue — HITL-v2
- **Service:** `murphy-r384-hitl.service` on port 8083
- **Routes:**
  - `GET  /api/hitl-v2/queue` — list pending decisions
  - `POST /api/hitl-v2/mail/{queue_id}/approve` — approve outbound mail
  - `POST /api/hitl-v2/mail/{queue_id}/reject` — reject outbound mail
  - `GET  /api/hitl-v2/mail/{queue_id}/inspect` — view full draft body
  - `POST /api/hitl-v2/form-intake/{item_id}/approve`
  - `POST /api/hitl-v2/form-intake/{item_id}/reject`
- `/api/hitl-v2/items` — **does not exist**. Don't call it.

## Domain dispatch — Rosetta
- **Service:** monolith only (port 8000 via murphy.service)
- **Route:** `POST /api/rosetta/dispatch` (when monolith is up)
- **Note:** No microservice for Rosetta exists. If the monolith is down, Rosetta is down.
- **Status (2026-06-04 10:45 PT):** monolith is up again, route should work.

## Legacy paths — DO NOT USE
- `/api/chat` — monolith stub, returns empty body
- `/api/hitl-v2/items` — never existed
- Anything starting with `/api/chat/` (singular) when you mean chat-v2

## Quick reference
```bash
# Ask Murphy a question
curl -s -m 30 -X POST https://murphy.systems/api/chat-v2 \
  -H "Content-Type: application/json" \
  -d '{"message":"...","session_id":"superagent_<purpose>_<utc>"}'

# Put a decision in the formal queue
curl -s -m 10 https://murphy.systems/api/hitl-v2/queue

# Domain-route (only if monolith healthy)
curl -s -m 10 -X POST https://murphy.systems/api/rosetta/dispatch \
  -H "X-API-Key: $KEY" -d '{"role":"sales","task":"..."}'
```
