"""
Structural Coherence Score Engine — Multi-Dimensional Text Coherence Analysis

Design Label: SCS-001 — Structural Coherence Score
Owner: Analysis Engine
Dependencies: None (standalone)

Purpose:
  Analyses arbitrary text for structural coherence across four dimensions:
  logical progression, dependency clarity, consistency, and functional
  completeness.  Produces a composite Structural Coherence Score (SCS)
  in the range [0, 6].  Includes contradiction detection that identifies
  mutually exclusive statements within a document.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class CoherenceScore:
    """Result of a structural coherence analysis.

    Attributes:
        logical_progression: 0-6 score for ordered reasoning.
        dependency_clarity: 0-6 score for relationship definitions.
        consistency: 0-6 score; starts at 6, reduced by contradictions.
        functional_completeness: 0-6 score for structural element coverage.
        scs: Composite score — average of all four dimensions.
        contradictions: Detected contradictions in the text.
        missing_elements: Structural pieces absent from the text.
    """

    logical_progression: float
    dependency_clarity: float
    consistency: float
    functional_completeness: float
    scs: float
    contradictions: List[str] = field(default_factory=list)
    missing_elements: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Keyword / pattern tables
# ---------------------------------------------------------------------------

_BASIC_CONNECTORS: List[str] = [
    "and", "also", "additionally",
]

_SEQUENCING_CONNECTORS: List[str] = [
    "first", "then", "next", "after", "before", "finally",
    "followed by", "subsequently",
]

_CONDITIONAL_CONNECTORS: List[str] = [
    "if", "then", "else", "when", "unless", "otherwise",
    "condition", "case", "depending on",
]

_CAUSAL_CONNECTORS: List[str] = [
    "because", "therefore", "thus", "hence", "consequently",
    "as a result", "due to", "caused by", "leads to", "implies",
]

_RESEARCH_CONNECTORS: List[str] = [
    "hypothesis", "evidence suggests", "correlation", "causation",
    "control variable", "independent variable",
]

_CONNECTOR_GROUPS: List[List[str]] = [
    _BASIC_CONNECTORS,
    _SEQUENCING_CONNECTORS,
    _CONDITIONAL_CONNECTORS,
    _CAUSAL_CONNECTORS,
    _RESEARCH_CONNECTORS,
]

_VAGUE_RELATIONSHIPS: List[str] = [
    "related", "connected", "linked",
]

_NAMED_RELATIONSHIPS: List[str] = [
    "sends to", "receives from", "calls", "depends on", "requires",
]

_DIRECTIONAL_FLOWS: List[str] = [
    "from a to b", "input→output", "upstream", "downstream",
]

_FORMAL_SPECS: List[str] = [
    "contract", "sla", "protocol", "schema", "interface definition",
]

_COMPLETENESS_CATEGORIES: Dict[str, List[str]] = {
    "inputs defined": [
        "input", "receive", "accept", "ingest", "import", "read",
        "consume", "parameter", "argument", "request",
    ],
    "process/logic described": [
        "process", "compute", "calculate", "transform", "analyze",
        "execute", "run", "handle", "evaluate", "generate",
    ],
    "outputs specified": [
        "output", "return", "produce", "send", "emit", "export",
        "write", "publish", "respond", "result",
    ],
    "constraints listed": [
        "constraint", "limit", "restrict", "must", "shall", "require",
        "boundary", "threshold", "maximum", "minimum",
    ],
    "validation/success criteria": [
        "test", "verify", "validate", "check", "assert", "monitor",
        "audit", "confirm", "measure", "benchmark",
    ],
}

_CONTRADICTION_PAIRS: List[tuple[str, str]] = [
    ("fully manual", "fully automated"),
    ("real-time", "batch-only"),
    ("no external access", "internet-connected"),
    ("single module", "distributed across all subsystems"),
    ("synchronous only", "fully asynchronous"),
    ("stateless", "maintains state"),
    ("no database", "database required"),
    ("offline only", "cloud-based"),
    ("open source", "proprietary only"),
    ("monolithic", "microservice"),
]


# ---------------------------------------------------------------------------
# Scoring helpers (module-private)
# ---------------------------------------------------------------------------


def _count_keyword_hits(text: str, keywords: List[str]) -> int:
    """Return how many *distinct* keywords from *keywords* appear in *text*."""
    return sum(1 for kw in keywords if kw in text)


def _score_logical_progression(text: str) -> float:
    """Score logical progression on a 0-6 scale."""
    has_research = _count_keyword_hits(text, _RESEARCH_CONNECTORS) > 0
    if has_research:
        return 6.0

    types_present = sum(
        1 for group in _CONNECTOR_GROUPS[:-1]
        if _count_keyword_hits(text, group) > 0
    )
    if types_present >= 4:
        return 5.0

    has_causal = _count_keyword_hits(text, _CAUSAL_CONNECTORS) > 0
    if has_causal:
        return 4.0

    has_conditional = _count_keyword_hits(text, _CONDITIONAL_CONNECTORS) > 0
    if has_conditional:
        return 3.0

    seq_count = _count_keyword_hits(text, _SEQUENCING_CONNECTORS)
    basic_count = _count_keyword_hits(text, _BASIC_CONNECTORS)
    total_connectors = basic_count + seq_count
    if total_connectors >= 2 and seq_count >= 1:
        return 2.0

    if total_connectors >= 1:
        return 1.0

    return 0.0


def _count_all_relationships(text: str) -> int:
    """Count total distinct relationship keywords across all tiers."""
    total = 0
    for group in (_VAGUE_RELATIONSHIPS, _NAMED_RELATIONSHIPS, _DIRECTIONAL_FLOWS):
        total += _count_keyword_hits(text, group)
    return total


def _score_dependency_clarity(text: str) -> float:
    """Score dependency clarity on a 0-6 scale."""
    has_formal = _count_keyword_hits(text, _FORMAL_SPECS) > 0
    if has_formal:
        return 6.0

    all_rel = _count_all_relationships(text)
    directional_count = _count_keyword_hits(text, _DIRECTIONAL_FLOWS)
    if all_rel >= 5 and directional_count >= 1:
        return 5.0

    named_count = _count_keyword_hits(text, _NAMED_RELATIONSHIPS)
    if all_rel >= 3:
        return 4.0

    if directional_count >= 1:
        return 3.0

    if named_count >= 1:
        return 2.0

    vague_count = _count_keyword_hits(text, _VAGUE_RELATIONSHIPS)
    if vague_count >= 1:
        return 1.0

    return 0.0


def _detect_contradictions(text: str) -> List[str]:
    """Return contradiction messages for mutually exclusive term pairs."""
    contradictions: List[str] = []
    for term1, term2 in _CONTRADICTION_PAIRS:
        if term1 in text and term2 in text:
            contradictions.append(
                f"Contradiction detected: '{term1}' conflicts with '{term2}'"
            )
    return contradictions


def _score_consistency(contradictions: List[str]) -> float:
    """Score consistency on a 0-6 scale: start at 6, subtract 2 per contradiction."""
    return max(0.0, 6.0 - 2.0 * len(contradictions))


def _score_functional_completeness(text: str) -> tuple[float, List[str]]:
    """Score functional completeness on a 0-6 scale (max 1.2 per category).

    Returns:
        Tuple of (score, missing_elements).
    """
    score = 0.0
    missing: List[str] = []
    for category, keywords in _COMPLETENESS_CATEGORIES.items():
        if _count_keyword_hits(text, keywords) > 0:
            score += 1.2
        else:
            missing.append(category)
    return score, missing


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class StructuralCoherenceEngine:
    """Thread-safe engine for computing Structural Coherence Scores.

    The engine analyses text across four dimensions — logical progression,
    dependency clarity, consistency, and functional completeness — and
    produces a composite SCS in [0, 6].
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def score(self, text: str, context: Optional[Dict] = None) -> CoherenceScore:
        """Compute the full Structural Coherence Score for *text*.

        Args:
            text: The document or specification text to analyse.
            context: Optional metadata dict (reserved for future use).

        Returns:
            A :class:`CoherenceScore` with per-dimension scores and the
            composite SCS.
        """
        with self._lock:
            lower = text.lower()

            lp = _score_logical_progression(lower)
            dc = _score_dependency_clarity(lower)
            contradictions = _detect_contradictions(lower)
            con = _score_consistency(contradictions)
            fc, missing = _score_functional_completeness(lower)
            scs = (lp + dc + con + fc) / 4.0

            result = CoherenceScore(
                logical_progression=lp,
                dependency_clarity=dc,
                consistency=con,
                functional_completeness=fc,
                scs=scs,
                contradictions=contradictions,
                missing_elements=missing,
            )

            logger.debug(
                "SCS=%.2f  LP=%.1f  DC=%.1f  CON=%.1f  FC=%.1f  "
                "contradictions=%d  missing=%d",
                scs, lp, dc, con, fc,
                len(contradictions), len(missing),
            )
            return result

    def detect_contradictions(self, text: str) -> List[str]:
        """Detect contradictions in *text* without computing full scores.

        Args:
            text: The document or specification text to check.

        Returns:
            List of human-readable contradiction messages.
        """
        with self._lock:
            return _detect_contradictions(text.lower())
