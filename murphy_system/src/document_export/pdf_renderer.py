# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Production-quality PDF renderer using WeasyPrint (BSD-3).

Converts branded HTML produced by ExportPipeline._markdown_to_html() into
a fully-styled PDF with tables, headings, branded headers/footers, and
optional cover pages.

Falls back gracefully to reportlab plain-text rendering when WeasyPrint is
not installed (e.g. system libraries cairo/pango unavailable in the
environment).
"""

from __future__ import annotations

import base64
import html
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy import sentinel — checked once at module level so is_available() is
# fast on repeated calls, and the import error is not swallowed silently.
# ---------------------------------------------------------------------------

_WEASYPRINT_AVAILABLE: Optional[bool] = None


def _check_weasyprint() -> bool:
    global _WEASYPRINT_AVAILABLE
    if _WEASYPRINT_AVAILABLE is None:
        try:
            import weasyprint  # noqa: F401  # type: ignore[import-untyped]

            _WEASYPRINT_AVAILABLE = True
        except Exception:
            _WEASYPRINT_AVAILABLE = False
    return _WEASYPRINT_AVAILABLE


# ---------------------------------------------------------------------------
# Print-media CSS template
# ---------------------------------------------------------------------------

_PRINT_CSS_TEMPLATE = """\
@page {{
    size: letter;
    margin: 1in 0.75in;
    @top-center {{
        content: "{company_name} | {document_title}";
        font-size: 8pt;
        color: {primary_color};
    }}
    @bottom-left {{
        content: "{legal_line}";
        font-size: 7pt;
        color: #999;
    }}
    @bottom-right {{
        content: "Page " counter(page) " of " counter(pages);
        font-size: 7pt;
    }}
}}
@page :first {{
    @top-center {{ content: none; }}
}}
body {{
    font-family: '{font_body}', 'Helvetica Neue', Helvetica, Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.5;
    color: #333;
}}
h1, h2, h3 {{
    font-family: '{font_heading}', 'Helvetica Neue', Helvetica, Arial, sans-serif;
    color: {primary_color};
}}
h1 {{ font-size: 18pt; border-bottom: 2pt solid {secondary_color}; padding-bottom: 4pt; page-break-before: auto; }}
h2 {{ font-size: 14pt; border-bottom: 1pt solid {secondary_color}; page-break-before: auto; }}
h3 {{ font-size: 12pt; page-break-before: auto; }}
table {{
    border-collapse: collapse;
    width: 100%;
    page-break-inside: avoid;
    margin: 12pt 0;
}}
th {{
    background-color: {secondary_color};
    color: white;
    font-weight: bold;
    padding: 6pt 8pt;
    text-align: left;
    border: 1pt solid {secondary_color};
}}
td {{
    padding: 5pt 8pt;
    border: 0.5pt solid #ccc;
}}
tr:nth-child(even) td {{ background-color: #f8f9fa; }}
a {{ color: {accent_color}; }}
pre, code {{ font-size: 9pt; background: #f5f5f5; padding: 2pt 4pt; }}
"""

# ---------------------------------------------------------------------------
# Cover-page HTML template
# ---------------------------------------------------------------------------

_COVER_PAGE_TEMPLATE = """\
<div style="page-break-after: always; text-align: center; padding-top: 3in; \
font-family: '{font_heading}', Helvetica, Arial, sans-serif;">
{logo_html}
<h1 style="color: {primary_color}; font-size: 28pt; margin-bottom: 0.5em;">{document_title}</h1>
<p style="color: {secondary_color}; font-size: 14pt; margin-top: 0;">{company_name}</p>
<p style="color: #999; font-size: 10pt;">{legal_line}</p>
</div>
"""


class RichPDFRenderer:
    """Production-quality PDF renderer using WeasyPrint (BSD-3).

    Converts branded HTML to PDF with proper tables, headers, styled
    typography, headers/footers, and cover pages.

    Falls back gracefully to reportlab plain-text rendering when
    WeasyPrint is not installed.

    This class is stateless — all state lives in the arguments passed to
    each method, making it safe to share across threads.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def is_available() -> bool:
        """Return ``True`` if WeasyPrint is importable, ``False`` otherwise."""
        return _check_weasyprint()

    def render(
        self,
        html_content: str,
        brand: object,
        metadata: Dict[str, str],
    ) -> bytes:
        """Convert branded HTML to PDF bytes.

        Parameters
        ----------
        html_content:
            Full HTML document string produced by
            ``ExportPipeline._markdown_to_html()``.
        brand:
            A :class:`~document_export.brand_registry.BrandProfile` instance
            supplying colors, fonts, company name, and legal text.
        metadata:
            Arbitrary string key/value pairs.  ``"document_title"`` is used
            in the page header if present.

        Returns
        -------
        bytes
            Raw PDF file bytes.

        Raises
        ------
        RuntimeError
            If WeasyPrint is not installed *and* reportlab is also absent.
        """
        document_title = metadata.get("document_title", "Document")

        if _check_weasyprint():
            return self._render_weasyprint(html_content, brand, document_title)
        return self._render_reportlab_fallback(html_content, brand)

    def render_to_base64(
        self,
        html_content: str,
        brand: object,
        metadata: Dict[str, str],
    ) -> str:
        """Return :meth:`render` output as a base64-encoded ASCII string."""
        return base64.b64encode(self.render(html_content, brand, metadata)).decode("ascii")

    # ------------------------------------------------------------------
    # WeasyPrint path
    # ------------------------------------------------------------------

    def _render_weasyprint(
        self,
        html_content: str,
        brand: object,
        document_title: str,
    ) -> bytes:
        """Inject print CSS (and optional cover page / logo), then call WeasyPrint."""
        import weasyprint  # type: ignore[import-untyped]

        full_html = self._build_full_html(html_content, brand, document_title)
        return weasyprint.HTML(string=full_html).write_pdf()

    def _build_full_html(
        self,
        html_content: str,
        brand: object,
        document_title: str,
    ) -> str:
        """Compose the final HTML document for WeasyPrint.

        Injects a ``<style>`` block with print-media CSS, prepends an
        optional cover page, and embeds an optional logo ``<img>``.
        """
        primary_color = getattr(brand, "primary_color", "#1E3A5F")
        secondary_color = getattr(brand, "secondary_color", "#2E86AB")
        accent_color = getattr(brand, "accent_color", "#F18F01")
        font_heading = getattr(brand, "font_heading", "Helvetica")
        font_body = getattr(brand, "font_body", "Helvetica")
        company_name = getattr(brand, "company_name", "murphy_system")
        legal_line = getattr(brand, "legal_line", "")
        logo_base64 = getattr(brand, "logo_base64", None)
        cover_page_template = getattr(brand, "cover_page_template", None)

        # Build print CSS
        print_css = _PRINT_CSS_TEMPLATE.format(
            primary_color=primary_color,
            secondary_color=secondary_color,
            accent_color=accent_color,
            font_body=font_body,
            font_heading=font_heading,
            company_name=html.escape(company_name),
            document_title=html.escape(document_title),
            legal_line=html.escape(legal_line),
        )

        # Build logo HTML (embedded data URI)
        logo_html = ""
        if logo_base64:
            logo_html = (
                f'<img src="data:image/png;base64,{logo_base64}" '
                f'style="max-height: 80pt; margin-bottom: 24pt;" alt="logo" /><br/>'
            )

        # Build cover page HTML
        cover_html = ""
        if cover_page_template:
            cover_html = _COVER_PAGE_TEMPLATE.format(
                logo_html=logo_html,
                primary_color=primary_color,
                secondary_color=secondary_color,
                font_heading=font_heading,
                company_name=html.escape(company_name),
                document_title=html.escape(document_title),
                legal_line=html.escape(legal_line),
            )

        # Inject print CSS and cover page into the HTML document.
        # Strategy: insert <style> before </head> (or at top of document if no
        # </head>), and prepend cover_html before the first <body> content.
        if "</head>" in html_content:
            full_html = html_content.replace(
                "</head>",
                f"<style>\n{print_css}\n</style>\n</head>",
                1,
            )
        else:
            full_html = f"<style>\n{print_css}\n</style>\n{html_content}"

        if cover_html:
            if "<body>" in full_html:
                full_html = full_html.replace("<body>", f"<body>\n{cover_html}", 1)
            else:
                full_html = cover_html + full_html

        return full_html

    # ------------------------------------------------------------------
    # reportlab fallback path
    # ------------------------------------------------------------------

    @staticmethod
    def _render_reportlab_fallback(html_content: str, brand: object) -> bytes:
        """Plain-text PDF via reportlab when WeasyPrint is unavailable."""
        import re
        from io import BytesIO

        from reportlab.lib.pagesizes import letter  # type: ignore[import-untyped]
        from reportlab.pdfgen import canvas as rl_canvas  # type: ignore[import-untyped]

        font_body = getattr(brand, "font_body", "Helvetica")
        font_name = font_body if font_body in ("Helvetica", "Times-Roman", "Courier") else "Helvetica"

        # Strip HTML tags to plain text for the fallback
        plain = re.sub(r"<[^>]+>", " ", html_content)
        plain = re.sub(r"&amp;", "&", plain)
        plain = re.sub(r"&lt;", "<", plain)
        plain = re.sub(r"&gt;", ">", plain)
        plain = re.sub(r"&nbsp;", " ", plain)
        plain = re.sub(r"\s{2,}", " ", plain)

        buf = BytesIO()
        c = rl_canvas.Canvas(buf, pagesize=letter)
        font_size = 11
        c.setFont(font_name, font_size)
        y = 750
        for line in plain.split("\n"):
            for segment in [line[i : i + 90] for i in range(0, max(len(line), 1), 90)]:
                if y < 50:
                    c.showPage()
                    c.setFont(font_name, font_size)
                    y = 750
                c.drawString(72, y, segment.strip())
                y -= font_size + 2
        c.save()
        return buf.getvalue()
