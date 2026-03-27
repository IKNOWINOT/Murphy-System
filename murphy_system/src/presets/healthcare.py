"""
PRESET-035 through PRESET-040 — Healthcare Presets
Copyright 2024 Inoni LLC – BSL-1.1
"""
from __future__ import annotations
from typing import List
from src.presets.base import (
    AgentPersona, WorkflowTemplate, ComplianceRule,
    KPIDefinition, IntegrationMapping, IndustryPreset, make_preset,
)

HOSPITAL = make_preset(
    name="Hospital", industry="Healthcare", sub_industry="Hospital",
    description="Department orchestration, patient flow, EMR integration, compliance.",
    tags=["healthcare","hospital","EMR","HIPAA","Joint-Commission"],
    workflow_templates=[
        WorkflowTemplate(template_id="WT-HOSP-001", name="Patient Admission Flow",
            description="End-to-end patient admission from ED to floor.", steps=[
                {"step_name":"ED Triage","step_type":"assessment","agent_persona":"Triage Nurse Agent","integrations":["Epic","Cerner"],"compliance_gates":["EMTALA"],"kpis":["door_to_doctor_time"]},
                {"step_name":"Bed Assignment","step_type":"allocation","agent_persona":"Bed Management Agent","integrations":["Epic","TeleTracking"],"compliance_gates":["CMS-CoP"],"kpis":["bed_turnaround_time"]},
                {"step_name":"Care Team Notification","step_type":"notification","agent_persona":"Care Coordinator Agent","integrations":["Epic","Vocera"],"compliance_gates":["HIPAA"],"kpis":["notification_latency"]},
            ], triggers=["patient_arrival"], outputs=["admission_record","bed_assignment","care_plan"]),
        WorkflowTemplate(template_id="WT-HOSP-002", name="Discharge Planning",
            description="Coordinated patient discharge with follow-up.", steps=[
                {"step_name":"Discharge Assessment","step_type":"clinical_review","agent_persona":"Case Manager Agent","integrations":["Epic","Cerner"],"compliance_gates":["CMS-CoP","TJC"],"kpis":["LOS"]},
                {"step_name":"Insurance Authorization","step_type":"authorization","agent_persona":"Insurance Auth Agent","integrations":["Availity","Epic"],"compliance_gates":["HIPAA"],"kpis":["auth_turnaround_time"]},
            ], triggers=["physician_discharge_order"], outputs=["discharge_summary","follow_up_appointments","prescriptions"]),
    ],
    agent_personas=[
        AgentPersona(persona_id="AP-HOSP-001", name="Triage Nurse Agent", role="Triage", domain="Hospital",
            capabilities=["patient_assessment","acuity_scoring","EMR_documentation"], tools=["Epic","Cerner","Vocera"], personality_traits=["calm","decisive","protocol-driven"]),
        AgentPersona(persona_id="AP-HOSP-002", name="Bed Management Agent", role="Bed Manager", domain="Hospital",
            capabilities=["bed_tracking","capacity_planning","department_coordination"], tools=["TeleTracking","Epic"], personality_traits=["organized","proactive"]),
    ],
    integration_mappings=[
        IntegrationMapping(connector_name="Epic", connector_type="EMR", required=True, config_template={"base_url":"","client_id":"","client_secret":""}, purpose="Primary EMR system."),
        IntegrationMapping(connector_name="Cerner", connector_type="EMR", required=False, config_template={"base_url":"","api_key":""}, purpose="Alternative EMR system."),
        IntegrationMapping(connector_name="TeleTracking", connector_type="bed_management", required=False, config_template={"api_key":""}, purpose="Real-time bed tracking."),
    ],
    compliance_rules=[
        ComplianceRule(rule_id="CR-HOSP-001", standard="HIPAA", description="All PHI must be encrypted and access-logged.", required_approvals=1, penalty_severity="critical", automated_check=True),
        ComplianceRule(rule_id="CR-HOSP-002", standard="The Joint Commission", description="Meet TJC accreditation standards.", required_approvals=2, penalty_severity="critical", automated_check=False),
        ComplianceRule(rule_id="CR-HOSP-003", standard="EMTALA", description="Emergency treatment must not be denied.", required_approvals=1, penalty_severity="critical", automated_check=False),
    ],
    kpi_definitions=[
        KPIDefinition(kpi_id="KPI-HOSP-001", name="HCAHPS Score", description="Patient satisfaction composite.", unit="score", target_value=85.0, warning_threshold=75.0, critical_threshold=65.0, measurement_method="hcahps_survey_composite"),
        KPIDefinition(kpi_id="KPI-HOSP-002", name="Average Length of Stay", description="Mean patient LOS in days.", unit="days", target_value=4.2, warning_threshold=5.5, critical_threshold=7.0, measurement_method="total_patient_days/total_discharges"),
        KPIDefinition(kpi_id="KPI-HOSP-003", name="30-Day Readmission Rate", description="% patients readmitted within 30 days.", unit="%", target_value=10.0, warning_threshold=15.0, critical_threshold=20.0, measurement_method="readmissions_30d/total_discharges*100"),
    ],
)

CLINIC = make_preset(
    name="Clinic", industry="Healthcare", sub_industry="Outpatient Clinic",
    description="Scheduling, billing, referral management for outpatient clinics.",
    tags=["healthcare","clinic","HIPAA","billing"],
    workflow_templates=[
        WorkflowTemplate(template_id="WT-CLIN-001", name="Patient Scheduling & Check-In", description="Appointment scheduling to check-in.", steps=[
            {"step_name":"Appointment Booking","step_type":"scheduling","agent_persona":"Scheduling Agent","integrations":["eClinicalWorks","Kareo"],"compliance_gates":["HIPAA"],"kpis":["no_show_rate"]},
            {"step_name":"Insurance Eligibility Verification","step_type":"verification","agent_persona":"Billing Agent","integrations":["Availity","Kareo"],"compliance_gates":["HIPAA"],"kpis":["eligibility_check_time"]},
            {"step_name":"Check-In & Intake","step_type":"intake","agent_persona":"Front Desk Agent","integrations":["eClinicalWorks"],"compliance_gates":["HIPAA"],"kpis":["check_in_time"]},
        ], triggers=["patient_appointment_request"], outputs=["appointment","eligibility_response","intake_forms"]),
    ],
    agent_personas=[
        AgentPersona(persona_id="AP-CLIN-001", name="Scheduling Agent", role="Scheduler", domain="Clinic",
            capabilities=["appointment_management","patient_communication","schedule_optimization"], tools=["eClinicalWorks","Kareo"], personality_traits=["organized","friendly","efficient"]),
        AgentPersona(persona_id="AP-CLIN-002", name="Billing Agent", role="Biller", domain="Clinic",
            capabilities=["insurance_verification","claim_submission","denial_management"], tools=["Kareo","Availity"], personality_traits=["detail-oriented","persistent"]),
    ],
    integration_mappings=[
        IntegrationMapping(connector_name="eClinicalWorks", connector_type="EHR", required=True, config_template={"api_key":"","base_url":""}, purpose="EHR and scheduling."),
        IntegrationMapping(connector_name="Kareo", connector_type="billing", required=False, config_template={"api_key":""}, purpose="Medical billing platform."),
    ],
    compliance_rules=[
        ComplianceRule(rule_id="CR-CLIN-001", standard="HIPAA", description="PHI protection and minimum necessary standard.", required_approvals=1, penalty_severity="critical", automated_check=True),
        ComplianceRule(rule_id="CR-CLIN-002", standard="CMS Billing Rules", description="Correct coding initiative compliance.", required_approvals=1, penalty_severity="high", automated_check=True),
    ],
    kpi_definitions=[
        KPIDefinition(kpi_id="KPI-CLIN-001", name="No-Show Rate", description="% appointments not attended.", unit="%", target_value=8.0, warning_threshold=12.0, critical_threshold=20.0, measurement_method="no_shows/total_appointments*100"),
        KPIDefinition(kpi_id="KPI-CLIN-002", name="Clean Claim Rate", description="% claims accepted on first submission.", unit="%", target_value=95.0, warning_threshold=88.0, critical_threshold=80.0, measurement_method="clean_claims/total_claims*100"),
    ],
)

PHARMACY = make_preset(
    name="Pharmacy", industry="Healthcare", sub_industry="Pharmacy",
    description="Prescription management, inventory, compliance for retail/specialty pharmacy.",
    tags=["healthcare","pharmacy","DEA","compliance"],
    workflow_templates=[
        WorkflowTemplate(template_id="WT-PHARM-001", name="Prescription Fill Workflow", description="Intake to dispensing.", steps=[
            {"step_name":"Rx Intake & DUR","step_type":"intake","agent_persona":"Pharmacist Agent","integrations":["PioneerRx","McKesson"],"compliance_gates":["DEA-Schedule","State-Board"],"kpis":["fill_accuracy"]},
            {"step_name":"Insurance Adjudication","step_type":"adjudication","agent_persona":"Billing Agent","integrations":["PioneerRx","Cardinal_Health"],"compliance_gates":["HIPAA","PCI"],"kpis":["adjudication_time"]},
            {"step_name":"Dispense & Counsel","step_type":"dispensing","agent_persona":"Pharmacist Agent","integrations":["PioneerRx"],"compliance_gates":["State-Board","OBRA-90"],"kpis":["counseling_rate"]},
        ], triggers=["new_prescription"], outputs=["dispensed_rx","claim","counseling_record"]),
    ],
    agent_personas=[
        AgentPersona(persona_id="AP-PHARM-001", name="Pharmacist Agent", role="Pharmacist", domain="Pharmacy",
            capabilities=["drug_utilization_review","counseling","inventory_management","compounding"], tools=["PioneerRx","QS1","McKesson"], personality_traits=["precise","patient-focused","safety-conscious"]),
    ],
    integration_mappings=[
        IntegrationMapping(connector_name="PioneerRx", connector_type="pharmacy_system", required=True, config_template={"api_key":""}, purpose="Primary pharmacy management system."),
        IntegrationMapping(connector_name="McKesson", connector_type="drug_wholesaler", required=True, config_template={"account_number":"","api_key":""}, purpose="Drug procurement and ordering."),
    ],
    compliance_rules=[
        ComplianceRule(rule_id="CR-PHARM-001", standard="DEA Regulations", description="Controlled substance handling, scheduling, DEA Form 222.", required_approvals=2, penalty_severity="critical", automated_check=False),
        ComplianceRule(rule_id="CR-PHARM-002", standard="State Board of Pharmacy", description="State licensing and dispensing regulations.", required_approvals=1, penalty_severity="critical", automated_check=False),
    ],
    kpi_definitions=[
        KPIDefinition(kpi_id="KPI-PHARM-001", name="Prescription Fill Accuracy", description="% prescriptions filled without error.", unit="%", target_value=99.9, warning_threshold=99.5, critical_threshold=99.0, measurement_method="correct_fills/total_fills*100"),
        KPIDefinition(kpi_id="KPI-PHARM-002", name="Inventory Turns", description="Annual prescription inventory turn rate.", unit="turns/year", target_value=12.0, warning_threshold=8.0, critical_threshold=5.0, measurement_method="annual_cogs/avg_inventory"),
    ],
)

BIOTECH_LAB = make_preset(
    name="Biotech Lab", industry="Healthcare", sub_industry="Biotech",
    description="Lab management, experiment tracking, regulatory compliance.",
    tags=["healthcare","biotech","GLP","FDA"],
    workflow_templates=[
        WorkflowTemplate(template_id="WT-BIO-001", name="Experiment Lifecycle", description="Experiment from design to data lock.", steps=[
            {"step_name":"Protocol Design & Approval","step_type":"approval","agent_persona":"Study Director Agent","integrations":["Benchling","LabArchives"],"compliance_gates":["GLP","GCP"],"kpis":["protocol_approval_time"]},
            {"step_name":"Experiment Execution","step_type":"execution","agent_persona":"Lab Technician Agent","integrations":["Benchling","LIMS"],"compliance_gates":["21CFR58"],"kpis":["experiment_success_rate"]},
            {"step_name":"Data Review & Lock","step_type":"review","agent_persona":"QA Agent","integrations":["LabWare","Benchling"],"compliance_gates":["21CFR11","GLP"],"kpis":["data_integrity_incidents"]},
        ], triggers=["new_experiment_request"], outputs=["experiment_report","raw_data","QA_approval"]),
    ],
    agent_personas=[
        AgentPersona(persona_id="AP-BIO-001", name="Study Director Agent", role="Study Director", domain="Biotech",
            capabilities=["protocol_design","regulatory_strategy","resource_planning"], tools=["Benchling","LabArchives"], personality_traits=["methodical","detail-oriented","regulatory-savvy"]),
        AgentPersona(persona_id="AP-BIO-002", name="QA Agent", role="Quality Assurance", domain="Biotech",
            capabilities=["data_integrity_review","audit_trail_verification","deviation_management"], tools=["LabWare","MasterControl"], personality_traits=["thorough","compliance-focused"]),
    ],
    integration_mappings=[
        IntegrationMapping(connector_name="Benchling", connector_type="ELN", required=True, config_template={"api_key":"","tenant":""}, purpose="Electronic lab notebook and data capture."),
        IntegrationMapping(connector_name="LabWare", connector_type="LIMS", required=False, config_template={"base_url":"","api_key":""}, purpose="Laboratory information management system."),
    ],
    compliance_rules=[
        ComplianceRule(rule_id="CR-BIO-001", standard="GLP (21 CFR Part 58)", description="Good Laboratory Practice for nonclinical studies.", required_approvals=2, penalty_severity="critical", automated_check=True),
        ComplianceRule(rule_id="CR-BIO-002", standard="21 CFR Part 11", description="Electronic records and signatures compliance.", required_approvals=1, penalty_severity="critical", automated_check=True),
    ],
    kpi_definitions=[
        KPIDefinition(kpi_id="KPI-BIO-001", name="Experiment Success Rate", description="% experiments reaching primary endpoint.", unit="%", target_value=70.0, warning_threshold=50.0, critical_threshold=30.0, measurement_method="successful_experiments/total_experiments*100"),
        KPIDefinition(kpi_id="KPI-BIO-002", name="Regulatory Submission Timeline", description="Days from study completion to regulatory submission.", unit="days", target_value=90.0, warning_threshold=120.0, critical_threshold=180.0, measurement_method="submission_date-study_completion_date"),
    ],
)

ALL_HEALTHCARE_PRESETS: List[IndustryPreset] = [HOSPITAL, CLINIC, PHARMACY, BIOTECH_LAB]
