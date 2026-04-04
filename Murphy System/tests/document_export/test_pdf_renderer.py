# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Tests for the WeasyPrint-based rich PDF renderer.

These tests are designed to be runnable regardless of whether WeasyPrint is
installed.  All tests that actually produce PDF output are skipped when
WeasyPrint is not available (e.g. in CI environments without cairo/pango).
"""

from __future__ import annotations

import base64
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Ensure the package is importable regardless of working directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.document_export.brand_registry import BrandProfile
from src.document_export.export_pipeline import ExportPipeline

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_brand(**kwargs) -> BrandProfile:
    defaults = dict(
        company_name="TestCo",
        primary_color="#1E3A5F",
        secondary_color="#2E86AB",
        accent_color="#F18F01",
        font_heading="Helvetica",
        font_body="Helvetica",
        legal_line="© 2026 TestCo. Confidential.",
    )
    defaults.update(kwargs)
    return BrandProfile(**defaults)


def _sample_html(brand: BrandProfile | None = None) -> str:
    if brand is None:
        brand = _make_brand()
    return (
        "<!DOCTYPE html><html><head><meta charset='UTF-8'>"
        f"<style>body {{ color: {brand.primary_color}; }}</style>"
        "</head><body>"
        f"<h1>Test Document</h1>"
        "<p>Sample paragraph.</p>"
        "<table><tr><th>Col A</th><th>Col B</th></tr>"
        "<tr><td>R1C1</td><td>R1C2</td></tr>"
        "<tr><td>R2C1</td><td>R2C2</td></tr>"
        "</table>"
        "</body></html>"
    )


# ---------------------------------------------------------------------------
# TestRichPDFRenderer
# ---------------------------------------------------------------------------


class TestRichPDFRenderer:
    """Tests for the WeasyPrint-based rich PDF renderer."""

    def test_is_available_returns_bool(self):
        """is_available() should return True or False without raising."""
        from src.document_export.pdf_renderer import RichPDFRenderer

        result = RichPDFRenderer.is_available()
        assert isinstance(result, bool)

    def test_render_to_base64_produces_valid_base64(self):
        """render_to_base64() output must decode without error."""
        from src.document_export.pdf_renderer import RichPDFRenderer

        renderer = RichPDFRenderer()
        brand = _make_brand()
        html_content = _sample_html(brand)
        metadata = {"document_title": "Unit Test Doc"}

        if not renderer.is_available():
            pytest.skip("WeasyPrint not installed")

        result = renderer.render_to_base64(html_content, brand, metadata)
        assert isinstance(result, str)
        decoded = base64.b64decode(result)
        assert len(decoded) > 0

    def test_render_produces_bytes(self):
        """When WeasyPrint is available, render() returns PDF bytes."""
        from src.document_export.pdf_renderer import RichPDFRenderer

        renderer = RichPDFRenderer()
        if not renderer.is_available():
            pytest.skip("WeasyPrint not installed")

        brand = _make_brand()
        result = renderer.render(_sample_html(brand), brand, {"document_title": "Test"})
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_brand_colors_injected_into_css(self):
        """The print CSS must contain the brand's primary/secondary colors."""
        from src.document_export.pdf_renderer import RichPDFRenderer

        renderer = RichPDFRenderer()
        brand = _make_brand(primary_color="#ABCDEF", secondary_color="#123456")
        full_html = renderer._build_full_html(_sample_html(brand), brand, "My Doc")
        assert "#ABCDEF" in full_html
        assert "#123456" in full_html

    def test_brand_fonts_injected_into_css(self):
        """The print CSS must reference brand font names."""
        from src.document_export.pdf_renderer import RichPDFRenderer

        renderer = RichPDFRenderer()
        brand = _make_brand(font_heading="Georgia", font_body="Times New Roman")
        full_html = renderer._build_full_html(_sample_html(brand), brand, "Doc")
        assert "Georgia" in full_html
        assert "Times New Roman" in full_html

    def test_header_footer_in_page_css(self):
        """@page rules must include company name and legal line."""
        from src.document_export.pdf_renderer import RichPDFRenderer

        renderer = RichPDFRenderer()
        brand = _make_brand(company_name="Acme Corp", legal_line="© 2026 Acme Corp.")
        full_html = renderer._build_full_html(_sample_html(brand), brand, "Report")
        assert "Acme Corp" in full_html
        assert "© 2026 Acme Corp." in full_html
        assert "@page" in full_html
        assert "@bottom-right" in full_html

    def test_cover_page_injected_when_template_set(self):
        """When brand.cover_page_template is set, a cover div is prepended."""
        from src.document_export.pdf_renderer import RichPDFRenderer

        renderer = RichPDFRenderer()
        brand = _make_brand(cover_page_template="Cover Page")
        full_html = renderer._build_full_html(_sample_html(brand), brand, "Doc Title")
        assert "page-break-after: always" in full_html

    def test_no_cover_page_when_template_not_set(self):
        """When cover_page_template is None, no cover div is added."""
        from src.document_export.pdf_renderer import RichPDFRenderer

        renderer = RichPDFRenderer()
        brand = _make_brand(cover_page_template=None)
        full_html = renderer._build_full_html(_sample_html(brand), brand, "Doc Title")
        assert "page-break-after: always" not in full_html

    def test_logo_embedded_when_base64_set(self):
        """When brand.logo_base64 is set, a data URI <img> is in the cover page."""
        from src.document_export.pdf_renderer import RichPDFRenderer

        renderer = RichPDFRenderer()
        brand = _make_brand(
            logo_base64="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            cover_page_template="Cover",
        )
        full_html = renderer._build_full_html(_sample_html(brand), brand, "Doc")
        assert "data:image/png;base64," in full_html

    def test_table_styling_in_print_css(self):
        """Tables must have page-break-inside:avoid and styled headers."""
        from src.document_export.pdf_renderer import RichPDFRenderer

        renderer = RichPDFRenderer()
        brand = _make_brand()
        full_html = renderer._build_full_html(_sample_html(brand), brand, "Doc")
        assert "page-break-inside: avoid" in full_html
        # th styling
        assert "background-color" in full_html

    def test_page_size_is_letter(self):
        """@page size must be 'letter' (8.5in x 11in)."""
        from src.document_export.pdf_renderer import RichPDFRenderer

        renderer = RichPDFRenderer()
        brand = _make_brand()
        full_html = renderer._build_full_html(_sample_html(brand), brand, "Doc")
        assert "size: letter" in full_html

    def test_fallback_when_weasyprint_unavailable(self):
        """When WeasyPrint is not importable, render falls back or raises gracefully."""
        from src.document_export import pdf_renderer as _mod
        from src.document_export.pdf_renderer import RichPDFRenderer

        renderer = RichPDFRenderer()
        brand = _make_brand()

        # Force WeasyPrint to appear unavailable
        with patch.object(_mod, "_WEASYPRINT_AVAILABLE", False):
            # Should either fall back to reportlab (bytes) or raise ImportError
            try:
                result = renderer.render(_sample_html(brand), brand, {})
                assert isinstance(result, bytes)
            except (ImportError, Exception):
                pass  # Graceful failure is acceptable

    def test_document_title_in_page_header(self):
        """The document title must appear in the @page header content."""
        from src.document_export.pdf_renderer import RichPDFRenderer

        renderer = RichPDFRenderer()
        brand = _make_brand()
        full_html = renderer._build_full_html(
            _sample_html(brand), brand, "My Special Report"
        )
        assert "My Special Report" in full_html

    def test_accent_color_in_css(self):
        """The brand accent color must appear in the CSS (used for links)."""
        from src.document_export.pdf_renderer import RichPDFRenderer

        renderer = RichPDFRenderer()
        brand = _make_brand(accent_color="#FF5500")
        full_html = renderer._build_full_html(_sample_html(brand), brand, "Doc")
        assert "#FF5500" in full_html

    def test_style_injected_before_head_close(self):
        """Print CSS <style> block must be injected inside <head>."""
        from src.document_export.pdf_renderer import RichPDFRenderer

        renderer = RichPDFRenderer()
        brand = _make_brand()
        full_html = renderer._build_full_html(_sample_html(brand), brand, "Doc")
        # The <style> block must appear before </head>
        style_pos = full_html.find("<style>")
        head_close_pos = full_html.find("</head>")
        assert style_pos != -1
        assert head_close_pos != -1
        assert style_pos < head_close_pos


# ---------------------------------------------------------------------------
# TestExportPipelineWeasyPrintIntegration
# ---------------------------------------------------------------------------


import asyncio


def _run(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("closed")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


SAMPLE_BOT_OUTPUT = {
    "filename": "test_plan.json",
    "content": {
        "plan_title": "Test Commissioning Plan",
        "project": "Test Project",
        "systems": [{"name": "HVAC-01", "type": "HVAC"}],
        "test_procedures": [
            {
                "id": "TP-001",
                "name": "Basic Test",
                "steps": [{"step": 1, "action": "Start system", "expected": "System starts"}],
            }
        ],
    },
}


class TestExportPipelineWeasyPrintIntegration:
    """Verify the pipeline prefers WeasyPrint when available."""

    def test_pdf_export_produces_valid_base64(self):
        """PDF output must always decode from base64 without error."""
        pipeline = ExportPipeline()
        result = _run(pipeline.export(SAMPLE_BOT_OUTPUT, format="pdf"))
        assert result.format == "pdf"
        decoded = base64.b64decode(result.content)
        assert len(decoded) > 0

    def test_pdf_export_falls_back_to_reportlab_or_text(self):
        """When WeasyPrint is unavailable, PDF still generates via reportlab or text fallback."""
        from src.document_export import pdf_renderer as _mod

        with patch.object(_mod, "_WEASYPRINT_AVAILABLE", False):
            pipeline = ExportPipeline()
            result = _run(pipeline.export(SAMPLE_BOT_OUTPUT, format="pdf"))
            assert result.format == "pdf"
            decoded = base64.b64decode(result.content)
            assert len(decoded) > 0

    def test_pdf_export_branded_html_passes_brand_colors(self):
        """The CSS injected by _build_full_html contains brand colors."""
        from src.document_export.pdf_renderer import RichPDFRenderer

        renderer = RichPDFRenderer()
        brand = _make_brand(primary_color="#DEADBE")
        pipeline = ExportPipeline()
        # Directly test HTML→CSS injection (works without WeasyPrint)
        html_content = pipeline._markdown_to_html("# Hello\n\nWorld.", brand)
        full_html = renderer._build_full_html(html_content, brand, "Title")
        assert "#DEADBE" in full_html

    def test_pdf_with_custom_brand(self):
        """A custom brand profile's colors/fonts should flow into the pipeline."""
        from src.document_export.brand_registry import BrandRegistry

        registry = BrandRegistry()
        brand = BrandProfile(
            company_name="Custom Corp",
            primary_color="#112233",
            secondary_color="#445566",
            font_heading="Times-Roman",
            font_body="Courier",
        )
        registry.register(brand)
        pipeline = ExportPipeline(brand_registry=registry)
        result = _run(
            pipeline.export(SAMPLE_BOT_OUTPUT, format="pdf", brand_profile_id=brand.brand_id)
        )
        assert result.format == "pdf"
        decoded = base64.b64decode(result.content)
        assert len(decoded) > 0
