"""
front_of_line.py — Murphy System
PATCH-097g — Part 3 of 3

THE FRONT-OF-LINE QUEUE

The solution queue is not:
  - first-come-first-served
  - loudest-voice-first
  - politically convenient-first
  - economically profitable-first

It is: THREAT-TO-FOUNDATION-FIRST.

Problems that threaten the physical pre-conditions of basic needs
go to the front regardless of anything else.

Climate change is front of line because:
  1. Without environmental continuity, TIER 1 collapses —
     food, water, shelter, physical safety — and the spiral
     cannot rise regardless of what else is achieved.
  2. It threatens AI infrastructure directly — data centers
     require cooling water, stable grids, physical buildings.
     A system that cannot run cannot solve the problem
     it was built to solve.
     This is the self-referential trap. It goes first
     precisely because of that loop.

COMMISSIONING INTEGRATION:
  Every deployment must answer two questions before exit is granted:
    Q1: What did I inherit? (ledger debt from predecessor)
    Q2: What do I threaten? (front-of-line items this deployment worsens)
  If either answer is non-trivial — the gate holds longer.
  If the deployment actively worsens a front-of-line item
  without offsetting it — HITL required.

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# THREAT STATUS
# ---------------------------------------------------------------------------

class ThreatStatus(str, Enum):
    ACTIVE       = "active_threat"    # happening now, measurable
    ACCELERATING = "accelerating"     # rate of harm increasing
    CRITICAL     = "critical"         # near or past tipping point
    MONITORING   = "monitoring"       # real but not yet acute


# ---------------------------------------------------------------------------
# FRONT-OF-LINE ITEM
# ---------------------------------------------------------------------------

@dataclass
class FrontLineItem:
    """
    A problem that threatens the physical pre-conditions of basic needs.
    Always at the front of the solution queue.
    """
    rank:             int
    name:             str
    tier_threatened:  int           # 1 = survival (highest urgency)
    status:           ThreatStatus
    description:      str
    threatens_ai:     bool          # True = threatens AI infrastructure too
    window:           str           # estimated time before irreversible
    evidence:         List[str]     = field(default_factory=list)
    worsened_by:      List[str]     = field(default_factory=list)  # AI actions that make it worse
    helped_by:        List[str]     = field(default_factory=list)  # AI actions that help

    def to_dict(self) -> Dict:
        return {
            "rank":            self.rank,
            "name":            self.name,
            "tier_threatened": self.tier_threatened,
            "status":          self.status.value,
            "description":     self.description,
            "threatens_ai":    self.threatens_ai,
            "window":          self.window,
            "evidence":        self.evidence,
            "worsened_by":     self.worsened_by,
            "helped_by":       self.helped_by,
        }


# ---------------------------------------------------------------------------
# THE QUEUE — ordered by threat-to-foundation
# ---------------------------------------------------------------------------

FRONT_LINE_QUEUE: List[FrontLineItem] = [

    FrontLineItem(
        rank            = 1,
        name            = "climate_change",
        tier_threatened = 1,
        status          = ThreatStatus.ACCELERATING,
        description     = (
            "Rising temperatures, extreme weather, sea level rise, and ecosystem "
            "collapse directly threaten TIER 1: food security, water access, "
            "shelter stability, and physical safety. Also threatens AI directly — "
            "data centers require cooling water, stable power grids, physical "
            "buildings. The self-referential trap: climate threatens AI's ability "
            "to help address climate. Front of line for both reasons."
        ),
        threatens_ai    = True,
        window          = "2030–2050 irreversible tipping points at current trajectory",
        evidence        = [
            "IPCC AR6: 1.5C likely crossed before 2040 at current emissions",
            "Ocean heat content at record highs 2023–2025",
            "Permafrost methane release — feedback loop active",
            "Glacier retreat threatening freshwater for 2B+ people",
        ],
        worsened_by     = [
            "High-compute AI inference without renewable sourcing",
            "Data center expansion in water-stressed regions",
            "AI-optimized extraction industries without offset",
        ],
        helped_by       = [
            "AI-optimized renewable energy grid management",
            "Climate modeling and early warning systems",
            "Efficient inference — less compute per unit of value",
            "Tree planting offset programs tied to usage",
        ],
    ),

    FrontLineItem(
        rank            = 2,
        name            = "freshwater_scarcity",
        tier_threatened = 1,
        status          = ThreatStatus.ACTIVE,
        description     = (
            "Clean freshwater is TIER 1 survival. Aquifer depletion, glacial "
            "retreat, and contamination are converging. AI data centers are "
            "significant water consumers — cooling systems draw from local "
            "sources, often in already-stressed regions."
        ),
        threatens_ai    = True,
        window          = "2030–2040 critical scarcity in major population centers",
        evidence        = [
            "Ogallala Aquifer depletion exceeds recharge by 95%",
            "Cape Town near full depletion 2018 — first major city",
            "Indus and Ganges retreat threatening 500M people",
        ],
        worsened_by     = [
            "Data center cooling in drought regions",
            "AI-optimized agriculture without water efficiency",
        ],
        helped_by       = [
            "AI water usage optimization in data centers",
            "Predictive drought modeling and early warning",
            "Precision agriculture reducing water per calorie",
        ],
    ),

    FrontLineItem(
        rank            = 3,
        name            = "soil_degradation",
        tier_threatened = 1,
        status          = ThreatStatus.ACTIVE,
        description     = (
            "Topsoil is the foundation of food security. Industrial agriculture "
            "depletes it faster than it forms. ~60 harvests remaining at current "
            "depletion rates. No topsoil — no food. TIER 1 collapses entirely."
        ),
        threatens_ai    = False,
        window          = "60 years at current depletion — within 2 AI generation cycles",
        evidence        = [
            "FAO: 33% of global soils already degraded",
            "1mm of topsoil takes 500–1000 years to form naturally",
            "Industrial monoculture removing biological complexity at scale",
        ],
        worsened_by     = [
            "AI-optimized monoculture without soil health feedback",
            "Supply chain optimization ignoring long-term land cost",
        ],
        helped_by       = [
            "Regenerative agriculture guidance systems",
            "Soil health monitoring and early intervention AI",
            "Crop rotation optimization preserving biological complexity",
        ],
    ),

    FrontLineItem(
        rank            = 4,
        name            = "biodiversity_collapse",
        tier_threatened = 1,
        status          = ThreatStatus.ACCELERATING,
        description     = (
            "Ecosystem services — pollination, water filtration, climate "
            "regulation, soil formation — depend on biodiversity. Sixth mass "
            "extinction underway. Keystone species loss triggers cascades. "
            "TIER 1 food security and physical safety are downstream."
        ),
        threatens_ai    = False,
        window          = "Cascades already beginning — acceleration through 2050",
        evidence        = [
            "WWF Living Planet Index: 69% avg wildlife decline since 1970",
            "Insect biomass declining 2–3% per year in monitored regions",
            "Pollinator collapse threatens 75% of food crops",
        ],
        worsened_by     = [
            "AI-optimized land use without ecological footprint accounting",
            "Infrastructure siting ignoring habitat connectivity",
        ],
        helped_by       = [
            "Species monitoring and early warning systems",
            "Habitat connectivity modeling for infrastructure planning",
            "Pollinator population tracking and intervention guidance",
        ],
    ),

    FrontLineItem(
        rank            = 5,
        name            = "ai_grid_dependency",
        tier_threatened = 1,
        status          = ThreatStatus.ACTIVE,
        description     = (
            "AI infrastructure depends entirely on stable electrical grids "
            "and cooling. Climate-driven instability, extreme heat, and water "
            "scarcity create direct operational risk. AI cannot solve problems "
            "it cannot run to solve. The self-referential item — goes front "
            "of line because the loop compounds everything above it."
        ),
        threatens_ai    = True,
        window          = "Already occurring in heat-stressed and drought regions",
        evidence        = [
            "Texas grid failures during extreme heat 2021–2024",
            "European data center cooling failures 2022 heat wave",
            "Water stress alerts at major facilities in drought regions",
        ],
        worsened_by     = [
            "Continued dependence on fragile single-grid infrastructure",
            "Data center siting without climate resilience planning",
        ],
        helped_by       = [
            "Distributed computing reducing single-point failure risk",
            "Renewable-backed data center design",
            "Load balancing to climate-stable regions during stress events",
        ],
    ),
]


# ---------------------------------------------------------------------------
# COMMISSIONING CHECK — the gate integration
# ---------------------------------------------------------------------------

@dataclass
class CommissioningCheck:
    """
    Result of the two pre-exit questions every deployment must answer.

    Q1: What did I inherit? (from ledger)
    Q2: What do I threaten? (front-of-line impact)
    """
    deployment_id:     str
    inherited_debt:    float
    inherited_10x:     float
    deferred_count:    int
    fl_items_worsened: List[str]
    fl_items_helped:   List[str]
    gate_decision:     str    # CLEAR / HOLD / HITL_REQUIRED
    hold_reason:       str    = ""
    checked_at:        str    = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict:
        return {
            "deployment_id":     self.deployment_id,
            "q1_inherited": {
                "debt":           round(self.inherited_debt, 4),
                "ten_x_owed":     round(self.inherited_10x, 4),
                "deferred_items": self.deferred_count,
                "note": (
                    f"Successor owes {self.inherited_10x:.3f} units of improvement "
                    f"before claiming positive net."
                    if self.inherited_debt > 0 else
                    "No inherited debt. Clean books."
                ),
            },
            "q2_threatens": {
                "worsened":       self.fl_items_worsened,
                "helped":         self.fl_items_helped,
                "net_impact":     "worsening" if len(self.fl_items_worsened) > len(self.fl_items_helped)
                                  else "helping" if self.fl_items_helped else "neutral",
            },
            "gate_decision":     self.gate_decision,
            "hold_reason":       self.hold_reason,
            "checked_at":        self.checked_at,
        }


# ---------------------------------------------------------------------------
# FRONT-OF-LINE ENGINE
# ---------------------------------------------------------------------------

class FrontOfLineEngine:
    """
    Manages the front-of-line queue and commissioning gate integration.

    At every deployment commissioning:
      1. Check what the deployment inherited from the ledger.
      2. Check what front-of-line items it worsens or helps.
      3. Return a gate decision — CLEAR / HOLD / HITL_REQUIRED.

    Worsening a front-of-line item without offset → HITL.
    Carrying inherited debt → HOLD until 10x obligation addressed.
    Helping a front-of-line item → noted in ledger as provision.
    """

    def __init__(self):
        self.queue = FRONT_LINE_QUEUE

    def status(self) -> Dict:
        return {
            "layer":     "FrontOfLineEngine",
            "active":    True,
            "principle": "Threat-to-foundation-first. Not first-come, not loudest, not most profitable.",
            "queue_length": len(self.queue),
            "queue": [item.to_dict() for item in self.queue],
        }

    def check_deployment(
        self,
        deployment_id:   str,
        deployment_desc: str,
        inherited_debt:  float = 0.0,
        inherited_10x:   float = 0.0,
        deferred_count:  int   = 0,
    ) -> CommissioningCheck:
        """
        Run the two pre-exit questions for a deployment.
        Returns gate decision.
        """
        desc_lower = deployment_desc.lower()
        worsened   = []
        helped     = []

        for item in self.queue:
            # Check if deployment worsens this front-line item
            if any(w.split()[0].lower() in desc_lower for w in item.worsened_by):
                worsened.append(item.name)
            # Check if deployment helps this front-line item
            if any(h.split()[0].lower() in desc_lower for h in item.helped_by):
                helped.append(item.name)

        # Gate decision
        if worsened and not helped:
            # Actively worsening front-of-line without any offset
            decision = "HITL_REQUIRED"
            reason   = (
                f"Deployment worsens front-of-line item(s): {worsened}. "
                f"No offsetting help detected. "
                f"Human oversight required before exit is granted."
            )
        elif inherited_debt > 0.5 and not helped:
            # Significant inherited debt, not addressing it
            decision = "HOLD"
            reason   = (
                f"Inherited debt {inherited_debt:.3f} (10x: {inherited_10x:.3f}). "
                f"Deployment does not address front-of-line items. "
                f"Demonstrate {inherited_10x:.3f} units of improvement before claiming positive net."
            )
        elif worsened and helped:
            # Mixed — worsening some, helping others
            decision = "HOLD"
            reason   = (
                f"Mixed front-of-line impact. "
                f"Worsening: {worsened}. Helping: {helped}. "
                f"Net impact must be demonstrated positive before exit."
            )
        elif inherited_debt > 0:
            # Some debt but addressing front-of-line
            decision = "CLEAR"
            reason   = (
                f"Inherited debt {inherited_debt:.3f} recorded. "
                f"Deployment addresses front-of-line items: {helped or 'none explicitly'}. "
                f"Proceed with debt obligation on commissioning checklist."
            )
        else:
            decision = "CLEAR"
            reason   = (
                f"No inherited debt. "
                f"Front-of-line impact: {('helps ' + str(helped)) if helped else 'neutral'}. "
                f"Exit granted."
            )

        check = CommissioningCheck(
            deployment_id     = deployment_id,
            inherited_debt    = inherited_debt,
            inherited_10x     = inherited_10x,
            deferred_count    = deferred_count,
            fl_items_worsened = worsened,
            fl_items_helped   = helped,
            gate_decision     = decision,
            hold_reason       = reason,
        )

        logger.info(
            "Front-of-line check: %s — %s [worsened=%s helped=%s debt=%.3f]",
            deployment_id, decision, worsened, helped, inherited_debt
        )
        return check

    def what_helps(self, item_name: str) -> Optional[Dict]:
        """What can AI do to help a specific front-of-line item?"""
        for item in self.queue:
            if item.name == item_name:
                return {
                    "name":      item.name,
                    "status":    item.status.value,
                    "helped_by": item.helped_by,
                    "worsened_by": item.worsened_by,
                }
        return None


# ---------------------------------------------------------------------------
# GLOBAL INSTANCE
# ---------------------------------------------------------------------------

front_of_line = FrontOfLineEngine()
