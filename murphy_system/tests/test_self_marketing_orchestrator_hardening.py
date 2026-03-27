"""
Test Suite: MKT-006 Self-Marketing Orchestrator — Security Hardening

Verifies all input-validation and memory-growth controls added as part of the
MKT-006 hardening pass:

  1.  prospect_id validation — regex enforcement (CWE-20)
  2.  channel allowlist — rejects unknown channels (CWE-20)
  3.  topic length cap — oversized topics rejected (CWE-20)
  4.  topic null-byte stripping (CWE-20)
  5.  keyword list size cap — truncated at _MAX_KEYWORDS (CWE-400)
  6.  per-keyword length cap — truncated at _MAX_KEYWORD_LEN (CWE-400)
  7.  reply body size cap — truncated at _MAX_REPLY_BODY (CWE-400)
  8.  pending-replies queue cap — drops oldest at _MAX_PENDING_REPLIES (CWE-400)
  9.  DNC set hard cap — opt-out recorded in audit only when full (CWE-400)
  10. _last_contacted dict hard cap — evicts oldest on overflow (CWE-400)
  11. content catalogue hard cap — evicts oldest on overflow (CWE-400)
  12. invalid prospect skipped in outreach cycle, not crash
  13. inject_reply raises for invalid prospect_id (CWE-20)
  14. inject_reply strips null bytes from body
  15. process_prospect_replies skips invalid prospect_id before DNC mutation
  16. load_state: poisoned numeric fields use safe defaults (CWE-20)
  17. load_state: invalid DNC entries stripped on restore (CWE-20)
  18. load_state: invalid cooldown keys stripped on restore (CWE-20)
  19. error messages do not contain raw email addresses (_sanitize_error, CWE-209)
  20. approve_content rejects invalid content_id format (CWE-20)
  21. generate_social_variants rejects invalid content_id format (CWE-20)

Design Label: TEST / MKT-006-HARDENING
Owner: QA Team
Copyright © 2020 Inoni Limited Liability Company
License: BSL 1.1
"""

from __future__ import annotations

import os

import pytest


from self_marketing_orchestrator import (  # noqa: I001
    SelfMarketingOrchestrator,
    ComplianceDecision,
    ContentStatus,
    _validate_prospect_id,
    _validate_channel,
    _validate_topic,
    _sanitize_error,
    _PROSPECT_ID_RE,
    _MAX_KEYWORDS,
    _MAX_KEYWORD_LEN,
    _MAX_REPLY_BODY,
    _MAX_PENDING_REPLIES,
    _MAX_DNC_ENTRIES,
    _MAX_LAST_CONTACTED,
    _MAX_CONTENT_ITEMS,
    _ALLOWED_CHANNELS,
    _MAX_TOPIC_LEN,
    PartnershipStatus,
    DEFAULT_DESIRED_OFFERINGS,
)


# ---------------------------------------------------------------------------
# Helpers / stubs
# ---------------------------------------------------------------------------

class _MockPersistence:
    def __init__(self):
        self._store = {}

    def save_document(self, doc_id, document):
        self._store[doc_id] = document

    def load_document(self, doc_id):
        return self._store.get(doc_id)


def _make_orch(**kwargs) -> SelfMarketingOrchestrator:
    return SelfMarketingOrchestrator(**kwargs)


# ---------------------------------------------------------------------------
# 1. prospect_id validation (CWE-20)
# ---------------------------------------------------------------------------

class TestProspectIdValidation:
    """_validate_prospect_id must enforce the regex constraint."""

    def test_valid_uuid_style(self):
        assert _validate_prospect_id("a1b2c3d4-e5f6-0000-aaaa-bbbbccccdddd") == \
            "a1b2c3d4-e5f6-0000-aaaa-bbbbccccdddd"

    def test_valid_email_style(self):
        assert _validate_prospect_id("user@example.com") == "user@example.com"

    def test_valid_slug(self):
        assert _validate_prospect_id("hubspot-partner_01") == "hubspot-partner_01"

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            _validate_prospect_id("")

    def test_too_long_raises(self):
        with pytest.raises(ValueError):
            _validate_prospect_id("a" * 201)

    def test_space_raises(self):
        with pytest.raises(ValueError):
            _validate_prospect_id("bad id here")

    def test_injection_characters_raise(self):
        for bad in ["<script>", "'; DROP TABLE", "id\x00null", "../../../etc"]:
            with pytest.raises(ValueError):
                _validate_prospect_id(bad)

    def test_non_string_raises(self):
        with pytest.raises(ValueError):
            _validate_prospect_id(12345)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 2. channel allowlist (CWE-20)
# ---------------------------------------------------------------------------

class TestChannelValidation:
    def test_allowed_channels_pass(self):
        for ch in _ALLOWED_CHANNELS:
            assert _validate_channel(ch) == ch

    def test_unknown_channel_raises(self):
        with pytest.raises(ValueError):
            _validate_channel("fax")

    def test_empty_channel_raises(self):
        with pytest.raises(ValueError):
            _validate_channel("")

    def test_injection_channel_raises(self):
        with pytest.raises(ValueError):
            _validate_channel("<script>alert(1)</script>")


# ---------------------------------------------------------------------------
# 3 & 4. Topic validation (CWE-20)
# ---------------------------------------------------------------------------

class TestTopicValidation:
    def test_valid_topic_returned(self):
        assert _validate_topic("AI automation") == "AI automation"

    def test_oversized_topic_raises(self):
        with pytest.raises(ValueError, match="maximum length"):
            _validate_topic("x" * (_MAX_TOPIC_LEN + 1))

    def test_null_bytes_stripped(self):
        result = _validate_topic("hello\x00world")
        assert "\x00" not in result
        assert "hello" in result

    def test_non_string_raises(self):
        with pytest.raises(ValueError):
            _validate_topic(42)  # type: ignore[arg-type]

    def test_generate_blog_post_rejects_oversized_topic(self):
        orch = _make_orch()
        with pytest.raises(ValueError):
            orch.generate_blog_post("x" * (_MAX_TOPIC_LEN + 1))

    def test_generate_case_study_rejects_oversized_subject(self):
        orch = _make_orch()
        with pytest.raises(ValueError):
            orch.generate_case_study("x" * (_MAX_TOPIC_LEN + 1))

    def test_generate_tutorial_rejects_oversized_feature(self):
        orch = _make_orch()
        with pytest.raises(ValueError):
            orch.generate_tutorial("x" * (_MAX_TOPIC_LEN + 1))

    def test_generate_blog_post_strips_null_bytes(self):
        orch = _make_orch()
        content = orch.generate_blog_post("null\x00byte\x00topic", ["kw"])
        assert "\x00" not in content.topic


# ---------------------------------------------------------------------------
# 5 & 6. Keyword caps (CWE-400 / CWE-20)
# ---------------------------------------------------------------------------

class TestKeywordCaps:
    def test_keyword_list_truncated_at_max(self):
        orch = _make_orch()
        big_list = [f"keyword{i}" for i in range(_MAX_KEYWORDS + 20)]
        content = orch.generate_blog_post("AI automation", big_list)
        assert len(content.keywords) <= _MAX_KEYWORDS

    def test_long_keyword_truncated(self):
        orch = _make_orch()
        long_kw = "k" * (_MAX_KEYWORD_LEN + 50)
        content = orch.generate_blog_post("Test topic", [long_kw])
        assert all(len(k) <= _MAX_KEYWORD_LEN for k in content.keywords)


# ---------------------------------------------------------------------------
# 7. Reply body size cap (CWE-400)
# ---------------------------------------------------------------------------

class TestReplyBodyCap:
    def test_body_truncated_at_max(self):
        orch = _make_orch()
        big_body = "a" * (_MAX_REPLY_BODY + 5000)
        orch.inject_reply("valid-prospect-1", big_body)
        with orch._lock:
            stored = orch._pending_replies[0]["body"]
        assert len(stored) == _MAX_REPLY_BODY

    def test_null_bytes_stripped_from_body(self):
        orch = _make_orch()
        orch.inject_reply("valid-prospect-2", "hello\x00world")
        with orch._lock:
            stored = orch._pending_replies[0]["body"]
        assert "\x00" not in stored

    def test_non_string_body_treated_as_empty(self):
        orch = _make_orch()
        orch.inject_reply("valid-prospect-3", None)  # type: ignore[arg-type]
        with orch._lock:
            stored = orch._pending_replies[0]["body"]
        assert stored == ""


# ---------------------------------------------------------------------------
# 8. Pending-replies queue cap (CWE-400)
# ---------------------------------------------------------------------------

class TestPendingRepliesQueueCap:
    def test_queue_does_not_exceed_max(self):
        orch = _make_orch()
        for i in range(_MAX_PENDING_REPLIES + 50):
            orch.inject_reply(f"prospect-{i:04d}", "test reply")
        with orch._lock:
            assert len(orch._pending_replies) <= _MAX_PENDING_REPLIES

    def test_oldest_reply_dropped_when_full(self):
        orch = _make_orch()
        # Fill queue to max
        for i in range(_MAX_PENDING_REPLIES):
            orch.inject_reply(f"old-prospect-{i:04d}", f"reply-{i}")
        # Add one more — oldest should be evicted
        orch.inject_reply("newest-prospect", "newest reply")
        with orch._lock:
            bodies = [r["body"] for r in orch._pending_replies]
        assert "newest reply" in bodies
        # Queue must still be within cap
        assert len(bodies) <= _MAX_PENDING_REPLIES


# ---------------------------------------------------------------------------
# 9. DNC set hard cap (CWE-400)
# ---------------------------------------------------------------------------

class TestDNCSetCap:
    def test_dnc_set_capped_at_max(self, monkeypatch):
        orch = _make_orch()
        # Fill the DNC set to the cap
        with orch._lock:
            for i in range(_MAX_DNC_ENTRIES):
                orch._dnc_set.add(f"p{i:06d}")

        # Inject a reply with opt-out — should NOT grow beyond cap
        orch.inject_reply("new-opter-1", "unsubscribe please")
        orch.process_prospect_replies()

        with orch._lock:
            assert len(orch._dnc_set) <= _MAX_DNC_ENTRIES

    def test_opt_out_at_capacity_still_counted_in_result(self):
        orch = _make_orch()
        with orch._lock:
            for i in range(_MAX_DNC_ENTRIES):
                orch._dnc_set.add(f"x{i:06d}")

        orch.inject_reply("overflow-opter", "stop emailing me")
        result = orch.process_prospect_replies()
        assert result["opt_outs"] == 1


# ---------------------------------------------------------------------------
# 10. _last_contacted dict hard cap (CWE-400)
# ---------------------------------------------------------------------------

class TestLastContactedCap:
    def test_last_contacted_does_not_grow_unbounded(self):
        orch = _make_orch()
        # Pre-fill to just below cap
        with orch._lock:
            for i in range(_MAX_LAST_CONTACTED):
                orch._last_contacted[f"pre-{i:06d}"] = "2026-01-01T00:00:00+00:00"

        # Trigger _send_outreach which must evict before inserting
        orch._send_outreach("new-prospect", "email", {})

        with orch._lock:
            assert len(orch._last_contacted) <= _MAX_LAST_CONTACTED

    def test_new_prospect_recorded_after_eviction(self):
        orch = _make_orch()
        with orch._lock:
            for i in range(_MAX_LAST_CONTACTED):
                orch._last_contacted[f"old-{i:06d}"] = "2025-01-01T00:00:00+00:00"
        orch._send_outreach("brand-new", "email", {})
        with orch._lock:
            assert "brand-new" in orch._last_contacted


# ---------------------------------------------------------------------------
# 11. Content catalogue hard cap (CWE-400)
# ---------------------------------------------------------------------------

class TestContentCatalogueCap:
    def test_content_dict_does_not_grow_beyond_cap(self):
        orch = _make_orch()
        # Fill to just below cap
        from self_marketing_orchestrator import GeneratedContent
        with orch._lock:
            for i in range(_MAX_CONTENT_ITEMS):
                cid = f"blog-{i:06d}"
                orch._content[cid] = GeneratedContent(
                    content_id=cid, category="blog", topic="t", content_type="blog",
                    title="T", body="B",
                )
        # Generate one more — eviction should occur
        orch.generate_blog_post("A new topic", ["AI"])
        with orch._lock:
            assert len(orch._content) <= _MAX_CONTENT_ITEMS


# ---------------------------------------------------------------------------
# 12. Invalid prospect skipped in outreach cycle (not crash)
# ---------------------------------------------------------------------------

class TestInvalidProspectSkippedInCycle:
    def test_invalid_prospect_id_skipped(self):
        orch = _make_orch()
        orch._get_prospects = lambda: [  # type: ignore[method-assign]
            {"id": "<script>alert(1)</script>", "channel": "email"},
            {"id": "valid-prospect-ok", "channel": "email"},
        ]
        result = orch.run_outreach_cycle()
        # The invalid prospect is skipped; the valid one proceeds
        assert result["prospects_evaluated"] == 2
        assert result["outreach_sent"] == 1

    def test_invalid_channel_skipped(self):
        orch = _make_orch()
        orch._get_prospects = lambda: [  # type: ignore[method-assign]
            {"id": "prospect-abc", "channel": "fax"},
        ]
        result = orch.run_outreach_cycle()
        # Invalid channel → validation error → skipped
        assert result["outreach_sent"] == 0
        assert len(result["errors"]) == 1

    def test_errors_do_not_contain_email_addresses(self):
        orch = _make_orch()
        orch._get_prospects = lambda: [  # type: ignore[method-assign]
            {"id": "badchannel", "channel": "fax@evil.com"},
        ]
        result = orch.run_outreach_cycle()
        for err in result["errors"]:
            assert "@" not in err or "<redacted>" in err


# ---------------------------------------------------------------------------
# 13. inject_reply raises for invalid prospect_id (CWE-20)
# ---------------------------------------------------------------------------

class TestInjectReplyValidation:
    def test_invalid_prospect_id_raises(self):
        orch = _make_orch()
        with pytest.raises(ValueError):
            orch.inject_reply("<evil>", "hello")

    def test_valid_prospect_id_accepted(self):
        orch = _make_orch()
        orch.inject_reply("valid-id-123", "hello")  # should not raise


# ---------------------------------------------------------------------------
# 14. inject_reply strips null bytes
# ---------------------------------------------------------------------------

class TestInjectReplyNullByteStripping:
    def test_null_bytes_removed(self):
        orch = _make_orch()
        orch.inject_reply("prospect-x", "hello\x00world\x00")
        with orch._lock:
            body = orch._pending_replies[0]["body"]
        assert "\x00" not in body
        assert "hello" in body


# ---------------------------------------------------------------------------
# 15. process_prospect_replies skips invalid prospect_id before DNC mutation
# ---------------------------------------------------------------------------

class TestProcessRepliesSkipsInvalid:
    def test_invalid_id_not_added_to_dnc(self):
        orch = _make_orch()
        # Manually inject raw invalid data into _pending_replies (bypassing inject_reply)
        with orch._lock:
            orch._pending_replies = [
                {"prospect_id": "<script>", "body": "unsubscribe"},
                {"prospect_id": "valid-one", "body": "tell me more"},
            ]
        result = orch.process_prospect_replies()
        with orch._lock:
            assert "<script>" not in orch._dnc_set
        # The valid one still processed
        assert result["processed"] == 1
        assert result["positives"] == 1


# ---------------------------------------------------------------------------
# 16–18. load_state type guards and collection validation (CWE-20)
# ---------------------------------------------------------------------------

class TestLoadStateTypeGuards:
    def test_poisoned_published_count_uses_zero(self):
        pm = _MockPersistence()
        orch = _make_orch(persistence_manager=pm)
        pm.save_document("self_marketing_orchestrator_state", {
            "published_count": "evil_string",
            "category_index": 3,
        })
        orch2 = _make_orch(persistence_manager=pm)
        orch2.load_state()
        assert orch2._published_count == 0

    def test_poisoned_category_index_uses_zero(self):
        pm = _MockPersistence()
        pm.save_document("self_marketing_orchestrator_state", {
            "published_count": 2,
            "category_index": None,
        })
        orch = _make_orch(persistence_manager=pm)
        orch.load_state()
        assert orch._category_index == 0

    def test_invalid_dnc_entries_stripped(self):
        pm = _MockPersistence()
        pm.save_document("self_marketing_orchestrator_state", {
            "published_count": 0,
            "category_index": 0,
            "dnc_set": ["valid-id", "<script>alert(1)</script>", "another@valid.com", 12345],
        })
        orch = _make_orch(persistence_manager=pm)
        orch.load_state()
        with orch._lock:
            assert "valid-id" in orch._dnc_set
            assert "another@valid.com" in orch._dnc_set
            assert "<script>alert(1)</script>" not in orch._dnc_set
            assert 12345 not in orch._dnc_set

    def test_invalid_cooldown_keys_stripped(self):
        pm = _MockPersistence()
        pm.save_document("self_marketing_orchestrator_state", {
            "published_count": 0,
            "category_index": 0,
            "last_contacted": {
                "valid-id": "2026-01-01T00:00:00+00:00",
                "<script>": "2026-01-01T00:00:00+00:00",
                "user@ok.com": "2026-01-01T00:00:00+00:00",
            },
        })
        orch = _make_orch(persistence_manager=pm)
        orch.load_state()
        with orch._lock:
            assert "valid-id" in orch._last_contacted
            assert "user@ok.com" in orch._last_contacted
            assert "<script>" not in orch._last_contacted

    def test_non_dict_last_contacted_defaults_to_empty(self):
        pm = _MockPersistence()
        pm.save_document("self_marketing_orchestrator_state", {
            "published_count": 0,
            "category_index": 0,
            "last_contacted": "not-a-dict",
        })
        orch = _make_orch(persistence_manager=pm)
        orch.load_state()
        with orch._lock:
            assert orch._last_contacted == {}

    def test_non_list_dnc_set_defaults_to_empty(self):
        pm = _MockPersistence()
        pm.save_document("self_marketing_orchestrator_state", {
            "published_count": 0,
            "category_index": 0,
            "dnc_set": "not-a-list",
        })
        orch = _make_orch(persistence_manager=pm)
        orch.load_state()
        with orch._lock:
            assert orch._dnc_set == set()


# ---------------------------------------------------------------------------
# 19. _sanitize_error strips email addresses (CWE-209)
# ---------------------------------------------------------------------------

class TestErrorMessageSanitization:
    def test_email_redacted_from_error(self):
        exc = ValueError("could not reach user@example.com — timeout")
        msg = _sanitize_error(exc)
        assert "@example.com" not in msg
        assert "<redacted>" in msg

    def test_truncated_to_max_length(self):
        exc = RuntimeError("x" * 500)
        msg = _sanitize_error(exc)
        from self_marketing_orchestrator import _MAX_ERROR_MSG_LEN
        assert len(msg) <= _MAX_ERROR_MSG_LEN

    def test_type_name_preserved(self):
        exc = ValueError("something went wrong")
        msg = _sanitize_error(exc)
        assert "ValueError" in msg

    def test_cycle_errors_do_not_contain_email(self):
        """Errors stored in cycle results must never contain raw email addresses."""
        class _BadSEO:
            def analyse_content(self, title, body, url=""):
                raise RuntimeError("Cannot reach seo-api@provider.io: timeout")

        orch = _make_orch(seo_engine=_BadSEO())
        with orch._lock:
            orch._published_count = 100  # skip HITL gate

        result = orch.run_content_cycle()
        for err in result.get("errors", []):
            assert "@provider.io" not in err


# ---------------------------------------------------------------------------
# 20. approve_content rejects invalid content_id format (CWE-20)
# ---------------------------------------------------------------------------

class TestApproveContentValidation:
    def test_invalid_id_format_returns_false(self):
        orch = _make_orch()
        assert orch.approve_content("<script>alert(1)</script>") is False

    def test_too_long_id_returns_false(self):
        orch = _make_orch()
        assert orch.approve_content("a" * 65) is False

    def test_valid_but_nonexistent_id_returns_false(self):
        orch = _make_orch()
        assert orch.approve_content("blog-12345678") is False


# ---------------------------------------------------------------------------
# 21. generate_social_variants rejects invalid content_id format (CWE-20)
# ---------------------------------------------------------------------------

class TestSocialVariantsValidation:
    def test_invalid_id_returns_empty_list(self):
        orch = _make_orch()
        assert orch.generate_social_variants("<injection>") == []

    def test_non_string_returns_empty_list(self):
        orch = _make_orch()
        assert orch.generate_social_variants(12345) == []  # type: ignore[arg-type]
