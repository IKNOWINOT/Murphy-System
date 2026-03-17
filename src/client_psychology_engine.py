"""
Client Psychology Engine — Murphy System
==========================================

Modernised client reading, demographic intelligence, pain-point detection,
and income-scaling playbooks for Murphy System agents and sales personas.

Embeds the most current 2020s sales science alongside timeless psychological
principles to enable agents to:

  1. Identify and surface client pain points (latent → critical)
  2. Adapt communication style to generational and cultural demographics
  3. Select the right modern sales framework for the situation
  4. Execute income-scaling strategies targeting 2× → 5× revenue uplift
  5. Read and respond to buying psychology in real time

Modern Frameworks Implemented
------------------------------
  MEDDIC / MEDDICC   — Enterprise qualification
  Challenger Sale    — Teach · Tailor · Take Control
  GAP Selling        — Current State → Desired State → Consequence of Inaction
  SPIN Modern        — Situation → Problem → Implication → Need-Payoff
  SNAP Selling       — Simple · iNvaluable · Aligned · Priority
  Command of Sale    — Connect · Clarify · Contrast · Convince · Close
  Jobs-to-be-Done    — Functional + Emotional + Social job layers
  Consultative       — Relationship-first, trust-led discovery

Design Label: CPE-001 — Client Psychology Engine
Owner:        Platform Engineering / Agent Intelligence
License:      BSL 1.1

Copyright © 2020 Inoni Limited Liability Company
Creator:      Corey Post
"""

from __future__ import annotations

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

class GenerationCohort(str, Enum):
    """Generational cohorts with distinct communication and buying patterns."""
    GEN_Z      = "gen_z"       # 1997–2012 — digital native, values-first
    MILLENNIAL = "millennial"  # 1981–1996 — digital immigrant, outcome-focused
    GEN_X      = "gen_x"       # 1965–1980 — pragmatic skeptic, ROI-driven
    BOOMER     = "boomer"      # 1946–1964 — relationship-first, stability-seeking
    SILENT     = "silent"      # 1928–1945 — institutional trust, formality-required


class IndustryVertical(str, Enum):
    TECHNOLOGY            = "technology"
    FINANCE               = "finance"
    HEALTHCARE            = "healthcare"
    MANUFACTURING         = "manufacturing"
    REAL_ESTATE           = "real_estate"
    RETAIL                = "retail"
    PROFESSIONAL_SERVICES = "professional_services"
    CONSTRUCTION          = "construction"
    ENERGY                = "energy"
    EDUCATION             = "education"
    GOVERNMENT            = "government"
    NONPROFIT             = "nonprofit"


class DecisionMakerRole(str, Enum):
    ECONOMIC_BUYER  = "economic_buyer"
    TECHNICAL_BUYER = "technical_buyer"
    CHAMPION        = "champion"
    END_USER        = "end_user"
    COACH           = "coach"
    BLOCKER         = "blocker"


class CommunicationStyle(str, Enum):
    DATA_DRIVEN       = "data_driven"
    STORY_DRIVEN      = "story_driven"
    RELATIONSHIP_FIRST = "relationship_first"
    RESULTS_FIRST     = "results_first"
    PROCESS_FIRST     = "process_first"
    VISION_FIRST      = "vision_first"


class PainCategory(str, Enum):
    REVENUE_GROWTH        = "revenue_growth"
    COST_REDUCTION        = "cost_reduction"
    RISK_MITIGATION       = "risk_mitigation"
    EFFICIENCY            = "efficiency"
    TALENT_RETENTION      = "talent_retention"
    COMPLIANCE            = "compliance"
    COMPETITIVE_THREAT    = "competitive_threat"
    DIGITAL_TRANSFORMATION = "digital_transformation"
    INNOVATION_PRESSURE   = "innovation_pressure"


class PainIntensity(str, Enum):
    LATENT       = "latent"        # They don't know they have it yet
    ACKNOWLEDGED = "acknowledged"  # They know but haven't prioritised it
    ACTIVE       = "active"        # They're actively feeling it
    CRITICAL     = "critical"      # It's existential; keeping them up at night

    @property
    def urgency_score(self) -> float:
        return {"latent": 0.25, "acknowledged": 0.50, "active": 0.75, "critical": 1.00}[self.value]


class SalesFramework(str, Enum):
    MEDDIC          = "meddic"
    CHALLENGER      = "challenger"
    GAP_SELLING     = "gap_selling"
    SPIN_MODERN     = "spin_modern"
    SNAP_SELLING    = "snap_selling"
    COMMAND_OF_SALE = "command_of_sale"
    JBTD            = "jbtd"
    CONSULTATIVE    = "consultative"


class IncomeMultiplier(str, Enum):
    TWO_X   = "2x"
    THREE_X = "3x"
    FOUR_X  = "4x"
    FIVE_X  = "5x"

    @property
    def numeric(self) -> int:
        return int(self.value[0])


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class DemographicProfile:
    """Who the client is — drives all communication adaptation."""
    generation:             GenerationCohort
    industry:               IndustryVertical
    role:                   DecisionMakerRole
    communication_style:    CommunicationStyle = CommunicationStyle.RESULTS_FIRST
    tech_savviness:         float = 0.70   # 0=technophobe, 1=early adopter
    formality_preference:   float = 0.50   # 0=casual, 1=very formal
    relationship_dependency: float = 0.50  # 0=transactional, 1=relationship-first
    decision_speed:         float = 0.50   # 0=slow/deliberate, 1=fast/intuitive

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generation":             self.generation.value,
            "industry":               self.industry.value,
            "role":                   self.role.value,
            "communication_style":    self.communication_style.value,
            "tech_savviness":         self.tech_savviness,
            "formality_preference":   self.formality_preference,
            "relationship_dependency": self.relationship_dependency,
            "decision_speed":         self.decision_speed,
        }


@dataclass(frozen=True)
class PainSignal:
    """A detected pain indicator from client conversation."""
    category:                  PainCategory
    intensity:                 PainIntensity
    trigger_phrase:            str
    evidence_statement:        str
    consequence_if_unaddressed: str
    recommended_probe:         str

    @property
    def urgency_score(self) -> float:
        return self.intensity.urgency_score

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category":                  self.category.value,
            "intensity":                 self.intensity.value,
            "urgency_score":             self.urgency_score,
            "trigger_phrase":            self.trigger_phrase,
            "evidence_statement":        self.evidence_statement,
            "consequence_if_unaddressed": self.consequence_if_unaddressed,
            "recommended_probe":         self.recommended_probe,
        }


@dataclass(frozen=True)
class LanguagePack:
    """Generation-specific vocabulary and communication patterns."""
    generation:       GenerationCohort
    power_words:      Tuple[str, ...]    # words that resonate
    avoid_words:      Tuple[str, ...]    # words that create friction
    preferred_format: str                # how to structure communications
    trust_signals:    Tuple[str, ...]    # what builds credibility
    value_anchors:    Tuple[str, ...]    # what they care about most
    opening_hooks:    Tuple[str, ...]    # conversation starters that land
    modern_lingo:     Tuple[str, ...]    # 2020s-era power phrases for this cohort

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generation":       self.generation.value,
            "power_words":      list(self.power_words),
            "avoid_words":      list(self.avoid_words),
            "preferred_format": self.preferred_format,
            "trust_signals":    list(self.trust_signals),
            "value_anchors":    list(self.value_anchors),
            "opening_hooks":    list(self.opening_hooks),
            "modern_lingo":     list(self.modern_lingo),
        }


@dataclass(frozen=True)
class IncomeScalingPlaybook:
    """Strategy for achieving a specific revenue multiplier."""
    multiplier:        IncomeMultiplier
    strategy_name:     str
    thesis:            str
    preconditions:     Tuple[str, ...]
    primary_tactics:   Tuple[str, ...]
    agent_behaviors:   Tuple[str, ...]
    risk_factors:      Tuple[str, ...]
    success_metrics:   Tuple[str, ...]
    timeline_weeks:    int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "multiplier":      self.multiplier.value,
            "strategy_name":   self.strategy_name,
            "thesis":          self.thesis,
            "preconditions":   list(self.preconditions),
            "primary_tactics": list(self.primary_tactics),
            "agent_behaviors": list(self.agent_behaviors),
            "risk_factors":    list(self.risk_factors),
            "success_metrics": list(self.success_metrics),
            "timeline_weeks":  self.timeline_weeks,
        }


@dataclass(frozen=True)
class FrameworkGuide:
    """Complete operating guide for one sales framework."""
    framework:          SalesFramework
    full_name:          str
    best_for:           Tuple[str, ...]
    opening_move:       str
    key_questions:      Tuple[str, ...]
    closing_technique:  str
    objection_handler:  str
    modern_twist:       str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "framework":         self.framework.value,
            "full_name":         self.full_name,
            "best_for":          list(self.best_for),
            "opening_move":      self.opening_move,
            "key_questions":     list(self.key_questions),
            "closing_technique": self.closing_technique,
            "objection_handler": self.objection_handler,
            "modern_twist":      self.modern_twist,
        }


@dataclass
class ClientReadingReport:
    """Full psychological reading of a client — the agent's compass."""
    client_id:              str
    demographic_profile:    DemographicProfile
    detected_pain_signals:  List[PainSignal]
    primary_pain:           Optional[PainSignal]
    recommended_framework:  SalesFramework
    income_scaling_lever:   IncomeMultiplier
    language_pack:          LanguagePack
    opening_gambit:         str
    key_discovery_questions: List[str]
    objection_preemptions:  List[str]
    closing_approach:       str
    urgency_narrative:      str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "client_id":              self.client_id,
            "demographic_profile":    self.demographic_profile.to_dict(),
            "detected_pain_signals":  [p.to_dict() for p in self.detected_pain_signals],
            "primary_pain":           self.primary_pain.to_dict() if self.primary_pain else None,
            "recommended_framework":  self.recommended_framework.value,
            "income_scaling_lever":   self.income_scaling_lever.value,
            "opening_gambit":         self.opening_gambit,
            "key_discovery_questions": self.key_discovery_questions,
            "objection_preemptions":  self.objection_preemptions,
            "closing_approach":       self.closing_approach,
            "urgency_narrative":      self.urgency_narrative,
        }


# ---------------------------------------------------------------------------
# Language Pack Library — generation-native vocabulary
# ---------------------------------------------------------------------------

LANGUAGE_PACKS: Dict[GenerationCohort, LanguagePack] = {

    GenerationCohort.GEN_Z: LanguagePack(
        generation=GenerationCohort.GEN_Z,
        power_words=(
            "authentic", "transparent", "impact", "values-aligned", "real",
            "no-fluff", "measurable", "community", "mission-driven", "inclusive",
        ),
        avoid_words=(
            "synergy", "leverage", "paradigm shift", "circle back", "boil the ocean",
            "pick your brain", "move the needle", "touch base", "bandwidth",
        ),
        preferred_format=(
            "TL;DR first → 3 bullet points → one clear ask. "
            "Mobile-optimised, async-friendly, visual-first, short-form video."
        ),
        trust_signals=(
            "peer recommendations and social proof",
            "founder story with honest failures included",
            "real user reviews and case studies",
            "transparent pricing with no hidden fees",
            "company values that match their own",
        ),
        value_anchors=(
            "authentic social impact",
            "personal growth and learning velocity",
            "work-life harmony (not just balance)",
            "psychological safety",
            "financial clarity and fairness",
        ),
        opening_hooks=(
            "Here's what most people in your space are getting wrong about X.",
            "We ran a 30-day experiment with 3 companies just like yours.",
            "One metric shifted everything for a team we worked with last quarter.",
        ),
        modern_lingo=(
            "ICP fit", "north star metric", "value realization", "async-first",
            "outcome-based", "PLG motion", "time-to-value", "mutual success plan",
        ),
    ),

    GenerationCohort.MILLENNIAL: LanguagePack(
        generation=GenerationCohort.MILLENNIAL,
        power_words=(
            "scalable", "impact", "outcome", "data-backed", "collaborative",
            "sustainable", "ROI", "engagement", "accountability", "growth",
        ),
        avoid_words=(
            "game-changer", "disruption", "ninja", "rockstar", "guru",
            "thought leader without evidence", "revolutionary overused",
        ),
        preferred_format=(
            "Data → narrative → social proof → clear next step. "
            "Email or async Loom video, collaborative Google Doc, bullet-pointed options."
        ),
        trust_signals=(
            "case studies from similar companies",
            "LinkedIn credibility and mutual connections",
            "thought leadership content that teaches before selling",
            "transparent process and timeline",
            "references from peers they respect",
        ),
        value_anchors=(
            "career advancement and skill development",
            "meaningful work with measurable impact",
            "financial security and flexibility",
            "team culture and psychological safety",
            "sustainability and ethics alignment",
        ),
        opening_hooks=(
            "Companies that made this one shift in Q1 compounded it to X by Q4.",
            "Here's a data pattern we saw across 50 teams in your segment.",
            "Your peers are talking about this problem — let me show you how three solved it.",
        ),
        modern_lingo=(
            "land and expand", "business case co-creation", "champion enablement",
            "revenue acceleration", "GTM motion", "demand gen", "customer lifetime value",
            "net revenue retention", "product-market fit signal",
        ),
    ),

    GenerationCohort.GEN_X: LanguagePack(
        generation=GenerationCohort.GEN_X,
        power_words=(
            "ROI", "proven", "bottom line", "practical", "efficient",
            "results", "reliable", "direct", "accountable", "no-nonsense",
        ),
        avoid_words=(
            "innovation theatre", "thought leader", "world-class", "best-of-breed",
            "holistic", "ecosystem overused", "synergy", "bleeding edge",
        ),
        preferred_format=(
            "Bottom line first → evidence → options with tradeoffs → recommendation. "
            "Concise email, executive summary, respect their time absolutely."
        ),
        trust_signals=(
            "hard ROI numbers with attribution",
            "reference customers they can call today",
            "proven track record over multiple years",
            "direct, no-spin communication",
            "options presented with honest tradeoffs",
        ),
        value_anchors=(
            "autonomy and respect for their judgment",
            "financial returns and efficiency gains",
            "practical results over theoretical potential",
            "minimal disruption to what already works",
            "personal accountability in the relationship",
        ),
        opening_hooks=(
            "Here's the number: companies like yours see X% improvement in 90 days.",
            "I'll cut straight to it — here's what this solves and what it costs.",
            "Three references. You can call any of them today. Want the names?",
        ),
        modern_lingo=(
            "EBITDA impact", "operating leverage", "efficiency ratio",
            "total cost of ownership", "implementation risk", "change management",
            "integration complexity", "vendor consolidation",
        ),
    ),

    GenerationCohort.BOOMER: LanguagePack(
        generation=GenerationCohort.BOOMER,
        power_words=(
            "trusted partner", "proven", "enterprise-grade", "comprehensive",
            "personal attention", "long-term", "stability", "commitment", "dedicated",
        ),
        avoid_words=(
            "disruption", "pivot", "agile casual use", "fail fast",
            "MVP", "iterate", "growth hack", "viral", "unicorn",
        ),
        preferred_format=(
            "Relationship first → formal proposal → in-depth discussion → mutual commitment. "
            "Face-to-face or phone call preferred, detailed written proposal, patient process."
        ),
        trust_signals=(
            "personal introduction from a mutual contact",
            "institutional credibility and tenure",
            "reference customers from recognised brands",
            "long-standing business relationships demonstrated",
            "personal commitment from senior leadership",
        ),
        value_anchors=(
            "long-term stability and reliability",
            "personal relationship with dedicated team",
            "proven solution with reference customers",
            "respect for their experience and judgment",
            "legacy protection and continuity",
        ),
        opening_hooks=(
            "I was referred to you by [mutual contact] — they spoke very highly of your work.",
            "We've worked with companies like yours for over a decade.",
            "I'd value the opportunity to understand your priorities before presenting anything.",
        ),
        modern_lingo=(
            "enterprise agreement", "executive sponsor", "strategic partnership",
            "managed service", "dedicated account team", "reference program",
            "board-level visibility", "risk-adjusted return",
        ),
    ),

    GenerationCohort.SILENT: LanguagePack(
        generation=GenerationCohort.SILENT,
        power_words=(
            "trust", "integrity", "commitment", "honour", "personal",
            "long-standing", "institutional", "dependable", "character", "stewardship",
        ),
        avoid_words=(
            "startup", "pivot", "disrupt", "agile", "iterate", "MVP",
            "growth hack", "unicorn", "viral", "ecosystem",
        ),
        preferred_format=(
            "Formal written proposal → in-person meeting → handshake agreement. "
            "Traditional courtesy, unhurried process, personal relationship built first."
        ),
        trust_signals=(
            "personal introduction through known institutional channels",
            "long track record of institutional reliability",
            "personal meetings with senior leadership present",
            "formal written commitments",
            "references from respected community figures",
        ),
        value_anchors=(
            "personal integrity and character alignment",
            "institutional stability and longevity",
            "honour and keeping one's word",
            "community standing and reputation",
            "leaving a worthy legacy",
        ),
        opening_hooks=(
            "It's a privilege to meet you. [Mutual contact] spoke of your work with great respect.",
            "We've served institutions like yours for many years with the same commitment.",
            "I'd be honoured to learn about your work before discussing how we might help.",
        ),
        modern_lingo=(
            "institutional partnership", "stewardship", "legacy programme",
            "personal service commitment", "executive relationship management",
        ),
    ),
}

# ---------------------------------------------------------------------------
# Pain Signal Library — trigger phrases → pain signals
# ---------------------------------------------------------------------------

_PAIN_LIBRARY: List[Tuple[str, PainCategory, PainIntensity, str, str, str]] = [
    # (trigger_phrase, category, intensity, evidence, consequence, probe)

    # Revenue Growth
    ("leaving money on the table",
     PainCategory.REVENUE_GROWTH, PainIntensity.ACTIVE,
     "Current revenue capture is below market potential",
     "Competitors fill the gap while your pipeline velocity stalls",
     "What does your current conversion rate look like from first touch to close?"),

    ("not hitting targets",
     PainCategory.REVENUE_GROWTH, PainIntensity.ACTIVE,
     "Revenue performance is below plan",
     "Compounding miss cascades into headcount freezes and board pressure",
     "How far from target are you, and what quarter did the gap first appear?"),

    ("plateauing",
     PainCategory.REVENUE_GROWTH, PainIntensity.ACKNOWLEDGED,
     "Growth rate has flattened despite sales effort",
     "Market share erodes as competitors compound their advantage",
     "Is the plateau from pipeline volume, conversion rate, or deal size — or all three?"),

    ("board wants more",
     PainCategory.REVENUE_GROWTH, PainIntensity.ACTIVE,
     "Leadership expectations exceed current execution trajectory",
     "Funding, valuation, or leadership tenure at risk without breakout growth",
     "What's the target the board has set, and what's your current run rate gap?"),

    ("need to grow faster",
     PainCategory.REVENUE_GROWTH, PainIntensity.ACKNOWLEDGED,
     "Strategic imperative to accelerate, without clear path to do so",
     "Window of opportunity closes as market matures or competitors fund up",
     "What's the one constraint that, if removed, would unlock the growth?"),

    # Cost Reduction
    ("do more with less",
     PainCategory.COST_REDUCTION, PainIntensity.ACTIVE,
     "Budget reduction mandate while output expectations remain unchanged",
     "Team burnout, quality degradation, and retention risk accelerate",
     "Where are the three biggest cost pools today, and which are discretionary?"),

    ("burn rate too high",
     PainCategory.COST_REDUCTION, PainIntensity.CRITICAL,
     "Spend outpacing revenue threatens runway",
     "Funding round pressure or existential runway risk within quarters",
     "What's your current runway and what burn reduction would extend it meaningfully?"),

    ("margins shrinking",
     PainCategory.COST_REDUCTION, PainIntensity.ACTIVE,
     "Revenue growth not translating to profit improvement",
     "Valuation multiple compression, investor concern, strategic options narrow",
     "Which cost category is growing fastest relative to revenue — COGS, S&M, or G&A?"),

    # Risk Mitigation
    ("can't afford another outage",
     PainCategory.RISK_MITIGATION, PainIntensity.ACTIVE,
     "Previous failure event has sensitised leadership to reliability risk",
     "Revenue loss, reputational damage, and customer churn accelerate with next incident",
     "What was the business impact of the last incident, and what's the recurrence probability?"),

    ("compliance keeping me up",
     PainCategory.RISK_MITIGATION, PainIntensity.ACTIVE,
     "Regulatory exposure is unresolved and personally threatening to leadership",
     "Fines, legal liability, and operating licence risk materialise on the current path",
     "Which regulation or audit finding is most acute, and what's the remediation timeline?"),

    ("single point of failure",
     PainCategory.RISK_MITIGATION, PainIntensity.ACKNOWLEDGED,
     "Critical dependency on one system, person, or vendor",
     "One failure cascades to full operational stoppage",
     "If that single point failed tomorrow, what's your recovery time objective?"),

    # Efficiency
    ("burned out",
     PainCategory.EFFICIENCY, PainIntensity.ACKNOWLEDGED,
     "Team capacity is overwhelmed by process inefficiency",
     "Turnover accelerates, quality degrades, delivery timelines slip",
     "What percentage of team time goes to work that doesn't directly create value?"),

    ("doing this manually",
     PainCategory.EFFICIENCY, PainIntensity.LATENT,
     "High-volume repetitive work is unautomated",
     "Labour cost grows linearly with output, creating a scaling ceiling",
     "How many person-hours per week does this process consume, and what's the error rate?"),

    ("process takes forever",
     PainCategory.EFFICIENCY, PainIntensity.ACKNOWLEDGED,
     "Cycle time on critical workflows exceeds competitive or customer expectations",
     "Deals lost, customers frustrated, and competitive differentiation erodes",
     "What's the current cycle time and what would best-in-class look like for you?"),

    # Talent Retention
    ("keep losing our best people",
     PainCategory.TALENT_RETENTION, PainIntensity.CRITICAL,
     "Top-performer attrition is materially impacting capability",
     "Institutional knowledge evaporates and recruiting cost compounds",
     "What do exit interviews reveal as the top three reasons for departure?"),

    ("recruiting is brutal",
     PainCategory.TALENT_RETENTION, PainIntensity.ACTIVE,
     "Talent acquisition is failing to fill critical roles on plan",
     "Growth targets become unachievable without the headcount to execute them",
     "What's your average time-to-fill for critical roles, and what's the offer acceptance rate?"),

    # Competitive Threat
    ("competitors moving faster",
     PainCategory.COMPETITIVE_THREAT, PainIntensity.CRITICAL,
     "Competitive velocity is outpacing current execution capability",
     "Market share loss accelerates and becomes structural if not reversed",
     "In which specific capability or segment are they pulling ahead fastest?"),

    ("losing deals to",
     PainCategory.COMPETITIVE_THREAT, PainIntensity.CRITICAL,
     "Active competitive displacement happening in pipeline",
     "Revenue plan misses compound and sales team confidence erodes",
     "What's the primary reason buyers choose them over you right now?"),

    # Digital Transformation
    ("legacy systems",
     PainCategory.DIGITAL_TRANSFORMATION, PainIntensity.ACKNOWLEDGED,
     "Technical debt is constraining business agility",
     "Innovation velocity lags industry, and integration cost grows quarterly",
     "What new capability can't you deliver today because of the legacy constraint?"),

    ("tech stack holding us back",
     PainCategory.DIGITAL_TRANSFORMATION, PainIntensity.ACTIVE,
     "Current technology architecture prevents execution of strategic priorities",
     "Roadmap items slip indefinitely, creating compounding strategic disadvantage",
     "What's the one thing your team would build or launch if the constraint were removed?"),

    # Innovation Pressure
    ("not innovating fast enough",
     PainCategory.INNOVATION_PRESSURE, PainIntensity.ACTIVE,
     "Innovation cadence is below market expectations",
     "Product differentiation narrows and premium pricing power erodes",
     "What's the gap between your current release cadence and what customers are asking for?"),

    ("startup competitors eating our lunch",
     PainCategory.INNOVATION_PRESSURE, PainIntensity.CRITICAL,
     "Agile competitors are capturing customer preference with newer approaches",
     "Customer base gradually migrates to alternatives if product velocity doesn't match",
     "Which customer segments are most vulnerable to the startup alternative right now?"),

    # Compliance
    ("got a warning letter",
     PainCategory.COMPLIANCE, PainIntensity.CRITICAL,
     "Regulatory body has issued formal notice of non-compliance",
     "Fines, consent order, or operating restriction imminent without remediation",
     "What's the deadline for your response, and what resources are currently allocated?"),

    ("audit findings piling up",
     PainCategory.COMPLIANCE, PainIntensity.ACTIVE,
     "Repeated or accumulating audit observations signal systemic risk",
     "Regulatory escalation risk grows with each unremediated finding",
     "How many open findings are there, and which carries the highest severity rating?"),
]

# Build lookup dict keyed by trigger keywords for fast matching
PAIN_SIGNAL_LIBRARY: List[PainSignal] = [
    PainSignal(
        category=cat, intensity=inten,
        trigger_phrase=trig, evidence_statement=evid,
        consequence_if_unaddressed=conseq, recommended_probe=probe,
    )
    for trig, cat, inten, evid, conseq, probe in _PAIN_LIBRARY
]


# ---------------------------------------------------------------------------
# Income Scaling Playbooks — 2× through 5×
# ---------------------------------------------------------------------------

INCOME_SCALING_PLAYBOOKS: Dict[IncomeMultiplier, IncomeScalingPlaybook] = {

    IncomeMultiplier.TWO_X: IncomeScalingPlaybook(
        multiplier=IncomeMultiplier.TWO_X,
        strategy_name="Efficiency Compounding",
        thesis=(
            "Double revenue by maximising what you already have. "
            "Automate the pipeline, tighten qualification, close the conversion gap, "
            "and eliminate the waste that caps your current capacity ceiling."
        ),
        preconditions=(
            "Healthy inbound pipeline (minimum 3× coverage)",
            "Sales team with proven individual performers in place",
            "Clear ICP and repeatable discovery process",
            "CRM hygiene sufficient to measure conversion rates by stage",
        ),
        primary_tactics=(
            "Pipeline automation: sequences, triggers, and cadence optimisation",
            "MEDDIC qualification scoring to cut wasted late-stage effort",
            "SDR-to-AE handoff ritual redesign for zero-drop handoff",
            "Sales velocity formula optimisation: deals × win rate × ACV ÷ cycle time",
            "Win-loss analysis on last 20 deals to identify conversion blockers",
        ),
        agent_behaviors=(
            "Lead every conversation with time-to-value: 'How fast do you need to see results?'",
            "Quantify the cost of the current inefficiency before presenting the solution",
            "Build urgency around opportunity cost: every week of delay = $X in lost revenue",
            "Use social proof from similar companies who achieved 2× in 90 days",
        ),
        risk_factors=(
            "Pipeline volume insufficient to convert — need lead generation alongside",
            "Sales team skill gaps limit conversion improvement ceiling",
            "Leadership unwilling to enforce qualification discipline",
        ),
        success_metrics=(
            "Sales velocity ($ per day in pipeline)",
            "Stage-by-stage conversion rates week over week",
            "Average sales cycle length trending down",
            "Win rate on qualified pipeline",
        ),
        timeline_weeks=16,
    ),

    IncomeMultiplier.THREE_X: IncomeScalingPlaybook(
        multiplier=IncomeMultiplier.THREE_X,
        strategy_name="Market Expansion Sprint",
        thesis=(
            "Triple revenue by reaching more buyers. "
            "Expand the ICP to adjacent segments, add new outbound channels, "
            "activate partner ecosystems, and build the referral loop "
            "that turns every customer into a growth vector."
        ),
        preconditions=(
            "Proven playbook with 20+ closed-won case studies",
            "Repeatable sales motion that a new hire can execute within 60 days",
            "Operational infrastructure to onboard 3× the current customer volume",
            "At least one successful channel or geography to expand from",
        ),
        primary_tactics=(
            "ICP expansion to two adjacent verticals using existing case studies",
            "Partner ecosystem activation: 3–5 channel partners with co-sell motions",
            "Structured referral programme with incentivised customer advocates",
            "Outbound SDR team scale: 3× SDR headcount with sequenced territory coverage",
            "Account-Based Marketing campaigns targeting Tier 1 and Tier 2 named accounts",
        ),
        agent_behaviors=(
            "Lead with market size narrative: 'Here's the total addressable market you're leaving'",
            "Present competitive displacement story: 'This is how you take share from X'",
            "Use land-and-expand motion: low-friction entry → rapid expansion after first value",
            "Build champion enablement kits so buyers can sell internally for you",
        ),
        risk_factors=(
            "New segment requires product adaptation not yet resourced",
            "Channel partners underperform without dedicated partner success resources",
            "Operational team can't scale onboarding to match sales velocity",
        ),
        success_metrics=(
            "New logo acquisition rate by segment",
            "Partner-sourced pipeline as % of total",
            "Referral conversion rate and volume",
            "Net Revenue Retention (NRR) ≥ 110%",
        ),
        timeline_weeks=26,
    ),

    IncomeMultiplier.FOUR_X: IncomeScalingPlaybook(
        multiplier=IncomeMultiplier.FOUR_X,
        strategy_name="Premium Elevation & Enterprise Move",
        thesis=(
            "Quadruple revenue by moving upmarket. "
            "Redesign the offer for enterprise buyers, launch a premium tier, "
            "activate executive selling, and build the strategic account motion "
            "that turns $50K customers into $200K customers."
        ),
        preconditions=(
            "3+ enterprise-grade reference customers willing to be named publicly",
            "Product capable of meeting enterprise security, compliance, and integration requirements",
            "Executive team with credibility to sell at C-suite level",
            "Professional services or implementation capability to support complex deployments",
        ),
        primary_tactics=(
            "Enterprise tier launch: premium SKU with ROI-guarantee and executive SLA",
            "Executive sponsor programme: CEO/CPO engagement in top 20 accounts",
            "Strategic account management: dedicated CSM + AE pod for top-10 accounts",
            "Business case co-creation: custom ROI models built jointly with the buyer",
            "Professional services expansion: implementation + transformation consulting",
        ),
        agent_behaviors=(
            "Lead with transformation narrative, not feature list",
            "Co-create the business case with the economic buyer, not the champion",
            "Use the MEDDIC framework rigorously: no proposal without confirmed champion + EC",
            "Build multi-threaded relationships across 3+ stakeholders in every account",
        ),
        risk_factors=(
            "Enterprise sales cycle length delays revenue recognition by 6–12 months",
            "Product gaps surface during enterprise POC and delay close",
            "Mid-market team culture resistant to upmarket motion and longer cycles",
        ),
        success_metrics=(
            "Average Contract Value (ACV) trajectory toward 4× current level",
            "Enterprise pipeline as % of total bookings",
            "Professional services attach rate and margin",
            "Strategic account expansion revenue (net new ARR from existing accounts)",
        ),
        timeline_weeks=40,
    ),

    IncomeMultiplier.FIVE_X: IncomeScalingPlaybook(
        multiplier=IncomeMultiplier.FIVE_X,
        strategy_name="Business Model Transformation",
        thesis=(
            "5× revenue by fundamentally changing how value is created and captured. "
            "Build the platform, activate network effects, convert to recurring revenue, "
            "and create the ecosystem where every participant makes every other participant "
            "more valuable — and your revenue compounds automatically."
        ),
        preconditions=(
            "Market leadership position in core business",
            "Capital and board mandate to invest in 18–36 month transformation",
            "Visionary leadership team with platform-building experience",
            "Existing customer base large enough to seed network effects",
        ),
        primary_tactics=(
            "Platform strategy: API monetisation, marketplace, or data network play",
            "Recurring revenue conversion: all transactional revenue moved to subscription",
            "Network effects architecture: mechanisms that make product more valuable with each user",
            "Ecosystem partner monetisation: revenue share, integration marketplace, ISV programme",
            "Usage-based pricing model: align revenue capture to value delivered",
        ),
        agent_behaviors=(
            "Lead with the 10-year vision: 'Here's where this market ends up and who owns it'",
            "Conduct board-level conversations about platform strategy, not product features",
            "Build the strategic partnership thesis that justifies joint investment",
            "Frame every decision through the lens of 'does this strengthen the network effect?'",
        ),
        risk_factors=(
            "Platform transformation cannibalises core revenue before replacement revenue matures",
            "Network effects take longer to activate than capital runway allows",
            "Existing team lacks platform-building DNA and resists the transformation",
        ),
        success_metrics=(
            "Recurring revenue as % of total (target: 80%+)",
            "Net Revenue Retention ≥ 130%",
            "Ecosystem partner revenue as % of total",
            "Customer acquisition cost trending toward zero via network effect",
        ),
        timeline_weeks=78,
    ),
}


# ---------------------------------------------------------------------------
# Framework Guides — complete operating guides for each framework
# ---------------------------------------------------------------------------

FRAMEWORK_GUIDES: Dict[SalesFramework, FrameworkGuide] = {

    SalesFramework.MEDDIC: FrameworkGuide(
        framework=SalesFramework.MEDDIC,
        full_name="MEDDIC — Metrics, Economic Buyer, Decision Criteria, Decision Process, Identify Pain, Champion",
        best_for=(
            "Enterprise deals over $100K ACV",
            "Multi-stakeholder buying committees (3+ people)",
            "Sales cycles exceeding 90 days",
            "Competitive situations requiring documented differentiation",
        ),
        opening_move=(
            "Map the buying committee before your first meeting. "
            "Identify the economic buyer, find your champion, and qualify the decision criteria "
            "before you invest in a formal proposal."
        ),
        key_questions=(
            "What metrics will you use to measure success 12 months after implementation?",
            "Who has final budget authority for this decision?",
            "Walk me through your evaluation process — what does good look like at each stage?",
            "Who internally is most invested in solving this problem?",
            "What does the status quo cost you right now in measurable terms?",
        ),
        closing_technique=(
            "Mutual Close Plan: co-create a written timeline with the champion, "
            "milestone by milestone, that leads to the signature date. "
            "Make the buyer the architect of their own decision."
        ),
        objection_handler=(
            "For 'we need to think about it': 'Absolutely — let me share what others "
            "at your stage found most useful for their internal evaluation. "
            "What criteria matter most to your team?'"
        ),
        modern_twist=(
            "Add Competition (MEDDICC): document competitive differentiation "
            "explicitly so your champion can defend you in rooms you're not in. "
            "Build a 'champion enablement kit' — a one-page internal selling tool."
        ),
    ),

    SalesFramework.CHALLENGER: FrameworkGuide(
        framework=SalesFramework.CHALLENGER,
        full_name="Challenger Sale — Teach · Tailor · Take Control",
        best_for=(
            "Commoditised markets where buyers think all options are equivalent",
            "Status-quo-biased buyers who haven't prioritised the problem",
            "Complex solutions where the buyer doesn't know what they don't know",
            "When differentiation must be taught, not just demonstrated",
        ),
        opening_move=(
            "Lead with a commercial insight the buyer has never heard — "
            "something that reframes their business challenge in a way "
            "that makes your solution the obvious path forward."
        ),
        key_questions=(
            "Have you considered that [industry assumption] is actually costing you [specific amount]?",
            "What if the constraint you're optimising for isn't actually the binding constraint?",
            "Most companies in your position focus on X — but the ones who outperform focus on Y. "
            "What's driving your current focus?",
        ),
        closing_technique=(
            "Constructive Tension Close: maintain the tension of the insight "
            "until the buyer resolves it by moving forward. "
            "'Given what we've uncovered today, what's the cost of not acting?'"
        ),
        objection_handler=(
            "For 'we're happy with our current approach': "
            "'I'd expect that — most companies at your stage feel the same. "
            "Let me share what changed the perspective of three of them.'"
        ),
        modern_twist=(
            "2025 update: pair Challenger insight with Jobs-to-be-Done language. "
            "The insight should illuminate a 'job' the buyer is struggling with "
            "that they didn't know they were hiring solutions to perform."
        ),
    ),

    SalesFramework.GAP_SELLING: FrameworkGuide(
        framework=SalesFramework.GAP_SELLING,
        full_name="GAP Selling — Current State → Future State → Consequence of Inaction",
        best_for=(
            "Buyers who can clearly articulate a problem but haven't connected it to urgency",
            "Mid-market deals where emotion and logic both need to be engaged",
            "Discovery calls where you need to build the business case together",
            "Situations where the buyer needs to feel the pain before they'll move",
        ),
        opening_move=(
            "Map the current state in explicit detail before introducing any solution. "
            "The more precisely you can describe their problem, the more credibly "
            "you can describe the future state."
        ),
        key_questions=(
            "Walk me through exactly what happens today when [problem occurs].",
            "What does that cost you — in time, money, or team morale?",
            "What would be different if this problem were solved 6 months from now?",
            "What happens if it isn't solved — what does that path look like?",
            "What's the gap between where you are and where you need to be?",
        ),
        closing_technique=(
            "Consequence Acceleration: make the cost of inaction vivid and time-bound. "
            "'Based on what you've told me, every quarter without a solution costs X. "
            "What would change your timeline decision?'"
        ),
        objection_handler=(
            "For 'it's not a priority right now': "
            "'I understand. Let me ask — what is the business impact if it stays "
            "where it is for another 6 months? That might help clarify the priority.'"
        ),
        modern_twist=(
            "Pair GAP Selling with a live ROI calculator in the meeting. "
            "Have the buyer input their own numbers so they own the consequence "
            "calculation — it's far more persuasive than your numbers."
        ),
    ),

    SalesFramework.SPIN_MODERN: FrameworkGuide(
        framework=SalesFramework.SPIN_MODERN,
        full_name="SPIN Modern — Situation · Problem · Implication · Need-Payoff",
        best_for=(
            "First discovery meetings with unknown buyers",
            "Complex situations where implications are not yet visible to the buyer",
            "Consultative relationships where trust must be built through questioning",
            "SMB-to-mid-market deals where discovery depth is competitive advantage",
        ),
        opening_move=(
            "Ask 2–3 Situation questions to establish context, "
            "then move rapidly to Problem questions. "
            "Never linger in Situation — it wastes buyer time and signals low preparation."
        ),
        key_questions=(
            "Situation: 'How are you currently handling X?' (1–2 questions max)",
            "Problem: 'What's the most frustrating part of the current approach?'",
            "Implication: 'If that problem goes unresolved, what else does it affect?'",
            "Implication: 'What's the downstream impact on your team / customers / revenue?'",
            "Need-Payoff: 'If you could fix that specific thing, what would it mean for you?'",
        ),
        closing_technique=(
            "Buyer Self-Discovery Close: the Need-Payoff questions have the buyer "
            "articulate the value themselves. Then confirm: "
            "'Based on what you've described, would a solution that did X, Y, Z be worth it?'"
        ),
        objection_handler=(
            "For 'we're not sure we have that problem': "
            "'That's a fair point. Let me ask a few more questions to see "
            "whether this is relevant to your situation — is that OK?'"
        ),
        modern_twist=(
            "Layer Jobs-to-be-Done into the Problem question: "
            "'Beyond the functional problem, what's the underlying job your team is really "
            "trying to get done that this is getting in the way of?'"
        ),
    ),

    SalesFramework.SNAP_SELLING: FrameworkGuide(
        framework=SalesFramework.SNAP_SELLING,
        full_name="SNAP Selling — Simple · iNvaluable · Aligned · Priority",
        best_for=(
            "Extremely busy C-suite buyers with 10-minute attention windows",
            "High-velocity, short-cycle deals where simplicity wins",
            "Initial outreach and first contact with overwhelmed decision-makers",
            "When complexity is the buyer's enemy and you need to cut through",
        ),
        opening_move=(
            "Remove all friction from every interaction. "
            "Open with one sentence: what you do, who it's for, and the result it produces. "
            "Never make a busy person work to understand your value."
        ),
        key_questions=(
            "What's the one metric your board is most focused on this quarter?",
            "If you had one hour to fix your biggest problem, where would you point it?",
            "What's on your 'wish list' that keeps getting deprioritised?",
        ),
        closing_technique=(
            "Priority Alignment Close: connect your solution directly to their "
            "stated #1 priority. 'You said X is your north star metric this quarter. "
            "This is the fastest path to moving that number. What would make it easy to start?'"
        ),
        objection_handler=(
            "For 'I don't have time right now': "
            "'I understand completely. Two questions — that's it — and I'll tell you "
            "in under 60 seconds whether this is worth more of your time.'"
        ),
        modern_twist=(
            "In 2025, SNAP buyers live in Slack and are trained on async communication. "
            "Your Loom video, one-pager, or single compelling stat can do the work "
            "of a 30-minute meeting. Design your outreach for async consumption first."
        ),
    ),

    SalesFramework.COMMAND_OF_SALE: FrameworkGuide(
        framework=SalesFramework.COMMAND_OF_SALE,
        full_name="Command of the Sale — Connect · Clarify · Contrast · Convince · Close",
        best_for=(
            "Competitive displacement situations where the buyer has an incumbent",
            "When the salesperson needs to re-establish control of a drifting deal",
            "High-stakes deals where the buyer's process threatens the outcome",
            "When you need to compress a slow buying process without alienating the buyer",
        ),
        opening_move=(
            "Establish connection first: show you understand their world intimately. "
            "Then clarify the problem with more precision than they've heard before. "
            "The contrast against alternatives comes after you've earned the right."
        ),
        key_questions=(
            "What does your ideal outcome look like — specifically?",
            "What's the difference between a successful implementation and a failed one for you?",
            "What has every other solution you've evaluated gotten wrong?",
            "What would it take to make this decision by [date]?",
        ),
        closing_technique=(
            "Command Close: when the deal stalls, name the stall. "
            "'Something's shifted since we last spoke. Can you help me understand "
            "what the real decision is right now?' Then solve the actual blocker."
        ),
        objection_handler=(
            "For 'we're going with another vendor': "
            "'I respect that. Can I ask what made the difference? "
            "Not to change your mind — but so I understand what we missed.'"
            " (This often re-opens the conversation.)"
        ),
        modern_twist=(
            "In 2025, Command of Sale requires a digital command centre: "
            "track every stakeholder interaction in a purpose-built deal room, "
            "share content selectively, and monitor engagement signals in real time."
        ),
    ),

    SalesFramework.JBTD: FrameworkGuide(
        framework=SalesFramework.JBTD,
        full_name="Jobs-to-be-Done — Functional + Emotional + Social Job Layers",
        best_for=(
            "Product-led growth motions where usage drives purchase",
            "Innovation buyers trying to solve a new problem with a new approach",
            "When feature-selling isn't working and you need to sell outcomes",
            "Building positioning for a new market category",
        ),
        opening_move=(
            "Ask about the job, not the product. "
            "'What were you trying to accomplish when you first started looking for a solution?' "
            "Surface the functional, emotional, and social dimensions of the job."
        ),
        key_questions=(
            "Functional: 'What specific task or outcome were you trying to achieve?'",
            "Functional: 'What were you using before, and what forced the change?'",
            "Emotional: 'How did it feel when the old approach failed you?'",
            "Social: 'How does your team / boss / peers see you when this works well?'",
            "Switching: 'What would have to be true for you to switch away from us?'",
        ),
        closing_technique=(
            "Job Completion Close: confirm you solve all three layers. "
            "'You need to [functional job], feel [emotional job], "
            "and be seen as [social job]. Does what we've shown you accomplish all three?'"
        ),
        objection_handler=(
            "For 'we need to think about it': "
            "'Of course. Can I ask — which of the three outcomes is the one "
            "you're still not certain we can deliver? Let's look at that together.'"
        ),
        modern_twist=(
            "2025: layer AI/automation into the JBTD framework. "
            "The fastest-growing 'social job' is 'look like the person who brought AI "
            "into the organisation effectively.' That job is real and highly motivating."
        ),
    ),

    SalesFramework.CONSULTATIVE: FrameworkGuide(
        framework=SalesFramework.CONSULTATIVE,
        full_name="Consultative Selling — Relationship-First, Trust-Led Discovery",
        best_for=(
            "Long-cycle, relationship-dependent accounts",
            "Rebuilding trust after a bad experience with a previous vendor",
            "Highly complex solutions requiring deep organisational understanding",
            "Sectors where reputation and referral are the primary pipeline source",
        ),
        opening_move=(
            "Invest in understanding before proposing anything. "
            "Your first job is to understand their world so well "
            "that they believe you can solve problems they haven't named yet."
        ),
        key_questions=(
            "What are you working on that matters most to you right now?",
            "What does success look like for you personally — not just the business?",
            "Who else needs to be involved for this to move forward?",
            "What have you tried before, and what did you learn from it?",
            "What would make this the best professional relationship you've had?",
        ),
        closing_technique=(
            "Invitation Close: never push. 'Based on what we've discussed, "
            "I believe we can help. Would you like to explore what that looks like together?' "
            "Mutual readiness, not sales pressure."
        ),
        objection_handler=(
            "For any objection: 'That's really helpful feedback. "
            "Help me understand that more — what's behind that concern?' "
            "Consultative selling means objections are information, not obstacles."
        ),
        modern_twist=(
            "2025: the consultative relationship now includes AI-powered insights "
            "delivered proactively. The best consultative sellers send 'you might find "
            "this relevant' intelligence to clients between meetings — maintaining "
            "presence without being transactional."
        ),
    ),
}


# ---------------------------------------------------------------------------
# Framework Selection Logic
# ---------------------------------------------------------------------------

def _select_framework(
    profile: DemographicProfile,
    pain_signals: List[PainSignal],
) -> SalesFramework:
    """Deterministically select the best framework for the given client context."""
    max_urgency = max((p.urgency_score for p in pain_signals), default=0.0)
    has_critical = any(p.intensity == PainIntensity.CRITICAL for p in pain_signals)
    pain_categories = {p.category for p in pain_signals}

    # Relationship-first cohorts (Boomer/Silent) with strong relational preference
    # override enterprise qualification; trust comes before metrics.
    if (profile.generation in (GenerationCohort.BOOMER, GenerationCohort.SILENT)
            and profile.relationship_dependency >= 0.75):
        return SalesFramework.CONSULTATIVE

    # Enterprise economic buyer, complex deal → MEDDIC
    if (profile.role == DecisionMakerRole.ECONOMIC_BUYER
            and profile.formality_preference >= 0.60):
        return SalesFramework.MEDDIC

    # Busy C-suite with low patience → SNAP
    if (profile.role == DecisionMakerRole.ECONOMIC_BUYER
            and profile.decision_speed > 0.75
            and profile.formality_preference < 0.40):
        return SalesFramework.SNAP_SELLING

    # Relationship-first cohorts (Boomer/Silent) without dominant relational signal → Consultative
    if profile.generation in (GenerationCohort.BOOMER, GenerationCohort.SILENT):
        return SalesFramework.CONSULTATIVE

    # Competitive threat pain → Challenger
    if PainCategory.COMPETITIVE_THREAT in pain_categories or has_critical:
        return SalesFramework.CHALLENGER

    # Innovation / digital transformation → JBTD
    if (PainCategory.INNOVATION_PRESSURE in pain_categories
            or PainCategory.DIGITAL_TRANSFORMATION in pain_categories):
        return SalesFramework.JBTD

    # Clear gap between current and desired → GAP Selling
    if (PainCategory.REVENUE_GROWTH in pain_categories
            or PainCategory.EFFICIENCY in pain_categories) and max_urgency >= 0.75:
        return SalesFramework.GAP_SELLING

    # Technical buyer in discovery → SPIN Modern
    if profile.role == DecisionMakerRole.TECHNICAL_BUYER:
        return SalesFramework.SPIN_MODERN

    # Control needed (champion with unclear EC) → Command of Sale
    if profile.role == DecisionMakerRole.CHAMPION:
        return SalesFramework.COMMAND_OF_SALE

    # Default: GAP Selling is universally applicable
    return SalesFramework.GAP_SELLING


def _recommend_multiplier(
    profile: DemographicProfile,
    pain_signals: List[PainSignal],
) -> IncomeMultiplier:
    """Recommend the most achievable income multiplier for this client context."""
    has_critical = any(p.intensity == PainIntensity.CRITICAL for p in pain_signals)
    pain_categories = {p.category for p in pain_signals}

    # Digital / innovation transformation → 5×
    if (PainCategory.DIGITAL_TRANSFORMATION in pain_categories
            and PainCategory.INNOVATION_PRESSURE in pain_categories):
        return IncomeMultiplier.FIVE_X

    # Premium-ready: enterprise role + high formality + competitive threat → 4×
    if (profile.role == DecisionMakerRole.ECONOMIC_BUYER
            and profile.formality_preference >= 0.65
            and PainCategory.COMPETITIVE_THREAT in pain_categories):
        return IncomeMultiplier.FOUR_X

    # Growth + talent + efficiency together → 3×
    growth_pain = {PainCategory.REVENUE_GROWTH, PainCategory.EFFICIENCY, PainCategory.TALENT_RETENTION}
    if len(growth_pain & pain_categories) >= 2:
        return IncomeMultiplier.THREE_X

    # Default for most situations → 2×
    return IncomeMultiplier.TWO_X


# ---------------------------------------------------------------------------
# PainPointDetector
# ---------------------------------------------------------------------------

class PainPointDetector:
    """
    Detects pain signals in client conversation text.

    Matches trigger phrases against the PAIN_SIGNAL_LIBRARY and returns
    ranked PainSignal instances sorted by urgency (critical → latent).
    """

    # Build lookup index: normalised trigger phrase → PainSignal
    _INDEX: Dict[str, PainSignal] = {
        signal.trigger_phrase.lower(): signal
        for signal in PAIN_SIGNAL_LIBRARY
    }

    def detect(self, conversation_signals: List[str]) -> List[PainSignal]:
        """
        Scan *conversation_signals* (list of utterances or phrases) and
        return all detected PainSignals ranked by urgency descending.
        """
        found: Dict[str, PainSignal] = {}
        combined = " ".join(s.lower() for s in conversation_signals)

        for trigger, signal in self._INDEX.items():
            if trigger in combined:
                found[trigger] = signal

        # Fuzzy word-overlap fallback for partial matches
        combined_words = set(re.findall(r"\b\w+\b", combined))
        for trigger, signal in self._INDEX.items():
            if trigger in found:
                continue
            trigger_words = set(re.findall(r"\b\w+\b", trigger))
            if len(trigger_words) >= 3 and len(trigger_words & combined_words) >= 2:
                found[trigger] = signal

        return sorted(found.values(), key=lambda s: s.urgency_score, reverse=True)

    def primary_pain(self, signals: List[PainSignal]) -> Optional[PainSignal]:
        """Return the highest-urgency signal, or None if no signals detected."""
        return signals[0] if signals else None

    def get_probes(self, category: PainCategory) -> List[str]:
        """Return all recommended probes for a given pain category."""
        return [s.recommended_probe for s in PAIN_SIGNAL_LIBRARY if s.category == category]


# ---------------------------------------------------------------------------
# DemographicAdapter
# ---------------------------------------------------------------------------

class DemographicAdapter:
    """
    Adapts communication style and vocabulary to the client's demographic profile.

    Provides language packs, message adaptation, and demographic inference
    from conversation signals.
    """

    def get_language_pack(self, profile: DemographicProfile) -> LanguagePack:
        """Return the generation-native LanguagePack for this profile."""
        return LANGUAGE_PACKS[profile.generation]

    def adapt_message(self, base_message: str, profile: DemographicProfile) -> str:
        """
        Adapt a base message for the demographic profile.

        Prepends the most appropriate opening hook and formats the close
        to match communication style preferences.
        """
        pack = self.get_language_pack(profile)
        hook = pack.opening_hooks[0] if pack.opening_hooks else ""
        avoid_note = (
            f" [Avoid: {', '.join(list(pack.avoid_words)[:3])}]"
            if pack.avoid_words else ""
        )
        style_note = f" — formatted as: {pack.preferred_format.split('.')[0]}"
        return f"{hook} {base_message}{style_note}{avoid_note}".strip()

    def infer_profile_from_signals(
        self,
        signals: List[str],
        default_generation: GenerationCohort = GenerationCohort.MILLENNIAL,
        default_industry: IndustryVertical = IndustryVertical.TECHNOLOGY,
        default_role: DecisionMakerRole = DecisionMakerRole.ECONOMIC_BUYER,
    ) -> DemographicProfile:
        """
        Infer a DemographicProfile from conversation signals using keyword matching.
        Falls back to sensible defaults for unresolvable attributes.
        """
        text = " ".join(s.lower() for s in signals)

        # Generation inference from vocabulary
        generation = default_generation
        if any(w in text for w in ("roi", "bottom line", "proven", "cut to the chase")):
            generation = GenerationCohort.GEN_X
        elif any(w in text for w in ("trusted partner", "long-term", "personal relationship", "enterprise-grade")):
            generation = GenerationCohort.BOOMER
        elif any(w in text for w in ("authentic", "impact", "values", "transparency")):
            generation = GenerationCohort.GEN_Z
        elif any(w in text for w in ("scalable", "data", "outcome", "bandwidth")):
            generation = GenerationCohort.MILLENNIAL

        # Industry inference
        industry = default_industry
        for vert in IndustryVertical:
            if vert.value.replace("_", " ") in text:
                industry = vert
                break

        # Role inference
        role = default_role
        if any(w in text for w in ("cto", "ciso", "technical", "engineer", "architect")):
            role = DecisionMakerRole.TECHNICAL_BUYER
        elif any(w in text for w in ("ceo", "cfo", "coo", "board", "investor")):
            role = DecisionMakerRole.ECONOMIC_BUYER
        elif any(w in text for w in ("champion", "sponsor", "advocate")):
            role = DecisionMakerRole.CHAMPION

        return DemographicProfile(
            generation=generation,
            industry=industry,
            role=role,
        )


# ---------------------------------------------------------------------------
# IncomeScalingEngine
# ---------------------------------------------------------------------------

class IncomeScalingEngine:
    """
    Provides income-scaling playbooks and multiplier recommendations.

    Maps client context (demographic profile + pain signals) to the
    most achievable revenue scaling strategy (2× → 5×).
    """

    def get_playbook(self, multiplier: IncomeMultiplier) -> IncomeScalingPlaybook:
        """Return the scaling playbook for the specified multiplier."""
        return INCOME_SCALING_PLAYBOOKS[multiplier]

    def recommend_multiplier(
        self,
        profile: DemographicProfile,
        pain_signals: List[PainSignal],
    ) -> IncomeMultiplier:
        """Recommend the most achievable multiplier for this client context."""
        return _recommend_multiplier(profile, pain_signals)

    def all_playbooks(self) -> List[IncomeScalingPlaybook]:
        """Return all four scaling playbooks in ascending multiplier order."""
        return [INCOME_SCALING_PLAYBOOKS[m] for m in IncomeMultiplier]


# ---------------------------------------------------------------------------
# FrameworkSelector
# ---------------------------------------------------------------------------

class FrameworkSelector:
    """Selects the optimal sales framework for a given client context."""

    def select(
        self,
        profile: DemographicProfile,
        pain_signals: List[PainSignal],
    ) -> SalesFramework:
        """Return the recommended SalesFramework for this context."""
        return _select_framework(profile, pain_signals)

    def get_guide(self, framework: SalesFramework) -> FrameworkGuide:
        """Return the operating guide for a specific framework."""
        return FRAMEWORK_GUIDES[framework]

    def all_guides(self) -> List[FrameworkGuide]:
        """Return all framework guides."""
        return list(FRAMEWORK_GUIDES.values())


# ---------------------------------------------------------------------------
# ClientPsychologyEngine — top-level façade
# ---------------------------------------------------------------------------

class ClientPsychologyEngine:
    """
    Top-level façade for the Client Psychology Engine.

    Combines demographic intelligence, pain point detection, framework
    selection, and income scaling into a single unified client reading.

    Usage::

        engine = ClientPsychologyEngine()

        report = engine.read_client(
            client_id="acme_ceo",
            conversation_signals=[
                "We're leaving money on the table",
                "Our competitors are moving faster",
                "The board wants us to scale 3x this year",
            ],
            demographic_hints={
                "generation": GenerationCohort.GEN_X,
                "industry":   IndustryVertical.TECHNOLOGY,
                "role":       DecisionMakerRole.ECONOMIC_BUYER,
            },
        )
        print(report.opening_gambit)
        print(report.recommended_framework.value)
    """

    def __init__(self) -> None:
        self._detector  = PainPointDetector()
        self._adapter   = DemographicAdapter()
        self._scaling   = IncomeScalingEngine()
        self._selector  = FrameworkSelector()
        self._lock      = threading.Lock()
        self._history:  List[ClientReadingReport] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def read_client(
        self,
        client_id: str,
        conversation_signals: List[str],
        demographic_hints: Optional[Dict[str, Any]] = None,
    ) -> ClientReadingReport:
        """
        Generate a full psychological reading of the client.

        Parameters
        ----------
        client_id:
            Unique identifier for this client (used for caching).
        conversation_signals:
            Raw utterances or key phrases from the client conversation.
        demographic_hints:
            Optional dict with keys: generation, industry, role
            (GenerationCohort, IndustryVertical, DecisionMakerRole instances).
        """
        hints = demographic_hints or {}

        # Build or infer demographic profile
        if all(k in hints for k in ("generation", "industry", "role")):
            profile = DemographicProfile(
                generation=hints["generation"],
                industry=hints["industry"],
                role=hints["role"],
                communication_style=hints.get("communication_style", CommunicationStyle.RESULTS_FIRST),
                tech_savviness=hints.get("tech_savviness", 0.70),
                formality_preference=hints.get("formality_preference", 0.50),
                relationship_dependency=hints.get("relationship_dependency", 0.50),
                decision_speed=hints.get("decision_speed", 0.50),
            )
        else:
            profile = self._adapter.infer_profile_from_signals(conversation_signals)

        # Detect pain signals
        pain_signals = self._detector.detect(conversation_signals)
        primary_pain = self._detector.primary_pain(pain_signals)

        # Select framework and scaling lever
        framework  = self._selector.select(profile, pain_signals)
        multiplier = self._scaling.recommend_multiplier(profile, pain_signals)

        # Get language pack
        lang = self._adapter.get_language_pack(profile)

        # Build guide
        guide = self._selector.get_guide(framework)
        playbook = self._scaling.get_playbook(multiplier)

        # Compose opening gambit
        opening_gambit = self._compose_opening(profile, primary_pain, lang, framework)

        # Build urgency narrative
        urgency_narrative = self._compose_urgency(primary_pain, multiplier)

        # Objection preemptions based on framework
        objection_preemptions = [
            guide.objection_handler,
            f"For 'we have no budget': 'Understood — let me help you build the business case "
            f"that unlocks the budget. What's the ROI threshold your CFO needs to see?'",
            f"For 'too risky': 'What would need to be true for this to feel safe? "
            f"Let's start there.'",
        ]

        report = ClientReadingReport(
            client_id=client_id,
            demographic_profile=profile,
            detected_pain_signals=pain_signals,
            primary_pain=primary_pain,
            recommended_framework=framework,
            income_scaling_lever=multiplier,
            language_pack=lang,
            opening_gambit=opening_gambit,
            key_discovery_questions=list(guide.key_questions[:4]),
            objection_preemptions=objection_preemptions,
            closing_approach=guide.closing_technique,
            urgency_narrative=urgency_narrative,
        )

        with self._lock:
            if len(self._history) >= 500:
                del self._history[:50]
            self._history.append(report)

        return report

    def get_language_pack(self, generation: GenerationCohort) -> LanguagePack:
        """Return the language pack for a specific generational cohort."""
        return LANGUAGE_PACKS[generation]

    def get_scaling_playbook(self, multiplier: IncomeMultiplier) -> IncomeScalingPlaybook:
        """Return the scaling playbook for a specific multiplier."""
        return self._scaling.get_playbook(multiplier)

    def describe_framework(self, framework: SalesFramework) -> FrameworkGuide:
        """Return the complete operating guide for a specific framework."""
        return self._selector.get_guide(framework)

    def all_language_packs(self) -> List[LanguagePack]:
        """Return all generation language packs."""
        return list(LANGUAGE_PACKS.values())

    def recent_readings(self, n: int = 10) -> List[ClientReadingReport]:
        """Return the *n* most recent client readings."""
        with self._lock:
            return self._history[-n:]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compose_opening(
        self,
        profile: DemographicProfile,
        primary_pain: Optional[PainSignal],
        lang: LanguagePack,
        framework: SalesFramework,
    ) -> str:
        hook = lang.opening_hooks[0] if lang.opening_hooks else "Let me get straight to the point."
        if primary_pain:
            return (
                f"{hook} Based on what I'm hearing, {primary_pain.evidence_statement.lower()} "
                f"is the core challenge. Here's how we'd address that."
            )
        return hook

    def _compose_urgency(
        self,
        primary_pain: Optional[PainSignal],
        multiplier: IncomeMultiplier,
    ) -> str:
        if primary_pain and primary_pain.intensity in (PainIntensity.ACTIVE, PainIntensity.CRITICAL):
            return (
                f"{primary_pain.consequence_if_unaddressed} "
                f"The {multiplier.value} scaling pathway we're proposing addresses this directly — "
                f"with the right motion in place, the cost of inaction compounds every quarter."
            )
        return (
            f"The {multiplier.value} revenue pathway is achievable within "
            f"{INCOME_SCALING_PLAYBOOKS[multiplier].timeline_weeks} weeks "
            f"with the right prioritisation. Every quarter of delay narrows the window."
        )
