"""
Tests for MKT-006: SelfMarketingOrchestrator.

Validates:
  - Content cycle generates blog posts with SEO scores
  - Social cycle creates platform-specific variants
  - Outreach cycle respects 30-day cooldown (mocked governor returns BLOCK_COOLDOWN)
  - Outreach cycle skips DNC contacts
  - Reply processing detects opt-out and adds to DNC
  - Developer attraction cycle generates tutorials
  - Marketing dashboard aggregates metrics
  - Save/load state round-trip
  - Content calendar rotation (doesn't repeat topics within 30 days)
  - HITL gate on content publishing (first N posts require review)

Design Label: TEST / MKT-006
Owner: QA Team
"""

import os
from datetime import datetime, timedelta, timezone

import pytest


from self_marketing_orchestrator import (  # noqa: I001
    SelfMarketingOrchestrator,
    CONTENT_CATEGORIES,
    HITL_REVIEW_THRESHOLD,
    OUTREACH_COOLDOWN_DAYS,
    ComplianceDecision,
    ContentStatus,
    OutreachStatus,
    GeneratedContent,
    OutreachRecord,
    ReplyRecord,
    ContentCycleResult,
    SocialCycleResult,
    OutreachCycleResult,
    DeveloperAttractionResult,
)


# ---------------------------------------------------------------------------
# Helpers / stubs
# ---------------------------------------------------------------------------

class _MockPersistence:
    """Minimal PersistenceManager stub."""

    def __init__(self):
        self._store = {}

    def save_document(self, doc_id, document):
        self._store[doc_id] = document

    def load_document(self, doc_id):
        return self._store.get(doc_id)


class _MockSEOEngine:
    """Minimal SEOOptimisationEngine stub that returns a fixed score."""

    def analyse_content(self, title, body, url=""):
        class _Analysis:
            seo_score = 78.5
        return _Analysis()


class _MockContentEngine:
    """Minimal ContentPipelineEngine stub."""

    def __init__(self):
        self.briefs = {}
        self.drafts = {}
        self._next_brief_id = 0
        self._next_draft_id = 0

    def create_brief(self, topic, content_type, keywords=None, tone="professional"):
        brief_id = f"brief-{self._next_brief_id}"
        self._next_brief_id += 1
        self.briefs[brief_id] = {"topic": topic, "content_type": content_type}

        class _Brief:
            pass
        b = _Brief()
        b.brief_id = brief_id
        return b

    def create_draft(self, brief_id, title, body, channel="blog"):
        draft_id = f"draft-{self._next_draft_id}"
        self._next_draft_id += 1
        self.drafts[draft_id] = {"brief_id": brief_id, "title": title}

        class _Item:
            pass
        item = _Item()
        item.item_id = draft_id
        return item


class _MockAdaptiveCampaign:
    """Minimal AdaptiveCampaignEngine stub."""

    def __init__(self):
        self.snapshots = []

    def record_snapshot(self, tier, period, **kwargs):
        self.snapshots.append({"tier": tier, "period": period, **kwargs})


class _DNCComplianceGate:
    """Governor that always returns BLOCK_DNC."""

    def check(self, prospect_id, prospect):
        return ComplianceDecision.BLOCK_DNC


class _CooldownComplianceGate:
    """Governor that always returns BLOCK_COOLDOWN."""

    def check(self, prospect_id, prospect):
        return ComplianceDecision.BLOCK_COOLDOWN


class _ConsentRequiredGate:
    """Governor that always returns REQUIRES_CONSENT."""

    def check(self, prospect_id, prospect):
        return ComplianceDecision.REQUIRES_CONSENT


class _AllowComplianceGate:
    """Governor that always returns ALLOW."""

    def check(self, prospect_id, prospect):
        return ComplianceDecision.ALLOW


class _MockEventBackbone:
    """Minimal EventBackbone stub that captures published events."""

    def __init__(self):
        self.events = []

    def publish(self, event_type, payload):
        self.events.append({"event_type": event_type, "payload": payload})


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def orchestrator():
    """Bare orchestrator with no external dependencies."""
    return SelfMarketingOrchestrator()


@pytest.fixture
def full_orchestrator():
    """Orchestrator with all optional dependencies wired."""
    pm = _MockPersistence()
    backbone = _MockEventBackbone()
    return SelfMarketingOrchestrator(
        content_engine=_MockContentEngine(),
        seo_engine=_MockSEOEngine(),
        adaptive_campaign=_MockAdaptiveCampaign(),
        event_backbone=backbone,
        persistence_manager=pm,
    )


# ---------------------------------------------------------------------------
# Content generation tests
# ---------------------------------------------------------------------------

class TestContentGeneration:
    def test_generate_blog_post_returns_content(self, orchestrator):
        content = orchestrator.generate_blog_post("AI automation in manufacturing", ["AI", "automation"])
        assert content is not None
        assert content.content_id.startswith("blog-")
        assert "AI automation" in content.title
        assert len(content.body) > 0

    def test_generate_blog_post_with_seo_engine(self, full_orchestrator):
        content = full_orchestrator.generate_blog_post("Confidence-gated AI", ["AI", "safety"])
        assert content.seo_score == 78.5

    def test_generate_blog_post_fallback_seo_score(self, orchestrator):
        """Without SEO engine, a fallback heuristic score is assigned."""
        content = orchestrator.generate_blog_post("Murphy SDK tutorial", ["SDK", "Python"])
        assert content.seo_score > 0

    def test_generate_blog_post_assigns_keywords(self, orchestrator):
        content = orchestrator.generate_blog_post("Describe-to-Execute: automation", ["describe", "execute"])
        assert len(content.keywords) > 0

    def test_generate_case_study(self, orchestrator):
        content = orchestrator.generate_case_study("Murphy sells Murphy")
        assert content.content_type == "case_study"
        assert "Case Study" in content.title

    def test_generate_tutorial(self, orchestrator):
        content = orchestrator.generate_tutorial("confidence_gating")
        assert content.content_type == "tutorial"
        assert "Tutorial" in content.title
        assert "confidence_gating" in content.body

    def test_generate_tutorial_contains_sdk_keywords(self, orchestrator):
        content = orchestrator.generate_tutorial("natural_language_workflow")
        assert "SDK" in content.keywords or "sdk" in content.body.lower() or "murphy_sdk" in content.body

    def test_content_stored_in_catalogue(self, orchestrator):
        content = orchestrator.generate_blog_post("Test topic", ["test"])
        with orchestrator._lock:
            assert content.content_id in orchestrator._content


# ---------------------------------------------------------------------------
# Content cycle tests
# ---------------------------------------------------------------------------

class TestContentCycle:
    def test_content_cycle_returns_dict(self, orchestrator):
        result = orchestrator.run_content_cycle()
        assert isinstance(result, dict)
        assert "pieces_generated" in result
        assert "avg_seo_score" in result

    def test_content_cycle_generates_pieces(self, orchestrator):
        result = orchestrator.run_content_cycle()
        assert result["pieces_generated"] >= 1

    def test_content_cycle_records_history(self, orchestrator):
        orchestrator.run_content_cycle()
        with orchestrator._lock:
            assert len(orchestrator._content_cycles) == 1

    def test_hitl_gate_first_posts_require_review(self, full_orchestrator):
        """First HITL_REVIEW_THRESHOLD content pieces must go to pending_review."""
        # Ensure published_count is 0
        with full_orchestrator._lock:
            full_orchestrator._published_count = 0

        result = full_orchestrator.run_content_cycle()
        assert result["pieces_pending_review"] >= 1

    def test_hitl_gate_auto_publish_after_threshold(self, full_orchestrator):
        """Once threshold is exceeded, content is auto-published."""
        with full_orchestrator._lock:
            full_orchestrator._published_count = HITL_REVIEW_THRESHOLD + 10

        result = full_orchestrator.run_content_cycle()
        assert result["pieces_published"] >= 1

    def test_approve_content_transitions_status(self, orchestrator):
        """HITL approval gate moves content from pending_review to published."""
        with orchestrator._lock:
            orchestrator._published_count = 0  # Force HITL gate

        content = orchestrator.generate_blog_post("Automation review test", [])
        content.status = ContentStatus.PENDING_REVIEW.value

        result = orchestrator.approve_content(content.content_id)
        assert result is True
        with orchestrator._lock:
            updated = orchestrator._content[content.content_id]
        assert updated.status == ContentStatus.PUBLISHED.value

    def test_approve_nonexistent_content_returns_false(self, orchestrator):
        assert orchestrator.approve_content("nonexistent-id") is False


# ---------------------------------------------------------------------------
# Social cycle tests
# ---------------------------------------------------------------------------

class TestSocialCycle:
    def _publish_some_content(self, orchestrator):
        """Helper to add published content for social cycle to pick up."""
        content = orchestrator.generate_blog_post("Social test topic", ["AI"])
        content.status = ContentStatus.PUBLISHED.value
        content.published_at = "2026-01-01T00:00:00+00:00"
        with orchestrator._lock:
            orchestrator._content[content.content_id] = content
        return content

    def test_social_cycle_returns_dict(self, orchestrator):
        result = orchestrator.run_social_cycle()
        assert isinstance(result, dict)
        assert "variants_generated" in result

    def test_social_cycle_with_no_published_content(self, orchestrator):
        result = orchestrator.run_social_cycle()
        assert result["variants_generated"] == 0

    def test_social_cycle_generates_variants(self, orchestrator):
        self._publish_some_content(orchestrator)
        result = orchestrator.run_social_cycle()
        assert result["variants_generated"] >= 1

    def test_generate_social_variants_creates_platform_posts(self, orchestrator):
        content = self._publish_some_content(orchestrator)
        variants = orchestrator.generate_social_variants(content.content_id)
        assert len(variants) == 3  # twitter, linkedin, reddit

    def test_generate_social_variants_platform_names(self, orchestrator):
        content = self._publish_some_content(orchestrator)
        variants = orchestrator.generate_social_variants(content.content_id)
        platforms = {v["platform"] for v in variants}
        assert "twitter" in platforms
        assert "linkedin" in platforms
        assert "reddit" in platforms

    def test_twitter_variant_respects_char_limit(self, orchestrator):
        content = self._publish_some_content(orchestrator)
        variants = orchestrator.generate_social_variants(content.content_id)
        twitter = next(v for v in variants if v["platform"] == "twitter")
        assert len(twitter["body"]) <= 280

    def test_generate_social_variants_unknown_id(self, orchestrator):
        variants = orchestrator.generate_social_variants("nonexistent-id")
        assert variants == []

    def test_social_cycle_records_history(self, orchestrator):
        self._publish_some_content(orchestrator)
        orchestrator.run_social_cycle()
        with orchestrator._lock:
            assert len(orchestrator._social_cycles) == 1


# ---------------------------------------------------------------------------
# Outreach compliance tests
# ---------------------------------------------------------------------------

class TestOutreachCompliance:
    def _add_prospects(self, orchestrator, prospects):
        """Inject a fake prospect list into the orchestrator for testing."""
        orchestrator._test_prospects = prospects

        original_get = orchestrator._get_prospects
        orchestrator._get_prospects = lambda: orchestrator._test_prospects

    def test_outreach_cycle_returns_dict(self, orchestrator):
        result = orchestrator.run_outreach_cycle()
        assert isinstance(result, dict)
        assert "prospects_evaluated" in result

    def test_outreach_skips_dnc_contacts(self, orchestrator):
        """Contacts in the DNC set must never be sent outreach."""
        with orchestrator._lock:
            orchestrator._dnc_set.add("prospect-dnc-1")

        self._add_prospects(orchestrator, [{"id": "prospect-dnc-1", "channel": "email"}])
        result = orchestrator.run_outreach_cycle()

        assert result["blocked_dnc"] == 1
        assert result["outreach_sent"] == 0

    def test_outreach_respects_cooldown_from_governor(self):
        """When compliance governor returns BLOCK_COOLDOWN, outreach is blocked."""
        orch = SelfMarketingOrchestrator(compliance_gate=_CooldownComplianceGate())
        orch._get_prospects = lambda: [{"id": "prospect-1", "channel": "email"}]

        result = orch.run_outreach_cycle()

        assert result["blocked_cooldown"] == 1
        assert result["outreach_sent"] == 0

    def test_outreach_blocks_dnc_from_governor(self):
        """When compliance governor returns BLOCK_DNC, outreach is blocked."""
        orch = SelfMarketingOrchestrator(compliance_gate=_DNCComplianceGate())
        orch._get_prospects = lambda: [{"id": "prospect-2", "channel": "email"}]

        result = orch.run_outreach_cycle()

        assert result["blocked_dnc"] == 1
        assert result["outreach_sent"] == 0

    def test_outreach_blocks_consent_required(self):
        """When compliance governor returns REQUIRES_CONSENT, outreach is blocked."""
        orch = SelfMarketingOrchestrator(compliance_gate=_ConsentRequiredGate())
        orch._get_prospects = lambda: [{"id": "prospect-3", "channel": "email"}]

        result = orch.run_outreach_cycle()

        assert result["blocked_consent"] == 1
        assert result["outreach_sent"] == 0

    def test_outreach_sent_when_allowed(self):
        """When governor allows, outreach is sent and recorded."""
        orch = SelfMarketingOrchestrator(compliance_gate=_AllowComplianceGate())
        orch._get_prospects = lambda: [{"id": "prospect-ok", "channel": "email"}]

        result = orch.run_outreach_cycle()

        assert result["outreach_sent"] == 1
        assert result["blocked_dnc"] == 0
        assert result["blocked_cooldown"] == 0

    def test_internal_cooldown_blocks_repeat_contact(self):
        """Contacting the same prospect within OUTREACH_COOLDOWN_DAYS must be blocked."""
        orch = SelfMarketingOrchestrator()
        prospect_id = "repeat-prospect"

        # Record a recent contact
        recent = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        with orch._lock:
            orch._last_contacted[prospect_id] = recent

        orch._get_prospects = lambda: [{"id": prospect_id, "channel": "email"}]
        result = orch.run_outreach_cycle()

        assert result["blocked_cooldown"] == 1
        assert result["outreach_sent"] == 0

    def test_contact_after_cooldown_window_is_allowed(self):
        """Contact attempted after 31+ days since last contact must be allowed."""
        orch = SelfMarketingOrchestrator()
        prospect_id = "old-contact"

        # Record an old contact (31 days ago)
        old = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
        with orch._lock:
            orch._last_contacted[prospect_id] = old

        orch._get_prospects = lambda: [{"id": prospect_id, "channel": "email"}]
        result = orch.run_outreach_cycle()

        assert result["outreach_sent"] == 1

    def test_outreach_records_contact_timestamp(self):
        """After sending outreach, last_contacted must be set for the prospect."""
        orch = SelfMarketingOrchestrator()
        prospect_id = "ts-prospect"
        orch._get_prospects = lambda: [{"id": prospect_id, "channel": "email"}]
        orch.run_outreach_cycle()
        with orch._lock:
            assert prospect_id in orch._last_contacted


# ---------------------------------------------------------------------------
# Reply processing tests
# ---------------------------------------------------------------------------

class TestReplyProcessing:
    def test_opt_out_reply_adds_to_dnc(self, orchestrator):
        orchestrator.inject_reply("prospect-opt-out", "Please unsubscribe me immediately")
        result = orchestrator.process_prospect_replies()

        assert result["opt_outs"] == 1
        with orchestrator._lock:
            assert "prospect-opt-out" in orchestrator._dnc_set

    def test_opt_out_phrase_stop(self, orchestrator):
        orchestrator.inject_reply("p1", "Stop sending me emails")
        result = orchestrator.process_prospect_replies()
        assert result["opt_outs"] == 1

    def test_opt_out_phrase_remove_me(self, orchestrator):
        orchestrator.inject_reply("p2", "Please remove me from your list")
        result = orchestrator.process_prospect_replies()
        assert result["opt_outs"] == 1

    def test_positive_reply_detected(self, orchestrator):
        orchestrator.inject_reply("prospect-pos", "This sounds interesting, tell me more!")
        result = orchestrator.process_prospect_replies()

        assert result["positives"] == 1
        with orchestrator._lock:
            assert "prospect-pos" not in orchestrator._dnc_set

    def test_positive_demo_reply(self, orchestrator):
        orchestrator.inject_reply("p3", "I'd like to book a demo")
        result = orchestrator.process_prospect_replies()
        assert result["positives"] == 1

    def test_neutral_reply_not_opt_out(self, orchestrator):
        orchestrator.inject_reply("p4", "What does Murphy do exactly?")
        result = orchestrator.process_prospect_replies()
        assert result["opt_outs"] == 0
        assert result["positives"] == 0

    def test_opt_out_prevents_future_outreach(self):
        """After opt-out, the DNC set must block future outreach cycles."""
        orch = SelfMarketingOrchestrator()
        orch.inject_reply("dnc-test", "unsubscribe please")
        orch.process_prospect_replies()

        orch._get_prospects = lambda: [{"id": "dnc-test", "channel": "email"}]
        result = orch.run_outreach_cycle()

        assert result["blocked_dnc"] == 1
        assert result["outreach_sent"] == 0

    def test_multiple_replies_processed(self, orchestrator):
        orchestrator.inject_reply("r1", "unsubscribe")
        orchestrator.inject_reply("r2", "Yes, I'm interested!")
        orchestrator.inject_reply("r3", "What is this?")
        result = orchestrator.process_prospect_replies()
        assert result["processed"] == 3
        assert result["opt_outs"] == 1
        assert result["positives"] == 1


# ---------------------------------------------------------------------------
# Developer attraction cycle tests
# ---------------------------------------------------------------------------

class TestDeveloperAttractionCycle:
    def test_dev_cycle_returns_dict(self, orchestrator):
        result = orchestrator.run_developer_attraction_cycle()
        assert isinstance(result, dict)
        assert "tutorials_created" in result

    def test_dev_cycle_generates_tutorials(self, orchestrator):
        result = orchestrator.run_developer_attraction_cycle()
        assert result["tutorials_created"] >= 1

    def test_dev_cycle_generates_snippets(self, orchestrator):
        result = orchestrator.run_developer_attraction_cycle()
        assert result["snippets_created"] >= 1

    def test_dev_cycle_generates_changelogs(self, orchestrator):
        result = orchestrator.run_developer_attraction_cycle()
        assert result["changelogs_created"] >= 1

    def test_dev_cycle_proposes_github_issues(self, orchestrator):
        result = orchestrator.run_developer_attraction_cycle()
        assert result["github_issues_proposed"] >= 1

    def test_dev_cycle_records_history(self, orchestrator):
        orchestrator.run_developer_attraction_cycle()
        with orchestrator._lock:
            assert len(orchestrator._dev_cycles) == 1

    def test_tutorials_stored_in_catalogue(self, orchestrator):
        orchestrator.run_developer_attraction_cycle()
        with orchestrator._lock:
            tutorials = [c for c in orchestrator._content.values() if c.content_type == "tutorial"]
        assert len(tutorials) >= 1


# ---------------------------------------------------------------------------
# Marketing dashboard tests
# ---------------------------------------------------------------------------

class TestMarketingDashboard:
    def test_dashboard_returns_dict(self, orchestrator):
        dashboard = orchestrator.get_marketing_dashboard()
        assert isinstance(dashboard, dict)

    def test_dashboard_has_content_section(self, orchestrator):
        dashboard = orchestrator.get_marketing_dashboard()
        assert "content" in dashboard
        assert "published" in dashboard["content"]
        assert "pending_review" in dashboard["content"]
        assert "avg_seo_score" in dashboard["content"]

    def test_dashboard_has_outreach_section(self, orchestrator):
        dashboard = orchestrator.get_marketing_dashboard()
        assert "outreach" in dashboard
        assert "sent" in dashboard["outreach"]
        assert "blocked" in dashboard["outreach"]
        assert "dnc_list_size" in dashboard["outreach"]

    def test_dashboard_has_cycles_section(self, orchestrator):
        dashboard = orchestrator.get_marketing_dashboard()
        assert "cycles" in dashboard
        assert "content_cycles_run" in dashboard["cycles"]
        assert "outreach_cycles_run" in dashboard["cycles"]

    def test_dashboard_aggregates_published_count(self, orchestrator):
        orchestrator.generate_blog_post("Test 1", [])
        content = orchestrator.generate_blog_post("Test 2", [])
        content.status = ContentStatus.PUBLISHED.value
        content.published_at = "2026-01-01T00:00:00+00:00"
        with orchestrator._lock:
            orchestrator._content[content.content_id] = content
            orchestrator._published_count = 1

        dashboard = orchestrator.get_marketing_dashboard()
        assert dashboard["content"]["published"] >= 1

    def test_dashboard_dnc_count(self):
        orch = SelfMarketingOrchestrator()
        with orch._lock:
            orch._dnc_set.add("p1")
            orch._dnc_set.add("p2")
        dashboard = orch.get_marketing_dashboard()
        assert dashboard["outreach"]["dnc_list_size"] == 2

    def test_compliance_report_returns_dict(self, orchestrator):
        report = orchestrator.get_compliance_report()
        assert isinstance(report, dict)
        assert "dnc_list_size" in report
        assert "sent" in report
        assert "blocked_dnc" in report


# ---------------------------------------------------------------------------
# Save / load state round-trip tests
# ---------------------------------------------------------------------------

class TestStatePersistence:
    def test_save_state_without_pm_returns_false(self, orchestrator):
        assert orchestrator.save_state() is False

    def test_load_state_without_pm_returns_false(self, orchestrator):
        assert orchestrator.load_state() is False

    def test_save_and_load_state_round_trip(self):
        pm = _MockPersistence()
        orch = SelfMarketingOrchestrator(persistence_manager=pm)

        # Set some state
        orch.generate_blog_post("Round-trip test", ["test"])
        with orch._lock:
            orch._dnc_set.add("blocked-forever")
            orch._published_count = 7
            orch._category_index = 3

        assert orch.save_state() is True

        # Create a fresh orchestrator, load state
        orch2 = SelfMarketingOrchestrator(persistence_manager=pm)
        assert orch2.load_state() is True

        with orch2._lock:
            assert orch2._published_count == 7
            assert orch2._category_index == 3
            assert "blocked-forever" in orch2._dnc_set
            assert len(orch2._content) == 1

    def test_load_state_no_prior_data_returns_false(self):
        pm = _MockPersistence()
        orch = SelfMarketingOrchestrator(persistence_manager=pm)
        assert orch.load_state() is False

    def test_save_state_persists_outreach_records(self):
        pm = _MockPersistence()
        orch = SelfMarketingOrchestrator(persistence_manager=pm)
        orch._get_prospects = lambda: [{"id": "p-save", "channel": "email"}]
        orch.run_outreach_cycle()
        orch.save_state()

        orch2 = SelfMarketingOrchestrator(persistence_manager=pm)
        orch2.load_state()
        with orch2._lock:
            assert len(orch2._outreach_records) >= 1


# ---------------------------------------------------------------------------
# Content calendar rotation tests
# ---------------------------------------------------------------------------

class TestContentCalendarRotation:
    def test_content_categories_defined(self):
        assert len(CONTENT_CATEGORIES) >= 1
        for category, topics in CONTENT_CATEGORIES.items():
            assert len(topics) >= 1

    def test_category_index_increments_each_cycle(self, orchestrator):
        with orchestrator._lock:
            before = orchestrator._category_index
        orchestrator.run_content_cycle()
        with orchestrator._lock:
            after = orchestrator._category_index
        assert after == before + 1

    def test_topic_marked_used_after_generation(self, orchestrator):
        from self_marketing_orchestrator import CONTENT_CATEGORIES as CC
        first_category = list(CC.keys())[0]
        first_topic = CC[first_category][0].replace("{industry}", "manufacturing")
        orchestrator._mark_topic_used(first_category, first_topic)
        assert orchestrator._is_topic_recent(first_category, first_topic) is True

    def test_topic_not_recent_after_31_days(self):
        """Topics used 31 days ago should not be considered recent."""
        orch = SelfMarketingOrchestrator()
        old_entry = {
            "category": "ai_automation",
            "topic": "old topic",
            "used_at": (datetime.now(timezone.utc) - timedelta(days=31)).isoformat(),
        }
        with orch._lock:
            orch._recent_topics.append(old_entry)
        assert orch._is_topic_recent("ai_automation", "old topic") is False

    def test_second_cycle_uses_different_category(self, orchestrator):
        """Two consecutive cycles must use different topic categories."""
        with orchestrator._lock:
            orchestrator._category_index = 0
        orchestrator.run_content_cycle()
        with orchestrator._lock:
            idx_after_first = orchestrator._category_index
        orchestrator.run_content_cycle()
        with orchestrator._lock:
            idx_after_second = orchestrator._category_index
        assert idx_after_second == idx_after_first + 1


# ---------------------------------------------------------------------------
# CONTENT_CATEGORIES completeness test
# ---------------------------------------------------------------------------

class TestContentCategories:
    def test_all_required_categories_present(self):
        expected = {
            "ai_automation",
            "developer_tools",
            "industrial_iot",
            "business_automation",
            "case_studies",
            "thought_leadership",
        }
        assert expected.issubset(set(CONTENT_CATEGORIES.keys()))

    def test_each_category_has_multiple_topics(self):
        for cat, topics in CONTENT_CATEGORIES.items():
            assert len(topics) >= 2, f"Category '{cat}' needs at least 2 topics"


# ---------------------------------------------------------------------------
# Module manifest integration test
# ---------------------------------------------------------------------------

class TestModuleManifest:
    def test_self_marketing_orchestrator_in_manifest(self):
        """MKT-006 must be registered in the module manifest."""
        from matrix_bridge.module_manifest import MODULE_MANIFEST
        modules = [e.module for e in MODULE_MANIFEST]
        assert "self_marketing_orchestrator" in modules

    def test_manifest_entry_has_marketing_commands(self):
        from matrix_bridge.module_manifest import MODULE_MANIFEST
        entry = next(e for e in MODULE_MANIFEST if e.module == "self_marketing_orchestrator")
        assert any("marketing" in cmd for cmd in entry.commands)

    def test_manifest_entry_emits_expected_events(self):
        from matrix_bridge.module_manifest import MODULE_MANIFEST
        entry = next(e for e in MODULE_MANIFEST if e.module == "self_marketing_orchestrator")
        assert "content_published" in entry.emits
        assert "outreach_sent" in entry.emits
        assert "outreach_blocked" in entry.emits
