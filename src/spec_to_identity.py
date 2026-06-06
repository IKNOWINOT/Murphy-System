"""
PATCH-WIRE9-001 (2026-05-28 R54) — Extracted Spec → Identity Layer

WHAT THIS IS:
  When a customer uploads a document (requirements, business plan, design
  brief, etc.) and document_processor extracts structured content, this
  wire absorbs that content into Murphy's identity layer so future
  agent dispatches see the new context.

WHY IT EXISTS:
  Wire #7 (import_gate) said WHAT documents are required for a chain.
  document_processor extracts the content.
  But the extracted content was going nowhere — it sat in document_metadata.
  Murphy's RosettaSoul.world_context and DLF-R snapshots had no way to
  receive it. So an uploaded business plan never shaped Murphy's behavior.

  Wire #9 closes that loop: extracted spec → world_context update +
  DLF-R snapshot capture + per-tenant scoping.

HOW IT FITS:
  upload → document_processor.upload_document() → DocumentMetadata
                                                       ↓
                                            spec_to_identity.absorb()
                                                       ↓
                            ┌──────────────────────────┴───────────────┐
                            ↓                                          ↓
            RosettaSoul.world_context updated      DLF-R snapshot packed
                            ↓                                          ↓
            future agent.check() sees new note     historical state preserved

KEY CONCEPTS:
  - absorb(): one call ingests extracted content into both layers
  - tenant_scope: scopes ingestion to a tenant so cross-tenant docs don't leak
  - document_type → context_key mapping (REQUIREMENTS → "active_requirements" etc)
  - snapshot_after_absorb: optionally pack DLF-R state for historical record

ENDPOINTS / PUBLIC SURFACE:
  absorb(document_id, content_extract, document_type, tenant_id=None,
         snapshot=True) -> Dict
  get_absorbed_specs(tenant_id=None) -> List[Dict]
  get_world_context_for_tenant(tenant_id) -> Dict

DEPENDENCIES:
  - src.rosetta_core.get_rosetta_soul (writes to .world_context)
  - src.dlf_r.pack (optional snapshot)
  - own DB: spec_absorption.db (tracks what was absorbed when)

KNOWN LIMITS:
  - World context is a singleton — tenant scoping is via context_key prefix
    (e.g. "t1.requirements"), not a real tenant-isolated soul
  - Phase C tenant isolation will replace prefix-scoping with per-tenant souls
  - Doesn't yet re-trigger pending chains when new specs arrive

LAST UPDATED: 2026-05-28 R54
"""

import logging
import os
import sqlite3
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("spec_to_identity")

_DB_PATH = "/var/lib/murphy-production/spec_absorption.db"

# Mapping: document_type → context_key in world_context
_TYPE_TO_KEY: Dict[str, str] = {
    "requirements":   "active_requirements",
    "business":       "business_context",
    "design":         "design_brief",
    "architecture":   "system_architecture",
    "specification":  "active_specifications",
    "equipment_list": "equipment_inventory",
    "technical":      "technical_context",
}


def _ensure_db() -> None:
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(_DB_PATH, timeout=3)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS spec_absorptions (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id       TEXT,
                document_type     TEXT NOT NULL,
                context_key       TEXT NOT NULL,
                tenant_id         TEXT,
                content_preview   TEXT,
                content_length    INTEGER DEFAULT 0,
                absorbed_at       TEXT DEFAULT CURRENT_TIMESTAMP,
                dlfr_snapshot_id  TEXT,
                wire_version      TEXT DEFAULT 'WIRE9-001'
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sa_tenant ON spec_absorptions(tenant_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sa_type ON spec_absorptions(document_type)")
        conn.commit()
    finally:
        conn.close()


def _make_context_key(doc_type: str, tenant_id: Optional[str]) -> str:
    """Map doc type → world_context key, tenant-scoped if tenant_id."""
    base = _TYPE_TO_KEY.get(doc_type.lower(), f"misc_{doc_type.lower()}")
    if tenant_id:
        return f"{tenant_id}.{base}"
    return f"platform.{base}"


def _update_rosetta_world_context(key: str, content: str) -> bool:
    """Write extracted content into RosettaSoul.world_context singleton."""
    try:
        from src.rosetta_core import get_rosetta_soul
        soul = get_rosetta_soul()
        if not hasattr(soul, "world_context"):
            return False
        # world_context is a Dict per memory R34
        soul.world_context[key] = {
            "content": content[:5000],  # cap to avoid bloating soul
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "wire_version": "WIRE9-001",
        }
        return True
    except Exception as e:
        logger.debug("rosetta world_context update failed: %s", e)
        return False


def _snapshot_dlfr(label: str, key: str, content: str) -> Optional[str]:
    """Pack a DLF-R snapshot of the current absorbed spec. Returns blob id if available."""
    try:
        from src.dlf_r import pack
        snapshot = {
            "label": label,
            "context_key": key,
            "content_preview": content[:1000],
            "absorbed_at": datetime.now(timezone.utc).isoformat(),
            "wire_version": "WIRE9-001",
        }
        blob = pack(snapshot)
        # blob is bytes — return its first 12 chars as ID for traceability
        if blob:
            import hashlib
            return hashlib.md5(blob).hexdigest()[:12] if isinstance(blob, bytes) else None
    except Exception as e:
        logger.debug("dlfr snapshot failed: %s", e)
    return None


def absorb(
    document_id: str,
    content_extract: str,
    document_type: str,
    tenant_id: Optional[str] = None,
    snapshot: bool = True,
) -> Dict[str, Any]:
    """
    Absorb extracted document content into Murphy's identity layer.

    Args:
        document_id: unique identifier from document_processor
        content_extract: extracted structured content (string or JSON)
        document_type: REQUIREMENTS | BUSINESS | DESIGN | etc.
        tenant_id: optional tenant scope (defaults to platform)
        snapshot: if True, also pack a DLF-R snapshot

    Returns:
        {
          "document_id", "context_key", "tenant_id",
          "rosetta_updated", "dlfr_snapshot_id",
          "content_length", "wire_version", "absorbed_at"
        }
    """
    _ensure_db()

    context_key = _make_context_key(document_type, tenant_id)
    rosetta_ok = _update_rosetta_world_context(context_key, content_extract)
    snapshot_id = None
    if snapshot:
        snapshot_id = _snapshot_dlfr(
            label=f"spec_absorb:{document_id}",
            key=context_key,
            content=content_extract,
        )

    try:
        conn = sqlite3.connect(_DB_PATH, timeout=3)
        try:
            conn.execute(
                """INSERT INTO spec_absorptions
                   (document_id, document_type, context_key, tenant_id,
                    content_preview, content_length, dlfr_snapshot_id)
                   VALUES (?,?,?,?,?,?,?)""",
                (document_id, document_type, context_key, tenant_id,
                 content_extract[:500], len(content_extract or ""), snapshot_id)
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.warning("absorb DB write failed: %s", e)

    return {
        "document_id": document_id,
        "context_key": context_key,
        "tenant_id": tenant_id,
        "document_type": document_type,
        "rosetta_updated": rosetta_ok,
        "dlfr_snapshot_id": snapshot_id,
        "content_length": len(content_extract or ""),
        "absorbed_at": datetime.now(timezone.utc).isoformat(),
        "wire_version": "WIRE9-001",
    }


def get_absorbed_specs(tenant_id: Optional[str] = None,
                       limit: int = 20) -> List[Dict[str, Any]]:
    """Inspection API — list recently absorbed specs."""
    _ensure_db()
    try:
        conn = sqlite3.connect(f"file:{_DB_PATH}?mode=ro", uri=True, timeout=2)
        try:
            conn.row_factory = sqlite3.Row
            if tenant_id:
                cur = conn.execute(
                    "SELECT * FROM spec_absorptions WHERE tenant_id = ? "
                    "ORDER BY absorbed_at DESC LIMIT ?", (tenant_id, limit)
                )
            else:
                cur = conn.execute(
                    "SELECT * FROM spec_absorptions ORDER BY absorbed_at DESC LIMIT ?",
                    (limit,)
                )
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()
    except Exception:
        return []


def get_world_context_for_tenant(tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """Read current world_context entries scoped to a tenant."""
    try:
        from src.rosetta_core import get_rosetta_soul
        soul = get_rosetta_soul()
        ctx = getattr(soul, "world_context", {}) or {}
        prefix = f"{tenant_id}." if tenant_id else "platform."
        scoped = {k: v for k, v in ctx.items() if k.startswith(prefix)}
        return {
            "tenant_id": tenant_id,
            "scoped_keys": list(scoped.keys()),
            "scoped_entries": scoped,
            "all_keys": list(ctx.keys()),
            "wire_version": "WIRE9-001",
        }
    except Exception as e:
        return {"error": str(e), "wire_version": "WIRE9-001"}


if __name__ == "__main__":
    import json as _j
    print("── absorb sample ──")
    r = absorb(
        document_id="doc_1",
        content_extract="Build SaaS MVP for SMB invoicing. Stripe payments required. 3-month MVP timeline.",
        document_type="REQUIREMENTS",
        tenant_id="t1",
    )
    print(_j.dumps(r, indent=2, default=str))
    print("\n── get_absorbed_specs(t1) ──")
    print(_j.dumps(get_absorbed_specs("t1"), indent=2, default=str)[:500])
    print("\n── get_world_context_for_tenant(t1) ──")
    print(_j.dumps(get_world_context_for_tenant("t1"), indent=2, default=str)[:500])
