"""
Energy Trust of Oregon form definition.
© 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""
from __future__ import annotations

from src.billing.grants.form_filler.form_definitions.base import BaseFormDefinition
from src.billing.grants.form_filler.review_session import (
    FormDefinition,
    FormField,
    FormSection,
)


class EnergyTrustForm(BaseFormDefinition):
    form_id = "energy_trust"

    def get_definition(self) -> FormDefinition:
        return FormDefinition(
            form_id="energy_trust",
            form_name="Energy Trust of Oregon Incentive Application",
            grant_program_id="energy_trust_oregon",
            version="1.0",
            submission_format="pdf",
            sections=[
                FormSection(section_id="organization", title="Organization", order=0),
                FormSection(section_id="project", title="Project Details", order=1),
                FormSection(section_id="certification", title="Certification", order=2),
            ],
            fields=[
                FormField(field_id="organization_name", label="Organization Name",
                          field_type="text", required=True, data_source_hint="company_info",
                          section_id="organization"),
                FormField(field_id="service_territory", label="Service Territory",
                          field_type="select", required=True,
                          options=["Pacific Power", "Portland General Electric",
                                   "NW Natural", "Cascade Natural Gas"],
                          data_source_hint="company_info", section_id="organization"),
                # Project section
                FormField(field_id="project_type", label="Project Type", field_type="select",
                          required=True,
                          options=["Energy Efficiency", "Renewable Energy",
                                   "Combined Heat and Power"],
                          data_source_hint="project_info", section_id="project"),
                FormField(field_id="project_description", label="Project Description",
                          field_type="textarea", required=True, data_source_hint="project_info",
                          section_id="project"),
                FormField(field_id="expected_energy_savings",
                          label="Expected Energy Savings",
                          field_type="number", required=True, data_source_hint="financial",
                          help_text="Expected annual energy savings in kWh or therms",
                          section_id="project"),
                FormField(field_id="project_cost", label="Project Cost", field_type="number",
                          required=True, data_source_hint="financial", section_id="project"),
                FormField(field_id="contractor_name", label="Contractor Name",
                          field_type="text", required=False, data_source_hint="company_info",
                          section_id="project"),
                # Certification section
                FormField(field_id="certification_agreement",
                          label="Certification Agreement",
                          field_type="checkbox", required=True, legal_certification=True,
                          data_source_hint="legal_certification",
                          section_id="certification"),
            ],
        )
