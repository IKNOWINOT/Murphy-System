# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Nonprofit and advocacy industry preset for the org_build_plan package."""

from __future__ import annotations

from ..presets import IndustryPreset

PRESET = IndustryPreset(
    preset_id="nonprofit_advocacy",
    name="Nonprofit & Advocacy",
    description=(
        "GDPR/CAN-SPAM compliant nonprofit organization with campaign "
        "management, grant tracking, and volunteer onboarding workflows."
    ),
    industry="nonprofit",
    default_org_type="nonprofit",
    default_labor_model="mixed",
    default_company_size="small",
    recommended_connectors=[
        "mailchimp",
        "stripe",
        "slack",
        "google_analytics",
        "canva",
    ],
    recommended_frameworks=["CAN_SPAM", "GDPR"],
    default_departments=[
        {
            "name": "programs",
            "head_name": "Programs Director",
            "head_email": "programs@nonprofit.org",
            "headcount": 8,
            "level": "director",
            "responsibilities": ["program_delivery", "impact_measurement", "partnerships"],
            "automation_priorities": ["data", "agent"],
        },
        {
            "name": "fundraising",
            "head_name": "Development Director",
            "head_email": "fundraising@nonprofit.org",
            "headcount": 5,
            "level": "director",
            "responsibilities": ["grant_writing", "donor_relations", "campaigns"],
            "automation_priorities": ["business", "content"],
        },
        {
            "name": "communications",
            "head_name": "Communications Manager",
            "head_email": "comms@nonprofit.org",
            "headcount": 4,
            "level": "manager",
            "responsibilities": ["social_media", "press_releases", "email_campaigns"],
            "automation_priorities": ["content", "data"],
        },
        {
            "name": "volunteer_coordination",
            "head_name": "Volunteer Coordinator",
            "head_email": "volunteers@nonprofit.org",
            "headcount": 3,
            "level": "lead",
            "responsibilities": ["volunteer_recruitment", "scheduling", "training"],
            "automation_priorities": ["agent", "business"],
        },
    ],
    workflow_templates=[
        {
            "template_id": "npo_campaign_launch",
            "name": "Campaign Launch",
            "description": "End-to-end fundraising campaign launch sequence",
            "category": "operations",
            "steps": [
                {
                    "step_id": "create_campaign_assets",
                    "name": "Create Campaign Assets",
                    "action": "canva.create_design",
                    "depends_on": [],
                    "description": "Design campaign graphics and materials",
                },
                {
                    "step_id": "setup_donation_page",
                    "name": "Setup Donation Page",
                    "action": "stripe.create_payment_link",
                    "depends_on": ["create_campaign_assets"],
                    "description": "Create donation landing page with payment processor",
                },
                {
                    "step_id": "send_launch_email",
                    "name": "Send Launch Email",
                    "action": "mailchimp.send_campaign",
                    "depends_on": ["setup_donation_page"],
                    "description": "Email donor list with campaign announcement",
                },
            ],
        },
        {
            "template_id": "npo_grant_tracking",
            "name": "Grant Tracking",
            "description": "Track grant applications, deadlines, and reporting",
            "category": "finance",
            "steps": [
                {
                    "step_id": "check_deadlines",
                    "name": "Check Grant Deadlines",
                    "action": "data.check_grant_deadlines",
                    "depends_on": [],
                    "description": "Review upcoming grant application deadlines",
                },
                {
                    "step_id": "draft_report",
                    "name": "Draft Progress Report",
                    "action": "data.draft_grant_report",
                    "depends_on": ["check_deadlines"],
                    "description": "Generate impact data for grant reporting",
                },
                {
                    "step_id": "notify_team",
                    "name": "Notify Development Team",
                    "action": "slack.send_message",
                    "depends_on": ["draft_report"],
                    "description": "Alert team of upcoming deadlines and drafts",
                },
            ],
        },
        {
            "template_id": "npo_volunteer_onboarding",
            "name": "Volunteer Onboarding",
            "description": "Streamlined volunteer intake and training workflow",
            "category": "operations",
            "steps": [
                {
                    "step_id": "collect_application",
                    "name": "Collect Volunteer Application",
                    "action": "data.capture_volunteer_form",
                    "depends_on": [],
                    "description": "Receive and store volunteer application data",
                },
                {
                    "step_id": "send_welcome",
                    "name": "Send Welcome Email",
                    "action": "mailchimp.send_transactional",
                    "depends_on": ["collect_application"],
                    "description": "Send welcome packet and orientation materials",
                },
                {
                    "step_id": "schedule_orientation",
                    "name": "Schedule Orientation",
                    "action": "data.schedule_event",
                    "depends_on": ["send_welcome"],
                    "description": "Book volunteer for next orientation session",
                },
            ],
        },
        {
            "template_id": "npo_impact_report",
            "name": "Impact Report",
            "description": "Quarterly impact measurement and reporting",
            "category": "compliance",
            "steps": [
                {
                    "step_id": "collect_metrics",
                    "name": "Collect Impact Metrics",
                    "action": "google_analytics.get_metrics",
                    "depends_on": [],
                    "description": "Pull program outcome and reach metrics",
                },
                {
                    "step_id": "compile_report",
                    "name": "Compile Impact Report",
                    "action": "data.compile_impact_report",
                    "depends_on": ["collect_metrics"],
                    "description": "Assemble narrative and data into report",
                },
                {
                    "step_id": "publish_report",
                    "name": "Publish to Stakeholders",
                    "action": "mailchimp.send_campaign",
                    "depends_on": ["compile_report"],
                    "description": "Distribute impact report to donors and board",
                },
            ],
        },
    ],
    setup_wizard_preset="solo_operator",
)
