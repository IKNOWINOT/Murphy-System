"""MemoryManagerBot with embedding-based search and persistence."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict

try:
    from sentence_transformers import SentenceTransformer, util
except Exception:  # pragma: no cover - heavy dep optional
    SentenceTransformer = None  # type: ignore
    util = None
try:  # optional for ANN search
    import faiss  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    faiss = None
import sqlite3
import os
import math
import time
import zlib
import base64
import json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from .crypto_utils import encrypt_payload, decrypt_payload

# simple persistence using SQLite
DB_PATH = os.environ.get('MEMORY_DB', 'memory.db')

@dataclass
class MemoryEntry:
    id: int
    text: str
    embedding: List[float]
    trust: float = 1.0
    last_accessed: float = 0.0
    access_count: int = 0


class MemoryManagerBot:
    def __init__(self, model_name: str = 'sentence-transformers/LaBSE', *, encryption_key: bytes | None = None, context_window: int = 50):
        """Initialize with a cross-language embedding model."""
        if SentenceTransformer is None:
            raise ImportError('sentence-transformers is required for MemoryManagerBot')
        try:
            self.model = SentenceTransformer(model_name)
        except TypeError:
            # Support test stubs that lack an __init__ signature
            self.model = SentenceTransformer()
        if hasattr(self.model, 'get_sentence_embedding_dimension'):
            self.dim = self.model.get_sentence_embedding_dimension()
        else:  # minimal stub model
            sample = self.model.encode("dim")
            self.dim = len(sample) if hasattr(sample, '__len__') else 0
        if faiss is not None:
            self.index = faiss.IndexIDMap(faiss.IndexFlatIP(self.dim))
        else:
            self.index = None
        self.id_to_text: Dict[int, str] = {}
        self.enc_key = encryption_key
        self.context_window = context_window
        self.archived_memories: Dict[int, bytes] = {}
        self._ensure_db()
        self._load_index()

    def ttl_check(self, threshold: float = 0.3) -> dict:
        """Flush STM to LTM when adaptive retention is below ``threshold``.

        Expired entries are:
        1. Compressed with ``zlib``.
        2. Moved to an ``archived_memories`` dict keyed by memory id.
        3. Removed from the active memory store (and FAISS index when present).

        Returns:
            dict with keys ``archived`` (int), ``total_checked`` (int),
            ``bytes_saved`` (int).
        """
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT id, text, last_accessed, access_count, compressed FROM memories WHERE is_deleted = 0')
        to_archive: list[int] = []
        row_data: dict[int, tuple] = {}
        for row in cursor.fetchall():
            mem_id, text, last_accessed, acc, compressed = row
            retain = adaptive_decay(last_accessed, acc)
            if retain < threshold:
                to_archive.append(mem_id)
                row_data[mem_id] = (text, compressed)
        conn.close()

        archived_count = 0
        bytes_saved = 0
        for m in to_archive:
            text, compressed = row_data[m]
            try:
                raw = text.encode("utf-8") if isinstance(text, str) else text
                original_size = len(raw)
                if not compressed:
                    compressed_blob = zlib.compress(raw)
                else:
                    compressed_blob = raw
                compressed_size = len(compressed_blob)
                bytes_saved += max(0, original_size - compressed_size)

                self.archived_memories[m] = compressed_blob

                conn2 = sqlite3.connect(DB_PATH)
                conn2.execute('UPDATE memories SET is_deleted = 1 WHERE id = ?', (m,))
                conn2.commit()
                conn2.close()

                self.id_to_text.pop(m, None)
                if self.index is not None:
                    try:
                        self.index.remove_ids(np.array([m], dtype='int64'))
                    except Exception:
                        pass

                archived_count += 1
            except Exception:
                pass

        return {"archived": archived_count, "total_checked": len(to_archive), "bytes_saved": bytes_saved}

    def _load_index(self) -> None:
        """Load existing memories into the ANN index."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id, text, embedding, trust, last_accessed, access_count '
            'FROM memories WHERE is_deleted = 0'
        )
        rows = cursor.fetchall()
        conn.close()
        if self.index is not None and rows:
            embeddings = []
            ids = []
            for mem_id, text, emb_blob, trust, _last, _cnt in rows:
                emb = np.frombuffer(emb_blob, dtype=np.float32)
                self.id_to_text[mem_id] = text
                # normalize for cosine similarity
                norm = np.linalg.norm(emb) or 1.0
                embeddings.append((emb / norm).astype('float32'))
                ids.append(mem_id)
            self.index.add_with_ids(np.vstack(embeddings), np.array(ids, dtype='int64'))
        else:
            for mem_id, text, _, _trust, _last, _cnt in rows:
                self.id_to_text[mem_id] = text

    def _ensure_db(self) -> None:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            'CREATE TABLE IF NOT EXISTS memories ('
            'id INTEGER PRIMARY KEY, '
            'text TEXT, '
            'embedding BLOB, '
            'trust REAL DEFAULT 1.0, '
            'last_accessed REAL DEFAULT 0, '
            'access_count INTEGER DEFAULT 0, '
            'is_deleted INTEGER DEFAULT 0, '
            'tenant TEXT DEFAULT "default", '
            'ttl_seconds INTEGER DEFAULT 0, '
            'compressed INTEGER DEFAULT 0'
            ')'
        )
        cursor.execute(
            'CREATE TABLE IF NOT EXISTS memory_history ('
            'mem_id INTEGER, '
            'timestamp REAL, '
            'editor TEXT, '
            'reason TEXT, '
            'text TEXT'
            ')'
        )
        cursor.execute("PRAGMA table_info(memories)")
        cols = [row[1] for row in cursor.fetchall()]
        if 'trust' not in cols:
            cursor.execute('ALTER TABLE memories ADD COLUMN trust REAL DEFAULT 1.0')
        if 'last_accessed' not in cols:
            cursor.execute('ALTER TABLE memories ADD COLUMN last_accessed REAL DEFAULT 0')
        if 'access_count' not in cols:
            cursor.execute('ALTER TABLE memories ADD COLUMN access_count INTEGER DEFAULT 0')
        if 'is_deleted' not in cols:
            cursor.execute('ALTER TABLE memories ADD COLUMN is_deleted INTEGER DEFAULT 0')
        if 'tenant' not in cols:
            cursor.execute('ALTER TABLE memories ADD COLUMN tenant TEXT DEFAULT "default"')
        if 'ttl_seconds' not in cols:
            cursor.execute('ALTER TABLE memories ADD COLUMN ttl_seconds INTEGER DEFAULT 0')
        if 'compressed' not in cols:
            cursor.execute('ALTER TABLE memories ADD COLUMN compressed INTEGER DEFAULT 0')
        conn.commit()
        conn.close()

    def add_memory(self, text: str, trust: float = 1.0, tenant: str = "default") -> int:
        plain_text = text
        if self.enc_key:
            plain_text = encrypt_payload(self.enc_key, text.encode()).decode()
        embedding = self.model.encode(text).astype('float32')
        norm = np.linalg.norm(embedding) or 1.0
        embedding = (embedding / norm).astype('float32')
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO memories (text, embedding, trust, last_accessed, access_count, tenant) '
            'VALUES (?, ?, ?, strftime("%s","now"), 0, ?)',
            (plain_text, embedding.tobytes(), trust, tenant),
        )
        conn.commit()
        memory_id = cursor.lastrowid
        conn.close()
        self.id_to_text[memory_id] = text
        if self.index is not None:
            self.index.add_with_ids(np.expand_dims(embedding, 0), np.array([memory_id], dtype='int64'))
        return memory_id

    def record_update(self, mem_id: int, new_text: str, editor: str, reason: str = "") -> None:
        """Record an updated version of a memory and store diff."""
        old = self.retrieve_ltm(mem_id)
        if old is None:
            return
        from .history_diff import get_diff
        diff_text = get_diff(old, new_text)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO memory_history (mem_id, timestamp, editor, reason, text) '
            'VALUES (?, strftime("%s","now"), ?, ?, ?)',
            (mem_id, editor, reason, diff_text),
        )
        cursor.execute('UPDATE memories SET text = ? WHERE id = ?', (new_text, mem_id))
        conn.commit()
        conn.close()
        self.id_to_text[mem_id] = new_text
        if self.index is not None:
            emb = self.model.encode(new_text).astype('float32')
            norm = np.linalg.norm(emb) or 1.0
            emb = (emb / norm).astype('float32')
            self.index.remove_ids(np.array([mem_id], dtype='int64'))
            self.index.add_with_ids(np.expand_dims(emb, 0), np.array([mem_id], dtype='int64'))

    def retrieve_ltm(self, mem_id: int) -> str | None:
        """Return memory text by id if present."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT text, compressed FROM memories WHERE id = ?', (mem_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        text, compressed = row
        if compressed:
            try:
                text = zlib.decompress(base64.b64decode(text)).decode()
            except Exception:
                pass
        if self.enc_key:
            try:
                text = decrypt_payload(self.enc_key, text.encode()).decode()
            except Exception:
                pass
        return text

    def search_ltm(self, query: str, top_k: int = 5, tenant: str = "default") -> List[MemoryEntry]:
        query_emb = self.model.encode(query).astype('float32')
        norm = np.linalg.norm(query_emb) or 1.0
        query_emb = np.expand_dims(query_emb / norm, 0).astype('float32')
        if self.index is not None and self.index.ntotal > 0:
            scores, ids = self.index.search(query_emb, top_k)
            results = []
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            for score, mem_id in zip(scores[0], ids[0]):
                if mem_id == -1:
                    continue
                cursor.execute(
                    'SELECT text, trust, last_accessed, access_count, compressed, ttl_seconds FROM memories WHERE id = ? AND tenant = ?',
                    (int(mem_id), tenant),
                )
                row = cursor.fetchone()
                if not row:
                    continue
                text, trust, last_accessed, access_count, compressed, ttl = row
                if ttl and last_accessed + ttl < time.time():
                    continue
                if compressed:
                    try:
                        text = zlib.decompress(base64.b64decode(text)).decode()
                    except Exception:
                        pass
                if self.enc_key:
                    try:
                        text = decrypt_payload(self.enc_key, text.encode()).decode()
                    except Exception:
                        pass
                results.append(
                    (
                        score * trust,
                        MemoryEntry(int(mem_id), text, [], trust, last_accessed, access_count),
                    )
                )
                cursor.execute(
                    'UPDATE memories SET last_accessed = strftime("%s","now"), access_count = access_count + 1 WHERE id = ?',
                    (int(mem_id),),
                )
            conn.close()
            results.sort(key=lambda x: x[0], reverse=True)
            limit = min(top_k, self.context_window)
            return [entry for _, entry in results[:limit]]
        # fallback to brute-force search
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT id, text, embedding, trust, last_accessed, access_count, compressed, ttl_seconds FROM memories WHERE is_deleted = 0 AND tenant = ?', (tenant,))
        results = []
        for mem_id, text, emb_blob, trust, last_accessed, access_count, compressed, ttl in cursor.fetchall():
            if ttl and last_accessed + ttl < time.time():
                continue
            if self.enc_key:
                try:
                    text = decrypt_payload(self.enc_key, text.encode()).decode()
                except Exception:
                    pass
            
            # decompress if needed
            if compressed:
                try:
                    text = zlib.decompress(base64.b64decode(text)).decode()
                except Exception:
                    pass
            emb = np.frombuffer(emb_blob, dtype=np.float32)
            norm_emb = emb / (np.linalg.norm(emb) or 1.0)
            q = query_emb.flatten()
            n = norm_emb.flatten()
            m = min(len(q), len(n))
            score = float(np.dot(q[:m], n[:m]))
            results.append(
                (
                    score * trust,
                    MemoryEntry(mem_id, text, emb.tolist(), trust, last_accessed, access_count),
                )
            )
            cursor.execute(
                'UPDATE memories SET last_accessed = strftime("%s","now"), access_count = access_count + 1 WHERE id = ?',
                (mem_id,),
            )
        conn.close()
        results.sort(key=lambda x: x[0], reverse=True)
        limit = min(top_k, self.context_window)
        return [entry for _, entry in results[:limit]]

    def search_ltm_cross_language(self, query: str, lang: str, top_k: int = 5) -> List[MemoryEntry]:
        """Search LTM using cross-language embeddings."""
        # the embedding model is multilingual, so we can search directly
        return self.search_ltm(query, top_k=top_k)

    def query_command(self, query: str) -> str:
        """Return a simple string result for chat commands."""
        results = self.search_ltm(query)
        return '\n'.join(f'[{r.id}] {r.text}' for r in results)

    def prune_memories(self, threshold: float = 0.25) -> None:
        """Remove memories whose retention probability falls below threshold."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id, last_accessed, access_count FROM memories'
        )
        to_delete = []
        for mem_id, last_accessed, access_count in cursor.fetchall():
            retain = adaptive_decay(last_accessed, access_count)
            if retain < threshold:
                to_delete.append(mem_id)
        for mem_id in to_delete:
            cursor.execute('UPDATE memories SET is_deleted = 1 WHERE id = ?', (mem_id,))
            self.id_to_text.pop(mem_id, None)
            if self.index is not None:
                self.index.remove_ids(np.array([mem_id], dtype='int64'))
        conn.commit()
        conn.close()

    def soft_delete(self, mem_id: int) -> None:
        """Mark a memory as deleted without removing from storage."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('UPDATE memories SET is_deleted = 1 WHERE id = ?', (mem_id,))
        conn.commit()
        conn.close()
        self.id_to_text.pop(mem_id, None)
        if self.index is not None:
            self.index.remove_ids(np.array([mem_id], dtype='int64'))

    def export_memory(self, file_path: str) -> None:
        """Export all memories to a JSONL file."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT id, text, embedding, trust, last_accessed, access_count, is_deleted, ttl_seconds, compressed FROM memories')
        rows = cursor.fetchall()
        conn.close()
        import json, base64
        with open(file_path, 'w') as f:
            for row in rows:
                mem_id, text, emb_blob, trust, last_accessed, access_count, is_del, ttl, compressed = row
                record = {
                    'id': mem_id,
                    'text': text,
                    'embedding': base64.b64encode(emb_blob).decode(),
                    'trust': trust,
                    'last_accessed': last_accessed,
                    'access_count': access_count,
                    'is_deleted': is_del,
                    'ttl_seconds': ttl,
                    'compressed': compressed,
                }
                f.write(json.dumps(record) + '\n')

    def import_memory(self, file_path: str) -> None:
        """Import memories from a JSONL file."""
        import json, base64
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        with open(file_path) as f:
            for line in f:
                record = json.loads(line)
                cursor.execute(
                    'INSERT OR REPLACE INTO memories '
                    '(id, text, embedding, trust, last_accessed, access_count, is_deleted, ttl_seconds, compressed) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                    (
                        record['id'],
                        record['text'],
                        base64.b64decode(record['embedding']),
                        record.get('trust', 1.0),
                        record.get('last_accessed', 0.0),
                        record.get('access_count', 0),
                        record.get('is_deleted', 0),
                        record.get('ttl_seconds', 0),
                        record.get('compressed', 0),
                    ),
                )
        conn.commit()
        conn.close()

    def get_history(self, mem_id: int) -> List[str]:
        """Return stored diffs for ``mem_id`` in chronological order."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            'SELECT text FROM memory_history WHERE mem_id = ? ORDER BY timestamp',
            (mem_id,),
        )
        rows = [row[0] for row in cursor.fetchall()]
        conn.close()
        return rows

    def archive_ltm(self, text: str, ttl_seconds: int) -> int:
        """Archive data with a TTL."""
        mem_id = self.add_memory(text)
        conn = sqlite3.connect(DB_PATH)
        conn.execute('UPDATE memories SET ttl_seconds = ? WHERE id = ?', (ttl_seconds, mem_id))
        conn.commit()
        conn.close()
        return mem_id

    def list_expired_ltm(self) -> List[int]:
        conn = sqlite3.connect(DB_PATH)
        now = time.time()
        cursor = conn.execute(
            'SELECT id FROM memories WHERE ttl_seconds > 0 AND (last_accessed + ttl_seconds) < ?',
            (now,),
        )
        ids = [row[0] for row in cursor.fetchall()]
        conn.close()
        return ids

    def purge_ltm(self, mem_id: int) -> None:
        conn = sqlite3.connect(DB_PATH)
        conn.execute('DELETE FROM memories WHERE id = ?', (mem_id,))
        conn.commit()
        conn.close()
        self.id_to_text.pop(mem_id, None)
        if self.index is not None:
            self.index.remove_ids(np.array([mem_id], dtype='int64'))

    def compress_ltm(self, mem_id: int) -> None:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT text, compressed FROM memories WHERE id = ?', (mem_id,))
        row = cursor.fetchone()
        if not row or row[1]:
            conn.close()
            return
        import zlib, base64
        compressed = base64.b64encode(zlib.compress(row[0].encode())).decode()
        cursor.execute('UPDATE memories SET text = ?, compressed = 1 WHERE id = ?', (compressed, mem_id))
        conn.commit()
        conn.close()


def adaptive_decay(last_accessed: float, accesses: int, decay_factor: float = 1.8) -> float:
    """Return retention probability using an adaptive forgetting curve."""
    age_days = (time.time() - last_accessed) / 86400
    stability = accesses ** decay_factor if accesses > 0 else 1.0
    return math.exp(-age_days / stability)


def adaptive_forgetting_curve(age: float, stability: float = 1.0) -> float:
    """Backward compatibility wrapper for adaptive decay."""
    return adaptive_decay(time.time() - age * 86400, stability)

STM_DIR = Path('memory/stm')
LTM_DIR = Path('memory/ltm')


def store_stm(task_id: str, content: str, context: dict, ttl_seconds: int = 1800) -> None:
    STM_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        'task_id': task_id,
        'owner': 'AionMind_Core',
        'bot': context.get('bot', ''),
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'content': content,
        'tags': context.get('tags', []),
        'context': context,
        'ttl_seconds': ttl_seconds,
    }
    with open(STM_DIR / f"{task_id}.json", 'w', encoding='utf-8') as f:
        json.dump(entry, f, indent=2)


def retrieve_ltm_entries(query: dict) -> list[dict]:
    project = query.get('project', 'default')
    topic = query.get('topic')
    archive_file = LTM_DIR / project / 'memory_chunks.json'
    if not archive_file.exists():
        return []
    with open(archive_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    results = []
    for chunk in data:
        if topic is None or topic == chunk.get('context', {}).get('topic'):
            results.append(chunk)
    results.sort(key=lambda x: x['timestamp'], reverse=True)
    return results
