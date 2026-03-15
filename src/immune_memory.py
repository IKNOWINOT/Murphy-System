"""
Immune Memory System for the Murphy System.

Design Label: ARCH-011 — Biological Immune Memory
Owner: Backend Team

Implements a biological immune system-inspired pattern memory that allows the
Murphy System to recognise recurring gap patterns and apply proven fixes instantly,
growing exponentially more effective over time.

Key concepts:
- Antigen: a normalised representation of a gap seen by the system
- Antibody: a proven fix action paired with its effectiveness history
- MemoryCell: an activated antigen-antibody pair with decay and threshold logic
- Jaccard similarity + category matching for approximate gap recognition

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import hashlib
import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class Antigen:
    """Normalised representation of a gap observed by the immune system."""

    antigen_id: str
    signature: str                    # deterministic hash of gap characteristics
    gap_category: str
    gap_source: str
    description_tokens: List[str]     # tokenised gap description
    first_seen: str                   # ISO timestamp
    times_seen: int = 1


@dataclass
class Antibody:
    """A proven fix action paired with its effectiveness history."""

    antibody_id: str
    antigen_id: str
    action_template: Dict[str, Any]   # the fix action that works
    effectiveness: float              # current effectiveness score 0.0-1.0
    maturity: int = 0                 # number of successful applications
    created_at: str = ""
    last_activated: str = ""

    def __post_init__(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.last_activated:
            self.last_activated = now


@dataclass
class MemoryCell:
    """An activated antigen-antibody pair with lifecycle management."""

    cell_id: str
    antibody: Antibody
    activation_threshold: float  # minimum similarity to trigger this cell
    decay_rate: float            # potency lost per decay_interval without activation
    potency: float = 1.0         # current potency (1.0 = fully active)


# ---------------------------------------------------------------------------
# ImmuneMemorySystem
# ---------------------------------------------------------------------------

class ImmuneMemorySystem:
    """
    Biological immune system-inspired pattern memory.

    Recognises recurring gap patterns and generates candidate actions
    from proven historical fixes.  Memory cells decay without use and
    are pruned when the maximum cell count is exceeded.

    Thread-safe — all shared state protected by an internal Lock.
    """

    def __init__(
        self,
        similarity_threshold: float = 0.7,
        max_memory_cells: int = 500,
        decay_interval_hours: float = 24.0,
    ) -> None:
        """
        Args:
            similarity_threshold: Minimum similarity score to consider a memory cell
                a match for an incoming gap.
            max_memory_cells: Hard cap on the number of memory cells.
            decay_interval_hours: How often (in simulated hours) cells lose potency.
        """
        self._threshold = similarity_threshold
        self._max_cells = max_memory_cells
        self._decay_interval_hours = decay_interval_hours

        self._cells: Dict[str, MemoryCell] = {}                  # cell_id → MemoryCell
        self._antigens: Dict[str, Antigen] = {}                  # antigen_id → Antigen
        self._signature_to_antigen_id: Dict[str, str] = {}       # signature → antigen_id
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def recognize(self, gap: Any) -> Optional[MemoryCell]:
        """
        Check whether any memory cell matches this gap above the similarity threshold.

        Matching uses:
        - Jaccard similarity on description tokens (40% weight)
        - Exact signature match (40% weight)
        - Category match (20% weight)
        """
        gap_sig = self._compute_signature(gap)
        gap_tokens = self._tokenize(getattr(gap, "description", ""))
        gap_category = getattr(gap, "category", "")

        best_cell: Optional[MemoryCell] = None
        best_score = 0.0

        with self._lock:
            for cell in self._cells.values():
                antigen = self._antigens.get(cell.antibody.antigen_id)
                if antigen is None:
                    continue
                score = self._compute_similarity(
                    gap_sig,
                    antigen.signature,
                    gap_tokens,
                    antigen.description_tokens,
                    gap_category,
                    antigen.gap_category,
                )
                effective_threshold = self._threshold * cell.potency
                if score >= effective_threshold and score > best_score:
                    best_score = score
                    best_cell = cell

        if best_cell is not None:
            logger.debug(
                "recognize: matched cell %s (score=%.3f)", best_cell.cell_id, best_score
            )
        return best_cell

    def activate(self, cell: MemoryCell, gap: Any) -> Any:
        """
        Generate a CandidateAction from a matched memory cell.

        Refreshes the cell's last_activated timestamp and potency.
        """
        from causality_sandbox import CandidateAction  # avoid circular top-level import

        with self._lock:
            cell.antibody.last_activated = datetime.now(timezone.utc).isoformat()
            cell.potency = min(1.0, cell.potency + 0.1)  # activation boosts potency

        template = dict(cell.antibody.action_template)
        return CandidateAction(
            action_id=f"immune_{gap.gap_id}_{uuid.uuid4().hex[:8]}",
            gap_id=gap.gap_id,
            fix_type=template.get("fix_type", "config_adjustment"),
            fix_steps=list(template.get("fix_steps", [])),
            rollback_steps=list(template.get("rollback_steps", [])),
            test_criteria=list(template.get("test_criteria", [])),
            expected_outcome=template.get("expected_outcome", "immune_memory_fix"),
            source_strategy="immune_memory",
        )

    def memorize(
        self,
        gap: Any,
        successful_action: Any,
        effectiveness: float,
    ) -> None:
        """
        Create or strengthen a memory cell for a gap/action pair.

        If a cell already exists for this gap signature, increases its maturity
        and updates effectiveness.  Otherwise creates a new cell.
        """
        signature = self._compute_signature(gap)
        tokens = self._tokenize(getattr(gap, "description", ""))
        category = getattr(gap, "category", "")
        source = getattr(gap, "source", "")
        now = datetime.now(timezone.utc).isoformat()

        action_template: Dict[str, Any] = {
            "fix_type": getattr(successful_action, "fix_type", "config_adjustment"),
            "fix_steps": list(getattr(successful_action, "fix_steps", [])),
            "rollback_steps": list(getattr(successful_action, "rollback_steps", [])),
            "test_criteria": list(getattr(successful_action, "test_criteria", [])),
            "expected_outcome": getattr(successful_action, "expected_outcome", ""),
        }

        with self._lock:
            # Update existing antigen
            if signature in self._signature_to_antigen_id:
                antigen_id = self._signature_to_antigen_id[signature]
                self._antigens[antigen_id].times_seen += 1
            else:
                antigen = Antigen(
                    antigen_id=str(uuid.uuid4()),
                    signature=signature,
                    gap_category=category,
                    gap_source=source,
                    description_tokens=tokens,
                    first_seen=now,
                )
                self._antigens[antigen.antigen_id] = antigen
                self._signature_to_antigen_id[signature] = antigen.antigen_id

            antigen_id = self._signature_to_antigen_id[signature]
            antigen = self._antigens[antigen_id]

            # Find existing cell for this signature
            existing_cell: Optional[MemoryCell] = None
            for cell in self._cells.values():
                if cell.antibody.antigen_id == antigen.antigen_id:
                    existing_cell = cell
                    break

            if existing_cell is not None:
                existing_cell.antibody.maturity += 1
                existing_cell.antibody.last_activated = now
                # Update effectiveness as exponential moving average
                alpha = 0.3
                existing_cell.antibody.effectiveness = round(
                    alpha * effectiveness + (1 - alpha) * existing_cell.antibody.effectiveness,
                    4,
                )
                existing_cell.potency = min(1.0, existing_cell.potency + 0.05)
            else:
                antibody = Antibody(
                    antibody_id=str(uuid.uuid4()),
                    antigen_id=antigen.antigen_id,
                    action_template=action_template,
                    effectiveness=effectiveness,
                    maturity=1,
                    created_at=now,
                    last_activated=now,
                )
                cell = MemoryCell(
                    cell_id=str(uuid.uuid4()),
                    antibody=antibody,
                    activation_threshold=self._threshold,
                    decay_rate=0.05,
                )
                self._cells[cell.cell_id] = cell

            # Prune if over limit
            if len(self._cells) > self._max_cells:
                self._prune_cells()

        logger.debug("memorize: signature=%s effectiveness=%.3f", signature, effectiveness)

    def decay(self) -> None:
        """
        Reduce potency of all memory cells.

        Cells that fall below a minimum potency threshold (0.1) are removed.
        """
        min_potency = 0.1
        to_remove: List[str] = []

        with self._lock:
            for cell_id, cell in self._cells.items():
                cell.potency = max(0.0, cell.potency - cell.decay_rate)
                if cell.potency < min_potency:
                    to_remove.append(cell_id)

            for cell_id in to_remove:
                del self._cells[cell_id]

        if to_remove:
            logger.debug("decay: removed %d depleted memory cells", len(to_remove))

    def get_statistics(self) -> Dict[str, Any]:
        """Return statistics about the current memory state."""
        with self._lock:
            cells = list(self._cells.values())

        if not cells:
            return {
                "cell_count": 0,
                "avg_effectiveness": 0.0,
                "avg_potency": 0.0,
                "avg_maturity": 0.0,
                "top_patterns": [],
            }

        avg_effectiveness = sum(c.antibody.effectiveness for c in cells) / (len(cells) or 1)
        avg_potency = sum(c.potency for c in cells) / (len(cells) or 1)
        avg_maturity = sum(c.antibody.maturity for c in cells) / (len(cells) or 1)

        top_cells = sorted(cells, key=lambda c: c.antibody.effectiveness, reverse=True)[:5]
        top_patterns = [
            {
                "cell_id": c.cell_id,
                "effectiveness": c.antibody.effectiveness,
                "maturity": c.antibody.maturity,
                "potency": round(c.potency, 3),
            }
            for c in top_cells
        ]

        return {
            "cell_count": len(cells),
            "avg_effectiveness": round(avg_effectiveness, 4),
            "avg_potency": round(avg_potency, 4),
            "avg_maturity": round(avg_maturity, 2),
            "top_patterns": top_patterns,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_signature(gap: Any) -> str:
        """Deterministic hash from gap category + source + sorted description tokens."""
        category = getattr(gap, "category", "")
        source = getattr(gap, "source", "")
        description = getattr(gap, "description", "")
        tokens = sorted(description.lower().split())
        raw = f"{category}:{source}:{':'.join(tokens)}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Tokenise a text string into lowercase words."""
        return [w.strip(".,;:!?()[]{}\"'") for w in text.lower().split() if w.strip()]

    @staticmethod
    def _compute_similarity(
        sig1: str,
        sig2: str,
        tokens1: List[str],
        tokens2: List[str],
        category1: str,
        category2: str,
    ) -> float:
        """
        Weighted similarity:
        - Exact signature match: 0.4
        - Jaccard token similarity: 0.4
        - Category match: 0.2
        """
        sig_score = 1.0 if sig1 == sig2 else 0.0
        set1 = set(tokens1)
        set2 = set(tokens2)
        union = set1 | set2
        # Two empty token sets are considered identical (jaccard = 1.0)
        if not union:
            jaccard = 1.0
        else:
            jaccard = len(set1 & set2) / (len(union) or 1)
        category_score = 1.0 if (category1 and category1 == category2) else 0.0
        return sig_score * 0.4 + jaccard * 0.4 + category_score * 0.2

    def _prune_cells(self) -> None:
        """Remove the weakest cells to stay within max_memory_cells."""
        if len(self._cells) <= self._max_cells:
            return
        sorted_cells = sorted(
            self._cells.items(),
            key=lambda kv: kv[1].antibody.effectiveness * kv[1].potency,
        )
        to_remove = len(self._cells) - self._max_cells
        for cell_id, _ in sorted_cells[:to_remove]:
            del self._cells[cell_id]
