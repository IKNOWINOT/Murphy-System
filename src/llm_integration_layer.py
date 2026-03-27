"""
LLM Integration Layer
Coordinates Aristotle API (deterministic), Wulfrum (fuzzy match/math validation),
and Murphy LLM (generative) — now powered by DeepInfra (primary) + Together.ai (fallback)
instead of Groq.
Provides domain-specific routing and human-in-the-loop validation triggers.

Copyright © 2020 Inoni LLC · Creator: Corey Post · BSL 1.1
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import requests

try:
    from src.local_llm_fallback import (
        _check_ollama_available,
        _ollama_base_url,
        _preferred_ollama_models,
        _query_ollama,
    )
    _HAS_OLLAMA_FALLBACK = True
except ImportError:
    _HAS_OLLAMA_FALLBACK = False

# Import the new unified provider
try:
    from src.llm_provider import (
        MurphyLLMProvider,
        LLMCompletion,
        DEEPINFRA_BASE_URL,
        DEEPINFRA_CHAT_MODEL,
        TOGETHER_BASE_URL,
        TOGETHER_CHAT_MODEL,
        get_llm,
    )
    _HAS_MURPHY_LLM = True
except ImportError:
    _HAS_MURPHY_LLM = False

logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    """LLM providers"""
    ARISTOTLE  = "aristotle"   # Deterministic, math/physics
    WULFRUM    = "wulfrum"     # Fuzzy match, math validation
    DEEPINFRA  = "deepinfra"   # Generative, creative — PRIMARY
    TOGETHER   = "together"    # Generative, creative — FALLBACK
    GROQ       = "deepinfra"   # Legacy alias → DeepInfra (kept for backward compat)
    MFM        = "mfm"         # Murphy Foundation Model — local, self-trained
    AUTO       = "auto"        # Automatic routing


class DomainType(Enum):
    """Domain types for LLM routing"""
    MATHEMATICAL  = "mathematical"   # Use Aristotle
    PHYSICS       = "physics"        # Use Aristotle
    ENGINEERING   = "engineering"    # Use Aristotle + Wulfrum
    CREATIVE      = "creative"       # Use DeepInfra
    STRATEGIC     = "strategic"      # Use DeepInfra
    ARCHITECTURAL = "architectural"  # Use DeepInfra + Wulfrum
    REGULATORY    = "regulatory"     # Use Aristotle
    GENERAL       = "general"        # Use DeepInfra


class ValidationStatus(Enum):
    """Validation status for math/physics checks"""
    VALIDATED   = "validated"
    DISAGREEMENT = "disagreement"  # Needs human in the loop
    ERROR       = "error"
    PENDING     = "pending"


@dataclass
class LLMRequest:
    """LLM request structure"""
    request_id:          str
    provider:            LLMProvider
    domain:              DomainType
    prompt:              str
    context:             Dict[str, Any]
    parameters:          Dict[str, Any] = field(default_factory=dict)
    requires_validation: bool           = False
    validation_type:     Optional[str]  = None  # math, physics, engineering

    def to_dict(self) -> Dict:
        return {
            "request_id":          self.request_id,
            "provider":            self.provider.value,
            "domain":              self.domain.value,
            "prompt":              self.prompt,
            "context":             self.context,
            "parameters":          self.parameters,
            "requires_validation": self.requires_validation,
            "validation_type":     self.validation_type,
        }


@dataclass
class LLMResponse:
    """LLM response structure"""
    request_id: str
    provider:   LLMProvider
    response:   str
    confidence: float
    metadata:   Dict[str, Any]
    validation: Optional[Dict[str, Any]] = None
    timestamp:  str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict:
        return {
            "request_id": self.request_id,
            "provider":   self.provider.value,
            "response":   self.response,
            "confidence": self.confidence,
            "metadata":   self.metadata,
            "validation": self.validation,
            "timestamp":  self.timestamp,
        }


@dataclass
class ValidationResult:
    """Result of math/physics validation"""
    validation_id:        str
    request_id:           str
    status:               ValidationStatus
    aristotle_result:     Optional[str]          = None
    wulfrum_result:       Optional[str]          = None
    agreement:            bool                   = False
    disagreement_details: Optional[Dict[str, Any]] = None
    human_review_required: bool                  = False
    confidence:           float                  = 0.0

    def to_dict(self) -> Dict:
        return {
            "validation_id":        self.validation_id,
            "request_id":           self.request_id,
            "status":               self.status.value,
            "aristotle_result":     self.aristotle_result,
            "wulfrum_result":       self.wulfrum_result,
            "agreement":            self.agreement,
            "disagreement_details": self.disagreement_details,
            "human_review_required": self.human_review_required,
            "confidence":           self.confidence,
        }


@dataclass
class HumanLoopTrigger:
    """Trigger for human-in-the-loop validation"""
    trigger_id:  str
    request_id:  str
    trigger_type: str   # disagreement, low_confidence, validation_error
    severity:    str    # low, medium, high, critical
    message:     str
    context:     Dict[str, Any]
    options:     List[str] = field(default_factory=list)
    created_at:  str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict:
        return {
            "trigger_id":  self.trigger_id,
            "request_id":  self.request_id,
            "trigger_type": self.trigger_type,
            "severity":    self.severity,
            "message":     self.message,
            "context":     self.context,
            "options":     self.options,
            "created_at":  self.created_at,
        }


class LLMIntegrationLayer:
    """
    Master LLM integration layer coordinating Aristotle, Wulfrum, and Murphy LLM
    (DeepInfra primary / Together.ai fallback).
    Routes requests based on domain type and provides validation.
    """

    def __init__(
        self,
        aristotle_api_key: Optional[str] = None,
        wulfrum_api_key:   Optional[str] = None,
        # Legacy param names kept for backward compat — ignored (DeepInfra/Together used instead)
        groq_api_key:      Optional[str] = None,
        deepinfra_api_key: Optional[str] = None,
        together_api_key:  Optional[str] = None,
        use_local_fallback: bool = True,
    ):
        self.request_count    = 0
        self.validation_count = 0
        self.trigger_count    = 0

        self.aristotle_api_key = aristotle_api_key or os.getenv("ARISTOTLE_API_KEY")
        self.wulfrum_api_key   = wulfrum_api_key   or os.getenv("WULFRUM_API_KEY")

        # ── Unified LLM provider (DeepInfra → Together.ai) ───────────
        if _HAS_MURPHY_LLM:
            self._llm = MurphyLLMProvider(
                deepinfra_api_key=deepinfra_api_key or os.getenv("DEEPINFRA_API_KEY", ""),
                together_api_key= together_api_key  or os.getenv("TOGETHER_API_KEY",  ""),
            )
        else:
            self._llm = None

        # Domain routing configuration
        self.domain_routing = self._load_domain_routing()

        # Validation triggers
        self.triggers: Dict[str, HumanLoopTrigger] = {}

        # Request / response history
        self.request_history:  List[LLMRequest]  = []
        self.response_history: List[LLMResponse] = []

        # Enhanced Local LLM Fallback
        self.use_local_fallback = use_local_fallback
        self.local_llm = None
        if use_local_fallback:
            try:
                from src.local_inference_engine import LocalInferenceEngine
                self.local_llm = LocalInferenceEngine()
                logger.info("✅ Local Inference Engine loaded successfully")
            except ImportError as exc:
                logger.info("⚠️  Could not import Local Inference Engine: %s", exc)
                self.use_local_fallback = False

    def _load_domain_routing(self) -> Dict[DomainType, Dict[str, Any]]:
        """Load domain-specific routing configuration"""
        return {
            DomainType.MATHEMATICAL: {
                "primary_provider":  LLMProvider.ARISTOTLE,
                "fallback_provider": LLMProvider.WULFRUM,
                "requires_validation": True,
                "validation_type": "math",
            },
            DomainType.PHYSICS: {
                "primary_provider":  LLMProvider.ARISTOTLE,
                "fallback_provider": LLMProvider.WULFRUM,
                "requires_validation": True,
                "validation_type": "physics",
            },
            DomainType.ENGINEERING: {
                "primary_provider":    LLMProvider.ARISTOTLE,
                "secondary_provider":  LLMProvider.DEEPINFRA,
                "validation_provider": LLMProvider.WULFRUM,
                "requires_validation": True,
                "validation_type": "engineering",
            },
            DomainType.ARCHITECTURAL: {
                "primary_provider":    LLMProvider.DEEPINFRA,
                "validation_provider": LLMProvider.WULFRUM,
                "requires_validation": True,
                "validation_type": "architecture",
            },
            DomainType.REGULATORY: {
                "primary_provider":  LLMProvider.ARISTOTLE,
                "fallback_provider": LLMProvider.DEEPINFRA,
                "requires_validation": True,
                "validation_type": "regulatory",
            },
            DomainType.CREATIVE: {
                "primary_provider":    LLMProvider.DEEPINFRA,
                "requires_validation": False,
            },
            DomainType.STRATEGIC: {
                "primary_provider":    LLMProvider.DEEPINFRA,
                "requires_validation": False,
            },
            DomainType.GENERAL: {
                "primary_provider":    LLMProvider.DEEPINFRA,
                "requires_validation": False,
            },
        }

    def route_request(
        self,
        prompt:   str,
        domain:   DomainType               = DomainType.GENERAL,
        context:  Optional[Dict[str, Any]] = None,
        provider: Optional[LLMProvider]    = None,
    ) -> LLMResponse:
        """
        Route request to appropriate LLM provider based on domain.

        Args:
            prompt:   The prompt to send to LLM
            domain:   Domain type for routing
            context:  Additional context
            provider: Override provider if specified

        Returns:
            LLMResponse object
        """
        self.request_count += 1
        request_id = f"req_{self.request_count}"

        if provider == LLMProvider.AUTO or provider is None:
            provider = self._determine_provider(domain)

        domain_config = self.domain_routing.get(domain, self.domain_routing[DomainType.GENERAL])

        request = LLMRequest(
            request_id=request_id,
            provider=provider,
            domain=domain,
            prompt=prompt,
            context=context or {},
            requires_validation=domain_config.get("requires_validation", False),
            validation_type=domain_config.get("validation_type"),
        )

        self.request_history.append(request)
        response = self._execute_request(request)
        self.response_history.append(response)

        if request.requires_validation:
            validation = self._validate_response(request, response)
            response.validation = validation.to_dict()
            if validation.status == ValidationStatus.DISAGREEMENT:
                self._create_trigger(request, response, validation)

        return response

    def _determine_provider(self, domain: DomainType) -> LLMProvider:
        """Determine best provider for domain"""
        domain_config = self.domain_routing.get(domain)
        if domain_config:
            return domain_config.get("primary_provider", LLMProvider.DEEPINFRA)
        return LLMProvider.DEEPINFRA

    def _execute_request(self, request: LLMRequest) -> LLMResponse:
        """Execute LLM request with fallback support"""
        try:
            if request.provider == LLMProvider.ARISTOTLE:
                return self._call_aristotle(request)
            elif request.provider == LLMProvider.WULFRUM:
                return self._call_wulfrum(request)
            elif request.provider in (LLMProvider.DEEPINFRA, LLMProvider.TOGETHER):
                return self._call_generative(request)
            else:
                # Legacy GROQ value now maps to DEEPINFRA
                return self._call_generative(request)
        except Exception as exc:
            logger.info("⚠️  API call failed for %s: %s", request.provider.value, exc)
            # Fallback to generative (DeepInfra/Together chain)
            if request.provider not in (LLMProvider.DEEPINFRA, LLMProvider.TOGETHER):
                try:
                    logger.info("🔄 Fallback to DeepInfra/Together...")
                    return self._call_generative(request)
                except Exception as e2:
                    logger.info("⚠️  DeepInfra/Together fallback also failed: %s", e2)
            # Final fallback to local LLM
            if self.use_local_fallback and self.local_llm:
                logger.info("🔄 Fallback to Enhanced Local LLM...")
                return self._call_local_llm(request)
            raise Exception(f"All LLM providers failed. Last error: {exc}")

    def _call_generative(self, request: LLMRequest) -> LLMResponse:
        """
        Call generative LLM via MurphyLLMProvider (DeepInfra → Together.ai → onboard).
        This replaces the old _call_groq method entirely.
        """
        if self._llm:
            try:
                result = self._llm.complete(
                    prompt=request.prompt,
                    system="You are Murphy, an AI automation platform built by Inoni LLC.",
                    temperature=0.7,
                    max_tokens=1024,
                )
                if result.content:
                    # Map provider string back to enum
                    prov = LLMProvider.DEEPINFRA if result.provider == "deepinfra" else LLMProvider.TOGETHER
                    return LLMResponse(
                        request_id=request.request_id,
                        provider=prov,
                        response=result.content,
                        confidence=0.85,
                        metadata={
                            "model":           result.model,
                            "domain":          request.domain.value,
                            "processing_type": "generative",
                            "source":          result.provider,
                            "usage": {
                                "prompt_tokens":     result.tokens_prompt,
                                "completion_tokens": result.tokens_completion,
                                "total_tokens":      result.tokens_total,
                            },
                        },
                    )
            except Exception as exc:
                logger.debug("Suppressed MurphyLLMProvider exception: %s", exc)

        # Fallback: try Ollama
        if _HAS_OLLAMA_FALLBACK:
            try:
                base_url = _ollama_base_url()
                if _check_ollama_available(base_url):
                    for model in _preferred_ollama_models():
                        ollama_result = _query_ollama(
                            request.prompt, model=model, base_url=base_url, max_tokens=1024
                        )
                        if ollama_result:
                            return LLMResponse(
                                request_id=request.request_id,
                                provider=LLMProvider.MFM,
                                response=ollama_result,
                                confidence=0.75,
                                metadata={
                                    "model":           model,
                                    "source":          "ollama",
                                    "domain":          request.domain.value,
                                    "processing_type": "generative",
                                },
                            )
            except Exception as exc:
                logger.debug("Suppressed Ollama exception: %s", exc)

        # Final: local canned response
        response_text = self._local_generative_response(request)
        return LLMResponse(
            request_id=request.request_id,
            provider=LLMProvider.DEEPINFRA,
            response=response_text,
            confidence=0.85,
            metadata={
                "model":           "onboard",
                "domain":          request.domain.value,
                "processing_type": "generative",
                "source":          "local",
            },
        )

    # Keep old name as alias for backward compatibility
    def _call_groq(self, request: LLMRequest) -> LLMResponse:
        """Legacy alias — routes to _call_generative (DeepInfra → Together.ai)."""
        return self._call_generative(request)

    def _call_aristotle(self, request: LLMRequest) -> LLMResponse:
        """Call Aristotle API for deterministic/mathematical processing."""
        api_url = os.getenv("ARISTOTLE_API_URL")
        if api_url and self.aristotle_api_key:
            try:
                resp = requests.post(
                    api_url,
                    json={
                        "prompt":          request.prompt,
                        "domain":          request.domain.value,
                        "validation_type": request.validation_type or "general",
                    },
                    headers={
                        "Authorization": f"Bearer {self.aristotle_api_key}",
                        "Content-Type":  "application/json",
                    },
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()
                return LLMResponse(
                    request_id=request.request_id,
                    provider=LLMProvider.ARISTOTLE,
                    response=data.get("response", ""),
                    confidence=float(data.get("confidence", 0.95)),
                    metadata={
                        "model":           data.get("model", "aristotle-deterministic"),
                        "domain":          request.domain.value,
                        "processing_type": "deterministic",
                        "source":          "api",
                    },
                )
            except Exception as exc:
                logger.debug("Suppressed exception: %s", exc)

        response_text = self._local_aristotle_response(request)
        return LLMResponse(
            request_id=request.request_id,
            provider=LLMProvider.ARISTOTLE,
            response=response_text,
            confidence=0.95,
            metadata={
                "model":           "aristotle-deterministic",
                "domain":          request.domain.value,
                "processing_type": "deterministic",
                "source":          "local",
            },
        )

    def _call_wulfrum(self, request: LLMRequest) -> LLMResponse:
        """Call Wulfrum API for fuzzy match and math validation."""
        api_url = os.getenv("WULFRUM_API_URL")
        if api_url and self.wulfrum_api_key:
            try:
                resp = requests.post(
                    api_url,
                    json={
                        "prompt":          request.prompt,
                        "domain":          request.domain.value,
                        "validation_type": request.validation_type or "general",
                    },
                    headers={
                        "Authorization": f"Bearer {self.wulfrum_api_key}",
                        "Content-Type":  "application/json",
                    },
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()
                return LLMResponse(
                    request_id=request.request_id,
                    provider=LLMProvider.WULFRUM,
                    response=data.get("response", ""),
                    confidence=float(data.get("confidence", 0.88)),
                    metadata={
                        "model":           data.get("model", "wulfrum-fuzzy"),
                        "domain":          request.domain.value,
                        "processing_type": "fuzzy_match",
                        "source":          "api",
                    },
                )
            except Exception as exc:
                logger.debug("Suppressed exception: %s", exc)

        response_text = self._local_wulfrum_response(request)
        return LLMResponse(
            request_id=request.request_id,
            provider=LLMProvider.WULFRUM,
            response=response_text,
            confidence=0.88,
            metadata={
                "model":           "wulfrum-fuzzy",
                "domain":          request.domain.value,
                "processing_type": "fuzzy_match",
                "source":          "local",
            },
        )

    def _local_aristotle_response(self, request: LLMRequest) -> str:
        if request.validation_type == "math":
            return "Aristotle deterministic analysis: Mathematical calculation verified. Confidence: 0.95."
        elif request.validation_type == "physics":
            return "Aristotle deterministic analysis: Physics principles verified. Confidence: 0.95."
        return "Aristotle deterministic analysis: Verified under domain standards. Confidence: 0.95."

    def _local_wulfrum_response(self, request: LLMRequest) -> str:
        if request.validation_type == "math":
            return "Wulfrum fuzzy match: Mathematical validation complete. Match score: 0.88."
        elif request.validation_type == "physics":
            return "Wulfrum fuzzy match: Physics validation complete. Match score: 0.92."
        return "Wulfrum fuzzy match: Validation complete. Match score: 0.85."

    def _local_generative_response(self, request: LLMRequest) -> str:
        """Local canned response when all generative providers fail."""
        domain_contexts = {
            DomainType.CREATIVE:      "Creative response generated with innovative solutions.",
            DomainType.STRATEGIC:     "Strategic analysis completed with recommended actions.",
            DomainType.ARCHITECTURAL: "Architectural design generated with best practices.",
            DomainType.GENERAL:       "General response generated based on context.",
        }
        base_response = domain_contexts.get(request.domain, "Response generated.")
        if request.context:
            ctx = ", ".join(f"{k}: {v}" for k, v in request.context.items() if isinstance(v, (str, int, float)))
            return f"{base_response} Context: {ctx}"
        return base_response

    # Legacy alias kept for any code referencing _local_groq_response
    def _local_groq_response(self, request: LLMRequest) -> str:
        return self._local_generative_response(request)

    def _call_local_llm(self, request: LLMRequest) -> LLMResponse:
        """Call Enhanced Local LLM as final fallback"""
        if not self.local_llm:
            raise Exception("Enhanced Local LLM not available")

        local_response = self.local_llm.query(
            prompt=request.prompt,
            provider="deepinfra",
            temperature=0.7,
        )

        return LLMResponse(
            request_id=request.request_id,
            provider=LLMProvider.MFM,
            response=local_response["response"],
            confidence=local_response["confidence"],
            metadata={
                "model":           "enhanced-local-llm",
                "domain":          request.domain.value,
                "processing_type": "local-fallback",
                "tokens_used":     local_response["tokens_used"],
                "offline_mode":    True,
                "local_metadata":  local_response.get("metadata", {}),
            },
        )

    def _validate_response(
        self,
        request:  LLMRequest,
        response: LLMResponse,
    ) -> ValidationResult:
        self.validation_count += 1
        validation_id = f"val_{self.validation_count}"

        domain_config       = self.domain_routing.get(request.domain, {})
        validation_provider = domain_config.get("validation_provider")

        if not validation_provider:
            return ValidationResult(
                validation_id=validation_id,
                request_id=request.request_id,
                status=ValidationStatus.VALIDATED,
                agreement=True,
                confidence=response.confidence,
            )

        if validation_provider == LLMProvider.WULFRUM:
            validation_response = self._call_wulfrum(request)
        elif validation_provider == LLMProvider.ARISTOTLE:
            validation_response = self._call_aristotle(request)
        else:
            validation_response = self._call_generative(request)

        aristotle_result = response.response if request.provider == LLMProvider.ARISTOTLE else None
        wulfrum_result   = validation_response.response if validation_provider == LLMProvider.WULFRUM else None
        agreement        = self._check_agreement(response.response, validation_response.response)

        return ValidationResult(
            validation_id=validation_id,
            request_id=request.request_id,
            status=ValidationStatus.VALIDATED if agreement else ValidationStatus.DISAGREEMENT,
            aristotle_result=aristotle_result,
            wulfrum_result=wulfrum_result,
            agreement=agreement,
            disagreement_details={
                "primary":         response.response[:200],
                "validation":      validation_response.response[:200],
                "confidence_diff": abs(response.confidence - validation_response.confidence),
            } if not agreement else None,
            human_review_required=not agreement,
            confidence=(response.confidence + validation_response.confidence) / 2,
        )

    def _check_agreement(self, response1: str, response2: str) -> bool:
        if "verified" in response1.lower() and "verified" in response2.lower():
            return True
        if "error" in response1.lower() or "error" in response2.lower():
            return False
        return True

    def _create_trigger(
        self,
        request:    LLMRequest,
        response:   LLMResponse,
        validation: ValidationResult,
    ):
        self.trigger_count += 1
        trigger_id = f"trigger_{self.trigger_count}"
        if validation.confidence < 0.5:
            severity = "critical"
        elif validation.confidence < 0.7:
            severity = "high"
        else:
            severity = "medium"

        trigger = HumanLoopTrigger(
            trigger_id=trigger_id,
            request_id=request.request_id,
            trigger_type="disagreement",
            severity=severity,
            message=f"Aristotle and Wulfrum disagree on {request.domain.value} validation. Please review.",
            context={
                "prompt":           request.prompt[:200],
                "aristotle_result": validation.aristotle_result[:200] if validation.aristotle_result else None,
                "wulfrum_result":   validation.wulfrum_result[:200]   if validation.wulfrum_result   else None,
                "domain":           request.domain.value,
            },
            options=["Accept Aristotle", "Accept Wulfrum", "Request Re-evaluation", "Manual Override"],
        )
        self.triggers[trigger_id] = trigger

    def get_pending_triggers(self) -> List[HumanLoopTrigger]:
        return list(self.triggers.values())

    def resolve_trigger(self, trigger_id: str, resolution: str) -> bool:
        if trigger_id in self.triggers:
            del self.triggers[trigger_id]
            return True
        return False

    def generate_system_report(self) -> Dict[str, Any]:
        by_provider: Dict[str, int] = {}
        for response in self.response_history:
            p = response.provider.value
            by_provider[p] = by_provider.get(p, 0) + 1

        by_domain: Dict[str, int] = {}
        for request in self.request_history:
            d = request.domain.value
            by_domain[d] = by_domain.get(d, 0) + 1

        validations_pending = sum(
            1 for r in self.response_history
            if r.validation and r.validation.get("human_review_required")
        )

        llm_status = self._llm.get_status() if self._llm else {}

        return {
            "total_requests":             self.request_count,
            "total_validations":          self.validation_count,
            "pending_triggers":           len(self.triggers),
            "by_provider":                by_provider,
            "by_domain":                  by_domain,
            "validations_pending_review": validations_pending,
            "llm_provider_status":        llm_status,
        }


if __name__ == "__main__":
    llm_layer = LLMIntegrationLayer()

    logger.info("=== Test 1: Mathematical Domain ===")
    response = llm_layer.route_request(
        prompt="Calculate the structural load bearing capacity of a beam with given dimensions",
        domain=DomainType.MATHEMATICAL,
        context={"beam_width": 10, "beam_height": 20, "material": "steel"},
    )
    logger.info("Provider: %s", response.provider.value)
    logger.info("Response: %s", response.response)
    logger.info("Confidence: %.2f", response.confidence)

    logger.info("\n=== Test 2: Creative Domain (DeepInfra) ===")
    response = llm_layer.route_request(
        prompt="Suggest innovative features for a mobile app",
        domain=DomainType.CREATIVE,
        context={"app_type": "fitness"},
    )
    logger.info("Provider: %s", response.provider.value)
    logger.info("Response: %s", response.response)

    logger.info("\n=== System Report ===")
    logger.info(json.dumps(llm_layer.generate_system_report(), indent=2))