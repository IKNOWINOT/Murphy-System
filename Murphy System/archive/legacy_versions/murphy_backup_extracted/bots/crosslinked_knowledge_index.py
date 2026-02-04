"""Cross-linked Knowledge Index (CKI)

This advanced indexer replaces isolated document storage with an embedding-aware
semantic tag graph. Designed as an extension for LibrarianBot.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
import numpy as np
import networkx as nx

try:
    from sentence_transformers import SentenceTransformer, util
except Exception:  # pragma: no cover - optional dependency
    SentenceTransformer = None
    util = None


@dataclass
class KnowledgeNode:
    doc_id: str
    text: str
    tags: List[str]
    embedding: Optional[np.ndarray] = None


class CrosslinkedKnowledgeIndex:
    """Embedding-aware knowledge index with tag graph."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        if SentenceTransformer is None or util is None:
            raise ImportError("SentenceTransformer package required for CKI")
        self.model = SentenceTransformer(model_name)
        self.nodes: Dict[str, KnowledgeNode] = {}
        self.tag_graph = nx.Graph()

    def add_document(self, doc_id: str, text: str, tags: List[str]) -> None:
        embedding = self.model.encode(text, convert_to_tensor=True)
        node = KnowledgeNode(doc_id=doc_id, text=text, tags=tags, embedding=embedding)
        self.nodes[doc_id] = node
        for tag in tags:
            self.tag_graph.add_node(tag)
        for i in range(len(tags)):
            for j in range(i + 1, len(tags)):
                self.tag_graph.add_edge(tags[i], tags[j])

    def search(self, query: str, top_k: int = 5) -> List[str]:
        query_emb = self.model.encode(query, convert_to_tensor=True)
        scored = []
        for doc_id, node in self.nodes.items():
            if node.embedding is None:
                continue
            score = util.cos_sim(query_emb, node.embedding)[0][0].item()
            scored.append((score, doc_id))
        scored.sort(reverse=True)
        return [doc_id for _, doc_id in scored[:top_k]]

    def find_related_tags(self, tag: str, depth: int = 2) -> List[str]:
        if tag not in self.tag_graph:
            return []
        return list(nx.single_source_shortest_path_length(self.tag_graph, tag, cutoff=depth).keys())


if __name__ == "__main__":  # pragma: no cover - simple usage example
    index = CrosslinkedKnowledgeIndex()
    index.add_document("doc1", "How to start a fire with friction", ["survival", "fire", "manual"])
    index.add_document("doc2", "Building a solar oven", ["survival", "cooking", "solar"])
    print(index.search("fire cooking"))
    print(index.find_related_tags("survival"))
