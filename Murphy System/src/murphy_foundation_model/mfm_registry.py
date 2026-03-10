# Copyright © 2020-2026 Inoni LLC — Created by Corey Post
# License: BSL 1.1
"""
MFM Registry (Phase 2 Stub)
=============================

Model versioning and artefact storage for MFM checkpoints.  Mirrors
the existing :class:`ModelRegistry` in the learning engine but is
tailored for MFM lifecycle: registration → validation → shadow →
canary → production → archive.

.. note:: Full implementation deferred to Phase 2.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MFMRegistry:
    """MFM model registry stub."""

    def __init__(self, registry_dir: Optional[str] = None) -> None:
        self.registry_dir = registry_dir or "./data/mfm_registry"
        self._models: Dict[str, Dict[str, Any]] = {}
        logger.debug("MFMRegistry stub initialised — dir=%s", self.registry_dir)

    def register(
        self, name: str, version: str, metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Register a new model version (stub)."""
        model_id = f"{name}:{version}"
        self._models[model_id] = {
            "name": name,
            "version": version,
            "status": "registered",
            "metadata": metadata or {},
        }
        logger.info("Registered MFM model %s (stub)", model_id)
        return model_id

    def get(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a model record (stub)."""
        return self._models.get(model_id)

    def list_models(self) -> List[Dict[str, Any]]:
        """List all registered models (stub)."""
        return list(self._models.values())

    def promote(self, model_id: str, target_status: str = "production") -> None:
        """Promote a model to *target_status* (stub)."""
        if model_id in self._models:
            self._models[model_id]["status"] = target_status
            logger.info("Promoted %s → %s (stub)", model_id, target_status)
