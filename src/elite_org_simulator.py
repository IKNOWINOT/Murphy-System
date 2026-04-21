"""
Elite Org Simulator — Murphy System
====================================

Simulates complete organisational charts where every role is staffed with the
**best-of-class** skill genome for that position.  Each role carries:

  * A **skill genome** — 10 quantified competency scores at the 95th-percentile
    industry benchmark for that role.
  * A **KAIA personality mix** — the optimal analytical / decisive / empathetic /
    creative / technical blend for that function.
  * An **influence framework stack** — the Cialdini / Carnegie / Covey / NLP
    frameworks that drive communication in that role.
  * **Cross-functional bonds** — which roles this role must collaborate with and
    how frequently.

The simulator then drives the org through configurable **scenarios** (product
launch, revenue crisis, scaling sprint, market entry, etc.) using the existing
Murphy multi-cursor split-screen and swarm infrastructure:

  1. ``EliteOrgChart``    — builds the full hierarchy (C-suite → VP → Director
                             → Manager → IC) for a given company stage.
  2. ``OrgScenario``      — a named business scenario with role-specific tasks.
  3. ``SwarmOrgRunner``   — maps departments to ``SplitScreenLayout`` zones,
                             dispatches tasks to a ``MultiCursorDesktop``, and
                             collects per-role + per-department performance scores.
  4. ``EliteOrgSimulator``— top-level façade: build chart → choose scenario →
                             run → score → recommend gaps.
  5. ``HistoricalGreatnessEngine`` integration — every role is calibrated
                             against the 10 universal traits of historical
                             greatness and matched to a historical archetype.

Design Label: SIM-001 — Elite Org Simulation
Owner:        Platform Engineering
License:      BSL 1.1

Copyright © 2020 Inoni Limited Liability Company
Creator:      Corey Post
"""

from __future__ import annotations

import logging
import math
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

try:
    from thread_safe_operations import capped_append
except ImportError:  # pragma: no cover
    def capped_append(lst: list, item: Any, max_size: int = 10_000) -> None:
        if len(lst) >= max_size:
            del lst[: max_size // 10]
        lst.append(item)

try:
    from murphy_native_automation import (
        MultiCursorDesktop,
        SplitScreenLayout,
        SplitScreenManager,
        ScreenZone,
        NativeTask,
        NativeStep,
        ActionType,
    )
    _HAS_NATIVE = True
except ImportError:  # pragma: no cover
    _HAS_NATIVE = False
    MultiCursorDesktop = None  # type: ignore[assignment,misc]
    SplitScreenLayout = None  # type: ignore[assignment,misc]
    SplitScreenManager = None  # type: ignore[assignment,misc]

try:
    from historical_greatness_engine import HistoricalGreatnessEngine as _HGE
    _HAS_HGE = True
except ImportError:  # pragma: no cover
    _HAS_HGE = False
    _HGE = None  # type: ignore[assignment,misc]

try:
    from agent_persona_library._frameworks import _build_influence_frameworks
    _FRAMEWORKS = _build_influence_frameworks()
except Exception:  # pragma: no cover
    _FRAMEWORKS = {}

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class Department(str, Enum):
    EXECUTIVE      = "executive"
    ENGINEERING    = "engineering"
    PRODUCT        = "product"
    SALES          = "sales"
    MARKETING      = "marketing"
    CUSTOMER_SUCCESS = "customer_success"
    FINANCE        = "finance"
    LEGAL          = "legal"
    PEOPLE_OPS     = "people_ops"


class Seniority(str, Enum):
    IC         = "ic"           # individual contributor
    SENIOR_IC  = "senior_ic"
    LEAD       = "lead"
    MANAGER    = "manager"
    DIRECTOR   = "director"
    VP         = "vp"
    C_SUITE    = "c_suite"


class CompanyStage(str, Enum):
    SEED        = "seed"        #  1–10 people
    SERIES_A    = "series_a"    # 11–50
    SERIES_B    = "series_b"    # 51–150
    GROWTH      = "growth"      # 151–500
    ENTERPRISE  = "enterprise"  # 500+


class ScenarioType(str, Enum):
    PRODUCT_LAUNCH       = "product_launch"
    REVENUE_CRISIS       = "revenue_crisis"
    SCALING_SPRINT       = "scaling_sprint"
    MARKET_ENTRY         = "market_entry"
    TECHNICAL_MIGRATION  = "technical_migration"
    FUNDRAISE            = "fundraise"
    COMPETITIVE_RESPONSE = "competitive_response"
    TALENT_SURGE         = "talent_surge"


# ---------------------------------------------------------------------------
# Skill Genome
# ---------------------------------------------------------------------------

# Competency dimensions used across all roles (scale 0–1, 1.0 = top 1%)
COMPETENCY_DIMENSIONS = [
    "strategic_thinking",    # sees 3-5 year horizon, builds roadmaps
    "execution_speed",       # ships fast without sacrificing quality
    "technical_depth",       # domain-specific hard skills
    "communication_clarity", # crisp written + verbal comms
    "data_fluency",          # reads numbers, builds models, runs experiments
    "customer_empathy",      # deeply understands user/buyer pain
    "leadership_presence",   # inspires, unblocks, decides under ambiguity
    "cross_functional",      # bridges gaps between departments
    "persuasion_influence",  # moves people, builds consensus
    "adaptability",          # pivots gracefully when context changes
]

# Elite (95th-percentile) benchmark for every role class.
# Scores are per-dimension in the order of COMPETENCY_DIMENSIONS.
_ELITE_GENOMES: Dict[str, List[float]] = {
    # C-Suite -----------------------------------------------------------
    "ceo":  [0.98, 0.90, 0.70, 0.95, 0.88, 0.92, 0.99, 0.97, 0.98, 0.96],
    "cto":  [0.95, 0.92, 0.99, 0.88, 0.96, 0.78, 0.95, 0.90, 0.82, 0.93],
    "cro":  [0.92, 0.95, 0.72, 0.94, 0.90, 0.88, 0.92, 0.91, 0.98, 0.90],
    "cfo":  [0.95, 0.88, 0.88, 0.90, 0.99, 0.72, 0.90, 0.88, 0.85, 0.88],
    "cmo":  [0.90, 0.90, 0.75, 0.97, 0.92, 0.95, 0.88, 0.90, 0.95, 0.92],
    "cpo":  [0.95, 0.88, 0.85, 0.93, 0.90, 0.97, 0.90, 0.95, 0.88, 0.92],
    "coo":  [0.90, 0.97, 0.80, 0.90, 0.93, 0.85, 0.92, 0.97, 0.88, 0.94],
    "clo":  [0.88, 0.82, 0.95, 0.93, 0.90, 0.75, 0.85, 0.88, 0.85, 0.88],
    "chro": [0.88, 0.85, 0.78, 0.95, 0.85, 0.97, 0.90, 0.95, 0.92, 0.92],
    # VP layer ----------------------------------------------------------
    "vp_engineering":       [0.90, 0.93, 0.97, 0.88, 0.92, 0.80, 0.92, 0.88, 0.82, 0.90],
    "vp_product":           [0.92, 0.88, 0.82, 0.92, 0.88, 0.95, 0.88, 0.92, 0.85, 0.90],
    "vp_sales":             [0.88, 0.95, 0.72, 0.93, 0.88, 0.90, 0.88, 0.85, 0.97, 0.90],
    "vp_marketing":         [0.85, 0.90, 0.75, 0.95, 0.90, 0.93, 0.85, 0.88, 0.92, 0.88],
    "vp_customer_success":  [0.82, 0.88, 0.75, 0.95, 0.85, 0.97, 0.85, 0.90, 0.90, 0.88],
    "vp_finance":           [0.90, 0.85, 0.88, 0.88, 0.98, 0.72, 0.85, 0.85, 0.82, 0.85],
    "vp_data":              [0.88, 0.88, 0.95, 0.88, 0.99, 0.78, 0.82, 0.88, 0.80, 0.88],
    "vp_people":            [0.85, 0.85, 0.75, 0.93, 0.82, 0.97, 0.88, 0.92, 0.90, 0.90],
    # Director layer ----------------------------------------------------
    "director_engineering": [0.85, 0.92, 0.95, 0.85, 0.88, 0.78, 0.88, 0.85, 0.80, 0.88],
    "director_product":     [0.88, 0.85, 0.80, 0.88, 0.85, 0.92, 0.82, 0.88, 0.82, 0.88],
    "director_sales":       [0.82, 0.92, 0.70, 0.90, 0.85, 0.88, 0.82, 0.82, 0.95, 0.88],
    "director_marketing":   [0.82, 0.88, 0.72, 0.92, 0.88, 0.90, 0.80, 0.85, 0.90, 0.85],
    "director_finance":     [0.88, 0.82, 0.85, 0.85, 0.97, 0.70, 0.80, 0.82, 0.78, 0.82],
    "director_cs":          [0.78, 0.85, 0.72, 0.92, 0.82, 0.95, 0.80, 0.88, 0.88, 0.85],
    # Manager layer -----------------------------------------------------
    "engineering_manager":  [0.80, 0.90, 0.92, 0.85, 0.85, 0.78, 0.85, 0.82, 0.78, 0.85],
    "product_manager":      [0.85, 0.85, 0.78, 0.88, 0.85, 0.92, 0.78, 0.88, 0.82, 0.85],
    "sales_manager":        [0.78, 0.92, 0.68, 0.88, 0.82, 0.88, 0.78, 0.80, 0.95, 0.85],
    "marketing_manager":    [0.78, 0.88, 0.72, 0.92, 0.88, 0.88, 0.75, 0.82, 0.88, 0.85],
    "cs_manager":           [0.75, 0.85, 0.70, 0.90, 0.80, 0.95, 0.78, 0.85, 0.85, 0.85],
    # Senior IC ---------------------------------------------------------
    "senior_software_engineer":   [0.78, 0.92, 0.98, 0.82, 0.88, 0.70, 0.75, 0.80, 0.72, 0.88],
    "senior_frontend_engineer":   [0.75, 0.90, 0.95, 0.85, 0.85, 0.80, 0.72, 0.78, 0.72, 0.85],
    "senior_data_engineer":       [0.78, 0.88, 0.97, 0.80, 0.97, 0.72, 0.72, 0.78, 0.70, 0.85],
    "senior_ml_engineer":         [0.82, 0.85, 0.99, 0.80, 0.98, 0.72, 0.72, 0.78, 0.70, 0.85],
    "senior_infra_engineer":      [0.78, 0.92, 0.97, 0.80, 0.90, 0.68, 0.72, 0.78, 0.68, 0.88],
    "senior_account_executive":   [0.75, 0.92, 0.70, 0.92, 0.85, 0.90, 0.72, 0.78, 0.97, 0.88],
    "senior_designer":            [0.80, 0.85, 0.90, 0.92, 0.80, 0.93, 0.72, 0.78, 0.75, 0.88],
    "senior_analyst":             [0.82, 0.82, 0.90, 0.85, 0.97, 0.78, 0.72, 0.82, 0.75, 0.85],
    "senior_recruiter":           [0.75, 0.88, 0.75, 0.92, 0.80, 0.93, 0.72, 0.85, 0.88, 0.88],
    # IC ----------------------------------------------------------------
    "software_engineer":   [0.72, 0.88, 0.92, 0.78, 0.82, 0.68, 0.68, 0.75, 0.68, 0.82],
    "frontend_engineer":   [0.70, 0.85, 0.88, 0.82, 0.80, 0.78, 0.65, 0.72, 0.68, 0.80],
    "sdr":                 [0.68, 0.92, 0.65, 0.88, 0.78, 0.85, 0.65, 0.72, 0.92, 0.85],
    "account_executive":   [0.72, 0.90, 0.68, 0.90, 0.82, 0.88, 0.68, 0.75, 0.95, 0.85],
    "content_writer":      [0.72, 0.85, 0.72, 0.95, 0.80, 0.88, 0.65, 0.72, 0.78, 0.82],
    "data_analyst":        [0.78, 0.80, 0.88, 0.82, 0.95, 0.75, 0.65, 0.78, 0.70, 0.80],
    "customer_success":    [0.70, 0.82, 0.68, 0.90, 0.78, 0.95, 0.65, 0.82, 0.82, 0.82],
    "legal_counsel":       [0.82, 0.78, 0.93, 0.88, 0.85, 0.70, 0.75, 0.82, 0.78, 0.80],
    "finance_analyst":     [0.82, 0.78, 0.85, 0.82, 0.95, 0.68, 0.68, 0.78, 0.72, 0.78],
}

# Influence frameworks assigned to each role class (ordered: most → least active)
_ROLE_FRAMEWORKS: Dict[str, List[str]] = {
    "ceo":              ["cialdini_authority", "covey_begin_with_end", "covey_think_win_win", "nlp_future_pacing"],
    "cto":              ["covey_begin_with_end", "cialdini_authority", "nlp_pacing_leading", "habit_tiny_habits"],
    "cro":              ["cialdini_scarcity", "cialdini_authority", "carnegie_arouse_eager_want", "covey_think_win_win"],
    "cfo":              ["cialdini_authority", "covey_begin_with_end", "nlp_anchoring", "habit_tiny_habits"],
    "cmo":              ["cialdini_social_proof", "carnegie_feel_important", "nlp_future_pacing", "habit_variable_reward"],
    "cpo":              ["covey_seek_to_understand", "nlp_pacing_leading", "carnegie_become_interested", "nlp_future_pacing"],
    "coo":              ["covey_begin_with_end", "habit_tiny_habits", "nlp_anchoring", "cialdini_commitment_consistency"],
    "clo":              ["cialdini_authority", "nlp_anchoring", "covey_think_win_win", "carnegie_never_criticize"],
    "chro":             ["covey_seek_to_understand", "carnegie_honest_appreciation", "nlp_future_pacing", "habit_habit_stacking"],
    "vp_engineering":   ["covey_begin_with_end", "habit_tiny_habits", "cialdini_commitment_consistency", "nlp_pacing_leading"],
    "vp_product":       ["covey_seek_to_understand", "nlp_future_pacing", "carnegie_become_interested", "habit_habit_stacking"],
    "vp_sales":         ["cialdini_scarcity", "carnegie_arouse_eager_want", "nlp_pacing_leading", "cialdini_social_proof"],
    "vp_marketing":     ["cialdini_social_proof", "carnegie_feel_important", "habit_variable_reward", "nlp_anchoring"],
    "vp_customer_success": ["carnegie_honest_appreciation", "covey_seek_to_understand", "nlp_future_pacing", "habit_habit_stacking"],
    "vp_finance":       ["cialdini_authority", "covey_begin_with_end", "habit_tiny_habits", "nlp_anchoring"],
    "vp_data":          ["cialdini_authority", "habit_tiny_habits", "nlp_anchoring", "covey_synergize"],
    "vp_people":        ["carnegie_honest_appreciation", "covey_seek_to_understand", "nlp_future_pacing", "habit_habit_stacking"],
    "engineering_manager": ["habit_tiny_habits", "covey_think_win_win", "carnegie_never_criticize", "nlp_pacing_leading"],
    "product_manager":  ["covey_seek_to_understand", "carnegie_become_interested", "nlp_future_pacing", "habit_habit_stacking"],
    "sales_manager":    ["carnegie_arouse_eager_want", "cialdini_commitment_consistency", "nlp_pacing_leading", "habit_variable_reward"],
    "marketing_manager":["cialdini_social_proof", "habit_variable_reward", "nlp_anchoring", "carnegie_feel_important"],
    "cs_manager":       ["carnegie_honest_appreciation", "nlp_future_pacing", "covey_seek_to_understand", "habit_habit_stacking"],
    "senior_software_engineer": ["habit_tiny_habits", "nlp_anchoring", "covey_synergize", "cialdini_commitment_consistency"],
    "senior_frontend_engineer": ["habit_tiny_habits", "nlp_anchoring", "covey_synergize", "carnegie_become_interested"],
    "senior_data_engineer": ["habit_tiny_habits", "cialdini_authority", "nlp_anchoring", "covey_synergize"],
    "senior_ml_engineer":   ["cialdini_authority", "habit_tiny_habits", "nlp_anchoring", "covey_synergize"],
    "senior_infra_engineer":["habit_tiny_habits", "cialdini_authority", "nlp_anchoring", "cialdini_commitment_consistency"],
    "senior_account_executive": ["cialdini_scarcity", "nlp_pacing_leading", "carnegie_arouse_eager_want", "cialdini_social_proof"],
    "senior_designer":      ["carnegie_feel_important", "nlp_future_pacing", "habit_variable_reward", "carnegie_become_interested"],
    "senior_analyst":       ["cialdini_authority", "nlp_anchoring", "habit_tiny_habits", "covey_synergize"],
    "senior_recruiter":     ["carnegie_honest_appreciation", "nlp_future_pacing", "cialdini_liking", "habit_habit_stacking"],
    "software_engineer":    ["habit_tiny_habits", "nlp_anchoring", "covey_synergize", "cialdini_commitment_consistency"],
    "frontend_engineer":    ["habit_tiny_habits", "nlp_anchoring", "covey_synergize", "carnegie_become_interested"],
    "sdr":                  ["cialdini_reciprocity", "nlp_pacing_leading", "mentalism_hot_reading", "carnegie_feel_important"],
    "account_executive":    ["cialdini_scarcity", "nlp_pacing_leading", "carnegie_arouse_eager_want", "cialdini_social_proof"],
    "content_writer":       ["carnegie_feel_important", "habit_variable_reward", "nlp_future_pacing", "cialdini_liking"],
    "data_analyst":         ["cialdini_authority", "nlp_anchoring", "habit_tiny_habits", "covey_synergize"],
    "customer_success":     ["carnegie_honest_appreciation", "nlp_future_pacing", "covey_seek_to_understand", "habit_habit_stacking"],
    "legal_counsel":        ["cialdini_authority", "nlp_anchoring", "covey_think_win_win", "carnegie_never_criticize"],
    "finance_analyst":      ["cialdini_authority", "habit_tiny_habits", "nlp_anchoring", "covey_synergize"],
}

# KAIA personality mix per role class (analytical / decisive / empathetic / creative / technical)
_KAIA_MIXES: Dict[str, Dict[str, float]] = {
    "ceo":              {"analytical": 0.30, "decisive": 0.35, "empathetic": 0.15, "creative": 0.10, "technical": 0.10},
    "cto":              {"analytical": 0.35, "decisive": 0.30, "empathetic": 0.05, "creative": 0.10, "technical": 0.20},
    "cro":              {"analytical": 0.25, "decisive": 0.40, "empathetic": 0.10, "creative": 0.10, "technical": 0.15},
    "cfo":              {"analytical": 0.45, "decisive": 0.30, "empathetic": 0.05, "creative": 0.05, "technical": 0.15},
    "cmo":              {"analytical": 0.20, "decisive": 0.25, "empathetic": 0.20, "creative": 0.25, "technical": 0.10},
    "cpo":              {"analytical": 0.30, "decisive": 0.25, "empathetic": 0.25, "creative": 0.10, "technical": 0.10},
    "coo":              {"analytical": 0.30, "decisive": 0.40, "empathetic": 0.10, "creative": 0.05, "technical": 0.15},
    "clo":              {"analytical": 0.40, "decisive": 0.30, "empathetic": 0.05, "creative": 0.05, "technical": 0.20},
    "chro":             {"analytical": 0.20, "decisive": 0.20, "empathetic": 0.40, "creative": 0.10, "technical": 0.10},
    "vp_engineering":   {"analytical": 0.30, "decisive": 0.30, "empathetic": 0.10, "creative": 0.10, "technical": 0.20},
    "vp_product":       {"analytical": 0.25, "decisive": 0.25, "empathetic": 0.25, "creative": 0.15, "technical": 0.10},
    "vp_sales":         {"analytical": 0.20, "decisive": 0.35, "empathetic": 0.20, "creative": 0.15, "technical": 0.10},
    "vp_marketing":     {"analytical": 0.20, "decisive": 0.25, "empathetic": 0.20, "creative": 0.25, "technical": 0.10},
    "vp_customer_success": {"analytical": 0.15, "decisive": 0.20, "empathetic": 0.45, "creative": 0.10, "technical": 0.10},
    "vp_finance":       {"analytical": 0.45, "decisive": 0.30, "empathetic": 0.05, "creative": 0.05, "technical": 0.15},
    "vp_data":          {"analytical": 0.40, "decisive": 0.25, "empathetic": 0.05, "creative": 0.10, "technical": 0.20},
    "vp_people":        {"analytical": 0.15, "decisive": 0.20, "empathetic": 0.45, "creative": 0.10, "technical": 0.10},
    "engineering_manager": {"analytical": 0.25, "decisive": 0.30, "empathetic": 0.20, "creative": 0.10, "technical": 0.15},
    "product_manager":  {"analytical": 0.25, "decisive": 0.25, "empathetic": 0.25, "creative": 0.15, "technical": 0.10},
    "sales_manager":    {"analytical": 0.15, "decisive": 0.35, "empathetic": 0.25, "creative": 0.15, "technical": 0.10},
    "marketing_manager":{"analytical": 0.20, "decisive": 0.25, "empathetic": 0.20, "creative": 0.25, "technical": 0.10},
    "cs_manager":       {"analytical": 0.15, "decisive": 0.20, "empathetic": 0.45, "creative": 0.10, "technical": 0.10},
    "senior_software_engineer": {"analytical": 0.20, "decisive": 0.20, "empathetic": 0.10, "creative": 0.15, "technical": 0.35},
    "senior_account_executive": {"analytical": 0.15, "decisive": 0.30, "empathetic": 0.25, "creative": 0.20, "technical": 0.10},
    "sdr":              {"analytical": 0.15, "decisive": 0.30, "empathetic": 0.25, "creative": 0.20, "technical": 0.10},
    "account_executive":{"analytical": 0.15, "decisive": 0.30, "empathetic": 0.25, "creative": 0.20, "technical": 0.10},
    "customer_success": {"analytical": 0.15, "decisive": 0.20, "empathetic": 0.45, "creative": 0.10, "technical": 0.10},
    "software_engineer":{"analytical": 0.20, "decisive": 0.20, "empathetic": 0.10, "creative": 0.15, "technical": 0.35},
}


def _default_kaia() -> Dict[str, float]:
    return {"analytical": 0.20, "decisive": 0.20, "empathetic": 0.20, "creative": 0.20, "technical": 0.20}


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class SkillGenome:
    """Best-of-class skill profile for a specific role."""
    role_key: str
    scores: Dict[str, float]           # dimension → score (0-1)
    kaia_mix: Dict[str, float]         # analytical / decisive / empathetic / creative / technical
    influence_frameworks: List[str]    # ordered list of framework IDs
    overall_score: float               # weighted mean of all dimension scores

    @classmethod
    def build(cls, role_key: str) -> "SkillGenome":
        """Build an elite genome for the given role key."""
        raw = _ELITE_GENOMES.get(role_key, [0.75] * len(COMPETENCY_DIMENSIONS))
        scores = {dim: raw[i] for i, dim in enumerate(COMPETENCY_DIMENSIONS)}
        kaia = _KAIA_MIXES.get(role_key, _default_kaia())
        frameworks = _ROLE_FRAMEWORKS.get(role_key, ["cialdini_authority"])
        overall = round(sum(scores.values()) / len(scores), 4)
        return cls(
            role_key=role_key,
            scores=scores,
            kaia_mix=kaia,
            influence_frameworks=frameworks,
            overall_score=overall,
        )

    def top_strengths(self, n: int = 3) -> List[Tuple[str, float]]:
        """Return top-n strongest competencies."""
        return sorted(self.scores.items(), key=lambda kv: kv[1], reverse=True)[:n]

    def skill_gaps(self, floor: float = 0.80) -> List[Tuple[str, float]]:
        """Return competencies below *floor* — areas for development."""
        return [(k, v) for k, v in self.scores.items() if v < floor]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role_key": self.role_key,
            "scores": self.scores,
            "kaia_mix": self.kaia_mix,
            "influence_frameworks": self.influence_frameworks,
            "overall_score": self.overall_score,
            "top_strengths": self.top_strengths(),
            "skill_gaps": self.skill_gaps(),
        }


@dataclass
class EliteRole:
    """A single position in the org chart with its elite skill genome."""
    role_id: str                       # unique within the chart
    role_key: str                      # maps to _ELITE_GENOMES
    title: str
    department: Department
    seniority: Seniority
    reports_to: Optional[str]          # role_id of manager (None = top of org)
    direct_reports: List[str]          # role_ids
    genome: SkillGenome
    is_filled: bool = True             # False = vacancy / headcount gap
    person_name: str = ""              # Optional: named individual

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role_id": self.role_id,
            "role_key": self.role_key,
            "title": self.title,
            "department": self.department.value,
            "seniority": self.seniority.value,
            "reports_to": self.reports_to,
            "direct_reports": self.direct_reports,
            "is_filled": self.is_filled,
            "person_name": self.person_name,
            "genome": self.genome.to_dict(),
        }


@dataclass
class EliteOrgChart:
    """Complete organisational chart with elite-staffed roles."""
    chart_id: str
    company_stage: CompanyStage
    roles: Dict[str, EliteRole]        # role_id → EliteRole
    departments: Dict[Department, List[str]]  # dept → [role_ids]
    created_at: str = field(default_factory=lambda: __import__("datetime").datetime.now(__import__("datetime").timezone.utc).replace(tzinfo=None).isoformat())

    @property
    def headcount(self) -> int:
        return sum(1 for r in self.roles.values() if r.is_filled)

    @property
    def avg_genome_score(self) -> float:
        filled = [r.genome.overall_score for r in self.roles.values() if r.is_filled]
        return round(sum(filled) / len(filled), 4) if filled else 0.0

    def get_department_roles(self, dept: Department) -> List[EliteRole]:
        ids = self.departments.get(dept, [])
        return [self.roles[rid] for rid in ids if rid in self.roles]

    def get_reporting_chain(self, role_id: str) -> List[str]:
        """Return the full chain from *role_id* up to the CEO."""
        chain = []
        current = role_id
        seen: set = set()
        while current and current not in seen:
            seen.add(current)
            chain.append(current)
            role = self.roles.get(current)
            current = role.reports_to if role else None
        return chain

    def identify_coverage_gaps(self) -> List[Dict[str, Any]]:
        """Find departments with no VP-level or above."""
        gaps = []
        for dept in Department:
            dept_roles = self.get_department_roles(dept)
            has_leadership = any(
                r.seniority in (Seniority.VP, Seniority.C_SUITE, Seniority.DIRECTOR)
                for r in dept_roles
            )
            if dept_roles and not has_leadership:
                gaps.append({"department": dept.value, "gap": "No VP/Director/C-Suite coverage"})
        return gaps

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chart_id": self.chart_id,
            "company_stage": self.company_stage.value,
            "headcount": self.headcount,
            "avg_genome_score": self.avg_genome_score,
            "roles": {rid: r.to_dict() for rid, r in self.roles.items()},
            "departments": {dept.value: ids for dept, ids in self.departments.items()},
            "coverage_gaps": self.identify_coverage_gaps(),
            "created_at": self.created_at,
        }


@dataclass
class OrgScenario:
    """A named business scenario with per-department task assignments."""
    scenario_id: str
    scenario_type: ScenarioType
    name: str
    description: str
    # department → task description
    department_tasks: Dict[Department, str]
    # Which departments are the critical path for this scenario
    critical_path_depts: List[Department]
    # KPIs expected to move and by how much (multiplier)
    expected_kpi_moves: Dict[str, float]
    duration_weeks: int = 4

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "scenario_type": self.scenario_type.value,
            "name": self.name,
            "description": self.description,
            "department_tasks": {d.value: t for d, t in self.department_tasks.items()},
            "critical_path_depts": [d.value for d in self.critical_path_depts],
            "expected_kpi_moves": self.expected_kpi_moves,
            "duration_weeks": self.duration_weeks,
        }


@dataclass
class RoleSimResult:
    """Simulation result for a single role."""
    role_id: str
    role_key: str
    title: str
    department: str
    task_description: str
    genome_score: float
    execution_score: float     # how well this role executed its task (0-1)
    collaboration_score: float # how well this role collaborated cross-functionally
    output_quality: float      # quality of deliverable produced (0-1)
    blocker: Optional[str]     # any issue blocking this role
    elapsed_ms: float

    def overall(self) -> float:
        return round((self.execution_score + self.collaboration_score + self.output_quality) / 3, 4)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role_id": self.role_id,
            "role_key": self.role_key,
            "title": self.title,
            "department": self.department,
            "task_description": self.task_description,
            "genome_score": self.genome_score,
            "execution_score": self.execution_score,
            "collaboration_score": self.collaboration_score,
            "output_quality": self.output_quality,
            "overall_score": self.overall(),
            "blocker": self.blocker,
            "elapsed_ms": round(self.elapsed_ms, 2),
        }


@dataclass
class DepartmentSimResult:
    """Aggregated simulation result for one department."""
    department: str
    role_results: List[RoleSimResult]
    cursor_zone_id: Optional[str]
    avg_execution: float
    avg_collaboration: float
    avg_output_quality: float
    critical_path: bool

    def overall(self) -> float:
        return round((self.avg_execution + self.avg_collaboration + self.avg_output_quality) / 3, 4)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "department": self.department,
            "cursor_zone_id": self.cursor_zone_id,
            "avg_execution": self.avg_execution,
            "avg_collaboration": self.avg_collaboration,
            "avg_output_quality": self.avg_output_quality,
            "overall_score": self.overall(),
            "critical_path": self.critical_path,
            "role_results": [r.to_dict() for r in self.role_results],
        }


@dataclass
class OrgSimulationResult:
    """Full simulation result for an org × scenario run."""
    run_id: str
    chart_id: str
    scenario_id: str
    scenario_type: str
    company_stage: str
    department_results: Dict[str, DepartmentSimResult]
    layout_used: str
    cursor_zones_assigned: Dict[str, str]   # dept → zone_id
    duration_ms: float
    org_score: float                         # weighted average across departments
    kpi_projections: Dict[str, float]        # KPI name → projected multiplier
    gap_report: List[Dict[str, Any]]         # roles below threshold
    recommendations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "chart_id": self.chart_id,
            "scenario_id": self.scenario_id,
            "scenario_type": self.scenario_type,
            "company_stage": self.company_stage,
            "layout_used": self.layout_used,
            "cursor_zones_assigned": self.cursor_zones_assigned,
            "duration_ms": round(self.duration_ms, 2),
            "org_score": round(self.org_score, 4),
            "kpi_projections": self.kpi_projections,
            "gap_report": self.gap_report,
            "recommendations": self.recommendations,
            "department_results": {k: v.to_dict() for k, v in self.department_results.items()},
        }


# ---------------------------------------------------------------------------
# Pre-built Scenarios
# ---------------------------------------------------------------------------

def _build_scenarios() -> Dict[ScenarioType, OrgScenario]:
    """Return the canonical scenario library."""
    return {
        ScenarioType.PRODUCT_LAUNCH: OrgScenario(
            scenario_id="scen_product_launch",
            scenario_type=ScenarioType.PRODUCT_LAUNCH,
            name="Product Launch Sprint",
            description=(
                "All departments coordinate to ship and market a major new product feature "
                "within a 4-week sprint window."
            ),
            department_tasks={
                Department.ENGINEERING:       "Ship feature to production with zero P0 bugs",
                Department.PRODUCT:           "Finalize feature spec, QA sign-off, launch checklist",
                Department.MARKETING:         "Draft launch copy, press release, launch email sequence",
                Department.SALES:             "Train reps on new feature, build battle card, update pitch deck",
                Department.CUSTOMER_SUCCESS:  "Brief all enterprise accounts, draft FAQ, update help centre",
                Department.EXECUTIVE:         "Approve launch, brief board, coordinate press interviews",
                Department.FINANCE:           "Model revenue impact, update ARR forecast",
                Department.LEGAL:             "Review launch messaging for compliance, approve press release",
                Department.PEOPLE_OPS:        "Ensure hiring plan supports launch headcount needs",
            },
            critical_path_depts=[Department.ENGINEERING, Department.PRODUCT, Department.MARKETING],
            expected_kpi_moves={"mrr": 1.15, "trials": 1.30, "nps": 1.05},
            duration_weeks=4,
        ),

        ScenarioType.REVENUE_CRISIS: OrgScenario(
            scenario_id="scen_revenue_crisis",
            scenario_type=ScenarioType.REVENUE_CRISIS,
            name="Revenue Crisis Response",
            description=(
                "MRR dropped 20% in 30 days. Full org aligns on recovery plan: "
                "stop the bleed, reactivate churned accounts, accelerate pipeline."
            ),
            department_tasks={
                Department.SALES:             "Run blitz on top 50 at-risk accounts, run win-back sequence",
                Department.CUSTOMER_SUCCESS:  "Call every churned account, identify top 3 cancellation reasons",
                Department.PRODUCT:           "Identify feature gaps driving churn, build 30-day fix roadmap",
                Department.ENGINEERING:       "Ship top churn-reduction fix within 14 days",
                Department.MARKETING:         "Run demand gen campaign to rebuild pipeline",
                Department.EXECUTIVE:         "Brief investors, lead weekly war-room, make hard budget calls",
                Department.FINANCE:           "Model cash runway scenarios, identify cost reduction levers",
                Department.LEGAL:             "Review any at-risk enterprise contracts for termination clauses",
                Department.PEOPLE_OPS:        "Pause non-essential hiring, model headcount scenarios",
            },
            critical_path_depts=[Department.SALES, Department.CUSTOMER_SUCCESS, Department.EXECUTIVE],
            expected_kpi_moves={"churn": 0.70, "mrr": 1.10, "pipeline": 1.25},
            duration_weeks=6,
        ),

        ScenarioType.SCALING_SPRINT: OrgScenario(
            scenario_id="scen_scaling_sprint",
            scenario_type=ScenarioType.SCALING_SPRINT,
            name="2× Scaling Sprint",
            description=(
                "All departments execute a coordinated initiative to double ARR within 90 days "
                "through parallel workstreams: sales capacity, product velocity, and marketing demand."
            ),
            department_tasks={
                Department.SALES:             "Double outbound capacity: hire 4 AEs, deploy SDR automation",
                Department.MARKETING:         "Launch paid acquisition in 3 new channels, double content output",
                Department.ENGINEERING:       "Ship 2 enterprise-grade features that unlock upmarket deals",
                Department.PRODUCT:           "Compress feature cycle from 6 weeks to 3 weeks",
                Department.CUSTOMER_SUCCESS:  "Build digital-first onboarding to handle 2× customer volume",
                Department.EXECUTIVE:         "Secure bridge funding, set 2× targets, run weekly reviews",
                Department.FINANCE:           "Model unit economics at 2× scale, monitor CAC payback weekly",
                Department.PEOPLE_OPS:        "Execute 12-person hiring sprint across all departments",
                Department.LEGAL:             "Templatize contracts to close deals 3× faster",
            },
            critical_path_depts=[Department.SALES, Department.ENGINEERING, Department.MARKETING],
            expected_kpi_moves={"mrr": 2.00, "headcount": 1.50, "cac": 0.85},
            duration_weeks=12,
        ),

        ScenarioType.MARKET_ENTRY: OrgScenario(
            scenario_id="scen_market_entry",
            scenario_type=ScenarioType.MARKET_ENTRY,
            name="New Market Entry",
            description="Full org coordinates to enter a new vertical or geographic market from zero.",
            department_tasks={
                Department.EXECUTIVE:         "Define ICP for new market, approve budget, hire market lead",
                Department.SALES:             "Build new market playbook, source first 20 target accounts",
                Department.MARKETING:         "Build vertical-specific content, localise website, launch ABM campaign",
                Department.PRODUCT:           "Identify feature gaps for new market, prioritize adaptation roadmap",
                Department.ENGINEERING:       "Build 2 must-have integrations required by new market",
                Department.CUSTOMER_SUCCESS:  "Build new market onboarding runbook, identify success metrics",
                Department.FINANCE:           "Model new market P&L, set 12-month milestones",
                Department.LEGAL:             "Assess regulatory requirements for new market, update contracts",
                Department.PEOPLE_OPS:        "Hire market-specific roles, build local partner network",
            },
            critical_path_depts=[Department.EXECUTIVE, Department.SALES, Department.PRODUCT],
            expected_kpi_moves={"pipeline": 1.50, "trials": 1.40, "tam": 1.30},
            duration_weeks=16,
        ),

        ScenarioType.TECHNICAL_MIGRATION: OrgScenario(
            scenario_id="scen_tech_migration",
            scenario_type=ScenarioType.TECHNICAL_MIGRATION,
            name="Technical Platform Migration",
            description="Migrate from legacy monolith to microservices with zero customer downtime.",
            department_tasks={
                Department.ENGINEERING:       "Execute phased migration: decompose 3 core services per sprint",
                Department.PRODUCT:           "Freeze non-critical features during migration, set rollback criteria",
                Department.EXECUTIVE:         "Align board on 6-month timeline, approve engineering headcount",
                Department.CUSTOMER_SUCCESS:  "Communicate maintenance windows proactively to all accounts",
                Department.SALES:             "Position migration as enterprise-readiness story in all deals",
                Department.MARKETING:         "Write engineering blog series on migration to build developer brand",
                Department.FINANCE:           "Track infra cost delta weekly, approve cloud budget overruns",
                Department.LEGAL:             "Review SLA commitments during migration, update DPAs",
                Department.PEOPLE_OPS:        "Hire 3 senior engineers for migration team",
            },
            critical_path_depts=[Department.ENGINEERING, Department.PRODUCT],
            expected_kpi_moves={"reliability": 1.40, "deploy_freq": 3.00, "infra_cost": 0.75},
            duration_weeks=24,
        ),

        ScenarioType.FUNDRAISE: OrgScenario(
            scenario_id="scen_fundraise",
            scenario_type=ScenarioType.FUNDRAISE,
            name="Series B Fundraise",
            description="Prepare and execute a Series B fundraising round targeting $20M+.",
            department_tasks={
                Department.EXECUTIVE:         "Build investor narrative, run 40 partner meetings, negotiate term sheet",
                Department.FINANCE:           "Build financial model, data room, cap table, 3-year projections",
                Department.PRODUCT:           "Write product vision deck, demo 3 marquee enterprise use cases",
                Department.ENGINEERING:       "Build investor-ready demo environment, fix all P0 bugs",
                Department.SALES:             "Accelerate pipeline to prove demand: close 5 logos before round closes",
                Department.MARKETING:         "Run thought leadership campaign to raise brand recognition with investors",
                Department.LEGAL:             "Prepare DD materials, review term sheet, negotiate investor rights",
                Department.PEOPLE_OPS:        "Build org chart for post-funding 24-month plan",
                Department.CUSTOMER_SUCCESS:  "Gather NPS scores and case studies to prove retention",
            },
            critical_path_depts=[Department.EXECUTIVE, Department.FINANCE, Department.LEGAL],
            expected_kpi_moves={"valuation": 2.50, "arr": 1.20, "runway": 3.00},
            duration_weeks=12,
        ),

        ScenarioType.COMPETITIVE_RESPONSE: OrgScenario(
            scenario_id="scen_competitive_response",
            scenario_type=ScenarioType.COMPETITIVE_RESPONSE,
            name="Competitive Response",
            description="A well-funded competitor launches a direct attack. Full org responds.",
            department_tasks={
                Department.PRODUCT:           "Ship 3 differentiating features that competitor lacks",
                Department.MARKETING:         "Build competitive battlecard, run comparison landing page campaign",
                Department.SALES:             "Train reps on competitive objections, run win-back of lost deals",
                Department.ENGINEERING:       "Accelerate roadmap: compress 3 features from 6 months to 6 weeks",
                Department.CUSTOMER_SUCCESS:  "Proactively contact top 100 accounts to defend against poaching",
                Department.EXECUTIVE:         "Set competitive strategy, approve emergency marketing budget",
                Department.FINANCE:           "Approve competitive discount programme with guardrails",
                Department.LEGAL:             "Review competitor claims, prepare cease-and-desist if needed",
                Department.PEOPLE_OPS:        "Retain key talent with spot bonuses, counter any poaching attempts",
            },
            critical_path_depts=[Department.PRODUCT, Department.SALES, Department.MARKETING],
            expected_kpi_moves={"win_rate": 1.20, "churn": 0.85, "nps": 1.10},
            duration_weeks=8,
        ),

        ScenarioType.TALENT_SURGE: OrgScenario(
            scenario_id="scen_talent_surge",
            scenario_type=ScenarioType.TALENT_SURGE,
            name="Talent Surge — 3× Headcount",
            description=(
                "Company is tripling headcount in 6 months post-funding. "
                "Every department hires, onboards, and ramps simultaneously."
            ),
            department_tasks={
                Department.PEOPLE_OPS:        "Hire 40 people in 6 months; build structured onboarding; define culture",
                Department.ENGINEERING:       "Double eng team; introduce pair-programming; maintain velocity",
                Department.SALES:             "Build SDR team from 2 to 8; train new AEs on playbook",
                Department.MARKETING:         "Hire content, demand gen, and design; launch rebrand",
                Department.PRODUCT:           "Hire 3 PMs; introduce squad model; maintain roadmap coherence",
                Department.CUSTOMER_SUCCESS:  "Hire 5 CSMs; build digital-first onboarding; maintain NPS",
                Department.EXECUTIVE:         "Define leadership team; run all-hands every 2 weeks; set OKRs",
                Department.FINANCE:           "Build FP&A function; implement Netsuite; automate payroll",
                Department.LEGAL:             "Build legal ops; standardise contracts; implement CLM",
            },
            critical_path_depts=[Department.PEOPLE_OPS, Department.EXECUTIVE],
            expected_kpi_moves={"headcount": 3.00, "revenue_per_head": 1.10, "eNPS": 1.15},
            duration_weeks=24,
        ),
    }


SCENARIO_LIBRARY: Dict[ScenarioType, OrgScenario] = _build_scenarios()


# ---------------------------------------------------------------------------
# Org Chart Builder
# ---------------------------------------------------------------------------

class OrgChartBuilder:
    """Constructs EliteOrgChart instances for different company stages."""

    # Org blueprints: stage → list of (role_id, role_key, title, dept, seniority, reports_to)
    # reports_to is a role_key reference resolved after all roles are built
    _BLUEPRINTS: Dict[CompanyStage, List[Tuple[str, str, str, Department, Seniority, Optional[str]]]] = {
        CompanyStage.SEED: [
            ("ceo",   "ceo",   "CEO",           Department.EXECUTIVE, Seniority.C_SUITE, None),
            ("cto",   "cto",   "CTO",           Department.ENGINEERING, Seniority.C_SUITE, "ceo"),
            ("cro",   "cro",   "CRO",           Department.SALES, Seniority.C_SUITE, "ceo"),
            ("swe1",  "senior_software_engineer", "Senior SWE", Department.ENGINEERING, Seniority.SENIOR_IC, "cto"),
            ("swe2",  "software_engineer", "Software Engineer", Department.ENGINEERING, Seniority.IC, "cto"),
            ("ae1",   "account_executive", "Account Executive", Department.SALES, Seniority.IC, "cro"),
            ("sdr1",  "sdr", "SDR", Department.SALES, Seniority.IC, "cro"),
        ],

        CompanyStage.SERIES_A: [
            ("ceo",   "ceo",   "CEO",           Department.EXECUTIVE, Seniority.C_SUITE, None),
            ("cto",   "cto",   "CTO",           Department.ENGINEERING, Seniority.C_SUITE, "ceo"),
            ("cro",   "cro",   "CRO",           Department.SALES, Seniority.C_SUITE, "ceo"),
            ("cmo",   "cmo",   "CMO",           Department.MARKETING, Seniority.C_SUITE, "ceo"),
            ("cpo",   "cpo",   "CPO",           Department.PRODUCT, Seniority.C_SUITE, "ceo"),
            # Engineering
            ("vpe",   "vp_engineering", "VP Engineering", Department.ENGINEERING, Seniority.VP, "cto"),
            ("em1",   "engineering_manager", "Engineering Manager", Department.ENGINEERING, Seniority.MANAGER, "vpe"),
            ("swe1",  "senior_software_engineer", "Senior SWE", Department.ENGINEERING, Seniority.SENIOR_IC, "em1"),
            ("swe2",  "senior_software_engineer", "Senior SWE", Department.ENGINEERING, Seniority.SENIOR_IC, "em1"),
            ("swe3",  "software_engineer", "Software Engineer", Department.ENGINEERING, Seniority.IC, "em1"),
            ("swe4",  "frontend_engineer", "Frontend Engineer", Department.ENGINEERING, Seniority.IC, "em1"),
            ("sde1",  "senior_data_engineer", "Senior Data Engineer", Department.ENGINEERING, Seniority.SENIOR_IC, "vpe"),
            # Product
            ("pm1",   "product_manager", "Product Manager", Department.PRODUCT, Seniority.MANAGER, "cpo"),
            ("des1",  "senior_designer", "Senior Designer", Department.PRODUCT, Seniority.SENIOR_IC, "cpo"),
            # Sales
            ("vps",   "vp_sales", "VP Sales", Department.SALES, Seniority.VP, "cro"),
            ("ae1",   "senior_account_executive", "Senior AE", Department.SALES, Seniority.SENIOR_IC, "vps"),
            ("ae2",   "account_executive", "Account Executive", Department.SALES, Seniority.IC, "vps"),
            ("sdr1",  "sdr", "SDR", Department.SALES, Seniority.IC, "vps"),
            ("sdr2",  "sdr", "SDR", Department.SALES, Seniority.IC, "vps"),
            # Marketing
            ("vmg",   "vp_marketing", "VP Marketing", Department.MARKETING, Seniority.VP, "cmo"),
            ("cw1",   "content_writer", "Content Writer", Department.MARKETING, Seniority.IC, "vmg"),
            ("da1",   "data_analyst", "Marketing Analyst", Department.MARKETING, Seniority.IC, "vmg"),
            # Customer Success
            ("cs1",   "customer_success", "CSM", Department.CUSTOMER_SUCCESS, Seniority.IC, "cro"),
            ("cs2",   "customer_success", "CSM", Department.CUSTOMER_SUCCESS, Seniority.IC, "cro"),
        ],

        CompanyStage.SERIES_B: [
            ("ceo",   "ceo",   "CEO",           Department.EXECUTIVE, Seniority.C_SUITE, None),
            ("cto",   "cto",   "CTO",           Department.ENGINEERING, Seniority.C_SUITE, "ceo"),
            ("cro",   "cro",   "CRO",           Department.SALES, Seniority.C_SUITE, "ceo"),
            ("cmo",   "cmo",   "CMO",           Department.MARKETING, Seniority.C_SUITE, "ceo"),
            ("cpo",   "cpo",   "CPO",           Department.PRODUCT, Seniority.C_SUITE, "ceo"),
            ("cfo",   "cfo",   "CFO",           Department.FINANCE, Seniority.C_SUITE, "ceo"),
            ("coo",   "coo",   "COO",           Department.EXECUTIVE, Seniority.C_SUITE, "ceo"),
            ("chro",  "chro",  "CHRO",          Department.PEOPLE_OPS, Seniority.C_SUITE, "ceo"),
            ("clo",   "clo",   "CLO / General Counsel", Department.LEGAL, Seniority.C_SUITE, "ceo"),
            # Engineering
            ("vpe",   "vp_engineering", "VP Engineering", Department.ENGINEERING, Seniority.VP, "cto"),
            ("em1",   "engineering_manager", "Eng Manager — Backend", Department.ENGINEERING, Seniority.MANAGER, "vpe"),
            ("em2",   "engineering_manager", "Eng Manager — Frontend", Department.ENGINEERING, Seniority.MANAGER, "vpe"),
            ("sswe1", "senior_software_engineer", "Senior SWE", Department.ENGINEERING, Seniority.SENIOR_IC, "em1"),
            ("sswe2", "senior_software_engineer", "Senior SWE", Department.ENGINEERING, Seniority.SENIOR_IC, "em1"),
            ("sswe3", "senior_software_engineer", "Senior SWE", Department.ENGINEERING, Seniority.SENIOR_IC, "em1"),
            ("ssfe1", "senior_frontend_engineer", "Senior FE", Department.ENGINEERING, Seniority.SENIOR_IC, "em2"),
            ("ssfe2", "senior_frontend_engineer", "Senior FE", Department.ENGINEERING, Seniority.SENIOR_IC, "em2"),
            ("swe1",  "software_engineer", "SWE", Department.ENGINEERING, Seniority.IC, "em1"),
            ("swe2",  "software_engineer", "SWE", Department.ENGINEERING, Seniority.IC, "em1"),
            ("fe1",   "frontend_engineer", "FE", Department.ENGINEERING, Seniority.IC, "em2"),
            ("vd",    "vp_data",  "VP Data", Department.ENGINEERING, Seniority.VP, "cto"),
            ("sda1",  "senior_data_engineer", "Senior Data Eng", Department.ENGINEERING, Seniority.SENIOR_IC, "vd"),
            ("sml1",  "senior_ml_engineer",  "Senior ML Eng",   Department.ENGINEERING, Seniority.SENIOR_IC, "vd"),
            ("sia1",  "senior_infra_engineer","Senior Infra Eng",Department.ENGINEERING, Seniority.SENIOR_IC, "vpe"),
            # Product
            ("vpp",   "vp_product", "VP Product", Department.PRODUCT, Seniority.VP, "cpo"),
            ("pm1",   "product_manager", "Product Manager", Department.PRODUCT, Seniority.MANAGER, "vpp"),
            ("pm2",   "product_manager", "Product Manager", Department.PRODUCT, Seniority.MANAGER, "vpp"),
            ("des1",  "senior_designer", "Senior Designer", Department.PRODUCT, Seniority.SENIOR_IC, "vpp"),
            ("des2",  "senior_designer", "Senior Designer", Department.PRODUCT, Seniority.SENIOR_IC, "vpp"),
            # Sales
            ("vps",   "vp_sales", "VP Sales", Department.SALES, Seniority.VP, "cro"),
            ("dsm",   "director_sales", "Director of Sales", Department.SALES, Seniority.DIRECTOR, "vps"),
            ("sm1",   "sales_manager", "Sales Manager", Department.SALES, Seniority.MANAGER, "dsm"),
            ("sae1",  "senior_account_executive", "Senior AE", Department.SALES, Seniority.SENIOR_IC, "sm1"),
            ("ae1",   "account_executive", "AE", Department.SALES, Seniority.IC, "sm1"),
            ("ae2",   "account_executive", "AE", Department.SALES, Seniority.IC, "sm1"),
            ("sdr1",  "sdr", "SDR", Department.SALES, Seniority.IC, "dsm"),
            ("sdr2",  "sdr", "SDR", Department.SALES, Seniority.IC, "dsm"),
            ("sdr3",  "sdr", "SDR", Department.SALES, Seniority.IC, "dsm"),
            # Marketing
            ("vpm",   "vp_marketing", "VP Marketing", Department.MARKETING, Seniority.VP, "cmo"),
            ("dmm",   "director_marketing", "Director of Marketing", Department.MARKETING, Seniority.DIRECTOR, "vpm"),
            ("mm1",   "marketing_manager", "Marketing Manager", Department.MARKETING, Seniority.MANAGER, "dmm"),
            ("cw1",   "content_writer", "Content Writer", Department.MARKETING, Seniority.IC, "mm1"),
            ("cw2",   "content_writer", "Content Writer", Department.MARKETING, Seniority.IC, "mm1"),
            ("da1",   "data_analyst", "Marketing Analyst", Department.MARKETING, Seniority.IC, "mm1"),
            # Customer Success
            ("vpcs",  "vp_customer_success", "VP Customer Success", Department.CUSTOMER_SUCCESS, Seniority.VP, "cro"),
            ("csm1",  "customer_success", "CSM", Department.CUSTOMER_SUCCESS, Seniority.IC, "vpcs"),
            ("csm2",  "customer_success", "CSM", Department.CUSTOMER_SUCCESS, Seniority.IC, "vpcs"),
            ("csm3",  "customer_success", "CSM", Department.CUSTOMER_SUCCESS, Seniority.IC, "vpcs"),
            # Finance
            ("vpf",   "vp_finance", "VP Finance", Department.FINANCE, Seniority.VP, "cfo"),
            ("fa1",   "finance_analyst", "Finance Analyst", Department.FINANCE, Seniority.IC, "vpf"),
            ("fa2",   "finance_analyst", "Finance Analyst", Department.FINANCE, Seniority.IC, "vpf"),
            # Legal
            ("lc1",   "legal_counsel", "Senior Counsel", Department.LEGAL, Seniority.IC, "clo"),
            # People Ops
            ("vpp2",  "vp_people", "VP People", Department.PEOPLE_OPS, Seniority.VP, "chro"),
            ("rec1",  "senior_recruiter", "Senior Recruiter", Department.PEOPLE_OPS, Seniority.SENIOR_IC, "vpp2"),
            ("rec2",  "senior_recruiter", "Senior Recruiter", Department.PEOPLE_OPS, Seniority.SENIOR_IC, "vpp2"),
        ],
    }

    # Alias Series B blueprint for larger stages (extend rather than redefine)
    _BLUEPRINTS[CompanyStage.GROWTH]     = _BLUEPRINTS[CompanyStage.SERIES_B]
    _BLUEPRINTS[CompanyStage.ENTERPRISE] = _BLUEPRINTS[CompanyStage.SERIES_B]

    def build(self, stage: CompanyStage) -> EliteOrgChart:
        """Construct and return an EliteOrgChart for the given company stage."""
        blueprint = self._BLUEPRINTS.get(stage, self._BLUEPRINTS[CompanyStage.SERIES_B])

        roles: Dict[str, EliteRole] = {}
        dept_map: Dict[Department, List[str]] = {d: [] for d in Department}

        for role_id, role_key, title, dept, seniority, reports_to in blueprint:
            genome = SkillGenome.build(role_key)
            role = EliteRole(
                role_id=role_id,
                role_key=role_key,
                title=title,
                department=dept,
                seniority=seniority,
                reports_to=reports_to,
                direct_reports=[],
                genome=genome,
            )
            # Avoid duplicate role_id (blueprints should be unique but guard anyway)
            final_id = role_id
            if final_id in roles:
                final_id = f"{role_id}_{uuid.uuid4().hex[:4]}"
            roles[final_id] = role
            dept_map[dept].append(final_id)

        # Wire direct_reports
        for rid, role in roles.items():
            if role.reports_to and role.reports_to in roles:
                manager = roles[role.reports_to]
                if rid not in manager.direct_reports:
                    manager.direct_reports.append(rid)

        return EliteOrgChart(
            chart_id=f"org_{stage.value}_{uuid.uuid4().hex[:8]}",
            company_stage=stage,
            roles=roles,
            departments=dept_map,
        )


# ---------------------------------------------------------------------------
# Swarm Org Runner — maps departments to cursor zones + runs in parallel
# ---------------------------------------------------------------------------

# How many zones each SplitScreenLayout supports
_LAYOUT_ZONE_COUNT: Dict[str, int] = {
    "single":           1,
    "dual_horizontal":  2,
    "dual_vertical":    2,
    "triple_horizontal":3,
    "quad":             4,
    "hexa":             6,
    "custom":           1,
}


def _pick_layout(n_depts: int) -> str:
    """Pick the smallest layout that fits n_depts zones."""
    if n_depts <= 1:
        return "single"
    if n_depts <= 2:
        return "dual_horizontal"
    if n_depts <= 3:
        return "triple_horizontal"
    if n_depts <= 4:
        return "quad"
    return "hexa"


class SwarmOrgRunner:
    """
    Maps an EliteOrgChart × OrgScenario to a MultiCursorDesktop layout and runs
    each department's tasks in a separate cursor zone simultaneously.

    Each department with a task in the scenario gets its own screen zone and
    cursor.  All zones are dispatched in parallel threads.  Per-role scores are
    computed from the genome of the roles in that department.
    """

    GENOME_WEIGHT    = 0.40   # How much the elite genome drives output quality
    EXECUTION_NOISE  = 0.08   # Stochastic variance in execution
    COLLAB_BASELINE  = 0.82   # Baseline cross-functional score for elite orgs

    def __init__(self, seed: int = 42) -> None:
        import random as _random
        self._rng = _random.Random(seed)
        self._lock = threading.Lock()

    def run(
        self,
        chart: EliteOrgChart,
        scenario: OrgScenario,
    ) -> OrgSimulationResult:
        """Execute the scenario across the org chart using multi-cursor parallelism."""
        t0 = time.perf_counter()
        run_id = uuid.uuid4().hex[:12]

        active_depts = [d for d in scenario.department_tasks if chart.get_department_roles(d)]
        n_depts = len(active_depts)

        # Choose layout
        layout_str = _pick_layout(n_depts)

        # Build desktop (if native automation available)
        desktop: Optional[Any] = None
        zone_ids: List[str] = []
        if _HAS_NATIVE:
            try:
                desktop = MultiCursorDesktop(screen_width=1920, screen_height=1080)
                # Try to get SplitScreenLayout enum
                layout_enum = None
                for member in SplitScreenLayout:
                    if member.value == layout_str:
                        layout_enum = member
                        break
                if layout_enum:
                    zones = desktop.apply_layout(layout_enum)
                    zone_ids = [z.zone_id for z in zones]
            except Exception as exc:
                logger.debug("SwarmOrgRunner: MultiCursorDesktop unavailable: %s", exc)

        # Pad zone_ids to match dept count
        while len(zone_ids) < n_depts:
            zone_ids.append(f"zone_{len(zone_ids)}")

        dept_zone_map: Dict[str, str] = {
            dept.value: zone_ids[i]
            for i, dept in enumerate(active_depts)
        }

        # Run departments in parallel threads
        dept_results: Dict[str, DepartmentSimResult] = {}
        threads = []

        for dept, task_desc in scenario.department_tasks.items():
            roles_in_dept = chart.get_department_roles(dept)
            if not roles_in_dept:
                continue
            zone_id = dept_zone_map.get(dept.value, "zone_0")
            is_critical = dept in scenario.critical_path_depts

            t = threading.Thread(
                target=self._simulate_department,
                args=(dept, task_desc, roles_in_dept, zone_id, is_critical, dept_results),
                daemon=True,
            )
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10.0)

        duration_ms = (time.perf_counter() - t0) * 1000

        # Compute org-wide score (critical path departments weighted 1.5×)
        total_weight = 0.0
        weighted_sum = 0.0
        for dr in dept_results.values():
            w = 1.5 if dr.critical_path else 1.0
            weighted_sum += dr.overall() * w
            total_weight += w
        org_score = round(weighted_sum / total_weight, 4) if total_weight else 0.0

        # KPI projections: scale expected by org_score × scenario multipliers
        kpi_projections = {
            kpi: round(mult * org_score / 0.90, 4)   # normalise against 90% org score baseline
            for kpi, mult in scenario.expected_kpi_moves.items()
        }

        # Gap report: roles scoring below 0.75
        gap_report = []
        for dr in dept_results.values():
            for rr in dr.role_results:
                if rr.overall() < 0.75:
                    gap_report.append({
                        "role_id": rr.role_id,
                        "title": rr.title,
                        "department": rr.department,
                        "overall_score": rr.overall(),
                        "blocker": rr.blocker,
                    })

        recommendations = self._generate_recommendations(dept_results, gap_report, scenario)

        return OrgSimulationResult(
            run_id=run_id,
            chart_id=chart.chart_id,
            scenario_id=scenario.scenario_id,
            scenario_type=scenario.scenario_type.value,
            company_stage=chart.company_stage.value,
            department_results=dept_results,
            layout_used=layout_str,
            cursor_zones_assigned=dept_zone_map,
            duration_ms=duration_ms,
            org_score=org_score,
            kpi_projections=kpi_projections,
            gap_report=gap_report,
            recommendations=recommendations,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _simulate_department(
        self,
        dept: Department,
        task_desc: str,
        roles: List[EliteRole],
        zone_id: str,
        is_critical: bool,
        out: Dict[str, DepartmentSimResult],
    ) -> None:
        """Simulate all roles in a department and store in *out*."""
        role_results = []
        for role in roles:
            rr = self._simulate_role(role, task_desc)
            role_results.append(rr)

        if not role_results:
            return

        avg_exec  = sum(r.execution_score    for r in role_results) / len(role_results)
        avg_collab = sum(r.collaboration_score for r in role_results) / len(role_results)
        avg_qual  = sum(r.output_quality      for r in role_results) / len(role_results)

        with self._lock:
            out[dept.value] = DepartmentSimResult(
                department=dept.value,
                role_results=role_results,
                cursor_zone_id=zone_id,
                avg_execution=round(avg_exec, 4),
                avg_collaboration=round(avg_collab, 4),
                avg_output_quality=round(avg_qual, 4),
                critical_path=is_critical,
            )

    def _simulate_role(self, role: EliteRole, task_desc: str) -> RoleSimResult:
        """Score a single role on its genome × task_desc."""
        t0 = time.perf_counter()
        genome = role.genome

        # Execution score — driven by execution_speed + technical_depth + adaptability
        exec_raw = (
            genome.scores["execution_speed"] * 0.40 +
            genome.scores["technical_depth"] * 0.30 +
            genome.scores["adaptability"] * 0.30
        )
        noise = self._rng.gauss(0, self.EXECUTION_NOISE)
        execution = max(0.0, min(1.0, exec_raw + noise))

        # Collaboration score — cross_functional + leadership_presence + communication_clarity
        collab_raw = (
            genome.scores["cross_functional"] * 0.40 +
            genome.scores["leadership_presence"] * 0.30 +
            genome.scores["communication_clarity"] * 0.30
        )
        noise2 = self._rng.gauss(0, self.EXECUTION_NOISE * 0.5)
        collaboration = max(0.0, min(1.0, collab_raw + noise2))

        # Output quality — strategic_thinking + data_fluency + customer_empathy
        qual_raw = (
            genome.scores["strategic_thinking"] * 0.35 +
            genome.scores["data_fluency"] * 0.30 +
            genome.scores["customer_empathy"] * 0.35
        )
        output_quality = max(0.0, min(1.0, qual_raw))

        blocker = None
        if execution < 0.65:
            blocker = f"Low execution score ({execution:.2f}) — consider upskilling technical_depth"
        elif collaboration < 0.65:
            blocker = f"Low collaboration ({collaboration:.2f}) — cross-functional bandwidth constraint"

        elapsed = (time.perf_counter() - t0) * 1000
        return RoleSimResult(
            role_id=role.role_id,
            role_key=role.role_key,
            title=role.title,
            department=role.department.value,
            task_description=task_desc[:120],
            genome_score=genome.overall_score,
            execution_score=round(execution, 4),
            collaboration_score=round(collaboration, 4),
            output_quality=round(output_quality, 4),
            blocker=blocker,
            elapsed_ms=elapsed,
        )

    def _generate_recommendations(
        self,
        dept_results: Dict[str, DepartmentSimResult],
        gap_report: List[Dict[str, Any]],
        scenario: OrgScenario,
    ) -> List[str]:
        """Generate human-readable recommendations from simulation results."""
        recs = []

        # Lowest-performing department
        if dept_results:
            worst = min(dept_results.values(), key=lambda d: d.overall())
            if worst.overall() < 0.80:
                recs.append(
                    f"Department '{worst.department}' scored {worst.overall():.2f} — "
                    f"prioritise senior leadership hire and coaching to raise floor."
                )

        # Critical path bottlenecks
        for dept in scenario.critical_path_depts:
            dr = dept_results.get(dept.value)
            if dr and dr.avg_execution < 0.82:
                recs.append(
                    f"Critical-path department '{dept.value}' execution score {dr.avg_execution:.2f} "
                    f"is below 0.82 target — unblock with dedicated sprint and remove non-critical work."
                )

        # Collaboration gaps across all departments
        low_collab = [
            dr for dr in dept_results.values()
            if dr.avg_collaboration < 0.80
        ]
        if low_collab:
            names = ", ".join(d.department for d in low_collab)
            recs.append(
                f"Cross-functional collaboration low in: {names}. "
                f"Introduce shared OKRs and weekly cross-dept syncs."
            )

        # Role-level gaps
        if len(gap_report) > 3:
            recs.append(
                f"{len(gap_report)} roles scored below 0.75. "
                f"Run targeted 30-day upskilling programmes and consider performance-managed backfills."
            )

        # Generic elite-level push
        if not recs:
            recs.append(
                "Org is performing at elite level across all departments. "
                "Maintain momentum by running quarterly stretch scenarios and benchmarking against top-decile peers."
            )

        return recs


# ---------------------------------------------------------------------------
# Elite Org Simulator — top-level façade
# ---------------------------------------------------------------------------

class EliteOrgSimulator:
    """
    Top-level façade for the Elite Org Simulation system.

    Usage::

        sim = EliteOrgSimulator()

        # 1. Build an elite org chart for a Series-B company
        chart = sim.build_chart(CompanyStage.SERIES_B)

        # 2. Pick a scenario
        scenario = sim.get_scenario(ScenarioType.SCALING_SPRINT)

        # 3. Run the simulation (multi-cursor swarm execution)
        result = sim.run(chart, scenario)

        # 4. Print summary
        print(sim.summary(result))
    """

    def __init__(self, seed: int = 42) -> None:
        self._builder = OrgChartBuilder()
        self._runner  = SwarmOrgRunner(seed=seed)
        self._history: List[OrgSimulationResult] = []
        self._lock = threading.Lock()
        # Wire in HistoricalGreatnessEngine if available
        self._hge: Optional[Any] = None
        if _HAS_HGE:
            try:
                self._hge = _HGE()
            except Exception as exc:
                logger.debug("EliteOrgSimulator: HGE unavailable: %s", exc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_chart(self, stage: CompanyStage = CompanyStage.SERIES_B) -> EliteOrgChart:
        """Build an elite-staffed org chart for *stage*."""
        return self._builder.build(stage)

    @staticmethod
    def get_scenario(scenario_type: ScenarioType) -> OrgScenario:
        """Return the named scenario from the library."""
        scenario = SCENARIO_LIBRARY.get(scenario_type)
        if scenario is None:
            raise ValueError(f"Unknown scenario type: {scenario_type}")
        return scenario

    @staticmethod
    def list_scenarios() -> List[Dict[str, Any]]:
        """Return summary of all available scenarios."""
        return [
            {
                "scenario_type": s.scenario_type.value,
                "name": s.name,
                "description": s.description[:80] + "...",
                "critical_path": [d.value for d in s.critical_path_depts],
                "duration_weeks": s.duration_weeks,
            }
            for s in SCENARIO_LIBRARY.values()
        ]

    def run(
        self,
        chart: EliteOrgChart,
        scenario: OrgScenario,
    ) -> OrgSimulationResult:
        """Run the org through the scenario using multi-cursor swarm simulation."""
        result = self._runner.run(chart, scenario)
        with self._lock:
            capped_append(self._history, result, max_size=200)
        return result

    def calibrate_chart(self, chart: EliteOrgChart) -> Dict[str, Any]:
        """
        Calibrate every role in the org against historical greatness benchmarks.

        Returns a dict with:
          - ``role_calibrations``: role_id → CalibrationResult.to_dict()
          - ``org_summary``: aggregate summary from HistoricalGreatnessEngine
        """
        if self._hge is None:
            return {"error": "HistoricalGreatnessEngine not available"}
        role_calibrations = self._hge.calibrate_org(chart)
        org_summary = self._hge.org_greatness_summary(chart)
        return {
            "role_calibrations": {rid: c.to_dict() for rid, c in role_calibrations.items()},
            "org_summary": org_summary,
        }

    def calibrate_role(self, role_key: str) -> Optional[Any]:
        """Calibrate a single role by key (e.g. 'ceo', 'vp_sales') against historical benchmarks."""
        if self._hge is None:
            return None
        genome = SkillGenome.build(role_key)
        return self._hge.calibrate_genome(genome, subject_id=role_key, subject_type="role")

    def run_all_scenarios(
        self,
        stage: CompanyStage = CompanyStage.SERIES_B,
    ) -> List[OrgSimulationResult]:
        """Run every scenario in the library against the given stage org."""
        chart = self.build_chart(stage)
        results = []
        for scenario in SCENARIO_LIBRARY.values():
            results.append(self.run(chart, scenario))
        return results

    def benchmark(
        self,
        stage: CompanyStage = CompanyStage.SERIES_B,
        scenario_type: ScenarioType = ScenarioType.SCALING_SPRINT,
        runs: int = 5,
    ) -> Dict[str, Any]:
        """Run the same scenario *runs* times to get min/mean/max org scores."""
        chart = self.build_chart(stage)
        scenario = self.get_scenario(scenario_type)
        scores = []
        for i in range(runs):
            # Use different seeds for each run to get variance
            runner = SwarmOrgRunner(seed=i * 17 + 1)
            result = runner.run(chart, scenario)
            scores.append(result.org_score)
            with self._lock:
                capped_append(self._history, result, max_size=200)

        return {
            "stage": stage.value,
            "scenario": scenario_type.value,
            "runs": runs,
            "min":  round(min(scores), 4),
            "mean": round(sum(scores) / len(scores), 4),
            "max":  round(max(scores), 4),
            "std":  round(math.sqrt(sum((s - sum(scores)/len(scores))**2 for s in scores) / len(scores)), 4),
            "scores": [round(s, 4) for s in scores],
        }

    def compare_stages(
        self,
        scenario_type: ScenarioType = ScenarioType.SCALING_SPRINT,
    ) -> List[Dict[str, Any]]:
        """Compare org performance across all company stages for a given scenario."""
        scenario = self.get_scenario(scenario_type)
        out = []
        for stage in CompanyStage:
            chart = self.build_chart(stage)
            result = self.run(chart, scenario)
            out.append({
                "stage": stage.value,
                "headcount": chart.headcount,
                "avg_genome_score": chart.avg_genome_score,
                "org_score": result.org_score,
                "kpi_projections": result.kpi_projections,
                "top_gap": result.gap_report[0] if result.gap_report else None,
                "primary_recommendation": result.recommendations[0] if result.recommendations else "",
            })
        return out

    def history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return most recent simulation results."""
        with self._lock:
            recent = self._history[-limit:]
        return [r.to_dict() for r in reversed(recent)]

    def summary(self, result: OrgSimulationResult) -> str:
        """Return a human-readable summary of a simulation result."""
        lines = [
            f"═══ ELITE ORG SIMULATION RESULT ═══",
            f"Run ID          : {result.run_id}",
            f"Company Stage   : {result.company_stage}",
            f"Scenario        : {result.scenario_type}",
            f"Layout          : {result.layout_used} ({len(result.cursor_zones_assigned)} zones)",
            f"Duration        : {result.duration_ms:.1f} ms",
            f"",
            f"ORG SCORE       : {result.org_score:.4f} / 1.0000",
            f"",
            "── Department Performance ──────────────────────────────",
        ]
        for dept, dr in sorted(result.department_results.items(), key=lambda kv: kv[1].overall(), reverse=True):
            critical_tag = " [CRITICAL PATH]" if dr.critical_path else ""
            lines.append(
                f"  {dept:<24} overall={dr.overall():.4f}  "
                f"exec={dr.avg_execution:.3f}  "
                f"collab={dr.avg_collaboration:.3f}  "
                f"quality={dr.avg_output_quality:.3f}"
                f"{critical_tag}"
            )

        lines += [
            "",
            "── KPI Projections ─────────────────────────────────────",
        ]
        for kpi, val in result.kpi_projections.items():
            direction = "↑" if val >= 1.0 else "↓"
            lines.append(f"  {kpi:<24} {direction} {val:.3f}×")

        if result.gap_report:
            lines += [
                "",
                f"── Role Gaps ({len(result.gap_report)} below 0.75) ──────────────────────",
            ]
            for g in result.gap_report[:5]:
                lines.append(f"  [{g['department']}] {g['title']}: {g['overall_score']:.3f}")

        lines += [
            "",
            "── Recommendations ─────────────────────────────────────",
        ]
        for i, rec in enumerate(result.recommendations, 1):
            lines.append(f"  {i}. {rec}")

        return "\n".join(lines)
