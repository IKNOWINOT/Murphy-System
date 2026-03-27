# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Retail and e-commerce industry preset for the org_build_plan package."""

from __future__ import annotations

from ..presets import IndustryPreset

PRESET = IndustryPreset(
    preset_id="retail_ecommerce",
    name="Retail & E-Commerce",
    description=(
        "PCI-DSS/GDPR-compliant retail LLC with order fulfillment, "
        "inventory management, and marketing campaign workflows."
    ),
    industry="retail",
    default_org_type="llc",
    default_labor_model="w2",
    default_company_size="small",
    recommended_connectors=[
        "stripe",
        "quickbooks",
        "mailchimp",
        "slack",
        "canva",
        "google_analytics",
    ],
    recommended_frameworks=["PCI_DSS", "GDPR"],
    default_departments=[
        {
            "name": "sales",
            "head_name": "Sales Manager",
            "head_email": "sales@retail.com",
            "headcount": 10,
            "level": "manager",
            "responsibilities": ["sales_targets", "customer_acquisition", "channel_management"],
            "automation_priorities": ["business", "data"],
        },
        {
            "name": "marketing",
            "head_name": "Marketing Manager",
            "head_email": "marketing@retail.com",
            "headcount": 6,
            "level": "manager",
            "responsibilities": ["campaigns", "seo", "social_media", "email_marketing"],
            "automation_priorities": ["content", "data"],
        },
        {
            "name": "fulfillment",
            "head_name": "Fulfillment Manager",
            "head_email": "fulfillment@retail.com",
            "headcount": 12,
            "level": "manager",
            "responsibilities": ["order_processing", "shipping", "warehouse_management"],
            "automation_priorities": ["business", "system"],
        },
        {
            "name": "customer_support",
            "head_name": "Customer Support Lead",
            "head_email": "support@retail.com",
            "headcount": 8,
            "level": "lead",
            "responsibilities": ["ticket_resolution", "returns", "customer_communications"],
            "automation_priorities": ["agent", "business"],
        },
    ],
    workflow_templates=[
        {
            "template_id": "ret_order_fulfillment",
            "name": "Order Fulfillment",
            "description": "Automated order processing from payment to shipment",
            "category": "operations",
            "steps": [
                {
                    "step_id": "capture_payment",
                    "name": "Capture Payment",
                    "action": "stripe.capture_charge",
                    "depends_on": [],
                    "description": "Confirm and capture payment for order",
                },
                {
                    "step_id": "pick_pack",
                    "name": "Pick and Pack Order",
                    "action": "fulfillment.pick_pack",
                    "depends_on": ["capture_payment"],
                    "description": "Generate pick list and pack confirmation",
                },
                {
                    "step_id": "generate_label",
                    "name": "Generate Shipping Label",
                    "action": "fulfillment.create_shipping_label",
                    "depends_on": ["pick_pack"],
                    "description": "Print shipping label via carrier API",
                },
                {
                    "step_id": "send_confirmation",
                    "name": "Send Order Confirmation",
                    "action": "mailchimp.send_transactional",
                    "depends_on": ["generate_label"],
                    "description": "Email customer with tracking information",
                },
            ],
        },
        {
            "template_id": "ret_inventory_restock",
            "name": "Inventory Restock",
            "description": "Automated low-stock detection and reorder",
            "category": "operations",
            "steps": [
                {
                    "step_id": "check_stock",
                    "name": "Check Inventory Levels",
                    "action": "inventory.check_stock_levels",
                    "depends_on": [],
                    "description": "Query current inventory for all SKUs",
                },
                {
                    "step_id": "identify_low",
                    "name": "Identify Low-Stock Items",
                    "action": "inventory.find_low_stock",
                    "depends_on": ["check_stock"],
                    "description": "Flag SKUs below reorder threshold",
                },
                {
                    "step_id": "create_purchase_order",
                    "name": "Create Purchase Order",
                    "action": "quickbooks.create_purchase_order",
                    "depends_on": ["identify_low"],
                    "description": "Generate PO for low-stock SKUs",
                },
            ],
        },
        {
            "template_id": "ret_support_ticket",
            "name": "Customer Support Ticket",
            "description": "Automated customer support triage and routing",
            "category": "customer",
            "steps": [
                {
                    "step_id": "receive_ticket",
                    "name": "Receive Support Request",
                    "action": "data.capture_support_request",
                    "depends_on": [],
                    "description": "Capture incoming customer support request",
                },
                {
                    "step_id": "classify_issue",
                    "name": "Classify Issue Type",
                    "action": "agent.classify_support_issue",
                    "depends_on": ["receive_ticket"],
                    "description": "Categorize ticket for proper routing",
                },
                {
                    "step_id": "assign_agent",
                    "name": "Assign to Support Agent",
                    "action": "slack.send_message",
                    "depends_on": ["classify_issue"],
                    "description": "Route ticket to appropriate support agent",
                },
            ],
        },
        {
            "template_id": "ret_marketing_campaign",
            "name": "Marketing Campaign",
            "description": "Multi-channel promotional campaign launch",
            "category": "customer",
            "steps": [
                {
                    "step_id": "create_content",
                    "name": "Create Campaign Content",
                    "action": "canva.create_design",
                    "depends_on": [],
                    "description": "Design promotional graphics and copy",
                },
                {
                    "step_id": "segment_audience",
                    "name": "Segment Audience",
                    "action": "mailchimp.segment_list",
                    "depends_on": ["create_content"],
                    "description": "Segment email list by purchase history",
                },
                {
                    "step_id": "launch_campaign",
                    "name": "Launch Campaign",
                    "action": "mailchimp.send_campaign",
                    "depends_on": ["segment_audience"],
                    "description": "Send campaign to segmented list",
                },
            ],
        },
    ],
    setup_wizard_preset="startup_growth",
)
