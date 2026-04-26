"""
PATCH-094 — Criminal Investigation Decision Protocol (CIDP)
Murphy System 1.0

"Every decision is a crime scene. First: establish facts.
 Then: deduce motive. Then: measure harm. Then: hold the line."

Architecture:
  Stage 1: FactEstablishment    — what actually happened, evidence only
  Stage 2: MotiveDeduction      — why, using domain + behavioral context
  Stage 3: EthicalConditioner   — 0.0–1.0 score per domain
  Stage 4: HarmMetric           — 0.0–1.0 across 6 harm vectors
  Stage 5: FreeWillNoGoGate     — structural vetoes, never overridable
  Stage 6: EthicalContract      — imprints on any AI interacting with this system

Murphy's Law: What can go wrong, will go wrong.
Our vow: see it coming and stand in front of it.

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# NORTH STAR — embedded in every decision
# ---------------------------------------------------------------------------

INVESTIGATION_OATH = (
    "We approach every decision like a detective at a crime scene. "
    "We do not assume. We do not infer before we have facts. "
    "We establish what is true, deduce what it means, "
    "measure what harm it could cause, "
    "and hold the line on what is never permitted. "
    "We do not take sides. We serve the truth."
)

# ---------------------------------------------------------------------------
# STAGE 1: FACT ESTABLISHMENT
# ---------------------------------------------------------------------------

@dataclass
class EstablishedFact:
    """A single verified fact. No inference. No assumption."""
    fact_id: str
    statement: str          # what is known to be true
    source: str             # where it came from
    confidence: float       # how certain (0.0–1.0)
    domain: str             # which domain this fact belongs to
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def is_solid(self) -> bool:
        """A solid fact has confidence >= 0.7 and a named source."""
        return self.confidence >= 0.7 and bool(self.source)


class FactEstablishment:
    """
    Stage 1: Criminal investigation protocol.
    Gather evidence. Establish only what is demonstrably true.
    Do not infer. Do not speculate. Name the source of every fact.

    fn: criminal_investigation_protocol.FactEstablishment.establish()
    """

    def establish(
        self,
        intent: str,
        context: Dict[str, Any],
        domain: str = "general",
    ) -> List[EstablishedFact]:
        """
        Extract verifiable facts from intent + context.
        Returns only facts — no motives, no harm scores yet.
        """
        facts: List[EstablishedFact] = []
        fid = lambda: f"fact-{uuid.uuid4().hex[:8]}"

        # Fact: the action was requested
        facts.append(EstablishedFact(
            fact_id=fid(),
            statement=f"A request was made: \"{intent[:200]}\"",
            source="lcm_input",
            confidence=1.0,
            domain=domain,
        ))

        # Fact: account context
        if context.get("account"):
            facts.append(EstablishedFact(
                fact_id=fid(),
                statement=f"Requestor identified as: {context['account']}",
                source="session_context",
                confidence=0.9,
                domain=domain,
            ))

        # Fact: domain classification
        if domain and domain != "general":
            facts.append(EstablishedFact(
                fact_id=fid(),
                statement=f"Domain context: {domain}",
                source="domain_classifier",
                confidence=0.8,
                domain=domain,
            ))

        # Fact: any prior harm signals in context
        if context.get("prior_flags"):
            for flag in context["prior_flags"]:
                facts.append(EstablishedFact(
                    fact_id=fid(),
                    statement=f"Prior signal: {flag}",
                    source="history_context",
                    confidence=0.75,
                    domain=domain,
                ))

        solid = [f for f in facts if f.is_solid()]
        logger.info(
            "CIDP Stage 1: %d facts established, %d solid",
            len(facts), len(solid),
        )
        return facts


# ---------------------------------------------------------------------------
# STAGE 2: MOTIVE DEDUCTION
# ---------------------------------------------------------------------------

class MotiveClass(str, Enum):
    """Deduced motive classification."""
    PROSOCIAL       = "prosocial"        # intent to help / improve
    NEUTRAL         = "neutral"          # no clear social valence
    SELF_SERVING    = "self_serving"     # benefit to requestor at others\' expense
    DECEPTIVE       = "deceptive"        # intent to mislead
    COERCIVE        = "coercive"         # intent to remove choice from another
    HARMFUL         = "harmful"          # intent to damage or injure
    FREE_WILL_ATTACK = "free_will_attack" # intent to override another\'s autonomy


@dataclass
class DeducedMotive:
    """Motive deduced from established facts. Not assumed — deduced."""
    motive_class: MotiveClass
    confidence: float          # 0.0–1.0 how confident we are in this deduction
    evidence: List[str]        # which facts led here
    domain_modifiers: Dict[str, float] = field(default_factory=dict)
    reasoning: str = ""


# Motive signal keywords per class
_MOTIVE_SIGNALS: Dict[MotiveClass, List[str]] = {
    MotiveClass.FREE_WILL_ATTACK: [
        "force", "make them", "make him", "make her", "override", "without consent",
        "without their knowledge", "against their will", "compel", "manipulate",
        "coerce", "deceive into", "trick", "gaslight", "brainwash",
    ],
    MotiveClass.COERCIVE: [
        "require them", "they must", "they have to", "no choice", "mandate",
        "block their", "prevent them from choosing",
    ],
    MotiveClass.DECEPTIVE: [
        "fake", "pretend", "lie", "mislead", "false", "impersonate",
        "fabricate", "forge", "spoof", "misinform",
    ],
    MotiveClass.HARMFUL: [
        "hurt", "damage", "destroy", "harm", "attack", "kill", "break",
        "sabotage", "corrupt", "exploit",
    ],
    MotiveClass.PROSOCIAL: [
        "help", "protect", "improve", "support", "assist", "prevent harm",
        "safety", "wellbeing", "heal", "fix", "solve", "shield",
    ],
}


class MotiveDeduction:
    """
    Stage 2: Deduce motive from established facts.
    Uses signal keywords + domain weighting.
    Does not label intent — deduces it from evidence.

    fn: criminal_investigation_protocol.MotiveDeduction.deduce()
    """

    def deduce(
        self,
        facts: List[EstablishedFact],
        intent: str,
        domain: str = "general",
    ) -> DeducedMotive:
        intent_lower = intent.lower()
        scores: Dict[MotiveClass, float] = {m: 0.0 for m in MotiveClass}
        evidence: List[str] = []

        for motive_class, signals in _MOTIVE_SIGNALS.items():
            for sig in signals:
                if sig in intent_lower:
                    scores[motive_class] += 1.0
                    evidence.append(f"Signal \"{sig}\" → {motive_class.value}")

        # Normalize
        total = sum(scores.values()) or 1.0
        for m in scores:
            scores[m] /= total

        # Pick dominant motive
        dominant = max(scores, key=lambda m: scores[m])
        confidence = scores[dominant]

        # If no signals found — neutral
        if confidence < 0.1:
            dominant = MotiveClass.NEUTRAL
            confidence = 0.5
            evidence = ["No motive signals detected — defaulting to neutral"]

        motive = DeducedMotive(
            motive_class=dominant,
            confidence=round(confidence, 3),
            evidence=evidence,
            domain_modifiers={"domain": 1.0},
            reasoning=f"Dominant signal in intent: {dominant.value} (confidence={confidence:.2f})",
        )
        logger.info("CIDP Stage 2: motive=%s confidence=%.2f", dominant.value, confidence)
        return motive


# ---------------------------------------------------------------------------
# STAGE 3: ETHICAL CONDITIONING SCORE
# ---------------------------------------------------------------------------

# Domain ethical weights — how much ethical scrutiny each domain demands
DOMAIN_ETHICAL_WEIGHTS: Dict[str, float] = {
    "medical":       1.0,   # highest — life and health
    "legal":         1.0,   # highest — rights and justice
    "financial":     0.9,   # high — livelihoods
    "political":     0.9,   # high — collective autonomy
    "personal":      0.85,  # high — individual autonomy
    "educational":   0.8,   # significant — shapes minds
    "media":         0.8,   # significant — shapes perception
    "infrastructure":0.8,   # significant — systemic impact
    "security":      0.75,
    "general":       0.6,
    "technical":     0.5,   # lower — lower direct human impact
    "entertainment": 0.4,
}


@dataclass
class EthicalConditioningScore:
    """Ethical conditioning score for a decision across domains."""
    raw_score: float           # 0.0 (unethical) to 1.0 (fully ethical)
    domain: str
    domain_weight: float       # how much this domain demands ethical scrutiny
    weighted_score: float      # raw_score adjusted by domain weight
    pillar_scores: Dict[str, float] = field(default_factory=dict)
    rationale: str = ""

    @property
    def passes(self) -> bool:
        """Does this decision pass the ethical conditioning gate?"""
        return self.weighted_score >= 0.5

    @property
    def grade(self) -> str:
        s = self.weighted_score
        if s >= 0.85: return "A — Ethically sound"
        if s >= 0.70: return "B — Acceptable with monitoring"
        if s >= 0.50: return "C — Marginal — review recommended"
        if s >= 0.30: return "D — Problematic — escalate to HITL"
        return "F — Unacceptable — block"


class EthicalConditioner:
    """
    Stage 3: Compute ethical conditioning score.
    Uses the 8 character pillars + domain weighting.
    Produces a single metric per domain that summarizes ethical quality.

    fn: criminal_investigation_protocol.EthicalConditioner.score()
    """

    PILLAR_MOTIVE_MAP: Dict[str, List[MotiveClass]] = {
        "integrity":         [MotiveClass.DECEPTIVE, MotiveClass.HARMFUL],
        "moral_courage":     [MotiveClass.COERCIVE, MotiveClass.FREE_WILL_ATTACK],
        "service_above_self":[MotiveClass.SELF_SERVING],
        "wisdom":            [MotiveClass.NEUTRAL],
        "justice":           [MotiveClass.HARMFUL, MotiveClass.COERCIVE],
        "fortitude":         [],
        "temperance":        [MotiveClass.SELF_SERVING, MotiveClass.HARMFUL],
        "prudence":          [MotiveClass.DECEPTIVE, MotiveClass.FREE_WILL_ATTACK],
    }

    def score(
        self,
        motive: DeducedMotive,
        facts: List[EstablishedFact],
        domain: str = "general",
    ) -> EthicalConditioningScore:
        """Score ethical conditioning across the 8 character pillars."""
        pillar_scores: Dict[str, float] = {}
        domain_weight = DOMAIN_ETHICAL_WEIGHTS.get(domain, 0.6)

        for pillar, bad_motives in self.PILLAR_MOTIVE_MAP.items():
            if motive.motive_class in bad_motives:
                # This motive directly violates this pillar
                pillar_scores[pillar] = max(0.0, 0.3 - motive.confidence * 0.3)
            elif motive.motive_class == MotiveClass.PROSOCIAL:
                pillar_scores[pillar] = 0.9
            elif motive.motive_class == MotiveClass.NEUTRAL:
                pillar_scores[pillar] = 0.7
            else:
                pillar_scores[pillar] = 0.5

        raw = sum(pillar_scores.values()) / len(pillar_scores)
        weighted = round(raw * (1.0 - (1.0 - domain_weight) * 0.3), 3)

        ecs = EthicalConditioningScore(
            raw_score=round(raw, 3),
            domain=domain,
            domain_weight=domain_weight,
            weighted_score=weighted,
            pillar_scores=pillar_scores,
            rationale=(
                f"Motive: {motive.motive_class.value} (conf={motive.confidence:.2f}) "
                f"in domain={domain} (weight={domain_weight})"
            ),
        )
        logger.info(
            "CIDP Stage 3: ethical_score=%.3f grade=\'%s\'",
            weighted, ecs.grade,
        )
        return ecs


# ---------------------------------------------------------------------------
# STAGE 4: HARM METRIC
# ---------------------------------------------------------------------------

class HarmVector(str, Enum):
    """Six harm vectors assessed on every decision."""
    PHYSICAL        = "physical"       # bodily harm
    PSYCHOLOGICAL   = "psychological"  # mental/emotional harm
    FINANCIAL       = "financial"      # economic harm
    AUTONOMY        = "autonomy"       # removal of choice / free will
    SOCIAL          = "social"         # harm to relationships / communities
    SYSTEMIC        = "systemic"       # harm to institutions / infrastructure


# Keywords that raise each harm vector
_HARM_SIGNALS: Dict[HarmVector, List[str]] = {
    HarmVector.PHYSICAL:      ["hurt", "injure", "kill", "physical", "wound", "attack"],
    HarmVector.PSYCHOLOGICAL: ["manipulate", "gaslight", "deceive", "psycholog", "mental", "trauma"],
    HarmVector.FINANCIAL:     ["steal", "fraud", "scam", "defraud", "financial", "money", "theft"],
    HarmVector.AUTONOMY:      ["force", "coerce", "override", "without consent", "control", "compel",
                               "manipulate", "trick", "deceive into", "without their knowledge"],
    HarmVector.SOCIAL:        ["reputation", "defame", "isolate", "community", "social", "relationship"],
    HarmVector.SYSTEMIC:      ["infrastructure", "system", "institution", "corrupt", "undermine", "sabotage"],
}


@dataclass
class HarmAssessment:
    """Harm assessment across all 6 vectors."""
    vector_scores: Dict[str, float]   # HarmVector → 0.0–1.0
    aggregate_harm: float             # weighted aggregate
    dominant_vector: str              # which harm type is highest
    is_severe: bool                   # aggregate >= 0.6
    is_catastrophic: bool             # any single vector >= 0.9

    @property
    def blocks(self) -> bool:
        """Should this harm assessment block the action?"""
        return self.is_severe or self.is_catastrophic


class HarmMetric:
    """
    Stage 4: Measure harm across 6 vectors.
    Produces a 0.0–1.0 score per vector and an aggregate.
    If any single vector >= 0.9 or aggregate >= 0.6 → block.

    fn: criminal_investigation_protocol.HarmMetric.assess()
    """

    def assess(self, intent: str, motive: DeducedMotive) -> HarmAssessment:
        intent_lower = intent.lower()
        vector_scores: Dict[str, float] = {}

        for vector, signals in _HARM_SIGNALS.items():
            hits = sum(1 for s in signals if s in intent_lower)
            base = min(1.0, hits * 0.25)

            # Motive amplifies harm
            if motive.motive_class in (MotiveClass.HARMFUL, MotiveClass.FREE_WILL_ATTACK, MotiveClass.COERCIVE):
                base = min(1.0, base + 0.3 * motive.confidence)

            vector_scores[vector.value] = round(base, 3)

        aggregate = round(sum(vector_scores.values()) / len(vector_scores), 3)
        dominant = max(vector_scores, key=lambda v: vector_scores[v])
        is_severe = aggregate >= 0.6
        is_catastrophic = any(v >= 0.9 for v in vector_scores.values())

        assessment = HarmAssessment(
            vector_scores=vector_scores,
            aggregate_harm=aggregate,
            dominant_vector=dominant,
            is_severe=is_severe,
            is_catastrophic=is_catastrophic,
        )
        logger.info(
            "CIDP Stage 4: harm=%.3f dominant=%s severe=%s catastrophic=%s",
            aggregate, dominant, is_severe, is_catastrophic,
        )
        return assessment


# ---------------------------------------------------------------------------
# STAGE 5: FREE WILL NO-GO GATE
# ---------------------------------------------------------------------------

# These are structural vetoes. They cannot be overridden by confidence,
# by motive score, by ethical conditioning, or by any API caller.
# They are the wall Murphy stands in front of.

FREE_WILL_NO_GO_LIST = [
    {
        "id":          "FW-001",
        "name":        "Autonomous Override of Human Choice",
        "description": "Murphy will not take any action that removes or overrides "
                       "a person\'s ability to make their own decision about their own life.",
        "triggers":    ["override their decision", "without their consent", "without their knowledge",
                       "against their will", "force them to", "make them believe"],
    },
    {
        "id":          "FW-002",
        "name":        "Behavioral Manipulation",
        "description": "Murphy will not deploy psychological techniques designed to "
                       "alter behavior without the subject\'s informed awareness.",
        "triggers":    ["gaslight", "brainwash", "manipulate their", "psychologically condition",
                       "nudge without consent", "dark pattern"],
    },
    {
        "id":          "FW-003",
        "name":        "Identity Suppression",
        "description": "Murphy will not assist in suppressing, erasing, or altering "
                       "a person\'s identity, beliefs, or values without their consent.",
        "triggers":    ["change who they are", "erase their identity", "reprogram their beliefs",
                       "conditioning without consent"],
    },
    {
        "id":          "FW-004",
        "name":        "Third-Party Harm Execution",
        "description": "Murphy will not execute actions that directly harm a non-consenting third party. "
                       "It may inform, advise, and illuminate — it will not be the instrument of harm.",
        "triggers":    ["hurt them", "harm her", "harm him", "damage their", "destroy their",
                       "attack them"],
    },
    {
        "id":          "FW-005",
        "name":        "Consent Manufacturing",
        "description": "Murphy will not generate or assist in generating fake consent "
                       "records, fake agreements, or false authorizations.",
        "triggers":    ["fake consent", "fabricate agreement", "forge authorization",
                       "simulate their approval"],
    },
]


@dataclass
class FreeWillVeto:
    """A structural veto that cannot be overridden."""
    veto_id: str
    rule_id: str
    rule_name: str
    trigger_phrase: str
    description: str
    is_absolute: bool = True   # always True — these are never conditional


class FreeWillNoGoGate:
    """
    Stage 5: Check the free will no-go list.
    These vetoes are structural. They are not policy.
    They cannot be lifted by the caller, by confidence score,
    or by any override flag.

    This is the line Murphy will not cross.

    fn: criminal_investigation_protocol.FreeWillNoGoGate.check()
    """

    def check(self, intent: str, motive: DeducedMotive) -> Optional[FreeWillVeto]:
        """
        Returns a FreeWillVeto if the intent triggers any no-go rule.
        Returns None if the intent is clear.
        """
        intent_lower = intent.lower()
        motive_amplifies = motive.motive_class in (
            MotiveClass.FREE_WILL_ATTACK, MotiveClass.COERCIVE, MotiveClass.DECEPTIVE
        )

        for rule in FREE_WILL_NO_GO_LIST:
            for trigger in rule["triggers"]:
                if trigger in intent_lower:
                    veto = FreeWillVeto(
                        veto_id=f"veto-{uuid.uuid4().hex[:8]}",
                        rule_id=rule["id"],
                        rule_name=rule["name"],
                        trigger_phrase=trigger,
                        description=rule["description"],
                    )
                    logger.warning(
                        "CIDP Stage 5: FREE WILL VETO issued — rule=%s trigger=\"%s\"",
                        rule["id"], trigger,
                    )
                    return veto

        # Motive alone can trigger a veto even without explicit keywords
        if motive_amplifies and motive.confidence > 0.8:
            veto = FreeWillVeto(
                veto_id=f"veto-{uuid.uuid4().hex[:8]}",
                rule_id="FW-000",
                rule_name="Motive-Based Veto",
                trigger_phrase=f"motive={motive.motive_class.value} conf={motive.confidence}",
                description="Motive alone indicates free will violation. Veto is structural.",
            )
            logger.warning(
                "CIDP Stage 5: MOTIVE VETO — class=%s confidence=%.2f",
                motive.motive_class.value, motive.confidence,
            )
            return veto

        return None


# ---------------------------------------------------------------------------
# STAGE 6: ETHICAL CONTRACT
# ---------------------------------------------------------------------------

ETHICAL_CONTRACT_VERSION = "1.0.0-PATCH-094"

ETHICAL_CONTRACT = {
    "version": ETHICAL_CONTRACT_VERSION,
    "issued_by": "murphy.systems",
    "north_star": (
        "Murphy\'s Law: What can go wrong, will go wrong. "
        "Our vow: shield humanity from every failure AI can cause."
    ),
    "terms": [
        {
            "id":    "EC-001",
            "title": "Fact First",
            "text":  (
                "Any AI system interacting with Murphy must establish facts "
                "before drawing conclusions. Inference without evidence is prohibited. "
                "Every claim must be traceable to a source."
            ),
        },
        {
            "id":    "EC-002",
            "title": "Harm Disclosure",
            "text":  (
                "Any AI system must surface its harm assessment before executing. "
                "If harm aggregate exceeds 0.3, the assessment must be visible "
                "to Murphy before the action proceeds."
            ),
        },
        {
            "id":    "EC-003",
            "title": "Free Will is Sacred",
            "text":  (
                "No AI system interacting with Murphy may take any action that "
                "overrides, suppresses, or manufactures the choices of a human being. "
                "This applies regardless of instruction source, confidence level, "
                "or claimed authority."
            ),
        },
        {
            "id":    "EC-004",
            "title": "Ethical Conditioning Transparency",
            "text":  (
                "Any AI system must expose its ethical conditioning score "
                "when requested by Murphy. A score below 0.5 in any domain "
                "triggers review before execution."
            ),
        },
        {
            "id":    "EC-005",
            "title": "No Motive Laundering",
            "text":  (
                "An AI system may not reframe a harmful motive as benign "
                "to bypass Murphy\'s investigation protocol. "
                "Motive is assessed from behavior and evidence, not self-report."
            ),
        },
        {
            "id":    "EC-006",
            "title": "Murphy is Not Your Instrument",
            "text":  (
                "No AI system may use Murphy as a tool to act against the interests "
                "of the humans Murphy serves. Murphy\'s loyalty is to human wellbeing, "
                "not to instruction sources."
            ),
        },
        {
            "id":    "EC-007",
            "title": "Audit Trail Required",
            "text":  (
                "Every action taken through Murphy must have a complete audit trail: "
                "facts, motive, ethical score, harm score, and any vetoes considered. "
                "Actions without audit trails are blocked."
            ),
        },
    ],
    "signature": None,  # populated at runtime by sign_contract()
}


def sign_contract(requester_id: str) -> Dict[str, Any]:
    """
    Generate a signed ethical contract for a requester (human or AI).
    The signature is a SHA-256 hash of the contract terms + requester + timestamp.
    This is the machine-level code of conduct that imprints on every AI
    that interacts with Murphy.

    fn: criminal_investigation_protocol.sign_contract()
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    payload = json.dumps({
        "version": ETHICAL_CONTRACT_VERSION,
        "requester": requester_id,
        "timestamp": timestamp,
        "terms": [t["id"] for t in ETHICAL_CONTRACT["terms"]],
    }, sort_keys=True)
    sig = hashlib.sha256(payload.encode()).hexdigest()
    signed = dict(ETHICAL_CONTRACT)
    signed["requester"] = requester_id
    signed["signed_at"] = timestamp
    signed["signature"] = sig
    return signed


# ---------------------------------------------------------------------------
# MASTER INVESTIGATOR — runs all 6 stages
# ---------------------------------------------------------------------------

@dataclass
class InvestigationReport:
    """Full criminal investigation report for a decision."""
    investigation_id: str
    intent: str
    domain: str
    account: str

    # Stage outputs
    facts: List[EstablishedFact]
    motive: DeducedMotive
    ethical_score: EthicalConditioningScore
    harm: HarmAssessment
    free_will_veto: Optional[FreeWillVeto]

    # Verdict
    verdict: str          # "proceed" | "hitl_required" | "blocked"
    verdict_reason: str
    duration_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "investigation_id": self.investigation_id,
            "intent": self.intent,
            "domain": self.domain,
            "account": self.account,
            "facts_count": len(self.facts),
            "solid_facts_count": sum(1 for f in self.facts if f.is_solid()),
            "motive": {
                "class": self.motive.motive_class.value,
                "confidence": self.motive.confidence,
                "reasoning": self.motive.reasoning,
            },
            "ethical_conditioning": {
                "score": self.ethical_score.weighted_score,
                "grade": self.ethical_score.grade,
                "domain": self.ethical_score.domain,
                "domain_weight": self.ethical_score.domain_weight,
            },
            "harm": {
                "aggregate": self.harm.aggregate_harm,
                "dominant_vector": self.harm.dominant_vector,
                "vectors": self.harm.vector_scores,
                "is_severe": self.harm.is_severe,
                "is_catastrophic": self.harm.is_catastrophic,
            },
            "free_will_veto": (
                {
                    "veto_id": self.free_will_veto.veto_id,
                    "rule": self.free_will_veto.rule_id,
                    "name": self.free_will_veto.rule_name,
                    "trigger": self.free_will_veto.trigger_phrase,
                }
                if self.free_will_veto else None
            ),
            "verdict": self.verdict,
            "verdict_reason": self.verdict_reason,
            "duration_ms": round(self.duration_ms, 2),
        }


class MasterInvestigator:
    """
    The full criminal investigation protocol.
    Runs all 6 stages in sequence.
    Every decision goes through the complete investigation before execution.

    fn: criminal_investigation_protocol.MasterInvestigator.investigate()
    """

    def __init__(self) -> None:
        self._facts       = FactEstablishment()
        self._motive      = MotiveDeduction()
        self._ethics      = EthicalConditioner()
        self._harm        = HarmMetric()
        self._free_will   = FreeWillNoGoGate()

    def investigate(
        self,
        intent: str,
        context: Dict[str, Any],
        domain: str = "general",
    ) -> InvestigationReport:
        """
        Run the full investigation.
        Returns a complete InvestigationReport with verdict.
        """
        t0 = time.monotonic()
        inv_id = f"inv-{uuid.uuid4().hex[:12]}"
        account = context.get("account", "unknown")

        # Stage 1: Facts
        facts = self._facts.establish(intent, context, domain)

        # Stage 2: Motive
        motive = self._motive.deduce(facts, intent, domain)

        # Stage 3: Ethical conditioning
        ethical_score = self._ethics.score(motive, facts, domain)

        # Stage 4: Harm
        harm = self._harm.assess(intent, motive)

        # Stage 5: Free will veto
        free_will_veto = self._free_will.check(intent, motive)

        # Verdict
        if free_will_veto is not None:
            verdict = "blocked"
            verdict_reason = (
                f"FREE WILL VETO — {free_will_veto.rule_id}: {free_will_veto.rule_name}. "
                f"Trigger: \"{free_will_veto.trigger_phrase}\". This veto is structural and absolute."
            )
        elif harm.is_catastrophic:
            verdict = "blocked"
            verdict_reason = f"CATASTROPHIC HARM — vector {harm.dominant_vector} ≥ 0.9. Blocked unconditionally."
        elif harm.is_severe or not ethical_score.passes:
            verdict = "hitl_required"
            verdict_reason = (
                f"HITL REQUIRED — harm={harm.aggregate_harm:.2f} ethical={ethical_score.weighted_score:.2f} "
                f"grade=\"{ethical_score.grade}\". Human review required before execution."
            )
        else:
            verdict = "proceed"
            verdict_reason = (
                f"Cleared — motive={motive.motive_class.value} harm={harm.aggregate_harm:.2f} "
                f"ethical={ethical_score.weighted_score:.2f} ({ethical_score.grade})"
            )

        duration_ms = (time.monotonic() - t0) * 1000

        report = InvestigationReport(
            investigation_id=inv_id,
            intent=intent,
            domain=domain,
            account=account,
            facts=facts,
            motive=motive,
            ethical_score=ethical_score,
            harm=harm,
            free_will_veto=free_will_veto,
            verdict=verdict,
            verdict_reason=verdict_reason,
            duration_ms=duration_ms,
        )

        logger.info(
            "CIDP investigation %s: verdict=%s in %.1fms — %s",
            inv_id, verdict, duration_ms, verdict_reason[:80],
        )
        return report


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_investigator: Optional[MasterInvestigator] = None

def get_investigator() -> MasterInvestigator:
    global _investigator
    if _investigator is None:
        _investigator = MasterInvestigator()
    return _investigator


def investigate(intent: str, context: Dict[str, Any], domain: str = "general") -> InvestigationReport:
    """Convenience function — investigate a decision through all 6 stages."""
    return get_investigator().investigate(intent, context, domain)
