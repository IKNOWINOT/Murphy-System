# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Logistics and fleet industry preset for the org_build_plan package."""

from __future__ import annotations

from ..presets import IndustryPreset

PRESET = IndustryPreset(
    preset_id="logistics_fleet",
    name="Logistics & Fleet",
    description=(
        "DOT/FMCSA-compliant logistics organization with fleet dispatch, "
        "driver compliance, and vehicle maintenance workflows."
    ),
    industry="logistics",
    default_org_type="corporation",
    default_labor_model="union",
    default_company_size="medium",
    recommended_connectors=[
        "quickbooks",
        "slack",
        "clickup",
        "salesforce",
    ],
    recommended_frameworks=["DOT", "FMCSA", "OSHA"],
    default_departments=[
        {
            "name": "fleet_operations",
            "head_name": "Fleet Operations Manager",
            "head_email": "fleet@company.com",
            "headcount": 25,
            "level": "manager",
            "responsibilities": ["dispatch", "route_optimization", "driver_management"],
            "automation_priorities": ["data", "business"],
        },
        {
            "name": "dispatch",
            "head_name": "Dispatch Supervisor",
            "head_email": "dispatch@company.com",
            "headcount": 10,
            "level": "lead",
            "responsibilities": ["load_assignment", "driver_communication", "tracking"],
            "automation_priorities": ["data", "agent"],
        },
        {
            "name": "maintenance",
            "head_name": "Maintenance Manager",
            "head_email": "maintenance@company.com",
            "headcount": 12,
            "level": "manager",
            "responsibilities": ["vehicle_maintenance", "dot_inspections", "parts_inventory"],
            "automation_priorities": ["system", "data"],
        },
        {
            "name": "safety",
            "head_name": "Safety Director",
            "head_email": "safety@company.com",
            "headcount": 5,
            "level": "director",
            "responsibilities": ["fmcsa_compliance", "driver_training", "incident_reporting"],
            "automation_priorities": ["data", "agent"],
        },
        {
            "name": "administration",
            "head_name": "Operations Administrator",
            "head_email": "admin@company.com",
            "headcount": 6,
            "level": "manager",
            "responsibilities": ["billing", "hr", "compliance_reporting"],
            "automation_priorities": ["business", "data"],
        },
    ],
    workflow_templates=[
        {
            "template_id": "log_fleet_dispatch",
            "name": "Fleet Dispatch",
            "description": "Automated load assignment and driver dispatch",
            "category": "logistics",
            "steps": [
                {
                    "step_id": "receive_load",
                    "name": "Receive Load Order",
                    "action": "salesforce.get_new_orders",
                    "depends_on": [],
                    "description": "Pull incoming load orders from dispatch system",
                },
                {
                    "step_id": "assign_driver",
                    "name": "Assign Available Driver",
                    "action": "fleet.assign_driver",
                    "depends_on": ["receive_load"],
                    "description": "Match load to available compliant driver",
                },
                {
                    "step_id": "notify_driver",
                    "name": "Notify Driver",
                    "action": "slack.send_message",
                    "depends_on": ["assign_driver"],
                    "description": "Send dispatch notification to driver",
                },
            ],
        },
        {
            "template_id": "log_vehicle_maintenance",
            "name": "Vehicle Maintenance",
            "description": "DOT-compliant vehicle preventive maintenance scheduling",
            "category": "operations",
            "steps": [
                {
                    "step_id": "check_mileage",
                    "name": "Check Vehicle Mileage",
                    "action": "fleet.get_vehicle_mileage",
                    "depends_on": [],
                    "description": "Query telematics for vehicle mileage and hours",
                },
                {
                    "step_id": "schedule_service",
                    "name": "Schedule Service",
                    "action": "clickup.create_task",
                    "depends_on": ["check_mileage"],
                    "description": "Create maintenance task for shop",
                },
                {
                    "step_id": "update_dot_records",
                    "name": "Update DOT Records",
                    "action": "compliance_engine.update_dot_maintenance",
                    "depends_on": ["schedule_service"],
                    "description": "Log maintenance for DOT inspection records",
                },
            ],
        },
        {
            "template_id": "log_driver_compliance",
            "name": "Driver Compliance",
            "description": "FMCSA HOS and CSA compliance monitoring",
            "category": "compliance",
            "steps": [
                {
                    "step_id": "pull_eld_data",
                    "name": "Pull ELD Hours Data",
                    "action": "fleet.get_eld_hours",
                    "depends_on": [],
                    "description": "Retrieve electronic logging device HOS data",
                },
                {
                    "step_id": "check_violations",
                    "name": "Check for Violations",
                    "action": "compliance_engine.check_fmcsa_hos",
                    "depends_on": ["pull_eld_data"],
                    "description": "Identify HOS violations against FMCSA limits",
                },
                {
                    "step_id": "notify_safety",
                    "name": "Notify Safety Team",
                    "action": "slack.send_alert",
                    "depends_on": ["check_violations"],
                    "description": "Alert safety director of compliance issues",
                },
            ],
        },
        {
            "template_id": "log_route_optimization",
            "name": "Route Optimization",
            "description": "AI-driven route planning for fuel efficiency",
            "category": "logistics",
            "steps": [
                {
                    "step_id": "get_active_loads",
                    "name": "Get Active Loads",
                    "action": "fleet.list_active_loads",
                    "depends_on": [],
                    "description": "Retrieve all pending deliveries",
                },
                {
                    "step_id": "optimize_routes",
                    "name": "Optimize Routes",
                    "action": "data.optimize_routes",
                    "depends_on": ["get_active_loads"],
                    "description": "Calculate optimal routes minimizing fuel and time",
                },
                {
                    "step_id": "push_to_drivers",
                    "name": "Push Routes to Drivers",
                    "action": "fleet.update_driver_routes",
                    "depends_on": ["optimize_routes"],
                    "description": "Send optimized routes to driver apps",
                },
            ],
        },
    ],
    setup_wizard_preset="org_onboarding",
)
