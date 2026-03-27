"""
SAM.gov registration form definition.
© 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""
from __future__ import annotations

from src.billing.grants.form_filler.form_definitions.base import BaseFormDefinition
from src.billing.grants.form_filler.review_session import (
    FormDefinition,
    FormField,
    FormSection,
)


class SAMGovForm(BaseFormDefinition):
    form_id = "sam_gov"

    def get_definition(self) -> FormDefinition:
        return FormDefinition(
            form_id="sam_gov",
            form_name="SAM.gov Entity Registration",
            grant_program_id="sam_gov_registration",
            version="1.0",
            submission_format="pdf",
            sections=[
                FormSection(section_id="entity", title="Entity Information", order=0),
                FormSection(section_id="address", title="Address", order=1),
                FormSection(section_id="contact", title="Point of Contact", order=2),
                FormSection(section_id="banking", title="Banking Information", order=3),
                FormSection(section_id="certifications", title="Certifications", order=4),
            ],
            fields=[
                FormField(field_id="legal_business_name", label="Legal Business Name",
                          field_type="text", required=True, data_source_hint="company_info",
                          section_id="entity"),
                FormField(field_id="dba_name", label="DBA Name", field_type="text",
                          required=False, data_source_hint="company_info",
                          help_text="Doing Business As name (if different)", section_id="entity"),
                FormField(field_id="ein_tin", label="EIN/TIN", field_type="text",
                          required=True, validation_regex=r"^\d{2}-\d{7}$",
                          data_source_hint="company_info", section_id="entity"),
                FormField(field_id="business_type", label="Business Type", field_type="select",
                          required=True,
                          options=["LLC", "Corporation", "Sole Proprietor", "Partnership",
                                   "Non-Profit", "Government"],
                          data_source_hint="company_info", section_id="entity"),
                FormField(field_id="naics_codes", label="NAICS Codes", field_type="text",
                          required=True, data_source_hint="company_info",
                          help_text="Comma-separated NAICS codes", section_id="entity"),
                # Address section
                FormField(field_id="physical_street", label="Physical Street",
                          field_type="text", required=True, data_source_hint="company_info",
                          section_id="address"),
                FormField(field_id="physical_city", label="Physical City",
                          field_type="text", required=True, data_source_hint="company_info",
                          section_id="address"),
                FormField(field_id="physical_state", label="Physical State",
                          field_type="text", required=True, data_source_hint="company_info",
                          section_id="address"),
                FormField(field_id="physical_zip", label="Physical ZIP",
                          field_type="text", required=True, data_source_hint="company_info",
                          section_id="address"),
                FormField(field_id="mailing_same_as_physical",
                          label="Mailing Same as Physical",
                          field_type="checkbox", required=False,
                          data_source_hint="company_info", section_id="address"),
                # Contact section
                FormField(field_id="poc_name", label="POC Name", field_type="text",
                          required=True, data_source_hint="company_info", section_id="contact"),
                FormField(field_id="poc_email", label="POC Email", field_type="text",
                          required=True, data_source_hint="company_info", section_id="contact"),
                FormField(field_id="poc_phone", label="POC Phone", field_type="text",
                          required=True, data_source_hint="company_info", section_id="contact"),
                # Banking section
                FormField(field_id="banking_info_document",
                          label="Banking Information Document",
                          field_type="file_upload", required=True, legal_certification=True,
                          data_source_hint="legal_certification",
                          help_text="Bank account information document", section_id="banking"),
                # Certifications section
                FormField(field_id="sam_certifications", label="SAM Certifications",
                          field_type="checkbox", required=True, legal_certification=True,
                          data_source_hint="legal_certification",
                          help_text="I certify that all information is accurate",
                          section_id="certifications"),
            ],
        )
