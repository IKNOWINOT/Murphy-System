# Librarian

The `librarian` package implements Murphy's knowledge management subsystem.
It indexes all system knowledge, answers semantic queries, and powers the
`POST /api/librarian/query` endpoint that routes capability requests.

## Key Modules

| Module | Purpose |
|--------|---------|
| `librarian_module.py` | `SystemLibrarian` — primary query interface |
| `knowledge_base.py` | In-memory and persisted knowledge-base store |
| `document_manager.py` | CRUD for knowledge documents with versioning |
| `semantic_search.py` | Embedding-based semantic search over the knowledge base |

## Usage

```python
from librarian.librarian_module import SystemLibrarian
librarian = SystemLibrarian()
results = librarian.query("how do I configure email integration?")
```
