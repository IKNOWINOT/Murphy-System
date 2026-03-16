# Copyright © 2020-2026 Inoni LLC — Created by Corey Post
# License: BSL 1.1
"""
MFM Tokenizer — Action-Aware Tokenizer
=======================================

Custom tokeniser for structured action-trace inputs.  Provides a
domain-aware vocabulary that understands Murphy System concepts such as
action types, governance levels, murphy-index ranges, and confidence
buckets.  Special tokens delineate SENSE → THINK → ACT → LEARN phase
boundaries so the model can learn phase-transition dynamics.

When *transformers* is available the tokeniser can extend a HuggingFace
base tokeniser with the Murphy-specific vocabulary.  Without heavy ML
dependencies it falls back to simple character-ordinal encoding.
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# -- special token catalogue --------------------------------------------

_PHASE_TOKENS: Dict[str, str] = {
    "sense": "<|sense|>",
    "think": "<|think|>",
    "act": "<|act|>",
    "learn": "<|learn|>",
}

_ACTION_TOKENS: Dict[str, str] = {
    "api_call": "<|api_call|>",
    "actuator": "<|actuator|>",
    "content": "<|content|>",
    "data": "<|data|>",
    "command": "<|command|>",
    "agent": "<|agent|>",
}

_GATE_TOKENS: Dict[str, str] = {
    "gate_pass": "<|gate_pass|>",
    "gate_fail": "<|gate_fail|>",
    "gate_escalate": "<|gate_escalate|>",
}

_AUTHORITY_LEVELS = ("none", "low", "medium", "high", "critical", "system")

_SCORE_STEP = 0.05
_SCORE_VALUES = [round(i * _SCORE_STEP, 2) for i in range(int(1.0 / _SCORE_STEP) + 1)]


def _build_special_tokens() -> Dict[str, str]:
    """Build the complete special-token dictionary."""
    tokens: Dict[str, str] = {}
    tokens.update(_PHASE_TOKENS)
    tokens.update(_ACTION_TOKENS)
    tokens.update(_GATE_TOKENS)

    for val in _SCORE_VALUES:
        label = f"{val:.2f}"
        tokens[f"confidence:{label}"] = f"<|confidence:{label}|>"
        tokens[f"murphy_index:{label}"] = f"<|murphy_index:{label}|>"

    for level in _AUTHORITY_LEVELS:
        tokens[f"authority:{level}"] = f"<|authority:{level}|>"

    return tokens


SPECIAL_TOKENS: Dict[str, str] = _build_special_tokens()


# -- helper --------------------------------------------------------------

def discretize_score(score: float, step: float = _SCORE_STEP) -> float:
    """Round *score* to the nearest *step* increment, clamped to [0, 1]."""
    clamped = max(0.0, min(1.0, score))
    return round(round(clamped / step) * step, 2)


# -- tokenizer -----------------------------------------------------------

@dataclass
class MFMTokenizer:
    """Action-aware tokeniser for the Murphy Foundation Model.

    Maintains a catalogue of Murphy-specific special tokens and can
    either operate standalone (character-ordinal encoding) or extend a
    HuggingFace tokeniser with the full special vocabulary.
    """

    vocab_path: Optional[str] = None
    _vocab: Dict[str, int] = field(default_factory=dict, repr=False)
    _base_tokenizer: Any = field(default=None, repr=False)

    # -- init ---------------------------------------------------------------

    def __post_init__(self) -> None:
        self._build_local_vocab()
        logger.debug(
            "MFMTokenizer initialised — %d special tokens, vocab_size=%d",
            len(SPECIAL_TOKENS),
            self.vocab_size,
        )

    def _build_local_vocab(self) -> None:
        """Populate ``_vocab`` with special tokens starting at offset 256."""
        offset = 256  # reserve 0-255 for byte fallback
        for key, token_str in SPECIAL_TOKENS.items():
            self._vocab[token_str] = offset
            offset += 1

    # -- public API ---------------------------------------------------------

    def encode(self, text: str) -> List[int]:
        """Encode *text* into token IDs.

        If a HuggingFace base tokeniser has been attached via
        :meth:`extend_base_tokenizer`, it is used.  Otherwise a simple
        character-ordinal encoding is returned with special-token IDs
        substituted where they appear.
        """
        if self._base_tokenizer is not None:
            return self._base_tokenizer.encode(text, add_special_tokens=False)
        return self._encode_fallback(text)

    def decode(self, token_ids: List[int]) -> str:
        """Decode token IDs back to text."""
        if self._base_tokenizer is not None:
            return self._base_tokenizer.decode(token_ids, skip_special_tokens=False)
        inv = {v: k for k, v in self._vocab.items()}
        parts: List[str] = []
        for tid in token_ids:
            if tid in inv:
                parts.append(inv[tid])
            elif 0 <= tid < 256:
                parts.append(chr(tid))
            else:
                parts.append(f"<unk:{tid}>")
        return "".join(parts)

    def encode_trace(self, trace_dict: Dict[str, Any]) -> List[int]:
        """Encode a structured trace dict with special tokens at phase
        boundaries.

        The serialisation format inserts phase tokens before each
        section, confidence/murphy-index tokens for numeric fields,
        and authority tokens for the governance level.
        """
        parts: List[str] = []

        # -- SENSE phase ----------------------------------------------------
        if "world_state" in trace_dict or "sense" in trace_dict:
            parts.append(_PHASE_TOKENS["sense"])
            sense_data = trace_dict.get("sense", trace_dict.get("world_state", {}))
            parts.append(json.dumps(sense_data, default=str))

        # -- THINK phase ----------------------------------------------------
        if "intent" in trace_dict or "think" in trace_dict:
            parts.append(_PHASE_TOKENS["think"])
            think_data = trace_dict.get("think", trace_dict.get("intent", ""))
            if isinstance(think_data, dict):
                parts.append(json.dumps(think_data, default=str))
            else:
                parts.append(str(think_data))

        # -- ACT phase ------------------------------------------------------
        if "action_plan" in trace_dict or "act" in trace_dict:
            parts.append(_PHASE_TOKENS["act"])
            act_data = trace_dict.get("act", trace_dict.get("action_plan", []))
            if isinstance(act_data, list):
                for action in act_data:
                    action_type = action.get("type", "") if isinstance(action, dict) else str(action)
                    token_key = action_type.lower().replace(" ", "_")
                    if token_key in _ACTION_TOKENS:
                        parts.append(_ACTION_TOKENS[token_key])
                    parts.append(json.dumps(action, default=str) if isinstance(action, dict) else str(action))
            else:
                parts.append(json.dumps(act_data, default=str))

        # -- LEARN phase ----------------------------------------------------
        if "outcome" in trace_dict or "learn" in trace_dict:
            parts.append(_PHASE_TOKENS["learn"])
            learn_data = trace_dict.get("learn", trace_dict.get("outcome", {}))
            parts.append(json.dumps(learn_data, default=str))

        # -- confidence / murphy_index / authority --------------------------
        if "confidence" in trace_dict:
            disc = discretize_score(float(trace_dict["confidence"]))
            parts.append(f"<|confidence:{disc:.2f}|>")

        if "murphy_index" in trace_dict:
            disc = discretize_score(float(trace_dict["murphy_index"]))
            parts.append(f"<|murphy_index:{disc:.2f}|>")

        if "authority_level" in trace_dict:
            level = str(trace_dict["authority_level"]).lower()
            if level in _AUTHORITY_LEVELS:
                parts.append(f"<|authority:{level}|>")

        # -- gate outcome ---------------------------------------------------
        if "gate_result" in trace_dict:
            gate = str(trace_dict["gate_result"]).lower()
            if gate in _GATE_TOKENS:
                parts.append(_GATE_TOKENS[gate])

        serialized = " ".join(parts)
        return self.encode(serialized)

    @staticmethod
    def get_special_tokens() -> List[str]:
        """Return all special token strings."""
        return list(SPECIAL_TOKENS.values())

    def extend_base_tokenizer(self, base_tokenizer: Any) -> Any:
        """Add Murphy special tokens to a HuggingFace tokeniser.

        Parameters
        ----------
        base_tokenizer:
            A ``PreTrainedTokenizerBase`` instance (e.g. from
            ``AutoTokenizer.from_pretrained``).

        Returns
        -------
        The same tokeniser instance, mutated in-place with the new
        special tokens.
        """
        try:
            from transformers import PreTrainedTokenizerBase  # noqa: F811
        except ImportError:
            logger.warning(
                "transformers not installed — returning base tokenizer unchanged"
            )
            self._base_tokenizer = base_tokenizer
            return base_tokenizer

        new_tokens = self.get_special_tokens()
        num_added = base_tokenizer.add_special_tokens(
            {"additional_special_tokens": new_tokens}
        )
        logger.info(
            "Extended base tokenizer with %d Murphy special tokens (vocab now %d)",
            num_added,
            len(base_tokenizer),
        )
        self._base_tokenizer = base_tokenizer
        return base_tokenizer

    @property
    def vocab_size(self) -> int:
        """Return vocabulary size."""
        if self._base_tokenizer is not None:
            return len(self._base_tokenizer)
        return 256 + len(self._vocab)

    # -- internal -----------------------------------------------------------

    def _encode_fallback(self, text: str) -> List[int]:
        """Fallback encoder: substitute known special tokens then map
        remaining characters to ordinals."""
        ids: List[int] = []
        remaining = text
        while remaining:
            matched = False
            for token_str, token_id in self._vocab.items():
                if remaining.startswith(token_str):
                    ids.append(token_id)
                    remaining = remaining[len(token_str):]
                    matched = True
                    break
            if not matched:
                ids.append(ord(remaining[0]))
                remaining = remaining[1:]
        return ids
