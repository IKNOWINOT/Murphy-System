"""
Workdocs – Document Manager
=============================

Central façade for document CRUD, block editing, and version history.

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .models import (
    Block,
    BlockType,
    DocPermission,
    DocStatus,
    Document,
    DocVersion,
    _now,
)

logger = logging.getLogger(__name__)


class DocManager:
    """In-memory collaborative document manager.

    Manages documents with block-based content, versioning, and sharing.
    """

    def __init__(self) -> None:
        self._documents: Dict[str, Document] = {}

    # -- Document CRUD ------------------------------------------------------

    def create_document(
        self,
        title: str,
        *,
        owner_id: str = "",
        board_id: str = "",
        permission: DocPermission = DocPermission.PRIVATE,
    ) -> Document:
        doc = Document(
            title=title,
            owner_id=owner_id,
            board_id=board_id,
            permission=permission,
        )
        self._documents[doc.id] = doc
        logger.info("Document created: %s (%s)", doc.title, doc.id)
        return doc

    def get_document(self, doc_id: str) -> Optional[Document]:
        return self._documents.get(doc_id)

    def list_documents(
        self,
        *,
        owner_id: str = "",
        board_id: str = "",
        status: Optional[DocStatus] = None,
    ) -> List[Document]:
        docs = list(self._documents.values())
        if owner_id:
            docs = [d for d in docs if d.owner_id == owner_id]
        if board_id:
            docs = [d for d in docs if d.board_id == board_id]
        if status is not None:
            docs = [d for d in docs if d.status == status]
        return docs

    def update_document(
        self,
        doc_id: str,
        *,
        user_id: str = "",
        title: Optional[str] = None,
        status: Optional[DocStatus] = None,
        permission: Optional[DocPermission] = None,
    ) -> Document:
        doc = self._documents.get(doc_id)
        if doc is None:
            raise KeyError(f"Document not found: {doc_id!r}")
        if user_id and doc.owner_id != user_id and user_id not in doc.collaborator_ids:
            raise PermissionError("Not authorized to edit this document")
        if title is not None:
            doc.title = title
        if status is not None:
            doc.status = status
        if permission is not None:
            doc.permission = permission
        doc.updated_at = _now()
        return doc

    def delete_document(self, doc_id: str, *, user_id: str = "") -> bool:
        doc = self._documents.get(doc_id)
        if doc is None:
            return False
        if user_id and doc.owner_id != user_id:
            raise PermissionError("Only the owner can delete this document")
        del self._documents[doc_id]
        return True

    # -- Block editing ------------------------------------------------------

    def add_block(
        self,
        doc_id: str,
        block_type: BlockType,
        content: str = "",
        *,
        position: int = -1,
        metadata: Optional[Dict[str, Any]] = None,
        indent_level: int = 0,
    ) -> Block:
        doc = self._documents.get(doc_id)
        if doc is None:
            raise KeyError(f"Document not found: {doc_id!r}")
        block = Block(
            block_type=block_type,
            content=content,
            metadata=metadata or {},
            indent_level=indent_level,
        )
        if position < 0 or position >= len(doc.blocks):
            doc.blocks.append(block)
        else:
            doc.blocks.insert(position, block)
        doc.updated_at = _now()
        return block

    def update_block(
        self,
        doc_id: str,
        block_id: str,
        *,
        content: Optional[str] = None,
        checked: Optional[bool] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Block:
        doc = self._documents.get(doc_id)
        if doc is None:
            raise KeyError(f"Document not found: {doc_id!r}")
        for block in doc.blocks:
            if block.id == block_id:
                if content is not None:
                    block.content = content
                if checked is not None:
                    block.checked = checked
                if metadata is not None:
                    block.metadata.update(metadata)
                doc.updated_at = _now()
                return block
        raise KeyError(f"Block not found: {block_id!r}")

    def delete_block(self, doc_id: str, block_id: str) -> bool:
        doc = self._documents.get(doc_id)
        if doc is None:
            raise KeyError(f"Document not found: {doc_id!r}")
        for i, block in enumerate(doc.blocks):
            if block.id == block_id:
                doc.blocks.pop(i)
                doc.updated_at = _now()
                return True
        return False

    def move_block(self, doc_id: str, block_id: str, new_position: int) -> bool:
        doc = self._documents.get(doc_id)
        if doc is None:
            raise KeyError(f"Document not found: {doc_id!r}")
        for i, block in enumerate(doc.blocks):
            if block.id == block_id:
                doc.blocks.pop(i)
                doc.blocks.insert(min(new_position, len(doc.blocks)), block)
                doc.updated_at = _now()
                return True
        return False

    # -- Versioning ---------------------------------------------------------

    def create_version(
        self,
        doc_id: str,
        *,
        editor_id: str = "",
        summary: str = "",
    ) -> DocVersion:
        doc = self._documents.get(doc_id)
        if doc is None:
            raise KeyError(f"Document not found: {doc_id!r}")
        version_number = len(doc.versions) + 1
        version = DocVersion(
            version_number=version_number,
            blocks_snapshot=[b.to_dict() for b in doc.blocks],
            editor_id=editor_id,
            summary=summary,
        )
        doc.versions.append(version)
        return version

    def get_versions(self, doc_id: str) -> List[DocVersion]:
        doc = self._documents.get(doc_id)
        if doc is None:
            raise KeyError(f"Document not found: {doc_id!r}")
        return list(doc.versions)

    # -- Collaboration ------------------------------------------------------

    def add_collaborator(self, doc_id: str, user_id: str) -> Document:
        doc = self._documents.get(doc_id)
        if doc is None:
            raise KeyError(f"Document not found: {doc_id!r}")
        if user_id not in doc.collaborator_ids:
            doc.collaborator_ids.append(user_id)
        return doc

    def remove_collaborator(self, doc_id: str, user_id: str) -> bool:
        doc = self._documents.get(doc_id)
        if doc is None:
            raise KeyError(f"Document not found: {doc_id!r}")
        if user_id in doc.collaborator_ids:
            doc.collaborator_ids.remove(user_id)
            return True
        return False
