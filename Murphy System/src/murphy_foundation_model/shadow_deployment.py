# Copyright © 2020-2026 Inoni LLC — Created by Corey Post
# License: BSL 1.1
"""
Shadow Deployment (Phase 2 Stub)
=================================

Runs the MFM in shadow mode alongside live agents, comparing its
predictions against actual outcomes without affecting production
behaviour.

.. note:: Full implementation deferred to Phase 2.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ShadowDeployment:
    """Shadow deployment controller stub."""

    def __init__(
        self,
        inference_engine: Any = None,
        sample_rate: float = 0.1,
    ) -> None:
        self.inference_engine = inference_engine
        self.sample_rate = sample_rate
        self._active = False
        logger.debug("ShadowDeployment stub initialised")

    def start(self) -> None:
        """Activate shadow mode (stub)."""
        self._active = True
        logger.info("Shadow deployment started (stub)")

    def stop(self) -> None:
        """Deactivate shadow mode (stub)."""
        self._active = False
        logger.info("Shadow deployment stopped (stub)")

    @property
    def is_active(self) -> bool:
        return self._active

    def get_comparison_report(self) -> Dict[str, Any]:
        """Return shadow vs. live comparison metrics (stub)."""
        return {"status": "stub", "comparisons": 0, "agreement_rate": 0.0}
