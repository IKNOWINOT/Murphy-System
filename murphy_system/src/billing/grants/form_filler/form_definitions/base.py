"""
Base form definition.
© 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""
from __future__ import annotations

from typing import List

from src.billing.grants.form_filler.review_session import FilledField, FormDefinition


class BaseFormDefinition:
    form_id: str = "base"

    def get_definition(self) -> FormDefinition:
        raise NotImplementedError

    def validate_filled_fields(self, filled: List[FilledField]) -> List[str]:
        """Returns list of error messages for invalid/missing required fields."""
        errors = []
        definition = self.get_definition()
        filled_map = {f.field_id: f for f in filled}
        for field in definition.fields:
            if field.required:
                ff = filled_map.get(field.field_id)
                if ff is None or ff.value is None or (isinstance(ff.value, str) and not ff.value.strip()):
                    if not field.legal_certification:
                        errors.append(f"Required field '{field.label}' is missing or empty.")
        return errors
