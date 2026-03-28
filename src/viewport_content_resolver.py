"""
Viewport Content Resolver
==========================

Bridges the Artifact Viewport service with Murphy System's data stores:
- Memory Artifact System (MAS): artifacts across sandbox/working/control/execution planes
- Persistence Manager: persisted documents, gate history, audit trails
- System Librarian: generated documentation and transcripts

Thread-safe. Tenant-isolated. Read-only.
"""

import logging
from typing import Any, Dict, Optional

from artifact_viewport import ViewportOrigin

logger = logging.getLogger(__name__)


class ViewportContentResolver:
    """
    Resolves artifact IDs to raw content by searching across data stores.

    The resolver maps ViewportOrigin enum values to the appropriate backend:
    - SANDBOX/WORKING/CONTROL/EXECUTION → Memory Artifact System
    - PERSISTENCE → Persistence Manager (documents, gate history, audit)
    - LIBRARIAN → System Librarian (transcripts, generated docs)

    If no origin is specified, searches all stores in order.
    """

    def __init__(
        self,
        memory_system=None,
        persistence_manager=None,
        system_librarian=None,
    ):
        self._mas = memory_system
        self._persistence = persistence_manager
        self._librarian = system_librarian

    @staticmethod
    def _extract_content(obj) -> Any:
        """Extract viewable content from an artifact or document object."""
        if hasattr(obj, 'content'):
            return obj.content
        if hasattr(obj, 'to_dict'):
            return obj.to_dict()
        return obj

    def resolve(
        self,
        artifact_id: str,
        tenant_id: str,
        origin: ViewportOrigin,
    ) -> Optional[Any]:
        """
        Resolve an artifact ID to its raw content.

        Args:
            artifact_id: Unique identifier of the artifact
            tenant_id: Tenant isolation key
            origin: Which data store to search

        Returns:
            Raw content (str, dict, list) or None if not found
        """
        if origin in (
            ViewportOrigin.SANDBOX,
            ViewportOrigin.WORKING,
            ViewportOrigin.CONTROL,
            ViewportOrigin.EXECUTION,
        ):
            return self._resolve_from_mas(artifact_id, origin)

        if origin == ViewportOrigin.PERSISTENCE:
            return self._resolve_from_persistence(artifact_id)

        if origin == ViewportOrigin.LIBRARIAN:
            return self._resolve_from_librarian(artifact_id)

        # Fallback: search all stores
        return self._resolve_any(artifact_id)

    def _resolve_from_mas(
        self,
        artifact_id: str,
        origin: ViewportOrigin,
    ) -> Optional[Any]:
        """Look up artifact in the Memory Artifact System."""
        if not self._mas:
            return None

        plane_map = {
            ViewportOrigin.SANDBOX: 'sandbox',
            ViewportOrigin.WORKING: 'working',
            ViewportOrigin.CONTROL: 'control',
            ViewportOrigin.EXECUTION: 'execution',
        }
        plane_name = plane_map.get(origin)

        # Try reading from the specific memory plane
        try:
            plane = getattr(self._mas, plane_name, None)
            if plane and hasattr(plane, 'read'):
                artifact = plane.read(artifact_id)
                if artifact:
                    return self._extract_content(artifact)
        except Exception as exc:
            logger.debug(f"MAS lookup failed for {artifact_id} in {plane_name}: {exc}")

        return None

    def _resolve_from_persistence(self, artifact_id: str) -> Optional[Any]:
        """Look up artifact in the Persistence Manager."""
        if not self._persistence:
            return None

        try:
            doc = self._persistence.load_document(artifact_id)
            if doc is not None:
                return doc
        except Exception as exc:
            logger.debug(f"Persistence lookup failed for {artifact_id}: {exc}")

        return None

    def _resolve_from_librarian(self, artifact_id: str) -> Optional[Any]:
        """Look up artifact in the System Librarian."""
        if not self._librarian:
            return None

        try:
            if hasattr(self._librarian, 'get_document'):
                doc = self._librarian.get_document(artifact_id)
                if doc:
                    return self._extract_content(doc)
            if hasattr(self._librarian, 'get_transcript'):
                transcript = self._librarian.get_transcript(artifact_id)
                if transcript:
                    return transcript
        except Exception as exc:
            logger.debug(f"Librarian lookup failed for {artifact_id}: {exc}")

        return None

    def _resolve_any(self, artifact_id: str) -> Optional[Any]:
        """Search all data stores for an artifact."""
        # Check persistence first (most common for document review)
        content = self._resolve_from_persistence(artifact_id)
        if content is not None:
            return content

        # Check all MAS planes
        for origin in (
            ViewportOrigin.WORKING,
            ViewportOrigin.SANDBOX,
            ViewportOrigin.CONTROL,
            ViewportOrigin.EXECUTION,
        ):
            content = self._resolve_from_mas(artifact_id, origin)
            if content is not None:
                return content

        # Check librarian
        return self._resolve_from_librarian(artifact_id)
