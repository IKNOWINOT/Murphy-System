"""Turn-end crystallization: GhostLayer + PSI → DLF-Lite v2 package."""
import json, sqlite3, hashlib, logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_PKG_DIR = Path("/var/lib/murphy-production/dlf_packages")
_INDEX_DB = "/var/lib/murphy-production/dlf_packages.db"


def _init_index():
    _PKG_DIR.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(_INDEX_DB, timeout=10.0)
    c.execute("""
        CREATE TABLE IF NOT EXISTS packages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            correlation_id TEXT NOT NULL,
            blob_path TEXT NOT NULL,
            checksum TEXT NOT NULL,
            audit_state TEXT,
            hygiene_status TEXT,
            byte_size INTEGER,
            created_at TEXT NOT NULL
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_pkg_corr ON packages(correlation_id)")
    c.commit(); c.close()


def crystallize(correlation_id: str,
                outcome: str = "sent",
                hygiene_override: Optional[str] = None) -> Optional[str]:
    """Crystallize a turn into a DLF-Lite v2 package.

    Reads GhostLayer snapshots + PSI events for the correlation_id,
    builds threads/nodes/weaves, calls dlf_r.pack() with v2 metadata, writes
    the package blob + index row. Returns the package_id on success, None
    on failure. Never raises.
    """
    try:
        from src.loom_lite.ghost_layer import list_for_turn as _ghost_list
        from src.loom_lite.psi_history  import list_for_turn as _psi_list
        from src.dlf_r import pack as _pack

        snaps = _ghost_list(correlation_id)
        ops   = _psi_list(correlation_id)
        if not snaps and not ops:
            return None

        # Build DLF v2 shape: each snapshot becomes a thread+node pair,
        # each PSI op becomes a thread, weaves link them in SEQUENCE.
        threads = []
        nodes   = []
        weaves  = []
        node_ids = []

        for i, s in enumerate(snaps):
            tid = f"thr_snap_{i}"
            nid = f"node_snap_{i}_{s['phase']}"
            threads.append({
                "id": tid,
                "payload": json.dumps(s["payload"])[:5000],
                "created_at_utc": s["created_at"],
                "metadata": {"kind": "ghost_snapshot", "phase": s["phase"]},
                "symbol_signature": s["phase"],
            })
            nodes.append({
                "id": nid,
                "label": s["phase"],
                "thread_refs": [tid],
                "metadata": {
                    "kind": "snapshot",
                    "phase": s["phase"],
                    # v2 fields
                    "authority_role": "derived_low_authority",
                    "hygiene_status": "USABLE_CREATIVE_SUBSTRATE",
                    "substrate_role": "background",
                    "provenance_mode": "creative_background_not_factual_authority",
                },
            })
            node_ids.append(nid)

        # SEQUENCE weaves linking snapshots in order
        for i in range(1, len(node_ids)):
            weaves.append({
                "id": f"weave_seq_{i}",
                "source": node_ids[i-1],
                "target": node_ids[i],
                "type": "SEQUENCE",
                "relation_family": "ORDER",
                "confidence": 1.0,
                "provenance": "loom_lite.precipitator",
            })

        # PSI operations as their own threads + a meta-node
        if ops:
            for j, o in enumerate(ops):
                tid = f"thr_psi_{j}"
                threads.append({
                    "id": tid,
                    "payload": json.dumps(o)[:2000],
                    "created_at_utc": o["created_at"],
                    "metadata": {"kind": "psi_event"},
                    "symbol_signature": o["operation"],
                })

        # Hygiene determination
        hygiene = hygiene_override
        if not hygiene:
            # If any snapshot phase contains "hold" or "revise" outcome -> reject
            for s in snaps:
                p = (s.get("payload") or {})
                if str(p.get("verdict","")).lower() in ("hold", "revise"):
                    hygiene = "REJECT_FUTURE_SELECTION"
                    break
            if not hygiene:
                hygiene = ("USABLE_CREATIVE_SUBSTRATE" if outcome == "sent"
                           else "REJECT_FUTURE_SELECTION")

        # Audit state — at minimum we know it was AVAILABLE; if any node has a
        # CREATIVE_SUBSTRATE weave, we'd mark CONFIRMED. v1 starts at AVAILABLE.
        audit_state = "DLF_AVAILABLE"

        metadata = {
            "format_addendum": "DLF-LITE",
            "format_addendum_version": "2.0",
            "correlation_id": correlation_id,
            "outcome": outcome,
            "audit_state": audit_state,
            "hygiene_status": hygiene,
            "turn_node_count": len(nodes),
            "turn_op_count": len(ops),
        }

        blob = _pack(
            threads=threads, nodes=nodes, weaves=weaves,
            metadata=metadata, creator="loom_lite.precipitator",
            compress=True,
        )

        # Write to disk + index
        _init_index()
        pkg_id = hashlib.sha1(blob).hexdigest()[:16]
        blob_path = _PKG_DIR / f"{pkg_id}.dlf-lite"
        blob_path.write_bytes(blob)

        c = sqlite3.connect(_INDEX_DB, timeout=10.0)
        c.execute(
            "INSERT INTO packages (correlation_id, blob_path, checksum, "
            "audit_state, hygiene_status, byte_size, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (correlation_id, str(blob_path),
             hashlib.sha256(blob).hexdigest()[:32],
             audit_state, hygiene, len(blob),
             datetime.now(timezone.utc).isoformat()),
        )
        c.commit(); c.close()
        logger.info(
            "Ship 31cw precipitator: turn %s crystallized as %s (hygiene=%s, %d bytes)",
            correlation_id, pkg_id, hygiene, len(blob),
        )
        return pkg_id

    except Exception as exc:
        logger.warning("Ship 31cw precipitator failed (turn continues): %s", exc)
        return None
