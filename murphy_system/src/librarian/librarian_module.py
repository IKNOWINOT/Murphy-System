"""
Unified Librarian Module for Murphy System Runtime
Combines knowledge base, semantic search, and document management
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from .document_manager import DocumentManager
from .knowledge_base import KnowledgeBase
from .semantic_search import SemanticSearchEngine


class LibrarianModule:
    """
    Unified librarian module providing comprehensive knowledge management.

    Combines:
    - Knowledge base storage and retrieval
    - Semantic search capabilities
    - Document management and processing
    """

    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize the librarian module.

        Args:
            storage_path: Optional path for persistent storage
        """
        # Initialize components
        self.knowledge_base = KnowledgeBase(storage_path)
        self.semantic_search = SemanticSearchEngine(self.knowledge_base)
        self.document_manager = DocumentManager(self.knowledge_base)

        # Module statistics
        self.stats = {
            'initialized_at': datetime.now(timezone.utc).isoformat(),
            'total_operations': 0,
            'search_queries': 0,
            'documents_processed': 0
        }

        logger.info("Librarian Module initialized with all components")

    def add_knowledge(self, entry_id: str, content: Dict[str, Any],
                     metadata: Optional[Dict] = None) -> bool:
        """
        Add knowledge to the system.

        Args:
            entry_id: Unique identifier
            content: Content dictionary
            metadata: Optional metadata

        Returns:
            True if successful
        """
        self.stats['total_operations'] += 1
        return self.knowledge_base.add_entry(entry_id, content, metadata)

    def search(self, query: str, filters: Optional[Dict] = None,
              limit: int = 10) -> List[Dict]:
        """
        Perform semantic search.

        Args:
            query: Search query
            filters: Optional filters
            limit: Maximum results

        Returns:
            List of search results
        """
        self.stats['search_queries'] += 1
        return self.semantic_search.search(query, filters, limit)

    def ingest_document(self, document_content: Any, metadata: Optional[Dict] = None,
                       document_type: str = 'text') -> Optional[str]:
        """
        Ingest a document.

        Args:
            document_content: Document content
            metadata: Optional metadata
            document_type: Document type

        Returns:
            Document ID if successful
        """
        self.stats['documents_processed'] += 1
        return self.document_manager.ingest_document(
            document_content, metadata, document_type
        )

    def get_knowledge(self, entry_id: str) -> Optional[Dict]:
        """
        Retrieve knowledge entry.

        Args:
            entry_id: Entry identifier

        Returns:
            Entry dictionary if found
        """
        return self.knowledge_base.get_entry(entry_id)

    def update_knowledge(self, entry_id: str, content: Optional[Dict] = None,
                        metadata: Optional[Dict] = None) -> bool:
        """
        Update knowledge entry.

        Args:
            entry_id: Entry identifier
            content: New content
            metadata: New metadata

        Returns:
            True if successful
        """
        self.stats['total_operations'] += 1
        return self.knowledge_base.update_entry(entry_id, content, metadata)

    def delete_knowledge(self, entry_id: str) -> bool:
        """
        Delete knowledge entry.

        Args:
            entry_id: Entry identifier

        Returns:
            True if successful
        """
        self.stats['total_operations'] += 1
        return self.knowledge_base.delete_entry(entry_id)

    def get_related_knowledge(self, entry_id: str, depth: int = 1) -> List[Dict]:
        """
        Get related knowledge entries.

        Args:
            entry_id: Starting entry ID
            depth: Reference depth

        Returns:
            List of related entries
        """
        return self.knowledge_base.get_related_entries(entry_id, depth)

    def suggest_queries(self, partial_query: str, limit: int = 5) -> List[str]:
        """
        Get query suggestions.

        Args:
            partial_query: Partial query
            limit: Maximum suggestions

        Returns:
            List of suggestions
        """
        return self.semantic_search.suggest_queries(partial_query, limit)

    def get_statistics(self) -> Dict:
        """
        Get comprehensive statistics.

        Returns:
            Dictionary with statistics from all components
        """
        kb_stats = self.knowledge_base.get_statistics()
        search_stats = self.semantic_search.get_search_statistics()
        doc_stats = self.document_manager.get_statistics()

        return {
            'module_stats': self.stats,
            'knowledge_base': kb_stats,
            'semantic_search': search_stats,
            'document_manager': doc_stats
        }
