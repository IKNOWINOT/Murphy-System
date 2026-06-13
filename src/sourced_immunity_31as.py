"""
sourced_immunity_31as — Ship 31as.SOURCED_IMMUNITY

Adds provenance to the immune-memory and antibody-intervention systems
so the Immunology Department can write documentation that CITES evidence
instead of waving at frequency counters.

The deeper problem this fixes:
  Today's immune_memory.pattern says "thing failed" but not WHY/WHERE.
  When the Pattern Analyst tries to document an antibody they can't
  point to anything. This module makes every observation traceable.

NEW COLUMNS (added to existing tables, no schema break):

  source_kind       e.g. "user_email" / "qa_test" / "validator_attestation"
                         / "log_pattern" / "founder_directive"
                         / "ipn_failure" / "drift_observation"
  source_ref        opaque ID — email Message-ID, test name, log_id,
                    validator's mLIC, founder session_id, etc.
  source_excerpt    first 300 chars of offending content (smart-redacted)
  source_url        optional — public URL if available
  discovered_by     which agent / role / automation noticed it
  discovered_at     timestamp (separate from "last_seen")
  evidence_count    how many independent sources confirmed it
                    (proves it's not a one-off)

SMART REDACTION (option B, picked by founder 2026-06-12):
  Excerpts are scrubbed of PII patterns (email addrs, phone, SSN,
  credit-card-like, IPs) before storage. Non-PII context is preserved
  so Immunology curators can read what happened without exposing
  user data.

Used by:
  • immune_memory.record() — add source kwargs
  • antibody.record_intervention() — add source kwargs
  • drift_events insert — add source kwargs
  • Immunology dashboard reads these to render evidence trails
"""
from __future__ import annotations

import hashlib
import logging
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger("murphy.sourced_immunity_31as")

IMMUNE_DB    = "/var/lib/murphy-production/immune.db"
ANTIBODY_DB  = "/var/lib/murphy-production/antibody_interventions.db"

# ── PII redaction patterns ─────────────────────────────────────────
_RE_EMAIL = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
_RE_PHONE = re.compile(r'\+?\d[\d\s\-\(\)]{8,}\d')
_RE_SSN   = re.compile(r'\b\d{3}-\d{2}-\d{4}\b')
_RE_CC    = re.compile(r'\b(?:\d{4}[\s-]?){3}\d{4}\b')
_RE_IP    = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')
_RE_UUID  = re.compile(r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b', re.I)


def smart_redact(text: str, max_len: int = 300) -> str:
    """Replace PII patterns with hashed tokens; preserve everything else.

    The hash uses sha256 truncated to 8 chars — enough that the
    Immunology curator can see when two events involve the SAME
    redacted identity, without exposing the raw value.
    """
    if not text:
        return ""
    snippet = text[:max_len]

    def _hash_token(prefix: str, m: re.Match) -> str:
        h = hashlib.sha256(m.group(0).encode()).hexdigest()[:8]
        return f"[{prefix}:{h}]"

    snippet = _RE_EMAIL.sub(lambda m: _hash_token("email", m), snippet)
    snippet = _RE_PHONE.sub(lambda m: _hash_token("phone", m), snippet)
    snippet = _RE_SSN.sub(lambda m: _hash_token("ssn", m), snippet)
    snippet = _RE_CC.sub(lambda m: _hash_token("card", m), snippet)
    snippet = _RE_IP.sub(lambda m: _hash_token("ip", m), snippet)
    snippet = _RE_UUID.sub(lambda m: _hash_token("uuid", m), snippet)
    return snippet


# ── Schema migrations (idempotent) ─────────────────────────────────

_SOURCE_COLS = [
    ("source_kind",     "TEXT"),
    ("source_ref",      "TEXT"),
    ("source_excerpt",  "TEXT"),
    ("source_url",      "TEXT"),
    ("discovered_by",   "TEXT"),
    ("discovered_at",   "TEXT"),
    ("evidence_count",  "INTEGER DEFAULT 1"),
]


def _add_columns_if_missing(db_path: str, table: str) -> List[str]:
    """Idempotently add source_* columns to a table. Returns added cols."""
    if not Path(db_path).exists():
        # Don't auto-create; that's another system's job
        logger.info("31as.migrate skip — %s missing", db_path)
        return []
    added = []
    try:
        c = sqlite3.connect(db_path, timeout=5.0)
        existing = {row[1] for row in c.execute(f"PRAGMA table_info({table})")}
        for col, ctype in _SOURCE_COLS:
            if col not in existing:
                try:
                    c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ctype}")
                    added.append(col)
                except sqlite3.OperationalError as e:
                    logger.warning("31as alter %s.%s failed: %s",
                                   table, col, e)
        c.commit()
        c.close()
        if added:
            logger.info("31as.migrate %s.%s: added %s",
                        db_path, table, added)
    except Exception as e:
        logger.warning("31as migrate %s failed: %s", db_path, e)
    return added


def migrate_all() -> Dict[str, List[str]]:
    """Add source columns to immune_memory + antibody_interventions."""
    return {
        "immune_memory":          _add_columns_if_missing(IMMUNE_DB, "immune_memory"),
        "drift_events":           _add_columns_if_missing(IMMUNE_DB, "drift_events"),
        "antibody_interventions": _add_columns_if_missing(ANTIBODY_DB,
                                                          "antibody_interventions"),
    }


# ── Write-helpers (used by upstream recorders) ─────────────────────

def record_immune_event(
    pattern: str,
    severity: str = "info",
    source_kind: str = "unspecified",
    source_ref: str = "",
    source_excerpt: str = "",
    source_url: str = "",
    discovered_by: str = "system",
) -> Optional[int]:
    """Record an immune-memory observation with source tags.

    Returns the new id, or None on failure.
    If a row with the same pattern already exists, INCREMENT frequency
    and evidence_count, and refresh discovered_at.
    """
    migrate_all()
    excerpt = smart_redact(source_excerpt)
    now_iso = datetime.now(timezone.utc).isoformat()
    now_unix = datetime.now(timezone.utc).timestamp()
    try:
        c = sqlite3.connect(IMMUNE_DB, timeout=5.0)
        existing = c.execute(
            "SELECT id, frequency, COALESCE(evidence_count, 1) "
            "FROM immune_memory WHERE pattern = ?", (pattern,)
        ).fetchone()
        if existing:
            row_id, freq, evi = existing
            c.execute(
                "UPDATE immune_memory SET frequency = ?, last_seen = ?, "
                "evidence_count = ?, source_kind = COALESCE(source_kind, ?), "
                "source_ref = COALESCE(source_ref, ?), "
                "source_excerpt = COALESCE(source_excerpt, ?), "
                "source_url = COALESCE(source_url, ?), "
                "discovered_by = COALESCE(discovered_by, ?), "
                "discovered_at = COALESCE(discovered_at, ?) "
                "WHERE id = ?",
                (freq + 1, now_unix, evi + 1, source_kind, source_ref,
                 excerpt, source_url, discovered_by, now_iso, row_id),
            )
            c.commit(); c.close()
            return row_id
        cur = c.execute(
            "INSERT INTO immune_memory (pattern, frequency, last_seen, severity, "
            "source_kind, source_ref, source_excerpt, source_url, discovered_by, "
            "discovered_at, evidence_count) "
            "VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, 1)",
            (pattern, now_unix, severity, source_kind, source_ref,
             excerpt, source_url, discovered_by, now_iso),
        )
        new_id = cur.lastrowid
        c.commit(); c.close()
        return new_id
    except Exception as e:
        logger.warning("31as record_immune_event failed: %s", e)
        return None


def evidence_trail(pattern_or_id: Any) -> Dict[str, Any]:
    """Read back the full evidence trail for a pattern (for Immunology UI).

    Accepts either the int id or the pattern string.
    """
    migrate_all()
    try:
        c = sqlite3.connect(f"file:{IMMUNE_DB}?mode=ro", uri=True, timeout=5.0)
        c.row_factory = sqlite3.Row
        if isinstance(pattern_or_id, int) or (
            isinstance(pattern_or_id, str) and pattern_or_id.isdigit()
        ):
            row = c.execute(
                "SELECT * FROM immune_memory WHERE id = ?",
                (int(pattern_or_id),)
            ).fetchone()
        else:
            row = c.execute(
                "SELECT * FROM immune_memory WHERE pattern = ?",
                (pattern_or_id,)
            ).fetchone()
        c.close()
        return dict(row) if row else {}
    except Exception as e:
        logger.warning("31as evidence_trail failed: %s", e)
        return {}


def documentation_paragraph(pattern_or_id: Any) -> str:
    """Render a human-readable evidence paragraph for an antibody/pattern.

    This is what the Immunology Department's documentation tool calls
    when writing up a new antibody. Gives the curator a starting draft.
    """
    row = evidence_trail(pattern_or_id)
    if not row:
        return "No evidence trail recorded for this pattern."
    parts = []
    parts.append(f"Pattern: {row.get('pattern', '(unknown)')}")
    parts.append(f"Severity: {row.get('severity', 'unspecified')}")
    evi = row.get('evidence_count', 1)
    parts.append(f"Independent confirmations: {evi}")
    src_kind = row.get('source_kind') or "unspecified"
    src_ref  = row.get('source_ref') or "n/a"
    parts.append(f"First observed via {src_kind} (ref={src_ref})")
    if row.get('discovered_by'):
        parts.append(f"Discovered by: {row['discovered_by']}")
    if row.get('discovered_at'):
        parts.append(f"Discovered at: {row['discovered_at']}")
    if row.get('source_excerpt'):
        parts.append(f"Sample (PII-redacted): {row['source_excerpt']}")
    if row.get('source_url'):
        parts.append(f"Reference URL: {row['source_url']}")
    return "\n".join("  • " + p for p in parts)


# Run migration on module load so existing systems pick up the new cols
try:
    migrate_all()
except Exception as e:
    logger.warning("31as auto-migrate failed: %s", e)
