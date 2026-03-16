# LLM Subsystem

**Package:** `src/` (standalone modules)  
**Key files:** `llm_controller.py`, `llm_integration_layer.py`, `groq_key_rotator.py`, `openai_compatible_provider.py`  
**Last updated:** 2026-03-16

---

## Overview

The Murphy System LLM Subsystem is the unified gateway between the application layer and all language model providers. It provides:

- **Provider abstraction** — a single `OpenAICompatibleProvider` that speaks to OpenAI, Azure OpenAI, Groq, Ollama, vLLM, LiteLLM, custom endpoints, and the on-board Murphy Foundation Model (MFM)
- **Intelligent routing** — `LLMController` selects the best model for each request based on capability, cost, and context requirements
- **Domain-to-provider routing** — `LLMIntegrationLayer` routes by knowledge domain (mathematical → Aristotle, creative → Groq, etc.)
- **API key rotation** — `GroqKeyRotator` distributes calls across multiple keys to maximize throughput and handle key failures gracefully

---

## Architecture Diagram

```
Application Layer
       │
       ▼
LLMController ──────────────────────────────┐
  - model selection (capability + cost)     │
  - context routing                         │
       │                                    │
       ▼                                    ▼
LLMIntegrationLayer              OpenAICompatibleProvider
  - domain routing (8 domains)    - ProviderType enum (8 providers)
  - HITL trigger detection        - Unified request / response model
  - math/physics validation       │
       │                          │
       ▼                          ▼
GroqKeyRotator          Provider Backends
  - round-robin rotation   OpenAI / Azure / Groq / Ollama /
  - auto-disable on error  vLLM / LiteLLM / Custom / MFM
  - usage stats
```

---

## Modules

### `openai_compatible_provider.py`

**Central abstraction layer for all LLM providers.**

#### Supported Provider Types

| `ProviderType` | Description |
|----------------|-------------|
| `OPENAI` | OpenAI API (gpt-4, gpt-3.5-turbo, etc.) |
| `AZURE` | Azure OpenAI Service |
| `GROQ` | Groq Cloud (Mixtral, LLaMA, Gemma) |
| `OLLAMA` | Local Ollama server |
| `VLLM` | vLLM inference server |
| `LITELLM` | LiteLLM unified proxy |
| `CUSTOM` | Custom OpenAI-compatible endpoint |
| `ONBOARD` | Murphy Foundation Model (on-device) |

#### Key Classes

```python
ProviderConfig(
    provider_type: ProviderType,
    api_key: str,
    base_url: str,
    model: str,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    timeout: float = 30.0,
)

ChatMessage(role: str, content: str)

CompletionResponse(
    content: str,
    model: str,
    usage: dict,
    finish_reason: str,
)
```

#### Usage

```python
from openai_compatible_provider import OpenAICompatibleProvider, ProviderConfig, ProviderType

config = ProviderConfig(
    provider_type=ProviderType.GROQ,
    api_key=os.environ["GROQ_API_KEY"],
    base_url="https://api.groq.com/openai/v1",
    model="mixtral-8x7b-32768",
)
provider = OpenAICompatibleProvider(config)
response = await provider.complete([ChatMessage(role="user", content="Hello")])
print(response.content)
```

---

### `llm_controller.py`

**Master backend controller — model selection and routing logic.**

Based on the Recursive Language Models (RLM) pattern (arXiv:2512.24601).

#### Model Registry

| `LLMModel` | Description | Best For |
|------------|-------------|----------|
| `GROQ_MIXTRAL` | Groq Mixtral-8x7B | General purpose, high quality |
| `GROQ_LLAMA` | Groq LLaMA-3 | Fast inference, reasoning |
| `GROQ_GEMMA` | Groq Gemma-7B | Lightweight tasks |
| `LOCAL_SMALL` | On-device small model | Offline, fast |
| `LOCAL_MEDIUM` | On-device medium model | Offline, balanced |
| `MFM` | Murphy Foundation Model | Murphy-specific domain knowledge |

#### Model Capabilities

| `ModelCapability` | Description |
|-------------------|-------------|
| `CODE_GENERATION` | Generate and review code |
| `REASONING` | Multi-step logical reasoning |
| `CONTEXT_PROCESSING` | Long-context document processing |
| `SWARM_PLANNING` | Multi-agent task decomposition |
| `SAFETY_ANALYSIS` | Risk and safety assessment |

#### Selection Algorithm

The controller selects the model with the highest capability match score that stays within the cost budget:

```
score = Σ (capability_weight × capability_match) − cost_penalty
```

#### Usage

```python
from llm_controller import LLMController, ModelCapability

controller = LLMController()
response = await controller.complete(
    prompt="Analyse the safety of this industrial system...",
    required_capabilities=[ModelCapability.SAFETY_ANALYSIS, ModelCapability.REASONING],
    max_cost_per_1k=0.01,
)
```

---

### `llm_integration_layer.py`

**Domain-to-provider routing with HITL validation triggers.**

#### Domain Routing Table

| `DomainType` | Primary Provider | Secondary | HITL Trigger |
|--------------|-----------------|-----------|--------------|
| `MATHEMATICAL` | Aristotle | — | On disagreement |
| `PHYSICS` | Aristotle | — | On disagreement |
| `ENGINEERING` | Aristotle | Wulfrum | Always validate |
| `CREATIVE` | Groq | — | Never |
| `STRATEGIC` | Groq | — | On low confidence |
| `ARCHITECTURAL` | Groq | Wulfrum | On disagreement |
| `REGULATORY` | Aristotle | — | Always |
| `GENERAL` | Groq | — | Never |

#### Validation Flow

```
Request ──► route_request()
               │
               ├── determine_provider(domain)
               │
               ├── execute_request(provider)
               │
               └── validate_response()
                       │
                       ├── math/physics: cross-validate with Wulfrum
                       │
                       └── disagreement: emit HumanLoopTrigger
```

#### Key Classes

```python
LLMRequest(
    request_id: str,
    provider: LLMProvider,
    domain: DomainType,
    prompt: str,
    context: dict,
    requires_validation: bool,
)

LLMResponse(
    request_id: str,
    provider: LLMProvider,
    content: str,
    validation_status: ValidationStatus,
    human_loop_triggers: list[HumanLoopTrigger],
)

HumanLoopTrigger(
    trigger_id: str,
    reason: str,
    urgency: str,
    context: dict,
)
```

#### Usage

```python
from llm_integration_layer import LLMIntegrationLayer, DomainType, LLMProvider

layer = LLMIntegrationLayer(
    groq_api_key=os.environ["GROQ_API_KEY"],
)
response = layer.route_request(
    prompt="Calculate the load-bearing capacity of this beam...",
    domain=DomainType.ENGINEERING,
)
if response.human_loop_triggers:
    # Escalate to HITL queue
    for trigger in response.human_loop_triggers:
        hitl_queue.add(trigger)
```

---

### `groq_key_rotator.py`

**Round-robin API key rotation with automatic failure handling.**

#### Features

- Round-robin distribution across N API keys
- Automatic key disabling after repeated failures (`disable_threshold`, default 3)
- Per-key statistics: total calls, successful calls, failed calls, last error
- Thread-safe via `threading.Lock`
- Re-enable disabled keys after a configurable recovery window

#### `KeyStats` Fields

| Field | Type | Description |
|-------|------|-------------|
| `key` | `str` | The API key value |
| `name` | `str` | Human-readable label |
| `total_calls` | `int` | Total requests using this key |
| `successful_calls` | `int` | Successfully completed requests |
| `failed_calls` | `int` | Requests that resulted in an error |
| `is_active` | `bool` | Whether the key is eligible for rotation |
| `last_error` | `str | None` | Most recent error message |

#### Usage

```python
from groq_key_rotator import GroqKeyRotator

rotator = GroqKeyRotator([
    ("Primary", os.environ["GROQ_KEY_1"]),
    ("Secondary", os.environ["GROQ_KEY_2"]),
    ("Tertiary", os.environ["GROQ_KEY_3"]),
])

name, key = rotator.get_next_key()
# Use key for Groq API call
rotator.record_success(name)  # or rotator.record_failure(name, "Rate limited")

stats = rotator.get_statistics()
# [{"name": "Primary", "total_calls": 42, "success_rate": 0.98, "is_active": True}, ...]
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | Optional | Default Groq API key |
| `GROQ_API_KEY_2` | Optional | Secondary Groq key for rotation |
| `GROQ_API_KEY_3` | Optional | Tertiary Groq key for rotation |
| `OPENAI_API_KEY` | Optional | OpenAI API key |
| `AZURE_OPENAI_API_KEY` | Optional | Azure OpenAI API key |
| `AZURE_OPENAI_ENDPOINT` | Optional | Azure OpenAI endpoint URL |
| `OLLAMA_BASE_URL` | Optional | Ollama server URL (default: `http://localhost:11434`) |
| `MFM_MODEL_PATH` | Optional | Path to on-device Murphy Foundation Model |
| `LLM_DEFAULT_PROVIDER` | Optional | Default provider (`groq`, `openai`, `mfm`, …) |
| `LLM_MAX_TOKENS` | Optional | Global token limit override (default: 2048) |
| `LLM_TEMPERATURE` | Optional | Global temperature override (default: 0.7) |

---

## Testing

```bash
# Unit tests
python -m pytest tests/test_groq_key_rotator.py tests/test_llm_integration_layer.py --no-cov -q

# Groq integration tests (requires GROQ_API_KEY)
python -m pytest tests/test_groq_integration.py --no-cov -q
```

---

## Related Documentation

- `documentation/components/` — Component-level architecture docs
- `docs/AUAR_TECHNICAL_PROPOSAL.md` — AUAR routing proposal (references LLM layer)
- `documentation/api/ENDPOINTS.md` — API endpoints that use LLM services
