# ADR-0002: DeepInfra is the primary LLM provider

* **Status:** Accepted
* **Date:** 2026-04-22 (retroactive)

## Context

Murphy executes thousands of LLM calls per tenant per day across diverse
workloads: summarisation, code generation, classification, agent reasoning,
embedding-style retrieval. The platform must:

1. Run cheaply enough that the unit economics close at the founder's target
   pricing tier.
2. Support multiple model families (general-purpose, code, small-and-fast,
   long-context) through a single integration surface.
3. Allow per-tenant routing decisions without re-architecting on every model
   release.
4. Be replaceable — no LLM vendor stays cheapest or best forever.

We evaluated OpenAI (gpt-4o, gpt-4o-mini), Anthropic (Claude family),
Google (Gemini), AWS Bedrock, Together AI, Groq, and DeepInfra.

## Decision

DeepInfra is the **primary** provider. The selection criteria that decided
it:

* Hosts the open-weights models we already prefer (Llama 3.x, Qwen, Mixtral)
  with OpenAI-compatible APIs, so swap cost is one base-URL change.
* Per-token cost is consistently among the lowest of the providers tested for
  the model classes we use most (small fast models for routing, mid-size for
  generation).
* Provides both chat and embedding endpoints, removing the need for a second
  embeddings vendor.
* Operationally simple: no AWS account / IAM / region quota management.

Other providers are **secondary** and reachable through the same
`MurphyLLMProvider` interface (`src/llm_provider.py`):

* **Local** (Ollama / llama.cpp) — for air-gapped tenants and dev loops.
* **OpenAI / Anthropic** — for capabilities DeepInfra does not host
  (e.g. specific frontier models when a tenant explicitly requests them).
* **Groq** — for latency-sensitive paths where cost is secondary.

The router can fall back across providers on rate-limit / 5xx responses.

## Consequences

* **Positive:** single dominant provider keeps integration code small.
  Fallback paths are tested but exercised rarely, so we keep one provider's
  quirks in the hot path.
* **Positive:** open-weights focus protects against the political /
  pricing risk of a single closed-model vendor (we can move the same model
  family to a different host).
* **Negative:** DeepInfra outages affect the majority of tenant traffic
  until the fallback path activates. SLO-burn alerts (Item 17) and the
  multi-provider fallback in `MurphyLLMProvider` mitigate but do not
  eliminate this.
* **Negative:** when a frontier capability ships first on OpenAI or
  Anthropic, we lag until a comparable open-weights model exists.
