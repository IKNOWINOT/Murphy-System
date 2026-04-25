"""
Information Quality — Composite Quality Index Engine
=====================================================
Design Label : CQI-001
Owner        : Murphy System / Inoni LLC
Dependencies : resolution_scoring, information_density, structural_coherence
Purpose      : Aggregate resolution, density, and coherence scores into a single
               Composite Quality Index (CQI) with actionable recommendations and
               risk indicators.
Flow         : text ➜ RDE.score ➜ IDE.score ➜ SCE.score ➜ CQI + recommendation

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.information_density import DensityScore, InformationDensityEngine
from src.resolution_scoring import ResolutionDetectionEngine, ResolutionScore
from src.structural_coherence import CoherenceScore, StructuralCoherenceEngine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class InformationQuality:
    """Composite quality assessment produced by :class:`InformationQualityEngine`.

    Attributes:
        resolution_score: Resolution Score (RS) in the range 0–6.
        density_index: Information Density Index (IDI) in the range 0–1.
        coherence_score: Structural Coherence Score (SCS) in the range 0–6.
        iqs: Information Quality Sub-score — ``(RS + IDI×6) / 2``.
        cqi: Composite Quality Index — ``(RS + IDI×6 + SCS) / 3``.
        resolution_level: Resolution-maturity label (e.g. ``"RM0"``–``"RM6"``).
        risk_indicators: Human-readable warning strings.
        recommendation: One of ``"proceed"``, ``"clarify"``,
            ``"specify_further"``, or ``"block"``.
    """

    resolution_score: float
    density_index: float
    coherence_score: float
    iqs: float
    cqi: float
    resolution_level: str
    risk_indicators: List[str] = field(default_factory=list)
    recommendation: str = "clarify"


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class InformationQualityEngine:
    """Orchestrates resolution, density, and coherence engines to produce a
    single :class:`InformationQuality` assessment for a given text.

    Args:
        rde: A :class:`ResolutionDetectionEngine` instance.
        ide: A :class:`InformationDensityEngine` instance.
        sce: A :class:`StructuralCoherenceEngine` instance.
    """

    def __init__(
        self,
        rde: ResolutionDetectionEngine,
        ide: InformationDensityEngine,
        sce: StructuralCoherenceEngine,
    ) -> None:
        """Initialise the engine with the three sub-engines."""
        self._rde = rde
        self._ide = ide
        self._sce = sce

    # --------------------------------------------------------------------- #
    # Public API
    # --------------------------------------------------------------------- #

    def assess(
        self,
        text: str,
        context: Optional[Dict[str, object]] = None,
    ) -> InformationQuality:
        """Run a full composite quality assessment on *text*.

        Args:
            text: Free-form input to analyse.
            context: Optional metadata dict forwarded to the resolution and
                coherence sub-engines.

        Returns:
            An :class:`InformationQuality` dataclass containing scores,
            risk indicators, and a recommendation.
        """
        # Step 1 – Resolution
        res_score: ResolutionScore = self._rde.score(text, context)
        rs: float = res_score.rs
        logger.debug("RS=%.3f  level=%s", rs, res_score.resolution_level)

        # Step 2 – Information Density
        den_score: DensityScore = self._ide.score(text, res_score)
        idi: float = den_score.idi
        logger.debug("IDI=%.3f  scope_creep=%s", idi, den_score.scope_creep_warning)

        # Step 3 – Structural Coherence
        coh_score: CoherenceScore = self._sce.score(text, context)
        scs: float = coh_score.scs
        logger.debug("SCS=%.3f  contradictions=%d", scs, len(coh_score.contradictions))

        # Step 4 – Compute IQS and CQI
        iqs: float = (rs + idi * 6.0) / 2.0
        cqi: float = (rs + idi * 6.0 + scs) / 3.0

        # Step 5 – Base recommendation from CQI thresholds
        recommendation = self._recommendation_from_cqi(cqi)

        # Step 6 – Collect risk indicators and apply overrides
        risk_indicators: List[str] = self._collect_risk_indicators(
            den_score, coh_score, idi, scs,
        )

        if coh_score.contradictions:
            recommendation = "block"
        elif den_score.scope_creep_warning:
            recommendation = "specify_further"

        logger.info("CQI=%.3f  recommendation=%s", cqi, recommendation)

        # Step 7 – Build result
        return InformationQuality(
            resolution_score=rs,
            density_index=idi,
            coherence_score=scs,
            iqs=iqs,
            cqi=cqi,
            resolution_level=res_score.resolution_level.value,
            risk_indicators=risk_indicators,
            recommendation=recommendation,
        )

    # --------------------------------------------------------------------- #
    # Internal helpers
    # --------------------------------------------------------------------- #

    @staticmethod
    def _recommendation_from_cqi(cqi: float) -> str:
        """Map a CQI value to a base recommendation string.

        Args:
            cqi: Composite Quality Index in the range 0–6.

        Returns:
            ``"clarify"``, ``"specify_further"``, or ``"proceed"``.
        """
        if cqi < 1.5:
            return "clarify"
        if cqi < 3.0:
            return "specify_further"
        return "proceed"

    @staticmethod
    def _collect_risk_indicators(
        den_score: DensityScore,
        coh_score: CoherenceScore,
        idi: float,
        scs: float,
    ) -> List[str]:
        """Build a list of human-readable risk-indicator strings.

        Args:
            den_score: Density sub-score result.
            coh_score: Coherence sub-score result.
            idi: Information Density Index value.
            scs: Structural Coherence Score value.

        Returns:
            A list of warning strings (may be empty).
        """
        indicators: List[str] = []

        if den_score.scope_creep_warning:
            indicators.append(
                "Scope creep: high resolution but low information density"
            )

        if coh_score.contradictions:
            count = len(coh_score.contradictions)
            indicators.append(
                f"Contradictions detected: {count} conflicts found"
            )

        if coh_score.missing_elements:
            joined = ", ".join(coh_score.missing_elements)
            indicators.append(f"Missing elements: {joined}")

        if idi < 0.2:
            indicators.append("Very low information density")

        if scs < 2.0:
            indicators.append("Low structural coherence")

        return indicators
