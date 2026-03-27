"""Tests for social_media_moderation module."""

import unittest
import time
import threading
import sys
import os


from social_media_moderation import (
    PlatformType, ContentVerdict, ViolationCategory, ModerationAction,
    QueuePriority, AppealStatus, ConnectorHealth, AuthType,
    RateLimitConfig, AuthConfig, ModerationRule, QueueItem, Appeal,
    PlatformConnector, ContentClassifier, AutoModerationEngine,
    ModerationQueueManager, CrossPlatformPolicyEnforcer,
    ModerationAnalytics, AppealHandler, SocialMediaModerationSystem,
)


# ── Platform Connector Tests ──────────────────────────────────────────────

class TestPlatformConnector(unittest.TestCase):

    def _make(self, pt=PlatformType.FACEBOOK):
        return PlatformConnector("test", pt, capabilities=["post_moderation"])

    def test_health_check_default(self):
        c = self._make()
        h = c.health_check()
        self.assertEqual(h["health"], ConnectorHealth.HEALTHY.value)
        self.assertTrue(h["enabled"])

    def test_disable_enable(self):
        c = self._make()
        c.disable()
        h = c.health_check()
        self.assertEqual(h["health"], ConnectorHealth.DISABLED.value)
        c.enable()
        h = c.health_check()
        self.assertEqual(h["health"], ConnectorHealth.HEALTHY.value)

    def test_moderate_content(self):
        c = self._make()
        r = c.moderate_content("c1", "hello world", author_id="u1")
        self.assertEqual(r["content_id"], "c1")
        self.assertEqual(r["status"], "moderated")

    def test_moderate_disabled(self):
        c = self._make()
        c.disable()
        r = c.moderate_content("c1", "text")
        self.assertEqual(r["error"], "connector_disabled")

    def test_rate_limit(self):
        c = PlatformConnector("rl", PlatformType.TWITTER,
                              rate_limit=RateLimitConfig(max_requests=2, window_seconds=60))
        c.moderate_content("1", "a")
        c.moderate_content("2", "b")
        r = c.moderate_content("3", "c")
        self.assertEqual(r["error"], "rate_limited")

    def test_queue_operations(self):
        c = self._make()
        c.add_to_queue({"id": "q1", "text": "hello"})
        q = c.get_content_queue()
        self.assertEqual(len(q), 1)
        self.assertEqual(q[0]["id"], "q1")

    def test_status(self):
        c = self._make()
        s = c.status()
        self.assertIn("capabilities", s)
        self.assertEqual(s["platform"], "facebook")

    def test_all_platforms_instantiate(self):
        for pt in PlatformType:
            c = PlatformConnector(f"{pt.value}_test", pt)
            self.assertEqual(c.platform_type, pt)


# ── Content Classifier Tests ─────────────────────────────────────────────

class TestContentClassifier(unittest.TestCase):

    def setUp(self):
        self.clf = ContentClassifier()

    def test_safe_content(self):
        r = self.clf.classify("What a nice sunny day!")
        self.assertEqual(r["verdict"], ContentVerdict.SAFE.value)
        self.assertGreater(r["confidence"], 0.8)

    def test_single_violation_warning(self):
        r = self.clf.classify("buy now and get free money")
        self.assertEqual(r["verdict"], ContentVerdict.WARNING.value)
        self.assertIn(ViolationCategory.SPAM.value, r["categories"])

    def test_multiple_violations(self):
        r = self.clf.classify("buy now click here and kill them all")
        self.assertEqual(r["verdict"], ContentVerdict.VIOLATION.value)
        self.assertGreaterEqual(len(r["categories"]), 2)

    def test_history_tracking(self):
        self.clf.classify("test1")
        self.clf.classify("test2")
        self.assertEqual(len(self.clf.get_history()), 2)

    def test_context_passthrough(self):
        r = self.clf.classify("ok", context={"source": "api"})
        self.assertEqual(r["context"]["source"], "api")


# ── Auto-Moderation Rules Engine Tests ────────────────────────────────────

class TestAutoModerationEngine(unittest.TestCase):

    def setUp(self):
        self.eng = AutoModerationEngine()

    def test_add_and_get_rule(self):
        rule = ModerationRule(rule_id="r1", name="spam", keywords=["buy now"],
                              action=ModerationAction.REJECT)
        self.eng.add_rule(rule)
        r = self.eng.get_rule("r1")
        self.assertIsNotNone(r)
        self.assertEqual(r["name"], "spam")

    def test_remove_rule(self):
        self.eng.add_rule(ModerationRule(rule_id="r2", name="x"))
        r = self.eng.remove_rule("r2")
        self.assertTrue(r["removed"])
        self.assertIsNone(self.eng.get_rule("r2"))

    def test_remove_missing(self):
        r = self.eng.remove_rule("nope")
        self.assertFalse(r["removed"])

    def test_evaluate_keyword_hit(self):
        self.eng.add_rule(ModerationRule(rule_id="k1", name="kw",
                                         keywords=["spam"],
                                         action=ModerationAction.REJECT))
        r = self.eng.evaluate("this is spam content")
        self.assertEqual(len(r["triggered_rules"]), 1)
        self.assertEqual(r["recommended_action"], ModerationAction.REJECT.value)

    def test_evaluate_regex_hit(self):
        self.eng.add_rule(ModerationRule(rule_id="rx", name="regex",
                                         regex_patterns=[r"\b\d{16}\b"],
                                         action=ModerationAction.FLAG))
        r = self.eng.evaluate("card 1234567890123456 here")
        self.assertEqual(len(r["triggered_rules"]), 1)

    def test_evaluate_reputation(self):
        self.eng.add_rule(ModerationRule(rule_id="rep", name="rep",
                                         min_reputation_score=0.5,
                                         action=ModerationAction.MUTE))
        r = self.eng.evaluate("hi", author_reputation=0.2)
        self.assertEqual(len(r["triggered_rules"]), 1)

    def test_evaluate_no_trigger(self):
        self.eng.add_rule(ModerationRule(rule_id="n", name="n", keywords=["xyz"]))
        r = self.eng.evaluate("normal text")
        self.assertEqual(len(r["triggered_rules"]), 0)
        self.assertEqual(r["recommended_action"], ModerationAction.APPROVE.value)

    def test_list_rules_platform_filter(self):
        self.eng.add_rule(ModerationRule(rule_id="a", name="a", platform=PlatformType.REDDIT))
        self.eng.add_rule(ModerationRule(rule_id="b", name="b", platform=PlatformType.DISCORD))
        reddit_rules = self.eng.list_rules(platform=PlatformType.REDDIT)
        self.assertEqual(len(reddit_rules), 1)

    def test_auto_generated_rule_id(self):
        rule = ModerationRule(name="auto_id")
        result = self.eng.add_rule(rule)
        self.assertTrue(len(result["rule_id"]) > 0)


# ── Moderation Queue Manager Tests ────────────────────────────────────────

class TestModerationQueueManager(unittest.TestCase):

    def setUp(self):
        self.qm = ModerationQueueManager()

    def _item(self, verdict=ContentVerdict.WARNING, confidence=0.7, **kw):
        return QueueItem(content_id="c1", platform=PlatformType.YOUTUBE,
                         content_text="test", verdict=verdict,
                         confidence=confidence, **kw)

    def test_auto_approve(self):
        item = self._item(ContentVerdict.SAFE, 0.95)
        r = self.qm.enqueue(item)
        self.assertEqual(r["status"], "auto_approved")
        self.assertEqual(self.qm.queue_size(), 0)

    def test_auto_reject(self):
        item = self._item(ContentVerdict.VIOLATION, 0.9)
        r = self.qm.enqueue(item)
        self.assertEqual(r["status"], "auto_rejected")

    def test_queue_for_review(self):
        item = self._item(ContentVerdict.WARNING, 0.6)
        r = self.qm.enqueue(item)
        self.assertEqual(r["status"], "queued")
        self.assertEqual(self.qm.queue_size(), 1)

    def test_process_item(self):
        item = self._item(ContentVerdict.WARNING, 0.5, item_id="qi1")
        self.qm.enqueue(item)
        r = self.qm.process_item("qi1", ModerationAction.APPROVE, reviewer_id="mod1")
        self.assertEqual(r["status"], "processed")
        self.assertEqual(self.qm.queue_size(), 0)

    def test_process_missing(self):
        r = self.qm.process_item("missing", ModerationAction.APPROVE)
        self.assertIn("error", r)

    def test_queue_priority_order(self):
        self.qm.enqueue(QueueItem(item_id="low", content_id="l",
                                  platform=PlatformType.TIKTOK,
                                  priority=QueuePriority.LOW,
                                  verdict=ContentVerdict.WARNING, confidence=0.5))
        self.qm.enqueue(QueueItem(item_id="high", content_id="h",
                                  platform=PlatformType.TIKTOK,
                                  priority=QueuePriority.HIGH,
                                  verdict=ContentVerdict.WARNING, confidence=0.5))
        q = self.qm.get_queue()
        self.assertEqual(q[0]["item_id"], "high")

    def test_get_processed(self):
        item = self._item(ContentVerdict.SAFE, 0.95)
        self.qm.enqueue(item)
        self.assertGreaterEqual(len(self.qm.get_processed()), 1)


# ── Cross-Platform Policy Enforcer Tests ──────────────────────────────────

class TestCrossPlatformPolicyEnforcer(unittest.TestCase):

    def setUp(self):
        self.pe = CrossPlatformPolicyEnforcer()

    def test_global_policy_set(self):
        r = self.pe.set_global_policy({"max_links_per_post": 3})
        self.assertEqual(r["policy"]["max_links_per_post"], 3)

    def test_platform_override(self):
        self.pe.set_platform_override(PlatformType.LINKEDIN,
                                       {"require_verification": True})
        p = self.pe.get_effective_policy(PlatformType.LINKEDIN)
        self.assertTrue(p["require_verification"])

    def test_enforce_compliant(self):
        r = self.pe.enforce("normal text", PlatformType.DISCORD)
        self.assertTrue(r["compliant"])

    def test_enforce_too_many_links(self):
        self.pe.set_global_policy({"max_links_per_post": 1})
        text = "http://a.com http://b.com http://c.com"
        r = self.pe.enforce(text, PlatformType.FACEBOOK)
        self.assertFalse(r["compliant"])
        self.assertIn("too_many_links", r["violations"])

    def test_enforce_blocked_category(self):
        self.pe.set_global_policy({"blocked_categories": ["spam"]})
        r = self.pe.enforce("text", PlatformType.TWITTER,
                            metadata={"categories": ["spam"]})
        self.assertFalse(r["compliant"])

    def test_enforce_account_too_new(self):
        self.pe.set_global_policy({"min_author_age_days": 30})
        r = self.pe.enforce("text", PlatformType.REDDIT,
                            metadata={"author_age_days": 5})
        self.assertFalse(r["compliant"])
        self.assertIn("account_too_new", r["violations"])


# ── Moderation Analytics Tests ────────────────────────────────────────────

class TestModerationAnalytics(unittest.TestCase):

    def setUp(self):
        self.an = ModerationAnalytics()

    def test_record_and_summary(self):
        self.an.record_action(PlatformType.FACEBOOK, ModerationAction.REJECT,
                              ViolationCategory.SPAM, response_time_ms=120.0)
        s = self.an.get_summary()
        self.assertEqual(s["total_actions"], 1)
        self.assertEqual(s["avg_response_time_ms"], 120.0)

    def test_false_positive_rate(self):
        self.an.record_action(PlatformType.TWITTER, ModerationAction.REJECT,
                              is_false_positive=True)
        self.an.record_action(PlatformType.TWITTER, ModerationAction.REJECT,
                              is_false_positive=False)
        s = self.an.get_summary()
        self.assertAlmostEqual(s["false_positive_rate"], 0.5)

    def test_platform_breakdown(self):
        self.an.record_action(PlatformType.YOUTUBE, ModerationAction.FLAG)
        self.an.record_action(PlatformType.TIKTOK, ModerationAction.FLAG)
        b = self.an.get_platform_breakdown()
        self.assertEqual(b["total"], 2)
        self.assertIn("youtube", b["platforms"])

    def test_trend_filter(self):
        self.an.record_action(PlatformType.REDDIT, ModerationAction.REJECT,
                              ViolationCategory.HARASSMENT)
        self.an.record_action(PlatformType.REDDIT, ModerationAction.APPROVE)
        t = self.an.get_trend(category=ViolationCategory.HARASSMENT)
        self.assertEqual(len(t), 1)

    def test_empty_summary(self):
        s = self.an.get_summary()
        self.assertEqual(s["total_actions"], 0)
        self.assertEqual(s["false_positive_rate"], 0.0)


# ── Appeal Handler Tests ──────────────────────────────────────────────────

class TestAppealHandler(unittest.TestCase):

    def setUp(self):
        self.ah = AppealHandler()

    def test_submit_appeal(self):
        r = self.ah.submit_appeal("c1", PlatformType.INSTAGRAM, "u1", "unfair")
        self.assertEqual(r["status"], AppealStatus.PENDING.value)
        self.assertEqual(r["platform"], "instagram")

    def test_review_approve(self):
        a = self.ah.submit_appeal("c2", PlatformType.DISCORD, "u2", "reason")
        r = self.ah.review_appeal(a["appeal_id"], "mod1", approved=True,
                                   notes="overturned")
        self.assertEqual(r["status"], AppealStatus.APPROVED.value)

    def test_review_deny(self):
        a = self.ah.submit_appeal("c3", PlatformType.LINKEDIN, "u3", "r")
        r = self.ah.review_appeal(a["appeal_id"], "mod2", approved=False)
        self.assertEqual(r["status"], AppealStatus.DENIED.value)

    def test_escalate(self):
        a = self.ah.submit_appeal("c4", PlatformType.TIKTOK, "u4", "r")
        r = self.ah.escalate_appeal(a["appeal_id"])
        self.assertEqual(r["status"], AppealStatus.ESCALATED.value)

    def test_missing_appeal(self):
        r = self.ah.review_appeal("nope", "m", True)
        self.assertIn("error", r)

    def test_list_by_status(self):
        self.ah.submit_appeal("c5", PlatformType.REDDIT, "u5", "r")
        self.ah.submit_appeal("c6", PlatformType.REDDIT, "u6", "r")
        pending = self.ah.list_appeals(status=AppealStatus.PENDING)
        self.assertEqual(len(pending), 2)

    def test_outcomes_summary(self):
        self.ah.submit_appeal("c7", PlatformType.YOUTUBE, "u7", "r")
        s = self.ah.get_outcomes_summary()
        self.assertEqual(s["total_appeals"], 1)
        self.assertIn("pending", s["by_status"])


# ── Social Media Moderation System (Integration) ──────────────────────────

class TestSocialMediaModerationSystem(unittest.TestCase):

    def setUp(self):
        self.sys = SocialMediaModerationSystem()

    def test_all_connectors_registered(self):
        connectors = self.sys.list_connectors()
        platforms = {c["platform"] for c in connectors}
        for pt in PlatformType:
            self.assertIn(pt.value, platforms)

    def test_get_connector(self):
        c = self.sys.get_connector(PlatformType.DISCORD)
        self.assertIsNotNone(c)
        self.assertEqual(c.platform_type, PlatformType.DISCORD)

    def test_moderate_safe(self):
        r = self.sys.moderate("Nice weather today", PlatformType.FACEBOOK)
        self.assertEqual(r["classification"]["verdict"], ContentVerdict.SAFE.value)

    def test_moderate_violation(self):
        r = self.sys.moderate("buy now click here and kill threat",
                              PlatformType.TWITTER)
        self.assertIn(r["classification"]["verdict"],
                      [ContentVerdict.WARNING.value, ContentVerdict.VIOLATION.value])

    def test_status(self):
        s = self.sys.status()
        self.assertEqual(s["connectors"], len(PlatformType))
        self.assertIn("queue_size", s)

    def test_connector_capabilities(self):
        c = self.sys.get_connector(PlatformType.YOUTUBE)
        self.assertIn("comment_moderation", c.capabilities)

    def test_thread_safety(self):
        errors = []

        def worker(i):
            try:
                self.sys.moderate(f"content {i}", PlatformType.REDDIT,
                                  content_id=f"t{i}")
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(errors), 0)


if __name__ == "__main__":
    unittest.main()
