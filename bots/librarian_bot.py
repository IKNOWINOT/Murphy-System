"""LibrarianBot with caching and tag search."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Any
import numpy as np
from cachetools import TTLCache
from functools import lru_cache
from .crypto_utils import encrypt_payload, decrypt_payload
import aiohttp
import asyncio

try:
    from sentence_transformers import SentenceTransformer, util
except Exception:  # pragma: no cover - heavy dep optional
    SentenceTransformer = None  # type: ignore
    util = None

@dataclass
class Document:
    id: int
    text: str
    tags: List[str] = field(default_factory=list)
    embedding: List[float] | None = None


memory_cache = TTLCache(maxsize=1024, ttl=3600)


class LibrarianBot:
    def __init__(self, model_name: str = 'sentence-transformers/LaBSE', *, ttl: int = 600, enc_key: bytes | None = None) -> None:
        self.cache: TTLCache[str, List[Document]] = TTLCache(maxsize=256, ttl=ttl)
        self.docs: Dict[int, Document] = {}
        self.enc_key = enc_key
        if SentenceTransformer is not None:
            self.model = SentenceTransformer(model_name)
        else:
            self.model = None

    def add_document(self, doc: Document) -> None:
        if self.model is not None:
            doc.embedding = self.model.encode(doc.text).astype('float32').tolist()
        self.docs[doc.id] = doc

    @lru_cache(maxsize=128)
    def search_docs_static(self, term: str) -> List[Document]:
        """Simple LRU cached search over local documents."""
        return [d for d in self.docs.values() if term.lower() in d.text.lower()]

    def search(self, query: str, tags: List[str] | None = None) -> List[Document]:
        """Search documents with caching and optional tag filtering."""
        key = query + str(tags)
        if key in self.cache:
            return self.cache[key]
        if self.model is not None:
            query_emb = self.model.encode(query).astype('float32')
            results = []
            for d in self.docs.values():
                if d.embedding is None:
                    continue
                emb = np.array(d.embedding, dtype='float32')
                score = float(util.cos_sim(query_emb, emb)[0][0])
                results.append((score, d))
            results.sort(key=lambda x: x[0], reverse=True)
            docs = [d for _, d in results]
        else:
            docs = [d for d in self.docs.values() if query in d.text]
        if tags:
            docs = [d for d in docs if set(tags) <= set(d.tags)]
        self.cache[key] = docs
        return docs

    async def fetch_remote(self, term: str) -> Any:
        """Fetch term from remote source with async I/O and caching."""
        if term in memory_cache:
            data = memory_cache[term]
            if self.enc_key:
                try:
                    import json
                    data = json.loads(decrypt_payload(self.enc_key, data))
                except Exception:
                    pass
            return data
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://example.com/search?q={term}") as resp:
                data = await resp.json()
        if self.enc_key:
            import json
            store = encrypt_payload(self.enc_key, json.dumps(data).encode())
        else:
            store = data
        memory_cache[term] = store
        return data

import json
from datetime import datetime, timezone
from pathlib import Path

LIBRARY_INDEX = Path("library/library_index.json")
LIBRARY_INDEX.parent.mkdir(parents=True, exist_ok=True)
if not LIBRARY_INDEX.exists():
    LIBRARY_INDEX.write_text("[]")


def index_data(key: str, tags: list[str], source_bot: str, task_id: str, filepath: str) -> None:
    entry = {
        "key": key,
        "tags": tags,
        "source_bot": source_bot,
        "task_id": task_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "filepath": filepath,
        "usage_count": 0,
    }
    index = json.loads(LIBRARY_INDEX.read_text())
    index.append(entry)
    LIBRARY_INDEX.write_text(json.dumps(index, indent=2))


def retrieve(query: str) -> list[dict]:
    index = json.loads(LIBRARY_INDEX.read_text())
    results = []
    for entry in index:
        if query in entry.get("tags", []) or query in entry.get("task_id", ""):
            entry["usage_count"] += 1
            results.append(entry)
    LIBRARY_INDEX.write_text(json.dumps(index, indent=2))
    return sorted(results, key=lambda x: (x["usage_count"], x["timestamp"]), reverse=True)


def search_by_metadata(bot: str | None = None, tag: str | None = None, since: str | None = None) -> list[dict]:
    index = json.loads(LIBRARY_INDEX.read_text())
    filtered = []
    for entry in index:
        if bot and entry["source_bot"] != bot:
            continue
        if tag and tag not in entry["tags"]:
            continue
        if since and datetime.fromisoformat(entry["timestamp"]) < datetime.fromisoformat(since):
            continue
        filtered.append(entry)
    return sorted(filtered, key=lambda x: x["timestamp"], reverse=True)


def sync_library(peer_path: str) -> None:
    local = {e["key"]: e for e in json.loads(LIBRARY_INDEX.read_text())}
    peer = {e["key"]: e for e in json.loads(Path(peer_path).read_text())}
    for k, v in peer.items():
        if k not in local or v["timestamp"] > local[k]["timestamp"]:
            local[k] = v
    LIBRARY_INDEX.write_text(json.dumps(list(local.values()), indent=2))
