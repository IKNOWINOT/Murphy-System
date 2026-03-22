"""Federal grant programs relevant to Murphy System (SBIR, DOE, NSF, EDA, NIST)."""

from __future__ import annotations

from typing import List

from src.billing.grants.models import Grant, ProgramType

_MURPHY_VERTICALS = [
    "agentic",
    "building_automation",
    "energy_management",
    "hvac_controls",
    "industrial_iot",
    "smart_manufacturing",
    "ai_ml",
    "software",
]

_SB_TYPES = ["small_business", "startup"]


def get_federal_grants() -> List[Grant]:
    """Return fully populated Grant objects for federal grant programs."""
    return [
        Grant(
            id="sbir_phase1",
            name="SBIR Phase I — Small Business Innovation Research",
            program_type=ProgramType.federal_grant,
            agency="Multiple Federal Agencies (DOE, NSF, DOD, etc.)",
            description=(
                "Feasibility study funding for small businesses to explore technical "
                "merit and commercial potential of innovative research. Murphy System "
                "AI orchestration, NL→DAG, and autonomous controls qualify across "
                "multiple agency programs."
            ),
            min_amount=50_000.0,
            max_amount=275_000.0,
            eligible_entity_types=_SB_TYPES,
            eligible_verticals=_MURPHY_VERTICALS,
            eligible_states=[],
            application_url="https://www.sbir.gov/apply",
            deadline_pattern="Agency-specific; year-round solicitations",
            longevity_years=10,
            requirements=[
                "U.S.-owned small business (< 500 employees)",
                "Principal investigator primarily employed by applicant",
                "At least 2/3 of work performed by applicant",
                "EIN and SAM.gov registration required",
            ],
            tags=["sbir", "r_and_d", "feasibility", "competitive"],
        ),
        Grant(
            id="sbir_phase2",
            name="SBIR Phase II — Full R&D Development",
            program_type=ProgramType.federal_grant,
            agency="Multiple Federal Agencies (DOE, NSF, DOD, etc.)",
            description=(
                "Full R&D funding to develop and commercialize Phase I innovations. "
                "Murphy System can seek Phase II for autonomous workflow engine, "
                "confidence-gated execution, and enterprise AI deployment platforms."
            ),
            min_amount=750_000.0,
            max_amount=1_750_000.0,
            eligible_entity_types=_SB_TYPES,
            eligible_verticals=_MURPHY_VERTICALS,
            eligible_states=[],
            application_url="https://www.sbir.gov/apply",
            deadline_pattern="Requires successful Phase I; agency-specific deadlines",
            longevity_years=10,
            requirements=[
                "Successful Phase I completion or Phase I equivalent",
                "U.S.-owned small business (< 500 employees)",
                "Commercialization plan required",
                "At least 1/2 of work performed by applicant",
            ],
            tags=["sbir", "r_and_d", "full_development", "commercialization"],
        ),
        Grant(
            id="sbir_breakthrough",
            name="SBIR Strategic Breakthrough — Direct-to-Phase-II / Large Awards",
            program_type=ProgramType.federal_grant,
            agency="DOD / DARPA / ARPA-E",
            description=(
                "Large strategic SBIR awards for breakthrough technologies. DARPA "
                "and ARPA-E issue broad agency announcements for transformative "
                "technologies including autonomous systems, AI, and energy innovation."
            ),
            min_amount=1_000_000.0,
            max_amount=30_000_000.0,
            eligible_entity_types=_SB_TYPES + ["corporation"],
            eligible_verticals=_MURPHY_VERTICALS + ["defense_tech", "autonomous_systems"],
            eligible_states=[],
            application_url="https://www.darpa.mil/work-with-us/opportunities",
            deadline_pattern="BAA-specific; monitor DARPA/ARPA-E announcements",
            longevity_years=10,
            requirements=[
                "Response to specific BAA or SBIR solicitation",
                "Technical volume with strong innovation narrative",
                "Team qualifications and past performance",
                "Cost proposal with detailed budget",
            ],
            tags=["sbir", "darpa", "breakthrough", "large_award"],
        ),
        Grant(
            id="sttr",
            name="STTR — Small Business Technology Transfer",
            program_type=ProgramType.federal_grant,
            agency="Multiple Federal Agencies (DOE, NSF, DOD, NIH, NASA)",
            description=(
                "Like SBIR but requires formal collaboration with a U.S. research "
                "institution. Murphy System academic partnerships for AI research, "
                "controls theory, and human-machine teaming qualify."
            ),
            min_amount=50_000.0,
            max_amount=1_750_000.0,
            eligible_entity_types=_SB_TYPES,
            eligible_verticals=_MURPHY_VERTICALS,
            eligible_states=[],
            application_url="https://www.sbir.gov/apply",
            deadline_pattern="Agency-specific; often concurrent with SBIR solicitations",
            longevity_years=10,
            requirements=[
                "Formal collaboration agreement with U.S. research institution",
                "At least 40% of work by applicant small business",
                "At least 30% of work by research institution partner",
                "SAM.gov registration required",
            ],
            tags=["sttr", "academic_partnership", "r_and_d"],
        ),
        Grant(
            id="doe_arpa_e",
            name="DOE ARPA-E — Advanced Research Projects Agency-Energy",
            program_type=ProgramType.federal_grant,
            agency="U.S. Department of Energy — ARPA-E",
            description=(
                "Funding for transformational energy technology R&D. Murphy System "
                "grid-interactive AI, demand response optimization, and autonomous "
                "building energy management align with ARPA-E program areas."
            ),
            min_amount=500_000.0,
            max_amount=10_000_000.0,
            eligible_entity_types=_SB_TYPES + ["corporation", "university", "nonprofit"],
            eligible_verticals=_MURPHY_VERTICALS + ["grid_management", "energy_storage"],
            eligible_states=[],
            application_url="https://arpa-e.energy.gov/technologies/apply-for-funding",
            deadline_pattern="FOA-specific; monitor ARPA-E announcements",
            longevity_years=10,
            requirements=[
                "Response to specific ARPA-E FOA",
                "High technical risk/high potential impact",
                "Clear plan to move beyond current state of the art",
                "Commercialization pathway required",
            ],
            tags=["doe", "arpa_e", "transformational", "energy_tech"],
        ),
        Grant(
            id="doe_amo",
            name="DOE Advanced Manufacturing Office (AMO) Funding",
            program_type=ProgramType.federal_grant,
            agency="U.S. Department of Energy — Advanced Manufacturing Office",
            description=(
                "R&D funding for advanced manufacturing technologies that improve "
                "energy efficiency. Murphy System industrial IoT, SCADA integration, "
                "and smart manufacturing controls directly qualify."
            ),
            min_amount=100_000.0,
            max_amount=5_000_000.0,
            eligible_entity_types=_SB_TYPES + ["corporation", "university", "national_lab"],
            eligible_verticals=["smart_manufacturing", "industrial_iot", "energy_management"],
            eligible_states=[],
            application_url="https://www.energy.gov/eere/amo/advanced-manufacturing-office",
            deadline_pattern="FOA-specific; check EERE Exchange for current FOAs",
            longevity_years=10,
            requirements=[
                "Response to active AMO FOA",
                "Cost-sharing typically 20-50%",
                "Technology must demonstrate significant energy savings",
                "SAM.gov registration required",
            ],
            tags=["doe", "amo", "manufacturing", "energy_efficiency"],
        ),
        Grant(
            id="doe_bto",
            name="DOE Building Technologies Office (BTO) Funding",
            program_type=ProgramType.federal_grant,
            agency="U.S. Department of Energy — Building Technologies Office",
            description=(
                "R&D funding for building energy efficiency technologies. Murphy System "
                "building automation, HVAC controls, occupancy sensing, and grid-interactive "
                "buildings directly align with BTO program goals."
            ),
            min_amount=100_000.0,
            max_amount=5_000_000.0,
            eligible_entity_types=_SB_TYPES + ["corporation", "university"],
            eligible_verticals=["building_automation", "hvac_controls", "energy_management"],
            eligible_states=[],
            application_url="https://www.energy.gov/eere/buildings/building-technologies-office",
            deadline_pattern="FOA-specific; check EERE Exchange for current FOAs",
            longevity_years=10,
            requirements=[
                "Response to active BTO FOA",
                "Demonstrated energy savings potential",
                "Cost-sharing typically 20-50%",
                "SAM.gov registration required",
            ],
            tags=["doe", "bto", "buildings", "hvac", "grid_interactive"],
        ),
        Grant(
            id="cesmii",
            name="CESMII — Clean Energy Smart Manufacturing Innovation Institute",
            program_type=ProgramType.federal_grant,
            agency="DOE / CESMII",
            description=(
                "Funding through the CESMII institute for smart manufacturing platform "
                "development and deployment. Murphy System industrial IoT platform and "
                "AI-driven process optimization are directly relevant."
            ),
            min_amount=50_000.0,
            max_amount=2_000_000.0,
            eligible_entity_types=_SB_TYPES + ["corporation", "university"],
            eligible_verticals=["smart_manufacturing", "industrial_iot", "energy_management"],
            eligible_states=[],
            application_url="https://www.cesmii.org/membership",
            deadline_pattern="Rolling project calls; check CESMII website",
            longevity_years=10,
            requirements=[
                "CESMII membership or partnership",
                "Smart manufacturing platform relevance",
                "Collaboration with institute members encouraged",
            ],
            tags=["cesmii", "smart_manufacturing", "institute", "iot"],
        ),
        Grant(
            id="nsf_convergence",
            name="NSF Convergence Accelerator",
            program_type=ProgramType.federal_grant,
            agency="National Science Foundation",
            description=(
                "NSF program for use-inspired convergence research addressing national "
                "challenges. Murphy System AI orchestration and autonomous decision-making "
                "aligns with tracks on AI, Future of Work, and Sustainable Materials."
            ),
            min_amount=750_000.0,
            max_amount=5_000_000.0,
            eligible_entity_types=_SB_TYPES + ["university", "nonprofit", "corporation"],
            eligible_verticals=_MURPHY_VERTICALS,
            eligible_states=[],
            application_url="https://www.nsf.gov/convergenceaccelerator",
            deadline_pattern="Annual cohort cycles; Phase I then Phase II",
            longevity_years=10,
            requirements=[
                "Response to active NSF Convergence Accelerator track",
                "Multi-stakeholder team encouraged",
                "Use-inspired research with near-term deliverables",
                "Technology Transfer Office involvement for universities",
            ],
            tags=["nsf", "convergence", "use_inspired", "ai", "phase_model"],
        ),
        Grant(
            id="nsf_pfi",
            name="NSF Partnerships for Innovation (PFI)",
            program_type=ProgramType.federal_grant,
            agency="National Science Foundation",
            description=(
                "NSF program to accelerate commercialization of NSF-funded research. "
                "Murphy System can pursue PFI-TT (Technology Translation) or PFI-RP "
                "(Research Partnerships) for AI automation technology."
            ),
            min_amount=250_000.0,
            max_amount=1_000_000.0,
            eligible_entity_types=_SB_TYPES + ["university"],
            eligible_verticals=_MURPHY_VERTICALS,
            eligible_states=[],
            application_url="https://www.nsf.gov/funding/pgm_summ.jsp?pims_id=504900",
            deadline_pattern="Annual solicitation; typically January deadline",
            longevity_years=10,
            requirements=[
                "Prior NSF funding or collaboration with NSF-funded researcher",
                "Clear commercialization pathway",
                "Industry partner required for PFI-TT",
                "Mentorship and I-Corps training expected",
            ],
            tags=["nsf", "pfi", "commercialization", "tech_transfer"],
        ),
        Grant(
            id="eda_b2s",
            name="EDA Build to Scale (B2S) Program",
            program_type=ProgramType.federal_grant,
            agency="Economic Development Administration",
            description=(
                "EDA program to build regional innovation ecosystems and scale "
                "startups. Murphy System can leverage B2S for regional expansion "
                "and ecosystem development partnerships."
            ),
            min_amount=500_000.0,
            max_amount=2_000_000.0,
            eligible_entity_types=["nonprofit", "university", "government", "small_business"],
            eligible_verticals=_MURPHY_VERTICALS,
            eligible_states=[],
            application_url="https://www.eda.gov/funding/programs/build-to-scale",
            deadline_pattern="Annual NOFO; typically spring",
            longevity_years=10,
            requirements=[
                "Regional economic impact potential",
                "Non-federal cost match required (1:1)",
                "Ecosystem building focus not direct company funding",
                "Collaboration with regional stakeholders",
            ],
            tags=["eda", "ecosystem", "regional", "scale"],
        ),
        Grant(
            id="nist_mep",
            name="NIST MEP — Manufacturing Extension Partnership",
            program_type=ProgramType.federal_grant,
            agency="NIST / MEP National Network",
            description=(
                "Technical assistance and voucher programs for small and mid-size "
                "manufacturers through NIST MEP centers. Murphy System manufacturing "
                "customers can access subsidized implementation and consulting services."
            ),
            min_amount=5_000.0,
            max_amount=100_000.0,
            eligible_entity_types=["small_business", "manufacturer"],
            eligible_verticals=["smart_manufacturing", "industrial_iot", "energy_management"],
            eligible_states=[],
            application_url="https://www.nist.gov/mep",
            deadline_pattern="Rolling through local MEP center; no federal deadline",
            longevity_years=10,
            requirements=[
                "Small or mid-size manufacturer (< 500 employees)",
                "Work with local MEP center",
                "Technology adoption project plan",
                "Cost share typically required",
            ],
            tags=["nist", "mep", "manufacturer", "technical_assistance"],
        ),
        Grant(
            id="doe_grip",
            name="DOE Grid Resilience and Innovation Partnerships (GRIP)",
            program_type=ProgramType.federal_grant,
            agency="U.S. Department of Energy — GRIP Program",
            description=(
                "Grid infrastructure funding for modernization, resilience, and clean "
                "energy integration. Murphy System grid-interactive buildings and demand "
                "response optimization support GRIP project goals."
            ),
            min_amount=1_000_000.0,
            max_amount=3_000_000_000.0,
            eligible_entity_types=["utility", "corporation", "government", "nonprofit"],
            eligible_verticals=["energy_management", "grid_management", "building_automation"],
            eligible_states=[],
            application_url="https://www.energy.gov/gdo/grid-resilience-and-innovation-partnerships-grip-program",
            deadline_pattern="NOFO-specific; program ongoing through IRA funding",
            longevity_years=10,
            requirements=[
                "Grid resilience or innovation project",
                "50% cost share required",
                "Utility or grid operator partnership often required",
                "SAM.gov registration required",
            ],
            tags=["doe", "grip", "grid", "resilience", "large_scale"],
        ),
    ]
