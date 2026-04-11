"""
src/ml — Murphy System ML subsystem.

Public API surface (all imports wrapped in try/except for graceful degradation):

    from src.ml import (
        # Config
        ModelProvider, TaskComplexity, ModelConfig, MFMConfig,
        ProviderRoutingConfig, DEFAULT_MODEL_CONFIG, DEFAULT_ROUTING_CONFIG,
        get_model_config,

        # Training
        TrainingSource, TrainingJob, TrainingPipeline,

        # Registry
        ModelVersion, ModelRegistry,

        # Inference
        InferenceRequest, InferenceResult, InferenceEngine,

        # Copilot
        CopilotTaskType, CopilotRequest, CopilotResult, CopilotAdapter,

        # Evaluation
        EvalMetric, EvalResult, BusinessDomain, ModelEvaluator,

        # API
        create_ml_router,
    )
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# model_config
# ---------------------------------------------------------------------------
try:
    from .model_config import (  # noqa: F401
        DEFAULT_MODEL_CONFIG,
        DEFAULT_MFM_CONFIG,
        DEFAULT_ROUTING_CONFIG,
        MFMConfig,
        ModelConfig,
        ModelProvider,
        ProviderRoutingConfig,
        TaskComplexity,
        get_model_config,
    )
except Exception as _e:  # pragma: no cover
    logger.warning("src.ml.model_config import failed: %s", _e)

# ---------------------------------------------------------------------------
# training_pipeline
# ---------------------------------------------------------------------------
try:
    from .training_pipeline import (  # noqa: F401
        JobStatus,
        TrainingJob,
        TrainingPipeline,
        TrainingSource,
    )
except Exception as _e:  # pragma: no cover
    logger.warning("src.ml.training_pipeline import failed: %s", _e)

# ---------------------------------------------------------------------------
# model_registry
# ---------------------------------------------------------------------------
try:
    from .model_registry import (  # noqa: F401
        ABTest,
        ModelRegistry,
        ModelStatus,
        ModelVersion,
    )
except Exception as _e:  # pragma: no cover
    logger.warning("src.ml.model_registry import failed: %s", _e)

# ---------------------------------------------------------------------------
# inference_engine
# ---------------------------------------------------------------------------
try:
    from .inference_engine import (  # noqa: F401
        InferenceEngine,
        InferenceRequest,
        InferenceResult,
    )
except Exception as _e:  # pragma: no cover
    logger.warning("src.ml.inference_engine import failed: %s", _e)

# ---------------------------------------------------------------------------
# copilot_adapter
# ---------------------------------------------------------------------------
try:
    from .copilot_adapter import (  # noqa: F401
        CopilotAdapter,
        CopilotRequest,
        CopilotResult,
        CopilotTaskType,
    )
except Exception as _e:  # pragma: no cover
    logger.warning("src.ml.copilot_adapter import failed: %s", _e)

# ---------------------------------------------------------------------------
# evaluation
# ---------------------------------------------------------------------------
try:
    from .evaluation import (  # noqa: F401
        BusinessDomain,
        EvalMetric,
        EvalResult,
        ModelEvaluator,
    )
except Exception as _e:  # pragma: no cover
    logger.warning("src.ml.evaluation import failed: %s", _e)

# ---------------------------------------------------------------------------
# manifold_optimizer
# ---------------------------------------------------------------------------
try:
    from .manifold_optimizer import (  # noqa: F401
        ManifoldTrainingStep,
        StiefelOptimizer,
    )
except Exception as _e:  # pragma: no cover
    logger.warning("src.ml.manifold_optimizer import failed: %s", _e)

# ---------------------------------------------------------------------------
# api
# ---------------------------------------------------------------------------
try:
    from .api import create_ml_router  # noqa: F401
except Exception as _e:  # pragma: no cover
    logger.warning("src.ml.api import failed: %s", _e)

__all__ = [
    # model_config
    "ModelProvider",
    "TaskComplexity",
    "ModelConfig",
    "MFMConfig",
    "ProviderRoutingConfig",
    "DEFAULT_MODEL_CONFIG",
    "DEFAULT_MFM_CONFIG",
    "DEFAULT_ROUTING_CONFIG",
    "get_model_config",
    # training_pipeline
    "TrainingSource",
    "JobStatus",
    "TrainingJob",
    "TrainingPipeline",
    # model_registry
    "ModelVersion",
    "ModelStatus",
    "ModelRegistry",
    "ABTest",
    # inference_engine
    "InferenceRequest",
    "InferenceResult",
    "InferenceEngine",
    # copilot_adapter
    "CopilotTaskType",
    "CopilotRequest",
    "CopilotResult",
    "CopilotAdapter",
    # evaluation
    "EvalMetric",
    "EvalResult",
    "BusinessDomain",
    "ModelEvaluator",
    # api
    "create_ml_router",
    # manifold_optimizer
    "StiefelOptimizer",
    "ManifoldTrainingStep",
]
