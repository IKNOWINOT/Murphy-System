# Copyright © 2020-2026 Inoni LLC — Created by Corey Post
# License: BSL 1.1
"""
MFM Tokenizer (Phase 2 Stub)
=============================

Custom tokeniser for structured action-trace inputs.  Provides a
domain-aware vocabulary that understands Murphy System concepts such as
action types, governance levels and murphy-index ranges.

.. note:: Full implementation deferred to Phase 2.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MFMTokenizer:
    """Tokeniser stub for the Murphy Foundation Model.

    The Phase 2 implementation will provide:

    * A domain vocabulary covering action types, event types, constraint
      names, and Murphy-index buckets.
    * Structured field separators for the instruction-tuning format.
    * BPE fall-back for free-text fields.
    """

    def __init__(self, vocab_path: Optional[str] = None) -> None:
        self.vocab_path = vocab_path
        self._vocab: Dict[str, int] = {}
        logger.debug("MFMTokenizer stub initialised")

    def encode(self, text: str) -> List[int]:
        """Encode *text* into token IDs (stub — returns character ordinals)."""
        return [ord(ch) for ch in text]

    def decode(self, token_ids: List[int]) -> str:
        """Decode token IDs back to text (stub)."""
        return "".join(chr(tid) for tid in token_ids)

    def encode_trace(self, trace_dict: Dict[str, Any]) -> List[int]:
        """Encode a structured trace dict (stub)."""
        import json

        return self.encode(json.dumps(trace_dict, default=str))

    @property
    def vocab_size(self) -> int:
        """Return vocabulary size."""
        return len(self._vocab) if self._vocab else 256  # ASCII fallback
