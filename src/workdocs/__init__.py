"""
Workdocs – Collaborative Documents
====================================

Phase 5 of management systems feature parity for the Murphy System.

Provides collaborative document authoring including:

- **Documents** – CRUD with owner, board link, sharing levels
- **Blocks** – text, heading, bullet/numbered lists, checklists, code, quote, divider, image, table, board embed
- **Versioning** – snapshot-based version history
- **Collaboration** – add/remove collaborators with permission checks

Quick start::

    from workdocs import DocManager, BlockType

    mgr = DocManager()
    doc = mgr.create_document("Sprint Notes", owner_id="u1")
    mgr.add_block(doc.id, BlockType.HEADING, "Day 1")
    mgr.add_block(doc.id, BlockType.TEXT, "Completed board setup")
    mgr.create_version(doc.id, editor_id="u1", summary="Initial draft")

Copyright 2024 Inoni LLC – BSL-1.1
"""

__version__ = "0.1.0"
__codename__ = "Workdocs"

from .doc_manager import DocManager
from .models import (
    Block,
    BlockType,
    DocPermission,
    DocStatus,
    Document,
    DocVersion,
)

try:
    from .api import create_workdocs_router
except Exception:  # pragma: no cover
    create_workdocs_router = None  # type: ignore[assignment]

__all__ = [
    "Block",
    "BlockType",
    "DocPermission",
    "DocStatus",
    "DocVersion",
    "Document",
    "DocManager",
    "create_workdocs_router",
]
