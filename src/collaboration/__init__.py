"""
Collaboration System – Real-Time Collaboration
================================================

Phase 2 of management systems feature parity for the Murphy System.

Provides a complete collaboration layer including:

- **Comments** – CRUD on items and boards with threaded replies
- **@Mentions** – user / team / @everyone parsing with pluggable resolver
- **Notifications** – in-app notification engine with read/archive
- **Activity Feed** – board-level, item-level, user-level, and global feeds
- **Reactions** – emoji reactions on comments

Quick start::

    from collaboration import CommentManager, CommentEntityType

    mgr = CommentManager()
    comment = mgr.add_comment(
        CommentEntityType.ITEM, "item123",
        board_id="board1",
        author_id="u1", author_name="Alice",
        body="Hey @bob, can you review this?",
    )
    # comment.mentions[0].target_id == "bob"

Copyright 2024 Inoni LLC – BSL-1.1
"""

__version__ = "0.1.0"
__codename__ = "Collab"

# -- Models -----------------------------------------------------------------
# -- Activity feed ----------------------------------------------------------
from .activity_feed import ActivityFeed

# -- Comment manager --------------------------------------------------------
from .comment_manager import CommentManager

# -- Mentions ---------------------------------------------------------------
from .mentions import (
    UserResolver,
    get_default_resolver,
    parse_mentions,
)
from .models import (
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

# -- Notifications ----------------------------------------------------------
from .notifications import NotificationEngine

# -- API (optional – requires fastapi) -------------------------------------
try:
    from .api import create_collaboration_router
except Exception as exc:  # pragma: no cover
    create_collaboration_router = None  # type: ignore[assignment]

__all__ = [
    # Models
    "ActivityFeedEntry",
    "Comment",
    "CommentEntityType",
    "FeedEventType",
    "Mention",
    "MentionType",
    "Notification",
    "NotificationStatus",
    "NotificationType",
    # Mentions
    "UserResolver",
    "get_default_resolver",
    "parse_mentions",
    # Notifications
    "NotificationEngine",
    # Activity feed
    "ActivityFeed",
    # Manager
    "CommentManager",
    # API
    "create_collaboration_router",
]
