"""Murphy System pre-built grant application profiles (Track A)."""

from __future__ import annotations

from typing import Any, Dict


murphy_sbir_profile: Dict[str, Any] = {
    "company_name": "Inoni LLC (Murphy System)",
    "ein": "XX-XXXXXXX",
    "address": {
        "street": "TBD",
        "city": "TBD",
        "state": "OR",
        "zip": "97201",
    },
    "naics_codes": ["541511", "541512", "541519", "541715"],
    "entity_type": "small_business",
    "state": "OR",
    "verticals": [
        "ai_ml",
        "software",
        "building_automation",
        "energy_management",
        "industrial_iot",
    ],
    "project_type": "research_and_development",
    "annual_revenue": 0.0,
    "employee_count": 5,
    "project_cost": 275_000.0,
    "is_rural": False,
    "has_ein": True,
    "has_sam_gov": False,
    "technical_description": (
        "Murphy System is an AI orchestration platform that translates natural language "
        "directives into directed-acyclic-graph (DAG) execution plans. The core innovation "
        "is a confidence-gated execution engine that autonomously routes tasks between "
        "fully-automated, human-in-the-loop, and blocked states based on real-time "
        "confidence scoring. The system self-improves through reinforcement learning "
        "from human feedback (RLHF) loops embedded in every task completion event."
    ),
    "innovation_narrative": (
        "Murphy System represents a fundamental advance in human-AI teaming. Unlike "
        "existing workflow automation tools that require rigid scripting, Murphy System "
        "accepts ambiguous natural language goals and autonomously decomposes them into "
        "executable steps. The confidence-gated architecture ensures humans remain in "
        "control of high-stakes decisions while the system learns to handle routine "
        "tasks autonomously over time."
    ),
    "commercial_potential": (
        "Target markets include commercial building operators ($50B+ market), industrial "
        "manufacturers, federal agencies, and enterprise software buyers. The platform "
        "addresses a $200B+ workflow automation market. Early customer pilots in building "
        "automation and energy management demonstrate 20-40% operational cost reductions."
    ),
    "team_description": (
        "Led by Corey Post (founder/CEO), a software architect with 15+ years in "
        "distributed systems and AI. Team includes ML engineers, control systems "
        "specialists, and enterprise sales professionals."
    ),
    "budget_template": {
        "personnel_costs": 150_000.0,
        "subcontractor_costs": 50_000.0,
        "equipment": 15_000.0,
        "travel": 5_000.0,
        "other_direct_costs": 10_000.0,
        "indirect_costs": 45_000.0,
        "total": 275_000.0,
    },
    "focus_grants": [
        "sbir_phase1",
        "sttr",
        "tc_41_rd",
        "federal_rd_41",
        "state_rd_or",
        "nsf_pfi",
    ],
}

murphy_doe_profile: Dict[str, Any] = {
    "company_name": "Inoni LLC (Murphy System)",
    "ein": "XX-XXXXXXX",
    "address": {
        "street": "TBD",
        "city": "TBD",
        "state": "OR",
        "zip": "97201",
    },
    "naics_codes": ["541511", "541512", "238290", "541330"],
    "entity_type": "small_business",
    "state": "OR",
    "verticals": [
        "building_automation",
        "energy_management",
        "hvac_controls",
        "grid_management",
        "ai_ml",
    ],
    "project_type": "energy_technology_rd",
    "annual_revenue": 0.0,
    "employee_count": 5,
    "project_cost": 1_000_000.0,
    "is_rural": False,
    "has_ein": True,
    "has_sam_gov": False,
    "technical_description": (
        "Murphy System provides AI-driven building energy management and grid-interactive "
        "control systems. The platform uses real-time sensor fusion, occupancy prediction, "
        "and weather-adaptive control algorithms to minimize energy consumption while "
        "maintaining occupant comfort. Grid-interactive capabilities enable automated "
        "demand response, load shifting, and grid services without human intervention."
    ),
    "innovation_narrative": (
        "Existing building energy management systems (BEMS) require extensive manual "
        "programming and cannot adapt autonomously to changing conditions. Murphy System's "
        "NL→DAG architecture allows facility managers to specify energy goals in plain "
        "English, with the AI autonomously optimizing control sequences. This reduces "
        "energy use by 20-35% compared to conventional BAS/BMS systems."
    ),
    "commercial_potential": (
        "Commercial and industrial buildings consume 40% of U.S. energy. Murphy System "
        "targets the $15B building energy management market with a SaaS + hardware model. "
        "DOE BTO and AMO programs directly address Murphy's technical focus areas."
    ),
    "team_description": (
        "Energy systems engineers, control theory specialists, and AI/ML researchers "
        "with backgrounds in building automation and grid services."
    ),
    "budget_template": {
        "personnel_costs": 500_000.0,
        "subcontractor_costs": 200_000.0,
        "equipment": 100_000.0,
        "travel": 30_000.0,
        "other_direct_costs": 70_000.0,
        "indirect_costs": 100_000.0,
        "total": 1_000_000.0,
    },
    "focus_grants": [
        "sbir_phase2",
        "doe_bto",
        "doe_amo",
        "doe_arpa_e",
        "tc_179d",
        "state_rd_or",
    ],
}

murphy_nsf_profile: Dict[str, Any] = {
    "company_name": "Inoni LLC (Murphy System)",
    "ein": "XX-XXXXXXX",
    "address": {
        "street": "TBD",
        "city": "TBD",
        "state": "OR",
        "zip": "97201",
    },
    "naics_codes": ["541511", "541715", "611310"],
    "entity_type": "small_business",
    "state": "OR",
    "verticals": [
        "ai_ml",
        "software",
        "building_automation",
        "industrial_iot",
    ],
    "project_type": "fundamental_research",
    "annual_revenue": 0.0,
    "employee_count": 5,
    "project_cost": 750_000.0,
    "is_rural": False,
    "has_ein": True,
    "has_sam_gov": False,
    "technical_description": (
        "Murphy System investigates fundamental questions in AI planning under uncertainty: "
        "How can autonomous agents decompose ambiguous natural language goals into reliable "
        "execution plans? How should confidence thresholds be calibrated to minimize human "
        "interruption while maximizing safety? The HITL (Human-in-the-Loop) architecture "
        "provides a novel framework for human-AI collaborative task execution."
    ),
    "innovation_narrative": (
        "The research addresses open problems in AI planning, natural language understanding, "
        "and human-machine teaming. The confidence-gated execution model is a novel "
        "contribution to the field of autonomous systems with broad applicability beyond "
        "the commercial building domain to healthcare, defense, and scientific research."
    ),
    "commercial_potential": (
        "NSF SBIR/STTR commercialization pathway targets the enterprise AI platform market. "
        "Academic partnerships enable peer-reviewed publications that validate the approach "
        "and build credibility for enterprise sales."
    ),
    "team_description": (
        "Principal investigator with computer science PhD focus. Academic collaborators "
        "at Oregon and Pacific Northwest universities. Industry advisory board from "
        "AI and building automation sectors."
    ),
    "budget_template": {
        "personnel_costs": 400_000.0,
        "subcontractor_costs": 150_000.0,
        "equipment": 50_000.0,
        "travel": 25_000.0,
        "other_direct_costs": 50_000.0,
        "indirect_costs": 75_000.0,
        "total": 750_000.0,
    },
    "focus_grants": [
        "sbir_phase1",
        "sbir_phase2",
        "sttr",
        "nsf_pfi",
        "nsf_convergence",
        "tc_41_rd",
        "federal_rd_41",
    ],
}

murphy_manufacturing_profile: Dict[str, Any] = {
    "company_name": "Inoni LLC (Murphy System)",
    "ein": "XX-XXXXXXX",
    "address": {
        "street": "TBD",
        "city": "TBD",
        "state": "OR",
        "zip": "97201",
    },
    "naics_codes": ["541511", "541512", "333244", "334513"],
    "entity_type": "small_business",
    "state": "OR",
    "verticals": [
        "smart_manufacturing",
        "industrial_iot",
        "energy_management",
        "ai_ml",
    ],
    "project_type": "manufacturing_technology",
    "annual_revenue": 0.0,
    "employee_count": 5,
    "project_cost": 500_000.0,
    "is_rural": False,
    "has_ein": True,
    "has_sam_gov": False,
    "technical_description": (
        "Murphy System provides AI-driven supervisory control and data acquisition (SCADA) "
        "intelligence for manufacturing facilities. The platform integrates with existing "
        "PLCs, DCS systems, and industrial IoT sensors to optimize production processes, "
        "reduce energy consumption, and predict equipment failures before they occur. "
        "Natural language interfaces allow operators to query machine status and initiate "
        "process changes without specialized programming knowledge."
    ),
    "innovation_narrative": (
        "Manufacturing facilities lose $50B annually to unplanned downtime. Murphy System's "
        "AI orchestration layer provides a universal control plane that works across "
        "heterogeneous industrial equipment without costly custom integration. The NL→DAG "
        "engine enables non-expert operators to automate complex multi-step processes."
    ),
    "commercial_potential": (
        "The smart manufacturing market exceeds $300B. Murphy System targets mid-market "
        "manufacturers (100-2000 employees) who cannot afford tier-1 MES/SCADA vendors. "
        "CESMII and DOE AMO programs directly support this application domain."
    ),
    "team_description": (
        "Industrial automation engineers, SCADA specialists, and AI/ML researchers. "
        "Advisory board includes manufacturing operations executives from automotive, "
        "food & beverage, and electronics sectors."
    ),
    "budget_template": {
        "personnel_costs": 275_000.0,
        "subcontractor_costs": 100_000.0,
        "equipment": 75_000.0,
        "travel": 20_000.0,
        "other_direct_costs": 30_000.0,
        "indirect_costs": 0.0,
        "total": 500_000.0,
    },
    "focus_grants": [
        "sbir_phase1",
        "sbir_phase2",
        "doe_amo",
        "cesmii",
        "nist_mep",
        "tc_48c",
        "tc_41_rd",
    ],
}


def get_murphy_profiles() -> Dict[str, Dict[str, Any]]:
    """Return all Murphy System grant profiles keyed by profile name."""
    return {
        "murphy_sbir_profile": murphy_sbir_profile,
        "murphy_doe_profile": murphy_doe_profile,
        "murphy_nsf_profile": murphy_nsf_profile,
        "murphy_manufacturing_profile": murphy_manufacturing_profile,
    }
