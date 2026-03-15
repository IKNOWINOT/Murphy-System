"""
Document Manager for Librarian Module
Provides document ingestion, processing, and management capabilities
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DocumentManager:
    """
    Document management system for handling various document types.

    Provides:
    - Document ingestion and parsing
    - Metadata extraction
    - Document processing pipelines
    - Version control
    """

    def __init__(self, knowledge_base):
        """
        Initialize the document manager.

        Args:
            knowledge_base: Reference to the knowledge base
        """
        self.knowledge_base = knowledge_base
        self.document_registry: Dict[str, Dict] = {}
        self.processing_pipelines: Dict[str, callable] = {}

        # Register default pipelines
        self._register_default_pipelines()

        logger.info("Document Manager initialized")

    def ingest_document(self,
                       document_content: Any,
                       metadata: Optional[Dict] = None,
                       document_type: str = 'text',
                       processing_pipeline: Optional[str] = None) -> Optional[str]:
        """
        Ingest a document into the knowledge base.

        Args:
            document_content: Content of the document
            metadata: Optional metadata
            document_type: Type of document (text, json, markdown, etc.)
            processing_pipeline: Optional pipeline to apply

        Returns:
            Document ID if successful, None otherwise
        """
        try:
            # Generate document ID
            document_id = self._generate_document_id(document_content, document_type)

            # Process document if pipeline specified
            processed_content = document_content
            if processing_pipeline and processing_pipeline in self.processing_pipelines:
                processed_content = self.processing_pipelines[processing_pipeline](document_content)

            # Extract metadata
            extracted_metadata = self._extract_metadata(processed_content, document_type)

            # Merge with provided metadata
            final_metadata = {**extracted_metadata, **(metadata or {})}

            # Add document-specific metadata
            final_metadata.update({
                'document_type': document_type,
                'ingested_at': datetime.now(timezone.utc).isoformat(),
                'processing_pipeline': processing_pipeline,
                'content_hash': self._compute_hash(str(processed_content))
            })

            # Create document entry
            document_entry = {
                'content': processed_content,
                'document_type': document_type,
                'metadata': final_metadata,
                'versions': []
            }

            # Store in knowledge base
            success = self.knowledge_base.add_entry(document_id, document_entry, final_metadata)

            if success:
                # Register document
                self.document_registry[document_id] = {
                    'id': document_id,
                    'type': document_type,
                    'ingested_at': final_metadata['ingested_at'],
                    'size': len(str(processed_content)),
                    'pipeline': processing_pipeline
                }

                logger.info(f"Successfully ingested document {document_id}")
                return document_id
            else:
                logger.error(f"Failed to store document {document_id}")
                return None

        except Exception as exc:
            logger.error(f"Error ingesting document: {exc}")
            return None

    def get_document(self, document_id: str) -> Optional[Dict]:
        """
        Retrieve a document from the knowledge base.

        Args:
            document_id: Document identifier

        Returns:
            Document entry if found, None otherwise
        """
        try:
            entry = self.knowledge_base.get_entry(document_id)
            if entry:
                return entry
            return None
        except Exception as exc:
            logger.error(f"Error retrieving document {document_id}: {exc}")
            return None

    def update_document(self,
                       document_id: str,
                       content: Optional[Any] = None,
                       metadata: Optional[Dict] = None) -> bool:
        """
        Update an existing document.

        Args:
            document_id: Document identifier
            content: New content (optional)
            metadata: New metadata (optional)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get current document
            current_doc = self.get_document(document_id)
            if not current_doc:
                logger.warning(f"Document {document_id} not found for update")
                return False

            # Create version backup
            version_entry = {
                'content': current_doc['content'],
                'metadata': current_doc['metadata'],
                'updated_at': current_doc.get('updated_at', datetime.now(timezone.utc).isoformat()),
                'version_number': len(current_doc.get('versions', [])) + 1
            }

            # Update document
            update_data = {}
            if content:
                update_data['content'] = content
            if metadata:
                update_data['metadata'] = metadata

            success = self.knowledge_base.update_entry(document_id, **update_data)

            if success:
                # Add version history
                updated_doc = self.get_document(document_id)
                if updated_doc:
                    if 'versions' not in updated_doc:
                        updated_doc['versions'] = []
                    updated_doc['versions'].append(version_entry)

                    # Update registry
                    if document_id in self.document_registry:
                        self.document_registry[document_id]['last_updated'] = datetime.now(timezone.utc).isoformat()

                logger.info(f"Updated document {document_id}")
                return True

            return False

        except Exception as exc:
            logger.error(f"Error updating document {document_id}: {exc}")
            return False

    def delete_document(self, document_id: str) -> bool:
        """
        Delete a document from the knowledge base.

        Args:
            document_id: Document identifier

        Returns:
            True if successful, False otherwise
        """
        try:
            success = self.knowledge_base.delete_entry(document_id)

            if success:
                # Remove from registry
                if document_id in self.document_registry:
                    del self.document_registry[document_id]

                logger.info(f"Deleted document {document_id}")
                return True

            return False

        except Exception as exc:
            logger.error(f"Error deleting document {document_id}: {exc}")
            return False

    def list_documents(self,
                      filters: Optional[Dict] = None,
                      limit: int = 50) -> List[Dict]:
        """
        List documents with optional filtering.

        Args:
            filters: Optional metadata filters
            limit: Maximum number of documents

        Returns:
            List of document summaries
        """
        try:
            results = self.knowledge_base.query("", filters, limit)

            # Create document summaries
            summaries = []
            for entry in results:
                summary = {
                    'id': entry['id'],
                    'type': entry.get('document_type', 'unknown'),
                    'ingested_at': entry.get('metadata', {}).get('ingested_at', 'unknown'),
                    'size': entry.get('metadata', {}).get('content_hash', 'unknown'),
                    'metadata': entry.get('metadata', {})
                }
                summaries.append(summary)

            logger.info(f"Listed {len(summaries)} documents")
            return summaries

        except Exception as exc:
            logger.error(f"Error listing documents: {exc}")
            return []

    def _generate_document_id(self, content: Any, document_type: str) -> str:
        """
        Generate a unique document ID.

        Args:
            content: Document content
            document_type: Type of document

        Returns:
            Unique document ID
        """
        content_hash = self._compute_hash(str(content))
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        return f"doc_{document_type}_{timestamp}_{content_hash[:8]}"

    def _compute_hash(self, content: str) -> str:
        """
        Compute hash of content.

        Args:
            content: Content string

        Returns:
            Hash string
        """
        return hashlib.md5(content.encode(), usedforsecurity=False).hexdigest()  # content checksum only, not used for security

    def _extract_metadata(self, content: Any, document_type: str) -> Dict:
        """
        Extract metadata from document content.

        Args:
            content: Document content
            document_type: Type of document

        Returns:
            Extracted metadata
        """
        metadata = {
            'document_type': document_type,
            'extraction_timestamp': datetime.now(timezone.utc).isoformat()
        }

        try:
            content_str = str(content)

            # Extract basic statistics
            metadata['content_length'] = len(content_str)
            metadata['word_count'] = len(content_str.split())

            # Type-specific extraction
            if document_type == 'json':
                try:
                    json_data = json.loads(content_str) if isinstance(content_str, str) else content
                    metadata['json_keys'] = list(json_data.keys()) if isinstance(json_data, dict) else []
                    metadata['is_json_valid'] = True
                except Exception as exc:
                    logger.debug("Suppressed exception: %s", exc)
                    metadata['is_json_valid'] = False

            elif document_type == 'text':
                # Extract potential titles
                lines = content_str.split('\n')
                if lines:
                    first_line = lines[0].strip()
                    if len(first_line) < 100 and len(first_line.split()) <= 15:
                        metadata['potential_title'] = first_line

            # Language detection (simple heuristic)
            if content_str:
                metadata['has_alpha_chars'] = any(c.isalpha() for c in content_str)
                metadata['has_numeric_chars'] = any(c.isdigit() for c in content_str)

        except Exception as exc:
            logger.error(f"Error extracting metadata: {exc}")

        return metadata

    def _register_default_pipelines(self):
        """Register default document processing pipelines."""

        def text_pipeline(content):
            """Process text documents."""
            if isinstance(content, str):
                # Basic text normalization
                processed = content.strip()
                return processed
            return content

        def json_pipeline(content):
            """Process JSON documents."""
            try:
                if isinstance(content, str):
                    return json.loads(content)
                elif isinstance(content, dict):
                    return content
                return content
            except Exception as exc:
                logger.debug("Suppressed exception: %s", exc)
                return content

        # Register pipelines
        self.processing_pipelines['text'] = text_pipeline
        self.processing_pipelines['json'] = json_pipeline

        logger.info(f"Registered {len(self.processing_pipelines)} default processing pipelines")

    def register_pipeline(self, name: str, pipeline: callable):
        """
        Register a custom processing pipeline.

        Args:
            name: Pipeline name
            pipeline: Processing function
        """
        self.processing_pipelines[name] = pipeline
        logger.info(f"Registered custom pipeline: {name}")

    def get_statistics(self) -> Dict:
        """
        Get document manager statistics.

        Returns:
            Dictionary with statistics
        """
        doc_types = {}
        total_size = 0

        for doc_info in self.document_registry.values():
            doc_type = doc_info['type']
            doc_types[doc_type] = doc_types.get(doc_type, 0) + 1
            total_size += doc_info.get('size', 0)

        return {
            'total_documents': len(self.document_registry),
            'document_types': doc_types,
            'total_size_bytes': total_size,
            'processing_pipelines': list(self.processing_pipelines.keys())
        }
