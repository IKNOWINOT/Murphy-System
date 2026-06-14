"""
Ship 31ba.INTENT_GATE — classify whether an inbound stranger email is
asking for a deliverable, just chatting, mimicking a doc, or filling a form.

Founder direction 2026-06-13: do NOT produce attachments or pseudo-documents
unless the correspondent explicitly asked for one.
"""
import re
from typing import Literal, Dict

Intent = Literal[
    "conversational",   # plain question, no work product expected
    "deliverable",      # asked for a doc / quote / analysis / draft / plan
    "mimic_document",   # 'make me a doc that looks like this'
    "fill_form",        # 'fill out this blank form'
]


# Words/phrases that ASK for a deliverable
_DELIVERABLE_TRIGGERS = [
    r"\b(send|attach|create|generate|draft|prepare|produce|write|build|make)\s+(me\s+)?(a\s+)?(doc|document|pdf|word|spreadsheet|sheet|deck|slide|proposal|quote|estimate|invoice|contract|report|brief|memo|plan|analysis|summary|letter|email\s+template|template)",
    r"\b(quote|estimate|proposal|contract|invoice|spec|specification|drawing|schematic|blueprint)\s+(for|on)\b",
    r"\bcan you (draw up|put together|knock together|cobble together)\b",
    r"\b(write up|put together|spin up|knock up|throw together)\b",
    r"\bi need (a|an)\s+(quote|estimate|proposal|spec|doc|document|pdf|report|plan)",
    r"\battach(ed)? (a|the) (doc|document|pdf|report|file|spreadsheet)",
    r"\bdeliverable\b",
]

# Mimic phrases — user wants doc that looks like something
_MIMIC_TRIGGERS = [
    r"\b(make|create|write|draft)\s+.*(look|style|format)(ed)?\s+like\b",
    r"\b(in the style of|formatted like|mimic(king|s)?|copy the format|match the format|same format as|like this (one|sample|example|document))\b",
    r"\bbased on (the|this) (attached|sample|example|template)\b",
    r"\bin the same style\b",
]

# Form-fill phrases — user wants blank filled in
_FORM_FILL_TRIGGERS = [
    r"\b(fill|complete|populate)\s+(in|out)?\s+(this|the|attached|blank)?\s*(form|template|document|pdf|application|w-?9|w-?2|w-?4|i-?9|1099|invoice|order|po|application)",
    r"\b(here'?s|here is) (a|the|my) (blank|empty|template|form)\b",
    r"\bcomplete (this|the) (form|template|application|document)\b",
]


def classify_intent(subject: str, body: str, has_attachment: bool = False) -> Dict:
    """Return {intent, confidence, matched_phrase, wants_attachment}."""
    text = ((subject or "") + " " + (body or "")).lower()

    # Check form-fill first (most specific)
    for pattern in _FORM_FILL_TRIGGERS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return {
                "intent": "fill_form",
                "confidence": 0.92 if has_attachment else 0.75,
                "matched": m.group(0)[:80],
                "wants_attachment": True,
                "reason": "Detected form-fill request" + (
                    " with attachment" if has_attachment else " (no attachment yet)"
                ),
            }

    # Then mimic (also specific)
    for pattern in _MIMIC_TRIGGERS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return {
                "intent": "mimic_document",
                "confidence": 0.90 if has_attachment else 0.70,
                "matched": m.group(0)[:80],
                "wants_attachment": True,
                "reason": "Detected style-mimicry request" + (
                    " with reference doc" if has_attachment else " (no reference yet)"
                ),
            }

    # Then deliverable
    for pattern in _DELIVERABLE_TRIGGERS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return {
                "intent": "deliverable",
                "confidence": 0.85,
                "matched": m.group(0)[:80],
                "wants_attachment": True,
                "reason": "Detected explicit deliverable request",
            }

    # Default: pure conversation
    return {
        "intent": "conversational",
        "confidence": 0.95,
        "matched": "",
        "wants_attachment": False,
        "reason": (
            "No deliverable trigger phrase found — treating as conversational. "
            "Reply will be a considered prose answer with NO attachment and NO pseudo-document."
        ),
    }


# Self-test if run directly
if __name__ == "__main__":
    cases = [
        ("Hi Murphy", "Quick question about what you can do.",          "conversational"),
        ("Quote please", "Can you send me a quote on a 4-ton chiller.", "deliverable"),
        ("RFQ", "Need a proposal for pump replacement next month.",     "deliverable"),
        ("Form attached", "Please fill out this W-9 and send it back.", "fill_form"),
        ("Sample doc",   "Make me a contract that looks like the attached.", "mimic_document"),
        ("Help",         "What's the deal with HVAC compressors?",       "conversational"),
        ("Generate",     "Generate a report on indoor air quality codes for Texas.", "deliverable"),
    ]
    for subj, body, expected in cases:
        r = classify_intent(subj, body, has_attachment=False)
        mark = "✅" if r["intent"] == expected else "❌"
        print(f"  {mark} '{subj}' → {r['intent']:16} (expected {expected:16}) — {r['reason'][:60]}")
