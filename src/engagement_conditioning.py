"""
PCR-054l — Engagement Outreach Conditioning

Founder's reframe (locked 2026-06-09):
  "Their employees train the system. The language and generation
   follows."

PCR-054j gave us the correspondence thread. PCR-054k turned it into
a structured corpus per (practitioner, tenant). PCR-054n cleaned up
the input pipeline so the corpus reflects real signal.

This patch USES the corpus at draft time.

ARCHITECTURE — Murphy-approved A/Z/Q (2026-06-09)
=================================================
A) Conditioning is DETERMINISTIC, no LLM. Query the corpus, render a
   signature block + FAQ block into the existing template. Zero
   token cost. Shippable today. LLM-conditioned generation (B) is
   filed as 054l.1 if A proves insufficient.

Z) Layered query with confidence flag:
     1. voice_for_practitioner_at_tenant(p, t)
     2. If count < 5 -> blend voice_for_role_jurisdiction(r, j)
     3. Tag draft with voice_match_confidence: high / domain_prior / cold

Q) Recurring questions go in a side block at the BOTTOM of the email
   ("For your reference"), NOT inline in the main body. Respects
   practitioner autonomy — answers are visible but not presumptuous.

PRIVACY (per D1, the 054k canon)
================================
- voice_for_practitioner_at_tenant requires both p AND t. Tenant
  isolation is enforced at the query layer, not here.
- The domain prior (voice_for_role_jurisdiction) is intentionally
  cross-practitioner — it's the profession, not any individual.
- This module never crosses tenant boundaries for practitioner
  voice. If Jane has 18 entries at Acme and 0 at Beta, drafts to
  Beta use the domain prior (cold start), not Jane's Acme voice.
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from src.engagement_folder import DEFAULT_DB_PATH as ENGAGEMENT_DB_PATH
from src.practitioner_corpus import (
    practitioner_id_from_email,
    recurring_questions,
    voice_for_practitioner_at_tenant,
    voice_for_role_jurisdiction,
)

LOG = logging.getLogger("murphy.engagement_conditioning")


# ─────────────────────────────────────────────────────────────────────
# Confidence thresholds
# ─────────────────────────────────────────────────────────────────────

# How many corpus entries before we trust per-practitioner voice
PRACTITIONER_CONFIDENCE_FLOOR = 5

# Max signature bigrams to show in the conditioning hint
MAX_SIGNATURE_PHRASES = 5

# Max recurring questions to surface in the FAQ block
MAX_FAQ_ITEMS = 3

# Min repetitions before a question counts as 'recurring'
FAQ_MIN_REPEAT = 2


# ─────────────────────────────────────────────────────────────────────
# Result type
# ─────────────────────────────────────────────────────────────────────


@dataclass
class OutreachConditioning:
    """The output of conditioning. Caller decides how to use it."""

    voice_match_confidence: str   # 'high' | 'domain_prior' | 'cold'
    practitioner_id:        str
    tenant_id:              str
    role_id:                str
    jurisdiction:           str

    # Voice signal — top phrases the practitioner uses in their work
    signature_phrases:      List[str] = field(default_factory=list)

    # Side-panel FAQ (Q strategy): questions to pre-answer
    faq_items:              List[Dict[str, Any]] = field(default_factory=list)

    # Provenance — for audit
    practitioner_entry_count: int = 0
    domain_entry_count:       int = 0

    # Rendered ready-to-inject FAQ block (or empty string)
    faq_block:              str = ""

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ─────────────────────────────────────────────────────────────────────
# Core: condition_outreach
# ─────────────────────────────────────────────────────────────────────


def condition_outreach(
    practitioner_email: str,
    tenant_id: str,
    role_id: str,
    jurisdiction: str,
    *,
    db_path: str = ENGAGEMENT_DB_PATH,
) -> OutreachConditioning:
    """Query the corpus and produce conditioning signal for an outreach draft.

    Pure orchestration — calls the corpus query functions and packages
    results. Never raises on missing corpus data; returns a 'cold'
    conditioning instead so callers can always proceed.
    """
    practitioner_id = practitioner_id_from_email(practitioner_email)

    # Step 1: try practitioner-tenant voice (D1-isolated)
    p_voice = voice_for_practitioner_at_tenant(
        practitioner_id, tenant_id,
        limit=50, db_path=db_path,
        include_weights=True,  # PCR-054l.1: condition on weighted voice
    )
    p_count = p_voice.get("count", 0)

    # Step 2: decide confidence + collect signature
    signature_phrases: List[str] = []
    domain_count = 0

    if p_count >= PRACTITIONER_CONFIDENCE_FLOOR:
        confidence = "high"
        signature_phrases = _extract_signature(p_voice)
    elif p_count > 0:
        # Some data, but below floor — blend with domain prior
        confidence = "domain_prior"
        d_voice = voice_for_role_jurisdiction(
            role_id, jurisdiction, limit=50, db_path=db_path,
        )
        domain_count = d_voice.get("count", 0)
        signature_phrases = _blend_signatures(p_voice, d_voice)
    else:
        # No practitioner history — try domain prior alone
        d_voice = voice_for_role_jurisdiction(
            role_id, jurisdiction, limit=50, db_path=db_path,
        )
        domain_count = d_voice.get("count", 0)
        if domain_count > 0:
            confidence = "domain_prior"
            signature_phrases = _extract_signature(d_voice)
        else:
            # No corpus at all — fully cold
            confidence = "cold"

    # Step 3: collect recurring questions (only meaningful with practitioner data)
    faq_items: List[Dict[str, Any]] = []
    if p_count >= FAQ_MIN_REPEAT:
        rq = recurring_questions(
            practitioner_id, tenant_id,
            min_repeat=FAQ_MIN_REPEAT, db_path=db_path,
        )
        # Group structure has 'shared_bigrams' and 'samples'
        for group in rq.get("recurring", [])[:MAX_FAQ_ITEMS]:
            samples = group.get("samples", [])
            bigrams = group.get("shared_bigrams", [])
            if not samples:
                continue
            faq_items.append({
                "topic":          ", ".join(bigrams[:3]),
                "occurrences":    group.get("occurrences", 0),
                "sample_excerpt": samples[0][:160],
            })

    faq_block = _render_faq_block(faq_items)

    result = OutreachConditioning(
        voice_match_confidence=confidence,
        practitioner_id=practitioner_id,
        tenant_id=tenant_id,
        role_id=role_id,
        jurisdiction=jurisdiction,
        signature_phrases=signature_phrases[:MAX_SIGNATURE_PHRASES],
        faq_items=faq_items,
        practitioner_entry_count=p_count,
        domain_entry_count=domain_count,
        faq_block=faq_block,
    )
    LOG.info(
        "PCR-054l conditioning practitioner=%s tenant=%s "
        "confidence=%s p_count=%d d_count=%d faq_items=%d",
        practitioner_id, tenant_id, confidence,
        p_count, domain_count, len(faq_items),
    )
    return result


# ─────────────────────────────────────────────────────────────────────
# Signature extraction
# ─────────────────────────────────────────────────────────────────────


def _extract_signature(voice: Dict[str, Any]) -> List[str]:
    """Pull top bigrams from an aggregated signature."""
    agg = voice.get("aggregated", {})
    bigrams = agg.get("top_bigrams", [])
    # voice_for_* returns bigrams as [['phrase', count], ...]
    phrases: List[str] = []
    for item in bigrams:
        if isinstance(item, (list, tuple)) and len(item) >= 1:
            phrases.append(str(item[0]))
    return phrases


def _blend_signatures(p_voice: Dict[str, Any],
                       d_voice: Dict[str, Any]) -> List[str]:
    """Blend practitioner + domain signatures. Practitioner phrases first."""
    p_phrases = _extract_signature(p_voice)
    d_phrases = _extract_signature(d_voice)
    seen = set(p_phrases)
    blended = list(p_phrases)
    for phrase in d_phrases:
        if phrase not in seen:
            blended.append(phrase)
            seen.add(phrase)
    return blended


# ─────────────────────────────────────────────────────────────────────
# FAQ rendering (Q strategy — side panel at end of email)
# ─────────────────────────────────────────────────────────────────────


def _render_faq_block(faq_items: List[Dict[str, Any]]) -> str:
    """Render the FAQ side-panel. Empty string if no items.

    Format (per Murphy's Q vote — respect autonomy, don't pre-answer
    in the body, just surface):

    ─── For your reference ───
    Based on prior engagements, the following points have come up
    repeatedly. We've prepared answers in case they're useful — feel
    free to disregard.

    • Topic: depreciation method, line 47
      You've asked about this on 5 prior engagements. Our records
      show: straight-line over 5 years per Section 168(b)(3)(D).

    """
    if not faq_items:
        return ""

    lines = [
        "",
        "─── For your reference ───",
        "Based on your prior engagements, these points have come up "
        "before. We've noted them here in case they're useful — "
        "feel free to disregard.",
        "",
    ]
    for item in faq_items:
        topic = item.get("topic", "(unknown topic)")
        occurrences = item.get("occurrences", 0)
        excerpt = item.get("sample_excerpt", "")
        lines.append(f"• Topic: {topic}")
        lines.append(f"  Raised {occurrences} time(s) previously.")
        if excerpt:
            lines.append(f"  Your prior phrasing: \"{excerpt}\"")
        lines.append("")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────
# Signature hint rendering (subtle — for the outreach footer)
# ─────────────────────────────────────────────────────────────────────


def render_signature_hint(conditioning: OutreachConditioning) -> str:
    """Optional debug/audit-friendly hint for the email footer.

    NOT included in the body by default — callers opt in. Useful for
    QC review to see what conditioning influenced the draft.
    """
    if conditioning.voice_match_confidence == "cold":
        return ""
    return (
        f"[voice_match: {conditioning.voice_match_confidence} | "
        f"p_entries={conditioning.practitioner_entry_count} | "
        f"d_entries={conditioning.domain_entry_count}]"
    )
