"""
Extract first-class constraints (capital, timeline, headcount) from a
free-form request and attach them to downstream :class:`IntentSpec`s.

The original prompt that motivated this module —

    "we have 3k in capital ... clear goals for the first year ...
     reasonable for a one man operation"

— mentions $3,000, a 12-month horizon, and a 1-person team.  Today
those are treated as ordinary words.  This module turns them into
typed values so any downstream evaluator (cost gate, deadline gate,
team-size sanity check) can consult them.

CITL / HITL boundary
====================

* **CITL OK** — *extracting* the constraints, normalising units,
  attaching them to an intent spec, surfacing them in the dashboard,
  rejecting plans that exceed the stated cap as a soft warning.
* **HITL required** — actually *spending* the capital, *committing*
  to the deadline externally, or *hiring* against the headcount.
  No automation may treat an extracted constraint as authorisation.

Design label: BUDGET-001
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# Capital — captures "$3k", "$3,000", "3000 USD", "USD 3000", "3 million".
# Not bullet-proof, but covers the shapes we actually see in user prompts.
_MONEY_RE = re.compile(
    r"""
    (?P<currency>\$|USD|EUR|GBP|€|£)?            # optional currency symbol/code
    \s*
    (?P<amount>\d{1,3}(?:[,]\d{3})+|\d+(?:\.\d+)?)  # 3,000  or  3  or  3.5
    \s*
    (?P<scale>k|m|million|thousand|bn|billion)?\b  # optional scale (whole word)
    (?:\s*(?P<currency2>USD|EUR|GBP))?           # trailing currency code
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Timeline — captures "first year", "6 months", "30 days", "by Q2", "in 2 weeks".
_TIMELINE_RE = re.compile(
    r"""
    (?:
        (?:first|next|in|within|over\s+the\s+next)\s+
        (?P<n1>\d+|a|one|two|three|four|six|twelve)\s+
        (?P<unit1>day|days|week|weeks|month|months|year|years)
      | (?:by|before)\s+Q(?P<quarter>[1-4])
      | (?:first|next)\s+(?P<unit2>year|month|quarter|week)
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Headcount — "one-man", "solo", "two-person", "team of 3".
_HEADCOUNT_RE = re.compile(
    r"""
    (?:
        (?P<solo>(?:one[\-\s](?:man|person)|solo|by\s+myself|single[\-\s]operator))
      | (?:team\s+of\s+(?P<n>\d+))
      | (?:(?P<n2>\d+)[\-\s]person\s+team)
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

_NUMBER_WORDS = {
    "a": 1, "one": 1, "two": 2, "three": 3, "four": 4,
    "six": 6, "twelve": 12,
}
_UNIT_DAYS = {
    "day": 1, "days": 1,
    "week": 7, "weeks": 7,
    "month": 30, "months": 30,
    "quarter": 90,
    "year": 365, "years": 365,
}


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Constraints:
    """Typed constraints extracted from a request."""

    capital_usd: Optional[float] = None
    timeline_days: Optional[int] = None
    headcount: Optional[int] = None
    raw_capital_phrase: Optional[str] = None
    raw_timeline_phrase: Optional[str] = None
    raw_headcount_phrase: Optional[str] = None

    @property
    def has_any(self) -> bool:
        return any((self.capital_usd, self.timeline_days, self.headcount))

    def to_dict(self) -> dict:
        return {
            "capital_usd": self.capital_usd,
            "timeline_days": self.timeline_days,
            "headcount": self.headcount,
            "raw_capital_phrase": self.raw_capital_phrase,
            "raw_timeline_phrase": self.raw_timeline_phrase,
            "raw_headcount_phrase": self.raw_headcount_phrase,
        }


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------


class ConstraintExtractor:
    """Pull capital, timeline, and headcount constraints out of free text."""

    def extract(self, text: str) -> Constraints:
        if not text or not text.strip():
            return Constraints()

        capital, capital_phrase = self._extract_capital(text)
        timeline, timeline_phrase = self._extract_timeline(text)
        headcount, headcount_phrase = self._extract_headcount(text)

        return Constraints(
            capital_usd=capital,
            timeline_days=timeline,
            headcount=headcount,
            raw_capital_phrase=capital_phrase,
            raw_timeline_phrase=timeline_phrase,
            raw_headcount_phrase=headcount_phrase,
        )

    # ------------------------------------------------------------------

    @staticmethod
    def _extract_capital(text: str) -> tuple[Optional[float], Optional[str]]:
        # Treat a money match as capital only when it carries either a
        # currency symbol/code OR a scale suffix (k, m, million, ...).
        # A bare integer near "have"/"budget" is ambiguous ("have 3 phases")
        # — we'd rather miss it than hallucinate capital.
        for m in _MONEY_RE.finditer(text):
            phrase = m.group(0).strip()
            currency = (m.group("currency") or m.group("currency2") or "").strip()
            scale = (m.group("scale") or "").lower()
            if not currency and not scale:
                continue
            try:
                raw = m.group("amount").replace(",", "")
                amount = float(raw)
            except (TypeError, ValueError):
                continue
            if scale in ("k", "thousand"):
                amount *= 1_000
            elif scale in ("m", "million"):
                amount *= 1_000_000
            elif scale in ("bn", "billion"):
                amount *= 1_000_000_000
            return amount, phrase
        return None, None

    @staticmethod
    def _extract_timeline(text: str) -> tuple[Optional[int], Optional[str]]:
        m = _TIMELINE_RE.search(text)
        if not m:
            return None, None
        phrase = m.group(0).strip()

        if m.group("quarter"):
            # "by Q2" → days from start of fiscal year (approx).
            return int(m.group("quarter")) * 90, phrase

        if m.group("n1") and m.group("unit1"):
            n_raw = m.group("n1").lower()
            n = _NUMBER_WORDS.get(n_raw)
            if n is None:
                try:
                    n = int(n_raw)
                except ValueError:
                    return None, phrase
            unit = m.group("unit1").lower()
            return n * _UNIT_DAYS.get(unit, 1), phrase

        if m.group("unit2"):
            return _UNIT_DAYS.get(m.group("unit2").lower(), 1), phrase

        return None, phrase

    @staticmethod
    def _extract_headcount(text: str) -> tuple[Optional[int], Optional[str]]:
        m = _HEADCOUNT_RE.search(text)
        if not m:
            return None, None
        phrase = m.group(0).strip()
        if m.group("solo"):
            return 1, phrase
        for grp in ("n", "n2"):
            if m.group(grp):
                try:
                    return int(m.group(grp)), phrase
                except ValueError:
                    return None, phrase
        return None, phrase


__all__ = ["Constraints", "ConstraintExtractor"]
