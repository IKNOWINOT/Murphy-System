"""
Market Positioning Engine — Murphy Knows Its Market

Design Label: MPE-001 — Market Positioning Engine
Owner: VP Strategy (Shadow Agent) / Founder HITL
Dependencies: (none — stdlib only, leaf module)

Purpose:
  Encodes Murphy System's market positioning so that every autonomous
  marketing action — content generation, B2B outreach, partnership pitches —
  is grounded in the system's actual capabilities and the specific pains of
  each industry vertical it serves.

  This is the authoritative source for:
    - What Murphy can do  (MURPHY_CAPABILITIES registry)
    - Who Murphy serves   (INDUSTRY_VERTICALS registry)
    - Why Murphy wins     (MarketPosition differentiation pillars)
    - How Murphy pitches  (industry-aware value propositions + content topics)

  Capabilities are drawn from the live CAPABILITY_SCORECARD.md (97.1%
  readiness, 12/17 at 10/10) and from EU_AI_ACT_POSITIONING.md.
  Industry verticals are sourced from BUSINESS_MODEL.md and the three
  passing vertical demos (healthcare, financial services, manufacturing).

Public API:
  engine = MarketPositioningEngine()
  engine.get_market_position()                           → MarketPosition
  engine.list_capabilities()                             → List[MurphyCapability]
  engine.get_capability("nlp_workflow_automation")       → MurphyCapability
  engine.list_verticals()                                → List[IndustryVertical]
  engine.get_vertical("healthcare")                      → IndustryVertical
  engine.get_capability_matrix()                         → Dict[capability_id → [vertical_id]]
  engine.get_ideal_customer_profile("financial_services")→ Dict
  engine.get_content_topics_for_vertical("manufacturing")→ List[str]
  engine.get_industry_pitch_angle("healthcare", ["case_study"]) → str
  engine.score_partner_fit("HubSpot", ["case_study", "featuring"]) → float
  engine.get_positioning_for_offering_types(["case_study"]) → Dict

Safety invariants:
  - All public method parameters validated against closed allowlists (CWE-20)
  - No external I/O, no network calls — pure in-memory computation
  - Immutable registries (tuples / frozensets) — cannot be mutated at runtime
  - ValueError raised on unknown ids so callers fail loudly
  - All string outputs bounded (no unbounded concatenation)

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hardening constants (CWE-20)
# ---------------------------------------------------------------------------

# Closed allowsets — validated in every public method that accepts an ID.
_VALID_CAPABILITY_IDS: FrozenSet[str] = frozenset({
    "nlp_workflow_automation",
    "confidence_gated_execution",
    "hitl_governance",
    "safety_gates",
    "multi_agent_orchestration",
    "llm_multi_provider_routing",
    "business_process_automation",
    "app_connector_ecosystem",
    "no_code_low_code_ux",
    "iot_sensor_actuator_control",
    "self_improving_learning",
    "ml_builtin",
    "autonomous_business_ops",
    "cryptographic_audit_trail",
    "eu_ai_act_compliance",
    "community_ecosystem",
    "production_deployment_readiness",
})

_VALID_VERTICAL_IDS: FrozenSet[str] = frozenset({
    "healthcare",
    "financial_services",
    "manufacturing",
    "technology",
    "professional_services",
    "government",
    "iot_building_automation",
    "energy_management",
    "additive_manufacturing",
    "factory_automation",
})

_VALID_OFFERING_TYPES: FrozenSet[str] = frozenset({
    "case_study",
    "featuring",
    "co_marketing",
    "integration_featuring",
    "press_mention",
    "podcast_guest",
})

_MAX_INPUT_LEN = 200   # max chars for any string parameter (CWE-400)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MurphyCapability:
    """A discrete capability that Murphy System provides to customers.

    Attributes
    ----------
    capability_id : str
        Unique slug identifier (validated against _VALID_CAPABILITY_IDS).
    name : str
        Short human-readable name.
    description : str
        One-to-two sentence description for marketing copy.
    maturity_score : int
        Score out of 10 reflecting current implementation maturity
        (sourced from CAPABILITY_SCORECARD.md).
    relevant_vertical_ids : tuple[str, ...]
        Which industry verticals this capability is most valuable for.
    differentiators : tuple[str, ...]
        One-line competitive differentiators for use in pitches.
    """

    capability_id: str
    name: str
    description: str
    maturity_score: int
    relevant_vertical_ids: tuple
    differentiators: tuple


@dataclass(frozen=True)
class IndustryVertical:
    """An industry segment that Murphy System targets.

    Attributes
    ----------
    vertical_id : str
        Unique slug identifier (validated against _VALID_VERTICAL_IDS).
    name : str
        Full industry name.
    icp : str
        Ideal Customer Profile — one paragraph describing the target buyer.
    pain_points : tuple[str, ...]
        Top 3–5 pains that Murphy directly addresses in this vertical.
    regulatory_context : str
        Key regulations / frameworks this vertical must comply with.
    murphy_value_props : tuple[str, ...]
        Murphy-specific value propositions for this vertical (used in pitches).
    relevant_capability_ids : tuple[str, ...]
        Which Murphy capabilities are most relevant to this vertical.
    content_topics : tuple[str, ...]
        Blog/case-study topics that resonate with this vertical's buyers.
    b2b_pitch_hook : str
        Opening hook sentence for B2B partnership pitches targeting this vertical.
    """

    vertical_id: str
    name: str
    icp: str
    pain_points: tuple
    regulatory_context: str
    murphy_value_props: tuple
    relevant_capability_ids: tuple
    content_topics: tuple
    b2b_pitch_hook: str


@dataclass(frozen=True)
class MarketPosition:
    """Murphy System's overarching market positioning.

    Attributes
    ----------
    positioning_statement : str
        The single-sentence market positioning statement.
    differentiation_pillars : tuple[str, ...]
        The 4–5 core things that make Murphy unique vs. competitors.
    target_segments : tuple[str, ...]
        Ordered list of priority target segments.
    competitive_moats : tuple[str, ...]
        Defensible technical / structural moats.
    tagline : str
        Short tagline for social/press use.
    """

    positioning_statement: str
    differentiation_pillars: tuple
    target_segments: tuple
    competitive_moats: tuple
    tagline: str


# ---------------------------------------------------------------------------
# Capability registry (sourced from CAPABILITY_SCORECARD.md + EU_AI_ACT)
# ---------------------------------------------------------------------------

MURPHY_CAPABILITIES: Dict[str, MurphyCapability] = {
    "nlp_workflow_automation": MurphyCapability(
        capability_id="nlp_workflow_automation",
        name="Natural-Language Workflow Automation",
        description=(
            "Teams describe any workflow in plain English and Murphy executes it — "
            "no drag-and-drop, no scripting required."
        ),
        maturity_score=10,
        relevant_vertical_ids=(
            "technology", "professional_services", "financial_services",
            "healthcare", "manufacturing", "government",
        ),
        differentiators=(
            "Describe-to-Execute paradigm — superior to visual no-code builders",
            "Zero external dependencies — runs air-gapped",
            "Handles multi-step, multi-system workflows from a single sentence",
        ),
    ),
    "confidence_gated_execution": MurphyCapability(
        capability_id="confidence_gated_execution",
        name="Confidence-Gated Execution (MFGC)",
        description=(
            "Every action is scored by the Multi-Factor Generative-Deterministic "
            "confidence formula before execution — the system refuses to act when "
            "confidence is below the threshold."
        ),
        maturity_score=10,
        relevant_vertical_ids=(
            "healthcare", "financial_services", "manufacturing",
            "government", "technology",
        ),
        differentiators=(
            "Proprietary MFGC formula — not available in any competing platform",
            "Six-tier action classification maps to regulatory escalation requirements",
            "Phase-adaptive weights become maximally conservative at EXECUTE phase",
        ),
    ),
    "hitl_governance": MurphyCapability(
        capability_id="hitl_governance",
        name="Human-in-the-Loop (HITL) Governance",
        description=(
            "Every high-stakes decision routes to a human for approval before "
            "execution — satisfying EU AI Act Article 14 and enterprise governance mandates."
        ),
        maturity_score=9,
        relevant_vertical_ids=(
            "healthcare", "financial_services", "government", "manufacturing",
        ),
        differentiators=(
            "HITL gate is enforced at the architecture level — cannot be bypassed by automation",
            "BLOCK_EXECUTION provides mandatory stop — no equivalent in LangChain/AutoGPT",
            "Graduated trust model: automation earns autonomy through tracked performance",
        ),
    ),
    "safety_gates": MurphyCapability(
        capability_id="safety_gates",
        name="Governance & Safety Gates",
        description=(
            "Configurable safety gates enforce RBAC, compliance policies, budget limits, "
            "and emergency-stop at every execution boundary."
        ),
        maturity_score=10,
        relevant_vertical_ids=(
            "manufacturing", "healthcare", "government", "financial_services",
        ),
        differentiators=(
            "Emergency-stop gate — full execution halt without data loss",
            "GateCompiler dynamically generates gate pipelines per domain",
            "Safety gates proven on IEC 61508 SIL-2 pathway",
        ),
    ),
    "multi_agent_orchestration": MurphyCapability(
        capability_id="multi_agent_orchestration",
        name="Multi-Agent Orchestration",
        description=(
            "Coordinate swarms of specialised agents — executor, validator, "
            "researcher, planner, reviewer, optimizer — with thread-safe broadcast "
            "and priority routing."
        ),
        maturity_score=10,
        relevant_vertical_ids=(
            "technology", "manufacturing", "financial_services",
        ),
        differentiators=(
            "AgentCoordinator with 6 roles, broadcast + priority routing",
            "Wingman Protocol: every executor paired with a validator",
            "Cascading wingman evolution — validation rules improve over time",
        ),
    ),
    "llm_multi_provider_routing": MurphyCapability(
        capability_id="llm_multi_provider_routing",
        name="LLM Multi-Provider Routing",
        description=(
            "Routes inference requests across 12 LLM providers using 6 strategies "
            "including confidence-weighted routing — no single-provider lock-in."
        ),
        maturity_score=10,
        relevant_vertical_ids=("technology", "professional_services"),
        differentiators=(
            "12 providers: Groq, OpenAI, Anthropic, local models, and more",
            "Confidence-weighted routing — unique optimization strategy",
            "Automatic failover with zero downtime",
        ),
    ),
    "business_process_automation": MurphyCapability(
        capability_id="business_process_automation",
        name="Business Process Automation",
        description=(
            "Automates end-to-end business processes — sales qualification, "
            "contract workflows, reporting, and operational tasks — via natural language."
        ),
        maturity_score=10,
        relevant_vertical_ids=(
            "professional_services", "financial_services", "technology",
            "healthcare", "government",
        ),
        differentiators=(
            "workflow_builder.py compiles NL descriptions into executable pipelines",
            "57+ connectors across CRM, ERP, SCADA, cloud, and communication platforms",
            "Self-correcting: golden-path replay recreates successful executions",
        ),
    ),
    "app_connector_ecosystem": MurphyCapability(
        capability_id="app_connector_ecosystem",
        name="App Connector Ecosystem (57+ connectors)",
        description=(
            "57 pre-built connectors across 20 categories — CRM, ERP, cloud, "
            "IoT, healthcare (FHIR), financial, DevOps, and communication platforms. "
            "Industrial connectors cover building automation (BACnet, KNX, Modbus), "
            "energy management (ISO 50001, demand response), additive manufacturing "
            "(OPC-UA AM, GrabCAD, Eiger, EOSTATE), and factory automation "
            "(OPC-UA, EtherNet/IP, PROFINET, MTConnect)."
        ),
        maturity_score=10,
        relevant_vertical_ids=(
            "technology", "financial_services", "healthcare",
            "manufacturing", "professional_services",
            "iot_building_automation", "energy_management",
            "additive_manufacturing", "factory_automation",
        ),
        differentiators=(
            "7 connectors beyond the 50-connector industry benchmark",
            "FHIR Healthcare connector — ships ready for HIPAA-compliant workflows",
            "Plugin SDK — operators build and publish custom connectors",
            "Building automation: BACnet/IP, KNX, Modbus, DALI, LonWorks, OPC-UA",
            "Factory automation: 15 vendor connectors — Rockwell, Siemens, Beckhoff, FANUC, ABB, KUKA",
            "Additive manufacturing: FDM/SLS/DMLS — GrabCAD, Eiger, EOSTATE, HP Command Center",
        ),
    ),
    "no_code_low_code_ux": MurphyCapability(
        capability_id="no_code_low_code_ux",
        name="No-Code / Low-Code UX (Describe → Execute)",
        description=(
            "The Describe-to-Execute paradigm replaces drag-and-drop builders — "
            "operators describe what they want in plain English and Murphy builds "
            "and runs the workflow automatically."
        ),
        maturity_score=10,
        relevant_vertical_ids=(
            "technology", "professional_services", "financial_services",
            "healthcare", "government",
        ),
        differentiators=(
            "Superior to Zapier/Make/n8n visual builders — no canvas required",
            "Text-to-automation engine handles complex multi-branch workflows",
            "Visual builder also available for teams that prefer it",
        ),
    ),
    "iot_sensor_actuator_control": MurphyCapability(
        capability_id="iot_sensor_actuator_control",
        name="IoT / Sensor / Actuator Control",
        description=(
            "Native integration with industrial IoT protocols (OPC-UA, SCADA, "
            "Modbus TCP, BACnet, KNX, EtherNet/IP, PROFINET, MTConnect) — Murphy reads "
            "sensors, processes telemetry, and triggers actuators through "
            "confidence-gated commands."
        ),
        maturity_score=9,
        relevant_vertical_ids=(
            "manufacturing", "government",
            "iot_building_automation", "energy_management",
            "factory_automation",
        ),
        differentiators=(
            "Safety-critical EXECUTIVE gate with emergency-stop for actuator commands",
            "Predictive maintenance: trend-based failure classification before downtime",
            "Multi-sensor fusion: Kalman, Bayesian, Complementary strategies",
            "15+ factory automation connectors: Rockwell, Siemens, Beckhoff, FANUC, ABB, KUKA",
            "Building automation connectors: BACnet/IP, KNX, Modbus, DALI, OPC-UA",
        ),
    ),
    "self_improving_learning": MurphyCapability(
        capability_id="self_improving_learning",
        name="Self-Improving / Learning",
        description=(
            "Murphy learns from every execution — golden-path replay, outcome "
            "feedback loops, and the Shadow Learning System that practices strategies "
            "before promoting them to live use."
        ),
        maturity_score=9,
        relevant_vertical_ids=("technology", "financial_services", "manufacturing"),
        differentiators=(
            "Shadow Learning: paper bots practice vs live data — winning weeks promoted by human",
            "GeographicLoadBalancer adjusts routing weights from real-time outcomes",
            "Causality sandbox: what-if scenario simulation before live execution",
        ),
    ),
    "ml_builtin": MurphyCapability(
        capability_id="ml_builtin",
        name="Built-in ML (Zero External Dependencies)",
        description=(
            "Core ML capabilities ship with Murphy — pattern detection, "
            "outcome tracking, and anomaly detection — without requiring "
            "PyTorch, TensorFlow, or cloud ML services."
        ),
        maturity_score=9,
        relevant_vertical_ids=("technology", "manufacturing", "financial_services"),
        differentiators=(
            "Runs fully air-gapped — no cloud ML dependency",
            "Zero-dep stdlib implementation for all core scoring",
            "scikit-learn and scipy used when available for enhanced accuracy",
        ),
    ),
    "autonomous_business_ops": MurphyCapability(
        capability_id="autonomous_business_ops",
        name="Autonomous Business Operations",
        description=(
            "Murphy can run entire business functions autonomously — marketing, "
            "sales outreach, content creation, billing management, and developer "
            "relations — all HITL-gated and compliance-checked."
        ),
        maturity_score=9,
        relevant_vertical_ids=(
            "technology", "professional_services",
        ),
        differentiators=(
            "Self-Marketing Orchestrator (MKT-006): Murphy markets itself autonomously",
            "Self-Selling Engine: compliant B2B outreach on autopilot",
            "Revenue loop: subscription management + billing via PayPal and Coinbase",
        ),
    ),
    "cryptographic_audit_trail": MurphyCapability(
        capability_id="cryptographic_audit_trail",
        name="Cryptographic Audit Trail",
        description=(
            "Every decision, execution, and override is recorded in a "
            "tamper-evident, SHA-256 hash-chained audit log — satisfying EU AI "
            "Act Article 15 and SOC 2 audit requirements."
        ),
        maturity_score=10,
        relevant_vertical_ids=(
            "healthcare", "financial_services", "government", "manufacturing",
        ),
        differentiators=(
            "Blockchain-inspired hash chaining — tamper detection on any entry",
            "HMAC-SHA256 payload signing on all webhook events",
            "Patent #3 in progress for cryptographic execution integrity",
        ),
    ),
    "eu_ai_act_compliance": MurphyCapability(
        capability_id="eu_ai_act_compliance",
        name="EU AI Act Compliance Infrastructure",
        description=(
            "Murphy is purpose-built for the EU AI Act era — Articles 9 "
            "(Risk Management), 13 (Transparency), and 14 (Human Oversight) "
            "satisfied by core architecture."
        ),
        maturity_score=10,
        relevant_vertical_ids=(
            "healthcare", "financial_services", "government", "manufacturing",
        ),
        differentiators=(
            "Only AI automation platform with MFGC formula satisfying Art. 9 continuously",
            "ConfidenceResult provides auditable rationale per decision (Art. 13)",
            "BLOCK_EXECUTION satisfies Art. 14 'effective oversight' requirement",
        ),
    ),
    "community_ecosystem": MurphyCapability(
        capability_id="community_ecosystem",
        name="Community & Plugin Ecosystem",
        description=(
            "A thriving community portal, Plugin SDK, and 57+ connector registry "
            "let developers extend Murphy with custom capabilities and share them "
            "via the community marketplace."
        ),
        maturity_score=10,
        relevant_vertical_ids=("technology", "professional_services"),
        differentiators=(
            "Plugin SDK with integrity validation — connectors cannot bypass safety gates",
            "Community portal with discussion, showcases, and plugin marketplace",
            "Pre-built healthcare workflow ships in the visual builder",
        ),
    ),
    "production_deployment_readiness": MurphyCapability(
        capability_id="production_deployment_readiness",
        name="Production Deployment Readiness",
        description=(
            "Docker / Kubernetes / Helm deployment with Prometheus + Grafana "
            "observability, full health checks, and zero-downtime rolling updates — "
            "ready for enterprise on-premises or cloud deployment."
        ),
        maturity_score=10,
        relevant_vertical_ids=(
            "technology", "manufacturing", "government", "financial_services",
        ),
        differentiators=(
            "Full observability stack (Prometheus + Grafana) ships in docker-compose",
            "Kubernetes NetworkPolicy + PodDisruptionBudget hardened for production",
            "Self-hosted, cloud-managed, and hybrid deployment modes",
        ),
    ),
}

# ---------------------------------------------------------------------------
# Industry vertical registry
# ---------------------------------------------------------------------------

INDUSTRY_VERTICALS: Dict[str, IndustryVertical] = {
    "healthcare": IndustryVertical(
        vertical_id="healthcare",
        name="Healthcare & Life Sciences",
        icp=(
            "Mid-to-large healthcare organisations, hospital systems, digital health "
            "startups, and medical device companies that need to automate clinical "
            "workflows, patient data pipelines, or administrative processes while "
            "maintaining strict HIPAA compliance and physician-in-the-loop oversight. "
            "Decision-makers are typically CTOs, Chief Digital Officers, or VP of "
            "Clinical Operations with $200K–$2M annual automation budgets."
        ),
        pain_points=(
            "Manual clinical workflows slow care delivery and introduce human error",
            "HIPAA and EU AI Act compliance burden for any AI-augmented decision support",
            "EHR integration complexity — HL7 FHIR, DICOM, and proprietary APIs",
            "Physician time wasted on administrative automation that lacks clinical context",
            "Regulatory requirement for explainable, auditable AI decisions (Art. 13/14)",
        ),
        regulatory_context=(
            "HIPAA, EU AI Act Annex III §5b (High-Risk — clinical decision support), "
            "MDR/IVDR (medical device software), FDA SaMD guidelines, SOC 2 Type II"
        ),
        murphy_value_props=(
            "HITL gate enforces physician-in-the-loop — every AI recommendation requires "
            "approval before action; no autonomous clinical decisions",
            "ConfidenceResult provides auditable rationale per recommendation — satisfies "
            "EU AI Act Article 13 transparency requirement",
            "FHIR Healthcare connector ships ready-to-use — zero integration code required",
            "Pre-built HIPAA-compliant Patient → HIPAA Gate → AI Diagnosis → Doctor Approval "
            "workflow in the visual builder",
            "Cryptographic audit trail with SHA-256 hash-chaining for compliance evidence",
        ),
        relevant_capability_ids=(
            "confidence_gated_execution",
            "hitl_governance",
            "safety_gates",
            "cryptographic_audit_trail",
            "eu_ai_act_compliance",
            "nlp_workflow_automation",
            "app_connector_ecosystem",
            "business_process_automation",
        ),
        content_topics=(
            "How confidence-gated AI prevents clinical errors in automated workflows",
            "HIPAA-compliant workflow automation: what every healthcare CTO needs to know",
            "EU AI Act Article 14 for healthcare: how Murphy satisfies human oversight",
            "From FHIR to action: automating patient onboarding with zero code",
            "Why healthcare AI must refuse to act — the case for BLOCK_EXECUTION",
            "Physician-in-the-loop automation: reducing administrative burden without risk",
            "Audit trails for AI in healthcare: SHA-256 tamper detection in practice",
        ),
        b2b_pitch_hook=(
            "Murphy System ships with FHIR connectors, physician-in-the-loop gates, and "
            "EU AI Act Article 14 compliance built into its core architecture — "
            "making it the only automation platform that healthcare organisations can "
            "deploy without a custom compliance layer."
        ),
    ),
    "financial_services": IndustryVertical(
        vertical_id="financial_services",
        name="Financial Services & FinTech",
        icp=(
            "Banks, asset managers, insurance companies, and FinTech startups that "
            "need to automate regulated financial processes — KYC/AML, loan decisioning, "
            "trading compliance, or claims processing — with full auditability and "
            "regulatory controls. Typical buyers: CTOs, Chief Risk Officers, or "
            "VP of Operations with $500K–$5M technology budgets."
        ),
        pain_points=(
            "Regulatory burden for every automated financial decision (SOX, MiFID II, AML)",
            "Manual KYC/AML processes create bottlenecks and compliance exposure",
            "Explainability gap: AI decisions in credit scoring require human-readable rationale",
            "Integration complexity with core banking, trading, and risk systems",
            "Audit trail requirements for every automated action under SOC 2 / SOX",
        ),
        regulatory_context=(
            "SOX, MiFID II, AML/KYC (FATF), PCI DSS, EU AI Act Annex III §5b "
            "(High-Risk — credit scoring, insurance), SOC 2 Type II, GDPR"
        ),
        murphy_value_props=(
            "BUDGET gate controls financial exposure — hard stops before any spend action",
            "COMPLIANCE gate enforces regulatory thresholds — no action without policy clearance",
            "Six-tier classification maps directly to regulatory escalation requirements",
            "Cryptographic audit trail satisfies SOC 2 and SOX evidence requirements",
            "MFGC confidence formula provides explainable rationale for every automated decision",
        ),
        relevant_capability_ids=(
            "confidence_gated_execution",
            "safety_gates",
            "cryptographic_audit_trail",
            "eu_ai_act_compliance",
            "hitl_governance",
            "business_process_automation",
            "self_improving_learning",
            "nlp_workflow_automation",
        ),
        content_topics=(
            "Automating KYC/AML workflows without compliance exposure",
            "How confidence-gated AI satisfies MiFID II explainability requirements",
            "SOC 2 audit trails for AI automation: what financial services teams need",
            "From manual to automated loan decisioning in 30 days with Murphy",
            "EU AI Act Annex III: preparing financial services AI for high-risk classification",
            "Six-tier action classification: mapping Murphy's safety model to regulatory tiers",
            "Budget gates and risk gates: how Murphy prevents financial automation runaway",
        ),
        b2b_pitch_hook=(
            "Murphy System's BUDGET gate, COMPLIANCE gate, and cryptographic audit trail "
            "were designed specifically for regulated financial processes — "
            "giving your compliance team the evidence they need while freeing "
            "your operations team from manual bottlenecks."
        ),
    ),
    "manufacturing": IndustryVertical(
        vertical_id="manufacturing",
        name="Manufacturing & Industrial / IIoT",
        icp=(
            "Discrete manufacturers, process plants, and industrial automation "
            "companies looking to modernise SCADA/OT systems with AI-native "
            "orchestration — predictive maintenance, production scheduling, "
            "quality control, and safety-critical actuation. Typical buyers: "
            "VP of Operations, Plant Managers, or OT/IT integration leads with "
            "$300K–$3M operational technology budgets."
        ),
        pain_points=(
            "Legacy SCADA and PLC systems cannot integrate with modern AI orchestration",
            "Unplanned downtime from equipment failures that predictive models could prevent",
            "IEC 61508 SIL-2 certification requirements for safety-critical automation",
            "OT/IT integration gap — operational data siloed from business systems",
            "Manual production scheduling that cannot adapt to real-time shop-floor conditions",
        ),
        regulatory_context=(
            "IEC 61508 (Functional Safety), IEC 62443 (Industrial Cybersecurity), "
            "EU AI Act Annex III §3 (High-Risk — critical infrastructure), "
            "OSHA process safety regulations, ISO 13849"
        ),
        murphy_value_props=(
            "Safety-critical EXECUTIVE gate with emergency-stop — full halt without data loss",
            "OPC-UA, SCADA, and Modbus TCP connectors — native industrial protocol support",
            "Predictive Maintenance Engine (PME-001): trend-based failure prediction with "
            "days-to-failure estimates before downtime occurs",
            "Multi-sensor fusion (Kalman, Bayesian, Complementary) for redundant safety signals",
            "Confidence gates become maximally conservative at execution phase — safe for SIL-2 pathway",
        ),
        relevant_capability_ids=(
            "iot_sensor_actuator_control",
            "safety_gates",
            "confidence_gated_execution",
            "self_improving_learning",
            "ml_builtin",
            "cryptographic_audit_trail",
            "business_process_automation",
            "production_deployment_readiness",
        ),
        content_topics=(
            "SCADA modernisation with AI: how Murphy bridges OT and IT",
            "Predictive maintenance ROI: preventing $500K downtime events with trend AI",
            "IEC 61508 SIL-2 and AI automation: Murphy's safety gate pathway",
            "Multi-sensor fusion for industrial safety: Kalman vs. Bayesian approaches",
            "Natural language production scheduling: describe it, Murphy runs it",
            "Emergency-stop architecture for autonomous manufacturing systems",
            "OPC-UA to cloud: zero-code industrial IoT integration with Murphy",
        ),
        b2b_pitch_hook=(
            "Murphy's EXECUTIVE gate with emergency-stop, OPC-UA/SCADA connectors, and "
            "Predictive Maintenance Engine were built specifically for industrial environments "
            "where an AI system that cannot stop is more dangerous than one that does nothing."
        ),
    ),
    "technology": IndustryVertical(
        vertical_id="technology",
        name="Technology & SaaS Companies",
        icp=(
            "Software companies, SaaS platforms, and technology services firms that "
            "want to embed AI automation into their products, automate their internal "
            "DevOps/engineering workflows, or build on top of Murphy as a platform. "
            "Typical buyers: CPOs, CTOs, or VP Engineering with $100K–$2M "
            "platform/tooling budgets. Strong overlap with integration partnership targets."
        ),
        pain_points=(
            "Engineering bottlenecks from manual CI/CD, issue triage, and release management",
            "LLM provider lock-in — single-vendor dependency creates reliability and cost risk",
            "Scaling internal automation without scaling the DevOps team",
            "Integration maintenance burden across 10–100 SaaS tools",
            "Lack of audit trail and governance for AI-assisted engineering decisions",
        ),
        regulatory_context=(
            "SOC 2 Type II (for SaaS), GDPR (data handling), EU AI Act (if AI features "
            "are customer-facing), open-source license compliance"
        ),
        murphy_value_props=(
            "Multi-provider LLM routing across 12 providers — no single-vendor lock-in",
            "Describe-to-Execute paradigm: automate any DevOps workflow in plain English",
            "Plugin SDK and 57+ connectors — extend Murphy or embed it in your product",
            "GitHub, Linear, Datadog, and CI/CD connectors ship ready-to-use",
            "Multi-agent orchestration with Wingman Protocol — every action validated",
        ),
        relevant_capability_ids=(
            "nlp_workflow_automation",
            "no_code_low_code_ux",
            "llm_multi_provider_routing",
            "multi_agent_orchestration",
            "app_connector_ecosystem",
            "community_ecosystem",
            "production_deployment_readiness",
            "autonomous_business_ops",
            "self_improving_learning",
        ),
        content_topics=(
            "Multi-provider LLM routing: eliminating AI vendor lock-in in 2026",
            "Automating GitHub workflows with natural language — zero YAML required",
            "Describe-to-Execute vs. drag-and-drop: why NL automation wins for engineering teams",
            "Building on Murphy: the Plugin SDK for SaaS developers",
            "Wingman Protocol: why every autonomous AI action needs a validator",
            "Confidence-weighted LLM routing: the optimization strategy Zapier can't match",
            "Murphy + Linear: automating sprint planning, issue triage, and CI triggers via chat",
        ),
        b2b_pitch_hook=(
            "Murphy's Plugin SDK, 57-connector ecosystem, and multi-provider LLM routing "
            "make it the only AI automation platform that technology companies can embed "
            "into their own product without rebuilding it from scratch."
        ),
    ),
    "professional_services": IndustryVertical(
        vertical_id="professional_services",
        name="Professional Services & Agencies",
        icp=(
            "Consulting firms, law firms, marketing agencies, and managed-service "
            "providers that run complex, multi-client operational workflows and want "
            "to automate project management, reporting, client onboarding, and "
            "knowledge work. Typical buyers: COOs, Operations Directors, or "
            "Managing Partners with $50K–$500K operational efficiency budgets."
        ),
        pain_points=(
            "High-volume repetitive knowledge work (reporting, proposals, status updates) "
            "consuming billable hours",
            "Multi-client workflow management with different toolsets and compliance requirements",
            "Onboarding new clients manually — weeks of setup for each engagement",
            "Knowledge silos: insights from one engagement not reused across the portfolio",
            "Billing and project tracking scattered across disconnected SaaS tools",
        ),
        regulatory_context=(
            "GDPR (client data handling), SOC 2 (for MSPs handling enterprise clients), "
            "sector-specific: SRA (law firms), FCA (financial advisors)"
        ),
        murphy_value_props=(
            "Automate proposal generation, status reporting, and client onboarding in plain English",
            "Notion, Linear, and Microsoft 365 connectors for knowledge-work automation",
            "Self-Marketing Orchestrator: Murphy generates its own content and pitches — "
            "same capability available for agency white-label use",
            "Multi-tenant workspace isolation — separate automation environments per client",
            "Billing automation via PayPal and Coinbase Commerce — zero manual invoicing",
        ),
        relevant_capability_ids=(
            "nlp_workflow_automation",
            "business_process_automation",
            "no_code_low_code_ux",
            "autonomous_business_ops",
            "app_connector_ecosystem",
            "llm_multi_provider_routing",
        ),
        content_topics=(
            "How consulting firms automate proposal writing without losing the human touch",
            "Multi-client automation: managing 50 engagements from a single Murphy instance",
            "Automating client onboarding: from signed contract to active workspace in minutes",
            "Knowledge work on autopilot: how Murphy runs a professional services firm",
            "Billing automation for agencies: from time-tracking to invoice in 3 NL commands",
            "Murphy for MSPs: white-label AI automation with per-client isolation",
            "The autonomous agency: what Murphy-powered professional services looks like in 2026",
        ),
        b2b_pitch_hook=(
            "Murphy's multi-tenant workspace isolation, Notion/M365/Linear connectors, and "
            "Describe-to-Execute paradigm let professional services firms automate every "
            "repetitive workflow across all their clients from a single instance — "
            "without a single line of code."
        ),
    ),
    "government": IndustryVertical(
        vertical_id="government",
        name="Government & Public Sector",
        icp=(
            "Federal, state, and local government agencies, defence contractors, and "
            "public-sector technology teams that need to automate citizen services, "
            "benefits administration, or internal operations while meeting strict "
            "AI governance requirements. Decision-makers: IT Directors, Digital "
            "Transformation Officers, or Programme Managers with $500K–$10M "
            "technology modernisation budgets."
        ),
        pain_points=(
            "Manual benefits and services administration creating citizen-facing delays",
            "Strict AI governance requirements — accountability, explainability, and oversight",
            "Legacy system integration with mainframes and on-premises databases",
            "Security and data sovereignty requirements — cloud-first is often not an option",
            "EU AI Act high-risk classification for many government AI use cases",
        ),
        regulatory_context=(
            "EU AI Act Annex III (High-Risk — benefits administration, law enforcement AI, "
            "border management), FISMA (US federal), ISO 27001, GDPR, "
            "NIST AI Risk Management Framework"
        ),
        murphy_value_props=(
            "HITL governance satisfies EU AI Act Article 14 'effective oversight' requirement "
            "— mandatory for high-risk government AI",
            "Air-gapped deployment: zero external cloud dependency — full data sovereignty",
            "ConfidenceResult provides auditable rationale per decision for FOI/transparency",
            "BLOCK_EXECUTION provides mandatory stop — required for Annex III high-risk systems",
            "Cryptographic audit trail satisfies FISMA and NIST AI RMF evidence requirements",
        ),
        relevant_capability_ids=(
            "eu_ai_act_compliance",
            "hitl_governance",
            "cryptographic_audit_trail",
            "safety_gates",
            "confidence_gated_execution",
            "production_deployment_readiness",
            "iot_sensor_actuator_control",
            "business_process_automation",
        ),
        content_topics=(
            "EU AI Act Annex III: what government agencies must do before deploying AI",
            "Air-gapped AI automation: how Murphy runs with zero cloud dependency",
            "HITL governance for public sector AI: satisfying Article 14 in practice",
            "Automating benefits administration with confidence-gated AI",
            "FISMA and NIST AI RMF: how Murphy's audit trail satisfies federal evidence requirements",
            "Digital transformation in government: NL automation without IT department bottlenecks",
            "The explainability imperative: why government AI must provide auditable rationale",
        ),
        b2b_pitch_hook=(
            "Murphy is the only AI automation platform that was designed from the ground up "
            "for the EU AI Act high-risk classification — with mandatory HITL oversight, "
            "air-gapped deployability, and a cryptographic audit trail that satisfies "
            "Article 15 evidence requirements out of the box."
        ),
    ),
    "iot_building_automation": IndustryVertical(
        vertical_id="iot_building_automation",
        name="IoT & Building Automation Systems (BAS/BMS)",
        icp=(
            "Commercial real-estate owners, facility management companies, smart-building "
            "technology vendors, and systems integrators who deploy BACnet, KNX, Modbus, "
            "or OPC-UA building automation systems and need AI orchestration to unify "
            "HVAC, lighting, access control, and energy systems into a single adaptive loop. "
            "Buyers: VP of Facilities Technology, Chief Sustainability Officers, or BAS "
            "Systems Integrators with $100K–$2M smart-building automation budgets."
        ),
        pain_points=(
            "Siloed building systems (HVAC, lighting, access, elevators) that cannot share "
            "data or respond to each other in real time",
            "Manual setpoint management that wastes 20–40% of building energy",
            "BACnet/KNX/Modbus protocol fragmentation — each system speaks a different language",
            "Reactive rather than predictive maintenance: equipment fails before alerts fire",
            "Sustainability reporting burden — manually aggregating energy data for ESG compliance",
        ),
        regulatory_context=(
            "ASHRAE 90.1 (energy efficiency), ISO 50001 (energy management), "
            "LEED / BREEAM certification requirements, EU Energy Performance of Buildings "
            "Directive (EPBD), local fire and life safety codes (NFPA 72)"
        ),
        murphy_value_props=(
            "Unified protocol bridge: BACnet/IP, KNX, Modbus TCP, DALI, LonWorks, and OPC-UA "
            "all connected through a single Murphy orchestration layer",
            "Describe-to-Execute building automation: 'Reduce HVAC setpoints by 2°C when "
            "occupancy drops below 10%' — Murphy writes the logic automatically",
            "Predictive Maintenance Engine: trend-based failure detection on HVAC, chillers, "
            "and AHUs before downtime occurs",
            "Real-time ESG dashboards: automated energy consumption aggregation and reporting "
            "against LEED/BREEAM/ISO 50001 targets",
            "Safety-gated actuator commands: confidence gates prevent erroneous HVAC/fire-safety "
            "actuation — EU AI Act–aligned oversight built in",
        ),
        relevant_capability_ids=(
            "iot_sensor_actuator_control",
            "app_connector_ecosystem",
            "nlp_workflow_automation",
            "safety_gates",
            "confidence_gated_execution",
            "self_improving_learning",
            "cryptographic_audit_trail",
            "production_deployment_readiness",
        ),
        content_topics=(
            "Unifying BACnet, KNX, and Modbus with AI orchestration — no custom middleware",
            "How AI building automation reduces HVAC energy waste by 30% with zero manual setpoints",
            "Predictive HVAC maintenance: Murphy detects chiller degradation 3 weeks early",
            "LEED and BREEAM automation: how Murphy generates energy compliance reports automatically",
            "Smart building with natural language: 'Reduce cooling when meeting rooms are empty'",
            "OPC-UA companion spec for buildings: Murphy as the unified BAS integration layer",
            "EU EPBD compliance automation: continuous energy performance tracking with Murphy",
        ),
        b2b_pitch_hook=(
            "Murphy's building automation connectors (BACnet/IP, KNX, Modbus, DALI, OPC-UA) "
            "and Describe-to-Execute paradigm let facilities teams automate cross-system "
            "building logic in plain English — unifying HVAC, lighting, and access control "
            "without writing a single line of integration code."
        ),
    ),
    "energy_management": IndustryVertical(
        vertical_id="energy_management",
        name="Energy Management Systems & Energy Audits",
        icp=(
            "Commercial and industrial facility owners, energy services companies (ESCOs), "
            "utility analytics providers, and sustainability managers who need to automate "
            "energy data collection, execute ASHRAE Level I/II/III audits, identify Energy "
            "Conservation Measures (ECMs), and demonstrate ISO 50001 / ENERGY STAR compliance. "
            "Buyers: Chief Sustainability Officers, Energy Managers, or VP Operations with "
            "$50K–$500K energy management programme budgets."
        ),
        pain_points=(
            "Manual energy data collection from multiple utility meters and EMS platforms "
            "taking days of analyst time per facility",
            "ASHRAE energy audits still largely paper-based — ECM identification is slow and "
            "inconsistently prioritised",
            "ISO 50001 certification documentation burden — evidence collection across dozens "
            "of systems",
            "Demand response programme participation requires real-time decision-making that "
            "manual processes cannot support",
            "ESG reporting inconsistency — carbon calculations vary by analyst methodology",
        ),
        regulatory_context=(
            "ISO 50001 (Energy Management Systems), ISO 50002 (Energy Audits), "
            "ASHRAE 90.1 / 100 / 211 (energy performance standards), "
            "ENERGY STAR (EPA benchmarking), EU Energy Efficiency Directive, "
            "LEED / BREEAM (green building certification), SEC climate disclosure rules"
        ),
        murphy_value_props=(
            "ASHRAE Level I/II/III audit automation: ingest utility data, identify ECMs, "
            "auto-compute payback and ROI — weeks of work done in hours",
            "ISO 50001 / ISO 50002 compliance checklists auto-generated with evidence links "
            "from the cryptographic audit trail",
            "Greedy-knapsack ECM prioritisation: maximum energy savings within your capital "
            "budget, ranked by ROI",
            "Demand response automation: Murphy monitors grid signals and dispatches load-shed "
            "commands through building automation connectors in real time",
            "Automated carbon reporting: EUI calculations, kg CO2e estimates, and ENERGY STAR "
            "benchmarking against CBECS medians — all generated from raw meter data",
        ),
        relevant_capability_ids=(
            "iot_sensor_actuator_control",
            "app_connector_ecosystem",
            "nlp_workflow_automation",
            "business_process_automation",
            "self_improving_learning",
            "cryptographic_audit_trail",
            "safety_gates",
            "production_deployment_readiness",
        ),
        content_topics=(
            "ASHRAE Level II energy audit automation: from utility bills to ECM report in 4 hours",
            "ISO 50001 certification with Murphy: automating the evidence trail",
            "Greedy ECM prioritisation: maximising energy savings within a $500K capital budget",
            "Demand response on autopilot: Murphy dispatches load-shed in under 30 seconds",
            "Energy Use Intensity benchmarking: how Murphy compares your facility to CBECS medians",
            "Carbon reporting automation: from smart meter data to SEC-ready ESG disclosure",
            "How AI energy audits find 20% more ECMs than manual ASHRAE Level II",
        ),
        b2b_pitch_hook=(
            "Murphy's Energy Audit Engine (ASHRAE Level I/II/III) and Energy Management "
            "connectors automate the full audit lifecycle — from utility data ingestion to "
            "ISO 50001–compliant reports with ECM ROI rankings — turning a 3-week manual "
            "audit process into a 4-hour automated analysis."
        ),
    ),
    "additive_manufacturing": IndustryVertical(
        vertical_id="additive_manufacturing",
        name="Additive Manufacturing & 3D Printing Automation",
        icp=(
            "Manufacturing companies running FDM, SLS, DMLS, SLA, or PolyJet production "
            "systems who need to automate build job management, quality control, material "
            "tracking, and post-processing workflows. Also AM service bureaus and OEMs "
            "integrating 3D printing into their production floor. Buyers: AM Operations "
            "Managers, Manufacturing Engineers, or VP of Advanced Manufacturing with "
            "$200K–$5M AM fleet investment."
        ),
        pain_points=(
            "Manual build job scheduling across multi-vendor AM fleets wastes machine time "
            "and requires constant human intervention",
            "Post-processing coordination (support removal, heat treatment, finishing) "
            "disconnected from print completion events",
            "Quality tracking inconsistency — build parameters not systematically linked "
            "to inspection results for traceability",
            "OPC-UA AM companion spec adoption uneven — each vendor has a proprietary API",
            "Material consumption tracking manual — wastage hard to quantify across platforms",
        ),
        regulatory_context=(
            "OPC UA Companion Specification for AM (OPC 40564), AS9100D (aerospace quality), "
            "ISO/ASTM 52900 (AM terminology), FDA 21 CFR Part 820 (medical device AM), "
            "MTConnect Additive Device Model, Nadcap AM accreditation"
        ),
        murphy_value_props=(
            "Unified AM fleet management: GrabCAD Print (Stratasys), Eiger (Markforged), "
            "EOSTATE (EOS), HP 3D Command Center — all orchestrated from a single Murphy layer",
            "OPC-UA AM companion spec (OPC 40564) support — standardised machine telemetry "
            "ingestion across compliant vendors",
            "Describe-to-Execute AM workflows: 'Run titanium SLS batch when queue exceeds 5 jobs "
            "and material level is >20%' — Murphy automates the dispatch logic",
            "Quality traceability: build parameters, material lot numbers, and inspection "
            "results linked in the cryptographic audit trail",
            "Post-processing automation: print completion triggers downstream CNC, heat treatment, "
            "and inspection workflows via Murphy's factory automation connectors",
        ),
        relevant_capability_ids=(
            "iot_sensor_actuator_control",
            "app_connector_ecosystem",
            "nlp_workflow_automation",
            "multi_agent_orchestration",
            "cryptographic_audit_trail",
            "business_process_automation",
            "self_improving_learning",
            "safety_gates",
        ),
        content_topics=(
            "Automating multi-vendor AM fleets: GrabCAD + Eiger + EOSTATE unified with Murphy",
            "OPC-UA companion spec for additive manufacturing: Murphy as the integration layer",
            "End-to-end AM traceability: linking build parameters to inspection with AI",
            "Post-processing automation: how Murphy connects print completion to CNC and heat treat",
            "Describe-to-Execute AM scheduling: 'Run titanium SLS when queue exceeds 5 jobs'",
            "AS9100D compliance automation for additive manufacturing with Murphy",
            "AI-driven material consumption tracking across FDM, SLS, and DMLS fleets",
        ),
        b2b_pitch_hook=(
            "Murphy's additive manufacturing connectors (OPC-UA AM / OPC 40564, GrabCAD, "
            "Eiger, EOSTATE, HP Command Center) and natural-language orchestration let AM "
            "operations teams automate multi-vendor fleet scheduling, quality traceability, "
            "and post-processing workflows from a single describe-and-execute interface."
        ),
    ),
    "factory_automation": IndustryVertical(
        vertical_id="factory_automation",
        name="Factory Automation & Industrial Control Systems",
        icp=(
            "Discrete and process manufacturers deploying PLCs, CNC machines, industrial "
            "robots, and SCADA systems who need to modernise their OT layer with AI-native "
            "orchestration — machine-tending automation, production scheduling, quality vision "
            "inspection, and closed-loop process control. Buyers: VP of Manufacturing "
            "Operations, OT/IT Integration Architects, or Plant Managers with $500K–$10M "
            "factory automation investment."
        ),
        pain_points=(
            "OT/IT integration gap — PLC/SCADA data cannot reach business systems without "
            "expensive custom middleware",
            "Robot programming requires specialist integrators for every new task — "
            "no natural-language interface to motion control",
            "Production scheduling is manual or rigid MES-driven — cannot adapt to "
            "real-time machine availability, quality rejects, or material shortages",
            "Machine vision inspection results not fed back to upstream process control",
            "IEC 13849 safety compliance for collaborative robot cells requires careful "
            "software control architecture",
        ),
        regulatory_context=(
            "IEC 61131 (PLC programming languages), IEC 13849 (safety of machinery — "
            "CAT B through CAT 4), ISO 10218 (industrial robot safety), IEC 62443 "
            "(industrial cybersecurity), ISA-95 (enterprise-control integration), "
            "OSHA 1910.217 (machine guarding), EU Machinery Directive"
        ),
        murphy_value_props=(
            "15 factory automation connectors: Rockwell FactoryTalk, Siemens SIMATIC, "
            "Beckhoff TwinCAT, FANUC, ABB OmniCore, KUKA KR C5, Yaskawa, Omron, "
            "Mitsubishi, PTC ThingWorx, Cognex vision — all orchestrated via Murphy",
            "ISA-95 layer-aware execution: Murphy orchestrates FIELD → CONTROL → "
            "SUPERVISORY → MES sequences in the correct order",
            "IEC 13849 safety gate: sequences involving sub-CAT 2 connectors require "
            "explicit safety override — built-in machinery safety compliance",
            "Natural-language robot programming: 'Move robot arm to pick position when "
            "conveyor sensor fires and gripper pressure confirms part present'",
            "Confidence-gated machine commands: the MFGC formula prevents erroneous "
            "actuator commands — no unbound autonomous machine control",
        ),
        relevant_capability_ids=(
            "iot_sensor_actuator_control",
            "app_connector_ecosystem",
            "nlp_workflow_automation",
            "safety_gates",
            "confidence_gated_execution",
            "multi_agent_orchestration",
            "self_improving_learning",
            "cryptographic_audit_trail",
            "production_deployment_readiness",
        ),
        content_topics=(
            "OT/IT convergence with Murphy: connecting PLCs to business systems without custom code",
            "Natural-language robot programming: 'Pick when sensor fires' — Murphy writes the logic",
            "ISA-95 orchestration: how Murphy sequences FIELD, CONTROL, and MES layers correctly",
            "IEC 13849 safety gate in software: Murphy's approach to collaborative robot safety",
            "SCADA modernisation without rip-and-replace: Murphy as the AI overlay layer",
            "Machine vision + process control: closing the quality loop with Murphy and Cognex",
            "Factory automation on autopilot: how Murphy schedules CNC, robots, and conveyors via NL",
        ),
        b2b_pitch_hook=(
            "Murphy's 15-vendor factory automation connector library (Rockwell, Siemens, "
            "Beckhoff, FANUC, ABB, KUKA), ISA-95 layer-aware orchestration, and IEC 13849 "
            "software safety gate give manufacturing teams a natural-language interface to "
            "their entire factory floor — without a single line of PLC code."
        ),
    ),
}

# ---------------------------------------------------------------------------
# Market position (singleton — drawn from EU_AI_ACT_POSITIONING + BUSINESS_MODEL)
# ---------------------------------------------------------------------------

MURPHY_MARKET_POSITION = MarketPosition(
    positioning_statement=(
        "Murphy System is the AI Safety Operating System for regulated enterprises — "
        "the only AI automation platform that combines natural-language workflow "
        "execution with confidence-gated safety, human-in-the-loop governance, and "
        "a cryptographic audit trail that satisfies EU AI Act Article 15."
    ),
    differentiation_pillars=(
        "Confidence-Gated Execution (MFGC): proprietary formula that scores every "
        "action before it runs — no unbound autonomous execution",
        "Describe-to-Execute UX: NL automation that eliminates drag-and-drop builders — "
        "superior to Zapier, Make, and n8n for complex workflows",
        "EU AI Act–ready by architecture: Articles 9, 13, and 14 satisfied by core design, "
        "not bolt-on compliance layers",
        "Zero external dependencies: runs fully air-gapped with Python stdlib — "
        "deployable in sovereign, classified, or air-isolated environments",
        "Full autonomy with full control: HITL graduation model earns automation rights "
        "through tracked performance — trust is measured, not assumed",
        "Industrial-grade connector depth: 57+ connectors spanning BACnet/KNX/OPC-UA "
        "building automation, ISO 50001 energy management, OPC-UA AM additive manufacturing, "
        "and ISA-95 factory automation (EtherNet/IP, PROFINET, MTConnect)",
    ),
    target_segments=(
        "Regulated enterprises in healthcare, financial services, and government "
        "(EU AI Act high-risk — highest willingness to pay)",
        "Industrial manufacturers: factory automation (Rockwell/Siemens/Beckhoff/FANUC), "
        "additive manufacturing (Stratasys/EOS/Markforged), and SCADA modernisation",
        "Smart building & IoT: BAS/BMS operators using BACnet/KNX/Modbus for "
        "HVAC, lighting, access control, and building-wide energy optimisation",
        "Energy management and sustainability: ESCOs and facility owners running "
        "ASHRAE energy audits, ISO 50001 programmes, and ESG reporting",
        "Technology companies and SaaS platforms building on or integrating with Murphy",
        "Professional services firms automating knowledge work and client operations",
    ),
    competitive_moats=(
        "MFGC confidence formula: proprietary — not replicable without deep architectural change",
        "Six-tier action classification: maps directly to EU AI Act risk tiers",
        "Wingman Protocol: executor/validator pairing enforced at the architecture level",
        "57-connector ecosystem with Plugin SDK: network effects grow with community",
        "Patent #3 in progress: cryptographic execution integrity — HMAC-SHA256 audit trail",
        "Air-gap deployability: zero stdlib-external Python — unique in the market",
        "ISA-95 layer-ordered orchestration + IEC 13849 safety gate: built-in factory safety",
        "ASHRAE Level I/II/III Energy Audit Engine + ISO 50001 auto-compliance: "
        "no competing automation platform offers this out of the box",
    ),
    tagline="Automate anything. Trust every action.",
)

# ---------------------------------------------------------------------------
# Offering-type to capability mapping
# ---------------------------------------------------------------------------

# Maps partnership offering types to the capabilities most relevant to demonstrate
_OFFERING_CAPABILITY_MAP: Dict[str, List[str]] = {
    "case_study":             ["nlp_workflow_automation", "business_process_automation", "confidence_gated_execution"],
    "featuring":              ["no_code_low_code_ux", "app_connector_ecosystem", "nlp_workflow_automation"],
    "co_marketing":           ["autonomous_business_ops", "business_process_automation", "community_ecosystem"],
    "integration_featuring":  ["app_connector_ecosystem", "llm_multi_provider_routing", "production_deployment_readiness"],
    "press_mention":          ["eu_ai_act_compliance", "confidence_gated_execution", "cryptographic_audit_trail"],
    "podcast_guest":          ["nlp_workflow_automation", "hitl_governance", "autonomous_business_ops"],
}

# ---------------------------------------------------------------------------
# MarketPositioningEngine
# ---------------------------------------------------------------------------


class MarketPositioningEngine:
    """Provides market positioning intelligence to autonomous marketing systems.

    This engine is the single source of truth for:
      - Murphy's capabilities and their maturity scores
      - Target industry verticals, ICPs, and pain points
      - Industry-specific value propositions and content topics
      - Partner fit scoring based on offering types and industry alignment

    All methods are pure (no side effects) and safe to call concurrently.
    All public inputs are validated against closed allowlists (CWE-20).
    """

    def get_market_position(self) -> MarketPosition:
        """Return Murphy's overarching market position."""
        return MURPHY_MARKET_POSITION

    # ── Capability queries ─────────────────────────────────────────────────

    def list_capabilities(self) -> List[MurphyCapability]:
        """Return all registered capabilities ordered by maturity_score descending."""
        return sorted(
            MURPHY_CAPABILITIES.values(),
            key=lambda c: c.maturity_score,
            reverse=True,
        )

    def get_capability(self, capability_id: str) -> MurphyCapability:
        """Return a capability by ID.

        Raises ValueError for unknown or syntactically invalid IDs (CWE-20).
        """
        capability_id = self._validate_capability_id(capability_id)
        cap = MURPHY_CAPABILITIES.get(capability_id)
        if cap is None:
            raise ValueError(f"Unknown capability_id: {capability_id!r}")
        return cap

    # ── Vertical queries ────────────────────────────────────────────────────

    def list_verticals(self) -> List[IndustryVertical]:
        """Return all registered industry verticals."""
        return list(INDUSTRY_VERTICALS.values())

    def get_vertical(self, vertical_id: str) -> IndustryVertical:
        """Return an industry vertical by ID.

        Raises ValueError for unknown or syntactically invalid IDs (CWE-20).
        """
        vertical_id = self._validate_vertical_id(vertical_id)
        vert = INDUSTRY_VERTICALS.get(vertical_id)
        if vert is None:
            raise ValueError(f"Unknown vertical_id: {vertical_id!r}")
        return vert

    def get_ideal_customer_profile(self, vertical_id: str) -> Dict[str, Any]:
        """Return the ICP, pain points, and regulatory context for a vertical.

        Raises ValueError for unknown vertical_id (CWE-20).
        """
        vert = self.get_vertical(vertical_id)
        return {
            "vertical_id": vert.vertical_id,
            "name": vert.name,
            "icp": vert.icp,
            "pain_points": list(vert.pain_points),
            "regulatory_context": vert.regulatory_context,
            "murphy_value_props": list(vert.murphy_value_props),
            "b2b_pitch_hook": vert.b2b_pitch_hook,
        }

    # ── Content + pitch helpers ─────────────────────────────────────────────

    def get_content_topics_for_vertical(self, vertical_id: str) -> List[str]:
        """Return the content topics most relevant to an industry vertical.

        These topics are designed for blog posts, case studies, and tutorials
        that resonate with the vertical's buyer personas.

        Raises ValueError for unknown vertical_id (CWE-20).
        """
        vert = self.get_vertical(vertical_id)
        return list(vert.content_topics)

    def get_industry_pitch_angle(
        self,
        vertical_id: str,
        offering_types: Optional[List[str]] = None,
    ) -> str:
        """Return an industry-specific pitch angle for a B2B pitch.

        Combines the vertical's B2B pitch hook with offering-type–specific
        capability highlights.

        Raises ValueError for unknown vertical_id or invalid offering_types (CWE-20).
        """
        vert = self.get_vertical(vertical_id)
        hook = vert.b2b_pitch_hook

        if not offering_types:
            return hook

        # Gather unique capability names relevant to the requested offering types
        relevant_caps: List[str] = []
        for ot in offering_types[:6]:          # cap list size — CWE-400
            ot = str(ot)[:_MAX_INPUT_LEN]
            if ot in _OFFERING_CAPABILITY_MAP:
                for cap_id in _OFFERING_CAPABILITY_MAP[ot]:
                    cap = MURPHY_CAPABILITIES.get(cap_id)
                    if cap and cap.name not in relevant_caps:
                        relevant_caps.append(cap.name)
                        if len(relevant_caps) >= 3:
                            break

        if not relevant_caps:
            return hook

        cap_list = ", ".join(relevant_caps[:3])
        return f"{hook}\n\nKey capabilities relevant to this partnership: {cap_list}."

    def get_positioning_for_offering_types(
        self,
        offering_types: List[str],
    ) -> Dict[str, Any]:
        """Return market positioning data tailored to specific offering types.

        Returns a dict with the positioning statement, relevant capabilities,
        and offering-specific differentiation points.

        All offering_types entries are validated against the closed allowlist (CWE-20).
        """
        valid_types: List[str] = []
        for ot in offering_types[:6]:          # cap list size — CWE-400
            ot = str(ot)[:_MAX_INPUT_LEN]
            if ot in _VALID_OFFERING_TYPES:
                valid_types.append(ot)

        relevant_caps: List[MurphyCapability] = []
        seen: set = set()
        for ot in valid_types:
            for cap_id in _OFFERING_CAPABILITY_MAP.get(ot, []):
                if cap_id not in seen:
                    cap = MURPHY_CAPABILITIES.get(cap_id)
                    if cap:
                        relevant_caps.append(cap)
                        seen.add(cap_id)

        return {
            "positioning_statement": MURPHY_MARKET_POSITION.positioning_statement,
            "tagline": MURPHY_MARKET_POSITION.tagline,
            "differentiation_pillars": list(MURPHY_MARKET_POSITION.differentiation_pillars),
            "offering_types": valid_types,
            "relevant_capabilities": [
                {
                    "capability_id": c.capability_id,
                    "name": c.name,
                    "description": c.description,
                    "maturity_score": c.maturity_score,
                    "differentiators": list(c.differentiators),
                }
                for c in relevant_caps
            ],
        }

    # ── Matrix + scoring ────────────────────────────────────────────────────

    def get_capability_matrix(self) -> Dict[str, List[str]]:
        """Return a mapping of capability_id → [vertical_id, ...].

        Useful for understanding which capabilities are most broadly applicable
        and which are niche.
        """
        return {
            cap.capability_id: list(cap.relevant_vertical_ids)
            for cap in MURPHY_CAPABILITIES.values()
        }

    def score_partner_fit(
        self,
        company_name: str,
        offering_types: List[str],
        vertical_id: Optional[str] = None,
    ) -> float:
        """Score the fit between a prospective partner and Murphy's positioning (0.0–1.0).

        Higher scores indicate stronger capability/offering alignment.

        Parameters
        ----------
        company_name : str
            The partner's company name (used for heuristic vertical detection when
            vertical_id is not provided).
        offering_types : list[str]
            The offering types being proposed to this partner.
        vertical_id : str, optional
            Explicit vertical ID; if omitted, inferred from company_name heuristics.

        All inputs are validated/bounded (CWE-20 / CWE-400).
        """
        company_name = str(company_name)[:_MAX_INPUT_LEN].lower()

        # Validate offering types against closed allowlist
        valid_types = [
            str(ot)[:_MAX_INPUT_LEN]
            for ot in offering_types[:6]
            if str(ot)[:_MAX_INPUT_LEN] in _VALID_OFFERING_TYPES
        ]

        # Infer vertical from company name if not provided
        detected_vertical: Optional[str] = vertical_id
        if detected_vertical is None:
            detected_vertical = self._infer_vertical(company_name)

        # Base score: proportion of valid offering types
        if not valid_types:
            base_score = 0.0
        else:
            base_score = len(valid_types) / max(len(offering_types), 1)
            base_score = min(base_score, 1.0)

        # Bonus: vertical relevance — how many relevant capabilities overlap
        vertical_bonus = 0.0
        if detected_vertical and detected_vertical in _VALID_VERTICAL_IDS:
            vert = INDUSTRY_VERTICALS.get(detected_vertical)
            if vert:
                # Count how many offering-type capabilities are in the vertical
                vertical_cap_ids = set(vert.relevant_capability_ids)
                offering_cap_ids: set = set()
                for ot in valid_types:
                    offering_cap_ids.update(_OFFERING_CAPABILITY_MAP.get(ot, []))
                overlap = len(vertical_cap_ids & offering_cap_ids)
                total_offering_caps = len(offering_cap_ids) or 1
                vertical_bonus = min(overlap / total_offering_caps, 0.4)

        return round(min(base_score * 0.6 + vertical_bonus, 1.0), 3)

    def get_vertical_summary(self) -> Dict[str, Any]:
        """Return a compact summary of all verticals for dashboard display."""
        return {
            v.vertical_id: {
                "name": v.name,
                "pain_points_count": len(v.pain_points),
                "value_props_count": len(v.murphy_value_props),
                "relevant_capabilities": len(v.relevant_capability_ids),
                "content_topics_count": len(v.content_topics),
            }
            for v in INDUSTRY_VERTICALS.values()
        }

    def get_capabilities_for_vertical(self, vertical_id: str) -> List[MurphyCapability]:
        """Return the capabilities most relevant to a specific vertical.

        Raises ValueError for unknown vertical_id (CWE-20).
        """
        vert = self.get_vertical(vertical_id)
        caps = []
        for cap_id in vert.relevant_capability_ids:
            cap = MURPHY_CAPABILITIES.get(cap_id)
            if cap:
                caps.append(cap)
        return caps

    # ── Private helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _validate_capability_id(capability_id: str) -> str:
        """Validate capability_id against the closed allowlist (CWE-20)."""
        if not isinstance(capability_id, str):
            raise ValueError("capability_id must be a string")
        capability_id = capability_id.strip()[:_MAX_INPUT_LEN]
        if capability_id not in _VALID_CAPABILITY_IDS:
            raise ValueError(
                f"Unknown capability_id {capability_id!r}. "
                f"Valid IDs: {sorted(_VALID_CAPABILITY_IDS)}"
            )
        return capability_id

    @staticmethod
    def _validate_vertical_id(vertical_id: str) -> str:
        """Validate vertical_id against the closed allowlist (CWE-20)."""
        if not isinstance(vertical_id, str):
            raise ValueError("vertical_id must be a string")
        vertical_id = vertical_id.strip()[:_MAX_INPUT_LEN]
        if vertical_id not in _VALID_VERTICAL_IDS:
            raise ValueError(
                f"Unknown vertical_id {vertical_id!r}. "
                f"Valid IDs: {sorted(_VALID_VERTICAL_IDS)}"
            )
        return vertical_id

    @staticmethod
    def _infer_vertical(company_name_lower: str) -> Optional[str]:
        """Heuristic vertical detection from company name fragments."""
        _HINTS: List[tuple] = [
            # Healthcare
            ("health", "healthcare"),
            ("medical", "healthcare"),
            ("pharma", "healthcare"),
            ("clinic", "healthcare"),
            ("hospital", "healthcare"),
            # Financial services
            ("bank", "financial_services"),
            ("financ", "financial_services"),
            ("insur", "financial_services"),
            ("invest", "financial_services"),
            ("trading", "financial_services"),
            ("capital", "financial_services"),
            # Factory automation — check before generic "manufacturing"
            ("rockwell", "factory_automation"),
            ("beckhoff", "factory_automation"),
            ("fanuc", "factory_automation"),
            ("siemens", "factory_automation"),
            ("abb", "factory_automation"),
            ("kuka", "factory_automation"),
            ("yaskawa", "factory_automation"),
            ("omron", "factory_automation"),
            ("mitsubishi", "factory_automation"),
            ("cognex", "factory_automation"),
            ("keyence", "factory_automation"),
            ("ptc", "factory_automation"),
            ("thingworx", "factory_automation"),
            ("ignition", "factory_automation"),
            ("emerson", "factory_automation"),
            ("factorytalk", "factory_automation"),
            # Additive manufacturing — check before generic "manufacturing"
            ("stratasys", "additive_manufacturing"),
            ("eos gmbh", "additive_manufacturing"),
            ("markforged", "additive_manufacturing"),
            ("hp 3d", "additive_manufacturing"),
            ("bambu", "additive_manufacturing"),
            ("ultimaker", "additive_manufacturing"),
            ("formlabs", "additive_manufacturing"),
            ("carbon3d", "additive_manufacturing"),
            ("additive", "additive_manufacturing"),
            # IoT / building automation
            ("johnson controls", "iot_building_automation"),
            ("honeywell", "iot_building_automation"),
            ("schneider", "iot_building_automation"),
            ("bacnet", "iot_building_automation"),
            ("knx", "iot_building_automation"),
            ("building auto", "iot_building_automation"),
            ("smart building", "iot_building_automation"),
            ("desigo", "iot_building_automation"),
            ("openblue", "iot_building_automation"),
            # Energy management / audits
            ("ameresco", "energy_management"),
            ("facilio", "energy_management"),
            ("energycap", "energy_management"),
            ("energy toolbase", "energy_management"),
            ("energy manage", "energy_management"),
            ("energy audit", "energy_management"),
            ("esco", "energy_management"),
            ("wattics", "energy_management"),
            ("enertiv", "energy_management"),
            # Generic manufacturing (lower priority — after specific verticals)
            ("manufactur", "manufacturing"),
            ("factory", "factory_automation"),
            ("industrial", "manufacturing"),
            ("scada", "manufacturing"),
            ("plant", "manufacturing"),
            # Technology
            ("zapier", "technology"),
            ("hubspot", "technology"),
            ("salesforce", "technology"),
            ("github", "technology"),
            ("linear", "technology"),
            ("notion", "technology"),
            ("datadog", "technology"),
            ("microsoft", "technology"),
            # Government
            ("government", "government"),
            ("agency", "government"),
            ("federal", "government"),
            ("ministry", "government"),
            ("council", "government"),
            # Professional services
            ("consulting", "professional_services"),
            ("advisory", "professional_services"),
        ]
        for fragment, vertical in _HINTS:
            if fragment in company_name_lower:
                return vertical
        return None


# ---------------------------------------------------------------------------
# Module-level singleton (optional convenience accessor)
# ---------------------------------------------------------------------------

_DEFAULT_ENGINE: Optional[MarketPositioningEngine] = None


def get_default_positioning_engine() -> MarketPositioningEngine:
    """Return the module-level singleton MarketPositioningEngine.

    Creates the instance lazily on first call.  Thread-safe because CPython
    module-level assignment is atomic for simple assignments.
    """
    global _DEFAULT_ENGINE  # noqa: PLW0603
    if _DEFAULT_ENGINE is None:
        _DEFAULT_ENGINE = MarketPositioningEngine()
    return _DEFAULT_ENGINE


# ---------------------------------------------------------------------------
# Public API surface
# ---------------------------------------------------------------------------

__all__ = [
    # Data models
    "MurphyCapability",
    "IndustryVertical",
    "MarketPosition",
    # Registries
    "MURPHY_CAPABILITIES",
    "INDUSTRY_VERTICALS",
    "MURPHY_MARKET_POSITION",
    # Engine
    "MarketPositioningEngine",
    "get_default_positioning_engine",
]
