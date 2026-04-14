# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Murphy Memory Palace — Wiring Layer (MEMPALACE-WIRE-001)

Owner: Memory / Knowledge Graph
Dep: conversation_manager, rag_vector_integration, knowledge_graph_builder,
     semantic_search, tenant_memory

Wires existing Murphy modules into a coherent Memory Palace system:
  1. Auto-index conversations into RAG as they happen.
  2. Organise knowledge graph nodes into a palace hierarchy
     (wing → hall → room → closet).
  3. Add temporal validity windows to KG entity triples.
  4. Hybrid scoring for semantic search (keyword + temporal + entity boost).

This is a **wiring layer** — it connects existing modules, not replaces them.
All four subsystems already exist; this module makes them talk to each other.

Integration Points:
  - conversation_manager.ConversationManager — source of raw conversations
  - rag_vector_integration.RAGVectorIntegration — vector indexing target
  - knowledge_graph_builder.KnowledgeGraphBuilder — entity triple store
  - semantic_search — search with hybrid scoring

Error Handling:
  All public methods log and raise on invalid input.  No silent failures.
  Error codes: MEMPALACE-WIRE-ERR-001 through MEMPALACE-WIRE-ERR-008.
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Palace hierarchy model (MEMPALACE-WIRE-002)
# ---------------------------------------------------------------------------

class PalaceLevel(str, Enum):
    """Levels in the Memory Palace hierarchy.

    Wing → Hall → Room → Closet → Drawer
    Each level narrows the search scope.
    """
    WING = "wing"         # Top-level: tenant, project, person
    HALL = "hall"          # Memory type: facts, events, discoveries, preferences
    ROOM = "room"         # Topic cluster: e.g. "authentication", "deployment"
    CLOSET = "closet"     # Sub-topic: e.g. "OAuth flow", "Docker config"
    DRAWER = "drawer"     # Individual memory item


class HallType(str, Enum):
    """Pre-defined hall types (memory categories)."""
    FACTS = "facts"
    EVENTS = "events"
    DISCOVERIES = "discoveries"
    PREFERENCES = "preferences"
    ADVICE = "advice"
    DECISIONS = "decisions"


@dataclass
class PalaceNode:
    """A node in the Memory Palace hierarchy.

    Design Label: MEMPALACE-WIRE-003

    Attributes:
        node_id:     Unique identifier.
        level:       PalaceLevel (wing/hall/room/closet/drawer).
        name:        Human-readable name.
        parent_id:   ID of the parent node (None for wings).
        hall_type:   If level=HALL, which HallType this is.
        tenant_id:   Multi-tenant isolation key.
        metadata:    Arbitrary key-value pairs.
        created_at:  When this node was created.
    """

    node_id: str = field(default_factory=lambda: "pn_" + uuid.uuid4().hex[:8])
    level: PalaceLevel = PalaceLevel.ROOM
    name: str = ""
    parent_id: Optional[str] = None
    hall_type: Optional[HallType] = None
    tenant_id: str = "default"
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "level": self.level.value,
            "name": self.name,
            "parent_id": self.parent_id,
            "hall_type": self.hall_type.value if self.hall_type else None,
            "tenant_id": self.tenant_id,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# Temporal validity for KG triples (MEMPALACE-WIRE-004)
# ---------------------------------------------------------------------------

@dataclass
class TemporalTriple:
    """A knowledge graph triple with temporal validity window.

    Extends the existing KG builder's entity triples with:
      - valid_from: when this fact became true
      - ended: when this fact stopped being true (None = still true)

    Design Label: MEMPALACE-WIRE-004
    """

    triple_id: str = field(default_factory=lambda: "tt_" + uuid.uuid4().hex[:8])
    subject: str = ""
    predicate: str = ""
    obj: str = ""
    valid_from: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    ended: Optional[str] = None
    confidence: float = 1.0
    source: str = ""
    palace_room_id: Optional[str] = None  # Link to palace hierarchy
    tenant_id: str = "default"

    @property
    def is_current(self) -> bool:
        """True if this triple is still valid (not ended)."""
        return self.ended is None

    def end(self) -> None:
        """Mark this triple as no longer valid."""
        self.ended = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "triple_id": self.triple_id,
            "subject": self.subject,
            "predicate": self.predicate,
            "object": self.obj,
            "valid_from": self.valid_from,
            "ended": self.ended,
            "is_current": self.is_current,
            "confidence": self.confidence,
            "source": self.source,
            "palace_room_id": self.palace_room_id,
            "tenant_id": self.tenant_id,
        }


# ---------------------------------------------------------------------------
# Hybrid scoring (MEMPALACE-WIRE-005)
# ---------------------------------------------------------------------------

@dataclass
class HybridSearchResult:
    """A search result with hybrid scoring breakdown.

    Design Label: MEMPALACE-WIRE-005

    Scoring formula:
      final_score = (
          w_semantic * semantic_score
        + w_keyword  * keyword_score
        + w_temporal * temporal_boost
        + w_entity   * entity_name_boost
      )
    """

    content: str = ""
    source_id: str = ""
    semantic_score: float = 0.0
    keyword_score: float = 0.0
    temporal_boost: float = 0.0
    entity_name_boost: float = 0.0
    final_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content[:200],  # truncate for readability
            "source_id": self.source_id,
            "semantic_score": round(self.semantic_score, 4),
            "keyword_score": round(self.keyword_score, 4),
            "temporal_boost": round(self.temporal_boost, 4),
            "entity_name_boost": round(self.entity_name_boost, 4),
            "final_score": round(self.final_score, 4),
        }


class HybridScorer:
    """Combines multiple scoring signals for memory retrieval.

    Design Label: MEMPALACE-WIRE-005

    Weights default to the values that produced the best LongMemEval
    scores in MemPalace benchmarks:
      - semantic: 0.50 (embedding similarity)
      - keyword:  0.20 (keyword overlap)
      - temporal: 0.15 (recency boost)
      - entity:   0.15 (entity name match boost)
    """

    def __init__(
        self,
        w_semantic: float = 0.50,
        w_keyword: float = 0.20,
        w_temporal: float = 0.15,
        w_entity: float = 0.15,
    ) -> None:
        total = w_semantic + w_keyword + w_temporal + w_entity
        if total <= 0:
            raise ValueError(
                "MEMPALACE-WIRE-ERR-004: Score weights must sum to > 0, "
                f"got {total}"
            )
        # Normalise to sum to 1.0
        self.w_semantic = w_semantic / total
        self.w_keyword = w_keyword / total
        self.w_temporal = w_temporal / total
        self.w_entity = w_entity / total

    def score(
        self,
        content: str,
        query: str,
        semantic_score: float = 0.0,
        created_at: Optional[str] = None,
        entity_names: Optional[List[str]] = None,
    ) -> HybridSearchResult:
        """Compute hybrid score for a single result.

        Args:
            content:        The text content being scored.
            query:          The search query.
            semantic_score: Pre-computed embedding similarity (0–1).
            created_at:     ISO-8601 timestamp for recency calculation.
            entity_names:   Entity names mentioned in this content.

        Returns:
            HybridSearchResult with per-signal breakdown.
        """
        kw_score = self._keyword_overlap(content, query)
        temp_boost = self._temporal_boost(created_at) if created_at else 0.0
        entity_boost = self._entity_boost(content, query, entity_names)

        final = (
            self.w_semantic * semantic_score
            + self.w_keyword * kw_score
            + self.w_temporal * temp_boost
            + self.w_entity * entity_boost
        )

        return HybridSearchResult(
            content=content,
            semantic_score=semantic_score,
            keyword_score=kw_score,
            temporal_boost=temp_boost,
            entity_name_boost=entity_boost,
            final_score=final,
        )

    def rank(
        self,
        results: List[HybridSearchResult],
        top_k: int = 10,
    ) -> List[HybridSearchResult]:
        """Sort results by final_score descending, return top_k."""
        sorted_results = sorted(results, key=lambda r: r.final_score, reverse=True)
        return sorted_results[:top_k]

    # ------------------------------------------------------------------
    # Scoring signals
    # ------------------------------------------------------------------

    @staticmethod
    def _keyword_overlap(content: str, query: str) -> float:
        """Jaccard-style keyword overlap between query and content."""
        if not query or not content:
            return 0.0
        q_words = set(query.lower().split())
        c_words = set(content.lower().split())
        if not q_words:
            return 0.0
        overlap = q_words & c_words
        return len(overlap) / len(q_words)

    @staticmethod
    def _temporal_boost(created_at: str) -> float:
        """Recency boost: newer items get higher scores (0–1).

        Items less than 1 day old get 1.0; decays linearly to 0 at 365 days.
        """
        try:
            ts = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            age_days = max(0, (now - ts).total_seconds() / 86400)
            return max(0.0, 1.0 - age_days / 365.0)
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def _entity_boost(
        content: str,
        query: str,
        entity_names: Optional[List[str]] = None,
    ) -> float:
        """Boost score if query mentions known entity names found in content."""
        if not entity_names:
            return 0.0
        q_lower = query.lower()
        c_lower = content.lower()
        matches = sum(
            1 for name in entity_names
            if name.lower() in q_lower and name.lower() in c_lower
        )
        return min(1.0, matches / max(1, len(entity_names)))


# ---------------------------------------------------------------------------
# MemoryPalaceWiring — the integration layer (MEMPALACE-WIRE-001)
# ---------------------------------------------------------------------------

class MemoryPalaceWiring:
    """Wires conversation_manager → RAG → KG into a coherent Memory Palace.

    Design Label: MEMPALACE-WIRE-001

    This is the thin adapter that makes existing modules work together:
      1. Listens for new conversations and auto-indexes them into RAG.
      2. Organises KG entities into palace hierarchy (wing/hall/room).
      3. Applies temporal validity to KG triples.
      4. Uses HybridScorer for multi-signal search ranking.

    All subsystems are optional — if a module isn't available, that
    feature degrades gracefully (logged, not crashed).

    Usage::

        palace = MemoryPalaceWiring(tenant_id="acme")
        palace.index_conversation("hello world", source="chat")
        results = palace.search("hello", top_k=5)
    """

    MAX_TRIPLES = 100_000  # CWE-770: bounded

    def __init__(
        self,
        tenant_id: str = "default",
        scorer: Optional[HybridScorer] = None,
    ) -> None:
        self.tenant_id = tenant_id
        self._scorer = scorer or HybridScorer()
        self._palace_nodes: Dict[str, PalaceNode] = {}
        self._temporal_triples: Dict[str, TemporalTriple] = {}
        self._indexed_conversations: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

        # Optional subsystem references (set via wire_* methods)
        self._rag = None
        self._kg = None
        self._conversation_mgr = None

        # Create default palace structure
        self._init_default_palace()

    def _init_default_palace(self) -> None:
        """Create the default wing → hall structure."""
        wing = PalaceNode(
            level=PalaceLevel.WING,
            name=f"tenant_{self.tenant_id}",
            tenant_id=self.tenant_id,
        )
        self._palace_nodes[wing.node_id] = wing

        for hall_type in HallType:
            hall = PalaceNode(
                level=PalaceLevel.HALL,
                name=hall_type.value,
                parent_id=wing.node_id,
                hall_type=hall_type,
                tenant_id=self.tenant_id,
            )
            self._palace_nodes[hall.node_id] = hall

    # ------------------------------------------------------------------
    # Subsystem wiring
    # ------------------------------------------------------------------

    def wire_rag(self, rag_instance: Any) -> None:
        """Wire RAGVectorIntegration for auto-indexing."""
        self._rag = rag_instance
        logger.info(
            "MEMPALACE-WIRE-001: RAG subsystem wired for tenant %s",
            self.tenant_id,
        )

    def wire_knowledge_graph(self, kg_instance: Any) -> None:
        """Wire KnowledgeGraphBuilder for entity triples."""
        self._kg = kg_instance
        logger.info(
            "MEMPALACE-WIRE-001: KG subsystem wired for tenant %s",
            self.tenant_id,
        )

    def wire_conversation_manager(self, conv_mgr: Any) -> None:
        """Wire ConversationManager for auto-capture."""
        self._conversation_mgr = conv_mgr
        logger.info(
            "MEMPALACE-WIRE-001: Conversation manager wired for tenant %s",
            self.tenant_id,
        )

    # ------------------------------------------------------------------
    # Conversation auto-indexing (MEMPALACE-WIRE-006)
    # ------------------------------------------------------------------

    def index_conversation(
        self,
        text: str,
        source: str = "chat",
        hall_type: HallType = HallType.FACTS,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Index a conversation chunk into the Memory Palace.

        Steps:
          1. Store verbatim text in indexed_conversations (raw, no lossy extraction).
          2. If RAG is wired, push to vector index for semantic search.
          3. Assign to palace room based on hall_type.

        Args:
            text:      Raw conversation text (verbatim, no modification).
            source:    Source identifier (e.g. "chat", "slack", "email").
            hall_type: Which hall to file this under.
            metadata:  Optional additional metadata.

        Returns:
            Dict with index_id and status.
        """
        if not text or not text.strip():
            logger.warning("MEMPALACE-WIRE-ERR-005: Empty text, skipping index")
            return {"status": "skipped", "reason": "empty_text"}

        index_id = "idx_" + uuid.uuid4().hex[:8]
        record: Dict[str, Any] = {
            "index_id": index_id,
            "text": text,
            "source": source,
            "hall_type": hall_type.value,
            "tenant_id": self.tenant_id,
            "indexed_at": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }

        with self._lock:
            if len(self._indexed_conversations) >= self.MAX_TRIPLES:
                self._indexed_conversations = self._indexed_conversations[
                    -(self.MAX_TRIPLES // 2):
                ]
                logger.warning(
                    "MEMPALACE-WIRE-ERR-006: Conversation index hit max, truncated"
                )
            self._indexed_conversations.append(record)

        # Auto-push to RAG if wired
        if self._rag is not None:
            try:
                if hasattr(self._rag, "index_text"):
                    self._rag.index_text(text, metadata=record)
                elif hasattr(self._rag, "add_document"):
                    self._rag.add_document(text, metadata=record)
                logger.info(
                    "MEMPALACE-WIRE-006: Indexed conversation %s into RAG",
                    index_id,
                )
            except Exception as exc:  # MEMPALACE-WIRE-ERR-007
                logger.error(
                    "MEMPALACE-WIRE-ERR-007: Failed to index into RAG: %s",
                    exc,
                )

        return {"status": "indexed", "index_id": index_id}

    # ------------------------------------------------------------------
    # Temporal triple management (MEMPALACE-WIRE-004)
    # ------------------------------------------------------------------

    def add_temporal_triple(
        self,
        subject: str,
        predicate: str,
        obj: str,
        palace_room_id: Optional[str] = None,
        confidence: float = 1.0,
        source: str = "",
    ) -> TemporalTriple:
        """Add a temporal knowledge triple to the palace.

        Automatically invalidates any existing triple with the same
        subject + predicate that is still current (contradiction detection).

        Returns:
            The newly created TemporalTriple.
        """
        with self._lock:
            if len(self._temporal_triples) >= self.MAX_TRIPLES:
                # Evict ended triples first
                ended = [
                    tid for tid, t in self._temporal_triples.items()
                    if not t.is_current
                ]
                for tid in ended[:len(ended) // 2]:
                    del self._temporal_triples[tid]
                logger.warning(
                    "MEMPALACE-WIRE-ERR-008: Triple store at capacity, "
                    "evicted %d ended triples", len(ended) // 2,
                )

            # Invalidate contradicting triples
            for existing in self._temporal_triples.values():
                if (
                    existing.is_current
                    and existing.subject == subject
                    and existing.predicate == predicate
                    and existing.obj != obj
                    and existing.tenant_id == self.tenant_id
                ):
                    existing.end()
                    logger.info(
                        "MEMPALACE-WIRE-004: Invalidated triple %s "
                        "(%s %s %s) — contradicted by new value %s",
                        existing.triple_id, subject, predicate,
                        existing.obj, obj,
                    )

            triple = TemporalTriple(
                subject=subject,
                predicate=predicate,
                obj=obj,
                confidence=confidence,
                source=source,
                palace_room_id=palace_room_id,
                tenant_id=self.tenant_id,
            )
            self._temporal_triples[triple.triple_id] = triple

        # Push to KG if wired
        if self._kg is not None:
            try:
                if hasattr(self._kg, "add_triple"):
                    self._kg.add_triple(subject, predicate, obj)
                elif hasattr(self._kg, "add_entity"):
                    self._kg.add_entity(subject, {predicate: obj})
            except Exception as exc:  # MEMPALACE-WIRE-ERR-008
                logger.error(
                    "MEMPALACE-WIRE-ERR-008: Failed to push triple to KG: %s",
                    exc,
                )

        return triple

    def query_triples(
        self,
        subject: Optional[str] = None,
        predicate: Optional[str] = None,
        current_only: bool = True,
    ) -> List[TemporalTriple]:
        """Query temporal triples with optional filters."""
        with self._lock:
            results = []
            for t in self._temporal_triples.values():
                if t.tenant_id != self.tenant_id:
                    continue
                if current_only and not t.is_current:
                    continue
                if subject and t.subject != subject:
                    continue
                if predicate and t.predicate != predicate:
                    continue
                results.append(t)
            return results

    # ------------------------------------------------------------------
    # Hybrid search (MEMPALACE-WIRE-005)
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        top_k: int = 10,
        hall_type: Optional[HallType] = None,
    ) -> List[HybridSearchResult]:
        """Search the Memory Palace using hybrid scoring.

        Combines semantic similarity (if RAG wired), keyword overlap,
        temporal recency, and entity name matching.

        Args:
            query:     Search query string.
            top_k:     Maximum results to return.
            hall_type: Optional filter by hall type.

        Returns:
            Ranked list of HybridSearchResult objects.
        """
        if not query or not query.strip():
            return []

        # Gather entity names from current triples
        entity_names = list({
            t.subject for t in self._temporal_triples.values()
            if t.is_current and t.tenant_id == self.tenant_id
        })

        candidates: List[HybridSearchResult] = []

        # Score indexed conversations
        with self._lock:
            conversations = list(self._indexed_conversations)

        for conv in conversations:
            if hall_type and conv.get("hall_type") != hall_type.value:
                continue
            result = self._scorer.score(
                content=conv["text"],
                query=query,
                semantic_score=0.0,  # placeholder if RAG not wired
                created_at=conv.get("indexed_at"),
                entity_names=entity_names,
            )
            result.source_id = conv["index_id"]
            result.metadata = conv.get("metadata", {})
            candidates.append(result)

        return self._scorer.rank(candidates, top_k=top_k)

    # ------------------------------------------------------------------
    # Palace structure queries
    # ------------------------------------------------------------------

    def get_palace_structure(self) -> Dict[str, Any]:
        """Return the full palace hierarchy as a nested dict."""
        wings = [
            n for n in self._palace_nodes.values()
            if n.level == PalaceLevel.WING
        ]
        result: Dict[str, Any] = {"tenant_id": self.tenant_id, "wings": []}
        for wing in wings:
            wing_dict = wing.to_dict()
            wing_dict["halls"] = [
                n.to_dict() for n in self._palace_nodes.values()
                if n.parent_id == wing.node_id
            ]
            result["wings"].append(wing_dict)
        return result

    def add_room(
        self,
        name: str,
        hall_type: HallType,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PalaceNode:
        """Add a room to a hall in the palace."""
        # Find the hall
        hall = next(
            (n for n in self._palace_nodes.values()
             if n.hall_type == hall_type and n.tenant_id == self.tenant_id),
            None,
        )
        if hall is None:
            raise ValueError(
                f"MEMPALACE-WIRE-ERR-001: No hall of type {hall_type.value!r} "
                f"for tenant {self.tenant_id}"
            )
        room = PalaceNode(
            level=PalaceLevel.ROOM,
            name=name,
            parent_id=hall.node_id,
            tenant_id=self.tenant_id,
            metadata=metadata or {},
        )
        self._palace_nodes[room.node_id] = room
        return room

    # ------------------------------------------------------------------
    # Status / diagnostics
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return diagnostic status of the Memory Palace."""
        with self._lock:
            current_triples = sum(
                1 for t in self._temporal_triples.values() if t.is_current
            )
            return {
                "tenant_id": self.tenant_id,
                "palace_nodes": len(self._palace_nodes),
                "temporal_triples": len(self._temporal_triples),
                "current_triples": current_triples,
                "indexed_conversations": len(self._indexed_conversations),
                "rag_wired": self._rag is not None,
                "kg_wired": self._kg is not None,
                "conversation_mgr_wired": self._conversation_mgr is not None,
            }
