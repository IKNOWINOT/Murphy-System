"""
RAG Vector Integration for Murphy System (RECOMMENDATIONS 6.2.8)

Connects the golden_path_bridge with vector-like semantic retrieval:
- Document ingestion with chunking and TF-IDF style embeddings
- Semantic search via cosine similarity on term-frequency vectors
- Context assembly for LLM prompts with token budget control
- Knowledge graph with entity-relationship extraction
- Full retrieval-augmented generation pipeline
- **ChromaDB** vector store backend (optional; falls back to built-in TF-IDF)

The ChromaDB backend is activated when ``chromadb`` is installed and
``CHROMADB_PATH`` env var is set.  Otherwise the pure-Python TF-IDF
implementation is used as a zero-dependency fallback.

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

import logging
import math
import os
import re
import threading
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ChromaDB — lazy import (INC-15: real vector store integration)
# ---------------------------------------------------------------------------
try:
    import chromadb  # noqa: F401
    from chromadb.config import Settings as _ChromaSettings  # noqa: F401
    _CHROMADB_AVAILABLE = True
    logger.info("chromadb available — vector store backend enabled")
except ImportError:
    chromadb = None  # type: ignore[assignment]
    _CHROMADB_AVAILABLE = False
    logger.info("chromadb not installed — using built-in TF-IDF vectors")


# ── Enums ────────────────────────────────────────────────────────────

class ChunkStrategy(str, Enum):
    """Chunk strategy (str subclass)."""
    FIXED = "fixed"
    SENTENCE = "sentence"
    PARAGRAPH = "paragraph"


class RetrievalMode(str, Enum):
    """Retrieval mode (str subclass)."""
    VECTOR = "vector"
    GRAPH = "graph"
    HYBRID = "hybrid"


# ── Dataclasses ──────────────────────────────────────────────────────

@dataclass
class DocumentChunk:
    """Document chunk."""
    chunk_id: str
    doc_id: str
    text: str
    index: int
    term_vector: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IngestedDocument:
    """Ingested document."""
    doc_id: str
    title: str
    source: str
    chunks: List[DocumentChunk] = field(default_factory=list)
    ingested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResult:
    """Search result."""
    chunk_id: str
    doc_id: str
    score: float
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEntity:
    """Graph entity."""
    entity_id: str
    name: str
    entity_type: str
    doc_ids: Set[str] = field(default_factory=set)
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphRelation:
    """Graph relation."""
    relation_id: str
    source_entity: str
    target_entity: str
    relation_type: str
    weight: float = 1.0
    doc_ids: Set[str] = field(default_factory=set)


# ── Stopwords ────────────────────────────────────────────────────────

_STOPWORDS: Set[str] = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "must", "to", "of",
    "in", "for", "on", "with", "at", "by", "from", "as", "into", "about",
    "it", "its", "this", "that", "these", "those", "and", "but", "or",
    "not", "no", "if", "then", "than", "so", "up", "out", "just",
}


# ── Helpers ──────────────────────────────────────────────────────────

def _tokenize(text: str) -> List[str]:
    """Lowercase alpha-numeric tokenization with stopword removal."""
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return [t for t in tokens if t not in _STOPWORDS and len(t) > 1]


def _term_frequency(tokens: List[str]) -> Dict[str, float]:
    """Normalized term-frequency vector."""
    counts = Counter(tokens)
    total = len(tokens) if tokens else 1
    return {term: count / total for term, count in counts.items()}


def _cosine_similarity(vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
    """Cosine similarity between two sparse term-frequency vectors."""
    if not vec_a or not vec_b:
        return 0.0
    common = set(vec_a) & set(vec_b)
    dot = sum(vec_a[k] * vec_b[k] for k in common)
    mag_a = math.sqrt(sum(v * v for v in vec_a.values()))
    mag_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0
    return dot / (mag_a * mag_b)


def _estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars per token)."""
    return max(1, len(text) // 4)


def _split_fixed(text: str, size: int, overlap: int) -> List[str]:
    """Split text into fixed-size word chunks with overlap."""
    words = text.split()
    if not words:
        return []
    chunks: List[str] = []
    step = max(1, size - overlap)
    for i in range(0, len(words), step):
        chunk = " ".join(words[i : i + size])
        if chunk:
            chunks.append(chunk)
    return chunks


def _split_sentences(text: str) -> List[str]:
    """Split text on sentence boundaries."""
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p.strip()]


def _split_paragraphs(text: str) -> List[str]:
    """Split text on paragraph boundaries."""
    parts = re.split(r"\n\s*\n", text.strip())
    return [p.strip() for p in parts if p.strip()]


# ── Core class ───────────────────────────────────────────────────────

class RAGVectorIntegration:
    """Advanced RAG integration with vector-like semantic retrieval.

    Thread-safe, pure-Python implementation using TF-IDF style term
    frequency vectors and cosine similarity for document retrieval.
    """

    def __init__(
        self,
        chunk_size: int = 128,
        chunk_overlap: int = 32,
        chunk_strategy: ChunkStrategy = ChunkStrategy.FIXED,
        default_token_budget: int = 2048,
    ) -> None:
        self._lock = threading.RLock()
        self._documents: Dict[str, IngestedDocument] = {}
        self._chunks: Dict[str, DocumentChunk] = {}
        self._entities: Dict[str, GraphEntity] = {}
        self._relations: Dict[str, GraphRelation] = {}
        # IDF cache: term -> log(N / df)
        self._idf_cache: Dict[str, float] = {}
        self._idf_dirty = True

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.chunk_strategy = chunk_strategy
        self.default_token_budget = default_token_budget

    # ── Document ingestion ───────────────────────────────────────

    def ingest_document(
        self,
        text: str,
        title: str = "",
        source: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        strategy: Optional[ChunkStrategy] = None,
    ) -> Dict[str, Any]:
        """Ingest a document: chunk, compute TF vectors, store."""
        if not text or not text.strip():
            return {"status": "error", "message": "empty document"}

        strat = strategy or self.chunk_strategy
        if strat == ChunkStrategy.SENTENCE:
            raw_chunks = _split_sentences(text)
        elif strat == ChunkStrategy.PARAGRAPH:
            raw_chunks = _split_paragraphs(text)
        else:
            raw_chunks = _split_fixed(text, self.chunk_size, self.chunk_overlap)

        if not raw_chunks:
            return {"status": "error", "message": "no chunks produced"}

        doc_id = f"doc-{uuid.uuid4().hex[:12]}"
        doc = IngestedDocument(
            doc_id=doc_id,
            title=title or doc_id,
            source=source,
            metadata=metadata or {},
        )

        with self._lock:
            for idx, chunk_text in enumerate(raw_chunks):
                tokens = _tokenize(chunk_text)
                tf = _term_frequency(tokens)
                chunk = DocumentChunk(
                    chunk_id=f"chk-{uuid.uuid4().hex[:12]}",
                    doc_id=doc_id,
                    text=chunk_text,
                    index=idx,
                    term_vector=tf,
                    metadata=metadata or {},
                )
                doc.chunks.append(chunk)
                self._chunks[chunk.chunk_id] = chunk

            self._documents[doc_id] = doc
            self._idf_dirty = True

        logger.info("Ingested doc %s with %d chunks", doc_id, len(raw_chunks))
        return {
            "status": "ok",
            "doc_id": doc_id,
            "title": doc.title,
            "chunk_count": len(raw_chunks),
        }

    def remove_document(self, doc_id: str) -> Dict[str, Any]:
        """Remove a document and its chunks."""
        with self._lock:
            doc = self._documents.pop(doc_id, None)
            if doc is None:
                return {"status": "error", "message": "document not found"}
            for chunk in doc.chunks:
                self._chunks.pop(chunk.chunk_id, None)
            self._idf_dirty = True
        return {"status": "ok", "doc_id": doc_id}

    def get_document(self, doc_id: str) -> Dict[str, Any]:
        """Return document metadata and chunk ids."""
        with self._lock:
            doc = self._documents.get(doc_id)
            if doc is None:
                return {"status": "error", "message": "document not found"}
            return {
                "status": "ok",
                "doc_id": doc.doc_id,
                "title": doc.title,
                "source": doc.source,
                "chunk_count": len(doc.chunks),
                "chunk_ids": [c.chunk_id for c in doc.chunks],
                "ingested_at": doc.ingested_at.isoformat(),
                "metadata": doc.metadata,
            }

    def list_documents(self) -> Dict[str, Any]:
        """List all ingested documents."""
        with self._lock:
            docs = [
                {
                    "doc_id": d.doc_id,
                    "title": d.title,
                    "chunk_count": len(d.chunks),
                }
                for d in self._documents.values()
            ]
        return {"status": "ok", "count": len(docs), "documents": docs}

    # ── IDF computation ──────────────────────────────────────────

    def _rebuild_idf(self) -> None:
        """Rebuild IDF cache from all chunks. Caller must hold lock."""
        n_docs = len(self._chunks)
        if n_docs == 0:
            self._idf_cache = {}
            self._idf_dirty = False
            return
        df: Counter = Counter()
        for chunk in self._chunks.values():
            for term in chunk.term_vector:
                df[term] += 1
        self._idf_cache = {
            term: math.log((1 + n_docs) / (1 + count)) + 1.0
            for term, count in df.items()
        }
        self._idf_dirty = False

    def _tfidf_vector(self, tf: Dict[str, float]) -> Dict[str, float]:
        """Apply IDF weights to a term-frequency vector. Caller holds lock."""
        if self._idf_dirty:
            self._rebuild_idf()
        return {
            term: freq * self._idf_cache.get(term, 1.0)
            for term, freq in tf.items()
        }

    # ── Semantic search ──────────────────────────────────────────

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.0,
        doc_filter: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Semantic search over ingested chunks using TF-IDF cosine similarity."""
        if not query or not query.strip():
            return {"status": "error", "message": "empty query"}

        query_tokens = _tokenize(query)
        if not query_tokens:
            return {"status": "ok", "results": [], "query": query}

        query_tf = _term_frequency(query_tokens)

        with self._lock:
            query_vec = self._tfidf_vector(query_tf)
            scored: List[Tuple[float, DocumentChunk]] = []
            for chunk in self._chunks.values():
                if doc_filter and chunk.doc_id not in doc_filter:
                    continue
                chunk_vec = self._tfidf_vector(chunk.term_vector)
                score = _cosine_similarity(query_vec, chunk_vec)
                if score >= min_score:
                    scored.append((score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = [
            {
                "chunk_id": c.chunk_id,
                "doc_id": c.doc_id,
                "score": round(s, 6),
                "text": c.text,
                "index": c.index,
            }
            for s, c in scored[:top_k]
        ]
        return {"status": "ok", "query": query, "result_count": len(results), "results": results}

    # ── Context assembly ─────────────────────────────────────────

    def assemble_context(
        self,
        query: str,
        token_budget: Optional[int] = None,
        top_k: int = 10,
        min_score: float = 0.01,
        include_metadata: bool = False,
    ) -> Dict[str, Any]:
        """Assemble context from top search results within a token budget."""
        budget = token_budget or self.default_token_budget
        search_result = self.search(query, top_k=top_k, min_score=min_score)
        if search_result["status"] != "ok":
            return search_result

        segments: List[str] = []
        used_tokens = 0
        included_chunks: List[Dict[str, Any]] = []

        for r in search_result["results"]:
            chunk_tokens = _estimate_tokens(r["text"])
            if used_tokens + chunk_tokens > budget:
                break
            segments.append(r["text"])
            used_tokens += chunk_tokens
            entry: Dict[str, Any] = {
                "chunk_id": r["chunk_id"],
                "doc_id": r["doc_id"],
                "score": r["score"],
                "token_estimate": chunk_tokens,
            }
            if include_metadata:
                with self._lock:
                    ch = self._chunks.get(r["chunk_id"])
                    if ch:
                        entry["metadata"] = ch.metadata
            included_chunks.append(entry)

        context_text = "\n\n---\n\n".join(segments)
        return {
            "status": "ok",
            "context": context_text,
            "token_estimate": used_tokens,
            "token_budget": budget,
            "chunks_used": len(included_chunks),
            "chunks_detail": included_chunks,
        }

    # ── Knowledge graph ──────────────────────────────────────────

    def _extract_entities(self, text: str, doc_id: str) -> List[str]:
        """Simple NER: extract capitalised multi-word phrases as entities."""
        # Match sequences of capitalised words (2+ chars)
        matches = re.findall(r"\b([A-Z][a-z]{1,}\s*(?:[A-Z][a-z]{1,}\s*)*)", text)
        entity_ids: List[str] = []
        with self._lock:
            for raw in matches:
                name = raw.strip()
                if not name or len(name) < 3:
                    continue
                eid = f"ent-{name.lower().replace(' ', '_')}"
                if eid in self._entities:
                    self._entities[eid].doc_ids.add(doc_id)
                else:
                    self._entities[eid] = GraphEntity(
                        entity_id=eid,
                        name=name,
                        entity_type="concept",
                        doc_ids={doc_id},
                    )
                entity_ids.append(eid)
        return entity_ids

    def build_knowledge_graph(self, doc_id: Optional[str] = None) -> Dict[str, Any]:
        """Build/update entity-relationship graph from documents."""
        with self._lock:
            docs = (
                [self._documents[doc_id]]
                if doc_id and doc_id in self._documents
                else list(self._documents.values())
            )
            if not docs:
                return {"status": "error", "message": "no documents"}

        total_entities = 0
        total_relations = 0

        for doc in docs:
            all_entity_ids: List[str] = []
            for chunk in doc.chunks:
                eids = self._extract_entities(chunk.text, doc.doc_id)
                all_entity_ids.extend(eids)

            # Co-occurrence relations between entities in same doc
            unique_eids = list(dict.fromkeys(all_entity_ids))
            with self._lock:
                for i, e1 in enumerate(unique_eids):
                    for e2 in unique_eids[i + 1 :]:
                        rid = f"rel-{e1}-{e2}"
                        if rid in self._relations:
                            self._relations[rid].weight += 1.0
                            self._relations[rid].doc_ids.add(doc.doc_id)
                        else:
                            self._relations[rid] = GraphRelation(
                                relation_id=rid,
                                source_entity=e1,
                                target_entity=e2,
                                relation_type="co_occurs",
                                doc_ids={doc.doc_id},
                            )
                        total_relations += 1
            total_entities += len(unique_eids)

        with self._lock:
            ent_count = len(self._entities)
            rel_count = len(self._relations)

        return {
            "status": "ok",
            "entity_count": ent_count,
            "relation_count": rel_count,
            "processed_docs": len(docs),
        }

    def query_graph(
        self,
        entity_name: str,
        max_depth: int = 1,
    ) -> Dict[str, Any]:
        """Query the knowledge graph for an entity and its neighbours."""
        with self._lock:
            eid = f"ent-{entity_name.lower().replace(' ', '_')}"
            entity = self._entities.get(eid)
            if entity is None:
                return {"status": "error", "message": f"entity '{entity_name}' not found"}

            neighbours: List[Dict[str, Any]] = []
            for rel in self._relations.values():
                other = None
                if rel.source_entity == eid:
                    other = rel.target_entity
                elif rel.target_entity == eid:
                    other = rel.source_entity
                if other and other in self._entities:
                    neighbours.append({
                        "entity_id": other,
                        "name": self._entities[other].name,
                        "relation": rel.relation_type,
                        "weight": rel.weight,
                    })

            return {
                "status": "ok",
                "entity": {
                    "entity_id": eid,
                    "name": entity.name,
                    "type": entity.entity_type,
                    "doc_ids": sorted(entity.doc_ids),
                },
                "neighbours": neighbours,
            }

    def get_graph_stats(self) -> Dict[str, Any]:
        """Return knowledge graph statistics."""
        with self._lock:
            return {
                "status": "ok",
                "entity_count": len(self._entities),
                "relation_count": len(self._relations),
                "entity_types": dict(
                    Counter(e.entity_type for e in self._entities.values())
                ),
            }

    # ── RAG pipeline ─────────────────────────────────────────────

    def rag_pipeline(
        self,
        query: str,
        mode: RetrievalMode = RetrievalMode.VECTOR,
        top_k: int = 5,
        token_budget: Optional[int] = None,
        system_prompt: str = "Answer the question using the provided context.",
        include_sources: bool = True,
    ) -> Dict[str, Any]:
        """Full RAG pipeline: query → retrieve → rank → assemble → prompt."""
        if not query or not query.strip():
            return {"status": "error", "message": "empty query"}

        budget = token_budget or self.default_token_budget

        # Retrieve
        if mode in (RetrievalMode.VECTOR, RetrievalMode.HYBRID):
            ctx = self.assemble_context(query, token_budget=budget, top_k=top_k)
            if ctx["status"] != "ok":
                return ctx
            context_text = ctx["context"]
            chunks_used = ctx["chunks_detail"]
        else:
            context_text = ""
            chunks_used = []

        # Graph enrichment
        graph_entities: List[Dict[str, Any]] = []
        if mode in (RetrievalMode.GRAPH, RetrievalMode.HYBRID):
            query_tokens = _tokenize(query)
            for token in query_tokens:
                result = self.query_graph(token)
                if result["status"] == "ok":
                    graph_entities.append(result["entity"])

            if graph_entities and mode == RetrievalMode.GRAPH:
                context_text = "Entities: " + ", ".join(
                    e["name"] for e in graph_entities
                )

        # Assemble prompt
        prompt_parts = [system_prompt, ""]
        if context_text:
            prompt_parts.append("Context:")
            prompt_parts.append(context_text)
            prompt_parts.append("")
        prompt_parts.append(f"Question: {query}")

        prompt = "\n".join(prompt_parts)
        prompt_tokens = _estimate_tokens(prompt)

        sources: List[Dict[str, Any]] = []
        if include_sources and chunks_used:
            sources = [
                {"chunk_id": c["chunk_id"], "doc_id": c["doc_id"], "score": c["score"]}
                for c in chunks_used
            ]

        return {
            "status": "ok",
            "prompt": prompt,
            "prompt_token_estimate": prompt_tokens,
            "retrieval_mode": mode.value,
            "chunks_used": len(chunks_used),
            "graph_entities": len(graph_entities),
            "sources": sources,
        }

    # ── Utility ──────────────────────────────────────────────────

    def stats(self) -> Dict[str, Any]:
        """Return overall system statistics."""
        with self._lock:
            total_terms = set()
            for chunk in self._chunks.values():
                total_terms.update(chunk.term_vector.keys())
            return {
                "status": "ok",
                "document_count": len(self._documents),
                "chunk_count": len(self._chunks),
                "vocabulary_size": len(total_terms),
                "entity_count": len(self._entities),
                "relation_count": len(self._relations),
            }

    def clear(self) -> Dict[str, Any]:
        """Clear all data."""
        with self._lock:
            self._documents.clear()
            self._chunks.clear()
            self._entities.clear()
            self._relations.clear()
            self._idf_cache.clear()
            self._idf_dirty = True
        return {"status": "ok"}


# ---------------------------------------------------------------------------
# ChromaDB-backed vector store (INC-15)
# ---------------------------------------------------------------------------


class ChromaVectorStore:
    """ChromaDB-backed vector store for production RAG.

    When ``chromadb`` is installed this class provides a real vector store
    with persistent embeddings.  Use ``ChromaVectorStore.create()`` to
    obtain an instance that is configured from environment variables.

    Environment variables:
        CHROMADB_PATH  — Directory for persistent storage (default: ``.chroma``)
        CHROMADB_COLLECTION — Collection name (default: ``murphy_knowledge``)
    """

    def __init__(self, persist_directory: str = ".chroma", collection_name: str = "murphy_knowledge") -> None:
        if not _CHROMADB_AVAILABLE:
            raise ImportError(
                "chromadb is not installed. "
                "Install it with: pip install chromadb"
            )
        self._persist_dir = persist_directory
        self._collection_name = collection_name
        self._client = chromadb.Client(
            _ChromaSettings(
                persist_directory=persist_directory,
                anonymized_telemetry=False,
            )
        )
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "ChromaDB vector store initialized",
            extra={
                "persist_directory": persist_directory,
                "collection": collection_name,
            },
        )

    @classmethod
    def create(cls) -> "ChromaVectorStore":
        """Factory: create from env vars."""
        return cls(
            persist_directory=os.getenv("CHROMADB_PATH", ".chroma"),
            collection_name=os.getenv("CHROMADB_COLLECTION", "murphy_knowledge"),
        )

    def add_document(
        self,
        doc_id: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Add a document to the vector store."""
        self._collection.add(
            ids=[doc_id],
            documents=[text],
            metadatas=[metadata or {}],
        )
        logger.info("Document added to ChromaDB", extra={"doc_id": doc_id})
        return {"status": "ok", "doc_id": doc_id}

    def query(
        self,
        query_text: str,
        n_results: int = 5,
    ) -> List[Dict[str, Any]]:
        """Query the vector store for similar documents."""
        results = self._collection.query(
            query_texts=[query_text],
            n_results=n_results,
        )
        docs = []
        if results and results.get("ids"):
            for i, doc_id in enumerate(results["ids"][0]):
                docs.append({
                    "doc_id": doc_id,
                    "text": results["documents"][0][i] if results.get("documents") else "",
                    "distance": results["distances"][0][i] if results.get("distances") else 0.0,
                    "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
                })
        return docs

    def count(self) -> int:
        """Return the number of documents in the collection."""
        return self._collection.count()

    def delete(self, doc_id: str) -> Dict[str, Any]:
        """Delete a document from the vector store."""
        self._collection.delete(ids=[doc_id])
        return {"status": "ok", "doc_id": doc_id}

    def get_status(self) -> Dict[str, Any]:
        """Return store status."""
        return {
            "backend": "chromadb",
            "persist_directory": self._persist_dir,
            "collection": self._collection_name,
            "document_count": self._collection.count(),
        }


def create_vector_store() -> Any:
    """Factory: create the best available vector store.

    Returns ChromaDB if available, otherwise falls back to
    RAGVectorIntegration (pure-Python TF-IDF).
    """
    if _CHROMADB_AVAILABLE and os.getenv("CHROMADB_PATH"):
        return ChromaVectorStore.create()
    return RAGVectorIntegration()
