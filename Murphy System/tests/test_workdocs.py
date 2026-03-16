"""Tests for Phase 5 – Collaborative Docs (workdocs)."""

import sys, os

import pytest
from workdocs.models import Block, BlockType, DocPermission, DocStatus, DocVersion, Document
from workdocs.doc_manager import DocManager


class TestModels:
    def test_document_to_dict(self):
        d = Document(title="Notes", owner_id="u1")
        r = d.to_dict()
        assert r["title"] == "Notes"
        assert r["status"] == "draft"

    def test_block_to_dict(self):
        b = Block(block_type=BlockType.HEADING, content="Title")
        r = b.to_dict()
        assert r["block_type"] == "heading"

    def test_doc_version_to_dict(self):
        v = DocVersion(version_number=2, editor_id="u1")
        r = v.to_dict()
        assert r["version_number"] == 2


class TestDocManager:
    def test_create_document(self):
        mgr = DocManager()
        doc = mgr.create_document("Test", owner_id="u1")
        assert doc.title == "Test"

    def test_get_document(self):
        mgr = DocManager()
        doc = mgr.create_document("X")
        assert mgr.get_document(doc.id) is doc
        assert mgr.get_document("nope") is None

    def test_list_documents(self):
        mgr = DocManager()
        mgr.create_document("A", owner_id="u1")
        mgr.create_document("B", owner_id="u2")
        assert len(mgr.list_documents()) == 2
        assert len(mgr.list_documents(owner_id="u1")) == 1

    def test_update_document(self):
        mgr = DocManager()
        doc = mgr.create_document("Old", owner_id="u1")
        upd = mgr.update_document(doc.id, user_id="u1", title="New")
        assert upd.title == "New"

    def test_update_document_not_found(self):
        mgr = DocManager()
        with pytest.raises(KeyError):
            mgr.update_document("bad", title="X")

    def test_update_document_permission(self):
        mgr = DocManager()
        doc = mgr.create_document("X", owner_id="u1")
        with pytest.raises(PermissionError):
            mgr.update_document(doc.id, user_id="u2", title="Hacked")

    def test_delete_document(self):
        mgr = DocManager()
        doc = mgr.create_document("X", owner_id="u1")
        assert mgr.delete_document(doc.id, user_id="u1")
        assert mgr.get_document(doc.id) is None

    def test_delete_document_not_found(self):
        mgr = DocManager()
        assert not mgr.delete_document("bad")

    def test_add_block(self):
        mgr = DocManager()
        doc = mgr.create_document("D")
        b = mgr.add_block(doc.id, BlockType.TEXT, "Hello")
        assert b.content == "Hello"
        assert len(doc.blocks) == 1

    def test_add_block_at_position(self):
        mgr = DocManager()
        doc = mgr.create_document("D")
        mgr.add_block(doc.id, BlockType.TEXT, "A")
        mgr.add_block(doc.id, BlockType.TEXT, "C")
        mgr.add_block(doc.id, BlockType.TEXT, "B", position=1)
        assert [b.content for b in doc.blocks] == ["A", "B", "C"]

    def test_update_block(self):
        mgr = DocManager()
        doc = mgr.create_document("D")
        b = mgr.add_block(doc.id, BlockType.TEXT, "Old")
        upd = mgr.update_block(doc.id, b.id, content="New")
        assert upd.content == "New"

    def test_update_block_not_found(self):
        mgr = DocManager()
        doc = mgr.create_document("D")
        with pytest.raises(KeyError):
            mgr.update_block(doc.id, "bad", content="X")

    def test_delete_block(self):
        mgr = DocManager()
        doc = mgr.create_document("D")
        b = mgr.add_block(doc.id, BlockType.TEXT, "X")
        assert mgr.delete_block(doc.id, b.id)
        assert len(doc.blocks) == 0

    def test_move_block(self):
        mgr = DocManager()
        doc = mgr.create_document("D")
        b1 = mgr.add_block(doc.id, BlockType.TEXT, "A")
        b2 = mgr.add_block(doc.id, BlockType.TEXT, "B")
        mgr.move_block(doc.id, b2.id, 0)
        assert doc.blocks[0].content == "B"

    def test_create_version(self):
        mgr = DocManager()
        doc = mgr.create_document("D")
        mgr.add_block(doc.id, BlockType.TEXT, "Hello")
        v = mgr.create_version(doc.id, editor_id="u1", summary="v1")
        assert v.version_number == 1
        assert len(v.blocks_snapshot) == 1

    def test_get_versions(self):
        mgr = DocManager()
        doc = mgr.create_document("D")
        mgr.create_version(doc.id)
        mgr.create_version(doc.id)
        assert len(mgr.get_versions(doc.id)) == 2

    def test_add_collaborator(self):
        mgr = DocManager()
        doc = mgr.create_document("D")
        mgr.add_collaborator(doc.id, "u2")
        assert "u2" in doc.collaborator_ids

    def test_remove_collaborator(self):
        mgr = DocManager()
        doc = mgr.create_document("D")
        mgr.add_collaborator(doc.id, "u2")
        assert mgr.remove_collaborator(doc.id, "u2")
        assert "u2" not in doc.collaborator_ids

    def test_collaborator_can_edit(self):
        mgr = DocManager()
        doc = mgr.create_document("D", owner_id="u1")
        mgr.add_collaborator(doc.id, "u2")
        upd = mgr.update_document(doc.id, user_id="u2", title="Updated")
        assert upd.title == "Updated"


class TestAPIRouter:
    def test_create_router(self):
        from workdocs.api import create_workdocs_router
        router = create_workdocs_router()
        assert router is not None
