"""
Neuro-Symbolic Confidence Models
=================================

Auxiliary ML enhancement layer for confidence estimation.

This module provides learned estimates of:
- H(x): Epistemic instability
- D(x): Deterministic grounding
- R(x): Authority risk

Key Principles:
1. Additive, not replacement
2. Optional enhancement
3. Graceful degradation
4. Safety guarantees
"""

__version__ = "1.0.0"
__status__ = "Production"

# Try to import the full module, fall back to simple wrapper if dependencies missing
try:
    from .data import GraphDataset, TrainingDataCollector
    from .inference import MLInferenceService
    from .models import NeuroSymbolicConfidenceModel
    from .training import ModelTrainer, ModelValidator

    __all__ = [
        "NeuroSymbolicConfidenceModel",
        "GraphDataset",
        "TrainingDataCollector",
        "MLInferenceService",
        "ModelTrainer",
        "ModelValidator"
    ]
except ImportError as exc:
    # Fall back to simple wrapper without external dependencies
    import logging
    logging.getLogger(__name__).debug(  # PATCH-110c: torch_geometric not installed — expected, simple wrapper active
        "Using simplified neuro-symbolic model due to missing dependencies: %s", exc,
    )

    from .simple_wrapper import NeuroSymbolicConfidenceModel, SimpleNeuroSymbolicModel

    __all__ = [
        "NeuroSymbolicConfidenceModel",
        "SimpleNeuroSymbolicModel"
    ]
