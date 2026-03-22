"""
JSON export generator for grant form data.
© 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from src.billing.grants.form_filler.output_generators.base import BaseOutputGenerator
from src.billing.grants.form_filler.review_session import FilledField, FormDefinition


class JSONExporter(BaseOutputGenerator):
    format_name = "json"

    def generate(
        self,
        form_def: FormDefinition,
        filled_fields: List[FilledField],
        metadata: Dict,
    ) -> bytes:
        filled_map = {f.field_id: f for f in filled_fields}

        sections_out = []
        for section in sorted(form_def.sections, key=lambda s: s.order):
            section_fields = [f for f in form_def.fields if f.section_id == section.section_id]
            sections_out.append({
                "section_id": section.section_id,
                "title": section.title,
                "order": section.order,
            })

        fields_out: List[Dict[str, Any]] = []
        for field in form_def.fields:
            ff = filled_map.get(field.field_id)
            fields_out.append({
                "field_id": field.field_id,
                "label": field.label,
                "field_type": field.field_type,
                "section_id": field.section_id,
                "required": field.required,
                "legal_certification": field.legal_certification,
                "value": ff.value if ff else None,
                "confidence": round(ff.confidence, 4) if ff else 0.0,
                "status": ff.status if ff else "missing",
                "source": ff.source if ff else "",
                "reasoning": ff.reasoning if ff else "",
                "edited_by_human": ff.edited_by_human if ff else False,
            })

        output = {
            "form_id": form_def.form_id,
            "form_name": form_def.form_name,
            "grant_program_id": form_def.grant_program_id,
            "version": form_def.version,
            "metadata": metadata or {},
            "sections": sections_out,
            "fields": fields_out,
        }
        return json.dumps(output, indent=2, default=str).encode("utf-8")

    def get_content_type(self) -> str:
        return "application/json"

    def get_file_extension(self) -> str:
        return "json"
