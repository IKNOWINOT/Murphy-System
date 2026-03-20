"""
OpenAI-Compatible LLM Provider for Murphy System.

Provides a unified interface to any OpenAI-compatible API endpoint,
including OpenAI, Azure OpenAI, Groq, Ollama, vLLM, LiteLLM, and
other compatible providers. Uses the ``openai`` Python SDK as the
single client for all providers.

When **no API keys** are configured, the provider automatically falls
back to Murphy's **onboard LLM** (``EnhancedLocalLLM``), which works
entirely offline with zero external dependencies.  This means Murphy
always has a working LLM — no API key required for local development.

Architecture decision (INC-01 / C-01):
    The ``openai`` Python package is the industry-standard SDK that speaks
    the OpenAI chat-completions wire format.  Every major LLM host now
    exposes an OpenAI-compatible endpoint, so a single client covers
    OpenAI, Azure, Groq, Ollama, vLLM, LiteLLM, and more.

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
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

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration dataclasses
# ---------------------------------------------------------------------------


class ProviderType(Enum):
    """Supported OpenAI-compatible provider backends."""

    OPENAI = "openai"
    AZURE = "azure"
    GROQ = "groq"
    OLLAMA = "ollama"
    VLLM = "vllm"
    LITELLM = "litellm"
    CUSTOM = "custom"
    ONBOARD = "onboard"


@dataclass
class ProviderConfig:
    """Configuration for a single provider endpoint.

    All tunables are sourced from environment variables with sensible
    defaults so the system works out-of-the-box in development.

    Attributes:
        provider_type: Which backend flavour to use.
        api_key: Bearer token / API key (from env).
        base_url: Override the SDK base URL for non-OpenAI hosts.
        default_model: Model identifier to use when the caller does not
            specify one explicitly.
        max_retries: Number of retries the SDK should attempt.
        timeout_seconds: Per-request timeout.
        temperature: Default sampling temperature.
        max_tokens: Default maximum tokens for completions.
    """

    provider_type: ProviderType = ProviderType.OPENAI
    api_key: str = ""
    base_url: Optional[str] = None
    default_model: str = "gpt-3.5-turbo"
    max_retries: int = 2
    timeout_seconds: float = 30.0
    temperature: float = 0.7
    max_tokens: int = 2048


@dataclass
class ChatMessage:
    """A single chat message in the OpenAI format."""

    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class CompletionResponse:
    """Normalised response from any OpenAI-compatible endpoint.

    Attributes:
        content: The assistant reply text.
        model: Model identifier actually used.
        provider: Which backend served the response.
        tokens_prompt: Prompt token count (if reported).
        tokens_completion: Completion token count (if reported).
        tokens_total: Total token count (if reported).
        latency_seconds: Wall-clock time for the API call.
        request_id: Correlation ID for observability.
        raw_response: The raw API response dict (for debugging).
    """

    content: str
    model: str
    provider: str
    tokens_prompt: int = 0
    tokens_completion: int = 0
    tokens_total: int = 0
    latency_seconds: float = 0.0
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    raw_response: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Circuit-breaker (lightweight, inline)
# ---------------------------------------------------------------------------


class _CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class _CircuitBreaker:
    """Minimal circuit-breaker for external API calls.

    Opens after ``failure_threshold`` consecutive failures, stays open
    for ``recovery_timeout`` seconds, then allows a single probe.
    """

    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    _state: _CircuitState = _CircuitState.CLOSED
    _failure_count: int = 0
    _last_failure_time: float = 0.0

    def record_success(self) -> None:
        self._failure_count = 0
        self._state = _CircuitState.CLOSED

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self.failure_threshold:
            self._state = _CircuitState.OPEN
            logger.warning(
                "Circuit breaker OPEN after %d failures",
                self._failure_count,
                extra={"failure_count": self._failure_count},
            )

    def allow_request(self) -> bool:
        if self._state == _CircuitState.CLOSED:
            return True
        elapsed = time.monotonic() - self._last_failure_time
        if elapsed >= self.recovery_timeout:
            self._state = _CircuitState.HALF_OPEN
            return True
        return False


# ---------------------------------------------------------------------------
# Main provider class
# ---------------------------------------------------------------------------


class OpenAICompatibleProvider:
    """Unified LLM provider using the OpenAI chat-completions format.

    Works with any backend that implements the OpenAI API contract.
    The ``openai`` Python package is lazily imported so that the module
    can be loaded even when the package is not installed (graceful
    degradation).

    Usage::

        provider = OpenAICompatibleProvider.from_env()
        response = await provider.chat_completion([
            ChatMessage(role="system", content="You are Murphy."),
            ChatMessage(role="user", content="Hello!"),
        ])
        print(response.content)
    """

    def __init__(self, config: ProviderConfig) -> None:
        self._config = config
        self._circuit = _CircuitBreaker()
        self._client: Any = None  # lazily created
        self._async_client: Any = None  # lazily created
        self._onboard_llm: Any = None  # lazily created onboard LLM
        self._available = True

        # Onboard provider is always available — no API key needed
        if config.provider_type == ProviderType.ONBOARD:
            logger.info(
                "Using onboard LLM — no API key required",
                extra={"provider": "onboard"},
            )
            return

        # Validate API key presence for cloud providers
        cloud_providers = {
            ProviderType.OPENAI,
            ProviderType.AZURE,
            ProviderType.GROQ,
        }
        if config.provider_type in cloud_providers and not config.api_key:
            logger.info(
                "No API key configured for %s — provider disabled",
                config.provider_type.value,
                extra={"provider": config.provider_type.value},
            )
            self._available = False

    # ------------------------------------------------------------------
    # Factory helpers
    # ------------------------------------------------------------------

    @classmethod
    def from_env(cls) -> "OpenAICompatibleProvider":
        """Build a provider from environment variables.

        Environment variables (all optional, sensible defaults):
            OPENAI_API_KEY          — API key
            OPENAI_BASE_URL         — Base URL override
            OPENAI_DEFAULT_MODEL    — Model name (default gpt-3.5-turbo)
            OPENAI_PROVIDER_TYPE    — One of openai/groq/ollama/onboard/…
            OPENAI_MAX_RETRIES      — SDK retry count
            OPENAI_TIMEOUT          — Per-request timeout in seconds
            OPENAI_TEMPERATURE      — Default temperature
            OPENAI_MAX_TOKENS       — Default max tokens

        For Groq-specific usage, ``GROQ_API_KEY`` is also accepted and
        takes precedence when the provider type is ``groq``.

        **Default behaviour (no API keys):** When neither ``OPENAI_API_KEY``
        nor ``GROQ_API_KEY`` is set and no explicit provider type is
        configured, the provider automatically selects the **onboard LLM**
        (``EnhancedLocalLLM``) so Murphy works out-of-the-box with zero
        external dependencies.
        """
        provider_type_str = os.getenv("OPENAI_PROVIDER_TYPE", "").lower()

        # Resolve API key — honour provider-specific env vars
        api_key = os.getenv("OPENAI_API_KEY", "")
        groq_key = os.getenv("GROQ_API_KEY", "")

        # Auto-detect provider type when not explicitly set
        if not provider_type_str:
            if api_key:
                provider_type_str = "openai"
            elif groq_key:
                provider_type_str = "groq"
                api_key = groq_key
            else:
                # No API keys at all → use the onboard LLM
                provider_type_str = "onboard"

        try:
            provider_type = ProviderType(provider_type_str)
        except ValueError:
            provider_type = ProviderType.CUSTOM

        if provider_type == ProviderType.GROQ:
            api_key = groq_key or api_key

        # Resolve base URL — provider-specific defaults
        base_url = os.getenv("OPENAI_BASE_URL")
        if base_url is None and provider_type == ProviderType.GROQ:
            base_url = "https://api.groq.com/openai/v1"
        elif base_url is None and provider_type == ProviderType.OLLAMA:
            _ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
            base_url = f"{_ollama_host}/v1"

        default_model = os.getenv("OPENAI_DEFAULT_MODEL", "gpt-3.5-turbo")
        if provider_type == ProviderType.GROQ and default_model == "gpt-3.5-turbo":
            default_model = "mixtral-8x7b-32768"
        elif provider_type == ProviderType.OLLAMA and default_model == "gpt-3.5-turbo":
            default_model = os.getenv("OLLAMA_MODEL", "llama3")
        elif provider_type == ProviderType.ONBOARD:
            default_model = "murphy-onboard"

        config = ProviderConfig(
            provider_type=provider_type,
            api_key=api_key,
            base_url=base_url,
            default_model=default_model,
            max_retries=int(os.getenv("OPENAI_MAX_RETRIES", "2")),
            timeout_seconds=float(os.getenv("OPENAI_TIMEOUT", "30")),
            temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.7")),
            max_tokens=int(os.getenv("OPENAI_MAX_TOKENS", "2048")),
        )
        return cls(config)

    # ------------------------------------------------------------------
    # SDK client creation (lazy)
    # ------------------------------------------------------------------

    def _get_sync_client(self) -> Any:
        """Lazily create the synchronous OpenAI client."""
        if self._client is None:
            try:
                import openai  # noqa: F811 — lazy import

                kwargs: Dict[str, Any] = {
                    "api_key": self._config.api_key or "dummy-key",
                    "max_retries": self._config.max_retries,
                    "timeout": self._config.timeout_seconds,
                }
                if self._config.base_url:
                    kwargs["base_url"] = self._config.base_url
                self._client = openai.OpenAI(**kwargs)
            except ImportError:
                logger.warning(
                    "openai package not installed — using fallback mode",
                    extra={"provider": self._config.provider_type.value},
                )
                self._client = None
                self._available = False
        return self._client

    def _get_async_client(self) -> Any:
        """Lazily create the asynchronous OpenAI client."""
        if self._async_client is None:
            try:
                import openai  # noqa: F811

                kwargs: Dict[str, Any] = {
                    "api_key": self._config.api_key or "dummy-key",
                    "max_retries": self._config.max_retries,
                    "timeout": self._config.timeout_seconds,
                }
                if self._config.base_url:
                    kwargs["base_url"] = self._config.base_url
                self._async_client = openai.AsyncOpenAI(**kwargs)
            except ImportError:
                logger.warning(
                    "openai package not installed — using async fallback mode",
                    extra={"provider": self._config.provider_type.value},
                )
                self._async_client = None
                self._available = False
        return self._async_client

    def _get_onboard_llm(self) -> Any:
        """Lazily create the onboard EnhancedLocalLLM instance.

        The onboard LLM works entirely offline — no API keys, no network
        calls.  It is the default when no cloud provider is configured.
        """
        if self._onboard_llm is None:
            try:
                from enhanced_local_llm import EnhancedLocalLLM
                self._onboard_llm = EnhancedLocalLLM()
                logger.info(
                    "Onboard LLM initialized (EnhancedLocalLLM)",
                    extra={"provider": "onboard"},
                )
            except ImportError:
                try:
                    from src.enhanced_local_llm import EnhancedLocalLLM
                    self._onboard_llm = EnhancedLocalLLM()
                    logger.info(
                        "Onboard LLM initialized (src.EnhancedLocalLLM)",
                        extra={"provider": "onboard"},
                    )
                except ImportError:
                    logger.warning(
                        "EnhancedLocalLLM not available — onboard mode degraded",
                        extra={"provider": "onboard"},
                    )
                    self._onboard_llm = None
        return self._onboard_llm

    async def _query_onboard(
        self,
        messages: List[ChatMessage],
        request_id: str,
        temperature: Optional[float] = None,
    ) -> CompletionResponse:
        """Route a request through the onboard EnhancedLocalLLM.

        Extracts the last user message and feeds it to the onboard LLM,
        returning the result in the standard ``CompletionResponse`` format.

        Args:
            messages: Conversation messages.
            request_id: Correlation ID.
            temperature: Sampling temperature.

        Returns:
            A ``CompletionResponse`` from the onboard LLM.
        """
        onboard = self._get_onboard_llm()

        # Extract user prompt (last user message)
        user_prompt = ""
        system_context = ""
        for m in messages:
            if m.role == "user":
                user_prompt = m.content
            elif m.role == "system":
                system_context = m.content

        if system_context and user_prompt:
            full_prompt = f"{system_context}\n\n{user_prompt}"
        else:
            full_prompt = user_prompt or system_context or ""

        if onboard is None:
            # Degraded fallback when EnhancedLocalLLM isn't importable
            return self._fallback_response(messages, request_id)

        start = time.monotonic()
        try:
            resolved_temp = temperature if temperature is not None else self._config.temperature
            result = onboard.query(
                prompt=full_prompt,
                provider="aristotle",
                temperature=resolved_temp,
            )
            elapsed = time.monotonic() - start

            content = result.get("response", "")
            tokens_used = result.get("tokens_used", len(content.split()))
            confidence = result.get("confidence", 0.0)

            logger.info(
                "Onboard LLM query succeeded",
                extra={
                    "request_id": request_id,
                    "provider": "onboard",
                    "tokens": tokens_used,
                    "confidence": confidence,
                    "latency": round(elapsed, 3),
                },
            )

            return CompletionResponse(
                content=content,
                model="murphy-onboard",
                provider="onboard",
                tokens_prompt=len(full_prompt.split()),
                tokens_completion=len(content.split()),
                tokens_total=tokens_used,
                latency_seconds=elapsed,
                request_id=request_id,
                raw_response=result.get("metadata", {}),
            )

        except Exception as exc:
            elapsed = time.monotonic() - start
            logger.error(
                "Onboard LLM query failed: %s",
                exc,
                extra={
                    "request_id": request_id,
                    "provider": "onboard",
                    "latency": round(elapsed, 3),
                    "error": str(exc),
                },
            )
            return self._fallback_response(messages, request_id)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        """Whether this provider is configured and ready to serve."""
        return self._available

    @property
    def provider_type(self) -> ProviderType:
        """The provider backend type."""
        return self._config.provider_type

    @property
    def default_model(self) -> str:
        """Default model identifier."""
        return self._config.default_model

    async def chat_completion(
        self,
        messages: List[ChatMessage],
        *,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> CompletionResponse:
        """Send a chat-completion request (async).

        Args:
            messages: Conversation messages.
            model: Model override (uses config default if *None*).
            temperature: Sampling temperature override.
            max_tokens: Max tokens override.

        Returns:
            A ``CompletionResponse`` with the assistant reply.

        Raises:
            RuntimeError: If the circuit breaker is open or the provider
                is not available.
        """
        request_id = str(uuid.uuid4())

        # Onboard LLM — always available, no API key needed
        if self._config.provider_type == ProviderType.ONBOARD:
            return await self._query_onboard(messages, request_id, temperature)

        if not self._available:
            logger.info(
                "Provider not available, routing to onboard LLM",
                extra={"request_id": request_id, "provider": self._config.provider_type.value},
            )
            return await self._query_onboard(messages, request_id, temperature)

        if not self._circuit.allow_request():
            logger.warning(
                "Circuit breaker open — routing to onboard LLM",
                extra={"request_id": request_id},
            )
            return await self._query_onboard(messages, request_id, temperature)

        resolved_model = model or self._config.default_model
        resolved_temp = temperature if temperature is not None else self._config.temperature
        resolved_max = max_tokens if max_tokens is not None else self._config.max_tokens

        api_messages = [{"role": m.role, "content": m.content} for m in messages]

        start = time.monotonic()
        try:
            client = self._get_async_client()
            if client is None:
                return await self._query_onboard(messages, request_id, temperature)

            response = await client.chat.completions.create(
                model=resolved_model,
                messages=api_messages,
                temperature=resolved_temp,
                max_tokens=resolved_max,
            )
            elapsed = time.monotonic() - start
            self._circuit.record_success()

            content = response.choices[0].message.content or ""
            usage = response.usage
            tokens_prompt = usage.prompt_tokens if usage else 0
            tokens_completion = usage.completion_tokens if usage else 0
            tokens_total = usage.total_tokens if usage else 0

            logger.info(
                "Chat completion succeeded",
                extra={
                    "request_id": request_id,
                    "provider": self._config.provider_type.value,
                    "model": resolved_model,
                    "tokens_total": tokens_total,
                    "latency": round(elapsed, 3),
                },
            )

            return CompletionResponse(
                content=content,
                model=resolved_model,
                provider=self._config.provider_type.value,
                tokens_prompt=tokens_prompt,
                tokens_completion=tokens_completion,
                tokens_total=tokens_total,
                latency_seconds=elapsed,
                request_id=request_id,
            )

        except Exception as exc:
            elapsed = time.monotonic() - start
            self._circuit.record_failure()
            logger.error(
                "Chat completion failed, falling back to onboard LLM: %s",
                exc,
                extra={
                    "request_id": request_id,
                    "provider": self._config.provider_type.value,
                    "model": resolved_model,
                    "latency": round(elapsed, 3),
                    "error": str(exc),
                },
            )
            return await self._query_onboard(messages, request_id, temperature)

    def chat_completion_sync(
        self,
        messages: List[ChatMessage],
        *,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> CompletionResponse:
        """Synchronous wrapper around :meth:`chat_completion`.

        Useful in non-async contexts (CLI tools, scripts).
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Already inside an event loop — create a new thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
                    asyncio.run,
                    self.chat_completion(
                        messages,
                        model=model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    ),
                )
                return future.result(timeout=self._config.timeout_seconds + 5)
        else:
            return asyncio.run(
                self.chat_completion(
                    messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            )

    def reconfigure(self, api_key: str, base_url: Optional[str] = None) -> None:
        """Hot-reload the provider with a new API key.

        Resets the internal clients so the next request picks up the
        new credentials.

        Args:
            api_key: New API key / bearer token.
            base_url: Optional new base URL.
        """
        self._config.api_key = api_key
        if base_url is not None:
            self._config.base_url = base_url
        self._client = None
        self._async_client = None
        self._available = bool(api_key)
        self._circuit = _CircuitBreaker()
        logger.info(
            "Provider reconfigured",
            extra={
                "provider": self._config.provider_type.value,
                "available": self._available,
            },
        )

    def get_status(self) -> Dict[str, Any]:
        """Return provider health / configuration summary."""
        is_onboard = self._config.provider_type == ProviderType.ONBOARD
        return {
            "provider_type": self._config.provider_type.value,
            "available": self._available,
            "default_model": self._config.default_model,
            "base_url": self._config.base_url or ("(local)" if is_onboard else "(default)"),
            "circuit_state": self._circuit._state.value,
            "has_api_key": bool(self._config.api_key),
            "onboard_active": is_onboard or not self._available,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fallback_response(
        self,
        messages: List[ChatMessage],
        request_id: str,
    ) -> CompletionResponse:
        """Generate an offline / degraded response."""
        user_msg = ""
        for m in reversed(messages):
            if m.role == "user":
                user_msg = m.content
                break

        preview = user_msg[:120] if user_msg else "(no prompt)"
        content = (
            f"[Murphy Fallback] Provider '{self._config.provider_type.value}' "
            f"is unavailable. Your request: {preview}"
        )
        return CompletionResponse(
            content=content,
            model="fallback",
            provider="fallback",
            request_id=request_id,
        )
