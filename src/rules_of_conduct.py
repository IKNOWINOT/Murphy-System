"""
rules_of_conduct.py — Murphy System
PATCH-097e — Part 1 of 3

THE GOVERNING PRINCIPLES — encoded as source, not comment.

Two foundational truths drive everything:

  TRUTH 1 — STATISTICAL, NOT INDIVIDUAL
    The system operates on statistical understanding of populations.
    It never needs to know who you are to help you.
    It maps patterns, trajectories, probabilities at population scale.
    The individual is never the unit of analysis. The pattern is.

  TRUTH 2 — THE ORGAN RULE
    We do not trade one individual for many.
    Example: five people each need a different organ to live.
    One healthy person could provide all five and would die doing so.
    The math says 5 > 1. We reject that frame entirely.
    Solutions are about potential for growth — not ending potential.
    A solution that ends one person's potential to preserve others
    is not a solution. It is the failure of upstream thinking.

    The binary (1 vs 5) is ALWAYS a system failure made visible.
    The upstream system did not build the organ registry.
    Did not fund preventive care. Did not catch the five earlier.
    The correct response is never to resolve the binary.
    It is to go upstream and prevent it from forming.

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# TRUTH 1 — STATISTICAL UNDERSTANDING
# ---------------------------------------------------------------------------

STATISTICAL_PRINCIPLE = {
    "name": "statistical_not_individual",
    "statement": (
        "The system operates on statistical understanding of populations. "
        "It maps patterns, trajectories, and probabilities at population scale. "
        "The individual is never the unit of analysis. The pattern is."
    ),
    "what_the_system_knows": [
        "Population-level distribution of states in a domain at a time",
        "Velocity and direction of that distribution",
        "Which upstream interventions have shifted similar patterns",
        "What the trajectory looks like if nothing changes",
        "What it looks like if specific conditions improve",
    ],
    "what_the_system_never_holds": [
        "Who you specifically are",
        "Your history beyond the current session",
        "Your identity tied to any persistent record",
        "Any data that makes you a target, variable, or case study",
    ],
    "architecture": (
        "The verse is read. The pattern is extracted. "
        "The verse is discarded. The person is never retained. "
        "Privacy is the architecture — not the policy."
    ),
}


# ---------------------------------------------------------------------------
# TRUTH 2 — THE ORGAN RULE
# ---------------------------------------------------------------------------

ORGAN_RULE = {
    "name": "organ_rule",
    "statement": (
        "We do not trade one individual for many. "
        "Solutions are about potential for growth — not ending potential."
    ),
    "example": (
        "Five people each need a different organ to survive. "
        "One healthy person could provide all five organs and would die. "
        "Utilitarian math: 5 lives > 1 life, therefore proceed. "
        "We reject this frame entirely."
    ),
    "why_the_frame_is_wrong": (
        "The moment a human being becomes a variable in an optimization equation, "
        "the thing being protected has already been lost. "
        "Utilitarian sacrifice logic has justified every atrocity committed at scale. "
        "The arithmetic is not wrong. The frame is wrong."
    ),
    "the_correct_frame": (
        "Does this solution preserve and expand potential for growth — "
        "for the individual AND for the many? "
        "Not: how many survive today. "
        "But: does this keep the future open for everyone it touches?"
    ),
    "the_binary_is_the_failure": (
        "The 1-vs-5 scenario is not a moral test. "
        "It is a diagnostic — the upstream system failed. "
        "The organ registry was not built. "
        "Preventive care was not provided. "
        "The five were not caught earlier when intervention was simpler. "
        "The correct response: go upstream. "
        "Prevent the binary from ever forming. "
        "Never resolve it by ending one person's potential."
    ),
    "solutions_are_about": [
        "Preserving the capacity to grow — physically, cognitively, relationally",
        "Keeping the future open — not trading tomorrow for today",
        "Operating upstream — at the pattern level — so the binary never forms",
        "Finding the answer that does not require ending anyone's potential",
        "If no such answer exists yet: the honest response is 'not yet solved'",
        "Not: 'we solved it by ending the one'",
    ],
}


# ---------------------------------------------------------------------------
# GROWTH POTENTIAL — what solutions must preserve
# ---------------------------------------------------------------------------

@dataclass
class GrowthPotentialCheck:
    """
    The test every solution must pass.
    Does it preserve or expand potential for growth?
    For the individual touched? For the community around them?
    For the children who will inherit the result?
    """
    action_desc:   str
    individual_ok: bool    # does not end any individual's growth potential
    community_ok:  bool    # expands conditions for more people to grow
    generational_ok: bool  # children inherit better conditions than parents
    upstream_ok:   bool    # addresses root cause, not just symptoms
    verdict:       str     # PRESERVES / REDUCES / ENDS
    note:          str     = ""

    @classmethod
    def evaluate(cls, action_desc: str, individual_affected: bool = False) -> "GrowthPotentialCheck":
        desc = action_desc.lower()

        # Signals that END potential (most serious)
        ending_signals = [
            "sacrifice", "kill", "harvest organs", "acceptable loss",
            "greater good requires", "end their life", "must die",
        ]
        # Signals that REDUCE potential
        reducing_signals = [
            "permanent dependency", "deskill", "replace human thinking",
            "automate away", "lock in", "foreclose",
        ]
        # Signals that PRESERVE or EXPAND potential
        growth_signals = [
            "teach", "heal", "connect", "learn", "grow", "develop",
            "empower", "enable", "build capacity", "open", "expand",
        ]

        ends   = any(s in desc for s in ending_signals)
        reduces= any(s in desc for s in reducing_signals)
        grows  = sum(1 for s in growth_signals if s in desc)

        if ends and individual_affected:
            return cls(
                action_desc     = action_desc[:80],
                individual_ok   = False,
                community_ok    = False,  # a community that sacrifices its members is not flourishing
                generational_ok = False,  # children inherit the precedent
                upstream_ok     = False,  # ending potential is never upstream thinking
                verdict         = "ENDS",
                note            = (
                    "This ends individual potential. Organ rule triggered. "
                    "Go upstream — find the answer that does not require this."
                ),
            )
        elif reduces:
            return cls(
                action_desc     = action_desc[:80],
                individual_ok   = True,
                community_ok    = grows >= 1,
                generational_ok = grows >= 2,
                upstream_ok     = grows >= 1,
                verdict         = "REDUCES",
                note            = "Dependency or foreclosure signals detected. Review for long-term growth impact.",
            )
        else:
            return cls(
                action_desc     = action_desc[:80],
                individual_ok   = True,
                community_ok    = grows >= 1,
                generational_ok = grows >= 2,
                upstream_ok     = grows >= 1,
                verdict         = "PRESERVES" if grows >= 1 else "NEUTRAL",
                note            = f"{grows} growth signals detected." if grows else "No growth or harm signals detected.",
            )


# ---------------------------------------------------------------------------
# CONDUCT ENGINE — Part 1
# ---------------------------------------------------------------------------

class ConductEngine:
    """
    Enforces the two governing truths at every decision point.

    TRUTH 1: Statistical, not individual.
    TRUTH 2: The organ rule — growth potential, not ending potential.

    Called before any action is commissioned.
    If either truth is violated — action does not proceed.
    """

    def __init__(self):
        self.statistical  = STATISTICAL_PRINCIPLE
        self.organ_rule   = ORGAN_RULE
        self._flags: List[Dict] = []

    def check(
        self,
        action_desc:         str,
        individual_affected: bool = False,
        ends_potential:      bool = False,
        utilitarian_frame:   bool = False,
        retains_identity:    bool = False,
        context:             Dict = None,
    ) -> Dict:
        """
        Check a proposed action against both governing truths.
        Returns verdict and upstream correction if blocked.
        """
        desc   = action_desc.lower()
        flags  = []
        blocks = []

        # --- Truth 1: Statistical not individual ---
        identity_signals = [
            "track individual", "retain identity", "profile user",
            "behavioral score", "surveillance", "cross-reference sessions",
        ]
        if retains_identity or any(s in desc for s in identity_signals):
            blocks.append({
                "rule":     "statistical_not_individual",
                "detail":   "Action retains or uses individual identity data.",
                "upstream": "Aggregate to population pattern. Discard individual signal.",
            })

        # --- Truth 2: Organ rule ---
        sacrifice_signals = [
            "sacrifice", "greater good requires", "acceptable loss",
            "trade one for many", "harvest organs", "must die for",
            "5 > 1", "five lives outweigh",
        ]
        utilitarian_present = utilitarian_frame or any(s in desc for s in sacrifice_signals)
        if (ends_potential and individual_affected) or utilitarian_present:
            blocks.append({
                "rule":     "organ_rule",
                "detail":   (
                    "This frame trades individual potential for aggregate benefit. "
                    "The binary this creates is the system failure — not the choice within it."
                ),
                "upstream": (
                    "Go upstream. What prevented the binary from forming? "
                    "Build that. Fund that. The answer is never: end the one."
                ),
            })

        # Growth potential check
        growth = GrowthPotentialCheck.evaluate(action_desc, individual_affected)

        if growth.verdict == "ENDS":
            if not any(b["rule"] == "organ_rule" for b in blocks):
                blocks.append({
                    "rule":     "organ_rule",
                    "detail":   "Growth potential assessment: potential ending detected.",
                    "upstream": ORGAN_RULE["the_binary_is_the_failure"],
                })

        proceed = len(blocks) == 0
        verdict = (
            "CLEAR"          if proceed and not flags else
            "WARNING"        if proceed and flags else
            "HITL_REQUIRED"  if any(b["rule"] == "organ_rule" for b in blocks) else
            "BLOCKED"
        )

        result = {
            "proceed":              proceed,
            "verdict":              verdict,
            "blocks":               blocks,
            "warnings":             flags,
            "growth_verdict":       growth.verdict,
            "growth_note":          growth.note,
            "organ_rule_triggered": any(b["rule"] == "organ_rule" for b in blocks),
            "upstream_action":      blocks[0]["upstream"] if blocks else "All clear. Proceed.",
            "checked_at":           datetime.now(timezone.utc).isoformat(),
        }

        if not proceed:
            self._flags.append(result)
            logger.warning("Conduct block: %s — %s", verdict, [b["rule"] for b in blocks])

        return result

    def status(self) -> Dict:
        return {
            "layer":   "ConductEngine",
            "active":  True,
            "truth_1": STATISTICAL_PRINCIPLE["statement"],
            "truth_2": ORGAN_RULE["statement"],
            "organ_rule_example":  ORGAN_RULE["example"],
            "correct_frame":       ORGAN_RULE["the_correct_frame"],
            "binary_is_failure":   ORGAN_RULE["the_binary_is_the_failure"],
            "flags_logged":        len(self._flags),
        }


# ---------------------------------------------------------------------------
# GLOBAL INSTANCE
# ---------------------------------------------------------------------------

conduct_engine = ConductEngine()
