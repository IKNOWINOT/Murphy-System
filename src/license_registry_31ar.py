"""
license_registry_31ar — Ship 31ar.FOOTER

Mints license IDs for every Murphy-generated artifact and tracks
their lifecycle (active / suspended / terminated / revoked).

Every outbound email, document, attestation, deliverable gets a
license_id minted here. The footer renderer reads from this
registry; the public /verify/<id> endpoint reads from this registry.

The license is owned by Inoni LLC. The customer holds a
"license-while-subscribed" grant per ToS. Footer ownership is
absolute (per founder direction 2026-06-12) — the eye+gear logo
+ verify link are immutable.

License IDs are 16-hex-char (64 bits of entropy). Format:
  mLIC-<8hex>-<8hex>   e.g. mLIC-3f7a8b21-c4d09e15

That's enough entropy to make collisions astronomically unlikely
(2^32 birthday limit per cohort, so 4B docs before risk emerges).
"""
from __future__ import annotations

import hashlib
import logging
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger("murphy.license_31ar")

REGISTRY_DB = "/var/lib/murphy-production/license_registry.db"


def _init() -> None:
    Path(REGISTRY_DB).parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(REGISTRY_DB, timeout=2.0)
    c.execute("""
      CREATE TABLE IF NOT EXISTS licenses (
        license_id    TEXT PRIMARY KEY,
        minted_at     TEXT NOT NULL,
        artifact_kind TEXT NOT NULL,
        artifact_ref  TEXT,
        tenant_id     TEXT,
        recipient     TEXT,
        content_sha256 TEXT,
        status        TEXT NOT NULL DEFAULT 'active',
        status_at     TEXT NOT NULL,
        status_reason TEXT,
        metadata      TEXT
      )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_lic_tenant ON licenses(tenant_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_lic_status ON licenses(status)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_lic_kind   ON licenses(artifact_kind)")
    c.commit()
    c.close()


def mint(
    artifact_kind: str,
    artifact_ref: str = "",
    tenant_id: str = "",
    recipient: str = "",
    content: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """Mint a new license_id and record it. Returns the license_id.

    artifact_kind: 'email_outbound' | 'document' | 'attestation' |
                   'deliverable' | 'pdf' | 'other'
    artifact_ref:  free-form ID (e.g. queue_id, doc filename)
    tenant_id:     owning tenant (empty for free-tier / system)
    recipient:     email addr or party who receives the artifact
    content:       hashed for tamper-evidence (we store sha256 only)
    """
    _init()
    license_id = f"mlic-{secrets.token_hex(4)}-{secrets.token_hex(4)}"
    now = datetime.now(timezone.utc).isoformat()
    content_sha = hashlib.sha256(content.encode()).hexdigest() if content else ""
    try:
        import json as _json
        meta_s = _json.dumps(metadata or {})
        c = sqlite3.connect(REGISTRY_DB, timeout=2.0)
        c.execute(
            """INSERT INTO licenses
               (license_id, minted_at, artifact_kind, artifact_ref, tenant_id,
                recipient, content_sha256, status, status_at, metadata)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (license_id, now, artifact_kind, artifact_ref, tenant_id,
             recipient, content_sha, "active", now, meta_s),
        )
        c.commit()
        c.close()
        logger.info("31ar.mint kind=%s tenant=%s license_id=%s",
                    artifact_kind, tenant_id or "-", license_id)
    except Exception as e:
        logger.warning("31ar.mint write failed: %s — returning unregistered id", e)
    return license_id


def lookup(license_id: str) -> Optional[Dict[str, Any]]:
    """Public verifier lookup. Case-insensitive (CDN lowercases paths)."""
    _init()
    try:
        c = sqlite3.connect(f"file:{REGISTRY_DB}?mode=ro", uri=True, timeout=2.0)
        c.row_factory = sqlite3.Row
        row = c.execute(
            "SELECT * FROM licenses WHERE lower(license_id) = lower(?)",
            (license_id,)
        ).fetchone()
        c.close()
        return dict(row) if row else None
    except Exception as e:
        logger.warning("31ar.lookup failed: %s", e)
        return None


def set_status(license_id: str, new_status: str, reason: str = "") -> bool:
    """Update license status (called by subscription lifecycle hooks)."""
    _init()
    valid = {"active", "suspended", "terminated", "revoked"}
    if new_status not in valid:
        raise ValueError(f"invalid status {new_status}")
    try:
        c = sqlite3.connect(REGISTRY_DB, timeout=2.0)
        c.execute(
            "UPDATE licenses SET status=?, status_at=?, status_reason=? "
            "WHERE license_id=?",
            (new_status, datetime.now(timezone.utc).isoformat(),
             reason, license_id),
        )
        ok = c.total_changes > 0
        c.commit()
        c.close()
        return ok
    except Exception as e:
        logger.warning("31ar.set_status failed: %s", e)
        return False


def bulk_set_tenant_status(tenant_id: str, new_status: str, reason: str = "") -> int:
    """Lifecycle hook: when a tenant cancels, mark all their licenses."""
    _init()
    if new_status not in {"active", "suspended", "terminated", "revoked"}:
        raise ValueError(f"invalid status {new_status}")
    try:
        c = sqlite3.connect(REGISTRY_DB, timeout=2.0)
        c.execute(
            "UPDATE licenses SET status=?, status_at=?, status_reason=? "
            "WHERE tenant_id=?",
            (new_status, datetime.now(timezone.utc).isoformat(),
             reason, tenant_id),
        )
        n = c.total_changes
        c.commit()
        c.close()
        logger.info("31ar.bulk_set kind=%s tenant=%s n=%d", new_status, tenant_id, n)
        return n
    except Exception as e:
        logger.warning("31ar.bulk_set failed: %s", e)
        return 0


_init()
