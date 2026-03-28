"""
Murphy LLM Controller - Master Backend Terminal
Controls DeepInfra API and onboard smaller LLMs
Powers the neon terminal UI for system/module setup guidance

Based on Recursive Language Models (RLM) pattern from 2512.24601v1.pdf

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from murphy_identity import MURPHY_SYSTEM_IDENTITY

# INC-01 / C-01: Import the OpenAI-compatible provider (unified LLM gateway)
from openai_compatible_provider import (  # noqa: F401
    ChatMessage,
    CompletionResponse,
    OpenAICompatibleProvider,
    ProviderConfig,
    ProviderType,
)

logger = logging.getLogger(__name__)


class LLMModel(Enum):
    """Available LLM models"""
    DEEPINFRA_70B = "deepinfra_70b"  # formerly GROQ_MIXTRAL
    DEEPINFRA_LLAMA = "deepinfra_llama"  # formerly GROQ_LLAMA
    DEEPINFRA_FAST = "deepinfra_fast"  # formerly GROQ_GEMMA
    LOCAL_SMALL = "local_small"
    LOCAL_MEDIUM = "local_medium"
    MFM = "mfm"  # Murphy Foundation Model — local, self-trained


class ModelCapability(Enum):
    """Model capabilities"""
    CODE_GENERATION = "code_generation"
    REASONING = "reasoning"
    CONTEXT_PROCESSING = "context_processing"
    SWARM_PLANNING = "swarm_planning"
    SAFETY_ANALYSIS = "safety_analysis"


@dataclass
class LLMModelInfo:
    """Information about an LLM model"""
    name: str
    model_type: LLMModel
    capabilities: List[ModelCapability]
    max_context: int
    cost_per_1k_tokens: float
    avg_latency: float
    confidence_threshold: float
    available: bool = True


@dataclass
class LLMRequest:
    """LLM request structure"""
    prompt: str
    context: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2000
    model_preference: Optional[LLMModel] = None
    require_capabilities: Optional[List[ModelCapability]] = None


@dataclass
class LLMResponse:
    """LLM response structure"""
    content: str
    model_used: LLMModel
    confidence: float
    tokens_used: int
    cost: float
    latency: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class LLMController:
    """
    Master LLM Controller for Murphy System

    Features:
    - Automatic model selection based on confidence and capabilities
    - DeepInfra API integration for fast inference
    - Local model fallback for cost efficiency
    - Context chunking for long inputs
    - Recursive query support
    - Safety gate integration
    - Cost tracking and optimization
    """

    def __init__(self):
        self.models: Dict[LLMModel, LLMModelInfo] = self._initialize_models()
        self.request_count = 0
        self.total_cost = 0.0
        self.total_tokens = 0
        self.confidence_history = []

    def _initialize_models(self) -> Dict[LLMModel, LLMModelInfo]:
        """Initialize available LLM models"""
        return {
            LLMModel.DEEPINFRA_70B: LLMModelInfo(
                name="Mixtral-8x7B",
                model_type=LLMModel.DEEPINFRA_70B,
                capabilities=[
                    ModelCapability.CODE_GENERATION,
                    ModelCapability.REASONING,
                    ModelCapability.CONTEXT_PROCESSING,
                    ModelCapability.SWARM_PLANNING,
                ],
                max_context=32000,
                cost_per_1k_tokens=0.00027,
                avg_latency=0.05,
                confidence_threshold=0.85,
                available=os.environ.get("DEEPINFRA_API_KEY") is not None
            ),
            LLMModel.DEEPINFRA_LLAMA: LLMModelInfo(
                name="Llama3-70B",
                model_type=LLMModel.DEEPINFRA_LLAMA,
                capabilities=[
                    ModelCapability.REASONING,
                    ModelCapability.SWARM_PLANNING,
                    ModelCapability.SAFETY_ANALYSIS,
                ],
                max_context=8192,
                cost_per_1k_tokens=0.00059,
                avg_latency=0.08,
                confidence_threshold=0.90,
                available=os.environ.get("DEEPINFRA_API_KEY") is not None
            ),
            LLMModel.DEEPINFRA_FAST: LLMModelInfo(
                name="Gemma-7B",
                model_type=LLMModel.DEEPINFRA_FAST,
                capabilities=[
                    ModelCapability.CODE_GENERATION,
                    ModelCapability.CONTEXT_PROCESSING,
                ],
                max_context=8192,
                cost_per_1k_tokens=0.00010,
                avg_latency=0.03,
                confidence_threshold=0.75,
                available=os.environ.get("DEEPINFRA_API_KEY") is not None
            ),
            LLMModel.LOCAL_SMALL: LLMModelInfo(
                name="Phi-2 (Local)",
                model_type=LLMModel.LOCAL_SMALL,
                capabilities=[
                    ModelCapability.CODE_GENERATION,
                    ModelCapability.CONTEXT_PROCESSING,
                ],
                max_context=2048,
                cost_per_1k_tokens=0.0,
                avg_latency=0.5,
                confidence_threshold=0.65,
                available=True
            ),
            LLMModel.LOCAL_MEDIUM: LLMModelInfo(
                name="Local-Medium",
                model_type=LLMModel.LOCAL_MEDIUM,
                capabilities=[
                    ModelCapability.REASONING,
                    ModelCapability.SWARM_PLANNING,
                    ModelCapability.SAFETY_ANALYSIS,
                ],
                max_context=4096,
                cost_per_1k_tokens=0.0,
                avg_latency=1.0,
                confidence_threshold=0.80,
                available=True
            ),
            LLMModel.MFM: LLMModelInfo(
                name="Murphy Foundation Model",
                model_type=LLMModel.MFM,
                capabilities=[
                    ModelCapability.CODE_GENERATION,
                    ModelCapability.REASONING,
                    ModelCapability.CONTEXT_PROCESSING,
                    ModelCapability.SWARM_PLANNING,
                    ModelCapability.SAFETY_ANALYSIS,
                ],
                max_context=4096,
                cost_per_1k_tokens=0.0,
                avg_latency=0.2,
                confidence_threshold=0.80,
                available=os.environ.get("MFM_MODE", "disabled") == "production"
            ),
        }

    def select_model(self, request: LLMRequest, required_confidence: float = 0.8) -> LLMModel:
        """
        Select the best model for the request based on:
        - Required capabilities
        - Context length
        - Required confidence
        - Cost optimization
        """
        available_models = [
            model for model, info in self.models.items()
            if info.available and info.confidence_threshold >= required_confidence
        ]

        if not available_models:
            # Fall back to any available model
            available_models = [
                model for model, info in self.models.items()
                if info.available
            ]

        if not available_models:
            raise RuntimeError("No LLM models available")

        # Filter by required capabilities
        if request.require_capabilities:
            capable_models = [
                model for model in available_models
                if all(cap in self.models[model].capabilities
                      for cap in request.require_capabilities)
            ]
            if capable_models:
                available_models = capable_models

        # Check context length requirements
        context_length = len(request.context) if request.context else len(request.prompt)
        suitable_models = [
            model for model in available_models
            if self.models[model].max_context >= context_length
        ]

        if suitable_models:
            available_models = suitable_models

        # Sort by confidence threshold (prefer higher confidence)
        available_models.sort(
            key=lambda m: self.models[m].confidence_threshold,
            reverse=True
        )

        # Respect user preference if available
        if request.model_preference in available_models:
            return request.model_preference

        return available_models[0]

    def estimate_confidence(self, request: LLMRequest, model: LLMModel) -> float:
        """
        Estimate confidence level for a request
        Based on:
        - Model's inherent confidence threshold
        - Context length relative to max context
        - Task complexity (heuristic)
        """
        model_info = self.models[model]
        base_confidence = model_info.confidence_threshold

        # Adjust for context usage
        context_length = len(request.context) if request.context else len(request.prompt)
        context_ratio = context_length / model_info.max_context
        context_factor = 1.0 - (context_ratio * 0.2)  # Penalty for long contexts

        # Adjust for task complexity (heuristic based on prompt length and complexity)
        complexity_factor = 1.0
        if len(request.prompt) > 500:
            complexity_factor -= 0.05
        if len(request.prompt) > 1000:
            complexity_factor -= 0.05

        estimated_confidence = base_confidence * context_factor * complexity_factor
        return min(estimated_confidence, 1.0)

    def chunk_context(self, context: str, model: LLMModel) -> List[str]:
        """
        Chunk context to fit within model's context window
        Uses intelligent chunking based on content structure
        """
        model_info = self.models[model]
        max_chunk_size = model_info.max_context // 2  # Leave room for prompt

        if len(context) <= max_chunk_size:
            return [context]

        chunks = []

        # Try to chunk at natural boundaries
        # 1. Markdown headers
        if '\n## ' in context:
            chunks = re.split(r'\n## ', context)
        # 2. Paragraphs
        elif '\n\n' in context:
            chunks = context.split('\n\n')
        # 3. Sentences
        else:
            chunks = re.split(r'(?<=[.!?])\s+', context)

        # Merge chunks to optimal size
        merged_chunks = []
        current_chunk = ""

        for chunk in chunks:
            if len(current_chunk) + len(chunk) <= max_chunk_size:
                current_chunk += chunk + "\n"
            else:
                if current_chunk:
                    merged_chunks.append(current_chunk.strip())
                current_chunk = chunk + "\n"

        if current_chunk:
            merged_chunks.append(current_chunk.strip())

        return merged_chunks

    async def query_llm(self, request: LLMRequest) -> LLMResponse:
        """
        Main query method - routes to appropriate LLM
        """
        self.request_count += 1

        # Select best model
        model = self.select_model(request)

        # Estimate confidence
        confidence = self.estimate_confidence(request, model)

        # Record confidence for tracking
        self.confidence_history.append(confidence)

        # Route to appropriate backend
        start_time = datetime.now(timezone.utc)

        if model == LLMModel.MFM:
            response = await self._query_mfm(request)
        elif model == LLMModel.DEEPINFRA_70B:
            response = await self._query_deepinfra_70b(request)
        elif model == LLMModel.DEEPINFRA_LLAMA:
            response = await self._query_deepinfra_llama(request)
        elif model == LLMModel.DEEPINFRA_FAST:
            response = await self._query_deepinfra_fast(request)
        elif model == LLMModel.LOCAL_SMALL:
            response = await self._query_local_small(request)
        elif model == LLMModel.LOCAL_MEDIUM:
            response = await self._query_local_medium(request)
        else:
            response = await self._query_fallback(request)

        latency = (datetime.now(timezone.utc) - start_time).total_seconds()

        # Update tracking
        self.total_cost += response.cost
        self.total_tokens += response.tokens_used

        # Update response metadata
        response.model_used = model
        response.confidence = confidence
        response.latency = latency

        return response

    async def _query_mfm(self, request: LLMRequest) -> LLMResponse:
        """Query the Murphy Foundation Model (local, self-trained)."""
        try:
            from murphy_foundation_model.mfm_inference import MFMInferenceConfig, MFMInferenceService

            config = MFMInferenceConfig()
            service = MFMInferenceService(config=config)
            if not service.is_loaded:
                service.load_model()

            result = service.predict(
                world_state={"prompt": request.prompt, "context": request.context or ""},
                intent=request.prompt,
                constraints=[],
                history=[],
            )

            content = json.dumps(result.get("action_plan", []), default=str)
            return LLMResponse(
                content=content,
                model_used=LLMModel.MFM,
                confidence=result.get("confidence", 0.0),
                tokens_used=0,
                cost=0.0,
                latency=0.0,
                metadata={"provider": "mfm", "model": "murphy_foundation_model"},
            )
        except Exception as exc:
            logger.info("MFM query failed, falling back: %s", exc)
            return await self._query_fallback(request)

    async def _query_deepinfra_70b(self, request: LLMRequest) -> LLMResponse:
        """Query DeepInfra Mixtral model"""
        try:
            # deepinfra replaced: from openai import DeepInfra

            client = DeepInfra(api_key=os.environ.get("DEEPINFRA_API_KEY"))

            messages = [{"role": "system", "content": MURPHY_SYSTEM_IDENTITY}]

            if request.context:
                messages.append({
                    "role": "system",
                    "content": f"Context: {request.context}"
                })

            messages.append({"role": "user", "content": request.prompt})

            response = client.chat.completions.create(
                model="meta-llama/Meta-Llama-3.1-70B-Instruct",
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens
            )

            content = response.choices[0].message.content
            tokens_used = response.usage.total_tokens
            cost = (tokens_used / 1000) * self.models[LLMModel.DEEPINFRA_70B].cost_per_1k_tokens

            return LLMResponse(
                content=content,
                model_used=LLMModel.DEEPINFRA_70B,
                confidence=0.0,  # Will be set by caller
                tokens_used=tokens_used,
                cost=cost,
                latency=0.0,  # Will be set by caller
                metadata={"provider": "deepinfra", "model": "meta-llama/Meta-Llama-3.1-70B-Instruct"}
            )

        except Exception as exc:
            logger.info(f"Error querying DeepInfra Mixtral: {exc}")
            return await self._query_fallback(request)

    async def _query_deepinfra_llama(self, request: LLMRequest) -> LLMResponse:
        """Query DeepInfra Llama model"""
        try:
            # deepinfra replaced: from openai import DeepInfra

            client = DeepInfra(api_key=os.environ.get("DEEPINFRA_API_KEY"))

            messages = [{"role": "system", "content": MURPHY_SYSTEM_IDENTITY}]

            if request.context:
                messages.append({
                    "role": "system",
                    "content": f"Context: {request.context}"
                })

            messages.append({"role": "user", "content": request.prompt})

            response = client.chat.completions.create(
                model="meta-llama/Meta-Llama-3.1-70B-Instruct",
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens
            )

            content = response.choices[0].message.content
            tokens_used = response.usage.total_tokens
            cost = (tokens_used / 1000) * self.models[LLMModel.DEEPINFRA_LLAMA].cost_per_1k_tokens

            return LLMResponse(
                content=content,
                model_used=LLMModel.DEEPINFRA_LLAMA,
                confidence=0.0,
                tokens_used=tokens_used,
                cost=cost,
                latency=0.0,
                metadata={"provider": "deepinfra", "model": "meta-llama/Meta-Llama-3.1-70B-Instruct"}
            )

        except Exception as exc:
            logger.info(f"Error querying DeepInfra Llama: {exc}")
            return await self._query_fallback(request)

    async def _query_deepinfra_fast(self, request: LLMRequest) -> LLMResponse:
        """Query DeepInfra Gemma model"""
        try:
            # deepinfra replaced: from openai import DeepInfra

            client = DeepInfra(api_key=os.environ.get("DEEPINFRA_API_KEY"))

            messages = [{"role": "system", "content": MURPHY_SYSTEM_IDENTITY}]

            if request.context:
                messages.append({
                    "role": "system",
                    "content": f"Context: {request.context}"
                })

            messages.append({"role": "user", "content": request.prompt})

            response = client.chat.completions.create(
                model="gemma-7b-it",
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens
            )

            content = response.choices[0].message.content
            tokens_used = response.usage.total_tokens
            cost = (tokens_used / 1000) * self.models[LLMModel.DEEPINFRA_FAST].cost_per_1k_tokens

            return LLMResponse(
                content=content,
                model_used=LLMModel.DEEPINFRA_FAST,
                confidence=0.0,
                tokens_used=tokens_used,
                cost=cost,
                latency=0.0,
                metadata={"provider": "deepinfra", "model": "gemma-7b-it"}
            )

        except Exception as exc:
            logger.error("Error querying DeepInfra Gemma: %s", exc)
            return await self._query_fallback(request)

    async def _query_local_small(self, request: LLMRequest) -> LLMResponse:
        """Query local small model — tries Ollama first, then placeholder."""
        try:
            from src.local_llm_fallback import (
                _check_ollama_available, _query_ollama,
                _ollama_base_url, _preferred_ollama_models, _OLLAMA_SMALL_MODELS,
            )
            _base = _ollama_base_url()
            # Honour OLLAMA_MODEL if set, but keep small models at the front
            _env_model = _preferred_ollama_models()[0]
            _models = [_env_model] + [m for m in _OLLAMA_SMALL_MODELS if m != _env_model]
            if _check_ollama_available(_base):
                for _model in _models:
                    result = _query_ollama(request.prompt, model=_model, base_url=_base, max_tokens=request.max_tokens)
                    if result:
                        return LLMResponse(
                            content=result,
                            model_used=LLMModel.LOCAL_SMALL,
                            confidence=0.0,
                            tokens_used=len(result.split()),
                            cost=0.0,
                            latency=0.0,
                            metadata={"provider": "ollama", "model": _model}
                        )
        except Exception as exc:
            logger.debug("Suppressed exception: %s", exc)
            pass

        content = f"[Local Small Model] I understand you need help with: {request.prompt[:100]}..."
        if request.context:
            content += f" Context length: {len(request.context)} chars"

        return LLMResponse(
            content=content,
            model_used=LLMModel.LOCAL_SMALL,
            confidence=0.0,
            tokens_used=len(request.prompt.split()),
            cost=0.0,
            latency=0.0,
            metadata={"provider": "local", "model": "phi-2"}
        )

    async def _query_local_medium(self, request: LLMRequest) -> LLMResponse:
        """Query local medium model — tries Ollama first, then placeholder."""
        try:
            from src.local_llm_fallback import (
                _check_ollama_available, _query_ollama,
                _ollama_base_url, _preferred_ollama_models, _OLLAMA_MEDIUM_MODELS,
            )
            _base = _ollama_base_url()
            # Honour OLLAMA_MODEL if set, but keep medium models at the front
            _env_model = _preferred_ollama_models()[0]
            _models = [_env_model] + [m for m in _OLLAMA_MEDIUM_MODELS if m != _env_model]
            if _check_ollama_available(_base):
                for model in _models:
                    result = _query_ollama(request.prompt, model=model, base_url=_base, max_tokens=request.max_tokens)
                    if result:
                        return LLMResponse(
                            content=result,
                            model_used=LLMModel.LOCAL_MEDIUM,
                            confidence=0.0,
                            tokens_used=len(result.split()),
                            cost=0.0,
                            latency=0.0,
                            metadata={"provider": "ollama", "model": model}
                        )
        except Exception as exc:
            logger.debug("Suppressed exception: %s", exc)
            pass

        content = f"[Local Medium Model] Analyzing request: {request.prompt[:100]}..."

        return LLMResponse(
            content=content,
            model_used=LLMModel.LOCAL_MEDIUM,
            confidence=0.0,
            tokens_used=len(request.prompt.split()) * 2,
            cost=0.0,
            latency=0.0,
            metadata={"provider": "local", "model": "local-medium"}
        )

    async def _query_fallback(self, request: LLMRequest) -> LLMResponse:
        """Onboard fallback — always available, uses LocalLLMFallback pattern-matcher / Ollama."""
        try:
            from local_llm_fallback import LocalLLMFallback
            fallback = LocalLLMFallback()
            content = fallback.generate(request.prompt, max_tokens=request.max_tokens)
        except Exception as exc:
            logger.debug("LocalLLMFallback unavailable (%s), using minimal response", exc)
            content = (
                f"[Onboard] I can help with: {request.prompt[:120]}. "
                "Add a DeepInfra API key via 'set key deepinfra <key>' for enhanced responses."
            )
        return LLMResponse(
            content=content,
            model_used=LLMModel.LOCAL_SMALL,
            confidence=0.55,
            tokens_used=len(content.split()),
            cost=0.0,
            latency=0.0,
            metadata={"provider": "onboard_fallback", "always_available": True},
        )

    async def recursive_query(
        self,
        base_request: LLMRequest,
        max_depth: int = 3,
        current_depth: int = 0
    ) -> LLMResponse:
        """
        Perform recursive query for complex tasks
        Similar to RLM pattern from the paper
        """
        if current_depth >= max_depth:
            return await self.query_llm(base_request)

        # First, get an initial response
        initial_response = await self.query_llm(base_request)

        # Check if response contains sub-tasks or needs decomposition
        # Simple heuristic: look for markers like "First,", "Next,", "Then,"
        decomposition_markers = ["First,", "Next,", "Then,", "After that,", "Step"]
        needs_decomposition = any(
            marker in initial_response.content
            for marker in decomposition_markers
        )

        if not needs_decomposition:
            return initial_response

        # Decompose task and process recursively
        sub_tasks = self._decompose_response(initial_response.content)

        sub_results = []
        for task in sub_tasks:
            sub_request = LLMRequest(
                prompt=task,
                context=base_request.context,
                temperature=base_request.temperature,
                max_tokens=base_request.max_tokens
            )
            sub_result = await self.recursive_query(
                sub_request,
                max_depth,
                current_depth + 1
            )
            sub_results.append(sub_result)

        # Aggregate sub-results
        aggregated_content = self._aggregate_sub_results(
            initial_response.content,
            sub_results
        )

        # Update response with aggregated content
        initial_response.content = aggregated_content
        initial_response.metadata["recursive_depth"] = current_depth + 1
        initial_response.metadata["sub_tasks"] = len(sub_results)

        return initial_response

    def _decompose_response(self, response: str) -> List[str]:
        """Decompose response into sub-tasks"""
        # Simple implementation - split by common markers
        sub_tasks = []
        lines = response.split('\n')

        current_task = ""
        for line in lines:
            if any(marker in line for marker in ["First,", "Next,", "Then,", "After that,", "Step"]):
                if current_task:
                    sub_tasks.append(current_task.strip())
                current_task = line
            else:
                current_task += "\n" + line

        if current_task:
            sub_tasks.append(current_task.strip())

        return sub_tasks

    def _aggregate_sub_results(self, base_content: str, sub_results: List[LLMResponse]) -> str:
        """Aggregate sub-task results into final response"""
        # Simple aggregation - replace markers with actual results
        aggregated = base_content

        for i, result in enumerate(sub_results):
            marker = f"[Sub-task {i+1}]"
            if marker in aggregated:
                aggregated = aggregated.replace(marker, result.content)

        return aggregated

    def refresh_availability(self) -> None:
        """Re-check environment variables and update model availability.

        Call this after a key is added or changed at runtime (e.g. via
        ``/api/llm/configure``) so DeepInfra models are marked available without
        requiring an application restart.
        """
        deepinfra_available = os.environ.get("DEEPINFRA_API_KEY") is not None
        for model_type, info in self.models.items():
            if model_type in (LLMModel.DEEPINFRA_70B, LLMModel.DEEPINFRA_LLAMA, LLMModel.DEEPINFRA_FAST):
                info.available = deepinfra_available

    def reconfigure(self, api_key: str) -> None:
        """Update the DeepInfra API key in the environment and refresh availability.

        This is the single call that hot-reloads a new key without restarting
        the application.  It updates ``os.environ`` directly so that every
        subsequent _query_deepinfra_* call picks up the new value.

        Args:
            api_key: The new DeepInfra API key (must start with ``gsk_``).
        """
        os.environ["DEEPINFRA_API_KEY"] = api_key
        self.refresh_availability()

    def get_statistics(self) -> Dict[str, Any]:
        """Get usage statistics"""
        return {
            "total_requests": self.request_count,
            "total_cost": self.total_cost,
            "total_tokens": self.total_tokens,
            "avg_confidence": sum(self.confidence_history) / (len(self.confidence_history) or 1) if self.confidence_history else 0.0,
            "available_models": [
                {
                    "name": info.name,
                    "model_type": model.value,
                    "available": info.available,
                    "confidence_threshold": info.confidence_threshold
                }
                for model, info in self.models.items()
            ]
        }
