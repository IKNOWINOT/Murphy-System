"""
Federal Grants — SBIR, STTR, ARPA-E, AMO, BTO, CESMII, NSF, EDA and more.

Focus on programs with 10+ year longevity relevant to:
  • Track A: Murphy/Inoni LLC R&D grant applications
  • Track B: Customer automation projects (smart manufacturing, energy, IoT)

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

from src.billing.grants.models import Grant, GrantCategory, GrantTrack

# ---------------------------------------------------------------------------
# SBIR — Small Business Innovation Research
# ---------------------------------------------------------------------------
SBIR_PHASE1 = Grant(
    id="sbir_phase1",
    name="SBIR Phase I — Proof of Concept",
    category=GrantCategory.FEDERAL_GRANT,
    track=GrantTrack.TRACK_A,
    short_description="$50K–$275K non-dilutive grant for proof-of-concept R&D. No IP surrender. Reauthorized through 2031.",
    long_description=(
        "The Small Business Innovation Research (SBIR) Phase I award funds feasibility and "
        "proof-of-concept research for small businesses. Award sizes vary by agency: NSF $275K, "
        "DOE $225K, NIH $275K, DoD $50–$250K. No equity given up — 100% non-dilutive. The "
        "company retains IP rights. Phase I typically runs 6–12 months. For Inoni LLC / Murphy "
        "System, SBIR Phase I is best targeted at: DOE (smart manufacturing, grid-interactive "
        "buildings, industrial energy optimization) and NSF (AI/ML orchestration, autonomous "
        "systems, human-in-the-loop AI). SBIR was reauthorized through Sept 30, 2031 via the "
        "SBA SBIR/STTR Reauthorization Act. Murphy's R&D flavor profile is the correct "
        "application identity for this grant."
    ),
    agency_or_provider="Multiple Federal Agencies (DOE, NSF, DoD, NIH, NASA, etc.)",
    program_url="https://www.sbir.gov/",
    application_url="https://www.sbir.gov/apply",
    min_amount_usd=50_000,
    max_amount_usd=275_000,
    value_description="$50K–$275K depending on agency; no equity",
    eligible_entity_types=["small_business"],
    eligible_project_types=["ai_platform", "software_rd", "automation_rd", "industrial_iot", "smart_manufacturing", "grid_interactive", "ems"],
    requires_rd_activity=True,
    is_recurring=True,
    program_expiry_year=2031,
    longevity_note="Reauthorized through Sept 30, 2031",
    stackable_with=["rd_credit_sec41", "state_rd_credits", "sbir_phase2"],
    tags=["sbir", "non_dilutive", "rd", "small_business", "track_a", "doe", "nsf"],
    last_updated="2024-01",
)

SBIR_PHASE2 = Grant(
    id="sbir_phase2",
    name="SBIR Phase II — Full R&D",
    category=GrantCategory.FEDERAL_GRANT,
    track=GrantTrack.TRACK_A,
    short_description="$750K–$1.75M to advance Phase I results into a full prototype or product.",
    long_description=(
        "SBIR Phase II provides substantially larger funding to advance Phase I proof-of-concept "
        "results. Award sizes: NSF $1M (up to $2M with supplementals), DOE $1.1M–$1.7M, "
        "DoD $750K–$1.75M. Phase II runs 18–24 months. Phase II companies are often eligible "
        "for Phase IIB (matching private investment) and Phase III (commercialization). For "
        "Murphy System, Phase II would fund full productization of the agentic AI orchestration "
        "engine, multi-LLM routing infrastructure, and industrial protocol integrations. "
        "Requires completion of Phase I with the same agency. SBIR reauthorized through 2031."
    ),
    agency_or_provider="Multiple Federal Agencies (DOE, NSF, DoD, NIH, NASA, etc.)",
    program_url="https://www.sbir.gov/",
    application_url="https://www.sbir.gov/apply",
    min_amount_usd=750_000,
    max_amount_usd=1_750_000,
    value_description="$750K–$1.75M; Phase IIB available with matching investment",
    eligible_entity_types=["small_business"],
    eligible_project_types=["ai_platform", "software_rd", "automation_rd", "industrial_iot", "smart_manufacturing"],
    requires_rd_activity=True,
    is_recurring=True,
    program_expiry_year=2031,
    longevity_note="Reauthorized through Sept 30, 2031",
    stackable_with=["rd_credit_sec41", "state_rd_credits", "sbir_phase1"],
    tags=["sbir", "non_dilutive", "rd", "small_business", "track_a", "phase2"],
    last_updated="2024-01",
)

SBIR_STRATEGIC = Grant(
    id="sbir_strategic_breakthrough",
    name="SBIR / STTR Strategic Breakthrough Award",
    category=GrantCategory.FEDERAL_GRANT,
    track=GrantTrack.TRACK_A,
    short_description="Up to $30M for transformative R&D with significant commercial potential (agency-specific programs).",
    long_description=(
        "Several agencies offer expanded SBIR/STTR-adjacent programs for transformative research: "
        "DOE's ARPA-E OPEN (up to $10M+), NSF's Convergence Accelerator (up to $5M), and "
        "agency-specific 'strategic breakthrough' awards. These target innovations that can "
        "fundamentally change an industry. For Murphy System, this tier applies to the universal "
        "automation platform concept — a single system spanning industrial, building, energy, and "
        "business domains with agentic AI execution. The cross-agency, cross-vertical nature of "
        "Murphy makes it a strong candidate for transformative programs."
    ),
    agency_or_provider="DOE ARPA-E, NSF, Multiple Agencies",
    program_url="https://arpa-e.energy.gov/",
    application_url="https://arpa-e.energy.gov/apply",
    min_amount_usd=5_000_000,
    max_amount_usd=30_000_000,
    value_description="Up to $30M; agency and program dependent",
    eligible_entity_types=["small_business"],
    eligible_project_types=["ai_platform", "automation_rd", "universal_automation", "industrial_iot"],
    requires_rd_activity=True,
    is_recurring=True,
    longevity_note="Rolling — ARPA-E and NSF have recurring OPEN solicitations",
    stackable_with=["rd_credit_sec41"],
    tags=["sbir", "arpa_e", "nsf", "transformative", "track_a", "large_award"],
    last_updated="2024-01",
)

# ---------------------------------------------------------------------------
# STTR — Small Business Technology Transfer
# ---------------------------------------------------------------------------
STTR = Grant(
    id="sttr",
    name="STTR — Small Business Technology Transfer",
    category=GrantCategory.FEDERAL_GRANT,
    track=GrantTrack.TRACK_A,
    short_description="$50K–$1.75M for R&D partnerships between small businesses and research institutions.",
    long_description=(
        "STTR requires a formal partnership between a small business and a U.S. research "
        "institution (university, federally funded R&D center, or nonprofit). At least 40% of "
        "work must be performed by the small business; at least 30% by the research partner. "
        "Phase I: $50K–$275K; Phase II: $750K–$1.75M. Funded by NSF, NIH, DoD, DOE, NASA. "
        "For Murphy System, STTR enables partnership with university researchers working on "
        "AI/ML, autonomous systems, industrial IoT, or energy systems. Oregon State University, "
        "MIT, CMU, Georgia Tech, and NREL are strong potential STTR partners aligned with "
        "Murphy's technology domains. Reauthorized through 2031."
    ),
    agency_or_provider="Multiple Federal Agencies (DOE, NSF, DoD, NIH, NASA)",
    program_url="https://www.sbir.gov/sttr",
    application_url="https://www.sbir.gov/apply",
    min_amount_usd=50_000,
    max_amount_usd=1_750_000,
    value_description="Phase I: $50K–$275K; Phase II: $750K–$1.75M",
    eligible_entity_types=["small_business"],
    eligible_project_types=["ai_platform", "software_rd", "automation_rd", "industrial_iot"],
    requires_rd_activity=True,
    is_recurring=True,
    program_expiry_year=2031,
    longevity_note="Reauthorized through Sept 30, 2031",
    stackable_with=["rd_credit_sec41", "sbir_phase1"],
    tags=["sttr", "university_partnership", "non_dilutive", "track_a"],
    last_updated="2024-01",
)

# ---------------------------------------------------------------------------
# DOE ARPA-E
# ---------------------------------------------------------------------------
ARPA_E = Grant(
    id="arpa_e",
    name="DOE ARPA-E — Advanced Research Projects Agency-Energy",
    category=GrantCategory.FEDERAL_GRANT,
    track=GrantTrack.TRACK_A,
    short_description="Up to $10M+ for transformative energy technology R&D. High risk, high reward. OPEN and focused programs.",
    long_description=(
        "ARPA-E funds transformative energy R&D projects that are too early-stage or high-risk "
        "for private investment. OPEN solicitations (2–3x/decade) accept any energy technology. "
        "Focused programs target specific challenges. Average award: $1–5M; exceptional projects "
        "receive $10M+. ARPA-E maintains a program of ~60 active projects at any given time. "
        "For Murphy System, ARPA-E OPEN is the ideal target: grid-interactive building automation, "
        "AI-optimized energy dispatch, demand response automation, and smart manufacturing energy "
        "optimization are all ARPA-E-relevant. The combination of real-time control theory with "
        "agentic AI execution is a novel technical approach ARPA-E favors. No match required. "
        "Not limited to small businesses (but small businesses are competitive)."
    ),
    agency_or_provider="U.S. Department of Energy — ARPA-E",
    program_url="https://arpa-e.energy.gov/",
    application_url="https://arpa-e-foa.energy.gov/",
    min_amount_usd=500_000,
    max_amount_usd=10_000_000,
    value_description="$500K–$10M+; average $1–5M",
    eligible_entity_types=["small_business", "corporation", "university", "nonprofit"],
    eligible_project_types=["ai_platform", "grid_interactive", "ems", "demand_response", "industrial_iot", "smart_manufacturing"],
    requires_rd_activity=True,
    is_recurring=True,
    longevity_note="Permanent DOE program; OPEN solicitations every 2-3 years",
    stackable_with=["rd_credit_sec41", "sbir_phase1"],
    tags=["arpa_e", "doe", "energy", "transformative", "track_a", "high_risk"],
    last_updated="2024-01",
)

# ---------------------------------------------------------------------------
# DOE AMO / IEDO — Advanced Manufacturing Office
# ---------------------------------------------------------------------------
DOE_AMO = Grant(
    id="doe_amo",
    name="DOE Advanced Manufacturing Office (AMO) / IEDO Grants",
    category=GrantCategory.FEDERAL_GRANT,
    track=GrantTrack.BOTH,
    short_description="Competitive grants for advanced manufacturing, smart manufacturing, and industrial energy efficiency.",
    long_description=(
        "DOE's Advanced Manufacturing Office (AMO) and Industrial Efficiency & Decarbonization "
        "Office (IEDO) fund projects that advance U.S. manufacturing competitiveness and reduce "
        "industrial energy use. Key programs include: BIL/IRA-funded Industrial Demonstrations "
        "(up to $500M for large industrial projects), Innovative and Novel Computational Impact "
        "on Theory and Experiment (INCITE), and recurring AMO FOAs for smart manufacturing "
        "technology development. For Murphy System, AMO funds the manufacturing flavor: "
        "SCADA automation, OPC UA integration, energy optimization in industrial facilities, "
        "PackML/ISA-95 implementation, and additive manufacturing process control. For customers, "
        "AMO funds facility upgrades that include smart controls and energy management systems."
    ),
    agency_or_provider="DOE Office of Energy Efficiency & Renewable Energy (EERE) — AMO/IEDO",
    program_url="https://www.energy.gov/eere/amo/advanced-manufacturing-office",
    application_url="https://eere-exchange.energy.gov/",
    min_amount_usd=100_000,
    max_amount_usd=5_000_000,
    value_description="Varies widely; $100K–$5M for most programs; up to $500M for large industrial demos",
    eligible_entity_types=["small_business", "corporation", "university", "nonprofit"],
    eligible_project_types=["manufacturing_automation", "smart_manufacturing", "industrial_iot", "scada", "ems", "industrial_decarbonization"],
    requires_rd_activity=True,
    is_recurring=True,
    longevity_note="Ongoing AMO program with annual FOAs; IRA + BIL funded through 2030+",
    stackable_with=["rd_credit_sec41", "sbir_phase1", "sec_48c"],
    tags=["doe", "manufacturing", "amo", "iedo", "smart_manufacturing", "industrial_energy"],
    last_updated="2024-01",
)

# ---------------------------------------------------------------------------
# DOE BTO — Building Technologies Office
# ---------------------------------------------------------------------------
DOE_BTO = Grant(
    id="doe_bto",
    name="DOE Building Technologies Office (BTO) Grants",
    category=GrantCategory.FEDERAL_GRANT,
    track=GrantTrack.BOTH,
    short_description="R&D and deployment funding for advanced building systems, grid-interactive buildings, and BAS.",
    long_description=(
        "DOE's Building Technologies Office (BTO) funds research, development, and deployment "
        "of advanced building technologies including: Grid-Interactive Efficient Buildings (GEB), "
        "advanced controls for HVAC/lighting/plug loads, high-performance building envelopes, "
        "and connected building systems. BTO issues FOAs for commercial and residential building "
        "technology demonstrations. For Murphy System, BTO's GEB program is highly relevant: "
        "Murphy's BAS/BMS capabilities enable demand flexibility, automated DR participation, "
        "and occupant-aware control — core GEB requirements. BTO also funds the OpenBuildingControl "
        "initiative and BACnet/BRICK schema projects that Murphy integrates with. Average awards: "
        "$500K–$5M for R&D; up to $50M for large demonstration projects."
    ),
    agency_or_provider="DOE Office of Energy Efficiency & Renewable Energy (EERE) — BTO",
    program_url="https://www.energy.gov/eere/buildings/building-technologies-office",
    application_url="https://eere-exchange.energy.gov/",
    min_amount_usd=250_000,
    max_amount_usd=5_000_000,
    value_description="$250K–$5M for R&D; up to $50M for large demos",
    eligible_entity_types=["small_business", "corporation", "university", "nonprofit"],
    eligible_project_types=["bas_bms", "ems", "grid_interactive", "demand_response", "hvac_automation", "smart_building"],
    requires_rd_activity=True,
    is_recurring=True,
    longevity_note="Ongoing BTO program; IRA + BIL funded through 2030+",
    stackable_with=["sec_179d", "sec_48_itc", "rd_credit_sec41", "sbir_phase1"],
    tags=["doe", "bto", "buildings", "bas_bms", "grid_interactive", "geb", "demand_response"],
    last_updated="2024-01",
)

# ---------------------------------------------------------------------------
# DOE GRIP — Grid Resilience and Innovation Partnerships
# ---------------------------------------------------------------------------
DOE_GRIP = Grant(
    id="doe_grip",
    name="DOE GRIP — Grid Resilience and Innovation Partnerships",
    category=GrantCategory.FEDERAL_GRANT,
    track=GrantTrack.BOTH,
    short_description="Up to $3B total for grid modernization, resilience, and smart grid technology deployment.",
    long_description=(
        "The Grid Resilience and Innovation Partnerships (GRIP) program, funded by the "
        "Infrastructure Investment and Jobs Act (BIL), provides $10.5B over 5 years for grid "
        "resilience and grid innovation. GRIP FOAs include: Grid Resilience Grants (utility/co-op "
        "focused), Smart Grid Grants (technology innovation), and Grid Resilience Utility and "
        "Industry Grants. For Murphy System, Smart Grid Grants are most relevant: advanced "
        "metering, demand response automation platforms, grid-interactive building controls, "
        "and AI-optimized grid management all qualify. Murphy's EMS and demand response "
        "capabilities can serve as the control layer for GRIP-funded smart grid projects. "
        "Typical award: $1M–$100M; technology partners (like Murphy) often participate "
        "as subcontractors to utilities applying for GRIP."
    ),
    agency_or_provider="DOE Office of Electricity (OE)",
    program_url="https://www.energy.gov/oe/grid-resilience-and-innovation-partnerships-grip-program",
    application_url="https://www.grants.gov/",
    min_amount_usd=1_000_000,
    max_amount_usd=100_000_000,
    value_description="$1M–$100M per award; $10.5B total program",
    eligible_entity_types=["small_business", "corporation", "utility", "cooperative"],
    eligible_project_types=["grid_interactive", "demand_response", "ems", "smart_grid", "bas_bms"],
    is_recurring=True,
    longevity_note="BIL-funded through 2026; additional IRA grid funding through 2030+",
    stackable_with=["sec_48_itc", "sec_45y_ptc", "doe_bto"],
    tags=["doe", "smart_grid", "grid_resilience", "demand_response", "bil", "utility_partnership"],
    last_updated="2024-01",
)

# ---------------------------------------------------------------------------
# CESMII — Smart Manufacturing Institute
# ---------------------------------------------------------------------------
CESMII = Grant(
    id="cesmii",
    name="CESMII Smart Manufacturing Leadership Coalition",
    category=GrantCategory.FEDERAL_GRANT,
    track=GrantTrack.BOTH,
    short_description="DOE-funded smart manufacturing R&D, tools, and workforce programs for U.S. manufacturers.",
    long_description=(
        "The Clean Energy Smart Manufacturing Innovation Institute (CESMII), funded by DOE, "
        "advances smart manufacturing through R&D, technology deployment, and workforce "
        "development. CESMII maintains the Smart Manufacturing Platform (SMP) — an open "
        "industrial IoT platform — and issues competitive funding calls for smart manufacturing "
        "technology projects ($50K–$2M). Members (companies, universities, national labs) get "
        "access to shared R&D resources, the SMP, and co-funding opportunities. For Murphy "
        "System, CESMII membership enables: access to DOE-funded manufacturing R&D, deployment "
        "of Murphy's SCADA/OPC UA/MTConnect capabilities as SMP add-ons, co-funding for smart "
        "manufacturing demonstrations, and positioning Murphy as a CESMII-compatible platform. "
        "CESMII's mandate extends through DOE's Manufacturing USA initiative."
    ),
    agency_or_provider="DOE — CESMII / Manufacturing USA",
    program_url="https://www.cesmii.org/",
    application_url="https://www.cesmii.org/membership/",
    min_amount_usd=50_000,
    max_amount_usd=2_000_000,
    value_description="$50K–$2M for project calls; membership-based access to co-funding",
    eligible_entity_types=["small_business", "corporation", "university"],
    eligible_project_types=["smart_manufacturing", "manufacturing_automation", "industrial_iot", "scada", "opc_ua"],
    requires_rd_activity=True,
    is_recurring=True,
    longevity_note="Ongoing DOE Manufacturing USA program; multi-year mandate",
    stackable_with=["sbir_phase1", "doe_amo", "rd_credit_sec41"],
    tags=["cesmii", "smart_manufacturing", "doe", "manufacturing_usa", "industrial_iot", "membership"],
    last_updated="2024-01",
)

# ---------------------------------------------------------------------------
# NSF — National Science Foundation
# ---------------------------------------------------------------------------
NSF_CONVERGENCE = Grant(
    id="nsf_convergence_accelerator",
    name="NSF Convergence Accelerator",
    category=GrantCategory.FEDERAL_GRANT,
    track=GrantTrack.TRACK_A,
    short_description="Up to $5M for use-inspired research addressing national-scale societal challenges.",
    long_description=(
        "The NSF Convergence Accelerator funds use-inspired convergence research addressing "
        "national-scale challenges through a cohort model. Phase I: up to $750K (9 months); "
        "Phase II: up to $5M (24 months). Topics change each cycle; recent themes: AI for "
        "decision making, quantum technology, food and nutrition security. For Murphy System, "
        "the AI for Decision Making and autonomous systems tracks are directly relevant. "
        "Murphy's NL→DAG→Execute architecture, multi-LLM routing, and governance framework "
        "represent exactly the kind of use-inspired AI research the Convergence Accelerator "
        "targets. Phase I teams receive intensive coaching and must pivot toward societal impact. "
        "Competitive — cohorts of 20–40 teams selected per topic area."
    ),
    agency_or_provider="National Science Foundation (NSF)",
    program_url="https://www.nsf.gov/od/oia/convergence-accelerator/",
    application_url="https://beta.nsf.gov/funding/initiatives/convergence-accelerator",
    min_amount_usd=100_000,
    max_amount_usd=5_000_000,
    value_description="Phase I: up to $750K; Phase II: up to $5M",
    eligible_entity_types=["small_business", "university", "nonprofit", "corporation"],
    eligible_project_types=["ai_platform", "automation_rd", "software_rd"],
    requires_rd_activity=True,
    is_recurring=True,
    longevity_note="Annual new topic areas; cohort-based; ongoing NSF program",
    stackable_with=["rd_credit_sec41", "sbir_phase1"],
    tags=["nsf", "convergence", "ai", "use_inspired", "track_a", "cohort"],
    last_updated="2024-01",
)

NSF_PFI = Grant(
    id="nsf_pfi",
    name="NSF Partnerships for Innovation (PFI)",
    category=GrantCategory.FEDERAL_GRANT,
    track=GrantTrack.TRACK_A,
    short_description="$250K–$1M for translating NSF-funded research into commercial products and startups.",
    long_description=(
        "NSF PFI supports translation of NSF-funded research into commercial products, services, "
        "and companies. PFI-TT (Technology Translation): up to $250K for proof-of-concept. "
        "PFI-RP (Research Partnerships): up to $1M for industry-university partnerships. "
        "Requires prior NSF funding or connection to academic research. For Murphy System, "
        "PFI-TT is a path for commercializing academic AI/autonomous systems research through "
        "a partnership with a university PI. The I-Corps program (part of NSF's innovation "
        "ecosystem) is a prerequisite for many PFI awards and provides $50K for customer "
        "discovery — valuable for validating Murphy's market fit."
    ),
    agency_or_provider="National Science Foundation (NSF)",
    program_url="https://www.nsf.gov/pfi",
    application_url="https://www.nsf.gov/funding/pgm_summ.jsp?pims_id=504900",
    min_amount_usd=50_000,
    max_amount_usd=1_000_000,
    value_description="PFI-TT: up to $250K; PFI-RP: up to $1M",
    eligible_entity_types=["small_business", "university"],
    eligible_project_types=["ai_platform", "software_rd", "automation_rd"],
    requires_rd_activity=True,
    is_recurring=True,
    longevity_note="Ongoing NSF program; annual solicitations",
    stackable_with=["sbir_phase1", "sttr", "rd_credit_sec41"],
    tags=["nsf", "pfi", "commercialization", "university_partnership", "track_a"],
    last_updated="2024-01",
)

# ---------------------------------------------------------------------------
# EDA — Economic Development Administration
# ---------------------------------------------------------------------------
EDA_BUILD_TO_SCALE = Grant(
    id="eda_build_to_scale",
    name="EDA Build to Scale (B2S) Program",
    category=GrantCategory.FEDERAL_GRANT,
    track=GrantTrack.TRACK_A,
    short_description="$500K–$2M for scaling innovation-based startups. Capital Challenge and Venture Challenge tracks.",
    long_description=(
        "EDA's Build to Scale program supports regional innovation ecosystems and helps "
        "innovation-based companies scale. Two tracks: (1) Capital Challenge — supports "
        "organizations that help startups access capital ($500K–$2M); (2) Venture Challenge — "
        "supports organizations that identify and scale high-growth ventures ($500K–$2M). "
        "Awards go to organizations (accelerators, incubators, economic development orgs) that "
        "support startups like Murphy/Inoni. For Murphy, the path is through Oregon or regional "
        "economic development organizations (RAIN, Oregon BEST, Portland Seed Fund) that apply "
        "to EDA on behalf of their portfolio companies. Requires 50% match."
    ),
    agency_or_provider="U.S. Economic Development Administration (EDA)",
    program_url="https://www.eda.gov/funding/programs/build-to-scale",
    application_url="https://www.grants.gov/",
    min_amount_usd=500_000,
    max_amount_usd=2_000_000,
    value_description="$500K–$2M (50% match required; typically through ecosystem partner)",
    eligible_entity_types=["nonprofit", "university", "government"],
    eligible_project_types=["general_business_automation", "ai_platform", "automation_rd"],
    is_recurring=True,
    longevity_note="Annual EDA program; ongoing",
    stackable_with=["sbir_phase1", "rd_credit_sec41"],
    tags=["eda", "scaling", "innovation_ecosystem", "accelerator", "track_a"],
    last_updated="2024-01",
)

EDA_TECH_HUBS = Grant(
    id="eda_tech_hubs",
    name="EDA Regional Technology and Innovation Hubs (Tech Hubs)",
    category=GrantCategory.FEDERAL_GRANT,
    track=GrantTrack.TRACK_A,
    short_description="Up to $75M per hub for regional tech ecosystem development. CHIPS and Science Act funded.",
    long_description=(
        "EDA's Tech Hubs program, authorized by the CHIPS and Science Act, designates regional "
        "technology and innovation hubs and provides implementation grants of up to $75M per hub. "
        "Tech Hubs focus on critical technologies: semiconductors, clean energy, AI/ML, "
        "biotechnology, advanced manufacturing. Companies in designated hub regions can benefit "
        "from hub-funded R&D, workforce programs, and commercialization support. Oregon's "
        "semiconductor/clean tech ecosystem and potential hub designations are relevant for "
        "Inoni LLC. Companies participate as hub consortium members, not direct grantees. "
        "The program is ongoing with new hub designations and implementation grants."
    ),
    agency_or_provider="U.S. Economic Development Administration (EDA)",
    program_url="https://www.eda.gov/programs/tech-hubs",
    application_url="https://www.eda.gov/funding/programs/tech-hubs",
    min_amount_usd=5_000_000,
    max_amount_usd=75_000_000,
    value_description="Up to $75M per hub; consortium members benefit through hub programs",
    eligible_entity_types=["small_business", "corporation", "university", "nonprofit"],
    eligible_project_types=["ai_platform", "automation_rd", "smart_manufacturing", "industrial_iot"],
    is_recurring=True,
    longevity_note="CHIPS Act funded; multi-year program through 2030+",
    stackable_with=["sbir_phase1", "sec_48c"],
    tags=["eda", "tech_hubs", "chips_act", "regional", "clean_energy", "ai", "track_a"],
    last_updated="2024-01",
)

# ---------------------------------------------------------------------------
# NIST MEP
# ---------------------------------------------------------------------------
NIST_MEP = Grant(
    id="nist_mep",
    name="NIST Manufacturing Extension Partnership (MEP)",
    category=GrantCategory.FEDERAL_GRANT,
    track=GrantTrack.TRACK_B,
    short_description="Free or low-cost consulting and co-investment for U.S. manufacturers to adopt advanced technologies.",
    long_description=(
        "NIST's MEP National Network provides manufacturers with access to local MEP Centers "
        "for consulting, technology adoption assistance, and co-investment. Each state has at "
        "least one MEP Center (Oregon: Oregon Manufacturing Extension Partnership / Oregon MEP). "
        "Services include: lean manufacturing, quality systems, technology adoption (including "
        "automation, IoT, and smart manufacturing), workforce training, and supply chain "
        "optimization. Cost: subsidized (typically $500–$5K for projects that would cost "
        "$50K+ from private consultants). For Murphy customers in manufacturing, MEP Centers "
        "can co-fund automation pilot projects and provide a path to larger DOE AMO/CESMII "
        "investments. MEP has 1,400+ locations nationwide."
    ),
    agency_or_provider="NIST — National Institute of Standards and Technology",
    program_url="https://www.nist.gov/mep",
    application_url="https://www.nist.gov/mep/mep-national-network",
    min_amount_usd=0,
    max_amount_usd=250_000,
    value_description="Subsidized consulting; co-investment varies by center; typically $5K–$250K in services",
    eligible_entity_types=["small_business", "corporation"],
    eligible_project_types=["manufacturing_automation", "smart_manufacturing", "industrial_iot", "lean_manufacturing"],
    is_recurring=True,
    longevity_note="Permanent NIST program; nationwide network",
    stackable_with=["doe_amo", "cesmii", "sec_48c"],
    tags=["nist", "mep", "manufacturing", "consulting", "automation_adoption", "track_b"],
    last_updated="2024-01",
)


def get_federal_grants() -> list:
    """Return all federal grant objects."""
    return [
        SBIR_PHASE1,
        SBIR_PHASE2,
        SBIR_STRATEGIC,
        STTR,
        ARPA_E,
        DOE_AMO,
        DOE_BTO,
        DOE_GRIP,
        CESMII,
        NSF_CONVERGENCE,
        NSF_PFI,
        EDA_BUILD_TO_SCALE,
        EDA_TECH_HUBS,
        NIST_MEP,
    ]
