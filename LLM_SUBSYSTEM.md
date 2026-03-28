# Murphy System — LLM Subsystem

## Architecture (Post-Migration — DeepInfra + Together.ai)

```
UI Chat  →  POST /api/chat
              │
              ▼
     MurphySystem._try_llm_generate()
              │
         ┌────┴──────────────────────────────────────────┐
         │ Chain 1: Direct DeepInfra API (runtime core)  │
         │   • DEEPINFRA_API_KEY → api.deepinfra.com     │
         │   • OpenAI-compatible endpoint                │
         │   • Model: meta-llama/Llama-3.3-70B-Instruct  │
         └────┬──────────────────────────────────────────┘
              │ (if Chain 1 fails or unavailable)
         ┌────┴──────────────────────────────────────────┐
         │ Chain 2: MurphyLLMProvider (src/llm_provider) │
         │   • Primary: DeepInfra (api.deepinfra.com)    │
         │   • Fallback: Together.ai (api.together.xyz)  │
         │   • Emergency: LocalLLMFallback               │
         └────┬──────────────────────────────────────────┘
              │ (only if all cloud providers fail)
         ┌────┴─────────────────────────────────────────┐
         │ Chain 3: Local Fallback                      │
         │   • Ollama (phi3, llama3, mistral)           │
         │   • Deterministic template matcher           │
         └──────────────────────────────────────────────┘


POST /api/prompt  →  production_router
              │
              ▼
     MurphyLLMProvider.generate()
              │
         ┌────┴──────────────────────────────────────────┐
         │ Primary: DeepInfra API                        │
         │   • https://api.deepinfra.com/v1/openai       │
         │   • DEEPINFRA_API_KEY from environment        │
         ├───────────────────────────────────────────────┤
         │ Fallback: Together.ai API                     │
         │   • https://api.together.xyz/v1               │
         │   • TOGETHER_API_KEY from environment         │
         ├───────────────────────────────────────────────┤
         │ Emergency: LocalLLMFallback                   │
         │   • Ollama → deterministic templates          │
         └──────────────────────────────────────────────┘
```

## Provider Priority

| Priority | Provider | Endpoint | Env Var | Model |
|----------|----------|----------|---------|-------|
| 1 (Primary) | **DeepInfra** | `https://api.deepinfra.com/v1/openai` | `DEEPINFRA_API_KEY` | `meta-llama/Llama-3.3-70B-Instruct` |
| 2 (Fallback) | **Together.ai** | `https://api.together.xyz/v1` | `TOGETHER_API_KEY` | `meta-llama/Llama-3.3-70B-Instruct-Turbo` |
| 3 (Local) | **Ollama** | `http://localhost:11434` | `OLLAMA_HOST` | `phi3` → `llama3` → `mistral` |
| 4 (Emergency) | **LocalLLMFallback** | (in-process) | — | Deterministic template matcher |

## Key Files

| File | Role |
|------|------|
| `src/llm_provider.py` | **MurphyLLMProvider** — unified provider with DeepInfra + Together.ai + fallback |
| `src/llm_integration_layer.py` | LLMIntegrationLayer — routes requests by domain, calls providers |
| `src/local_llm_fallback.py` | LocalLLMFallback — Ollama probe + deterministic templates |
| `src/runtime/murphy_system_core.py` | MurphySystem._try_llm_generate() — direct DeepInfra API chain |
| `src/production_router.py` | /api/prompt endpoint — uses MurphyLLMProvider |

## Default Local Model: phi3

All local Ollama inference defaults to **phi3** (Microsoft's 3.8B parameter model).

| File | Setting |
|------|---------|
| `src/local_llm_fallback.py` | `_query_ollama(model="phi3")` |
| `src/llm_integration.py` | `OllamaLLM(model_name="phi3")` |
| `src/llm_swarm_integration.py` | `OLLAMA_MODEL=phi3` |
| `src/llm_integration_layer.py` | Ollama tried before deterministic templates |

## Model Probe Order (Ollama)

When Ollama is available, models are tried in this order:

```
["phi3", "llama3", "mistral", "phi", "tinyllama"]
```

## API Endpoints

| Endpoint | Server | Description |
|----------|--------|-------------|
| `POST /api/chat` | Runtime (core) | Main chat — uses _try_llm_generate() → DeepInfra direct |
| `POST /api/prompt` | Production Router | Prompt completion — uses MurphyLLMProvider |
| `GET /api/llm/providers` | Runtime | Lists all providers with live Ollama status |
| `POST /api/llm/configure` | Runtime | Hot-swap provider / API key without restart |
| `GET /api/llm/status` | Runtime | Current LLM provider status and health |

## Hot-Swap Configuration

```bash
curl -X POST http://localhost:8000/api/llm/configure \
  -H "Content-Type: application/json" \
  -d '{"provider": "deepinfra", "api_key": "your-key-here"}'
```

The key is written to `.env` (persisted across restarts) and to `os.environ` (immediate use).

## LLM Mode Detection

The LLM subsystem is **always active** — it never completely fails. When no external LLM API key is configured, it operates in "onboard" mode using the LocalLLMFallback.

### Mode Detection Logic

```python
# Check librarian status (preferred method)
status = murphy._get_librarian_status()
if status["mode"] == "onboard":
    # Using LocalLLMFallback (no external LLM)
elif status["mode"] == "llm":
    # Using external LLM API (DeepInfra, Together.ai)

# IMPORTANT: Do NOT check llm_status["enabled"] — it is always True
# because the onboard fallback is always available.
```

### Mode Values

| Mode | Description |
|------|-------------|
| `external_api` | External LLM provider configured (DeepInfra, Together.ai) |
| `onboard` | Using LocalLLMFallback (Ollama or pattern matcher) |

### Boot Validation

Use `validate_llm_boot_status()` at boot time to check LLM configuration:

```python
from src.startup_validator import validate_llm_boot_status

status = validate_llm_boot_status()
print(f"Mode: {status['mode']}")      # "external_api" or "onboard"
print(f"Provider: {status['provider']}")  # "deepinfra", "together", or "onboard"
print(f"Healthy: {status['healthy']}")    # Always True (onboard is always available)
```

## Migration History

- **Pre-2026**: Groq API as primary cloud provider
- **2026-03-26**: Migrated to DeepInfra (primary) + Together.ai (fallback)
  - 286 files changed across the codebase
  - All `groq` references replaced with `deepinfra`/`together` equivalents
  - OpenAI-compatible API format retained for seamless switching
  - Branch: `audit/comprehensive-production-readiness`