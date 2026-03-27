# Murphy System — LLM Subsystem

## Architecture

```
UI Chat  →  POST /api/chat
              │
              ▼
     IntegrationBus._process_chat()
              │
         ┌────┴──────────────────────────────────────────┐
         │ Step 1: LLMIntegrationLayer.route_request()   │
         │   • _determine_provider() picks domain        │
         │   • _call_groq()  →  tries DEEPINFRA_API_KEY       │
         │                  →  tries Ollama (phi3 first) │
         │                  →  falls back to template    │
         └────┬──────────────────────────────────────────┘
              │ (only if Step 1 returns None)
         ┌────┴─────────────────────────┐
         │ Step 2: LLMController        │
         │   • _query_local_small()     │
         │   • _query_ollama("phi3")    │
         └────┬─────────────────────────┘
              │
         ┌────┴─────────────────────────┐
         │ Step 3: LLMOutputValidator   │
         └──────────────────────────────┘
```

## Default Model: phi3

All local Ollama inference defaults to **phi3** (Microsoft's 3.8B parameter model).

| File | Setting |
|------|---------|
| `src/local_llm_fallback.py` | `_query_ollama(model="phi3")` |
| `src/llm_integration.py` | `OllamaLLM(model_name="phi3")` |
| `src/llm_swarm_integration.py` | `OLLAMA_MODEL=phi3` |
| `src/llm_integration_layer.py` | Ollama tried before canned templates |

## Model Probe Order

When Ollama is available, models are tried in this order:

```
["phi3", "llama3", "mistral", "phi", "tinyllama"]
```

## Provider Priority

1. **Groq Cloud** (`DEEPINFRA_API_KEY`) — fastest, cloud-hosted
2. **Ollama / phi3** — local, private, no API key needed
3. **Deterministic fallback** — template-based, always available

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/llm/providers` | Lists all providers with live Ollama status |
| `POST /api/llm/configure` | Hot-swap provider / API key without restart |
| `POST /api/llm/test` | Smoke-test the active provider |
| `POST /api/chat` | Main chat endpoint (routes through integration layer) |

## Ollama Setup (Production)

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull phi3 (default model)
ollama pull phi3

# Verify
ollama run phi3 "Hello"
```

### Systemd Integration

```ini
# /etc/systemd/system/murphy-production.service.d/override.conf
[Unit]
After=network.target ollama.service
Requires=ollama.service
```

### Environment Variables

```bash
OLLAMA_BASE_URL=http://localhost:11434   # Default Ollama endpoint
OLLAMA_MODEL=phi3                        # Default model
DEEPINFRA_API_KEY=di_...                    # Optional: DeepInfra cloud API key
```

## Agentic API Key Collection

Murphy includes a fully agentic API key harvester (`src/key_harvester.py`) that:

1. **Auto-detects** which provider keys are needed from workflow context
2. **Requests credentials** from the user via a HITL gate (email + password)
3. **Opens a real browser** so the user sees every action
4. **Requires explicit TOS approval** before any "I agree" checkbox
5. **Stores keys securely** via `CredentialVault` (Fernet-encrypted at rest)

### REST Endpoints

```
GET  /api/key-harvester/status               — Poll harvest status (15 providers tracked)
POST /api/key-harvester/start                — Start harvest (background)
GET  /api/key-harvester/pending-credentials  — What credentials does the user need to provide?
POST /api/key-harvester/credentials/{id}/provide  — User provides email/password
GET  /api/key-harvester/pending-tos          — Which TOS needs approval?
POST /api/key-harvester/tos/{id}/approve     — User approves TOS
GET  /api/key-harvester/audit-log            — Full audit trail
```

### Three Unbypassable Gates

1. **Credential gate first** — no action until user provides their email/password
2. **TOS gate before every checkbox** — every "I Agree" requires explicit human approval
3. **Visible browser** — user's own real browser; Murphy never acts in a hidden window

### Credential Storage via `POST /api/credentials/store`

```json
{ "integration": "sendgrid", "credential": "SG.xxxx" }
```

Supported integrations: `deepinfra`, `openai`, `anthropic`, `sendgrid`, `slack`, `stripe`, `hubspot`, `github`, `twilio`, `google_calendar`, `google_sheets`, `datadog`, `postgres`

The key is written to `.env` (persisted across restarts) and to `os.environ` (immediate use).

## LLM Mode Detection (Important!)

The LLM subsystem is **always active** — it never completely fails. When no external LLM API key is configured, it operates in "onboard" mode using the LocalLLMFallback.

### Mode Detection Logic

```python
# Check librarian status (preferred method)
status = murphy._get_librarian_status()
if status["mode"] == "onboard":
    # Using LocalLLMFallback (no external LLM)
elif status["mode"] == "llm":
    # Using external LLM API (Groq, OpenAI, Anthropic)

# IMPORTANT: Do NOT check llm_status["enabled"] — it is always True
# because the onboard fallback is always available.
```

### Mode Values

| Mode | Description |
|------|-------------|
| `external_api` | External LLM provider configured (Groq, OpenAI, Anthropic) |
| `onboard` | Using LocalLLMFallback (Ollama or pattern matcher) |

### Boot Validation

Use `validate_llm_boot_status()` at boot time to check LLM configuration:

```python
from src.startup_validator import validate_llm_boot_status

status = validate_llm_boot_status()
print(f"Mode: {status['mode']}")      # "external_api" or "onboard"
print(f"Provider: {status['provider']}")  # "deepinfra", "openai", "anthropic", or "onboard"
print(f"Healthy: {status['healthy']}")    # Always True (onboard is always available)
```
