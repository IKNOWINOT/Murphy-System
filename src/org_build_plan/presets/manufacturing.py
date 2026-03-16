# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Manufacturing industry preset for the org_build_plan package."""

from __future__ import annotations
import logging

from ..presets import IndustryPreset

PRESET = IndustryPreset(
    preset_id="manufacturing",
    name="Manufacturing",
    description=(
        "Union-based manufacturing organization with SCADA integration, "
        "safety compliance, and production quality control workflows."
    ),
    industry="manufacturing",
    default_org_type="corporation",
    default_labor_model="union",
    default_company_size="medium",
    recommended_connectors=[
        "scada_modbus",
        "scada_bacnet",
        "additive_manufacturing",
        "solidworks",
        "fusion360",
        "autocad",
        "quickbooks",
    ],
    recommended_frameworks=["OSHA", "EPA"],
    default_departments=[
        {
            "name": "operations",
            "head_name": "Director of Operations",
            "head_email": "ops@company.com",
            "headcount": 30,
            "level": "director",
            "responsibilities": ["production", "floor_management", "scheduling"],
            "automation_priorities": ["factory_iot", "data"],
        },
        {
            "name": "engineering",
            "head_name": "VP of Engineering",
            "head_email": "engineering@company.com",
            "headcount": 20,
            "level": "vp",
            "responsibilities": ["design", "cad", "process_improvement"],
            "automation_priorities": ["factory_iot", "system"],
        },
        {
            "name": "safety",
            "head_name": "Safety Manager",
            "head_email": "safety@company.com",
            "headcount": 5,
            "level": "manager",
            "responsibilities": ["osha_compliance", "incident_reporting", "training"],
            "automation_priorities": ["data", "agent"],
        },
        {
            "name": "finance",
            "head_name": "CFO",
            "head_email": "finance@company.com",
            "headcount": 8,
            "level": "c_suite",
            "responsibilities": ["budgeting", "payroll", "reporting"],
            "automation_priorities": ["business", "data"],
        },
        {
            "name": "logistics",
            "head_name": "Logistics Manager",
            "head_email": "logistics@company.com",
            "headcount": 15,
            "level": "manager",
            "responsibilities": ["supply_chain", "shipping", "inventory"],
            "automation_priorities": ["data", "business"],
        },
    ],
    workflow_templates=[
        {
            "template_id": "mfg_safety_monitoring",
            "name": "Safety Monitoring",
            "description": "Automated OSHA safety monitoring and incident alerts",
            "category": "safety",
            "steps": [
                {
                    "step_id": "collect_sensor_data",
                    "name": "Collect Sensor Data",
                    "action": "scada_modbus.read_sensors",
                    "depends_on": [],
                    "description": "Read safety sensor data from SCADA",
                },
                {
                    "step_id": "evaluate_thresholds",
                    "name": "Evaluate Safety Thresholds",
                    "action": "compliance_engine.check_osha",
                    "depends_on": ["collect_sensor_data"],
                    "description": "Check readings against OSHA thresholds",
                },
                {
                    "step_id": "send_alert",
                    "name": "Send Safety Alert",
                    "action": "notify.safety_team",
                    "depends_on": ["evaluate_thresholds"],
                    "description": "Alert safety team if thresholds exceeded",
                },
            ],
        },
        {
            "template_id": "mfg_production_qc",
            "name": "Production QC",
            "description": "Quality control checks on production output",
            "category": "manufacturing",
            "steps": [
                {
                    "step_id": "sample_units",
                    "name": "Sample Production Units",
                    "action": "operations.sample_batch",
                    "depends_on": [],
                    "description": "Select sample units from production run",
                },
                {
                    "step_id": "run_qc_checks",
                    "name": "Run QC Checks",
                    "action": "operations.quality_check",
                    "depends_on": ["sample_units"],
                    "description": "Execute quality tests on sampled units",
                },
                {
                    "step_id": "log_results",
                    "name": "Log QC Results",
                    "action": "data.log_qc_results",
                    "depends_on": ["run_qc_checks"],
                    "description": "Record QC results for traceability",
                },
            ],
        },
        {
            "template_id": "mfg_equipment_maintenance",
            "name": "Equipment Maintenance Schedule",
            "description": "Preventive maintenance scheduling and tracking",
            "category": "operations",
            "steps": [
                {
                    "step_id": "check_maintenance_due",
                    "name": "Check Maintenance Due",
                    "action": "scada_modbus.check_run_hours",
                    "depends_on": [],
                    "description": "Query equipment run hours and maintenance schedule",
                },
                {
                    "step_id": "schedule_maintenance",
                    "name": "Schedule Maintenance",
                    "action": "operations.schedule_downtime",
                    "depends_on": ["check_maintenance_due"],
                    "description": "Schedule maintenance window",
                },
                {
                    "step_id": "notify_team",
                    "name": "Notify Maintenance Team",
                    "action": "notify.maintenance_team",
                    "depends_on": ["schedule_maintenance"],
                    "description": "Alert maintenance crew of upcoming work",
                },
            ],
        },
        {
            "template_id": "mfg_material_tracking",
            "name": "Material Tracking",
            "description": "Track raw material inventory and reorder points",
            "category": "operations",
            "steps": [
                {
                    "step_id": "scan_inventory",
                    "name": "Scan Inventory Levels",
                    "action": "inventory.scan_materials",
                    "depends_on": [],
                    "description": "Get current raw material inventory counts",
                },
                {
                    "step_id": "check_reorder",
                    "name": "Check Reorder Points",
                    "action": "inventory.check_reorder_levels",
                    "depends_on": ["scan_inventory"],
                    "description": "Identify materials below reorder threshold",
                },
                {
                    "step_id": "create_po",
                    "name": "Create Purchase Orders",
                    "action": "quickbooks.create_purchase_order",
                    "depends_on": ["check_reorder"],
                    "description": "Auto-generate POs for low-stock materials",
                },
            ],
        },
    ],
    setup_wizard_preset="org_onboarding",
)
