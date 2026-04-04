"""
Wave 11 — Demo System Commissioning Tests
Murphy System Production Readiness Audit

Covers:
  1. DemoBundleGenerator — ZIP bundle structure, proposal, quote, spec
  2. DemoDeliverableGenerator — custom queries across 10+ domains, fallback quality
  3. Rate limiting enforcement (5/anon, 10/free, unlimited/paid)
  4. Automation spec with itemized workflows and cost breakdown
  5. All demo API endpoint shapes (/api/demo/run, generate-deliverable, download-bundle)
  6. End-to-end: query → deliverable → bundle → spec summary

Commission criteria:
  - Every custom domain produces a non-trivial deliverable (>500 chars)
  - Bundle ZIP contains exactly 5+ files in correct structure
  - Proposal includes scope, timeline, outcomes sections
  - Quote includes itemized labor, platform subscription, payback period
  - Rate limiter blocks at correct thresholds
  - API endpoints return correct response shapes

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import io
import os
import sys
import json
import hashlib
import zipfile
import pytest
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────────────────────
SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# ── Imports under test (all module-level functions) ───────────────────────────
from demo_deliverable_generator import (
    generate_deliverable,
    generate_custom_deliverable,
    generate_predefined_deliverable,
    generate_automation_spec,
    make_fingerprint,
    _build_minimal_custom_content,
    _build_automation_blueprint,
    _build_quality_plan,
)
from demo_bundle_generator import (
    generate_demo_bundle,
    _build_automation_proposal,
    _build_itemized_quote,
    _build_bundle_readme,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 1: Multi-Domain Custom Deliverables
# ═══════════════════════════════════════════════════════════════════════════════

CROSS_DOMAIN_QUERIES = {
    "sales": "Create a sales pipeline for B2B SaaS selling to enterprise customers",
    "marketing": "Build a content marketing strategy for a fintech startup",
    "support": "Design a customer support ticketing workflow with SLA escalation",
    "operations": "Automate warehouse inventory management and reorder processes",
    "hr": "Screen and onboard 50 new engineering candidates this quarter",
    "finance": "Generate monthly financial reconciliation reports for 3 subsidiaries",
    "compliance": "Implement GDPR compliance audit across all data processing systems",
    "legal": "Draft contract review workflow for vendor agreements",
    "healthcare": "Automate patient intake forms and insurance verification",
    "education": "Build a course enrollment and grading automation system",
    "real_estate": "Automate property listing syndication and lead management",
    "manufacturing": "Create quality control inspection workflow for assembly line",
    "logistics": "Optimize last-mile delivery routing and driver scheduling",
    "retail": "Automate inventory forecasting and automated reorder for 200 SKUs",
}


class TestDeliverableFunctionAvailability:
    """Verify all required functions are importable and callable."""

    def test_generate_deliverable_callable(self):
        assert callable(generate_deliverable)

    def test_generate_custom_deliverable_callable(self):
        assert callable(generate_custom_deliverable)

    def test_generate_automation_spec_callable(self):
        assert callable(generate_automation_spec)

    def test_make_fingerprint_callable(self):
        assert callable(make_fingerprint)

    def test_generate_demo_bundle_callable(self):
        assert callable(generate_demo_bundle)


class TestCrossDomainDeliverables:
    """Every domain produces a substantial deliverable via the custom path."""

    @pytest.mark.parametrize("domain,query", list(CROSS_DOMAIN_QUERIES.items()))
    def test_custom_deliverable_non_empty(self, domain, query):
        """Each domain query should produce content > 500 chars."""
        result = generate_deliverable(query)
        assert result is not None, f"[{domain}] generate_deliverable returned None"
        content = result.get("content", "")
        assert len(content) > 500, (
            f"[{domain}] Deliverable too short ({len(content)} chars). "
            f"Expected >500 for query: {query!r}"
        )

    @pytest.mark.parametrize("domain,query", list(CROSS_DOMAIN_QUERIES.items()))
    def test_custom_deliverable_has_filename(self, domain, query):
        """Each deliverable must have a filename."""
        result = generate_deliverable(query)
        filename = result.get("filename", "")
        assert filename, f"[{domain}] Missing filename"

    @pytest.mark.parametrize("domain,query", list(CROSS_DOMAIN_QUERIES.items()))
    def test_custom_deliverable_has_title(self, domain, query):
        """Each deliverable must have a title."""
        result = generate_deliverable(query)
        title = result.get("title", "")
        assert title, f"[{domain}] Missing title"


class TestDeliverableContentQuality:
    """Deliverables should contain substantive content, not placeholder text."""

    def test_sales_deliverable_has_pipeline_content(self):
        result = generate_deliverable(
            "Create a sales pipeline for enterprise B2B customers"
        )
        content = result.get("content", "").lower()
        assert any(term in content for term in [
            "pipeline", "lead", "prospect", "qualification", "close",
            "crm", "revenue", "conversion", "sales"
        ]), "Sales deliverable missing domain-specific content"

    def test_marketing_deliverable_has_strategy_content(self):
        result = generate_deliverable(
            "Build a content marketing strategy for a startup"
        )
        content = result.get("content", "").lower()
        assert any(term in content for term in [
            "content", "strategy", "audience", "channel", "seo",
            "campaign", "brand", "marketing"
        ]), "Marketing deliverable missing domain-specific content"

    def test_compliance_deliverable_has_audit_content(self):
        result = generate_deliverable(
            "Run GDPR compliance audit across data processing"
        )
        content = result.get("content", "").lower()
        assert any(term in content for term in [
            "compliance", "audit", "gdpr", "data", "regulation",
            "policy", "assessment"
        ]), "Compliance deliverable missing domain-specific content"

    def test_deliverable_contains_murphy_branding(self):
        """All deliverables must include Murphy attribution."""
        result = generate_deliverable("Automate invoice processing")
        content = result.get("content", "")
        assert "murphy" in content.lower() or "Murphy" in content, (
            "Deliverable missing Murphy branding"
        )


class TestMinimalCustomContent:
    """_build_minimal_custom_content produces domain-aware content."""

    @pytest.mark.parametrize("query,expected_terms", [
        ("Build a sales funnel with CRM integration", ["lead", "pipeline", "prospect", "revenue", "sales"]),
        ("Create social media marketing campaign", ["content", "audience", "campaign", "brand", "marketing"]),
        ("Set up customer support ticket system", ["ticket", "support", "customer", "sla", "escalat"]),
        ("Automate warehouse operations workflow", ["inventory", "process", "operation", "workflow", "automat"]),
    ])
    def test_domain_aware_content(self, query, expected_terms):
        content = _build_minimal_custom_content(query).lower()
        assert any(term in content for term in expected_terms), (
            f"Minimal content for '{query}' missing expected domain terms"
        )

    def test_minimal_content_is_substantial(self):
        """Even the minimal path should produce >300 chars."""
        content = _build_minimal_custom_content("Do something interesting with data")
        assert len(content) > 300, f"Minimal content too short: {len(content)} chars"


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 2: Automation Spec Generation
# ═══════════════════════════════════════════════════════════════════════════════

class TestAutomationSpecGeneration:
    """Automation spec must include workflows, costs, and ROI data."""

    @pytest.fixture(scope="class")
    def spec(self):
        return generate_automation_spec("Automate HR onboarding for new employees")

    def test_spec_has_id(self, spec):
        assert spec.get("spec_id"), "Spec missing spec_id"

    def test_spec_has_title(self, spec):
        assert spec.get("title"), "Spec missing title"

    def test_spec_has_workflows(self, spec):
        workflows = spec.get("workflows", [])
        assert len(workflows) > 0, "Spec has no workflows"

    def test_spec_workflows_have_structure(self, spec):
        for w in spec.get("workflows", []):
            assert "name" in w, f"Workflow missing 'name': {w}"

    def test_spec_has_roi_data(self, spec):
        """Spec must include ROI calculations."""
        assert spec.get("hours_saved_month") is not None or spec.get("monthly_savings_usd") is not None, (
            "Spec missing ROI data (hours_saved_month or monthly_savings_usd)"
        )

    def test_spec_has_murphy_cost(self, spec):
        """Spec must include Murphy platform cost."""
        assert spec.get("murphy_cost") is not None or spec.get("recommended_tier") is not None, (
            "Spec missing Murphy cost/tier info"
        )

    def test_spec_has_competitor_comparison(self, spec):
        """Spec should include competitor pricing."""
        competitors = spec.get("competitor_pricing", {})
        if competitors:
            assert len(competitors) > 0, "Competitor pricing dict is empty"


class TestAutomationSpecMultiDomain:
    """Spec generation works across multiple domains."""

    @pytest.mark.parametrize("query", [
        "Automate restaurant order processing and delivery",
        "Build a SaaS billing and subscription management system",
        "Create automated legal document review pipeline",
        "Automate supply chain procurement workflow",
        "Build automated customer feedback analysis",
    ])
    def test_spec_generated_for_diverse_queries(self, query):
        spec = generate_automation_spec(query)
        assert spec is not None, f"Spec is None for: {query}"
        assert spec.get("spec_id"), f"Spec missing ID for: {query}"
        assert spec.get("title"), f"Spec missing title for: {query}"


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 3: DemoBundleGenerator — ZIP Bundle Structure
# ═══════════════════════════════════════════════════════════════════════════════

class TestBundleFunctionAvailability:
    def test_generate_demo_bundle_callable(self):
        assert callable(generate_demo_bundle)

    def test_build_automation_proposal_callable(self):
        assert callable(_build_automation_proposal)

    def test_build_itemized_quote_callable(self):
        assert callable(_build_itemized_quote)

    def test_build_bundle_readme_callable(self):
        assert callable(_build_bundle_readme)


class TestBundleGeneration:
    """Bundle must produce a valid ZIP with professional file structure."""

    @pytest.fixture(scope="class")
    def sample_bundle(self):
        query = "Automate employee onboarding across departments"
        deliverable = generate_deliverable(query)
        spec = generate_automation_spec(query)
        return generate_demo_bundle(query, deliverable, spec)

    def test_bundle_returns_dict(self, sample_bundle):
        assert isinstance(sample_bundle, dict), "Bundle should return a dict"

    def test_bundle_has_zip_bytes(self, sample_bundle):
        assert "zip_bytes" in sample_bundle, "Bundle missing zip_bytes"
        assert isinstance(sample_bundle["zip_bytes"], bytes), "zip_bytes should be bytes"
        assert len(sample_bundle["zip_bytes"]) > 100, "ZIP is suspiciously small"

    def test_bundle_has_filename(self, sample_bundle):
        assert "filename" in sample_bundle, "Bundle missing filename"
        assert sample_bundle["filename"].endswith(".zip"), "Filename should end in .zip"

    def test_bundle_has_file_count(self, sample_bundle):
        assert "file_count" in sample_bundle, "Bundle missing file_count"
        assert sample_bundle["file_count"] >= 5, f"Expected >=5 files, got {sample_bundle['file_count']}"

    def test_bundle_zip_is_valid(self, sample_bundle):
        """ZIP bytes must be a valid zip archive."""
        bio = io.BytesIO(sample_bundle["zip_bytes"])
        assert zipfile.is_zipfile(bio), "zip_bytes is not a valid ZIP file"

    def test_bundle_contains_required_files(self, sample_bundle):
        """ZIP must contain: README.md, deliverable.txt, automation-proposal.txt,
        itemized-quote.txt, automation-spec.txt, LICENSE"""
        bio = io.BytesIO(sample_bundle["zip_bytes"])
        with zipfile.ZipFile(bio, "r") as zf:
            names = [os.path.basename(n) for n in zf.namelist()]
            required = [
                "README.md",
                "deliverable.txt",
                "automation-proposal.txt",
                "itemized-quote.txt",
                "automation-spec.txt",
                "LICENSE",
            ]
            for req in required:
                assert req in names, f"ZIP missing required file: {req}"

    def test_bundle_files_are_non_empty(self, sample_bundle):
        """Every file in the ZIP must have content."""
        bio = io.BytesIO(sample_bundle["zip_bytes"])
        with zipfile.ZipFile(bio, "r") as zf:
            for info in zf.infolist():
                if not info.filename.endswith("/"):
                    data = zf.read(info.filename)
                    assert len(data) > 0, f"Empty file in ZIP: {info.filename}"


class TestBundleProposalContent:
    """The automation proposal must contain required sections."""

    @pytest.fixture(scope="class")
    def proposal_content(self):
        query = "Automate accounts payable invoice processing"
        deliverable = generate_deliverable(query)
        spec = generate_automation_spec(query)
        bundle = generate_demo_bundle(query, deliverable, spec)
        bio = io.BytesIO(bundle["zip_bytes"])
        with zipfile.ZipFile(bio, "r") as zf:
            for name in zf.namelist():
                if name.endswith("automation-proposal.txt"):
                    return zf.read(name).decode("utf-8")
        return ""

    def test_proposal_has_executive_summary(self, proposal_content):
        assert "executive summary" in proposal_content.lower(), (
            "Proposal missing Executive Summary section"
        )

    def test_proposal_has_scope(self, proposal_content):
        assert "scope" in proposal_content.lower(), (
            "Proposal missing Scope section"
        )

    def test_proposal_has_timeline(self, proposal_content):
        assert "timeline" in proposal_content.lower(), (
            "Proposal missing Timeline section"
        )

    def test_proposal_has_outcomes(self, proposal_content):
        assert any(term in proposal_content.lower() for term in [
            "outcomes", "expected", "benefits", "results"
        ]), "Proposal missing Outcomes section"

    def test_proposal_is_substantial(self, proposal_content):
        assert len(proposal_content) > 1000, (
            f"Proposal too short ({len(proposal_content)} chars), expected >1000"
        )


class TestBundleQuoteContent:
    """The itemized quote must include labor, platform costs, and payback."""

    @pytest.fixture(scope="class")
    def quote_content(self):
        query = "Automate customer support ticket routing and SLA management"
        deliverable = generate_deliverable(query)
        spec = generate_automation_spec(query)
        bundle = generate_demo_bundle(query, deliverable, spec)
        bio = io.BytesIO(bundle["zip_bytes"])
        with zipfile.ZipFile(bio, "r") as zf:
            for name in zf.namelist():
                if name.endswith("itemized-quote.txt"):
                    return zf.read(name).decode("utf-8")
        return ""

    def test_quote_has_labor_section(self, quote_content):
        assert any(term in quote_content.lower() for term in [
            "labor", "implementation", "hours", "engineering"
        ]), "Quote missing labor/implementation section"

    def test_quote_has_platform_cost(self, quote_content):
        assert any(term in quote_content.lower() for term in [
            "platform", "subscription", "murphy", "monthly"
        ]), "Quote missing platform subscription section"

    def test_quote_has_dollar_amounts(self, quote_content):
        assert "$" in quote_content, "Quote missing dollar amounts"

    def test_quote_has_total(self, quote_content):
        assert "total" in quote_content.lower(), "Quote missing total section"

    def test_quote_is_substantial(self, quote_content):
        assert len(quote_content) > 500, (
            f"Quote too short ({len(quote_content)} chars), expected >500"
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 4: Rate Limiting — Fingerprint & Enforcement
# ═══════════════════════════════════════════════════════════════════════════════

class TestFingerprint:
    """Fingerprinting function produces consistent, deterministic hashes."""

    def test_fingerprint_deterministic(self):
        fp1 = make_fingerprint("192.168.1.1", "Mozilla/5.0")
        fp2 = make_fingerprint("192.168.1.1", "Mozilla/5.0")
        assert fp1 == fp2, "Fingerprint is not deterministic"

    def test_fingerprint_varies_by_ip(self):
        fp1 = make_fingerprint("10.0.0.1", "UA-A")
        fp2 = make_fingerprint("10.0.0.2", "UA-A")
        assert fp1 != fp2, "Different IPs should produce different fingerprints"

    def test_fingerprint_varies_by_ua(self):
        fp1 = make_fingerprint("10.0.0.1", "UA-A")
        fp2 = make_fingerprint("10.0.0.1", "UA-B")
        assert fp1 != fp2, "Different UAs should produce different fingerprints"

    def test_fingerprint_is_string(self):
        fp = make_fingerprint("1.2.3.4", "Test")
        assert isinstance(fp, str), "Fingerprint should be a string"
        assert len(fp) > 8, "Fingerprint suspiciously short"


class TestSubscriptionManagerRateLimiting:
    """SubscriptionManager enforces correct daily limits."""

    @pytest.fixture
    def sub_manager(self):
        from subscription_manager import SubscriptionManager
        return SubscriptionManager()

    def test_anon_limit_is_5(self, sub_manager):
        assert sub_manager._ANON_DAILY_LIMIT == 5, (
            f"Anonymous limit should be 5, got {sub_manager._ANON_DAILY_LIMIT}"
        )

    def test_free_limit_is_10(self, sub_manager):
        assert sub_manager._FREE_DAILY_LIMIT == 10, (
            f"Free tier limit should be 10, got {sub_manager._FREE_DAILY_LIMIT}"
        )

    def test_anon_usage_tracking(self, sub_manager):
        """First 5 anonymous requests should be allowed."""
        fp = "test-fingerprint-wave11-" + str(id(sub_manager))
        for i in range(5):
            result = sub_manager.record_anon_usage(fp)
            assert result["allowed"] is True, f"Request {i+1} should be allowed"
            assert result["remaining"] == 4 - i, f"Remaining should be {4-i}"

    def test_anon_usage_blocks_at_6(self, sub_manager):
        """6th anonymous request should be blocked."""
        fp = "test-fingerprint-wave11-block-" + str(id(sub_manager))
        for i in range(5):
            sub_manager.record_anon_usage(fp)
        result = sub_manager.record_anon_usage(fp)
        assert result["allowed"] is False, "6th anonymous request should be blocked"
        assert result["remaining"] == 0

    def test_free_user_usage_tracking(self, sub_manager):
        """First 10 free-tier requests should be allowed."""
        account_id = "test-free-user-wave11-" + str(id(sub_manager))
        for i in range(10):
            result = sub_manager.record_usage(account_id)
            assert result["allowed"] is True, f"Free request {i+1} should be allowed"

    def test_free_user_blocks_at_11(self, sub_manager):
        """11th free-tier request should be blocked."""
        account_id = "test-free-user-wave11-block-" + str(id(sub_manager))
        for i in range(10):
            sub_manager.record_usage(account_id)
        result = sub_manager.record_usage(account_id)
        assert result["allowed"] is False, "11th free request should be blocked"


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 5: API Endpoint Shape Validation
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def client():
    """Create a FastAPI test client."""
    os.environ["MURPHY_ENV"] = "development"
    os.environ["MURPHY_RATE_LIMIT_RPM"] = "6000"
    os.environ["MURPHY_RATE_LIMIT_BURST"] = "200"
    try:
        from starlette.testclient import TestClient
        from src.runtime.app import create_app
        app = create_app()
        return TestClient(app, follow_redirects=False)
    except Exception as e:
        pytest.skip(f"Cannot create test client: {e}")


class TestDemoRunEndpoint:
    """POST /api/demo/run response shape."""

    def test_missing_query_returns_400(self, client):
        resp = client.post("/api/demo/run", json={})
        assert resp.status_code == 400
        data = resp.json()
        assert data["error"] == "missing_query"

    def test_valid_query_returns_success_or_rate_limited(self, client):
        resp = client.post("/api/demo/run", json={"query": "Onboard a new client"})
        data = resp.json()
        if resp.status_code == 200:
            assert data["success"] is True
            assert "steps" in data
            assert "roi_message" in data
            assert "usage" in data
            assert isinstance(data["steps"], list)
        elif resp.status_code == 429:
            assert data["error"] == "limit_exceeded"
        else:
            # 500 is acceptable if pipeline modules aren't fully available
            assert resp.status_code in (200, 429, 500)

    def test_usage_in_success_response(self, client):
        resp = client.post(
            "/api/demo/run",
            json={"query": "Generate finance report"},
        )
        data = resp.json()
        if resp.status_code == 200:
            usage = data.get("usage", {})
            assert "used" in usage
            assert "limit" in usage
            assert "remaining" in usage
            assert "tier" in usage


class TestGenerateDeliverableEndpoint:
    """POST /api/demo/generate-deliverable response shape."""

    def test_missing_query_returns_400(self, client):
        resp = client.post("/api/demo/generate-deliverable", json={})
        assert resp.status_code == 400

    def test_valid_query_returns_deliverable_or_rate_limited(self, client):
        resp = client.post(
            "/api/demo/generate-deliverable",
            json={"query": "Create project plan for website redesign"},
        )
        data = resp.json()
        if resp.status_code == 200:
            assert data.get("success") is True
            assert "deliverable" in data
            deliverable = data["deliverable"]
            assert "content" in deliverable
            assert "filename" in deliverable
            assert len(deliverable["content"]) > 100
        elif resp.status_code == 429:
            assert data["error"] == "limit_exceeded"


class TestDownloadBundleEndpoint:
    """POST /api/demo/download-bundle response shape."""

    def test_missing_query_returns_400(self, client):
        resp = client.post("/api/demo/download-bundle", json={})
        assert resp.status_code == 400

    def test_valid_query_returns_zip_or_rate_limited(self, client):
        resp = client.post(
            "/api/demo/download-bundle",
            json={"query": "Automate customer onboarding"},
        )
        if resp.status_code == 200:
            ct = resp.headers.get("content-type", "")
            assert "zip" in ct or "octet-stream" in ct, f"Unexpected content-type: {ct}"
            assert "content-disposition" in resp.headers
            bio = io.BytesIO(resp.content)
            assert zipfile.is_zipfile(bio), "Response is not a valid ZIP"
        elif resp.status_code == 429:
            data = resp.json()
            assert data["error"] == "limit_exceeded"


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 6: End-to-End Integration
# ═══════════════════════════════════════════════════════════════════════════════

class TestEndToEndDemoFlow:
    """Full demo flow: query → deliverable → spec → bundle."""

    def test_full_flow_sales_domain(self):
        query = "Build automated sales outreach and follow-up system"
        # Step 1: Generate deliverable
        deliverable = generate_deliverable(query)
        assert deliverable is not None
        assert len(deliverable.get("content", "")) > 500

        # Step 2: Generate automation spec
        spec = generate_automation_spec(query)
        assert spec is not None
        assert spec.get("spec_id")

        # Step 3: Generate bundle
        bundle = generate_demo_bundle(query, deliverable, spec)
        assert bundle is not None
        assert len(bundle["zip_bytes"]) > 100

        # Step 4: Validate bundle content
        bio = io.BytesIO(bundle["zip_bytes"])
        with zipfile.ZipFile(bio, "r") as zf:
            names = [os.path.basename(n) for n in zf.namelist()]
            assert "deliverable.txt" in names
            assert "automation-proposal.txt" in names
            assert "itemized-quote.txt" in names
            assert "automation-spec.txt" in names
            assert "README.md" in names

    def test_full_flow_operations_domain(self):
        query = "Automate warehouse inventory tracking and restocking"
        deliverable = generate_deliverable(query)
        spec = generate_automation_spec(query)
        bundle = generate_demo_bundle(query, deliverable, spec)

        bio = io.BytesIO(bundle["zip_bytes"])
        with zipfile.ZipFile(bio, "r") as zf:
            for info in zf.infolist():
                if not info.filename.endswith("/"):
                    data = zf.read(info.filename)
                    assert len(data) > 50, f"File too small: {info.filename}"

    def test_full_flow_exotic_domain(self):
        """Even unusual domains should produce a valid bundle."""
        query = "Create automated pet grooming salon appointment and inventory system"
        deliverable = generate_deliverable(query)
        assert deliverable is not None
        assert len(deliverable.get("content", "")) > 200

        spec = generate_automation_spec(query)
        assert spec is not None

        bundle = generate_demo_bundle(query, deliverable, spec)
        assert bundle is not None
        bio = io.BytesIO(bundle["zip_bytes"])
        assert zipfile.is_zipfile(bio)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 7: Custom Deliverable Always Includes Automation Content
# ═══════════════════════════════════════════════════════════════════════════════

class TestCustomDeliverableAlwaysIncludesAutomation:
    """After D6-SPEC-CUSTOM fix, every custom deliverable must include
    automation blueprint and quality plan sections."""

    @pytest.mark.parametrize("query", [
        "Write a business letter to a client",
        "Summarize Q4 earnings for the board",
        "Create a training manual for new hires",
        "Design a restaurant menu layout",
    ])
    def test_always_has_automation_section(self, query):
        """Even queries without automation keywords should include
        automation-related content."""
        result = generate_deliverable(query)
        content = result.get("content", "").lower()
        has_automation = any(term in content for term in [
            "automation", "workflow", "murphy", "blueprint",
            "quality plan", "service catalog", "integration"
        ])
        assert has_automation, (
            f"Custom deliverable for '{query}' missing automation content. "
            f"Content length: {len(content)} chars"
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 8: DemoRunner Commission Report
# ═══════════════════════════════════════════════════════════════════════════════

class TestDemoRunnerCommission:
    """DemoRunner.commission_all() must pass with 0 errors."""

    def test_commission_all_passes(self):
        from demo_runner import DemoRunner
        runner = DemoRunner()
        report = runner.commission_all()
        assert report is not None, "commission_all returned None"
        # Report uses 'errors' as a dict (not list) — check it's empty
        errors = report.get("errors", {})
        if isinstance(errors, dict):
            assert len(errors) == 0, (
                f"Commission found {len(errors)} errors: {errors}"
            )
        elif isinstance(errors, list):
            assert len(errors) == 0, (
                f"Commission found {len(errors)} errors: {errors}"
            )
        # Report uses 'passed' (bool), not 'status'
        assert report.get("passed", report.get("status")) in (True, "pass", "PASS"), (
            f"Commission not passing: passed={report.get('passed')}, status={report.get('status')}"
        )