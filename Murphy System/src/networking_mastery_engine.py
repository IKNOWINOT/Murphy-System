"""
Networking Mastery Engine — Murphy System
==========================================

Encodes the strategies of history's greatest network builders and applies
them as a live system for buzz creation, capability signalling, and
network intelligence.

Three Capability Layers
-----------------------
Every truly powerful networker communicates on three simultaneous layers:

  FACE VALUE      — What you explicitly say you do.
                    The direct value proposition.  Clear, credible, measurable.

  BETWEEN LINES   — What your presence signals without saying.
                    Your network, your questions, your energy, your clients —
                    the unspoken evidence of what you are worth.

  OUTSIDE BOX     — Unexpected applications of your capability.
                    Cross-domain skill transfers that the other person didn't
                    expect but immediately recognises as valuable.

The networkers who built the greatest networks operated on all three layers
simultaneously.  Caesar knew every soldier's name (between lines: I see you).
Franklin ran salons where ideas collided (outside box: unexpected connections).
Nightingale shared data to make her case unanswerable (face value: numbers win).

The 6 Networking Styles
-----------------------
  POLITICAL     — Coalition building for power and influence
  INTELLECTUAL  — Ideas-based networks (salons, journals, conferences)
  COMMERCIAL    — Business networks (supplier, customer, investor, partner)
  COMMUNITY     — Grassroots and cause-based networks
  DIGITAL       — Platform and social networks (LinkedIn, communities, media)
  CULTURAL      — Arts, media, and taste-making networks

Design Label: NME-001 — Networking Mastery Engine
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

class NetworkingStyle(str, Enum):
    POLITICAL    = "political"
    INTELLECTUAL = "intellectual"
    COMMERCIAL   = "commercial"
    COMMUNITY    = "community"
    DIGITAL      = "digital"
    CULTURAL     = "cultural"


class BuzzType(str, Enum):
    WORD_OF_MOUTH       = "word_of_mouth"
    THOUGHT_LEADERSHIP  = "thought_leadership"
    SOCIAL_PROOF        = "social_proof"
    DEMONSTRATION       = "demonstration_effect"
    VIRAL_LOOP          = "viral_loop"


class CapabilityLayer(str, Enum):
    FACE_VALUE    = "face_value"      # What you explicitly say
    BETWEEN_LINES = "between_lines"   # What you implicitly signal
    OUTSIDE_BOX   = "outside_box"     # Unexpected applications of your skill


class NetworkHealthStatus(str, Enum):
    ELITE        = "elite"        # NQ > 0.85
    STRONG       = "strong"       # NQ > 0.70
    DEVELOPING   = "developing"   # NQ > 0.55
    NASCENT      = "nascent"      # NQ ≤ 0.55


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NetworkingGreat:
    """
    A historical master networker — modelled with methodology and modern translation.
    """
    great_id:            str
    name:                str
    era:                 str
    primary_style:       NetworkingStyle
    secondary_styles:    Tuple[NetworkingStyle, ...]
    signature_method:    str   # The single most distinctive networking technique
    network_scale:       str   # How large / far-reaching their network was
    buzz_mechanism:      str   # How they generated reputation momentum
    face_value_signal:   str   # Their explicit value claim
    between_lines_signal: str  # What their presence implied
    outside_box_move:    str   # The unexpected capability transfer that surprised people
    modern_translation:  str   # What this looks like for a 2025 professional
    core_principle:      str   # The transferable networking insight
    network_quote:       str   # A quote that captures their philosophy

    @property
    def networking_iq_score(self) -> float:
        """Proxy score based on style breadth and method sophistication."""
        style_count = 1 + len(self.secondary_styles)
        return round(min(1.0, 0.70 + style_count * 0.05), 4)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "great_id":             self.great_id,
            "name":                 self.name,
            "era":                  self.era,
            "primary_style":        self.primary_style.value,
            "secondary_styles":     [s.value for s in self.secondary_styles],
            "signature_method":     self.signature_method,
            "buzz_mechanism":       self.buzz_mechanism,
            "face_value_signal":    self.face_value_signal,
            "between_lines_signal": self.between_lines_signal,
            "outside_box_move":     self.outside_box_move,
            "modern_translation":   self.modern_translation,
            "core_principle":       self.core_principle,
            "network_quote":        self.network_quote,
            "networking_iq_score":  self.networking_iq_score,
        }


@dataclass(frozen=True)
class BuzzCampaign:
    """A structured buzz creation strategy."""
    campaign_id:            str
    buzz_type:              BuzzType
    strategy_name:          str
    primary_vehicle:        str       # LinkedIn series, podcast, demo event, etc.
    trigger_event:          str       # What launches this
    propagation_mechanism:  str       # How it spreads
    amplification_tactics:  Tuple[str, ...]
    measurement_metric:     str
    timeline_days:          int
    reach_multiplier:       float     # expected impressions / effort ratio
    great_exemplar:         str       # which networking great used this

    def to_dict(self) -> Dict[str, Any]:
        return {
            "campaign_id":           self.campaign_id,
            "buzz_type":             self.buzz_type.value,
            "strategy_name":         self.strategy_name,
            "primary_vehicle":       self.primary_vehicle,
            "trigger_event":         self.trigger_event,
            "propagation_mechanism": self.propagation_mechanism,
            "amplification_tactics": list(self.amplification_tactics),
            "measurement_metric":    self.measurement_metric,
            "timeline_days":         self.timeline_days,
            "reach_multiplier":      self.reach_multiplier,
            "great_exemplar":        self.great_exemplar,
        }


@dataclass
class CapabilitySignalSet:
    """
    Complete three-layer capability signal set for an agent or professional.

    Face value + between lines + outside box — what you say, what you imply,
    and what no one expected you to also be able to do.
    """
    subject_id:         str
    face_value:         List[str]     # Explicit, direct capability claims
    between_lines:      List[str]     # Implicit signals your presence communicates
    outside_box:        List[str]     # Unexpected cross-domain applications
    archetype_match:    Optional[NetworkingGreat] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subject_id":      self.subject_id,
            "face_value":      self.face_value,
            "between_lines":   self.between_lines,
            "outside_box":     self.outside_box,
            "archetype_match": self.archetype_match.name if self.archetype_match else None,
        }


@dataclass
class NetworkIntelligenceReport:
    """Complete network intelligence analysis for an agent."""
    agent_id:            str
    networking_style:    NetworkingStyle
    archetype_match:     NetworkingGreat
    capability_signals:  CapabilitySignalSet
    buzz_campaigns:      List[BuzzCampaign]
    network_gaps:        List[str]
    quick_wins:          List[str]
    ninety_day_plan:     List[Dict[str, Any]]
    network_iq:          float

    @property
    def health_status(self) -> NetworkHealthStatus:
        if self.network_iq > 0.85:
            return NetworkHealthStatus.ELITE
        if self.network_iq > 0.70:
            return NetworkHealthStatus.STRONG
        if self.network_iq > 0.55:
            return NetworkHealthStatus.DEVELOPING
        return NetworkHealthStatus.NASCENT

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id":           self.agent_id,
            "networking_style":   self.networking_style.value,
            "archetype_match":    self.archetype_match.name,
            "network_iq":         self.network_iq,
            "health_status":      self.health_status.value,
            "capability_signals": self.capability_signals.to_dict(),
            "buzz_campaigns":     [b.to_dict() for b in self.buzz_campaigns],
            "network_gaps":       self.network_gaps,
            "quick_wins":         self.quick_wins,
            "ninety_day_plan":    self.ninety_day_plan,
        }


# ---------------------------------------------------------------------------
# Networking Greats Corpus — 18 master networkers
# ---------------------------------------------------------------------------

def _build_networking_greats() -> Dict[str, NetworkingGreat]:
    greats = [

        NetworkingGreat(
            great_id="julius_caesar",
            name="Julius Caesar",
            era="100–44 BC",
            primary_style=NetworkingStyle.POLITICAL,
            secondary_styles=(NetworkingStyle.COMMERCIAL, NetworkingStyle.CULTURAL),
            signature_method=(
                "Remembered the name, hometown, and personal history of every legionary "
                "under his command — 10,000+ men — creating individual loyalty at scale."
            ),
            network_scale="Military network spanning 30+ legions across 3 continents",
            buzz_mechanism=(
                "His Commentarii (field dispatches) were published in Rome while he was "
                "on campaign — real-time narrative control that made him the protagonist "
                "of his own story before opponents could shape it."
            ),
            face_value_signal="I win campaigns and I share the spoils with those who serve.",
            between_lines_signal=(
                "When Caesar remembered your name, you understood: he sees individuals, "
                "not numbers. That signal of recognition creates loyalty no salary can buy."
            ),
            outside_box_move=(
                "Used his financial network (Crassus) to fund political ambitions — "
                "crossed domains (military → finance → politics) fluidly when others stayed in one."
            ),
            modern_translation=(
                "The CRM master who turns data into personal recognition. "
                "A modern Caesar has a system for remembering what everyone on their team "
                "values, fears, and is working toward — and acts on that knowledge daily."
            ),
            core_principle=(
                "Recognition at scale. Every person you make feel seen becomes an advocate. "
                "The network effect of personal recognition compounds faster than any "
                "marketing strategy."
            ),
            network_quote="Veni, vidi, vici — but the real victory was knowing which allies to bring.",
        ),

        NetworkingGreat(
            great_id="benjamin_franklin",
            name="Benjamin Franklin",
            era="1706–1790",
            primary_style=NetworkingStyle.INTELLECTUAL,
            secondary_styles=(NetworkingStyle.POLITICAL, NetworkingStyle.COMMERCIAL),
            signature_method=(
                "The Junto Club: founded a mutual improvement society of 12 tradesmen — "
                "a structured weekly mastermind that met for 38 years and became the "
                "seedbed of the Philadelphia Library, fire department, and university."
            ),
            network_scale="Correspondence network spanning North America and Europe; personal contacts in 6 countries",
            buzz_mechanism=(
                "Poor Richard's Almanack: annual publication of wisdom, wit, and practical advice — "
                "10,000 copies/year made him the most widely read American author of his era "
                "before he'd done anything politically significant."
            ),
            face_value_signal="I solve practical problems through organised collective thinking.",
            between_lines_signal=(
                "His curiosity and genuine delight in other people's ideas made "
                "every conversation feel like the most interesting he'd had — "
                "people sought him out because being with him made them smarter."
            ),
            outside_box_move=(
                "Applied scientific credibility (electricity experiments) to give him "
                "diplomatic weight in France — crossed from science to politics using "
                "intellectual reputation as the bridge."
            ),
            modern_translation=(
                "The mastermind architect who builds structured intellectual communities. "
                "A modern Franklin runs a weekly peer group, publishes a regular newsletter, "
                "and treats every conversation as both giving and receiving."
            ),
            core_principle=(
                "Structured reciprocity. The mastermind format — regular, structured exchange "
                "among a committed group — is still the most powerful networking technology "
                "ever invented. Franklin invented it in 1727."
            ),
            network_quote=(
                "An investment in knowledge pays the best interest — "
                "and knowledge shared in community pays compound interest."
            ),
        ),

        NetworkingGreat(
            great_id="napoleon_networking",
            name="Napoleon Bonaparte",
            era="1769–1821",
            primary_style=NetworkingStyle.POLITICAL,
            secondary_styles=(NetworkingStyle.COMMERCIAL, NetworkingStyle.CULTURAL),
            signature_method=(
                "Promotion by merit and loyalty simultaneously — built a network of generals "
                "who owed him everything and knew it, creating reciprocal personal loyalty "
                "at every level of the hierarchy."
            ),
            network_scale="Pan-European military-political network of 800+ senior officers and administrators",
            buzz_mechanism=(
                "His bulletins were masterworks of selective truth — victories amplified, "
                "defeats reframed, always with Caesar as the hero. "
                "The first modern propaganda machine."
            ),
            face_value_signal="Serve with me and I will advance you on merit — no one else offers that.",
            between_lines_signal=(
                "His personal attention to officers in the field — walking the lines, "
                "calling men by name — signalled that proximity to Napoleon meant visibility, "
                "and visibility meant opportunity."
            ),
            outside_box_move=(
                "Used his legal network (Code Napoléon) to reshape European governance — "
                "a military commander who understood that legal infrastructure was "
                "the most durable network he could build."
            ),
            modern_translation=(
                "The talent developer who builds an alumni network of people who owe "
                "their careers to working for you. A modern Napoleon gives everyone "
                "who works for them a bigger title and responsibility than they can "
                "currently justify — and watches them grow into it."
            ),
            core_principle=(
                "Loyalty through advancement. The most durable network is built from "
                "people whose success you made possible. They will work harder for you "
                "than for any financial incentive."
            ),
            network_quote="Impossible is a word found only in the dictionary of fools — and in the vocabulary of those without a network.",
        ),

        NetworkingGreat(
            great_id="andrew_carnegie",
            name="Andrew Carnegie",
            era="1835–1919",
            primary_style=NetworkingStyle.COMMERCIAL,
            secondary_styles=(NetworkingStyle.INTELLECTUAL, NetworkingStyle.COMMUNITY),
            signature_method=(
                "The Carnegie Memos: obsessive written follow-up after every significant "
                "meeting — handwritten notes to steel buyers, railroad executives, and "
                "politicians within 24 hours, always referencing something specific they said."
            ),
            network_scale="Industrial network spanning 50+ major steel buyers, 200+ railroad executives, and 3 governments",
            buzz_mechanism=(
                "Philanthropy as strategic reputation: 2,500 libraries and Carnegie Hall "
                "created a permanent, visible proof of character that preceded him "
                "into every business negotiation."
            ),
            face_value_signal="I deliver more steel, faster, at lower cost, than any competitor.",
            between_lines_signal=(
                "His personal library of 80,000 books, donated to public use, signalled: "
                "this is not a robber baron — this is someone who believes in human development. "
                "That signal opened doors that money alone couldn't."
            ),
            outside_box_move=(
                "Used his experience as a telegraph operator (at 14) to build faster "
                "information networks in his steel business — crossed from communications "
                "to manufacturing, carrying the information advantage with him."
            ),
            modern_translation=(
                "The systematic follow-up machine who turns every conversation into a "
                "compounding relationship. A modern Carnegie has a CRM note for every "
                "meeting within 24 hours and a personal follow-up within 7 days."
            ),
            core_principle=(
                "Philanthropy as differentiation. The professional who is visibly invested "
                "in their community's flourishing commands a premium in every negotiation — "
                "because the other party knows they're dealing with someone whose "
                "reputation is worth more to them than any single deal."
            ),
            network_quote="No man will make a great leader who wants to do it all himself, or to get all the credit for doing it.",
        ),

        NetworkingGreat(
            great_id="dale_carnegie",
            name="Dale Carnegie",
            era="1888–1955",
            primary_style=NetworkingStyle.INTELLECTUAL,
            secondary_styles=(NetworkingStyle.COMMERCIAL, NetworkingStyle.COMMUNITY),
            signature_method=(
                "The Name Rule: remember and use the other person's name — "
                "a name is to a person the sweetest and most important sound "
                "in any language. Systematic, deliberate, compounding."
            ),
            network_scale="Teaching methodology that reached 8 million people across 80 countries",
            buzz_mechanism=(
                "'How to Win Friends and Influence People' (1936): the first systematic "
                "codification of relationship building as a teachable skill — "
                "word-of-mouth propagation driven by the book's practical results."
            ),
            face_value_signal="I teach you how to make anyone want to work with you.",
            between_lines_signal=(
                "Carnegie's genuine curiosity about every person he met was felt immediately. "
                "He was famous for making each person feel like the most interesting "
                "person in any room — a signal of presence that no technique can fake."
            ),
            outside_box_move=(
                "Applied stage-fright management techniques (from his speaking background) "
                "to business networking training — turned performance anxiety into "
                "a competitive advantage by teaching others to manage it."
            ),
            modern_translation=(
                "The systematic relationship architect. A modern Carnegie has a "
                "documented method for every relationship touchpoint: first meeting, "
                "follow-up, check-in, support, and celebration of the other person's wins."
            ),
            core_principle=(
                "You can make more friends in two months by becoming interested in "
                "other people than you can in two years by trying to get other "
                "people interested in you. This principle has never been superseded."
            ),
            network_quote="You can make more friends in two months by becoming interested in other people than in two years trying to get people interested in you.",
        ),

        NetworkingGreat(
            great_id="warren_buffett_network",
            name="Warren Buffett",
            era="1930–present",
            primary_style=NetworkingStyle.COMMERCIAL,
            secondary_styles=(NetworkingStyle.INTELLECTUAL, NetworkingStyle.COMMUNITY),
            signature_method=(
                "The Lunch Auction strategy: made himself accessible to exactly the right "
                "people (shareholder meetings, Omaha pilgrimage) while remaining "
                "intentionally inaccessible to the wrong ones — controlled scarcity."
            ),
            network_scale="Global network of CEOs, investors, and operators who orbit Berkshire Hathaway",
            buzz_mechanism=(
                "Annual shareholder letter: 40+ years of writing that is simultaneously "
                "a financial report, a philosophy essay, and a character demonstration — "
                "the most widely forwarded business document in the world."
            ),
            face_value_signal="I deploy capital into businesses run by people I trust for as long as it works.",
            between_lines_signal=(
                "When Buffett partners with you, his reputation becomes collateral. "
                "Every CEO in his network knows that Berkshire's name on a deal "
                "signals character and patience — a signal no press release can manufacture."
            ),
            outside_box_move=(
                "Applied insurance float theory to equity investing — crossed from "
                "insurance to finance in a way that no pure investor saw coming, "
                "creating a structural funding advantage that compounded for 60 years."
            ),
            modern_translation=(
                "The annual letter architect. A modern Buffett writes one deep, "
                "honest, specific communication per year that demonstrates "
                "character, teaches something useful, and makes the reader feel "
                "smarter for having read it."
            ),
            core_principle=(
                "Reputation compounds. Every year of consistent, transparent behaviour "
                "makes your network more valuable at an accelerating rate. "
                "The best networking strategy is to be the same person at 80 "
                "that you were at 30."
            ),
            network_quote="It takes 20 years to build a reputation and five minutes to ruin it. If you think about that, you'll do things differently.",
        ),

        NetworkingGreat(
            great_id="oprah_winfrey",
            name="Oprah Winfrey",
            era="1954–present",
            primary_style=NetworkingStyle.CULTURAL,
            secondary_styles=(NetworkingStyle.INTELLECTUAL, NetworkingStyle.COMMUNITY),
            signature_method=(
                "The Oprah Effect: a personal endorsement that could move a book "
                "from 10,000 to 1,000,000 sales in a week — network leverage through "
                "authentic, personal vouching at scale."
            ),
            network_scale="250 million weekly TV audience + cross-demographic cultural network spanning 40 years",
            buzz_mechanism=(
                "Vulnerability as currency: the willingness to share personal struggle "
                "publicly converted viewers into loyalists and guests into advocates. "
                "Authenticity was her amplification mechanism."
            ),
            face_value_signal="I amplify ideas and people whose work deserves a larger stage.",
            between_lines_signal=(
                "To be on Oprah's couch was to receive a character endorsement to "
                "250 million people. That implicit signal of her personal trust "
                "transformed every person she featured."
            ),
            outside_box_move=(
                "Applied talk-show intimacy techniques (vulnerability, personal story) "
                "to business leadership — creating a corporate culture (OWN, Harpo) "
                "built on principles that media and business schools said couldn't coexist."
            ),
            modern_translation=(
                "The platform builder who amplifies others to build their own network. "
                "A modern Oprah creates a podcast, newsletter, or event series whose "
                "primary value is the platform it gives to people they believe in."
            ),
            core_principle=(
                "Amplification through authenticity. The most powerful networking move "
                "is to give someone else the platform — your network grows when the "
                "people you elevate succeed and attribute it to you."
            ),
            network_quote="The biggest adventure you can take is to live the life of your dreams — and bring as many people as you can.",
        ),

        NetworkingGreat(
            great_id="reid_hoffman",
            name="Reid Hoffman",
            era="1967–present",
            primary_style=NetworkingStyle.DIGITAL,
            secondary_styles=(NetworkingStyle.COMMERCIAL, NetworkingStyle.INTELLECTUAL),
            signature_method=(
                "The PayPal Mafia architecture: created a post-exit culture where "
                "alumni actively helped each other found companies, make investments, "
                "and hire — the first modern professional alumni network with "
                "documented reciprocal obligations."
            ),
            network_scale="LinkedIn: 1 billion professional users. Personal network: 10,000+ direct relationships",
            buzz_mechanism=(
                "'The Alliance' and 'Masters of Scale' podcast: codified network theory "
                "into transferable frameworks that became the vocabulary of Silicon Valley — "
                "intellectual property as buzz mechanism."
            ),
            face_value_signal="I create the infrastructure for professional networks at every scale.",
            between_lines_signal=(
                "An introduction from Reid Hoffman signals that you passed a filter that "
                "10,000 other people didn't. The quality of his introductions "
                "is his most valuable network asset."
            ),
            outside_box_move=(
                "Applied game theory (mutual obligation, reputation signalling) "
                "to professional networking — turned social science into "
                "a systematic practice that scaled to a billion users."
            ),
            modern_translation=(
                "The network architect who designs reciprocal obligation systems. "
                "A modern Hoffman builds an alumni programme with documented norms "
                "of mutual support — making the network's rules explicit "
                "rather than hoping culture will sustain them."
            ),
            core_principle=(
                "Your network is a portfolio. Invest in relationships the way you invest "
                "in assets: diversify, invest early, maintain actively, "
                "and measure the quality of the relationship — not just its breadth."
            ),
            network_quote="The fastest way to change yourself is to hang out with people who are already the way you want to be.",
        ),

        NetworkingGreat(
            great_id="florence_nightingale_network",
            name="Florence Nightingale",
            era="1820–1910",
            primary_style=NetworkingStyle.INTELLECTUAL,
            secondary_styles=(NetworkingStyle.POLITICAL, NetworkingStyle.COMMUNITY),
            signature_method=(
                "Data as networking currency: shared evidence-backed reports with "
                "politicians, generals, and journalists simultaneously — "
                "making her case undeniable and her network indispensable to everyone "
                "who needed to claim credit for reform."
            ),
            network_scale="Reform network spanning British military command, Parliament, and the medical establishment",
            buzz_mechanism=(
                "The rose diagram (polar area chart): invented a new data visualisation "
                "format to make mortality statistics impossible to ignore — "
                "the data itself became the buzz mechanism."
            ),
            face_value_signal="I save lives through evidence-based care that reduces mortality from 42% to 2%.",
            between_lines_signal=(
                "Her willingness to go to Crimea when every institution said not to "
                "signalled a commitment that made every subsequent request unanswerable. "
                "'She went when no one else would' was her most powerful network signal."
            ),
            outside_box_move=(
                "Applied statistical methods (learned from Quetelet in Belgium) "
                "to nursing administration — turned mathematics into medical reform "
                "at a time when no nurse had ever used a spreadsheet."
            ),
            modern_translation=(
                "The data-first advocate who makes every argument with numbers. "
                "A modern Nightingale builds a network not through socialising "
                "but through sharing research that makes other people's cases "
                "for them — becoming indispensable through intellectual generosity."
            ),
            core_principle=(
                "Data as relationship currency. Share your research freely with "
                "everyone who might act on it. The person who gives evidence away "
                "gets credit when the evidence wins — and the evidence always wins eventually."
            ),
            network_quote="I attribute my success to this: I never gave or took any excuse.",
        ),

        NetworkingGreat(
            great_id="cicero",
            name="Marcus Tullius Cicero",
            era="106–43 BC",
            primary_style=NetworkingStyle.POLITICAL,
            secondary_styles=(NetworkingStyle.INTELLECTUAL, NetworkingStyle.CULTURAL),
            signature_method=(
                "The letter as political instrument: Cicero's 900+ surviving letters "
                "were deliberate, crafted, and designed to maintain relationships "
                "across the entire Roman political class simultaneously."
            ),
            network_scale="Political correspondence network spanning the entire Roman Senate and provincial governance",
            buzz_mechanism=(
                "Orations published as pamphlets immediately after delivery — "
                "the Philippics circulated through Rome within hours, "
                "turning a speech into a distributed political weapon."
            ),
            face_value_signal="I am the best lawyer and orator in Rome — and I will win your case.",
            between_lines_signal=(
                "Cicero's network was a form of insurance: to be known as his "
                "correspondent meant you had access to the most connected man in Rome. "
                "The signal of his friendship was a status asset."
            ),
            outside_box_move=(
                "Applied Greek rhetorical philosophy (imported from Athens) to "
                "Roman political practice — creating the first synthesis of "
                "Greek intellectual rigour with Roman practical power."
            ),
            modern_translation=(
                "The prolific communicator who turns every relationship into a written "
                "record of mutual understanding. A modern Cicero sends thoughtful "
                "emails that are worth reading, publishes opinions that are worth sharing, "
                "and is remembered for the quality of their written communication."
            ),
            core_principle=(
                "The written word endures when the voice is silent. "
                "A letter is a relationship that survives the conversation. "
                "Write more than you speak — and write as if your words will outlast you."
            ),
            network_quote="If you have a garden and a library, you have everything you need.",
        ),

        NetworkingGreat(
            great_id="jp_morgan",
            name="J.P. Morgan",
            era="1837–1913",
            primary_style=NetworkingStyle.COMMERCIAL,
            secondary_styles=(NetworkingStyle.POLITICAL, NetworkingStyle.CULTURAL),
            signature_method=(
                "The Morgan Library: used his art collection and physical space to "
                "create a neutral ground where financial adversaries could meet — "
                "hosted the 1907 Panic resolution in his library for 72 hours "
                "until a deal was struck."
            ),
            network_scale="Financial network that stabilised the US economy twice (1895, 1907) — effectively outranked the US Treasury",
            buzz_mechanism=(
                "Silence as buzz: Morgan rarely gave interviews or public statements, "
                "making every word he did say carry ten times the weight — "
                "scarcity of communication as amplification strategy."
            ),
            face_value_signal="I am the one person who can close any deal in American finance.",
            between_lines_signal=(
                "Morgan's physical presence in a room changed its dynamics. "
                "His arrival at a negotiation was a signal: this deal will now close, "
                "because Morgan is here and Morgan does not come to deals that don't close."
            ),
            outside_box_move=(
                "Used his art patronage network (Metropolitan Museum, library) "
                "to create trusted relationships with European nobility — "
                "crossed from finance to culture to unlock international capital flows."
            ),
            modern_translation=(
                "The convener who controls the room by controlling the venue. "
                "A modern Morgan creates the dinner, the event, or the retreat "
                "where the right conversations happen — and becomes indispensable "
                "by being the catalyst, not the loudest voice."
            ),
            core_principle=(
                "Be the room where it happens. The person who convenes the conversation "
                "shapes it. The most powerful network move is to create the forum "
                "where your peers gather — you become the centre by building the circle."
            ),
            network_quote="A man always has two reasons for what he does — a good reason and the real reason.",
        ),

        NetworkingGreat(
            great_id="sam_walton",
            name="Sam Walton",
            era="1918–1992",
            primary_style=NetworkingStyle.COMMERCIAL,
            secondary_styles=(NetworkingStyle.COMMUNITY, NetworkingStyle.POLITICAL),
            signature_method=(
                "The Saturday morning meeting: every week, 8am, all store managers — "
                "no exceptions, no agenda, raw intelligence from the front line "
                "flowing back to headquarters before competitors knew what was happening."
            ),
            network_scale="Supplier network of 60,000+ vendors; associate network of 1.5 million people",
            buzz_mechanism=(
                "Visiting stores unannounced and personally — the CEO who showed up "
                "at a Walmart in rural Arkansas at 7am to stock shelves with the team "
                "was a story every associate told their family. "
                "Visible humility as brand-building."
            ),
            face_value_signal="I deliver the lowest prices anywhere, every day — because I've eliminated every inefficiency.",
            between_lines_signal=(
                "Walton's interest in every associate's name and story signalled that "
                "no one was invisible in his organisation — a radical idea in retail "
                "that created extraordinary loyalty in a traditionally high-turnover industry."
            ),
            outside_box_move=(
                "Applied military intelligence-gathering principles (from WW2 service) "
                "to retail operations — creating a supply-chain information system "
                "that was a decade ahead of any competitor."
            ),
            modern_translation=(
                "The field intelligence architect who builds network advantage through "
                "front-line access. A modern Walton spends 20% of their time "
                "with customers and front-line staff — not in headquarters — "
                "and turns that intelligence into competitive decisions."
            ),
            core_principle=(
                "Go to where the truth is. The information that will save or destroy "
                "your business doesn't live in boardrooms — it lives where your "
                "customers and frontline staff interact. Go there more than anyone else."
            ),
            network_quote="Outstanding leaders go out of their way to boost the self-esteem of their personnel.",
        ),

        NetworkingGreat(
            great_id="keith_ferrazzi",
            name="Keith Ferrazzi",
            era="1968–present",
            primary_style=NetworkingStyle.COMMERCIAL,
            secondary_styles=(NetworkingStyle.INTELLECTUAL, NetworkingStyle.COMMUNITY),
            signature_method=(
                "Never Eat Alone: the radical act of turning every meal into a "
                "relationship-building opportunity — not as networking theatre "
                "but as a personal discipline of generous hospitality."
            ),
            network_scale="Personal network documented in 'Who's Got Your Back': 5,000+ curated relationships",
            buzz_mechanism=(
                "The book as network engine: 'Never Eat Alone' (2005) codified his "
                "approach and made his name the synonym for generous networking — "
                "intellectual property as the ultimate buzz mechanism."
            ),
            face_value_signal="I teach you to build a network that will catch you when you fall.",
            between_lines_signal=(
                "Ferrazzi's invitations were famous for their generosity — "
                "dinners where CEOs and NGO founders sat together, "
                "where the mix was intentional and the conversations surprising. "
                "Being invited to his table was itself a network signal."
            ),
            outside_box_move=(
                "Applied hospitality industry principles (from studying great hotels) "
                "to professional networking — treating every interaction as a service "
                "experience rather than a transaction."
            ),
            modern_translation=(
                "The generous host who designs connection experiences. "
                "A modern Ferrazzi hosts a monthly dinner where 6 people who've never "
                "met have 3 things in common — and watches the compound interest "
                "accumulate over years."
            ),
            core_principle=(
                "Givers gain. The fastest path to a great network is to stop "
                "thinking about what you need from it and start thinking about "
                "what every person in it needs from you. Give first, always."
            ),
            network_quote="Relationships are all there is. Everything in the universe only exists because it is in relationship to everything else.",
        ),

        NetworkingGreat(
            great_id="barack_obama",
            name="Barack Obama",
            era="1961–present",
            primary_style=NetworkingStyle.COMMUNITY,
            secondary_styles=(NetworkingStyle.POLITICAL, NetworkingStyle.CULTURAL),
            signature_method=(
                "Community organising as network architecture: taught by Saul Alinsky's "
                "one-on-one relationship-building method — met 10 people every day "
                "in Chicago for 3 years before running for anything."
            ),
            network_scale="Presidential network: 100M+ grassroots donors, 69M voters, 190 country diplomatic relationships",
            buzz_mechanism=(
                "'Yes We Can' — a movement that made every supporter a network node, "
                "distributing the buzz to millions of personal networks simultaneously. "
                "The first presidential campaign built on user-generated network propagation."
            ),
            face_value_signal="I organise communities around shared values to create change that outlasts any single leader.",
            between_lines_signal=(
                "Obama's ability to make a stadium of 80,000 feel like a one-on-one "
                "conversation was a network superpower — people who heard him felt "
                "personally connected, creating a distributed network of personal advocates."
            ),
            outside_box_move=(
                "Applied digital community tools (Facebook, email list) to political "
                "organising before any campaign had tried it — crossed from community "
                "organising to digital networking and invented the modern political network."
            ),
            modern_translation=(
                "The values-based movement builder. A modern Obama identifies the shared "
                "value that connects 10,000 people, creates the shared language for it, "
                "and builds the infrastructure that lets them find each other."
            ),
            core_principle=(
                "The most durable networks are built around shared values, not shared "
                "interests. Interests change. Values compound. Build your network "
                "around the principle, not the transaction."
            ),
            network_quote="Change will not come if we wait for some other person or some other time. We are the ones we've been waiting for.",
        ),

        NetworkingGreat(
            great_id="oprah_book_club",
            name="Rockefeller (John D.)",
            era="1839–1937",
            primary_style=NetworkingStyle.COMMERCIAL,
            secondary_styles=(NetworkingStyle.POLITICAL, NetworkingStyle.COMMUNITY),
            signature_method=(
                "The trust agreement: structured his network as a formal legal entity — "
                "the Standard Oil Trust — turning informal partnerships into "
                "binding network obligations that could survive any individual's departure."
            ),
            network_scale="Industrial network of 40 oil refineries, 100+ railroad contracts, and 3 government relationships",
            buzz_mechanism=(
                "Philanthropy before PR: founded University of Chicago (1890) and "
                "Rockefeller Institute (1901) before he was famous for philanthropy — "
                "creating legacy infrastructure that outlasted every controversy."
            ),
            face_value_signal="I eliminate market inefficiency and share the productivity gains with my supply chain.",
            between_lines_signal=(
                "Rockefeller's obsessive accounting (tracked every penny from age 16) "
                "signalled to partners that he would be the most reliable "
                "and precise partner they had ever worked with. "
                "Precision as trust signal."
            ),
            outside_box_move=(
                "Applied Baptist church tithing discipline (10% to charity from first income) "
                "to business networking — treating community investment as a "
                "non-negotiable operating cost rather than a PR strategy."
            ),
            modern_translation=(
                "The systematic ecosystem builder who formalises network relationships "
                "as structured obligations. A modern Rockefeller creates partner "
                "agreements, revenue-sharing structures, and formal alliances "
                "that make the network more durable than personal goodwill."
            ),
            core_principle=(
                "Formalise the reciprocal obligation. A handshake network dissolves "
                "when interests diverge. A structured network — clear obligations, "
                "shared upside, defined roles — survives market cycles."
            ),
            network_quote="The ability to deal with people is as purchasable a commodity as sugar or coffee. And I will pay more for that ability than for any other under the sun.",
        ),

        NetworkingGreat(
            great_id="peter_thiel",
            name="Peter Thiel",
            era="1967–present",
            primary_style=NetworkingStyle.COMMERCIAL,
            secondary_styles=(NetworkingStyle.INTELLECTUAL, NetworkingStyle.DIGITAL),
            signature_method=(
                "The PayPal Mafia alumni strategy: invested in every founder who left "
                "PayPal before they had proven themselves elsewhere — creating "
                "pre-validated loyalty through investment before track record."
            ),
            network_scale="Portfolio network: 100+ companies; PayPal Mafia: 22 companies valued at >$1B including LinkedIn, YouTube, Yelp",
            buzz_mechanism=(
                "'Zero to One' (2014): a book that functioned as a global recruiting "
                "pitch — codifying contrarian thinking as intellectual identity "
                "and making every reader feel they'd passed a filter."
            ),
            face_value_signal="I back founders who build monopolies in markets no one else has defined yet.",
            between_lines_signal=(
                "Receiving a Thiel Fellowship or Founders Fund investment "
                "signalled membership in a network whose standards were unusually high — "
                "the filter itself created the value of passing it."
            ),
            outside_box_move=(
                "Applied Girardian mimetic theory (French literary philosophy) "
                "to business strategy — crossed from academic philosophy to "
                "venture capital in a way that no other investor attempted."
            ),
            modern_translation=(
                "The conviction investor who backs people before the market does. "
                "A modern Thiel writes the recommendation letter before the person "
                "needs it, makes the introduction before it's asked for, "
                "and backs the contrarian view before consensus validates it."
            ),
            core_principle=(
                "Invest in people before the market discovers them. The most "
                "valuable network move is the early bet — backing someone when "
                "it costs you credibility, not when it confirms it."
            ),
            network_quote="Competition is for losers — the best networks are built in markets others haven't defined.",
        ),

        NetworkingGreat(
            great_id="confucius_network",
            name="Confucius",
            era="551–479 BC",
            primary_style=NetworkingStyle.INTELLECTUAL,
            secondary_styles=(NetworkingStyle.POLITICAL, NetworkingStyle.CULTURAL),
            signature_method=(
                "Itinerant teaching: travelled between states for 14 years with a cohort "
                "of 72 devoted students — turning teaching into a mobile network "
                "that penetrated every political court in China."
            ),
            network_scale="Intellectual network spanning 12 Chinese states; 3,000 students documented",
            buzz_mechanism=(
                "The Analects: his students' collected records of his conversations — "
                "the world's first posthumously published network manifesto, "
                "still shaping 1.5 billion people's values 2,500 years later."
            ),
            face_value_signal="I teach the principles by which a ruler governs a prosperous and harmonious state.",
            between_lines_signal=(
                "To study under Confucius was to signal to every subsequent employer "
                "that you had been shaped by the most rigorous moral and intellectual "
                "tradition available. His students were pre-qualified by their teacher's reputation."
            ),
            outside_box_move=(
                "Applied family relationship ethics (filial piety, reciprocity) "
                "to governance and commerce — crossed from family structure to "
                "state organisation in a framework that unified the two."
            ),
            modern_translation=(
                "The teacher whose students become your network. "
                "A modern Confucius invests more in 12 deep mentoring relationships "
                "than in 1,200 LinkedIn connections — and watches the alumni "
                "network compound across decades."
            ),
            core_principle=(
                "Your network is your students. The people you have genuinely "
                "taught — not just employed, not just met, but truly developed — "
                "will serve your network for 30 years longer than any peer relationship."
            ),
            network_quote="Tell me and I forget. Teach me and I remember. Involve me and I learn — and I will remember you forever.",
        ),

        NetworkingGreat(
            great_id="socrates_network",
            name="Socrates",
            era="470–399 BC",
            primary_style=NetworkingStyle.INTELLECTUAL,
            secondary_styles=(NetworkingStyle.CULTURAL, NetworkingStyle.COMMUNITY),
            signature_method=(
                "Elenchus (Socratic method): built his network by making every person "
                "feel they had discovered a truth for themselves in conversation with him — "
                "the most psychologically compelling network-building technique ever devised."
            ),
            network_scale="Network of 2,000+ Athenian citizens including every major political figure of his era",
            buzz_mechanism=(
                "Trial and death as ultimate buzz: Socrates refused to stop his teaching "
                "even when facing execution — the most extreme demonstration of conviction "
                "as personal brand in history, generating network loyalty across 2,500 years."
            ),
            face_value_signal="I do not teach — I help you discover what you already know.",
            between_lines_signal=(
                "A conversation with Socrates left you feeling both smaller "
                "(you realised you knew less than you thought) and larger "
                "(you discovered a truth you didn't know you held). "
                "That paradox made him unforgettable."
            ),
            outside_box_move=(
                "Applied midwifery metaphor to philosophy — crossed from biology "
                "to epistemology to create the concept of intellectual dialogue "
                "as a process of birth rather than instruction."
            ),
            modern_translation=(
                "The coach who builds a network through questions, not answers. "
                "A modern Socrates never pitches — they ask questions so incisive "
                "that the other person arrives at the conclusion themselves "
                "and attributes the insight to the conversation."
            ),
            core_principle=(
                "Ask better questions than you give answers. The person who helps "
                "someone discover their own truth creates a more durable bond "
                "than the person who delivers wisdom."
            ),
            network_quote="I cannot teach anybody anything. I can only make them think.",
        ),
    ]
    return {g.great_id: g for g in greats}


NETWORKING_GREATS: Dict[str, NetworkingGreat] = _build_networking_greats()


# ---------------------------------------------------------------------------
# Buzz Campaign Templates
# ---------------------------------------------------------------------------

BUZZ_CAMPAIGN_TEMPLATES: List[BuzzCampaign] = [

    BuzzCampaign(
        campaign_id="buzz_wom_01",
        buzz_type=BuzzType.WORD_OF_MOUTH,
        strategy_name="The Result Story Engine",
        primary_vehicle="Structured client success stories shared by the client, not you",
        trigger_event="Client achieves measurable outcome within 90 days",
        propagation_mechanism=(
            "Client tells 3 peers in adjacent roles → each peer becomes a warm lead "
            "→ you introduce them to each other → creates a self-reinforcing reference community"
        ),
        amplification_tactics=(
            "Write the client's success story for them — they just approve it",
            "Feature them at your next event or webinar as the protagonist",
            "Introduce them to two people who would benefit from knowing them",
        ),
        measurement_metric="Referral-sourced pipeline as % of total new pipeline",
        timeline_days=90,
        reach_multiplier=8.0,
        great_exemplar="Warren Buffett — every Berkshire annual letter made clients do the marketing for him",
    ),

    BuzzCampaign(
        campaign_id="buzz_tl_01",
        buzz_type=BuzzType.THOUGHT_LEADERSHIP,
        strategy_name="The Weekly Insight Series",
        primary_vehicle="LinkedIn post or email newsletter — one insight, 300 words, every week",
        trigger_event="Identify 3 counterintuitive insights from your work this month",
        propagation_mechanism=(
            "Consistent, useful content builds an audience who shares it with their peers "
            "→ creates inbound network growth without cold outreach"
        ),
        amplification_tactics=(
            "Tag 2 people who would find it useful in each post",
            "Reply to every comment within 24 hours",
            "Repurpose top posts into longer articles or short videos quarterly",
        ),
        measurement_metric="Follower growth rate and inbound connection requests per post",
        timeline_days=180,
        reach_multiplier=15.0,
        great_exemplar="Benjamin Franklin — Poor Richard's Almanack built his reputation before he needed it",
    ),

    BuzzCampaign(
        campaign_id="buzz_sp_01",
        buzz_type=BuzzType.SOCIAL_PROOF,
        strategy_name="The Reference Architecture",
        primary_vehicle="Curated set of reference customers by role and vertical",
        trigger_event="3+ successful outcomes achieved in a target segment",
        propagation_mechanism=(
            "Reference customer community → shared Slack group → mutual referrals between members → "
            "creates a self-sustaining endorsement ecosystem"
        ),
        amplification_tactics=(
            "Host a quarterly reference customer dinner where members meet each other",
            "Co-author a case study with your 3 best reference customers",
            "Create a 'customer advisory board' with the top 5 — signals confidence to prospects",
        ),
        measurement_metric="Win rate when a reference call is included in the sales process",
        timeline_days=120,
        reach_multiplier=6.0,
        great_exemplar="Andrew Carnegie — philanthropy created visible proof of character that preceded him",
    ),

    BuzzCampaign(
        campaign_id="buzz_demo_01",
        buzz_type=BuzzType.DEMONSTRATION,
        strategy_name="The Live Result Demonstration",
        primary_vehicle="Public demonstration of capability — workshop, hackathon, or before/after showcase",
        trigger_event="Prospect has a specific problem you can solve visibly in under 2 hours",
        propagation_mechanism=(
            "People who watch you solve a real problem in real time become advocates "
            "who describe what they saw — demonstration is more credible than any testimonial"
        ),
        amplification_tactics=(
            "Record the demonstration and share with permission",
            "Invite 3 prospects to observe (not participate) while you work with a client",
            "Publish the methodology behind the demonstration as a blog post within 48 hours",
        ),
        measurement_metric="Attendance-to-pipeline conversion rate from demonstration events",
        timeline_days=30,
        reach_multiplier=12.0,
        great_exemplar="Florence Nightingale — reduced mortality from 42% to 2% before presenting any theory",
    ),

    BuzzCampaign(
        campaign_id="buzz_viral_01",
        buzz_type=BuzzType.VIRAL_LOOP,
        strategy_name="The Network Connector Loop",
        primary_vehicle="Structured introduction programme — you make 2 introductions per week",
        trigger_event="Every meaningful conversation prompts the question: who else should meet this person?",
        propagation_mechanism=(
            "Every introduction you make creates 2 people who feel your network value → "
            "they recommend you to others → referral compounds geometrically"
        ),
        amplification_tactics=(
            "Track every introduction you make and follow up 30 days later",
            "Host a quarterly 'serendipity dinner' — 8 people who've never met with 3 things in common",
            "Create a monthly 'connection digest' — who in your network is looking for what",
        ),
        measurement_metric="Introductions made per month and percentage that result in ongoing relationships",
        timeline_days=90,
        reach_multiplier=25.0,
        great_exemplar="Keith Ferrazzi — Never Eat Alone built a 5,000-person network through structured hospitality",
    ),
]


# ---------------------------------------------------------------------------
# BuzzEngine
# ---------------------------------------------------------------------------

class BuzzEngine:
    """
    Generates and prioritises buzz campaigns for a given networking context.
    """

    def get_campaigns(
        self,
        buzz_types: Optional[List[BuzzType]] = None,
        max_campaigns: int = 3,
    ) -> List[BuzzCampaign]:
        """Return campaigns, optionally filtered by buzz type."""
        campaigns = BUZZ_CAMPAIGN_TEMPLATES
        if buzz_types:
            campaigns = [c for c in campaigns if c.buzz_type in buzz_types]
        return sorted(campaigns, key=lambda c: c.reach_multiplier, reverse=True)[:max_campaigns]

    def recommend_for_stage(self, network_iq: float) -> List[BuzzCampaign]:
        """
        Recommend campaigns appropriate for the current network development stage.

        Early stage → demonstration + word of mouth (trust builders)
        Growing → thought leadership + social proof (scale)
        Elite → viral loops (compound existing network)
        """
        if network_iq < 0.60:
            return self.get_campaigns([BuzzType.DEMONSTRATION, BuzzType.WORD_OF_MOUTH])
        if network_iq < 0.80:
            return self.get_campaigns([BuzzType.THOUGHT_LEADERSHIP, BuzzType.SOCIAL_PROOF])
        return self.get_campaigns([BuzzType.VIRAL_LOOP, BuzzType.THOUGHT_LEADERSHIP])

    def all_campaigns(self) -> List[BuzzCampaign]:
        return BUZZ_CAMPAIGN_TEMPLATES


# ---------------------------------------------------------------------------
# CapabilityMapper
# ---------------------------------------------------------------------------

class CapabilityMapper:
    """
    Generates three-layer capability signals for an agent or professional.

    Face Value + Between Lines + Outside Box = the complete capability picture.
    """

    # Generic capability signals by layer type
    _FACE_VALUE_TEMPLATES = [
        "I help {target} achieve {outcome} in {timeframe}.",
        "My clients move from {current_state} to {desired_state}.",
        "I have delivered {result} for {n} {client_type} clients.",
    ]

    _BETWEEN_LINES_SIGNALS = [
        "The quality of my questions reveals how deeply I understand your industry",
        "The people I introduce you to signal the calibre of relationships I maintain",
        "The way I prepare for this meeting demonstrates my standard of professionalism",
        "My network's willingness to be references demonstrates the depth of my client relationships",
        "The specificity of my case studies signals that I solve problems, not just sell products",
        "My response time and follow-through demonstrate the reliability I bring to every engagement",
        "The clients I work with reflect the trust my network places in my judgment",
    ]

    _OUTSIDE_BOX_SIGNALS = [
        "Military strategy principles applied to competitive market analysis",
        "Behavioural economics frameworks applied to sales team incentive design",
        "Systems thinking (from engineering) applied to revenue operations architecture",
        "Narrative structure (from screenwriting) applied to sales discovery questioning",
        "Athletic coaching periodisation applied to sales performance management",
        "Data visualisation (from Florence Nightingale's rose diagrams) applied to executive reporting",
        "Community organising (Obama playbook) applied to customer success community building",
        "Game theory applied to pricing and negotiation strategy",
        "Anthropological observation techniques applied to customer empathy research",
    ]

    def generate_capability_signals(
        self,
        subject_id: str,
        role_context: str = "professional",
        primary_strength: str = "expertise",
    ) -> CapabilitySignalSet:
        """
        Generate a full three-layer capability signal set.

        Parameters
        ----------
        subject_id:      Identifier for the subject.
        role_context:    Brief description of the professional context.
        primary_strength: The subject's primary area of demonstrated strength.
        """
        # Face value: 3 explicit claims
        face_value = [
            f"I help organisations transform {primary_strength} into measurable business outcomes.",
            f"My clients typically see 2–5× improvement in {primary_strength}-related metrics within 90 days.",
            f"I have a repeatable methodology for {role_context} that has worked across multiple industries.",
        ]

        # Between lines: 4 implicit signals (select most relevant)
        between_lines = list(self._BETWEEN_LINES_SIGNALS[:4])

        # Outside box: 3 unexpected cross-domain applications
        outside_box = list(self._OUTSIDE_BOX_SIGNALS[:3])

        return CapabilitySignalSet(
            subject_id=subject_id,
            face_value=face_value,
            between_lines=between_lines,
            outside_box=outside_box,
        )

    def add_archetype_signals(
        self,
        signal_set: CapabilitySignalSet,
        archetype: NetworkingGreat,
    ) -> CapabilitySignalSet:
        """Enrich a capability signal set with the archetype's specific signals."""
        enriched_face    = signal_set.face_value + [archetype.face_value_signal]
        enriched_between = signal_set.between_lines + [archetype.between_lines_signal]
        enriched_outside = signal_set.outside_box + [archetype.outside_box_move]

        return CapabilitySignalSet(
            subject_id=signal_set.subject_id,
            face_value=enriched_face,
            between_lines=enriched_between,
            outside_box=enriched_outside,
            archetype_match=archetype,
        )


# ---------------------------------------------------------------------------
# NetworkingGreatLibrary
# ---------------------------------------------------------------------------

class NetworkingGreatLibrary:
    """Access and search the networking greats corpus."""

    def get_all(self) -> Dict[str, NetworkingGreat]:
        return NETWORKING_GREATS

    def get_by_style(self, style: NetworkingStyle) -> List[NetworkingGreat]:
        return [
            g for g in NETWORKING_GREATS.values()
            if g.primary_style == style or style in g.secondary_styles
        ]

    def find_archetype_for_style(self, style: NetworkingStyle) -> Optional[NetworkingGreat]:
        """Return the great with the highest networking IQ for the given primary style."""
        candidates = [g for g in NETWORKING_GREATS.values() if g.primary_style == style]
        if not candidates:
            return None
        return max(candidates, key=lambda g: g.networking_iq_score)

    def top_n(self, n: int = 5) -> List[NetworkingGreat]:
        return sorted(
            NETWORKING_GREATS.values(),
            key=lambda g: g.networking_iq_score,
            reverse=True,
        )[:n]

    def find_by_principle(self, keyword: str) -> List[NetworkingGreat]:
        """Find greats whose core_principle mentions the keyword."""
        kw = keyword.lower()
        return [g for g in NETWORKING_GREATS.values() if kw in g.core_principle.lower()]


# ---------------------------------------------------------------------------
# NetworkIntelligenceEngine
# ---------------------------------------------------------------------------

class NetworkIntelligenceEngine:
    """
    Generates comprehensive network intelligence reports.

    Combines archetype matching, buzz campaign selection, capability signal
    generation, and 90-day action planning into a single unified output.
    """

    def __init__(self) -> None:
        self._library = NetworkingGreatLibrary()
        self._buzz    = BuzzEngine()
        self._mapper  = CapabilityMapper()

    def build_report(
        self,
        agent_id: str,
        networking_style: NetworkingStyle,
        current_network_iq: float = 0.65,
        primary_strength: str = "client outcomes",
        role_context: str = "professional",
    ) -> NetworkIntelligenceReport:
        """Generate a full network intelligence report for an agent."""

        # Find archetype
        archetype = self._library.find_archetype_for_style(networking_style)
        if archetype is None:
            archetype = list(NETWORKING_GREATS.values())[0]

        # Generate capability signals enriched with archetype
        base_signals = self._mapper.generate_capability_signals(
            subject_id=agent_id,
            role_context=role_context,
            primary_strength=primary_strength,
        )
        enriched_signals = self._mapper.add_archetype_signals(base_signals, archetype)

        # Select buzz campaigns
        campaigns = self._buzz.recommend_for_stage(current_network_iq)

        # Identify gaps
        gaps = self._identify_gaps(networking_style, current_network_iq)

        # Quick wins
        quick_wins = self._quick_wins(networking_style, archetype)

        # 90-day plan
        plan = self._build_ninety_day_plan(networking_style, archetype, campaigns)

        return NetworkIntelligenceReport(
            agent_id=agent_id,
            networking_style=networking_style,
            archetype_match=archetype,
            capability_signals=enriched_signals,
            buzz_campaigns=campaigns,
            network_gaps=gaps,
            quick_wins=quick_wins,
            ninety_day_plan=plan,
            network_iq=current_network_iq,
        )

    def assess_networking_iq(self, behavioral_signals: List[str]) -> float:
        """
        Estimate a networking IQ score (0–1) from behavioral signals.

        Higher score = more systematic, multi-style, and consistent networking.
        """
        text = " ".join(s.lower() for s in behavioral_signals)
        indicators = [
            "introduced", "referred", "connected", "followed up", "sent a note",
            "wrote", "published", "presented", "hosted", "invited",
            "thanked", "credited", "remembered", "consistent", "weekly",
        ]
        hits = sum(1 for ind in indicators if ind in text)
        return min(1.0, round(0.50 + hits * 0.03, 4))

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _identify_gaps(self, style: NetworkingStyle, iq: float) -> List[str]:
        gaps = []
        if iq < 0.70:
            gaps.append("Insufficient follow-up discipline — relationships initiated but not maintained")
        if iq < 0.65:
            gaps.append("No systematic documentation of network relationships")
        if style != NetworkingStyle.DIGITAL:
            gaps.append("Digital presence under-leveraged — LinkedIn and thought leadership underutilised")
        if style != NetworkingStyle.INTELLECTUAL:
            gaps.append("No structured thought leadership platform — insights not being captured or shared")
        if style not in (NetworkingStyle.COMMUNITY, NetworkingStyle.CULTURAL):
            gaps.append("Community/cause network absent — no network built around shared values")
        return gaps[:3]

    def _quick_wins(self, style: NetworkingStyle, archetype: NetworkingGreat) -> List[str]:
        return [
            f"Make 2 introductions today using {archetype.name}'s signature method: "
            f"'{archetype.signature_method[:80]}'",
            "Send 3 personal, specific 'thought of you' messages this week with a useful resource attached",
            f"Publish one insight from your work this week using {archetype.name}'s buzz mechanism approach",
            "Identify the 5 people in your network who would benefit most from knowing each other — "
            "make those introductions this month",
        ][:3]

    def _build_ninety_day_plan(
        self,
        style: NetworkingStyle,
        archetype: NetworkingGreat,
        campaigns: List[BuzzCampaign],
    ) -> List[Dict[str, Any]]:
        plan = []

        # Month 1: Foundation
        plan.append({
            "month": 1,
            "theme": "Foundation — build the system",
            "focus": f"Adopt {archetype.name}'s signature method as your weekly discipline",
            "actions": [
                "Document your current network in a CRM or spreadsheet — 50+ key contacts",
                f"Implement the signature method: {archetype.signature_method[:100]}",
                "Start the first buzz campaign: " + (campaigns[0].strategy_name if campaigns else "thought leadership series"),
            ],
            "success_metric": "50 contacts documented + 2 introductions made per week",
        })

        # Month 2: Activation
        plan.append({
            "month": 2,
            "theme": "Activation — put the network in motion",
            "focus": "Deepen 10 key relationships and start generating referrals",
            "actions": [
                "Host a 'serendipity' dinner or virtual session — 6–8 people who should know each other",
                "Publish 4 pieces of useful content (one per week)",
                "Ask 3 trusted contacts for 2 specific introductions each",
            ],
            "success_metric": "First referral received from network + 4 pieces of content published",
        })

        # Month 3: Compounding
        plan.append({
            "month": 3,
            "theme": "Compounding — make the network self-sustaining",
            "focus": f"Apply {archetype.name}'s core principle: '{archetype.core_principle[:100]}'",
            "actions": [
                "Launch the second buzz campaign from the recommendation list",
                "Create a monthly 'value delivery' ritual for your top 20 network contacts",
                "Identify 5 'network nodes' — people who know everyone you want to know — and invest in them specifically",
            ],
            "success_metric": "Network generating ≥2 warm introductions per week without prompting",
        })

        return plan


# ---------------------------------------------------------------------------
# NetworkingMasteryEngine — top-level façade
# ---------------------------------------------------------------------------

class NetworkingMasteryEngine:
    """
    Top-level façade for the Networking Mastery Engine.

    Combines network intelligence, buzz creation, capability signalling,
    and historical archetype wisdom into a unified system.

    Usage::

        engine = NetworkingMasteryEngine()

        report = engine.analyse(
            agent_id="alex_reeves",
            networking_style=NetworkingStyle.COMMERCIAL,
            current_network_iq=0.65,
            primary_strength="enterprise sales",
        )

        print(report.archetype_match.name)
        for win in report.quick_wins:
            print(f"  → {win}")
    """

    def __init__(self) -> None:
        self._intelligence = NetworkIntelligenceEngine()
        self._library      = NetworkingGreatLibrary()
        self._buzz         = BuzzEngine()
        self._mapper       = CapabilityMapper()
        self._lock         = threading.Lock()
        self._history:     List[NetworkIntelligenceReport] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyse(
        self,
        agent_id: str,
        networking_style: NetworkingStyle,
        current_network_iq: float = 0.65,
        primary_strength: str = "client outcomes",
        role_context: str = "professional",
    ) -> NetworkIntelligenceReport:
        """Generate a full network intelligence report."""
        report = self._intelligence.build_report(
            agent_id=agent_id,
            networking_style=networking_style,
            current_network_iq=current_network_iq,
            primary_strength=primary_strength,
            role_context=role_context,
        )
        with self._lock:
            if len(self._history) >= 200:
                del self._history[:20]
            self._history.append(report)
        return report

    def describe_great(self, great_id: str) -> Optional[Dict[str, Any]]:
        """Return the full profile of a networking great by ID."""
        great = NETWORKING_GREATS.get(great_id)
        return great.to_dict() if great else None

    def get_buzz_campaigns(
        self,
        buzz_types: Optional[List[BuzzType]] = None,
    ) -> List[BuzzCampaign]:
        """Return recommended buzz campaigns, optionally filtered by type."""
        return self._buzz.get_campaigns(buzz_types=buzz_types)

    def get_capability_signals(
        self,
        subject_id: str,
        role_context: str = "professional",
        primary_strength: str = "expertise",
    ) -> CapabilitySignalSet:
        """Generate a three-layer capability signal set."""
        return self._mapper.generate_capability_signals(
            subject_id=subject_id,
            role_context=role_context,
            primary_strength=primary_strength,
        )

    def all_greats(self) -> Dict[str, NetworkingGreat]:
        """Return the full networking greats corpus."""
        return NETWORKING_GREATS

    def all_buzz_campaigns(self) -> List[BuzzCampaign]:
        """Return all buzz campaign templates."""
        return BUZZ_CAMPAIGN_TEMPLATES

    def assess_networking_iq(self, behavioral_signals: List[str]) -> float:
        """Estimate networking IQ from behavioral evidence."""
        return self._intelligence.assess_networking_iq(behavioral_signals)

    def recent_analyses(self, n: int = 10) -> List[NetworkIntelligenceReport]:
        """Return the *n* most recent intelligence reports."""
        with self._lock:
            return self._history[-n:]
