"""
PCR-054k — PractitionerCorpus

The founder's reframe (2026-06-09):
  "Their employees train the system. The language and generation
   follows."

PCR-054j gave us the correspondence thread — every message related
to an engagement, classified by intent, preserved verbatim. This
patch turns that raw material into a STRUCTURED LEARNING SURFACE
that PCR-054l (generation conditioning) will draft against.

ARCHITECTURE (per Murphy's vote, 2026-06-09)
============================================
Option D1: per-(practitioner, tenant) isolation, all four dimensions
stored at finest grain. Generation views are query-time projections.
Cross-tenant practitioner-voice mixing is BLOCKED by default.

GRAIN
-----
Each corpus entry is keyed by:
  practitioner_id   (derived from from_email)
  tenant_id         (from the engagement's folder)
  role_id           (from the engagement's folder)
  jurisdiction      (from the engagement's folder)
  intent            (from PCR-054j classifier)

Three query-time views:
  voice_for_practitioner_at_tenant(p, t)
    Jane's voice WITH Acme (tenant-isolated, per Murphy/founder canon)
  voice_for_role_jurisdiction(r, j)
    Domain prior — US-CA CPA work in general — used as cold-start
    fallback when a practitioner has no history
  recurring_questions(p, t)
    Questions Jane asks Acme repeatedly — pre-answer these in
    future drafts so she doesn't have to ask again

VOCABULARY SIGNATURE
--------------------
For each entry we compute a lightweight signature: token frequency,
bigrams, salient phrases. Pure-function, no LLM dependency. Good
enough to detect 'this practitioner uses "section 1031" not
"like-kind exchange"' patterns.

PRIVACY / ISOLATION (per D1)
----------------------------
- voice_for_practitioner_at_tenant requires BOTH practitioner_id
  AND tenant_id. There is no API to fetch a practitioner's voice
  across all their tenants without explicit cross-tenant query.
- voice_for_role_jurisdiction is the domain prior — it explicitly
  aggregates across practitioners and tenants because it's modeling
  the PROFESSION, not any individual.
- All entries are tenant-tagged for audit. Any future cross-tenant
  query (D2 upgrade) becomes explicit and reviewable.
"""
from __future__ import annotations

import json
import logging
import re
import sqlite3
import time
import uuid
from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.engagement_folder import (
    DEFAULT_DB_PATH as ENGAGEMENT_DB_PATH,
    _connect,
    get_folder,
)
from src.engagement_correspondence import (
    Correspondence,
    get_thread_by_practitioner,
    get_thread,
)

LOG = logging.getLogger("murphy.practitioner_corpus")


# ─────────────────────────────────────────────────────────────────────
# Schema
# ─────────────────────────────────────────────────────────────────────


SCHEMA = """
CREATE TABLE IF NOT EXISTS practitioner_corpus_entries (
    entry_id              TEXT PRIMARY KEY,
    practitioner_id       TEXT NOT NULL,
    tenant_id             TEXT NOT NULL,
    role_id               TEXT NOT NULL,
    jurisdiction          TEXT NOT NULL,
    intent                TEXT NOT NULL,
    confidence            TEXT NOT NULL,
    body                  TEXT NOT NULL,
    vocab_signature_json  TEXT NOT NULL DEFAULT '{}',
    source_corr_id        TEXT NOT NULL,
    source_engagement_id  TEXT NOT NULL,
    received_at           REAL NOT NULL,
    harvested_at          REAL NOT NULL,
    UNIQUE(source_corr_id)
);

CREATE INDEX IF NOT EXISTS idx_corpus_practitioner_tenant
    ON practitioner_corpus_entries (practitioner_id, tenant_id);
CREATE INDEX IF NOT EXISTS idx_corpus_role_jurisdiction
    ON practitioner_corpus_entries (role_id, jurisdiction);
CREATE INDEX IF NOT EXISTS idx_corpus_intent
    ON practitioner_corpus_entries (intent);
"""


def init_db(db_path: str = ENGAGEMENT_DB_PATH) -> None:
    con = _connect(db_path)
    try:
        con.executescript(SCHEMA)
        con.commit()
    finally:
        con.close()


# ─────────────────────────────────────────────────────────────────────
# Practitioner ID derivation
# ─────────────────────────────────────────────────────────────────────


def practitioner_id_from_email(email: str) -> str:
    """Stable practitioner_id from from_email. Lowercase + trim.

    Email is the canonical identifier today. Future versions may
    layer in license_number once verification is real, but the
    practitioner identity should still be email-stable so the
    corpus survives license renewals.
    """
    if not email:
        return "unknown"
    return email.strip().lower()


# ─────────────────────────────────────────────────────────────────────
# Vocabulary signature (pure function)
# ─────────────────────────────────────────────────────────────────────


# Stop words we don't want polluting the signature
STOPWORDS = frozenset("""
a an the and or but if then else for to from of in on at by with
is are was were be been being has have had do does did will would
could should may might can must shall i you he she it we they
this that these those my your his her its our their me him us them
re fwd subject body engagement attached please thank thanks regards
hi hello dear sincerely
""".split())

# Word tokenizer
WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9\-']{2,}")


@dataclass
class VocabSignature:
    """Lightweight vocabulary fingerprint, pure function output."""
    token_count:        int
    unique_tokens:      int
    top_tokens:         List[Tuple[str, int]]       # (token, freq) top 15
    top_bigrams:        List[Tuple[str, int]]       # ('word1 word2', freq) top 10
    salient_phrases:    List[str]                    # phrases >= 3 caps tokens

    def as_dict(self) -> Dict[str, Any]:
        return {
            "token_count":     self.token_count,
            "unique_tokens":   self.unique_tokens,
            "top_tokens":      [list(t) for t in self.top_tokens],
            "top_bigrams":     [list(b) for b in self.top_bigrams],
            "salient_phrases": list(self.salient_phrases),
        }


def compute_vocab_signature(body: str) -> VocabSignature:
    """Tokenize, count, find bigrams. Pure function, no I/O."""
    tokens_raw = WORD_RE.findall(body)
    tokens = [t.lower() for t in tokens_raw if t.lower() not in STOPWORDS]

    token_counter = Counter(tokens)
    top_tokens = token_counter.most_common(15)

    # Bigrams
    bigram_counter: Counter = Counter()
    for i in range(len(tokens) - 1):
        bigram = f"{tokens[i]} {tokens[i+1]}"
        bigram_counter[bigram] += 1
    top_bigrams = bigram_counter.most_common(10)

    # Salient phrases: runs of 3+ Capitalized words from original text
    cap_run_re = re.compile(r"\b(?:[A-Z][a-zA-Z]+\b\s*){3,}")
    salient = [m.group(0).strip() for m in cap_run_re.finditer(body)]

    return VocabSignature(
        token_count=len(tokens),
        unique_tokens=len(token_counter),
        top_tokens=top_tokens,
        top_bigrams=top_bigrams,
        salient_phrases=salient[:5],
    )


# ─────────────────────────────────────────────────────────────────────
# Corpus entry + harvest
# ─────────────────────────────────────────────────────────────────────


@dataclass
class CorpusEntry:
    entry_id:             str
    practitioner_id:      str
    tenant_id:            str
    role_id:              str
    jurisdiction:         str
    intent:               str
    confidence:           str
    body:                 str
    vocab_signature_json: str
    source_corr_id:       str
    source_engagement_id: str
    received_at:          float
    harvested_at:         float

    def to_row(self) -> tuple:
        return (
            self.entry_id, self.practitioner_id, self.tenant_id,
            self.role_id, self.jurisdiction, self.intent,
            self.confidence, self.body, self.vocab_signature_json,
            self.source_corr_id, self.source_engagement_id,
            self.received_at, self.harvested_at,
        )

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "CorpusEntry":
        return cls(
            entry_id=row["entry_id"],
            practitioner_id=row["practitioner_id"],
            tenant_id=row["tenant_id"],
            role_id=row["role_id"],
            jurisdiction=row["jurisdiction"],
            intent=row["intent"],
            confidence=row["confidence"],
            body=row["body"],
            vocab_signature_json=row["vocab_signature_json"],
            source_corr_id=row["source_corr_id"],
            source_engagement_id=row["source_engagement_id"],
            received_at=row["received_at"],
            harvested_at=row["harvested_at"],
        )

    def as_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        try:
            d["vocab_signature"] = json.loads(self.vocab_signature_json)
        except Exception:
            d["vocab_signature"] = {}
        return d


def harvest_from_thread(
    engagement_id: str,
    *,
    db_path: str = ENGAGEMENT_DB_PATH,
) -> Dict[str, Any]:
    """Harvest practitioner correspondence from one engagement's thread
    into the corpus.

    Only INBOUND messages from practitioners (direction='in') are
    harvested. Outbound system messages are not training signal.
    Idempotent: re-harvesting the same thread is a no-op via the
    UNIQUE(source_corr_id) constraint.
    """
    init_db(db_path)
    folder = get_folder(engagement_id, db_path=db_path)
    if folder is None:
        return {"ok": False, "error": f"engagement {engagement_id} not found"}

    thread = get_thread(engagement_id, db_path=db_path)
    inbound = [c for c in thread if c.direction == "in"]

    harvested = 0
    skipped = 0
    now = time.time()

    con = _connect(db_path)
    try:
        for corr in inbound:
            practitioner_id = practitioner_id_from_email(corr.from_email)
            if practitioner_id == "unknown":
                skipped += 1
                continue

            signature = compute_vocab_signature(corr.body)
            entry = CorpusEntry(
                entry_id=f"corp_{uuid.uuid4().hex[:14]}",
                practitioner_id=practitioner_id,
                tenant_id=folder.tenant_id,
                role_id=folder.role_id,
                jurisdiction=folder.jurisdiction_required or "unknown",
                intent=corr.classified_intent,
                confidence=corr.classifier_confidence,
                body=corr.body,
                vocab_signature_json=json.dumps(signature.as_dict()),
                source_corr_id=corr.corr_id,
                source_engagement_id=engagement_id,
                received_at=corr.received_at,
                harvested_at=now,
            )
            try:
                con.execute(
                    "INSERT INTO practitioner_corpus_entries VALUES "
                    "(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    entry.to_row(),
                )
                harvested += 1
            except sqlite3.IntegrityError:
                # Already harvested (UNIQUE source_corr_id)
                skipped += 1
        con.commit()
    finally:
        con.close()

    LOG.info(
        "PCR-054k harvested eid=%s harvested=%d skipped=%d",
        engagement_id, harvested, skipped,
    )
    return {
        "ok":             True,
        "engagement_id":  engagement_id,
        "scanned":        len(inbound),
        "harvested":      harvested,
        "skipped":        skipped,
    }


def harvest_all_finalized(
    *,
    limit: int = 500,
    db_path: str = ENGAGEMENT_DB_PATH,
) -> Dict[str, Any]:
    """Sweep all FINALIZED engagements and harvest their threads.

    Used by the timer-driven corpus builder. Idempotent — already
    harvested rows skip via UNIQUE constraint.
    """
    init_db(db_path)
    con = _connect(db_path)
    try:
        rows = con.execute(
            "SELECT engagement_id FROM engagement_folders "
            "WHERE state IN ('finalized', 'verified', 'flagged') "
            "ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        con.close()

    total_harvested = 0
    total_skipped = 0
    results = []
    for r in rows:
        result = harvest_from_thread(r["engagement_id"], db_path=db_path)
        if result.get("ok"):
            total_harvested += result["harvested"]
            total_skipped += result["skipped"]
            results.append({
                "engagement_id": r["engagement_id"],
                "harvested":     result["harvested"],
                "skipped":       result["skipped"],
            })

    return {
        "ok":              True,
        "engagements_scanned": len(rows),
        "total_harvested": total_harvested,
        "total_skipped":   total_skipped,
        "results":         results,
    }


# ─────────────────────────────────────────────────────────────────────
# Query-time views (the three projections)
# ─────────────────────────────────────────────────────────────────────


def voice_for_practitioner_at_tenant(
    practitioner_id: str,
    tenant_id: str,
    *,
    intents: Optional[List[str]] = None,
    limit: int = 100,
    db_path: str = ENGAGEMENT_DB_PATH,
    include_weights: bool = False,
) -> Dict[str, Any]:
    """Jane's voice WITH Acme (tenant-isolated per D1).

    Returns entries + an aggregated signature.
    """
    init_db(db_path)
    con = _connect(db_path)
    try:
        if intents:
            placeholders = ",".join("?" * len(intents))
            rows = con.execute(
                f"SELECT * FROM practitioner_corpus_entries "
                f"WHERE practitioner_id = ? AND tenant_id = ? "
                f"AND intent IN ({placeholders}) "
                f"ORDER BY received_at DESC LIMIT ?",
                (practitioner_id, tenant_id, *intents, limit),
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM practitioner_corpus_entries "
                "WHERE practitioner_id = ? AND tenant_id = ? "
                "ORDER BY received_at DESC LIMIT ?",
                (practitioner_id, tenant_id, limit),
            ).fetchall()
    finally:
        con.close()

    entries = [CorpusEntry.from_row(r) for r in rows]

    # PCR-054m Y strategy: rank by weight if requested
    entries_serialized = [e.as_dict() for e in entries]
    if include_weights and entries:
        try:
            from src.corpus_feedback import get_entry_weights_bulk
            entry_ids = [e.entry_id for e in entries]
            weights = get_entry_weights_bulk(entry_ids, db_path=db_path)
            for d in entries_serialized:
                d["weight"] = weights.get(d["entry_id"], 1.0)
            # Stable sort: weight DESC, then received_at DESC
            entries_serialized.sort(
                key=lambda d: (-d.get("weight", 1.0), d.get("received_at", "")),
            )
            # Re-aggregate signature in weight-ranked order for top-N
            # bigram extraction. We re-derive entry objects in the new
            # order so _aggregate_signature respects the rank.
            id_to_entry = {e.entry_id: e for e in entries}
            entries = [id_to_entry[d["entry_id"]] for d in entries_serialized]
        except Exception as e:
            import logging
            logging.getLogger("murphy.practitioner_corpus").warning(
                "PCR-054m weight ranking failed (falling back to unweighted): %s", e,
            )

    return {
        "practitioner_id": practitioner_id,
        "tenant_id":       tenant_id,
        "entries":         entries_serialized,
        "count":           len(entries),
        "aggregated":      _aggregate_signature(entries),
        "weights_applied": include_weights,
    }


def voice_for_role_jurisdiction(
    role_id: str,
    jurisdiction: str,
    *,
    limit: int = 200,
    db_path: str = ENGAGEMENT_DB_PATH,
) -> Dict[str, Any]:
    """Domain prior — what does US-CA CPA work sound like in general.

    Aggregates across practitioners and tenants because it's
    modeling the PROFESSION. Used as cold-start fallback in 054l.
    """
    init_db(db_path)
    con = _connect(db_path)
    try:
        rows = con.execute(
            "SELECT * FROM practitioner_corpus_entries "
            "WHERE role_id = ? AND jurisdiction = ? "
            "ORDER BY received_at DESC LIMIT ?",
            (role_id, jurisdiction, limit),
        ).fetchall()
    finally:
        con.close()

    entries = [CorpusEntry.from_row(r) for r in rows]
    return {
        "role_id":       role_id,
        "jurisdiction":  jurisdiction,
        "entries":       [e.as_dict() for e in entries],
        "count":         len(entries),
        "aggregated":    _aggregate_signature(entries),
        "is_domain_prior": True,
    }


def recurring_questions(
    practitioner_id: str,
    tenant_id: str,
    *,
    min_repeat: int = 2,
    db_path: str = ENGAGEMENT_DB_PATH,
) -> Dict[str, Any]:
    """Questions the practitioner asks repeatedly at this tenant.

    Bigram-overlap heuristic: if two clarifying_question entries
    share 3+ bigrams from their top-10, they count as 'the same
    question'. Pre-answer these in future drafts.
    """
    init_db(db_path)
    con = _connect(db_path)
    try:
        rows = con.execute(
            "SELECT * FROM practitioner_corpus_entries "
            "WHERE practitioner_id = ? AND tenant_id = ? "
            "AND intent = 'clarifying_question' "
            "ORDER BY received_at DESC",
            (practitioner_id, tenant_id),
        ).fetchall()
    finally:
        con.close()

    entries = [CorpusEntry.from_row(r) for r in rows]

    # Group by bigram overlap
    groups: List[Dict[str, Any]] = []
    for entry in entries:
        sig = json.loads(entry.vocab_signature_json)
        entry_bigrams = set(b[0] for b in sig.get("top_bigrams", []))
        matched = False
        for group in groups:
            overlap = entry_bigrams & group["shared_bigrams"]
            if len(overlap) >= 3:
                group["entries"].append(entry.as_dict())
                group["shared_bigrams"] &= entry_bigrams
                matched = True
                break
        if not matched:
            groups.append({
                "shared_bigrams": entry_bigrams,
                "entries":        [entry.as_dict()],
            })

    recurring = []
    for group in groups:
        if len(group["entries"]) >= min_repeat:
            recurring.append({
                "shared_bigrams": list(group["shared_bigrams"])[:5],
                "occurrences":    len(group["entries"]),
                "samples":        [e["body"][:200] for e in group["entries"][:3]],
            })

    return {
        "practitioner_id":     practitioner_id,
        "tenant_id":           tenant_id,
        "recurring":           recurring,
        "total_questions":     len(entries),
        "recurring_groups":    len(recurring),
    }


def _aggregate_signature(entries: List[CorpusEntry]) -> Dict[str, Any]:
    """Aggregate vocab signatures across multiple entries."""
    if not entries:
        return {"token_count": 0, "top_tokens": [], "top_bigrams": []}

    token_counter: Counter = Counter()
    bigram_counter: Counter = Counter()

    for e in entries:
        try:
            sig = json.loads(e.vocab_signature_json)
        except Exception:
            continue
        for tok, count in sig.get("top_tokens", []):
            token_counter[tok] += count
        for bg, count in sig.get("top_bigrams", []):
            bigram_counter[bg] += count

    return {
        "token_count":   sum(token_counter.values()),
        "unique_tokens": len(token_counter),
        "top_tokens":    token_counter.most_common(20),
        "top_bigrams":   bigram_counter.most_common(15),
        "entries_used":  len(entries),
    }
