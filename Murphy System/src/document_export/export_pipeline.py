"""
Document Export Pipeline.

Orchestrates the full flow:
    Bot JSON Output → Style Rewriter → Template Rendering → Brand Injection
                    → Format Conversion → Document
"""

from __future__ import annotations

import asyncio
import base64
import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .brand_registry import BrandProfile, BrandRegistry
from .style_rewriter import DocumentStyleRewriter
from .templates.commissioning import COMMISSIONING_TEMPLATES

# ---------------------------------------------------------------------------
# Optional: wire existing DocumentGenerationEngine for PDF/Word rendering.
# The relative import works when the package is loaded as part of src/;
# falls back to None (pipeline uses its own converters) when unavailable.
# ---------------------------------------------------------------------------
try:
    from ..execution.document_generation_engine import (
        DocumentGenerationEngine as _DocEngine,
    )
except ImportError:
    _DocEngine = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


class ExportResult(BaseModel):
    """The outcome of a single export operation."""

    document_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    format: str
    # base64-encoded for binary formats (pdf, word); plain string for text formats
    content: str
    filename: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ---------------------------------------------------------------------------
# Supported formats and their display names
# ---------------------------------------------------------------------------

SUPPORTED_FORMATS: Dict[str, str] = {
    "pdf": "PDF Document",
    "word": "Microsoft Word (.docx)",
    "html": "HTML Document",
    "markdown": "Markdown",
    "latex": "LaTeX",
    "plain_text": "Plain Text",
}

# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class ExportPipeline:
    """
    Orchestrate bot JSON output → styled document in the requested format.

    Thread-safe document registry via ``self._lock``.
    """

    def __init__(
        self,
        brand_registry: Optional[BrandRegistry] = None,
        style_rewriter: Optional[DocumentStyleRewriter] = None,
    ) -> None:
        self._brand_registry: BrandRegistry = brand_registry or BrandRegistry()
        self._rewriter: DocumentStyleRewriter = style_rewriter or DocumentStyleRewriter()
        self._lock: threading.Lock = threading.Lock()
        self._documents: Dict[str, ExportResult] = {}
        # Delegate PDF/Word rendering to the existing DocumentGenerationEngine when
        # available (architecture requirement: "don't reinvent them").
        self._doc_engine = _DocEngine() if _DocEngine is not None else None

    # ------------------------------------------------------------------
    # Public async API
    # ------------------------------------------------------------------

    async def export(
        self,
        source_output: Dict[str, Any],
        format: str = "markdown",
        brand_profile_id: Optional[str] = None,
        writing_style: str = "formal_engineering",
        template_type: str = "cx_plan_report",
    ) -> ExportResult:
        """
        Full export pipeline.

        Parameters
        ----------
        source_output:
            Raw bot output dict.  If it contains a ``result.plan`` key it is
            treated as commissioning bot output; otherwise the entire dict is
            used as the document data.
        format:
            One of ``SUPPORTED_FORMATS`` keys.
        brand_profile_id:
            ID of a registered :class:`BrandProfile`, or ``None`` for DEFAULT.
        writing_style:
            One of the style keys in :data:`~style_rewriter.STYLE_PROMPTS`.
        template_type:
            Template to use for commissioning outputs (``cx_plan_report``,
            ``fpt_report``, ``cx_punch_list``, ``cx_summary``).
            Ignored for generic outputs.

        Returns
        -------
        ExportResult
        """
        format = format.lower()
        if format not in SUPPORTED_FORMATS:
            raise ValueError(
                f"Unsupported format '{format}'. "
                f"Supported: {list(SUPPORTED_FORMATS)}"
            )

        brand = self._brand_registry.get_or_default(brand_profile_id)

        # 1. Extract structured data
        plan_data, is_commissioning = self._extract_plan(source_output)

        # 2. Render to Markdown via template or style rewriter
        if is_commissioning and template_type in COMMISSIONING_TEMPLATES:
            raw_markdown = COMMISSIONING_TEMPLATES[template_type](plan_data, brand)
        else:
            raw_markdown = await self._rewriter.rewrite(plan_data, writing_style, template_type)

        # 3. Convert Markdown to the requested output format
        content = self._convert(raw_markdown, format, brand)

        # 4. Build filename
        filename = self._make_filename(source_output, template_type, format)

        result = ExportResult(
            format=format,
            content=content,
            filename=filename,
            metadata={
                "brand_profile_id": brand.brand_id,
                "writing_style": writing_style,
                "template_type": template_type,
                "is_commissioning": is_commissioning,
                "source_keys": list(source_output.keys()),
            },
        )

        with self._lock:
            self._documents[result.document_id] = result

        logger.info(
            "Export complete: %s (%s, %s bytes)",
            result.document_id,
            format,
            len(result.content),
        )
        return result

    # ------------------------------------------------------------------
    # Sync convenience wrapper
    # ------------------------------------------------------------------

    def export_sync(
        self,
        source_output: Dict[str, Any],
        format: str = "markdown",
        brand_profile_id: Optional[str] = None,
        writing_style: str = "formal_engineering",
        template_type: str = "cx_plan_report",
    ) -> ExportResult:
        """Synchronous wrapper around :meth:`export`."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(
                        asyncio.run,
                        self.export(
                            source_output, format, brand_profile_id, writing_style, template_type
                        ),
                    )
                    return future.result()
            return loop.run_until_complete(
                self.export(source_output, format, brand_profile_id, writing_style, template_type)
            )
        except RuntimeError:
            return asyncio.run(
                self.export(source_output, format, brand_profile_id, writing_style, template_type)
            )

    # ------------------------------------------------------------------
    # Document store
    # ------------------------------------------------------------------

    def get_document(self, document_id: str) -> Optional[ExportResult]:
        """Retrieve a previously exported document by ID."""
        with self._lock:
            return self._documents.get(document_id)

    def list_documents(self) -> List[ExportResult]:
        """Return all exported documents."""
        with self._lock:
            return list(self._documents.values())

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_plan(source_output: Dict[str, Any]) -> tuple[Dict[str, Any], bool]:
        """
        Return ``(plan_dict, is_commissioning)``.

        Detects commissioning bot output by checking for ``result.plan`` or
        the presence of commissioning-specific keys (``assets``, ``procedures``).

        When the commissioning bot's ``meta.forms`` list (FPT form JSON objects
        generated by the bot) is present, it is embedded into the returned plan
        dict under the ``_meta_forms`` key so that templates can render the
        richer structured form data.
        """
        # Extract FPT form objects from meta.forms (commissioning bot Output shape)
        meta = source_output.get("meta", {})
        meta_forms: list = meta.get("forms", []) if isinstance(meta, dict) else []

        def _attach_forms(plan: Dict[str, Any]) -> Dict[str, Any]:
            if meta_forms:
                plan = dict(plan)  # shallow copy — don't mutate caller's dict
                plan["_meta_forms"] = meta_forms
            return plan

        # Standard commissioning bot Output shape: { result: { plan: {...} }, ... }
        result = source_output.get("result", {})
        if isinstance(result, dict):
            plan = result.get("plan")
            if isinstance(plan, dict):
                return _attach_forms(plan), True
            # Some commissioning outputs embed the plan directly in result
            if any(k in result for k in ("assets", "procedures", "points")):
                return _attach_forms(result), True

        # Top-level plan shape
        if any(k in source_output for k in ("assets", "procedures", "points", "risk_register")):
            return _attach_forms(source_output), True

        # Generic fallback
        return source_output, False

    def _convert(self, markdown: str, format: str, brand: BrandProfile) -> str:
        """Convert Markdown content to the target format."""
        if format == "markdown":
            return markdown
        if format == "plain_text":
            return self._markdown_to_text(markdown)
        if format == "html":
            return self._markdown_to_html(markdown, brand)
        if format == "latex":
            return self._markdown_to_latex(markdown, brand)
        if format == "pdf":
            return self._markdown_to_pdf(markdown, brand)
        if format == "word":
            return self._markdown_to_word(markdown, brand)
        # Should not reach here given earlier validation
        return markdown

    # ---- Format converters --------------------------------------------------

    @staticmethod
    def _markdown_to_text(markdown: str) -> str:
        """Strip Markdown syntax to produce plain text."""
        import re

        text = markdown
        # Remove headings markers
        text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
        # Remove bold/italic
        text = re.sub(r"\*{1,3}(.*?)\*{1,3}", r"\1", text)
        text = re.sub(r"_{1,3}(.*?)_{1,3}", r"\1", text)
        # Remove link syntax but keep label
        text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
        # Remove table row separators
        text = re.sub(r"^\|[-|: ]+\|$", "", text, flags=re.MULTILINE)
        # Remove horizontal rules
        text = re.sub(r"^---+$", "", text, flags=re.MULTILINE)
        # Normalise blank lines
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def _markdown_to_html(markdown: str, brand: BrandProfile) -> str:
        """Convert Markdown to a styled HTML document."""
        import re

        def md_to_html(md: str) -> str:
            html = md
            # Headings
            for lvl in range(6, 0, -1):
                pattern = r"^" + "#" * lvl + r"\s+(.*?)$"
                html = re.sub(pattern, rf"<h{lvl}>\1</h{lvl}>", html, flags=re.MULTILINE)
            # Bold/italic
            html = re.sub(r"\*\*\*(.*?)\*\*\*", r"<strong><em>\1</em></strong>", html)
            html = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", html)
            html = re.sub(r"\*(.*?)\*", r"<em>\1</em>", html)
            # Code blocks
            html = re.sub(r"```[\w]*\n(.*?)```", r"<pre><code>\1</code></pre>", html, flags=re.DOTALL)
            html = re.sub(r"`(.*?)`", r"<code>\1</code>", html)
            # Links
            html = re.sub(r"\[([^\]]+)\]\(([^\)]+)\)", r'<a href="\2">\1</a>', html)
            # Horizontal rules
            html = re.sub(r"^---+$", "<hr/>", html, flags=re.MULTILINE)
            # Newlines to <br> (simplified)
            html = re.sub(r"\n\n", "</p><p>", html)
            return f"<p>{html}</p>"

        body = md_to_html(markdown)
        return (
            "<!DOCTYPE html>\n<html>\n<head>\n"
            f'<meta charset="UTF-8">\n'
            f"<style>\n"
            f"  body {{ font-family: {brand.font_body}, sans-serif; "
            f"color: #333; max-width: 900px; margin: auto; padding: 2em; }}\n"
            f"  h1, h2, h3 {{ font-family: {brand.font_heading}, sans-serif; "
            f"color: {brand.primary_color}; }}\n"
            f"  h2 {{ border-bottom: 2px solid {brand.secondary_color}; }}\n"
            f"  table {{ border-collapse: collapse; width: 100%; }}\n"
            f"  th, td {{ border: 1px solid #ccc; padding: 6px 10px; text-align: left; }}\n"
            f"  th {{ background-color: {brand.secondary_color}; color: #fff; }}\n"
            f"  a {{ color: {brand.accent_color}; }}\n"
            "</style>\n</head>\n<body>\n"
            f"{body}\n"
            "</body>\n</html>"
        )

    @staticmethod
    def _markdown_to_latex(markdown: str, brand: BrandProfile) -> str:
        """Convert Markdown to a minimal LaTeX document."""
        import re

        def escape(s: str) -> str:
            for char in ["&", "%", "$", "#", "_", "{", "}"]:
                s = s.replace(char, "\\" + char)
            return s

        lines = markdown.split("\n")
        latex_lines: list[str] = [
            "\\documentclass[12pt]{article}",
            "\\usepackage[utf8]{inputenc}",
            "\\usepackage{geometry}",
            "\\geometry{margin=1in}",
            "\\usepackage{booktabs}",
            "\\usepackage{hyperref}",
            "\\title{Document}",
            f"\\author{{{escape(brand.company_name)}}}",
            "\\date{\\today}",
            "\\begin{document}",
            "\\maketitle",
        ]
        for line in lines:
            # Headings
            m6 = re.match(r"^######\s+(.*)", line)
            m5 = re.match(r"^#####\s+(.*)", line)
            m4 = re.match(r"^####\s+(.*)", line)
            m3 = re.match(r"^###\s+(.*)", line)
            m2 = re.match(r"^##\s+(.*)", line)
            m1 = re.match(r"^#\s+(.*)", line)
            if m1:
                latex_lines.append(f"\\section*{{{escape(m1.group(1))}}}")
            elif m2:
                latex_lines.append(f"\\subsection*{{{escape(m2.group(1))}}}")
            elif m3:
                latex_lines.append(f"\\subsubsection*{{{escape(m3.group(1))}}}")
            elif m4 or m5 or m6:
                match = (m4 or m5 or m6)
                latex_lines.append(f"\\paragraph*{{{escape(match.group(1))}}}")
            elif line.startswith("---"):
                latex_lines.append("\\hrulefill")
            elif line.startswith("- ") or line.startswith("* "):
                # Simplified list items (not nested)
                item_text = escape(line[2:])
                latex_lines.append(f"  \\item {item_text}")
            elif re.match(r"^\d+\.\s", line):
                item_text = escape(re.sub(r"^\d+\.\s+", "", line))
                latex_lines.append(f"  \\item {item_text}")
            elif line.strip() == "":
                latex_lines.append("")
            else:
                latex_lines.append(escape(line))
        latex_lines.append("\\end{document}")
        return "\n".join(latex_lines)

    def _markdown_to_pdf(self, markdown: str, brand: BrandProfile) -> str:
        """Convert Markdown to base64-encoded PDF.

        Strategy (ordered by quality):
        1. WeasyPrint (BSD-3): Full HTML→PDF with tables, styling, branding.
        2. reportlab via DocumentGenerationEngine: Plain-text line-by-line.
        3. base64-encoded plain text: Ultimate fallback.
        """
        # 1. Try WeasyPrint rich rendering first
        try:
            from .pdf_renderer import RichPDFRenderer

            renderer = RichPDFRenderer()
            if renderer.is_available():
                html = self._markdown_to_html(markdown, brand)
                metadata = {"document_title": "Murphy System Document"}
                return renderer.render_to_base64(html, brand, metadata)
        except Exception:
            pass  # Fall through to reportlab

        plain_text = self._markdown_to_text(markdown)
        font = brand.font_body if brand.font_body in ("Helvetica", "Times-Roman", "Courier") else "Helvetica"
        styling = {"font": font, "size": 11}

        # 2. reportlab via DocumentGenerationEngine
        if self._doc_engine is not None:
            raw = self._doc_engine.render_pdf(plain_text, styling)
            # render_pdf() returns base64-encoded bytes when reportlab is available,
            # or a plain-text fallback sentinel when it is not.  Ensure the
            # pipeline always emits base64.
            try:
                base64.b64decode(raw, validate=True)
                return raw  # already valid base64
            except Exception:
                return base64.b64encode(raw.encode("utf-8", errors="replace")).decode("ascii")

        # 3. Ultimate fallback (no engine)
        return base64.b64encode(plain_text.encode("utf-8")).decode("ascii")

    def _markdown_to_word(self, markdown: str, brand: BrandProfile) -> str:
        """Convert Markdown to base64-encoded DOCX.

        Delegates to :meth:`~execution.document_generation_engine.DocumentGenerationEngine.render_word`
        when the engine is available (architecture requirement:
        "leverage the existing method — don't reinvent it").  Falls back to a
        plain-text base64 payload when the engine is not importable.
        """
        plain_text = self._markdown_to_text(markdown)
        styling = {"font": brand.font_body, "size": 11}

        if self._doc_engine is not None:
            raw = self._doc_engine.render_word(plain_text, styling)
            # Same normalisation as _markdown_to_pdf — ensure output is base64.
            try:
                base64.b64decode(raw, validate=True)
                return raw  # already valid base64
            except Exception:
                return base64.b64encode(raw.encode("utf-8", errors="replace")).decode("ascii")

        # Ultimate fallback (no engine)
        return base64.b64encode(plain_text.encode("utf-8")).decode("ascii")

    @staticmethod
    def _make_filename(source_output: Dict[str, Any], template_type: str, format: str) -> str:
        """Generate a safe filename for the exported document."""
        ext_map = {
            "pdf": "pdf",
            "word": "docx",
            "html": "html",
            "markdown": "md",
            "latex": "tex",
            "plain_text": "txt",
        }
        ext = ext_map.get(format, format)
        result = source_output.get("result", {})
        if isinstance(result, dict):
            plan = result.get("plan", result)
            site = str(plan.get("site", "")).replace(" ", "_").lower() if isinstance(plan, dict) else ""
        else:
            site = ""
        name = f"{template_type}_{site}_{datetime.now(timezone.utc).strftime('%Y%m%d')}" if site else template_type
        return f"{name}.{ext}"

    # ------------------------------------------------------------------
    # Introspection helpers
    # ------------------------------------------------------------------

    @staticmethod
    def available_formats() -> Dict[str, str]:
        """Return the supported format map."""
        return dict(SUPPORTED_FORMATS)

    @staticmethod
    def available_styles() -> List[str]:
        """Return the available writing styles."""
        from .style_rewriter import STYLE_PROMPTS

        return list(STYLE_PROMPTS.keys())

    @staticmethod
    def available_templates() -> List[str]:
        """Return the available template names."""
        return list(COMMISSIONING_TEMPLATES.keys())
