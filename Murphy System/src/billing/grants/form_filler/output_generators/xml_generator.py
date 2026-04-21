"""
XML output generator for grant form data.
© 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""
from __future__ import annotations

# PROD-HARD-SEC-001 (audit G18): this module generates XML output
# (ET.Element/SubElement/ElementTree.write) and never parses untrusted input —
# no ET.fromstring / ET.parse / ET.iterparse / XMLParser call sites.
# Serialization has no XXE surface, so defusedxml is not required here.
import xml.etree.ElementTree as ET  # nosec B405
from typing import Dict, List

from src.billing.grants.form_filler.output_generators.base import BaseOutputGenerator
from src.billing.grants.form_filler.review_session import FilledField, FormDefinition


class XMLGenerator(BaseOutputGenerator):
    format_name = "xml"

    def generate(
        self,
        form_def: FormDefinition,
        filled_fields: List[FilledField],
        metadata: Dict,
    ) -> bytes:
        root = ET.Element("GrantApplication")
        root.set("form_id", form_def.form_id)
        root.set("form_name", form_def.form_name)
        root.set("grant_program_id", form_def.grant_program_id)
        root.set("version", form_def.version)

        meta_el = ET.SubElement(root, "Metadata")
        for k, v in (metadata or {}).items():
            m = ET.SubElement(meta_el, "Meta")
            m.set("key", str(k))
            m.text = str(v)

        filled_map = {f.field_id: f for f in filled_fields}

        sections_el = ET.SubElement(root, "Sections")
        for section in sorted(form_def.sections, key=lambda s: s.order):
            sec_el = ET.SubElement(sections_el, "Section")
            sec_el.set("id", section.section_id)
            sec_el.set("title", section.title)
            section_fields = [f for f in form_def.fields if f.section_id == section.section_id]
            for field in section_fields:
                ff = filled_map.get(field.field_id)
                field_el = ET.SubElement(sec_el, "Field")
                field_el.set("id", field.field_id)
                field_el.set("label", field.label)
                field_el.set("type", field.field_type)
                field_el.set("required", str(field.required))
                field_el.set("status", ff.status if ff else "missing")
                field_el.set("confidence", str(round(ff.confidence, 4)) if ff else "0")
                field_el.set("source", ff.source if ff else "")
                field_el.text = str(ff.value) if ff and ff.value is not None else ""

        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        from io import BytesIO
        buf = BytesIO()
        tree.write(buf, encoding="utf-8", xml_declaration=True)
        return buf.getvalue()

    def get_content_type(self) -> str:
        return "application/xml"

    def get_file_extension(self) -> str:
        return "xml"
