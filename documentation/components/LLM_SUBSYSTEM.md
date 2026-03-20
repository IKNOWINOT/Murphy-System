# LLM Subsystem — Technical Reference

**Murphy System — LLM Controller, Integration Layer, and Key Rotation**

> **Copyright © 2020–2026 Inoni LLC — Created by Corey Post  
> License: BSL 1.1**

---

## Table of Contents

1. [Overview](#overview)
2. [LLM Controller (`llm_controller.py`)](#llm-controller)
   - [Model Inventory](#model-inventory)
   - [Capability Routing](#capability-routing)
   - [Request / Response Structures](#request--response-structures)
   - [Cost Optimization](#cost-optimization)
3. [LLM Integration Layer (`llm_integration_layer.py`)](#llm-integration-layer)
   - [Provider Types](#provider-types)
   - [Domain-to-Provider Routing](#domain-to-provider-routing)
   - [Validation and HITL](#validation-and-hitl)
4. [Groq Key Rotation (`groq_key_rotator.py`)](#groq-key-rotation)
   - [Round-Robin Rotation](#round-robin-rotation)
   - [Auto-Disable on Failure](#auto-disable-on-failure)
   - [Usage Statistics](#usage-statistics)
5. [OpenAI-Compatible Provider (`openai_compatible_provider.py`)](#openai-compatible-provider)
6. [Environment Variables](#environment-variables)
7. [Architecture Diagram](#architecture-diagram)

---

## Overview

Murphy's LLM subsystem routes natural-language workloads across three tiers:

| Tier | Provider | Best For | Latency |
|------|----------|----------|---------|
| **Deterministic** | Aristotle / Wulfrum | Math, physics, engineering validation | ~10 ms |
| **Generative** | Groq (Mixtral / Llama / Gemma) | Creative, strategic, architectural | ~600 ms |
| **Self-hosted** | MFM (Murphy Foundation Model) | Private / offline inference | ~300 ms |
| **Onboard LLM** | Local small/medium model | Dev/test, no API key required | varies |

The `LLMController` selects a model based on *capability requirements*.  
The `LLMIntegrationLayer` further routes by *domain type* and validates math/physics outputs across providers, triggering a Human-in-the-Loop (HITL) gate when providers disagree.

---

## LLM Controller

**Source:** `src/llm_controller.py`

The `LLMController` is the master backend terminal that powers the neon terminal UI for system/module setup guidance and orchestrates all LLM calls within Murphy.

### Model Inventory

```python
class LLMModel(Enum):
    GROQ_MIXTRAL = "groq_mixtral"     # Large, high-quality reasoning
    GROQ_LLAMA   = "groq_llama"       # Balanced speed/quality
    GROQ_GEMMA   = "groq_gemma"       # Fast, low-latency
    LOCAL_SMALL  = "local_small"      # On-device, no API key
    LOCAL_MEDIUM = "local_medium"     # On-device, higher quality
    MFM          = "mfm"              # Murphy Foundation Model
```

Each model is registered as an `LLMModelInfo` with:

```python
@dataclass
class LLMModelInfo:
    name: str
    model_type: LLMModel
    capabilities: List[ModelCapability]   # What it can do
    max_context: int                       # Token context window
    cost_per_1k_tokens: float              # USD cost
    avg_latency: float                     # Seconds
    confidence_threshold: float            # Min confidence to auto-approve
    available: bool = True
```

### Capability Routing

The controller selects the cheapest available model that satisfies all required capabilities:

```python
class ModelCapability(Enum):
    CODE_GENERATION    = "code_generation"
    REASONING          = "reasoning"
    CONTEXT_PROCESSING = "context_processing"
    SWARM_PLANNING     = "swarm_planning"
    SAFETY_ANALYSIS    = "safety_analysis"
```

**Selection algorithm:**

1. Filter models by `available=True` and `required_capabilities ⊆ model.capabilities`.
2. Among passing models, pick the one with the lowest `cost_per_1k_tokens`.
3. If `model_preference` is set on the request, use that model if it passes capability check.
4. Fall back to the onboard LLM (`LOCAL_SMALL`) if all external models are unavailable.

### Request / Response Structures

```python
@dataclass
class LLMRequest:
    prompt: str
    context: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2000
    model_preference: Optional[LLMModel] = None
    require_capabilities: Optional[List[ModelCapability]] = None

@dataclass
class LLMResponse:
    content: str
    model_used: LLMModel
    tokens_used: int
    latency_ms: float
    confidence: float
    requires_human_review: bool = False
```

### Cost Optimization

The controller tracks per-model cumulative token cost and surfaces this in `/api/status`. When monthly costs exceed a configurable budget threshold (`MURPHY_LLM_BUDGET_USD`), it automatically downgrades to the cheapest capable tier.

---

## LLM Integration Layer

**Source:** `src/llm_integration_layer.py`

The `LLMIntegrationLayer` provides domain-aware routing between four providers, with cross-provider validation for high-stakes domains.

### Provider Types

```python
class LLMProvider(Enum):
    ARISTOTLE = "aristotle"   # Deterministic: math/physics validation
    WULFRUM   = "wulfrum"     # Fuzzy-match + math validation
    GROQ      = "groq"        # Generative: creative/strategic
    MFM       = "mfm"         # Murphy Foundation Model (self-hosted)
    AUTO      = "auto"        # Automatic routing (default)
```

### Domain-to-Provider Routing

The integration layer maps request domains to provider combinations:

| Domain | Primary Provider | Secondary (Validation) | HITL Trigger |
|--------|-----------------|------------------------|--------------|
| `MATHEMATICAL` | Aristotle | — | Never (deterministic) |
| `PHYSICS` | Aristotle | — | Never |
| `ENGINEERING` | Aristotle | Wulfrum | If disagreement |
| `CREATIVE` | Groq | — | Low confidence |
| `STRATEGIC` | Groq | — | Low confidence |
| `ARCHITECTURAL` | Groq | Wulfrum | If disagreement |
| `REGULATORY` | Aristotle | — | Low confidence |
| `GENERAL` | Groq | — | Low confidence |

```python
class DomainType(Enum):
    MATHEMATICAL   = "mathematical"
    PHYSICS        = "physics"
    ENGINEERING    = "engineering"
    CREATIVE       = "creative"
    STRATEGIC      = "strategic"
    ARCHITECTURAL  = "architectural"
    REGULATORY     = "regulatory"
    GENERAL        = "general"
```

### Validation and HITL

For engineering/architectural domains, both Aristotle and Wulfrum compute a result. If they **disagree** (difference > threshold), the integration layer:

1. Sets `ValidationStatus.DISAGREEMENT`.
2. Creates a HITL trigger via the gate system.
3. Returns the Aristotle result as the provisional answer.
4. Logs the disagreement in the audit trail.

```python
class ValidationStatus(Enum):
    VALIDATED   = "validated"
    DISAGREEMENT = "disagreement"   # Triggers HITL gate
    ERROR       = "error"
    PENDING     = "pending"
```

---

## Groq Key Rotation

**Source:** `src/groq_key_rotator.py`

Murphy distributes Groq API calls across multiple keys to maximize throughput and avoid rate limiting.

### Round-Robin Rotation

```python
rotator = GroqKeyRotator(keys=[
    ("Primary",   "gsk_aaaa..."),
    ("Secondary", "gsk_bbbb..."),
    ("Tertiary",  "gsk_cccc..."),
])

key = rotator.get_next_key()   # Thread-safe round-robin
rotator.report_success(key)
rotator.report_failure(key, "rate_limited")
```

### Auto-Disable on Failure

Each key tracks consecutive failures. When a key reaches `max_failures` (default: **3 consecutive failures**), it is automatically disabled:

- `is_active = False` — removed from rotation.
- `last_error` field records the most recent error message.
- An `ERROR` log is emitted with the key name (not the key value).

Keys can be re-enabled with `rotator.enable_key(name)`.

### Usage Statistics

```python
stats = rotator.get_statistics()
# Returns per-key stats:
# {
#   "Primary":   {"total": 4200, "success": 4190, "failed": 10, "active": True},
#   "Secondary": {"total": 4180, "success": 4180, "failed": 0,  "active": True},
# }
```

```python
@dataclass
class KeyStats:
    key: str                         # The API key (never logged)
    name: str                        # Human-readable label
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    last_used: Optional[datetime] = None
    last_error: Optional[str] = None
    is_active: bool = True
```

---

## OpenAI-Compatible Provider

**Source:** `src/openai_compatible_provider.py`

The `OpenAICompatibleProvider` is the unified gateway that implements the OpenAI API contract for all external and local LLM backends.

### Supported Provider Types

```python
class ProviderType(Enum):
    OPENAI   = "openai"    # OpenAI GPT-4/3.5
    AZURE    = "azure"     # Azure OpenAI deployment
    GROQ     = "groq"      # Groq API (Mixtral/Llama/Gemma)
    OLLAMA   = "ollama"    # Ollama local server
    VLLM     = "vllm"      # vLLM inference server
    LITELLM  = "litellm"   # LiteLLM proxy
    CUSTOM   = "custom"    # Any OpenAI-compatible endpoint
    ONBOARD  = "onboard"   # Murphy onboard model (no API key)
```

Configure via `ProviderConfig`:

```python
config = ProviderConfig(
    provider_type=ProviderType.GROQ,
    api_key=os.getenv("GROQ_API_KEY"),
    model="mixtral-8x7b-32768",
    base_url="https://api.groq.com/openai/v1",
)
provider = OpenAICompatibleProvider(config)
response: CompletionResponse = await provider.complete(messages)
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | — | Primary Groq API key |
| `GROQ_API_KEY_2` | — | Secondary Groq key for rotation |
| `GROQ_API_KEY_3` | — | Tertiary Groq key for rotation |
| `OPENAI_API_KEY` | — | OpenAI API key (optional) |
| `OPENAI_MODEL` | `gpt-4o-mini` | Default OpenAI model |
| `GROQ_MODEL` | `mixtral-8x7b-32768` | Default Groq model |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server base URL (read by all Ollama call-sites) |
| `OLLAMA_MODEL` | `llama3` | Default Ollama model; overrides the built-in probe order |
| `MURPHY_LLM_BUDGET_USD` | `50` | Monthly LLM spend cap |
| `MURPHY_LLM_DEFAULT_PROVIDER` | `groq` | Default provider for AUTO routing |
| `MURPHY_LLM_TIMEOUT` | `30` | Request timeout in seconds |

### Onboard LLM (Ollama)

When no external API key (`GROQ_API_KEY`, `OPENAI_API_KEY`, etc.) is set,
Murphy automatically uses its **onboard LLM** powered by Ollama:

1. **Install Ollama** (one-time, already done on the Hetzner server):
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   systemctl enable ollama
   systemctl start ollama
   ```
2. **Pull a model** (choose based on available RAM):
   ```bash
   ollama pull llama3        # ~4.7 GB — default, requires 6 GB+ RAM
   ollama pull phi3          # ~2.3 GB — use on 2.5–6 GB systems
   ollama pull tinyllama     # ~1 GB   — minimal footprint (< 2.5 GB RAM)
   ```
3. **Select the model** via env var (optional — auto-detected otherwise):
   ```bash
   export OLLAMA_MODEL=llama3
   ```
4. **Verify** via the health endpoint:
   ```bash
   curl -s http://localhost:8000/api/health?deep=true | python3 -m json.tool
   # Look for "ollama_running": true and "ollama_models": ["llama3"]
   ```

The deploy workflow automatically installs Ollama, starts the service, and
pulls `OLLAMA_MODEL` (default `llama3`) on every `git push` to `main`.

---

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Caller (API handler / automation engine / AionMind)                     │
└─────────────────────────────┬────────────────────────────────────────────┘
                              │ LLMRequest(domain=MATHEMATICAL, ...)
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      LLMController                                       │
│  1. Resolves required capabilities                                       │
│  2. Selects cheapest available model                                     │
│  3. Delegates to LLMIntegrationLayer                                     │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │
          ┌────────────────┼──────────────────┐
          │                │                  │
          ▼                ▼                  ▼
   ┌─────────────┐  ┌──────────────┐  ┌──────────────┐
   │  Aristotle  │  │   Wulfrum    │  │     Groq     │
   │  (math/phy) │  │ (fuzzy/eng)  │  │ (generative) │
   └──────┬──────┘  └──────┬───────┘  └──────┬───────┘
          │                │                  │
          └────────────────┼──────────────────┘
                           │ Validation / Disagreement check
                           ▼
               ┌───────────────────────┐
               │   ValidationStatus     │
               │  VALIDATED / DISAGREE  │
               └───────────┬───────────┘
                           │ DISAGREEMENT
                           ▼
               ┌───────────────────────┐
               │    HITL Gate Trigger  │
               │ (human review prompt) │
               └───────────────────────┘
```

---

*See also:*
- [`documentation/architecture/SYSTEM_COMPONENTS.md`](../architecture/SYSTEM_COMPONENTS.md) — high-level component map
- [`documentation/api/ENDPOINTS.md`](../api/ENDPOINTS.md) — API reference including MFM endpoints
- [`docs/AUDIT_AND_COMPLETION_REPORT.md`](../../docs/AUDIT_AND_COMPLETION_REPORT.md) — audit findings
