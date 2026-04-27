"""
PATCH-121 — src/world_corpus.py
Murphy System — WorldCorpus: Collect → Store → Inference

Design principle:
  COLLECT: Scheduled background jobs pull from public sources + internal signals.
  STORE:   Normalized records in SQLite. Dedup by content hash. Append-only.
  INFER:   On-demand query + relevance scoring + LLM synthesis.
           Agents never make live API calls — they query the stored corpus.

This replaces the live-fetch pattern in influence_collector.py.
InfluenceCollector is now a thin wrapper that calls WorldCorpus.collect_all().

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""
from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("murphy.world_corpus")

_DB_PATH = Path("/var/lib/murphy-production/world_corpus.db")
_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

_STOP_WORDS = {
    "a","an","the","and","or","to","for","of","in","on","with","is","it","this",
    "that","be","by","at","as","from","i","me","my","we","you","your","what",
    "how","why","when","where","who","which","are","was","were","has","have",
    "had","do","does","did","will","would","could","should","may","might","not",
    "but","if","so","then","than","about","get","its","their","they","them",
    "our","can","just","more","also","into","over","after","latest","new","news",
}


def _content_hash(content: str) -> str:
    return hashlib.md5(content[:200].lower().encode()).hexdigest()[:16]


def _score_words(question: str) -> set:
    """Lowercase question, strip stop words, return significant word set."""
    words = set(question.lower().split())
    return words - _STOP_WORDS


@dataclass
class CorpusRecord:
    record_id: str
    source: str
    domain: str
    content: str
    timestamp: str
    tags: List[str]
    score: float = 0.0


class WorldCorpus:
    """
    PATCH-121: Unified world knowledge corpus.
    Collect from external + internal sources. Store in SQLite.
    Inference via relevance scoring + LLM synthesis.
    """

    def __init__(self, db_path: Path = _DB_PATH):
        self._db_path = db_path
        self._lock = threading.Lock()
        self._dedup_hits = 0
        self._init_db()
        logger.info("PATCH-121: WorldCorpus initialized — %s", db_path)

    def _conn(self) -> sqlite3.Connection:
        """New connection per call — thread safe."""
        return sqlite3.connect(str(self._db_path), timeout=10)

    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS corpus (
                    record_id  TEXT PRIMARY KEY,
                    source     TEXT NOT NULL,
                    domain     TEXT NOT NULL,
                    content    TEXT NOT NULL,
                    timestamp  TEXT NOT NULL,
                    tags       TEXT DEFAULT ''
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_domain ON corpus(domain)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ts ON corpus(timestamp)")

    # ── COLLECT ───────────────────────────────────────────────────────────────

    def ingest(self, source: str, domain: str, content: str,
               tags: List[str] = None) -> Optional[str]:
        """Store one record. Dedup by content hash (PRIMARY KEY lookup)."""
        if not content or not content.strip():
            return None
        rid = _content_hash(content)
        tag_str = " ".join(tags or [])
        now = datetime.now(timezone.utc).isoformat()

        with self._lock:
            with self._conn() as conn:
                existing = conn.execute(
                    "SELECT record_id FROM corpus WHERE record_id=?", (rid,)
                ).fetchone()
                if existing:
                    self._dedup_hits += 1
                    return None
                conn.execute(
                    "INSERT INTO corpus (record_id, source, domain, content, timestamp, tags) "
                    "VALUES (?,?,?,?,?,?)",
                    (rid, source, domain, content, now, tag_str)
                )
        return rid

    def collect_hn(self) -> int:
        """Fetch HN top 15 stories. Returns count of NEW records stored."""
        stored = 0
        try:
            req = urllib.request.Request(
                "https://hacker-news.firebaseio.com/v0/topstories.json",
                headers={"User-Agent": "Murphy/1.0 (murphy.systems)"}
            )
            ids = json.loads(urllib.request.urlopen(req, timeout=6).read())[:15]
            for story_id in ids:
                try:
                    sreq = urllib.request.Request(
                        f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json",
                        headers={"User-Agent": "Murphy/1.0 (murphy.systems)"}
                    )
                    item = json.loads(urllib.request.urlopen(sreq, timeout=5).read())
                    title = item.get("title", "").strip()
                    url   = item.get("url", "")
                    if not title:
                        continue
                    content = f"{title} | {url}" if url else title
                    rid = self.ingest("hn", "tech", content, tags=["trending", "hn"])
                    if rid:
                        stored += 1
                except Exception:
                    continue
        except Exception as exc:
            logger.warning("WorldCorpus.collect_hn failed: %s", exc)
        logger.info("WorldCorpus: HN collected %d new records", stored)
        return stored

    def collect_reddit(self, subreddit: str, domain: str,
                       tags: List[str] = None) -> int:
        """Fetch Reddit top 15 posts. Returns count of NEW records stored."""
        stored = 0
        try:
            req = urllib.request.Request(
                f"https://www.reddit.com/r/{subreddit}/top.json?limit=15&t=day",
                headers={"User-Agent": "Murphy/1.0 (murphy.systems)"}
            )
            data = json.loads(urllib.request.urlopen(req, timeout=6).read())
            for post in data["data"]["children"]:
                d = post["data"]
                title = d.get("title", "").strip()
                url   = d.get("url", "")
                if not title or title in ("[removed]", "[deleted]"):
                    continue
                content = f"{title} | {url}" if url else title
                base_tags = [subreddit] + (tags or [])
                rid = self.ingest("reddit", domain, content, tags=base_tags)
                if rid:
                    stored += 1
        except Exception as exc:
            logger.warning("WorldCorpus.collect_reddit(%s) failed: %s", subreddit, exc)
        logger.info("WorldCorpus: reddit/%s collected %d new records", subreddit, stored)
        return stored

    def collect_all(self) -> Dict[str, int]:
        """Run all collectors. Returns per-source new record counts."""
        counts = {
            "hn":        self.collect_hn(),
            "worldnews": self.collect_reddit("worldnews",  "geopolitics", ["world"]),
            "technology":self.collect_reddit("technology", "tech",        ["tech"]),
            "economics": self.collect_reddit("economics",  "finance",     ["finance"]),
        }
        counts["total"] = sum(counts.values())
        logger.info("WorldCorpus.collect_all: %s", counts)
        return counts

    # ── QUERY ─────────────────────────────────────────────────────────────────

    def query(self, domain: str = None, tags: List[str] = None,
              limit: int = 20, since_hours: int = 24) -> List[CorpusRecord]:
        """Return recent records matching filters."""
        since = (datetime.now(timezone.utc) - timedelta(hours=since_hours)).isoformat()
        conditions = ["timestamp >= ?"]
        params: List = [since]

        if domain:
            conditions.append("domain = ?")
            params.append(domain)

        if tags:
            # Space-separated tag storage: each tag is surrounded by spaces (or edge)
            tag_conditions = []
            for tag in tags:
                tag_conditions.append("(' ' || tags || ' ') LIKE ?")
                params.append(f"% {tag} %")
            conditions.append(f"({' OR '.join(tag_conditions)})")

        sql = (
            f"SELECT record_id, source, domain, content, timestamp, tags "
            f"FROM corpus WHERE {' AND '.join(conditions)} "
            f"ORDER BY timestamp DESC LIMIT ?"
        )
        params.append(limit)

        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()

        return [
            CorpusRecord(
                record_id=r[0], source=r[1], domain=r[2],
                content=r[3], timestamp=r[4],
                tags=r[5].split() if r[5] else [],
            )
            for r in rows
        ]

    # ── INFERENCE ─────────────────────────────────────────────────────────────

    def infer(self, question: str, domain: str = None, limit: int = 10) -> Dict:
        """
        THE KEY METHOD.
        Query corpus → score relevance → LLM synthesis.
        Agents call this. They never make live API calls.
        """
        records = self.query(domain=domain, since_hours=48, limit=200)
        records_queried = len(records)

        if not records:
            return {
                "answer": "Insufficient data collected yet. Run collect_all() first.",
                "confidence": 0.0,
                "sources": [],
                "records_queried": 0,
                "records_used": 0,
                "domain": domain,
            }

        # Score: keyword overlap (stop-words stripped, lowercased)
        q_words = _score_words(question)
        if not q_words:
            q_words = set(question.lower().split())

        scored = []
        for rec in records:
            # Only score on title portion (before pipe)
            title = rec.content.split(" | ")[0].lower()
            r_words = set(title.split()) - _STOP_WORDS
            if not r_words:
                continue
            overlap = len(q_words & r_words)
            score = overlap / max(len(q_words), 1)
            if score > 0:
                rec.score = round(score, 4)
                scored.append(rec)

        scored.sort(key=lambda r: r.score, reverse=True)
        top = scored[:limit]

        if not top:
            # No keyword overlap — return most recent records as fallback
            top = records[:limit]

        sources = [r.content.split(" | ")[0] for r in top]

        # LLM synthesis
        answer = ""
        confidence = 0.0
        try:
            from src.llm_provider import MurphyLLMProvider
            llm = MurphyLLMProvider()
            newline = chr(10)
            obs = newline.join("- " + r.content.split(" | ")[0] for r in top)
            prompt = (
                "You are Murphy, an AI operating system analyzing world signals." + newline
                + "Based on these recent observations:" + newline + obs + newline + newline
                + "Answer concisely (2-3 sentences): " + question
            )
            result = llm.complete(prompt=prompt, max_tokens=250)
            answer = result.content.strip()
            confidence = min(0.9, 0.4 + (len(top) / limit) * 0.5)
        except Exception as exc:
            logger.warning("WorldCorpus.infer: LLM failed, using corpus summary: %s", exc)
            answer = "Top signals: " + " | ".join(sources[:5])
            confidence = 0.3

        return {
            "answer": answer,
            "confidence": round(confidence, 3),
            "sources": sources,
            "records_queried": records_queried,
            "records_used": len(top),
            "domain": domain,
            "question": question,
        }

    # ── STATS ─────────────────────────────────────────────────────────────────

    def stats(self) -> Dict:
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM corpus").fetchone()[0]
            by_domain = {
                row[0]: row[1]
                for row in conn.execute(
                    "SELECT domain, COUNT(*) FROM corpus GROUP BY domain"
                ).fetchall()
            }
            ts = conn.execute(
                "SELECT MIN(timestamp), MAX(timestamp) FROM corpus"
            ).fetchone()
        return {
            "total_records": total,
            "by_domain": by_domain,
            "oldest": ts[0],
            "newest": ts[1],
            "dedup_hits": self._dedup_hits,
        }


# ── Singleton ─────────────────────────────────────────────────────────────────
_corpus: Optional[WorldCorpus] = None
_corpus_lock = threading.Lock()

def get_world_corpus() -> WorldCorpus:
    global _corpus
    if _corpus is None:
        with _corpus_lock:
            if _corpus is None:
                _corpus = WorldCorpus()
    return _corpus
