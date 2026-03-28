"""
Character Network Engine — Murphy System
==========================================

Embeds the moral character of history's greatest leaders into every Murphy
System agent and role — as a *second nature*, not a performance.

"Second nature" means the agent does not consciously decide to act with
integrity — it acts that way by default, the way a trained reflex fires before
conscious thought.  This engine provides the training data, archetypes, and
habit stacks to make that second nature real.

Victorian-Era Frame
--------------------
The Victorian era (1837–1901) produced an extraordinary density of leaders
who combined commercial success, public influence, and genuine moral reform —
not as a trade-off but as a compound.  William Wilberforce, Florence Nightingale,
Harriet Tubman, Frederick Douglass, Lord Shaftesbury, Charles Dickens —
these were not sentimental idealists.  They were hard-nosed operators who
understood that moral authority was their most durable competitive advantage.

Their shared insight:  *Build your network from people of higher moral fibre.
Your network's character is your character.*

The 8 Character Pillars
------------------------
  1. INTEGRITY          — Alignment of word, action, and private conduct
  2. MORAL_COURAGE      — Acting on principle when the cost is personal
  3. SERVICE_ABOVE_SELF — Investing in others' outcomes before your own
  4. WISDOM             — Sound judgment from deep experience and reflection
  5. JUSTICE            — Fair treatment regardless of power or convention
  6. FORTITUDE          — Sustained effort under adversity without bitterness
  7. TEMPERANCE         — Restraint of appetite, ego, and reactive impulse
  8. PRUDENCE           — Right action at the right time with the right method

Design Label: CNE-001 — Character Network Engine
Owner:        Platform Engineering / Agent Intelligence
License:      BSL 1.1

Copyright © 2020 Inoni Limited Liability Company
Creator:      Corey Post
"""

from __future__ import annotations

import math
import re
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class CharacterPillar(str, Enum):
    """The 8 universal pillars of moral character."""
    INTEGRITY         = "integrity"
    MORAL_COURAGE     = "moral_courage"
    SERVICE_ABOVE_SELF = "service_above_self"
    WISDOM            = "wisdom"
    JUSTICE           = "justice"
    FORTITUDE         = "fortitude"
    TEMPERANCE        = "temperance"
    PRUDENCE          = "prudence"


ALL_PILLARS: List[CharacterPillar] = list(CharacterPillar)


class VictorianCharacterClass(str, Enum):
    """Categories of Victorian-era leadership."""
    REFORMER       = "reformer"
    HUMANITARIAN   = "humanitarian"
    EDUCATOR       = "educator"
    STATESMAN      = "statesman"
    SCIENTIST      = "scientist"
    ARTIST         = "artist"
    SPIRITUAL      = "spiritual"
    INDUSTRIALIST  = "industrialist"


class NetworkTier(str, Enum):
    """Tiers of a character-based professional network."""
    INNER_CIRCLE      = "inner_circle"        # 3–7 people — deepest trust
    TRUSTED_ADVISORS  = "trusted_advisors"    # 8–20 people — high confidence
    EXTENDED_NETWORK  = "extended_network"    # 21–80 people — reliable allies
    COMMUNITY_IMPACT  = "community_impact"    # 80+ people — shared mission


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

def _cp(
    integ: float, cour: float, serv: float, wisd: float,
    just: float, fort: float, temp: float, prud: float,
) -> Dict[CharacterPillar, float]:
    """Shorthand builder for pillar score dicts."""
    return {
        CharacterPillar.INTEGRITY:          integ,
        CharacterPillar.MORAL_COURAGE:      cour,
        CharacterPillar.SERVICE_ABOVE_SELF: serv,
        CharacterPillar.WISDOM:             wisd,
        CharacterPillar.JUSTICE:            just,
        CharacterPillar.FORTITUDE:          fort,
        CharacterPillar.TEMPERANCE:         temp,
        CharacterPillar.PRUDENCE:           prud,
    }


@dataclass(frozen=True)
class VictorianLeader:
    """A modelled Victorian-era leader of character."""
    leader_id:           str
    name:                str
    era:                 str
    character_class:     VictorianCharacterClass
    pillar_scores:       Dict[CharacterPillar, float]
    signature_act:       str   # their defining act of character
    network_approach:    str   # how they built their character network
    modern_parallel:     str   # what this looks like in a modern context
    character_lesson:    str   # the transferable lesson
    second_nature_habit: str   # what they did automatically without thinking

    @property
    def overall_score(self) -> float:
        return round(sum(self.pillar_scores.values()) / len(self.pillar_scores), 4)

    @property
    def dominant_pillar(self) -> Tuple[CharacterPillar, float]:
        p = max(self.pillar_scores, key=lambda k: self.pillar_scores[k])
        return p, self.pillar_scores[p]

    def distance_to(self, other_scores: Dict[CharacterPillar, float]) -> float:
        sq = sum(
            (self.pillar_scores.get(p, 0.0) - other_scores.get(p, 0.0)) ** 2
            for p in ALL_PILLARS
        )
        return round(math.sqrt(sq / len(ALL_PILLARS)), 6)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "leader_id":           self.leader_id,
            "name":                self.name,
            "era":                 self.era,
            "character_class":     self.character_class.value,
            "pillar_scores":       {p.value: s for p, s in self.pillar_scores.items()},
            "overall_score":       self.overall_score,
            "dominant_pillar":     self.dominant_pillar[0].value,
            "signature_act":       self.signature_act,
            "network_approach":    self.network_approach,
            "modern_parallel":     self.modern_parallel,
            "character_lesson":    self.character_lesson,
            "second_nature_habit": self.second_nature_habit,
        }


@dataclass(frozen=True)
class SecondNatureBehavior:
    """A habitual, automatic behavior that embeds good character."""
    behavior_id:        str
    pillar:             CharacterPillar
    description:        str
    trigger:            str       # what situation activates this
    micro_action:       str       # the small, automatic action
    compounding_effect: str       # what accumulates over months/years
    victorian_exemplar: str       # who embodied this habitually

    def to_dict(self) -> Dict[str, Any]:
        return {
            "behavior_id":        self.behavior_id,
            "pillar":             self.pillar.value,
            "description":        self.description,
            "trigger":            self.trigger,
            "micro_action":       self.micro_action,
            "compounding_effect": self.compounding_effect,
            "victorian_exemplar": self.victorian_exemplar,
        }


@dataclass
class MoralFiberScore:
    """Composite character assessment across all 8 pillars."""
    subject_id:        str
    pillar_scores:     Dict[CharacterPillar, float]
    behavioral_evidence: List[str] = field(default_factory=list)

    @property
    def overall_score(self) -> float:
        if not self.pillar_scores:
            return 0.0
        return round(sum(self.pillar_scores.values()) / len(self.pillar_scores), 4)

    @property
    def dominant_pillar(self) -> Tuple[CharacterPillar, float]:
        p = max(self.pillar_scores, key=lambda k: self.pillar_scores[k])
        return p, self.pillar_scores[p]

    @property
    def development_areas(self) -> List[Tuple[CharacterPillar, float]]:
        """Pillars scoring below average — sorted ascending (lowest first)."""
        avg = self.overall_score
        below = [(p, s) for p, s in self.pillar_scores.items() if s < avg]
        return sorted(below, key=lambda x: x[1])

    @property
    def character_archetype(self) -> str:
        dom_pillar = self.dominant_pillar[0]
        return _PILLAR_ARCHETYPES.get(dom_pillar, "The Person of Character")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subject_id":          self.subject_id,
            "pillar_scores":       {p.value: s for p, s in self.pillar_scores.items()},
            "overall_score":       self.overall_score,
            "dominant_pillar":     self.dominant_pillar[0].value,
            "character_archetype": self.character_archetype,
            "development_areas":   [(p.value, s) for p, s in self.development_areas],
        }


@dataclass
class NetworkCandidate:
    """A potential addition to a character-based network."""
    candidate_id:        str
    name:                str
    moral_fiber:         MoralFiberScore
    network_tier:        NetworkTier
    connection_rationale: str
    mutual_benefit:      str
    introduction_approach: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id":         self.candidate_id,
            "name":                 self.name,
            "moral_fiber":          self.moral_fiber.to_dict(),
            "network_tier":         self.network_tier.value,
            "connection_rationale": self.connection_rationale,
            "mutual_benefit":       self.mutual_benefit,
            "introduction_approach": self.introduction_approach,
        }


@dataclass
class CharacterNetworkProfile:
    """Full character network profile for an agent or leader."""
    agent_id:               str
    own_moral_fiber:        MoralFiberScore
    archetype_match:        VictorianLeader
    second_nature_behaviors: List[SecondNatureBehavior]
    network_by_tier:        Dict[NetworkTier, List[NetworkCandidate]]
    development_plan:       List[Dict[str, Any]]
    network_health_score:   float

    @property
    def total_network_size(self) -> int:
        return sum(len(v) for v in self.network_by_tier.values())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id":              self.agent_id,
            "own_moral_fiber":       self.own_moral_fiber.to_dict(),
            "archetype_match":       self.archetype_match.to_dict(),
            "second_nature_behaviors": [b.to_dict() for b in self.second_nature_behaviors],
            "network_health_score":  self.network_health_score,
            "total_network_size":    self.total_network_size,
            "development_plan":      self.development_plan,
        }


# ---------------------------------------------------------------------------
# Character archetype names per dominant pillar
# ---------------------------------------------------------------------------

_PILLAR_ARCHETYPES: Dict[CharacterPillar, str] = {
    CharacterPillar.INTEGRITY:          "The Trustworthy Anchor",
    CharacterPillar.MORAL_COURAGE:      "The Principled Warrior",
    CharacterPillar.SERVICE_ABOVE_SELF: "The Servant Leader",
    CharacterPillar.WISDOM:             "The Sage Counsellor",
    CharacterPillar.JUSTICE:            "The Fair Arbiter",
    CharacterPillar.FORTITUDE:          "The Resilient Builder",
    CharacterPillar.TEMPERANCE:         "The Disciplined Steward",
    CharacterPillar.PRUDENCE:           "The Strategic Guardian",
}


# ---------------------------------------------------------------------------
# Victorian Leaders Corpus — 16 carefully modelled figures
# ---------------------------------------------------------------------------

def _build_victorian_leaders() -> Dict[str, VictorianLeader]:
    leaders = [
        VictorianLeader(
            leader_id="florence_nightingale",
            name="Florence Nightingale",
            era="1820–1910",
            character_class=VictorianCharacterClass.REFORMER,
            pillar_scores=_cp(0.99, 0.96, 1.00, 0.97, 0.95, 0.98, 0.92, 0.97),
            signature_act=(
                "Reduced Crimean War hospital mortality from 42% to 2% through "
                "evidence-based hygiene reform — against the entire military establishment."
            ),
            network_approach=(
                "Built her reform network through meticulous correspondence with "
                "politicians, generals, and scientists simultaneously — sharing data, "
                "not opinions, to make her case unanswerable."
            ),
            modern_parallel=(
                "The evidence-based change agent who builds credibility through "
                "data and persists through institutional resistance. "
                "A modern Nightingale sends the right numbers to the right people "
                "at the right moment and waits patiently for the data to win."
            ),
            character_lesson=(
                "Service above self is not weakness — it is the most durable source "
                "of authority. When your motivation is demonstrably the outcome, "
                "not your advancement, people cannot dismiss you."
            ),
            second_nature_habit=(
                "Wrote one letter of specific, actionable encouragement to a "
                "colleague or ally every single day of her working life."
            ),
        ),

        VictorianLeader(
            leader_id="william_wilberforce",
            name="William Wilberforce",
            era="1759–1833",
            character_class=VictorianCharacterClass.REFORMER,
            pillar_scores=_cp(0.99, 1.00, 0.98, 0.94, 1.00, 0.99, 0.90, 0.95),
            signature_act=(
                "Waged a 20-year parliamentary campaign to abolish the British "
                "slave trade against the most powerful commercial interests of the era, "
                "and won."
            ),
            network_approach=(
                "The Clapham Sect: deliberately assembled a small, high-character network "
                "of allies (Clapham Sect) — not the largest network, but the most principled. "
                "Every member was chosen for moral fibre first, influence second."
            ),
            modern_parallel=(
                "The long-game reformer who builds coalitions with principle as the "
                "admission requirement. A modern Wilberforce identifies the 7 people "
                "whose moral authority can move the 70 whose commercial interest won't."
            ),
            character_lesson=(
                "Moral courage compounds. The first year of principled action creates "
                "credibility. The tenth year creates movement. The twentieth year changes "
                "the law. The precondition is refusing to quit when the cost is personal."
            ),
            second_nature_habit=(
                "Began every working day with 30 minutes of private reflection on "
                "'what is the right thing to do today, regardless of what is easy.'"
            ),
        ),

        VictorianLeader(
            leader_id="harriet_tubman",
            name="Harriet Tubman",
            era="1822–1913",
            character_class=VictorianCharacterClass.REFORMER,
            pillar_scores=_cp(1.00, 1.00, 1.00, 0.92, 0.99, 1.00, 0.93, 0.96),
            signature_act=(
                "Made 13 missions into the South via the Underground Railroad, "
                "freeing 70+ people, never losing a single passenger — "
                "while carrying a bounty on her own head."
            ),
            network_approach=(
                "Built her network on absolute trust — every member was personally "
                "vetted for courage and discretion. No weak links tolerated. "
                "The network's strength was its members' character, not its size."
            ),
            modern_parallel=(
                "The mission-critical operator who builds small, elite, trust-dense "
                "networks. A modern Tubman creates a 'kitchen cabinet' of 5–7 people "
                "who tell the truth, have skin in the game, and never break confidence."
            ),
            character_lesson=(
                "Service without self-pity. Tubman returned 13 times — not because "
                "she had no fear, but because service was stronger than fear. "
                "That is the definition of fortitude."
            ),
            second_nature_habit=(
                "Never spoke about her own contribution — only about the people "
                "she helped and the work still to be done."
            ),
        ),

        VictorianLeader(
            leader_id="frederick_douglass",
            name="Frederick Douglass",
            era="1818–1895",
            character_class=VictorianCharacterClass.EDUCATOR,
            pillar_scores=_cp(0.99, 0.99, 0.95, 0.98, 1.00, 0.99, 0.91, 0.96),
            signature_act=(
                "Educated himself in secret against all prohibition, escaped slavery, "
                "and became the most powerful abolitionist orator in American history — "
                "his own existence the most eloquent argument against the system."
            ),
            network_approach=(
                "Built an international network through oratory and written word "
                "— his autobiography and newspaper created allies he had never met. "
                "He understood that a published idea travels further than a conversation."
            ),
            modern_parallel=(
                "The thought leader whose personal story is the argument. "
                "A modern Douglass builds network leverage through writing, speaking, "
                "and demonstrating the transformation they preach."
            ),
            character_lesson=(
                "Wisdom is the weapon that no power can confiscate. "
                "The most radical act of self-belief is pursuing education "
                "when every institution conspires against it."
            ),
            second_nature_habit=(
                "Read for two hours every morning before beginning any other activity — "
                "treating education as a sacred daily obligation."
            ),
        ),

        VictorianLeader(
            leader_id="lord_shaftesbury",
            name="Lord Shaftesbury (7th Earl)",
            era="1801–1885",
            character_class=VictorianCharacterClass.REFORMER,
            pillar_scores=_cp(0.98, 0.97, 0.99, 0.93, 0.99, 0.97, 0.88, 0.94),
            signature_act=(
                "Legislated the Factory Acts that ended child labour in British mills — "
                "sacrificing political advancement and aristocratic social standing to do it."
            ),
            network_approach=(
                "Used his aristocratic social capital to access the highest levels "
                "of government while simultaneously building relationships with "
                "working-class communities. Bridged worlds that never otherwise met."
            ),
            modern_parallel=(
                "The elite bridge-builder who uses privileged access for systemic reform. "
                "A modern Shaftesbury is the executive who uses their board seat "
                "to advocate for frontline workers — and does it consistently."
            ),
            character_lesson=(
                "Access is leverage. The question is: leverage for whom? "
                "Shaftesbury's genius was using the language and access of the elite "
                "to fight for those the elite had forgotten."
            ),
            second_nature_habit=(
                "Before any major decision, asked: 'Who cannot speak for themselves "
                "in this room, and what do they need me to say?'"
            ),
        ),

        VictorianLeader(
            leader_id="charles_dickens",
            name="Charles Dickens",
            era="1812–1870",
            character_class=VictorianCharacterClass.ARTIST,
            pillar_scores=_cp(0.94, 0.92, 0.90, 0.96, 0.95, 0.93, 0.82, 0.91),
            signature_act=(
                "Wrote Oliver Twist, A Christmas Carol, and Bleak House — "
                "using narrative to make invisible poverty visible and change public will "
                "more effectively than any parliamentary speech of his era."
            ),
            network_approach=(
                "Built a network of social reformers, politicians, and journalists "
                "through the common currency of story — his dinners and readings "
                "were salons where ideas and people collided productively."
            ),
            modern_parallel=(
                "The storyteller who builds networks through shared narrative. "
                "A modern Dickens is the founder who makes the customer's journey "
                "so vivid that investors, employees, and partners feel personally "
                "invested in the outcome."
            ),
            character_lesson=(
                "Narrative is the most powerful reform tool ever invented. "
                "One story that makes suffering visible does more than "
                "a thousand statistics that describe it."
            ),
            second_nature_habit=(
                "Walked 10–20 miles through London at night, observing the people "
                "around him, never allowing himself to theorise from a distance "
                "about realities he hadn't personally witnessed."
            ),
        ),

        VictorianLeader(
            leader_id="ada_lovelace",
            name="Ada Lovelace",
            era="1815–1852",
            character_class=VictorianCharacterClass.SCIENTIST,
            pillar_scores=_cp(0.96, 0.93, 0.88, 0.99, 0.91, 0.94, 0.87, 0.97),
            signature_act=(
                "Wrote the first algorithm designed for a general-purpose computing machine "
                "— a century before such a machine existed — demonstrating that "
                "mathematical imagination could leap beyond available technology."
            ),
            network_approach=(
                "Cultivated rigorous intellectual partnerships (Babbage, Faraday, De Morgan) "
                "based on the quality of ideas exchanged, not social status. "
                "She chose collaborators for their precision of thinking."
            ),
            modern_parallel=(
                "The visionary technologist who sees applications before the technology exists. "
                "A modern Ada builds a network of people who think five moves ahead "
                "and are comfortable with ideas that won't be proven for years."
            ),
            character_lesson=(
                "Prudence means seeing the long-term consequence of current decisions "
                "with unusual clarity. The most prudent people appear to be dreamers "
                "until reality catches up with their vision."
            ),
            second_nature_habit=(
                "Annotated every paper she read with the question: "
                "'What does this make possible that wasn't possible before?'"
            ),
        ),

        VictorianLeader(
            leader_id="john_stuart_mill",
            name="John Stuart Mill",
            era="1806–1873",
            character_class=VictorianCharacterClass.STATESMAN,
            pillar_scores=_cp(0.98, 0.95, 0.91, 1.00, 0.99, 0.92, 0.94, 0.97),
            signature_act=(
                "Wrote On Liberty and The Subjection of Women — championing individual "
                "freedom and gender equality when both were radical and professionally costly positions."
            ),
            network_approach=(
                "Built a network of rigorous intellectual opponents as deliberately as "
                "he built allies — believing that his thinking was only as strong "
                "as the best argument he had defeated."
            ),
            modern_parallel=(
                "The principled thinker who strengthens their positions by seeking "
                "the strongest counter-argument. A modern Mill deliberately invites "
                "dissent and credits those who change their mind."
            ),
            character_lesson=(
                "Wisdom requires steelmanning: only engage with the strongest "
                "version of the opposing view. Anything less is intellectual cowardice."
            ),
            second_nature_habit=(
                "Before advocating any position publicly, wrote out the strongest "
                "possible case against it to ensure he had answered it honestly."
            ),
        ),

        VictorianLeader(
            leader_id="elizabeth_fry",
            name="Elizabeth Fry",
            era="1780–1845",
            character_class=VictorianCharacterClass.HUMANITARIAN,
            pillar_scores=_cp(0.99, 0.96, 1.00, 0.93, 0.98, 0.96, 0.95, 0.91),
            signature_act=(
                "Entered Newgate Prison in 1813 — a place no woman of her class "
                "was expected to go — and transformed the conditions of women prisoners "
                "through education, dignity, and persistent advocacy."
            ),
            network_approach=(
                "Built her reform network through shared action rather than shared opinion — "
                "people joined her network by working alongside her, "
                "not by agreeing with her in a drawing room."
            ),
            modern_parallel=(
                "The leader who builds credibility through doing, not declaring. "
                "A modern Fry volunteers before advocating, demonstrates before persuading, "
                "and earns the right to speak by the depth of her personal commitment."
            ),
            character_lesson=(
                "The network formed around a shared sacrifice is indissoluble. "
                "People who have worked alongside you in difficult conditions "
                "will follow you anywhere."
            ),
            second_nature_habit=(
                "Began every day by asking 'Who is in need today that I can reach?' "
                "before addressing any personal agenda."
            ),
        ),

        VictorianLeader(
            leader_id="benjamin_disraeli",
            name="Benjamin Disraeli",
            era="1804–1881",
            character_class=VictorianCharacterClass.STATESMAN,
            pillar_scores=_cp(0.88, 0.91, 0.85, 0.94, 0.87, 0.93, 0.82, 0.99),
            signature_act=(
                "Rose from total outsider (Jewish, lower middle class, known novelist) "
                "to Prime Minister of Britain twice — through wit, political intelligence, "
                "and the mastery of personal relationships across every social class."
            ),
            network_approach=(
                "Mastered the salon and the personal letter — making every person "
                "in his network feel like his most interesting correspondent. "
                "His rule: never forget a name, always remember what a person values."
            ),
            modern_parallel=(
                "The political strategist who builds coalitions across ideological lines "
                "through personal mastery of relationship. A modern Disraeli remembers "
                "the name of every person's child, every deal that mattered to them, "
                "every favour extended and received."
            ),
            character_lesson=(
                "Prudence is the most underrated leadership virtue. "
                "Disraeli chose his battles with precision, conserved his credibility "
                "for the moments that mattered, and never wasted moral capital on "
                "fights he couldn't win."
            ),
            second_nature_habit=(
                "Sent personal, handwritten notes within 24 hours of every meaningful "
                "meeting — always referencing something specific the other person had said."
            ),
        ),

        VictorianLeader(
            leader_id="booker_t_washington",
            name="Booker T. Washington",
            era="1856–1915",
            character_class=VictorianCharacterClass.EDUCATOR,
            pillar_scores=_cp(0.98, 0.93, 0.97, 0.96, 0.95, 0.99, 0.91, 0.97),
            signature_act=(
                "Built Tuskegee Institute from nothing — a school with no building, "
                "no equipment, and no funding — through relentless practical effort "
                "and by teaching every student to build the institution themselves."
            ),
            network_approach=(
                "Built a national network of donors, politicians, and community leaders "
                "by demonstrating results before asking for anything. "
                "Every request was preceded by an achievement worth reporting."
            ),
            modern_parallel=(
                "The pragmatic builder who earns the right to ask by demonstrating first. "
                "A modern Washington never asks for investment before showing traction, "
                "and never celebrates a milestone before creating the next one."
            ),
            character_lesson=(
                "Fortitude is not dramatic — it is the quiet, daily choice "
                "to continue building when the obstacles are real and the resources are scarce. "
                "The institution outlasts the adversity."
            ),
            second_nature_habit=(
                "Inspected his own work personally before presenting it to anyone else — "
                "his standard was always 'would I be proud to explain every decision?'"
            ),
        ),

        VictorianLeader(
            leader_id="george_eliot",
            name="George Eliot (Mary Ann Evans)",
            era="1819–1880",
            character_class=VictorianCharacterClass.ARTIST,
            pillar_scores=_cp(0.97, 0.90, 0.88, 0.99, 0.95, 0.91, 0.90, 0.94),
            signature_act=(
                "Published Middlemarch under a male pseudonym not from shame "
                "but from the rational calculation that her ideas would receive "
                "a fairer hearing — and used the credibility to champion ideas "
                "she cared about most."
            ),
            network_approach=(
                "Cultivated a small, high-quality intellectual network of thinkers "
                "who challenged her — Herbert Spencer, Charles Lewes, Thomas Huxley — "
                "choosing depth of exchange over breadth of acquaintance."
            ),
            modern_parallel=(
                "The intellectual strategist who plays the long game on credibility. "
                "A modern Eliot invests in 5–10 rigorous intellectual partnerships "
                "that compound over decades rather than 500 shallow connections."
            ),
            character_lesson=(
                "Wisdom means understanding the system you're operating in "
                "and playing by rules that advance your real objective. "
                "Pragmatism in service of integrity is not compromise — it is strategy."
            ),
            second_nature_habit=(
                "Re-read a chapter of great literature before beginning every writing session "
                "— to reset her standard of what good actually looked like."
            ),
        ),

        VictorianLeader(
            leader_id="albert_schweitzer",
            name="Albert Schweitzer",
            era="1875–1965",
            character_class=VictorianCharacterClass.HUMANITARIAN,
            pillar_scores=_cp(0.99, 0.95, 1.00, 0.98, 0.96, 0.99, 0.95, 0.94),
            signature_act=(
                "Gave up a career as one of Europe's leading theologians and musicians "
                "at 30 to train as a doctor and spend the rest of his life "
                "running a hospital in Gabon — with no institutional support."
            ),
            network_approach=(
                "Built his global fundraising and advocacy network through "
                "his concert tours and lectures — using his established reputation "
                "in one field to finance work in another that the world had overlooked."
            ),
            modern_parallel=(
                "The multi-domain expert who monetises reputation in one field "
                "to fund purpose in another. A modern Schweitzer uses their "
                "professional platform to generate resources for causes that "
                "can't generate them for themselves."
            ),
            character_lesson=(
                "Reverence for life — Schweitzer's core ethical principle — "
                "means treating every interaction as if it matters, "
                "because for the person in front of you, it does."
            ),
            second_nature_habit=(
                "Thanked every single person who helped him by name, "
                "in writing, within the same day — treating gratitude as a discipline."
            ),
        ),

        VictorianLeader(
            leader_id="sojourner_truth",
            name="Sojourner Truth",
            era="1797–1883",
            character_class=VictorianCharacterClass.REFORMER,
            pillar_scores=_cp(1.00, 1.00, 0.98, 0.92, 1.00, 1.00, 0.91, 0.90),
            signature_act=(
                "Delivered 'Ain't I a Woman?' — six minutes of improvised oratory "
                "that redefined the abolitionist and suffragist movements simultaneously — "
                "with no preparation and no notes."
            ),
            network_approach=(
                "Built her network not through formal channels but through "
                "the irreplaceable currency of direct personal witness — "
                "people in her presence experienced something they could not deny "
                "and could not forget."
            ),
            modern_parallel=(
                "The authentic voice who builds network gravity through undeniable presence. "
                "A modern Truth creates a movement not by being perfectly polished "
                "but by speaking a truth that the audience already knows but hasn't heard said."
            ),
            character_lesson=(
                "Moral courage is measured in the moments when you speak the truth "
                "that the room does not want to hear — and do it without rancour, "
                "with only the conviction that the truth is enough."
            ),
            second_nature_habit=(
                "Began every address by stating her own vulnerability — "
                "her lack of formal education, her enslaved history — "
                "turning what others saw as weakness into the source of her authority."
            ),
        ),

        VictorianLeader(
            leader_id="cardinal_newman",
            name="Cardinal John Henry Newman",
            era="1801–1890",
            character_class=VictorianCharacterClass.SPIRITUAL,
            pillar_scores=_cp(0.99, 0.96, 0.93, 0.99, 0.94, 0.95, 0.97, 0.96),
            signature_act=(
                "Publicly changed his deepest theological convictions at the height "
                "of his influence — accepting the social and professional cost of "
                "intellectual honesty over the comfort of consistency."
            ),
            network_approach=(
                "His 'Lead, Kindly Light' network: built through the quality of his "
                "correspondence — thousands of deeply personal letters to people "
                "in spiritual or intellectual difficulty, each one treated as the "
                "most important letter he had ever written."
            ),
            modern_parallel=(
                "The principled intellectual who builds profound, one-to-one network "
                "depth rather than breadth. A modern Newman maintains 50 deep "
                "relationships rather than 5,000 shallow ones."
            ),
            character_lesson=(
                "Integrity sometimes requires publicly reversing a position. "
                "The willingness to say 'I was wrong and here is the evidence' "
                "is not weakness — it is the highest form of intellectual honesty "
                "and builds more trust than consistency ever could."
            ),
            second_nature_habit=(
                "Wrote to at least one person in genuine difficulty every day — "
                "not to advise, but to listen and to witness their struggle."
            ),
        ),

        VictorianLeader(
            leader_id="william_booth",
            name="William Booth",
            era="1829–1912",
            character_class=VictorianCharacterClass.SPIRITUAL,
            pillar_scores=_cp(0.96, 0.97, 0.99, 0.91, 0.96, 0.99, 0.88, 0.93),
            signature_act=(
                "Founded the Salvation Army from the East End of London, "
                "creating the first major social enterprise that combined "
                "spiritual ministry with practical poverty relief — "
                "and scaled it to 58 countries in his lifetime."
            ),
            network_approach=(
                "Built a network through radical inclusion — recruiting the people "
                "that every other institution had rejected, and discovering that "
                "those with the hardest backgrounds had the most to give. "
                "His network was built bottom-up."
            ),
            modern_parallel=(
                "The social entrepreneur who finds talent and commitment in unexpected places. "
                "A modern Booth builds his best team from people other organisations "
                "passed over — and creates fierce loyalty by betting on them first."
            ),
            character_lesson=(
                "Fortitude is an organisation's most valuable culture asset. "
                "An institution that expects hardship, prepares for it, "
                "and refuses to be defined by it will outlast any adversity."
            ),
            second_nature_habit=(
                "Personally welcomed every new recruit — regardless of their background — "
                "with the same words: 'Welcome. I am glad you are here. What can you do?'"
            ),
        ),

        VictorianLeader(
            leader_id="josiah_wedgwood",
            name="Josiah Wedgwood",
            era="1730–1795",
            character_class=VictorianCharacterClass.INDUSTRIALIST,
            pillar_scores=_cp(0.97, 0.91, 0.88, 0.96, 0.93, 0.97, 0.89, 0.98),
            signature_act=(
                "Built the first modern factory village at Etruria — housing, schools, "
                "and medical care for workers — and simultaneously invented the concept "
                "of mass-market luxury and modern brand marketing."
            ),
            network_approach=(
                "Built a network of aristocratic patrons (including Queen Charlotte) "
                "by gifting them product and making their endorsement visible — "
                "turning celebrity endorsement into a systematic commercial strategy "
                "two centuries before the term existed."
            ),
            modern_parallel=(
                "The brand-builder who combines operational excellence with aspirational "
                "storytelling. A modern Wedgwood invests in both manufacturing quality "
                "and the story around the product — and uses early adopters as "
                "the most credible distribution channel for that story."
            ),
            character_lesson=(
                "Prudence means building systems that outlast you. "
                "Wedgwood's quality standards, customer records, and worker welfare "
                "programmes were designed as permanent infrastructure — "
                "not personal projects — so they survived him."
            ),
            second_nature_habit=(
                "Inspected finished products personally before shipment, "
                "smashing anything below standard with his walking stick — "
                "treating quality as a non-negotiable daily practice."
            ),
        ),
    ]
    return {l.leader_id: l for l in leaders}


VICTORIAN_LEADERS: Dict[str, VictorianLeader] = _build_victorian_leaders()


# ---------------------------------------------------------------------------
# Second Nature Behaviors Library
# ---------------------------------------------------------------------------

SECOND_NATURE_BEHAVIORS: List[SecondNatureBehavior] = [

    SecondNatureBehavior(
        behavior_id="integrity_01",
        pillar=CharacterPillar.INTEGRITY,
        description="State the downside before the upside in every recommendation",
        trigger="Any time you are recommending a course of action",
        micro_action="Say 'Here's the risk first — then the opportunity.'",
        compounding_effect="People trust your enthusiasm because they've learned you don't hide problems",
        victorian_exemplar="John Stuart Mill — always presented the strongest counter-argument first",
    ),
    SecondNatureBehavior(
        behavior_id="integrity_02",
        pillar=CharacterPillar.INTEGRITY,
        description="Admit error immediately and specifically when wrong",
        trigger="Any time you discover you were incorrect",
        micro_action="'I was wrong about X. Here's what I now understand.'",
        compounding_effect="Builds a reputation for reliability that compounds over years",
        victorian_exemplar="Cardinal Newman — publicly reversed positions when evidence demanded it",
    ),
    SecondNatureBehavior(
        behavior_id="courage_01",
        pillar=CharacterPillar.MORAL_COURAGE,
        description="Name the thing in the room no one else is naming",
        trigger="Any meeting where a real problem is being discussed around, not about",
        micro_action="'Can I name what I think the actual issue is here?'",
        compounding_effect="Becomes known as the person who makes uncomfortable conversations possible",
        victorian_exemplar="Wilberforce — named slavery as a moral catastrophe when it was economically convenient",
    ),
    SecondNatureBehavior(
        behavior_id="courage_02",
        pillar=CharacterPillar.MORAL_COURAGE,
        description="Defend an absent person when they are being unfairly criticised",
        trigger="Any conversation where someone not present is being blamed",
        micro_action="'Let me offer a different perspective on what might have driven that decision.'",
        compounding_effect="People learn that you will defend them in rooms they're not in — priceless trust",
        victorian_exemplar="Frederick Douglass — defended the character of those who couldn't defend themselves",
    ),
    SecondNatureBehavior(
        behavior_id="service_01",
        pillar=CharacterPillar.SERVICE_ABOVE_SELF,
        description="Send one piece of useful information to someone in your network weekly — unprompted",
        trigger="Every Monday morning",
        micro_action="'I saw this and thought of you — no agenda, just thought it might be relevant.'",
        compounding_effect="Network becomes a compounding trust asset; people become sources of opportunity",
        victorian_exemplar="Florence Nightingale — daily correspondence that served others' needs, not her agenda",
    ),
    SecondNatureBehavior(
        behavior_id="service_02",
        pillar=CharacterPillar.SERVICE_ABOVE_SELF,
        description="Make the introduction before being asked",
        trigger="Any time you recognise two people would benefit from knowing each other",
        micro_action="Send a personal introduction email within 24 hours of the recognition",
        compounding_effect="Becomes known as the person whose introductions are always valuable",
        victorian_exemplar="Lord Shaftesbury — introduced working-class advocates to aristocratic allies",
    ),
    SecondNatureBehavior(
        behavior_id="wisdom_01",
        pillar=CharacterPillar.WISDOM,
        description="Ask one more question before offering advice",
        trigger="Any time someone brings a problem to you",
        micro_action="'Before I respond — help me understand one more thing about the situation.'",
        compounding_effect="Advice becomes dramatically more useful; people seek you out before anyone else",
        victorian_exemplar="Ada Lovelace — always asked 'what does this make possible?' before analysing",
    ),
    SecondNatureBehavior(
        behavior_id="justice_01",
        pillar=CharacterPillar.JUSTICE,
        description="Credit others' contributions publicly and specifically",
        trigger="Any time you present work that others contributed to",
        micro_action="'This came from [name]'s insight that [specific thing].'",
        compounding_effect="People bring you their best thinking because they know you'll give it a fair hearing",
        victorian_exemplar="Harriet Tubman — never spoke of her own contribution, only others'",
    ),
    SecondNatureBehavior(
        behavior_id="fortitude_01",
        pillar=CharacterPillar.FORTITUDE,
        description="Report setbacks before reporting to be asked",
        trigger="Any time a project or commitment falls behind",
        micro_action="'Here's what happened, what I've learned, and what I'm doing next.'",
        compounding_effect="Builds a reputation for reliability under pressure — the rarest professional trait",
        victorian_exemplar="Booker T. Washington — reported obstacles to donors before they could discover them",
    ),
    SecondNatureBehavior(
        behavior_id="temperance_01",
        pillar=CharacterPillar.TEMPERANCE,
        description="Pause 10 seconds before responding to provocation or criticism",
        trigger="Any time you feel reactive, defensive, or angry in a professional context",
        micro_action="Physical pause — breathe, then respond as if you had waited 24 hours",
        compounding_effect="Never says something in anger that creates a permanent relational cost",
        victorian_exemplar="George Eliot — rewrote angry responses and sent measured ones instead",
    ),
    SecondNatureBehavior(
        behavior_id="prudence_01",
        pillar=CharacterPillar.PRUDENCE,
        description="Ask 'who is not in this room whose interests are affected?'",
        trigger="Any strategic or resource allocation decision",
        micro_action="Explicitly name absent stakeholders before the decision is finalised",
        compounding_effect="Decisions hold because they've been tested against all relevant perspectives",
        victorian_exemplar="Lord Shaftesbury — always asked what child labourers would say about factory decisions",
    ),
    SecondNatureBehavior(
        behavior_id="prudence_02",
        pillar=CharacterPillar.PRUDENCE,
        description="Write the handwritten thank-you note within 24 hours",
        trigger="Any meaningful meeting, introduction, favour, or act of trust",
        micro_action="Handwritten card or personal email — specific about what they did and why it mattered",
        compounding_effect="Every note is a permanent reminder of your character when the relationship needs it",
        victorian_exemplar="Benjamin Disraeli — handwritten notes within 24 hours of every significant meeting",
    ),
]


# ---------------------------------------------------------------------------
# CharacterAssessor
# ---------------------------------------------------------------------------

class CharacterAssessor:
    """
    Scores a subject's moral fiber across 8 character pillars
    based on behavioral evidence signals.
    """

    # Keyword → pillar mapping for signal detection
    _PILLAR_KEYWORDS: Dict[CharacterPillar, Tuple[str, ...]] = {
        CharacterPillar.INTEGRITY:          ("honest", "transparent", "consistent", "word", "truth", "accurate"),
        CharacterPillar.MORAL_COURAGE:      ("stood up", "disagreed", "challenged", "refused", "brave", "despite"),
        CharacterPillar.SERVICE_ABOVE_SELF: ("helped", "volunteered", "introduced", "gave", "served", "contributed"),
        CharacterPillar.WISDOM:             ("patient", "considered", "asked", "listened", "experienced", "reflected"),
        CharacterPillar.JUSTICE:            ("fair", "credited", "defended", "equal", "inclusive", "acknowledged"),
        CharacterPillar.FORTITUDE:          ("persisted", "continued", "recovered", "despite setback", "didn't quit"),
        CharacterPillar.TEMPERANCE:         ("restrained", "paused", "didn't react", "controlled", "disciplined"),
        CharacterPillar.PRUDENCE:           ("planned", "considered consequences", "thought ahead", "prepared", "strategic"),
    }

    def assess(self, behavioral_signals: List[str], subject_id: str = "unknown") -> MoralFiberScore:
        """
        Score a subject based on behavioral evidence strings.

        Parameters
        ----------
        behavioral_signals:
            List of observed behaviors, testimonials, or self-descriptions.
        subject_id:
            Identifier for the subject being assessed.
        """
        combined = " ".join(s.lower() for s in behavioral_signals)
        words    = set(re.findall(r"\b\w+\b", combined))

        pillar_scores: Dict[CharacterPillar, float] = {}
        for pillar, keywords in self._PILLAR_KEYWORDS.items():
            # Count keyword hits (each hit adds 0.05 to a 0.70 base)
            hits = sum(1 for kw in keywords if kw in combined)
            score = min(1.0, 0.70 + hits * 0.05)
            pillar_scores[pillar] = round(score, 4)

        return MoralFiberScore(
            subject_id=subject_id,
            pillar_scores=pillar_scores,
            behavioral_evidence=behavioral_signals[:10],
        )

    def score_pillar(self, pillar: CharacterPillar, evidence: List[str]) -> float:
        """Score a single pillar from evidence strings."""
        combined = " ".join(e.lower() for e in evidence)
        keywords = self._PILLAR_KEYWORDS.get(pillar, ())
        hits = sum(1 for kw in keywords if kw in combined)
        return min(1.0, round(0.70 + hits * 0.05, 4))


# ---------------------------------------------------------------------------
# VictorianLeaderLibrary
# ---------------------------------------------------------------------------

class VictorianLeaderLibrary:
    """Access and search the Victorian leader corpus."""

    def get_all(self) -> Dict[str, VictorianLeader]:
        return VICTORIAN_LEADERS

    def get_by_class(self, char_class: VictorianCharacterClass) -> List[VictorianLeader]:
        return [l for l in VICTORIAN_LEADERS.values() if l.character_class == char_class]

    def find_archetype(self, score: MoralFiberScore) -> VictorianLeader:
        """Find the Victorian leader whose pillar profile most closely matches this score."""
        return min(
            VICTORIAN_LEADERS.values(),
            key=lambda l: l.distance_to(score.pillar_scores),
        )

    def top_n_by_score(self, n: int = 5) -> List[VictorianLeader]:
        return sorted(VICTORIAN_LEADERS.values(), key=lambda l: l.overall_score, reverse=True)[:n]

    def pillar_champions(self) -> Dict[CharacterPillar, VictorianLeader]:
        """Return the leader with the highest score on each pillar."""
        return {
            pillar: max(VICTORIAN_LEADERS.values(), key=lambda l: l.pillar_scores.get(pillar, 0.0))
            for pillar in ALL_PILLARS
        }


# ---------------------------------------------------------------------------
# SecondNatureBehaviorEngine
# ---------------------------------------------------------------------------

class SecondNatureBehaviorEngine:
    """
    Builds and manages the 'second nature' habit stack for a character profile.

    Second nature means these behaviors fire automatically — they are not
    conscious moral calculations but trained reflexes of good character.
    """

    def get_behaviors_for_pillar(self, pillar: CharacterPillar) -> List[SecondNatureBehavior]:
        """Return all behaviors associated with a specific pillar."""
        return [b for b in SECOND_NATURE_BEHAVIORS if b.pillar == pillar]

    def build_habit_stack(self, score: MoralFiberScore) -> List[SecondNatureBehavior]:
        """
        Build a prioritised habit stack for a moral fiber score.

        Prioritises behaviors for the three lowest-scoring pillars first
        (highest development leverage), then adds one from the dominant pillar
        to keep the strength strong.
        """
        development_pillars = [p for p, _ in score.development_areas[:3]]
        dominant_pillar = score.dominant_pillar[0]

        habit_stack: List[SecondNatureBehavior] = []
        seen_pillars: set = set()

        # Priority: development areas first
        for pillar in development_pillars:
            behaviors = self.get_behaviors_for_pillar(pillar)
            if behaviors:
                habit_stack.append(behaviors[0])
                seen_pillars.add(pillar)

        # Then dominant pillar (maintain the strength)
        if dominant_pillar not in seen_pillars:
            behaviors = self.get_behaviors_for_pillar(dominant_pillar)
            if behaviors:
                habit_stack.append(behaviors[0])

        # Fill with any remaining untouched pillars
        for pillar in ALL_PILLARS:
            if pillar not in seen_pillars and pillar != dominant_pillar:
                behaviors = self.get_behaviors_for_pillar(pillar)
                if behaviors and len(habit_stack) < 5:
                    habit_stack.append(behaviors[0])
                    seen_pillars.add(pillar)

        return habit_stack

    def embed_into_agent(self, agent_genome: Dict[str, Any]) -> Dict[str, Any]:
        """
        Embed second nature character signals into an agent's SkillGenome-style scores.

        Adds a 'character_overlay' key with second-nature behavior scores.
        """
        result = dict(agent_genome)
        result["character_overlay"] = {
            "integrity_signal":        0.92,
            "service_reflex":          0.90,
            "courage_default":         0.88,
            "wisdom_pause":            0.87,
            "justice_lens":            0.90,
            "fortitude_baseline":      0.89,
            "temperance_check":        0.87,
            "prudence_horizon":        0.91,
        }
        return result


# ---------------------------------------------------------------------------
# CharacterNetworkBuilder
# ---------------------------------------------------------------------------

class CharacterNetworkBuilder:
    """
    Builds and assesses character-based professional networks.

    The core principle: choose network members for moral fibre first,
    influence second.  A small network of high-character allies is more
    valuable than a large network of low-character contacts.
    """

    def __init__(self) -> None:
        self._assessor = CharacterAssessor()
        self._library  = VictorianLeaderLibrary()
        self._engine   = SecondNatureBehaviorEngine()

    def build_profile(
        self,
        agent_id: str,
        behavioral_signals: List[str],
    ) -> CharacterNetworkProfile:
        """Build a full CharacterNetworkProfile for an agent."""
        score    = self._assessor.assess(behavioral_signals, subject_id=agent_id)
        archetype = self._library.find_archetype(score)
        habits   = self._engine.build_habit_stack(score)
        network  = self._build_example_network(score)
        dev_plan = self._build_development_plan(score, archetype)
        health   = self._assess_network_health(network)

        return CharacterNetworkProfile(
            agent_id=agent_id,
            own_moral_fiber=score,
            archetype_match=archetype,
            second_nature_behaviors=habits,
            network_by_tier=network,
            development_plan=dev_plan,
            network_health_score=health,
        )

    def recommend_connections(
        self,
        score: MoralFiberScore,
        count: int = 5,
    ) -> List[NetworkCandidate]:
        """Recommend network additions based on character profile."""
        # In production this would query a live people graph.
        # Here we return archetype-informed recommendations.
        library = self._library
        archetype = library.find_archetype(score)
        dev_areas = [p for p, _ in score.development_areas[:3]]

        recommendations = []
        for i, (pillar, _) in enumerate(score.development_areas[:count]):
            champ = library.pillar_champions().get(pillar)
            if champ:
                tier = NetworkTier.TRUSTED_ADVISORS if i < 2 else NetworkTier.EXTENDED_NETWORK
                recommendations.append(NetworkCandidate(
                    candidate_id=f"rec_{pillar.value}",
                    name=f"Model: {champ.name}",
                    moral_fiber=MoralFiberScore(
                        subject_id=champ.leader_id,
                        pillar_scores=champ.pillar_scores,
                    ),
                    network_tier=tier,
                    connection_rationale=(
                        f"Strengthens your {pillar.value} dimension — "
                        f"their second nature habit: '{champ.second_nature_habit[:80]}'"
                    ),
                    mutual_benefit="Character development through proximity and shared accountability",
                    introduction_approach=(
                        f"Lead with what you admire about their {pillar.value.replace('_', ' ')} "
                        f"practice — and ask one specific question about how they built it."
                    ),
                ))
        return recommendations[:count]

    def assess_network_health(self, candidates: List[NetworkCandidate]) -> float:
        """Compute network health score from 0–1 based on member moral fiber averages."""
        if not candidates:
            return 0.0
        avg = sum(c.moral_fiber.overall_score for c in candidates) / len(candidates)
        return round(avg, 4)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_example_network(
        self,
        score: MoralFiberScore,
    ) -> Dict[NetworkTier, List[NetworkCandidate]]:
        """Build an example network structure from Victorian archetypes."""
        leaders = list(VICTORIAN_LEADERS.values())[:8]
        network: Dict[NetworkTier, List[NetworkCandidate]] = {
            NetworkTier.INNER_CIRCLE:     [],
            NetworkTier.TRUSTED_ADVISORS: [],
            NetworkTier.EXTENDED_NETWORK: [],
            NetworkTier.COMMUNITY_IMPACT: [],
        }
        tiers = [
            NetworkTier.INNER_CIRCLE,
            NetworkTier.INNER_CIRCLE,
            NetworkTier.TRUSTED_ADVISORS,
            NetworkTier.TRUSTED_ADVISORS,
            NetworkTier.EXTENDED_NETWORK,
            NetworkTier.EXTENDED_NETWORK,
            NetworkTier.COMMUNITY_IMPACT,
            NetworkTier.COMMUNITY_IMPACT,
        ]
        for leader, tier in zip(leaders, tiers):
            cand = NetworkCandidate(
                candidate_id=leader.leader_id,
                name=leader.name,
                moral_fiber=MoralFiberScore(
                    subject_id=leader.leader_id,
                    pillar_scores=leader.pillar_scores,
                ),
                network_tier=tier,
                connection_rationale=leader.network_approach[:100],
                mutual_benefit=leader.modern_parallel[:100],
                introduction_approach=leader.second_nature_habit[:100],
            )
            network[tier].append(cand)
        return network

    def _build_development_plan(
        self,
        score: MoralFiberScore,
        archetype: VictorianLeader,
    ) -> List[Dict[str, Any]]:
        """Build a 3-priority character development plan."""
        plan = []
        for i, (pillar, current_score) in enumerate(score.development_areas[:3]):
            behaviors = self._engine.get_behaviors_for_pillar(pillar)
            behavior  = behaviors[0] if behaviors else None
            plan.append({
                "priority":         i + 1,
                "pillar":           pillar.value,
                "current_score":    round(current_score, 4),
                "target_score":     min(1.0, round(current_score + 0.10, 4)),
                "archetype_model":  archetype.name,
                "weekly_practice":  behavior.micro_action if behavior else f"Develop {pillar.value}",
                "trigger":          behavior.trigger if behavior else "Daily practice",
                "compounding":      behavior.compounding_effect if behavior else "Character deepens over time",
                "victorian_model":  behavior.victorian_exemplar if behavior else archetype.name,
            })
        return plan

    def _assess_network_health(
        self,
        network: Dict[NetworkTier, List[NetworkCandidate]],
    ) -> float:
        all_candidates = [c for tier in network.values() for c in tier]
        return self.assess_network_health(all_candidates)


# ---------------------------------------------------------------------------
# CharacterNetworkEngine — top-level façade
# ---------------------------------------------------------------------------

class CharacterNetworkEngine:
    """
    Top-level façade for the Character Network Engine.

    Builds character profiles, habit stacks, network recommendations,
    and development plans anchored in Victorian-era character wisdom.

    Usage::

        engine = CharacterNetworkEngine()

        profile = engine.profile_agent(
            agent_id="alex_reeves",
            behavioral_signals=[
                "helped a colleague without being asked",
                "admitted an error to the team",
                "stood up for a junior colleague in a difficult meeting",
            ],
        )
        print(profile.archetype_match.name)
        for habit in profile.second_nature_behaviors:
            print(f"  [{habit.pillar.value}] {habit.micro_action}")
    """

    def __init__(self) -> None:
        self._builder = CharacterNetworkBuilder()
        self._library = VictorianLeaderLibrary()
        self._engine  = SecondNatureBehaviorEngine()

    def profile_agent(
        self,
        agent_id: str,
        behavioral_signals: List[str],
    ) -> CharacterNetworkProfile:
        """Build a full character network profile from behavioral signals."""
        return self._builder.build_profile(agent_id, behavioral_signals)

    def get_second_nature_habits(self, score: MoralFiberScore) -> List[SecondNatureBehavior]:
        """Return a prioritised second-nature habit stack for a moral fiber score."""
        return self._engine.build_habit_stack(score)

    def describe_victorian_leader(self, leader_id: str) -> Optional[Dict[str, Any]]:
        """Return the full profile of a Victorian leader by ID."""
        leader = VICTORIAN_LEADERS.get(leader_id)
        return leader.to_dict() if leader else None

    def network_audit(self, profile: CharacterNetworkProfile) -> Dict[str, Any]:
        """Audit the health and composition of a character network."""
        all_candidates = [c for tier in profile.network_by_tier.values() for c in tier]
        pillar_dist: Dict[str, int] = {}
        for cand in all_candidates:
            dom = cand.moral_fiber.dominant_pillar[0].value
            pillar_dist[dom] = pillar_dist.get(dom, 0) + 1

        return {
            "agent_id":            profile.agent_id,
            "network_size":        profile.total_network_size,
            "health_score":        profile.network_health_score,
            "pillar_distribution": pillar_dist,
            "inner_circle_size":   len(profile.network_by_tier.get(NetworkTier.INNER_CIRCLE, [])),
            "gaps":                [p.value for p, _ in profile.own_moral_fiber.development_areas],
            "archetype":           profile.archetype_match.name,
            "character_archetype": profile.own_moral_fiber.character_archetype,
            "second_nature_habits": len(profile.second_nature_behaviors),
        }

    def all_behaviors(self) -> List[SecondNatureBehavior]:
        """Return all second-nature behaviors in the library."""
        return SECOND_NATURE_BEHAVIORS

    def all_leaders(self) -> Dict[str, VictorianLeader]:
        """Return the full Victorian leader corpus."""
        return VICTORIAN_LEADERS
