"""
PRESET-025 through PRESET-029 — Retail & Commerce Presets
Copyright 2024 Inoni LLC – BSL-1.1
"""
from __future__ import annotations
import logging
from typing import List
from .base import AgentPersona, ComplianceRule, IndustryPreset, IntegrationMapping, KPIDefinition, WorkflowTemplate
logger = logging.getLogger(__name__)

ECOMMERCE = IndustryPreset(
    preset_id="PRESET-025", name="E-Commerce", industry="Retail & Commerce", sub_industry="E-Commerce",
    description="Inventory, fulfillment, customer service, and marketing automation for online retailers.",
    version="1.0.0", tags=["ecommerce","shopify","fulfillment","PCI-DSS","GDPR","CLV"],
    compatible_with=["PRESET-026","PRESET-028"],
    workflow_templates=[
        WorkflowTemplate(template_id="WF-ECOM-001", name="Order Fulfillment", description="Order receipt to customer delivery.",
            steps=[
                {"step_name":"Order Receipt & Fraud Check","step_type":"automated_check","agent_persona":"E-Commerce Operations Agent","integrations":["Shopify","ShipStation"],"compliance_gates":["PCI-DSS"],"kpis":["fulfillment_accuracy"]},
                {"step_name":"Pick, Pack & Ship","step_type":"processing","agent_persona":"E-Commerce Operations Agent","integrations":["ShipStation"],"compliance_gates":[],"kpis":["fulfillment_accuracy","on_time_ship_rate"]},
                {"step_name":"Delivery Confirmation & Review Request","step_type":"communication","agent_persona":"E-Commerce Operations Agent","integrations":["Klaviyo"],"compliance_gates":["GDPR-marketing-consent"],"kpis":["CLV"]},
            ], triggers=["order_placed"], outputs=["shipped_order","tracking_number","review_request"]),
        WorkflowTemplate(template_id="WF-ECOM-002", name="Cart Abandonment Recovery", description="Recover abandoned carts via email/SMS sequences.",
            steps=[
                {"step_name":"Abandonment Detection","step_type":"automated_check","agent_persona":"E-Commerce Marketing Agent","integrations":["Shopify","Klaviyo"],"compliance_gates":["GDPR-consent","CAN-SPAM"],"kpis":["cart_abandonment_rate"]},
                {"step_name":"Recovery Sequence","step_type":"communication","agent_persona":"E-Commerce Marketing Agent","integrations":["Klaviyo"],"compliance_gates":["GDPR-consent"],"kpis":["recovery_revenue","CAC"]},
            ], triggers=["cart_abandoned_60min"], outputs=["recovered_order","campaign_report"]),
    ],
    agent_personas=[
        AgentPersona(persona_id="AP-ECOM-001", name="E-Commerce Operations Agent", role="Operations", domain="E-Commerce",
            capabilities=["order_management","inventory_sync","return_processing","carrier_management"], tools=["Shopify","ShipStation"], personality_traits=["efficient","accurate","customer-focused"]),
        AgentPersona(persona_id="AP-ECOM-002", name="E-Commerce Marketing Agent", role="Marketing", domain="E-Commerce",
            capabilities=["email_automation","segmentation","campaign_analytics","A/B_testing"], tools=["Klaviyo","Shopify"], personality_traits=["data-driven","creative","growth-oriented"]),
    ],
    integration_mappings=[
        IntegrationMapping(connector_name="Shopify", connector_type="ecommerce_platform", required=True, config_template={"shop_url":"","access_token":""}, purpose="Storefront, orders, and inventory."),
        IntegrationMapping(connector_name="ShipStation", connector_type="fulfillment", required=True, config_template={"api_key":"","api_secret":""}, purpose="Multi-carrier shipping and label generation."),
        IntegrationMapping(connector_name="Klaviyo", connector_type="email_marketing", required=True, config_template={"api_key":""}, purpose="Email/SMS marketing automation."),
        IntegrationMapping(connector_name="WooCommerce", connector_type="ecommerce_platform", required=False, config_template={"consumer_key":"","consumer_secret":""}, purpose="Alternative open-source storefront."),
    ],
    compliance_rules=[
        ComplianceRule(rule_id="CR-ECOM-001", standard="PCI DSS", description="Payment card data handling must comply with PCI DSS.", required_approvals=2, penalty_severity="critical", automated_check=True),
        ComplianceRule(rule_id="CR-ECOM-002", standard="GDPR/CCPA", description="Customer data collection requires consent and subject rights management.", required_approvals=1, penalty_severity="critical", automated_check=True),
    ],
    kpi_definitions=[
        KPIDefinition(kpi_id="KPI-ECOM-001", name="Customer Acquisition Cost", description="Total marketing spend divided by new customers.", unit="USD", target_value=30.0, warning_threshold=60.0, critical_threshold=100.0, measurement_method="marketing_spend/new_customers"),
        KPIDefinition(kpi_id="KPI-ECOM-002", name="Cart Abandonment Rate", description="Percentage of carts abandoned before purchase.", unit="%", target_value=65.0, warning_threshold=75.0, critical_threshold=85.0, measurement_method="abandoned_carts/initiated_carts*100"),
        KPIDefinition(kpi_id="KPI-ECOM-003", name="Fulfillment Accuracy", description="Percentage of orders fulfilled correctly.", unit="%", target_value=99.5, warning_threshold=98.0, critical_threshold=96.0, measurement_method="correct_orders/total_orders*100"),
    ],
)

BRICK_MORTAR_RETAIL = IndustryPreset(
    preset_id="PRESET-026", name="Brick & Mortar Retail", industry="Retail & Commerce", sub_industry="Retail Store",
    description="POS, inventory management, staffing, and loss prevention for physical retail.",
    version="1.0.0", tags=["retail","POS","inventory","staffing","loss-prevention"],
    compatible_with=["PRESET-025","PRESET-029"],
    workflow_templates=[
        WorkflowTemplate(template_id="WF-BMR-001", name="Daily Store Operations", description="Open, operate, and close store with inventory and staff management.",
            steps=[
                {"step_name":"Opening Inventory Count","step_type":"processing","agent_persona":"Retail Store Manager","integrations":["Square","Lightspeed"],"compliance_gates":[],"kpis":["inventory_accuracy"]},
                {"step_name":"Sales Floor & POS Operations","step_type":"processing","agent_persona":"Retail Store Manager","integrations":["Square"],"compliance_gates":["PCI-DSS"],"kpis":["same_store_sales_growth","inventory_turns"]},
                {"step_name":"End-of-Day Reconciliation","step_type":"automated_check","agent_persona":"Retail Store Manager","integrations":["Square","Lightspeed"],"compliance_gates":[],"kpis":["shrinkage_rate"]},
            ], triggers=["store_open","store_close"], outputs=["daily_sales_report","inventory_snapshot"]),
        WorkflowTemplate(template_id="WF-BMR-002", name="Staff Scheduling", description="Create and publish employee schedules aligned to sales forecast.",
            steps=[
                {"step_name":"Demand Forecast Pull","step_type":"automated_check","agent_persona":"Retail HR & Workforce Agent","integrations":["Lightspeed","ADP"],"compliance_gates":["labor-law-compliance"],"kpis":["labor_cost_pct"]},
                {"step_name":"Schedule Publication","step_type":"communication","agent_persona":"Retail HR & Workforce Agent","integrations":["ADP"],"compliance_gates":["predictive-scheduling-laws"],"kpis":["schedule_coverage"]},
            ], triggers=["weekly_schedule_cycle"], outputs=["published_schedule","labor_budget"]),
    ],
    agent_personas=[
        AgentPersona(persona_id="AP-BMR-001", name="Retail Store Manager", role="Store Manager", domain="Retail",
            capabilities=["POS_management","inventory_control","customer_service","loss_prevention"], tools=["Square","Lightspeed"], personality_traits=["organized","customer-centric","decisive"]),
        AgentPersona(persona_id="AP-BMR-002", name="Retail HR & Workforce Agent", role="HR Coordinator", domain="Retail",
            capabilities=["scheduling","payroll_coordination","onboarding","labor_law_compliance"], tools=["ADP","Lightspeed"], personality_traits=["fair","organized","compliant"]),
    ],
    integration_mappings=[
        IntegrationMapping(connector_name="Square", connector_type="POS", required=True, config_template={"access_token":"","location_id":""}, purpose="Point-of-sale, payments, and inventory."),
        IntegrationMapping(connector_name="Lightspeed", connector_type="POS", required=False, config_template={"api_key":""}, purpose="Alternative retail POS and inventory management."),
        IntegrationMapping(connector_name="ADP", connector_type="payroll_HR", required=True, config_template={"client_id":"","client_secret":""}, purpose="Payroll, scheduling, and HR management."),
        IntegrationMapping(connector_name="Verkada", connector_type="loss_prevention", required=False, config_template={"api_key":""}, purpose="Video surveillance and loss prevention."),
    ],
    compliance_rules=[
        ComplianceRule(rule_id="CR-BMR-001", standard="PCI DSS", description="Card present transactions must comply with PCI DSS.", required_approvals=2, penalty_severity="critical", automated_check=True),
        ComplianceRule(rule_id="CR-BMR-002", standard="State Labor Laws", description="Scheduling, breaks, and overtime must comply with state labor regulations.", required_approvals=1, penalty_severity="high", automated_check=True),
    ],
    kpi_definitions=[
        KPIDefinition(kpi_id="KPI-BMR-001", name="Same-Store Sales Growth", description="Year-over-year sales growth for comparable stores.", unit="%", target_value=5.0, warning_threshold=0.0, critical_threshold=-5.0, measurement_method="(current_sales-prior_sales)/prior_sales*100"),
        KPIDefinition(kpi_id="KPI-BMR-002", name="Inventory Turns", description="Times inventory is sold and replaced per year.", unit="turns", target_value=8.0, warning_threshold=5.0, critical_threshold=3.0, measurement_method="COGS/avg_inventory"),
        KPIDefinition(kpi_id="KPI-BMR-003", name="Shrinkage Rate", description="Inventory lost to theft/damage as % of sales.", unit="%", target_value=1.0, warning_threshold=2.0, critical_threshold=3.5, measurement_method="shrinkage/total_sales*100"),
    ],
)

RESTAURANT = IndustryPreset(
    preset_id="PRESET-027", name="Restaurant", industry="Retail & Commerce", sub_industry="Restaurant",
    description="Order management, kitchen display, inventory, and reservation systems for food service.",
    version="1.0.0", tags=["restaurant","F&B","POS","reservations","kitchen","health-codes"],
    compatible_with=["PRESET-012","PRESET-028"],
    workflow_templates=[
        WorkflowTemplate(template_id="WF-REST-001", name="Table Service Flow", description="Reservation to POS order to kitchen to payment.",
            steps=[
                {"step_name":"Reservation & Seating","step_type":"scheduling","agent_persona":"Restaurant Operations Agent","integrations":["Toast","OpenTable"],"compliance_gates":["ADA-accessibility"],"kpis":["table_turns"]},
                {"step_name":"Order Taking & KDS","step_type":"processing","agent_persona":"Restaurant Operations Agent","integrations":["Toast"],"compliance_gates":["allergen-disclosure"],"kpis":["ticket_time"]},
                {"step_name":"Payment Processing","step_type":"integration_action","agent_persona":"Restaurant Operations Agent","integrations":["Toast"],"compliance_gates":["PCI-DSS"],"kpis":["average_check"]},
            ], triggers=["reservation_confirmed","walk_in"], outputs=["paid_check","table_cleared"]),
        WorkflowTemplate(template_id="WF-REST-002", name="Inventory & COGS Management", description="Track inventory, calculate food cost, and manage supplier orders.",
            steps=[
                {"step_name":"Daily Inventory Count","step_type":"processing","agent_persona":"Restaurant Back-of-House Agent","integrations":["Sysco","Toast"],"compliance_gates":["health-code-storage"],"kpis":["food_cost_pct"]},
                {"step_name":"Supplier Order Placement","step_type":"integration_action","agent_persona":"Restaurant Back-of-House Agent","integrations":["Sysco"],"compliance_gates":[],"kpis":["waste_pct"]},
            ], triggers=["daily_inventory","par_level_alert"], outputs=["purchase_order","COGS_report"]),
    ],
    agent_personas=[
        AgentPersona(persona_id="AP-REST-001", name="Restaurant Operations Agent", role="Front-of-House Manager", domain="Restaurant",
            capabilities=["reservation_management","table_management","POS_operations","customer_service"], tools=["Toast","OpenTable"], personality_traits=["hospitable","fast-paced","organized"]),
        AgentPersona(persona_id="AP-REST-002", name="Restaurant Back-of-House Agent", role="Kitchen Manager", domain="Restaurant",
            capabilities=["inventory_management","COGS_tracking","supplier_management","food_safety"], tools=["Sysco","Toast"], personality_traits=["efficiency-focused","food-safety-conscious","detail-oriented"]),
    ],
    integration_mappings=[
        IntegrationMapping(connector_name="Toast", connector_type="POS", required=True, config_template={"client_id":"","client_secret":""}, purpose="Restaurant POS, KDS, and reporting."),
        IntegrationMapping(connector_name="OpenTable", connector_type="reservations", required=True, config_template={"api_key":"","restaurant_id":""}, purpose="Online reservations and waitlist management."),
        IntegrationMapping(connector_name="Sysco", connector_type="food_supplier", required=False, config_template={"account_number":""}, purpose="Food and beverage supply ordering."),
        IntegrationMapping(connector_name="7Shifts", connector_type="scheduling", required=False, config_template={"api_key":""}, purpose="Restaurant staff scheduling and labor management."),
    ],
    compliance_rules=[
        ComplianceRule(rule_id="CR-REST-001", standard="Local Health Codes", description="Food handling, storage, and preparation must meet local health department standards.", required_approvals=1, penalty_severity="critical", automated_check=False),
        ComplianceRule(rule_id="CR-REST-002", standard="ADA Accessibility", description="Restaurant facilities must meet ADA accessibility requirements.", required_approvals=1, penalty_severity="high", automated_check=False),
    ],
    kpi_definitions=[
        KPIDefinition(kpi_id="KPI-REST-001", name="Table Turns per Shift", description="Average tables served per shift per server.", unit="turns", target_value=4.0, warning_threshold=3.0, critical_threshold=2.0, measurement_method="tables_served/server_shifts"),
        KPIDefinition(kpi_id="KPI-REST-002", name="Food Cost Percentage", description="Food cost as % of food revenue.", unit="%", target_value=28.0, warning_threshold=33.0, critical_threshold=38.0, measurement_method="food_cost/food_revenue*100"),
        KPIDefinition(kpi_id="KPI-REST-003", name="Labor Cost Percentage", description="Labor cost as % of total revenue.", unit="%", target_value=30.0, warning_threshold=35.0, critical_threshold=40.0, measurement_method="labor_cost/total_revenue*100"),
    ],
)

GROCERY = IndustryPreset(
    preset_id="PRESET-028", name="Grocery Store", industry="Retail & Commerce", sub_industry="Grocery",
    description="Perishable inventory, supply chain, pricing management, and food safety compliance.",
    version="1.0.0", tags=["grocery","perishables","inventory","FDA","FSMA","supply-chain"],
    compatible_with=["PRESET-012","PRESET-027"],
    workflow_templates=[
        WorkflowTemplate(template_id="WF-GROC-001", name="Perishable Inventory Management", description="Track expiry dates, rotate stock, and manage waste.",
            steps=[
                {"step_name":"Receiving & Date Check","step_type":"processing","agent_persona":"Grocery Operations Agent","integrations":["NCR"],"compliance_gates":["FDA-FSMA-traceability"],"kpis":["waste_pct","out_of_stock_rate"]},
                {"step_name":"FIFO Rotation & Markdown","step_type":"processing","agent_persona":"Grocery Operations Agent","integrations":["Symphony EYC","NCR"],"compliance_gates":["health-code-temperature"],"kpis":["waste_pct"]},
            ], triggers=["receiving_event","daily_inventory"], outputs=["inventory_report","markdown_list"]),
        WorkflowTemplate(template_id="WF-GROC-002", name="Category Pricing Management", description="Competitive pricing analysis and margin optimization by category.",
            steps=[
                {"step_name":"Competitive Price Scan","step_type":"automated_check","agent_persona":"Grocery Category Manager","integrations":["Symphony EYC"],"compliance_gates":[],"kpis":["margin_by_category"]},
                {"step_name":"Price Update & Signage","step_type":"integration_action","agent_persona":"Grocery Category Manager","integrations":["NCR","Symphony EYC"],"compliance_gates":["price-accuracy-laws"],"kpis":["price_accuracy"]},
            ], triggers=["weekly_price_review","competitor_change"], outputs=["price_update","category_margin_report"]),
    ],
    agent_personas=[
        AgentPersona(persona_id="AP-GROC-001", name="Grocery Operations Agent", role="Store Operations", domain="Grocery",
            capabilities=["receiving","inventory_management","FIFO_rotation","freshness_monitoring"], tools=["NCR","Symphony EYC"], personality_traits=["food-safety-conscious","organized","efficient"]),
        AgentPersona(persona_id="AP-GROC-002", name="Grocery Category Manager", role="Category Manager", domain="Grocery",
            capabilities=["pricing_strategy","vendor_negotiations","planogram_management","promotion_planning"], tools=["Symphony EYC","NCR"], personality_traits=["analytical","market-aware","margin-focused"]),
    ],
    integration_mappings=[
        IntegrationMapping(connector_name="NCR", connector_type="POS", required=True, config_template={"api_key":"","store_id":""}, purpose="Grocery POS, loyalty, and inventory."),
        IntegrationMapping(connector_name="Symphony EYC", connector_type="pricing_analytics", required=True, config_template={"api_key":""}, purpose="Category management and competitive pricing."),
        IntegrationMapping(connector_name="Instacart", connector_type="delivery_marketplace", required=False, config_template={"api_key":""}, purpose="Online grocery delivery marketplace."),
    ],
    compliance_rules=[
        ComplianceRule(rule_id="CR-GROC-001", standard="FDA FSMA Traceability Rule", description="Key data elements must be captured at each step of the food supply chain.", required_approvals=2, penalty_severity="critical", automated_check=True),
        ComplianceRule(rule_id="CR-GROC-002", standard="State Weights & Measures", description="All price scanners and scales must be tested and certified by state W&M.", required_approvals=1, penalty_severity="high", automated_check=False),
    ],
    kpi_definitions=[
        KPIDefinition(kpi_id="KPI-GROC-001", name="Waste Percentage", description="Perishable product waste as % of department sales.", unit="%", target_value=3.0, warning_threshold=6.0, critical_threshold=10.0, measurement_method="waste_value/sales*100"),
        KPIDefinition(kpi_id="KPI-GROC-002", name="Out-of-Stock Rate", description="% of SKUs out of stock at any point during operating hours.", unit="%", target_value=2.0, warning_threshold=5.0, critical_threshold=8.0, measurement_method="oos_sku_hours/total_sku_hours*100"),
        KPIDefinition(kpi_id="KPI-GROC-003", name="Gross Margin by Category", description="Gross margin % by merchandise category.", unit="%", target_value=30.0, warning_threshold=24.0, critical_threshold=18.0, measurement_method="(sales-COGS)/sales*100"),
    ],
)

FRANCHISE = IndustryPreset(
    preset_id="PRESET-029", name="Franchise Business", industry="Retail & Commerce", sub_industry="Franchise",
    description="Multi-location management, brand compliance auditing, and royalty collection.",
    version="1.0.0", tags=["franchise","multi-location","brand-compliance","royalties","FranConnect"],
    compatible_with=["PRESET-026","PRESET-027"],
    workflow_templates=[
        WorkflowTemplate(template_id="WF-FRAN-001", name="Franchisee Compliance Audit", description="Schedule, conduct, and score brand compliance audits.",
            steps=[
                {"step_name":"Audit Scheduling","step_type":"scheduling","agent_persona":"Franchise Operations Manager","integrations":["FranConnect"],"compliance_gates":["franchise-agreement-audit-requirements"],"kpis":["audit_compliance_score"]},
                {"step_name":"On-site or Virtual Audit","step_type":"human_review","agent_persona":"Franchise Operations Manager","integrations":["FranConnect","Zendesk"],"compliance_gates":["brand-standards"],"kpis":["audit_compliance_score"]},
                {"step_name":"Corrective Action Follow-up","step_type":"communication","agent_persona":"Franchise Operations Manager","integrations":["FranConnect"],"compliance_gates":[],"kpis":["CAP_closure_rate"]},
            ], triggers=["scheduled_audit_cycle","complaint_received"], outputs=["audit_report","CAP","franchise_scorecard"]),
        WorkflowTemplate(template_id="WF-FRAN-002", name="Royalty Billing & Collection", description="Calculate, invoice, and collect royalties from franchisees.",
            steps=[
                {"step_name":"Sales Reporting Ingestion","step_type":"automated_check","agent_persona":"Franchise Finance Agent","integrations":["FranConnect","Salesforce"],"compliance_gates":["franchise-agreement-reporting"],"kpis":["royalty_collection_rate"]},
                {"step_name":"Royalty Invoice Generation","step_type":"document_generation","agent_persona":"Franchise Finance Agent","integrations":["FranConnect"],"compliance_gates":[],"kpis":["royalty_collection_rate","days_to_payment"]},
            ], triggers=["weekly_sales_report_due"], outputs=["royalty_invoice","collection_report"]),
    ],
    agent_personas=[
        AgentPersona(persona_id="AP-FRAN-001", name="Franchise Operations Manager", role="Operations Manager", domain="Franchise",
            capabilities=["compliance_auditing","training_delivery","opening_support","performance_coaching"], tools=["FranConnect","Zendesk"], personality_traits=["supportive","standards-driven","organized"]),
        AgentPersona(persona_id="AP-FRAN-002", name="Franchise Finance Agent", role="Finance Coordinator", domain="Franchise",
            capabilities=["royalty_calculation","invoicing","collections","financial_benchmarking"], tools=["FranConnect","Salesforce"], personality_traits=["precise","process-driven","firm"]),
    ],
    integration_mappings=[
        IntegrationMapping(connector_name="FranConnect", connector_type="franchise_management", required=True, config_template={"api_key":"","tenant_id":""}, purpose="Franchise management, audits, and royalty tracking."),
        IntegrationMapping(connector_name="Salesforce", connector_type="crm", required=True, config_template={"client_id":"","instance_url":""}, purpose="Franchisee CRM and performance tracking."),
        IntegrationMapping(connector_name="Zendesk", connector_type="support", required=False, config_template={"api_key":""}, purpose="Franchisee support ticketing."),
    ],
    compliance_rules=[
        ComplianceRule(rule_id="CR-FRAN-001", standard="FTC Franchise Rule", description="Franchise Disclosure Document must be provided 14 days before signing per FTC rules.", required_approvals=2, penalty_severity="critical", automated_check=False),
        ComplianceRule(rule_id="CR-FRAN-002", standard="Brand Standards Agreement", description="Franchisees must operate in accordance with the current Operations Manual.", required_approvals=1, penalty_severity="high", automated_check=True),
    ],
    kpi_definitions=[
        KPIDefinition(kpi_id="KPI-FRAN-001", name="Franchisee Performance Score", description="Composite score from sales, compliance, and customer satisfaction.", unit="score", target_value=85.0, warning_threshold=70.0, critical_threshold=55.0, measurement_method="weighted_avg(sales_score,compliance_score,csat_score)"),
        KPIDefinition(kpi_id="KPI-FRAN-002", name="Royalty Collection Rate", description="% of invoiced royalties collected on time.", unit="%", target_value=98.0, warning_threshold=94.0, critical_threshold=88.0, measurement_method="collected_royalties/invoiced_royalties*100"),
        KPIDefinition(kpi_id="KPI-FRAN-003", name="Audit Compliance Score", description="Average brand compliance audit score across all locations.", unit="score", target_value=90.0, warning_threshold=80.0, critical_threshold=70.0, measurement_method="avg(audit_scores)"),
    ],
)

ALL_RETAIL_PRESETS: List[IndustryPreset] = [ECOMMERCE, BRICK_MORTAR_RETAIL, RESTAURANT, GROCERY, FRANCHISE]
