# Librarian Component

## Overview

The Librarian component provides comprehensive knowledge management capabilities for the Murphy System Runtime. It handles document storage, semantic search, knowledge base management, and information retrieval across the entire system.

## Architecture

### Core Components

#### 1. LibrarianModule (`src/librarian/librarian_module.py`)
The main module interface for librarian operations.

**Key Features:**
- Unified knowledge management interface
- Document ingestion and storage
- Semantic search capabilities
- Knowledge graph management

**API Methods:**
```python
add_document(document, metadata=None)
search(query, limit=10)
get_document(document_id)
update_document(document_id, updates)
delete_document(document_id)
get_knowledge_summary()
```

#### 2. KnowledgeBase (`src/librarian/knowledge_base.py`)
Core knowledge storage and retrieval system.

**Key Features:**
- Document storage with metadata
- Knowledge graph relationships
- Efficient indexing and retrieval
- Version control for documents

**API Methods:**
```python
store_document(document, metadata)
retrieve_document(document_id)
search_documents(query)
add_relationship(doc1_id, doc2_id, relation_type)
get_related_documents(document_id)
```

#### 3. SemanticSearch (`src/librarian/semantic_search.py`)
Advanced semantic search capabilities.

**Key Features:**
- Vector-based similarity search
- Natural language understanding
- Context-aware results
- Ranking and scoring

**API Methods:**
```python
search(query, filters=None, limit=10)
semantic_similarity(query1, query2)
get_context(document_id, window=5)
expand_query(query)
```

#### 4. DocumentManager (`src/librarian/document_manager.py`)
Document lifecycle management.

**Key Features:**
- Document ingestion
- Metadata extraction
- Document processing
- Lifecycle management

**API Methods:**
```python
ingest_document(source, format='text')
extract_metadata(document)
process_document(document)
validate_document(document)
archive_document(document_id)
```

## Usage Examples

### Adding Documents

```python
from src.system_integrator import SystemIntegrator

integrator = SystemIntegrator()

# Add a simple text document
document = {
    "content": "The Murphy System Runtime provides enterprise-grade AI capabilities.",
    "title": "System Overview",
    "author": "Corey Post InonI LLC"
}

metadata = {
    "category": "documentation",
    "tags": ["overview", "enterprise", "AI"],
    "created": "2024-01-01"
}

doc_id = integrator.librarian_adapter.add_document(document, metadata)
print(f"Document added with ID: {doc_id}")
```

### Searching Documents

```python
# Simple search
results = integrator.librarian_adapter.search("enterprise AI capabilities", limit=5)

for result in results:
    print(f"Score: {result['score']}")
    print(f"Title: {result['document']['title']}")
    print(f"Content: {result['document']['content'][:100]}...")
```

### Semantic Search

```python
# Semantic search with context
results = integrator.librarian_adapter.semantic_search(
    query="How does the system handle large organizations?",
    filters={"category": "documentation"},
    limit=3
)

for result in results:
    print(f"Relevance: {result['relevance']}")
    print(f"Summary: {result['summary']}")
```

### Knowledge Graph Operations

```python
# Add relationship between documents
integrator.librarian_adapter.knowledge_base.add_relationship(
    doc1_id="doc1",
    doc2_id="doc2",
    relation_type="references"
)

# Get related documents
related = integrator.librarian_adapter.knowledge_base.get_related_documents(
    document_id="doc1",
    relation_type="references"
)
```

## Document Types

### Text Documents
- Plain text files
- Markdown documents
- HTML content
- JSON/YAML data

### Structured Documents
- Configuration files
- Data schemas
- API specifications
- Workflow definitions

### Binary Documents
- PDF files
- Images
- Archives
- Executables

## Search Capabilities

### Keyword Search
- Exact phrase matching
- Boolean operators (AND, OR, NOT)
- Wildcard support
- Field-specific search

### Semantic Search
- Vector similarity
- Context understanding
- Query expansion
- Relevance ranking

### Hybrid Search
- Combines keyword and semantic search
- Weighted scoring
- Multiple ranking strategies
- Result diversification

## Knowledge Graph

### Relationship Types
- **references**: Document A references Document B
- **contains**: Document A contains Document B
- **extends**: Document A extends Document B
- **implements**: Document A implements Document B
- **related**: General relationship

### Graph Operations
```python
# Add relationship
librarian.add_relationship(doc1, doc2, "references")

# Get related documents
related = librarian.get_related_documents(doc1, max_depth=2)

# Find paths between documents
paths = librarian.find_path(doc1, doc2)

# Get graph statistics
stats = librarian.get_graph_statistics()
```

## Performance Characteristics

### Storage Performance
- **Document Ingestion**: <100ms per document
- **Indexing**: <50ms per document
- **Metadata Extraction**: <20ms per document

### Search Performance
- **Keyword Search**: <10ms (simple), <50ms (complex)
- **Semantic Search**: <100ms (simple), <500ms (complex)
- **Knowledge Graph Queries**: <200ms (shallow), <1s (deep)

### Scalability
- **Document Storage**: 100,000+ documents
- **Search Queries**: 1,000+ queries/second
- **Knowledge Graph**: 10,000+ nodes, 50,000+ edges

## Configuration

### Environment Variables
```bash
# Enable/disable librarian
LIBRARIAN_ENABLED=true

# Storage settings
LIBRARIAN_STORAGE_PATH=./data/librarian
LIBRARIAN_MAX_DOCUMENT_SIZE=10485760  # 10MB

# Search settings
LIBRARIAN_SEARCH_LIMIT=100
LIBRARIAN_SEMANTIC_SEARCH_ENABLED=true

# Knowledge graph settings
LIBRARIAN_KNOWLEDGE_GRAPH_ENABLED=true
```

### Configuration File
```yaml
librarian:
  enabled: true
  
  storage:
    path: ./data/librarian
    max_document_size: 10485760
    compression: true
  
  search:
    default_limit: 100
    semantic_enabled: true
    ranking_algorithm: bm25
  
  knowledge_graph:
    enabled: true
    auto_link: true
    max_depth: 3
  
  processing:
    extract_metadata: true
    auto_tag: true
    validate: true
```

## Best Practices

### 1. Use Rich Metadata
```python
# Good
metadata = {
    "title": "System Architecture Guide",
    "author": "Corey Post InonI LLC",
    "category": "documentation",
    "tags": ["architecture", "enterprise", "scalability"],
    "version": "2.0",
    "language": "en",
    "created": "2024-01-01",
    "updated": "2024-01-15"
}

# Avoid
metadata = {
    "title": "Guide"
}
```

### 2. Structure Documents Well
```python
# Use clear structure
document = {
    "title": "System Architecture",
    "summary": "Overview of system architecture",
    "sections": [
        {
            "heading": "Introduction",
            "content": "..."
        },
        {
            "heading": "Components",
            "content": "..."
        }
    ],
    "appendices": [...]
}
```

### 3. Use Appropriate Search Queries
```python
# Specific query
results = librarian.search("enterprise architecture scalability")

# With filters
results = librarian.search(
    query="architecture",
    filters={"category": "documentation", "language": "en"}
)

# Semantic search
results = librarian.semantic_search(
    query="How does the system scale?",
    context="enterprise"
)
```

### 4. Manage Knowledge Graph
```python
# Add meaningful relationships
librarian.add_relationship(doc1, doc2, "references")
librarian.add_relationship(doc3, doc1, "extends")

# Use relationship metadata
librarian.add_relationship(
    doc1, doc2, 
    "references",
    metadata={"strength": 0.9, "context": "architectural"}
)
```

### 5. Monitor Performance
```python
# Get statistics
stats = librarian.get_statistics()
print(f"Total documents: {stats['total_documents']}")
print(f"Search performance: {stats['avg_search_time']}ms")

# Get knowledge graph stats
graph_stats = librarian.get_graph_statistics()
print(f"Nodes: {graph_stats['nodes']}")
print(f"Edges: {graph_stats['edges']}")
```

## Troubleshooting

### Slow Search Performance
**Symptoms**: Search queries taking >500ms

**Solutions:**
1. Rebuild indexes
2. Reduce search limit
3. Use filters to narrow results
4. Optimize document structure
5. Increase caching

### Poor Search Results
**Symptoms**: Irrelevant or missing results

**Solutions:**
1. Improve document metadata
2. Use semantic search
3. Adjust ranking algorithm
4. Add more tags/categories
5. Clean up duplicate content

### Knowledge Graph Issues
**Symptoms**: Incorrect or missing relationships

**Solutions:**
1. Verify relationship types
2. Check document IDs
3. Rebuild graph index
4. Use explicit relationship creation
5. Validate graph integrity

### Storage Problems
**Symptoms**: Documents not storing or retrieving

**Solutions:**
1. Check storage permissions
2. Verify storage path
3. Check disk space
4. Validate document format
5. Review error logs

## Integration Examples

### With SystemIntegrator
```python
from src.system_integrator import SystemIntegrator

integrator = SystemIntegrator()

# Add system documentation
system_doc = {
    "title": "System Overview",
    "content": "The Murphy System Runtime..."
}

integrator.librarian_adapter.add_document(
    system_doc,
    metadata={"type": "system_doc"}
)

# Search for relevant information
results = integrator.librarian_adapter.search("enterprise capabilities")
```

### With ConfidenceEngine
```python
# Use librarian for knowledge validation
query = "How to optimize for 1000+ roles?"
results = integrator.librarian_adapter.search(query, limit=5)

# Use results for confidence scoring
confidence = integrator.confidence.calculate_confidence(
    context="knowledge_validation",
    evidence=results
)
```

### With LearningSystem
```python
# Learn from document patterns
documents = integrator.librarian_adapter.get_all_documents()
patterns = integrator.learning.analyze_documents(documents)

# Improve search based on patterns
integrator.librarian_adapter.improve_search(patterns)
```

## API Reference

### add_document()
Add a document to the knowledge base.

**Parameters:**
- `document` (dict): Document content and structure
- `metadata` (dict, optional): Document metadata

**Returns:** Document ID (str)

### search()
Search for documents.

**Parameters:**
- `query` (str): Search query
- `filters` (dict, optional): Search filters
- `limit` (int, optional): Maximum results (default: 10)

**Returns:** List of search results with scores

### get_document()
Retrieve a document by ID.

**Parameters:**
- `document_id` (str): Document ID

**Returns:** Document dictionary

### update_document()
Update an existing document.

**Parameters:**
- `document_id` (str): Document ID
- `updates` (dict): Updates to apply

**Returns:** Updated document

### delete_document()
Delete a document.

**Parameters:**
- `document_id` (str): Document ID

**Returns:** Success status

### get_knowledge_summary()
Get a summary of the knowledge base.

**Parameters:** None

**Returns:** Knowledge summary dictionary

## Advanced Features

### Document Versioning
```python
# Version a document
version_id = librarian.version_document(document_id)

# Get specific version
version = librarian.get_document_version(document_id, version_id)

# Compare versions
diff = librarian.compare_versions(v1_id, v2_id)
```

### Batch Operations
```python
# Batch ingest documents
documents = [doc1, doc2, doc3]
results = librarian.batch_ingest(documents)

# Batch search
queries = ["query1", "query2", "query3"]
results = librarian.batch_search(queries)
```

### Export/Import
```python
# Export knowledge base
librarian.export_knowledge("backup.json")

# Import knowledge base
librarian.import_knowledge("backup.json")
```

## Related Components

- **SystemIntegrator**: Main integration point
- **ConfidenceEngine**: Uses librarian for knowledge validation
- **LearningSystem**: Learns from document patterns
- **Telemetry**: Tracks librarian performance metrics

## License

BSL 1.1 (converts to Apache 2.0 after four years) - See LICENSE.md for details.

## Support

For issues or questions:
- Contact: corey.gfc@gmail.com
- Owner: Corey Post InonI LLC