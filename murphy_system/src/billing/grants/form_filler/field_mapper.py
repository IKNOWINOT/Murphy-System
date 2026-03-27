"""
Field Mapper — Maps saved data and profiles to form fields.
© 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from src.billing.grants.form_filler.review_session import FormDefinition, FormField

_COMPANY_INFO_KEYS = {
    "company_name", "company_legal_name", "legal_business_name", "business_name",
    "ein", "ein_tin", "uei", "cage_code",
    "address_street", "address_city", "address_state", "address_zip", "address_country",
    "physical_street", "physical_city", "physical_state", "physical_zip",
    "naics_code", "naics_codes",
    "employee_count", "formation_date",
    "poc_name", "pi_name", "poc_email", "pi_email", "poc_phone", "pi_phone",
    "organization_name",
}

_PROJECT_INFO_KEYS = {
    "project_title", "project_description", "technical_approach", "innovation",
    "innovation_statement", "keywords", "research_focus", "commercialization_plan",
    "target_customers", "market_size", "institution_name", "institution_type",
    "partner_pi_name", "grant_experience", "mission_statement",
    "project_start_date", "project_end_date",
}

_FINANCIAL_KEYS = {
    "annual_revenue", "annual_revenue_usd",
    "total_budget_request", "direct_labor", "indirect_costs",
    "equipment_costs", "other_costs", "funding_requested",
    "budget_total", "loan_amount_requested", "credit_score",
    "monthly_expenses", "market_size",
}

_TECHNICAL_KEYS = {
    "technical_narrative", "rd_plan", "methodology", "technical_focus",
    "rd_description", "ip_strategy",
}

_HINT_KEY_MAP: Dict[str, set] = {
    "company_info": _COMPANY_INFO_KEYS,
    "project_info": _PROJECT_INFO_KEYS,
    "financial": _FINANCIAL_KEYS,
    "technical": _TECHNICAL_KEYS,
}


class FieldMapper:
    def map_fields(
        self,
        form_def: FormDefinition,
        saved_data: Dict[str, Any],
        murphy_profile_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        merged = {**murphy_profile_data, **saved_data}
        results: Dict[str, Any] = {}

        for form_field in form_def.fields:
            if form_field.legal_certification:
                results[form_field.field_id] = {
                    "value": None,
                    "source": "legal_certification",
                    "confidence": 0.0,
                }
                continue

            match = (
                self._match_by_field_id(form_field.field_id, saved_data)
                or self._match_by_field_id(form_field.field_id, murphy_profile_data)
                or self._match_by_hint(form_field, saved_data)
                or self._match_by_hint(form_field, murphy_profile_data)
                or self._match_by_semantic(form_field, merged)
            )

            if match is not None:
                value, source, confidence = match
                results[form_field.field_id] = {
                    "value": value,
                    "source": source,
                    "confidence": confidence,
                }
            # If no match, the field won't be in results; agent will handle

        return results

    def _match_by_field_id(
        self,
        field_id: str,
        data: Dict[str, Any],
    ) -> Optional[Tuple[Any, str, float]]:
        if field_id in data:
            return (data[field_id], "saved_form_data", 0.95)
        return None

    def _match_by_hint(
        self,
        field: FormField,
        data: Dict[str, Any],
    ) -> Optional[Tuple[Any, str, float]]:
        hint = field.data_source_hint
        if hint == "legal_certification":
            return None

        hint_keys = _HINT_KEY_MAP.get(hint, set())
        fid_lower = field.field_id.lower()

        # Try exact field_id against hint keys
        for key in hint_keys:
            if key == fid_lower or key in fid_lower or fid_lower in key:
                if key in data and data[key] not in (None, "", [], {}):
                    return (data[key], "murphy_profile", 0.85)

        return None

    def _match_by_semantic(
        self,
        field: FormField,
        data: Dict[str, Any],
    ) -> Optional[Tuple[Any, str, float]]:
        label_words = set(field.label.lower().split())
        for data_key, data_val in data.items():
            if data_val in (None, "", [], {}):
                continue
            key_lower = data_key.lower().replace("_", " ")
            key_words = set(key_lower.split())
            if label_words & key_words:
                return (data_val, "murphy_profile", 0.7)
        return None

    def build_field_context(self, field: FormField, all_data: Dict[str, Any]) -> str:
        available_keys = ", ".join(sorted(all_data.keys())[:20])
        return (
            f"Field: {field.label}, "
            f"Type: {field.field_type}, "
            f"Hint: {field.data_source_hint}, "
            f"Available data keys: {available_keys}"
        )
