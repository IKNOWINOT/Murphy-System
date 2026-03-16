# Copyright © 2020-2026 Inoni LLC — Created by Corey Post
# License: BSL 1.1
"""
MFM Model — Murphy Foundation Model Architecture
=================================================

Transformer backbone for the Murphy Foundation Model.  Wraps a
HuggingFace causal-LM (default: Phi-3-mini-4k-instruct) with
additional prediction heads for confidence estimation and risk
scoring.

Heavy ML dependencies (``torch``, ``transformers``) are imported
lazily inside methods so the module can be imported in lightweight
environments without GPU or ML packages installed.  When those
dependencies are unavailable the model operates in *stub mode*,
returning empty outputs.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# -- configuration -------------------------------------------------------

_DEFAULT_BASE_MODEL = os.getenv(
    "MFM_BASE_MODEL", "microsoft/Phi-3-mini-4k-instruct"
)
_DEFAULT_DEVICE = os.getenv("MFM_DEVICE", "auto")

_ACTION_TYPES = [
    "api_call",
    "actuator",
    "content",
    "data",
    "command",
    "agent",
]


@dataclass
class MFMConfig:
    """Configuration for :class:`MFMModel`."""

    base_model: str = _DEFAULT_BASE_MODEL
    hidden_size: int = 3072
    num_layers: int = 32
    num_heads: int = 32
    max_seq_len: int = 4096
    action_types: List[str] = field(default_factory=lambda: list(_ACTION_TYPES))
    confidence_bins: int = 21
    murphy_index_bins: int = 21
    device: str = _DEFAULT_DEVICE


# -- model ---------------------------------------------------------------

class MFMModel:
    """Murphy Foundation Model wrapper.

    Wraps a HuggingFace causal-LM with auxiliary heads for:

    * **action-plan logits** — next-action prediction over the Murphy
      action vocabulary.
    * **confidence logits** — calibrated confidence estimate
      (discretised into ``confidence_bins`` buckets).
    * **risk logits** — Murphy-index risk score prediction.

    When ML dependencies are unavailable the model operates in *stub
    mode* and all inference methods return safe empty defaults.
    """

    def __init__(self, config: Optional[MFMConfig] = None) -> None:
        self.config = config or MFMConfig()
        self._base_model: Any = None
        self._confidence_head: Any = None
        self._risk_head: Any = None
        self._device: Any = None
        self._stub_mode = True
        logger.debug("MFMModel initialised (config=%s)", self.config.base_model)

    # -- public API ---------------------------------------------------------

    def forward(
        self,
        input_ids: Any,
        attention_mask: Any = None,
    ) -> Dict[str, Any]:
        """Run a forward pass through the base model and auxiliary heads.

        Returns
        -------
        dict
            ``logits`` — language-model logits from the base model,
            ``confidence_logits`` — softmax over confidence bins,
            ``risk_logits`` — softmax over murphy-index bins.
        """
        if self._stub_mode or self._base_model is None:
            return {
                "logits": [],
                "confidence_logits": [],
                "risk_logits": [],
            }

        try:
            import torch  # noqa: F811
        except ImportError:
            return {"logits": [], "confidence_logits": [], "risk_logits": []}

        with torch.no_grad() if not self._base_model.training else _nullcontext():
            outputs = self._base_model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                output_hidden_states=True,
            )

        lm_logits = outputs.logits
        last_hidden = outputs.hidden_states[-1]
        pooled = last_hidden[:, -1, :]

        confidence_logits = self._confidence_head(pooled) if self._confidence_head else None
        risk_logits = self._risk_head(pooled) if self._risk_head else None

        return {
            "logits": lm_logits,
            "confidence_logits": confidence_logits,
            "risk_logits": risk_logits,
        }

    def predict_action_plan(
        self,
        world_state: Dict[str, Any],
        intent: str,
        constraints: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """High-level inference: produce an action plan with confidence
        and risk estimates.

        Parameters
        ----------
        world_state : dict
            Current environment / context.
        intent : str
            User or agent intent in natural language.
        constraints : dict, optional
            Governance or business constraints.
        history : list, optional
            Previous traces for context.

        Returns
        -------
        dict with keys ``action_plan``, ``confidence``, ``risk_score``,
        ``escalation_needed``.
        """
        if self._stub_mode or self._base_model is None:
            return {
                "action_plan": [],
                "confidence": 0.0,
                "risk_score": 1.0,
                "escalation_needed": True,
                "mode": "stub",
            }

        try:
            import torch  # noqa: F811
        except ImportError:
            return {
                "action_plan": [],
                "confidence": 0.0,
                "risk_score": 1.0,
                "escalation_needed": True,
                "mode": "stub",
            }

        prompt = self._build_prompt(world_state, intent, constraints, history)

        from .mfm_tokenizer import MFMTokenizer

        tokenizer = MFMTokenizer()
        input_ids_list = tokenizer.encode(prompt)
        input_ids = torch.tensor([input_ids_list], device=self._device)
        attention_mask = torch.ones_like(input_ids)

        outputs = self.forward(input_ids, attention_mask)

        confidence = 0.0
        risk_score = 1.0
        if outputs["confidence_logits"] is not None and len(outputs["confidence_logits"]) > 0:
            conf_probs = torch.softmax(outputs["confidence_logits"], dim=-1)
            bins = torch.linspace(0, 1, self.config.confidence_bins, device=self._device)
            confidence = float((conf_probs * bins).sum(dim=-1).item())

        if outputs["risk_logits"] is not None and len(outputs["risk_logits"]) > 0:
            risk_probs = torch.softmax(outputs["risk_logits"], dim=-1)
            bins = torch.linspace(0, 1, self.config.murphy_index_bins, device=self._device)
            risk_score = float((risk_probs * bins).sum(dim=-1).item())

        escalation_needed = confidence < 0.7 or risk_score > 0.5

        # Decode action plan from generated logits
        action_plan = self._decode_action_plan(outputs["logits"])

        return {
            "action_plan": action_plan,
            "confidence": round(confidence, 4),
            "risk_score": round(risk_score, 4),
            "escalation_needed": escalation_needed,
            "mode": "live",
        }

    def load_weights(self, path: str) -> None:
        """Load model weights (base + auxiliary heads) from *path*."""
        try:
            import torch  # noqa: F811
        except ImportError:
            logger.warning("torch not available — cannot load weights")
            return

        if not os.path.isdir(path):
            logger.error("Weight path does not exist: %s", path)
            return

        self._load_base_model()

        head_path = os.path.join(path, "auxiliary_heads.pt")
        if os.path.isfile(head_path):
            state = torch.load(head_path, map_location=self._device, weights_only=True)
            if self._confidence_head is not None and "confidence_head" in state:
                self._confidence_head.load_state_dict(state["confidence_head"])
            if self._risk_head is not None and "risk_head" in state:
                self._risk_head.load_state_dict(state["risk_head"])
            logger.info("Auxiliary heads loaded from %s", head_path)

        adapter_path = os.path.join(path, "adapter_model.safetensors")
        adapter_bin = os.path.join(path, "adapter_model.bin")
        if os.path.isfile(adapter_path) or os.path.isfile(adapter_bin):
            try:
                from peft import PeftModel  # noqa: F811

                self._base_model = PeftModel.from_pretrained(
                    self._base_model, path
                )
                logger.info("LoRA adapter loaded from %s", path)
            except ImportError:
                logger.warning("peft not available — adapter not loaded")

        logger.info("MFMModel weights loaded from %s", path)

    def save_weights(self, path: str) -> None:
        """Persist model weights to *path*."""
        try:
            import torch  # noqa: F811
        except ImportError:
            logger.warning("torch not available — cannot save weights")
            return

        os.makedirs(path, exist_ok=True)

        if self._base_model is not None:
            self._base_model.save_pretrained(path)
            logger.info("Base model saved to %s", path)

        heads_state: Dict[str, Any] = {}
        if self._confidence_head is not None:
            heads_state["confidence_head"] = self._confidence_head.state_dict()
        if self._risk_head is not None:
            heads_state["risk_head"] = self._risk_head.state_dict()
        if heads_state:
            torch.save(heads_state, os.path.join(path, "auxiliary_heads.pt"))

    def parameter_count(self) -> int:
        """Return total trainable parameter count."""
        if self._base_model is None:
            return 0
        try:
            return sum(
                p.numel() for p in self._base_model.parameters() if p.requires_grad
            )
        except Exception as exc:
            return 0

    def to_device(self, device: str) -> None:
        """Move model to the specified device."""
        try:
            import torch  # noqa: F811
        except ImportError:
            logger.warning("torch not available — cannot move device")
            return

        resolved = self._resolve_device(device)
        if self._base_model is not None:
            self._base_model = self._base_model.to(resolved)
        if self._confidence_head is not None:
            self._confidence_head = self._confidence_head.to(resolved)
        if self._risk_head is not None:
            self._risk_head = self._risk_head.to(resolved)
        self._device = resolved
        logger.info("Model moved to %s", resolved)

    # -- internal -----------------------------------------------------------

    def _load_base_model(self) -> None:
        """Lazily load the HuggingFace base model and create auxiliary
        heads."""
        if self._base_model is not None:
            return

        try:
            import torch  # noqa: F811
            from transformers import AutoModelForCausalLM  # noqa: F811
        except ImportError:
            logger.warning(
                "torch/transformers not available — model stays in stub mode"
            )
            return

        self._device = self._resolve_device(self.config.device)

        logger.info("Loading base model %s …", self.config.base_model)
        self._base_model = AutoModelForCausalLM.from_pretrained(
            self.config.base_model,
            torch_dtype=torch.float16,
            device_map=self.config.device if self.config.device == "auto" else None,
            trust_remote_code=True,
        )

        if self.config.device != "auto":
            self._base_model = self._base_model.to(self._device)

        hidden = self.config.hidden_size
        self._confidence_head = torch.nn.Linear(hidden, self.config.confidence_bins)
        self._risk_head = torch.nn.Linear(hidden, self.config.murphy_index_bins)

        if self._device is not None and self.config.device != "auto":
            self._confidence_head = self._confidence_head.to(self._device)
            self._risk_head = self._risk_head.to(self._device)

        self._stub_mode = False
        logger.info(
            "Base model loaded — %d parameters",
            self.parameter_count(),
        )

    @staticmethod
    def _resolve_device(device_str: str) -> Any:
        """Resolve a device string to a ``torch.device``."""
        try:
            import torch  # noqa: F811
        except ImportError:
            return None

        if device_str == "auto":
            if torch.cuda.is_available():
                return torch.device("cuda")
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return torch.device("mps")
            return torch.device("cpu")
        return torch.device(device_str)

    @staticmethod
    def _build_prompt(
        world_state: Dict[str, Any],
        intent: str,
        constraints: Optional[Dict[str, Any]],
        history: Optional[List[Dict[str, Any]]],
    ) -> str:
        """Construct a text prompt for the model from structured inputs."""
        parts = ["<|sense|>", json.dumps(world_state, default=str)]
        parts.append("<|think|>")
        parts.append(intent)
        if constraints:
            parts.append(json.dumps(constraints, default=str))
        if history:
            for h in history[-3:]:
                parts.append(json.dumps(h, default=str))
        parts.append("<|act|>")
        return " ".join(parts)

    def _decode_action_plan(self, logits: Any) -> List[Dict[str, Any]]:
        """Decode action-plan steps from model logits."""
        if logits is None or (hasattr(logits, "__len__") and len(logits) == 0):
            return []
        try:
            import torch  # noqa: F811

            probs = torch.softmax(logits[:, -1, :], dim=-1)
            top_k = torch.topk(probs, k=min(5, probs.shape[-1]), dim=-1)
            actions = []
            for i, (val, idx) in enumerate(
                zip(top_k.values[0].tolist(), top_k.indices[0].tolist())
            ):
                action_type = (
                    self.config.action_types[idx % len(self.config.action_types)]
                )
                actions.append(
                    {
                        "step": i + 1,
                        "type": action_type,
                        "token_id": idx,
                        "probability": round(val, 4),
                    }
                )
            return actions
        except Exception as exc:
            logger.debug("Action-plan decode fallback: %s", exc)
            return []


# -- helpers -------------------------------------------------------------

class _nullcontext:
    """Minimal no-op context manager for Python < 3.10 compat."""

    def __enter__(self) -> None:
        return None

    def __exit__(self, *args: Any) -> None:
        pass
