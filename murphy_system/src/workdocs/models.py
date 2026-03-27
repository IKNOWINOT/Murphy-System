"""
Workdocs – Data Models
=======================

Core data structures for the Collaborative Documents system
(Phase 5 of management systems parity).

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

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


# ---------------------------------------------------------------------------
# Document templates
# ---------------------------------------------------------------------------

@dataclass
class DocTemplate:
    """A reusable document template with pre-seeded blocks.

    Templates are named blueprints from which new documents can be
    instantiated via :meth:`DocManager.create_from_template`.
    """
    id: str = field(default_factory=_new_id)
    name: str = ""
    description: str = ""
    category: str = ""  # e.g. "meeting_notes", "project_brief", "retrospective"
    block_definitions: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "block_count": len(self.block_definitions),
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# Built-in template definitions
# ---------------------------------------------------------------------------

_BUILTIN_TEMPLATES: List[Dict[str, Any]] = [
    {
        "name": "Meeting Notes",
        "description": "Structured template for capturing meeting outcomes",
        "category": "meeting_notes",
        "block_definitions": [
            {"block_type": "heading", "content": "Meeting Notes", "metadata": {"level": 1}},
            {"block_type": "text", "content": "**Date:** "},
            {"block_type": "text", "content": "**Attendees:** "},
            {"block_type": "heading", "content": "Agenda", "metadata": {"level": 2}},
            {"block_type": "bullet_list", "content": "Agenda item 1"},
            {"block_type": "heading", "content": "Discussion", "metadata": {"level": 2}},
            {"block_type": "text", "content": ""},
            {"block_type": "heading", "content": "Action Items", "metadata": {"level": 2}},
            {"block_type": "checklist", "content": "Follow-up task"},
        ],
    },
    {
        "name": "Project Brief",
        "description": "One-page overview for a new project or initiative",
        "category": "project_brief",
        "block_definitions": [
            {"block_type": "heading", "content": "Project Brief", "metadata": {"level": 1}},
            {"block_type": "heading", "content": "Overview", "metadata": {"level": 2}},
            {"block_type": "text", "content": ""},
            {"block_type": "heading", "content": "Goals", "metadata": {"level": 2}},
            {"block_type": "bullet_list", "content": "Goal 1"},
            {"block_type": "heading", "content": "Scope", "metadata": {"level": 2}},
            {"block_type": "text", "content": ""},
            {"block_type": "heading", "content": "Timeline", "metadata": {"level": 2}},
            {"block_type": "table", "content": ""},
            {"block_type": "heading", "content": "Stakeholders", "metadata": {"level": 2}},
            {"block_type": "table", "content": ""},
        ],
    },
    {
        "name": "Sprint Retrospective",
        "description": "What went well, what to improve, action items",
        "category": "retrospective",
        "block_definitions": [
            {"block_type": "heading", "content": "Sprint Retrospective", "metadata": {"level": 1}},
            {"block_type": "heading", "content": "What Went Well", "metadata": {"level": 2}},
            {"block_type": "bullet_list", "content": ""},
            {"block_type": "heading", "content": "What Could Be Improved", "metadata": {"level": 2}},
            {"block_type": "bullet_list", "content": ""},
            {"block_type": "heading", "content": "Action Items", "metadata": {"level": 2}},
            {"block_type": "checklist", "content": ""},
        ],
    },
    {
        "name": "Technical Spec",
        "description": "Engineering specification with requirements, design, and API contracts",
        "category": "technical_spec",
        "block_definitions": [
            {"block_type": "heading", "content": "Technical Specification", "metadata": {"level": 1}},
            {"block_type": "heading", "content": "Problem Statement", "metadata": {"level": 2}},
            {"block_type": "text", "content": ""},
            {"block_type": "heading", "content": "Proposed Solution", "metadata": {"level": 2}},
            {"block_type": "text", "content": ""},
            {"block_type": "heading", "content": "API Design", "metadata": {"level": 2}},
            {"block_type": "code", "content": "", "metadata": {"language": "json"}},
            {"block_type": "heading", "content": "Open Questions", "metadata": {"level": 2}},
            {"block_type": "numbered_list", "content": ""},
        ],
    },
]
