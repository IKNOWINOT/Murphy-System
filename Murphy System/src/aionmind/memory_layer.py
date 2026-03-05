"""
Layer 5 — Memory Integration Layer (STM / LTM).

Two memory modes:
  * **STM (Short-Term Memory):** active contexts, active workflows, pending
    approvals, current evidence.
  * **LTM (Long-Term Memory):** archived workflows, outcomes, corrections,
    proven templates.

For Murphy 2.0a (embedded) both stores are in-memory dicts; for 2.0b they will
be backed by a persistent store / external service.

Similarity search uses lightweight TF-IDF + cosine similarity so that no
external dependencies (e.g. numpy, sklearn) are required.
"""

from __future__ import annotations

import logging
import math
import threading
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── lightweight TF-IDF helpers (no external deps) ────────────────

def _tokenize(text: str) -> List[str]:
    """Simple whitespace + lowercase tokenizer."""
    return [w for w in text.lower().split() if len(w) > 1]


def _term_freq(tokens: List[str]) -> Dict[str, float]:
    counts = Counter(tokens)
    total = len(tokens) or 1
    return {t: c / total for t, c in counts.items()}


def _cosine_similarity(a: Dict[str, float], b: Dict[str, float]) -> float:
    """Cosine similarity between two sparse vectors represented as dicts."""
    common = set(a) & set(b)
    if not common:
        return 0.0
    dot = sum(a[k] * b[k] for k in common)
    mag_a = math.sqrt(sum(v * v for v in a.values()))
    mag_b = math.sqrt(sum(v * v for v in b.values()))
    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0
    return dot / (mag_a * mag_b)


class MemoryLayer:
    """Unified STM / LTM façade.

    Thread-safe; suitable for in-process use in 2.0a.  The interface is designed
    so that swapping to an external service in 2.0b requires only a new backend
    implementation behind the same API.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # STM — keyed by arbitrary string IDs
        self._stm: Dict[str, Dict[str, Any]] = {}
        # LTM — keyed by arbitrary string IDs
        self._ltm: Dict[str, Dict[str, Any]] = {}

    # ── STM operations ────────────────────────────────────────────

    def store_intermediate_state(
        self, key: str, data: Dict[str, Any]
    ) -> None:
        """Persist an intermediate state into STM."""
        with self._lock:
            self._stm[key] = {
                **data,
                "_stored_at": datetime.now(timezone.utc).isoformat(),
            }
        logger.debug("STM store: %s", key)

    def retrieve_context(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve an entry from STM."""
        with self._lock:
            return self._stm.get(key)

    def list_stm_keys(self) -> List[str]:
        with self._lock:
            return list(self._stm.keys())

    def delete_stm(self, key: str) -> bool:
        with self._lock:
            return self._stm.pop(key, None) is not None

    # ── LTM operations ────────────────────────────────────────────

    def archive_workflow(
        self, key: str, data: Dict[str, Any]
    ) -> None:
        """Move a workflow / outcome into LTM."""
        with self._lock:
            self._ltm[key] = {
                **data,
                "_archived_at": datetime.now(timezone.utc).isoformat(),
            }
        logger.debug("LTM archive: %s", key)

    def retrieve_archived(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve an entry from LTM."""
        with self._lock:
            return self._ltm.get(key)

    def search_ltm(
        self, *, tags: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Simple tag-based search over LTM entries."""
        with self._lock:
            if not tags:
                return list(self._ltm.values())
            tag_set = set(tags)
            return [
                v
                for v in self._ltm.values()
                if tag_set & set(v.get("tags", []))
            ]

    def list_ltm_keys(self) -> List[str]:
        with self._lock:
            return list(self._ltm.keys())

    # ── similarity-based retrieval (Gap 4 — 2.0b preview) ───────

    def search_similar(
        self,
        query: str,
        *,
        top_k: int = 5,
        threshold: float = 0.0,
        pool: str = "ltm",
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        """Return entries most similar to *query* using TF-IDF cosine similarity.

        Parameters
        ----------
        query : str
            Free-text search query.
        top_k : int
            Maximum number of results to return.
        threshold : float
            Minimum similarity score (0.0–1.0) to include a result.
        pool : str
            ``"ltm"`` (default), ``"stm"``, or ``"all"``.

        Returns
        -------
        list of (key, score, data) tuples sorted by descending similarity.
        """
        query_vec = _term_freq(_tokenize(query))
        if not query_vec:
            return []

        with self._lock:
            if pool == "stm":
                source = self._stm
            elif pool == "all":
                source = {**self._stm, **self._ltm}
            else:
                source = self._ltm

            scored: List[Tuple[str, float, Dict[str, Any]]] = []
            for key, data in source.items():
                text = self._text_of(data)
                if not text:
                    continue
                doc_vec = _term_freq(_tokenize(text))
                sim = _cosine_similarity(query_vec, doc_vec)
                if sim >= threshold:
                    scored.append((key, sim, data))

        scored.sort(key=lambda t: t[1], reverse=True)
        return scored[:top_k]

    @staticmethod
    def _text_of(data: Dict[str, Any]) -> str:
        """Extract searchable text from a memory entry."""
        parts: List[str] = []
        for key in ("description", "intent", "raw_input", "name", "outcome",
                     "task_description", "tags"):
            val = data.get(key)
            if isinstance(val, str):
                parts.append(val)
            elif isinstance(val, list):
                parts.extend(str(v) for v in val)
        if not parts:
            # fallback: concatenate all string values
            parts = [str(v) for v in data.values() if isinstance(v, str)]
        return " ".join(parts)

    # ── statistics ────────────────────────────────────────────────

    def stats(self) -> Dict[str, int]:
        with self._lock:
            return {
                "stm_entries": len(self._stm),
                "ltm_entries": len(self._ltm),
            }
