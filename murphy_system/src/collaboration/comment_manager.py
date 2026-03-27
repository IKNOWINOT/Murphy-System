"""
Collaboration System – Comment Manager
========================================

Central façade for comment CRUD operations with @mention parsing,
notification dispatch, and activity feed recording.

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .activity_feed import ActivityFeed
from .mentions import UserResolver, get_default_resolver, parse_mentions
from .models import (
    Comment,
    CommentEntityType,
    FeedEventType,
    MentionType,
    NotificationType,
    _now,
)
from .notifications import NotificationEngine

logger = logging.getLogger(__name__)


class CommentManager:
    """Manages comments, integrating mentions, notifications, and activity feed.

    Parameters
    ----------
    notification_engine : NotificationEngine, optional
        Shared notification engine.  A new one is created if not supplied.
    activity_feed : ActivityFeed, optional
        Shared activity feed.  A new one is created if not supplied.
    resolver : UserResolver, optional
        User/team name resolver for @mentions.
    """

    def __init__(
        self,
        notification_engine: Optional[NotificationEngine] = None,
        activity_feed: Optional[ActivityFeed] = None,
        resolver: Optional[UserResolver] = None,
    ) -> None:
        self._comments: Dict[str, Comment] = {}
        self._entity_comments: Dict[str, List[str]] = {}  # entity_id → [comment_ids]
        self.notifications = notification_engine or NotificationEngine()
        self.feed = activity_feed or ActivityFeed()
        self._resolver = resolver or get_default_resolver()

    # -- Comment CRUD -------------------------------------------------------

    def add_comment(
        self,
        entity_type: CommentEntityType,
        entity_id: str,
        *,
        board_id: str = "",
        author_id: str = "",
        author_name: str = "",
        body: str = "",
        parent_id: str = "",
    ) -> Comment:
        """Create a comment, parse mentions, send notifications, record feed."""
        mentions = parse_mentions(body, self._resolver)

        comment = Comment(
            entity_type=entity_type,
            entity_id=entity_id,
            board_id=board_id,
            author_id=author_id,
            author_name=author_name,
            body=body,
            mentions=mentions,
            parent_id=parent_id,
        )
        self._comments[comment.id] = comment
        self._entity_comments.setdefault(entity_id, []).append(comment.id)

        # Send notifications for mentions
        for mention in mentions:
            if mention.mention_type == MentionType.USER:
                self.notifications.send(
                    user_id=mention.target_id,
                    notification_type=NotificationType.MENTION,
                    title=f"{author_name} mentioned you",
                    body=body[:200],
                    board_id=board_id,
                    entity_type=entity_type.value,
                    entity_id=entity_id,
                    triggered_by=author_id,
                )

        # If this is a reply, notify the parent comment author
        if parent_id and parent_id in self._comments:
            parent = self._comments[parent_id]
            if parent.author_id != author_id:
                self.notifications.send(
                    user_id=parent.author_id,
                    notification_type=NotificationType.REPLY,
                    title=f"{author_name} replied to your comment",
                    body=body[:200],
                    board_id=board_id,
                    entity_type=entity_type.value,
                    entity_id=entity_id,
                    triggered_by=author_id,
                )

        # Record in activity feed
        self.feed.record(
            FeedEventType.COMMENT_ADDED,
            board_id=board_id,
            item_id=entity_id if entity_type == CommentEntityType.ITEM else "",
            user_id=author_id,
            user_name=author_name,
            summary=f"{author_name} commented on {entity_type.value} {entity_id}",
            details={"comment_id": comment.id, "body_preview": body[:100]},
        )

        logger.info("Comment %s added by %s on %s %s",
                     comment.id, author_id, entity_type.value, entity_id)
        return comment

    def get_comment(self, comment_id: str) -> Optional[Comment]:
        return self._comments.get(comment_id)

    def list_comments(
        self,
        entity_id: str,
        *,
        limit: int = 50,
        include_replies: bool = True,
    ) -> List[Comment]:
        """Return comments for an entity, sorted by creation time."""
        comment_ids = self._entity_comments.get(entity_id, [])
        comments = [self._comments[cid] for cid in comment_ids if cid in self._comments]
        if not include_replies:
            comments = [c for c in comments if not c.parent_id]
        comments.sort(key=lambda c: c.created_at)
        return comments[:limit]

    def edit_comment(
        self,
        comment_id: str,
        *,
        body: str,
        editor_id: str = "",
    ) -> Comment:
        """Edit a comment's body and re-parse mentions."""
        comment = self._comments.get(comment_id)
        if comment is None:
            raise KeyError(f"Comment not found: {comment_id!r}")
        if editor_id and comment.author_id != editor_id:
            raise PermissionError("Only the author can edit a comment")

        comment.body = body
        comment.mentions = parse_mentions(body, self._resolver)
        comment.edited = True
        comment.updated_at = _now()

        self.feed.record(
            FeedEventType.COMMENT_EDITED,
            board_id=comment.board_id,
            item_id=comment.entity_id if comment.entity_type == CommentEntityType.ITEM else "",
            user_id=editor_id or comment.author_id,
            summary=f"Comment edited on {comment.entity_type.value} {comment.entity_id}",
        )
        return comment

    def delete_comment(self, comment_id: str, *, deleter_id: str = "") -> bool:
        """Delete a comment. Returns ``True`` if removed."""
        comment = self._comments.get(comment_id)
        if comment is None:
            return False
        if deleter_id and comment.author_id != deleter_id:
            raise PermissionError("Only the author can delete a comment")

        del self._comments[comment_id]
        entity_ids = self._entity_comments.get(comment.entity_id, [])
        if comment_id in entity_ids:
            entity_ids.remove(comment_id)

        self.feed.record(
            FeedEventType.COMMENT_DELETED,
            board_id=comment.board_id,
            user_id=deleter_id or comment.author_id,
            summary=f"Comment deleted on {comment.entity_type.value} {comment.entity_id}",
        )
        return True

    # -- Reactions -----------------------------------------------------------

    def add_reaction(self, comment_id: str, emoji: str, user_id: str) -> Comment:
        comment = self._comments.get(comment_id)
        if comment is None:
            raise KeyError(f"Comment not found: {comment_id!r}")
        comment.add_reaction(emoji, user_id)
        return comment

    def remove_reaction(self, comment_id: str, emoji: str, user_id: str) -> bool:
        comment = self._comments.get(comment_id)
        if comment is None:
            raise KeyError(f"Comment not found: {comment_id!r}")
        return comment.remove_reaction(emoji, user_id)

    # -- Thread helpers ------------------------------------------------------

    def get_thread(self, parent_comment_id: str) -> List[Comment]:
        """Return all replies to a comment, sorted chronologically."""
        replies = [
            c for c in self._comments.values()
            if c.parent_id == parent_comment_id
        ]
        replies.sort(key=lambda c: c.created_at)
        return replies
