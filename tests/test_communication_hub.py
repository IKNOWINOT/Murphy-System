"""
Tests for the Communication Hub — IM, Voice, Video, Email, Automation, Moderator.

Covers:
1. Cross-account IM messaging (messages visible from both sender and recipient)
2. Session persistence within process (DB-backed SQLite)
3. Voice and video call signalling lifecycle
4. Email send / inbox / outbox / mark-read
5. Automation rule creation and evaluation
6. Moderator moderation actions and broadcast

Run with:
    MURPHY_ENV=development python -m pytest tests/test_communication_hub.py -v --no-cov
"""

from __future__ import annotations

import sys
import os
import pytest

# Ensure src/ is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from src.communication_hub import (
    IMStore,
    CallSessionStore,
    EmailStore,
    AutomationRuleStore,
    ModeratorConsole,
    CallState,
    ModerationAction,
    AutomationTrigger,
    _check_automod,
)


# ---------------------------------------------------------------------------
# Fixtures — fresh stores per test (avoids cross-test state)
# ---------------------------------------------------------------------------

@pytest.fixture()
def im():
    return IMStore()


@pytest.fixture()
def calls():
    return CallSessionStore()


@pytest.fixture()
def emails():
    return EmailStore()


@pytest.fixture()
def rules():
    return AutomationRuleStore()


@pytest.fixture()
def mod():
    return ModeratorConsole()


# ===========================================================================
# Automod helper
# ===========================================================================

class TestAutomod:
    def test_clean_text_passes(self):
        result = _check_automod("Hello, how are you today?")
        assert result["flagged"] is False
        assert result["action"] == ModerationAction.ALLOW

    def test_blocked_word_flagged(self):
        result = _check_automod("This message contains spam content.")
        assert result["flagged"] is True
        assert "spam" in result["matches"]

    def test_blocked_word_case_insensitive(self):
        result = _check_automod("SCAM alert!")
        assert result["flagged"] is True

    def test_extra_blocked_words(self):
        result = _check_automod("buy crypto now", extra_words=["crypto"])
        assert result["flagged"] is True
        assert "crypto" in result["matches"]

    def test_extra_words_do_not_affect_default(self):
        result = _check_automod("hello world", extra_words=["crypto"])
        assert result["flagged"] is False


# ===========================================================================
# IM Store — cross-account messaging
# ===========================================================================

class TestIMStore:
    def test_create_direct_thread(self, im: IMStore):
        thread = im.create_thread(participants=["alice", "bob"])
        assert thread["id"]
        assert "alice" in thread["participants"]
        assert "bob" in thread["participants"]
        assert thread["type"] == "direct"

    def test_create_group_thread(self, im: IMStore):
        thread = im.create_thread(
            participants=["alice", "bob", "carol"],
            name="Project Alpha",
            thread_type="group",
        )
        assert thread["type"] == "group"
        assert thread["name"] == "Project Alpha"
        assert len(thread["participants"]) == 3

    def test_list_threads_unfiltered(self, im: IMStore):
        im.create_thread(["alice", "bob"])
        im.create_thread(["carol", "dave"])
        threads = im.list_threads()
        assert len(threads) >= 2

    def test_list_threads_filtered_by_user(self, im: IMStore):
        t1 = im.create_thread(["alice", "bob"])
        im.create_thread(["carol", "dave"])
        alice_threads = im.list_threads(user="alice")
        ids = [t["id"] for t in alice_threads]
        assert t1["id"] in ids
        # carol/dave thread should not appear for alice
        carol_threads = im.list_threads(user="carol")
        for t in carol_threads:
            assert t1["id"] != t["id"]

    def test_get_thread(self, im: IMStore):
        t = im.create_thread(["alice", "bob"])
        fetched = im.get_thread(t["id"])
        assert fetched is not None
        assert fetched["id"] == t["id"]

    def test_get_nonexistent_thread_returns_none(self, im: IMStore):
        assert im.get_thread("no-such-thread") is None

    def test_post_message_alice_to_bob(self, im: IMStore):
        t = im.create_thread(["alice", "bob"])
        msg = im.post_message(thread_id=t["id"], sender="alice", content="Hey Bob!")
        assert msg["sender"] == "alice"
        assert msg["content"] == "Hey Bob!"
        assert msg["thread_id"] == t["id"]

    def test_post_message_bob_replies(self, im: IMStore):
        t = im.create_thread(["alice", "bob"])
        im.post_message(t["id"], "alice", "Hey Bob!")
        msg2 = im.post_message(t["id"], "bob", "Hey Alice!")
        assert msg2["sender"] == "bob"
        assert msg2["content"] == "Hey Alice!"

    def test_get_messages_both_accounts_see_same(self, im: IMStore):
        """Both accounts in a thread must see all messages."""
        t = im.create_thread(["alice", "bob"])
        im.post_message(t["id"], "alice", "Message 1")
        im.post_message(t["id"], "bob",   "Message 2")
        im.post_message(t["id"], "alice", "Message 3")
        msgs = im.get_messages(t["id"])
        assert len(msgs) == 3
        senders = [m["sender"] for m in msgs]
        assert "alice" in senders
        assert "bob" in senders

    def test_get_messages_limit(self, im: IMStore):
        t = im.create_thread(["alice", "bob"])
        for i in range(10):
            im.post_message(t["id"], "alice", f"msg {i}")
        msgs = im.get_messages(t["id"], limit=5)
        assert len(msgs) == 5

    def test_post_to_nonexistent_thread_raises(self, im: IMStore):
        with pytest.raises(KeyError):
            im.post_message("bad-thread", "alice", "hello")

    def test_message_automod_flags_spam(self, im: IMStore):
        t = im.create_thread(["alice", "bob"])
        msg = im.post_message(t["id"], "alice", "This is spam content")
        assert msg["automod"]["flagged"] is True

    def test_message_automod_clean(self, im: IMStore):
        t = im.create_thread(["alice", "bob"])
        msg = im.post_message(t["id"], "alice", "Good morning!")
        assert msg["automod"]["flagged"] is False

    def test_add_reaction(self, im: IMStore):
        t = im.create_thread(["alice", "bob"])
        msg = im.post_message(t["id"], "alice", "Hello!")
        reactions = im.add_reaction(t["id"], msg["id"], "👍", "bob")
        assert "👍" in reactions
        assert "bob" in reactions["👍"]

    def test_add_reaction_deduplicates(self, im: IMStore):
        t = im.create_thread(["alice", "bob"])
        msg = im.post_message(t["id"], "alice", "Hello!")
        im.add_reaction(t["id"], msg["id"], "👍", "bob")
        reactions = im.add_reaction(t["id"], msg["id"], "👍", "bob")
        assert len(reactions["👍"]) == 1  # Not duplicated

    def test_messages_persist_across_store_instances(self, im: IMStore):
        """Simulate persistence: write via one store, read via another (same DB)."""
        t = im.create_thread(["alice", "bob"])
        im.post_message(t["id"], "alice", "Persisted message")
        # A second IMStore instance reads from the same DB
        im2 = IMStore()
        msgs = im2.get_messages(t["id"])
        assert any(m["content"] == "Persisted message" for m in msgs), (
            "Message should be readable from a second store instance (same SQLite DB)"
        )

    def test_threads_persist_across_store_instances(self, im: IMStore):
        """Thread created in one store instance must be visible from another."""
        t = im.create_thread(["alice", "bob"], name="PersistTest")
        im2 = IMStore()
        fetched = im2.get_thread(t["id"])
        assert fetched is not None
        assert fetched["name"] == "PersistTest"


# ===========================================================================
# Call Sessions
# ===========================================================================

class TestCallSessionStore:
    def test_create_voice_session(self, calls: CallSessionStore):
        s = calls.create_session("alice", ["bob"], call_type="voice")
        assert s["type"] == "voice"
        assert s["caller"] == "alice"
        assert s["state"] == CallState.RINGING

    def test_create_video_session(self, calls: CallSessionStore):
        s = calls.create_session("alice", ["bob", "carol"], call_type="video")
        assert s["type"] == "video"
        assert len(s["participants"]) == 2

    def test_answer_session(self, calls: CallSessionStore):
        s = calls.create_session("alice", ["bob"])
        answered = calls.answer_session(s["id"], sdp_answer="v=0\r\n...")
        assert answered["state"] == CallState.ACTIVE
        assert answered["answered_at"] is not None

    def test_hold_session(self, calls: CallSessionStore):
        s = calls.create_session("alice", ["bob"])
        calls.answer_session(s["id"])
        on_hold = calls.hold_session(s["id"])
        assert on_hold["state"] == CallState.ON_HOLD

    def test_end_session_records_duration(self, calls: CallSessionStore):
        s = calls.create_session("alice", ["bob"])
        calls.answer_session(s["id"])
        ended = calls.end_session(s["id"])
        assert ended["state"] == CallState.ENDED
        assert ended["ended_at"] is not None
        assert ended["duration_seconds"] is not None
        assert ended["duration_seconds"] >= 0

    def test_end_unanswered_session_no_duration(self, calls: CallSessionStore):
        s = calls.create_session("alice", ["bob"])
        ended = calls.end_session(s["id"])
        assert ended["state"] == CallState.ENDED
        assert ended["duration_seconds"] is None

    def test_reject_session(self, calls: CallSessionStore):
        s = calls.create_session("alice", ["bob"])
        rejected = calls.reject_session(s["id"])
        assert rejected["state"] == CallState.REJECTED

    def test_add_ice_candidate(self, calls: CallSessionStore):
        s = calls.create_session("alice", ["bob"])
        calls.add_ice_candidate(s["id"], "candidate:12345")
        fetched = calls.get_session(s["id"])
        assert "candidate:12345" in fetched["ice_candidates"]

    def test_list_sessions_filtered_by_user(self, calls: CallSessionStore):
        s1 = calls.create_session("alice", ["bob"])
        calls.create_session("carol", ["dave"])
        alice_sessions = calls.list_sessions(user="alice")
        ids = [s["id"] for s in alice_sessions]
        assert s1["id"] in ids

    def test_list_sessions_filtered_by_type(self, calls: CallSessionStore):
        calls.create_session("alice", ["bob"], call_type="voice")
        calls.create_session("alice", ["carol"], call_type="video")
        voice_only = calls.list_sessions(call_type="voice")
        assert all(s["type"] == "voice" for s in voice_only)

    def test_end_session_with_voicemail(self, calls: CallSessionStore):
        s = calls.create_session("alice", ["bob"])
        ended = calls.end_session(s["id"], voicemail_url="https://cdn.murphy/vm/123.mp3")
        assert ended["voicemail_url"] == "https://cdn.murphy/vm/123.mp3"

    def test_sessions_persist_across_store_instances(self, calls: CallSessionStore):
        s = calls.create_session("alice", ["bob"])
        store2 = CallSessionStore()
        fetched = store2.get_session(s["id"])
        assert fetched is not None
        assert fetched["caller"] == "alice"


# ===========================================================================
# Email Store
# ===========================================================================

class TestEmailStore:
    def test_send_email(self, emails: EmailStore):
        e = emails.compose_and_send(
            sender="alice@murphy.systems",
            recipients=["bob@murphy.systems"],
            subject="Hello",
            body="Hi Bob!",
        )
        assert e["id"]
        assert e["status"] == "sent"

    def test_recipient_receives_in_inbox(self, emails: EmailStore):
        e = emails.compose_and_send(
            sender="alice@murphy.systems",
            recipients=["bob@murphy.systems"],
            subject="Test",
            body="Body",
        )
        inbox = emails.get_inbox("bob@murphy.systems")
        ids = [m["id"] for m in inbox]
        assert e["id"] in ids

    def test_sender_not_in_own_inbox(self, emails: EmailStore):
        emails.compose_and_send(
            sender="alice@murphy.systems",
            recipients=["bob@murphy.systems"],
            subject="Test",
            body="Body",
        )
        alice_inbox = emails.get_inbox("alice@murphy.systems")
        # Alice is not in recipients, so she should not see it in her inbox
        assert len(alice_inbox) == 0

    def test_sender_sees_in_outbox(self, emails: EmailStore):
        e = emails.compose_and_send(
            sender="alice@murphy.systems",
            recipients=["bob@murphy.systems"],
            subject="Test",
            body="Body",
        )
        outbox = emails.get_outbox("alice@murphy.systems")
        ids = [m["id"] for m in outbox]
        assert e["id"] in ids

    def test_cc_recipient_receives(self, emails: EmailStore):
        e = emails.compose_and_send(
            sender="alice@murphy.systems",
            recipients=["bob@murphy.systems"],
            cc=["carol@murphy.systems"],
            subject="CC Test",
            body="Body",
        )
        carol_inbox = emails.get_inbox("carol@murphy.systems")
        ids = [m["id"] for m in carol_inbox]
        assert e["id"] in ids

    def test_mark_read(self, emails: EmailStore):
        e = emails.compose_and_send(
            sender="alice@murphy.systems",
            recipients=["bob@murphy.systems"],
            subject="Hi",
            body="Hey!",
        )
        updated = emails.mark_read(e["id"], "bob@murphy.systems")
        assert "bob@murphy.systems" in updated["read_by"]

    def test_mark_read_idempotent(self, emails: EmailStore):
        e = emails.compose_and_send(
            sender="alice@murphy.systems",
            recipients=["bob@murphy.systems"],
            subject="Hi",
            body="Hey!",
        )
        emails.mark_read(e["id"], "bob@murphy.systems")
        updated = emails.mark_read(e["id"], "bob@murphy.systems")
        assert updated["read_by"].count("bob@murphy.systems") == 1

    def test_get_email(self, emails: EmailStore):
        e = emails.compose_and_send(
            sender="alice@murphy.systems",
            recipients=["bob@murphy.systems"],
            subject="Hi",
            body="Hey!",
        )
        fetched = emails.get_email(e["id"])
        assert fetched is not None
        assert fetched["id"] == e["id"]

    def test_automod_flags_body(self, emails: EmailStore):
        e = emails.compose_and_send(
            sender="alice@murphy.systems",
            recipients=["bob@murphy.systems"],
            subject="Normal subject",
            body="This body contains spam.",
        )
        assert e["automod"]["flagged"] is True

    def test_emails_persist_across_instances(self, emails: EmailStore):
        e = emails.compose_and_send(
            sender="alice@murphy.systems",
            recipients=["bob@murphy.systems"],
            subject="Persist test",
            body="This should survive.",
        )
        store2 = EmailStore()
        fetched = store2.get_email(e["id"])
        assert fetched is not None
        assert fetched["subject"] == "Persist test"


# ===========================================================================
# Automation Rules
# ===========================================================================

class TestAutomationRuleStore:
    def test_create_rule(self, rules: AutomationRuleStore):
        r = rules.create_rule(
            name="Test Rule",
            trigger=AutomationTrigger.ON_MESSAGE,
            channel="im",
            action="notify",
        )
        assert r["id"]
        assert r["enabled"] is True

    def test_list_rules(self, rules: AutomationRuleStore):
        rules.create_rule("R1", AutomationTrigger.ON_MESSAGE, "im", "notify")
        rules.create_rule("R2", AutomationTrigger.ON_EMAIL, "email", "archive")
        all_rules = rules.list_rules()
        names = [r["name"] for r in all_rules]
        assert "R1" in names
        assert "R2" in names

    def test_list_rules_filtered_by_channel(self, rules: AutomationRuleStore):
        rules.create_rule("IM Rule", AutomationTrigger.ON_MESSAGE, "im", "notify")
        rules.create_rule("Email Rule", AutomationTrigger.ON_EMAIL, "email", "archive")
        im_rules = rules.list_rules(channel="im")
        assert all(r["channel"] in ("im", "*") for r in im_rules)

    def test_toggle_rule_disable(self, rules: AutomationRuleStore):
        r = rules.create_rule("R", AutomationTrigger.ON_MESSAGE, "im", "notify")
        toggled = rules.toggle_rule(r["id"], enabled=False)
        assert toggled["enabled"] is False

    def test_toggle_rule_enable(self, rules: AutomationRuleStore):
        r = rules.create_rule("R", AutomationTrigger.ON_MESSAGE, "im", "notify")
        rules.toggle_rule(r["id"], enabled=False)
        toggled = rules.toggle_rule(r["id"], enabled=True)
        assert toggled["enabled"] is True

    def test_delete_rule(self, rules: AutomationRuleStore):
        r = rules.create_rule("R", AutomationTrigger.ON_MESSAGE, "im", "notify")
        deleted = rules.delete_rule(r["id"])
        assert deleted is True
        assert rules.get_rule(r["id"]) is None

    def test_delete_nonexistent_rule(self, rules: AutomationRuleStore):
        assert rules.delete_rule("no-such-id") is False

    def test_fire_rule_increments_count(self, rules: AutomationRuleStore):
        r = rules.create_rule("R", AutomationTrigger.ON_MESSAGE, "im", "notify")
        fired = rules.fire_rule(r["id"])
        assert fired["fire_count"] == 1
        fired2 = rules.fire_rule(r["id"])
        assert fired2["fire_count"] == 2

    def test_evaluate_matches_trigger_and_channel(self, rules: AutomationRuleStore):
        rules.create_rule("Match", AutomationTrigger.ON_MESSAGE, "im", "notify")
        rules.create_rule("No Match", AutomationTrigger.ON_EMAIL, "email", "archive")
        matched = rules.evaluate("on_message", "im", {"content": "hello"})
        names = [r["name"] for r in matched]
        assert "Match" in names
        assert "No Match" not in names

    def test_evaluate_keyword_condition(self, rules: AutomationRuleStore):
        rules.create_rule(
            "Urgent",
            AutomationTrigger.ON_EMAIL,
            "email",
            "escalate",
            conditions={"keyword": "urgent"},
        )
        matched_urgent = rules.evaluate("on_email", "email", {"content": "This is urgent!"})
        matched_normal = rules.evaluate("on_email", "email", {"content": "This is normal."})
        assert any(r["name"] == "Urgent" for r in matched_urgent)
        assert not any(r["name"] == "Urgent" for r in matched_normal)

    def test_evaluate_wildcard_channel(self, rules: AutomationRuleStore):
        rules.create_rule("Wildcard", AutomationTrigger.ON_MESSAGE, "*", "log")
        matched_im   = rules.evaluate("on_message", "im",    {"content": "hi"})
        matched_email = rules.evaluate("on_message", "email", {"content": "hi"})
        assert any(r["name"] == "Wildcard" for r in matched_im)
        assert any(r["name"] == "Wildcard" for r in matched_email)

    def test_disabled_rule_not_evaluated(self, rules: AutomationRuleStore):
        r = rules.create_rule("Disabled", AutomationTrigger.ON_MESSAGE, "im", "notify")
        rules.toggle_rule(r["id"], enabled=False)
        matched = rules.evaluate("on_message", "im", {"content": "hello"})
        assert not any(rule["name"] == "Disabled" for rule in matched)


# ===========================================================================
# Moderator Console
# ===========================================================================

class TestModeratorConsole:
    def test_set_user_role(self, mod: ModeratorConsole):
        profile = mod.set_user_role("alice", "moderator", by="admin")
        assert profile["role"] == "moderator"

    def test_warn_user(self, mod: ModeratorConsole):
        result = mod.warn_user("alice", reason="bad behaviour", by="mod1")
        assert result["warnings"] == 1

    def test_warn_user_increments(self, mod: ModeratorConsole):
        mod.warn_user("alice", "first", "mod1")
        result = mod.warn_user("alice", "second", "mod1")
        assert result["warnings"] == 2

    def test_mute_user(self, mod: ModeratorConsole):
        result = mod.mute_user("alice", reason="spamming", by="mod1")
        assert result["muted"] is True

    def test_unmute_user(self, mod: ModeratorConsole):
        mod.mute_user("alice", "spamming", "mod1")
        result = mod.unmute_user("alice", by="mod1")
        assert result["muted"] is False

    def test_ban_user(self, mod: ModeratorConsole):
        result = mod.ban_user("alice", reason="severe violation", by="admin")
        assert result["banned"] is True

    def test_unban_user(self, mod: ModeratorConsole):
        mod.ban_user("alice", "violation", "admin")
        result = mod.unban_user("alice", by="admin")
        assert result["banned"] is False

    def test_kick_user(self, mod: ModeratorConsole):
        result = mod.kick_user("alice", reason="disruption", by="mod1")
        assert result["kicked"] is True

    def test_add_blocked_words(self, mod: ModeratorConsole):
        updated = mod.add_blocked_words(["badword", "hateful"], by="admin")
        assert "badword" in updated
        assert "hateful" in updated

    def test_remove_blocked_word(self, mod: ModeratorConsole):
        mod.add_blocked_words(["badword"], by="admin")
        updated = mod.remove_blocked_word("badword", by="admin")
        assert "badword" not in updated

    def test_check_content_with_custom_blocked(self, mod: ModeratorConsole):
        mod.add_blocked_words(["crypto"], by="admin")
        result = mod.check_content("buy crypto now")
        assert result["flagged"] is True

    def test_check_clean_content(self, mod: ModeratorConsole):
        result = mod.check_content("Have a great day!")
        assert result["flagged"] is False

    def test_register_broadcast_target(self, mod: ModeratorConsole):
        mod.register_target("slack", "#announcements", by="admin")
        targets = mod.list_targets()
        assert "slack" in targets
        assert "#announcements" in targets["slack"]

    def test_register_unsupported_platform_raises(self, mod: ModeratorConsole):
        with pytest.raises(ValueError, match="not supported"):
            mod.register_target("fax", "123-456-7890", by="admin")

    def test_unregister_broadcast_target(self, mod: ModeratorConsole):
        mod.register_target("slack", "#announcements", by="admin")
        mod.unregister_target("slack", "#announcements", by="admin")
        targets = mod.list_targets()
        assert "slack" not in targets

    def test_broadcast_to_registered_targets(self, mod: ModeratorConsole):
        mod.register_target("im", "general", by="admin")
        mod.register_target("email", "all-staff", by="admin")
        result = mod.broadcast("System maintenance at midnight.", sender="admin")
        assert result["ok"] is True
        assert "im" in result["broadcast"]["results"]
        assert result["broadcast"]["results"]["im"]["status"] == "delivered"

    def test_broadcast_blocked_by_automod(self, mod: ModeratorConsole):
        mod.register_target("im", "general", by="admin")
        result = mod.broadcast("This is spam content!", sender="bad_actor")
        assert result["ok"] is False
        assert result["error"] == "broadcast_blocked_by_automod"

    def test_broadcast_history_records(self, mod: ModeratorConsole):
        mod.register_target("im", "general", by="admin")
        mod.broadcast("Announcement 1", sender="admin")
        mod.broadcast("Announcement 2", sender="admin")
        history = mod.broadcast_history()
        assert len(history) >= 2

    def test_broadcast_to_subset_of_platforms(self, mod: ModeratorConsole):
        mod.register_target("im",    "general",   by="admin")
        mod.register_target("slack", "#announcements", by="admin")
        result = mod.broadcast("IM only", sender="admin", platforms=["im"])
        assert result["ok"] is True
        assert list(result["broadcast"]["results"].keys()) == ["im"]

    def test_audit_log_records_actions(self, mod: ModeratorConsole):
        mod.warn_user("alice", "test", by="mod1")
        mod.ban_user("bob", "test", by="admin")
        log = mod.get_audit_log()
        actions = [entry["action"] for entry in log]
        assert ModerationAction.WARN in actions
        assert ModerationAction.BAN in actions

    def test_audit_log_records_broadcast(self, mod: ModeratorConsole):
        mod.register_target("im", "general", by="admin")
        mod.broadcast("Hello", sender="admin")
        log = mod.get_audit_log()
        actions = [entry["action"] for entry in log]
        assert "broadcast" in actions

    def test_list_users_after_actions(self, mod: ModeratorConsole):
        mod.set_user_role("alice", "moderator", by="admin")
        mod.set_user_role("bob", "member", by="admin")
        users = mod.list_users()
        usernames = [u["user"] for u in users]
        assert "alice" in usernames
        assert "bob" in usernames


# ===========================================================================
# Multi-account integration scenario
# ===========================================================================

class TestMultiAccountScenario:
    """
    End-to-end scenario: three accounts interact through IM, email, and
    moderation to confirm cross-account visibility and session persistence.
    """

    def test_three_account_group_chat(self, im: IMStore):
        """Alice, Bob, and Carol share a group thread and all see each other's messages."""
        t = im.create_thread(["alice", "bob", "carol"], name="Team Chat", thread_type="group")
        im.post_message(t["id"], "alice", "Good morning team!")
        im.post_message(t["id"], "bob",   "Morning Alice!")
        im.post_message(t["id"], "carol", "Hey everyone!")
        msgs = im.get_messages(t["id"])
        assert len(msgs) == 3
        senders = {m["sender"] for m in msgs}
        assert senders == {"alice", "bob", "carol"}

    def test_parallel_direct_threads_are_isolated(self, im: IMStore):
        """Alice-Bob DM and Alice-Carol DM are separate; Bob cannot see Alice-Carol."""
        t_ab = im.create_thread(["alice", "bob"])
        t_ac = im.create_thread(["alice", "carol"])
        im.post_message(t_ab["id"], "alice", "Bob-only message")
        im.post_message(t_ac["id"], "alice", "Carol-only message")
        bob_msgs   = im.get_messages(t_ab["id"])
        carol_msgs = im.get_messages(t_ac["id"])
        assert len(bob_msgs)   == 1
        assert len(carol_msgs) == 1
        assert bob_msgs[0]["content"]   == "Bob-only message"
        assert carol_msgs[0]["content"] == "Carol-only message"
        # Bob's thread list does not include the Alice-Carol thread
        bob_threads = {t["id"] for t in im.list_threads(user="bob")}
        assert t_ab["id"] in bob_threads
        assert t_ac["id"] not in bob_threads

    def test_email_to_multiple_accounts(self, emails: EmailStore):
        """One email sent to three accounts appears in each account's inbox."""
        e = emails.compose_and_send(
            sender="admin@murphy.systems",
            recipients=["alice@murphy.systems", "bob@murphy.systems"],
            cc=["carol@murphy.systems"],
            subject="Team update",
            body="Important news.",
        )
        for user in ["alice@murphy.systems", "bob@murphy.systems", "carol@murphy.systems"]:
            inbox = emails.get_inbox(user)
            assert any(m["id"] == e["id"] for m in inbox), f"{user} should see the email"

    def test_moderator_bans_user_is_reflected_in_profile(self, mod: ModeratorConsole):
        mod.ban_user("spammer", reason="flood", by="mod1")
        profile = mod.get_user("spammer")
        assert profile["banned"] is True

    def test_broadcast_reaches_all_registered_platforms(self, mod: ModeratorConsole):
        for platform in ["im", "email", "slack"]:
            channel = f"general-{platform}"
            mod.register_target(platform, channel, by="admin")
        result = mod.broadcast(
            "Emergency maintenance window tonight.",
            sender="admin",
        )
        assert result["ok"] is True
        for platform in ["im", "email", "slack"]:
            assert platform in result["broadcast"]["results"]
            assert result["broadcast"]["results"][platform]["status"] == "delivered"
