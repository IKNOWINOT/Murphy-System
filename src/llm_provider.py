"""
llm_provider.py — Murphy System Unified LLM Provider
=====================================================
Single source of truth for all LLM API calls in Murphy System.

Provider chain (system-wide):
  1. DeepInfra  (primary)   — https://api.deepinfra.com/v1/openai
  2. Together.ai (fallback) — https://api.together.xyz/v1

Both use the OpenAI-compatible chat completions wire format.
Environment variables:
  DEEPINFRA_API_KEY   — DeepInfra API key (primary)
  TOGETHER_API_KEY    — Together.ai API key (fallback)

Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · BSL 1.1
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Provider constants
# ---------------------------------------------------------------------------

DEEPINFRA_BASE_URL = "https://api.deepinfra.com/v1/openai"
TOGETHER_BASE_URL  = "https://api.together.xyz/v1"

# Primary models (DeepInfra)
DEEPINFRA_CHAT_MODEL   = "meta-llama/Meta-Llama-3.1-70B-Instruct"
DEEPINFRA_FAST_MODEL   = "meta-llama/Meta-Llama-3.1-8B-Instruct"
DEEPINFRA_CODE_MODEL   = "Qwen/Qwen2.5-Coder-32B-Instruct"

# Fallback models (Together.ai)
TOGETHER_CHAT_MODEL    = "meta-llama/Llama-3.1-70B-Instruct-Turbo"
TOGETHER_FAST_MODEL    = "meta-llama/Llama-3.1-8B-Instruct-Turbo"
TOGETHER_CODE_MODEL    = "Qwen/Qwen2.5-Coder-32B-Instruct"

# DeepInfra Llama-3.1-70B context window: 131 072 tokens (prompt + output).
# Output is not artificially capped — the LLM produces whatever the request
# requires.  Callers may pass a lower max_tokens for smaller tasks.
DEEPINFRA_MODEL_CONTEXT = 131072

# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------

class _CircuitState(Enum):
    CLOSED    = "closed"
    OPEN      = "open"
    HALF_OPEN = "half_open"


class _CircuitBreaker:
    """Minimal circuit breaker — opens after N failures, recovers after timeout."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 30.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout  = recovery_timeout
        self._state            = _CircuitState.CLOSED
        self._failure_count    = 0
        self._last_failure_time: float = 0.0

    def record_success(self) -> None:
        self._failure_count = 0
        self._state = _CircuitState.CLOSED

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self.failure_threshold:
            self._state = _CircuitState.OPEN
            logger.warning("Circuit breaker OPEN after %d failures", self._failure_count)

    def allow_request(self) -> bool:
        if self._state == _CircuitState.CLOSED:
            return True
        elapsed = time.monotonic() - self._last_failure_time
        if elapsed >= self.recovery_timeout:
            self._state = _CircuitState.HALF_OPEN
            return True
        return False

    @property
    def state(self) -> str:
        return self._state.value


# ---------------------------------------------------------------------------
# Response dataclass
# ---------------------------------------------------------------------------

@dataclass
class LLMCompletion:
    content:           str
    model:             str
    provider:          str      # "deepinfra" | "together" | "onboard" | "fallback"
    tokens_prompt:     int  = 0
    tokens_completion: int  = 0
    tokens_total:      int  = 0
    latency_seconds:   float = 0.0
    request_id:        str  = field(default_factory=lambda: str(uuid.uuid4()))
    raw_response:      Dict[str, Any] = field(default_factory=dict)
    success:           bool = True   # False when provider is "fallback" / error path
    error:             Optional[str] = None


# ---------------------------------------------------------------------------
# Core provider class
# ---------------------------------------------------------------------------

class MurphyLLMProvider:
    """
    Unified LLM provider for Murphy System.

    Call priority:
        1. DeepInfra  (DEEPINFRA_API_KEY)
        2. Together.ai (TOGETHER_API_KEY)
        3. Onboard / local fallback

    Usage::

        from src.llm_provider import MurphyLLMProvider
        llm = MurphyLLMProvider.from_env()
        resp = llm.complete("Summarise this contract.", model_hint="chat")
    """

    def __init__(
        self,
        deepinfra_api_key: Optional[str] = None,
        together_api_key:  Optional[str] = None,
        timeout:           float = 120.0,
        max_retries:       int   = 2,
    ) -> None:
        self.deepinfra_api_key = deepinfra_api_key or os.getenv("DEEPINFRA_API_KEY", "")
        self.together_api_key  = together_api_key  or os.getenv("TOGETHER_API_KEY",  "")
        self.timeout     = timeout
        self.max_retries = max_retries

        self._di_circuit  = _CircuitBreaker()  # DeepInfra circuit
        self._tog_circuit = _CircuitBreaker()  # Together circuit

        # Lazy async clients (openai SDK)
        self._di_async_client:  Any = None
        self._tog_async_client: Any = None
        self._di_sync_client:   Any = None
        self._tog_sync_client:  Any = None

        _di  = "✅" if self.deepinfra_api_key  else "⚠️  (DEEPINFRA_API_KEY not set)"
        _tog = "✅" if self.together_api_key   else "⚠️  (TOGETHER_API_KEY not set)"
        logger.info("MurphyLLMProvider — DeepInfra: %s | Together.ai: %s", _di, _tog)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_env(cls) -> "MurphyLLMProvider":
        return cls(
            deepinfra_api_key=os.getenv("DEEPINFRA_API_KEY", ""),
            together_api_key= os.getenv("TOGETHER_API_KEY",  ""),
            timeout=    float(os.getenv("LLM_TIMEOUT",    "120")),
            max_retries=int(  os.getenv("LLM_MAX_RETRIES", "2")),
        )

    # ------------------------------------------------------------------
    # Model resolution
    # ------------------------------------------------------------------

    def _resolve_model(self, provider: str, model_hint: str = "chat") -> str:
        """Pick the right model for the provider and task hint."""
        hint = (model_hint or "chat").lower()
        if provider == "deepinfra":
            if "code" in hint:      return DEEPINFRA_CODE_MODEL
            if "fast" in hint:      return DEEPINFRA_FAST_MODEL
            return DEEPINFRA_CHAT_MODEL
        else:  # together
            if "code" in hint:      return TOGETHER_CODE_MODEL
            if "fast" in hint:      return TOGETHER_FAST_MODEL
            return TOGETHER_CHAT_MODEL

    # ------------------------------------------------------------------
    # HTTP helpers (sync — used by llm_integration_layer compatibility)
    # ------------------------------------------------------------------

    def _post_openai_compat(
        self,
        base_url:  str,
        api_key:   str,
        model:     str,
        messages:  List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens:  int   = DEEPINFRA_MODEL_CONTEXT,
    ) -> Dict[str, Any]:
        """POST to an OpenAI-compatible chat completions endpoint."""
        resp = requests.post(
            f"{base_url}/chat/completions",
            json={
                "model":       model,
                "messages":    messages,
                "temperature": temperature,
                "max_tokens":  max_tokens,
            },
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type":  "application/json",
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Synchronous completion (primary public API for sync code)
    # ------------------------------------------------------------------

    def complete(
        self,
        prompt:      str,
        *,
        system:      str   = "You are Murphy, an AI automation platform built by Inoni LLC.",
        model_hint:  str   = "chat",
        temperature: float = 0.7,
        max_tokens:  int   = DEEPINFRA_MODEL_CONTEXT,
    ) -> LLMCompletion:
        """Complete a prompt synchronously.

        Tries DeepInfra first, falls back to Together.ai, then onboard.
        """
        messages = [
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt},
        ]
        return self._complete_with_fallback(
            messages=messages,
            model_hint=model_hint,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def complete_messages(
        self,
        messages:    List[Dict[str, str]],
        *,
        model_hint:  str   = "chat",
        temperature: float = 0.7,
        max_tokens:  int   = DEEPINFRA_MODEL_CONTEXT,
    ) -> LLMCompletion:
        """Complete a messages list synchronously."""
        return self._complete_with_fallback(
            messages=messages,
            model_hint=model_hint,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def _complete_with_fallback(
        self,
        messages:    List[Dict[str, str]],
        model_hint:  str   = "chat",
        temperature: float = 0.7,
        max_tokens:  int   = DEEPINFRA_MODEL_CONTEXT,
    ) -> LLMCompletion:
        request_id = str(uuid.uuid4())

        # ── 1. DeepInfra (primary) ────────────────────────────────────
        if self.deepinfra_api_key and self._di_circuit.allow_request():
            model = self._resolve_model("deepinfra", model_hint)
            start = time.monotonic()
            try:
                data = self._post_openai_compat(
                    DEEPINFRA_BASE_URL, self.deepinfra_api_key,
                    model, messages, temperature, max_tokens,
                )
                elapsed = time.monotonic() - start
                self._di_circuit.record_success()
                content = data["choices"][0]["message"]["content"]
                usage   = data.get("usage", {})
                logger.info("DeepInfra ✅ %.2fs | %s", elapsed, model)
                return LLMCompletion(
                    content=content, model=model, provider="deepinfra",
                    tokens_prompt=usage.get("prompt_tokens", 0),
                    tokens_completion=usage.get("completion_tokens", 0),
                    tokens_total=usage.get("total_tokens", 0),
                    latency_seconds=elapsed, request_id=request_id,
                    raw_response=data,
                )
            except Exception as exc:
                elapsed = time.monotonic() - start
                self._di_circuit.record_failure()
                logger.warning("DeepInfra ⚠️  %.2fs | %s | falling back to Together.ai", elapsed, exc)

        # ── 2. Together.ai (fallback) ─────────────────────────────────
        if self.together_api_key and self._tog_circuit.allow_request():
            model = self._resolve_model("together", model_hint)
            start = time.monotonic()
            try:
                data = self._post_openai_compat(
                    TOGETHER_BASE_URL, self.together_api_key,
                    model, messages, temperature, max_tokens,
                )
                elapsed = time.monotonic() - start
                self._tog_circuit.record_success()
                content = data["choices"][0]["message"]["content"]
                usage   = data.get("usage", {})
                logger.info("Together.ai ✅ %.2fs | %s", elapsed, model)
                return LLMCompletion(
                    content=content, model=model, provider="together",
                    tokens_prompt=usage.get("prompt_tokens", 0),
                    tokens_completion=usage.get("completion_tokens", 0),
                    tokens_total=usage.get("total_tokens", 0),
                    latency_seconds=elapsed, request_id=request_id,
                    raw_response=data,
                )
            except Exception as exc:
                elapsed = time.monotonic() - start
                self._tog_circuit.record_failure()
                logger.warning("Together.ai ⚠️  %.2fs | %s | falling back to onboard", elapsed, exc)

        # ── 3. Onboard fallback ────────────────────────────────────────
        return self._onboard_fallback(messages, request_id)

    def _onboard_fallback(
        self,
        messages:   List[Dict[str, str]],
        request_id: str,
    ) -> LLMCompletion:
        """Local deterministic fallback when all API providers are down."""
        user_msg = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        preview  = user_msg[:120]
        content  = (
            f"[Murphy Onboard] API providers unavailable. "
            f"Request acknowledged: {preview}"
        )
        logger.warning("Using onboard fallback for request %s", request_id)
        return LLMCompletion(
            content=content, model="murphy-onboard", provider="onboard",
            request_id=request_id, success=True,
        )

    # ------------------------------------------------------------------
    # Async completion (primary public API for async code)
    # ------------------------------------------------------------------

    async def acomplete(
        self,
        prompt:      str,
        *,
        system:      str   = "You are Murphy, an AI automation platform built by Inoni LLC.",
        model_hint:  str   = "chat",
        temperature: float = 0.7,
        max_tokens:  int   = DEEPINFRA_MODEL_CONTEXT,  # WIRE-LLM-001: match sync default
    ) -> LLMCompletion:
        """Async completion — DeepInfra primary, Together.ai fallback."""
        messages = [
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt},
        ]
        return await self._acomplete_with_fallback(
            messages=messages,
            model_hint=model_hint,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def acomplete_messages(
        self,
        messages:    List[Dict[str, str]],
        *,
        model_hint:  str   = "chat",
        temperature: float = 0.7,
        max_tokens:  int   = DEEPINFRA_MODEL_CONTEXT,  # WIRE-LLM-001: match sync default
    ) -> LLMCompletion:
        """Async messages completion."""
        return await self._acomplete_with_fallback(
            messages=messages,
            model_hint=model_hint,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def _acomplete_with_fallback(
        self,
        messages:    List[Dict[str, str]],
        model_hint:  str   = "chat",
        temperature: float = 0.7,
        max_tokens:  int   = DEEPINFRA_MODEL_CONTEXT,  # WIRE-LLM-001: match sync default
    ) -> LLMCompletion:
        request_id = str(uuid.uuid4())

        # ── 1. DeepInfra async ────────────────────────────────────────
        if self.deepinfra_api_key and self._di_circuit.allow_request():
            model = self._resolve_model("deepinfra", model_hint)
            client = self._get_async_client("deepinfra")
            if client:
                start = time.monotonic()
                try:
                    resp = await client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    elapsed = time.monotonic() - start
                    self._di_circuit.record_success()
                    content = resp.choices[0].message.content or ""
                    usage   = resp.usage
                    logger.info("DeepInfra async ✅ %.2fs | %s", elapsed, model)
                    return LLMCompletion(
                        content=content, model=model, provider="deepinfra",
                        tokens_prompt=usage.prompt_tokens if usage else 0,
                        tokens_completion=usage.completion_tokens if usage else 0,
                        tokens_total=usage.total_tokens if usage else 0,
                        latency_seconds=elapsed, request_id=request_id,
                    )
                except Exception as exc:
                    elapsed = time.monotonic() - start
                    self._di_circuit.record_failure()
                    logger.warning("DeepInfra async ⚠️  %.2fs | %s | trying Together.ai", elapsed, exc)

        # ── 2. Together.ai async fallback ─────────────────────────────
        if self.together_api_key and self._tog_circuit.allow_request():
            model = self._resolve_model("together", model_hint)
            client = self._get_async_client("together")
            if client:
                start = time.monotonic()
                try:
                    resp = await client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    elapsed = time.monotonic() - start
                    self._tog_circuit.record_success()
                    content = resp.choices[0].message.content or ""
                    usage   = resp.usage
                    logger.info("Together.ai async ✅ %.2fs | %s", elapsed, model)
                    return LLMCompletion(
                        content=content, model=model, provider="together",
                        tokens_prompt=usage.prompt_tokens if usage else 0,
                        tokens_completion=usage.completion_tokens if usage else 0,
                        tokens_total=usage.total_tokens if usage else 0,
                        latency_seconds=elapsed, request_id=request_id,
                    )
                except Exception as exc:
                    elapsed = time.monotonic() - start
                    self._tog_circuit.record_failure()
                    logger.warning("Together.ai async ⚠️  %.2fs | %s | falling back to onboard", elapsed, exc)

        # ── 3. Onboard fallback ────────────────────────────────────────
        return self._onboard_fallback(messages, request_id)

    def _get_async_client(self, provider: str) -> Any:
        """Lazily create an async openai-SDK client for the given provider."""
        try:
            import openai
        except ImportError:
            logger.warning("openai package not installed — async clients unavailable")
            return None

        if provider == "deepinfra":
            if self._di_async_client is None:
                self._di_async_client = openai.AsyncOpenAI(
                    api_key=self.deepinfra_api_key,
                    base_url=DEEPINFRA_BASE_URL,
                    timeout=self.timeout,
                    max_retries=self.max_retries,
                )
            return self._di_async_client
        else:  # together
            if self._tog_async_client is None:
                self._tog_async_client = openai.AsyncOpenAI(
                    api_key=self.together_api_key,
                    base_url=TOGETHER_BASE_URL,
                    timeout=self.timeout,
                    max_retries=self.max_retries,
                )
            return self._tog_async_client

    def _get_sync_client(self, provider: str) -> Any:
        """Lazily create a sync openai-SDK client for the given provider."""
        try:
            import openai
        except ImportError:
            return None

        if provider == "deepinfra":
            if self._di_sync_client is None:
                self._di_sync_client = openai.OpenAI(
                    api_key=self.deepinfra_api_key,
                    base_url=DEEPINFRA_BASE_URL,
                    timeout=self.timeout,
                    max_retries=self.max_retries,
                )
            return self._di_sync_client
        else:
            if self._tog_sync_client is None:
                self._tog_sync_client = openai.OpenAI(
                    api_key=self.together_api_key,
                    base_url=TOGETHER_BASE_URL,
                    timeout=self.timeout,
                    max_retries=self.max_retries,
                )
            return self._tog_sync_client

    # ------------------------------------------------------------------
    # Status / health
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        return {
            "deepinfra": {
                "configured":     bool(self.deepinfra_api_key),
                "base_url":       DEEPINFRA_BASE_URL,
                "default_model":  DEEPINFRA_CHAT_MODEL,
                "circuit_state":  self._di_circuit.state,
            },
            "together": {
                "configured":     bool(self.together_api_key),
                "base_url":       TOGETHER_BASE_URL,
                "default_model":  TOGETHER_CHAT_MODEL,
                "circuit_state":  self._tog_circuit.state,
            },
            "priority": ["deepinfra", "together", "onboard"],
        }


# ---------------------------------------------------------------------------
# Module-level singleton (imported everywhere)
# ---------------------------------------------------------------------------

_provider: Optional[MurphyLLMProvider] = None


def get_llm() -> MurphyLLMProvider:
    """Return the module-level singleton MurphyLLMProvider, creating it on first call."""
    global _provider
    if _provider is None:
        _provider = MurphyLLMProvider.from_env()
    return _provider


def reset_llm(provider: Optional[MurphyLLMProvider] = None) -> None:
    """Reset the singleton (useful in tests)."""
    global _provider
    _provider = provider


# ---------------------------------------------------------------------------
# Convenience shorthands matching OpenAI-compatible call patterns (DeepInfra / Together.ai)
# ---------------------------------------------------------------------------

def complete(
    prompt:      str,
    system:      str   = "You are Murphy, an AI automation platform built by Inoni LLC.",
    model_hint:  str   = "chat",
    temperature: float = 0.7,
    max_tokens:  int   = DEEPINFRA_MODEL_CONTEXT,  # WIRE-LLM-001: match class default
) -> str:
    """Single-call convenience: returns just the content string."""
    return get_llm().complete(
        prompt, system=system, model_hint=model_hint,
        temperature=temperature, max_tokens=max_tokens,
    ).content


async def acomplete(
    prompt:      str,
    system:      str   = "You are Murphy, an AI automation platform built by Inoni LLC.",
    model_hint:  str   = "chat",
    temperature: float = 0.7,
    max_tokens:  int   = DEEPINFRA_MODEL_CONTEXT,  # WIRE-LLM-001: match class default
) -> str:
    """Async convenience: returns just the content string."""
    resp = await get_llm().acomplete(
        prompt, system=system, model_hint=model_hint,
        temperature=temperature, max_tokens=max_tokens,
    )
    return resp.content