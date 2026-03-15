# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Financial services industry preset for the org_build_plan package."""

from __future__ import annotations

from ..presets import IndustryPreset

PRESET = IndustryPreset(
    preset_id="financial_services",
    name="Financial Services",
    description=(
        "SOC2/PCI/GDPR-hardened financial services organization with "
        "transaction audit, compliance reporting, and client onboarding workflows."
    ),
    industry="finance",
    default_org_type="corporation",
    default_labor_model="w2",
    default_company_size="medium",
    recommended_connectors=[
        "stripe",
        "quickbooks",
        "xero",
        "salesforce",
        "power_bi",
        "slack",
    ],
    recommended_frameworks=["SOC2", "PCI_DSS", "GDPR"],
    default_departments=[
        {
            "name": "trading",
            "head_name": "Head of Trading",
            "head_email": "trading@company.com",
            "headcount": 15,
            "level": "director",
            "responsibilities": ["trading_operations", "market_analysis", "portfolio_management"],
            "automation_priorities": ["data", "business"],
        },
        {
            "name": "compliance",
            "head_name": "Chief Compliance Officer",
            "head_email": "compliance@company.com",
            "headcount": 8,
            "level": "c_suite",
            "responsibilities": ["regulatory_compliance", "audit", "reporting"],
            "automation_priorities": ["data", "agent"],
        },
        {
            "name": "risk",
            "head_name": "Chief Risk Officer",
            "head_email": "risk@company.com",
            "headcount": 6,
            "level": "c_suite",
            "responsibilities": ["risk_assessment", "exposure_monitoring", "model_validation"],
            "automation_priorities": ["data", "agent"],
        },
        {
            "name": "client_services",
            "head_name": "VP of Client Services",
            "head_email": "clients@company.com",
            "headcount": 20,
            "level": "vp",
            "responsibilities": ["client_onboarding", "account_management", "support"],
            "automation_priorities": ["business", "agent"],
        },
        {
            "name": "it",
            "head_name": "CTO",
            "head_email": "it@company.com",
            "headcount": 12,
            "level": "c_suite",
            "responsibilities": ["infrastructure", "security", "systems"],
            "automation_priorities": ["system", "data"],
        },
    ],
    workflow_templates=[
        {
            "template_id": "fin_transaction_audit",
            "name": "Transaction Audit",
            "description": "Automated PCI-DSS transaction audit trail",
            "category": "compliance",
            "steps": [
                {
                    "step_id": "pull_transactions",
                    "name": "Pull Transaction Records",
                    "action": "stripe.list_transactions",
                    "depends_on": [],
                    "description": "Retrieve transaction batch from payment processor",
                },
                {
                    "step_id": "check_flags",
                    "name": "Flag Anomalies",
                    "action": "compliance_engine.flag_anomalies",
                    "depends_on": ["pull_transactions"],
                    "description": "Identify transactions that require review",
                },
                {
                    "step_id": "generate_audit_log",
                    "name": "Generate Audit Log",
                    "action": "data.write_audit_log",
                    "depends_on": ["check_flags"],
                    "description": "Write immutable audit record for compliance",
                },
            ],
        },
        {
            "template_id": "fin_compliance_report",
            "name": "Compliance Report",
            "description": "Generate periodic SOC2 compliance status report",
            "category": "compliance",
            "steps": [
                {
                    "step_id": "collect_controls",
                    "name": "Collect Control Evidence",
                    "action": "compliance_engine.collect_evidence",
                    "depends_on": [],
                    "description": "Gather evidence for SOC2 controls",
                },
                {
                    "step_id": "generate_report",
                    "name": "Generate Report",
                    "action": "data.generate_compliance_report",
                    "depends_on": ["collect_controls"],
                    "description": "Produce formatted compliance report",
                },
                {
                    "step_id": "distribute_report",
                    "name": "Distribute to Stakeholders",
                    "action": "slack.send_message",
                    "depends_on": ["generate_report"],
                    "description": "Send report to compliance stakeholders",
                },
            ],
        },
        {
            "template_id": "fin_client_onboarding",
            "name": "Client Onboarding",
            "description": "KYC/AML client onboarding with compliance gates",
            "category": "customer",
            "steps": [
                {
                    "step_id": "collect_kyc",
                    "name": "Collect KYC Documents",
                    "action": "salesforce.create_case",
                    "depends_on": [],
                    "description": "Request and collect client identity documents",
                },
                {
                    "step_id": "verify_identity",
                    "name": "Verify Identity",
                    "action": "compliance_engine.verify_kyc",
                    "depends_on": ["collect_kyc"],
                    "description": "Run automated KYC/AML verification",
                },
                {
                    "step_id": "open_account",
                    "name": "Open Client Account",
                    "action": "salesforce.update_account",
                    "depends_on": ["verify_identity"],
                    "description": "Activate client account upon successful verification",
                },
            ],
        },
        {
            "template_id": "fin_risk_assessment",
            "name": "Risk Assessment",
            "description": "Periodic portfolio risk scoring and exposure report",
            "category": "finance",
            "steps": [
                {
                    "step_id": "fetch_positions",
                    "name": "Fetch Current Positions",
                    "action": "data.fetch_portfolio_positions",
                    "depends_on": [],
                    "description": "Retrieve current portfolio holdings",
                },
                {
                    "step_id": "score_risk",
                    "name": "Score Risk Exposure",
                    "action": "data.calculate_risk_score",
                    "depends_on": ["fetch_positions"],
                    "description": "Calculate VaR and other risk metrics",
                },
                {
                    "step_id": "alert_breaches",
                    "name": "Alert on Breaches",
                    "action": "slack.send_alert",
                    "depends_on": ["score_risk"],
                    "description": "Notify risk team of limit breaches",
                },
            ],
        },
    ],
    setup_wizard_preset="enterprise_compliance",
)
