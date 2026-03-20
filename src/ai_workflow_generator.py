"""
AI-Powered Workflow Generation — translates natural language descriptions
into DAG workflow definitions using template matching, step inference,
and dependency resolution.

Implements RECOMMENDATIONS.md Section 6.2.3.
"""

import hashlib
import logging
import re
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


# Keywords mapped to automation step types
STEP_KEYWORDS = {
    "fetch": "data_retrieval",
    "get": "data_retrieval",
    "pull": "data_retrieval",
    "download": "data_retrieval",
    "read": "data_retrieval",
    "collect": "data_retrieval",
    "extract": "data_retrieval",
    "transform": "data_transformation",
    "convert": "data_transformation",
    "map": "data_transformation",
    "parse": "data_transformation",
    "format": "data_transformation",
    "clean": "data_transformation",
    "normalize": "data_transformation",
    "filter": "data_filtering",
    "validate": "validation",
    "check": "validation",
    "verify": "validation",
    "ensure": "validation",
    "test": "validation",
    "send": "notification",
    "notify": "notification",
    "alert": "notification",
    "email": "notification",
    "message": "notification",
    "slack": "notification",
    "write": "data_output",
    "save": "data_output",
    "store": "data_output",
    "upload": "data_output",
    "export": "data_output",
    "publish": "data_output",
    "deploy": "deployment",
    "release": "deployment",
    "provision": "deployment",
    "launch": "deployment",
    "approve": "approval",
    "review": "approval",
    "sign-off": "approval",
    "analyze": "analysis",
    "report": "analysis",
    "summarize": "analysis",
    "aggregate": "analysis",
    "calculate": "computation",
    "compute": "computation",
    "process": "computation",
    "run": "execution",
    "execute": "execution",
    "trigger": "execution",
    "invoke": "execution",
    "wait": "delay",
    "pause": "delay",
    "schedule": "scheduling",
    "retry": "error_handling",
    "rollback": "error_handling",
    "backup": "data_protection",
    "archive": "data_protection",
    "encrypt": "security",
    "decrypt": "security",
    "authenticate": "security",
    "authorize": "security",
    # E-commerce / business
    "order": "data_retrieval",
    "receive": "data_retrieval",
    "import": "data_retrieval",
    "sync": "data_retrieval",
    "fulfill": "execution",
    "ship": "execution",
    "shipping": "execution",
    "dispatch": "execution",
    "assign": "execution",
    "route": "execution",
    "escalate": "execution",
    "create": "execution",
    "generate": "execution",
    "build": "execution",
    "update": "execution",
    "post": "data_output",
    "log": "data_output",
    "record": "data_output",
    "track": "data_output",
    "invoice": "execution",
    "pay": "execution",
    "charge": "execution",
    "reconcile": "computation",
    "match": "computation",
    "score": "computation",
    "rank": "computation",
    "enrich": "data_transformation",
    "segment": "data_filtering",
    "classify": "data_filtering",
    "tag": "data_filtering",
    "notify_team": "notification",
    "alert_manager": "notification",
    "reject": "approval",
    "sign": "approval",
    "book": "scheduling",
}

# Dependency inference: step type B depends on step type A
IMPLICIT_DEPENDENCIES = {
    "data_transformation": ["data_retrieval"],
    "data_filtering": ["data_retrieval", "data_transformation"],
    "validation": ["data_retrieval", "data_transformation"],
    "analysis": ["data_retrieval", "data_transformation"],
    "computation": ["data_retrieval"],
    "notification": ["validation", "analysis", "computation", "data_output", "deployment"],
    "data_output": ["data_transformation", "data_filtering", "computation", "analysis"],
    "deployment": ["validation", "data_output"],
    "approval": ["analysis", "validation"],
    "error_handling": ["execution", "deployment"],
}

# Template library: common workflow patterns
WORKFLOW_TEMPLATES = {
    "etl_pipeline": {
        "description": "Extract-Transform-Load data pipeline",
        "keywords": ["etl", "pipeline", "extract", "transform", "load", "data"],
        "steps": [
            {"name": "extract_data", "type": "data_retrieval", "description": "Extract data from source"},
            {"name": "transform_data", "type": "data_transformation", "description": "Transform and clean data", "depends_on": ["extract_data"]},
            {"name": "validate_data", "type": "validation", "description": "Validate transformed data", "depends_on": ["transform_data"]},
            {"name": "load_data", "type": "data_output", "description": "Load data into destination", "depends_on": ["validate_data"]},
        ],
    },
    "ci_cd": {
        "description": "Continuous integration and deployment",
        "keywords": ["ci", "cd", "build", "test", "deploy", "release", "pipeline"],
        "steps": [
            {"name": "fetch_code", "type": "data_retrieval", "description": "Fetch latest code"},
            {"name": "run_tests", "type": "validation", "description": "Run test suite", "depends_on": ["fetch_code"]},
            {"name": "build_artifacts", "type": "computation", "description": "Build deployment artifacts", "depends_on": ["run_tests"]},
            {"name": "deploy_staging", "type": "deployment", "description": "Deploy to staging", "depends_on": ["build_artifacts"]},
            {"name": "approval_gate", "type": "approval", "description": "Manual approval for production", "depends_on": ["deploy_staging"]},
            {"name": "deploy_production", "type": "deployment", "description": "Deploy to production", "depends_on": ["approval_gate"]},
        ],
    },
    "data_report": {
        "description": "Data collection, analysis, and reporting",
        "keywords": ["report", "analyze", "dashboard", "summary", "metrics"],
        "steps": [
            {"name": "collect_data", "type": "data_retrieval", "description": "Collect data from sources"},
            {"name": "clean_data", "type": "data_transformation", "description": "Clean and standardize", "depends_on": ["collect_data"]},
            {"name": "analyze_data", "type": "analysis", "description": "Perform analysis", "depends_on": ["clean_data"]},
            {"name": "generate_report", "type": "data_output", "description": "Generate report", "depends_on": ["analyze_data"]},
            {"name": "send_report", "type": "notification", "description": "Distribute report", "depends_on": ["generate_report"]},
        ],
    },
    "incident_response": {
        "description": "Automated incident detection and response",
        "keywords": ["incident", "alert", "respond", "triage", "escalate", "outage"],
        "steps": [
            {"name": "detect_incident", "type": "data_retrieval", "description": "Detect incident from monitoring"},
            {"name": "triage_severity", "type": "analysis", "description": "Assess severity level", "depends_on": ["detect_incident"]},
            {"name": "notify_team", "type": "notification", "description": "Alert on-call team", "depends_on": ["triage_severity"]},
            {"name": "run_diagnostics", "type": "execution", "description": "Run automated diagnostics", "depends_on": ["detect_incident"]},
            {"name": "apply_remediation", "type": "execution", "description": "Apply automated fix", "depends_on": ["run_diagnostics", "triage_severity"]},
            {"name": "verify_resolution", "type": "validation", "description": "Verify issue resolved", "depends_on": ["apply_remediation"]},
        ],
    },
    "customer_onboarding": {
        "description": "Automated customer onboarding workflow",
        "keywords": ["onboard", "customer", "welcome", "setup", "account", "provision"],
        "steps": [
            {"name": "validate_info", "type": "validation", "description": "Validate customer information"},
            {"name": "provision_account", "type": "deployment", "description": "Create and configure account", "depends_on": ["validate_info"]},
            {"name": "setup_integrations", "type": "execution", "description": "Configure integrations", "depends_on": ["provision_account"]},
            {"name": "send_welcome", "type": "notification", "description": "Send welcome communications", "depends_on": ["provision_account"]},
        ],
    },
    "security_scan": {
        "description": "Security vulnerability scanning and remediation",
        "keywords": ["security", "scan", "vulnerability", "patch", "audit", "compliance"],
        "steps": [
            {"name": "scan_targets", "type": "data_retrieval", "description": "Scan systems for vulnerabilities"},
            {"name": "analyze_results", "type": "analysis", "description": "Analyze scan results", "depends_on": ["scan_targets"]},
            {"name": "prioritize_findings", "type": "computation", "description": "Prioritize by severity", "depends_on": ["analyze_results"]},
            {"name": "generate_tickets", "type": "data_output", "description": "Create remediation tickets", "depends_on": ["prioritize_findings"]},
            {"name": "notify_owners", "type": "notification", "description": "Notify asset owners", "depends_on": ["generate_tickets"]},
        ],
    },
    "order_fulfillment": {
        "description": "End-to-end e-commerce order fulfillment automation",
        "keywords": ["order", "shopify", "shipping", "inventory"],
        "steps": [
            {"name": "receive_order", "type": "data_retrieval", "description": "Receive new order event from e-commerce platform (Shopify webhook)"},
            {"name": "validate_payment", "type": "validation", "description": "Verify payment authorisation via payment gateway (Stripe/PayPal)", "depends_on": ["receive_order"]},
            {"name": "update_inventory", "type": "execution", "description": "Decrement stock levels in inventory system", "depends_on": ["validate_payment"]},
            {"name": "create_shipping_label", "type": "execution", "description": "Generate shipping label via carrier API (FedEx/UPS/USPS)", "depends_on": ["validate_payment"]},
            {"name": "notify_warehouse", "type": "notification", "description": "Send pick/pack instruction to warehouse team", "depends_on": ["create_shipping_label", "update_inventory"]},
            {"name": "send_confirmation", "type": "notification", "description": "Email order confirmation + tracking number to customer", "depends_on": ["create_shipping_label"]},
            {"name": "log_transaction", "type": "data_output", "description": "Record fulfillment details in CRM / ERP for reporting", "depends_on": ["send_confirmation"]},
        ],
    },
    "invoice_processing": {
        "description": "Automated invoice receipt, approval, and payment workflow",
        "keywords": ["invoice", "billing", "accounts payable"],
        "steps": [
            {"name": "receive_invoice", "type": "data_retrieval", "description": "Receive invoice via email / API / file upload"},
            {"name": "extract_data", "type": "data_transformation", "description": "Extract vendor, amount, line items, due date via OCR / API", "depends_on": ["receive_invoice"]},
            {"name": "validate_invoice", "type": "validation", "description": "Match against purchase order and contract terms", "depends_on": ["extract_data"]},
            {"name": "route_approval", "type": "approval", "description": "Route to approver based on amount thresholds and GL codes", "depends_on": ["validate_invoice"]},
            {"name": "process_payment", "type": "execution", "description": "Execute payment via ACH / wire transfer on approval", "depends_on": ["route_approval"]},
            {"name": "update_ledger", "type": "data_output", "description": "Post payment entry to accounting system (QuickBooks / NetSuite)", "depends_on": ["process_payment"]},
            {"name": "notify_vendor", "type": "notification", "description": "Send payment confirmation to vendor", "depends_on": ["process_payment"]},
        ],
    },
    "lead_nurture": {
        "description": "Automated lead scoring, nurturing, and CRM handoff",
        "keywords": ["lead", "nurtur", "crm", "email"],
        "steps": [
            {"name": "capture_lead", "type": "data_retrieval", "description": "Capture lead from form, ad, or website event"},
            {"name": "score_lead", "type": "analysis", "description": "Score lead by firmographics, behaviour, and intent signals", "depends_on": ["capture_lead"]},
            {"name": "enrich_profile", "type": "execution", "description": "Enrich contact data via Clearbit / Apollo / LinkedIn API", "depends_on": ["capture_lead"]},
            {"name": "segment_lead", "type": "data_filtering", "description": "Assign to appropriate nurture track (cold / warm / hot)", "depends_on": ["score_lead", "enrich_profile"]},
            {"name": "send_sequence", "type": "notification", "description": "Trigger personalised email sequence via Mailchimp / HubSpot", "depends_on": ["segment_lead"]},
            {"name": "update_crm", "type": "data_output", "description": "Sync lead record and activity to CRM", "depends_on": ["enrich_profile"]},
            {"name": "handoff_to_sales", "type": "notification", "description": "Alert sales rep when lead reaches hot threshold", "depends_on": ["score_lead"]},
        ],
    },
    "employee_onboarding": {
        "description": "Automated HR employee onboarding workflow",
        "keywords": ["employee", "hire", "new hire", "hris", "orientation"],
        "steps": [
            {"name": "create_profile", "type": "execution", "description": "Create employee record in HRIS (BambooHR / Workday)"},
            {"name": "provision_accounts", "type": "deployment", "description": "Provision email, Slack, JIRA, and app accounts", "depends_on": ["create_profile"]},
            {"name": "assign_equipment", "type": "execution", "description": "Raise IT ticket for laptop, hardware, and access cards", "depends_on": ["create_profile"]},
            {"name": "send_welcome_pack", "type": "notification", "description": "Send welcome email with first-day info and handbook link", "depends_on": ["provision_accounts"]},
            {"name": "schedule_orientation", "type": "scheduling", "description": "Book orientation sessions and manager 1:1 in calendar", "depends_on": ["create_profile"]},
            {"name": "assign_buddy", "type": "execution", "description": "Assign onboarding buddy and notify both parties", "depends_on": ["create_profile"]},
            {"name": "track_completion", "type": "data_output", "description": "Track checklist completion and notify HR at 30 / 60 / 90 days", "depends_on": ["send_welcome_pack", "assign_buddy"]},
        ],
    },
    "content_publishing": {
        "description": "Automated content creation, review, and multi-channel publishing",
        "keywords": ["content", "publish", "blog", "social media", "cms"],
        "steps": [
            {"name": "create_content", "type": "execution", "description": "Draft content using AI or human writer"},
            {"name": "review_content", "type": "approval", "description": "Route draft for editorial review and brand-voice check", "depends_on": ["create_content"]},
            {"name": "seo_optimise", "type": "data_transformation", "description": "Add metadata, alt text, and SEO keywords", "depends_on": ["review_content"]},
            {"name": "publish_primary", "type": "deployment", "description": "Publish to primary CMS (WordPress / Contentful)", "depends_on": ["seo_optimise"]},
            {"name": "syndicate_social", "type": "notification", "description": "Cross-post to LinkedIn, Twitter/X, Facebook via Buffer / Hootsuite", "depends_on": ["publish_primary"]},
            {"name": "track_performance", "type": "data_output", "description": "Log publish event and schedule performance report at 7 / 30 days", "depends_on": ["publish_primary"]},
        ],
    },
}


class AIWorkflowGenerator:
    """
    Translates natural language descriptions into DAG workflow definitions.
    Uses template matching, keyword analysis, step inference, and dependency
    resolution to generate executable workflows.
    """

    def __init__(self):
        self._templates = dict(WORKFLOW_TEMPLATES)
        self._custom_step_types: Dict[str, Dict[str, Any]] = {}
        self._generation_history: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def generate_workflow(self, description: str,
                          context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate a DAG workflow from a natural language description."""
        description_lower = description.lower().strip()

        # Step 1: Try template matching
        template_match = self._match_template(description_lower)

        # Step 2: Extract steps from description
        inferred_steps = self._infer_steps(description_lower)

        # Step 3: Decide strategy.
        # Use 50% threshold (instead of 60%) so that templates with 4 keywords
        # match when 2 of the core terms are present (e.g. "order" + "shopify"
        # for the order_fulfillment template).
        if template_match and template_match["score"] >= 0.5:
            steps = list(template_match["template"]["steps"])
            strategy = "template_match"
            template_name = template_match["name"]
        elif inferred_steps:
            steps = self._build_steps_from_inference(inferred_steps)
            strategy = "keyword_inference"
            template_name = None
        else:
            steps = self._build_generic_steps(description_lower)
            strategy = "generic_fallback"
            template_name = None

        # Step 4: Resolve dependencies
        steps = self._resolve_dependencies(steps)

        # Step 5: Build workflow
        workflow_id = hashlib.sha256(
            f"{description}:{datetime.now(timezone.utc).isoformat()}".encode()
        ).hexdigest()[:12]

        workflow = {
            "workflow_id": workflow_id,
            "name": self._generate_workflow_name(description),
            "description": description,
            "strategy": strategy,
            "template_used": template_name,
            "steps": steps,
            "step_count": len(steps),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "context": context or {},
        }

        with self._lock:
            capped_append(self._generation_history, {
                "workflow_id": workflow_id,
                "description": description[:200],
                "strategy": strategy,
                "step_count": len(steps),
                "timestamp": workflow["generated_at"],
            })

        return workflow

    def add_template(self, name: str, template: Dict[str, Any]) -> Dict[str, Any]:
        """Add a custom workflow template."""
        required = ["description", "keywords", "steps"]
        for field in required:
            if field not in template:
                return {"added": False, "error": f"Missing required field: {field}"}

        with self._lock:
            self._templates[name] = template
        return {"added": True, "name": name}

    def list_templates(self) -> List[Dict[str, Any]]:
        """List all available workflow templates."""
        with self._lock:
            return [
                {
                    "name": name,
                    "description": t["description"],
                    "keywords": t["keywords"],
                    "step_count": len(t["steps"]),
                }
                for name, t in self._templates.items()
            ]

    def register_step_type(self, type_name: str, spec: Dict[str, Any]):
        """Register a custom step type."""
        with self._lock:
            self._custom_step_types[type_name] = spec

    def get_generation_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._generation_history[-limit:])

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "module": "ai_workflow_generator",
                "template_count": len(self._templates),
                "custom_step_types": len(self._custom_step_types),
                "total_generations": len(self._generation_history),
                "supported_step_keywords": len(STEP_KEYWORDS),
            }

    def _match_template(self, description: str) -> Optional[Dict[str, Any]]:
        best_match = None
        best_score = 0.0

        with self._lock:
            templates = dict(self._templates)

        for name, template in templates.items():
            keywords = template.get("keywords", [])
            if not keywords:
                continue
            matches = sum(1 for kw in keywords if kw in description)
            score = matches / len(keywords)
            if score > best_score:
                best_score = score
                best_match = {"name": name, "template": template, "score": score}

        return best_match

    def _infer_steps(self, description: str) -> List[Tuple[str, str, str]]:
        """Extract (keyword, step_type, context) tuples from description."""
        words = re.findall(r'\b[a-z]+(?:-[a-z]+)*\b', description)
        found = []
        seen_types = set()

        for word in words:
            if word in STEP_KEYWORDS:
                step_type = STEP_KEYWORDS[word]
                if step_type not in seen_types:
                    seen_types.add(step_type)
                    context = self._extract_context(description, word)
                    found.append((word, step_type, context))

        return found

    def _extract_context(self, description: str, keyword: str) -> str:
        """Extract surrounding context for a keyword."""
        idx = description.find(keyword)
        if idx == -1:
            return ""
        start = max(0, idx - 30)
        end = min(len(description), idx + len(keyword) + 30)
        return description[start:end].strip()

    def _build_steps_from_inference(self, inferred: List[Tuple[str, str, str]]) -> List[Dict[str, Any]]:
        steps = []
        for i, (keyword, step_type, context) in enumerate(inferred):
            step_name = f"{keyword}_{step_type}_{i}"
            steps.append({
                "name": step_name,
                "type": step_type,
                "description": f"{keyword.title()}: {context}" if context else f"{keyword.title()} step",
                "depends_on": [],
            })
        return steps

    def _build_generic_steps(self, description: str) -> List[Dict[str, Any]]:
        """Build generic steps when no keywords or templates match."""
        return [
            {"name": "input_processing", "type": "data_retrieval",
             "description": f"Process input: {description[:80]}", "depends_on": []},
            {"name": "execution", "type": "execution",
             "description": "Execute main task", "depends_on": ["input_processing"]},
            {"name": "output", "type": "data_output",
             "description": "Generate output", "depends_on": ["execution"]},
        ]

    def _resolve_dependencies(self, steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Resolve implicit dependencies between steps based on type ordering."""
        step_names_by_type: Dict[str, List[str]] = {}
        for step in steps:
            t = step.get("type", "execution")
            if t not in step_names_by_type:
                step_names_by_type[t] = []
            step_names_by_type[t].append(step["name"])

        for step in steps:
            if step.get("depends_on"):
                continue
            step_type = step.get("type", "execution")
            dep_types = IMPLICIT_DEPENDENCIES.get(step_type, [])
            deps = []
            for dt in dep_types:
                if dt in step_names_by_type:
                    deps.extend(step_names_by_type[dt])
            existing_names = {s["name"] for s in steps}
            step["depends_on"] = [d for d in deps if d in existing_names and d != step["name"]]

        return steps

    def _generate_workflow_name(self, description: str) -> str:
        """Generate a workflow name from description."""
        words = re.findall(r'\b[a-z]+\b', description.lower())
        meaningful = [w for w in words if len(w) > 3 and w not in {"then", "from", "with", "this", "that", "when", "will", "into", "also", "each", "every"}]
        if meaningful:
            return "_".join(meaningful[:4]) + "_workflow"
        return "generated_workflow"
