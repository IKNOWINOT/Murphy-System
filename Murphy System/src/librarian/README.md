# `src/librarian` — Librarian Module

Knowledge base management, document storage, and semantic search for the Murphy System Runtime.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The librarian module is Murphy's long-term knowledge store and retrieval engine. The `KnowledgeBase` manages the structured collection of facts, documents, and agent-produced artifacts. `DocumentManager` handles CRUD for raw documents with metadata and versioning. `SemanticSearchEngine` enables embedding-based nearest-neighbour retrieval so agents can surface contextually relevant knowledge during reasoning. `LibrarianModule` is the top-level facade that wires all three components together and is the recommended entry point for other packages.

## Key Components

| Module | Purpose |
|--------|---------|
| `librarian_module.py` | `LibrarianModule` — top-level facade combining all librarian capabilities |
| `knowledge_base.py` | `KnowledgeBase` — structured fact and artifact storage |
| `document_manager.py` | `DocumentManager` — document CRUD with metadata and versioning |
| `semantic_search.py` | `SemanticSearchEngine` — embedding-based semantic retrieval |

## Usage

```python
from librarian import LibrarianModule

librarian = LibrarianModule()
doc_id = librarian.store_document(content="Murphy system architecture overview...", title="Arch")
results = librarian.search("how does the control plane work?", top_k=5)
for hit in results:
    print(hit.score, hit.title)
```

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*
