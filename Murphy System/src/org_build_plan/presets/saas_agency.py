# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""SaaS and agency industry preset for the org_build_plan package."""

from __future__ import annotations

from ..presets import IndustryPreset

PRESET = IndustryPreset(
    preset_id="saas_agency",
    name="SaaS & Agency",
    description=(
        "SOC2/GDPR-compliant technology LLC with client onboarding, "
        "sprint planning, deployment pipeline, and customer health workflows."
    ),
    industry="technology",
    default_org_type="llc",
    default_labor_model="w2",
    default_company_size="medium",
    recommended_connectors=[
        "github",
        "jira",
        "slack",
        "salesforce",
        "stripe",
        "quickbooks",
        "confluence",
    ],
    recommended_frameworks=["SOC2", "GDPR"],
    default_departments=[
        {
            "name": "engineering",
            "head_name": "VP of Engineering",
            "head_email": "engineering@tech.com",
            "headcount": 20,
            "level": "vp",
            "responsibilities": ["software_development", "architecture", "devops"],
            "automation_priorities": ["system", "data"],
        },
        {
            "name": "product",
            "head_name": "VP of Product",
            "head_email": "product@tech.com",
            "headcount": 8,
            "level": "vp",
            "responsibilities": ["roadmap", "feature_prioritization", "stakeholder_management"],
            "automation_priorities": ["data", "agent"],
        },
        {
            "name": "sales",
            "head_name": "VP of Sales",
            "head_email": "sales@tech.com",
            "headcount": 10,
            "level": "vp",
            "responsibilities": ["new_business", "account_expansion", "pipeline_management"],
            "automation_priorities": ["business", "agent"],
        },
        {
            "name": "customer_success",
            "head_name": "VP of Customer Success",
            "head_email": "cs@tech.com",
            "headcount": 8,
            "level": "vp",
            "responsibilities": ["onboarding", "retention", "health_scoring", "renewals"],
            "automation_priorities": ["agent", "data"],
        },
        {
            "name": "operations",
            "head_name": "COO",
            "head_email": "ops@tech.com",
            "headcount": 6,
            "level": "c_suite",
            "responsibilities": ["finance", "hr", "legal", "vendor_management"],
            "automation_priorities": ["business", "data"],
        },
    ],
    workflow_templates=[
        {
            "template_id": "saas_client_onboarding",
            "name": "Client Onboarding",
            "description": "Automated new client setup and activation",
            "category": "customer",
            "steps": [
                {
                    "step_id": "create_account",
                    "name": "Create Client Account",
                    "action": "salesforce.create_account",
                    "depends_on": [],
                    "description": "Set up client account in CRM",
                },
                {
                    "step_id": "provision_access",
                    "name": "Provision Platform Access",
                    "action": "system.provision_tenant",
                    "depends_on": ["create_account"],
                    "description": "Create isolated tenant environment for client",
                },
                {
                    "step_id": "send_welcome",
                    "name": "Send Welcome Materials",
                    "action": "slack.send_message",
                    "depends_on": ["provision_access"],
                    "description": "Send welcome kit and kickoff meeting invite",
                },
            ],
        },
        {
            "template_id": "saas_sprint_planning",
            "name": "Sprint Planning",
            "description": "Automated sprint planning and backlog management",
            "category": "operations",
            "steps": [
                {
                    "step_id": "review_backlog",
                    "name": "Review Product Backlog",
                    "action": "jira.get_backlog",
                    "depends_on": [],
                    "description": "Fetch and rank current product backlog",
                },
                {
                    "step_id": "assign_sprint",
                    "name": "Assign Sprint Issues",
                    "action": "jira.create_sprint",
                    "depends_on": ["review_backlog"],
                    "description": "Create new sprint and assign top backlog items",
                },
                {
                    "step_id": "notify_team",
                    "name": "Notify Engineering Team",
                    "action": "slack.send_message",
                    "depends_on": ["assign_sprint"],
                    "description": "Post sprint plan to team Slack channel",
                },
            ],
        },
        {
            "template_id": "saas_deployment_pipeline",
            "name": "Deployment Pipeline",
            "description": "CI/CD deployment pipeline with compliance gates",
            "category": "operations",
            "steps": [
                {
                    "step_id": "run_tests",
                    "name": "Run Automated Tests",
                    "action": "github.run_workflow",
                    "depends_on": [],
                    "description": "Execute test suite against release candidate",
                },
                {
                    "step_id": "security_scan",
                    "name": "Security Scan",
                    "action": "compliance_engine.scan_code",
                    "depends_on": ["run_tests"],
                    "description": "Run SAST/DAST security scanning",
                },
                {
                    "step_id": "deploy",
                    "name": "Deploy to Production",
                    "action": "system.deploy_release",
                    "depends_on": ["security_scan"],
                    "description": "Roll out release to production environment",
                },
            ],
        },
        {
            "template_id": "saas_customer_health",
            "name": "Customer Health Check",
            "description": "Automated customer health scoring and at-risk detection",
            "category": "customer",
            "steps": [
                {
                    "step_id": "collect_usage_data",
                    "name": "Collect Usage Metrics",
                    "action": "data.collect_product_usage",
                    "depends_on": [],
                    "description": "Pull product usage telemetry for all accounts",
                },
                {
                    "step_id": "calculate_health",
                    "name": "Calculate Health Scores",
                    "action": "data.calculate_health_scores",
                    "depends_on": ["collect_usage_data"],
                    "description": "Compute health scores for each account",
                },
                {
                    "step_id": "flag_at_risk",
                    "name": "Flag At-Risk Accounts",
                    "action": "salesforce.update_opportunity",
                    "depends_on": ["calculate_health"],
                    "description": "Mark accounts below health threshold in CRM",
                },
            ],
        },
    ],
    setup_wizard_preset="agency_automation",
)
