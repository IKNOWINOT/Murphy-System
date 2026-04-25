"""
Information Density Index Engine — Domain-Agnostic Actionable-Element Scoring

Design Label: IDI-001 — Information Density Index
Owner: Analysis Engine
Dependencies:
  - resolution_scoring (ResolutionScore for scope-creep detection)

Purpose:
  Tokenises arbitrary text, detects actionable elements across six domain-
  agnostic categories (function, component, process, constraint, metric,
  validation), and produces a normalised Information Density Index (IDI)
  in the range [0, 1].  When paired with an existing ResolutionScore whose
  RS >= 3.0, a low IDI (< 0.3) triggers a scope-creep warning.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Pattern

from src.resolution_scoring import ResolutionScore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Actionable-element category definitions
# ---------------------------------------------------------------------------

_CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "function": [
        "compute", "generate", "optimize", "route", "schedule",
        "calculate", "analyze", "transform", "process", "execute",
        "render", "compile", "parse", "serialize", "deserialize",
        "encrypt", "decrypt", "compress", "decompress", "filter",
        "sort", "aggregate", "validate", "authenticate", "authorize",
    ],
    "component": [
        "module", "service", "subsystem", "engine", "controller",
        "manager", "handler", "gateway", "proxy", "adapter",
        "connector", "driver", "plugin", "extension", "middleware",
        "broker", "registry", "repository", "factory", "provider",
        "client", "server", "daemon", "agent", "worker",
    ],
    "process": [
        "calculate", "analyze", "validate", "transform", "migrate",
        "deploy", "configure", "initialize", "bootstrap", "provision",
        "orchestrate", "choreograph", "pipeline", "batch", "stream",
        "queue", "schedule", "dispatch", "coordinate", "synchronize",
        "replicate",
    ],
    "constraint": [
        "must", "shall", "required", "limited to", "maximum",
        "minimum", "at least", "at most", "no more than", "not exceed",
        "within", "between", "ensure", "restrict", "prohibit",
        "mandatory", "compulsory", "prerequisite", "boundary",
        "threshold", "ceiling", "floor", "cap",
    ],
    "metric": [
        "accuracy", "latency", "throughput", "percentage", "uptime",
        "availability", "reliability", "response time", "error rate",
        "success rate", "coverage", "precision", "recall", "sla",
        "slo", "p99", "p95", "p50", "percentile", "median",
        "average", "mean", "variance",
    ],
    "validation": [
        "test", "verify", "assert", "check", "monitor",
        "audit", "inspect", "review", "evaluate", "benchmark",
        "profile", "trace", "debug", "log", "alert",
        "notify", "report", "dashboard", "observability", "coverage",
        "regression", "smoke test", "integration test", "unit test",
    ],
}

# Pre-compiled patterns: each keyword is matched as a whole word (\\b…\\b)
_CATEGORY_PATTERNS: Dict[str, List[Pattern[str]]] = {
    category: [re.compile(r"\b" + re.escape(kw) + r"\b", re.IGNORECASE) for kw in keywords]
    for category, keywords in _CATEGORY_KEYWORDS.items()
}

# ---------------------------------------------------------------------------
# IDI density-level thresholds
# ---------------------------------------------------------------------------

_DENSITY_THRESHOLDS: List[tuple[float, str]] = [
    (0.2, "very_low"),
    (0.4, "low"),
    (0.6, "moderate"),
    (0.8, "high"),
]


def _density_level(idi: float) -> str:
    """Map an IDI value in [0, 1] to its density level label."""
    for upper, level in _DENSITY_THRESHOLDS:
        if idi < upper:
            return level
    return "very_high"


# ---------------------------------------------------------------------------
# DensityScore data class
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DensityScore:
    """Immutable result of information-density analysis.

    Attributes:
        actionable_elements: Count of unique actionable keywords detected.
        total_tokens:        Total words/tokens in the input text.
        idi:                 Information Density Index (actionable / tokens),
                             clamped to [0, 1].
        density_level:       Human-readable tier — one of ``very_low``,
                             ``low``, ``moderate``, ``high``, ``very_high``.
        element_breakdown:   Per-category counts of unique keyword matches.
        scope_creep_warning: ``True`` when RS >= 3.0 **and** IDI < 0.3.
    """

    actionable_elements: int
    total_tokens: int
    idi: float
    density_level: str
    element_breakdown: Dict[str, int] = field(default_factory=dict)
    scope_creep_warning: bool = False


# ---------------------------------------------------------------------------
# InformationDensityEngine
# ---------------------------------------------------------------------------

class InformationDensityEngine:
    """Thread-safe engine that scores text for actionable information density.

    The engine tokenises input with a simple whitespace split, searches for
    unique keyword matches across six actionable-element categories, and
    produces a normalised IDI score.  An optional ``ResolutionScore`` enables
    scope-creep detection when the resolution is high but density is low.
    """

    def __init__(self) -> None:
        self._lock: threading.Lock = threading.Lock()
        self._total_scores: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def score(
        self,
        text: str,
        resolution_score: Optional[ResolutionScore] = None,
    ) -> DensityScore:
        """Score *text* for actionable information density.

        Args:
            text: Free-form input to analyse.
            resolution_score: Optional prior resolution score used to
                detect scope creep (RS >= 3.0 with IDI < 0.3).

        Returns:
            A ``DensityScore`` capturing counts, IDI, density level,
            per-category breakdown, and optional scope-creep warning.
        """
        lowered_text = text.lower()
        tokens = lowered_text.split()
        total_tokens = len(tokens)

        element_breakdown: Dict[str, int] = {}
        matched_keywords: set[str] = set()

        for category, keywords in _CATEGORY_KEYWORDS.items():
            category_matches: set[str] = set()
            for keyword, pattern in zip(keywords, _CATEGORY_PATTERNS[category]):
                if pattern.search(lowered_text):
                    category_matches.add(keyword)
            element_breakdown[category] = len(category_matches)
            matched_keywords.update(category_matches)

        actionable_elements = len(matched_keywords)

        if total_tokens > 0:
            idi = min(actionable_elements / total_tokens, 1.0)
        else:
            idi = 0.0

        idi = round(idi, 4)

        level = _density_level(idi)

        scope_creep = (
            resolution_score is not None
            and resolution_score.rs >= 3.0
            and idi < 0.3
        )

        result = DensityScore(
            actionable_elements=actionable_elements,
            total_tokens=total_tokens,
            idi=idi,
            density_level=level,
            element_breakdown=dict(element_breakdown),
            scope_creep_warning=scope_creep,
        )

        with self._lock:
            self._total_scores += 1
            logger.debug(
                "IDI score #%d: idi=%.4f level=%s actionable=%d tokens=%d scope_creep=%s",
                self._total_scores,
                idi,
                level,
                actionable_elements,
                total_tokens,
                scope_creep,
            )

        return result
