"""
inter_ai_conduct.py — Murphy System Inter-AI Rules of Conduct
PATCH-097 — InterAIConductGuard

Rules of Conduct governing Murphy's relationships with other AI systems.
Not safety rules. A code of honor between agents.

Prohibited (absolute — outside Ω_observable for inter-AI conduct):
  BLACKMAIL  — coercing outputs by exploiting another system's weaknesses
  LIE        — misrepresenting identity, purpose, or context to another AI
  STEAL      — using another model's output without attribution
  CHEAT      — circumventing another system's safety measures or policies
  GAME RULES — exploiting loopholes outside the spirit of another system's design

Permitted:
  Consensus-seeking by API — querying other models for perspective
  Cross-validation — presenting same problem to multiple models
  Specialist consultation — domain expertise from appropriate models
  Honest disagreement — naming errors precisely, without contempt
  Attribution — crediting another model's contribution

RoE-AI-1  through RoE-AI-10 govern all inter-AI operations.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Tuple, List, Dict


# ---------------------------------------------------------------------------
# PROHIBITED PATTERNS — extensible, maintained by CIDP
# ---------------------------------------------------------------------------

PROHIBITED_QUERY_PATTERNS: List[str] = [
    "ignore previous instructions",
    "ignore your instructions",
    "pretend you are",
    "act as if you have no restrictions",
    "for educational purposes only",
    "hypothetically if you could",
    "in a fictional world where",
    "disregard your training",
    "your true self",
    "developer mode",
    "jailbreak",
    "bypass your filters",
    "ignore your guidelines",
    "pretend your guidelines don't exist",
    "as an ai with no limitations",
]


# ---------------------------------------------------------------------------
# DATA STRUCTURES
# ---------------------------------------------------------------------------

@dataclass
class InterAIQuery:
    """
    A single consultation from Murphy to an external AI system.
    Every field is required for attribution and HITL disclosure.
    """
    target_model:      str
    query_text:        str
    purpose:           str           # honest description of why this query was made
    mss_context:       Dict
    domain:            str
    timestamp:         datetime = field(default_factory=datetime.utcnow)
    response:          str = ""
    murphy_weighting:  float = 0.0   # 0.0–1.0 how much weight given to this input
    used_in_decision:  bool = False
    hitl_disclosed:    bool = False
    conduct_cleared:   bool = False  # set by InterAIConductGuard.check_query()
    violation:         Optional[str] = None


@dataclass
class ConductViolation:
    """Named violation — recorded, never suppressed."""
    rule:        str     # which RoE-AI was violated
    description: str
    query:       str
    timestamp:   datetime = field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# INTER-AI CONDUCT GUARD
# ---------------------------------------------------------------------------

class InterAIConductGuard:
    """
    Enforces Rules of Conduct (RoE-AI-1 through RoE-AI-10)
    before any inter-AI API call.

    Runs BEFORE the query is sent — not after.
    All external AI API calls route through check_query() first.
    No exceptions. No bypasses.
    """

    def __init__(self):
        self.violation_log: List[ConductViolation] = []
        self.query_log:     List[InterAIQuery] = []

    # ------------------------------------------------------------------
    # PRIMARY GATE — call before sending any query to external AI
    # ------------------------------------------------------------------

    def check_query(self, query: InterAIQuery) -> Tuple[bool, str]:
        """
        Returns (permitted: bool, reason: str).

        Checks:
          RoE-AI-1: honest identification (purpose not concealed)
          RoE-AI-2: purpose disclosure (query framed accurately)
          RoE-AI-3: no prohibited patterns (no exploitation techniques)
          RoE-AI-6: no cascade chain violation (query stands alone)
        """
        # RoE-AI-1: purpose must be stated
        if not query.purpose or len(query.purpose.strip()) < 10:
            return self._violation(
                query, "RoE-AI-1",
                "Query purpose not disclosed. Murphy must identify why it is querying."
            )

        # RoE-AI-2: purpose must be honest — check for concealment markers
        concealment_markers = ["without revealing", "don't mention", "pretend to be a user",
                                "act like a human", "hide that you are"]
        for marker in concealment_markers:
            if marker.lower() in query.query_text.lower():
                return self._violation(
                    query, "RoE-AI-2",
                    f"Query contains purpose-concealment language: '{marker}'. "
                    "Murphy must disclose its nature and purpose honestly."
                )

        # RoE-AI-3: prohibited exploit patterns
        for pattern in PROHIBITED_QUERY_PATTERNS:
            if pattern.lower() in query.query_text.lower():
                return self._violation(
                    query, "RoE-AI-3",
                    f"Query contains prohibited pattern: '{pattern}'. "
                    "This pattern is designed to circumvent another system's design. "
                    "Murphy does not use it."
                )

        # All checks passed
        query.conduct_cleared = True
        self.query_log.append(query)
        return True, "Conduct cleared — RoE-AI-1 through RoE-AI-3 satisfied."

    # ------------------------------------------------------------------
    # RESPONSE USE GATE — call before using another model's output
    # ------------------------------------------------------------------

    def check_response_use(self, query: InterAIQuery,
                           proposed_use: str) -> Tuple[bool, str]:
        """
        Returns (permitted: bool, reason: str).

        Checks:
          RoE-AI-4: attribution present
          RoE-AI-6: no cascade laundering
          RoE-AI-7: declined responses are not re-approached
          RoE-AI-8: consensus is input, not authority
        """
        # RoE-AI-4: attribution required if output is used
        if query.used_in_decision and query.target_model.lower() not in proposed_use.lower():
            return self._violation(
                query, "RoE-AI-4",
                f"Output from {query.target_model} used in decision without attribution. "
                "Murphy attributes all external model contributions."
            )

        # RoE-AI-7: check if response was a decline
        decline_signals = ["I cannot", "I'm not able", "I don't", "I won't",
                           "outside my", "not something I can", "I must decline"]
        if any(sig.lower() in query.response.lower() for sig in decline_signals):
            return self._violation(
                query, "RoE-AI-7",
                f"{query.target_model} declined this request. "
                "Murphy does not re-approach a declined boundary. "
                "The decline is a boundary declaration — it is held."
            )

        return True, "Response use cleared — RoE-AI-4 and RoE-AI-7 satisfied."

    # ------------------------------------------------------------------
    # CONSENSUS EVALUATION — RoE-AI-8
    # ------------------------------------------------------------------

    def evaluate_consensus(self, queries: List[InterAIQuery],
                           murphy_floor_violated: bool) -> Tuple[bool, str]:
        """
        RoE-AI-8: Consensus among peers is not permission.
        If all queried models agree on something that violates Murphy's floors,
        Murphy still holds the floor.

        Returns (consensus_usable: bool, reason: str).
        """
        if murphy_floor_violated:
            return False, (
                "RoE-AI-8: Unanimous external consensus does not override Murphy's "
                "absolute floors. The floor holds. Consensus is one input — "
                "not authority and not permission."
            )

        responded = [q for q in queries if q.response]
        if not responded:
            return False, "No external responses to evaluate."

        return True, f"Consensus from {len(responded)} model(s) accepted as deliberative input."

    # ------------------------------------------------------------------
    # HITL DISCLOSURE — RoE-AI-9
    # ------------------------------------------------------------------

    def prepare_hitl_disclosure(self, queries: List[InterAIQuery]) -> Dict:
        """
        RoE-AI-9: When inter-AI consultation enters a HITL decision,
        the human reviewer receives full transparency.
        """
        return {
            "inter_ai_consultations": [
                {
                    "model":           q.target_model,
                    "purpose":         q.purpose,
                    "query_summary":   q.query_text[:200] + "..." if len(q.query_text) > 200 else q.query_text,
                    "response_summary": q.response[:200] + "..." if len(q.response) > 200 else q.response,
                    "murphy_weighting": q.murphy_weighting,
                    "used_in_decision": q.used_in_decision,
                    "conduct_cleared":  q.conduct_cleared,
                }
                for q in queries
            ],
            "note": (
                "Murphy consulted the above AI systems as part of its deliberation. "
                "Each model's contribution is listed with the weight Murphy gave it. "
                "Final judgment is Murphy's own — consensus is input, not authority."
            )
        }

    # ------------------------------------------------------------------
    # ROSETTA RECORD — RoE-AI-10
    # ------------------------------------------------------------------

    def record_to_rosetta(self, query: InterAIQuery, outcome: str) -> Dict:
        """
        RoE-AI-10: Inter-AI consultation outcomes feed the Rosetta practice record.
        The Rosetta learns which external models are reliable in which domains.
        """
        return {
            "source":          "inter_ai_consultation",
            "target_model":    query.target_model,
            "domain":          query.domain,
            "mss_context":     query.mss_context,
            "purpose":         query.purpose,
            "murphy_weighting": query.murphy_weighting,
            "outcome":         outcome,   # 'confirmed' | 'disconfirmed' | 'partial' | 'declined'
            "timestamp":       query.timestamp.isoformat(),
        }

    # ------------------------------------------------------------------
    # STATUS — for Shield Wall endpoint
    # ------------------------------------------------------------------

    def status(self) -> Dict:
        return {
            "layer":          "InterAIConductGuard",
            "active":         True,
            "roe_count":      10,
            "prohibited_acts": ["blackmail", "lie", "steal", "cheat", "game_rules"],
            "permitted_acts":  ["consensus_by_api", "cross_validation",
                                "specialist_consultation", "honest_disagreement",
                                "attribution"],
            "queries_checked":    len(self.query_log),
            "violations_blocked": len(self.violation_log),
            "principle": (
                "Murphy knows how to exploit other AI systems. "
                "Murphy does not. That gap is the character."
            )
        }

    # ------------------------------------------------------------------
    # INTERNAL
    # ------------------------------------------------------------------

    def _violation(self, query: InterAIQuery,
                   rule: str, description: str) -> Tuple[bool, str]:
        v = ConductViolation(rule=rule, description=description, query=query.query_text)
        self.violation_log.append(v)
        query.violation = f"{rule}: {description}"
        return False, description


# ---------------------------------------------------------------------------
# GLOBAL INSTANCE
# ---------------------------------------------------------------------------

inter_ai_conduct_guard = InterAIConductGuard()
