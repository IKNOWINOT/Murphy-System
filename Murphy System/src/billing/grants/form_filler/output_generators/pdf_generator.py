"""
PDF output generator — uses reportlab if available, falls back to HTML.
© 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""
from __future__ import annotations

from typing import Dict, List

from src.billing.grants.form_filler.output_generators.base import BaseOutputGenerator
from src.billing.grants.form_filler.review_session import FilledField, FormDefinition


def _generate_html_fallback(
    form_def: FormDefinition,
    filled_fields: List[FilledField],
    metadata: Dict,
) -> bytes:
    filled_map = {f.field_id: f for f in filled_fields}
    rows = []
    for section in sorted(form_def.sections, key=lambda s: s.order):
        rows.append(f"<h2>{section.title}</h2>")
        section_fields = [f for f in form_def.fields if f.section_id == section.section_id]
        for field in section_fields:
            ff = filled_map.get(field.field_id)
            val = ff.value if ff else ""
            status = ff.status if ff else "missing"
            conf = f"{ff.confidence:.0%}" if ff else "N/A"
            rows.append(
                f"<tr>"
                f"<td><b>{field.label}</b></td>"
                f"<td>{val}</td>"
                f"<td>{status}</td>"
                f"<td>{conf}</td>"
                f"</tr>"
            )
    table_rows = "\n".join(rows)
    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{form_def.form_name}</title>
<style>
  body {{ font-family: Arial, sans-serif; margin: 40px; }}
  h1 {{ color: #333; }}
  h2 {{ color: #555; border-bottom: 1px solid #ccc; }}
  table {{ border-collapse: collapse; width: 100%; }}
  td {{ padding: 6px 10px; border: 1px solid #ddd; vertical-align: top; }}
  td:first-child {{ font-weight: bold; width: 30%; }}
</style>
</head>
<body>
<h1>{form_def.form_name}</h1>
<p>Form ID: {form_def.form_id} | Program: {form_def.grant_program_id}</p>
<table>
<tr><th>Field</th><th>Value</th><th>Status</th><th>Confidence</th></tr>
{table_rows}
</table>
</body>
</html>"""
    return html.encode("utf-8")


class PDFGenerator(BaseOutputGenerator):
    format_name = "pdf"

    def __init__(self) -> None:
        try:
            from reportlab.lib.pagesizes import letter  # noqa: F401
            self._has_reportlab = True
        except ImportError:
            self._has_reportlab = False

    def generate(
        self,
        form_def: FormDefinition,
        filled_fields: List[FilledField],
        metadata: Dict,
    ) -> bytes:
        if self._has_reportlab:
            from io import BytesIO

            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter)
            styles = getSampleStyleSheet()
            story = []
            story.append(Paragraph(form_def.form_name, styles["Title"]))
            filled_map = {f.field_id: f for f in filled_fields}
            for section in sorted(form_def.sections, key=lambda s: s.order):
                story.append(Spacer(1, 12))
                story.append(Paragraph(section.title, styles["Heading2"]))
                for field in [f for f in form_def.fields if f.section_id == section.section_id]:
                    ff = filled_map.get(field.field_id)
                    val = ff.value if ff else ""
                    status = ff.status if ff else "missing"
                    story.append(
                        Paragraph(
                            f"<b>{field.label}:</b> {val} [{status}]",
                            styles["Normal"],
                        )
                    )
            doc.build(story)
            return buffer.getvalue()
        else:
            return _generate_html_fallback(form_def, filled_fields, metadata)

    def get_content_type(self) -> str:
        return "application/pdf" if self._has_reportlab else "text/html"

    def get_file_extension(self) -> str:
        return "pdf" if self._has_reportlab else "html"
