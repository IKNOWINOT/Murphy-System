"""
Resolution Detection Engine — Deterministic Resolution Scoring

Design Label: RDE-001 — Resolution Maturity Classification
Owner: Core Platform
Dependencies:
  - None (standalone module)

Purpose:
  Scores free-text input across five orthogonal dimensions of resolution
  maturity (D1–D5) using deterministic keyword/pattern matching.  The
  composite Resolution Score (RS) maps to a Resolution Level (RM0–RM6)
  that classifies the input from raw concept through implementation to
  exploratory R&D.

Flow:
  1. Receive text (and optional context dict).
  2. Compute SHA-256 hash as cache key.
  3. Score each dimension independently (highest-match-first).
  4. Compute RS = mean(D1..D5), derive RM level.
  5. Return immutable ResolutionScore; cache for determinism.

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Deterministic: no randomness, no LLM calls
  - Bounded: LRU cache, configurable limit
  - Idempotent: identical inputs always yield identical outputs

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import collections
import hashlib
import logging
import re
import threading
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ResolutionLevel(str, Enum):
    """Resolution Maturity level from concept (RM0) to exploratory R&D (RM6)."""

    RM0 = "RM0"  # Concept — idea or question
    RM1 = "RM1"  # Category — domain classification
    RM2 = "RM2"  # Requirements — feature list
    RM3 = "RM3"  # Technical specification — engineering description
    RM4 = "RM4"  # Architecture design — system layout
    RM5 = "RM5"  # Implementation — module specification
    RM6 = "RM6"  # Exploratory R&D — innovation analysis


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResolutionScore:
    """Immutable result of resolution scoring across five dimensions.

    Each dimension is scored 0–6.  ``rs`` is the arithmetic mean of all
    five dimensions and ``resolution_level`` is the corresponding RM tier.
    """

    d1_concept_clarity: float
    d2_structural_detail: float
    d3_operational_logic: float
    d4_implementation_readiness: float
    d5_evidence_validation: float
    rs: float
    resolution_level: ResolutionLevel
    input_hash: str


# ---------------------------------------------------------------------------
# Keyword / pattern tables  (scored highest → lowest)
# ---------------------------------------------------------------------------

# Each entry is (score, list_of_patterns).  Patterns are compiled at import
# time so the hot path only executes ``re.search``.

_PatternTable = List[Tuple[int, List[re.Pattern[str]]]]


def _compile_table(rows: List[Tuple[int, List[str]]]) -> _PatternTable:
    """Compile a list of ``(score, [raw_pattern, ...])`` into regex objects."""
    compiled: _PatternTable = []
    for score, patterns in rows:
        compiled.append(
            (score, [re.compile(p, re.IGNORECASE) for p in patterns])
        )
    return compiled


# D1 — Concept Clarity
_D1_TABLE: _PatternTable = _compile_table([
    (6, [
        r"\bhypothesis\b", r"\bexperiment\b", r"\bnovel\b",
        r"\bresearch\b", r"\binvestigate whether\b",
        r"\bcompare approaches\b",
        # RM6 Exploratory trigger signals
        r"\bdiscovery\b", r"\bunexplored\b",
        r"\bnew approach\b", r"\barbitrage\b",
    ]),
    (5, [
        r"\bmodule\b", r"\bclass\b", r"\bfunction\b",
        r"\bapi endpoint\b", r"\bservice method\b", r"\bdeploy\b",
    ]),
    (4, [
        r"\bsystem\b", r"\bplatform\b", r"\binfrastructure\b",
        r"\benterprise\b", r"\barchitecture\b", r"\bend-to-end\b",
    ]),
    (3, [
        r"\breduce by\b", r"\bincrease to\b", r"\bachieve\b",
        r"\boptimize for\b", r"\btarget\b", r"\bpercentage\b",
        r"\bwithin\b",
    ]),
    (2, [
        r"\bcreate\b", r"\bbuild\b", r"\bdevelop\b",
        r"\bimplement\b", r"\bdesign\b",
    ]),
    (1, [
        r"\bimprove\b", r"\bhelp\b", r"\bmake better\b",
        r"\bwant\b",
    ]),
])

# D2 — Structural Detail
_D2_COMPONENT_PATTERN: re.Pattern[str] = re.compile(
    r"\b(?:module|service|engine|controller|manager|handler|component|subsystem)\b",
    re.IGNORECASE,
)

_D2_TABLE: _PatternTable = _compile_table([
    (6, [
        r"\bnovel architecture\b", r"\bnew paradigm\b",
        r"\bexperimental design\b", r"\bcustom framework\b",
        # Utopia Map vocabulary
        r"\bcircular supply chain\b", r"\bregenerative\b",
        r"\bwaste recovery\b", r"\bnet positive\b",
    ]),
    # Level 5 is checked programmatically (>5 named components).
    (4, [
        r"\bfrontend\b", r"\bbackend\b", r"\bdatabase\b",
        r"\bcache\b", r"\bqueue\b", r"\bload balancer\b",
        r"\bgateway\b", r"\bmicroservice\b",
    ]),
    (3, [
        r"\blayer\b", r"\btier\b", r"\bpipeline\b",
        r"\bstage\b", r"\bphase\b", r"\bsubsystem\b",
    ]),
    # Level 2 is checked programmatically (≥2 component keywords).
    (1, [
        r"\bfinance\b", r"\bhealthcare\b", r"\blogistics\b",
        r"\bmanufacturing\b", r"\bretail\b", r"\beducation\b",
        r"\binsurance\b", r"\btelecommunications\b",
        r"\benergy\b", r"\btransportation\b",
    ]),
])

# D3 — Operational Logic
_D3_TABLE: _PatternTable = _compile_table([
    (6, [
        r"\bexperimental\b", r"\bcontrol group\b", r"\bvariable\b",
        r"\bhypothesis test\b", r"\ba/b test\b", r"\btrial\b",
    ]),
    (5, [
        r"\bworkflow\b", r"\borchestration\b", r"\bchoreography\b",
    ]),
    (4, [
        r"\bflow\b", r"\bpipeline\b", r"\bdag\b",
        r"\bparallel\b", r"\bconcurrent\b", r"\basync\b",
        r"\bsequence diagram\b", r"\bstate machine\b",
    ]),
    (3, [
        r"\bif\b", r"\bthen\b", r"\belse\b", r"\bwhen\b",
        r"\bunless\b", r"\bcondition\b", r"\botherwise\b",
        r"\bcase\b",
    ]),
    (2, [
        r"\bfirst\b", r"\bthen\b", r"\bnext\b", r"\bafter\b",
        r"\bfinally\b", r"\bstep\b", r"\bfollowed by\b",
    ]),
])

# D4 — Implementation Readiness
_D4_TABLE: _PatternTable = _compile_table([
    (6, [
        r"\bprototype\b", r"\bproof of concept\b", r"\bpoc\b",
        r"\bmvp\b", r"\bspike\b", r"\biteration plan\b",
    ]),
    (5, [
        r"\binstall\b", r"\bconfigure\b", r"\bdeploy\b",
        r"\bbuild\b", r"\bcompile\b", r"\bpackage\b",
        r"\bmigration\b", r"\bci/cd\b",
    ]),
    (4, [
        r"\bclass\b", r"\bmethod signature\b",
        r"\binput/output spec\b", r"\bdata model\b",
        r"\breturn type\b",
    ]),
    (3, [
        r"\bapi\b", r"\bendpoint\b", r"\binterface\b",
        r"\bprotocol\b", r"\bschema\b", r"\bcontract\b",
        r"\brest\b", r"\bgraphql\b",
    ]),
    (2, [
        r"\bpython\b", r"\bfastapi\b", r"\breact\b",
        r"\bpostgresql\b", r"\bdocker\b", r"\bkubernetes\b",
        r"\bjava\b", r"\btypescript\b", r"\bgo\b",
        r"\brust\b", r"\bterraform\b", r"\baws\b",
        r"\bgcp\b", r"\bazure\b", r"\bnode\b",
    ]),
    (1, [
        r"\btool\b", r"\bframework\b", r"\blibrary\b",
        r"\bsdk\b", r"\bserver\b", r"\bclient\b",
        r"\bdatabase\b", r"\bcloud\b",
    ]),
])

# D5 — Evidence / Validation
_D5_TABLE: _PatternTable = _compile_table([
    (6, [
        r"\bbenchmark\b", r"\bdataset\b", r"\bpublished\b",
        r"\bpeer-reviewed\b", r"\bstatistical analysis\b",
        r"\bp-value\b",
    ]),
    (5, [
        r"\btest plan\b", r"\bqa\b", r"\bmonitoring\b",
        r"\balerting\b", r"\bobservability\b", r"\bdashboard\b",
        r"\bcoverage\b",
        # Environmental performance signals
        r"\benvironmental performance\b", r"\bnet positive impact\b",
        r"\bsocial impact\b", r"\bcarbon neutral\b",
    ]),
    (4, [
        r"\blatency\b", r"\bthroughput\b", r"\buptime\b",
        r"\baccuracy\b", r"\bprecision\b", r"\brecall\b",
        r"\bp99\b", r"\bslo\b",
    ]),
    (3, [
        r"\btest\b", r"\bassert\b", r"\bverify\b",
        r"\bcheck\b", r"\bvalidate\b", r"\bunit test\b",
        r"\bintegration test\b",
    ]),
    (2, [
        r"\brequirement\b", r"\bspec\b", r"\buser story\b",
        r"\bacceptance criteria\b", r"\bsla\b",
    ]),
    (1, [
        r"\bshould work\b", r"\bexpected to\b",
        r"\bprobably\b", r"\blikely\b",
    ]),
])


# D3 helper patterns (compiled once at module level)
_D3_STEP_PATTERN: re.Pattern[str] = re.compile(
    r"\b(?:step\s*\d|first|second|third|fourth|fifth|"
    r"then|next|after that|finally|followed by)\b",
    re.IGNORECASE,
)

_D3_ACTION_VERB_PATTERN: re.Pattern[str] = re.compile(
    r"\b(?:run|execute|send|process|fetch|compute|call|start|stop|read|write)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------


def _match_table(text: str, table: _PatternTable) -> int:
    """Return the highest matching score from *table*, or ``0``."""
    for score, patterns in table:
        for pat in patterns:
            if pat.search(text):
                return score
    return 0


def _score_d1(text: str) -> float:
    """Score D1 — Concept Clarity."""
    return float(_match_table(text, _D1_TABLE))


def _score_d2(text: str) -> float:
    """Score D2 — Structural Detail."""
    # Level 6 — novel structure keywords
    for pat in _D2_TABLE[0][1]:  # score-6 row is first
        if pat.search(text):
            return 6.0

    # Level 5 — more than 5 named components
    component_matches = _D2_COMPONENT_PATTERN.findall(text)
    if len(component_matches) > 5:
        return 5.0

    # Level 4 — architecture layer keywords
    for pat in _D2_TABLE[1][1]:  # score-4 row
        if pat.search(text):
            return 4.0

    # Level 3 — subsystem breakdown keywords
    for pat in _D2_TABLE[2][1]:  # score-3 row
        if pat.search(text):
            return 3.0

    # Level 2 — two or more component keywords
    if len(component_matches) >= 2:
        return 2.0

    # Level 1 — domain mentioned
    for pat in _D2_TABLE[3][1]:  # score-1 row
        if pat.search(text):
            return 1.0

    return 0.0


def _score_d3(text: str) -> float:
    """Score D3 — Operational Logic.

    Level 5 additionally requires 5+ ordered steps described *or* an
    orchestration keyword; the keyword check is in the table, so we also
    count step indicators for the quantitative part.
    """
    # Check level 6 first
    for pat in _D3_TABLE[0][1]:
        if pat.search(text):
            return 6.0

    # Level 5 — keyword or 5+ step indicators
    for pat in _D3_TABLE[1][1]:
        if pat.search(text):
            return 5.0

    if len(_D3_STEP_PATTERN.findall(text)) >= 5:
        return 5.0

    # Levels 4, 3, 2
    for score, patterns in _D3_TABLE[2:]:
        for pat in patterns:
            if pat.search(text):
                return float(score)

    # Level 1 — any action verb present
    if _D3_ACTION_VERB_PATTERN.search(text):
        return 1.0

    return 0.0


def _score_d4(text: str) -> float:
    """Score D4 — Implementation Readiness."""
    return float(_match_table(text, _D4_TABLE))


def _score_d5(text: str) -> float:
    """Score D5 — Evidence / Validation."""
    return float(_match_table(text, _D5_TABLE))


def _rs_to_level(rs: float) -> ResolutionLevel:
    """Map a composite Resolution Score to a Resolution Level."""
    if rs >= 6.0:
        return ResolutionLevel.RM6
    if rs >= 5.0:
        return ResolutionLevel.RM5
    if rs >= 4.0:
        return ResolutionLevel.RM4
    if rs >= 3.0:
        return ResolutionLevel.RM3
    if rs >= 2.0:
        return ResolutionLevel.RM2
    if rs >= 1.0:
        return ResolutionLevel.RM1
    return ResolutionLevel.RM0


# ---------------------------------------------------------------------------
# Public engine
# ---------------------------------------------------------------------------


class ResolutionDetectionEngine:
    """Deterministic, thread-safe engine that scores text resolution maturity.

    Scores are cached by SHA-256 hash so repeated calls with identical
    input are O(1) after the first evaluation.
    """

    def __init__(self, *, cache_limit: int = 4096) -> None:
        """Initialise the engine.

        Args:
            cache_limit: Maximum number of cached scores.  When exceeded
                the least-recently-used entry is evicted.
        """
        self._cache: collections.OrderedDict[str, ResolutionScore] = (
            collections.OrderedDict()
        )
        self._lock: threading.Lock = threading.Lock()
        self._cache_limit: int = cache_limit

    # -- public API ---------------------------------------------------------

    def score(self, text: str, context: Optional[Dict[str, object]] = None) -> ResolutionScore:
        """Score *text* across all five resolution dimensions.

        Args:
            text: Free-form input to evaluate.
            context: Optional metadata dict (reserved for future use).

        Returns:
            A frozen :class:`ResolutionScore` dataclass.
        """
        input_hash = hashlib.sha256(text.encode()).hexdigest()

        with self._lock:
            if input_hash in self._cache:
                self._cache.move_to_end(input_hash)
                logger.debug("Cache hit for hash %s", input_hash[:12])
                return self._cache[input_hash]

        # Scoring is done outside the lock — it is pure and deterministic.
        lower_text = text.lower()

        d1 = _score_d1(lower_text)
        d2 = _score_d2(lower_text)
        d3 = _score_d3(lower_text)
        d4 = _score_d4(lower_text)
        d5 = _score_d5(lower_text)

        rs = round((d1 + d2 + d3 + d4 + d5) / 5.0, 4)
        level = _rs_to_level(rs)

        result = ResolutionScore(
            d1_concept_clarity=d1,
            d2_structural_detail=d2,
            d3_operational_logic=d3,
            d4_implementation_readiness=d4,
            d5_evidence_validation=d5,
            rs=rs,
            resolution_level=level,
            input_hash=input_hash,
        )

        with self._lock:
            self._maybe_evict()
            self._cache[input_hash] = result

        logger.info(
            "Scored text (hash=%s): RS=%.2f → %s",
            input_hash[:12],
            rs,
            level.value,
        )
        return result

    def detect_level(self, text: str) -> ResolutionLevel:
        """Convenience method returning only the resolution level.

        Args:
            text: Free-form input to evaluate.

        Returns:
            The :class:`ResolutionLevel` for the given text.
        """
        return self.score(text).resolution_level

    # -- internals ----------------------------------------------------------

    def _maybe_evict(self) -> None:
        """Evict least-recently-used entries when cache limit is exceeded."""
        while len(self._cache) >= self._cache_limit:
            evicted_key, _ = self._cache.popitem(last=False)
            logger.debug("Evicted cache entry %s", evicted_key[:12])
