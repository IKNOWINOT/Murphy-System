"""
Historical Greatness Engine — Murphy System
=============================================

Models the **10 universal traits** shared by the most successful people across
every class in recorded history — military leaders, business titans, scientists,
artists, political leaders, athletes, philosophers, engineers, religious thinkers,
and explorers.

The engine provides:

  GreatnessTrait          — A single universal trait with historical evidence
  HistoricalClass         — 10 categories spanning all human achievement domains
  HistoricalGreat         — A modelled historical figure with per-trait scores
  GreatnessBenchmark      — Reference scores per class and across all history
  TraitProfiler           — Scores any role / genome / agent against the 10 traits
  ArchetypeMatcher        — Finds the closest historical great for any profile
  CalibrationResult       — Trait scores + archetype match + gap analysis + recs
  HistoricalGreatnessEngine — Top-level façade

The 10 Universal Traits of Historical Greatness
------------------------------------------------

  1. OBSESSIVE_FOCUS          — Single-minded pursuit; deep work over distraction
  2. EXTREME_PREPARATION      — Over-prepare then act with decisive speed
  3. FAILURE_AS_DATA          — Reframe setbacks as information, never as identity
  4. PATTERN_RECOGNITION      — See connections and signal others miss
  5. RADICAL_SELF_BELIEF      — Operate at/beyond consensus; hold conviction alone
  6. CROSS_DOMAIN_LEARNING    — Voraciously learn outside your primary domain
  7. NARRATIVE_MASTERY        — Move people with words, story, and framing
  8. ADAPTIVE_STRATEGY        — Change approach while holding vision constant
  9. NETWORK_LEVERAGE         — Build and activate compounding human networks
  10. LONG_GAME_THINKING      — Sacrifice short-term comfort for long-term dominance

Design Label: HGE-001 — Historical Greatness Engine
Owner:        Platform Engineering / Agent Intelligence
License:      BSL 1.1

Copyright © 2020 Inoni Limited Liability Company
Creator:      Corey Post
"""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class GreatnessTrait(str, Enum):
    """The 10 universal traits of historical greatness."""
    OBSESSIVE_FOCUS       = "obsessive_focus"
    EXTREME_PREPARATION   = "extreme_preparation"
    FAILURE_AS_DATA       = "failure_as_data"
    PATTERN_RECOGNITION   = "pattern_recognition"
    RADICAL_SELF_BELIEF   = "radical_self_belief"
    CROSS_DOMAIN_LEARNING = "cross_domain_learning"
    NARRATIVE_MASTERY     = "narrative_mastery"
    ADAPTIVE_STRATEGY     = "adaptive_strategy"
    NETWORK_LEVERAGE      = "network_leverage"
    LONG_GAME_THINKING    = "long_game_thinking"


ALL_TRAITS: List[GreatnessTrait] = list(GreatnessTrait)


class HistoricalClass(str, Enum):
    """Categories of human achievement across history."""
    MILITARY    = "military"
    BUSINESS    = "business"
    SCIENCE     = "science"
    ARTS        = "arts"
    POLITICS    = "politics"
    ATHLETICS   = "athletics"
    PHILOSOPHY  = "philosophy"
    ENGINEERING = "engineering"
    SPIRITUAL   = "spiritual"
    EXPLORATION = "exploration"


# ---------------------------------------------------------------------------
# Trait definitions — canonical descriptions + historical evidence
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TraitDefinition:
    """Canonical definition of one universal greatness trait."""
    trait: GreatnessTrait
    name: str
    description: str
    core_question: str          # The diagnostic question that reveals this trait
    evidence_phrase: str        # How this trait manifests in great people
    modern_equivalent: str      # What this maps to in a professional context
    anti_pattern: str           # The failure mode / absence of this trait
    historical_epitome: str     # The single best historical example
    epitome_quote: str          # A quote that captures it perfectly


TRAIT_DEFINITIONS: Dict[GreatnessTrait, TraitDefinition] = {
    GreatnessTrait.OBSESSIVE_FOCUS: TraitDefinition(
        trait=GreatnessTrait.OBSESSIVE_FOCUS,
        name="Obsessive Focus",
        description=(
            "The ability to lock onto a single pursuit with total commitment for years "
            "or decades, excluding or subordinating everything else. The greats did not "
            "multitask — they mono-tasked at extreme depth."
        ),
        core_question="Can you say no to everything good in order to do the one great thing?",
        evidence_phrase=(
            "Newton spent 18-hour days on Principia for 18 months. Michelangelo slept "
            "in his clothes to avoid losing work time. Jobs returned to Apple and killed "
            "350 of 400 products, keeping 10."
        ),
        modern_equivalent="Deep work capacity; ability to hold context for 6+ months on one outcome",
        anti_pattern="Shiny-object syndrome; context-switching; diluted effort across many goals",
        historical_epitome="Isaac Newton",
        epitome_quote=(
            "If I have made any valuable discoveries, it has been owing more to patient "
            "attention than to any other talent. — Isaac Newton"
        ),
    ),

    GreatnessTrait.EXTREME_PREPARATION: TraitDefinition(
        trait=GreatnessTrait.EXTREME_PREPARATION,
        name="Extreme Preparation",
        description=(
            "Obsessive study of the domain before acting. The greats were not reckless "
            "improvisers — they out-prepared everyone, then acted with speed that looked "
            "like intuition but was built on encyclopedic preparation."
        ),
        core_question="Do you know the domain better than anyone who came before you?",
        evidence_phrase=(
            "Napoleon memorised every road, river, and village in Europe before his campaigns. "
            "Lincoln read every legal text in Illinois self-taught. Jordan watched game film "
            "for hours before every series. Buffett read 500 pages a day for decades."
        ),
        modern_equivalent="Domain mastery; data-driven decision-making; pre-mortem and scenario planning",
        anti_pattern="Ready-fire-aim; improvising from ignorance; confusing confidence with preparation",
        historical_epitome="Napoleon Bonaparte",
        epitome_quote=(
            "If I always appear prepared, it is because before entering an undertaking, "
            "I have meditated long and have foreseen what might occur. — Napoleon Bonaparte"
        ),
    ),

    GreatnessTrait.FAILURE_AS_DATA: TraitDefinition(
        trait=GreatnessTrait.FAILURE_AS_DATA,
        name="Failure as Data",
        description=(
            "The cognitive reframe that treats every failure as information rather than "
            "identity. The greats had an unusual relationship with failure — they expected "
            "it, catalogued it, and iterated from it without existential despair."
        ),
        core_question="Does failing make you faster or does it make you stop?",
        evidence_phrase=(
            "Edison ran 10,000 experiments before the light bulb. Lincoln lost 7 elections "
            "before the presidency. Jordan was cut from his high school team. Rowling "
            "received 12 rejections for Harry Potter. Walt Disney went bankrupt twice."
        ),
        modern_equivalent="Learning velocity; psychological safety; A/B testing culture; blameless post-mortems",
        anti_pattern="Failure avoidance; perfectionism paralysis; internalising outcomes as identity",
        historical_epitome="Thomas Edison",
        epitome_quote=(
            "I have not failed. I've just found 10,000 ways that won't work. — Thomas Edison"
        ),
    ),

    GreatnessTrait.PATTERN_RECOGNITION: TraitDefinition(
        trait=GreatnessTrait.PATTERN_RECOGNITION,
        name="Pattern Recognition",
        description=(
            "The ability to extract signal from noise — to see structural similarities "
            "across domains, anticipate second-order consequences, and identify the "
            "underlying pattern before others even see the data."
        ),
        core_question="Do you see what's really happening, not what everyone says is happening?",
        evidence_phrase=(
            "Da Vinci saw engineering patterns in bird flight 400 years before aviation. "
            "Einstein ran thought experiments to find patterns in physics before maths confirmed them. "
            "Jobs connected calligraphy to computer typography. Bezos saw the pattern of "
            "everything being a platform before anyone else."
        ),
        modern_equivalent="Systems thinking; first-principles reasoning; market timing; trend detection",
        anti_pattern="Recency bias; local optimisation; cargo-culting without understanding why",
        historical_epitome="Leonardo da Vinci",
        epitome_quote=(
            "The noblest pleasure is the joy of understanding. — Leonardo da Vinci"
        ),
    ),

    GreatnessTrait.RADICAL_SELF_BELIEF: TraitDefinition(
        trait=GreatnessTrait.RADICAL_SELF_BELIEF,
        name="Radical Self-Belief",
        description=(
            "The unwavering conviction that you are right when the entire world says "
            "you are wrong. Not arrogance — a calibrated, evidence-tested belief in "
            "your own vision that allows you to hold course under maximum social pressure."
        ),
        core_question="Can you hold your position when every authority in the room disagrees?",
        evidence_phrase=(
            "Galileo held heliocentrism under house arrest. Columbus sailed west despite "
            "every expert saying he would fall off. Tesla believed in AC power when Edison's "
            "entire empire ran on DC. Bezos held Amazon to zero profits for 20 years "
            "while Wall Street demanded dividends."
        ),
        modern_equivalent="Founder conviction; non-consensus bets; staying the course through market pressure",
        anti_pattern="Consensus-seeking; HiPPO-driven decisions; changing course from social pressure",
        historical_epitome="Galileo Galilei",
        epitome_quote=(
            "And yet it moves. — Galileo Galilei (attributed, on his heliocentrism)"
        ),
    ),

    GreatnessTrait.CROSS_DOMAIN_LEARNING: TraitDefinition(
        trait=GreatnessTrait.CROSS_DOMAIN_LEARNING,
        name="Cross-Domain Learning",
        description=(
            "Voracious, systematic learning across domains far outside your primary "
            "expertise. The greats treated every discipline as a source of mental models "
            "that could be imported into their core domain."
        ),
        core_question="How many fields outside your own are you actively studying right now?",
        evidence_phrase=(
            "Aristotle covered philosophy, biology, physics, ethics, rhetoric, and politics. "
            "Franklin was scientist, diplomat, writer, inventor, and economist. Da Vinci studied "
            "anatomy, music, architecture, and optics. Munger built 100+ mental models from "
            "a dozen disciplines. Darwin read geology, economics, and pigeon breeding to "
            "assemble evolution."
        ),
        modern_equivalent="T-shaped expertise; second-order thinking; reading outside your domain; lateral transfer",
        anti_pattern="Domain silo; refusing to learn from adjacent fields; 'not my job' thinking",
        historical_epitome="Benjamin Franklin",
        epitome_quote=(
            "An investment in knowledge pays the best interest. — Benjamin Franklin"
        ),
    ),

    GreatnessTrait.NARRATIVE_MASTERY: TraitDefinition(
        trait=GreatnessTrait.NARRATIVE_MASTERY,
        name="Narrative Mastery",
        description=(
            "The ability to move people with words, story, and frame. Every great leader, "
            "builder, or creator had an extraordinary command of narrative — they could "
            "articulate a vision so compellingly that others would sacrifice everything to "
            "join it."
        ),
        core_question="Can you make someone feel your vision as viscerally as you feel it?",
        evidence_phrase=(
            "Lincoln's Gettysburg Address reframed a war about union as a war about freedom. "
            "Churchill's 'We Shall Fight on the Beaches' held a nation together through "
            "existential threat. Jobs's 'one more thing' made consumers feel they were "
            "witnessing history. King's 'I Have a Dream' moved a generation to act."
        ),
        modern_equivalent="Storytelling; investor narrative; product vision; keynotes; written communication",
        anti_pattern="Feature-list thinking; jargon-heavy communication; failing to connect data to human stakes",
        historical_epitome="Winston Churchill",
        epitome_quote=(
            "We shall fight on the beaches, we shall fight on the landing grounds, "
            "we shall fight in the fields — we shall never surrender. — Winston Churchill"
        ),
    ),

    GreatnessTrait.ADAPTIVE_STRATEGY: TraitDefinition(
        trait=GreatnessTrait.ADAPTIVE_STRATEGY,
        name="Adaptive Strategy",
        description=(
            "The ability to change tactics and approach while holding the ultimate "
            "objective constant. The greats were not rigid — they were fluid in method "
            "but unwavering in destination."
        ),
        core_question="Can you change everything about how you're winning without changing what you're winning?",
        evidence_phrase=(
            "Napoleon invented a new battle doctrine for every major engagement. Darwin "
            "waited 20 years before publishing, then moved in 13 months when Wallace "
            "threatened to scoop him. Bezos: 'We are stubborn on vision, flexible on detail.' "
            "Lincoln changed his Cabinet, his generals, and his war strategy five times "
            "without changing his goal."
        ),
        modern_equivalent="Pivot discipline; product-market fit iteration; strategy vs. tactics separation",
        anti_pattern="Rigidity; changing the goal because the path got hard; reactive without a north star",
        historical_epitome="Jeff Bezos",
        epitome_quote=(
            "We are stubborn on vision. We are flexible on details. — Jeff Bezos"
        ),
    ),

    GreatnessTrait.NETWORK_LEVERAGE: TraitDefinition(
        trait=GreatnessTrait.NETWORK_LEVERAGE,
        name="Network Leverage",
        description=(
            "Building and activating compounding networks of people, resources, and "
            "information that multiply individual capability. The greats understood they "
            "could not do it alone — they built systems of humans as intentionally as "
            "they built anything else."
        ),
        core_question="Is your network growing faster than your competition's, and is it the right network?",
        evidence_phrase=(
            "Caesar built political alliances that rivalled his military campaigns. "
            "The Medici built Europe's greatest patron network. Carnegie built a steel "
            "network that created 65 billionaires. Rockefeller built supplier networks "
            "that crushed Standard Oil's competition. Jobs recruited 'A-players' who "
            "refused to work with B-players."
        ),
        modern_equivalent="Hiring excellence; board relationships; channel partnerships; community building",
        anti_pattern="Lone-wolf execution; not delegating; building a team of generalists when you need specialists",
        historical_epitome="Julius Caesar",
        epitome_quote=(
            "It is easier to find men who will volunteer to die than men who are willing "
            "to endure pain with patience. — Julius Caesar"
        ),
    ),

    GreatnessTrait.LONG_GAME_THINKING: TraitDefinition(
        trait=GreatnessTrait.LONG_GAME_THINKING,
        name="Long-Game Thinking",
        description=(
            "The willingness to make moves that look suboptimal or even irrational in "
            "the short term because they compound into overwhelming advantage over time. "
            "The greats out-waited, out-compounded, and out-positioned the competition."
        ),
        core_question="Are you building a cathedral or decorating a tent?",
        evidence_phrase=(
            "Buffett compounded at 20%/yr for 70 years. Amazon ran losses for 20 years "
            "while building infrastructure competitors could never replicate. Lincoln spent "
            "2 years building political capital before making any major move. Marcus Aurelius "
            "ruled for 19 years building institutions that outlasted him by 200 years."
        ),
        modern_equivalent="Compound growth; platform thinking; building moats; patient capital deployment",
        anti_pattern="Quarter-to-quarter thinking; optimising for optics over outcomes; burning goodwill for speed",
        historical_epitome="Warren Buffett",
        epitome_quote=(
            "Someone is sitting in the shade today because someone planted a tree a long "
            "time ago. — Warren Buffett"
        ),
    ),
}


# ---------------------------------------------------------------------------
# Historical Greats — 50+ modelled across all 10 classes
# Scores are per-trait on a 0.0–1.0 scale (1.0 = definitional example)
# Order matches ALL_TRAITS tuple order
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class HistoricalGreat:
    """A modelled historical figure with per-trait greatness scores."""
    great_id: str
    name: str
    era: str                            # e.g. "384–322 BC"
    primary_class: HistoricalClass
    secondary_classes: Tuple[HistoricalClass, ...]
    trait_scores: Dict[GreatnessTrait, float]   # 0–1 per trait
    signature_achievement: str
    core_lesson: str                    # What every person can learn from this figure

    @property
    def overall_score(self) -> float:
        vals = list(self.trait_scores.values())
        return round(sum(vals) / len(vals), 4) if vals else 0.0

    @property
    def peak_trait(self) -> Tuple[GreatnessTrait, float]:
        return max(self.trait_scores.items(), key=lambda kv: kv[1])

    def distance_to(self, scores: Dict[GreatnessTrait, float]) -> float:
        """Euclidean distance in trait space between this great and a given score dict."""
        diffs = []
        for trait in ALL_TRAITS:
            a = self.trait_scores.get(trait, 0.0)
            b = scores.get(trait, 0.0)
            diffs.append((a - b) ** 2)
        return round(math.sqrt(sum(diffs)), 4)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "great_id": self.great_id,
            "name": self.name,
            "era": self.era,
            "primary_class": self.primary_class.value,
            "secondary_classes": [c.value for c in self.secondary_classes],
            "trait_scores": {t.value: s for t, s in self.trait_scores.items()},
            "overall_score": self.overall_score,
            "peak_trait": {self.peak_trait[0].value: self.peak_trait[1]},
            "signature_achievement": self.signature_achievement,
            "core_lesson": self.core_lesson,
        }


def _t(**kw: float) -> Dict[GreatnessTrait, float]:
    """Helper: build trait dict from keyword args (maps short name → GreatnessTrait)."""
    _MAP = {
        "focus": GreatnessTrait.OBSESSIVE_FOCUS,
        "prep":  GreatnessTrait.EXTREME_PREPARATION,
        "fail":  GreatnessTrait.FAILURE_AS_DATA,
        "patt":  GreatnessTrait.PATTERN_RECOGNITION,
        "self":  GreatnessTrait.RADICAL_SELF_BELIEF,
        "cross": GreatnessTrait.CROSS_DOMAIN_LEARNING,
        "narr":  GreatnessTrait.NARRATIVE_MASTERY,
        "adap":  GreatnessTrait.ADAPTIVE_STRATEGY,
        "netw":  GreatnessTrait.NETWORK_LEVERAGE,
        "long":  GreatnessTrait.LONG_GAME_THINKING,
    }
    return {_MAP[k]: v for k, v in kw.items()}


def _build_historical_greats() -> Dict[str, HistoricalGreat]:
    """Build the canonical library of 50+ modelled historical greats."""
    greats: List[HistoricalGreat] = [

        # ── Military ────────────────────────────────────────────────────────
        HistoricalGreat(
            great_id="alexander_great",
            name="Alexander the Great",
            era="356–323 BC",
            primary_class=HistoricalClass.MILITARY,
            secondary_classes=(HistoricalClass.POLITICS, HistoricalClass.EXPLORATION),
            trait_scores=_t(focus=0.96, prep=0.92, fail=0.88, patt=0.97, self=0.99,
                            cross=0.90, narr=0.95, adap=0.97, netw=0.94, long=0.85),
            signature_achievement="Conquered 90% of the known world by age 32",
            core_lesson=(
                "Speed + surprise + psychological dominance beats superior numbers. "
                "Move faster than the enemy can think."
            ),
        ),
        HistoricalGreat(
            great_id="napoleon",
            name="Napoleon Bonaparte",
            era="1769–1821",
            primary_class=HistoricalClass.MILITARY,
            secondary_classes=(HistoricalClass.POLITICS, HistoricalClass.ENGINEERING),
            trait_scores=_t(focus=0.97, prep=1.00, fail=0.82, patt=0.98, self=0.99,
                            cross=0.93, narr=0.96, adap=0.95, netw=0.92, long=0.78),
            signature_achievement="Rewrote European law, education, and military doctrine simultaneously",
            core_lesson=(
                "Preparation is the force multiplier. Genius is knowing your material "
                "better than anyone else, then acting faster."
            ),
        ),
        HistoricalGreat(
            great_id="sun_tzu",
            name="Sun Tzu",
            era="544–496 BC",
            primary_class=HistoricalClass.MILITARY,
            secondary_classes=(HistoricalClass.PHILOSOPHY,),
            trait_scores=_t(focus=0.97, prep=0.95, fail=0.90, patt=0.99, self=0.95,
                            cross=0.92, narr=0.96, adap=0.99, netw=0.85, long=0.97),
            signature_achievement="The Art of War — still the definitive text on strategy 2,500 years later",
            core_lesson=(
                "Win without fighting. The highest form of strategy makes the battle "
                "unnecessary by shaping conditions before conflict begins."
            ),
        ),
        HistoricalGreat(
            great_id="eisenhower",
            name="Dwight D. Eisenhower",
            era="1890–1969",
            primary_class=HistoricalClass.MILITARY,
            secondary_classes=(HistoricalClass.POLITICS,),
            trait_scores=_t(focus=0.90, prep=0.98, fail=0.88, patt=0.93, self=0.90,
                            cross=0.85, narr=0.85, adap=0.90, netw=0.97, long=0.95),
            signature_achievement="Coordinated the largest amphibious operation in history (D-Day)",
            core_lesson=(
                "Plans are useless; planning is indispensable. Build coalitions, "
                "and let the plan adapt but never let the objective waver."
            ),
        ),

        # ── Business ────────────────────────────────────────────────────────
        HistoricalGreat(
            great_id="carnegie_andrew",
            name="Andrew Carnegie",
            era="1835–1919",
            primary_class=HistoricalClass.BUSINESS,
            secondary_classes=(HistoricalClass.PHILOSOPHY,),
            trait_scores=_t(focus=0.95, prep=0.90, fail=0.95, patt=0.94, self=0.96,
                            cross=0.88, narr=0.90, adap=0.92, netw=0.97, long=0.96),
            signature_achievement="Built the US steel industry; gave away $350M (≈$5B today)",
            core_lesson=(
                "Build the best team money can hire, then get out of their way. "
                "The man who dies rich dies disgraced."
            ),
        ),
        HistoricalGreat(
            great_id="rockefeller",
            name="John D. Rockefeller",
            era="1839–1937",
            primary_class=HistoricalClass.BUSINESS,
            secondary_classes=(HistoricalClass.ENGINEERING,),
            trait_scores=_t(focus=0.99, prep=0.97, fail=0.90, patt=0.97, self=0.96,
                            cross=0.85, narr=0.82, adap=0.90, netw=0.98, long=0.99),
            signature_achievement="Built Standard Oil to control 90% of US oil refining",
            core_lesson=(
                "Control the infrastructure, not just the product. "
                "The person who owns the pipeline owns the industry."
            ),
        ),
        HistoricalGreat(
            great_id="steve_jobs",
            name="Steve Jobs",
            era="1955–2011",
            primary_class=HistoricalClass.BUSINESS,
            secondary_classes=(HistoricalClass.ARTS, HistoricalClass.ENGINEERING),
            trait_scores=_t(focus=1.00, prep=0.90, fail=0.92, patt=0.97, self=1.00,
                            cross=0.95, narr=0.99, adap=0.92, netw=0.88, long=0.93),
            signature_achievement="Created the iPhone — the most profitable product in human history",
            core_lesson=(
                "The intersection of technology and liberal arts is where the future lives. "
                "Design is not how it looks; design is how it works."
            ),
        ),
        HistoricalGreat(
            great_id="jeff_bezos",
            name="Jeff Bezos",
            era="1964–",
            primary_class=HistoricalClass.BUSINESS,
            secondary_classes=(HistoricalClass.ENGINEERING, HistoricalClass.EXPLORATION),
            trait_scores=_t(focus=0.98, prep=0.95, fail=0.96, patt=0.98, self=0.97,
                            cross=0.92, narr=0.90, adap=1.00, netw=0.93, long=1.00),
            signature_achievement="Built Amazon into a $2T platform across retail, cloud, and logistics",
            core_lesson=(
                "Stubborn on vision; flexible on detail. Day-1 thinking means acting like "
                "the startup every single day regardless of size."
            ),
        ),
        HistoricalGreat(
            great_id="warren_buffett",
            name="Warren Buffett",
            era="1930–",
            primary_class=HistoricalClass.BUSINESS,
            secondary_classes=(HistoricalClass.PHILOSOPHY,),
            trait_scores=_t(focus=0.98, prep=1.00, fail=0.95, patt=0.99, self=0.97,
                            cross=0.92, narr=0.92, adap=0.85, netw=0.93, long=1.00),
            signature_achievement="Compounded $10K into $100B+ over 70 years",
            core_lesson=(
                "Time is the friend of the wonderful business and the enemy of the mediocre. "
                "The most important investment is in yourself."
            ),
        ),
        HistoricalGreat(
            great_id="henry_ford",
            name="Henry Ford",
            era="1863–1947",
            primary_class=HistoricalClass.BUSINESS,
            secondary_classes=(HistoricalClass.ENGINEERING,),
            trait_scores=_t(focus=0.97, prep=0.90, fail=0.90, patt=0.96, self=0.97,
                            cross=0.85, narr=0.88, adap=0.82, netw=0.92, long=0.95),
            signature_achievement="Democratised the automobile and invented mass-production",
            core_lesson=(
                "Don't find a fault; find a remedy. "
                "The assembly line is not a factory trick — it is a philosophy of systems."
            ),
        ),

        # ── Science ─────────────────────────────────────────────────────────
        HistoricalGreat(
            great_id="isaac_newton",
            name="Isaac Newton",
            era="1643–1727",
            primary_class=HistoricalClass.SCIENCE,
            secondary_classes=(HistoricalClass.MATHEMATICS,) if False else (HistoricalClass.PHILOSOPHY,),
            trait_scores=_t(focus=1.00, prep=0.98, fail=0.90, patt=1.00, self=0.95,
                            cross=0.92, narr=0.75, adap=0.80, netw=0.72, long=0.95),
            signature_achievement="Invented calculus and classical mechanics in 18 months during a plague",
            core_lesson=(
                "Patient attention beats raw talent. Genius is not a gift — "
                "it is the willingness to sit with a problem longer than anyone else."
            ),
        ),
        HistoricalGreat(
            great_id="marie_curie",
            name="Marie Curie",
            era="1867–1934",
            primary_class=HistoricalClass.SCIENCE,
            secondary_classes=(HistoricalClass.ENGINEERING,),
            trait_scores=_t(focus=0.99, prep=0.97, fail=0.97, patt=0.96, self=0.98,
                            cross=0.88, narr=0.80, adap=0.88, netw=0.82, long=0.93),
            signature_achievement="First person to win two Nobel Prizes in two different sciences",
            core_lesson=(
                "Nothing in life is to be feared — it is only to be understood. "
                "Barriers are not walls; they are problems waiting for the right method."
            ),
        ),
        HistoricalGreat(
            great_id="albert_einstein",
            name="Albert Einstein",
            era="1879–1955",
            primary_class=HistoricalClass.SCIENCE,
            secondary_classes=(HistoricalClass.PHILOSOPHY,),
            trait_scores=_t(focus=0.97, prep=0.93, fail=0.95, patt=1.00, self=0.98,
                            cross=0.95, narr=0.88, adap=0.90, netw=0.82, long=0.93),
            signature_achievement="Special and general relativity — redefined space, time, and energy",
            core_lesson=(
                "Imagination is more important than knowledge. "
                "Thought experiments are how you find truth when measurement is impossible."
            ),
        ),
        HistoricalGreat(
            great_id="nikola_tesla",
            name="Nikola Tesla",
            era="1856–1943",
            primary_class=HistoricalClass.SCIENCE,
            secondary_classes=(HistoricalClass.ENGINEERING,),
            trait_scores=_t(focus=0.99, prep=0.95, fail=0.85, patt=0.99, self=0.97,
                            cross=0.88, narr=0.75, adap=0.80, netw=0.72, long=0.88),
            signature_achievement="Invented AC power — the infrastructure that powers the modern world",
            core_lesson=(
                "The present is theirs; the future, for which I really worked, is mine. "
                "Network leverage is not optional — even genius needs an ally."
            ),
        ),
        HistoricalGreat(
            great_id="charles_darwin",
            name="Charles Darwin",
            era="1809–1882",
            primary_class=HistoricalClass.SCIENCE,
            secondary_classes=(HistoricalClass.PHILOSOPHY, HistoricalClass.EXPLORATION),
            trait_scores=_t(focus=0.98, prep=0.98, fail=0.93, patt=0.99, self=0.93,
                            cross=0.98, narr=0.88, adap=0.90, netw=0.88, long=0.98),
            signature_achievement="On the Origin of Species — the most consequential scientific idea ever published",
            core_lesson=(
                "It is not the strongest that survive, nor the most intelligent, "
                "but the most responsive to change. Evidence > conviction."
            ),
        ),

        # ── Arts ────────────────────────────────────────────────────────────
        HistoricalGreat(
            great_id="da_vinci",
            name="Leonardo da Vinci",
            era="1452–1519",
            primary_class=HistoricalClass.ARTS,
            secondary_classes=(HistoricalClass.SCIENCE, HistoricalClass.ENGINEERING),
            trait_scores=_t(focus=0.93, prep=0.97, fail=0.92, patt=1.00, self=0.95,
                            cross=1.00, narr=0.90, adap=0.95, netw=0.85, long=0.90),
            signature_achievement="The Mona Lisa + flying machine designs + anatomical drawings — all centuries ahead",
            core_lesson=(
                "The greatest curiosity is the engine of all discovery. "
                "The boundary between art and science is a human invention."
            ),
        ),
        HistoricalGreat(
            great_id="michelangelo",
            name="Michelangelo",
            era="1475–1564",
            primary_class=HistoricalClass.ARTS,
            secondary_classes=(HistoricalClass.ENGINEERING,),
            trait_scores=_t(focus=1.00, prep=0.98, fail=0.92, patt=0.95, self=0.97,
                            cross=0.88, narr=0.85, adap=0.85, netw=0.82, long=0.90),
            signature_achievement="Sistine Chapel ceiling; David; St Peter's Basilica dome",
            core_lesson=(
                "The greatest danger is not that our aim is too high and we miss it, "
                "but that it is too low and we hit it. Standards are a choice."
            ),
        ),
        HistoricalGreat(
            great_id="beethoven",
            name="Ludwig van Beethoven",
            era="1770–1827",
            primary_class=HistoricalClass.ARTS,
            secondary_classes=(),
            trait_scores=_t(focus=1.00, prep=0.97, fail=0.98, patt=0.97, self=1.00,
                            cross=0.88, narr=0.95, adap=0.92, netw=0.75, long=0.92),
            signature_achievement="Composed his greatest masterworks (9th Symphony) after going completely deaf",
            core_lesson=(
                "Limitation is often the mother of invention. "
                "What you create with constraints reveals your true capability."
            ),
        ),
        HistoricalGreat(
            great_id="shakespeare",
            name="William Shakespeare",
            era="1564–1616",
            primary_class=HistoricalClass.ARTS,
            secondary_classes=(HistoricalClass.PHILOSOPHY,),
            trait_scores=_t(focus=0.97, prep=0.92, fail=0.90, patt=0.98, self=0.92,
                            cross=0.95, narr=1.00, adap=0.93, netw=0.88, long=0.88),
            signature_achievement="37 plays and 154 sonnets — the most studied body of work in human history",
            core_lesson=(
                "All the world's a stage. To understand people, you must become them "
                "on the page first. The deepest truth is always human truth."
            ),
        ),

        # ── Politics ────────────────────────────────────────────────────────
        HistoricalGreat(
            great_id="lincoln",
            name="Abraham Lincoln",
            era="1809–1865",
            primary_class=HistoricalClass.POLITICS,
            secondary_classes=(HistoricalClass.PHILOSOPHY,),
            trait_scores=_t(focus=0.95, prep=0.97, fail=0.99, patt=0.95, self=0.97,
                            cross=0.95, narr=0.99, adap=0.97, netw=0.95, long=0.97),
            signature_achievement="Preserved the Union and abolished slavery against every political and military odd",
            core_lesson=(
                "Give me six hours to chop down a tree and I will spend the first four "
                "sharpening the axe. Preparation, not talent, is the great equaliser."
            ),
        ),
        HistoricalGreat(
            great_id="churchill",
            name="Winston Churchill",
            era="1874–1965",
            primary_class=HistoricalClass.POLITICS,
            secondary_classes=(HistoricalClass.MILITARY, HistoricalClass.ARTS),
            trait_scores=_t(focus=0.93, prep=0.93, fail=0.97, patt=0.95, self=0.99,
                            cross=0.92, narr=1.00, adap=0.92, netw=0.92, long=0.92),
            signature_achievement="Led Britain from the edge of capitulation to Allied victory",
            core_lesson=(
                "Success is not final; failure is not fatal. It is the courage to "
                "continue that counts. Words are the most powerful weapon ever made."
            ),
        ),
        HistoricalGreat(
            great_id="caesar",
            name="Julius Caesar",
            era="100–44 BC",
            primary_class=HistoricalClass.POLITICS,
            secondary_classes=(HistoricalClass.MILITARY, HistoricalClass.ENGINEERING),
            trait_scores=_t(focus=0.97, prep=0.97, fail=0.90, patt=0.97, self=0.99,
                            cross=0.93, narr=0.97, adap=0.97, netw=1.00, long=0.92),
            signature_achievement="Transformed Rome from a republic to the foundation of an empire",
            core_lesson=(
                "Experience is the teacher of all things. Network is not connections — "
                "it is loyalty earned through results and generosity."
            ),
        ),
        HistoricalGreat(
            great_id="marcus_aurelius",
            name="Marcus Aurelius",
            era="121–180 AD",
            primary_class=HistoricalClass.POLITICS,
            secondary_classes=(HistoricalClass.PHILOSOPHY,),
            trait_scores=_t(focus=0.95, prep=0.93, fail=0.98, patt=0.95, self=0.93,
                            cross=0.97, narr=0.93, adap=0.93, netw=0.88, long=0.99),
            signature_achievement="Ruled the Roman Empire for 19 years while writing Meditations — still studied today",
            core_lesson=(
                "You have power over your mind, not outside events. Realise this and you "
                "will find strength. Practise daily. Write it down."
            ),
        ),
        HistoricalGreat(
            great_id="mandela",
            name="Nelson Mandela",
            era="1918–2013",
            primary_class=HistoricalClass.POLITICS,
            secondary_classes=(HistoricalClass.PHILOSOPHY,),
            trait_scores=_t(focus=0.97, prep=0.90, fail=1.00, patt=0.92, self=1.00,
                            cross=0.88, narr=0.97, adap=0.93, netw=0.92, long=1.00),
            signature_achievement="Ended apartheid, served 27 years in prison without losing conviction",
            core_lesson=(
                "It always seems impossible until it's done. The long game is not just "
                "patience — it is using every year to prepare for the moment."
            ),
        ),
        HistoricalGreat(
            great_id="eleanor_roosevelt",
            name="Eleanor Roosevelt",
            era="1884–1962",
            primary_class=HistoricalClass.POLITICS,
            secondary_classes=(HistoricalClass.PHILOSOPHY,),
            trait_scores=_t(focus=0.92, prep=0.90, fail=0.97, patt=0.90, self=0.95,
                            cross=0.90, narr=0.95, adap=0.92, netw=0.93, long=0.90),
            signature_achievement="Authored the Universal Declaration of Human Rights",
            core_lesson=(
                "Do one thing every day that scares you. "
                "You gain strength every time you face fear directly."
            ),
        ),

        # ── Athletics ───────────────────────────────────────────────────────
        HistoricalGreat(
            great_id="muhammad_ali",
            name="Muhammad Ali",
            era="1942–2016",
            primary_class=HistoricalClass.ATHLETICS,
            secondary_classes=(HistoricalClass.POLITICS,),
            trait_scores=_t(focus=0.98, prep=0.97, fail=0.95, patt=0.95, self=1.00,
                            cross=0.85, narr=0.98, adap=0.93, netw=0.90, long=0.93),
            signature_achievement="Three-time heavyweight world champion; fought for civil rights at career cost",
            core_lesson=(
                "It's not bragging if you can back it up. "
                "Psychological warfare is half the fight — win the mind first."
            ),
        ),
        HistoricalGreat(
            great_id="michael_jordan",
            name="Michael Jordan",
            era="1963–",
            primary_class=HistoricalClass.ATHLETICS,
            secondary_classes=(HistoricalClass.BUSINESS,),
            trait_scores=_t(focus=1.00, prep=0.99, fail=0.98, patt=0.97, self=0.99,
                            cross=0.82, narr=0.88, adap=0.95, netw=0.88, long=0.93),
            signature_achievement="6 NBA championships, 6 Finals MVPs — redefined athletic excellence",
            core_lesson=(
                "I've missed more than 9,000 shots. I've lost almost 300 games. "
                "I've failed over and over. That is why I succeed."
            ),
        ),
        HistoricalGreat(
            great_id="serena_williams",
            name="Serena Williams",
            era="1981–",
            primary_class=HistoricalClass.ATHLETICS,
            secondary_classes=(HistoricalClass.BUSINESS,),
            trait_scores=_t(focus=0.99, prep=0.98, fail=0.97, patt=0.93, self=0.99,
                            cross=0.82, narr=0.88, adap=0.95, netw=0.85, long=0.95),
            signature_achievement="23 Grand Slam singles titles — the most dominant racket sport record in history",
            core_lesson=(
                "I really think a champion is defined not by their wins but by how they "
                "can recover when they fall. Resilience is the real skill."
            ),
        ),
        HistoricalGreat(
            great_id="ayrton_senna",
            name="Ayrton Senna",
            era="1960–1994",
            primary_class=HistoricalClass.ATHLETICS,
            secondary_classes=(HistoricalClass.ENGINEERING,),
            trait_scores=_t(focus=1.00, prep=0.98, fail=0.93, patt=0.98, self=0.99,
                            cross=0.88, narr=0.82, adap=0.95, netw=0.82, long=0.88),
            signature_achievement="Three F1 World Championships; revolutionised car setup engineering",
            core_lesson=(
                "And so you touch this limit, something happens and you suddenly can go "
                "a little bit further. Obsession is the engine of mastery."
            ),
        ),

        # ── Philosophy ──────────────────────────────────────────────────────
        HistoricalGreat(
            great_id="aristotle",
            name="Aristotle",
            era="384–322 BC",
            primary_class=HistoricalClass.PHILOSOPHY,
            secondary_classes=(HistoricalClass.SCIENCE, HistoricalClass.POLITICS),
            trait_scores=_t(focus=0.95, prep=0.97, fail=0.88, patt=0.99, self=0.92,
                            cross=1.00, narr=0.92, adap=0.90, netw=0.92, long=0.95),
            signature_achievement="Codified logic, ethics, biology, rhetoric, politics — the first encyclopaedist",
            core_lesson=(
                "We are what we repeatedly do. Excellence is not an act but a habit. "
                "Build systems of thought, not just ideas."
            ),
        ),
        HistoricalGreat(
            great_id="socrates",
            name="Socrates",
            era="470–399 BC",
            primary_class=HistoricalClass.PHILOSOPHY,
            secondary_classes=(),
            trait_scores=_t(focus=0.97, prep=0.90, fail=0.95, patt=0.97, self=0.99,
                            cross=0.90, narr=0.97, adap=0.88, netw=0.90, long=0.88),
            signature_achievement="Invented the Socratic method — still the best tool for eliciting truth",
            core_lesson=(
                "The unexamined life is not worth living. Questions are more powerful "
                "than answers. The best teacher makes the student discover for themselves."
            ),
        ),
        HistoricalGreat(
            great_id="benjamin_franklin",
            name="Benjamin Franklin",
            era="1706–1790",
            primary_class=HistoricalClass.PHILOSOPHY,
            secondary_classes=(HistoricalClass.SCIENCE, HistoricalClass.POLITICS, HistoricalClass.ENGINEERING),
            trait_scores=_t(focus=0.88, prep=0.92, fail=0.93, patt=0.96, self=0.92,
                            cross=1.00, narr=0.95, adap=0.95, netw=0.97, long=0.95),
            signature_achievement="Scientist, inventor, diplomat, author, founder — the original polymath",
            core_lesson=(
                "An investment in knowledge pays the best interest. "
                "The person who masters the most domains has the most options."
            ),
        ),
        HistoricalGreat(
            great_id="confucius",
            name="Confucius",
            era="551–479 BC",
            primary_class=HistoricalClass.PHILOSOPHY,
            secondary_classes=(HistoricalClass.POLITICS,),
            trait_scores=_t(focus=0.97, prep=0.92, fail=0.90, patt=0.93, self=0.92,
                            cross=0.88, narr=0.95, adap=0.88, netw=0.90, long=0.99),
            signature_achievement="The Analects — still guiding 1.5B people 2,500 years later",
            core_lesson=(
                "It does not matter how slowly you go as long as you do not stop. "
                "Ritual and character are the infrastructure of civilisation."
            ),
        ),

        # ── Engineering ─────────────────────────────────────────────────────
        HistoricalGreat(
            great_id="isambard_brunel",
            name="Isambard Kingdom Brunel",
            era="1806–1859",
            primary_class=HistoricalClass.ENGINEERING,
            secondary_classes=(HistoricalClass.BUSINESS,),
            trait_scores=_t(focus=0.98, prep=0.97, fail=0.93, patt=0.97, self=0.99,
                            cross=0.92, narr=0.85, adap=0.90, netw=0.88, long=0.90),
            signature_achievement="Built the GWR, Clifton suspension bridge, and SS Great Eastern simultaneously",
            core_lesson=(
                "I am opposed to the laying down of rules or conditions to be observed "
                "in the construction of bridges. Every bridge is a problem in itself."
            ),
        ),
        HistoricalGreat(
            great_id="thomas_edison",
            name="Thomas Edison",
            era="1847–1931",
            primary_class=HistoricalClass.ENGINEERING,
            secondary_classes=(HistoricalClass.BUSINESS, HistoricalClass.SCIENCE),
            trait_scores=_t(focus=0.97, prep=0.90, fail=1.00, patt=0.95, self=0.97,
                            cross=0.90, narr=0.88, adap=0.92, netw=0.92, long=0.90),
            signature_achievement="1,093 patents — the most prolific inventor in US history",
            core_lesson=(
                "Genius is 1% inspiration and 99% perspiration. "
                "Build the system, not just the invention. The lab matters as much as the idea."
            ),
        ),
        HistoricalGreat(
            great_id="wernher_von_braun",
            name="Wernher von Braun",
            era="1912–1977",
            primary_class=HistoricalClass.ENGINEERING,
            secondary_classes=(HistoricalClass.SCIENCE, HistoricalClass.EXPLORATION),
            trait_scores=_t(focus=0.99, prep=0.97, fail=0.90, patt=0.97, self=0.95,
                            cross=0.90, narr=0.90, adap=0.88, netw=0.88, long=0.97),
            signature_achievement="Designed the Saturn V rocket that put humans on the Moon",
            core_lesson=(
                "Basic research is what I'm doing when I don't know what I'm doing. "
                "The vision has to be so large that every person on the team can see themselves in it."
            ),
        ),

        # ── Spiritual / Wisdom Traditions ───────────────────────────────────
        HistoricalGreat(
            great_id="buddha",
            name="Siddhartha Gautama (Buddha)",
            era="563–483 BC",
            primary_class=HistoricalClass.SPIRITUAL,
            secondary_classes=(HistoricalClass.PHILOSOPHY,),
            trait_scores=_t(focus=1.00, prep=0.93, fail=0.99, patt=0.97, self=0.97,
                            cross=0.90, narr=0.95, adap=0.93, netw=0.88, long=1.00),
            signature_achievement="Founded Buddhism — still guiding 500M people 2,500 years later",
            core_lesson=(
                "Peace comes from within. Do not seek it without. "
                "The mind is the source of all suffering and all liberation."
            ),
        ),
        HistoricalGreat(
            great_id="king_mlk",
            name="Martin Luther King Jr.",
            era="1929–1968",
            primary_class=HistoricalClass.SPIRITUAL,
            secondary_classes=(HistoricalClass.POLITICS,),
            trait_scores=_t(focus=0.97, prep=0.93, fail=0.97, patt=0.93, self=0.99,
                            cross=0.90, narr=1.00, adap=0.90, netw=0.95, long=0.93),
            signature_achievement="Led the US Civil Rights movement to the Civil Rights Act of 1964",
            core_lesson=(
                "The time is always right to do what is right. "
                "Moral clarity, communicated with perfect narrative, is the most powerful force in politics."
            ),
        ),
        HistoricalGreat(
            great_id="gandhi",
            name="Mahatma Gandhi",
            era="1869–1948",
            primary_class=HistoricalClass.SPIRITUAL,
            secondary_classes=(HistoricalClass.POLITICS,),
            trait_scores=_t(focus=0.99, prep=0.90, fail=0.99, patt=0.92, self=1.00,
                            cross=0.88, narr=0.95, adap=0.95, netw=0.92, long=0.97),
            signature_achievement="Led India to independence without firing a single bullet",
            core_lesson=(
                "Be the change you wish to see in the world. "
                "Non-violent resistance is not weakness — it is the most disciplined form of strength."
            ),
        ),

        # ── Exploration ─────────────────────────────────────────────────────
        HistoricalGreat(
            great_id="columbus",
            name="Christopher Columbus",
            era="1451–1506",
            primary_class=HistoricalClass.EXPLORATION,
            secondary_classes=(HistoricalClass.MILITARY,),
            trait_scores=_t(focus=0.97, prep=0.88, fail=0.90, patt=0.88, self=1.00,
                            cross=0.82, narr=0.85, adap=0.85, netw=0.85, long=0.88),
            signature_achievement="Opened the Americas to the Old World — one of history's largest catalysts",
            core_lesson=(
                "You can never cross the ocean until you have the courage to lose sight "
                "of the shore. Radical self-belief is the price of discovery."
            ),
        ),
        HistoricalGreat(
            great_id="amelia_earhart",
            name="Amelia Earhart",
            era="1897–1937",
            primary_class=HistoricalClass.EXPLORATION,
            secondary_classes=(HistoricalClass.POLITICS,),
            trait_scores=_t(focus=0.97, prep=0.93, fail=0.95, patt=0.88, self=0.99,
                            cross=0.85, narr=0.90, adap=0.90, netw=0.85, long=0.88),
            signature_achievement="First woman to fly solo across the Atlantic Ocean",
            core_lesson=(
                "The most difficult thing is the decision to act; the rest is merely tenacity. "
                "Courage is the commitment to begin without any guarantee of success."
            ),
        ),
        HistoricalGreat(
            great_id="neil_armstrong",
            name="Neil Armstrong",
            era="1930–2012",
            primary_class=HistoricalClass.EXPLORATION,
            secondary_classes=(HistoricalClass.ENGINEERING, HistoricalClass.MILITARY),
            trait_scores=_t(focus=0.98, prep=1.00, fail=0.92, patt=0.95, self=0.97,
                            cross=0.90, narr=0.82, adap=0.97, netw=0.88, long=0.90),
            signature_achievement="First human to walk on the Moon — July 20, 1969",
            core_lesson=(
                "Mystery creates wonder and wonder is the basis of man's desire to understand. "
                "Prepare for every scenario; the unknown is just under-modelled."
            ),
        ),
    ]

    return {g.great_id: g for g in greats}


HISTORICAL_GREATS: Dict[str, HistoricalGreat] = _build_historical_greats()


# ---------------------------------------------------------------------------
# Greatness Benchmark — aggregate reference scores per class
# ---------------------------------------------------------------------------

@dataclass
class GreatnessBenchmark:
    """
    Aggregated trait benchmarks derived from the historical greats corpus.

    Provides:
      - per-class mean scores
      - all-time mean (across all classes and all greats)
      - elite threshold (mean of top-10 scorers per trait)
    """
    per_class_means: Dict[HistoricalClass, Dict[GreatnessTrait, float]]
    all_time_mean: Dict[GreatnessTrait, float]
    elite_threshold: Dict[GreatnessTrait, float]   # top-10 per trait

    @classmethod
    def build(cls) -> "GreatnessBenchmark":
        greats = list(HISTORICAL_GREATS.values())

        # Per-class means
        per_class: Dict[HistoricalClass, Dict[GreatnessTrait, float]] = {}
        for hc in HistoricalClass:
            members = [g for g in greats if g.primary_class == hc]
            if not members:
                continue
            per_class[hc] = {}
            for trait in ALL_TRAITS:
                vals = [g.trait_scores.get(trait, 0.0) for g in members]
                per_class[hc][trait] = round(sum(vals) / len(vals), 4)

        # All-time mean
        all_time: Dict[GreatnessTrait, float] = {}
        for trait in ALL_TRAITS:
            vals = [g.trait_scores.get(trait, 0.0) for g in greats]
            all_time[trait] = round(sum(vals) / len(vals), 4)

        # Elite threshold: mean of top-10 scorers per trait
        elite: Dict[GreatnessTrait, float] = {}
        for trait in ALL_TRAITS:
            sorted_vals = sorted(
                [g.trait_scores.get(trait, 0.0) for g in greats], reverse=True
            )
            top_10 = sorted_vals[:10]
            elite[trait] = round(sum(top_10) / len(top_10), 4)

        return cls(
            per_class_means=per_class,
            all_time_mean=all_time,
            elite_threshold=elite,
        )

    def percentile_rank(
        self, trait: GreatnessTrait, score: float
    ) -> float:
        """Return approximate percentile rank (0–100) of *score* for *trait*."""
        floor = self.all_time_mean.get(trait, 0.5) * 0.7
        ceil  = self.elite_threshold.get(trait, 1.0)
        if ceil <= floor:
            return 50.0
        rank = (score - floor) / (ceil - floor) * 100.0
        return round(max(0.0, min(100.0, rank)), 1)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "all_time_mean": {t.value: s for t, s in self.all_time_mean.items()},
            "elite_threshold": {t.value: s for t, s in self.elite_threshold.items()},
            "per_class_means": {
                hc.value: {t.value: s for t, s in scores.items()}
                for hc, scores in self.per_class_means.items()
            },
        }


BENCHMARK: GreatnessBenchmark = GreatnessBenchmark.build()


# ---------------------------------------------------------------------------
# Trait Profiler
# ---------------------------------------------------------------------------

# Mapping from elite_org_simulator competency dimensions to greatness traits.
# Each competency contributes to one or more greatness traits (weighted).
_COMPETENCY_TO_TRAITS: Dict[str, Dict[GreatnessTrait, float]] = {
    "strategic_thinking":    {GreatnessTrait.LONG_GAME_THINKING: 0.40, GreatnessTrait.PATTERN_RECOGNITION: 0.35, GreatnessTrait.ADAPTIVE_STRATEGY: 0.25},
    "execution_speed":       {GreatnessTrait.EXTREME_PREPARATION: 0.40, GreatnessTrait.OBSESSIVE_FOCUS: 0.35, GreatnessTrait.ADAPTIVE_STRATEGY: 0.25},
    "technical_depth":       {GreatnessTrait.OBSESSIVE_FOCUS: 0.40, GreatnessTrait.EXTREME_PREPARATION: 0.35, GreatnessTrait.PATTERN_RECOGNITION: 0.25},
    "communication_clarity": {GreatnessTrait.NARRATIVE_MASTERY: 0.55, GreatnessTrait.NETWORK_LEVERAGE: 0.25, GreatnessTrait.ADAPTIVE_STRATEGY: 0.20},
    "data_fluency":          {GreatnessTrait.PATTERN_RECOGNITION: 0.50, GreatnessTrait.FAILURE_AS_DATA: 0.30, GreatnessTrait.EXTREME_PREPARATION: 0.20},
    "customer_empathy":      {GreatnessTrait.NARRATIVE_MASTERY: 0.30, GreatnessTrait.NETWORK_LEVERAGE: 0.35, GreatnessTrait.CROSS_DOMAIN_LEARNING: 0.35},
    "leadership_presence":   {GreatnessTrait.NARRATIVE_MASTERY: 0.35, GreatnessTrait.RADICAL_SELF_BELIEF: 0.40, GreatnessTrait.NETWORK_LEVERAGE: 0.25},
    "cross_functional":      {GreatnessTrait.NETWORK_LEVERAGE: 0.40, GreatnessTrait.CROSS_DOMAIN_LEARNING: 0.35, GreatnessTrait.ADAPTIVE_STRATEGY: 0.25},
    "persuasion_influence":  {GreatnessTrait.NARRATIVE_MASTERY: 0.35, GreatnessTrait.RADICAL_SELF_BELIEF: 0.30, GreatnessTrait.NETWORK_LEVERAGE: 0.35},
    "adaptability":          {GreatnessTrait.ADAPTIVE_STRATEGY: 0.50, GreatnessTrait.FAILURE_AS_DATA: 0.30, GreatnessTrait.CROSS_DOMAIN_LEARNING: 0.20},
}


@dataclass
class CalibrationResult:
    """Full greatness calibration for any role, agent, or genome."""
    subject_id: str
    subject_type: str                              # "role", "agent", "custom"
    trait_scores: Dict[GreatnessTrait, float]      # derived greatness scores
    percentile_ranks: Dict[GreatnessTrait, float]  # vs all-time benchmark
    overall_greatness: float                       # mean of all trait scores
    archetype_match: "HistoricalGreat"             # closest historical great
    archetype_distance: float
    secondary_archetype: Optional["HistoricalGreat"]
    peak_trait: Tuple[GreatnessTrait, float]
    growth_traits: List[Tuple[GreatnessTrait, float]]  # lowest scores → most room to grow
    recommendations: List[str]
    historical_class_alignment: HistoricalClass    # which class this profile most resembles

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subject_id": self.subject_id,
            "subject_type": self.subject_type,
            "trait_scores": {t.value: s for t, s in self.trait_scores.items()},
            "percentile_ranks": {t.value: p for t, p in self.percentile_ranks.items()},
            "overall_greatness": self.overall_greatness,
            "archetype_match": self.archetype_match.to_dict(),
            "archetype_distance": self.archetype_distance,
            "secondary_archetype": self.secondary_archetype.to_dict() if self.secondary_archetype else None,
            "peak_trait": {self.peak_trait[0].value: self.peak_trait[1]},
            "growth_traits": [(t.value, s) for t, s in self.growth_traits],
            "recommendations": self.recommendations,
            "historical_class_alignment": self.historical_class_alignment.value,
        }


class TraitProfiler:
    """
    Derives greatness trait scores from a competency genome (as used in
    EliteOrgSimulator.SkillGenome or any dict of dimension→score).
    """

    def profile(
        self,
        competency_scores: Dict[str, float],
        subject_id: str = "unknown",
        subject_type: str = "role",
    ) -> CalibrationResult:
        """
        Derive greatness trait scores from a competency score dict and
        return a full CalibrationResult with archetype match + recommendations.
        """
        # Step 1: map competency scores → greatness trait weighted sums
        trait_accum: Dict[GreatnessTrait, float] = {t: 0.0 for t in ALL_TRAITS}
        trait_weights: Dict[GreatnessTrait, float] = {t: 0.0 for t in ALL_TRAITS}

        for dim, comp_score in competency_scores.items():
            mapping = _COMPETENCY_TO_TRAITS.get(dim)
            if not mapping:
                continue
            for trait, weight in mapping.items():
                trait_accum[trait]   += comp_score * weight
                trait_weights[trait] += weight

        # Normalise
        trait_scores: Dict[GreatnessTrait, float] = {}
        for trait in ALL_TRAITS:
            w = trait_weights[trait]
            trait_scores[trait] = round(trait_accum[trait] / w, 4) if w > 0 else 0.75

        # Step 2: percentile ranks vs all-time benchmark
        pct_ranks = {
            t: BENCHMARK.percentile_rank(t, s)
            for t, s in trait_scores.items()
        }

        # Step 3: overall
        overall = round(sum(trait_scores.values()) / len(trait_scores), 4)

        # Step 4: archetype match
        archetype, dist, secondary = self._find_archetypes(trait_scores)

        # Step 5: peak and growth traits
        peak = max(trait_scores.items(), key=lambda kv: kv[1])
        growth = sorted(trait_scores.items(), key=lambda kv: kv[1])[:3]

        # Step 6: historical class alignment
        class_alignment = self._infer_class(trait_scores)

        # Step 7: recommendations
        recs = self._build_recommendations(trait_scores, growth, archetype)

        return CalibrationResult(
            subject_id=subject_id,
            subject_type=subject_type,
            trait_scores=trait_scores,
            percentile_ranks=pct_ranks,
            overall_greatness=overall,
            archetype_match=archetype,
            archetype_distance=dist,
            secondary_archetype=secondary,
            peak_trait=peak,
            growth_traits=growth,
            recommendations=recs,
            historical_class_alignment=class_alignment,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _find_archetypes(
        trait_scores: Dict[GreatnessTrait, float],
    ) -> Tuple[HistoricalGreat, float, Optional[HistoricalGreat]]:
        """Find the top-1 and top-2 closest historical greats by Euclidean distance."""
        greats = list(HISTORICAL_GREATS.values())
        ranked = sorted(greats, key=lambda g: g.distance_to(trait_scores))
        primary   = ranked[0]
        secondary = ranked[1] if len(ranked) > 1 else None
        return primary, primary.distance_to(trait_scores), secondary

    @staticmethod
    def _infer_class(
        trait_scores: Dict[GreatnessTrait, float],
    ) -> HistoricalClass:
        """Infer which historical class best matches the trait profile."""
        # Class signatures: dominant traits per class
        _CLASS_SIGNATURES: Dict[HistoricalClass, List[GreatnessTrait]] = {
            HistoricalClass.MILITARY:    [GreatnessTrait.EXTREME_PREPARATION, GreatnessTrait.ADAPTIVE_STRATEGY, GreatnessTrait.RADICAL_SELF_BELIEF],
            HistoricalClass.BUSINESS:    [GreatnessTrait.LONG_GAME_THINKING, GreatnessTrait.NETWORK_LEVERAGE, GreatnessTrait.OBSESSIVE_FOCUS],
            HistoricalClass.SCIENCE:     [GreatnessTrait.OBSESSIVE_FOCUS, GreatnessTrait.PATTERN_RECOGNITION, GreatnessTrait.FAILURE_AS_DATA],
            HistoricalClass.ARTS:        [GreatnessTrait.OBSESSIVE_FOCUS, GreatnessTrait.NARRATIVE_MASTERY, GreatnessTrait.CROSS_DOMAIN_LEARNING],
            HistoricalClass.POLITICS:    [GreatnessTrait.NARRATIVE_MASTERY, GreatnessTrait.NETWORK_LEVERAGE, GreatnessTrait.ADAPTIVE_STRATEGY],
            HistoricalClass.ATHLETICS:   [GreatnessTrait.OBSESSIVE_FOCUS, GreatnessTrait.EXTREME_PREPARATION, GreatnessTrait.FAILURE_AS_DATA],
            HistoricalClass.PHILOSOPHY:  [GreatnessTrait.CROSS_DOMAIN_LEARNING, GreatnessTrait.PATTERN_RECOGNITION, GreatnessTrait.LONG_GAME_THINKING],
            HistoricalClass.ENGINEERING: [GreatnessTrait.EXTREME_PREPARATION, GreatnessTrait.FAILURE_AS_DATA, GreatnessTrait.PATTERN_RECOGNITION],
            HistoricalClass.SPIRITUAL:   [GreatnessTrait.LONG_GAME_THINKING, GreatnessTrait.RADICAL_SELF_BELIEF, GreatnessTrait.NARRATIVE_MASTERY],
            HistoricalClass.EXPLORATION: [GreatnessTrait.RADICAL_SELF_BELIEF, GreatnessTrait.EXTREME_PREPARATION, GreatnessTrait.ADAPTIVE_STRATEGY],
        }
        best_class = HistoricalClass.BUSINESS
        best_score = -1.0
        for hc, sig_traits in _CLASS_SIGNATURES.items():
            score = sum(trait_scores.get(t, 0.0) for t in sig_traits) / len(sig_traits)
            if score > best_score:
                best_score = score
                best_class = hc
        return best_class

    @staticmethod
    def _build_recommendations(
        trait_scores: Dict[GreatnessTrait, float],
        growth_traits: List[Tuple[GreatnessTrait, float]],
        archetype: HistoricalGreat,
    ) -> List[str]:
        recs = []
        recs.append(
            f"Your closest historical archetype is {archetype.name} "
            f"({archetype.primary_class.value}). Study their methods: {archetype.core_lesson}"
        )
        for trait, score in growth_traits[:2]:
            defn = TRAIT_DEFINITIONS[trait]
            recs.append(
                f"Develop '{defn.name}' (current: {score:.2f}): {defn.modern_equivalent}. "
                f"Anti-pattern to avoid: {defn.anti_pattern}."
            )
        # Universal recommendation
        recs.append(
            "Apply cross-domain learning weekly: dedicate 30 minutes to reading "
            "one field completely outside your primary domain."
        )
        return recs


# ---------------------------------------------------------------------------
# Archetype Matcher — public API for standalone lookups
# ---------------------------------------------------------------------------

class ArchetypeMatcher:
    """Find the best historical archetype for any set of trait scores or competencies."""

    def __init__(self) -> None:
        self._profiler = TraitProfiler()

    def match_by_competencies(
        self,
        competency_scores: Dict[str, float],
        subject_id: str = "unknown",
    ) -> CalibrationResult:
        """Match from a dict of competency dimension scores."""
        return self._profiler.profile(competency_scores, subject_id=subject_id)

    def match_by_traits(
        self,
        trait_scores: Dict[GreatnessTrait, float],
        subject_id: str = "unknown",
    ) -> HistoricalGreat:
        """Return closest great for a direct trait score dict."""
        greats = list(HISTORICAL_GREATS.values())
        return min(greats, key=lambda g: g.distance_to(trait_scores))

    def class_champions(self) -> Dict[HistoricalClass, HistoricalGreat]:
        """Return the single highest overall-scoring great from each class."""
        out: Dict[HistoricalClass, HistoricalGreat] = {}
        for great in HISTORICAL_GREATS.values():
            hc = great.primary_class
            if hc not in out or great.overall_score > out[hc].overall_score:
                out[hc] = great
        return out

    def top_n_all_time(self, n: int = 10) -> List[HistoricalGreat]:
        """Return top-n greats by overall score."""
        return sorted(HISTORICAL_GREATS.values(), key=lambda g: g.overall_score, reverse=True)[:n]

    def trait_champions(self) -> Dict[GreatnessTrait, HistoricalGreat]:
        """Return the person who scored highest on each individual trait."""
        out: Dict[GreatnessTrait, HistoricalGreat] = {}
        for trait in ALL_TRAITS:
            best = max(HISTORICAL_GREATS.values(), key=lambda g: g.trait_scores.get(trait, 0.0))
            out[trait] = best
        return out


# ---------------------------------------------------------------------------
# Historical Greatness Engine — top-level façade
# ---------------------------------------------------------------------------

class HistoricalGreatnessEngine:
    """
    Top-level façade for the Historical Greatness Engine.

    Usage::

        engine = HistoricalGreatnessEngine()

        # 1. Profile a role from EliteOrgSimulator
        from elite_org_simulator import SkillGenome
        genome = SkillGenome.build("ceo")
        result = engine.calibrate_genome(genome, subject_id="ceo")
        print(result.archetype_match.name)       # → "Steve Jobs" or "Jeff Bezos"
        print(result.recommendations[0])

        # 2. Calibrate all roles in an org chart
        from elite_org_simulator import EliteOrgSimulator, CompanyStage
        sim = EliteOrgSimulator()
        chart = sim.build_chart(CompanyStage.SERIES_B)
        calibrations = engine.calibrate_org(chart)

        # 3. Find trait champions
        champions = engine.archetype_matcher.trait_champions()

        # 4. Get full benchmark
        bench = engine.benchmark
    """

    def __init__(self) -> None:
        self._profiler = TraitProfiler()
        self._matcher  = ArchetypeMatcher()
        self._lock     = threading.Lock()

    @property
    def benchmark(self) -> GreatnessBenchmark:
        return BENCHMARK

    @property
    def archetype_matcher(self) -> ArchetypeMatcher:
        return self._matcher

    # ------------------------------------------------------------------
    # Core public API
    # ------------------------------------------------------------------

    def calibrate_genome(
        self,
        genome: Any,    # SkillGenome or any object with .scores dict
        subject_id: str = "unknown",
        subject_type: str = "role",
    ) -> CalibrationResult:
        """Calibrate a SkillGenome against historical greatness benchmarks."""
        scores: Dict[str, float] = {}
        if hasattr(genome, "scores"):
            scores = genome.scores
        elif isinstance(genome, dict):
            scores = genome
        return self._profiler.profile(scores, subject_id=subject_id, subject_type=subject_type)

    def calibrate_org(self, chart: Any) -> Dict[str, CalibrationResult]:
        """
        Calibrate every filled role in an EliteOrgChart.
        Returns dict of role_id → CalibrationResult.
        """
        results: Dict[str, CalibrationResult] = {}
        roles = getattr(chart, "roles", {})
        for role_id, role in roles.items():
            if not getattr(role, "is_filled", True):
                continue
            genome = getattr(role, "genome", None)
            if genome is None:
                continue
            calib = self.calibrate_genome(
                genome,
                subject_id=role_id,
                subject_type="role",
            )
            results[role_id] = calib
        return results

    def calibrate_agent(
        self,
        agent_id: str,
        kaia_mix: Dict[str, float],
        influence_frameworks: List[str],
    ) -> CalibrationResult:
        """
        Calibrate an agent persona from its KAIA mix and influence frameworks.
        Maps KAIA → competency proxy scores → greatness traits.
        """
        # Derive rough competency proxy from KAIA mix
        a = kaia_mix.get("analytical",  0.20)
        d = kaia_mix.get("decisive",    0.20)
        e = kaia_mix.get("empathetic",  0.20)
        c = kaia_mix.get("creative",    0.20)
        t = kaia_mix.get("technical",   0.20)

        # Influence framework bonus: count frameworks per source
        fw_sources = {"cialdini": 0, "carnegie": 0, "covey": 0, "nlp": 0, "mentalism": 0, "habit": 0}
        for fw_id in influence_frameworks:
            for src in fw_sources:
                if fw_id.startswith(src):
                    fw_sources[src] += 1

        # Map KAIA + frameworks → proxy competencies
        proxy: Dict[str, float] = {
            "strategic_thinking":    min(1.0, a * 0.6 + d * 0.4),
            "execution_speed":       min(1.0, d * 0.6 + t * 0.4),
            "technical_depth":       min(1.0, t * 0.7 + a * 0.3),
            "communication_clarity": min(1.0, e * 0.4 + c * 0.4 + (fw_sources["carnegie"] * 0.05)),
            "data_fluency":          min(1.0, a * 0.7 + t * 0.3),
            "customer_empathy":      min(1.0, e * 0.7 + c * 0.3),
            "leadership_presence":   min(1.0, d * 0.5 + e * 0.3 + (fw_sources["cialdini"] * 0.04)),
            "cross_functional":      min(1.0, e * 0.4 + a * 0.3 + (fw_sources["covey"] * 0.05)),
            "persuasion_influence":  min(1.0, (fw_sources["cialdini"] + fw_sources["nlp"] + fw_sources["mentalism"]) * 0.15 + d * 0.4),
            "adaptability":          min(1.0, c * 0.5 + d * 0.3 + (fw_sources["nlp"] * 0.05)),
        }
        return self._profiler.profile(proxy, subject_id=agent_id, subject_type="agent")

    def org_greatness_summary(self, chart: Any) -> Dict[str, Any]:
        """
        Return a summary of historical greatness calibration for an entire org.
        """
        calibrations = self.calibrate_org(chart)
        if not calibrations:
            return {"error": "No roles calibrated"}

        all_scores = [c.overall_greatness for c in calibrations.values()]
        avg_greatness = round(sum(all_scores) / len(all_scores), 4)

        # Most common archetype
        archetype_counts: Dict[str, int] = {}
        for c in calibrations.values():
            k = c.archetype_match.name
            archetype_counts[k] = archetype_counts.get(k, 0) + 1
        dominant_archetype = max(archetype_counts, key=lambda k: archetype_counts[k])

        # Top and bottom roles
        sorted_calib = sorted(calibrations.items(), key=lambda kv: kv[1].overall_greatness, reverse=True)
        top_roles    = [(rid, round(c.overall_greatness, 4)) for rid, c in sorted_calib[:3]]
        bottom_roles = [(rid, round(c.overall_greatness, 4)) for rid, c in sorted_calib[-3:]]

        # Class distribution
        class_dist: Dict[str, int] = {}
        for c in calibrations.values():
            k = c.historical_class_alignment.value
            class_dist[k] = class_dist.get(k, 0) + 1

        return {
            "headcount_calibrated": len(calibrations),
            "avg_greatness_score": avg_greatness,
            "dominant_archetype": dominant_archetype,
            "archetype_distribution": archetype_counts,
            "class_alignment_distribution": class_dist,
            "top_roles": top_roles,
            "bottom_roles": bottom_roles,
            "benchmark_vs_elite": {
                t.value: round(
                    sum(c.trait_scores.get(t, 0.0) for c in calibrations.values()) / len(calibrations), 4
                )
                for t in ALL_TRAITS
            },
        }

    def trait_development_plan(
        self,
        calibration: CalibrationResult,
        weeks: int = 12,
    ) -> Dict[str, Any]:
        """
        Generate a concrete trait-development plan for a calibrated subject.
        Covers each of the 3 lowest-scoring traits with weekly practices.
        """
        plan: List[Dict[str, Any]] = []
        for i, (trait, score) in enumerate(calibration.growth_traits[:3]):
            defn = TRAIT_DEFINITIONS[trait]
            champion = self._matcher.trait_champions().get(trait)
            plan.append({
                "priority": i + 1,
                "trait": trait.value,
                "trait_name": defn.name,
                "current_score": score,
                "target_score": round(BENCHMARK.elite_threshold.get(trait, 0.95), 4),
                "gap": round(BENCHMARK.elite_threshold.get(trait, 0.95) - score, 4),
                "weekly_practice": defn.modern_equivalent,
                "anti_pattern_to_break": defn.anti_pattern,
                "historical_model": champion.name if champion else "N/A",
                "model_quote": (
                    defn.epitome_quote
                    if champion and champion.name == defn.historical_epitome
                    else f"Study {champion.name if champion else 'the field'}: {defn.evidence_phrase[:80]}..."
                ),
                "weeks_to_impact": weeks // 3,
            })
        return {
            "subject_id": calibration.subject_id,
            "overall_current": calibration.overall_greatness,
            "archetype": calibration.archetype_match.name,
            "development_plan": plan,
            "universal_practice": (
                "Daily: 30-min deep reading outside your domain (cross-domain learning). "
                "Weekly: write one page reflecting on a failure and what it taught you. "
                "Monthly: teach something you just learned to someone else — "
                "the best test of mastery is explanation."
            ),
        }

    def describe_trait(self, trait: GreatnessTrait) -> Dict[str, Any]:
        """Return full human-readable description of a greatness trait."""
        defn = TRAIT_DEFINITIONS[trait]
        champion = self._matcher.trait_champions().get(trait)
        greats_with_high_score = sorted(
            [(g.name, g.trait_scores.get(trait, 0.0)) for g in HISTORICAL_GREATS.values()],
            key=lambda kv: kv[1], reverse=True
        )[:5]
        return {
            "trait": trait.value,
            "name": defn.name,
            "description": defn.description,
            "core_question": defn.core_question,
            "evidence": defn.evidence_phrase,
            "modern_equivalent": defn.modern_equivalent,
            "anti_pattern": defn.anti_pattern,
            "historical_epitome": defn.historical_epitome,
            "epitome_quote": defn.epitome_quote,
            "benchmark_mean": BENCHMARK.all_time_mean.get(trait, 0.0),
            "elite_threshold": BENCHMARK.elite_threshold.get(trait, 0.0),
            "top_5_scorers": greats_with_high_score,
        }
