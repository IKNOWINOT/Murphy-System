"""
Automation Type Registry — Registry of all automation types the Murphy System
can perform, with templates, capability declarations, and platform mappings.

Covers IT automation, business process automation, data pipeline automation,
marketing automation, customer service automation, HR/onboarding automation,
financial automation, content generation, security automation, DevOps automation,
and supply chain automation.
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class AutomationCategory(Enum):
    """Automation category (Enum subclass)."""
    IT_OPERATIONS = "it_operations"
    BUSINESS_PROCESS = "business_process"
    DATA_PIPELINE = "data_pipeline"
    MARKETING = "marketing"
    CUSTOMER_SERVICE = "customer_service"
    HR_ONBOARDING = "hr_onboarding"
    FINANCIAL = "financial"
    CONTENT_GENERATION = "content_generation"
    SECURITY = "security"
    DEVOPS = "devops"
    SUPPLY_CHAIN = "supply_chain"
    COMPLIANCE = "compliance"
    CUSTOM = "custom"


class ComplexityLevel(Enum):
    """Complexity level (Enum subclass)."""
    SIMPLE = "simple"  # single step, no approvals
    MODERATE = "moderate"  # multi-step, may need approval
    COMPLEX = "complex"  # multi-step, cross-system, requires approvals
    CRITICAL = "critical"  # high-risk, requires HITL + compliance


@dataclass
class AutomationTemplate:
    """Automation template."""
    template_id: str
    name: str
    category: AutomationCategory
    description: str
    complexity: ComplexityLevel
    required_connectors: List[str] = field(default_factory=list)
    steps: List[Dict[str, Any]] = field(default_factory=list)
    required_permissions: List[str] = field(default_factory=list)
    compliance_frameworks: List[str] = field(default_factory=list)
    estimated_duration_minutes: int = 5
    requires_hitl: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AutomationCapability:
    """Automation capability."""
    capability_id: str
    name: str
    category: AutomationCategory
    description: str
    supported_platforms: List[str] = field(default_factory=list)
    templates: List[str] = field(default_factory=list)  # template IDs
    enabled: bool = True


# Default automation templates
DEFAULT_TEMPLATES = [
    # IT Operations
    AutomationTemplate(
        template_id="it_incident_response",
        name="IT Incident Response",
        category=AutomationCategory.IT_OPERATIONS,
        description="Automated incident detection, triage, notification, and resolution tracking",
        complexity=ComplexityLevel.COMPLEX,
        required_connectors=["servicenow", "slack"],
        steps=[
            {"step": "detect", "action": "monitor_alerts"},
            {"step": "triage", "action": "classify_severity"},
            {"step": "notify", "action": "send_notification"},
            {"step": "assign", "action": "route_to_team"},
            {"step": "resolve", "action": "apply_runbook"},
            {"step": "close", "action": "update_ticket"},
        ],
        requires_hitl=True,
    ),
    AutomationTemplate(
        template_id="it_provisioning",
        name="Infrastructure Provisioning",
        category=AutomationCategory.IT_OPERATIONS,
        description="Automated server/service provisioning with compliance checks",
        complexity=ComplexityLevel.COMPLEX,
        required_connectors=["aws", "azure", "gcp"],
        steps=[
            {"step": "request", "action": "validate_request"},
            {"step": "approve", "action": "gate_approval"},
            {"step": "provision", "action": "create_resources"},
            {"step": "configure", "action": "apply_config"},
            {"step": "verify", "action": "run_health_checks"},
        ],
        requires_hitl=True,
        compliance_frameworks=["SOC2"],
    ),
    AutomationTemplate(
        template_id="it_patch_management",
        name="Patch Management",
        category=AutomationCategory.IT_OPERATIONS,
        description="Automated patch assessment, testing, and deployment",
        complexity=ComplexityLevel.CRITICAL,
        required_connectors=["servicenow", "github"],
        steps=[
            {"step": "assess", "action": "scan_vulnerabilities"},
            {"step": "test", "action": "deploy_staging"},
            {"step": "approve", "action": "gate_approval"},
            {"step": "deploy", "action": "deploy_production"},
            {"step": "verify", "action": "run_smoke_tests"},
        ],
        requires_hitl=True,
    ),
    # Business Process
    AutomationTemplate(
        template_id="bp_document_approval",
        name="Document Approval Workflow",
        category=AutomationCategory.BUSINESS_PROCESS,
        description="Multi-stage document review and approval with audit trail",
        complexity=ComplexityLevel.MODERATE,
        required_connectors=["confluence", "slack"],
        steps=[
            {"step": "submit", "action": "create_document"},
            {"step": "review", "action": "assign_reviewers"},
            {"step": "approve", "action": "gate_approval"},
            {"step": "publish", "action": "publish_document"},
            {"step": "notify", "action": "send_notification"},
        ],
    ),
    AutomationTemplate(
        template_id="bp_onboarding",
        name="Employee Onboarding",
        category=AutomationCategory.HR_ONBOARDING,
        description="End-to-end new employee onboarding automation",
        complexity=ComplexityLevel.COMPLEX,
        required_connectors=["slack", "google_workspace", "jira"],
        steps=[
            {"step": "create_accounts", "action": "provision_accounts"},
            {"step": "assign_equipment", "action": "create_ticket"},
            {"step": "setup_channels", "action": "add_to_channels"},
            {"step": "schedule_training", "action": "create_events"},
            {"step": "assign_mentor", "action": "notify_mentor"},
        ],
        requires_hitl=True,
    ),
    # Data Pipeline
    AutomationTemplate(
        template_id="dp_etl_pipeline",
        name="ETL Data Pipeline",
        category=AutomationCategory.DATA_PIPELINE,
        description="Extract, transform, and load data between systems",
        complexity=ComplexityLevel.MODERATE,
        required_connectors=["snowflake"],
        steps=[
            {"step": "extract", "action": "read_source"},
            {"step": "validate", "action": "check_schema"},
            {"step": "transform", "action": "apply_transforms"},
            {"step": "load", "action": "write_destination"},
            {"step": "verify", "action": "run_quality_checks"},
        ],
    ),
    AutomationTemplate(
        template_id="dp_report_generation",
        name="Automated Report Generation",
        category=AutomationCategory.DATA_PIPELINE,
        description="Scheduled report generation from multiple data sources",
        complexity=ComplexityLevel.SIMPLE,
        required_connectors=["snowflake", "google_workspace"],
        steps=[
            {"step": "query", "action": "run_queries"},
            {"step": "format", "action": "generate_report"},
            {"step": "distribute", "action": "send_email"},
        ],
    ),
    # Marketing
    AutomationTemplate(
        template_id="mktg_campaign_launch",
        name="Marketing Campaign Launch",
        category=AutomationCategory.MARKETING,
        description="Multi-channel marketing campaign orchestration",
        complexity=ComplexityLevel.COMPLEX,
        required_connectors=["hubspot", "slack", "google_workspace"],
        steps=[
            {"step": "plan", "action": "create_campaign"},
            {"step": "content", "action": "generate_content"},
            {"step": "review", "action": "gate_approval"},
            {"step": "schedule", "action": "schedule_posts"},
            {"step": "launch", "action": "activate_campaign"},
            {"step": "monitor", "action": "track_metrics"},
        ],
    ),
    AutomationTemplate(
        template_id="mktg_lead_nurture",
        name="Lead Nurture Sequence",
        category=AutomationCategory.MARKETING,
        description="Automated lead scoring and email nurture sequences",
        complexity=ComplexityLevel.MODERATE,
        required_connectors=["hubspot", "salesforce"],
        steps=[
            {"step": "score", "action": "evaluate_lead"},
            {"step": "segment", "action": "assign_segment"},
            {"step": "nurture", "action": "send_sequence"},
            {"step": "qualify", "action": "check_engagement"},
            {"step": "handoff", "action": "notify_sales"},
        ],
    ),
    # Customer Service
    AutomationTemplate(
        template_id="cs_ticket_routing",
        name="Customer Ticket Routing",
        category=AutomationCategory.CUSTOMER_SERVICE,
        description="Intelligent ticket classification and routing",
        complexity=ComplexityLevel.MODERATE,
        required_connectors=["hubspot", "slack"],
        steps=[
            {"step": "classify", "action": "analyze_ticket"},
            {"step": "route", "action": "assign_agent"},
            {"step": "escalate", "action": "check_sla"},
            {"step": "resolve", "action": "apply_solution"},
            {"step": "follow_up", "action": "send_survey"},
        ],
    ),
    # Financial
    AutomationTemplate(
        template_id="fin_invoice_processing",
        name="Invoice Processing",
        category=AutomationCategory.FINANCIAL,
        description="Automated invoice receipt, validation, and payment processing",
        complexity=ComplexityLevel.COMPLEX,
        required_connectors=["stripe"],
        steps=[
            {"step": "receive", "action": "capture_invoice"},
            {"step": "validate", "action": "verify_details"},
            {"step": "approve", "action": "gate_approval"},
            {"step": "process", "action": "initiate_payment"},
            {"step": "reconcile", "action": "update_ledger"},
        ],
        requires_hitl=True,
        compliance_frameworks=["SOC2", "PCI-DSS"],
    ),
    # Content Generation
    AutomationTemplate(
        template_id="content_blog_pipeline",
        name="Blog Content Pipeline",
        category=AutomationCategory.CONTENT_GENERATION,
        description="End-to-end blog content creation, review, and publication",
        complexity=ComplexityLevel.MODERATE,
        required_connectors=["notion", "confluence"],
        steps=[
            {"step": "research", "action": "gather_topics"},
            {"step": "outline", "action": "create_outline"},
            {"step": "draft", "action": "generate_content"},
            {"step": "review", "action": "gate_approval"},
            {"step": "publish", "action": "publish_post"},
            {"step": "promote", "action": "schedule_social"},
        ],
    ),
    # Security
    AutomationTemplate(
        template_id="sec_vulnerability_scan",
        name="Vulnerability Scanning",
        category=AutomationCategory.SECURITY,
        description="Automated vulnerability scanning and remediation tracking",
        complexity=ComplexityLevel.CRITICAL,
        required_connectors=["github", "jira"],
        steps=[
            {"step": "scan", "action": "run_scanner"},
            {"step": "analyze", "action": "classify_findings"},
            {"step": "prioritize", "action": "rank_severity"},
            {"step": "remediate", "action": "create_tickets"},
            {"step": "verify", "action": "rescan_targets"},
        ],
        requires_hitl=True,
        compliance_frameworks=["SOC2", "HIPAA"],
    ),
    # DevOps
    AutomationTemplate(
        template_id="devops_ci_cd",
        name="CI/CD Pipeline",
        category=AutomationCategory.DEVOPS,
        description="Continuous integration and deployment automation",
        complexity=ComplexityLevel.COMPLEX,
        required_connectors=["github", "aws"],
        steps=[
            {"step": "build", "action": "compile_code"},
            {"step": "test", "action": "run_tests"},
            {"step": "scan", "action": "security_scan"},
            {"step": "stage", "action": "deploy_staging"},
            {"step": "approve", "action": "gate_approval"},
            {"step": "deploy", "action": "deploy_production"},
            {"step": "monitor", "action": "check_health"},
        ],
        requires_hitl=True,
    ),
    AutomationTemplate(
        template_id="devops_release_management",
        name="Release Management",
        category=AutomationCategory.DEVOPS,
        description="Automated release notes, tagging, and deployment coordination",
        complexity=ComplexityLevel.MODERATE,
        required_connectors=["github", "slack", "jira"],
        steps=[
            {"step": "prepare", "action": "collect_changes"},
            {"step": "notes", "action": "generate_release_notes"},
            {"step": "tag", "action": "create_release"},
            {"step": "notify", "action": "announce_release"},
        ],
    ),
    # Compliance
    AutomationTemplate(
        template_id="compliance_audit",
        name="Compliance Audit Automation",
        category=AutomationCategory.COMPLIANCE,
        description="Automated compliance evidence collection and reporting",
        complexity=ComplexityLevel.CRITICAL,
        required_connectors=["servicenow", "confluence"],
        steps=[
            {"step": "scope", "action": "define_audit_scope"},
            {"step": "collect", "action": "gather_evidence"},
            {"step": "validate", "action": "verify_controls"},
            {"step": "report", "action": "generate_report"},
            {"step": "remediate", "action": "create_action_items"},
        ],
        requires_hitl=True,
        compliance_frameworks=["GDPR", "SOC2", "HIPAA", "PCI-DSS"],
    ),
]


class AutomationTypeRegistry:
    """Registry of all automation types with templates, capabilities, and platform mappings."""

    def __init__(self):
        self._lock = threading.Lock()
        self._templates: Dict[str, AutomationTemplate] = {}
        self._capabilities: Dict[str, AutomationCapability] = {}
        self._execution_count: Dict[str, int] = {}
        self._register_defaults()

    def _register_defaults(self):
        for template in DEFAULT_TEMPLATES:
            self._templates[template.template_id] = template

        # Auto-generate capabilities from templates
        cap_map: Dict[str, List[str]] = {}
        for t in DEFAULT_TEMPLATES:
            cat = t.category.value
            if cat not in cap_map:
                cap_map[cat] = []
            cap_map[cat].append(t.template_id)

        for cat, template_ids in cap_map.items():
            self._capabilities[cat] = AutomationCapability(
                capability_id=cat,
                name=cat.replace("_", " ").title(),
                category=AutomationCategory(cat),
                description=f"Automation capabilities for {cat.replace('_', ' ')}",
                templates=template_ids,
                supported_platforms=list(set(
                    conn for tid in template_ids
                    for conn in self._templates[tid].required_connectors
                )),
            )

    def register_template(self, template: AutomationTemplate) -> bool:
        with self._lock:
            self._templates[template.template_id] = template
            # Update capability
            cat = template.category.value
            if cat not in self._capabilities:
                self._capabilities[cat] = AutomationCapability(
                    capability_id=cat,
                    name=cat.replace("_", " ").title(),
                    category=template.category,
                    description=f"Automation capabilities for {cat.replace('_', ' ')}",
                )
            if template.template_id not in self._capabilities[cat].templates:
                self._capabilities[cat].templates.append(template.template_id)
            return True

    def get_template(self, template_id: str) -> Optional[AutomationTemplate]:
        return self._templates.get(template_id)

    def list_templates(self, category: Optional[AutomationCategory] = None) -> List[Dict[str, Any]]:
        templates = self._templates.values()
        if category:
            templates = [t for t in templates if t.category == category]
        return [
            {
                "template_id": t.template_id,
                "name": t.name,
                "category": t.category.value,
                "description": t.description,
                "complexity": t.complexity.value,
                "required_connectors": t.required_connectors,
                "step_count": len(t.steps),
                "requires_hitl": t.requires_hitl,
                "compliance_frameworks": t.compliance_frameworks,
                "estimated_duration_minutes": t.estimated_duration_minutes,
            }
            for t in templates
        ]

    def list_categories(self) -> List[Dict[str, Any]]:
        return [
            {
                "category": cap.category.value,
                "name": cap.name,
                "template_count": len(cap.templates),
                "supported_platforms": cap.supported_platforms,
                "enabled": cap.enabled,
            }
            for cap in self._capabilities.values()
        ]

    def get_templates_for_platform(self, platform: str) -> List[Dict[str, Any]]:
        return [
            {
                "template_id": t.template_id,
                "name": t.name,
                "category": t.category.value,
            }
            for t in self._templates.values()
            if platform in t.required_connectors
        ]

    def get_required_platforms(self) -> Dict[str, int]:
        """Get platforms sorted by how many templates use them."""
        platform_counts: Dict[str, int] = {}
        for t in self._templates.values():
            for conn in t.required_connectors:
                platform_counts[conn] = platform_counts.get(conn, 0) + 1
        return dict(sorted(platform_counts.items(), key=lambda x: -x[1]))

    def record_execution(self, template_id: str) -> None:
        with self._lock:
            self._execution_count[template_id] = self._execution_count.get(template_id, 0) + 1

    def get_statistics(self) -> Dict[str, Any]:
        return {
            "total_templates": len(self._templates),
            "total_categories": len(self._capabilities),
            "categories": [c.value for c in set(t.category for t in self._templates.values())],
            "total_executions": sum(self._execution_count.values()),
            "most_used": sorted(
                self._execution_count.items(),
                key=lambda x: -x[1],
            )[:5] if self._execution_count else [],
            "hitl_required_templates": sum(1 for t in self._templates.values() if t.requires_hitl),
            "critical_templates": sum(1 for t in self._templates.values() if t.complexity == ComplexityLevel.CRITICAL),
            "required_platforms": self.get_required_platforms(),
        }

    def status(self) -> Dict[str, Any]:
        return {
            "module": "automation_type_registry",
            "statistics": self.get_statistics(),
            "categories": self.list_categories(),
        }
