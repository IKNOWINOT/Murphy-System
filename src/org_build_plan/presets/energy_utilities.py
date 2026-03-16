# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Energy and utilities industry preset for the org_build_plan package."""

from __future__ import annotations
import logging

from ..presets import IndustryPreset

PRESET = IndustryPreset(
    preset_id="energy_utilities",
    name="Energy & Utilities",
    description=(
        "NERC/EPA/OSHA-hardened enterprise energy organization with SCADA "
        "integration, grid monitoring, and regulatory filing workflows."
    ),
    industry="energy",
    default_org_type="corporation",
    default_labor_model="union",
    default_company_size="enterprise",
    recommended_connectors=[
        "scada_modbus",
        "scada_bacnet",
        "scada_opcua",
        "johnson_controls_metasys",
        "honeywell_niagara",
        "schneider_ecostruxure",
        "power_bi",
    ],
    recommended_frameworks=["NERC", "EPA", "OSHA"],
    default_departments=[
        {
            "name": "grid_operations",
            "head_name": "VP of Grid Operations",
            "head_email": "grid@energy.com",
            "headcount": 50,
            "level": "vp",
            "responsibilities": ["grid_management", "load_balancing", "outage_response"],
            "automation_priorities": ["factory_iot", "data"],
        },
        {
            "name": "plant_maintenance",
            "head_name": "Director of Plant Maintenance",
            "head_email": "maintenance@energy.com",
            "headcount": 30,
            "level": "director",
            "responsibilities": ["equipment_maintenance", "safety_checks", "asset_management"],
            "automation_priorities": ["factory_iot", "system"],
        },
        {
            "name": "engineering",
            "head_name": "Chief Engineer",
            "head_email": "engineering@energy.com",
            "headcount": 25,
            "level": "director",
            "responsibilities": ["system_design", "capacity_planning", "technical_standards"],
            "automation_priorities": ["data", "system"],
        },
        {
            "name": "safety",
            "head_name": "VP of Safety",
            "head_email": "safety@energy.com",
            "headcount": 15,
            "level": "vp",
            "responsibilities": ["osha_compliance", "nerc_cip", "training", "incident_management"],
            "automation_priorities": ["data", "agent"],
        },
        {
            "name": "regulatory_affairs",
            "head_name": "Director of Regulatory Affairs",
            "head_email": "regulatory@energy.com",
            "headcount": 8,
            "level": "director",
            "responsibilities": ["regulatory_filings", "nerc_compliance", "epa_reporting"],
            "automation_priorities": ["agent", "data"],
        },
    ],
    workflow_templates=[
        {
            "template_id": "nrg_grid_monitoring",
            "name": "Grid Monitoring",
            "description": "Real-time SCADA grid health monitoring and alerting",
            "category": "energy",
            "steps": [
                {
                    "step_id": "poll_scada",
                    "name": "Poll SCADA Systems",
                    "action": "scada_modbus.read_grid_status",
                    "depends_on": [],
                    "description": "Read current grid load and equipment status",
                },
                {
                    "step_id": "analyze_stability",
                    "name": "Analyze Grid Stability",
                    "action": "data.analyze_grid_stability",
                    "depends_on": ["poll_scada"],
                    "description": "Check readings against NERC reliability standards",
                },
                {
                    "step_id": "alert_operators",
                    "name": "Alert Grid Operators",
                    "action": "notify.grid_ops_team",
                    "depends_on": ["analyze_stability"],
                    "description": "Notify operators of anomalies or near-violations",
                },
            ],
        },
        {
            "template_id": "nrg_carbon_capture",
            "name": "Carbon Capture Tracking",
            "description": "Track carbon capture metrics for EPA reporting",
            "category": "compliance",
            "steps": [
                {
                    "step_id": "read_capture_sensors",
                    "name": "Read Carbon Capture Sensors",
                    "action": "scada_opcua.read_capture_data",
                    "depends_on": [],
                    "description": "Get real-time carbon capture volumes from sensors",
                },
                {
                    "step_id": "calculate_credits",
                    "name": "Calculate Carbon Credits",
                    "action": "data.calculate_carbon_credits",
                    "depends_on": ["read_capture_sensors"],
                    "description": "Convert capture volumes to credit equivalents",
                },
                {
                    "step_id": "update_epa_log",
                    "name": "Update EPA Emissions Log",
                    "action": "compliance_engine.log_epa_data",
                    "depends_on": ["calculate_credits"],
                    "description": "Write to EPA-compliant emissions record",
                },
            ],
        },
        {
            "template_id": "nrg_energy_report",
            "name": "Energy Report",
            "description": "Monthly energy production and consumption reporting",
            "category": "energy",
            "steps": [
                {
                    "step_id": "collect_metering_data",
                    "name": "Collect Metering Data",
                    "action": "schneider_ecostruxure.get_energy_data",
                    "depends_on": [],
                    "description": "Pull energy metering data from building systems",
                },
                {
                    "step_id": "build_report",
                    "name": "Build Energy Report",
                    "action": "power_bi.generate_report",
                    "depends_on": ["collect_metering_data"],
                    "description": "Compile energy production and consumption report",
                },
                {
                    "step_id": "distribute",
                    "name": "Distribute to Management",
                    "action": "data.distribute_report",
                    "depends_on": ["build_report"],
                    "description": "Send report to executive team",
                },
            ],
        },
        {
            "template_id": "nrg_plant_maintenance",
            "name": "Plant Maintenance Schedule",
            "description": "Preventive maintenance scheduling for generation equipment",
            "category": "operations",
            "steps": [
                {
                    "step_id": "check_runtime",
                    "name": "Check Equipment Runtime",
                    "action": "honeywell_niagara.get_run_hours",
                    "depends_on": [],
                    "description": "Query runtime hours from building automation system",
                },
                {
                    "step_id": "identify_due",
                    "name": "Identify Maintenance Due",
                    "action": "data.check_maintenance_schedule",
                    "depends_on": ["check_runtime"],
                    "description": "Determine which assets are due for maintenance",
                },
                {
                    "step_id": "schedule_outage",
                    "name": "Schedule Planned Outage",
                    "action": "operations.schedule_outage",
                    "depends_on": ["identify_due"],
                    "description": "Coordinate planned outage window with grid ops",
                },
            ],
        },
        {
            "template_id": "nrg_regulatory_filing",
            "name": "Regulatory Filing",
            "description": "Automated NERC compliance filing preparation",
            "category": "compliance",
            "steps": [
                {
                    "step_id": "gather_data",
                    "name": "Gather Compliance Data",
                    "action": "compliance_engine.collect_nerc_data",
                    "depends_on": [],
                    "description": "Collect all data required for NERC filing",
                },
                {
                    "step_id": "validate_data",
                    "name": "Validate Data Completeness",
                    "action": "compliance_engine.validate_nerc_filing",
                    "depends_on": ["gather_data"],
                    "description": "Ensure all required fields are present and valid",
                },
                {
                    "step_id": "submit_filing",
                    "name": "Submit Regulatory Filing",
                    "action": "compliance_engine.submit_nerc_report",
                    "depends_on": ["validate_data"],
                    "description": "Submit completed filing to NERC portal",
                },
            ],
        },
    ],
    setup_wizard_preset="enterprise_compliance",
)
