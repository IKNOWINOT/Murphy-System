"""
Knowledge Base Management for Librarian Module
Provides storage, retrieval, and management of knowledge artifacts
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class KnowledgeBase:
    """
    Central knowledge management system for storing and retrieving information.

    Provides:
    - Structured knowledge storage
    - Metadata management
    - Cross-referencing capabilities
    - Query processing
    """

    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize the knowledge base.

        Args:
            storage_path: Optional path for persistent storage
        """
        self.storage_path = storage_path
        self.knowledge_store: Dict[str, Dict] = {}
        self.metadata_index: Dict[str, List[str]] = {}
        self.cross_references: Dict[str, List[str]] = {}

        # Statistics
        self.stats = {
            'total_entries': 0,
            'total_size_bytes': 0,
            'queries_processed': 0,
            'last_updated': datetime.now(timezone.utc).isoformat()
        }

        # Load existing data if path provided
        if storage_path:
            self._load_from_storage()

        logger.info(f"Knowledge Base initialized with {len(self.knowledge_store)} entries")

    def add_entry(self,
                  entry_id: str,
                  content: Dict[str, Any],
                  metadata: Optional[Dict] = None) -> bool:
        """
        Add a new entry to the knowledge base.

        Args:
            entry_id: Unique identifier for the entry
            content: Main content of the entry
            metadata: Optional metadata tags and attributes

        Returns:
            True if successful, False otherwise
        """
        try:
            if entry_id in self.knowledge_store:
                logger.warning(f"Entry {entry_id} already exists, updating")

            entry = {
                'id': entry_id,
                'content': content,
                'metadata': metadata or {},
                'created_at': datetime.now(timezone.utc).isoformat(),
                'updated_at': datetime.now(timezone.utc).isoformat(),
                'access_count': 0
            }

            self.knowledge_store[entry_id] = entry
            self.stats['total_entries'] = len(self.knowledge_store)
            self.stats['total_size_bytes'] += len(json.dumps(entry))
            self.stats['last_updated'] = datetime.now(timezone.utc).isoformat()

            # Update metadata index
            if metadata:
                for key, value in metadata.items():
                    if key not in self.metadata_index:
                        self.metadata_index[key] = []
                    self.metadata_index[key].append(entry_id)

            logger.info(f"Added entry {entry_id} to knowledge base")
            return True

        except Exception as exc:
            logger.error(f"Error adding entry {entry_id}: {exc}")
            return False

    def get_entry(self, entry_id: str) -> Optional[Dict]:
        """
        Retrieve an entry from the knowledge base.

        Args:
            entry_id: Unique identifier for the entry

        Returns:
            Entry dictionary if found, None otherwise
        """
        try:
            if entry_id in self.knowledge_store:
                entry = self.knowledge_store[entry_id]
                entry['access_count'] += 1
                entry['last_accessed'] = datetime.now(timezone.utc).isoformat()
                self.stats['queries_processed'] += 1
                return entry.copy()
            return None
        except Exception as exc:
            logger.error(f"Error retrieving entry {entry_id}: {exc}")
            return None

    def query(self,
              query: str,
              filters: Optional[Dict] = None,
              limit: int = 10) -> List[Dict]:
        """
        Query the knowledge base for matching entries.

        Args:
            query: Search query string
            filters: Optional metadata filters
            limit: Maximum number of results

        Returns:
            List of matching entries
        """
        try:
            results = []
            query_lower = query.lower()

            for entry_id, entry in self.knowledge_store.items():
                # Apply metadata filters
                if filters:
                    match = True
                    for key, value in filters.items():
                        if key not in entry.get('metadata', {}):
                            match = False
                            break
                        if entry['metadata'][key] != value:
                            match = False
                            break
                    if not match:
                        continue

                # Search in content
                content_str = json.dumps(entry['content']).lower()
                if query_lower in content_str:
                    results.append(entry.copy())

                if len(results) >= limit:
                    break

            self.stats['queries_processed'] += 1
            logger.info(f"Query returned {len(results)} results")
            return results

        except Exception as exc:
            logger.error(f"Error executing query: {exc}")
            return []

    def add_cross_reference(self, from_id: str, to_id: str) -> bool:
        """
        Add a cross-reference between entries.

        Args:
            from_id: Source entry ID
            to_id: Target entry ID

        Returns:
            True if successful, False otherwise
        """
        try:
            if from_id not in self.cross_references:
                self.cross_references[from_id] = []

            if to_id not in self.cross_references[from_id]:
                self.cross_references[from_id].append(to_id)

            logger.info(f"Added cross-reference from {from_id} to {to_id}")
            return True

        except Exception as exc:
            logger.error(f"Error adding cross-reference: {exc}")
            return False

    def get_related_entries(self, entry_id: str, depth: int = 1) -> List[Dict]:
        """
        Get entries related to the given entry through cross-references.

        Args:
            entry_id: Starting entry ID
            depth: How many levels of references to follow

        Returns:
            List of related entries
        """
        try:
            related = []
            visited = set()
            queue = [(entry_id, 0)]

            while queue and len(related) < 20:
                current_id, current_depth = queue.pop(0)

                if current_id in visited or current_depth > depth:
                    continue

                visited.add(current_id)

                if current_id != entry_id and current_id in self.knowledge_store:
                    related.append(self.knowledge_store[current_id].copy())

                if current_id in self.cross_references:
                    for ref_id in self.cross_references[current_id]:
                        queue.append((ref_id, current_depth + 1))

            logger.info(f"Found {len(related)} related entries for {entry_id}")
            return related

        except Exception as exc:
            logger.error(f"Error getting related entries: {exc}")
            return []

    def update_entry(self, entry_id: str, content: Optional[Dict] = None,
                    metadata: Optional[Dict] = None) -> bool:
        """
        Update an existing entry.

        Args:
            entry_id: Unique identifier for the entry
            content: New content (optional)
            metadata: New metadata (optional)

        Returns:
            True if successful, False otherwise
        """
        try:
            if entry_id not in self.knowledge_store:
                logger.warning(f"Entry {entry_id} not found for update")
                return False

            entry = self.knowledge_store[entry_id]

            if content:
                entry['content'] = content

            if metadata:
                entry['metadata'] = metadata

            entry['updated_at'] = datetime.now(timezone.utc).isoformat()
            self.stats['last_updated'] = datetime.now(timezone.utc).isoformat()

            logger.info(f"Updated entry {entry_id}")
            return True

        except Exception as exc:
            logger.error(f"Error updating entry {entry_id}: {exc}")
            return False

    def delete_entry(self, entry_id: str) -> bool:
        """
        Delete an entry from the knowledge base.

        Args:
            entry_id: Unique identifier for the entry

        Returns:
            True if successful, False otherwise
        """
        try:
            if entry_id in self.knowledge_store:
                del self.knowledge_store[entry_id]

                # Remove from metadata index
                for key in list(self.metadata_index.keys()):
                    if entry_id in self.metadata_index[key]:
                        self.metadata_index[key].remove(entry_id)

                # Remove cross-references
                if entry_id in self.cross_references:
                    del self.cross_references[entry_id]

                self.stats['total_entries'] = len(self.knowledge_store)
                self.stats['last_updated'] = datetime.now(timezone.utc).isoformat()

                logger.info(f"Deleted entry {entry_id}")
                return True

            return False

        except Exception as exc:
            logger.error(f"Error deleting entry {entry_id}: {exc}")
            return False

    def get_statistics(self) -> Dict:
        """
        Get knowledge base statistics.

        Returns:
            Dictionary with statistics
        """
        return self.stats.copy()

    def _load_from_storage(self):
        """Load knowledge base from persistent storage."""
        try:
            # This would load from a file or database
            # For now, we'll just initialize empty
            logger.info("Knowledge base storage not implemented, starting fresh")
        except Exception as exc:
            logger.error(f"Error loading from storage: {exc}")

    def export_knowledge(self, output_format: str = 'json') -> str:
        """
        Export knowledge base data.

        Args:
            output_format: Export format ('json', 'csv')

        Returns:
            Exported data as string
        """
        try:
            if output_format == 'json':
                return json.dumps(self.knowledge_store, indent=2)
            else:
                logger.warning(f"Format {output_format} not supported")
                return ""
        except Exception as exc:
            logger.error(f"Error exporting knowledge: {exc}")
            return ""
