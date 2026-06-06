# Chat (Pillar B)

Murphy's primary conversational surface is `chat-v2`, a microservice with multi-provider LLM routing.

## Service
- **Unit:** `murphy-r387-chat-v2.service`
- **Port:** 8084 (internal)
- **Code:** `/usr/local/bin/r387_chat_v2.py`

## Routes
- `POST /api/chat-v2` — main chat endpoint
- `GET  /api/chat-v2/state` — provider availability + recent fallback stats
- `GET  /health` — liveness

## Provider chain
1. **Ollama** (local) — `phi3:latest`. Fast, cheap, no external dependency.
2. **DeepInfra** fallback — `meta-llama/Meta-Llama-3.1-8B-Instruct`. Used when Ollama fails or times out.

## Request shape
```json
POST /api/chat-v2
{ "message": "...", "session_id": "..." }
```

## Response shape
```json
{
  "reply": "string",
  "provider_used": "ollama|deepinfra",
  "model": "phi3:latest|...",
  "tokens": {"prompt": int, "completion": int},
  "cost_usd": float,
  "latency_ms": int,
  "fallback_chain": ["ollama_succeeded"|"ollama_failed", ...]
}
```

## UI
The user-facing chat lives at `/chat` (rendered by `murphy_chat.html`). Requests go through nginx → 127.0.0.1:8084.

## Legacy
`/api/chat` (singular, on the monolith) is a stub. Use `/api/chat-v2` exclusively.

Last updated: 2026-06-04
