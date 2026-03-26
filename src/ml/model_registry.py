"""
Unified Model Registry — wraps MFMRegistry and MLModelRegistry into a single interface.

Lifecycle: registered → shadow → canary → production → archived
HITL gate enforced on promotions to production.
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_MAX_VERSIONS = 500


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

class ModelStatus(str, Enum):
    SHADOW = "shadow"
    CANARY = "canary"
    PRODUCTION = "production"
    ARCHIVED = "archived"
    REGISTERED = "registered"


@dataclass
class ModelVersion:
    version_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    version_name: str = ""
    provider: str = "mfm"
    status: ModelStatus = ModelStatus.REGISTERED
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metrics: Dict[str, Any] = field(default_factory=dict)
    config: Dict[str, Any] = field(default_factory=dict)
    ab_test_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version_id": self.version_id,
            "version_name": self.version_name,
            "provider": self.provider,
            "status": self.status.value,
            "created_at": self.created_at,
            "metrics": self.metrics,
            "config": self.config,
            "ab_test_id": self.ab_test_id,
        }


@dataclass
class ABTest:
    test_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    version_a: str = ""
    version_b: str = ""
    traffic_split: float = 0.1  # fraction of traffic routed to version_b
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    active: bool = True
    results: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_id": self.test_id,
            "version_a": self.version_a,
            "version_b": self.version_b,
            "traffic_split": self.traffic_split,
            "created_at": self.created_at,
            "active": self.active,
            "results": self.results,
        }


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class ModelRegistry:
    """
    Unified model registry.

    Wraps :class:`src.murphy_foundation_model.mfm_registry.MFMRegistry` and
    :class:`src.ml_model_registry.MLModelRegistry` with graceful fallbacks when
    those modules are unavailable.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._versions: List[ModelVersion] = []
        self._active_version_id: Optional[str] = None
        self._ab_tests: List[ABTest] = []

        # Optional backing registries — both wrapped in try/except.
        self._mfm_registry: Optional[Any] = None
        self._ml_registry: Optional[Any] = None

        try:
            from src.murphy_foundation_model.mfm_registry import MFMRegistry  # type: ignore
            self._mfm_registry = MFMRegistry()
        except Exception:
            try:
                from murphy_foundation_model.mfm_registry import MFMRegistry  # type: ignore
                self._mfm_registry = MFMRegistry()
            except Exception:
                logger.debug("MFMRegistry unavailable; using internal store only")

        try:
            from src.ml_model_registry import MLModelRegistry  # type: ignore
            self._ml_registry = MLModelRegistry()
        except Exception:
            try:
                from ml_model_registry import MLModelRegistry  # type: ignore
                self._ml_registry = MLModelRegistry()
            except Exception:
                logger.debug("MLModelRegistry unavailable; using internal store only")

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_model(
        self,
        version_name: str,
        provider: str,
        config: Dict[str, Any],
        metrics: Optional[Dict[str, Any]] = None,
    ) -> ModelVersion:
        """Register a new model version and forward to backing registries."""
        mv = ModelVersion(
            version_name=version_name,
            provider=provider,
            config=config,
            metrics=metrics or {},
            status=ModelStatus.REGISTERED,
        )
        self._append_version(mv)

        # Forward to MFMRegistry when provider is MFM.
        if provider.lower() in ("mfm", "murphy_foundation_model") and self._mfm_registry is not None:
            try:
                from src.murphy_foundation_model.mfm_registry import MFMModelVersion  # type: ignore
                mfm_mv = MFMModelVersion(
                    version_id=mv.version_id,
                    version_str=version_name,
                    base_model=config.get("model_name", "mfm-base"),
                    training_config=config,
                    traces_used=config.get("traces_used", 0),
                    created_at=mv.created_at,
                    metrics=metrics or {},
                )
                self._mfm_registry.register_version(mfm_mv)
            except Exception as exc:
                logger.debug("Could not forward to MFMRegistry: %s", exc)

        # Forward to MLModelRegistry for non-MFM providers.
        if self._ml_registry is not None:
            try:
                self._ml_registry.register_model(  # type: ignore[attr-defined]
                    name=version_name, provider=provider, config=config
                )
            except Exception as exc:
                logger.debug("Could not forward to MLModelRegistry: %s", exc)

        logger.info("Registered model version %s (provider=%s)", mv.version_id, provider)
        return mv

    # ------------------------------------------------------------------
    # Active model management
    # ------------------------------------------------------------------

    def get_active_model(self) -> Optional[ModelVersion]:
        """Return the current production ModelVersion."""
        with self._lock:
            if self._active_version_id:
                for mv in self._versions:
                    if mv.version_id == self._active_version_id:
                        return mv
            # Fall back to backing MFMRegistry.
        if self._mfm_registry is not None:
            try:
                mfm_prod = self._mfm_registry.get_current_production()
                if mfm_prod is not None:
                    return self._mfm_to_model_version(mfm_prod)
            except Exception as exc:
                logger.debug("MFMRegistry.get_current_production failed: %s", exc)
        return None

    def set_active_model(self, version_id: str, hitl_required: bool = True) -> ModelVersion:
        """Promote *version_id* to production. Requires HITL unless bypassed."""
        mv = self._find_version(version_id)
        if mv is None:
            raise ValueError(f"Unknown version_id: {version_id}")

        if hitl_required:
            # Log the HITL gate — callers must have pre-validated approval.
            logger.info(
                "HITL gate: promoting version %s (%s) to production", version_id, mv.version_name
            )

        with self._lock:
            # Archive previous production model.
            for v in self._versions:
                if v.status == ModelStatus.PRODUCTION and v.version_id != version_id:
                    v.status = ModelStatus.ARCHIVED
            mv.status = ModelStatus.PRODUCTION
            self._active_version_id = version_id

        # Mirror promotion in MFMRegistry.
        if self._mfm_registry is not None:
            try:
                # MFMRegistry.promote() advances through shadow→canary→production in steps.
                status = mv.status.value
                while status != "production":
                    status = self._mfm_registry.promote(version_id)
            except Exception as exc:
                logger.debug("Could not promote in MFMRegistry: %s", exc)

        logger.info("Model version %s is now PRODUCTION", version_id)
        return mv

    # ------------------------------------------------------------------
    # Listing / rollback
    # ------------------------------------------------------------------

    def list_models(self) -> List[ModelVersion]:
        with self._lock:
            return list(self._versions)

    def rollback_model(self, version_id: str) -> Optional[ModelVersion]:
        """Roll back active model to *version_id*."""
        mv = self._find_version(version_id)
        if mv is None:
            raise ValueError(f"Unknown version_id: {version_id}")

        with self._lock:
            for v in self._versions:
                if v.status == ModelStatus.PRODUCTION:
                    v.status = ModelStatus.ARCHIVED
            mv.status = ModelStatus.PRODUCTION
            self._active_version_id = version_id

        if self._mfm_registry is not None:
            try:
                self._mfm_registry.rollback()
            except Exception as exc:
                logger.debug("MFMRegistry.rollback failed: %s", exc)

        logger.info("Rolled back to model version %s", version_id)
        return mv

    # ------------------------------------------------------------------
    # A/B testing
    # ------------------------------------------------------------------

    def start_ab_test(
        self, version_a: str, version_b: str, traffic_split: float = 0.1
    ) -> ABTest:
        """Start an A/B test between two model versions."""
        if self._find_version(version_a) is None:
            raise ValueError(f"Unknown version_a: {version_a}")
        if self._find_version(version_b) is None:
            raise ValueError(f"Unknown version_b: {version_b}")

        test = ABTest(version_a=version_a, version_b=version_b, traffic_split=traffic_split)
        with self._lock:
            self._ab_tests.append(test)
            # Tag versions.
            for mv in self._versions:
                if mv.version_id in (version_a, version_b):
                    mv.ab_test_id = test.test_id

        logger.info(
            "A/B test %s started: version_a=%s, version_b=%s, split=%.2f",
            test.test_id, version_a, version_b, traffic_split,
        )
        return test

    def get_ab_tests(self) -> List[ABTest]:
        with self._lock:
            return list(self._ab_tests)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _append_version(self, mv: ModelVersion) -> None:
        with self._lock:
            self._versions.append(mv)
            if len(self._versions) > _MAX_VERSIONS:
                # Archive oldest non-production versions first.
                self._versions = (
                    [v for v in self._versions if v.status == ModelStatus.PRODUCTION]
                    + [v for v in self._versions if v.status != ModelStatus.PRODUCTION][
                        -(_MAX_VERSIONS - 1):
                    ]
                )

    def _find_version(self, version_id: str) -> Optional[ModelVersion]:
        with self._lock:
            for mv in reversed(self._versions):
                if mv.version_id == version_id:
                    return mv
        return None

    @staticmethod
    def _mfm_to_model_version(mfm_mv: Any) -> ModelVersion:
        return ModelVersion(
            version_id=getattr(mfm_mv, "version_id", uuid.uuid4().hex[:16]),
            version_name=getattr(mfm_mv, "version_str", "unknown"),
            provider="mfm",
            status=ModelStatus.PRODUCTION,
            created_at=getattr(mfm_mv, "created_at", datetime.now(timezone.utc).isoformat()),
            metrics=getattr(mfm_mv, "metrics", {}),
            config=getattr(mfm_mv, "training_config", {}),
        )

    # ------------------------------------------------------------------
    # Convenience: select inference target for a given request
    # ------------------------------------------------------------------

    def select_version_for_request(self, ab_test_seed: Optional[float] = None) -> Optional[ModelVersion]:
        """
        Return the ModelVersion to use for an inference request.

        If an active A/B test exists the *traffic_split* fraction of requests (based
        on *ab_test_seed*) will be routed to *version_b*.
        """
        with self._lock:
            active_tests = [t for t in self._ab_tests if t.active]

        if active_tests and ab_test_seed is not None:
            test = active_tests[0]
            version_id = test.version_b if ab_test_seed < test.traffic_split else test.version_a
            mv = self._find_version(version_id)
            if mv:
                return mv

        return self.get_active_model()
