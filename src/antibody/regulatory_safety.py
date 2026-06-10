"""PCR-090h — Regulatory safety classifier.

The antibody gate MUST NOT alter content that's part of a regulated chain:
  - Practitioner-attested engagement artifacts (CPA/PE/Attorney-stamped)
  - Documents in an active audit trail
  - Anything tagged with a compliance_class flag

Policy:
  - If response is being generated INTO an engagement folder past 'awaiting_attestation' state: REFUSE to alter
  - If response is part of a tax/SOX/HIPAA-classified workflow: REFUSE to alter
  - If response is plain operational text (chat, internal): PROCEED

Refused interventions are still LOGGED (passthrough + alert), so the
hallucination is recorded — we just don't auto-fix it. Founder + HITL
decides.
"""
import logging
import re
from typing import Dict, Any, Optional

LOG = logging.getLogger("murphy.antibody.regulatory")

# Tags that mean "do not touch"
_COMPLIANCE_TAGS = {
    "cpa_attestation", "pe_attestation", "attorney_attestation",
    "notary_attestation", "audit_response", "sox_filing",
    "tax_filing", "hipaa_phi", "regulated_disclosure",
    "engagement_final", "engagement_verified",
}

# Phrases in response text that suggest regulated content
_REGULATED_PHRASES = [
    r"\b(I|We)\s+(?:hereby\s+)?attest\b",
    r"\bunder\s+penalty\s+of\s+perjury\b",
    r"\bcertified\s+(?:true|correct|accurate)\b",
    r"\b(?:PE|CPA|Esq\.?|J\.D\.?)\s+(?:license|seal|stamp)\b",
    r"\bofficial\s+(?:filing|submission|disclosure)\b",
]
_REGULATED_RE = re.compile("|".join(_REGULATED_PHRASES), re.I)


def classify(
    response_text: str,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Decide if antibody is allowed to alter this response.
    
    Returns:
      {
        'verdict': 'safe' | 'compliance_tagged' | 'refused',
        'reason': str,
        'tags_matched': [str],
      }
    """
    context = context or {}
    tags = set(context.get("tags", []))
    matched = tags & _COMPLIANCE_TAGS
    if matched:
        return {
            "verdict": "refused",
            "reason": f"context has compliance tags: {sorted(matched)}",
            "tags_matched": sorted(matched),
        }
    # Engagement context past attestation = sacrosanct
    eng_state = context.get("engagement_state", "").lower()
    if eng_state in ("awaiting_attestation", "finalized", "verified"):
        return {
            "verdict": "refused",
            "reason": f"engagement state '{eng_state}' is post-attestation; chain-of-custody preserved",
            "tags_matched": [f"engagement_state:{eng_state}"],
        }
    # Heuristic: response text itself looks regulated
    if response_text and _REGULATED_RE.search(response_text):
        return {
            "verdict": "compliance_tagged",
            "reason": "response text matches regulated phrasing — passthrough + log + alert",
            "tags_matched": ["regulated_phrasing"],
        }
    return {"verdict": "safe", "reason": "no compliance markers found", "tags_matched": []}
