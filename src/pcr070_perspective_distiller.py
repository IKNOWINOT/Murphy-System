"""PCR-070 Stage 1 — Subject-matter perspective distiller.

Reads accumulated practitioner data and produces per-(role, jurisdiction)
PERSPECTIVE DOCUMENTS — distilled language patterns + common intents +
typical requirements + voice signatures.

Stage 1 is READ-ONLY + ADDITIVE:
  - New table: subject_matter_perspectives (additive, no schema migration)
  - New endpoints: /api/perspective/list, /api/perspective/{role}/{jurisdiction}
  - Reads from practitioner_corpus_entries, engagement_correspondence,
    boundary_loop_requirements, attestation_payloads

Stage 2 (NOT YET) wires this into Rosetta soul renderer. Founder-gated.

Privacy / regulatory:
  - Per L161, perspective extraction NEVER alters regulated attestation
    payloads. We READ them and aggregate vocabulary; we do not modify.
  - Per L160, the perspectives table is append-only (version_id PK,
    superseded_at marker).
  - Per SD-56 audit, this consult happened before code.
"""
from __future__ import annotations
import json
import sqlite3
import time
import uuid
from collections import Counter
from typing import Dict, Any, List, Optional, Tuple

ENGAGEMENT_DB = "/var/lib/murphy-production/engagement_folders.db"

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS subject_matter_perspectives (
    version_id              TEXT PRIMARY KEY,
    role_id                 TEXT NOT NULL,
    jurisdiction            TEXT NOT NULL,
    tenant_id               TEXT,                -- NULL means all-tenant aggregate
    distilled_at            REAL NOT NULL,
    superseded_at           REAL,                -- append-only: filled when a newer version supersedes
    source_corpus_count     INTEGER NOT NULL DEFAULT 0,
    source_corr_count       INTEGER NOT NULL DEFAULT 0,
    source_req_count        INTEGER NOT NULL DEFAULT 0,
    source_attest_count     INTEGER NOT NULL DEFAULT 0,
    perspective_json        TEXT NOT NULL,
    UNIQUE(role_id, jurisdiction, tenant_id, distilled_at)
);
CREATE INDEX IF NOT EXISTS idx_persp_role_jur ON subject_matter_perspectives(role_id, jurisdiction);
CREATE INDEX IF NOT EXISTS idx_persp_current ON subject_matter_perspectives(role_id, jurisdiction) WHERE superseded_at IS NULL;
"""

# Stop words removed during phrase scoring (common English noise)
_STOP = {
    "the","a","an","i","i'm","is","are","was","were","be","been","being",
    "and","or","but","of","to","for","in","on","at","by","with","from",
    "this","that","these","those","it","its","my","your","our","their",
    "as","can","will","would","should","could","may","might","do","does",
    "did","have","has","had","not","no","so","if","than","then","you",
    "he","she","we","they","what","when","where","why","how","which",
    "what's","when's","where's","why's","how's","which's","re:",
}


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(ENGAGEMENT_DB, timeout=5.0)
    c.row_factory = sqlite3.Row
    return c


def ensure_schema() -> None:
    """Idempotent — creates the perspectives table if missing."""
    c = _conn()
    try:
        c.executescript(_SCHEMA_SQL)
        c.commit()
    finally:
        c.close()


def _safe_json_loads(s: str | None) -> Any:
    if not s:
        return None
    try:
        return json.loads(s)
    except (ValueError, TypeError):
        return None


def _harvest_corpus(role_id: str, jurisdiction: str, tenant_id: Optional[str]) -> List[Dict[str, Any]]:
    """Pull practitioner_corpus_entries for the (role, jur) bucket."""
    c = _conn()
    try:
        sql = ("SELECT entry_id, intent, body, vocab_signature_json, "
               "received_at FROM practitioner_corpus_entries "
               "WHERE role_id=? AND jurisdiction=?")
        args: Tuple[Any, ...] = (role_id, jurisdiction)
        if tenant_id:
            sql += " AND tenant_id=?"
            args = (role_id, jurisdiction, tenant_id)
        sql += " ORDER BY received_at DESC LIMIT 500"
        rows = c.execute(sql, args).fetchall()
        return [dict(r) for r in rows]
    finally:
        c.close()


def _harvest_correspondence(role_id: str, jurisdiction: str, tenant_id: Optional[str]) -> List[Dict[str, Any]]:
    """Pull engagement_correspondence joined to engagement_folders for role+jur."""
    c = _conn()
    try:
        sql = ("SELECT ec.corr_id, ec.classified_intent, ec.body, "
               "ec.direction, ec.received_at "
               "FROM engagement_correspondence ec "
               "JOIN engagement_folders ef ON ec.engagement_id = ef.engagement_id "
               "WHERE ef.role_id=? AND ef.jurisdiction_required=? "
               "AND ec.direction='in'")
        args: Tuple[Any, ...] = (role_id, jurisdiction)
        if tenant_id:
            sql += " AND ef.tenant_id=?"
            args = (role_id, jurisdiction, tenant_id)
        sql += " ORDER BY ec.received_at DESC LIMIT 500"
        rows = c.execute(sql, args).fetchall()
        return [dict(r) for r in rows]
    finally:
        c.close()


def _harvest_requirements(role_id: str) -> List[Dict[str, Any]]:
    """Pull boundary_loop_requirements — these are role-agnostic at row
    level but the role_id is in the parent dispatch context."""
    c = _conn()
    try:
        rows = c.execute(
            "SELECT requirement_id, requirement_text, category, status "
            "FROM boundary_loop_requirements "
            "ORDER BY req_id_row DESC LIMIT 200"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        c.close()


def _harvest_attestations(role_id: str, jurisdiction: str) -> int:
    """Count of attestation payloads — body never read, only counted
    (regulatory safety per L161)."""
    c = _conn()
    try:
        row = c.execute(
            "SELECT COUNT(*) AS n FROM attestation_payloads ap "
            "JOIN engagement_folders ef ON ap.engagement_id = ef.engagement_id "
            "WHERE ef.role_id=? AND ef.jurisdiction_required=?",
            (role_id, jurisdiction),
        ).fetchone()
        return int(row["n"]) if row else 0
    finally:
        c.close()


def _tokenize(text: str) -> List[str]:
    """Lowercase + split on whitespace + strip punctuation; remove stop words."""
    import re
    tokens = re.findall(r"[a-zA-Z][a-zA-Z'\-]+", (text or "").lower())
    return [t for t in tokens if t not in _STOP and len(t) > 2]


def _top_phrases(bodies: List[str], n: int = 20) -> List[Tuple[str, int]]:
    """Get top n-gram phrases (bigrams + trigrams) across bodies."""
    big = Counter()
    tri = Counter()
    for body in bodies:
        toks = _tokenize(body)
        for i in range(len(toks) - 1):
            big[(toks[i], toks[i+1])] += 1
        for i in range(len(toks) - 2):
            tri[(toks[i], toks[i+1], toks[i+2])] += 1
    # Score: trigrams worth 1.5x bigrams (more specific)
    scored = []
    for ph, cnt in big.most_common(n * 2):
        scored.append((" ".join(ph), cnt, "bigram"))
    for ph, cnt in tri.most_common(n):
        scored.append((" ".join(ph), int(cnt * 1.5), "trigram"))
    scored.sort(key=lambda x: x[1], reverse=True)
    seen = set()
    out = []
    for ph, sc, _kind in scored:
        if ph in seen:
            continue
        seen.add(ph)
        out.append((ph, sc))
        if len(out) >= n:
            break
    return out


def _intent_distribution(rows: List[Dict[str, Any]], key: str) -> Dict[str, int]:
    """Counter of intents in a list of rows."""
    return dict(Counter((r.get(key) or "unknown") for r in rows))


def distill(role_id: str, jurisdiction: str, tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """Produce a perspective document for (role_id, jurisdiction[, tenant_id])."""
    ensure_schema()
    corpus = _harvest_corpus(role_id, jurisdiction, tenant_id)
    corr = _harvest_correspondence(role_id, jurisdiction, tenant_id)
    reqs = _harvest_requirements(role_id)
    attest_count = _harvest_attestations(role_id, jurisdiction)

    # Combine all practitioner-voice bodies
    voice_bodies = [r["body"] for r in corpus] + [r["body"] for r in corr]
    top_phrases = _top_phrases(voice_bodies, n=15)

    # Intent distribution
    corpus_intents = _intent_distribution(corpus, "intent")
    corr_intents = _intent_distribution(corr, "classified_intent")

    # Requirement categories
    req_cats = _intent_distribution(reqs, "category")
    req_statuses = _intent_distribution(reqs, "status")

    # Recency
    most_recent = 0.0
    for src in (corpus, corr):
        for r in src:
            ts = r.get("received_at") or 0
            if ts and ts > most_recent:
                most_recent = ts

    perspective = {
        "role_id": role_id,
        "jurisdiction": jurisdiction,
        "tenant_id": tenant_id,
        "distilled_at": time.time(),
        "sources": {
            "corpus_entries": len(corpus),
            "correspondence_in": len(corr),
            "boundary_requirements": len(reqs),
            "attestations_count_only": attest_count,
        },
        "voice_signature": {
            "top_phrases": [{"phrase": p, "weight": w} for p, w in top_phrases],
        },
        "intent_distribution": {
            "from_corpus": corpus_intents,
            "from_correspondence": corr_intents,
        },
        "work_demands": {
            "by_category": req_cats,
            "by_status": req_statuses,
        },
        "freshness": {
            "most_recent_signal_at": most_recent,
            "age_hours_at_distill": round((time.time() - most_recent) / 3600, 1) if most_recent else None,
        },
        "regulatory_note": "Attestation payload bodies are counted, not read (L161).",
    }
    return perspective


def persist(perspective: Dict[str, Any]) -> str:
    """Write the perspective to subject_matter_perspectives + mark older
    versions for same (role, jur, tenant) as superseded. Returns version_id."""
    ensure_schema()
    role_id = perspective["role_id"]
    jur = perspective["jurisdiction"]
    tenant = perspective.get("tenant_id")
    now = time.time()
    vid = f"persp_{uuid.uuid4().hex[:16]}"
    c = _conn()
    try:
        # Append-only supersede: mark existing current rows as superseded
        c.execute(
            "UPDATE subject_matter_perspectives "
            "SET superseded_at=? "
            "WHERE role_id=? AND jurisdiction=? "
            "AND (tenant_id IS ? OR tenant_id=?) "
            "AND superseded_at IS NULL",
            (now, role_id, jur, tenant, tenant or ""),
        )
        c.execute(
            "INSERT INTO subject_matter_perspectives "
            "(version_id, role_id, jurisdiction, tenant_id, distilled_at, "
            "source_corpus_count, source_corr_count, source_req_count, "
            "source_attest_count, perspective_json) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                vid, role_id, jur, tenant, now,
                perspective["sources"]["corpus_entries"],
                perspective["sources"]["correspondence_in"],
                perspective["sources"]["boundary_requirements"],
                perspective["sources"]["attestations_count_only"],
                json.dumps(perspective),
            ),
        )
        c.commit()
        return vid
    finally:
        c.close()


def list_current() -> List[Dict[str, Any]]:
    """List the currently-active perspective per (role, jur, tenant)."""
    ensure_schema()
    c = _conn()
    try:
        rows = c.execute(
            "SELECT version_id, role_id, jurisdiction, tenant_id, "
            "distilled_at, source_corpus_count, source_corr_count, "
            "source_req_count, source_attest_count "
            "FROM subject_matter_perspectives "
            "WHERE superseded_at IS NULL "
            "ORDER BY distilled_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        c.close()


def get_current(role_id: str, jurisdiction: str, tenant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Get the current perspective doc for (role, jur, tenant).
    Case-insensitive on role_id + jurisdiction (Cloudflare lowercases path segments — L153)."""
    ensure_schema()
    c = _conn()
    try:
        row = c.execute(
            "SELECT perspective_json FROM subject_matter_perspectives "
            "WHERE LOWER(role_id)=LOWER(?) AND LOWER(jurisdiction)=LOWER(?) "
            "AND (tenant_id IS ? OR tenant_id=?) "
            "AND superseded_at IS NULL "
            "ORDER BY distilled_at DESC LIMIT 1",
            (role_id, jurisdiction, tenant_id, tenant_id or ""),
        ).fetchone()
        if not row:
            return None
        return json.loads(row["perspective_json"])
    finally:
        c.close()


def distill_and_persist(role_id: str, jurisdiction: str, tenant_id: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
    p = distill(role_id, jurisdiction, tenant_id)
    vid = persist(p)
    return vid, p
