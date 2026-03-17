"""
LCM Domain Registry — Universal registry of every business domain Murphy can operate.

Design Label: LCM-001 — Domain Registry
Owner: Platform Engineering

Maps every real-world business domain to its gate-types, compliance standards,
connectors, and keywords so that the LCM engine can classify and route
intelligence without hard-coded domain knowledge.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class DomainCategory(Enum):
    PHYSICAL_MANUFACTURING = "physical_manufacturing"
    BUILDING_SYSTEMS = "building_systems"
    PROFESSIONAL_SERVICES = "professional_services"
    HEALTHCARE = "healthcare"
    ENERGY_UTILITIES = "energy_utilities"
    RETAIL_COMMERCE = "retail_commerce"
    FINANCIAL_SERVICES = "financial_services"
    MEDIA_COMMUNICATIONS = "media_communications"
    EDUCATION_NONPROFIT = "education_nonprofit"
    TRANSPORTATION_LOGISTICS = "transportation_logistics"


class GateType(Enum):
    SAFETY = "safety"
    QUALITY = "quality"
    COMPLIANCE = "compliance"
    PERFORMANCE = "performance"
    SECURITY = "security"
    BUSINESS = "business"
    ENERGY = "energy"
    COMFORT = "comfort"
    MONITORING = "monitoring"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class SubjectDomain:
    """Describes a single business domain Murphy can operate in."""
    domain_id: str
    name: str
    category: DomainCategory
    description: str
    gate_types: List[GateType]
    keywords: List[str]
    connectors: List[str] = field(default_factory=list)
    compliance_standards: List[str] = field(default_factory=list)
    priority: int = 0  # higher = more priority


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class LCMDomainRegistry:
    """Universal registry of all business domains Murphy can operate."""

    def __init__(self) -> None:
        self._domains: Dict[str, SubjectDomain] = {}
        self._lock = threading.RLock()
        self._build_registry()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(self, domain: SubjectDomain) -> None:
        """Register a domain."""
        with self._lock:
            self._domains[domain.domain_id] = domain

    def get(self, domain_id: str) -> Optional[SubjectDomain]:
        """Retrieve a domain by ID."""
        with self._lock:
            return self._domains.get(domain_id)

    def list_all(self) -> List[SubjectDomain]:
        """Return all registered domains."""
        with self._lock:
            return list(self._domains.values())

    def list_by_category(self, category: DomainCategory) -> List[SubjectDomain]:
        """Return all domains in a given category."""
        with self._lock:
            return [d for d in self._domains.values() if d.category == category]

    def get_gate_types(self, domain_id: str) -> List[GateType]:
        """Return gate types for a domain, empty list if not found."""
        domain = self.get(domain_id)
        return domain.gate_types if domain else []

    def __len__(self) -> int:
        with self._lock:
            return len(self._domains)

    # ------------------------------------------------------------------
    # Registry builder — all 50+ domains
    # ------------------------------------------------------------------

    def _build_registry(self) -> None:  # noqa: C901 (complex but intentional)
        """Populate the full domain registry."""
        domains: List[SubjectDomain] = [

            # ── 3D PRINTING ──────────────────────────────────────────────
            SubjectDomain(
                domain_id="3d_printing_fdm",
                name="3D Printing — FDM/FFF",
                category=DomainCategory.PHYSICAL_MANUFACTURING,
                description="Fused Deposition Modeling / Fused Filament Fabrication additive manufacturing.",
                gate_types=[GateType.QUALITY, GateType.SAFETY, GateType.PERFORMANCE, GateType.MONITORING],
                keywords=["fdm", "fff", "filament", "extruder", "layer adhesion", "bed leveling", "nozzle"],
                connectors=["AdditiveManufacturingRegistry"],
                compliance_standards=["ISO 17296", "ASTM F2792"],
                priority=8,
            ),
            SubjectDomain(
                domain_id="3d_printing_sla",
                name="3D Printing — SLA/DLP",
                category=DomainCategory.PHYSICAL_MANUFACTURING,
                description="Stereolithography and Digital Light Processing resin-based additive manufacturing.",
                gate_types=[GateType.QUALITY, GateType.SAFETY, GateType.COMPLIANCE, GateType.MONITORING],
                keywords=["sla", "dlp", "resin", "photopolymer", "uv curing", "supports", "build plate"],
                connectors=["AdditiveManufacturingRegistry"],
                compliance_standards=["ISO 17296", "ASTM F3122"],
                priority=8,
            ),
            SubjectDomain(
                domain_id="3d_printing_sls",
                name="3D Printing — SLS",
                category=DomainCategory.PHYSICAL_MANUFACTURING,
                description="Selective Laser Sintering powder-bed fusion for nylon and polymers.",
                gate_types=[GateType.QUALITY, GateType.SAFETY, GateType.PERFORMANCE, GateType.ENERGY],
                keywords=["sls", "laser sintering", "powder bed", "nylon", "pa12", "refresh rate"],
                connectors=["AdditiveManufacturingRegistry"],
                compliance_standards=["ISO 17296", "ASTM F3091"],
                priority=7,
            ),
            SubjectDomain(
                domain_id="3d_printing_slm_dmls",
                name="3D Printing — SLM/DMLS",
                category=DomainCategory.PHYSICAL_MANUFACTURING,
                description="Selective Laser Melting / Direct Metal Laser Sintering for metal parts.",
                gate_types=[GateType.QUALITY, GateType.SAFETY, GateType.COMPLIANCE, GateType.PERFORMANCE, GateType.ENERGY],
                keywords=["slm", "dmls", "metal powder", "titanium", "inconel", "post processing", "heat treatment"],
                connectors=["AdditiveManufacturingRegistry"],
                compliance_standards=["ISO 17296", "ASTM F3049", "AMS 7003"],
                priority=9,
            ),
            SubjectDomain(
                domain_id="3d_printing_ebm",
                name="3D Printing — EBM",
                category=DomainCategory.PHYSICAL_MANUFACTURING,
                description="Electron Beam Melting for high-temperature metals in vacuum environment.",
                gate_types=[GateType.QUALITY, GateType.SAFETY, GateType.ENERGY, GateType.COMPLIANCE],
                keywords=["ebm", "electron beam", "vacuum", "titanium", "cobalt chrome", "arcam"],
                connectors=["AdditiveManufacturingRegistry"],
                compliance_standards=["ISO 17296", "ASTM F3001"],
                priority=7,
            ),
            SubjectDomain(
                domain_id="3d_printing_polyjet",
                name="3D Printing — PolyJet/MJF",
                category=DomainCategory.PHYSICAL_MANUFACTURING,
                description="PolyJet and Multi Jet Fusion for multi-material, high-detail parts.",
                gate_types=[GateType.QUALITY, GateType.PERFORMANCE, GateType.MONITORING],
                keywords=["polyjet", "mjf", "inkjet", "voxel", "support material", "stratasys", "hp"],
                connectors=["AdditiveManufacturingRegistry"],
                compliance_standards=["ISO 17296"],
                priority=6,
            ),
            SubjectDomain(
                domain_id="3d_printing_binder",
                name="3D Printing — Binder Jetting",
                category=DomainCategory.PHYSICAL_MANUFACTURING,
                description="Binder jetting for metal, sand, and ceramic part production.",
                gate_types=[GateType.QUALITY, GateType.SAFETY, GateType.PERFORMANCE],
                keywords=["binder jetting", "infiltration", "sintering", "stainless steel", "sand casting"],
                connectors=["AdditiveManufacturingRegistry"],
                compliance_standards=["ISO 17296", "ASTM F2792"],
                priority=6,
            ),
            SubjectDomain(
                domain_id="3d_printing_ded",
                name="3D Printing — DED/WAAM",
                category=DomainCategory.PHYSICAL_MANUFACTURING,
                description="Directed Energy Deposition / Wire Arc Additive Manufacturing for large metal parts.",
                gate_types=[GateType.QUALITY, GateType.SAFETY, GateType.ENERGY, GateType.MONITORING],
                keywords=["ded", "waam", "laser cladding", "wire arc", "large format", "repair"],
                connectors=["AdditiveManufacturingRegistry"],
                compliance_standards=["ISO 17296", "AWS D1.1"],
                priority=7,
            ),
            SubjectDomain(
                domain_id="3d_printing_fiber",
                name="3D Printing — Continuous Fiber",
                category=DomainCategory.PHYSICAL_MANUFACTURING,
                description="Continuous fiber reinforcement (carbon, kevlar, fiberglass) in FFF base.",
                gate_types=[GateType.QUALITY, GateType.SAFETY, GateType.PERFORMANCE, GateType.COMPLIANCE],
                keywords=["continuous fiber", "carbon fiber", "kevlar", "markforged", "composite"],
                connectors=["AdditiveManufacturingRegistry"],
                compliance_standards=["ISO 17296", "ASTM D3039"],
                priority=7,
            ),

            # ── CAD / DESIGN ─────────────────────────────────────────────
            SubjectDomain(
                domain_id="cad_design",
                name="CAD / Design Engineering",
                category=DomainCategory.PHYSICAL_MANUFACTURING,
                description="Computer-Aided Design across platforms: AutoCAD, SolidWorks, Fusion360, Blender, OpenSCAD.",
                gate_types=[GateType.QUALITY, GateType.COMPLIANCE, GateType.PERFORMANCE],
                keywords=["cad", "solidworks", "autocad", "fusion360", "blender", "openscad", "parametric",
                          "assembly", "drawing", "bom", "tolerances", "gdt"],
                connectors=[],
                compliance_standards=["ISO 2768", "ASME Y14.5"],
                priority=7,
            ),

            # ── OTHER MANUFACTURING ───────────────────────────────────────
            SubjectDomain(
                domain_id="cnc_machining",
                name="CNC Machining",
                category=DomainCategory.PHYSICAL_MANUFACTURING,
                description="Subtractive manufacturing via CNC milling, turning, and EDM.",
                gate_types=[GateType.QUALITY, GateType.SAFETY, GateType.PERFORMANCE, GateType.MONITORING],
                keywords=["cnc", "milling", "turning", "g-code", "toolpath", "fixturing", "tolerance", "edm"],
                connectors=[],
                compliance_standards=["ISO 9001", "AS9100"],
                priority=8,
            ),
            SubjectDomain(
                domain_id="injection_molding",
                name="Injection Molding",
                category=DomainCategory.PHYSICAL_MANUFACTURING,
                description="Thermoplastic and thermoset injection molding for high-volume parts.",
                gate_types=[GateType.QUALITY, GateType.SAFETY, GateType.PERFORMANCE, GateType.ENERGY],
                keywords=["injection molding", "mold", "cavity", "cycle time", "shrinkage", "gate", "runner"],
                connectors=[],
                compliance_standards=["ISO 9001", "IATF 16949"],
                priority=7,
            ),
            SubjectDomain(
                domain_id="welding_fabrication",
                name="Welding & Metal Fabrication",
                category=DomainCategory.PHYSICAL_MANUFACTURING,
                description="MIG, TIG, stick and robotic welding plus sheet metal fabrication.",
                gate_types=[GateType.QUALITY, GateType.SAFETY, GateType.COMPLIANCE, GateType.MONITORING],
                keywords=["welding", "mig", "tig", "robotic welding", "sheet metal", "bending", "cutting"],
                connectors=[],
                compliance_standards=["AWS D1.1", "ISO 3834", "ASME IX"],
                priority=7,
            ),
            SubjectDomain(
                domain_id="electronics_manufacturing",
                name="Electronics Manufacturing",
                category=DomainCategory.PHYSICAL_MANUFACTURING,
                description="PCB assembly, SMT, through-hole, and electronics testing.",
                gate_types=[GateType.QUALITY, GateType.COMPLIANCE, GateType.SAFETY, GateType.MONITORING],
                keywords=["pcb", "smt", "reflow", "wave soldering", "ict", "aoi", "bom", "gerber"],
                connectors=[],
                compliance_standards=["IPC-A-610", "IEC 61340", "RoHS", "UL"],
                priority=7,
            ),

            # ── BUILDING SYSTEMS ──────────────────────────────────────────
            SubjectDomain(
                domain_id="hvac_bas",
                name="HVAC / Building Automation (BAS)",
                category=DomainCategory.BUILDING_SYSTEMS,
                description=(
                    "Building automation for 16 system types: AHU, FCU, chiller, boiler, cooling tower, "
                    "VAV, exhaust fan, heat pump, VRF, radiant, DOAS, ERV, MAU, UH, IT cooling, data center."
                ),
                gate_types=[
                    GateType.SAFETY, GateType.ENERGY, GateType.COMFORT,
                    GateType.COMPLIANCE, GateType.MONITORING, GateType.PERFORMANCE,
                ],
                keywords=[
                    "hvac", "ahu", "fcu", "chiller", "boiler", "cooling tower", "vav", "bas",
                    "bms", "ddc", "bacnet", "modbus", "ecobee", "nest", "setpoint", "pid",
                    "vrf", "radiant", "doas", "erv", "mau", "unit heater", "data center cooling",
                ],
                connectors=["BuildingAutomationRegistry"],
                compliance_standards=["ASHRAE 90.1", "ASHRAE 62.1", "IECC", "ISO 50001"],
                priority=9,
            ),
            SubjectDomain(
                domain_id="plumbing",
                name="Plumbing Systems",
                category=DomainCategory.BUILDING_SYSTEMS,
                description="Domestic water, sanitary, storm, and fire suppression plumbing systems.",
                gate_types=[GateType.SAFETY, GateType.COMPLIANCE, GateType.MONITORING, GateType.QUALITY],
                keywords=["plumbing", "domestic water", "sanitary", "storm", "fire suppression", "backflow", "booster pump"],
                connectors=["BuildingAutomationRegistry"],
                compliance_standards=["IPC", "UPC", "NFPA 13", "ASHRAE 188"],
                priority=7,
            ),
            SubjectDomain(
                domain_id="electrical_systems",
                name="Electrical Systems",
                category=DomainCategory.BUILDING_SYSTEMS,
                description="Low and medium voltage electrical distribution, lighting, and power systems.",
                gate_types=[GateType.SAFETY, GateType.COMPLIANCE, GateType.ENERGY, GateType.MONITORING],
                keywords=["electrical", "switchgear", "panel", "transformer", "lighting", "generator", "ups", "nec"],
                connectors=["BuildingAutomationRegistry"],
                compliance_standards=["NEC", "NFPA 70", "IEEE 1584", "IEC 60364"],
                priority=8,
            ),
            SubjectDomain(
                domain_id="elevators",
                name="Elevator & Vertical Transport",
                category=DomainCategory.BUILDING_SYSTEMS,
                description="Traction, hydraulic, and machine-room-less elevator systems.",
                gate_types=[GateType.SAFETY, GateType.COMPLIANCE, GateType.MONITORING, GateType.PERFORMANCE],
                keywords=["elevator", "lift", "escalator", "traction", "hydraulic", "mrl", "asme a17.1"],
                connectors=["BuildingAutomationRegistry"],
                compliance_standards=["ASME A17.1", "EN 81-20", "IBC"],
                priority=7,
            ),

            # ── PROFESSIONAL SERVICES ─────────────────────────────────────
            SubjectDomain(
                domain_id="architecture_engineering",
                name="Architecture & Engineering",
                category=DomainCategory.PROFESSIONAL_SERVICES,
                description="Architectural design, structural, MEP, and civil engineering services.",
                gate_types=[GateType.QUALITY, GateType.COMPLIANCE, GateType.SAFETY, GateType.PERFORMANCE],
                keywords=["architecture", "structural", "mep", "civil", "bim", "revit", "autocad", "specifications"],
                connectors=[],
                compliance_standards=["IBC", "ADA", "ISO 19650", "NFPA"],
                priority=7,
            ),
            SubjectDomain(
                domain_id="construction_management",
                name="Construction Management",
                category=DomainCategory.PROFESSIONAL_SERVICES,
                description="General contracting, project management, and construction oversight.",
                gate_types=[GateType.SAFETY, GateType.QUALITY, GateType.COMPLIANCE, GateType.BUSINESS],
                keywords=["construction", "general contractor", "subcontractor", "schedule", "rfi", "submittal", "punch list"],
                connectors=[],
                compliance_standards=["OSHA 1926", "AIA contracts", "ISO 45001"],
                priority=7,
            ),
            SubjectDomain(
                domain_id="legal",
                name="Legal Services",
                category=DomainCategory.PROFESSIONAL_SERVICES,
                description="Corporate, litigation, IP, real estate, and regulatory legal practice.",
                gate_types=[GateType.COMPLIANCE, GateType.SECURITY, GateType.QUALITY, GateType.BUSINESS],
                keywords=["legal", "contract", "litigation", "ip", "intellectual property", "discovery", "billing"],
                connectors=["EnterpriseIntegrationRegistry"],
                compliance_standards=["ABA Model Rules", "GDPR", "HIPAA"],
                priority=8,
            ),
            SubjectDomain(
                domain_id="accounting",
                name="Accounting & Audit",
                category=DomainCategory.PROFESSIONAL_SERVICES,
                description="Financial accounting, tax, audit, and management accounting.",
                gate_types=[GateType.COMPLIANCE, GateType.QUALITY, GateType.SECURITY, GateType.BUSINESS],
                keywords=["accounting", "audit", "tax", "gaap", "ifrs", "financial statements", "reconciliation"],
                connectors=["EnterpriseIntegrationRegistry"],
                compliance_standards=["GAAP", "IFRS", "SOX", "ISA"],
                priority=8,
            ),
            SubjectDomain(
                domain_id="consulting",
                name="Management Consulting",
                category=DomainCategory.PROFESSIONAL_SERVICES,
                description="Strategy, operations, technology, and change management consulting.",
                gate_types=[GateType.QUALITY, GateType.BUSINESS, GateType.PERFORMANCE, GateType.COMPLIANCE],
                keywords=["consulting", "strategy", "change management", "process improvement", "kpi", "deliverables"],
                connectors=["EnterpriseIntegrationRegistry"],
                compliance_standards=["ISO 20700"],
                priority=6,
            ),

            # ── HEALTHCARE ────────────────────────────────────────────────
            SubjectDomain(
                domain_id="clinical_operations",
                name="Clinical Operations",
                category=DomainCategory.HEALTHCARE,
                description="Hospital and clinic operations including scheduling, patient flow, and care coordination.",
                gate_types=[GateType.SAFETY, GateType.COMPLIANCE, GateType.QUALITY, GateType.MONITORING],
                keywords=["clinical", "ehr", "emr", "hl7", "fhir", "patient", "scheduling", "care coordination"],
                connectors=["EnterpriseIntegrationRegistry"],
                compliance_standards=["HIPAA", "HITECH", "Joint Commission", "HL7 FHIR"],
                priority=10,
            ),
            SubjectDomain(
                domain_id="medical_devices",
                name="Medical Devices",
                category=DomainCategory.HEALTHCARE,
                description="Design, manufacturing, and lifecycle management of medical devices.",
                gate_types=[GateType.SAFETY, GateType.COMPLIANCE, GateType.QUALITY, GateType.MONITORING],
                keywords=["medical device", "fda", "510k", "pma", "qsr", "design controls", "post market"],
                connectors=[],
                compliance_standards=["FDA 21 CFR 820", "ISO 13485", "IEC 62304", "MDR"],
                priority=10,
            ),
            SubjectDomain(
                domain_id="pharmaceutical",
                name="Pharmaceutical Manufacturing",
                category=DomainCategory.HEALTHCARE,
                description="Drug manufacturing, validation, and quality systems.",
                gate_types=[GateType.SAFETY, GateType.COMPLIANCE, GateType.QUALITY, GateType.MONITORING],
                keywords=["pharma", "gmp", "validation", "batch record", "deviation", "capa", "sterile"],
                connectors=[],
                compliance_standards=["FDA 21 CFR 211", "EU GMP", "ICH Q10", "USP"],
                priority=10,
            ),
            SubjectDomain(
                domain_id="laboratory",
                name="Laboratory Operations",
                category=DomainCategory.HEALTHCARE,
                description="Clinical, research, and analytical laboratory management.",
                gate_types=[GateType.QUALITY, GateType.SAFETY, GateType.COMPLIANCE, GateType.MONITORING],
                keywords=["laboratory", "lims", "sample", "reagent", "calibration", "accreditation", "qc"],
                connectors=[],
                compliance_standards=["ISO 15189", "ISO 17025", "CAP", "CLIA"],
                priority=8,
            ),

            # ── ENERGY & UTILITIES ────────────────────────────────────────
            SubjectDomain(
                domain_id="power_generation",
                name="Power Generation",
                category=DomainCategory.ENERGY_UTILITIES,
                description="Conventional and renewable power generation including solar, wind, gas turbine, and hydro.",
                gate_types=[GateType.SAFETY, GateType.PERFORMANCE, GateType.COMPLIANCE, GateType.ENERGY, GateType.MONITORING],
                keywords=["power generation", "solar", "wind", "gas turbine", "hydro", "scada", "grid", "dispatch"],
                connectors=[],
                compliance_standards=["NERC CIP", "IEEE 1547", "IEC 61850", "FERC"],
                priority=9,
            ),
            SubjectDomain(
                domain_id="oil_gas",
                name="Oil & Gas",
                category=DomainCategory.ENERGY_UTILITIES,
                description="Upstream, midstream, and downstream oil and gas operations.",
                gate_types=[GateType.SAFETY, GateType.COMPLIANCE, GateType.MONITORING, GateType.PERFORMANCE, GateType.ENERGY],
                keywords=["oil", "gas", "upstream", "downstream", "pipeline", "refinery", "api", "scada"],
                connectors=[],
                compliance_standards=["API RP 580", "API 1160", "PHMSA", "ISO 55000"],
                priority=9,
            ),
            SubjectDomain(
                domain_id="water_treatment",
                name="Water & Wastewater Treatment",
                category=DomainCategory.ENERGY_UTILITIES,
                description="Municipal water treatment, distribution, and wastewater management.",
                gate_types=[GateType.SAFETY, GateType.COMPLIANCE, GateType.QUALITY, GateType.MONITORING, GateType.ENERGY],
                keywords=["water treatment", "wastewater", "scada", "disinfection", "filtration", "nutrient removal"],
                connectors=[],
                compliance_standards=["EPA NPDES", "AWWA", "NSF/ANSI 61", "10 States Standards"],
                priority=8,
            ),
            SubjectDomain(
                domain_id="agriculture",
                name="Agriculture & AgriTech",
                category=DomainCategory.ENERGY_UTILITIES,
                description="Precision agriculture, irrigation, soil monitoring, and crop management.",
                gate_types=[GateType.QUALITY, GateType.PERFORMANCE, GateType.MONITORING, GateType.ENERGY],
                keywords=["agriculture", "irrigation", "soil sensor", "precision ag", "crop", "yield", "drone"],
                connectors=[],
                compliance_standards=["USDA NOP", "GlobalGAP", "ISO 11783"],
                priority=6,
            ),

            # ── RETAIL & COMMERCE ─────────────────────────────────────────
            SubjectDomain(
                domain_id="ecommerce",
                name="E-Commerce",
                category=DomainCategory.RETAIL_COMMERCE,
                description="Online retail, marketplaces, and digital storefronts.",
                gate_types=[GateType.SECURITY, GateType.PERFORMANCE, GateType.COMPLIANCE, GateType.BUSINESS, GateType.QUALITY],
                keywords=["ecommerce", "shopify", "magento", "woocommerce", "cart", "checkout", "pci", "fraud"],
                connectors=["EnterpriseIntegrationRegistry"],
                compliance_standards=["PCI DSS", "GDPR", "CCPA"],
                priority=8,
            ),
            SubjectDomain(
                domain_id="retail",
                name="Retail Operations",
                category=DomainCategory.RETAIL_COMMERCE,
                description="Physical and omnichannel retail store operations and management.",
                gate_types=[GateType.BUSINESS, GateType.COMPLIANCE, GateType.SECURITY, GateType.PERFORMANCE],
                keywords=["retail", "pos", "inventory", "planogram", "shrink", "omnichannel", "loyalty"],
                connectors=["EnterpriseIntegrationRegistry"],
                compliance_standards=["PCI DSS", "ADA", "FTC"],
                priority=7,
            ),
            SubjectDomain(
                domain_id="supply_chain",
                name="Supply Chain Management",
                category=DomainCategory.RETAIL_COMMERCE,
                description="End-to-end supply chain planning, procurement, and inventory management.",
                gate_types=[GateType.PERFORMANCE, GateType.COMPLIANCE, GateType.QUALITY, GateType.BUSINESS, GateType.MONITORING],
                keywords=["supply chain", "procurement", "vendor", "erp", "demand planning", "inventory", "rfq"],
                connectors=["EnterpriseIntegrationRegistry"],
                compliance_standards=["ISO 28000", "C-TPAT", "CTPAT"],
                priority=8,
            ),

            # ── FINANCIAL SERVICES ────────────────────────────────────────
            SubjectDomain(
                domain_id="trading",
                name="Trading & Capital Markets",
                category=DomainCategory.FINANCIAL_SERVICES,
                description="Equities, fixed income, derivatives, and algorithmic trading.",
                gate_types=[GateType.COMPLIANCE, GateType.SECURITY, GateType.PERFORMANCE, GateType.MONITORING, GateType.BUSINESS],
                keywords=["trading", "equities", "derivatives", "algo", "order management", "risk", "sec", "finra"],
                connectors=["EnterpriseIntegrationRegistry"],
                compliance_standards=["SEC Rule 15c3-5", "FINRA", "MiFID II", "Dodd-Frank"],
                priority=10,
            ),
            SubjectDomain(
                domain_id="insurance",
                name="Insurance",
                category=DomainCategory.FINANCIAL_SERVICES,
                description="Property, casualty, life, and health insurance underwriting and claims.",
                gate_types=[GateType.COMPLIANCE, GateType.QUALITY, GateType.BUSINESS, GateType.SECURITY],
                keywords=["insurance", "underwriting", "claims", "actuarial", "policy", "reinsurance"],
                connectors=["EnterpriseIntegrationRegistry"],
                compliance_standards=["NAIC", "Solvency II", "SOX"],
                priority=8,
            ),
            SubjectDomain(
                domain_id="banking",
                name="Banking & Lending",
                category=DomainCategory.FINANCIAL_SERVICES,
                description="Retail banking, commercial lending, mortgage, and payment processing.",
                gate_types=[GateType.COMPLIANCE, GateType.SECURITY, GateType.QUALITY, GateType.BUSINESS, GateType.MONITORING],
                keywords=["banking", "loan", "mortgage", "payment", "kyc", "aml", "fraud", "core banking"],
                connectors=["EnterpriseIntegrationRegistry"],
                compliance_standards=["BSA/AML", "CRA", "FDICIA", "PCI DSS", "Basel III"],
                priority=10,
            ),

            # ── MEDIA & COMMUNICATIONS ────────────────────────────────────
            SubjectDomain(
                domain_id="content_creation",
                name="Content Creation & Media Production",
                category=DomainCategory.MEDIA_COMMUNICATIONS,
                description="Video production, photography, audio recording, and live streaming.",
                gate_types=[GateType.QUALITY, GateType.BUSINESS, GateType.COMPLIANCE],
                keywords=["video", "audio", "production", "streaming", "editing", "broadcast", "content"],
                connectors=[],
                compliance_standards=["FCC", "DMCA", "GDPR"],
                priority=5,
            ),
            SubjectDomain(
                domain_id="publishing",
                name="Publishing & Digital Media",
                category=DomainCategory.MEDIA_COMMUNICATIONS,
                description="Print and digital publishing, journalism, and content distribution.",
                gate_types=[GateType.QUALITY, GateType.COMPLIANCE, GateType.BUSINESS, GateType.SECURITY],
                keywords=["publishing", "editorial", "cms", "seo", "newsletter", "paywall", "copyright"],
                connectors=[],
                compliance_standards=["GDPR", "DMCA", "WCAG"],
                priority=5,
            ),
            SubjectDomain(
                domain_id="telecommunications",
                name="Telecommunications",
                category=DomainCategory.MEDIA_COMMUNICATIONS,
                description="Voice, data, and wireless telecommunications network operations.",
                gate_types=[GateType.PERFORMANCE, GateType.COMPLIANCE, GateType.SECURITY, GateType.MONITORING],
                keywords=["telecom", "voip", "5g", "fiber", "noc", "sla", "qos", "oss", "bss"],
                connectors=[],
                compliance_standards=["FCC", "CALEA", "CPNI", "NEBS"],
                priority=8,
            ),

            # ── EDUCATION & NONPROFIT ─────────────────────────────────────
            SubjectDomain(
                domain_id="education",
                name="Education",
                category=DomainCategory.EDUCATION_NONPROFIT,
                description="K-12, higher education, and e-learning platform operations.",
                gate_types=[GateType.COMPLIANCE, GateType.QUALITY, GateType.SECURITY, GateType.PERFORMANCE],
                keywords=["education", "lms", "student", "curriculum", "assessment", "ferpa", "ada"],
                connectors=["EnterpriseIntegrationRegistry"],
                compliance_standards=["FERPA", "COPPA", "ADA", "WCAG"],
                priority=6,
            ),
            SubjectDomain(
                domain_id="nonprofit",
                name="Nonprofit & NGO",
                category=DomainCategory.EDUCATION_NONPROFIT,
                description="Nonprofit organization management including fundraising, grants, and programs.",
                gate_types=[GateType.COMPLIANCE, GateType.BUSINESS, GateType.QUALITY],
                keywords=["nonprofit", "501c3", "donor", "grant", "fundraising", "volunteer", "impact"],
                connectors=["EnterpriseIntegrationRegistry"],
                compliance_standards=["IRS Form 990", "FASB ASC 958", "GDPR"],
                priority=5,
            ),

            # ── TRANSPORTATION & LOGISTICS ────────────────────────────────
            SubjectDomain(
                domain_id="fleet_management",
                name="Fleet Management",
                category=DomainCategory.TRANSPORTATION_LOGISTICS,
                description="Commercial vehicle fleet tracking, maintenance, and driver management.",
                gate_types=[GateType.SAFETY, GateType.COMPLIANCE, GateType.PERFORMANCE, GateType.MONITORING],
                keywords=["fleet", "telematics", "gps", "dot", "hours of service", "maintenance", "driver scorecard"],
                connectors=[],
                compliance_standards=["FMCSA", "DOT", "ELD mandate", "ISO 39001"],
                priority=7,
            ),
            SubjectDomain(
                domain_id="warehousing",
                name="Warehousing & Distribution",
                category=DomainCategory.TRANSPORTATION_LOGISTICS,
                description="Warehouse operations, WMS, picking, packing, and distribution center management.",
                gate_types=[GateType.PERFORMANCE, GateType.SAFETY, GateType.QUALITY, GateType.MONITORING, GateType.BUSINESS],
                keywords=["warehouse", "wms", "picking", "packing", "receiving", "put-away", "slotting", "fulfillment"],
                connectors=["EnterpriseIntegrationRegistry"],
                compliance_standards=["OSHA", "ISO 9001", "CTPAT"],
                priority=7,
            ),
            SubjectDomain(
                domain_id="last_mile",
                name="Last-Mile Delivery",
                category=DomainCategory.TRANSPORTATION_LOGISTICS,
                description="Last-mile delivery routing, carrier management, and customer experience.",
                gate_types=[GateType.PERFORMANCE, GateType.COMPLIANCE, GateType.QUALITY, GateType.MONITORING],
                keywords=["last mile", "delivery", "routing", "carrier", "tracking", "pod", "returns", "dsp"],
                connectors=["EnterpriseIntegrationRegistry"],
                compliance_standards=["DOT", "FMCSA", "GDPR"],
                priority=7,
            ),

            # ── ADDITIONAL SUPPLEMENTARY DOMAINS ─────────────────────────
            SubjectDomain(
                domain_id="cybersecurity",
                name="Cybersecurity",
                category=DomainCategory.PROFESSIONAL_SERVICES,
                description="Information security, threat intelligence, SOC operations, and compliance.",
                gate_types=[GateType.SECURITY, GateType.COMPLIANCE, GateType.MONITORING, GateType.PERFORMANCE],
                keywords=["security", "soc", "siem", "vulnerability", "pentest", "incident response", "zero trust"],
                connectors=["EnterpriseIntegrationRegistry"],
                compliance_standards=["NIST CSF", "ISO 27001", "SOC 2", "CMMC"],
                priority=10,
            ),
            SubjectDomain(
                domain_id="data_center",
                name="Data Center Operations",
                category=DomainCategory.BUILDING_SYSTEMS,
                description="Colocation and enterprise data center infrastructure management (DCIM).",
                gate_types=[GateType.PERFORMANCE, GateType.ENERGY, GateType.SAFETY, GateType.MONITORING, GateType.COMPLIANCE],
                keywords=["data center", "dcim", "pue", "cooling", "ups", "generator", "cabling", "rack"],
                connectors=["BuildingAutomationRegistry"],
                compliance_standards=["TIA-942", "Uptime Institute Tiers", "ISO 50001", "SOC 2"],
                priority=9,
            ),
            SubjectDomain(
                domain_id="real_estate",
                name="Real Estate & Property Management",
                category=DomainCategory.PROFESSIONAL_SERVICES,
                description="Commercial and residential real estate transactions and property management.",
                gate_types=[GateType.COMPLIANCE, GateType.BUSINESS, GateType.SECURITY, GateType.QUALITY],
                keywords=["real estate", "lease", "property management", "cam", "tenant", "cap rate", "noi"],
                connectors=["EnterpriseIntegrationRegistry"],
                compliance_standards=["Fair Housing Act", "ADA", "RESPA", "Dodd-Frank"],
                priority=6,
            ),
            SubjectDomain(
                domain_id="hr_workforce",
                name="Human Resources & Workforce Management",
                category=DomainCategory.PROFESSIONAL_SERVICES,
                description="Talent acquisition, HR operations, payroll, and workforce planning.",
                gate_types=[GateType.COMPLIANCE, GateType.SECURITY, GateType.QUALITY, GateType.BUSINESS],
                keywords=["hr", "payroll", "talent", "onboarding", "performance", "benefits", "hris"],
                connectors=["EnterpriseIntegrationRegistry"],
                compliance_standards=["FLSA", "ADA", "EEO", "FMLA", "GDPR"],
                priority=7,
            ),
            SubjectDomain(
                domain_id="environmental_sustainability",
                name="Environmental & Sustainability",
                category=DomainCategory.ENERGY_UTILITIES,
                description="Environmental compliance, ESG reporting, and sustainability program management.",
                gate_types=[GateType.COMPLIANCE, GateType.MONITORING, GateType.ENERGY, GateType.QUALITY],
                keywords=["esg", "carbon", "sustainability", "emissions", "iso 14001", "leed", "scope 3"],
                connectors=[],
                compliance_standards=["ISO 14001", "GHG Protocol", "GRI", "TCFD"],
                priority=7,
            ),
            SubjectDomain(
                domain_id="food_beverage",
                name="Food & Beverage Manufacturing",
                category=DomainCategory.PHYSICAL_MANUFACTURING,
                description="Food processing, beverage production, and food safety management.",
                gate_types=[GateType.SAFETY, GateType.QUALITY, GateType.COMPLIANCE, GateType.MONITORING],
                keywords=["food", "beverage", "fsma", "haccp", "food safety", "sanitation", "traceability"],
                connectors=[],
                compliance_standards=["FSMA", "HACCP", "SQF", "BRC", "ISO 22000"],
                priority=8,
            ),
            SubjectDomain(
                domain_id="aerospace_defense",
                name="Aerospace & Defense",
                category=DomainCategory.PHYSICAL_MANUFACTURING,
                description="Aircraft, spacecraft, and defense system design and manufacturing.",
                gate_types=[GateType.SAFETY, GateType.QUALITY, GateType.COMPLIANCE, GateType.PERFORMANCE, GateType.SECURITY],
                keywords=["aerospace", "defense", "fas", "as9100", "do-178c", "mil-spec", "airworthiness"],
                connectors=[],
                compliance_standards=["AS9100", "DO-178C", "MIL-SPEC", "FAA AC", "ITAR"],
                priority=10,
            ),
            SubjectDomain(
                domain_id="automotive",
                name="Automotive Manufacturing",
                category=DomainCategory.PHYSICAL_MANUFACTURING,
                description="Automotive OEM and tier supplier manufacturing and quality systems.",
                gate_types=[GateType.QUALITY, GateType.SAFETY, GateType.COMPLIANCE, GateType.PERFORMANCE, GateType.MONITORING],
                keywords=["automotive", "iatf", "apqp", "ppap", "fmea", "control plan", "obd", "ev"],
                connectors=[],
                compliance_standards=["IATF 16949", "APQP", "VDA 6.3", "FMVSS"],
                priority=9,
            ),
            SubjectDomain(
                domain_id="smart_building",
                name="Smart Building & IoT",
                category=DomainCategory.BUILDING_SYSTEMS,
                description="IoT-enabled smart building systems, sensors, and edge computing.",
                gate_types=[GateType.SECURITY, GateType.PERFORMANCE, GateType.ENERGY, GateType.MONITORING, GateType.COMPLIANCE],
                keywords=["iot", "smart building", "edge", "sensor", "mqtt", "opcua", "digital twin"],
                connectors=["BuildingAutomationRegistry"],
                compliance_standards=["ISO 27001", "IEC 62443", "NIST 800-82"],
                priority=8,
            ),
            SubjectDomain(
                domain_id="hospitality",
                name="Hospitality & Hotels",
                category=DomainCategory.RETAIL_COMMERCE,
                description="Hotel operations, property management, reservations, and guest services.",
                gate_types=[GateType.QUALITY, GateType.COMPLIANCE, GateType.BUSINESS, GateType.SAFETY, GateType.MONITORING],
                keywords=["hotel", "pms", "reservation", "housekeeping", "concierge", "revenue management"],
                connectors=["EnterpriseIntegrationRegistry"],
                compliance_standards=["PCI DSS", "ADA", "OSHA"],
                priority=6,
            ),
            SubjectDomain(
                domain_id="mining",
                name="Mining & Extraction",
                category=DomainCategory.ENERGY_UTILITIES,
                description="Surface and underground mining operations, ore processing, and safety management.",
                gate_types=[GateType.SAFETY, GateType.COMPLIANCE, GateType.MONITORING, GateType.PERFORMANCE, GateType.ENERGY],
                keywords=["mining", "extraction", "ore", "haul truck", "blast", "ventilation", "msha"],
                connectors=[],
                compliance_standards=["MSHA", "ISO 45001", "ISO 14001"],
                priority=8,
            ),
            SubjectDomain(
                domain_id="government_public",
                name="Government & Public Sector",
                category=DomainCategory.PROFESSIONAL_SERVICES,
                description="Federal, state, and local government agency operations and service delivery.",
                gate_types=[GateType.COMPLIANCE, GateType.SECURITY, GateType.QUALITY, GateType.MONITORING],
                keywords=["government", "federal", "state", "municipal", "procurement", "grant", "fisma"],
                connectors=["EnterpriseIntegrationRegistry"],
                compliance_standards=["FISMA", "FedRAMP", "NIST 800-53", "FAR"],
                priority=8,
            ),
            SubjectDomain(
                domain_id="shipping_maritime",
                name="Shipping & Maritime",
                category=DomainCategory.TRANSPORTATION_LOGISTICS,
                description="Ocean freight, port operations, and maritime logistics.",
                gate_types=[GateType.SAFETY, GateType.COMPLIANCE, GateType.PERFORMANCE, GateType.MONITORING],
                keywords=["shipping", "maritime", "port", "container", "imo", "imdg", "customs", "bol"],
                connectors=[],
                compliance_standards=["IMO SOLAS", "ISPS Code", "US CBP", "IMDG Code"],
                priority=7,
            ),
            SubjectDomain(
                domain_id="rail_transit",
                name="Rail & Transit",
                category=DomainCategory.TRANSPORTATION_LOGISTICS,
                description="Freight rail, passenger rail, and urban transit system operations.",
                gate_types=[GateType.SAFETY, GateType.COMPLIANCE, GateType.PERFORMANCE, GateType.MONITORING],
                keywords=["rail", "transit", "locomotive", "signaling", "positive train control", "ptc", "fra"],
                connectors=[],
                compliance_standards=["FRA", "APTA", "AREMA", "NORAC"],
                priority=8,
            ),
        ]

        for domain in domains:
            self._domains[domain.domain_id] = domain
