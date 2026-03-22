"""
Base output generator.
© 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""
from __future__ import annotations

from typing import Dict, List

from src.billing.grants.form_filler.review_session import FilledField, FormDefinition


class BaseOutputGenerator:
    format_name: str = "base"

    def generate(
        self,
        form_def: FormDefinition,
        filled_fields: List[FilledField],
        metadata: Dict,
    ) -> bytes:
        raise NotImplementedError

    def get_content_type(self) -> str:
        raise NotImplementedError

    def get_file_extension(self) -> str:
        raise NotImplementedError
