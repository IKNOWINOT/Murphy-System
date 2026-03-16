"""
Pro/Con Decision Engine
========================
Weighs pros vs cons and picks the outcome with the most pros without
sacrificing core requirements of function, safety, and regulatory
compliance. Hard constraints (safety, codes) are never traded off.

"decisions are weighing cons vs pros and deciding the best outcome
with the most pros. pros generally means more opportunity/work/roi/
savings/ without sacrificing core requirements of function and safety
that meets whatever required regulation/codes"

Copyright (c) 2020 Inoni Limited Liability Company  Creator: Corey Post
License: BSL 1.1
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Criterion:
    criterion_id: str = ""
    name: str = ""
    category: str = "pro"          # "pro" | "con" | "constraint"
    weight: float = 1.0
    description: str = ""
    unit: str = ""
    threshold: Optional[float] = None   # for constraints: minimum passing value

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class Option:
    option_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    description: str = ""
    scores: Dict[str, float] = field(default_factory=dict)
    constraint_violations: List[str] = field(default_factory=list)
    total_pro_score: float = 0.0
    total_con_score: float = 0.0
    net_score: float = 0.0
    viable: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class Decision:
    decision_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    question: str = ""
    options: List[Option] = field(default_factory=list)
    winner: Optional[Option] = None
    runner_up: Optional[Option] = None
    reasoning: str = ""
    constraints_applied: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "question": self.question,
            "options": [o.to_dict() for o in self.options],
            "winner": self.winner.to_dict() if self.winner else None,
            "runner_up": self.runner_up.to_dict() if self.runner_up else None,
            "reasoning": self.reasoning,
            "constraints_applied": self.constraints_applied,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# Standard criteria sets
# ---------------------------------------------------------------------------

STANDARD_CRITERIA: Dict[str, List[Criterion]] = {
    "energy_system_selection": [
        Criterion("roi","Return on Investment","pro",0.25,"Higher ROI = better","% or years"),
        Criterion("energy_savings","Energy Savings %","pro",0.20,"% energy reduction","pct"),
        Criterion("implementation_cost","Implementation Cost","con",0.15,"Capital cost","USD"),
        Criterion("maintenance_burden","Maintenance Complexity","con",0.10,"Complexity score","1-10"),
        Criterion("occupant_comfort","Occupant Comfort Score","pro",0.15,"ASHRAE 55 compliance","1-10"),
        Criterion("resilience","System Resilience","pro",0.15,"Redundancy and uptime","1-10"),
        Criterion("safety_compliance","Safety Code Compliance","constraint",1.0,"Must meet all codes","binary",1.0),
        Criterion("ashrae_compliance","ASHRAE 90.1 Compliance","constraint",1.0,"Must comply","binary",1.0),
    ],
    "automation_strategy_selection": [
        Criterion("performance","Control Performance","pro",0.25,"Meets setpoint targets","1-10"),
        Criterion("energy_efficiency","Energy Efficiency","pro",0.20,"kW or kBtu savings","pct"),
        Criterion("complexity","Implementation Complexity","con",0.15,"Time and expertise","1-10"),
        Criterion("reliability","System Reliability","pro",0.20,"Uptime %","pct"),
        Criterion("scalability","Future Scalability","pro",0.10,"Ease of expansion","1-10"),
        Criterion("cost","Total Installed Cost","con",0.10,"USD","USD"),
        Criterion("safety_interlocks","Safety Interlocks Present","constraint",1.0,"Non-negotiable","binary",1.0),
        Criterion("code_compliance","Local Code Compliance","constraint",1.0,"Non-negotiable","binary",1.0),
    ],
    "equipment_selection": [
        Criterion("efficiency","Equipment Efficiency","pro",0.25,"kW/ton or EER","ratio"),
        Criterion("first_cost","First Cost","con",0.20,"Purchase price","USD"),
        Criterion("life_cycle_cost","Life Cycle Cost","con",0.15,"20-year NPV","USD"),
        Criterion("reliability","Manufacturer Reliability","pro",0.15,"MTBF / warranty","score"),
        Criterion("lead_time","Lead Time","con",0.10,"Weeks to delivery","weeks"),
        Criterion("local_support","Local Service Support","pro",0.15,"Available technicians","score"),
        Criterion("safety_listing","UL/ETL Safety Listing","constraint",1.0,"Required","binary",1.0),
        Criterion("code_compliance","Meets Local Codes","constraint",1.0,"Required","binary",1.0),
    ],
    "ecm_prioritization": [
        Criterion("simple_payback","Simple Payback","pro",0.30,"Shorter is better","years"),
        Criterion("energy_savings","Energy Savings","pro",0.25,"kWh or kBtu/yr","kBtu"),
        Criterion("npv","Net Present Value","pro",0.20,"10-year NPV","USD"),
        Criterion("implementation_risk","Implementation Risk","con",0.15,"Disruption score","1-10"),
        Criterion("maintenance_impact","Maintenance Impact","con",0.10,"Change in O&M cost","USD"),
        Criterion("safety","Does Not Compromise Safety","constraint",1.0,"Required","binary",1.0),
        Criterion("code","Meets Energy Code","constraint",1.0,"Required","binary",1.0),
    ],
}


class ProConDecisionEngine:
    """Evaluate options against criteria; hard safety/compliance constraints first."""

    def get_standard_criteria(self, criteria_set: str) -> List[Criterion]:
        return list(STANDARD_CRITERIA.get(criteria_set, []))

    def evaluate(self, question: str, options: List[Dict[str, Any]],
                 criteria: Optional[List[Criterion]] = None,
                 criteria_set: Optional[str] = None) -> Decision:
        if criteria is None:
            criteria = self.get_standard_criteria(criteria_set or "energy_system_selection")

        constraints = [c for c in criteria if c.category == "constraint"]
        pros = [c for c in criteria if c.category == "pro"]
        cons = [c for c in criteria if c.category == "con"]
        applied_constraints = [c.criterion_id for c in constraints]

        scored_options: List[Option] = []
        for opt_data in options:
            opt = Option(
                name=opt_data.get("name", "Option"),
                description=opt_data.get("description", ""),
                scores=opt_data.get("scores", {}),
            )
            # Check hard constraints
            for c in constraints:
                val = opt.scores.get(c.criterion_id, 0.0)
                threshold = c.threshold if c.threshold is not None else 1.0
                if val < threshold:
                    opt.constraint_violations.append(
                        f"{c.name}: required {threshold}, got {val}"
                    )
                    opt.viable = False

            if opt.viable:
                pro_score = sum(
                    c.weight * opt.scores.get(c.criterion_id, 5.0)
                    for c in pros
                )
                con_score = sum(
                    c.weight * opt.scores.get(c.criterion_id, 5.0)
                    for c in cons
                )
                opt.total_pro_score = round(pro_score, 3)
                opt.total_con_score = round(con_score, 3)
                opt.net_score = round(pro_score - con_score, 3)

            scored_options.append(opt)

        viable = sorted([o for o in scored_options if o.viable],
                        key=lambda o: o.net_score, reverse=True)
        winner = viable[0] if viable else None
        runner_up = viable[1] if len(viable) > 1 else None

        if winner:
            reasoning = (
                f"'{winner.name}' selected with net score {winner.net_score:.2f} "
                f"(pros {winner.total_pro_score:.2f} - cons {winner.total_con_score:.2f}). "
                f"All safety and compliance constraints satisfied. "
            )
            if runner_up:
                reasoning += (
                    f"Runner-up: '{runner_up.name}' (net score {runner_up.net_score:.2f})."
                )
        else:
            reasoning = "No viable options found — all options failed safety/compliance constraints."

        return Decision(
            question=question,
            options=scored_options,
            winner=winner,
            runner_up=runner_up,
            reasoning=reasoning,
            constraints_applied=applied_constraints,
        )

    def evaluate_ecms(self, ecms: List[Dict[str, Any]],
                       budget: float = 0, climate_zone: str = "") -> Decision:
        question = f"Which ECMs should be prioritised? Budget: ${budget:,.0f}, Climate: {climate_zone or 'unspecified'}"
        options = []
        for ecm in ecms:
            payback = ecm.get("typical_payback_years", 5.0)
            savings = ecm.get("typical_savings_pct", 10.0)
            cost_tier = ecm.get("implementation_cost_tier", "medium")
            risk_map = {"low": 2, "medium": 5, "high": 8}
            options.append({
                "name": ecm.get("name", ecm.get("ecm_id", "ECM")),
                "description": ecm.get("description", ""),
                "scores": {
                    "simple_payback": max(0, 10 - payback),
                    "energy_savings": savings / 10,
                    "npv": max(0, 10 - payback + savings / 10),
                    "implementation_risk": risk_map.get(cost_tier, 5),
                    "maintenance_impact": 3.0,
                    "safety": 1.0,
                    "code": 1.0,
                },
            })
        return self.evaluate(question, options, criteria_set="ecm_prioritization")

    def evaluate_equipment(self, equipment_options: List[Dict[str, Any]],
                            application: str = "", location: str = "") -> Decision:
        question = f"Which equipment best fits {application or 'this application'}? Location: {location or 'unspecified'}"
        return self.evaluate(question, equipment_options, criteria_set="equipment_selection")

    def evaluate_strategies(self, strategies: List[Dict[str, Any]],
                              system_type: str = "") -> Decision:
        question = f"Which control strategy is best for {system_type or 'this system'}?"
        return self.evaluate(question, strategies, criteria_set="automation_strategy_selection")

    def explain_decision(self, decision: Decision) -> str:
        if decision.winner is None:
            return "No decision could be made — all options failed safety or compliance requirements."
        lines = [
            f"Decision: {decision.question}",
            f"",
            f"Best Option: {decision.winner.name}",
            f"Why: {decision.reasoning}",
            f"",
            f"Pros score: {decision.winner.total_pro_score:.1f}",
            f"Cons score: {decision.winner.total_con_score:.1f}",
            f"Net score: {decision.winner.net_score:.1f}",
        ]
        if decision.runner_up:
            lines.extend([
                f"",
                f"Second choice: {decision.runner_up.name} (score {decision.runner_up.net_score:.1f})",
            ])
        eliminated = [o for o in decision.options if not o.viable]
        if eliminated:
            lines.extend([f"", f"Eliminated (failed safety/compliance):"])
            for o in eliminated:
                lines.append(f"  - {o.name}: {'; '.join(o.constraint_violations[:2])}")
        return "\n".join(lines)
