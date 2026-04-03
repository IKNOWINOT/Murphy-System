"""
Acceptance tests – Management Parity Phase 5: WorkDocs
======================================================

Validates the WorkDocs module (``src/workdocs``):

- Document creation (CRUD)
- Block-based content: text, heading, lists, code, checklist, etc.
- Inline @mentions proxied through block content (mention parsing)
- Version history (snapshot creation and retrieval)
- Template support (document pre-seeded with structured blocks)

Run selectively::

    pytest -m parity tests/test_mgmt_parity_phase5.py

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import sys
import os

import pytest


import workdocs
from workdocs import (
    Block,
    BlockType,
    DocManager,
    DocPermission,
    DocStatus,
    Document,
    DocVersion,
)

pytestmark = pytest.mark.parity


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mgr() -> DocManager:
    return DocManager()


def _create_doc(mgr: DocManager, title: str = "Sprint Notes") -> Document:
    return mgr.create_document(title, owner_id="alice", board_id="board-1")


# ---------------------------------------------------------------------------
# 1. Module structure
# ---------------------------------------------------------------------------


class TestModuleStructure:
    def test_package_version_exists(self):
        assert hasattr(workdocs, "__version__")

    def test_doc_manager_importable(self):
        assert DocManager is not None

    def test_block_types_defined(self):
        for bt in (
            BlockType.TEXT,
            BlockType.HEADING,
            BlockType.BULLET_LIST,
            BlockType.NUMBERED_LIST,
            BlockType.CHECKLIST,
            BlockType.CODE,
            BlockType.QUOTE,
            BlockType.DIVIDER,
            BlockType.IMAGE,
            BlockType.TABLE,
            BlockType.BOARD_EMBED,
        ):
            assert bt is not None

    def test_doc_permission_values(self):
        for perm in (DocPermission.PRIVATE, DocPermission.VIEW,
                     DocPermission.COMMENT, DocPermission.EDIT):
            assert perm is not None

    def test_doc_status_values(self):
        for status in (DocStatus.DRAFT, DocStatus.PUBLISHED, DocStatus.ARCHIVED):
            assert status is not None


# ---------------------------------------------------------------------------
# 2. Document creation
# ---------------------------------------------------------------------------


class TestDocumentCreation:
    def test_create_document_returns_document(self):
        mgr = _make_mgr()
        doc = _create_doc(mgr, "Project Charter")
        assert isinstance(doc, Document)
        assert doc.title == "Project Charter"

    def test_document_has_unique_id(self):
        mgr = _make_mgr()
        d1 = _create_doc(mgr, "Doc A")
        d2 = _create_doc(mgr, "Doc B")
        assert d1.id != d2.id

    def test_get_document(self):
        mgr = _make_mgr()
        doc = _create_doc(mgr)
        retrieved = mgr.get_document(doc.id)
        assert retrieved is not None
        assert retrieved.id == doc.id

    def test_list_documents_by_owner(self):
        mgr = _make_mgr()
        mgr.create_document("D1", owner_id="alice")
        mgr.create_document("D2", owner_id="alice")
        mgr.create_document("D3", owner_id="bob")
        alice_docs = mgr.list_documents(owner_id="alice")
        assert len(alice_docs) == 2

    def test_update_document_title(self):
        mgr = _make_mgr()
        doc = _create_doc(mgr, "Old Title")
        mgr.update_document(doc.id, user_id="alice", title="New Title")
        retrieved = mgr.get_document(doc.id)
        assert retrieved.title == "New Title"

    def test_delete_document(self):
        mgr = _make_mgr()
        doc = _create_doc(mgr)
        removed = mgr.delete_document(doc.id, user_id="alice")
        assert removed is True
        assert mgr.get_document(doc.id) is None

    def test_document_default_status_is_draft(self):
        mgr = _make_mgr()
        doc = _create_doc(mgr)
        assert doc.status == DocStatus.DRAFT


# ---------------------------------------------------------------------------
# 3. Block-based content
# ---------------------------------------------------------------------------


class TestBlockBasedContent:
    def test_add_text_block(self):
        mgr = _make_mgr()
        doc = _create_doc(mgr)
        block = mgr.add_block(doc.id, BlockType.TEXT, "Hello world")
        assert block.block_type == BlockType.TEXT
        assert block.content == "Hello world"

    def test_add_heading_block(self):
        mgr = _make_mgr()
        doc = _create_doc(mgr)
        block = mgr.add_block(doc.id, BlockType.HEADING, "Introduction")
        assert block.block_type == BlockType.HEADING

    def test_add_multiple_blocks(self):
        mgr = _make_mgr()
        doc = _create_doc(mgr)
        mgr.add_block(doc.id, BlockType.HEADING, "Day 1")
        mgr.add_block(doc.id, BlockType.TEXT, "Completed setup")
        mgr.add_block(doc.id, BlockType.BULLET_LIST, "Item A")
        retrieved = mgr.get_document(doc.id)
        assert len(retrieved.blocks) == 3

    def test_add_checklist_block(self):
        mgr = _make_mgr()
        doc = _create_doc(mgr)
        block = mgr.add_block(doc.id, BlockType.CHECKLIST, "Review PR")
        # Set checked state via update_block
        updated = mgr.update_block(doc.id, block.id, checked=False)
        assert updated.block_type == BlockType.CHECKLIST
        assert updated.checked is False

    def test_update_block_content(self):
        mgr = _make_mgr()
        doc = _create_doc(mgr)
        block = mgr.add_block(doc.id, BlockType.TEXT, "Original")
        updated = mgr.update_block(doc.id, block.id, content="Updated")
        assert updated.content == "Updated"

    def test_delete_block(self):
        mgr = _make_mgr()
        doc = _create_doc(mgr)
        block = mgr.add_block(doc.id, BlockType.TEXT, "To delete")
        removed = mgr.delete_block(doc.id, block.id)
        assert removed is True
        retrieved = mgr.get_document(doc.id)
        assert not any(b.id == block.id for b in retrieved.blocks)

    def test_add_code_block(self):
        mgr = _make_mgr()
        doc = _create_doc(mgr)
        block = mgr.add_block(
            doc.id, BlockType.CODE,
            "print('Hello')",
            metadata={"language": "python"},
        )
        assert block.block_type == BlockType.CODE
        assert block.metadata.get("language") == "python"

    def test_add_board_embed_block(self):
        mgr = _make_mgr()
        doc = _create_doc(mgr)
        block = mgr.add_block(
            doc.id, BlockType.BOARD_EMBED,
            "",
            metadata={"board_id": "board-sprint"},
        )
        assert block.block_type == BlockType.BOARD_EMBED
        assert block.metadata["board_id"] == "board-sprint"


# ---------------------------------------------------------------------------
# 4. Inline mentions (proxied through block content)
# ---------------------------------------------------------------------------


class TestInlineMentions:
    """@mention text is stored in block content and can be scanned."""

    def test_mention_stored_in_block_content(self):
        mgr = _make_mgr()
        doc = _create_doc(mgr)
        block = mgr.add_block(doc.id, BlockType.TEXT, "Please review @bob before merging.")
        assert "@bob" in block.content

    def test_multiple_mentions_in_block(self):
        mgr = _make_mgr()
        doc = _create_doc(mgr)
        block = mgr.add_block(doc.id, BlockType.TEXT, "@alice and @carol need to sign off.")
        assert "@alice" in block.content
        assert "@carol" in block.content

    def test_mention_in_heading(self):
        mgr = _make_mgr()
        doc = _create_doc(mgr)
        block = mgr.add_block(doc.id, BlockType.HEADING, "Action items for @dave")
        assert "@dave" in block.content


# ---------------------------------------------------------------------------
# 5. Version history
# ---------------------------------------------------------------------------


class TestVersionHistory:
    def test_create_version_snapshot(self):
        mgr = _make_mgr()
        doc = _create_doc(mgr, "Versioned Doc")
        mgr.add_block(doc.id, BlockType.TEXT, "Initial content")
        version = mgr.create_version(doc.id, editor_id="alice", summary="Initial draft")
        assert isinstance(version, DocVersion)
        assert version.summary == "Initial draft"
        assert version.editor_id == "alice"

    def test_version_captures_blocks_snapshot(self):
        mgr = _make_mgr()
        doc = _create_doc(mgr)
        mgr.add_block(doc.id, BlockType.TEXT, "Content at V1")
        v1 = mgr.create_version(doc.id, editor_id="alice", summary="V1")
        # Snapshot should contain the block
        assert len(v1.blocks_snapshot) >= 1

    def test_multiple_versions_stored(self):
        mgr = _make_mgr()
        doc = _create_doc(mgr)
        mgr.create_version(doc.id, editor_id="alice", summary="V1")
        mgr.add_block(doc.id, BlockType.TEXT, "Added in V2")
        mgr.create_version(doc.id, editor_id="alice", summary="V2")
        versions = mgr.get_versions(doc.id)
        assert len(versions) == 2

    def test_versions_ordered_by_creation(self):
        mgr = _make_mgr()
        doc = _create_doc(mgr)
        mgr.create_version(doc.id, editor_id="alice", summary="First")
        mgr.create_version(doc.id, editor_id="bob", summary="Second")
        versions = mgr.get_versions(doc.id)
        assert versions[0].summary == "First"
        assert versions[1].summary == "Second"


# ---------------------------------------------------------------------------
# 6. Template support
# ---------------------------------------------------------------------------


class TestTemplateSupport:
    """Templates are documents pre-seeded with structured blocks."""

    def _create_meeting_notes_template(self, mgr: DocManager) -> Document:
        """Build a meeting notes template document."""
        doc = mgr.create_document(
            "Meeting Notes Template",
            owner_id="system",
            permission=DocPermission.VIEW,
        )
        mgr.add_block(doc.id, BlockType.HEADING, "Agenda")
        mgr.add_block(doc.id, BlockType.BULLET_LIST, "")
        mgr.add_block(doc.id, BlockType.HEADING, "Notes")
        mgr.add_block(doc.id, BlockType.TEXT, "")
        mgr.add_block(doc.id, BlockType.HEADING, "Action Items")
        mgr.add_block(doc.id, BlockType.CHECKLIST, "")
        return doc

    def test_template_document_created(self):
        mgr = _make_mgr()
        template = self._create_meeting_notes_template(mgr)
        assert template is not None
        assert len(template.blocks) == 6

    def test_template_contains_expected_block_types(self):
        mgr = _make_mgr()
        template = self._create_meeting_notes_template(mgr)
        types = [b.block_type for b in template.blocks]
        assert BlockType.HEADING in types
        assert BlockType.BULLET_LIST in types
        assert BlockType.CHECKLIST in types

    def test_document_seeded_from_template(self):
        """Cloning a template into a new document simulates template usage."""
        mgr = _make_mgr()
        template = self._create_meeting_notes_template(mgr)
        # Create a new doc seeded from template blocks
        new_doc = mgr.create_document("Sprint Review Notes", owner_id="alice")
        for block in template.blocks:
            mgr.add_block(new_doc.id, block.block_type, block.content)
        retrieved = mgr.get_document(new_doc.id)
        assert len(retrieved.blocks) == len(template.blocks)

    def test_collaborators_on_document(self):
        mgr = _make_mgr()
        doc = _create_doc(mgr)
        mgr.add_collaborator(doc.id, "bob")
        retrieved = mgr.get_document(doc.id)
        assert "bob" in retrieved.collaborator_ids

    def test_remove_collaborator(self):
        mgr = _make_mgr()
        doc = _create_doc(mgr)
        mgr.add_collaborator(doc.id, "carol")
        removed = mgr.remove_collaborator(doc.id, "carol")
        assert removed is True
        retrieved = mgr.get_document(doc.id)
        assert "carol" not in retrieved.collaborator_ids
