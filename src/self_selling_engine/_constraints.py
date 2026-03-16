"""Business-type constraint registry for the self-selling pipeline.

Copyright © 2020 Inoni Limited Liability Company
License: BSL 1.1
"""

from __future__ import annotations
import logging

from typing import Any, Dict

# ---------------------------------------------------------------------------
# Business-type constraint registry
# ---------------------------------------------------------------------------

BUSINESS_TYPE_CONSTRAINTS: Dict[str, Dict[str, Any]] = {
    "consulting": {
        "display_name": "Professional Services / Consulting",
        "revenue_model": "billable_hours",
        "primary_constraints": [
            {"metric": "billable_utilization", "comparator": "gte", "threshold": 0.65,
             "unit": "ratio", "impact": "revenue"},
            {"metric": "pipeline_fill_rate", "comparator": "gte", "threshold": 0.50,
             "unit": "ratio", "impact": "growth"},
            {"metric": "proposal_turnaround_days", "comparator": "lte", "threshold": 3,
             "unit": "days", "impact": "conversion"},
            {"metric": "client_satisfaction_score", "comparator": "gte", "threshold": 4.0,
             "unit": "score_5", "impact": "retention"},
        ],
        "automation_opportunities": [
            "proposal_generation", "time_tracking", "invoice_automation", "follow_up_sequences",
        ],
    },
    "ecommerce": {
        "display_name": "E-Commerce Store",
        "revenue_model": "product_sales",
        "primary_constraints": [
            {"metric": "cart_abandonment_rate", "comparator": "lte", "threshold": 0.70,
             "unit": "ratio", "impact": "revenue"},
            {"metric": "order_fulfillment_hours", "comparator": "lte", "threshold": 24,
             "unit": "hours", "impact": "satisfaction"},
            {"metric": "return_rate", "comparator": "lte", "threshold": 0.10,
             "unit": "ratio", "impact": "margin"},
            {"metric": "customer_repeat_rate", "comparator": "gte", "threshold": 0.30,
             "unit": "ratio", "impact": "ltv"},
        ],
        "automation_opportunities": [
            "cart_recovery_emails", "inventory_reorder", "review_requests", "dynamic_pricing",
        ],
    },
    "law_firm": {
        "display_name": "Law Firm / Legal Practice",
        "revenue_model": "billable_hours",
        "primary_constraints": [
            {"metric": "billable_hours_per_attorney_annual", "comparator": "gte",
             "threshold": 1600, "unit": "hours", "impact": "revenue"},
            {"metric": "case_intake_response_hours", "comparator": "lte", "threshold": 4,
             "unit": "hours", "impact": "conversion"},
            {"metric": "document_review_hours_saved_pct", "comparator": "gte",
             "threshold": 0.40, "unit": "ratio", "impact": "efficiency"},
            {"metric": "invoice_collection_days", "comparator": "lte", "threshold": 30,
             "unit": "days", "impact": "cash_flow"},
        ],
        "automation_opportunities": [
            "client_intake_automation", "document_review_ai", "billing_automation",
            "deadline_tracking",
        ],
    },
    "restaurant": {
        "display_name": "Restaurant / Food Service",
        "revenue_model": "transaction_volume",
        "primary_constraints": [
            {"metric": "food_cost_pct", "comparator": "lte", "threshold": 0.32,
             "unit": "ratio", "impact": "margin"},
            {"metric": "table_turn_time_minutes", "comparator": "lte", "threshold": 75,
             "unit": "minutes", "impact": "capacity"},
            {"metric": "online_order_response_minutes", "comparator": "lte", "threshold": 5,
             "unit": "minutes", "impact": "satisfaction"},
            {"metric": "waste_pct", "comparator": "lte", "threshold": 0.05,
             "unit": "ratio", "impact": "margin"},
        ],
        "automation_opportunities": [
            "online_order_routing", "inventory_management", "staff_scheduling",
            "review_response",
        ],
    },
    "real_estate": {
        "display_name": "Real Estate Agency",
        "revenue_model": "commission",
        "primary_constraints": [
            {"metric": "lead_response_minutes", "comparator": "lte", "threshold": 5,
             "unit": "minutes", "impact": "conversion"},
            {"metric": "listings_per_agent", "comparator": "gte", "threshold": 8,
             "unit": "count", "impact": "revenue"},
            {"metric": "days_on_market_vs_avg", "comparator": "lte", "threshold": 1.0,
             "unit": "ratio", "impact": "client_satisfaction"},
            {"metric": "lead_nurture_followup_days", "comparator": "lte", "threshold": 1,
             "unit": "days", "impact": "pipeline"},
        ],
        "automation_opportunities": [
            "lead_response_automation", "listing_syndication", "market_report_generation",
            "drip_campaigns",
        ],
    },
    "medical_practice": {
        "display_name": "Medical Practice / Healthcare",
        "revenue_model": "fee_for_service",
        "primary_constraints": [
            {"metric": "patient_no_show_rate", "comparator": "lte", "threshold": 0.10,
             "unit": "ratio", "impact": "revenue"},
            {"metric": "claim_denial_rate", "comparator": "lte", "threshold": 0.05,
             "unit": "ratio", "impact": "cash_flow"},
            {"metric": "appointment_fill_rate", "comparator": "gte", "threshold": 0.85,
             "unit": "ratio", "impact": "capacity"},
            {"metric": "patient_wait_time_minutes", "comparator": "lte", "threshold": 20,
             "unit": "minutes", "impact": "satisfaction"},
        ],
        "automation_opportunities": [
            "appointment_reminders", "insurance_verification", "intake_forms",
            "post_visit_followup",
        ],
    },
    "trades_contractor": {
        "display_name": "Trades / Contractor",
        "revenue_model": "project_fees",
        "primary_constraints": [
            {"metric": "quote_response_hours", "comparator": "lte", "threshold": 4,
             "unit": "hours", "impact": "conversion"},
            {"metric": "job_completion_vs_estimate_ratio", "comparator": "lte",
             "threshold": 1.10, "unit": "ratio", "impact": "margin"},
            {"metric": "invoice_collection_days", "comparator": "lte", "threshold": 30,
             "unit": "days", "impact": "cash_flow"},
            {"metric": "customer_referral_rate", "comparator": "gte", "threshold": 0.25,
             "unit": "ratio", "impact": "growth"},
        ],
        "automation_opportunities": [
            "quote_generation", "job_scheduling", "invoice_automation", "review_solicitation",
        ],
    },
    "saas": {
        "display_name": "SaaS Company",
        "revenue_model": "subscription_mrr",
        "primary_constraints": [
            {"metric": "trial_to_paid_rate", "comparator": "gte", "threshold": 0.15,
             "unit": "ratio", "impact": "revenue"},
            {"metric": "monthly_churn_rate", "comparator": "lte", "threshold": 0.05,
             "unit": "ratio", "impact": "revenue"},
            {"metric": "support_response_hours", "comparator": "lte", "threshold": 2,
             "unit": "hours", "impact": "retention"},
            {"metric": "feature_adoption_rate", "comparator": "gte", "threshold": 0.40,
             "unit": "ratio", "impact": "expansion"},
        ],
        "automation_opportunities": [
            "onboarding_sequences", "churn_prediction_alerts", "support_ticket_routing",
            "expansion_revenue_triggers",
        ],
    },
    "marketing_agency": {
        "display_name": "Marketing Agency",
        "revenue_model": "retainer_project",
        "primary_constraints": [
            {"metric": "campaign_roi", "comparator": "gte", "threshold": 2.0,
             "unit": "ratio", "impact": "client_retention"},
            {"metric": "client_retention_rate", "comparator": "gte", "threshold": 0.85,
             "unit": "ratio", "impact": "revenue"},
            {"metric": "deliverable_on_time_rate", "comparator": "gte", "threshold": 0.90,
             "unit": "ratio", "impact": "satisfaction"},
            {"metric": "new_business_pipeline_value", "comparator": "gte",
             "threshold": 50000, "unit": "usd", "impact": "growth"},
        ],
        "automation_opportunities": [
            "report_generation", "content_scheduling", "lead_tracking",
            "client_communication_sequences",
        ],
    },
    "accounting_firm": {
        "display_name": "Accounting / CPA Firm",
        "revenue_model": "billable_hours_retainer",
        "primary_constraints": [
            {"metric": "tax_return_throughput_per_staff_day", "comparator": "gte",
             "threshold": 3.0, "unit": "count", "impact": "revenue"},
            {"metric": "client_document_collection_days", "comparator": "lte",
             "threshold": 7, "unit": "days", "impact": "efficiency"},
            {"metric": "audit_finding_rate", "comparator": "lte", "threshold": 0.02,
             "unit": "ratio", "impact": "quality"},
            {"metric": "client_retention_rate", "comparator": "gte", "threshold": 0.90,
             "unit": "ratio", "impact": "revenue"},
        ],
        "automation_opportunities": [
            "document_collection_reminders", "tax_prep_workflow", "compliance_calendar",
            "client_portal_automation",
        ],
    },
    "logistics": {
        "display_name": "Logistics / Supply Chain",
        "revenue_model": "per_shipment_contract",
        "primary_constraints": [
            {"metric": "on_time_delivery_rate", "comparator": "gte", "threshold": 0.95,
             "unit": "ratio", "impact": "client_retention"},
            {"metric": "cost_per_mile", "comparator": "lte", "threshold": 2.50,
             "unit": "usd", "impact": "margin"},
            {"metric": "empty_miles_pct", "comparator": "lte", "threshold": 0.15,
             "unit": "ratio", "impact": "efficiency"},
            {"metric": "driver_utilization_rate", "comparator": "gte", "threshold": 0.80,
             "unit": "ratio", "impact": "capacity"},
        ],
        "automation_opportunities": [
            "route_optimization", "load_matching", "delivery_notifications",
            "invoice_automation",
        ],
    },
    "education": {
        "display_name": "Education / EdTech",
        "revenue_model": "tuition_subscription",
        "primary_constraints": [
            {"metric": "student_completion_rate", "comparator": "gte", "threshold": 0.70,
             "unit": "ratio", "impact": "outcomes"},
            {"metric": "enrollment_conversion_rate", "comparator": "gte", "threshold": 0.25,
             "unit": "ratio", "impact": "revenue"},
            {"metric": "instructor_response_hours", "comparator": "lte", "threshold": 24,
             "unit": "hours", "impact": "satisfaction"},
            {"metric": "content_freshness_days", "comparator": "lte", "threshold": 90,
             "unit": "days", "impact": "quality"},
        ],
        "automation_opportunities": [
            "enrollment_drip_campaigns", "progress_nudges", "instructor_routing",
            "certificate_generation",
        ],
    },
}

