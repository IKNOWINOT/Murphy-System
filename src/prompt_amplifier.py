"""
Prompt Amplifier — MMMS→Solidify filter applied to every incoming request.

Every raw prompt entering the Murphy System is run through three Magnify passes
(expand fully — no ambiguity), one Simplify pass (compress to essence — kill
noise), then Solidify (lock the actionable request).  The solidified output
becomes the internal request that Murphy acts on.

This filter serves two purposes:
  1. Clarify user intent   — ambiguous prompts are resolved, missing components
     are surfaced, scope is sharpened.
  2. Protect internal quality — Murphy never acts on vague input; the MMMS gate
     ensures every downstream operation has a clean, well-scoped foundation.

Sequence: M → M → M → S → Solidify  (vs. MMSMM which is used for generation)

Design Label: NBG-PA-001
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from inference_gate_engine import InferenceDomainGateEngine
from mss_controls import MSSController, TransformationResult

logger = logging.getLogger(__name__)

#: The sequence used for prompt amplification (different from generation's MMSMM)
AMPLIFIER_SEQUENCE: str = "MMMS"

#: Minimum meaningful prompt length to amplify
_MIN_PROMPT_LENGTH: int = 5


@dataclass
class AmplifiedPrompt:
    """Result of running a raw prompt through the MMMS→Solidify amplifier.

    The ``amplified_prompt`` is the solidified output — the clean, scoped,
    actionable version of the user's original request that Murphy acts on.
    """
    original_prompt: str
    amplified_prompt: str                   # solidified output — Murphy acts on this
    magnify_results: List[TransformationResult]   # the 3 M passes
    simplify_result: Optional[TransformationResult]  # the S pass
    solidified_result: Optional[TransformationResult]  # the final Solidify
    components_discovered: int              # components found across the 3 M passes
    noise_removed_pct: float                # % token reduction in the S pass
    original_length: int
    amplified_length: int
    expansion_ratio: float                  # amplified_length / original_length
    confidence: float                       # solidified result quality score
    processing_metadata: Dict[str, Any]
    amplified_at: str


class PromptAmplifier:
    """
    MMMS→Solidify filter applied to every incoming request before Murphy processes it.

    Raw user input → M → M → M → S → Solidify → clean internal request.

    The three Magnify passes surface all components, requirements, architecture,
    and compliance concerns.  The Simplify pass prunes noise and keeps only the
    strongest signal.  Solidify locks the scoped, actionable request.

    Murphy NEVER processes a raw unamplifed prompt for any niche generation,
    RFP analysis, or viability gate operation.  Every request goes through this
    filter first.

    Args:
        mss_controller: Fully-initialised :class:`MSSController`.
        inference_engine: Fully-initialised :class:`InferenceDomainGateEngine`.
    """

    def __init__(
        self,
        mss_controller: MSSController,
        inference_engine: InferenceDomainGateEngine,
    ) -> None:
        self._controller = mss_controller
        self._inference_engine = inference_engine

    def amplify(
        self,
        raw_prompt: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AmplifiedPrompt:
        """Run *raw_prompt* through the MMMS→Solidify amplification pipeline.

        Args:
            raw_prompt: The user's original prompt or request text.
            context: Optional context dictionary passed to MSSController operations.

        Returns:
            An :class:`AmplifiedPrompt` — ``amplified_prompt`` is what Murphy
            acts on internally.
        """
        if not raw_prompt or len(raw_prompt.strip()) < _MIN_PROMPT_LENGTH:
            # Too short to amplify meaningfully — return as-is
            return self._passthrough(raw_prompt)

        ctx = context or {}
        magnify_results: List[TransformationResult] = []
        current_text = raw_prompt.strip()

        # ---- Three Magnify passes ----
        for pass_num in range(1, 4):
            try:
                result = self._controller.magnify(current_text, **ctx)
                magnify_results.append(result)
                current_text = self._extract_output(result, current_text)
                logger.debug("Amplifier M%d: %d chars", pass_num, len(current_text))
            except Exception as exc:
                logger.warning("Amplifier M%d failed: %s", pass_num, exc)
                break

        # ---- Simplify pass — prune noise, keep signal ----
        simplify_result: Optional[TransformationResult] = None
        text_before_simplify = current_text
        try:
            simplify_result = self._controller.simplify(current_text, **ctx)
            current_text = self._extract_output(simplify_result, current_text)
            logger.debug("Amplifier S: %d chars", len(current_text))
        except Exception as exc:
            logger.warning("Amplifier S failed: %s", exc)

        # ---- Solidify — lock the actionable request ----
        solidified_result: Optional[TransformationResult] = None
        try:
            solidified_result = self._controller.solidify(current_text, **ctx)
            current_text = self._extract_output(solidified_result, current_text)
            logger.debug("Amplifier Solidify: %d chars", len(current_text))
        except Exception as exc:
            logger.warning("Amplifier Solidify failed: %s", exc)

        # ---- Metrics ----
        original_len = len(raw_prompt)
        amplified_len = len(current_text)
        expansion_ratio = round(amplified_len / (original_len or 1), 3)

        # Noise removed = how much the S pass reduced the text
        pre_s_len = len(text_before_simplify)
        post_s_len = len(self._extract_output(simplify_result, text_before_simplify)) if simplify_result else pre_s_len
        noise_removed_pct = round(
            max(0.0, (pre_s_len - post_s_len) / (pre_s_len or 1)) * 100.0, 1
        )

        components_discovered = self._count_components(magnify_results)

        confidence = self._extract_confidence(solidified_result)

        return AmplifiedPrompt(
            original_prompt=raw_prompt,
            amplified_prompt=current_text,
            magnify_results=magnify_results,
            simplify_result=simplify_result,
            solidified_result=solidified_result,
            components_discovered=components_discovered,
            noise_removed_pct=noise_removed_pct,
            original_length=original_len,
            amplified_length=amplified_len,
            expansion_ratio=expansion_ratio,
            confidence=confidence,
            processing_metadata={
                "sequence": AMPLIFIER_SEQUENCE,
                "magnify_passes": len(magnify_results),
                "simplify_performed": simplify_result is not None,
                "solidify_performed": solidified_result is not None,
                "context_keys": list(ctx.keys()),
            },
            amplified_at=datetime.now(timezone.utc).isoformat(),
        )

    def amplify_for_niche(
        self,
        raw_prompt: str,
        niche_description: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AmplifiedPrompt:
        """Amplify a prompt in the context of a specific niche description.

        Combines the raw prompt with niche context before amplification so
        the Magnify passes surface niche-specific components and requirements.

        Args:
            raw_prompt: The user's original prompt.
            niche_description: The niche business description for context.
            context: Optional extra context.

        Returns:
            An :class:`AmplifiedPrompt` scoped to the niche.
        """
        combined = f"{niche_description.strip()} — {raw_prompt.strip()}"
        return self.amplify(combined, context)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _passthrough(self, raw_prompt: str) -> AmplifiedPrompt:
        """Return a no-op amplification for very short prompts."""
        return AmplifiedPrompt(
            original_prompt=raw_prompt,
            amplified_prompt=raw_prompt,
            magnify_results=[],
            simplify_result=None,
            solidified_result=None,
            components_discovered=0,
            noise_removed_pct=0.0,
            original_length=len(raw_prompt),
            amplified_length=len(raw_prompt),
            expansion_ratio=1.0,
            confidence=0.5,
            processing_metadata={"sequence": "passthrough"},
            amplified_at=datetime.now(timezone.utc).isoformat(),
        )

    @staticmethod
    def _extract_output(
        result: Optional[TransformationResult],
        fallback: str,
    ) -> str:
        """Extract usable text from a TransformationResult."""
        if result is None:
            return fallback
        # Try standard attributes in order of preference
        for attr in ("amplified_text", "simplified_text", "output_text", "text"):
            val = getattr(result, attr, None)
            if val and isinstance(val, str) and val.strip():
                return val.strip()
        # Try description / summary fields
        for attr in ("description", "summary", "content"):
            val = getattr(result, attr, None)
            if val and isinstance(val, str) and val.strip():
                return val.strip()
        return fallback

    @staticmethod
    def _count_components(magnify_results: List[TransformationResult]) -> int:
        """Count total components discovered across all magnify passes."""
        total = 0
        for result in magnify_results:
            # Try various component count attributes
            for attr in ("component_count", "components", "total_components"):
                val = getattr(result, attr, None)
                if isinstance(val, int):
                    total = max(total, val)
                    break
        return total

    @staticmethod
    def _extract_confidence(result: Optional[TransformationResult]) -> float:
        """Extract the confidence/quality score from a solidified result."""
        if result is None:
            return 0.5
        for attr in ("quality_score", "confidence", "resolution_score", "overall_score"):
            val = getattr(result, attr, None)
            if isinstance(val, float) and 0.0 <= val <= 1.0:
                return val
        # Try nested quality objects
        quality = getattr(result, "output_quality", None) or getattr(result, "quality", None)
        if quality is not None:
            for attr in ("resolution_score", "confidence", "overall_score"):
                val = getattr(quality, attr, None)
                if isinstance(val, float) and 0.0 <= val <= 1.0:
                    return val
        return 0.7
