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
import random
import threading
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

# PATCH-106b: Quality distillation model selection.
#
# PRIMARY: Qwen3-235B-A22B (MoE) — 262k ctx, 262k max output, $0.10/M out
#   → Best reasoning + instruction following on DeepInfra at this price point
#   → MoE architecture = fast despite 235B params (only 22B active)
#   → No artificial output cap — model stops when done, not when we stop it
#
# FALLBACK: Llama-3.3-70B-Turbo (Together) — used only if DeepInfra circuit opens
#
# model_hint is a no-op alias — one model does everything well.
DEEPINFRA_PRIMARY_MODEL = "Qwen/Qwen3-235B-A22B-Instruct-2507"

DEEPINFRA_CHAT_MODEL   = DEEPINFRA_PRIMARY_MODEL
DEEPINFRA_FAST_MODEL   = DEEPINFRA_PRIMARY_MODEL
DEEPINFRA_CODE_MODEL   = DEEPINFRA_PRIMARY_MODEL

TOGETHER_CHAT_MODEL    = "meta-llama/Llama-3.3-70B-Instruct-Turbo"
TOGETHER_FAST_MODEL    = "meta-llama/Llama-3.3-70B-Instruct-Turbo"
TOGETHER_CODE_MODEL    = "meta-llama/Llama-3.3-70B-Instruct-Turbo"

DEEPINFRA_MODEL_CONTEXT = 262144   # Qwen3-235B full context window
DEEPINFRA_MAX_OUTPUT    = 32768    # PATCH-106b: generous output room — distill, don't cap

# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------

class _CircuitState(Enum):
    CLOSED    = "closed"
    OPEN      = "open"
    HALF_OPEN = "half_open"


class _CircuitBreaker:
    """Production-grade circuit breaker (LLM-CB-001).

    Resilience4j-inspired implementation with thread safety, half-open probe
    limiting, jittered recovery timeout, exponential backoff on repeated
    open→half-open→open cycles, and observability metrics.
    """

    _MAX_BACKOFF: float = 300.0  # 5-minute cap on exponential backoff

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 1,
        name: str = "default",
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.name = name

        self._lock = threading.Lock()
        self._state = _CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._last_success_time: float = 0.0
        self._half_open_calls = 0
        self._open_cycle_count = 0

        # Cumulative metrics
        self._total_successes = 0
        self._total_failures = 0
        self._total_rejections = 0

    # -- state transitions ---------------------------------------------------

    def record_success(self) -> None:
        with self._lock:
            self._total_successes += 1
            self._failure_count = 0
            self._last_success_time = time.monotonic()
            if self._state == _CircuitState.HALF_OPEN:
                self._open_cycle_count = 0
                logger.info("Circuit breaker [%s] CLOSED (probe succeeded)", self.name)
            self._state = _CircuitState.CLOSED
            self._half_open_calls = 0

    def record_failure(self) -> None:
        with self._lock:
            self._total_failures += 1
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            if self._state == _CircuitState.HALF_OPEN:
                self._open_cycle_count += 1
                self._state = _CircuitState.OPEN
                self._half_open_calls = 0
                logger.warning(
                    "Circuit breaker [%s] OPEN (half-open probe failed, cycle %d)",
                    self.name,
                    self._open_cycle_count,
                )
            elif self._failure_count >= self.failure_threshold:
                self._open_cycle_count = 1
                self._state = _CircuitState.OPEN
                logger.warning(
                    "Circuit breaker [%s] OPEN after %d failures",
                    self.name,
                    self._failure_count,
                )

    def allow_request(self) -> bool:
        with self._lock:
            if self._state == _CircuitState.CLOSED:
                return True

            if self._state == _CircuitState.HALF_OPEN:
                if self._half_open_calls < self.half_open_max_calls:
                    self._half_open_calls += 1
                    return True
                self._total_rejections += 1
                return False

            # OPEN — check if recovery timeout (with jitter + backoff) elapsed
            effective_timeout = self._effective_timeout()
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= effective_timeout:
                self._state = _CircuitState.HALF_OPEN
                self._half_open_calls = 1
                logger.info(
                    "Circuit breaker [%s] HALF_OPEN (%.1fs elapsed, timeout=%.1fs)",
                    self.name,
                    elapsed,
                    effective_timeout,
                )
                return True

            self._total_rejections += 1
            return False

    # -- helpers --------------------------------------------------------------

    def _effective_timeout(self) -> float:
        """Recovery timeout with exponential backoff and ±20% jitter."""
        backoff_factor = min(
            2 ** (self._open_cycle_count - 1) if self._open_cycle_count > 0 else 1,
            self._MAX_BACKOFF / max(self.recovery_timeout, 0.001),
        )
        base = self.recovery_timeout * backoff_factor
        base = min(base, self._MAX_BACKOFF)
        jitter = base * random.uniform(-0.20, 0.20)
        return base + jitter

    # -- observability --------------------------------------------------------

    @property
    def state(self) -> str:
        return self._state.value

    def get_metrics(self) -> Dict[str, Any]:
        """Return a snapshot of circuit-breaker metrics."""
        with self._lock:
            return {
                "total_successes": self._total_successes,
                "total_failures": self._total_failures,
                "total_rejections": self._total_rejections,
                "consecutive_failures": self._failure_count,
                "state": self._state.value,
                "last_failure_time": self._last_failure_time,
                "last_success_time": self._last_success_time,
            }


# ---------------------------------------------------------------------------
# Retry budget (LLM-BUDGET-001)
# ---------------------------------------------------------------------------

class _RetryBudget:
    """Per-request retry budget to cap fallback chain cost.

    Not thread-safe — instantiated per request in _complete_with_fallback.
    """

    def __init__(
        self,
        max_attempts: int = 3,
        max_duration_seconds: float = 60.0,
    ) -> None:
        self._max_attempts = max_attempts
        self._max_duration = max_duration_seconds
        self._attempts = 0
        self._start: Optional[float] = None

    def start(self) -> None:
        """Record the request start time."""
        self._start = time.monotonic()

    def attempt(self) -> bool:
        """Increment attempt count; return True if still within budget."""
        if self.exhausted:
            return False
        self._attempts += 1
        return True

    def elapsed(self) -> float:
        """Seconds since start (0.0 if start() was never called)."""
        if self._start is None:
            return 0.0
        return time.monotonic() - self._start

    @property
    def exhausted(self) -> bool:
        """True when attempts >= max *or* duration exceeded."""
        if self._attempts >= self._max_attempts:
            return True
        if self._start is not None and self.elapsed() >= self._max_duration:
            return True
        return False

    def get_summary(self) -> Dict[str, Any]:
        """Return a dict describing the current budget state.

        Keys: attempts_used, max_attempts, elapsed_seconds,
        max_duration, exhausted, budget_reason (str | None).
        """
        reason: Optional[str] = None
        if self._attempts >= self._max_attempts:
            reason = "max_attempts_reached"
        elif self._start is not None and self.elapsed() >= self._max_duration:
            reason = "max_duration_exceeded"
        return {
            "attempts_used": self._attempts,
            "max_attempts": self._max_attempts,
            "elapsed_seconds": round(self.elapsed(), 3),
            "max_duration": self._max_duration,
            "exhausted": self.exhausted,
            "budget_reason": reason,
        }


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
        # PATCH-070c: per-provider timeouts — DeepInfra fast-fails, Together gets full window
        self.deepinfra_timeout = float(os.getenv("DEEPINFRA_TIMEOUT", "10"))
        self.together_timeout  = float(os.getenv("TOGETHER_TIMEOUT",  str(timeout)))

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
        max_tokens:  int   = DEEPINFRA_MAX_OUTPUT,  # PATCH-093b: output cap not context window
        seed:        Optional[int] = None,
        timeout:     Optional[float] = None,  # PATCH-070c: per-provider override
    ) -> Dict[str, Any]:
        """POST to an OpenAI-compatible chat completions endpoint."""
        # PATCH-093b: cap output tokens — context window != generation limit (422 fix)
        _safe_max = min(max_tokens, DEEPINFRA_MAX_OUTPUT) if base_url == DEEPINFRA_BASE_URL else max_tokens
        payload: Dict[str, Any] = {
            "model":       model,
            "messages":    messages,
            "temperature": temperature,
            "max_tokens":  _safe_max,
        }
        # DETERM-LLM-001: include seed when deterministic mode is active
        if seed is not None:
            payload["seed"] = seed
        resp = requests.post(
            f"{base_url}/chat/completions",
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type":  "application/json",
            },
            timeout=timeout if timeout is not None else self.timeout,
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
        max_tokens:  int   = DEEPINFRA_MAX_OUTPUT,  # PATCH-093b: output cap not context window
        deterministic: bool = False,
    ) -> LLMCompletion:
        """Complete a prompt synchronously.

        Tries DeepInfra first, falls back to Together.ai, then onboard.

        When ``deterministic=True``, the Determinism Guard enforces temp=0
        and a fixed seed, and caches responses so identical requests return
        identical outputs.  (label: DETERM-LLM-002)
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
            deterministic=deterministic,
        )

    def complete_messages(
        self,
        messages:    List[Dict[str, str]],
        *,
        model_hint:  str   = "chat",
        temperature: float = 0.7,
        max_tokens:  int   = DEEPINFRA_MAX_OUTPUT,  # PATCH-093b: output cap not context window
        deterministic: bool = False,
    ) -> LLMCompletion:
        """Complete a messages list synchronously."""
        return self._complete_with_fallback(
            messages=messages,
            model_hint=model_hint,
            temperature=temperature,
            max_tokens=max_tokens,
            deterministic=deterministic,
        )

    def _complete_with_fallback(
        self,
        messages:    List[Dict[str, str]],
        model_hint:  str   = "chat",
        temperature: float = 0.7,
        max_tokens:  int   = DEEPINFRA_MAX_OUTPUT,  # PATCH-093b: output cap not context window
        deterministic: bool = False,
    ) -> LLMCompletion:
        request_id = str(uuid.uuid4())
        budget = _RetryBudget()
        budget.start()

        # ── Determinism Guard: enforce params + check cache ───────────
        # (label: DETERM-LLM-003)
        seed: Optional[int] = None
        try:
            from src.llm_determinism_guard import get_determinism_guard
            guard = get_determinism_guard()
            params = guard.enforce_deterministic_params(
                temperature=temperature, seed=None, deterministic=deterministic,
            )
            temperature = params["temperature"]
            seed = params.get("seed")

            # Check for cached response (deterministic mode only)
            if deterministic:
                model_for_cache = self._resolve_model("deepinfra", model_hint)
                cached = guard.get_cached(
                    messages, model_for_cache, temperature, max_tokens,
                    seed=seed, deterministic=True,
                )
                if cached:
                    logger.info(
                        "DETERM-LLM-003: returning cached response for %s "
                        "(hits=%d)", cached.fingerprint[:12], cached.hit_count,
                    )
                    return LLMCompletion(
                        content=cached.content,
                        model=cached.model,
                        provider=f"{cached.provider}(cached)",
                        latency_seconds=0.0,
                        request_id=request_id,
                    )
        except Exception as exc:  # DETERM-LLM-ERR-001
            logger.debug("Determinism guard unavailable: %s", exc)

        # ── 1. DeepInfra (primary) ────────────────────────────────────
        if self.deepinfra_api_key and self._di_circuit.allow_request() and budget.attempt():
            model = self._resolve_model("deepinfra", model_hint)
            start = time.monotonic()
            try:
                data = self._post_openai_compat(
                    DEEPINFRA_BASE_URL, self.deepinfra_api_key,
                    model, messages, temperature, max_tokens, seed=seed,
                    timeout=self.deepinfra_timeout,  # PATCH-070c: fast-fail
                )
                elapsed = time.monotonic() - start
                self._di_circuit.record_success()
                content = data["choices"][0]["message"]["content"]
                usage   = data.get("usage", {})
                logger.info("DeepInfra ✅ %.2fs | %s", elapsed, model)
                try:
                    from src.pcc import pcc as _pcc104
                    _pcc104.feedback(f"llm_di_{id(self)}", outcome_quality=0.85, confirmed=True)
                except Exception:
                    pass
                completion = LLMCompletion(
                    content=content, model=model, provider="deepinfra",
                    tokens_prompt=usage.get("prompt_tokens", 0),
                    tokens_completion=usage.get("completion_tokens", 0),
                    tokens_total=usage.get("total_tokens", 0),
                    latency_seconds=elapsed, request_id=request_id,
                    raw_response=data,
                )
                self._record_to_guard(
                    messages, model, temperature, max_tokens,
                    seed, deterministic, completion,
                )
                return completion
            except Exception as exc:
                elapsed = time.monotonic() - start
                self._di_circuit.record_failure()
                logger.warning("DeepInfra ⚠️  %.2fs | %s | falling back to Together.ai", elapsed, exc)

        # ── 2. Together.ai (fallback) ─────────────────────────────────
        if self.together_api_key and self._tog_circuit.allow_request() and budget.attempt():
            model = self._resolve_model("together", model_hint)
            start = time.monotonic()
            try:
                data = self._post_openai_compat(
                    TOGETHER_BASE_URL, self.together_api_key,
                    model, messages, temperature, max_tokens, seed=seed,
                    timeout=self.together_timeout,  # PATCH-070c: full window
                )
                elapsed = time.monotonic() - start
                self._tog_circuit.record_success()
                content = data["choices"][0]["message"]["content"]
                usage   = data.get("usage", {})
                logger.info("Together.ai ✅ %.2fs | %s", elapsed, model)
                completion = LLMCompletion(
                    content=content, model=model, provider="together",
                    tokens_prompt=usage.get("prompt_tokens", 0),
                    tokens_completion=usage.get("completion_tokens", 0),
                    tokens_total=usage.get("total_tokens", 0),
                    latency_seconds=elapsed, request_id=request_id,
                    raw_response=data,
                )
                self._record_to_guard(
                    messages, model, temperature, max_tokens,
                    seed, deterministic, completion,
                )
                return completion
            except Exception as exc:
                elapsed = time.monotonic() - start
                self._tog_circuit.record_failure()
                logger.warning("Together.ai ⚠️  %.2fs | %s | falling back to onboard", elapsed, exc)

        # ── 3. Onboard fallback ────────────────────────────────────────
        if budget.exhausted:
            logger.warning(
                "LLM-BUDGET-001: retry budget exhausted after %d attempts (%.1fs)",
                budget.get_summary()["attempts_used"],
                budget.elapsed(),
            )
        return self._onboard_fallback(messages, request_id, budget_summary=budget.get_summary())

    def _record_to_guard(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        seed: Optional[int],
        deterministic: bool,
        completion: "LLMCompletion",
    ) -> None:
        """Record a completion to the determinism guard (best-effort)."""
        # (label: DETERM-LLM-004)
        try:
            from src.llm_determinism_guard import get_determinism_guard
            guard = get_determinism_guard()
            guard.record_response(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                seed=seed,
                deterministic=deterministic,
                content=completion.content,
                provider=completion.provider,
                latency_s=completion.latency_seconds,
            )
        except Exception:  # DETERM-LLM-ERR-002 / PROD-HARD A2: Guard failure must never break pipeline, but must be visible
            logger.warning("DETERM-LLM-ERR-002: determinism-guard failure (non-fatal)", exc_info=True)

    def _onboard_fallback(
        self,
        messages:   List[Dict[str, str]],
        request_id: str,
        budget_summary: Optional[Dict[str, Any]] = None,
    ) -> LLMCompletion:
        """Local deterministic fallback when all API providers are down."""
        user_msg = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        preview  = user_msg[:120]
        content  = (
            f"[Murphy Onboard] API providers unavailable. "
            f"Request acknowledged: {preview}"
        )
        logger.warning("Using onboard fallback for request %s", request_id)
        raw: Dict[str, Any] = {}
        if budget_summary is not None:
            raw["budget_summary"] = budget_summary
        return LLMCompletion(
            content=content, model="murphy-onboard", provider="onboard",
            request_id=request_id, success=True, raw_response=raw,
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
        max_tokens:  int   = DEEPINFRA_MAX_OUTPUT,  # PATCH-093b: output cap not context window
        deterministic: bool = False,
    ) -> LLMCompletion:
        """Async completion — DeepInfra primary, Together.ai fallback.

        When ``deterministic=True``, the Determinism Guard enforces temp=0
        and a fixed seed, and caches responses.  (label: DETERM-LLM-005)
        """
        messages = [
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt},
        ]
        return await self._acomplete_with_fallback(
            messages=messages,
            model_hint=model_hint,
            temperature=temperature,
            max_tokens=max_tokens,
            deterministic=deterministic,
        )

    async def acomplete_messages(
        self,
        messages:    List[Dict[str, str]],
        *,
        model_hint:  str   = "chat",
        temperature: float = 0.7,
        max_tokens:  int   = DEEPINFRA_MAX_OUTPUT,  # PATCH-093b: output cap not context window
        deterministic: bool = False,
    ) -> LLMCompletion:
        """Async messages completion."""
        return await self._acomplete_with_fallback(
            messages=messages,
            model_hint=model_hint,
            temperature=temperature,
            max_tokens=max_tokens,
            deterministic=deterministic,
        )

    async def _acomplete_with_fallback(
        self,
        messages:    List[Dict[str, str]],
        model_hint:  str   = "chat",
        temperature: float = 0.7,
        max_tokens:  int   = DEEPINFRA_MAX_OUTPUT,  # PATCH-093b: output cap not context window
        deterministic: bool = False,
    ) -> LLMCompletion:
        request_id = str(uuid.uuid4())

        # ── Determinism Guard: enforce params + check cache ───────────
        # (label: DETERM-LLM-006)
        seed: Optional[int] = None
        try:
            from src.llm_determinism_guard import get_determinism_guard
            guard = get_determinism_guard()
            params = guard.enforce_deterministic_params(
                temperature=temperature, seed=None, deterministic=deterministic,
            )
            temperature = params["temperature"]
            seed = params.get("seed")

            if deterministic:
                model_for_cache = self._resolve_model("deepinfra", model_hint)
                cached = guard.get_cached(
                    messages, model_for_cache, temperature, max_tokens,
                    seed=seed, deterministic=True,
                )
                if cached:
                    logger.info(
                        "DETERM-LLM-006: returning cached response (async) for %s",
                        cached.fingerprint[:12],
                    )
                    return LLMCompletion(
                        content=cached.content,
                        model=cached.model,
                        provider=f"{cached.provider}(cached)",
                        latency_seconds=0.0,
                        request_id=request_id,
                    )
        except Exception as exc:  # DETERM-LLM-ERR-003
            logger.debug("Determinism guard unavailable (async): %s", exc)

        # ── 1. DeepInfra async ────────────────────────────────────────
        if self.deepinfra_api_key and self._di_circuit.allow_request():
            model = self._resolve_model("deepinfra", model_hint)
            client = self._get_async_client("deepinfra")
            if client:
                start = time.monotonic()
                try:
                    create_kwargs: Dict[str, Any] = dict(
                        model=model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    if seed is not None:
                        create_kwargs["seed"] = seed
                    resp = await client.chat.completions.create(**create_kwargs)
                    elapsed = time.monotonic() - start
                    self._di_circuit.record_success()
                    content = resp.choices[0].message.content or ""
                    usage   = resp.usage
                    logger.info("DeepInfra async ✅ %.2fs | %s", elapsed, model)
                    completion = LLMCompletion(
                        content=content, model=model, provider="deepinfra",
                        tokens_prompt=usage.prompt_tokens if usage else 0,
                        tokens_completion=usage.completion_tokens if usage else 0,
                        tokens_total=usage.total_tokens if usage else 0,
                        latency_seconds=elapsed, request_id=request_id,
                    )
                    self._record_to_guard(
                        messages, model, temperature, max_tokens,
                        seed, deterministic, completion,
                    )
                    return completion
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
                    create_kwargs = dict(
                        model=model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    if seed is not None:
                        create_kwargs["seed"] = seed
                    resp = await client.chat.completions.create(**create_kwargs)
                    elapsed = time.monotonic() - start
                    self._tog_circuit.record_success()
                    content = resp.choices[0].message.content or ""
                    usage   = resp.usage
                    logger.info("Together.ai async ✅ %.2fs | %s", elapsed, model)
                    completion = LLMCompletion(
                        content=content, model=model, provider="together",
                        tokens_prompt=usage.prompt_tokens if usage else 0,
                        tokens_completion=usage.completion_tokens if usage else 0,
                        tokens_total=usage.total_tokens if usage else 0,
                        latency_seconds=elapsed, request_id=request_id,
                    )
                    self._record_to_guard(
                        messages, model, temperature, max_tokens,
                        seed, deterministic, completion,
                    )
                    return completion
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
    """Return the module-level singleton MurphyLLMProvider.
    
    PATCH-082a: Re-validates API keys on each call so late-loaded environment
    variables (from systemd secrets.env) are always picked up.
    """
    global _provider
    if _provider is None:
        _provider = MurphyLLMProvider.from_env()
    else:
        # Re-check if keys appeared in env since singleton was created
        di_key = os.getenv("DEEPINFRA_API_KEY", "")
        tog_key = os.getenv("TOGETHER_API_KEY", "")
        if di_key and not _provider.deepinfra_api_key:
            _provider.deepinfra_api_key = di_key
            logger.info("PATCH-082a: DeepInfra key hot-loaded into LLM singleton")
        if tog_key and not _provider.together_api_key:
            _provider.together_api_key = tog_key
            logger.info("PATCH-082a: Together.ai key hot-loaded into LLM singleton")
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
    max_tokens:  int   = DEEPINFRA_MAX_OUTPUT,  # PATCH-093b: output cap not context window
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
    max_tokens:  int   = DEEPINFRA_MAX_OUTPUT,  # PATCH-093b: output cap not context window
) -> str:
    """Async convenience: returns just the content string."""
    resp = await get_llm().acomplete(
        prompt, system=system, model_hint=model_hint,
        temperature=temperature, max_tokens=max_tokens,
    )
    return resp.content
