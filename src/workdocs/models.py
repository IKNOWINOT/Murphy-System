"""
Workdocs – Data Models
=======================

Core data structures for the Collaborative Documents system
(Phase 5 of management systems parity).

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

class BlockType(Enum):
    """Supported block types within a document."""
    TEXT = "text"
    HEADING = "heading"
    BULLET_LIST = "bullet_list"
    NUMBERED_LIST = "numbered_list"
    CHECKLIST = "checklist"
    CODE = "code"
    QUOTE = "quote"
    DIVIDER = "divider"
    IMAGE = "image"
    TABLE = "table"
    BOARD_EMBED = "board_embed"


class DocPermission(Enum):
    """Document sharing levels."""
    PRIVATE = "private"
    VIEW = "view"
    COMMENT = "comment"
    EDIT = "edit"


class DocStatus(Enum):
    """Document lifecycle status."""
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


# ---------------------------------------------------------------------------
# Core data models
# ---------------------------------------------------------------------------

@dataclass
class Block:
    """A single content block within a document."""
    id: str = field(default_factory=_new_id)
    block_type: BlockType = BlockType.TEXT
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    indent_level: int = 0
    checked: bool = False  # for CHECKLIST blocks

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "block_type": self.block_type.value,
            "content": self.content,
            "metadata": self.metadata,
            "indent_level": self.indent_level,
            "checked": self.checked,
        }


@dataclass
class DocVersion:
    """A snapshot of a document at a point in time."""
    id: str = field(default_factory=_new_id)
    version_number: int = 1
    blocks_snapshot: List[Dict[str, Any]] = field(default_factory=list)
    editor_id: str = ""
    summary: str = ""
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "version_number": self.version_number,
            "blocks_snapshot": self.blocks_snapshot,
            "editor_id": self.editor_id,
            "summary": self.summary,
            "created_at": self.created_at,
        }


@dataclass
class Document:
    """A collaborative document (Workdoc)."""
    id: str = field(default_factory=_new_id)
    title: str = ""
    owner_id: str = ""
    board_id: str = ""
    status: DocStatus = DocStatus.DRAFT
    permission: DocPermission = DocPermission.PRIVATE
    blocks: List[Block] = field(default_factory=list)
    collaborator_ids: List[str] = field(default_factory=list)
    versions: List[DocVersion] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "owner_id": self.owner_id,
            "board_id": self.board_id,
            "status": self.status.value,
            "permission": self.permission.value,
            "blocks": [b.to_dict() for b in self.blocks],
            "collaborator_ids": self.collaborator_ids,
            "version_count": len(self.versions),
            "tags": self.tags,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
