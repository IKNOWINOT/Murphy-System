"""
PATCH-FACET-WRITER-R90 (2026-05-28 R90) — Persist tag_extractor output into facet_tags

WHAT THIS IS:
  Idempotent writer: takes extractor output + entity ref, writes to facet_tags
  with INSERT OR IGNORE so the unique constraint protects against duplicates.

WHY IT EXISTS:
  R89 shipped tag_extractor — pure function with no side effects. This module
  is the side-effect partner: durably persist tags so they're queryable across
  the substrate (drill-down, related-tag queries, sort-by-axis).

INPUT:
  entity_table:  str    — which table the entity lives in
  entity_id:     str    — the entity's PK value
  tags:          list[dict] — output from tag_extractor.extract_tags()

OUTPUT:
  {written: int, skipped: int, errors: list}

USAGE:
  >>> from src.tag_extractor import extract_tags
  >>> from src.tag_writer import write_tags
  >>> tags = extract_tags({"entity_table": "provenance_trails", "entity_id": "abc", "payload": {...}})
  >>> result = write_tags("provenance_trails", "abc", tags)
  >>> result
  {"written": 7, "skipped": 0, "errors": []}

DEPENDS ON:
  Stdlib only. hitl_provenance.db with facet_tags table (created R89).

LAST UPDATED: 2026-05-28 R90
"""

import hashlib
import sqlite3
from typing import Any, Dict, List

_DB_PATH = "/var/lib/murphy-production/hitl_provenance.db"


def _tag_id(entity_table: str, entity_id: str, axis: str, tag_value: str) -> str:
    """Deterministic tag_id from the composite key — enables idempotency."""
    key = f"{entity_table}::{entity_id}::{axis}::{tag_value}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def write_tags(entity_table: str, entity_id: str, tags: List[Dict[str, Any]],
               db_path: str = _DB_PATH) -> Dict[str, Any]:
    """
    Persist tags into facet_tags. Idempotent via UNIQUE constraint + INSERT OR IGNORE.

    Returns {written: int, skipped: int, errors: list[str]}.
    Never raises — errors are captured per-tag.
    """
    written = 0
    skipped = 0
    errors: List[str] = []

    if not tags:
        return {"written": 0, "skipped": 0, "errors": []}

    try:
        conn = sqlite3.connect(db_path, timeout=5)
    except Exception as e:
        return {"written": 0, "skipped": 0,
                "errors": [f"connect_failed: {type(e).__name__}: {e}"]}

    try:
        for tag in tags:
            try:
                axis = tag.get("axis", "")
                value = tag.get("tag_value", "")
                if not axis or not value:
                    skipped += 1
                    continue
                tag_id = _tag_id(entity_table, entity_id, axis, value)
                conf = float(tag.get("confidence", 1.0))
                source = tag.get("source", "rule")
                cur = conn.execute(
                    "INSERT OR IGNORE INTO facet_tags "
                    "(tag_id, entity_table, entity_id, axis, tag_value, confidence, source) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (tag_id, entity_table, entity_id, axis, value, conf, source),
                )
                if cur.rowcount > 0:
                    written += 1
                else:
                    skipped += 1
            except Exception as e:
                errors.append(f"tag_failed[{tag.get('tag_value','?')}]: "
                              f"{type(e).__name__}: {e}")
        conn.commit()
    finally:
        conn.close()

    return {"written": written, "skipped": skipped, "errors": errors}


def query_tags_for_entity(entity_table: str, entity_id: str,
                           db_path: str = _DB_PATH) -> List[Dict[str, Any]]:
    """Fetch all tags for a single entity."""
    try:
        conn = sqlite3.connect(db_path, timeout=3)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT axis, tag_value, confidence, source, captured_at "
            "FROM facet_tags WHERE entity_table = ? AND entity_id = ? "
            "ORDER BY axis, tag_value",
            (entity_table, entity_id),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        return [{"error": f"{type(e).__name__}: {e}"}]


def query_entities_by_tag(tag_value: str, entity_table: str = None,
                           db_path: str = _DB_PATH) -> List[Dict[str, Any]]:
    """Drill: fetch all entities matching a tag, optionally filtered by table."""
    try:
        conn = sqlite3.connect(db_path, timeout=3)
        conn.row_factory = sqlite3.Row
        if entity_table:
            rows = conn.execute(
                "SELECT entity_table, entity_id, axis, confidence, captured_at "
                "FROM facet_tags WHERE tag_value = ? AND entity_table = ? "
                "ORDER BY captured_at DESC LIMIT 200",
                (tag_value, entity_table),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT entity_table, entity_id, axis, confidence, captured_at "
                "FROM facet_tags WHERE tag_value = ? "
                "ORDER BY captured_at DESC LIMIT 200",
                (tag_value,),
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        return [{"error": f"{type(e).__name__}: {e}"}]


def tag_distribution(axis: str = None, db_path: str = _DB_PATH) -> List[Dict[str, Any]]:
    """How many entities carry each tag? Useful for tag-cloud display."""
    try:
        conn = sqlite3.connect(db_path, timeout=3)
        conn.row_factory = sqlite3.Row
        if axis:
            rows = conn.execute(
                "SELECT tag_value, axis, COUNT(*) as n FROM facet_tags "
                "WHERE axis = ? GROUP BY tag_value ORDER BY n DESC LIMIT 50",
                (axis,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT tag_value, axis, COUNT(*) as n FROM facet_tags "
                "GROUP BY tag_value ORDER BY n DESC LIMIT 50",
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        return [{"error": f"{type(e).__name__}: {e}"}]


if __name__ == "__main__":
    # Demo
    sample_tags = [
        {"axis": "what", "tag_value": "#compliance", "confidence": 0.9, "source": "rule"},
        {"axis": "when", "tag_value": "#today", "confidence": 1.0, "source": "rule"},
    ]
    print("Writing demo tags...")
    r = write_tags("demo_table", "demo_id_1", sample_tags)
    print(f"Result: {r}")
    print()
    print("Distribution:")
    for d in tag_distribution()[:10]:
        print(f"  {d.get('tag_value','?'):<25} {d.get('axis','?'):<8} n={d.get('n','?')}")
