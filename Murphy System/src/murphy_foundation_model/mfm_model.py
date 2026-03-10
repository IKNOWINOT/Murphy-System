# Copyright © 2020-2026 Inoni LLC — Created by Corey Post
# License: BSL 1.1
"""
MFM Model (Phase 2 Stub)
=========================

Lightweight transformer backbone for the Murphy Foundation Model.

.. note:: Full implementation deferred to Phase 2.  Heavy ML
   dependencies (torch, transformers) are imported lazily.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MFMModel:
    """Placeholder model class for Phase 2.

    In Phase 2 this will wrap a small transformer that accepts
    tokenised action traces and produces action-plan logits.
    """

    def __init__(
        self,
        model_config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.config = model_config or {
            "hidden_size": 256,
            "num_layers": 4,
            "num_heads": 4,
            "max_seq_len": 2048,
        }
        self._weights_loaded = False
        logger.debug("MFMModel stub initialised with config=%s", self.config)

    def forward(self, input_ids: List[int]) -> Dict[str, Any]:
        """Run a forward pass (stub — returns empty logits)."""
        return {"logits": [], "hidden_states": []}

    def load_weights(self, path: str) -> None:
        """Load pre-trained weights from *path* (stub)."""
        self._weights_loaded = True
        logger.info("MFMModel weights loaded from %s (stub)", path)

    def save_weights(self, path: str) -> None:
        """Save weights to *path* (stub)."""
        logger.info("MFMModel weights saved to %s (stub)", path)

    def parameter_count(self) -> int:
        """Return total parameter count (stub)."""
        return 0
