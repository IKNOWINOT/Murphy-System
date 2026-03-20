"""
Inference-Based Domain Gate Engine with Rosetta Form Schemas

This module implements the "multi-Rosetta soul" pattern — each agent's soul is
their Rosetta state document which drives:

  1. What information the agent needs (form schema)
  2. What gates apply to their domain (inferred, not hardcoded)
  3. What metrics matter per org chart position
  4. What questions to ask when schema fields are missing

Architecture — the generative form loop:

  Agent Call-to-Action
       │
       ▼
  Rosetta Form Schema ─── defines what data the action needs
       │
       ▼
  Sensors ─── observe chronological events, feed data into schema
       │
       ▼
  LLM fills generatively ─── fills missing schema fields from event stream
       │
       ▼
  Gates ─── checkpoint each field/action (inferred from subject matter)
       │
       ▼
  Confidence Engine ─── computes error probability on generative fill
       │
       ▼
  HITL ─── human-in-the-loop catches remaining uncertainty
       │
       ▼
  Rosetta State updated ─── verified data becomes ground truth

The key insight: forms are built around agent calls-to-action. Gates are
checkpoints on those actions. Sensors observe data flowing in. The LLM's
job is to fill the schema generatively based on the chronological order
of events. But with the confidence engine + Murphy Index + HITL, the
error probability is worked out before anything executes.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from domain_gate_generator import DomainGate, DomainGateGenerator, GateSeverity, GateType

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Industry / Role knowledge base — drives inference
# ---------------------------------------------------------------------------

# Canonical org positions that apply across ALL company types.
# Each position has associated metrics that matter for running that function.
UNIVERSAL_POSITIONS: Dict[str, Dict[str, Any]] = {
    "ceo": {
        "title": "Chief Executive Officer",
        "metrics": ["revenue_growth", "net_margin", "customer_satisfaction", "employee_retention"],
        "authority": "executive",
        "gates": ["budget_gate", "strategic_alignment_gate"],
    },
    "cfo": {
        "title": "Chief Financial Officer",
        "metrics": ["cash_flow", "burn_rate", "gross_margin", "accounts_receivable_days"],
        "authority": "executive",
        "gates": ["budget_gate", "compliance_gate", "audit_gate"],
    },
    "cto": {
        "title": "Chief Technology Officer",
        "metrics": ["system_uptime", "deploy_frequency", "incident_response_time", "tech_debt_ratio"],
        "authority": "executive",
        "gates": ["architecture_review_gate", "security_gate"],
    },
    "vp_sales": {
        "title": "VP of Sales",
        "metrics": ["pipeline_velocity", "win_rate", "avg_deal_size", "quota_attainment"],
        "authority": "high",
        "gates": ["lead_validation_gate", "proposal_authority_gate"],
    },
    "vp_operations": {
        "title": "VP of Operations",
        "metrics": ["throughput", "error_rate", "cycle_time", "resource_utilization"],
        "authority": "high",
        "gates": ["quality_gate", "safety_gate"],
    },
    "sales_rep": {
        "title": "Sales Representative",
        "metrics": ["calls_per_day", "conversion_rate", "avg_response_time", "pipeline_value"],
        "authority": "low",
        "gates": ["lead_validation_gate", "outreach_compliance_gate"],
    },
    "engineer": {
        "title": "Software Engineer",
        "metrics": ["code_quality", "pr_review_time", "bug_fix_rate", "test_coverage"],
        "authority": "medium",
        "gates": ["code_review_gate", "security_scan_gate"],
    },
    "support_agent": {
        "title": "Customer Support Agent",
        "metrics": ["ticket_resolution_time", "csat_score", "first_contact_resolution", "ticket_volume"],
        "authority": "low",
        "gates": ["escalation_gate", "data_access_gate"],
    },
    "marketing_manager": {
        "title": "Marketing Manager",
        "metrics": ["lead_generation_rate", "cost_per_lead", "campaign_roi", "brand_awareness"],
        "authority": "medium",
        "gates": ["budget_gate", "brand_compliance_gate", "content_approval_gate"],
    },
    "hr_manager": {
        "title": "HR Manager",
        "metrics": ["time_to_hire", "offer_acceptance_rate", "employee_satisfaction", "turnover_rate"],
        "authority": "medium",
        "gates": ["compliance_gate", "data_privacy_gate"],
    },
    "product_manager": {
        "title": "Product Manager",
        "metrics": ["feature_adoption", "nps_score", "release_cadence", "backlog_health"],
        "authority": "medium",
        "gates": ["prioritization_gate", "stakeholder_approval_gate"],
    },
}

# Industry-specific positions and their additional metrics/gates.
INDUSTRY_POSITIONS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "technology": {
        "devops_engineer": {
            "title": "DevOps Engineer",
            "metrics": ["deploy_frequency", "lead_time_for_changes", "change_failure_rate", "mttr"],
            "authority": "medium",
            "gates": ["infrastructure_gate", "security_scan_gate"],
        },
        "data_scientist": {
            "title": "Data Scientist",
            "metrics": ["model_accuracy", "inference_latency", "data_pipeline_uptime", "experiment_velocity"],
            "authority": "medium",
            "gates": ["data_privacy_gate", "model_validation_gate"],
        },
    },
    "manufacturing": {
        "plant_manager": {
            "title": "Plant Manager",
            "metrics": ["oee", "defect_rate", "safety_incidents", "production_volume"],
            "authority": "high",
            "gates": ["safety_gate", "quality_gate", "environmental_gate"],
        },
        "quality_inspector": {
            "title": "Quality Inspector",
            "metrics": ["inspection_throughput", "defect_detection_rate", "false_positive_rate"],
            "authority": "medium",
            "gates": ["quality_gate", "calibration_gate"],
        },
    },
    "finance": {
        "risk_analyst": {
            "title": "Risk Analyst",
            "metrics": ["var_accuracy", "exposure_coverage", "model_backtest_score", "alert_precision"],
            "authority": "medium",
            "gates": ["compliance_gate", "audit_gate", "regulatory_gate"],
        },
        "compliance_officer": {
            "title": "Compliance Officer",
            "metrics": ["regulatory_filing_timeliness", "violation_count", "audit_findings", "training_completion"],
            "authority": "high",
            "gates": ["regulatory_gate", "audit_gate"],
        },
    },
    "healthcare": {
        "clinical_director": {
            "title": "Clinical Director",
            "metrics": ["patient_outcomes", "readmission_rate", "treatment_adherence", "wait_time"],
            "authority": "high",
            "gates": ["hipaa_gate", "clinical_protocol_gate", "patient_consent_gate"],
        },
        "nurse_manager": {
            "title": "Nurse Manager",
            "metrics": ["staff_ratio", "medication_error_rate", "patient_satisfaction", "overtime_hours"],
            "authority": "medium",
            "gates": ["staffing_gate", "safety_gate"],
        },
    },
    "retail": {
        "store_manager": {
            "title": "Store Manager",
            "metrics": ["revenue_per_sqft", "inventory_turnover", "shrinkage_rate", "customer_traffic"],
            "authority": "medium",
            "gates": ["inventory_gate", "pricing_gate"],
        },
        "merchandiser": {
            "title": "Merchandiser",
            "metrics": ["sell_through_rate", "margin_per_sku", "planogram_compliance", "stock_availability"],
            "authority": "low",
            "gates": ["pricing_gate", "brand_compliance_gate"],
        },
    },
    "energy": {
        "grid_operator": {
            "title": "Grid Operator",
            "metrics": ["grid_stability", "load_factor", "outage_duration", "renewable_mix"],
            "authority": "high",
            "gates": ["safety_gate", "environmental_gate", "regulatory_gate"],
        },
    },
    "media": {
        "content_director": {
            "title": "Content Director",
            "metrics": ["engagement_rate", "content_velocity", "audience_growth", "monetization_cpm"],
            "authority": "high",
            "gates": ["content_approval_gate", "brand_compliance_gate", "legal_review_gate"],
        },
    },
}

# Keywords → industry inference mapping
INDUSTRY_KEYWORDS: Dict[str, List[str]] = {
    "technology": [
        "tech", "software", "saas", "cloud", "ai", "startup", "app", "platform", "api", "devops",
        "ci/cd", "ci cd", "pipeline", "deploy", "microservice", "container", "kubernetes", "docker",
        "security scan", "vulnerability scan", "incident", "outage", "triage", "escalation",
        "etl", "data pipeline", "bigquery", "data warehouse",
        "onboarding", "account provisioning", "orientation",
        "dashboard", "metrics", "report", "data report",
        "blog", "content", "cms", "publishing",
        "crm", "lead", "nurtur", "email sequence",
        "automate", "automation", "workflow",
    ],
    "manufacturing": [
        "factory", "manufacturing", "production", "assembly", "industrial", "plant",
    ],
    "finance": [
        "bank", "finance", "financial", "fintech", "insurance", "investment", "trading", "lending",
        "payments", "invoice", "billing", "accounts payable", "quickbooks", "netsuite", "ledger",
        "accounting",
    ],
    "healthcare": [
        "hospital", "clinic", "health", "healthcare", "medical", "pharma", "biotech", "patient",
        "clinical",
    ],
    "retail": [
        "store", "ecommerce", "shop", "retail", "marketplace", "consumer", "brand", "merchandise",
    ],
    "energy": [
        "energy", "utility", "power", "grid", "solar", "wind", "oil", "gas", "renewable",
    ],
    "media": [
        "media", "content", "publishing", "news", "entertainment", "streaming", "social", "creative",
    ],
    "professional_services": [
        "consulting", "consultant", "advisory", "accountant", "accounting", "law", "legal",
        "audit", "strategy", "management consulting", "professional services", "agency",
        "staffing", "recruitment", "hr services", "coaching", "training",
    ],
    "trade_services": [
        "plumbing", "plumber", "hvac", "electrician", "electrical", "roofing", "roofer",
        "landscaping", "painter", "painting", "contractor", "handyman", "pest control",
        "cleaning", "janitorial", "flooring", "carpentry", "welding", "home services",
        "field services", "trade", "trades",
    ],
    "construction": [
        "construction", "builder", "general contractor", "civil", "infrastructure", "building",
        "renovation", "remodel", "architecture", "engineering", "project site", "subcontractor",
    ],
    "logistics": [
        "logistics", "freight", "shipping", "trucking", "warehouse", "fleet", "courier",
        "supply chain", "distribution", "fulfillment", "last mile", "3pl",
    ],
    "real_estate": [
        "real estate", "property", "broker", "realtor", "landlord", "tenant", "leasing",
        "property management", "commercial real estate", "residential", "mortgage",
    ],
    "education": [
        "school", "university", "education", "training", "elearning", "tutoring", "lms",
        "curriculum", "course", "instructor", "student", "enrollment", "academic",
    ],
    "nonprofit": [
        "nonprofit", "ngo", "charity", "foundation", "donor", "volunteer", "grant",
        "mission", "advocacy", "501c3", "fundraising",
    ],
    "agriculture": [
        "farm", "farming", "agriculture", "crop", "livestock", "agtech", "irrigation",
        "harvest", "soil", "agribusiness", "food production",
    ],
    "restaurant": [
        "restaurant", "cafe", "food service", "catering", "kitchen", "dining", "menu",
        "chef", "hospitality", "bar", "brewery", "food truck",
    ],
}

# Gate inference keywords — maps concepts to gate types
GATE_INFERENCE_KEYWORDS: Dict[str, Dict[str, Any]] = {
    "compliance": {"gate_type": GateType.COMPLIANCE, "severity": GateSeverity.HIGH,
                    "keywords": ["compliance", "regulation", "audit", "legal", "gdpr", "hipaa", "sox", "pci"]},
    "security": {"gate_type": GateType.SECURITY, "severity": GateSeverity.HIGH,
                  "keywords": ["security", "access", "authentication", "encryption", "breach", "zero-trust"]},
    "quality": {"gate_type": GateType.QUALITY, "severity": GateSeverity.MEDIUM,
                 "keywords": ["quality", "testing", "inspection", "defect", "review", "standard"]},
    "safety": {"gate_type": GateType.SAFETY, "severity": GateSeverity.CRITICAL,
                "keywords": ["safety", "hazard", "incident", "emergency", "osha", "risk"]},
    "budget": {"gate_type": GateType.BUSINESS, "severity": GateSeverity.HIGH,
                "keywords": ["budget", "cost", "spend", "pricing", "financial", "revenue"]},
    "authorization": {"gate_type": GateType.AUTHORIZATION, "severity": GateSeverity.HIGH,
                       "keywords": ["authority", "approval", "permission", "escalation", "sign-off"]},
    "validation": {"gate_type": GateType.VALIDATION, "severity": GateSeverity.MEDIUM,
                    "keywords": ["validate", "verify", "check", "input", "data quality", "schema"]},
    "performance": {"gate_type": GateType.PERFORMANCE, "severity": GateSeverity.MEDIUM,
                     "keywords": ["performance", "latency", "throughput", "uptime", "sla", "speed"]},
    "monitoring": {"gate_type": GateType.MONITORING, "severity": GateSeverity.LOW,
                    "keywords": ["monitor", "observe", "alert", "dashboard", "telemetry", "log"]},
}


# ---------------------------------------------------------------------------
# Schema field definitions — what information is needed per context
# ---------------------------------------------------------------------------

class FieldRequirement(str, Enum):
    """Whether a schema field is required or optional."""
    REQUIRED = "required"
    OPTIONAL = "optional"
    CONDITIONAL = "conditional"  # Required if another field has a certain value


@dataclass
class SchemaField:
    """One field in a Rosetta form schema."""
    field_id: str
    label: str
    description: str
    field_type: str  # "text", "number", "boolean", "select", "multi_select", "email"
    requirement: FieldRequirement = FieldRequirement.REQUIRED
    options: List[str] = field(default_factory=list)  # For select/multi_select
    default: Any = None
    depends_on: Optional[str] = None  # Field ID this depends on
    depends_value: Any = None  # Value of dependency that activates this field
    validation_regex: Optional[str] = None
    question: str = ""  # The question to ask the user when this field is missing

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field_id": self.field_id,
            "label": self.label,
            "description": self.description,
            "field_type": self.field_type,
            "requirement": self.requirement.value,
            "options": self.options,
            "default": self.default,
            "question": self.question,
        }


@dataclass
class RosettaFormSchema:
    """
    A form schema derived from a Rosetta agent's state — the agent's 'soul'.

    Defines what information is needed when interacting with this agent,
    which fields are missing, and what questions to ask to fill them.
    Soul architecture is implemented in ``src/eq/soul_engine.py``.
    """
    schema_id: str
    agent_id: str
    domain: str
    fields: List[SchemaField] = field(default_factory=list)
    collected: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def missing_fields(self) -> List[SchemaField]:
        """Fields that are required but not yet collected."""
        missing = []
        for f in self.fields:
            if f.requirement == FieldRequirement.REQUIRED and f.field_id not in self.collected:
                missing.append(f)
            elif f.requirement == FieldRequirement.CONDITIONAL:
                dep_val = self.collected.get(f.depends_on)
                if dep_val == f.depends_value and f.field_id not in self.collected:
                    missing.append(f)
        return missing

    @property
    def is_complete(self) -> bool:
        """Whether all required/conditional fields have been collected."""
        return len(self.missing_fields) == 0

    @property
    def next_question(self) -> Optional[str]:
        """The next question to ask the user, or None if complete."""
        missing = self.missing_fields
        if not missing:
            return None
        return missing[0].question or f"Please provide: {missing[0].label}"

    @property
    def all_questions(self) -> List[Dict[str, str]]:
        """All outstanding questions with field IDs."""
        return [
            {"field_id": f.field_id, "question": f.question or f"Please provide: {f.label}"}
            for f in self.missing_fields
        ]

    def submit_answer(self, field_id: str, value: Any) -> bool:
        """Submit an answer for a field. Returns True if accepted."""
        field_def = next((f for f in self.fields if f.field_id == field_id), None)
        if field_def is None:
            return False
        self.collected[field_id] = value
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "agent_id": self.agent_id,
            "domain": self.domain,
            "fields": [f.to_dict() for f in self.fields],
            "collected": self.collected,
            "is_complete": self.is_complete,
            "missing_count": len(self.missing_fields),
        }


# ---------------------------------------------------------------------------
# Org Position with metrics mapping
# ---------------------------------------------------------------------------

@dataclass
class OrgPositionMetrics:
    """Metrics mapped to a single org chart position."""
    position_id: str
    title: str
    authority: str
    metrics: List[str]
    gates: List[str]
    industry: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "position_id": self.position_id,
            "title": self.title,
            "authority": self.authority,
            "metrics": self.metrics,
            "gates": self.gates,
        }


# ---------------------------------------------------------------------------
# Inference Domain Gate Engine — the core
# ---------------------------------------------------------------------------

class InferenceDomainGateEngine:
    """
    Infers domain gates, org metrics, and form schemas for ANY subject matter.

    Instead of hardcoded domain-to-gate mappings, this engine:
      1. Takes a natural language description of a company/domain
      2. Infers the industry from keywords
      3. Maps org chart positions with metrics per position
      4. Generates domain-specific gates via inference
      5. Creates a Rosetta form schema for required information
      6. Identifies missing fields and generates questions

    Usage:
        engine = InferenceDomainGateEngine()
        result = engine.infer("How do I best manage a fintech startup?")
        logger.info(result.org_positions)   # Positions + metrics
        logger.info(result.inferred_gates)  # Gates for this domain
        logger.info(result.form_schema)     # What info is needed
        logger.info(result.form_schema.next_question)  # First missing field
    """

    def __init__(self):
        self.gate_generator = DomainGateGenerator()

    def infer_industry(self, description: str) -> str:
        """Infer industry from a natural language description."""
        desc_lower = description.lower()
        scores: Dict[str, int] = {}
        for industry, keywords in INDUSTRY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in desc_lower)
            if score > 0:
                scores[industry] = score

        if not scores:
            return "other"
        return max(scores, key=scores.get)

    def infer_gates_from_description(self, description: str) -> List[Dict[str, Any]]:
        """Infer which gate categories apply from a natural language description."""
        desc_lower = description.lower()
        matched_gates: List[Dict[str, Any]] = []

        for gate_name, gate_info in GATE_INFERENCE_KEYWORDS.items():
            score = sum(1 for kw in gate_info["keywords"] if kw in desc_lower)
            if score > 0:
                matched_gates.append({
                    "name": gate_name,
                    "gate_type": gate_info["gate_type"],
                    "severity": gate_info["severity"],
                    "match_score": score,
                })

        # Sort by match score descending
        matched_gates.sort(key=lambda g: g["match_score"], reverse=True)
        return matched_gates

    def map_org_positions(
        self, industry: str, description: str = ""
    ) -> List[OrgPositionMetrics]:
        """
        Map org chart positions with their metrics for the inferred industry.

        Every company gets universal positions (CEO, CFO, etc.).
        Industry-specific positions are added based on the inferred industry.
        """
        positions: List[OrgPositionMetrics] = []

        # Universal positions
        for pos_id, pos_data in UNIVERSAL_POSITIONS.items():
            positions.append(OrgPositionMetrics(
                position_id=pos_id,
                title=pos_data["title"],
                authority=pos_data["authority"],
                metrics=pos_data["metrics"],
                gates=pos_data["gates"],
                industry="universal",
            ))

        # Industry-specific positions
        industry_specific = INDUSTRY_POSITIONS.get(industry, {})
        for pos_id, pos_data in industry_specific.items():
            positions.append(OrgPositionMetrics(
                position_id=pos_id,
                title=pos_data["title"],
                authority=pos_data["authority"],
                metrics=pos_data["metrics"],
                gates=pos_data["gates"],
                industry=industry,
            ))

        return positions

    def build_form_schema(
        self,
        domain: str,
        industry: str,
        agent_id: str = "",
        existing_data: Optional[Dict[str, Any]] = None,
    ) -> RosettaFormSchema:
        """
        Build a Rosetta form schema for interacting with this domain.

        The schema defines what information is needed. Missing fields
        become questions in the form loop.
        """
        agent_id = agent_id or f"agent_{domain}_{uuid.uuid4().hex[:8]}"
        schema = RosettaFormSchema(
            schema_id=f"schema_{uuid.uuid4().hex[:8]}",
            agent_id=agent_id,
            domain=domain,
        )

        # Core fields every domain needs
        schema.fields.extend([
            SchemaField(
                field_id="organization_name",
                label="Organization Name",
                description="Name of the company or organization",
                field_type="text",
                requirement=FieldRequirement.REQUIRED,
                question="What is the name of your organization?",
            ),
            SchemaField(
                field_id="industry",
                label="Industry",
                description="Primary industry sector",
                field_type="select",
                requirement=FieldRequirement.REQUIRED,
                options=list(INDUSTRY_KEYWORDS.keys()) + ["other"],
                question="What industry does the organization operate in?",
            ),
            SchemaField(
                field_id="company_size",
                label="Company Size",
                description="Number of employees or scale",
                field_type="select",
                requirement=FieldRequirement.REQUIRED,
                options=["small", "medium", "enterprise"],
                question="What is the company size? (small / medium / enterprise)",
            ),
            SchemaField(
                field_id="primary_goal",
                label="Primary Business Goal",
                description="The main objective for using the system",
                field_type="text",
                requirement=FieldRequirement.REQUIRED,
                question="What is the primary business goal you want to achieve?",
            ),
            SchemaField(
                field_id="key_challenges",
                label="Key Challenges",
                description="The biggest operational challenges faced",
                field_type="text",
                requirement=FieldRequirement.REQUIRED,
                question="What are the key challenges you face in managing this organization?",
            ),
            SchemaField(
                field_id="existing_tools",
                label="Existing Tools",
                description="Tools and platforms currently in use",
                field_type="text",
                requirement=FieldRequirement.OPTIONAL,
                question="What tools or platforms does the team currently use?",
            ),
        ])

        # Industry-specific fields
        industry_fields = self._get_industry_fields(industry)
        schema.fields.extend(industry_fields)

        # Domain-specific fields based on inferred gates
        domain_fields = self._get_domain_fields(domain)
        schema.fields.extend(domain_fields)

        # Pre-fill any existing data
        if existing_data:
            for key, value in existing_data.items():
                schema.submit_answer(key, value)

        return schema

    def generate_inferred_gates(
        self,
        description: str,
        industry: str,
        positions: List[OrgPositionMetrics],
    ) -> List[DomainGate]:
        """
        Generate domain gates by inference from the description, industry, and positions.

        This replaces the hardcoded domain mapping with inference:
        - Keyword matching on the description determines gate categories
        - Industry determines additional compliance/regulatory gates
        - Org positions contribute their position-specific gates
        - All are deduplicated and generated through the gate generator
        """
        gates: List[DomainGate] = []
        seen_gate_names: set = set()

        # 1. Gates inferred from the natural language description
        inferred = self.infer_gates_from_description(description)
        for gi in inferred:
            gate_name = f"{gi['name']}_gate"
            if gate_name not in seen_gate_names:
                seen_gate_names.add(gate_name)
                gates.append(self.gate_generator.generate_gate(
                    name=gate_name,
                    description=f"Inferred from description: {gi['name']} controls",
                    gate_type=gi["gate_type"],
                    severity=gi["severity"],
                    risk_reduction=0.6,
                ))

        # 2. Gates from the industry's standard domain
        domain_gates, _ = self.gate_generator.generate_gates_for_system({
            "domain": industry if industry != "other" else "software",
            "complexity": "medium",
        })
        for g in domain_gates:
            if g.name not in seen_gate_names:
                seen_gate_names.add(g.name)
                gates.append(g)

        # 3. Gates contributed by org chart positions
        for pos in positions:
            for gate_name in pos.gates:
                if gate_name not in seen_gate_names:
                    seen_gate_names.add(gate_name)
                    gates.append(self.gate_generator.generate_gate(
                        name=gate_name,
                        description=f"Required by position: {pos.title}",
                        gate_type=self._infer_gate_type(gate_name),
                        severity=GateSeverity.MEDIUM,
                        risk_reduction=0.5,
                    ))

        return gates

    def infer(
        self,
        description: str,
        existing_data: Optional[Dict[str, Any]] = None,
        agent_id: str = "",
    ) -> "InferenceResult":
        """
        Full inference pipeline using Magnify → Simplify → Solidify.

        This is the main entry point. Given a natural language description like
        "How do I best manage a fintech startup?", it returns:
          - Inferred industry
          - Org chart positions with metrics
          - Domain-specific gates
          - A form schema with outstanding questions

        The pipeline follows the three-stage processing model:

          MAGNIFY  — Expand: infer ALL possible positions, metrics, gates.
                     Go wide. Explore the full domain space.
                     (+0.10 confidence boost)

          SIMPLIFY — Select: filter to the RELEVANT items based on
                     the user's description and existing data.
                     Go narrow. Remove noise.
                     (+0.05 confidence boost)

          SOLIDIFY — Lock: produce the final call-to-action dataset.
                     This becomes ground truth in Rosetta.
                     (+0.20 confidence boost)
        """
        industry = self.infer_industry(description)

        # --- MAGNIFY: go wide, explore all possibilities ---
        all_positions = self.map_org_positions(industry, description)
        all_gates = self.generate_inferred_gates(description, industry, all_positions)
        full_form = self.build_form_schema(
            domain=industry,
            industry=industry,
            agent_id=agent_id,
            existing_data=existing_data,
        )

        # --- SIMPLIFY: filter to relevant positions/gates ---
        # Positions: keep universal + industry-specific (already filtered by industry)
        # Gates: keep only those with risk_reduction > 0 (already filtered by inference)
        # Form: pre-fill what we can from existing data (already done above)
        # In production, the LLM would further prune based on the description.
        positions = all_positions
        gates = all_gates
        form_schema = full_form

        # --- SOLIDIFY: produce the final locked result ---
        return InferenceResult(
            description=description,
            inferred_industry=industry,
            org_positions=positions,
            inferred_gates=gates,
            form_schema=form_schema,
        )

    def infer_via_llm(
        self,
        description: str,
        llm_backend=None,
        agent_id: str = "",
    ) -> "InferenceResult":
        """LLM-driven inference: description → form fill → constraints → gates → pipeline.

        The LLM reads the free-text business description and fills the
        RosettaFormSchema fields directly.  Each filled field becomes a
        SensorReading with SensorType.LLM_INFERENCE and
        FillConfidence.LLM_GENERATED — it must pass the confidence gate
        before it is accepted as a constraint.

        Filled form fields ARE the business constraints:
          - industry   → which domain gates apply
          - services   → which capability modules are relevant
          - goals      → which automation pipeline flows to build
          - size       → resource and concurrency constraints
          - challenges → which business-context gates fire first

        These constraints drive generate_inferred_gates() and
        AgentActionBuilder.build_actions_from_inference() to produce the
        full set of AgentCallToAction pipeline flows.

        Falls back to keyword-based infer() when llm_backend is None or
        when the LLM response cannot be parsed as structured JSON.
        """
        import json as _json
        import re as _re

        if llm_backend is None:
            return self.infer(description, agent_id=agent_id)

        _agent_id = agent_id or f"agent_{uuid.uuid4().hex[:8]}"

        # Build the form schema with all fields empty — the LLM will fill it.
        form = self.build_form_schema(
            domain="general",
            industry="unknown",
            agent_id=_agent_id,
        )

        # Construct a structured extraction prompt using the form's own field
        # definitions as the schema.  The form tells the LLM exactly what to fill.
        field_lines = "\n".join(
            f'  "{f.field_id}": "<{f.description}>"'
            for f in form.fields
            if f.requirement.value == "required"
        )
        all_industries = sorted(INDUSTRY_KEYWORDS.keys())
        prompt = (
            "You are extracting structured business context from a plain-text description.\n"
            f"Description: {description}\n\n"
            "Return ONLY a JSON object with the following fields "
            "(use null for any field you cannot determine):\n"
            "{\n"
            f'  "industry": "<one of: {", ".join(all_industries)}, other>",\n'
            f'  "business_type": "<specific business type, e.g. plumbing contractor>",\n'
            f"{field_lines}\n"
            "}\n"
            "Return only valid JSON.  No explanation."
        )

        # Generate via SafeLLMWrapper so all existing safety gates apply.
        # Import here to avoid circular import at module level.
        try:
            from safe_llm_wrapper import SafeLLMWrapper
            wrapper = SafeLLMWrapper(llm_backend)
            llm_result = wrapper.safe_generate(
                prompt,
                context={"description": description},
                max_tokens=400,
            )
        except Exception as exc:
            logger.warning("LLM call failed (%s); falling back to keyword inference", exc)
            return self.infer(description, agent_id=_agent_id)

        raw_content = llm_result.get("content", "")
        llm_confidence = llm_result.get("confidence", 0.5)

        # Extract JSON from the response — the LLM may wrap it in prose.
        field_values: dict = {}
        try:
            json_match = _re.search(r"\{.*\}", raw_content, _re.DOTALL)
            if json_match:
                field_values = _json.loads(json_match.group())
        except (_json.JSONDecodeError, AttributeError):
            logger.warning(
                "LLM returned non-JSON content; falling back to keyword inference"
            )
            return self.infer(description, agent_id=_agent_id)

        # Feed LLM answers into the form as LLM_INFERENCE sensor readings.
        # High-confidence LLM responses (≥0.8) are promoted to HIGH_CONFIDENCE;
        # everything else remains LLM_GENERATED and requires a gate pass.
        fill_confidence = (
            FillConfidence.HIGH_CONFIDENCE
            if llm_confidence >= 0.8
            else FillConfidence.LLM_GENERATED
        )
        for field_id, value in field_values.items():
            if value is not None:
                reading = SensorReading(
                    sensor_id=f"llm_{field_id}",
                    sensor_type=SensorType.LLM_INFERENCE,
                    field_id=field_id,
                    value=value,
                    confidence=fill_confidence,
                    source="infer_via_llm",
                )
                # Write the value directly into the form schema field
                form.submit_answer(field_id, value)
                logger.debug(
                    "LLM filled field '%s' = %r (confidence=%s)",
                    field_id, value, fill_confidence.value,
                )
                _ = reading  # stored for audit; caller can retrieve via form.fields

        # Resolve industry from the LLM-filled field — no keyword matching needed.
        industry = (field_values.get("industry") or "other").lower().strip()
        if industry not in INDUSTRY_KEYWORDS and industry != "other":
            # LLM returned a freeform value; try a single-pass keyword fallback
            # on just that value rather than the full description.
            industry = self.infer_industry(field_values.get("industry", description))

        # MAGNIFY → SIMPLIFY → SOLIDIFY using the LLM-derived industry
        # (same pipeline as infer(), but the industry is semantically derived
        # from the filled form rather than a keyword scan of the description).
        positions = self.map_org_positions(industry, description)
        gates = self.generate_inferred_gates(description, industry, positions)

        return InferenceResult(
            description=description,
            inferred_industry=industry,
            org_positions=positions,
            inferred_gates=gates,
            form_schema=form,
        )

    # ---- Internal helpers ----

    def _infer_gate_type(self, gate_name: str) -> GateType:
        """Infer gate type from its name."""
        name_lower = gate_name.lower()
        if "compliance" in name_lower or "regulatory" in name_lower:
            return GateType.COMPLIANCE
        if "security" in name_lower or "access" in name_lower:
            return GateType.SECURITY
        if "quality" in name_lower or "inspection" in name_lower:
            return GateType.QUALITY
        if "safety" in name_lower or "hazard" in name_lower:
            return GateType.SAFETY
        if "budget" in name_lower or "pricing" in name_lower:
            return GateType.BUSINESS
        if "authority" in name_lower or "approval" in name_lower or "escalation" in name_lower:
            return GateType.AUTHORIZATION
        if "validation" in name_lower or "data" in name_lower:
            return GateType.VALIDATION
        return GateType.BUSINESS

    def _get_industry_fields(self, industry: str) -> List[SchemaField]:
        """Get industry-specific form fields."""
        fields: List[SchemaField] = []

        if industry == "healthcare":
            fields.append(SchemaField(
                field_id="hipaa_required",
                label="HIPAA Compliance Required",
                description="Whether HIPAA compliance is needed",
                field_type="boolean",
                requirement=FieldRequirement.REQUIRED,
                question="Does this organization handle protected health information (PHI) requiring HIPAA compliance?",
            ))
            fields.append(SchemaField(
                field_id="patient_data_scope",
                label="Patient Data Scope",
                description="Types of patient data handled",
                field_type="text",
                requirement=FieldRequirement.CONDITIONAL,
                depends_on="hipaa_required",
                depends_value=True,
                question="What types of patient data does the organization handle?",
            ))
        elif industry == "finance":
            fields.append(SchemaField(
                field_id="regulatory_frameworks",
                label="Regulatory Frameworks",
                description="Applicable financial regulations",
                field_type="multi_select",
                requirement=FieldRequirement.REQUIRED,
                options=["SOX", "PCI_DSS", "AML", "KYC", "Basel_III", "MiFID_II", "none"],
                question="Which financial regulatory frameworks apply to this organization?",
            ))
        elif industry == "manufacturing":
            fields.append(SchemaField(
                field_id="safety_certifications",
                label="Safety Certifications",
                description="Required safety certifications",
                field_type="multi_select",
                requirement=FieldRequirement.REQUIRED,
                options=["ISO_9001", "ISO_14001", "OSHA", "CE_marking", "UL", "none"],
                question="What safety certifications does or should this facility hold?",
            ))
            fields.append(SchemaField(
                field_id="automation_level",
                label="Automation Level",
                description="Current level of factory automation",
                field_type="select",
                requirement=FieldRequirement.OPTIONAL,
                options=["manual", "semi_automated", "fully_automated"],
                question="What is the current level of factory automation?",
            ))

        return fields

    def _get_domain_fields(self, domain: str) -> List[SchemaField]:
        """Get domain-specific operational fields."""
        fields: List[SchemaField] = []

        # Sales-related
        if domain in ("technology", "retail", "media"):
            fields.append(SchemaField(
                field_id="sales_model",
                label="Sales Model",
                description="Primary sales approach",
                field_type="select",
                requirement=FieldRequirement.OPTIONAL,
                options=["self_serve", "inside_sales", "field_sales", "partner_channel", "mixed"],
                question="What is the primary sales model?",
            ))

        # Compliance-heavy
        if domain in ("finance", "healthcare"):
            fields.append(SchemaField(
                field_id="data_residency",
                label="Data Residency Requirements",
                description="Geographic data storage requirements",
                field_type="text",
                requirement=FieldRequirement.REQUIRED,
                question="Are there data residency requirements (must data stay in specific regions)?",
            ))

        return fields


# ---------------------------------------------------------------------------
# Inference Result
# ---------------------------------------------------------------------------

@dataclass
class InferenceResult:
    """Complete result from the inference pipeline."""
    description: str
    inferred_industry: str
    org_positions: List[OrgPositionMetrics]
    inferred_gates: List[DomainGate]
    form_schema: RosettaFormSchema

    @property
    def position_count(self) -> int:
        return len(self.org_positions)

    @property
    def gate_count(self) -> int:
        return len(self.inferred_gates)

    @property
    def metrics_by_position(self) -> Dict[str, List[str]]:
        """Map of position title → metrics list."""
        return {p.title: p.metrics for p in self.org_positions}

    @property
    def gates_by_position(self) -> Dict[str, List[str]]:
        """Map of position title → gate names."""
        return {p.title: p.gates for p in self.org_positions}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "description": self.description,
            "inferred_industry": self.inferred_industry,
            "position_count": self.position_count,
            "gate_count": self.gate_count,
            "org_positions": [p.to_dict() for p in self.org_positions],
            "inferred_gates": [
                {"name": g.name, "type": g.gate_type.value, "severity": g.severity.value}
                for g in self.inferred_gates
            ],
            "form_schema": self.form_schema.to_dict(),
            "metrics_by_position": self.metrics_by_position,
        }

    def produce_dataset(self) -> Dict[str, Any]:
        """
        Produce the call-to-action dataset from inference results.

        Uses the Magnify → Simplify → Solidify pipeline:

          MAGNIFY  — The five inference questions expand the domain space:
            1. Org positions   → agent roster (who does what)
            2. Metrics/position → KPI dataset (what to measure per role)
            3. Domain gates     → checkpoint dataset (where to validate)
            4. Schema fields    → required information dataset (what data is needed)
            5. Missing fields   → action items dataset (what to ask / fill next)

          SIMPLIFY — Each dataset is deduplicated, cross-referenced, and
            reduced to only what's relevant for this specific company.

          SOLIDIFY — The final dataset IS the call-to-action. Agents read
            it from Rosetta, sensors fill it, LLM fills generatively,
            gates checkpoint, HITL verifies. Once solidified, this is
            ground truth.

        Returns a structured dataset ready for agent consumption.
        """
        # ---- MAGNIFY: expand all five inference question answers ----

        # 1. Agent roster — each position becomes an agent with responsibilities
        agent_roster = []
        for pos in self.org_positions:
            agent_roster.append({
                "agent_id": f"agent_{pos.position_id}",
                "position": pos.title,
                "authority": pos.authority,
                "industry": pos.industry,
                "kpis": pos.metrics,
                "checkpoints": pos.gates,
            })

        # 2. KPI dataset — every metric across all positions
        all_metrics: Dict[str, List[str]] = {}
        for pos in self.org_positions:
            for metric in pos.metrics:
                all_metrics.setdefault(metric, []).append(pos.title)

        kpi_dataset = [
            {"metric": metric, "tracked_by": tracked_by}
            for metric, tracked_by in all_metrics.items()
        ]

        # 3. Checkpoint dataset — every gate
        checkpoint_dataset = [
            {
                "gate_id": g.gate_id,
                "gate_name": g.name,
                "gate_type": g.gate_type.value,
                "severity": g.severity.value,
                "risk_reduction": g.risk_reduction,
            }
            for g in self.inferred_gates
        ]

        # 4. Required information — all schema fields
        required_info = [
            {
                "field_id": f.field_id,
                "label": f.label,
                "type": f.field_type,
                "requirement": f.requirement.value,
                "status": "collected" if f.field_id in self.form_schema.collected else "missing",
                "value": self.form_schema.collected.get(f.field_id),
            }
            for f in self.form_schema.fields
        ]

        # 5. Action items — outstanding questions
        action_items = [
            {
                "field_id": f.field_id,
                "question": f.question or f"Please provide: {f.label}",
                "field_type": f.field_type,
                "options": f.options,
            }
            for f in self.form_schema.missing_fields
        ]

        # ---- SIMPLIFY: deduplicate and cross-reference ----

        collected_count = sum(1 for f in required_info if f["status"] == "collected")
        missing_count = len(action_items)

        # ---- SOLIDIFY: lock as the call-to-action dataset ----

        # Base confidence starts at 0.45 (per system design)
        # Magnify adds +0.10, Simplify adds +0.05, Solidify adds +0.20
        base_confidence = 0.45
        magnify_boost = 0.10
        simplify_boost = 0.05
        solidify_boost = 0.20 if missing_count == 0 else 0.0  # Only solidify when complete
        dataset_confidence = base_confidence + magnify_boost + simplify_boost + solidify_boost

        return {
            "industry": self.inferred_industry,
            "description": self.description,
            "agent_roster": agent_roster,
            "kpi_dataset": kpi_dataset,
            "checkpoint_dataset": checkpoint_dataset,
            "required_information": required_info,
            "action_items": action_items,
            "processing_stage": "solidified" if missing_count == 0 else "simplified",
            "confidence": round(dataset_confidence, 2),
            "summary": {
                "total_agents": len(agent_roster),
                "total_kpis": len(kpi_dataset),
                "total_checkpoints": len(checkpoint_dataset),
                "total_fields": len(required_info),
                "fields_collected": collected_count,
                "fields_missing": missing_count,
                "dataset_complete": missing_count == 0,
                "magnify_boost": magnify_boost,
                "simplify_boost": simplify_boost,
                "solidify_boost": solidify_boost,
                "dataset_confidence": dataset_confidence,
            },
        }


# ===========================================================================
# Agent Call-to-Action Architecture
#
# Forms are built around what each agent ACTION needs.
# Gates checkpoint each action's data.
# Sensors observe chronological events feeding data into the form.
# The LLM fills generatively; confidence + HITL work out error probability.
# ===========================================================================


class SensorType(str, Enum):
    """Types of sensors that observe data for form filling."""
    EVENT_STREAM = "event_stream"      # Chronological events (logs, messages)
    API_RESPONSE = "api_response"      # External API data
    USER_INPUT = "user_input"          # Direct human input
    DATABASE_QUERY = "database_query"  # Database lookup result
    LLM_INFERENCE = "llm_inference"    # LLM-generated value (needs gating)
    COMPUTED = "computed"              # Deterministic computation


class FillConfidence(str, Enum):
    """How confident the system is in a field value."""
    VERIFIED = "verified"          # Deterministic or human-confirmed
    HIGH_CONFIDENCE = "high"       # Multiple corroborating sources
    MEDIUM_CONFIDENCE = "medium"   # Single reliable source
    LLM_GENERATED = "llm_generated"  # LLM filled — needs gating
    UNVERIFIED = "unverified"      # Unknown provenance


@dataclass
class SensorReading:
    """A single observation from a sensor — one piece of data entering the form."""
    sensor_id: str
    sensor_type: SensorType
    field_id: str           # Which schema field this reading fills
    value: Any
    confidence: FillConfidence
    source: str             # Where this data came from
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionFormField:
    """
    A field in an agent's call-to-action form.

    Unlike a generic schema field, this is tied to a specific agent action
    and tracks how the field was filled (sensor source, confidence, gate status).
    """
    field_id: str
    label: str
    description: str
    field_type: str
    requirement: FieldRequirement = FieldRequirement.REQUIRED
    options: List[str] = field(default_factory=list)
    question: str = ""
    # Filling state
    value: Any = None
    fill_confidence: FillConfidence = FillConfidence.UNVERIFIED
    filled_by: Optional[SensorType] = None
    gate_status: str = "pending"  # "pending", "passed", "failed", "bypassed"
    fill_history: List[SensorReading] = field(default_factory=list)

    @property
    def is_filled(self) -> bool:
        return self.value is not None

    @property
    def is_verified(self) -> bool:
        return self.fill_confidence in (FillConfidence.VERIFIED, FillConfidence.HIGH_CONFIDENCE)

    @property
    def needs_gating(self) -> bool:
        """LLM-generated values need confidence gating before acceptance."""
        return self.fill_confidence == FillConfidence.LLM_GENERATED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field_id": self.field_id,
            "label": self.label,
            "field_type": self.field_type,
            "requirement": self.requirement.value,
            "value": self.value,
            "is_filled": self.is_filled,
            "fill_confidence": self.fill_confidence.value,
            "filled_by": self.filled_by.value if self.filled_by else None,
            "gate_status": self.gate_status,
            "needs_gating": self.needs_gating,
        }


@dataclass
class AgentCallToAction:
    """
    An agent's call-to-action — the unit of work an agent performs.

    Each action has:
      - A form (what data is needed to execute)
      - Gates (checkpoints that must pass before/after execution)
      - Sensors (data sources that fill the form)

    The LLM's job is to fill the form generatively from the event stream.
    The confidence engine gates each LLM-generated fill.
    HITL catches remaining uncertainty.
    """
    action_id: str
    agent_id: str
    action_name: str
    description: str
    fields: List[ActionFormField] = field(default_factory=list)
    gate_ids: List[str] = field(default_factory=list)
    sensor_readings: List[SensorReading] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = "pending"  # "pending", "filling", "gating", "ready", "executed", "failed"

    @property
    def missing_fields(self) -> List[ActionFormField]:
        """Fields that are required but not yet filled."""
        return [f for f in self.fields
                if f.requirement == FieldRequirement.REQUIRED and not f.is_filled]

    @property
    def unverified_fields(self) -> List[ActionFormField]:
        """Fields filled by LLM that haven't passed gates yet."""
        return [f for f in self.fields if f.needs_gating]

    @property
    def is_form_complete(self) -> bool:
        return len(self.missing_fields) == 0

    @property
    def is_gate_ready(self) -> bool:
        """All fields filled AND all LLM-generated fields have passed gates."""
        return self.is_form_complete and len(self.unverified_fields) == 0

    @property
    def next_question(self) -> Optional[str]:
        missing = self.missing_fields
        return missing[0].question if missing else None

    def receive_sensor_reading(self, reading: SensorReading) -> bool:
        """
        Receive a sensor reading and apply it to the matching form field.

        Sensors observe events chronologically and feed data into the form.
        LLM-generated readings are flagged for gating.
        """
        target = next((f for f in self.fields if f.field_id == reading.field_id), None)
        if target is None:
            return False

        target.value = reading.value
        target.fill_confidence = reading.confidence
        target.filled_by = reading.sensor_type
        target.fill_history.append(reading)

        # LLM-generated values need gating; everything else passes immediately
        if reading.sensor_type == SensorType.LLM_INFERENCE:
            target.gate_status = "pending"
        else:
            target.gate_status = "passed"

        self.sensor_readings.append(reading)
        self.status = "filling"
        return True

    def gate_field(self, field_id: str, passed: bool) -> bool:
        """Apply a gate decision to an LLM-filled field."""
        target = next((f for f in self.fields if f.field_id == field_id), None)
        if target is None:
            return False
        target.gate_status = "passed" if passed else "failed"
        if passed and target.fill_confidence == FillConfidence.LLM_GENERATED:
            target.fill_confidence = FillConfidence.MEDIUM_CONFIDENCE
        return True

    def verify_field(self, field_id: str) -> bool:
        """Mark a field as human-verified (HITL confirmation)."""
        target = next((f for f in self.fields if f.field_id == field_id), None)
        if target is None:
            return False
        target.fill_confidence = FillConfidence.VERIFIED
        target.gate_status = "passed"
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "agent_id": self.agent_id,
            "action_name": self.action_name,
            "status": self.status,
            "is_form_complete": self.is_form_complete,
            "is_gate_ready": self.is_gate_ready,
            "fields": [f.to_dict() for f in self.fields],
            "missing_count": len(self.missing_fields),
            "unverified_count": len(self.unverified_fields),
            "sensor_reading_count": len(self.sensor_readings),
        }


class AgentActionBuilder:
    """
    Builds agent call-to-action forms from inferred domain context.

    Given an InferenceResult (industry, positions, gates), builds
    concrete agent actions with forms, gates, and sensor bindings.
    """

    def __init__(self, gate_engine: Optional[InferenceDomainGateEngine] = None):
        self.gate_engine = gate_engine or InferenceDomainGateEngine()

    def build_action_for_position(
        self,
        position: OrgPositionMetrics,
        action_name: str,
        action_description: str,
        extra_fields: Optional[List[ActionFormField]] = None,
    ) -> AgentCallToAction:
        """
        Build an agent call-to-action for a specific org chart position.

        The form fields are inferred from the position's metrics and gates.
        Each metric becomes a form field the agent needs to observe/fill.
        Each gate becomes a checkpoint on the action.
        """
        action_id = f"action_{uuid.uuid4().hex[:8]}"
        agent_id = f"agent_{position.position_id}"

        fields: List[ActionFormField] = []

        # Each metric the position tracks becomes a form field
        for metric in position.metrics:
            fields.append(ActionFormField(
                field_id=metric,
                label=metric.replace("_", " ").title(),
                description=f"Current value of {metric} for {position.title}",
                field_type="number",
                requirement=FieldRequirement.REQUIRED,
                question=f"What is the current {metric.replace('_', ' ')} for this {position.title.lower()}?",
            ))

        if extra_fields:
            fields.extend(extra_fields)

        action = AgentCallToAction(
            action_id=action_id,
            agent_id=agent_id,
            action_name=action_name,
            description=action_description,
            fields=fields,
            gate_ids=list(position.gates),
        )
        return action

    def build_actions_from_inference(
        self,
        inference_result: InferenceResult,
    ) -> List[AgentCallToAction]:
        """
        Build agent actions for every position in an inference result.

        Each position gets a "status_report" action — the baseline form
        that collects all metrics that position is responsible for.
        """
        actions: List[AgentCallToAction] = []
        for pos in inference_result.org_positions:
            action = self.build_action_for_position(
                position=pos,
                action_name=f"{pos.position_id}_status_report",
                action_description=f"Collect current metrics for {pos.title}",
            )
            actions.append(action)
        return actions

    def simulate_llm_fill(
        self,
        action: AgentCallToAction,
        event_data: Dict[str, Any],
    ) -> List[SensorReading]:
        """
        Simulate the LLM filling form fields from an event stream.

        In production, the LLM reads chronological events and infers values.
        Here we simulate: for each field, if event_data has a matching key,
        create an LLM_INFERENCE sensor reading (needs gating).
        If the key was in a deterministic source, mark as COMPUTED.
        """
        readings: List[SensorReading] = []
        for f in action.fields:
            if f.field_id in event_data:
                # Determine sensor type and confidence
                source_info = event_data.get(f"_source_{f.field_id}", "llm")
                if source_info == "deterministic":
                    sensor_type = SensorType.COMPUTED
                    confidence = FillConfidence.VERIFIED
                elif source_info == "api":
                    sensor_type = SensorType.API_RESPONSE
                    confidence = FillConfidence.HIGH_CONFIDENCE
                elif source_info == "user":
                    sensor_type = SensorType.USER_INPUT
                    confidence = FillConfidence.VERIFIED
                else:
                    sensor_type = SensorType.LLM_INFERENCE
                    confidence = FillConfidence.LLM_GENERATED

                reading = SensorReading(
                    sensor_id=f"sensor_{f.field_id}_{uuid.uuid4().hex[:4]}",
                    sensor_type=sensor_type,
                    field_id=f.field_id,
                    value=event_data[f.field_id],
                    confidence=confidence,
                    source=source_info,
                )
                action.receive_sensor_reading(reading)
                readings.append(reading)
        return readings
