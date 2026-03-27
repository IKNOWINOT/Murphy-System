# Copyright © 2020-2026 Inoni LLC — Created by Corey Post
# License: BSL 1.1
"""
Murphy Foundation Model (MFM) Package

A self-improving foundation model that learns from every action trace
produced by the Murphy System.  Phase 1 delivers data collection,
outcome labeling, and training-data pipeline modules.  Phase 2+
provides tokenisation, model architecture, fine-tuning, RLEF,
inference, shadow deployment, self-improvement, and model registry.

Components
----------
- ActionTraceCollector : Captures SENSE → THINK → ACT → LEARN traces
- OutcomeLabeler       : Scores traces on quality, safety and calibration
- TrainingDataPipeline : Converts labeled traces to instruction-tuning data
- MFMTokenizer         : Action-aware tokeniser with Murphy special tokens
- MFMModel             : Transformer backbone with confidence/risk heads
- MFMTrainer           : LoRA fine-tuning with multi-task loss
- RLEFEngine           : Reinforcement Learning from Execution Feedback
- MFMInferenceService  : Inference API with confidence gating
- ShadowDeployment     : Shadow-mode deployment alongside live agents
- SelfImprovementLoop  : Continuous improvement orchestrator
- MFMRegistry          : Model versioning & artefact storage
"""

__version__ = "0.1.0"
__author__ = "Corey Post"

# Phase 1 — data collection & pipeline
from .action_trace_serializer import (
    ActionTrace,
    ActionTraceCollector,
    dict_to_trace,
    trace_to_dict,
)
from .mfm_inference import MFMInferenceService
from .mfm_model import MFMConfig, MFMModel
from .mfm_registry import MFMModelVersion, MFMRegistry

# Phase 2+ — full implementations
from .mfm_tokenizer import SPECIAL_TOKENS, MFMTokenizer, discretize_score
from .mfm_trainer import MFMTrainer, MFMTrainerConfig, load_training_data
from .outcome_labeler import (
    OutcomeLabeler,
    OutcomeLabels,
)
from .rlef_engine import PreferencePair, RLEFConfig, RLEFEngine
from .self_improvement_loop import SelfImprovementConfig, SelfImprovementLoop
from .shadow_deployment import ShadowComparison, ShadowConfig, ShadowDeployment
from .training_data_pipeline import (
    TrainingDataPipeline,
)

__all__ = [
    # Phase 1 — data collection
    "ActionTrace",
    "ActionTraceCollector",
    "trace_to_dict",
    "dict_to_trace",

    # Phase 1 — labeling
    "OutcomeLabels",
    "OutcomeLabeler",

    # Phase 1 — pipeline
    "TrainingDataPipeline",

    # Phase 2+ — tokenizer
    "MFMTokenizer",
    "SPECIAL_TOKENS",
    "discretize_score",

    # Phase 2+ — model
    "MFMModel",
    "MFMConfig",

    # Phase 2+ — trainer
    "MFMTrainer",
    "MFMTrainerConfig",
    "load_training_data",

    # Phase 2+ — RLEF
    "RLEFEngine",
    "RLEFConfig",
    "PreferencePair",

    # Phase 2+ — inference
    "MFMInferenceService",

    # Phase 2+ — shadow deployment
    "ShadowDeployment",
    "ShadowConfig",
    "ShadowComparison",

    # Phase 2+ — self-improvement
    "SelfImprovementLoop",
    "SelfImprovementConfig",

    # Phase 2+ — registry
    "MFMRegistry",
    "MFMModelVersion",
]
