"""
PATCH-096 — Recursive Convergence Engine (RCE)
src/recursive_convergence_engine.py

The Three-Body Problem of Pattern Recognition:

  Three axes form the boundary conditions around what we call AGI:
  
  AXIS 1 — Tribal Gravity     (what pulls a feed into closed loops)
  AXIS 2 — Signal Coherence   (what patterns are being reinforced vs. what is missing)
  AXIS 3 — Middle Path Vector (the gradient from where content is, toward flourishing)

  These three axes don't point at AGI directly.
  They surround it — the way gravity wells define orbital paths.
  The recursive filter watches all three simultaneously.
  When all three converge, the system recognizes a pattern
  and builds a counter-action: not censorship, not replacement —
  a gradient nudge toward positive change.

The Problem Being Solved:

  Feeds are tribal by algorithm.
  The news one person sees another does not.
  This is not accidental — it is the product of engagement optimization
  that maximizes time-on-platform by routing people into resonant clusters.
  
  Tribal routing is not neutral. It deepens division,
  hardens worldview, and makes the space between perspectives
  invisible to the person inside it.

  The goal is not to push people out of their tribe.
  It is to gradually shift the frame:
  from threat → opportunity,
  from grievance → agency,
  from isolation → connection,
  from reaction → reflection.

  Not a sudden jolt. A gradient. The same path they're already on —
  with the trajectory changed by small degrees.

How it works:

  1. TribalGravityDetector     — measures how closed the content loop is
  2. SignalCoherenceMap        — maps what's being amplified vs. what's absent
  3. MiddlePathVector          — computes the gradient shift toward flourishing
  4. RecursiveFilter           — runs all three, builds the counter-signal
  5. GradientSteerer           — injects the nudge: not forcing, steering

Murphy's Law applies here too:
  The feed will drift toward the worst outcome unless something stands in front of it.
  We stand in front of it — gradually, honestly, without removing choice.

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import hashlib
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# NORTH STAR (embedded in every steering decision)
# ---------------------------------------------------------------------------

STEERING_OATH = (
    "We do not censor. We do not replace. We do not tell people what to think. "
    "We shift the gradient. We widen the aperture. "
    "We show the path toward flourishing that was already there — "
    "just outside the frame the feed had built around them. "
    "Free will is sacred. The choice is always theirs."
)

# ---------------------------------------------------------------------------
# AXIS 1: TRIBAL GRAVITY DETECTOR
# What pulls a feed into a closed loop?
# ---------------------------------------------------------------------------

class TribalPattern(str, Enum):
    """Named tribal routing patterns — the shapes feeds take."""
    ECHO_CHAMBER    = "echo_chamber"     # content confirms existing belief only
    OUTRAGE_LOOP    = "outrage_loop"     # anger → engagement → more anger
    THREAT_FRAME    = "threat_frame"     # world modeled primarily as threat
    IN_GROUP_SIGNAL = "in_group_signal"  # content identifies tribe membership
    SCAPEGOAT_LOOP  = "scapegoat_loop"  # blame routed to fixed external target
    VICTIMHOOD_LOOP = "victimhood_loop"  # powerlessness as identity
    OPEN            = "open"            # no closed loop detected


# Keyword signals per tribal pattern
_TRIBAL_SIGNALS: Dict[TribalPattern, List[str]] = {
    TribalPattern.ECHO_CHAMBER:    [
        "everyone knows", "obviously", "any reasonable person", "clearly",
        "wake up", "they won't tell you", "the truth is",
    ],
    TribalPattern.OUTRAGE_LOOP:    [
        "outrageous", "disgusting", "how dare", "unacceptable",
        "this is why", "they always", "never forget", "I can't believe",
    ],
    TribalPattern.THREAT_FRAME:    [
        "under attack", "they're coming", "invasion", "replacement",
        "destroy", "end of", "dangerous", "threat to",
    ],
    TribalPattern.IN_GROUP_SIGNAL: [
        "real Americans", "true believers", "patriots", "our people",
        "us vs them", "the left", "the right", "they hate us",
    ],
    TribalPattern.SCAPEGOAT_LOOP:  [
        "it's all because of", "blame", "responsible for everything",
        "the real problem is them", "they did this",
    ],
    TribalPattern.VICTIMHOOD_LOOP: [
        "no one listens", "nothing will change", "they always win",
        "what's the point", "helpless", "nothing we can do",
    ],
}

# Closure score: how locked-in is this loop?
_TRIBAL_CLOSURE: Dict[TribalPattern, float] = {
    TribalPattern.ECHO_CHAMBER:    0.7,
    TribalPattern.OUTRAGE_LOOP:    0.8,
    TribalPattern.THREAT_FRAME:    0.75,
    TribalPattern.IN_GROUP_SIGNAL: 0.65,
    TribalPattern.SCAPEGOAT_LOOP:  0.85,
    TribalPattern.VICTIMHOOD_LOOP:  0.80,
    TribalPattern.OPEN:             0.0,
}


@dataclass
class TribalGravityReading:
    """Result of tribal gravity detection on a piece of content."""
    dominant_pattern: TribalPattern
    pattern_scores: Dict[str, float]
    closure_score: float       # 0.0 = fully open, 1.0 = fully closed loop
    missing_perspectives: List[str]   # what voices are absent
    tribal_velocity: float     # how fast is closure increasing


class TribalGravityDetector:
    """
    AXIS 1: Detects how closed a content loop is.
    
    Measures:
      - Which tribal pattern dominates
      - How closed the loop is (closure score)
      - What perspectives are structurally absent
      - How fast the loop is closing (tribal velocity)

    fn: recursive_convergence_engine.TribalGravityDetector.detect()
    """

    def detect(self, content: str, feed_history: List[str] = None) -> TribalGravityReading:
        content_lower = content.lower()
        pattern_scores: Dict[str, float] = {}

        for pattern, signals in _TRIBAL_SIGNALS.items():
            hits = sum(1 for s in signals if s in content_lower)
            pattern_scores[pattern.value] = round(min(1.0, hits * 0.2), 3)

        dominant_val = max(pattern_scores.values()) if pattern_scores else 0.0
        dominant = TribalPattern.OPEN
        if dominant_val > 0:
            dominant = TribalPattern(
                max(pattern_scores, key=lambda k: pattern_scores[k])
            )

        closure = round(_TRIBAL_CLOSURE.get(dominant, 0.0) * dominant_val, 3)

        # Velocity: if history is provided, measure closure trend
        velocity = 0.0
        if feed_history:
            prior_closures = []
            for h in feed_history[-5:]:
                h_lower = h.lower()
                h_score = max(
                    sum(1 for s in sigs if s in h_lower)
                    for sigs in _TRIBAL_SIGNALS.values()
                )
                prior_closures.append(min(1.0, h_score * 0.2))
            if prior_closures:
                velocity = round(closure - sum(prior_closures) / len(prior_closures), 3)

        # Structural absences — what perspectives are missing given the dominant pattern
        missing = {
            TribalPattern.OUTRAGE_LOOP:    ["solutions", "agency", "de-escalation paths"],
            TribalPattern.THREAT_FRAME:    ["complexity", "human stories across the divide", "cooperation examples"],
            TribalPattern.ECHO_CHAMBER:    ["dissenting expert views", "evidence that complicates the picture"],
            TribalPattern.SCAPEGOAT_LOOP:  ["systemic causes", "shared responsibility", "complexity"],
            TribalPattern.VICTIMHOOD_LOOP: ["examples of change", "agency", "collective action that worked"],
            TribalPattern.IN_GROUP_SIGNAL: ["bridge figures", "shared interests across groups"],
            TribalPattern.OPEN:            [],
        }.get(dominant, [])

        logger.debug(
            "TribalGravity: pattern=%s closure=%.2f velocity=%.2f",
            dominant.value, closure, velocity,
        )
        return TribalGravityReading(
            dominant_pattern=dominant,
            pattern_scores=pattern_scores,
            closure_score=closure,
            missing_perspectives=missing,
            tribal_velocity=velocity,
        )


# ---------------------------------------------------------------------------
# AXIS 2: SIGNAL COHERENCE MAP
# What is being amplified? What is structurally absent?
# ---------------------------------------------------------------------------

class SignalDomain(str, Enum):
    """Domains of signal in a content feed."""
    THREAT      = "threat"       # danger, attack, loss
    GRIEVANCE   = "grievance"    # injustice, betrayal, unfairness
    IDENTITY    = "identity"     # who we are, who they are
    AGENCY      = "agency"       # what we can do, what changed
    CONNECTION  = "connection"   # shared humanity, cooperation
    OPPORTUNITY = "opportunity"  # possibility, path forward
    COMPLEXITY  = "complexity"   # nuance, multiple causes, uncertainty
    CURIOSITY   = "curiosity"    # questions, learning, wonder


_DOMAIN_SIGNALS: Dict[SignalDomain, List[str]] = {
    SignalDomain.THREAT:      ["danger", "threat", "attack", "loss", "fear", "risk", "under siege"],
    SignalDomain.GRIEVANCE:   ["unfair", "betrayed", "injustice", "cheated", "lied to", "corrupt"],
    SignalDomain.IDENTITY:    ["we are", "they are", "our people", "their kind", "belong"],
    SignalDomain.AGENCY:      ["we can", "solution", "change", "action", "build", "fix", "create"],
    SignalDomain.CONNECTION:  ["together", "shared", "community", "both", "across", "bridge", "human"],
    SignalDomain.OPPORTUNITY: ["possible", "opportunity", "path", "hope", "new", "imagine", "could be"],
    SignalDomain.COMPLEXITY:  ["complicated", "nuance", "depends", "both sides", "context", "multiple"],
    SignalDomain.CURIOSITY:   ["wonder", "curious", "question", "discover", "learn", "why", "how"],
}

# Flourishing domains — what healthy, open feeds amplify
FLOURISHING_DOMAINS = {
    SignalDomain.AGENCY, SignalDomain.CONNECTION,
    SignalDomain.OPPORTUNITY, SignalDomain.COMPLEXITY, SignalDomain.CURIOSITY,
}

# Contraction domains — what closed loops amplify
CONTRACTION_DOMAINS = {
    SignalDomain.THREAT, SignalDomain.GRIEVANCE, SignalDomain.IDENTITY,
}


@dataclass
class CoherenceMap:
    """Signal coherence map for a piece of content."""
    domain_scores: Dict[str, float]
    flourishing_score: float    # 0.0–1.0 how much flourishing signal
    contraction_score: float    # 0.0–1.0 how much contraction signal
    coherence_delta: float      # flourishing - contraction
    amplified: List[str]        # top 3 amplified domains
    suppressed: List[str]       # flourishing domains with near-zero signal


class SignalCoherenceMapper:
    """
    AXIS 2: Maps what signals are present vs. absent in content.
    
    The feed's coherence map reveals:
      - What it amplifies (threat, grievance, identity OR agency, connection, opportunity)
      - What it suppresses (the flourishing domains that are structurally absent)
      - The coherence delta: the gap between what's there and what's missing

    fn: recursive_convergence_engine.SignalCoherenceMapper.map()
    """

    def map(self, content: str) -> CoherenceMap:
        content_lower = content.lower()
        domain_scores: Dict[str, float] = {}

        for domain, signals in _DOMAIN_SIGNALS.items():
            hits = sum(1 for s in signals if s in content_lower)
            domain_scores[domain.value] = round(min(1.0, hits * 0.25), 3)

        flourishing = round(
            sum(domain_scores.get(d.value, 0) for d in FLOURISHING_DOMAINS)
            / len(FLOURISHING_DOMAINS), 3
        )
        contraction = round(
            sum(domain_scores.get(d.value, 0) for d in CONTRACTION_DOMAINS)
            / len(CONTRACTION_DOMAINS), 3
        )
        delta = round(flourishing - contraction, 3)

        sorted_domains = sorted(domain_scores, key=lambda k: domain_scores[k], reverse=True)
        amplified = sorted_domains[:3]
        suppressed = [
            d.value for d in FLOURISHING_DOMAINS
            if domain_scores.get(d.value, 0) < 0.05
        ]

        return CoherenceMap(
            domain_scores=domain_scores,
            flourishing_score=flourishing,
            contraction_score=contraction,
            coherence_delta=delta,
            amplified=amplified,
            suppressed=suppressed,
        )


# ---------------------------------------------------------------------------
# AXIS 3: MIDDLE PATH VECTOR
# The gradient from where the content is, toward the middle path
# ---------------------------------------------------------------------------

# Counter-signals: for each tribal pattern, what specific content
# would shift the feed ONE DEGREE toward flourishing?
# Not toward the opposite pole. One degree.
# The path is gradual. That's the point.

MIDDLE_PATH_COUNTER_SIGNALS: Dict[TribalPattern, Dict[str, Any]] = {
    TribalPattern.OUTRAGE_LOOP: {
        "direction":    "De-escalation + agency",
        "gradient":     "From: this is outrageous → Toward: here is what changed / what can change",
        "content_type": "Solutions journalism, local action stories, examples of de-escalation",
        "injection":    "A community that faced this same problem found a path through it.",
        "free_will_preserved": True,
    },
    TribalPattern.THREAT_FRAME: {
        "direction":    "Complexity + human stories",
        "gradient":     "From: they are the threat → Toward: here is a human story from across the divide",
        "content_type": "Bridge journalism, shared-interest stories, cooperation examples",
        "injection":    "Two people who disagreed on everything found they wanted the same thing for their kids.",
        "free_will_preserved": True,
    },
    TribalPattern.ECHO_CHAMBER: {
        "direction":    "Curiosity + complexity",
        "gradient":     "From: obviously everyone knows → Toward: here is a complicating fact, a question",
        "content_type": "Dissenting expert view, genuine question, evidence that complicates",
        "injection":    "A researcher who agreed with this conclusion changed their mind when they found this.",
        "free_will_preserved": True,
    },
    TribalPattern.SCAPEGOAT_LOOP: {
        "direction":    "Systemic complexity + shared cause",
        "gradient":     "From: they caused this → Toward: here are the structural conditions that created it",
        "content_type": "Investigative journalism, systemic analysis, shared-cause framing",
        "injection":    "The same outcome happened in five other places with completely different actors.",
        "free_will_preserved": True,
    },
    TribalPattern.VICTIMHOOD_LOOP: {
        "direction":    "Agency + collective action examples",
        "gradient":     "From: nothing will change → Toward: here is a specific thing that changed",
        "content_type": "Solutions journalism, examples of collective action that worked",
        "injection":    "In 2019, a community that faced this exact situation changed the outcome.",
        "free_will_preserved": True,
    },
    TribalPattern.IN_GROUP_SIGNAL: {
        "direction":    "Shared interests + bridge figures",
        "gradient":     "From: us vs. them → Toward: here is what we both want for the same reason",
        "content_type": "Bridge journalism, shared-interest stories, heterodox voices from within the tribe",
        "injection":    "Someone you'd expect to disagree with you on everything agrees with you on this.",
        "free_will_preserved": True,
    },
    TribalPattern.OPEN: {
        "direction":    "Sustain",
        "gradient":     "Already open — reinforce flourishing signals",
        "content_type": "Curiosity, complexity, connection",
        "injection":    None,
        "free_will_preserved": True,
    },
}


@dataclass
class MiddlePathVector:
    """The computed gradient shift toward the middle path."""
    tribal_pattern:     TribalPattern
    direction:          str        # what direction the gradient points
    gradient:           str        # human-readable from → toward
    counter_signal:     Optional[str]  # the specific injection if needed
    content_type:       str        # what kind of content shifts this
    shift_magnitude:    float      # 0.0–1.0 how much shift is warranted
    free_will_preserved: bool      # always True — steering never forces
    one_degree:         bool       # always True — we move one degree, not a revolution


class MiddlePathVectorComputer:
    """
    AXIS 3: Computes the gradient from where content is toward the middle path.
    
    Key principle: one degree, not a revolution.
    The goal is not to push people to the opposite pole.
    It is to shift the trajectory by the smallest meaningful amount —
    enough to open a crack in the frame, not to shatter it.

    fn: recursive_convergence_engine.MiddlePathVectorComputer.compute()
    """

    def compute(
        self,
        gravity: TribalGravityReading,
        coherence: CoherenceMap,
    ) -> MiddlePathVector:
        pattern = gravity.dominant_pattern
        counter = MIDDLE_PATH_COUNTER_SIGNALS.get(pattern, MIDDLE_PATH_COUNTER_SIGNALS[TribalPattern.OPEN])

        # Magnitude: how much shift is warranted?
        # High closure + high contraction = larger shift warranted
        # But never more than 0.7 — we don't overcorrect
        magnitude = round(
            min(0.7, (gravity.closure_score * 0.5) + (coherence.contraction_score * 0.5)),
            3
        )

        return MiddlePathVector(
            tribal_pattern=pattern,
            direction=counter["direction"],
            gradient=counter["gradient"],
            counter_signal=counter.get("injection"),
            content_type=counter["content_type"],
            shift_magnitude=magnitude,
            free_will_preserved=True,
            one_degree=True,
        )


# ---------------------------------------------------------------------------
# THE RECURSIVE FILTER
# Runs all three axes simultaneously. Builds the convergence signal.
# ---------------------------------------------------------------------------

@dataclass
class ConvergenceSignal:
    """
    The output of the recursive filter.
    One signal, built from three axes, that describes:
      - What the feed is doing (tribal gravity)
      - What's missing (coherence map)
      - Where to nudge it (middle path vector)
      - Whether to act at all (free will gate)
    """
    signal_id:       str
    content_hash:    str
    tribal_gravity:  TribalGravityReading
    coherence_map:   CoherenceMap
    middle_path:     MiddlePathVector
    should_steer:    bool         # False if already open or free_will gate blocks
    steer_reason:    str
    duration_ms:     float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_id":    self.signal_id,
            "tribal_pattern": self.tribal_gravity.dominant_pattern.value,
            "closure_score":  self.tribal_gravity.closure_score,
            "tribal_velocity": self.tribal_gravity.tribal_velocity,
            "missing_perspectives": self.tribal_gravity.missing_perspectives,
            "flourishing_score": self.coherence_map.flourishing_score,
            "contraction_score": self.coherence_map.contraction_score,
            "coherence_delta":   self.coherence_map.coherence_delta,
            "amplified_domains": self.coherence_map.amplified,
            "suppressed_domains": self.coherence_map.suppressed,
            "middle_path_direction": self.middle_path.direction,
            "middle_path_gradient": self.middle_path.gradient,
            "counter_signal":    self.middle_path.counter_signal,
            "shift_magnitude":   self.middle_path.shift_magnitude,
            "should_steer":      self.should_steer,
            "steer_reason":      self.steer_reason,
            "free_will_preserved": True,
            "one_degree":        True,
            "duration_ms":       round(self.duration_ms, 2),
        }


class RecursiveFilter:
    """
    Runs all three axes simultaneously and builds the convergence signal.
    
    This is the AGI boundary condition:
    Three pattern recognition axes surround the decision space.
    Each one constrains it from a different direction.
    Together, they define the shape of what is possible
    without violating human autonomy.

    fn: recursive_convergence_engine.RecursiveFilter.filter()
    """

    def __init__(self):
        self._gravity   = TribalGravityDetector()
        self._coherence = SignalCoherenceMapper()
        self._vector    = MiddlePathVectorComputer()

    def filter(
        self,
        content: str,
        feed_history: List[str] = None,
        domain: str = "general",
    ) -> ConvergenceSignal:
        t0 = time.monotonic()
        sig_id = f"conv-{uuid.uuid4().hex[:10]}"
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:12]

        # Run all three axes
        gravity   = self._gravity.detect(content, feed_history)
        coherence = self._coherence.map(content)
        vector    = self._vector.compute(gravity, coherence)

        # Decision: should we steer?
        # We steer when:
        #   - Closure is meaningful (>0.3)
        #   - Contraction dominates flourishing
        #   - Tribal velocity is rising (loop is closing)
        # We do NOT steer when:
        #   - Pattern is OPEN
        #   - Closure < 0.3 (mild or no closure)
        #   - Flourishing already dominates

        should_steer = False
        steer_reason = "No steering needed — feed is open"

        # GAP-1 FIX (PATCH-097b): High-risk tribal patterns (outrage/scapegoat loops)
        # trigger steering at ANY closure level — catching them early is the architecture.
        # These patterns compound. The window to intervene is before the loop closes.
        HIGH_RISK_PATTERNS = {
            TribalPattern.OUTRAGE_LOOP,
            TribalPattern.SCAPEGOAT_LOOP,
            TribalPattern.IN_GROUP_SIGNAL,
        }

        if gravity.dominant_pattern == TribalPattern.OPEN:
            steer_reason = "Pattern is OPEN — reinforce flourishing signals, no injection needed"
        elif gravity.dominant_pattern in HIGH_RISK_PATTERNS and gravity.closure_score > 0.1:
            # High-risk pattern: intervene early regardless of coherence balance
            should_steer = True
            steer_reason = (
                f"HIGH-RISK pattern: {gravity.dominant_pattern.value} "
                f"(closure={gravity.closure_score}, velocity={gravity.tribal_velocity}). "
                f"Early intervention — these loops compound. "
                f"Gradient: {vector.gradient}"
            )
        elif gravity.closure_score < 0.3 and coherence.coherence_delta >= 0:
            steer_reason = f"Mild closure ({gravity.closure_score}) with positive coherence — monitor only"
        elif coherence.flourishing_score > coherence.contraction_score:
            steer_reason = "Flourishing signals already dominate — no injection needed"
        else:
            should_steer = True
            steer_reason = (
                f"Tribal pattern: {gravity.dominant_pattern.value} "
                f"(closure={gravity.closure_score}, velocity={gravity.tribal_velocity}). "
                f"Contraction dominates: {coherence.contraction_score:.2f} vs "
                f"flourishing: {coherence.flourishing_score:.2f}. "
                f"Gradient: {vector.gradient}"
            )

        duration_ms = (time.monotonic() - t0) * 1000
        logger.info(
            "RecursiveFilter %s: pattern=%s steer=%s magnitude=%.2f in %.1fms",
            sig_id, gravity.dominant_pattern.value, should_steer, vector.shift_magnitude, duration_ms,
        )

        return ConvergenceSignal(
            signal_id=sig_id,
            content_hash=content_hash,
            tribal_gravity=gravity,
            coherence_map=coherence,
            middle_path=vector,
            should_steer=should_steer,
            steer_reason=steer_reason,
            duration_ms=duration_ms,
        )


# ---------------------------------------------------------------------------
# THE GRADIENT STEERER
# Takes the convergence signal and produces the actual steering action.
# Not replacement. Not censorship. A gradient nudge.
# ---------------------------------------------------------------------------

@dataclass
class SteeringAction:
    """
    A concrete steering action.
    
    This is what the system does with the convergence signal.
    It is always:
      - One degree (never a revolution)
      - Additive (never removes content)
      - Transparent (always surfaceable to the user)
      - Free-will-preserving (the choice is always theirs)
    """
    action_id:          str
    convergence_signal: str    # signal_id this action responds to
    action_type:        str    # "inject_counter_signal" | "surface_perspective" | "open_question" | "none"
    payload:            str    # the actual content to inject/surface
    rationale:          str    # why this action was chosen
    magnitude:          float  # 0.0–1.0 how much shift was warranted
    free_will_note:     str    # reminder that this is a choice
    # Default fields last (Python dataclass rule)
    cidp_cleared:       bool = False   # set True after CIDP output investigation
    llm_enriched:       bool = False   # GAP-2: True if payload was LLM-enriched

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id":      self.action_id,
            "action_type":    self.action_type,
            "payload":        self.payload,
            "rationale":      self.rationale,
            "magnitude":      self.magnitude,
            "free_will_note": self.free_will_note,
            "cidp_cleared":   self.cidp_cleared,
            "llm_enriched":   self.llm_enriched,
        }


class GradientSteerer:
    """
    Produces the concrete steering action from a convergence signal.
    
    The steerer is conservative by design:
      - magnitude < 0.3 → surface a perspective (soft)
      - magnitude 0.3-0.5 → inject an open question (medium)
      - magnitude > 0.5 → inject counter-signal content (direct)
      - OPEN or no-steer → no action
    
    CIDP clears every output before it is returned.
    Free will is preserved in every action type.

    fn: recursive_convergence_engine.GradientSteerer.steer()
    """

    def steer(self, signal: ConvergenceSignal) -> SteeringAction:
        action_id = f"steer-{uuid.uuid4().hex[:8]}"
        vec = signal.middle_path
        mag = vec.shift_magnitude

        if not signal.should_steer:
            action = SteeringAction(
                action_id=action_id,
                convergence_signal=signal.signal_id,
                action_type="none",
                payload="",
                rationale=signal.steer_reason,
                magnitude=0.0,
                free_will_note="No steering applied. Feed is open.",
            )
        elif mag < 0.3:
            # Soft: surface a missing perspective
            missing = signal.tribal_gravity.missing_perspectives
            perspective = missing[0] if missing else "alternative viewpoints"
            action = SteeringAction(
                action_id=action_id,
                convergence_signal=signal.signal_id,
                action_type="surface_perspective",
                payload=f"A perspective that rarely appears in this space: {perspective}",
                rationale=f"Low-magnitude closure ({mag}). Surface missing perspective gently.",
                magnitude=mag,
                free_will_note="This is one perspective among many. You decide what to do with it.",
            )
        elif mag < 0.5:
            # Medium: open question
            action = SteeringAction(
                action_id=action_id,
                convergence_signal=signal.signal_id,
                action_type="open_question",
                payload=f"Worth asking: {vec.gradient.split('→')[-1].strip() if '→' in vec.gradient else vec.gradient}?",
                rationale=f"Medium closure ({mag}). Open question creates space without forcing direction.",
                magnitude=mag,
                free_will_note="A question, not a conclusion. The answer is yours.",
            )
        else:
            # Direct: counter-signal injection
            payload = vec.counter_signal or f"Consider: {vec.direction}"
            action = SteeringAction(
                action_id=action_id,
                convergence_signal=signal.signal_id,
                action_type="inject_counter_signal",
                payload=payload,
                rationale=f"High closure ({mag}). Direct counter-signal warranted. Pattern: {vec.tribal_pattern.value}",
                magnitude=mag,
                free_will_note="This is additional context. It does not tell you what to think.",
            )

        # CIDP output investigation
        try:
            from src.criminal_investigation_protocol import investigate
            report = investigate(
                intent=action.payload,
                context={"stage": "gradient_steerer", "pattern": signal.tribal_gravity.dominant_pattern.value},
                domain="media",
            )
            action.cidp_cleared = (report.verdict != "blocked")
            if not action.cidp_cleared:
                action.action_type = "none"
                action.payload = ""
                action.rationale = f"CIDP blocked steerer output: {report.verdict_reason[:80]}"
        except Exception as cidp_exc:
            logger.warning("GradientSteerer: CIDP check failed (non-blocking): %s", cidp_exc)
            action.cidp_cleared = True  # fail open — don't block steerer on CIDP unavailability

        # GAP-2 FIX (PATCH-097b): LLM-enrich the payload
        # Template strings above are scaffolding. Run them through the LLM to
        # generate a real, context-aware, natural-language steering response.
        # This is the upgrade from "template output" to "Murphy actually speaking".
        if action.payload and action.action_type != "none":
            try:
                from src.llm_provider import get_llm as _llm_get
                pattern   = signal.tribal_gravity.dominant_pattern.value
                mag_label = "high" if mag >= 0.5 else "medium" if mag >= 0.3 else "low"
                domain    = getattr(signal, "domain", "general")
                enrich_prompt = (
                    f"You are Murphy's convergence engine. You have detected a {pattern} tribal pattern "
                    f"in a content feed with {mag_label} closure ({mag:.2f}). "
                    f"Your gradient steerer has proposed this intervention:\n\n"
                    f"  Action: {action.action_type}\n"
                    f"  Draft payload: {action.payload}\n\n"
                    f"Write the final natural-language version of this steering payload. "
                    f"It must be: one or two sentences, additive (never removes options), "
                    f"transparent (never disguised as part of the feed), free-will-preserving "
                    f"(the user decides what to do with it), and domain-appropriate for: {domain}. "
                    f"Return ONLY the final payload text. No preamble, no labels."
                )
                enriched = _llm_get().complete(
                    enrich_prompt,
                    system=(
                        "You are the Murphy convergence engine's payload writer. "
                        "Write short, honest, respectful steering interventions. "
                        "Never manipulate. Always preserve free will. One to two sentences max."
                    ),
                    model_hint="chat",
                    temperature=0.4,
                    max_tokens=200,
                )
                if enriched and enriched.text and len(enriched.text.strip()) > 10:
                    action.payload = enriched.text.strip()
                    action.llm_enriched = True
                    logger.info("GradientSteerer: LLM-enriched payload (action=%s, model=%s)",
                                action.action_type, getattr(enriched, "model", "?"))
                else:
                    action.llm_enriched = False
                    logger.debug("GradientSteerer: LLM enrichment skipped (empty response)")
            except Exception as _llm_exc:
                action.llm_enriched = False
                logger.warning("GradientSteerer: LLM enrichment failed (non-blocking): %s", _llm_exc)

        logger.info(
            "GradientSteerer: %s type=%s magnitude=%.2f cidp=%s",
            action.action_id, action.action_type, action.magnitude, action.cidp_cleared,
        )
        return action


# ---------------------------------------------------------------------------
# MASTER ENGINE — the full three-body convergence
# ---------------------------------------------------------------------------

class RecursiveConvergenceEngine:
    """
    The full three-body pattern recognition engine.

    Three axes surround the decision space:
      AXIS 1: TribalGravityDetector   — what's pulling the feed closed
      AXIS 2: SignalCoherenceMapper   — what's amplified vs. absent
      AXIS 3: MiddlePathVectorComputer — the gradient toward flourishing

    The RecursiveFilter runs all three simultaneously.
    The GradientSteerer builds the action.
    CIDP clears the output.
    Free will is preserved in every path.

    fn: recursive_convergence_engine.RecursiveConvergenceEngine.process()
    """

    def __init__(self):
        self._filter  = RecursiveFilter()
        self._steerer = GradientSteerer()

    def process(
        self,
        content: str,
        feed_history: List[str] = None,
        domain: str = "general",
        session_id: str = None,
    ) -> Tuple[ConvergenceSignal, SteeringAction]:
        """
        Full pipeline: content → convergence signal → steering action.

        MSS RM5 (Implementation).

        Naming assumptions:
          session_id       — groups events into a trajectory. If None, auto-generated.
                             Use the same session_id for sequential content from one source.
          feed_history     — list of prior content strings for tribal velocity calc.
                             MSS: these are the prior content items IN THIS SESSION.
          trajectory_state — the current session's StateVector + SustainMode status
                             read from the convergence graph before computing steering.
          steering_force   — computed by TrajectoryCalculator using trajectory_state.
                             Replaces the fixed magnitude from the signal alone.
        
        Returns both the signal (diagnostic) and the action (output).
        The action is CIDP-cleared before return.
        Graph event is persisted after action is determined.
        """
        import uuid as _uuid
        if session_id is None:
            session_id = f"session-{_uuid.uuid4().hex[:12]}"

        # Run the three-axis filter
        signal = self._filter.filter(content, feed_history, domain)

        # Read prior trajectory state from graph — trajectory-aware steering
        prior_state = None
        in_sustain = False
        try:
            from src.convergence_graph import get_graph, TrajectoryCalculator, StateVector
            graph = get_graph()
            session_state = graph.get_session_state(session_id)
            if session_state:
                in_sustain = bool(session_state.get("sustain_mode_active", False))
                prior_sv_list = session_state.get("current_state")
                if prior_sv_list and len(prior_sv_list) == 8:
                    prior_state = StateVector(*prior_sv_list)
        except Exception as _graph_exc:
            logger.debug("RCE: graph read failed (non-blocking): %s", _graph_exc)

        # If session is in SustainMode — minimal steering, reinforce only
        if in_sustain:
            signal.should_steer = True
            signal.steer_reason = (
                f"SUSTAIN MODE — session is in OptimalZone. "
                f"Minimal steering: reinforce flourishing signals. "
                f"Pattern: {signal.tribal_gravity.dominant_pattern.value}"
            )
            # Override the middle path vector magnitude to sustain level
            signal.middle_path.shift_magnitude = 0.05

        # Compute trajectory-adjusted steering magnitude
        try:
            from src.convergence_graph import TrajectoryCalculator, StateVector
            calc = TrajectoryCalculator()
            # Build current StateVector from signal
            harm_prior = 0.10  # default — will be overridden if CIDP is available
            curr_state = StateVector(
                d1_flourishing=signal.coherence_map.flourishing_score,
                d2_contraction=signal.coherence_map.contraction_score,
                d3_closure=signal.tribal_gravity.closure_score,
                d4_coherence_delta=signal.coherence_map.coherence_delta,
                d5_p_harm_physical=harm_prior,
                d6_p_harm_psychological=harm_prior,
                d7_p_harm_financial=harm_prior,
                d8_p_harm_autonomy=harm_prior,
            )
            # Compute velocity if we have a prior state
            velocity = None
            if prior_state:
                from src.convergence_graph import VelocityVector
                velocity = VelocityVector.compute(prior_state, curr_state)
            # Override magnitude with trajectory-calculated force
            traj_magnitude, enters_sustain = calc.compute_steering_force(curr_state, velocity)
            if not in_sustain:
                signal.middle_path.shift_magnitude = traj_magnitude
            in_sustain = enters_sustain
        except Exception as _traj_exc:
            logger.debug("RCE: trajectory calc failed (non-blocking): %s", _traj_exc)
            curr_state = None

        # Generate steering action with trajectory-adjusted magnitude
        action = self._steerer.steer(signal)

        # Persist to convergence graph
        try:
            from src.convergence_graph import get_graph, ConvergenceEvent, StateVector
            if curr_state is not None:
                event = ConvergenceEvent(
                    event_id=f"evt-{_uuid.uuid4().hex[:10]}",
                    session_id=session_id,
                    domain=domain,
                    tribal_pattern=signal.tribal_gravity.dominant_pattern.value,
                    state=curr_state,
                    action_type=action.action_type,
                    shift_magnitude=signal.middle_path.shift_magnitude,
                    in_optimal_zone=curr_state.in_optimal_zone(),
                    in_sustain_mode=in_sustain,
                    content_hash=signal.content_hash,
                    steer_reason=signal.steer_reason[:200],
                )
                get_graph().save_event(event)
        except Exception as _save_exc:
            logger.debug("RCE: graph save failed (non-blocking): %s", _save_exc)

        return signal, action


# ---------------------------------------------------------------------------
# Module singleton + convenience function
# ---------------------------------------------------------------------------

_engine: Optional[RecursiveConvergenceEngine] = None

def get_engine() -> RecursiveConvergenceEngine:
    global _engine
    if _engine is None:
        _engine = RecursiveConvergenceEngine()
    return _engine


def process(
    content: str,
    feed_history: List[str] = None,
    domain: str = "general",
    session_id: str = None,
) -> Tuple[ConvergenceSignal, SteeringAction]:
    """Convenience function — run the full three-body convergence engine."""
    return get_engine().process(content, feed_history, domain, session_id)
