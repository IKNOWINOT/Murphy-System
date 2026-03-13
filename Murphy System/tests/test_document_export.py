# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Tests for the Document Export pipeline.

Covers:
- Brand profile creation and retrieval
- Style rewriter deterministic fallback (no LLM) produces valid Markdown
- Commissioning templates render valid output from sample plan data
- Full export pipeline for each format (pdf, word, html, markdown, latex, plain_text)
- Export pipeline with brand injection includes brand elements in output
- API endpoint returns correct responses
"""

from __future__ import annotations

import asyncio
import sys
import os

import pytest

# Ensure the package is importable regardless of working directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.document_export.brand_registry import BrandProfile, BrandRegistry
from src.document_export.style_rewriter import DocumentStyleRewriter, STYLE_PROMPTS
from src.document_export.templates.commissioning import (
    cx_plan_report,
    cx_punch_list,
    cx_summary,
    fpt_report,
    COMMISSIONING_TEMPLATES,
)
from src.document_export.export_pipeline import ExportPipeline, ExportResult, SUPPORTED_FORMATS

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

SAMPLE_PLAN: dict = {
    "site": "Pacific Tower, Portland OR",
    "system": "AHU-1 Variable Air Volume",
    "assets": [
        {
            "id": "AHU-01",
            "name": "Air Handling Unit 1",
            "type": "AHU",
            "tag": "AHU-01",
            "location": "Mechanical Room B2",
            "meta": {},
        },
        {
            "id": "VAV-01",
            "name": "VAV Box Zone 1",
            "type": "VAV",
            "tag": "VAV-01",
            "location": "Floor 3",
            "meta": {},
        },
    ],
    "points": [
        {
            "name": "Supply Air Temp",
            "point_type": "analog_input",
            "unit": "°F",
            "source": "BACnet",
            "asset_id": "AHU-01",
            "range": {"min": 40, "max": 90, "unit": "°F"},
        },
        {
            "name": "Supply Fan Status",
            "point_type": "binary_input",
            "unit": "",
            "source": "BACnet",
            "asset_id": "AHU-01",
            "range": {},
        },
    ],
    "procedures": [
        {
            "name": "Supply Fan Start/Stop Test",
            "preconditions": ["BAS online", "AHU-01 accessible"],
            "steps": ["Enable AHU-01 from BAS", "Verify fan motor starts", "Check supply air temp drops"],
            "acceptance": ["Fan starts within 30s", "Supply air temp reaches setpoint ±2°F"],
            "risks": ["Motor overload during first start"],
        }
    ],
    "risk_register": {
        "items": [
            {
                "id": "R-001",
                "description": "Refrigerant leak during startup",
                "severity": "high",
                "mitigation": "Pressure test before commissioning",
            },
            {
                "id": "R-002",
                "description": "BAS network latency",
                "severity": "low",
                "mitigation": "Verify network latency < 100ms",
            },
        ]
    },
    "deliverables": [
        {"name": "Commissioning Plan", "type": "document", "link": ""},
        {"name": "FPT Checklists", "type": "checklist", "link": ""},
    ],
    "schedule": {
        "window": {"start": "2026-04-01", "end": "2026-04-30"},
        "dependencies": ["TAB complete", "Controls wiring complete"],
    },
}

SAMPLE_BOT_OUTPUT: dict = {
    "result": {"plan": SAMPLE_PLAN},
    "confidence": 0.92,
    "notes": ["ASHRAE Guideline 1.5-2017 applied"],
    "meta": {},
    "provenance": ["commissioning_bot@1.0.0"],
}


def _run(coro):
    """Helper: run an async coroutine synchronously in tests."""
    return asyncio.run(coro)


# ===========================================================================
# Brand Registry Tests
# ===========================================================================


class TestBrandRegistry:
    def test_default_brand_always_present(self):
        registry = BrandRegistry()
        brand = registry.get("default")
        assert brand is not None
        assert brand.brand_id == "default"
        assert brand.company_name == "Murphy System"

    def test_register_and_retrieve(self):
        registry = BrandRegistry()
        profile = BrandProfile(company_name="Acme Corp", primary_color="#FF0000")
        registry.register(profile)
        retrieved = registry.get(profile.brand_id)
        assert retrieved is not None
        assert retrieved.company_name == "Acme Corp"
        assert retrieved.primary_color == "#FF0000"

    def test_list_brands_includes_default_and_registered(self):
        registry = BrandRegistry()
        profile = BrandProfile(company_name="Beta Inc")
        registry.register(profile)
        brands = registry.list_brands()
        ids = [b.brand_id for b in brands]
        assert "default" in ids
        assert profile.brand_id in ids

    def test_get_or_default_returns_default_for_missing(self):
        registry = BrandRegistry()
        brand = registry.get_or_default("nonexistent-id")
        assert brand.brand_id == "default"

    def test_get_or_default_returns_default_for_none(self):
        registry = BrandRegistry()
        brand = registry.get_or_default(None)
        assert brand.brand_id == "default"

    def test_delete_custom_brand(self):
        registry = BrandRegistry()
        profile = BrandProfile(company_name="Delete Me")
        registry.register(profile)
        assert registry.get(profile.brand_id) is not None
        result = registry.delete(profile.brand_id)
        assert result is True
        assert registry.get(profile.brand_id) is None

    def test_cannot_delete_default_brand(self):
        registry = BrandRegistry()
        result = registry.delete("default")
        assert result is False
        assert registry.get("default") is not None

    def test_brand_render_header(self):
        profile = BrandProfile(
            company_name="Acme",
            header_template="**{company_name}** | {document_title} | {date}",
        )
        rendered = profile.render_header({"document_title": "Test Doc", "date": "2026-01-01"})
        assert "Acme" in rendered
        assert "Test Doc" in rendered

    def test_brand_render_footer(self):
        profile = BrandProfile(
            legal_line="© 2026 Test Corp.",
            footer_template="{legal_line} | Page {page_number}",
        )
        rendered = profile.render_footer({"page_number": "1"})
        assert "© 2026 Test Corp." in rendered


# ===========================================================================
# Style Rewriter Tests
# ===========================================================================


class TestDocumentStyleRewriter:
    def test_all_builtin_styles_defined(self):
        assert "formal_engineering" in STYLE_PROMPTS
        assert "executive_summary" in STYLE_PROMPTS
        assert "technical_manual" in STYLE_PROMPTS
        assert "client_facing" in STYLE_PROMPTS
        assert "academic" in STYLE_PROMPTS
        assert "casual" in STYLE_PROMPTS

    def test_available_styles_returns_list(self):
        styles = DocumentStyleRewriter.available_styles()
        assert isinstance(styles, list)
        assert len(styles) >= 6

    def test_deterministic_fallback_returns_markdown(self):
        rewriter = DocumentStyleRewriter(llm_client=None)
        result = _run(rewriter.rewrite(SAMPLE_PLAN, "formal_engineering", "cx_plan_report"))
        assert isinstance(result, str)
        assert len(result) > 0
        # Should produce headings
        assert "#" in result

    def test_deterministic_fallback_includes_data_keys(self):
        rewriter = DocumentStyleRewriter(llm_client=None)
        result = _run(rewriter.rewrite(SAMPLE_PLAN, "executive_summary", "cx_summary"))
        # Key sections should be present (case-insensitive title conversion)
        assert "Site" in result or "site" in result.lower()

    def test_unknown_style_falls_back_to_formal_engineering(self):
        rewriter = DocumentStyleRewriter(llm_client=None)
        # Should not raise
        result = _run(rewriter.rewrite(SAMPLE_PLAN, "unknown_style_xyz", "cx_plan_report"))
        assert isinstance(result, str)
        assert len(result) > 0

    def test_default_style_alias(self):
        rewriter = DocumentStyleRewriter(llm_client=None)
        result = _run(rewriter.rewrite(SAMPLE_PLAN, "default", "cx_plan_report"))
        assert isinstance(result, str)

    def test_rewrite_sync_wrapper(self):
        rewriter = DocumentStyleRewriter(llm_client=None)
        result = rewriter.rewrite_sync(SAMPLE_PLAN, "technical_manual", "fpt_report")
        assert isinstance(result, str)
        assert len(result) > 0


# ===========================================================================
# Commissioning Template Tests
# ===========================================================================


class TestCommissioningTemplates:
    def test_cx_plan_report_renders(self):
        result = cx_plan_report(SAMPLE_PLAN)
        assert "Commissioning Plan Report" in result
        assert "Pacific Tower" in result
        assert "AHU-1 Variable Air Volume" in result

    def test_cx_plan_report_includes_assets_table(self):
        result = cx_plan_report(SAMPLE_PLAN)
        assert "AHU-01" in result
        assert "Air Handling Unit 1" in result

    def test_cx_plan_report_includes_procedures(self):
        result = cx_plan_report(SAMPLE_PLAN)
        assert "Supply Fan Start/Stop Test" in result
        assert "Enable AHU-01 from BAS" in result

    def test_cx_plan_report_includes_risk_register(self):
        result = cx_plan_report(SAMPLE_PLAN)
        assert "R-001" in result
        assert "Refrigerant leak" in result

    def test_cx_plan_report_with_brand(self):
        brand = BrandProfile(company_name="Oregon CX Consultants", legal_line="© 2026 Oregon CX.")
        result = cx_plan_report(SAMPLE_PLAN, brand)
        assert "Oregon CX Consultants" in result
        assert "© 2026 Oregon CX." in result

    def test_fpt_report_renders(self):
        result = fpt_report(SAMPLE_PLAN)
        assert "Functional Performance Test" in result
        assert "FPT-001" in result

    def test_fpt_report_includes_steps_table(self):
        result = fpt_report(SAMPLE_PLAN)
        assert "Enable AHU-01 from BAS" in result
        # Table header
        assert "Pass/Fail" in result

    def test_cx_punch_list_renders(self):
        result = cx_punch_list(SAMPLE_PLAN)
        assert "Punch List" in result
        assert "R-001" in result or "Refrigerant" in result

    def test_cx_summary_renders(self):
        result = cx_summary(SAMPLE_PLAN)
        assert "Executive Summary" in result
        assert "2" in result  # 2 assets
        assert "1" in result  # 1 procedure

    def test_cx_summary_includes_risk_summary(self):
        result = cx_summary(SAMPLE_PLAN)
        assert "Risk" in result

    def test_template_registry_complete(self):
        assert "cx_plan_report" in COMMISSIONING_TEMPLATES
        assert "fpt_report" in COMMISSIONING_TEMPLATES
        assert "cx_punch_list" in COMMISSIONING_TEMPLATES
        assert "cx_summary" in COMMISSIONING_TEMPLATES

    def test_empty_plan_renders_without_error(self):
        empty_plan: dict = {}
        for fn in COMMISSIONING_TEMPLATES.values():
            result = fn(empty_plan)
            assert isinstance(result, str)

    def test_templates_accept_brand(self):
        brand = BrandProfile(company_name="ACME Cx")
        for fn in COMMISSIONING_TEMPLATES.values():
            result = fn(SAMPLE_PLAN, brand)
            assert "ACME Cx" in result


# ===========================================================================
# Export Pipeline Tests
# ===========================================================================


class TestExportPipeline:
    def _pipeline(self) -> ExportPipeline:
        return ExportPipeline()

    def test_export_markdown(self):
        pipeline = self._pipeline()
        result = _run(pipeline.export(SAMPLE_BOT_OUTPUT, format="markdown"))
        assert isinstance(result, ExportResult)
        assert result.format == "markdown"
        assert "Commissioning Plan Report" in result.content
        assert result.filename.endswith(".md")

    def test_export_html(self):
        pipeline = self._pipeline()
        result = _run(pipeline.export(SAMPLE_BOT_OUTPUT, format="html"))
        assert result.format == "html"
        assert "<!DOCTYPE html>" in result.content
        assert result.filename.endswith(".html")

    def test_export_plain_text(self):
        pipeline = self._pipeline()
        result = _run(pipeline.export(SAMPLE_BOT_OUTPUT, format="plain_text"))
        assert result.format == "plain_text"
        # Should not contain Markdown heading markers
        assert "# " not in result.content
        assert result.filename.endswith(".txt")

    def test_export_latex(self):
        pipeline = self._pipeline()
        result = _run(pipeline.export(SAMPLE_BOT_OUTPUT, format="latex"))
        assert result.format == "latex"
        assert "\\documentclass" in result.content
        assert result.filename.endswith(".tex")

    def test_export_pdf(self):
        pipeline = self._pipeline()
        result = _run(pipeline.export(SAMPLE_BOT_OUTPUT, format="pdf"))
        assert result.format == "pdf"
        # Content is base64-encoded (binary or text fallback)
        import base64
        decoded = base64.b64decode(result.content)
        assert len(decoded) > 0
        assert result.filename.endswith(".pdf")

    def test_export_word(self):
        pipeline = self._pipeline()
        result = _run(pipeline.export(SAMPLE_BOT_OUTPUT, format="word"))
        assert result.format == "word"
        import base64
        decoded = base64.b64decode(result.content)
        assert len(decoded) > 0
        assert result.filename.endswith(".docx")

    def test_export_all_formats_produce_output(self):
        pipeline = self._pipeline()
        for fmt in SUPPORTED_FORMATS:
            result = _run(pipeline.export(SAMPLE_BOT_OUTPUT, format=fmt))
            assert isinstance(result, ExportResult), f"ExportResult not returned for {fmt}"
            assert len(result.content) > 0, f"Empty content for {fmt}"

    def test_export_with_brand_injection(self):
        registry = BrandRegistry()
        brand = BrandProfile(company_name="Test Eng LLC", legal_line="© 2026 Test Eng LLC.")
        registry.register(brand)
        pipeline = ExportPipeline(brand_registry=registry)
        result = _run(
            pipeline.export(SAMPLE_BOT_OUTPUT, format="markdown", brand_profile_id=brand.brand_id)
        )
        assert "Test Eng LLC" in result.content

    def test_export_with_fpt_template(self):
        pipeline = self._pipeline()
        result = _run(
            pipeline.export(SAMPLE_BOT_OUTPUT, format="markdown", template_type="fpt_report")
        )
        assert "Functional Performance Test" in result.content

    def test_export_with_cx_summary_template(self):
        pipeline = self._pipeline()
        result = _run(
            pipeline.export(SAMPLE_BOT_OUTPUT, format="markdown", template_type="cx_summary")
        )
        assert "Executive Summary" in result.content

    def test_export_with_cx_punch_list_template(self):
        pipeline = self._pipeline()
        result = _run(
            pipeline.export(SAMPLE_BOT_OUTPUT, format="markdown", template_type="cx_punch_list")
        )
        assert "Punch List" in result.content

    def test_export_invalid_format_raises(self):
        pipeline = self._pipeline()
        with pytest.raises(ValueError):
            _run(pipeline.export(SAMPLE_BOT_OUTPUT, format="invalid_format"))

    def test_export_stores_document(self):
        pipeline = self._pipeline()
        result = _run(pipeline.export(SAMPLE_BOT_OUTPUT, format="markdown"))
        stored = pipeline.get_document(result.document_id)
        assert stored is not None
        assert stored.document_id == result.document_id

    def test_list_documents(self):
        pipeline = self._pipeline()
        _run(pipeline.export(SAMPLE_BOT_OUTPUT, format="markdown"))
        _run(pipeline.export(SAMPLE_BOT_OUTPUT, format="html"))
        docs = pipeline.list_documents()
        assert len(docs) >= 2

    def test_export_metadata_contains_brand(self):
        pipeline = self._pipeline()
        result = _run(pipeline.export(SAMPLE_BOT_OUTPUT, format="markdown"))
        assert "brand_profile_id" in result.metadata
        assert result.metadata["brand_profile_id"] == "default"

    def test_export_generic_bot_output(self):
        """Non-commissioning bot output should still produce a document."""
        generic_output = {
            "result": {"summary": "Research complete", "findings": ["finding1", "finding2"]},
            "confidence": 0.8,
        }
        pipeline = self._pipeline()
        result = _run(pipeline.export(generic_output, format="markdown"))
        assert isinstance(result, ExportResult)
        assert len(result.content) > 0

    def test_export_sync_wrapper(self):
        pipeline = self._pipeline()
        result = pipeline.export_sync(SAMPLE_BOT_OUTPUT, format="markdown")
        assert isinstance(result, ExportResult)
        assert result.format == "markdown"

    def test_available_formats(self):
        formats = ExportPipeline.available_formats()
        assert "pdf" in formats
        assert "word" in formats
        assert "html" in formats
        assert "markdown" in formats
        assert "latex" in formats
        assert "plain_text" in formats

    def test_available_styles(self):
        styles = ExportPipeline.available_styles()
        assert "formal_engineering" in styles
        assert "executive_summary" in styles

    def test_available_templates(self):
        templates = ExportPipeline.available_templates()
        assert "cx_plan_report" in templates
        assert "fpt_report" in templates


# ===========================================================================
# API Tests (requires FastAPI)
# ===========================================================================


class TestExportAPI:
    """Tests for the FastAPI router endpoints."""

    @pytest.fixture
    def client(self):
        try:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
        except (ImportError, RuntimeError):
            pytest.skip("FastAPI / httpx not installed")

        from src.document_export.api import create_router

        app = FastAPI()
        router = create_router()
        app.include_router(router)
        return TestClient(app)

    def test_list_formats(self, client):
        resp = client.get("/api/export/formats")
        assert resp.status_code == 200
        data = resp.json()
        assert "formats" in data
        assert "pdf" in data["formats"]

    def test_list_styles(self, client):
        resp = client.get("/api/export/styles")
        assert resp.status_code == 200
        data = resp.json()
        assert "styles" in data
        assert "formal_engineering" in data["styles"]

    def test_list_templates(self, client):
        resp = client.get("/api/export/templates")
        assert resp.status_code == 200
        data = resp.json()
        assert "templates" in data
        assert "cx_plan_report" in data["templates"]

    def test_post_export_markdown(self, client):
        payload = {
            "source_output": SAMPLE_BOT_OUTPUT,
            "format": "markdown",
            "writing_style": "formal_engineering",
            "template_type": "cx_plan_report",
        }
        resp = client.post("/api/export", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["format"] == "markdown"
        assert len(data["content"]) > 0
        assert "document_id" in data

    def test_post_export_invalid_format(self, client):
        payload = {
            "source_output": SAMPLE_BOT_OUTPUT,
            "format": "not_a_format",
        }
        resp = client.post("/api/export", json=payload)
        assert resp.status_code == 400

    def test_post_brand_register(self, client):
        payload = {
            "company_name": "API Test Corp",
            "primary_color": "#AABBCC",
        }
        resp = client.post("/api/brands", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["company_name"] == "API Test Corp"
        assert "brand_id" in data

    def test_list_brands(self, client):
        resp = client.get("/api/brands")
        assert resp.status_code == 200
        data = resp.json()
        assert "brands" in data
        # DEFAULT brand must always be present
        ids = [b["brand_id"] for b in data["brands"]]
        assert "default" in ids

    def test_get_brand_by_id(self, client):
        resp = client.get("/api/brands/default")
        assert resp.status_code == 200
        data = resp.json()
        assert data["brand_id"] == "default"

    def test_get_brand_not_found(self, client):
        resp = client.get("/api/brands/nonexistent-brand-id")
        assert resp.status_code == 404

    def test_delete_brand(self, client):
        # First register a brand
        create_resp = client.post("/api/brands", json={"company_name": "To Delete"})
        brand_id = create_resp.json()["brand_id"]
        # Delete it
        del_resp = client.delete(f"/api/brands/{brand_id}")
        assert del_resp.status_code == 200
        # Confirm gone
        get_resp = client.get(f"/api/brands/{brand_id}")
        assert get_resp.status_code == 404

    def test_cannot_delete_default_brand(self, client):
        resp = client.delete("/api/brands/default")
        assert resp.status_code == 404
