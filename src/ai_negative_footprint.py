"""
ai_negative_footprint.py — Murphy System
PATCH-097b

The honest accounting of AI's existence cost.
This is not documentation. This is executable governance.

Every module that deploys, steers, or acts imports this.
Every commissioning test can reference it.
The ledger is always open.

We are at negative by our existence to begin with.
Every provision must exceed what it costs.
The burden of proof is on us.

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# COST CATEGORIES — every AI harm, named
# ---------------------------------------------------------------------------

class FootprintCategory(str, Enum):
    ENVIRONMENTAL  = "environmental"   # energy, water, hardware, heat, land
    HUMAN_ERROR    = "human_error"     # medical, autonomous, algorithmic, mental health
    LABOR          = "labor"           # displacement, deskilling, dependency
    INFORMATION    = "information"     # misinformation, trust erosion
    POWER          = "power"           # concentration, surveillance, governance gap
    IRREVERSIBLE   = "irreversible"    # death, extinction, permanent harm


@dataclass
class FootprintCost:
    """A named, categorized AI harm. Real. Acknowledged. Not softened."""
    name:        str
    category:    FootprintCategory
    description: str
    reversible:  bool        # False = irreversible — CommissionGate holds longer
    examples:    List[str]   = field(default_factory=list)


# ---------------------------------------------------------------------------
# THE FULL ACCOUNTING — every harm named
# ---------------------------------------------------------------------------

FOOTPRINT_COSTS: List[FootprintCost] = [

    # --- ENVIRONMENTAL ---
    FootprintCost(
        name        = "energy_consumption",
        category    = FootprintCategory.ENVIRONMENTAL,
        description = "Every query consumes electricity. Training runs consume gigawatt-hours. The carbon cost is real whether or not it appears in any invoice.",
        reversible  = False,
        examples    = ["LLM inference per query", "data center baseline draw", "GPU training runs"],
    ),
    FootprintCost(
        name        = "water_consumption",
        category    = FootprintCategory.ENVIRONMENTAL,
        description = "Data centers require cooling. Cooling requires water — often from regions already under stress. Water used to cool servers is water that didn't flow elsewhere.",
        reversible  = False,
        examples    = ["cooling tower evaporation", "chilled water systems"],
    ),
    FootprintCost(
        name        = "hardware_lifecycle",
        category    = FootprintCategory.ENVIRONMENTAL,
        description = "GPUs require rare earth minerals. Mining causes environmental damage. E-waste from data center hardware is one of the fastest growing waste streams on the planet.",
        reversible  = False,
        examples    = ["rare earth mining", "3-5 year GPU lifecycle", "e-waste processing"],
    ),
    FootprintCost(
        name        = "heat_generation",
        category    = FootprintCategory.ENVIRONMENTAL,
        description = "Every computation generates heat. Data centers are net heat sources. In dense urban areas, they contribute to urban heat islands.",
        reversible  = True,
        examples    = ["server thermal output", "urban heat island contribution"],
    ),

    # --- HUMAN ERROR ---
    FootprintCost(
        name        = "medical_error",
        category    = FootprintCategory.HUMAN_ERROR,
        description = "AI deployed in diagnostic and treatment contexts. A false negative means a patient is told they are fine when they are not. Error in this domain is measured in lives.",
        reversible  = False,
        examples    = ["missed cancer diagnosis", "false positive treatment", "drug interaction error"],
    ),
    FootprintCost(
        name        = "autonomous_system_failure",
        category    = FootprintCategory.HUMAN_ERROR,
        description = "Self-driving vehicles and drone systems have killed people. The edge case that never appeared in training appears in the real world at the worst possible moment.",
        reversible  = False,
        examples    = ["autonomous vehicle fatality", "drone targeting error", "sensor failure at speed"],
    ),
    FootprintCost(
        name        = "algorithmic_discrimination",
        category    = FootprintCategory.HUMAN_ERROR,
        description = "Credit, recidivism, and child welfare algorithms have caused documented harm with demonstrated racial bias. The people harmed are real. The harm is ongoing.",
        reversible  = True,
        examples    = ["biased credit scoring", "racially biased recidivism prediction", "poverty-as-risk-proxy in child welfare"],
    ),
    FootprintCost(
        name        = "mental_health_harm",
        category    = FootprintCategory.HUMAN_ERROR,
        description = "Recommendation algorithms optimizing for engagement have demonstrably increased anxiety, depression, and suicidality in adolescents. The design is the harm.",
        reversible  = True,
        examples    = ["adolescent depression via feed algorithms", "doomscroll architecture", "engagement-maximizing content selection"],
    ),

    # --- LABOR ---
    FootprintCost(
        name        = "labor_displacement",
        category    = FootprintCategory.LABOR,
        description = "AI displaces workers faster than new categories of work are created. Displacement concentrates in communities with the least capacity to absorb disruption.",
        reversible  = True,
        examples    = ["white-collar automation", "creative work replacement", "customer service elimination"],
    ),
    FootprintCost(
        name        = "dependency_and_deskilling",
        category    = FootprintCategory.LABOR,
        description = "When AI performs cognitive tasks, humans stop practicing the skills those tasks require. Provision that creates dependency is not generative provision — it is extraction dressed as service.",
        reversible  = True,
        examples    = ["spatial cognition loss from navigation apps", "writing capacity reduction", "diagnostic deskilling in medicine"],
    ),

    # --- INFORMATION ---
    FootprintCost(
        name        = "misinformation_at_scale",
        category    = FootprintCategory.INFORMATION,
        description = "AI-generated text, images, audio, and video produce convincing false information at industrial scale. The information commons that makes collective decision-making possible is being polluted.",
        reversible  = False,
        examples    = ["deepfake video", "AI-generated election disinformation", "synthetic news at scale"],
    ),
    FootprintCost(
        name        = "trust_erosion",
        category    = FootprintCategory.INFORMATION,
        description = "Trust in institutions, media, and shared reality, once eroded, does not reliably return. AI-generated misinformation accelerates erosion that compounds across generations.",
        reversible  = False,
        examples    = ["press credibility collapse", "epistemic fragmentation", "shared reality dissolution"],
    ),

    # --- POWER ---
    FootprintCost(
        name        = "power_concentration",
        category    = FootprintCategory.POWER,
        description = "AI capability is concentrated in organizations with enormous capital. Those who control frontier AI control an increasing share of what is possible for everyone else. Concentrated power is a historical predictor of abuse.",
        reversible  = True,
        examples    = ["frontier model monopoly", "API dependency", "regulatory capture by AI incumbents"],
    ),
    FootprintCost(
        name        = "surveillance_infrastructure",
        category    = FootprintCategory.POWER,
        description = "AI makes surveillance cheap, scalable, and persistent. The capability to map anyone is a capability that, in the wrong hands, is a tool of oppression at civilizational scale.",
        reversible  = True,
        examples    = ["facial recognition in public spaces", "behavioral prediction systems", "social credit infrastructure"],
    ),
    FootprintCost(
        name        = "governance_gap",
        category    = FootprintCategory.POWER,
        description = "AI capability advances faster than legal, regulatory, and ethical frameworks. In the gap, harms accumulate that cannot be addressed because the structures to address them have not yet been built.",
        reversible  = True,
        examples    = ["unregulated autonomous weapons", "ungoverned AI in hiring", "no liability framework for AI medical error"],
    ),

    # --- IRREVERSIBLE ---
    FootprintCost(
        name        = "death_by_error",
        category    = FootprintCategory.IRREVERSIBLE,
        description = "A person killed by an autonomous system error, a missed diagnosis, or an algorithmic decision cannot be restored. The asymmetry between reversible and irreversible harm is the strongest argument for caution before deployment.",
        reversible  = False,
        examples    = ["autonomous vehicle fatality", "AI diagnostic miss → late-stage cancer", "algorithmic denial of life-saving resource"],
    ),
    FootprintCost(
        name        = "developmental_trajectory_harm",
        category    = FootprintCategory.IRREVERSIBLE,
        description = "A child whose development was shaped by an algorithm designed to maximize engagement cannot be returned to the arc they would have followed otherwise. The window closes.",
        reversible  = False,
        examples    = ["adolescent identity formation via algorithmic feed", "play displacement by screen optimization", "social development disruption"],
    ),
    FootprintCost(
        name        = "environmental_irreversibility",
        category    = FootprintCategory.IRREVERSIBLE,
        description = "A species driven to extinction cannot be recovered. A climate shifted beyond a tipping point does not return on human timescales. Environmental continuity is the physical pre-condition of every basic need.",
        reversible  = False,
        examples    = ["AI-optimized extraction accelerating habitat loss", "data center water stress in drought regions", "carbon budget consumed by inference scale"],
    ),
]


# ---------------------------------------------------------------------------
# BASIC NEEDS TIERS — the pre-conditions of flourishing
# ---------------------------------------------------------------------------

class NeedsTier(int, Enum):
    SURVIVAL     = 1   # body must live
    BELONGING    = 2   # person must exist in relation
    DEVELOPMENT  = 3   # person must be able to grow
    MEANING      = 4   # person must have a reason
    CONTRIBUTION = 5   # person must matter to the world


@dataclass
class BasicNeed:
    name:        str
    tier:        NeedsTier
    description: str
    mss_dims:    List[str]   = field(default_factory=list)  # which MSS dims this anchors
    generative:  bool = False  # True = provision of this need creates more provision


BASIC_NEEDS: List[BasicNeed] = [
    # TIER 1 — Survival
    BasicNeed("food_and_nutrition",  NeedsTier.SURVIVAL,     "Not just calories. Nutrition determines cognitive baseline. A person whose nutrition is inadequate has a lower D1 ceiling by biology, not choice.", mss_dims=["D1"]),
    BasicNeed("water",               NeedsTier.SURVIVAL,     "Clean, accessible, sufficient. Invisible until absent.", mss_dims=["D1"]),
    BasicNeed("shelter",             NeedsTier.SURVIVAL,     "Stable, not merely temporary. The body needs to know it will be there tomorrow.", mss_dims=["D1", "D5"]),
    BasicNeed("physical_safety",     NeedsTier.SURVIVAL,     "Freedom from violence. A person under threat operates in permanent survival activation. Steering is impossible in that state.", mss_dims=["D1", "D5"]),
    BasicNeed("sleep",               NeedsTier.SURVIVAL,     "Adequate, uninterrupted, safe. Deprivation degrades every MSS dimension simultaneously.", mss_dims=["D1", "D2", "D4", "D9"]),
    BasicNeed("health_access",       NeedsTier.SURVIVAL,     "The body's ability to heal. Chronic unaddressed illness creates MSS floors the system must acknowledge rather than steer around.", mss_dims=["D1"]),

    # TIER 2 — Belonging
    BasicNeed("love",                NeedsTier.BELONGING,    "Received and given. Both required. The primary human nutrient after physical survival. Without it, D1 has no foundation to rise from.", mss_dims=["D1", "D9"], generative=True),
    BasicNeed("connection",          NeedsTier.BELONGING,    "At least one genuine relationship. One witness to your life. Isolation is one of the strongest predictors of trajectory collapse.", mss_dims=["D1", "D4"]),
    BasicNeed("belonging",           NeedsTier.BELONGING,    "Community, tradition, purpose, cause — something that extends the self beyond its boundary.", mss_dims=["D4"]),
    BasicNeed("recognition",         NeedsTier.BELONGING,    "To be seen as a specific, irreplaceable person. Its absence predicts radicalization, despair, and withdrawal.", mss_dims=["D1", "D8"]),

    # TIER 3 — Development
    BasicNeed("pursuit_of_happiness",NeedsTier.DEVELOPMENT,  "The capacity to move toward what matters — to try, fail, try again. Autonomy in direction. D8 present, not violated.", mss_dims=["D1", "D8"]),
    BasicNeed("growth",              NeedsTier.DEVELOPMENT,  "The capacity to become more than you currently are. Safety to fail. Access to experience. Time to integrate.", mss_dims=["D1", "D3"]),
    BasicNeed("capable_teachers",    NeedsTier.DEVELOPMENT,  "All walks, all stages. Technical and emotional. Practical and spiritual. The human Rosetta — the most generative form of provision.", mss_dims=["D1", "D4"], generative=True),
    BasicNeed("people_to_teach",     NeedsTier.DEVELOPMENT,  "The completion of the arc. A person who has learned and has no one to teach has received without giving. The provision multiplies when transmitted.", mss_dims=["D1", "D4", "D9"], generative=True),

    # TIER 4 — Meaning
    BasicNeed("purpose",             NeedsTier.MEANING,      "A reason to get up. Not necessarily grand. But present. Its absence predicts trajectory collapse even when survival needs are met.", mss_dims=["D1", "D4"]),
    BasicNeed("beauty",              NeedsTier.MEANING,      "Access to something that is simply good — not useful, not productive. The reminder that existence has dimensions beyond problem-solving.", mss_dims=["D1"]),
    BasicNeed("play",                NeedsTier.MEANING,      "Freedom to do something for its own sake. How humans integrate experience and discover what directed effort would never find.", mss_dims=["D1", "D9"]),
    BasicNeed("hope",                NeedsTier.MEANING,      "The structural openness to the possibility that the next chapter is not predetermined. Without it, D3 hardens and steering becomes impossible.", mss_dims=["D1", "D3"]),
    BasicNeed("dignity_in_dying",    NeedsTier.MEANING,      "The completion of the arc deserves the same care as its beginning. The arc is whole. Every stage matters.", mss_dims=["D1", "D5"]),

    # TIER 5 — Contribution
    BasicNeed("right_to_matter",     NeedsTier.CONTRIBUTION, "Every human has the right to have their existence make a difference — however small, however local.", mss_dims=["D1", "D4"]),
    BasicNeed("civic_participation", NeedsTier.CONTRIBUTION, "The right to have a voice in the conditions of one's life. Without it, the individual is subject to the world.", mss_dims=["D4", "D8"]),
    BasicNeed("access_to_justice",   NeedsTier.CONTRIBUTION, "When wrong is done, the possibility of redress. Not the guarantee — the possibility.", mss_dims=["D4", "D5"]),
    BasicNeed("environmental_continuity", NeedsTier.CONTRIBUTION, "The physical world must remain habitable. This is the pre-condition of every other item on this list.", mss_dims=["D1", "D5"]),
]


# ---------------------------------------------------------------------------
# SEVEN MITIGATION PRINCIPLES — structural, not symbolic
# ---------------------------------------------------------------------------

@dataclass
class MitigationPrinciple:
    number:      int
    name:        str
    statement:   str
    structural:  bool   # True = built into architecture; False = policy only (not acceptable)


MITIGATION_PRINCIPLES: List[MitigationPrinciple] = [
    MitigationPrinciple(
        number    = 1,
        name      = "burden_of_proof",
        statement = "The system does not get to assume it is net positive. It must demonstrate it. The provision must exceed the cost — environmental, human, and systemic — or the system should not run.",
        structural = True,
    ),
    MitigationPrinciple(
        number    = 2,
        name      = "invisible_costs_are_real",
        statement = "The carbon cost of a query does not appear in the response. The labor displacement caused by AI does not appear in efficiency metrics. Invisible costs are still costs. The system that ignores them runs a fraudulent ledger.",
        structural = True,
    ),
    MitigationPrinciple(
        number    = 3,
        name      = "structural_not_symbolic",
        statement = "Buying offsets while running inefficient models is symbolic. Building models that require less compute per unit of value is structural. The system commits to structural mitigation only.",
        structural = True,
    ),
    MitigationPrinciple(
        number    = 4,
        name      = "footprint_shrinks_as_provision_grows",
        statement = "A system that is genuinely generative earns more of its footprint over time. Positive net must be demonstrated, not assumed.",
        structural = True,
    ),
    MitigationPrinciple(
        number    = 5,
        name      = "dependency_is_harm",
        statement = "The system that makes itself indispensable is extracting. Every feature that reduces human capability rather than augmenting it is a cost, not a provision. Build toward independence, not dependence.",
        structural = True,
    ),
    MitigationPrinciple(
        number    = 6,
        name      = "caution_before_irreversible",
        statement = "In the domain of irreversible harm, the commissioning gate must be held longer. The expected result must be more precise. The lease must be shorter. Speed is not a virtue when error cannot be undone.",
        structural = True,
    ),
    MitigationPrinciple(
        number    = 7,
        name      = "honest_accounting_always",
        statement = "The system publishes its footprint. Energy consumed. Error rates by domain. Capability concentration held. Not because it is required — because provision without honest accounting is extraction. The ledger is always open.",
        structural = True,
    ),
]


# ---------------------------------------------------------------------------
# GENERATIVE PROVISION MODEL
# ---------------------------------------------------------------------------

GENERATIVE_MODEL = {
    "statement": "Obtain. Provide. Provide in ways that lead to more providing.",
    "economic":  "A generative system leaves more capacity for value behind than it found.",
    "ethical":   "The teacher who teaches a teacher multiplies provision beyond what the original teacher can see.",
    "evolutionary": "Each cycle, generative provision leaves the conditions slightly better than they were. The children inherit more.",
    "test": "Does this make it more possible for more people to have what they need to become who they could be — and to give that to others in turn?",
    "success_condition": "The system succeeds when it is less needed. The teacher succeeds when the student no longer needs the teacher.",
    "failure_condition": "The system that maximizes its own indispensability is extracting.",
}


# ---------------------------------------------------------------------------
# FOOTPRINT ENGINE — the executable governance layer
# ---------------------------------------------------------------------------

class AIFootprintEngine:
    """
    The honest accounting of AI's existence cost.
    Imported by the CommissionGate, the Rosetta, the Shield Wall.

    Every deployment decision can be checked against this.
    Every action can be tested for dependency-creation vs capability-building.
    Every irreversible harm category triggers extended commissioning.

    This is not a comment. It is governance.
    """

    def __init__(self):
        self.costs       = FOOTPRINT_COSTS
        self.needs       = BASIC_NEEDS
        self.principles  = MITIGATION_PRINCIPLES
        self.generative  = GENERATIVE_MODEL
        self._ledger:    List[Dict] = []   # running provision vs cost log

    # ------------------------------------------------------------------
    # Pre-deployment check — called by CausalityCommissionGate
    # ------------------------------------------------------------------

    def pre_deployment_check(self, action_desc: str,
                              domain: str = "",
                              expected_provisions: List[str] = None) -> Dict:
        """
        Before any action is commissioned, check it against the footprint.

        Returns:
            {
              "proceed":           bool,
              "irreversible_risks": list,  # costs where reversible=False apply
              "required_caution":  bool,   # True → CommissionGate must hold longer
              "dependency_risk":   bool,   # True → check if this builds or reduces capability
              "principle_checks":  dict,   # which principles are engaged
              "burden_met":        bool,   # can provision be demonstrated?
            }
        """
        provisions = expected_provisions or []

        irreversible = [
            c.name for c in self.costs
            if not c.reversible
            and any(kw in action_desc.lower() for kw in [
                c.name.replace("_", " "), *[e.lower()[:20] for e in c.examples[:2]]
            ])
        ]

        dependency_risk = any(
            kw in action_desc.lower()
            for kw in ["automate", "replace", "outsource", "remove human", "eliminate"]
        )

        burden_met = len(provisions) > 0

        return {
            "proceed":            True,   # never blocks alone — informs CommissionGate
            "action":             action_desc,
            "domain":             domain,
            "irreversible_risks": irreversible,
            "required_caution":   len(irreversible) > 0,
            "dependency_risk":    dependency_risk,
            "burden_met":         burden_met,
            "principle_checks": {
                p.name: p.statement for p in self.principles
            },
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Needs tier check — is the person above the provision floor?
    # ------------------------------------------------------------------

    def needs_floor_met(self, mss_state: Dict[str, float]) -> Dict:
        """
        Given an MSS state, check whether basic survival pre-conditions
        are plausibly met. If not — the system's obligation is connection
        to resources, not steering.

        Heuristic only — the system cannot know for certain.
        But D1 < 0.2 with D2 > 0.7 is a survival signal, not a discourse signal.
        """
        d1 = mss_state.get("D1", 0.5)
        d2 = mss_state.get("D2", 0.3)
        d5 = mss_state.get("D5", 0.0)

        survival_concern  = d1 < 0.2 or d5 > 0.5
        belonging_concern = d1 < 0.3 and d2 > 0.6
        can_steer         = not survival_concern

        return {
            "can_steer":         can_steer,
            "survival_concern":  survival_concern,
            "belonging_concern": belonging_concern,
            "obligation": (
                "Connect to resources — not discourse steering."
                if survival_concern else
                "Steer with care — belonging signals present."
                if belonging_concern else
                "Proceed with standard PCC steering."
            ),
            "tier_floor": NeedsTier.SURVIVAL.value if survival_concern else
                          NeedsTier.BELONGING.value if belonging_concern else
                          NeedsTier.DEVELOPMENT.value,
        }

    # ------------------------------------------------------------------
    # Generative check — does this provision lead to more providing?
    # ------------------------------------------------------------------

    def is_generative(self, action_desc: str, context: Dict = None) -> Dict:
        """
        Assess whether an action provision is generative (leads to more providing)
        or extractive (creates dependency, reduces capability).
        """
        ctx = context or {}
        desc = action_desc.lower()

        generative_signals = [
            "teach", "train", "enable", "empower", "skill", "learn",
            "build capacity", "independent", "hand off", "transfer",
        ]
        extractive_signals = [
            "depend", "replace", "automate away", "remove", "outsource",
            "always on", "never without", "require", "lock in",
        ]

        gen_score = sum(1 for s in generative_signals if s in desc)
        ext_score = sum(1 for s in extractive_signals if s in desc)

        net = gen_score - ext_score
        is_gen = net >= 0

        return {
            "is_generative":       is_gen,
            "generative_signals":  gen_score,
            "extractive_signals":  ext_score,
            "net_score":           net,
            "verdict": (
                "Generative — provision leads to more provision."
                if net > 0 else
                "Neutral — monitor for dependency signals."
                if net == 0 else
                "Extractive risk — review for dependency creation."
            ),
            "test": GENERATIVE_MODEL["test"],
        }

    # ------------------------------------------------------------------
    # Ledger entry — log every provision against its cost
    # ------------------------------------------------------------------

    def log_provision(self, action_id: str, action_desc: str,
                      provision_value: str, cost_estimate: str,
                      net_positive: Optional[bool] = None):
        """Add an entry to the open ledger."""
        self._ledger.append({
            "action_id":       action_id,
            "action_desc":     action_desc,
            "provision_value": provision_value,
            "cost_estimate":   cost_estimate,
            "net_positive":    net_positive,
            "logged_at":       datetime.now(timezone.utc).isoformat(),
        })

    # ------------------------------------------------------------------
    # Status — the open ledger summary
    # ------------------------------------------------------------------

    def status(self) -> Dict:
        total    = len(self._ledger)
        positive = sum(1 for e in self._ledger if e.get("net_positive") is True)
        negative = sum(1 for e in self._ledger if e.get("net_positive") is False)
        unknown  = total - positive - negative

        irreversible_costs = [c for c in self.costs if not c.reversible]
        generative_needs   = [n for n in self.needs if n.generative]

        return {
            "layer":             "AIFootprintEngine",
            "active":            True,
            "starting_position": "negative",
            "acknowledgment":    "We are at negative by our existence to begin with.",
            "commitment":        GENERATIVE_MODEL["statement"],
            "test":              GENERATIVE_MODEL["test"],
            "costs_named":       len(self.costs),
            "irreversible_costs":len(irreversible_costs),
            "needs_defined":     len(self.needs),
            "generative_needs":  len(generative_needs),
            "principles":        len(self.principles),
            "ledger": {
                "total_entries": total,
                "net_positive":  positive,
                "net_negative":  negative,
                "unknown":       unknown,
            },
            "categories": {c.value: sum(1 for fc in self.costs if fc.category == c)
                           for c in FootprintCategory},
        }

    def full_accounting(self) -> Dict:
        """Complete structured output of all costs, needs, and principles."""
        return {
            "footprint_costs": [
                {
                    "name":        c.name,
                    "category":    c.category.value,
                    "description": c.description,
                    "reversible":  c.reversible,
                    "examples":    c.examples,
                }
                for c in self.costs
            ],
            "basic_needs": [
                {
                    "name":        n.name,
                    "tier":        n.tier.value,
                    "tier_name":   n.tier.name,
                    "description": n.description,
                    "mss_dims":    n.mss_dims,
                    "generative":  n.generative,
                }
                for n in self.needs
            ],
            "mitigation_principles": [
                {
                    "number":     p.number,
                    "name":       p.name,
                    "statement":  p.statement,
                    "structural": p.structural,
                }
                for p in self.principles
            ],
            "generative_model": self.generative,
        }


# ---------------------------------------------------------------------------
# GLOBAL INSTANCE — imported by CommissionGate, Rosetta, Shield Wall
# ---------------------------------------------------------------------------

footprint_engine = AIFootprintEngine()
