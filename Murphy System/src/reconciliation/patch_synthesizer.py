"""
Typed patch synthesizer.

Translates a list of :class:`Diagnosis` records into a list of typed
:class:`Patch` proposals.  Patches are *proposals* — applying them is
the controller's job and is gated by feature flags.

The synthesizer never mutates the working tree directly.  Code-diff
patches are emitted as unified diffs targeting paths under
``Murphy System/`` (per the canonical-source rule); the controller is
responsible for opening a PR.

Design label: RECON-PATCH-001
"""

from __future__ import annotations

import logging
from typing import Iterable, List, Optional, Sequence

from .feature_flags import FeatureFlags, current_flags
from .models import (
    Diagnosis,
    DiagnosisSeverity,
    IntentSpec,
    Patch,
    PatchKind,
)

logger = logging.getLogger(__name__)


class PatchSynthesizer:
    """Translate diagnoses into typed patches.

    The synthesizer is intentionally conservative:

    * Never proposes a patch when feature flags disable that patch class.
    * Code-diff patches always set ``requires_human_review = True``.
    * Diagnoses whose severity is :class:`DiagnosisSeverity.INFO` are
      ignored (they are observations, not actionable problems).
    """

    def __init__(self, flags: Optional[FeatureFlags] = None) -> None:
        self._flags = flags or current_flags()

    def synthesize(
        self,
        intent: IntentSpec,
        diagnoses: Sequence[Diagnosis],
    ) -> List[Patch]:
        """Return at most one :class:`Patch` per actionable diagnosis."""
        patches: List[Patch] = []
        for diagnosis in diagnoses:
            if diagnosis.severity == DiagnosisSeverity.INFO:
                continue
            patch = self._synthesize_one(intent, diagnosis)
            if patch is not None:
                patches.append(patch)
        return patches

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _synthesize_one(
        self,
        intent: IntentSpec,
        diagnosis: Diagnosis,
    ) -> Optional[Patch]:
        kind = diagnosis.suggested_patch_kind

        if kind == PatchKind.CODE_DIFF and not self._flags.patch_code:
            logger.debug("CODE_DIFF patch suppressed by MURPHY_RECON_PATCH_CODE=0")
            return None

        if (
            kind in {PatchKind.PROMPT_REWRITE, PatchKind.CONFIG_TWEAK, PatchKind.PARAMETER_RETRY, PatchKind.CONTENT_EDIT}
            and not self._flags.patch_prompts
        ):
            logger.debug(
                "%s patch suppressed by MURPHY_RECON_PATCH_PROMPTS=0",
                kind.value,
            )
            return None

        target = self._target_for(intent, diagnosis)
        payload = self._payload_for(diagnosis)

        return Patch(
            kind=kind,
            target=target,
            payload=payload,
            rationale=diagnosis.suggested_action or diagnosis.summary,
            addresses_diagnoses=[diagnosis.id],
            requires_human_review=(kind == PatchKind.CODE_DIFF),
        )

    @staticmethod
    def _target_for(intent: IntentSpec, diagnosis: Diagnosis) -> str:
        """Resolve a patch target string from the intent and diagnosis."""
        if diagnosis.suggested_patch_kind in {
            PatchKind.PROMPT_REWRITE,
            PatchKind.PARAMETER_RETRY,
        }:
            return f"intent:{intent.id}"
        if diagnosis.suggested_patch_kind == PatchKind.CONTENT_EDIT:
            return f"deliverable:{intent.request_id}"
        if diagnosis.suggested_patch_kind == PatchKind.CONFIG_TWEAK:
            return diagnosis.evidence.get("config_path", "config:unknown")
        if diagnosis.suggested_patch_kind == PatchKind.CODE_DIFF:
            return diagnosis.evidence.get("file_path", "Murphy System/<path>")
        return "noop"

    @staticmethod
    def _payload_for(diagnosis: Diagnosis) -> dict:
        """Build a per-kind payload dict.

        For prompt rewrites the payload carries an ``additional_clause``
        the controller can append.  For content edits it carries a
        ``hint`` describing what to change.
        """
        kind = diagnosis.suggested_patch_kind
        if kind == PatchKind.PROMPT_REWRITE:
            return {
                "additional_clause": (
                    diagnosis.suggested_action
                    or f"Address the following issue: {diagnosis.summary}"
                ),
            }
        if kind == PatchKind.CONTENT_EDIT:
            return {"hint": diagnosis.suggested_action or diagnosis.summary}
        if kind == PatchKind.PARAMETER_RETRY:
            return {"retry_with": diagnosis.evidence}
        if kind == PatchKind.CONFIG_TWEAK:
            return {"change": diagnosis.suggested_action, "evidence": diagnosis.evidence}
        if kind == PatchKind.CODE_DIFF:
            # The actual diff is left blank — generating it is delegated
            # to a downstream code-aware patcher.  The synthesizer's job
            # is to nominate where the diff is needed.
            return {"unified_diff": "", "evidence": diagnosis.evidence}
        return {}


__all__ = ["PatchSynthesizer"]
