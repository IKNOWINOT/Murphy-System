# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Copilot Tenant — LLM Routing with Local-First Fallback

Routes LLM requests through local Ollama first and falls back to cloud
providers (DeepInfra, OpenAI) when needed.  Wraps:
  - src/llm_controller.py
  - src/llm_integration_layer.py
  - src/local_llm_fallback.py
  - src/enhanced_local_llm.py
  - src/local_inference_engine.py
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency imports
# ---------------------------------------------------------------------------

try:
    from llm_controller import LLMController
    _LLM_CONTROLLER_AVAILABLE = True
except Exception:  # pragma: no cover
    LLMController = None  # type: ignore[assignment,misc]
    _LLM_CONTROLLER_AVAILABLE = False

try:
    from llm_integration_layer import LLMIntegrationLayer
    _INTEGRATION_LAYER_AVAILABLE = True
except Exception:  # pragma: no cover
    LLMIntegrationLayer = None  # type: ignore[assignment,misc]
    _INTEGRATION_LAYER_AVAILABLE = False

try:
    from local_llm_fallback import LocalLLMFallback
    _LOCAL_FALLBACK_AVAILABLE = True
except Exception:  # pragma: no cover
    LocalLLMFallback = None  # type: ignore[assignment,misc]
    _LOCAL_FALLBACK_AVAILABLE = False


class TenantLLMRouter:
    """Routes LLM requests with local-first fallback strategy.

    Strategy:
        1. Try local Ollama (via LocalLLMFallback / EnhancedLocalLLM)
        2. Fall back to DeepInfra/cloud via LLMController / LLMIntegrationLayer
        3. Return a synthetic stub response if all providers are unreachable
    """

    def __init__(self) -> None:
        self._local: Any = None
        self._cloud: Any = None
        self._layer: Any = None
        self._initialize()

    def _initialize(self) -> None:
        if _LOCAL_FALLBACK_AVAILABLE:
            try:
                self._local = LocalLLMFallback()
            except Exception as exc:
                logger.debug("LocalLLMFallback init failed: %s", exc)
        if _LLM_CONTROLLER_AVAILABLE:
            try:
                self._cloud = LLMController()
            except Exception as exc:
                logger.debug("LLMController init failed: %s", exc)
        if _INTEGRATION_LAYER_AVAILABLE:
            try:
                self._layer = LLMIntegrationLayer()
            except Exception as exc:
                logger.debug("LLMIntegrationLayer init failed: %s", exc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def complete(self, prompt: str, context: Dict[str, Any]) -> str:
        """Return a completion string for the given prompt and context."""
        full_prompt = self._build_prompt(prompt, context)
        # Try local first
        if self._local is not None:
            try:
                result = self._local.complete(full_prompt)
                if result:
                    return str(result)
            except Exception as exc:
                logger.debug("Local LLM complete failed: %s", exc)
        # Fall back to cloud
        if self._cloud is not None:
            try:
                result = self._cloud.complete(full_prompt)
                if result:
                    return str(result)
            except Exception as exc:
                logger.debug("Cloud LLM complete failed: %s", exc)
        if self._layer is not None:
            try:
                result = self._layer.complete(full_prompt)
                if result:
                    return str(result)
            except Exception as exc:
                logger.debug("LLM integration layer failed: %s", exc)
        logger.warning("All LLM providers unavailable; returning stub")
        return f"[stub] {prompt[:80]}"

    def analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a data dict and return structured insights."""
        prompt = f"Analyze the following system data and summarise key findings:\n{data}"
        text = self.complete(prompt, {})
        return {"analysis": text, "source": "tenant_llm_router"}

    def generate_plan(self, objective: str) -> List[Dict[str, Any]]:
        """Generate an ordered list of action steps for the given objective."""
        prompt = (
            f"Generate a numbered action plan to achieve the following objective:\n{objective}\n"
            "Return each step as a plain sentence."
        )
        text = self.complete(prompt, {"objective": objective})
        steps = [line.strip() for line in text.splitlines() if line.strip()]
        return [{"step": i + 1, "action": s} for i, s in enumerate(steps)]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_prompt(self, prompt: str, context: Dict[str, Any]) -> str:
        if context:
            ctx_lines = "\n".join(f"  {k}: {v}" for k, v in context.items())
            return f"Context:\n{ctx_lines}\n\n{prompt}"
        return prompt
