"""
Murphy/Inoni Grant Profiles — Grant-optimized descriptions for each application flavor.

Four flavors: R&D, Energy, Manufacturing, General.
Each profile is tailored to a different grant category and highlights the most
relevant subset of Murphy's 750+ modules.

"We are the first use case always." — Murphy/Inoni is Track A, the proving ground.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

from typing import Dict, List, Optional

from src.billing.grants.models import GrantCategory, GrantFlavor, GrantProfile

# ---------------------------------------------------------------------------
# Core positioning (shared across all flavors)
# ---------------------------------------------------------------------------
CORE_POSITIONING = (
    "Murphy System is a universal automation platform that converts natural-language requests "
    "into governed, auditable execution plans. Unlike traditional automation tools, Murphy "
    "uses PID-proven control theory combined with agentic AI to operate across industrial, "
    "building, energy, and business domains through a single unified system. Murphy's "
    "architecture — NL→DAG→Execute — enables any domain expert to describe what they need "
    "in plain language and receive a validated, executable automation plan in seconds. "
    "Developed by Inoni LLC, Murphy is licensed under BSL 1.1 and will convert to Apache 2.0 "
    "after 4 years — a commitment to long-term open-source availability."
)

# ---------------------------------------------------------------------------
# R&D Flavor — For SBIR, STTR, ARPA-E, NSF, §41 R&D Credit applications
# ---------------------------------------------------------------------------
RD_PROFILE = GrantProfile(
    flavor=GrantFlavor.RD,
    name="Murphy System — R&D / Innovation Profile",
    positioning=(
        CORE_POSITIONING + "\n\n"
        "For R&D grant applications, Murphy represents a novel convergence of three previously "
        "separate disciplines: (1) classical control theory (PID loops, state machines, "
        "finite automata) proven over decades in industrial automation; (2) modern large "
        "language models (LLMs) for natural-language understanding and knowledge synthesis; "
        "(3) agentic AI execution with formal governance and auditable decision chains. "
        "Murphy is not a chatbot wrapper — it is a full execution engine with confidence-gated "
        "decision making, multi-LLM routing, and self-improvement infrastructure that no "
        "commercial product currently provides."
    ),
    innovation_narrative=(
        "Murphy's core technical innovations address fundamental unsolved problems in AI "
        "deployment for high-stakes automation:\n\n"
        "1. **Confidence-Gated Execution (G/D/H Scoring):** Murphy does not execute if "
        "confidence is below threshold. The G (Go) / D (Defer) / H (Hold) framework "
        "provides provably safe automation by requiring human review when agent confidence "
        "falls below defined thresholds. This is a novel formal governance mechanism with "
        "no equivalent in commercial automation tools.\n\n"
        "2. **Multi-LLM Routing:** Murphy dynamically routes inference requests to the "
        "optimal LLM based on task type, cost, latency, and confidence requirements. This "
        "enables best-of-breed intelligence while managing cost and latency — a technical "
        "challenge the industry has not solved.\n\n"
        "3. **Wingman Protocol:** A secondary AI agent monitors primary execution for "
        "anomalies, unexpected outcomes, or confidence degradation — providing a novel "
        "form of AI-on-AI oversight.\n\n"
        "4. **Causality Sandbox:** Murphy's simulation environment tests automation plans "
        "against a causal model of the target system before execution — preventing "
        "unintended consequences in physical systems.\n\n"
        "5. **Self-Improvement Immune Engine:** Murphy's RLEF (Reinforcement Learning from "
        "Execution Feedback) system improves automation quality from real-world outcomes "
        "while maintaining a formal 'immune' check against performance regression.\n\n"
        "These innovations, taken together, represent a technically novel approach to "
        "safe, governed, self-improving automation — with applications spanning industrial "
        "control, building automation, energy management, and general business processes."
    ),
    job_creation_narrative=(
        "Inoni LLC projects creation of 15–25 high-skill jobs within 24 months of receiving "
        "Phase I funding, growing to 50–75 jobs within 5 years. Roles include: AI/ML "
        "engineers, industrial automation engineers, OT/IT integration specialists, "
        "energy systems engineers, full-stack developers, and solution architects. "
        "Murphy's multi-vertical approach creates a broader employment base than "
        "single-domain automation tools, with employees developing expertise across "
        "AI, industrial controls, energy, and manufacturing domains. Additionally, "
        "Murphy's platform enables U.S. manufacturers and building operators to increase "
        "productivity and global competitiveness, indirectly supporting tens of thousands "
        "of industrial jobs."
    ),
    energy_impact_narrative=(
        "Murphy's AI-optimized automation can reduce energy consumption in commercial "
        "buildings by 15–35% through BAS/BMS optimization, demand response automation, "
        "and predictive HVAC control. Across a 1,000-installation deployment, Murphy "
        "projects 50–150 GWh/year in avoided electricity consumption. In industrial "
        "settings, AI-driven process optimization can reduce energy intensity by 10–25%, "
        "representing significant GHG reduction potential."
    ),
    relevant_modules=[
        "Multi-LLM Router", "Confidence Gate Engine (G/D/H)", "Wingman Protocol",
        "Causality Sandbox", "Self-Improvement Immune Engine", "RLEF Engine",
        "Agentic Orchestrator", "NL→DAG Compiler", "Workflow Canvas",
        "Audit Trail Engine", "Governance Framework", "SOC 2 Compliance Layer",
    ],
    relevant_grant_categories=[
        GrantCategory.FEDERAL_GRANT,
        GrantCategory.RD_TAX_CREDIT,
        GrantCategory.FEDERAL_TAX_CREDIT,
    ],
    target_grants=[
        "sbir_phase1", "sbir_phase2", "sttr", "arpa_e",
        "nsf_convergence_accelerator", "nsf_pfi",
        "rd_credit_sec41", "state_rd_credits", "sec_48c",
    ],
    tech_highlights=[
        "Multi-LLM routing with dynamic model selection",
        "Confidence-gated execution (G/D/H scoring framework)",
        "Wingman Protocol — AI-on-AI oversight",
        "Causality Sandbox — pre-execution simulation",
        "Self-improvement immune engine with RLEF",
        "NL→DAG→Execute architecture",
        "SOC 2 Type II compliance framework",
        "Formal audit trail for all AI decisions",
    ],
    naics_codes=["541715", "541512", "541511"],  # R&D services, computer systems design
    keywords=["agentic AI", "multi-LLM", "confidence-gated execution", "autonomous systems",
              "AI governance", "safe AI", "industrial AI", "self-improving automation"],
)

# ---------------------------------------------------------------------------
# Energy Flavor — For DOE BTO, ARPA-E, Energy Trust, IRA tax credits
# ---------------------------------------------------------------------------
ENERGY_PROFILE = GrantProfile(
    flavor=GrantFlavor.ENERGY,
    name="Murphy System — Energy & Building Automation Profile",
    positioning=(
        CORE_POSITIONING + "\n\n"
        "For energy and building automation grant applications, Murphy represents the "
        "next generation of Building Automation Systems (BAS) and Energy Management Systems "
        "(EMS). Unlike traditional BAS vendors (Johnson Controls, Honeywell, Siemens, "
        "Schneider Electric) that require proprietary hardware and vendor lock-in, Murphy "
        "is a protocol-agnostic software platform that integrates with any existing BAS "
        "hardware via BACnet, Modbus, OPC UA, LonWorks, and other industrial protocols. "
        "Murphy adds AI-driven optimization, demand response automation, and grid-interactive "
        "capabilities to any building's existing automation infrastructure."
    ),
    innovation_narrative=(
        "Murphy's energy and building automation innovations address key barriers to "
        "widespread deployment of grid-interactive efficient buildings (GEBs):\n\n"
        "1. **Protocol Agnosticism:** Murphy's unified protocol layer (BACnet, Modbus TCP, "
        "OPC UA, LonWorks, KNX, MQTT, REST) eliminates the vendor lock-in that prevents "
        "building owners from upgrading controls.\n\n"
        "2. **AI-Optimized Control:** Murphy applies ML-based predictive control to HVAC "
        "schedules, setpoints, and equipment staging — reducing energy use while maintaining "
        "comfort.\n\n"
        "3. **Automated Demand Response (ADR):** Murphy implements OpenADR 2.0 for "
        "automated grid signal response, enabling buildings to participate in DR programs "
        "without manual intervention.\n\n"
        "4. **Energy Digital Twin:** Murphy's causality sandbox creates a real-time energy "
        "digital twin of the building for continuous simulation and optimization."
    ),
    job_creation_narrative=(
        "Murphy's building automation platform directly enables the clean energy workforce: "
        "BAS technicians trained on Murphy's open platform can serve any building, not just "
        "single-vendor installations. This expands the addressable technician workforce "
        "and reduces the labor shortage in building controls. Murphy training programs "
        "will certify 500+ technicians within 3 years of commercial launch."
    ),
    energy_impact_narrative=(
        "Commercial buildings account for ~18% of U.S. energy use. Murphy's AI-driven "
        "BAS/EMS can reduce building energy use by 15–35%. At scale (10,000 commercial "
        "buildings), Murphy projects 500 GWh–1.5 TWh/year in avoided consumption. "
        "Automated demand response participation enables 100–300 MW of dispatchable "
        "load flexibility per 10,000 enrolled buildings — equivalent to a medium-sized "
        "peaker plant. Grid-interactive operations reduce the need for new generation "
        "capacity, supporting FERC Order 2222 distributed resource integration."
    ),
    relevant_modules=[
        "BACnet/IP Integration", "Modbus TCP/RTU Integration", "OPC UA Client/Server",
        "OpenADR 2.0 Client", "Energy Management System (EMS)", "BAS Controller",
        "Demand Response Engine", "Energy Digital Twin", "HVAC Optimizer",
        "Grid Signal Processor", "Fault Detection & Diagnostics (FDD)",
        "Energy Metering & Reporting", "ASHRAE 90.1 Compliance Tools",
    ],
    relevant_grant_categories=[
        GrantCategory.FEDERAL_GRANT,
        GrantCategory.FEDERAL_TAX_CREDIT,
        GrantCategory.STATE_INCENTIVE,
        GrantCategory.UTILITY_PROGRAM,
        GrantCategory.PACE_FINANCING,
    ],
    target_grants=[
        "doe_bto", "arpa_e", "doe_grip", "sbir_phase1",
        "sec_179d", "sec_48_itc", "energy_trust_oregon", "nyserda",
        "utility_demand_response", "utility_custom_incentive", "pace_financing",
    ],
    tech_highlights=[
        "BACnet/IP, Modbus TCP/RTU, OPC UA, LonWorks, KNX protocol support",
        "OpenADR 2.0 automated demand response",
        "AI-predictive HVAC control (15–35% energy reduction)",
        "Real-time energy digital twin",
        "Fault detection & diagnostics (FDD)",
        "ASHRAE 90.1 compliance reporting",
        "Grid-interactive building controls (FERC Order 2222)",
        "Multi-building EMS dashboard",
    ],
    naics_codes=["238220", "541519", "541690"],  # HVAC contractors, tech consulting, energy consulting
    keywords=["BAS/BMS", "EMS", "demand response", "OpenADR", "grid-interactive buildings",
              "energy management", "BACnet", "OPC UA", "building automation"],
)

# ---------------------------------------------------------------------------
# Manufacturing Flavor — For DOE AMO, CESMII, NIST MEP, §48C
# ---------------------------------------------------------------------------
MANUFACTURING_PROFILE = GrantProfile(
    flavor=GrantFlavor.MANUFACTURING,
    name="Murphy System — Smart Manufacturing / Industrial Profile",
    positioning=(
        CORE_POSITIONING + "\n\n"
        "For smart manufacturing and industrial grant applications, Murphy represents a "
        "unified industrial automation platform that bridges OT (Operational Technology) "
        "and IT (Information Technology) domains. Murphy integrates with existing SCADA, "
        "PLC, and DCS systems via OPC UA, Modbus TCP, DNP3, and MTConnect to add AI-driven "
        "process optimization, predictive maintenance, and natural-language supervision. "
        "Murphy is ISA-95, PackML, and ISA-88 aware — speaking the language of "
        "industrial automation standards while enabling the transition to smart manufacturing."
    ),
    innovation_narrative=(
        "Murphy's smart manufacturing innovations address the OT/IT convergence challenge:\n\n"
        "1. **Unified OT/IT Protocol Layer:** Murphy's integration framework connects "
        "SCADA/DCS (OPC UA, DNP3, Modbus), ERP (SAP, Oracle), MES, and cloud analytics "
        "through a single platform — eliminating the costly, error-prone point integrations "
        "that plague industrial digital transformation.\n\n"
        "2. **NL-Driven Process Supervision:** Machine operators can query Murphy in natural "
        "language ('Why is Line 3 running hot?') and receive AI-synthesized answers from "
        "sensor data, historian records, and maintenance logs.\n\n"
        "3. **AI Predictive Maintenance:** Murphy's ML models detect equipment anomalies "
        "in real-time, reducing unplanned downtime by 20–40%.\n\n"
        "4. **Additive Manufacturing Integration:** Murphy's MTConnect and 3D printer "
        "integrations (Stratasys, Markforged, EOS) enable AI-supervised additive "
        "manufacturing — a key DOE advanced manufacturing priority."
    ),
    job_creation_narrative=(
        "Murphy enables U.S. manufacturers to compete globally by dramatically reducing "
        "the cost and complexity of smart manufacturing adoption. Small and medium "
        "manufacturers (the MEP target market) that previously couldn't afford $1M+ "
        "SCADA upgrades can implement Murphy for $10K–$100K. Murphy projects support for "
        "200+ manufacturing businesses within 2 years, preserving an estimated 2,000+ "
        "U.S. manufacturing jobs through improved competitiveness."
    ),
    energy_impact_narrative=(
        "Industrial energy use represents 33% of U.S. total energy consumption. "
        "Murphy's AI process optimization can reduce industrial energy intensity by "
        "10–25%. For a typical 50,000 sq ft manufacturing facility using 2M kWh/year, "
        "Murphy projects 200K–500K kWh/year in energy savings — reducing both operating "
        "costs and GHG emissions."
    ),
    relevant_modules=[
        "OPC UA Client/Server", "Modbus TCP/RTU Integration", "MTConnect Adapter",
        "SCADA Dashboard", "PackML State Machine", "ISA-88/ISA-95 Compliance",
        "Predictive Maintenance Engine", "Manufacturing Analytics", "ERP Integration (SAP/Oracle)",
        "MES Integration", "Additive Manufacturing Monitor", "Process Digital Twin",
        "Quality Management System (QMS)", "Supply Chain Optimizer",
    ],
    relevant_grant_categories=[
        GrantCategory.FEDERAL_GRANT,
        GrantCategory.FEDERAL_TAX_CREDIT,
        GrantCategory.USDA_PROGRAM,
    ],
    target_grants=[
        "doe_amo", "cesmii", "nist_mep", "sbir_phase1", "sbir_phase2",
        "arpa_e", "sec_48c", "rd_credit_sec41", "eda_tech_hubs",
    ],
    tech_highlights=[
        "OPC UA, Modbus TCP/RTU, DNP3, MTConnect protocol support",
        "ISA-95 / ISA-88 / PackML compliance",
        "AI predictive maintenance (20–40% downtime reduction)",
        "Natural language SCADA supervision",
        "Additive manufacturing integration (Stratasys, Markforged, EOS)",
        "Unified OT/IT data fabric",
        "CESMII Smart Manufacturing Platform compatible",
        "Real-time process digital twin",
    ],
    naics_codes=["333249", "541512", "811310"],  # Machinery mfg, computer systems design, industrial machinery repair
    keywords=["smart manufacturing", "SCADA", "OPC UA", "MTConnect", "PackML", "ISA-95",
              "industrial IoT", "predictive maintenance", "OT/IT convergence", "additive manufacturing"],
)

# ---------------------------------------------------------------------------
# General Flavor — For EDA, SBA, general business grants
# ---------------------------------------------------------------------------
GENERAL_PROFILE = GrantProfile(
    flavor=GrantFlavor.GENERAL,
    name="Murphy System — General Business Automation Profile",
    positioning=(
        CORE_POSITIONING + "\n\n"
        "For general business and economic development grant applications, Murphy is a "
        "universal business automation platform that enables any organization to automate "
        "complex workflows through natural language. Murphy's NL→DAG→Execute architecture "
        "allows business users — not just engineers — to create governed, auditable "
        "automation for any business process. With 90+ pre-built integrations (CRM, ERP, "
        "communication, data, cloud, IoT), Murphy connects every tool a business uses into "
        "a unified automation fabric."
    ),
    innovation_narrative=(
        "Murphy democratizes enterprise automation:\n\n"
        "1. **Natural Language Automation:** Any employee can describe a complex multi-step "
        "workflow in plain English and have Murphy compile it into an executable automation "
        "plan — no coding required.\n\n"
        "2. **Visual Workflow Canvas:** A drag-and-drop DAG editor allows visual workflow "
        "design with real-time execution preview.\n\n"
        "3. **90+ Integrations:** Murphy connects Salesforce, HubSpot, SAP, Slack, Teams, "
        "Gmail, QuickBooks, Stripe, GitHub, AWS, and 80+ other platforms out of the box.\n\n"
        "4. **SOC 2 Type II Compliance:** Enterprise-grade security and compliance built "
        "into every automation — audit trails, role-based access, data encryption."
    ),
    job_creation_narrative=(
        "Murphy creates jobs by enabling small businesses to operate at enterprise scale. "
        "By automating routine work, Murphy frees employees for higher-value activities — "
        "customer service, innovation, business development. Murphy projects support for "
        "500+ small businesses within 2 years, enabling each to grow revenue without "
        "proportional headcount increases."
    ),
    energy_impact_narrative=(
        "Murphy reduces the carbon footprint of business operations by optimizing "
        "data center usage, automating energy-aware scheduling, and integrating with "
        "building controls to reduce office energy consumption."
    ),
    relevant_modules=[
        "NL→DAG Compiler", "Visual Workflow Canvas", "90+ Integration Library",
        "CRM Integration (Salesforce, HubSpot)", "ERP Integration (SAP, Oracle, QuickBooks)",
        "Communication Integration (Slack, Teams, Email)", "Data Integration (PostgreSQL, MySQL, BigQuery)",
        "SOC 2 Compliance Layer", "Multi-tenant RBAC", "Audit Trail Engine",
        "Workflow Version Control", "Scheduled Automation", "Event-Driven Triggers",
    ],
    relevant_grant_categories=[
        GrantCategory.FEDERAL_GRANT,
        GrantCategory.SBA_FINANCING,
        GrantCategory.STATE_INCENTIVE,
    ],
    target_grants=[
        "sbir_phase1", "eda_build_to_scale", "eda_tech_hubs",
        "sba_microloan", "sba_7a", "rd_credit_sec41",
    ],
    tech_highlights=[
        "Natural language → DAG → Execute (NL→DAG→Execute)",
        "Visual workflow canvas with drag-and-drop",
        "90+ pre-built integrations",
        "SOC 2 Type II compliance framework",
        "Multi-tenant RBAC with audit trails",
        "Event-driven and scheduled automation",
        "REST API for any custom integration",
        "Agentic AI with human-in-the-loop controls",
    ],
    naics_codes=["541512", "541519", "561110"],  # Computer systems design, other IT services, office admin
    keywords=["business automation", "workflow automation", "NL→DAG", "no-code automation",
              "enterprise integration", "SOC 2", "multi-tenant", "agentic AI"],
)


# ---------------------------------------------------------------------------
# Profile registry
# ---------------------------------------------------------------------------
_PROFILES: Dict[GrantFlavor, GrantProfile] = {
    GrantFlavor.RD: RD_PROFILE,
    GrantFlavor.ENERGY: ENERGY_PROFILE,
    GrantFlavor.MANUFACTURING: MANUFACTURING_PROFILE,
    GrantFlavor.GENERAL: GENERAL_PROFILE,
}


def get_profile(flavor: GrantFlavor) -> Optional[GrantProfile]:
    """Return the Murphy grant profile for a specific flavor."""
    return _PROFILES.get(flavor)


def get_all_profiles() -> List[GrantProfile]:
    """Return all Murphy grant profiles."""
    return list(_PROFILES.values())


def get_mvp_modules(grant_type: str) -> List[str]:
    """
    Return the relevant subset of Murphy's modules for a specific grant type.

    Args:
        grant_type: One of 'rd', 'energy', 'manufacturing', 'general', or a grant ID.

    Returns:
        List of module names relevant to the grant type.
    """
    flavor_map = {
        "rd": GrantFlavor.RD,
        "research": GrantFlavor.RD,
        "innovation": GrantFlavor.RD,
        "sbir": GrantFlavor.RD,
        "sttr": GrantFlavor.RD,
        "arpa_e": GrantFlavor.RD,
        "energy": GrantFlavor.ENERGY,
        "building": GrantFlavor.ENERGY,
        "bas_bms": GrantFlavor.ENERGY,
        "ems": GrantFlavor.ENERGY,
        "bto": GrantFlavor.ENERGY,
        "manufacturing": GrantFlavor.MANUFACTURING,
        "industrial": GrantFlavor.MANUFACTURING,
        "scada": GrantFlavor.MANUFACTURING,
        "amo": GrantFlavor.MANUFACTURING,
        "cesmii": GrantFlavor.MANUFACTURING,
        "general": GrantFlavor.GENERAL,
        "business": GrantFlavor.GENERAL,
        "eda": GrantFlavor.GENERAL,
    }

    flavor = flavor_map.get(grant_type.lower(), GrantFlavor.GENERAL)
    profile = get_profile(flavor)
    return profile.relevant_modules if profile else []
