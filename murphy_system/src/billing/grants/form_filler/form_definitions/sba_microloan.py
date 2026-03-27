"""
SBA Microloan form definition.
© 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""
from __future__ import annotations

from src.billing.grants.form_filler.form_definitions.base import BaseFormDefinition
from src.billing.grants.form_filler.review_session import (
    FormDefinition,
    FormField,
    FormSection,
)


class SBAMicroloanForm(BaseFormDefinition):
    form_id = "sba_microloan"

    def get_definition(self) -> FormDefinition:
        return FormDefinition(
            form_id="sba_microloan",
            form_name="SBA Microloan Application",
            grant_program_id="sba_microloan",
            version="1.0",
            submission_format="pdf",
            sections=[
                FormSection(section_id="business", title="Business Information", order=0),
                FormSection(section_id="loan", title="Loan Request", order=1),
                FormSection(section_id="financial", title="Financial Information", order=2),
                FormSection(section_id="owner", title="Owner Information", order=3),
            ],
            fields=[
                FormField(field_id="business_name", label="Business Name", field_type="text",
                          required=True, data_source_hint="company_info", section_id="business"),
                FormField(field_id="business_type", label="Business Type", field_type="select",
                          required=True,
                          options=["LLC", "Sole Proprietor", "Partnership", "Corporation"],
                          data_source_hint="company_info", section_id="business"),
                FormField(field_id="years_in_operation", label="Years in Operation",
                          field_type="number", required=True, data_source_hint="company_info",
                          section_id="business"),
                # Loan section
                FormField(field_id="loan_amount_requested", label="Loan Amount Requested",
                          field_type="number", required=True, data_source_hint="financial",
                          section_id="loan"),
                FormField(field_id="loan_purpose", label="Loan Purpose", field_type="textarea",
                          required=True, data_source_hint="project_info", section_id="loan"),
                # Financial section
                FormField(field_id="credit_score", label="Credit Score", field_type="number",
                          required=False, data_source_hint="financial", section_id="financial"),
                FormField(field_id="annual_revenue", label="Annual Revenue", field_type="number",
                          required=True, data_source_hint="financial", section_id="financial"),
                FormField(field_id="monthly_expenses", label="Monthly Expenses",
                          field_type="number", required=False, data_source_hint="financial",
                          section_id="financial"),
                # Owner section
                FormField(field_id="owner_name", label="Owner Name", field_type="text",
                          required=True, data_source_hint="company_info", section_id="owner"),
                FormField(field_id="owner_ssn", label="Owner SSN", field_type="text",
                          required=True, legal_certification=True,
                          data_source_hint="legal_certification",
                          help_text="Social Security Number (sensitive)", section_id="owner"),
                FormField(field_id="personal_guarantee", label="Personal Guarantee",
                          field_type="checkbox", required=True, legal_certification=True,
                          data_source_hint="legal_certification", section_id="owner"),
            ],
        )
