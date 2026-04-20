"""
STTR Phase I form definition.
© 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""
from __future__ import annotations

from src.billing.grants.form_filler.form_definitions.base import BaseFormDefinition
from src.billing.grants.form_filler.form_definitions.sbir_phase1 import (
    _budget_fields,
    _cert_fields,
    _company_fields,
    _company_section,
    _personnel_fields,
    _project_fields,
    _project_section,
    _budget_section,
    _personnel_section,
    _cert_section,
)
from src.billing.grants.form_filler.review_session import (
    FormDefinition,
    FormField,
    FormSection,
)


def _research_partner_section() -> FormSection:
    return FormSection(
        section_id="research_partner",
        title="Research Institution Partner",
        order=5,
    )


def _research_partner_fields():
    return [
        FormField(
            field_id="institution_name",
            label="Institution Name",
            field_type="text",
            required=True,
            data_source_hint="project_info",
            section_id="research_partner",
        ),
        FormField(
            field_id="institution_type",
            label="Institution Type",
            field_type="select",
            required=True,
            options=["University", "Federal Lab", "FFRDC"],
            data_source_hint="project_info",
            section_id="research_partner",
        ),
        FormField(
            field_id="partner_pi_name",
            label="Partner PI Name",
            field_type="text",
            required=True,
            data_source_hint="project_info",
            section_id="research_partner",
        ),
        FormField(
            field_id="partnership_agreement",
            label="Partnership Agreement",
            field_type="file_upload",
            required=True,
            legal_certification=True,
            data_source_hint="legal_certification",
            help_text="Signed partnership agreement document",
            section_id="research_partner",
        ),
    ]


class STTRPhase1Form(BaseFormDefinition):
    form_id = "sttr_phase1"

    def get_definition(self) -> FormDefinition:
        return FormDefinition(
            form_id="sttr_phase1",
            form_name="STTR Phase I Application",
            grant_program_id="sttr_phase1",
            version="1.0",
            submission_format="pdf",
            sections=[
                _company_section(),
                _project_section(),
                _budget_section(),
                _personnel_section(),
                _cert_section(),
                _research_partner_section(),
            ],
            fields=(
                _company_fields()
                + _project_fields()
                + _budget_fields()
                + _personnel_fields()
                + _cert_fields()
                + _research_partner_fields()
            ),
        )
