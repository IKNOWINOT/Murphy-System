"""
Management Systems – Document Manager
=====================================

Workdoc management linked to boards and items.

Provides:
- Document types: meeting notes, specs, runbooks, retrospectives
- Template-based document creation
- Document versioning and history
- Linking documents to board items (bidirectional)
- Collaborative editing markers (who is editing)
- Document search across workspaces
- Matrix message → document append functionality

Integration points:
    - Documents link to :class:`~board_engine.BoardItem` by ID
    - Document events published via ``event_bridge.py`` (PR 2)
    - Content appended from Matrix messages via ``matrix_event_handler.py`` (PR 3)

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_UTC = timezone.utc

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_DOC_CONTENT_BYTES: int = 512 * 1024   # 512 KB per document
MAX_VERSION_HISTORY: int = 100
DEFAULT_DOC_TYPE_ICON: str = "📄"

DOC_TYPE_ICONS: Dict[str, str] = {
    "meeting_notes": "📝",
    "spec": "📐",
    "runbook": "📖",
    "retrospective": "🔄",
    "proposal": "💡",
    "adr": "🏗️",
    "postmortem": "🔍",
    "changelog": "📋",
    "readme": "ℹ️",
    "general": "📄",
}


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class DocType(Enum):
    """Document type categories."""

    MEETING_NOTES = "meeting_notes"
    SPEC = "spec"
    RUNBOOK = "runbook"
    RETROSPECTIVE = "retrospective"
    PROPOSAL = "proposal"
    ADR = "adr"              # Architecture Decision Record
    POSTMORTEM = "postmortem"
    CHANGELOG = "changelog"
    README = "readme"
    GENERAL = "general"


class DocStatus(Enum):
    """Lifecycle status of a document."""

    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    ARCHIVED = "archived"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _uid() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> str:
    return datetime.now(tz=_UTC).isoformat()


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class DocVersion:
    """An immutable snapshot of a document at a point in time.

    Args:
        content: Full document content at this version.
        edited_by: Matrix user who created this version.
        version_number: Monotonically increasing version integer.
        change_summary: Short description of what changed.
    """

    content: str
    edited_by: str
    version_number: int
    change_summary: str = ""
    id: str = field(default_factory=_uid)
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "edited_by": self.edited_by,
            "version_number": self.version_number,
            "change_summary": self.change_summary,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocVersion":
        obj = cls(
            content=data.get("content", ""),
            edited_by=data.get("edited_by", ""),
            version_number=data.get("version_number", 1),
            change_summary=data.get("change_summary", ""),
        )
        obj.id = data.get("id", obj.id)
        obj.created_at = data.get("created_at", obj.created_at)
        return obj


@dataclass
class DocTemplate:
    """A reusable document template.

    Args:
        name: Display name.
        doc_type: Document type this template covers.
        content_template: Markdown content with ``{placeholder}`` variables.
        description: Brief description.
    """

    name: str
    doc_type: DocType
    content_template: str = ""
    description: str = ""
    id: str = field(default_factory=_uid)

    def render(self, variables: Optional[Dict[str, str]] = None) -> str:
        """Render the template by substituting *variables*.

        Args:
            variables: Dict of placeholder → value pairs.

        Returns:
            Rendered Markdown string.
        """
        content = self.content_template
        for key, value in (variables or {}).items():
            content = content.replace(f"{{{key}}}", value)
        return content

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "doc_type": self.doc_type.value,
            "content_template": self.content_template,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocTemplate":
        obj = cls(
            name=data["name"],
            doc_type=DocType(data.get("doc_type", "general")),
            content_template=data.get("content_template", ""),
            description=data.get("description", ""),
        )
        obj.id = data.get("id", obj.id)
        return obj


@dataclass
class WorkDoc:
    """A versioned document linked to boards and items.

    Args:
        title: Document title.
        doc_type: Category.
        content: Current content (Markdown).
        workspace_id: Parent workspace.
        board_ids: Boards this document is linked to.
        item_ids: Board items this document is linked to.
        owner_id: Matrix user who created the document.
        editing_by: Set of Matrix user IDs currently editing.
    """

    title: str
    doc_type: DocType = DocType.GENERAL
    content: str = ""
    workspace_id: str = ""
    board_ids: List[str] = field(default_factory=list)
    item_ids: List[str] = field(default_factory=list)
    owner_id: str = ""
    status: DocStatus = DocStatus.DRAFT
    editing_by: List[str] = field(default_factory=list)
    version_history: List[DocVersion] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    id: str = field(default_factory=_uid)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    @property
    def current_version(self) -> int:
        return len(self.version_history)

    @property
    def type_icon(self) -> str:
        return DOC_TYPE_ICONS.get(self.doc_type.value, DEFAULT_DOC_TYPE_ICON)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "doc_type": self.doc_type.value,
            "content": self.content,
            "workspace_id": self.workspace_id,
            "board_ids": self.board_ids,
            "item_ids": self.item_ids,
            "owner_id": self.owner_id,
            "status": self.status.value,
            "editing_by": self.editing_by,
            "version_history": [v.to_dict() for v in self.version_history[-MAX_VERSION_HISTORY:]],
            "tags": self.tags,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkDoc":
        obj = cls(
            title=data["title"],
            doc_type=DocType(data.get("doc_type", "general")),
            content=data.get("content", ""),
            workspace_id=data.get("workspace_id", ""),
            board_ids=data.get("board_ids", []),
            item_ids=data.get("item_ids", []),
            owner_id=data.get("owner_id", ""),
            status=DocStatus(data.get("status", "draft")),
            editing_by=data.get("editing_by", []),
            tags=data.get("tags", []),
        )
        obj.id = data.get("id", obj.id)
        obj.created_at = data.get("created_at", obj.created_at)
        obj.updated_at = data.get("updated_at", obj.updated_at)
        obj.version_history = [
            DocVersion.from_dict(v) for v in data.get("version_history", [])
        ]
        return obj


# ---------------------------------------------------------------------------
# Built-in templates
# ---------------------------------------------------------------------------

_DOC_TEMPLATES: Dict[DocType, DocTemplate] = {
    DocType.MEETING_NOTES: DocTemplate(
        name="Meeting Notes",
        doc_type=DocType.MEETING_NOTES,
        description="Structured notes for team meetings.",
        content_template=(
            "# Meeting Notes – {title}\n\n"
            "**Date:** {date}\n"
            "**Attendees:** {attendees}\n"
            "**Facilitator:** {facilitator}\n\n"
            "## Agenda\n\n1. {agenda_item_1}\n\n"
            "## Notes\n\n\n"
            "## Action Items\n\n| Owner | Action | Due Date |\n|-------|--------|----------|\n| | | |\n\n"
            "## Decisions Made\n\n- \n\n"
            "## Next Meeting\n\n**Date:** {next_meeting_date}\n"
        ),
    ),
    DocType.RUNBOOK: DocTemplate(
        name="Runbook",
        doc_type=DocType.RUNBOOK,
        description="Operational runbook for a system or process.",
        content_template=(
            "# Runbook – {title}\n\n"
            "**Module:** {module}\n"
            "**Owner:** {owner}\n"
            "**Last Updated:** {date}\n\n"
            "## Overview\n\n{overview}\n\n"
            "## Prerequisites\n\n- \n\n"
            "## Procedure\n\n### Step 1: {step_1_title}\n\n```bash\n{step_1_command}\n```\n\n"
            "## Troubleshooting\n\n| Symptom | Cause | Resolution |\n|---------|-------|------------|\n| | | |\n\n"
            "## Escalation\n\nIf unable to resolve, escalate to: {escalation_contact}\n"
        ),
    ),
    DocType.RETROSPECTIVE: DocTemplate(
        name="Sprint Retrospective",
        doc_type=DocType.RETROSPECTIVE,
        description="Sprint retrospective template.",
        content_template=(
            "# Sprint Retrospective – {sprint_name}\n\n"
            "**Date:** {date}\n"
            "**Team:** {team}\n\n"
            "## What Went Well 🎉\n\n- \n\n"
            "## What Could Be Improved 🔧\n\n- \n\n"
            "## Action Items 🎯\n\n| Owner | Action | Due Date |\n|-------|--------|----------|\n| | | |\n\n"
            "## Team Health 📊\n\nMorale: /10\n"
        ),
    ),
    DocType.POSTMORTEM: DocTemplate(
        name="Incident Postmortem",
        doc_type=DocType.POSTMORTEM,
        description="Post-incident analysis document.",
        content_template=(
            "# Postmortem – {incident_title}\n\n"
            "**Incident Date:** {incident_date}\n"
            "**Severity:** {severity}\n"
            "**Author:** {author}\n\n"
            "## Executive Summary\n\n{summary}\n\n"
            "## Timeline\n\n| Time | Event |\n|------|-------|\n| {time_1} | {event_1} |\n\n"
            "## Root Cause\n\n{root_cause}\n\n"
            "## Impact\n\n- **Duration:** {duration}\n- **Affected Users:** {affected_users}\n\n"
            "## Lessons Learned\n\n- \n\n"
            "## Action Items\n\n| Owner | Action | Due Date | Priority |\n|-------|--------|----------|----------|\n| | | | |\n"
        ),
    ),
    DocType.SPEC: DocTemplate(
        name="Technical Specification",
        doc_type=DocType.SPEC,
        description="Technical design specification.",
        content_template=(
            "# Technical Specification – {title}\n\n"
            "**Author:** {author}\n"
            "**Status:** Draft\n"
            "**Date:** {date}\n\n"
            "## Overview\n\n{overview}\n\n"
            "## Goals\n\n- \n\n"
            "## Non-Goals\n\n- \n\n"
            "## Design\n\n### Architecture\n\n{architecture}\n\n"
            "## API Design\n\n```\n{api_design}\n```\n\n"
            "## Security Considerations\n\n- \n\n"
            "## Open Questions\n\n- [ ] \n"
        ),
    ),
}


# ---------------------------------------------------------------------------
# Document Manager
# ---------------------------------------------------------------------------


class DocManager:
    """Manages workdocs linked to Murphy Monday boards and items.

    Provides full document lifecycle management: creation from templates,
    versioning, linking to board items, collaborative editing markers,
    and full-text search.

    Example::

        mgr = DocManager()
        doc = mgr.create_doc(
            "Sprint 12 Retro",
            DocType.RETROSPECTIVE,
            owner_id="@alice:example.com",
        )
        mgr.update_content(doc.id, "# Sprint 12 Retro\\n...", "@alice:example.com")
        mgr.link_to_item(doc.id, "board-item-123")
        results = mgr.search("retro")
    """

    def __init__(self) -> None:
        self._docs: Dict[str, WorkDoc] = {}
        self._templates: Dict[str, DocTemplate] = {}
        # Load built-in templates
        for tpl in _DOC_TEMPLATES.values():
            self._templates[tpl.id] = tpl

    # -- Document CRUD ------------------------------------------------------

    def create_doc(
        self,
        title: str,
        doc_type: DocType = DocType.GENERAL,
        *,
        content: str = "",
        workspace_id: str = "",
        owner_id: str = "",
        tags: Optional[List[str]] = None,
        from_template: Optional[DocType] = None,
        template_variables: Optional[Dict[str, str]] = None,
    ) -> WorkDoc:
        """Create a new document.

        Args:
            title: Document title.
            doc_type: Category.
            content: Initial content (Markdown).
            workspace_id: Parent workspace.
            owner_id: Creator's Matrix user ID.
            tags: Optional tag list.
            from_template: Pre-populate from a built-in template.
            template_variables: Variables substituted into the template.

        Returns:
            The new :class:`WorkDoc`.
        """
        if from_template is not None:
            tpl = _DOC_TEMPLATES.get(from_template)
            if tpl is not None:
                content = tpl.render(template_variables or {"title": title})

        doc = WorkDoc(
            title=title,
            doc_type=doc_type,
            content=content,
            workspace_id=workspace_id,
            owner_id=owner_id,
            tags=tags or [],
        )
        # Save initial version
        if content:
            self._save_version(doc, owner_id, "Initial content")

        self._docs[doc.id] = doc
        logger.info("Document created: %s (%s)", title, doc.id)
        return doc

    def get_doc(self, doc_id: str) -> Optional[WorkDoc]:
        return self._docs.get(doc_id)

    def list_docs(
        self,
        *,
        workspace_id: str = "",
        doc_type: Optional[DocType] = None,
        status: Optional[DocStatus] = None,
        tag: str = "",
    ) -> List[WorkDoc]:
        """List documents with optional filters.

        Args:
            workspace_id: Filter to a workspace.
            doc_type: Filter by type.
            status: Filter by lifecycle status.
            tag: Filter by tag.

        Returns:
            Sorted list of matching documents.
        """
        docs = list(self._docs.values())
        if workspace_id:
            docs = [d for d in docs if d.workspace_id == workspace_id]
        if doc_type is not None:
            docs = [d for d in docs if d.doc_type == doc_type]
        if status is not None:
            docs = [d for d in docs if d.status == status]
        if tag:
            docs = [d for d in docs if tag in d.tags]
        return sorted(docs, key=lambda d: d.updated_at, reverse=True)

    def delete_doc(self, doc_id: str) -> bool:
        if doc_id in self._docs:
            del self._docs[doc_id]
            return True
        return False

    # -- Content editing ----------------------------------------------------

    def update_content(
        self,
        doc_id: str,
        new_content: str,
        edited_by: str,
        *,
        change_summary: str = "",
    ) -> Optional[WorkDoc]:
        """Update a document's content and save a new version.

        Args:
            doc_id: Target document.
            new_content: Replacement content.
            edited_by: Matrix user making the change.
            change_summary: Brief description of the change.

        Returns:
            Updated document or *None* if not found.
        """
        doc = self._docs.get(doc_id)
        if doc is None:
            return None

        if len(new_content.encode()) > MAX_DOC_CONTENT_BYTES:
            raise ValueError(
                f"Document content exceeds maximum size ({MAX_DOC_CONTENT_BYTES // 1024} KB)"
            )

        doc.content = new_content
        doc.updated_at = _now()
        self._save_version(doc, edited_by, change_summary or "Content update")
        return doc

    def append_message(
        self,
        doc_id: str,
        message: str,
        sender: str,
        *,
        heading: Optional[str] = None,
    ) -> Optional[WorkDoc]:
        """Append a Matrix message to a document.

        Useful for capturing chat discussions directly into runbooks or
        meeting notes.

        Args:
            doc_id: Target document.
            message: Message content.
            sender: Matrix user ID of the sender.
            heading: Optional section heading to prepend.

        Returns:
            Updated document or *None* if not found.
        """
        doc = self._docs.get(doc_id)
        if doc is None:
            return None

        ts = datetime.now(tz=_UTC).strftime("%Y-%m-%d %H:%M UTC")
        block = f"\n\n---\n**{sender}** _{ts}_"
        if heading:
            block = f"\n\n## {heading}\n\n**{sender}** _{ts}_"
        block += f"\n\n{message}"

        new_content = doc.content + block
        return self.update_content(
            doc_id,
            new_content,
            sender,
            change_summary=f"Appended message from {sender}",
        )

    # -- Collaborative editing markers -------------------------------------

    def start_editing(self, doc_id: str, user_id: str) -> bool:
        """Mark a user as actively editing a document."""
        doc = self._docs.get(doc_id)
        if doc is None:
            return False
        if user_id not in doc.editing_by:
            doc.editing_by.append(user_id)
        return True

    def stop_editing(self, doc_id: str, user_id: str) -> bool:
        """Remove a user's editing marker."""
        doc = self._docs.get(doc_id)
        if doc is None:
            return False
        if user_id in doc.editing_by:
            doc.editing_by.remove(user_id)
        return True

    # -- Linking ------------------------------------------------------------

    def link_to_board(self, doc_id: str, board_id: str) -> bool:
        """Associate a document with a board."""
        doc = self._docs.get(doc_id)
        if doc is None:
            return False
        if board_id not in doc.board_ids:
            doc.board_ids.append(board_id)
            doc.updated_at = _now()
        return True

    def link_to_item(self, doc_id: str, item_id: str) -> bool:
        """Associate a document with a board item."""
        doc = self._docs.get(doc_id)
        if doc is None:
            return False
        if item_id not in doc.item_ids:
            doc.item_ids.append(item_id)
            doc.updated_at = _now()
        return True

    def get_docs_for_item(self, item_id: str) -> List[WorkDoc]:
        """Return all documents linked to a board item."""
        return [d for d in self._docs.values() if item_id in d.item_ids]

    def get_docs_for_board(self, board_id: str) -> List[WorkDoc]:
        """Return all documents linked to a board."""
        return [d for d in self._docs.values() if board_id in d.board_ids]

    # -- Versioning ---------------------------------------------------------

    def get_version_history(
        self, doc_id: str, limit: int = 20
    ) -> List[DocVersion]:
        """Return the version history for a document (newest first).

        Args:
            doc_id: Target document.
            limit: Maximum versions to return.

        Returns:
            List of :class:`DocVersion` entries.
        """
        doc = self._docs.get(doc_id)
        if doc is None:
            return []
        return list(reversed(doc.version_history[-limit:]))

    def restore_version(
        self,
        doc_id: str,
        version_number: int,
        restored_by: str,
    ) -> Optional[WorkDoc]:
        """Restore a document to a previous version.

        Args:
            doc_id: Target document.
            version_number: Version to restore to.
            restored_by: Matrix user making the restore.

        Returns:
            Updated document or *None* if not found.
        """
        doc = self._docs.get(doc_id)
        if doc is None:
            return None
        version = next(
            (v for v in doc.version_history if v.version_number == version_number),
            None,
        )
        if version is None:
            return None
        return self.update_content(
            doc_id,
            version.content,
            restored_by,
            change_summary=f"Restored to version {version_number}",
        )

    # -- Search -------------------------------------------------------------

    def search(
        self,
        query: str,
        *,
        workspace_id: str = "",
        doc_type: Optional[DocType] = None,
    ) -> List[WorkDoc]:
        """Full-text search across document titles and content.

        Args:
            query: Search string (case-insensitive).
            workspace_id: Scope to a workspace.
            doc_type: Filter by type.

        Returns:
            Matching documents sorted by relevance (title match > content).
        """
        q = query.lower()
        docs = self.list_docs(workspace_id=workspace_id, doc_type=doc_type)
        title_matches = [d for d in docs if q in d.title.lower()]
        content_matches = [
            d for d in docs
            if d not in title_matches and q in d.content.lower()
        ]
        return title_matches + content_matches

    # -- Templates ----------------------------------------------------------

    def list_templates(self) -> List[DocTemplate]:
        """Return all available document templates."""
        return list(self._templates.values())

    def get_template(self, doc_type: DocType) -> Optional[DocTemplate]:
        """Return the template for a given doc type."""
        return _DOC_TEMPLATES.get(doc_type)

    def add_custom_template(self, template: DocTemplate) -> None:
        """Register a custom document template."""
        self._templates[template.id] = template

    # -- Rendering ----------------------------------------------------------

    def render_doc_summary(self, doc_id: str) -> str:
        """Render a compact document summary for Matrix.

        Args:
            doc_id: Document to summarise.

        Returns:
            Markdown string.
        """
        doc = self._docs.get(doc_id)
        if doc is None:
            return f"Document {doc_id} not found."

        editing = ", ".join(doc.editing_by) if doc.editing_by else "nobody"
        links_b = len(doc.board_ids)
        links_i = len(doc.item_ids)
        tags_str = " ".join(f"`{t}`" for t in doc.tags) if doc.tags else "—"
        snippet = doc.content[:300].replace("\n", " ").strip() + (
            "…" if len(doc.content) > 300 else ""
        )

        return (
            f"{doc.type_icon} **{doc.title}**\n"
            f"> Type: {doc.doc_type.value} | Status: {doc.status.value} | "
            f"Version: {doc.current_version}\n"
            f"> Boards linked: {links_b} | Items linked: {links_i}\n"
            f"> Tags: {tags_str}\n"
            f"> Currently editing: {editing}\n"
            f"> Last updated: {doc.updated_at[:10]}\n\n"
            f"_{snippet}_"
        )

    # -- Serialisation ------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {did: d.to_dict() for did, d in self._docs.items()}

    def load_dict(self, data: Dict[str, Any]) -> None:
        self._docs = {did: WorkDoc.from_dict(ddata) for did, ddata in data.items()}

    # -- Private helpers ----------------------------------------------------

    def _save_version(
        self, doc: WorkDoc, edited_by: str, change_summary: str
    ) -> DocVersion:
        """Append a version snapshot to the document's history."""
        version = DocVersion(
            content=doc.content,
            edited_by=edited_by,
            version_number=doc.current_version + 1,
            change_summary=change_summary,
        )
        doc.version_history.append(version)
        if len(doc.version_history) > MAX_VERSION_HISTORY:
            doc.version_history = doc.version_history[-MAX_VERSION_HISTORY:]
        return version
