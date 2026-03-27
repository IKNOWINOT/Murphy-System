"""
NSF SBIR form definition.
© 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""
from __future__ import annotations

from src.billing.grants.form_filler.form_definitions.base import BaseFormDefinition
from src.billing.grants.form_filler.form_definitions.sbir_phase1 import (
    _budget_fields,
    _budget_section,
    _cert_fields,
    _cert_section,
    _company_fields,
    _company_section,
    _personnel_fields,
    _personnel_section,
    _project_fields,
    _project_section,
)
from src.billing.grants.form_filler.review_session import (
    FormDefinition,
    FormField,
    FormSection,
)


def _commercial_section() -> FormSection:
    return FormSection(
        section_id="commercial",
        title="Commercial Potential",
        order=5,
    )


def _commercial_fields():
    return [
        FormField(
            field_id="market_size",
            label="Market Size",
            field_type="number",
            required=False,
            data_source_hint="financial",
            help_text="Estimated total addressable market in USD",
            section_id="commercial",
        ),
        FormField(
            field_id="target_customers",
            label="Target Customers",
            field_type="textarea",
            required=False,
            data_source_hint="project_info",
            section_id="commercial",
        ),
        FormField(
            field_id="commercialization_plan",
            label="Commercialization Plan",
            field_type="textarea",
            required=True,
            max_length=3000,
            data_source_hint="project_info",
            section_id="commercial",
        ),
        FormField(
            field_id="ip_strategy",
            label="IP Strategy",
            field_type="textarea",
            required=False,
            data_source_hint="technical",
            section_id="commercial",
        ),
    ]


class NSFSBIRForm(BaseFormDefinition):
    form_id = "nsf_sbir"

    def get_definition(self) -> FormDefinition:
        return FormDefinition(
            form_id="nsf_sbir",
            form_name="NSF SBIR Application",
            grant_program_id="nsf_sbir",
            version="1.0",
            submission_format="pdf",
            sections=[
                _company_section(),
                _project_section(),
                _budget_section(),
                _personnel_section(),
                _cert_section(),
                _commercial_section(),
            ],
            fields=(
                _company_fields()
                + _project_fields()
                + _budget_fields()
                + _personnel_fields()
                + _cert_fields()
                + _commercial_fields()
            ),
        )
