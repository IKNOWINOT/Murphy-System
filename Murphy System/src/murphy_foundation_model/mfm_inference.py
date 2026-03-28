# Copyright © 2020-2026 Inoni LLC — Created by Corey Post
# License: BSL 1.1
"""
MFM Inference — Inference Service
===================================

Production inference service for the Murphy Foundation Model.
Loads a trained checkpoint, runs inference with confidence gating
aligned to the Murphy Index, and exposes both single-request and
batch prediction APIs.

Internally delegates to :class:`MFMModel` and :class:`MFMTokenizer`.
All heavy ML dependencies are imported lazily so the service can be
imported in lightweight environments.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# -- configuration -------------------------------------------------------

_DEFAULT_CHECKPOINT = os.getenv("MFM_CHECKPOINT", "")
_DEFAULT_DEVICE = os.getenv("MFM_DEVICE", "auto")


@dataclass
class MFMInferenceConfig:
    """Configuration for :class:`MFMInferenceService`."""

    model_path: str = _DEFAULT_CHECKPOINT
    device: str = _DEFAULT_DEVICE
    max_length: int = 2048
    temperature: float = 0.7
    top_p: float = 0.9
    batch_size: int = 1


# -- service --------------------------------------------------------------


class MFMInferenceService:
    """Inference service for the Murphy Foundation Model.

    Manages model lifecycle (load / unload) and provides single-request
    and batched prediction APIs.  Each prediction returns an action
    plan, a calibrated confidence score, a risk score, and an
    escalation flag.
    """

    def __init__(self, config: Optional[MFMInferenceConfig] = None) -> None:
        self.config = config or MFMInferenceConfig()
        self._model: Any = None
        self._tokenizer: Any = None
        self._loaded = False
        self._request_count = 0
        self._total_latency_ms = 0.0
        logger.debug(
            "MFMInferenceService initialised — checkpoint=%s, device=%s",
            self.config.model_path,
            self.config.device,
        )

    # -- public API ---------------------------------------------------------

    @property
    def is_loaded(self) -> bool:
        """Whether the model is currently loaded and ready for inference."""
        return self._loaded

    def load_model(self) -> bool:
        """Load the MFM model and tokenizer from the configured checkpoint.

        Returns ``True`` on success.
        """
        from .mfm_model import MFMConfig, MFMModel
        from .mfm_tokenizer import MFMTokenizer

        model_config = MFMConfig(device=self.config.device)
        self._model = MFMModel(config=model_config)
        self._tokenizer = MFMTokenizer()

        if self.config.model_path and os.path.isdir(self.config.model_path):
            self._model.load_weights(self.config.model_path)
            logger.info("Model loaded from checkpoint %s", self.config.model_path)
        else:
            logger.info(
                "No checkpoint at %s — model initialised in base/stub mode",
                self.config.model_path,
            )

        self._loaded = True

        # Attempt to extend the HF tokenizer if the model has one
        try:
            from transformers import AutoTokenizer  # noqa: F811

            base_tok = AutoTokenizer.from_pretrained(
                model_config.base_model, trust_remote_code=True
            )
            self._tokenizer.extend_base_tokenizer(base_tok)
        except ImportError:
            logger.debug("transformers not available — using fallback tokenizer")
        except Exception as exc:
            logger.warning("Could not load HF tokenizer: %s", exc)

        return True

    def predict(
        self,
        world_state: Dict[str, Any],
        intent: str,
        constraints: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Generate an action-plan prediction for a single request.

        Returns
        -------
        dict with ``action_plan``, ``confidence``, ``risk_score``,
        ``escalation_needed``, ``latency_ms``.
        """
        if not self._loaded or self._model is None:
            return {
                "action_plan": [],
                "confidence": 0.0,
                "risk_score": 1.0,
                "escalation_needed": True,
                "error": "model_not_loaded",
            }

        start = time.monotonic()

        result = self._model.predict_action_plan(
            world_state=world_state,
            intent=intent,
            constraints=constraints,
            history=history,
        )

        latency_ms = (time.monotonic() - start) * 1000
        self._request_count += 1
        self._total_latency_ms += latency_ms

        confidence = result.get("confidence", 0.0)
        risk_score = result.get("risk_score", 1.0)

        # Apply temperature scaling to confidence
        if self.config.temperature != 1.0 and confidence > 0:
            confidence = pow(confidence, 1.0 / self.config.temperature)
            confidence = max(0.0, min(1.0, confidence))

        escalation_needed = result.get("escalation_needed", True)

        return {
            "action_plan": result.get("action_plan", []),
            "confidence": round(confidence, 4),
            "risk_score": round(risk_score, 4),
            "escalation_needed": escalation_needed,
            "latency_ms": round(latency_ms, 2),
        }

    def predict_batch(
        self,
        requests: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Run predictions for a batch of requests.

        Each element in *requests* should contain ``world_state`` and
        ``intent`` keys, with optional ``constraints`` and ``history``.
        """
        results: List[Dict[str, Any]] = []
        for req in requests:
            result = self.predict(
                world_state=req.get("world_state", {}),
                intent=req.get("intent", ""),
                constraints=req.get("constraints"),
                history=req.get("history"),
            )
            results.append(result)
        return results

    def get_status(self) -> Dict[str, Any]:
        """Return service status information."""
        avg_latency = (
            self._total_latency_ms / self._request_count
            if self._request_count > 0
            else 0.0
        )
        model_info: Dict[str, Any] = {}
        if self._model is not None:
            cfg = getattr(self._model, "config", None)
            model_info = {
                "base_model": getattr(cfg, "base_model", "unknown") if cfg else "unknown",
                "parameter_count": self._model.parameter_count(),
                "stub_mode": getattr(self._model, "_stub_mode", True),
            }

        return {
            "loaded": self._loaded,
            "model_path": self.config.model_path,
            "device": self.config.device,
            "model_info": model_info,
            "request_count": self._request_count,
            "avg_latency_ms": round(avg_latency, 2),
        }

    def unload_model(self) -> None:
        """Unload the model to free resources."""
        self._model = None
        self._tokenizer = None
        self._loaded = False

        try:
            import torch  # noqa: F811

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass

        logger.info("Model unloaded — resources freed")
