"""
Generic grant form definition.
© 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""
from __future__ import annotations

from src.billing.grants.form_filler.form_definitions.base import BaseFormDefinition
from src.billing.grants.form_filler.review_session import (
    FormDefinition,
    FormField,
    FormSection,
)


class GenericGrantForm(BaseFormDefinition):
    form_id = "generic_grant"

    def get_definition(self) -> FormDefinition:
        return FormDefinition(
            form_id="generic_grant",
            form_name="Generic Grant Application",
            grant_program_id="generic",
            version="1.0",
            submission_format="pdf",
            sections=[
                FormSection(section_id="organization", title="Organization", order=0),
                FormSection(section_id="project", title="Project", order=1),
                FormSection(section_id="pi", title="Principal Investigator", order=2),
                FormSection(section_id="certification", title="Certification", order=3),
            ],
            fields=[
                FormField(field_id="organization_name", label="Organization Name",
                          field_type="text", required=True, data_source_hint="company_info",
                          section_id="organization"),
                FormField(field_id="ein", label="EIN", field_type="text",
                          required=True, data_source_hint="company_info",
                          section_id="organization"),
                # Project section
                FormField(field_id="project_title", label="Project Title", field_type="text",
                          required=True, data_source_hint="project_info", section_id="project"),
                FormField(field_id="project_description", label="Project Description",
                          field_type="textarea", required=True, data_source_hint="project_info",
                          section_id="project"),
                FormField(field_id="funding_requested", label="Funding Requested",
                          field_type="number", required=True, data_source_hint="financial",
                          section_id="project"),
                FormField(field_id="project_start_date", label="Project Start Date",
                          field_type="date", required=False, data_source_hint="project_info",
                          section_id="project"),
                FormField(field_id="project_end_date", label="Project End Date",
                          field_type="date", required=False, data_source_hint="project_info",
                          section_id="project"),
                # PI section
                FormField(field_id="pi_name", label="PI Name", field_type="text",
                          required=True, data_source_hint="company_info", section_id="pi"),
                FormField(field_id="pi_email", label="PI Email", field_type="text",
                          required=True, data_source_hint="company_info", section_id="pi"),
                # Certification section
                FormField(field_id="certification", label="Certification",
                          field_type="checkbox", required=True, legal_certification=True,
                          data_source_hint="legal_certification",
                          section_id="certification"),
            ],
        )
