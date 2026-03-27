"""
SBIR Phase I form definition.
© 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""
from __future__ import annotations

from src.billing.grants.form_filler.form_definitions.base import BaseFormDefinition
from src.billing.grants.form_filler.review_session import (
    FormDefinition,
    FormField,
    FormSection,
)


def _company_section() -> FormSection:
    return FormSection(section_id="company", title="Company Information", order=0)


def _project_section() -> FormSection:
    return FormSection(section_id="project", title="Project Information", order=1)


def _budget_section() -> FormSection:
    return FormSection(section_id="budget", title="Budget", order=2)


def _personnel_section() -> FormSection:
    return FormSection(section_id="personnel", title="Personnel", order=3)


def _cert_section() -> FormSection:
    return FormSection(section_id="certifications", title="Certifications", order=4)


def _company_fields():
    return [
        FormField(field_id="company_legal_name", label="Company Legal Name", field_type="text",
                  required=True, data_source_hint="company_info",
                  help_text="Full legal name as registered with IRS", section_id="company"),
        FormField(field_id="ein", label="EIN", field_type="text", required=True,
                  validation_regex=r"^\d{2}-\d{7}$", data_source_hint="company_info",
                  help_text="Format: XX-XXXXXXX", section_id="company"),
        FormField(field_id="uei", label="UEI", field_type="text", required=True,
                  data_source_hint="company_info",
                  help_text="Unique Entity Identifier from SAM.gov", section_id="company"),
        FormField(field_id="cage_code", label="CAGE Code", field_type="text", required=True,
                  data_source_hint="company_info",
                  help_text="Commercial and Government Entity Code", section_id="company"),
        FormField(field_id="address_street", label="Street Address", field_type="text",
                  required=True, data_source_hint="company_info", section_id="company"),
        FormField(field_id="address_city", label="City", field_type="text",
                  required=True, data_source_hint="company_info", section_id="company"),
        FormField(field_id="address_state", label="State", field_type="text",
                  required=True, data_source_hint="company_info", section_id="company"),
        FormField(field_id="address_zip", label="ZIP Code", field_type="text",
                  required=True, data_source_hint="company_info", section_id="company"),
        FormField(field_id="naics_code", label="NAICS Code", field_type="text",
                  required=True, data_source_hint="company_info",
                  help_text="Primary NAICS code", section_id="company"),
        FormField(field_id="employee_count", label="Employee Count", field_type="number",
                  required=True, data_source_hint="company_info", section_id="company"),
        FormField(field_id="formation_date", label="Formation Date", field_type="date",
                  required=True, data_source_hint="company_info", section_id="company"),
    ]


def _project_fields():
    return [
        FormField(field_id="project_title", label="Project Title", field_type="text",
                  required=True, max_length=200, data_source_hint="project_info",
                  section_id="project"),
        FormField(field_id="project_description", label="Project Description",
                  field_type="textarea", required=True, max_length=2000,
                  data_source_hint="project_info", section_id="project"),
        FormField(field_id="technical_approach", label="Technical Approach",
                  field_type="textarea", required=True, data_source_hint="technical",
                  section_id="project"),
        FormField(field_id="innovation_statement", label="Innovation Statement",
                  field_type="textarea", required=False, data_source_hint="technical",
                  section_id="project"),
        FormField(field_id="keywords", label="Keywords", field_type="text",
                  required=False, data_source_hint="project_info", section_id="project"),
    ]


def _budget_fields():
    return [
        FormField(field_id="total_budget_request", label="Total Budget Request",
                  field_type="number", required=True, data_source_hint="financial",
                  section_id="budget"),
        FormField(field_id="direct_labor", label="Direct Labor",
                  field_type="number", required=False, data_source_hint="financial",
                  section_id="budget"),
        FormField(field_id="indirect_costs", label="Indirect Costs",
                  field_type="number", required=False, data_source_hint="financial",
                  section_id="budget"),
        FormField(field_id="equipment_costs", label="Equipment Costs",
                  field_type="number", required=False, data_source_hint="financial",
                  section_id="budget"),
        FormField(field_id="other_costs", label="Other Costs",
                  field_type="number", required=False, data_source_hint="financial",
                  section_id="budget"),
    ]


def _personnel_fields():
    return [
        FormField(field_id="pi_name", label="Principal Investigator Name",
                  field_type="text", required=True, data_source_hint="company_info",
                  section_id="personnel"),
        FormField(field_id="pi_email", label="PI Email", field_type="text",
                  required=True, data_source_hint="company_info", section_id="personnel"),
        FormField(field_id="pi_phone", label="PI Phone", field_type="text",
                  required=False, data_source_hint="company_info", section_id="personnel"),
        FormField(field_id="pi_title", label="PI Title", field_type="text",
                  required=False, data_source_hint="company_info", section_id="personnel"),
        FormField(field_id="key_personnel", label="Key Personnel",
                  field_type="textarea", required=False, data_source_hint="company_info",
                  section_id="personnel"),
    ]


def _cert_fields():
    return [
        FormField(field_id="authorized_rep_name", label="Authorized Representative Name",
                  field_type="text", required=True, legal_certification=True,
                  data_source_hint="legal_certification", section_id="certifications"),
        FormField(field_id="authorized_rep_title", label="Authorized Representative Title",
                  field_type="text", required=True, legal_certification=True,
                  data_source_hint="legal_certification", section_id="certifications"),
        FormField(field_id="certification_statement", label="Certification Statement",
                  field_type="checkbox", required=True, legal_certification=True,
                  data_source_hint="legal_certification",
                  help_text="I certify that the information provided is accurate and complete",
                  section_id="certifications"),
        FormField(field_id="signature_date", label="Signature Date", field_type="date",
                  required=True, legal_certification=True,
                  data_source_hint="legal_certification", section_id="certifications"),
    ]


class SBIRPhase1Form(BaseFormDefinition):
    form_id = "sbir_phase1"

    def get_definition(self) -> FormDefinition:
        return FormDefinition(
            form_id="sbir_phase1",
            form_name="SBIR Phase I Application",
            grant_program_id="sbir_phase1",
            version="1.0",
            submission_format="pdf",
            sections=[
                _company_section(),
                _project_section(),
                _budget_section(),
                _personnel_section(),
                _cert_section(),
            ],
            fields=(
                _company_fields()
                + _project_fields()
                + _budget_fields()
                + _personnel_fields()
                + _cert_fields()
            ),
        )
