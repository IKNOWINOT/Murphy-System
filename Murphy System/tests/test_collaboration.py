"""
Tests for the Collaboration System (Phase 2 of management systems parity).

Covers:
  1. Models & serialization
  2. @Mention parsing
  3. Notification engine
  4. Activity feed
  5. Comment manager (CRUD, reactions, threads)
  6. API router
"""

import os


import pytest

from collaboration.models import (
    ActivityFeedEntry,
    Comment,
    CommentEntityType,
    FeedEventType,
    Mention,
    MentionType,
    Notification,
    NotificationStatus,
    NotificationType,
)
from collaboration.mentions import UserResolver, parse_mentions
from collaboration.notifications import NotificationEngine
from collaboration.activity_feed import ActivityFeed
from collaboration.comment_manager import CommentManager


# ===================================================================
# 1. Models & serialization
# ===================================================================

class TestModels:
    def test_comment_to_dict(self):
        c = Comment(entity_type=CommentEntityType.ITEM, entity_id="i1",
                    author_id="u1", body="Hello")
        d = c.to_dict()
        assert d["entity_type"] == "item"
        assert d["body"] == "Hello"
        assert isinstance(d["mentions"], list)

    def test_comment_add_reaction(self):
        c = Comment(body="Nice")
        c.add_reaction("👍", "u1")
        c.add_reaction("👍", "u2")
        assert len(c.reactions["👍"]) == 2

    def test_comment_add_reaction_duplicate(self):
        c = Comment(body="Nice")
        c.add_reaction("👍", "u1")
        c.add_reaction("👍", "u1")
        assert len(c.reactions["👍"]) == 1

    def test_comment_remove_reaction(self):
        c = Comment(body="Nice")
        c.add_reaction("👍", "u1")
        assert c.remove_reaction("👍", "u1")
        assert "👍" not in c.reactions

    def test_comment_remove_reaction_missing(self):
        c = Comment(body="Nice")
        assert not c.remove_reaction("👍", "u1")

    def test_notification_mark_read(self):
        n = Notification(user_id="u1", title="Test")
        assert n.status == NotificationStatus.UNREAD
        n.mark_read()
        assert n.status == NotificationStatus.READ
        assert n.read_at is not None

    def test_notification_mark_archived(self):
        n = Notification(user_id="u1", title="Test")
        n.mark_archived()
        assert n.status == NotificationStatus.ARCHIVED

    def test_mention_to_dict(self):
        m = Mention(mention_type=MentionType.USER, target_id="u1", target_name="alice")
        d = m.to_dict()
        assert d["mention_type"] == "user"
        assert d["target_id"] == "u1"

    def test_activity_feed_entry_to_dict(self):
        e = ActivityFeedEntry(event_type=FeedEventType.COMMENT_ADDED, user_id="u1")
        d = e.to_dict()
        assert d["event_type"] == "comment_added"


# ===================================================================
# 2. @Mention parsing
# ===================================================================

class TestMentions:
    def test_parse_user_mention(self):
        mentions = parse_mentions("Hey @alice, check this out")
        assert len(mentions) == 1
        assert mentions[0].mention_type == MentionType.USER
        assert mentions[0].target_id == "alice"

    def test_parse_multiple_mentions(self):
        mentions = parse_mentions("@alice and @bob should review")
        assert len(mentions) == 2

    def test_parse_team_mention(self):
        mentions = parse_mentions("@team:engineering please review")
        assert len(mentions) == 1
        assert mentions[0].mention_type == MentionType.TEAM
        assert mentions[0].target_id == "engineering"

    def test_parse_everyone_mention(self):
        mentions = parse_mentions("@everyone heads up!")
        assert len(mentions) == 1
        assert mentions[0].mention_type == MentionType.EVERYONE

    def test_parse_no_mentions(self):
        mentions = parse_mentions("No mentions here")
        assert len(mentions) == 0

    def test_mention_offset(self):
        mentions = parse_mentions("Hey @alice")
        assert mentions[0].offset == 4
        assert mentions[0].length == 6

    def test_custom_resolver(self):
        resolver = UserResolver()
        resolver.register_user_lookup(
            lambda name: {"id": f"uid_{name}", "name": name.upper()}
        )
        mentions = parse_mentions("@bob", resolver)
        assert mentions[0].target_id == "uid_bob"
        assert mentions[0].target_name == "BOB"

    def test_custom_team_resolver(self):
        resolver = UserResolver()
        resolver.register_team_lookup(
            lambda name: {"id": f"tid_{name}", "name": f"Team {name}"}
        )
        mentions = parse_mentions("@team:devops", resolver)
        assert mentions[0].target_id == "tid_devops"


# ===================================================================
# 3. Notification engine
# ===================================================================

class TestNotifications:
    def test_send_notification(self):
        eng = NotificationEngine()
        n = eng.send(user_id="u1", notification_type=NotificationType.COMMENT,
                     title="New comment")
        assert n.user_id == "u1"
        assert n.status == NotificationStatus.UNREAD

    def test_send_to_many(self):
        eng = NotificationEngine()
        notifs = eng.send_to_many(
            ["u1", "u2", "u3"],
            notification_type=NotificationType.MENTION,
            title="You were mentioned",
        )
        assert len(notifs) == 3

    def test_list_notifications(self):
        eng = NotificationEngine()
        eng.send(user_id="u1", notification_type=NotificationType.COMMENT, title="A")
        eng.send(user_id="u1", notification_type=NotificationType.MENTION, title="B")
        eng.send(user_id="u2", notification_type=NotificationType.COMMENT, title="C")
        assert len(eng.list_notifications("u1")) == 2
        assert len(eng.list_notifications("u2")) == 1

    def test_list_notifications_filtered(self):
        eng = NotificationEngine()
        eng.send(user_id="u1", notification_type=NotificationType.COMMENT, title="A")
        n = eng.send(user_id="u1", notification_type=NotificationType.COMMENT, title="B")
        eng.mark_read("u1", n.id)
        unread = eng.list_notifications("u1", status=NotificationStatus.UNREAD)
        assert len(unread) == 1

    def test_unread_count(self):
        eng = NotificationEngine()
        eng.send(user_id="u1", notification_type=NotificationType.COMMENT, title="A")
        eng.send(user_id="u1", notification_type=NotificationType.COMMENT, title="B")
        assert eng.unread_count("u1") == 2

    def test_mark_read(self):
        eng = NotificationEngine()
        n = eng.send(user_id="u1", notification_type=NotificationType.COMMENT, title="A")
        assert eng.mark_read("u1", n.id)
        assert eng.unread_count("u1") == 0

    def test_mark_read_not_found(self):
        eng = NotificationEngine()
        assert not eng.mark_read("u1", "nonexistent")

    def test_mark_all_read(self):
        eng = NotificationEngine()
        eng.send(user_id="u1", notification_type=NotificationType.COMMENT, title="A")
        eng.send(user_id="u1", notification_type=NotificationType.COMMENT, title="B")
        count = eng.mark_all_read("u1")
        assert count == 2
        assert eng.unread_count("u1") == 0

    def test_archive(self):
        eng = NotificationEngine()
        n = eng.send(user_id="u1", notification_type=NotificationType.COMMENT, title="A")
        assert eng.archive("u1", n.id)

    def test_delete(self):
        eng = NotificationEngine()
        n = eng.send(user_id="u1", notification_type=NotificationType.COMMENT, title="A")
        assert eng.delete("u1", n.id)
        assert len(eng.list_notifications("u1")) == 0

    def test_delete_not_found(self):
        eng = NotificationEngine()
        assert not eng.delete("u1", "nope")


# ===================================================================
# 4. Activity feed
# ===================================================================

class TestActivityFeed:
    def test_record_entry(self):
        feed = ActivityFeed()
        e = feed.record(FeedEventType.COMMENT_ADDED, board_id="b1", user_id="u1",
                        summary="User commented")
        assert e.event_type == FeedEventType.COMMENT_ADDED

    def test_board_feed(self):
        feed = ActivityFeed()
        feed.record(FeedEventType.COMMENT_ADDED, board_id="b1", user_id="u1")
        feed.record(FeedEventType.ITEM_CREATED, board_id="b2", user_id="u1")
        assert len(feed.get_board_feed("b1")) == 1

    def test_user_feed(self):
        feed = ActivityFeed()
        feed.record(FeedEventType.COMMENT_ADDED, board_id="b1", user_id="u1")
        feed.record(FeedEventType.ITEM_CREATED, board_id="b1", user_id="u2")
        assert len(feed.get_user_feed("u1")) == 1

    def test_global_feed(self):
        feed = ActivityFeed()
        feed.record(FeedEventType.COMMENT_ADDED, board_id="b1")
        feed.record(FeedEventType.ITEM_CREATED, board_id="b2")
        assert len(feed.get_global_feed()) == 2

    def test_item_feed(self):
        feed = ActivityFeed()
        feed.record(FeedEventType.COMMENT_ADDED, item_id="i1")
        feed.record(FeedEventType.ITEM_UPDATED, item_id="i1")
        feed.record(FeedEventType.ITEM_CREATED, item_id="i2")
        assert len(feed.get_item_feed("i1")) == 2

    def test_feed_limit(self):
        feed = ActivityFeed()
        for i in range(10):
            feed.record(FeedEventType.COMMENT_ADDED, board_id="b1")
        assert len(feed.get_board_feed("b1", limit=5)) == 5

    def test_feed_filter_by_type(self):
        feed = ActivityFeed()
        feed.record(FeedEventType.COMMENT_ADDED, board_id="b1")
        feed.record(FeedEventType.ITEM_CREATED, board_id="b1")
        result = feed.get_board_feed("b1", event_type=FeedEventType.COMMENT_ADDED)
        assert len(result) == 1


# ===================================================================
# 5. Comment manager
# ===================================================================

class TestCommentManager:
    def test_add_comment(self):
        mgr = CommentManager()
        c = mgr.add_comment(CommentEntityType.ITEM, "i1",
                            author_id="u1", author_name="Alice",
                            body="Hello world")
        assert c.author_id == "u1"
        assert c.body == "Hello world"

    def test_add_comment_with_mention(self):
        mgr = CommentManager()
        c = mgr.add_comment(CommentEntityType.ITEM, "i1",
                            author_id="u1", author_name="Alice",
                            body="Hey @bob, check this")
        assert len(c.mentions) == 1
        assert c.mentions[0].target_id == "bob"
        # Notification should be sent to bob
        notifs = mgr.notifications.list_notifications("bob")
        assert len(notifs) == 1
        assert notifs[0].notification_type == NotificationType.MENTION

    def test_add_reply_notifies_parent_author(self):
        mgr = CommentManager()
        parent = mgr.add_comment(CommentEntityType.ITEM, "i1",
                                 author_id="u1", author_name="Alice",
                                 body="Original")
        mgr.add_comment(CommentEntityType.ITEM, "i1",
                        author_id="u2", author_name="Bob",
                        body="Reply", parent_id=parent.id)
        notifs = mgr.notifications.list_notifications("u1")
        assert any(n.notification_type == NotificationType.REPLY for n in notifs)

    def test_get_comment(self):
        mgr = CommentManager()
        c = mgr.add_comment(CommentEntityType.ITEM, "i1",
                            author_id="u1", body="Test")
        assert mgr.get_comment(c.id) is c
        assert mgr.get_comment("missing") is None

    def test_list_comments(self):
        mgr = CommentManager()
        mgr.add_comment(CommentEntityType.ITEM, "i1", author_id="u1", body="A")
        mgr.add_comment(CommentEntityType.ITEM, "i1", author_id="u2", body="B")
        mgr.add_comment(CommentEntityType.ITEM, "i2", author_id="u1", body="C")
        assert len(mgr.list_comments("i1")) == 2

    def test_edit_comment(self):
        mgr = CommentManager()
        c = mgr.add_comment(CommentEntityType.ITEM, "i1",
                            author_id="u1", body="Old")
        edited = mgr.edit_comment(c.id, body="New", editor_id="u1")
        assert edited.body == "New"
        assert edited.edited is True

    def test_edit_comment_permission(self):
        mgr = CommentManager()
        c = mgr.add_comment(CommentEntityType.ITEM, "i1",
                            author_id="u1", body="Old")
        with pytest.raises(PermissionError):
            mgr.edit_comment(c.id, body="Hacked", editor_id="u2")

    def test_edit_comment_not_found(self):
        mgr = CommentManager()
        with pytest.raises(KeyError):
            mgr.edit_comment("missing", body="X")

    def test_delete_comment(self):
        mgr = CommentManager()
        c = mgr.add_comment(CommentEntityType.ITEM, "i1",
                            author_id="u1", body="Delete me")
        assert mgr.delete_comment(c.id, deleter_id="u1")
        assert mgr.get_comment(c.id) is None

    def test_delete_comment_not_found(self):
        mgr = CommentManager()
        assert not mgr.delete_comment("missing")

    def test_delete_comment_permission(self):
        mgr = CommentManager()
        c = mgr.add_comment(CommentEntityType.ITEM, "i1",
                            author_id="u1", body="X")
        with pytest.raises(PermissionError):
            mgr.delete_comment(c.id, deleter_id="u2")

    def test_add_reaction(self):
        mgr = CommentManager()
        c = mgr.add_comment(CommentEntityType.ITEM, "i1",
                            author_id="u1", body="Nice")
        updated = mgr.add_reaction(c.id, "👍", "u2")
        assert "👍" in updated.reactions

    def test_remove_reaction(self):
        mgr = CommentManager()
        c = mgr.add_comment(CommentEntityType.ITEM, "i1",
                            author_id="u1", body="Nice")
        mgr.add_reaction(c.id, "👍", "u2")
        assert mgr.remove_reaction(c.id, "👍", "u2")

    def test_get_thread(self):
        mgr = CommentManager()
        parent = mgr.add_comment(CommentEntityType.ITEM, "i1",
                                 author_id="u1", body="Parent")
        mgr.add_comment(CommentEntityType.ITEM, "i1",
                        author_id="u2", body="Reply 1", parent_id=parent.id)
        mgr.add_comment(CommentEntityType.ITEM, "i1",
                        author_id="u3", body="Reply 2", parent_id=parent.id)
        thread = mgr.get_thread(parent.id)
        assert len(thread) == 2

    def test_activity_feed_recorded(self):
        mgr = CommentManager()
        mgr.add_comment(CommentEntityType.ITEM, "i1",
                        board_id="b1", author_id="u1", body="Test")
        feed = mgr.feed.get_board_feed("b1")
        assert len(feed) >= 1
        assert feed[0].event_type == FeedEventType.COMMENT_ADDED


# ===================================================================
# 6. API router
# ===================================================================

class TestAPIRouter:
    def test_create_collaboration_router(self):
        try:
            from collaboration.api import create_collaboration_router
            router = create_collaboration_router()
            assert router is not None
        except ImportError:
            pytest.skip("FastAPI not available")

    def test_router_with_custom_manager(self):
        try:
            from collaboration.api import create_collaboration_router
            mgr = CommentManager()
            router = create_collaboration_router(mgr)
            assert router is not None
        except ImportError:
            pytest.skip("FastAPI not available")
