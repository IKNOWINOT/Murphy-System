"""
ML Model Configuration — provider routing, model parameters, and MFM settings.

Defines the configuration hierarchy:
  ModelProvider → TaskComplexity → ModelConfig → ProviderRoutingConfig
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ModelProvider(str, Enum):
    LOCAL = "local"
    DEEPINFRA = "deepinfra"
    OPENAI = "openai"
    COPILOT = "copilot"
    OLLAMA = "ollama"
    MFM = "mfm"


class TaskComplexity(str, Enum):
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ModelConfig:
    """Per-provider model parameters."""
    provider: ModelProvider = ModelProvider.MFM
    model_name: str = "mfm-base"
    max_tokens: int = 512
    temperature: float = 0.7
    top_p: float = 0.9
    timeout_seconds: float = 30.0
    cost_per_token: float = 0.0
    priority_rank: int = 1  # lower = higher priority


@dataclass
class MFMConfig:
    """Architecture and training settings for the Murphy Foundation Model.

    LoRA Without Regret — LORA-ML-CFG-001
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    ``lora_dropout`` added.  ``lora_rank`` and ``lora_alpha`` kept
    consistent with :class:`MFMTrainerConfig` in the MFM package.
    """
    # Architecture
    architecture: str = "transformer"
    lora_rank: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    hidden_size: int = 768
    num_layers: int = 12

    # Training hyperparams
    learning_rate: float = 2e-4
    batch_size: int = 4
    epochs: int = 3

    # Routing thresholds (token count heuristics)
    complexity_threshold_moderate: int = 200   # prompts > N tokens → MODERATE
    complexity_threshold_complex: int = 500    # prompts > N tokens → COMPLEX


@dataclass
class ProviderRoutingConfig:
    """Maps each TaskComplexity to an ordered list of ModelProvider fallback chains."""
    # Ordered preference lists — first available provider wins.
    simple_chain: List[ModelProvider] = field(
        default_factory=lambda: [ModelProvider.MFM, ModelProvider.LOCAL]
    )
    moderate_chain: List[ModelProvider] = field(
        default_factory=lambda: [ModelProvider.DEEPINFRA, ModelProvider.OLLAMA, ModelProvider.MFM]
    )
    complex_chain: List[ModelProvider] = field(
        default_factory=lambda: [ModelProvider.OPENAI, ModelProvider.DEEPINFRA, ModelProvider.MFM]
    )
    critical_chain: List[ModelProvider] = field(
        default_factory=lambda: [ModelProvider.OPENAI, ModelProvider.DEEPINFRA, ModelProvider.MFM]
    )

    def chain_for(self, complexity: TaskComplexity) -> List[ModelProvider]:
        mapping = {
            TaskComplexity.SIMPLE: self.simple_chain,
            TaskComplexity.MODERATE: self.moderate_chain,
            TaskComplexity.COMPLEX: self.complex_chain,
            TaskComplexity.CRITICAL: self.critical_chain,
        }
        return mapping.get(complexity, self.simple_chain)


# ---------------------------------------------------------------------------
# Provider-specific model configs
# ---------------------------------------------------------------------------

_PROVIDER_MODEL_DEFAULTS: Dict[ModelProvider, ModelConfig] = {
    ModelProvider.MFM: ModelConfig(
        provider=ModelProvider.MFM,
        model_name="mfm-base",
        max_tokens=512,
        temperature=0.7,
        top_p=0.9,
        timeout_seconds=15.0,
        cost_per_token=0.0,
        priority_rank=5,
    ),
    ModelProvider.LOCAL: ModelConfig(
        provider=ModelProvider.LOCAL,
        model_name="local-rule-engine",
        max_tokens=256,
        temperature=0.0,
        top_p=1.0,
        timeout_seconds=5.0,
        cost_per_token=0.0,
        priority_rank=6,
    ),
    ModelProvider.OLLAMA: ModelConfig(
        provider=ModelProvider.OLLAMA,
        model_name="phi3",
        max_tokens=1024,
        temperature=0.7,
        top_p=0.9,
        timeout_seconds=30.0,
        cost_per_token=0.0,
        priority_rank=3,
    ),
    ModelProvider.DEEPINFRA: ModelConfig(
        provider=ModelProvider.DEEPINFRA,
        model_name="meta-llama/Meta-Llama-3.1-8B-Instruct",
        max_tokens=2048,
        temperature=0.7,
        top_p=0.9,
        timeout_seconds=20.0,
        cost_per_token=0.000_000_07,
        priority_rank=2,
    ),
    ModelProvider.OPENAI: ModelConfig(
        provider=ModelProvider.OPENAI,
        model_name="gpt-4o-mini",
        max_tokens=4096,
        temperature=0.7,
        top_p=0.9,
        timeout_seconds=60.0,
        cost_per_token=0.000_000_15,
        priority_rank=1,
    ),
    ModelProvider.COPILOT: ModelConfig(
        provider=ModelProvider.COPILOT,
        model_name="gpt-4o",
        max_tokens=4096,
        temperature=0.2,
        top_p=0.95,
        timeout_seconds=60.0,
        cost_per_token=0.0,
        priority_rank=1,
    ),
}

# ---------------------------------------------------------------------------
# Default singletons
# ---------------------------------------------------------------------------

DEFAULT_MODEL_CONFIG: ModelConfig = _PROVIDER_MODEL_DEFAULTS[ModelProvider.MFM]
DEFAULT_MFM_CONFIG: MFMConfig = MFMConfig()
DEFAULT_ROUTING_CONFIG: ProviderRoutingConfig = ProviderRoutingConfig()


# ---------------------------------------------------------------------------
# Public helper
# ---------------------------------------------------------------------------

def get_model_config(
    provider: ModelProvider,
    task_complexity: Optional[TaskComplexity] = None,
) -> ModelConfig:
    """Return the ModelConfig for *provider*, optionally overriding token limits by complexity."""
    base = _PROVIDER_MODEL_DEFAULTS.get(provider, DEFAULT_MODEL_CONFIG)
    if task_complexity is None:
        return base

    # Adjust max_tokens based on complexity without mutating the shared default.
    token_overrides: Dict[TaskComplexity, int] = {
        TaskComplexity.SIMPLE: min(base.max_tokens, 256),
        TaskComplexity.MODERATE: min(base.max_tokens, 1024),
        TaskComplexity.COMPLEX: min(base.max_tokens, 2048),
        TaskComplexity.CRITICAL: base.max_tokens,
    }
    override_tokens = token_overrides.get(task_complexity, base.max_tokens)

    # Return a shallow copy with adjusted tokens to avoid mutating the registry.
    import dataclasses
    return dataclasses.replace(base, max_tokens=override_tokens)
