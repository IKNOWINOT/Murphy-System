"""
Grants.gov organization profile form definition.
© 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""
from __future__ import annotations

from src.billing.grants.form_filler.form_definitions.base import BaseFormDefinition
from src.billing.grants.form_filler.review_session import (
    FormDefinition,
    FormField,
    FormSection,
)


class GrantsGovForm(BaseFormDefinition):
    form_id = "grants_gov"

    def get_definition(self) -> FormDefinition:
        return FormDefinition(
            form_id="grants_gov",
            form_name="Grants.gov Organization Profile",
            grant_program_id="grants_gov_account",
            version="1.0",
            submission_format="pdf",
            sections=[
                FormSection(section_id="organization", title="Organization Profile", order=0),
            ],
            fields=[
                FormField(field_id="organization_name", label="Organization Name",
                          field_type="text", required=True, data_source_hint="company_info",
                          section_id="organization"),
                FormField(field_id="uei", label="UEI", field_type="text",
                          required=True, data_source_hint="company_info",
                          section_id="organization"),
                FormField(field_id="cage_code", label="CAGE Code", field_type="text",
                          required=False, data_source_hint="company_info",
                          section_id="organization"),
                FormField(field_id="organization_type", label="Organization Type",
                          field_type="select", required=True,
                          options=["For-Profit Small Business", "Large Business", "Non-Profit",
                                   "University", "State/Local Government", "Federal Agency"],
                          data_source_hint="company_info", section_id="organization"),
                FormField(field_id="congressional_district", label="Congressional District",
                          field_type="text", required=False, data_source_hint="company_info",
                          help_text="e.g., OR-01", section_id="organization"),
                FormField(field_id="mission_statement", label="Mission Statement",
                          field_type="textarea", required=False, data_source_hint="project_info",
                          section_id="organization"),
                FormField(field_id="grant_experience", label="Grant Experience",
                          field_type="textarea", required=False, data_source_hint="project_info",
                          help_text="Brief description of past grant experience",
                          section_id="organization"),
                # Grants.gov requires at least one cert field
                FormField(field_id="grants_gov_certification",
                          label="Grants.gov Certification",
                          field_type="checkbox", required=True, legal_certification=True,
                          data_source_hint="legal_certification",
                          help_text="I certify that all information is accurate",
                          section_id="organization"),
            ],
        )
