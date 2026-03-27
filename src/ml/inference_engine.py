"""
Inference Engine — routes prompts to the optimal provider with full fallback chain.

Priority chain (highest → lowest):
  1. Cache hit (instant)
  2. MFMInferenceService (local fine-tuned model)
  3. DeepInfra API (fast cloud)
  4. Ollama (local LLM daemon)
  5. Deterministic template engine (always available)
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .model_config import (
    DEFAULT_ROUTING_CONFIG,
    ModelConfig,
    ModelProvider,
    ProviderRoutingConfig,
    TaskComplexity,
    get_model_config,
)

logger = logging.getLogger(__name__)

_DEFAULT_CACHE_SIZE = 1000


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class InferenceRequest:
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    prompt: str = ""
    task_complexity: TaskComplexity = TaskComplexity.SIMPLE
    context: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class InferenceResult:
    request_id: str = ""
    response: str = ""
    provider_used: str = ""
    model_used: str = ""
    latency_ms: float = 0.0
    token_count: int = 0
    cost_estimate: float = 0.0
    cached: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "response": self.response,
            "provider_used": self.provider_used,
            "model_used": self.model_used,
            "latency_ms": self.latency_ms,
            "token_count": self.token_count,
            "cost_estimate": self.cost_estimate,
            "cached": self.cached,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class InferenceEngine:
    """
    Unified inference gateway with routing, caching, and cascading fallbacks.

    Thread-safe; the internal LRU cache is bounded by *cache_size*.
    """

    def __init__(
        self,
        config: Optional[ProviderRoutingConfig] = None,
        cache_size: int = _DEFAULT_CACHE_SIZE,
    ) -> None:
        self._config = config or DEFAULT_ROUTING_CONFIG
        self._cache_size = cache_size
        self._lock = threading.Lock()
        self._cache: OrderedDict[str, InferenceResult] = OrderedDict()

        # Metrics accumulators.
        self._total_requests: int = 0
        self._cache_hits: int = 0
        self._provider_usage: Dict[str, int] = {}
        self._latency_sum: float = 0.0

        # Optional backing services (lazily initialised).
        self._mfm_service: Optional[Any] = None
        self._ollama_llm: Optional[Any] = None

        self._init_backing_services()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def infer(
        self,
        prompt: str,
        task_complexity: Optional[TaskComplexity] = None,
        context: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> InferenceResult:
        """Route *prompt* to the optimal provider and return an :class:`InferenceResult`."""
        complexity = task_complexity or self._estimate_complexity(prompt)
        request = InferenceRequest(
            prompt=prompt,
            task_complexity=complexity,
            context=context,
            metadata=metadata,
        )

        with self._lock:
            self._total_requests += 1

        # 1. Cache lookup.
        cached = self._get_cached_result(prompt)
        if cached is not None:
            with self._lock:
                self._cache_hits += 1
            return cached

        # 2. Route through provider chain.
        result = self._route_request(request)

        # 3. Cache and return.
        self._cache_result(prompt, result)
        return result

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def _route_request(self, request: InferenceRequest) -> InferenceResult:
        """Try each provider in the chain; return first successful result."""
        chain = self._config.chain_for(request.task_complexity)
        last_exc: Optional[Exception] = None

        for provider in chain:
            try:
                result = self._call_provider(provider, request)
                self._record_provider_use(result.provider_used)
                return result
            except Exception as exc:
                last_exc = exc
                logger.debug("Provider %s failed: %s — trying next in chain", provider.value, exc)

        # All providers failed — use deterministic fallback (never raises).
        logger.warning("All providers failed (%s); using deterministic fallback", last_exc)
        result = self._call_deterministic(request)
        self._record_provider_use(result.provider_used)
        return result

    def _call_provider(self, provider: ModelProvider, request: InferenceRequest) -> InferenceResult:
        dispatch = {
            ModelProvider.MFM: self._call_mfm,
            ModelProvider.OLLAMA: self._call_ollama,
            ModelProvider.DEEPINFRA: self._call_deepinfra,
            ModelProvider.OPENAI: self._call_openai,
            ModelProvider.COPILOT: self._call_copilot,
            ModelProvider.LOCAL: self._call_deterministic,
        }
        fn = dispatch.get(provider)
        if fn is None:
            raise ValueError(f"No handler for provider {provider}")
        return fn(request)

    # ------------------------------------------------------------------
    # Provider implementations
    # ------------------------------------------------------------------

    def _call_mfm(self, request: InferenceRequest) -> InferenceResult:
        if self._mfm_service is None:
            raise RuntimeError("MFMInferenceService not available")
        t0 = time.monotonic()
        raw = self._mfm_service.infer(request.prompt)  # type: ignore[attr-defined]
        latency = (time.monotonic() - t0) * 1000
        response = raw if isinstance(raw, str) else str(raw)
        cfg = get_model_config(ModelProvider.MFM, request.task_complexity)
        return self._make_result(request.request_id, response, ModelProvider.MFM, cfg, latency)

    def _call_deepinfra(self, request: InferenceRequest) -> InferenceResult:
        # Lazy import — graceful fallback if deepinfra package absent.
        try:
            from src.llm_provider import get_llm  # DeepInfra via MurphyLLMProvider  # type: ignore
        except ImportError:
            raise RuntimeError("deepinfra package not installed")

        import os
        api_key = os.environ.get("DEEPINFRA_API_KEY", "")
        if not api_key:
            raise RuntimeError("DEEPINFRA_API_KEY not set")

        cfg = get_model_config(ModelProvider.DEEPINFRA, request.task_complexity)
        client = _# deepinfra replaced — use get_llm()(api_key=api_key)
        t0 = time.monotonic()
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": request.prompt}],
            model=cfg.model_name,
            max_tokens=cfg.max_tokens,
            temperature=cfg.temperature,
        )
        latency = (time.monotonic() - t0) * 1000
        response = chat_completion.choices[0].message.content or ""
        token_count = getattr(chat_completion.usage, "total_tokens", len(response.split()))
        return self._make_result(
            request.request_id, response, ModelProvider.DEEPINFRA, cfg, latency,
            token_count=token_count,
        )

    def _call_ollama(self, request: InferenceRequest) -> InferenceResult:
        if self._ollama_llm is None:
            raise RuntimeError("OllamaLLM not available")
        cfg = get_model_config(ModelProvider.OLLAMA, request.task_complexity)
        t0 = time.monotonic()
        response = self._ollama_llm.generate(  # type: ignore[attr-defined]
            request.prompt,
            max_tokens=cfg.max_tokens,
            temperature=cfg.temperature,
        )
        latency = (time.monotonic() - t0) * 1000
        return self._make_result(request.request_id, response, ModelProvider.OLLAMA, cfg, latency)

    def _call_openai(self, request: InferenceRequest) -> InferenceResult:
        try:
            import openai as _openai  # type: ignore
        except ImportError:
            raise RuntimeError("openai package not installed")

        import os
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set")

        cfg = get_model_config(ModelProvider.OPENAI, request.task_complexity)
        client = _openai.OpenAI(api_key=api_key)
        t0 = time.monotonic()
        completion = client.chat.completions.create(
            model=cfg.model_name,
            messages=[{"role": "user", "content": request.prompt}],
            max_tokens=cfg.max_tokens,
            temperature=cfg.temperature,
        )
        latency = (time.monotonic() - t0) * 1000
        response = completion.choices[0].message.content or ""
        token_count = getattr(completion.usage, "total_tokens", len(response.split()))
        return self._make_result(
            request.request_id, response, ModelProvider.OPENAI, cfg, latency,
            token_count=token_count,
        )

    def _call_copilot(self, request: InferenceRequest) -> InferenceResult:
        """Delegate to CopilotAdapter (code-aware routing)."""
        try:
            from .copilot_adapter import CopilotAdapter, CopilotRequest, CopilotTaskType  # type: ignore
            adapter = CopilotAdapter()
            cop_req = CopilotRequest(
                prompt=request.prompt,
                task_type=CopilotTaskType.CODE_GENERATION,
            )
            result = adapter.generate(cop_req)
            cfg = get_model_config(ModelProvider.COPILOT, request.task_complexity)
            return self._make_result(
                request.request_id,
                result.generated_code or result.explanation,
                ModelProvider.COPILOT,
                cfg,
                0.0,
            )
        except Exception as exc:
            raise RuntimeError(f"CopilotAdapter failed: {exc}") from exc

    def _call_deterministic(self, request: InferenceRequest) -> InferenceResult:
        """Pure template-based fallback — always succeeds, zero external dependencies."""
        templates = {
            TaskComplexity.SIMPLE: (
                f"[deterministic] Processed request: {request.prompt[:80]}…"
                if len(request.prompt) > 80 else f"[deterministic] Processed: {request.prompt}"
            ),
            TaskComplexity.MODERATE: (
                "[deterministic] Task acknowledged. Analysing context and generating structured response."
            ),
            TaskComplexity.COMPLEX: (
                "[deterministic] Complex task received. Decomposing into sub-tasks for structured execution."
            ),
            TaskComplexity.CRITICAL: (
                "[deterministic] CRITICAL task received. Escalating to human review — please check queue."
            ),
        }
        response = templates.get(request.task_complexity, templates[TaskComplexity.SIMPLE])
        cfg = get_model_config(ModelProvider.LOCAL)
        return self._make_result(request.request_id, response, ModelProvider.LOCAL, cfg, 0.1)

    # ------------------------------------------------------------------
    # Cache
    # ------------------------------------------------------------------

    def _cache_key(self, prompt: str) -> str:
        return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:32]

    def _get_cached_result(self, prompt: str) -> Optional[InferenceResult]:
        key = self._cache_key(prompt)
        with self._lock:
            if key in self._cache:
                # Move to end (LRU refresh).
                self._cache.move_to_end(key)
                result = self._cache[key]
                # Return a copy marked as cached.
                import dataclasses
                return dataclasses.replace(result, cached=True)
        return None

    def _cache_result(self, prompt: str, result: InferenceResult) -> None:
        key = self._cache_key(prompt)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = result
            if len(self._cache) > self._cache_size:
                self._cache.popitem(last=False)  # evict oldest

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> Dict[str, Any]:
        with self._lock:
            total = self._total_requests
            hits = self._cache_hits
            avg_latency = self._latency_sum / max(total - hits, 1)
            return {
                "total_requests": total,
                "cache_hits": hits,
                "cache_hit_rate": round(hits / max(total, 1), 4),
                "avg_latency_ms": round(avg_latency, 2),
                "provider_usage": dict(self._provider_usage),
                "cache_size": len(self._cache),
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _init_backing_services(self) -> None:
        try:
            from src.murphy_foundation_model.mfm_inference import MFMInferenceService  # type: ignore
            self._mfm_service = MFMInferenceService()
        except Exception:
            try:
                from murphy_foundation_model.mfm_inference import MFMInferenceService  # type: ignore
                self._mfm_service = MFMInferenceService()
            except Exception:
                logger.debug("MFMInferenceService unavailable")

        try:
            from src.llm_integration import OllamaLLM  # type: ignore
            self._ollama_llm = OllamaLLM()
        except Exception:
            try:
                from llm_integration import OllamaLLM  # type: ignore
                self._ollama_llm = OllamaLLM()
            except Exception:
                logger.debug("OllamaLLM unavailable")

    def _estimate_complexity(self, prompt: str) -> TaskComplexity:
        """Heuristic complexity estimation based on prompt token count."""
        word_count = len(prompt.split())
        if word_count > 150:
            return TaskComplexity.COMPLEX
        if word_count > 50:
            return TaskComplexity.MODERATE
        return TaskComplexity.SIMPLE

    def _make_result(
        self,
        request_id: str,
        response: str,
        provider: ModelProvider,
        cfg: ModelConfig,
        latency_ms: float,
        token_count: Optional[int] = None,
    ) -> InferenceResult:
        tokens = token_count if token_count is not None else len(response.split())
        cost = tokens * cfg.cost_per_token
        with self._lock:
            self._latency_sum += latency_ms
        return InferenceResult(
            request_id=request_id,
            response=response,
            provider_used=provider.value,
            model_used=cfg.model_name,
            latency_ms=round(latency_ms, 2),
            token_count=tokens,
            cost_estimate=round(cost, 8),
            cached=False,
        )

    def _record_provider_use(self, provider_name: str) -> None:
        with self._lock:
            self._provider_usage[provider_name] = self._provider_usage.get(provider_name, 0) + 1
