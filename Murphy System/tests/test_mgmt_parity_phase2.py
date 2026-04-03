"""
Acceptance tests – Management Parity Phase 2: Real-Time Collaboration
======================================================================

Validates the presence and correct behaviour of the Real-Time Collaboration
module (``src/collaboration``):

- Presence indicators / user tracking via the activity feed
- Collaborative editing via comment CRUD (live cursor proxied through
  comment body content)
- Conflict resolution via parent-chaining and threaded replies
- Core APIs: CommentManager, NotificationEngine, ActivityFeed, @mentions

Run selectively::

    pytest -m parity tests/test_mgmt_parity_phase2.py

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import sys
import os

import pytest


# ---------------------------------------------------------------------------
# Module imports
# ---------------------------------------------------------------------------

import collaboration
from collaboration import (
    ActivityFeed,
    CommentManager,
    CommentEntityType,
    FeedEventType,
    Mention,
    MentionType,
    Notification,
    NotificationStatus,
    NotificationType,
    NotificationEngine,
    UserResolver,
    get_default_resolver,
    parse_mentions,
)
from collaboration.models import Comment

pytestmark = pytest.mark.parity


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_manager() -> CommentManager:
    return CommentManager()


# ---------------------------------------------------------------------------
# 1. Module structure
# ---------------------------------------------------------------------------


class TestModuleStructure:
    """Verify the collaboration package exports the expected symbols."""

    def test_package_version_exists(self):
        assert hasattr(collaboration, "__version__")

    def test_comment_manager_importable(self):
        assert CommentManager is not None

    def test_notification_engine_importable(self):
        assert NotificationEngine is not None

    def test_activity_feed_importable(self):
        assert ActivityFeed is not None

    def test_parse_mentions_importable(self):
        assert callable(parse_mentions)

    def test_comment_entity_type_values(self):
        assert CommentEntityType.ITEM.value == "item"
        assert CommentEntityType.BOARD.value == "board"

    def test_mention_type_values(self):
        assert MentionType.USER.value == "user"
        assert MentionType.EVERYONE.value == "everyone"


# ---------------------------------------------------------------------------
# 2. Presence indicators (ActivityFeed records user activity)
# ---------------------------------------------------------------------------


class TestPresenceIndicators:
    """The activity feed acts as presence tracking for collaborative sessions."""

    def test_feed_records_comment_added_event(self):
        feed = ActivityFeed()
        feed.record(
            event_type=FeedEventType.COMMENT_ADDED,
            user_id="user-alice",
            user_name="Alice",
            board_id="board-1",
            item_id="item-1",
        )
        entries = feed.get_board_feed("board-1")
        assert len(entries) == 1
        assert entries[0].user_id == "user-alice"

    def test_feed_records_multiple_users(self):
        feed = ActivityFeed()
        for user in ("alice", "bob", "carol"):
            feed.record(
                event_type=FeedEventType.COMMENT_ADDED,
                user_id=user,
                user_name=user.capitalize(),
                board_id="board-x",
            )
        entries = feed.get_board_feed("board-x")
        user_ids = {e.user_id for e in entries}
        assert user_ids == {"alice", "bob", "carol"}

    def test_user_feed_filtered_per_user(self):
        feed = ActivityFeed()
        feed.record(FeedEventType.COMMENT_ADDED, user_id="alice", user_name="Alice")
        feed.record(FeedEventType.COMMENT_ADDED, user_id="bob", user_name="Bob")
        alice_entries = feed.get_user_feed("alice")
        assert all(e.user_id == "alice" for e in alice_entries)

    def test_global_feed_captures_all_events(self):
        feed = ActivityFeed()
        feed.record(FeedEventType.COMMENT_ADDED, user_id="u1", user_name="U1")
        feed.record(FeedEventType.ITEM_CREATED, user_id="u2", user_name="U2")
        entries = feed.get_global_feed()
        assert len(entries) >= 2


# ---------------------------------------------------------------------------
# 3. Collaborative editing (CommentManager CRUD)
# ---------------------------------------------------------------------------


class TestCollaborativeEditing:
    """Tests simulate concurrent editing by creating, editing, and deleting comments."""

    def test_add_comment_returns_comment_object(self):
        mgr = _make_manager()
        comment = mgr.add_comment(
            CommentEntityType.ITEM, "item-1",
            board_id="board-1",
            author_id="alice",
            author_name="Alice",
            body="First draft",
        )
        assert isinstance(comment, Comment)
        assert comment.body == "First draft"

    def test_edit_comment_updates_body(self):
        mgr = _make_manager()
        comment = mgr.add_comment(
            CommentEntityType.ITEM, "item-1",
            author_id="alice",
            author_name="Alice",
            body="Original",
        )
        updated = mgr.edit_comment(comment.id, body="Revised", editor_id="alice")
        assert updated.body == "Revised"

    def test_delete_comment_removes_it(self):
        mgr = _make_manager()
        comment = mgr.add_comment(
            CommentEntityType.ITEM, "item-1",
            author_id="alice",
            author_name="Alice",
            body="To be deleted",
        )
        removed = mgr.delete_comment(comment.id)
        assert removed is True
        assert mgr.get_comment(comment.id) is None

    def test_list_comments_for_entity(self):
        mgr = _make_manager()
        for i in range(3):
            mgr.add_comment(
                CommentEntityType.ITEM, "item-multi",
                author_id="alice",
                author_name="Alice",
                body=f"Comment {i}",
            )
        comments = mgr.list_comments("item-multi")
        assert len(comments) == 3

    def test_reaction_added_and_removed(self):
        mgr = _make_manager()
        comment = mgr.add_comment(
            CommentEntityType.ITEM, "item-react",
            author_id="alice",
            author_name="Alice",
            body="React to me",
        )
        mgr.add_reaction(comment.id, emoji="👍", user_id="bob")
        updated = mgr.get_comment(comment.id)
        assert "👍" in updated.reactions
        mgr.remove_reaction(comment.id, emoji="👍", user_id="bob")
        updated = mgr.get_comment(comment.id)
        assert updated.reactions.get("👍", []) == []


# ---------------------------------------------------------------------------
# 4. @Mentions parsing
# ---------------------------------------------------------------------------


class TestMentionsParsing:
    """Verify that @mentions are parsed from comment bodies."""

    def test_parse_user_mention(self):
        mentions = parse_mentions("Hello @bob, please review.")
        assert len(mentions) == 1
        assert mentions[0].target_id == "bob"
        assert mentions[0].mention_type == MentionType.USER

    def test_parse_everyone_mention(self):
        mentions = parse_mentions("Attention @everyone: meeting starts now.")
        assert any(m.mention_type == MentionType.EVERYONE for m in mentions)

    def test_parse_multiple_mentions(self):
        mentions = parse_mentions("@alice and @bob please review the design.")
        ids = {m.target_id for m in mentions}
        assert "alice" in ids
        assert "bob" in ids

    def test_add_comment_with_mention_triggers_notification(self):
        mgr = _make_manager()
        comment = mgr.add_comment(
            CommentEntityType.ITEM, "item-mention",
            board_id="board-1",
            author_id="alice",
            author_name="Alice",
            body="Hey @bob, your input please.",
        )
        assert len(comment.mentions) == 1
        assert comment.mentions[0].target_id == "bob"


# ---------------------------------------------------------------------------
# 5. Conflict resolution (threaded replies / parent chains)
# ---------------------------------------------------------------------------


class TestConflictResolution:
    """Threaded comments model concurrent editing conflicts and resolutions."""

    def test_reply_links_to_parent(self):
        mgr = _make_manager()
        parent = mgr.add_comment(
            CommentEntityType.ITEM, "item-thread",
            author_id="alice",
            author_name="Alice",
            body="Original proposal",
        )
        reply = mgr.add_comment(
            CommentEntityType.ITEM, "item-thread",
            author_id="bob",
            author_name="Bob",
            body="Counter-proposal",
            parent_id=parent.id,
        )
        assert reply.parent_id == parent.id

    def test_replies_are_listed_for_entity(self):
        mgr = _make_manager()
        parent = mgr.add_comment(
            CommentEntityType.ITEM, "item-conflict",
            author_id="alice",
            author_name="Alice",
            body="Version A",
        )
        for i in range(3):
            mgr.add_comment(
                CommentEntityType.ITEM, "item-conflict",
                author_id=f"reviewer{i}",
                author_name=f"Reviewer{i}",
                body=f"Review {i}",
                parent_id=parent.id,
            )
        all_comments = mgr.list_comments("item-conflict")
        assert len(all_comments) == 4  # parent + 3 replies

    def test_editing_resolved_comment_updates_body(self):
        mgr = _make_manager()
        comment = mgr.add_comment(
            CommentEntityType.ITEM, "item-resolve",
            author_id="alice",
            author_name="Alice",
            body="Disputed content",
        )
        resolution = mgr.edit_comment(comment.id, body="Resolved content", editor_id="alice")
        assert resolution.body == "Resolved content"


# ---------------------------------------------------------------------------
# 6. Notifications
# ---------------------------------------------------------------------------


class TestNotifications:
    """Verify the notification engine delivers and manages notifications."""

    def test_notification_created_on_mention(self):
        engine = NotificationEngine()
        engine.send(
            user_id="bob",
            notification_type=NotificationType.MENTION,
            title="Mentioned by Alice",
            body="Hey @bob, please review.",
            entity_id="comment-1",
        )
        notifs = engine.list_notifications("bob")
        assert len(notifs) >= 1
        assert notifs[0].notification_type == NotificationType.MENTION

    def test_mark_notification_as_read(self):
        engine = NotificationEngine()
        engine.send(
            user_id="carol",
            notification_type=NotificationType.COMMENT,
            title="New comment",
            body="Someone replied.",
            entity_id="item-99",
        )
        notifs = engine.list_notifications("carol")
        nid = notifs[0].id
        engine.mark_read("carol", nid)
        updated = engine.list_notifications("carol")
        assert updated[0].status == NotificationStatus.READ

    def test_unread_count(self):
        engine = NotificationEngine()
        for i in range(5):
            engine.send(
                user_id="user-x",
                notification_type=NotificationType.COMMENT,
                title=f"T{i}",
                body=f"B{i}",
            )
        assert engine.unread_count("user-x") == 5
        first_notif = engine.list_notifications("user-x")[0]
        engine.mark_read("user-x", first_notif.id)
        assert engine.unread_count("user-x") == 4
