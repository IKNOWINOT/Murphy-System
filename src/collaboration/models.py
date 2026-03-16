"""
Collaboration System – Data Models
====================================

Core data structures for the Real-Time Collaboration System
(Phase 2 of management systems parity).

Provides dataclass-based models for:
- Comments on items and boards
- @mentions with user resolution
- In-app notifications
- Activity feed entries

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations
import logging

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

_UTC = timezone.utc


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> str:
    return datetime.now(tz=_UTC).isoformat()


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class CommentEntityType(Enum):
    """Entity types that can receive comments."""
    ITEM = "item"
    BOARD = "board"
    UPDATE = "update"


class MentionType(Enum):
    """Types of @mentions."""
    USER = "user"
    TEAM = "team"
    EVERYONE = "everyone"


class NotificationType(Enum):
    """Notification categories."""
    COMMENT = "comment"
    MENTION = "mention"
    ASSIGNMENT = "assignment"
    STATUS_CHANGE = "status_change"
    DUE_DATE = "due_date"
    ITEM_UPDATE = "item_update"
    REPLY = "reply"


class NotificationStatus(Enum):
    """Read/unread state for notifications."""
    UNREAD = "unread"
    READ = "read"
    ARCHIVED = "archived"


class FeedEventType(Enum):
    """Types of events in the activity feed."""
    COMMENT_ADDED = "comment_added"
    COMMENT_EDITED = "comment_edited"
    COMMENT_DELETED = "comment_deleted"
    MENTION = "mention"
    ITEM_CREATED = "item_created"
    ITEM_UPDATED = "item_updated"
    ITEM_MOVED = "item_moved"
    STATUS_CHANGED = "status_changed"
    PERSON_ASSIGNED = "person_assigned"
    FILE_UPLOADED = "file_uploaded"
    COLUMN_CHANGED = "column_changed"


# ---------------------------------------------------------------------------
# Core data models
# ---------------------------------------------------------------------------

@dataclass
class Mention:
    """A parsed @mention within comment text."""
    id: str = field(default_factory=_new_id)
    mention_type: MentionType = MentionType.USER
    target_id: str = ""
    target_name: str = ""
    offset: int = 0
    length: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "mention_type": self.mention_type.value,
            "target_id": self.target_id,
            "target_name": self.target_name,
            "offset": self.offset,
            "length": self.length,
        }


@dataclass
class Comment:
    """A comment on an item or board."""
    id: str = field(default_factory=_new_id)
    entity_type: CommentEntityType = CommentEntityType.ITEM
    entity_id: str = ""
    board_id: str = ""
    author_id: str = ""
    author_name: str = ""
    body: str = ""
    mentions: List[Mention] = field(default_factory=list)
    parent_id: str = ""
    reactions: Dict[str, List[str]] = field(default_factory=dict)
    edited: bool = False
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def add_reaction(self, emoji: str, user_id: str) -> None:
        if emoji not in self.reactions:
            self.reactions[emoji] = []
        if user_id not in self.reactions[emoji]:
            self.reactions[emoji].append(user_id)

    def remove_reaction(self, emoji: str, user_id: str) -> bool:
        if emoji in self.reactions and user_id in self.reactions[emoji]:
            self.reactions[emoji].remove(user_id)
            if not self.reactions[emoji]:
                del self.reactions[emoji]
            return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "entity_type": self.entity_type.value,
            "entity_id": self.entity_id,
            "board_id": self.board_id,
            "author_id": self.author_id,
            "author_name": self.author_name,
            "body": self.body,
            "mentions": [m.to_dict() for m in self.mentions],
            "parent_id": self.parent_id,
            "reactions": self.reactions,
            "edited": self.edited,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class Notification:
    """An in-app notification for a user."""
    id: str = field(default_factory=_new_id)
    user_id: str = ""
    notification_type: NotificationType = NotificationType.COMMENT
    status: NotificationStatus = NotificationStatus.UNREAD
    title: str = ""
    body: str = ""
    board_id: str = ""
    entity_type: str = ""
    entity_id: str = ""
    triggered_by: str = ""
    created_at: str = field(default_factory=_now)
    read_at: Optional[str] = None

    def mark_read(self) -> None:
        self.status = NotificationStatus.READ
        self.read_at = _now()

    def mark_archived(self) -> None:
        self.status = NotificationStatus.ARCHIVED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "notification_type": self.notification_type.value,
            "status": self.status.value,
            "title": self.title,
            "body": self.body,
            "board_id": self.board_id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "triggered_by": self.triggered_by,
            "created_at": self.created_at,
            "read_at": self.read_at,
        }


@dataclass
class ActivityFeedEntry:
    """A single entry in the activity feed."""
    id: str = field(default_factory=_new_id)
    event_type: FeedEventType = FeedEventType.COMMENT_ADDED
    board_id: str = ""
    item_id: str = ""
    user_id: str = ""
    user_name: str = ""
    summary: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "event_type": self.event_type.value,
            "board_id": self.board_id,
            "item_id": self.item_id,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "summary": self.summary,
            "details": self.details,
            "created_at": self.created_at,
        }
