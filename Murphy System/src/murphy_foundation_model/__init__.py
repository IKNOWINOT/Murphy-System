# Copyright © 2020-2026 Inoni LLC — Created by Corey Post
# License: BSL 1.1
"""
Murphy Foundation Model (MFM) Package

A self-improving foundation model that learns from every action trace
produced by the Murphy System.  Phase 1 delivers data collection,
outcome labeling, and training-data pipeline modules.

Components
----------
- ActionTraceCollector : Captures SENSE → THINK → ACT → LEARN traces
- OutcomeLabeler       : Scores traces on quality, safety and calibration
- TrainingDataPipeline : Converts labeled traces to instruction-tuning data
- MFMTokenizer         : Tokeniser for structured action-trace inputs
- MFMModel             : Lightweight transformer backbone (Phase 2+)
- MFMTrainer           : Fine-tuning loop with RLEF hooks (Phase 2+)
- RLEFEngine           : Reinforcement Learning from Execution Feedback
- MFMInference         : Inference API with confidence gating
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
    trace_to_dict,
    dict_to_trace,
)

from .outcome_labeler import (
    OutcomeLabels,
    OutcomeLabeler,
)

from .training_data_pipeline import (
    TrainingDataPipeline,
)

# Phase 2+ stubs — available but lightweight
from .mfm_tokenizer import MFMTokenizer
from .mfm_model import MFMModel
from .mfm_trainer import MFMTrainer
from .rlef_engine import RLEFEngine
from .mfm_inference import MFMInference
from .shadow_deployment import ShadowDeployment
from .self_improvement_loop import SelfImprovementLoop
from .mfm_registry import MFMRegistry

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

    # Phase 2+ stubs
    "MFMTokenizer",
    "MFMModel",
    "MFMTrainer",
    "RLEFEngine",
    "MFMInference",
    "ShadowDeployment",
    "SelfImprovementLoop",
    "MFMRegistry",
]
