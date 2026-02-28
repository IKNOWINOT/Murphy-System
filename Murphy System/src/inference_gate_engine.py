"""
Inference-Based Domain Gate Engine with Rosetta Form Schemas

This module implements the "multi-Rosetta soul" pattern — similar to OpenClaw.ai's
Molty soul.md, but each agent's soul is their Rosetta state document which drives:

  1. What information the agent needs (form schema)
  2. What gates apply to their domain (inferred, not hardcoded)
  3. What metrics matter per org chart position
  4. What questions to ask when schema fields are missing

The core idea: when someone asks "how do I best manage an [X] type of company?",
the system infers:
  - Which org chart positions exist for that company type
  - What metrics matter per position
  - What domain gates should apply
  - What information is required (schema)
  - What's missing from the schema (form questions)

Gates are inferred from subject matter, not hardcoded per domain.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: Apache License 2.0
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .domain_gate_generator import DomainGate, DomainGateGenerator, GateSeverity, GateType


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
    "technology": ["tech", "software", "saas", "cloud", "ai", "startup", "app", "platform", "api", "devops"],
    "manufacturing": ["factory", "manufacturing", "production", "assembly", "industrial", "plant", "supply chain"],
    "finance": ["bank", "financial", "fintech", "insurance", "investment", "trading", "lending", "payments"],
    "healthcare": ["hospital", "clinic", "health", "medical", "pharma", "biotech", "patient", "clinical"],
    "retail": ["store", "ecommerce", "shop", "retail", "marketplace", "consumer", "brand", "merchandise"],
    "energy": ["energy", "utility", "power", "grid", "solar", "wind", "oil", "gas", "renewable"],
    "media": ["media", "content", "publishing", "news", "entertainment", "streaming", "social", "creative"],
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
    Like OpenClaw.ai's Molty soul.md, but driven by Rosetta state documents.
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
        print(result.org_positions)   # Positions + metrics
        print(result.inferred_gates)  # Gates for this domain
        print(result.form_schema)     # What info is needed
        print(result.form_schema.next_question)  # First missing field
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
        Full inference pipeline: description → industry → positions → gates → form.

        This is the main entry point. Given a natural language description like
        "How do I best manage a fintech startup?", it returns:
          - Inferred industry
          - Org chart positions with metrics
          - Domain-specific gates
          - A form schema with outstanding questions
        """
        industry = self.infer_industry(description)
        positions = self.map_org_positions(industry, description)
        gates = self.generate_inferred_gates(description, industry, positions)
        form_schema = self.build_form_schema(
            domain=industry,
            industry=industry,
            agent_id=agent_id,
            existing_data=existing_data,
        )

        return InferenceResult(
            description=description,
            inferred_industry=industry,
            org_positions=positions,
            inferred_gates=gates,
            form_schema=form_schema,
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
