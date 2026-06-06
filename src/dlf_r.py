"""
PATCH-DLF-R-001 — DLF-R (DLF-Lite + Rosetta hybrid)
====================================================

WHAT THIS IS:
  A portable semantic continuity format that bundles DLF-Lite's three layers
  (Threads, Nodes, Weaves + provenance) with Murphy's native Rosetta cognitive
  state (souls, stances, characters, world_context, lens). The result is a
  single envelope a receiving system can use to BOTH see the relationships
  AND rehydrate the perspective that produced them.

WHY IT EXISTS:
  Plain DLF-Lite preserves WHAT was decided. Rosetta state preserves WHO
  decided it (stance, role, bias, hitl threshold). Either alone loses half
  the picture. Together: a receiver can re-evaluate the same Weaves under
  a different stance, audit why a contradiction was tolerated, or replay
  the swarm's reasoning under the original constitution.

HOW IT FITS:
  - Producers: any Murphy subsystem can call DLFR.pack(...) to emit a package.
    Initial integration points: swarm_bus, incident_router, mind_cycle commits.
  - Consumers: any Murphy subsystem (or external) can call DLFR.load(...).
    Rosetta state is rehydrated into a RosettaSoul snapshot dict; semantic
    layers become Thread/Node/Weave dicts.
  - Storage: SQLite at /var/lib/murphy-production/dlfr_packages.db, with the
    raw container (JSON, optionally gzipped) preserved verbatim for audit.

KEY CONCEPTS:
  - Thread:  raw info unit (an event, a message, a measurement)
  - Node:    semantic anchor (a concept, capability, deal, incident)
  - Weave:   typed edge between Nodes (SUPPORTS, CONTRADICTS, DEPENDS_ON,
             FALLBACK_SUCCEEDS, ROUTED_TO, ESCALATED_TO)
  - Rosetta-Block: the cognitive context that produced the above
                   (which agents, which stance, which world_context,
                    which HARM_THRESHOLDS were live)
  - Provenance:    creator agent, source system, ts, checksums, lineage

PUBLIC API:
  pack(threads, nodes, weaves, rosetta_state, metadata=None) -> bytes
  unpack(blob: bytes) -> dict
  validate(blob: bytes) -> (bool, list[str])  # checksum + schema + relationship integrity
  store(blob: bytes, label: str = "") -> str  # returns package_id
  load(package_id: str) -> dict

DEPENDENCIES:
  - src.rosetta_core.RosettaSoul (constitutional layer snapshot)
  - stdlib only otherwise (hashlib, json, gzip, sqlite3, uuid)

EVENT SPINE EMISSIONS:
  - dlfr.package.created  (when pack() runs)
  - dlfr.package.loaded   (when load() runs)

KNOWN LIMITS:
  - v0.1: no encryption (encryption stub present, returns plaintext)
  - v0.1: no streaming serialization (full in-memory pack)
  - v0.1: no schema migration between format versions

LAST UPDATED: 2026-05-27 by Murphy build session
"""
from __future__ import annotations

import gzip
import hashlib
import json
import logging
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("murphy.dlfr")

FORMAT_VERSION = "0.1"
DB_PATH = Path("/var/lib/murphy-production/dlfr_packages.db")

# ── Allowed Weave types ────────────────────────────────────────────────────
WEAVE_TYPES = {
    "SUPPORTS",          # A supports/reinforces B
    "CONTRADICTS",       # A contradicts B
    "DEPENDS_ON",        # A requires B
    "SEQUENCE",          # A then B
    "ASSOCIATION",       # A relates to B (untyped)
    "REFERENCE",         # A cites B
    "FALLBACK_SUCCEEDS", # When A fails, B works (CAF-derived)
    "ROUTED_TO",         # signal/incident A was routed to handler B
    "ESCALATED_TO",      # A was escalated to B (e.g., HITL)
    # R615 — multi-edge org graph edge types
    "DEPARTMENT_MEMBER_OF",     # node belongs to a department (constraint gate)
    "FUNCTIONAL_DELIVERABLE_OF",# node produces output toward a task spec
    "SPAWNED_BY",               # lineage edge: child node was spawned by parent
    "INHERITS_CAPABILITY",      # node reuses a forged capability from another node
}

# R615.0 — Node 'kind' convention (optional field).
# Nodes without a kind remain valid (backward compat). When set, must be one of:
NODE_KINDS = {
    "capability",   # a forged or registered capability (module, agent, tool)
    "department",   # an emergent or seeded department (Engineering, Finance, ...)
    "function",     # a deliverable-producing task node
    "exec",         # an executive position (CEO/CTO/CFO/CSO)
    "task",         # a generic task node (default for legacy)
    "concept",      # a semantic anchor (legacy DLF-R default usage)
}



# ── Schema ─────────────────────────────────────────────────────────────────
_SCHEMA = """
CREATE TABLE IF NOT EXISTS dlfr_packages (
    package_id     TEXT PRIMARY KEY,
    label          TEXT,
    format_version TEXT,
    checksum       TEXT,
    size_bytes     INTEGER,
    n_threads      INTEGER,
    n_nodes        INTEGER,
    n_weaves       INTEGER,
    has_rosetta    INTEGER DEFAULT 0,
    created_at     TEXT,
    raw_blob       BLOB
);
CREATE INDEX IF NOT EXISTS idx_dlfr_created ON dlfr_packages(created_at);
CREATE INDEX IF NOT EXISTS idx_dlfr_label ON dlfr_packages(label);
"""


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(DB_PATH), timeout=5)
    c.executescript(_SCHEMA)
    return c


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _checksum(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


# ── Validation ─────────────────────────────────────────────────────────────
def _validate_thread(t: Dict[str, Any], errors: List[str]) -> None:
    if "id" not in t:
        errors.append(f"thread missing id: {t}")
    if "payload" not in t:
        errors.append(f"thread {t.get('id','?')} missing payload")


def _validate_node(n: Dict[str, Any], errors: List[str]) -> None:
    if "id" not in n:
        errors.append(f"node missing id: {n}")
    if "label" not in n:
        errors.append(f"node {n.get('id','?')} missing label")
    # R615.0 — optional kind field; if present must be valid
    kind = n.get("kind")
    if kind is not None and kind not in NODE_KINDS:
        errors.append(f"node {n.get('id','?')} has invalid kind: {kind} (allowed: {sorted(NODE_KINDS)})")


def _validate_weave(w: Dict[str, Any], node_ids: set, errors: List[str]) -> None:
    if w.get("type") not in WEAVE_TYPES:
        errors.append(f"weave {w.get('id','?')} has invalid type: {w.get('type')}")
    if w.get("source") not in node_ids:
        errors.append(f"weave {w.get('id','?')} source node not found: {w.get('source')}")
    if w.get("target") not in node_ids:
        errors.append(f"weave {w.get('id','?')} target node not found: {w.get('target')}")


# ── Rosetta snapshot ───────────────────────────────────────────────────────
def _snapshot_rosetta() -> Dict[str, Any]:
    """Capture the live constitutional layer + current world_context.
    Returns a dict that's safe to JSON-serialize."""
    snap: Dict[str, Any] = {"captured_at": _now_iso()}
    try:
        from src.rosetta_core import RosettaSoul
        snap["north_star"] = RosettaSoul.NORTH_STAR
        snap["harm_thresholds"] = dict(RosettaSoul.HARM_THRESHOLDS)
        snap["team_covenant"] = list(RosettaSoul.TEAM_COVENANT)
        snap["characters"] = {
            cid: {
                "name": c.name, "position": c.position, "emoji": c.emoji,
                "tone": c.tone, "bias": c.bias,
                "hitl_threshold": c.hitl_threshold,
            }
            for cid, c in RosettaSoul.CHARACTERS.items()
        }
    except Exception as exc:
        log.warning("rosetta snapshot incomplete: %s", exc)
        snap["error"] = str(exc)[:200]

    # World context — best-effort, never block packing
    try:
        from src.world_context_provider import get_current_world_context
        snap["world_context"] = get_current_world_context()
    except Exception:
        snap["world_context"] = None

    return snap


# ── Public API ─────────────────────────────────────────────────────────────
def pack(
    threads: List[Dict[str, Any]],
    nodes: List[Dict[str, Any]],
    weaves: List[Dict[str, Any]],
    rosetta_state: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    creator: str = "unknown",
    compress: bool = True,
) -> bytes:
    """Serialize a DLF-R package to bytes.

    Args:
        threads: list of {id, payload, created_at_utc, metadata, symbol_signature}
        nodes: list of {id, label, thread_refs, metadata}
        weaves: list of {id, source, target, type, confidence, provenance}
        rosetta_state: dict from _snapshot_rosetta() or pre-captured snapshot.
                       Pass None to auto-capture live Rosetta state.
        metadata: optional package-level metadata
        creator: identifier of the producing system/agent
        compress: gzip the JSON body (default True)

    Returns:
        bytes — the serialized package. Pass to store() or transmit directly.
    """
    if rosetta_state is None:
        rosetta_state = _snapshot_rosetta()

    # Stable-sort weaves by source for deterministic output
    weaves_sorted = sorted(weaves, key=lambda w: (w.get("source",""), w.get("target","")))

    body = {
        "format": "DLF-R",
        "format_version": FORMAT_VERSION,
        "package_id": uuid.uuid4().hex[:16],
        "created_at_utc": _now_iso(),
        "creator": creator,
        "metadata": metadata or {},
        "rosetta_block": rosetta_state,
        "semantic_layers": {
            "threads": threads,
            "nodes": nodes,
            "weaves": weaves_sorted,
        },
        "fabric": {
            "n_threads": len(threads),
            "n_nodes": len(nodes),
            "n_weaves": len(weaves_sorted),
            "weave_type_histogram": _histogram([w.get("type") for w in weaves_sorted]),
            "has_rosetta": bool(rosetta_state),
        },
    }

    raw_json = json.dumps(body, sort_keys=True, default=str).encode("utf-8")
    checksum = _checksum(raw_json)

    envelope = {
        "magic": "DLFR",
        "version": FORMAT_VERSION,
        "compressed": compress,
        "checksum_sha256": checksum,
        "body": raw_json.decode("utf-8") if not compress else None,
    }
    if compress:
        envelope["body_gz_b64"] = _b64(gzip.compress(raw_json))

    blob = json.dumps(envelope, sort_keys=True).encode("utf-8")
    log.info("DLF-R packed: %d threads, %d nodes, %d weaves, %d bytes (compress=%s)",
             len(threads), len(nodes), len(weaves_sorted), len(blob), compress)
    return blob


def unpack(blob: bytes) -> Dict[str, Any]:
    """Reverse pack(). Returns the full body dict including rosetta_block + semantic_layers."""
    envelope = json.loads(blob.decode("utf-8"))
    if envelope.get("magic") != "DLFR":
        raise ValueError("not a DLF-R blob (magic mismatch)")
    if envelope.get("compressed"):
        raw_json = gzip.decompress(_unb64(envelope["body_gz_b64"]))
    else:
        raw_json = envelope["body"].encode("utf-8")
    body = json.loads(raw_json)
    # Verify checksum
    expected = envelope.get("checksum_sha256")
    actual = _checksum(raw_json)
    if expected != actual:
        raise ValueError(f"checksum mismatch: expected {expected}, got {actual}")
    return body


def validate(blob: bytes) -> Tuple[bool, List[str]]:
    """Strict validation per DLF-Lite section 9.5 + our weave type rules."""
    errors: List[str] = []
    try:
        body = unpack(blob)
    except Exception as exc:
        return False, [f"unpack failed: {exc}"]

    layers = body.get("semantic_layers", {})
    threads = layers.get("threads", [])
    nodes = layers.get("nodes", [])
    weaves = layers.get("weaves", [])

    for t in threads: _validate_thread(t, errors)
    for n in nodes: _validate_node(n, errors)
    node_ids = {n.get("id") for n in nodes}
    for w in weaves: _validate_weave(w, node_ids, errors)

    return (len(errors) == 0), errors


def store(blob: bytes, label: str = "") -> str:
    """Persist a package to dlfr_packages.db. Returns package_id."""
    body = unpack(blob)
    pkg_id = body["package_id"]
    fabric = body.get("fabric", {})
    with _conn() as c:
        c.execute(
            """INSERT OR REPLACE INTO dlfr_packages
               (package_id, label, format_version, checksum, size_bytes,
                n_threads, n_nodes, n_weaves, has_rosetta, created_at, raw_blob)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (pkg_id, label, body.get("format_version"),
             _checksum(blob), len(blob),
             fabric.get("n_threads",0), fabric.get("n_nodes",0),
             fabric.get("n_weaves",0), 1 if fabric.get("has_rosetta") else 0,
             body.get("created_at_utc"), blob),
        )
    log.info("DLF-R stored: %s (%d bytes, label=%s)", pkg_id, len(blob), label)
    return pkg_id


def load(package_id: str) -> Optional[Dict[str, Any]]:
    """Load a stored package by id. Returns the full body dict or None."""
    with _conn() as c:
        row = c.execute(
            "SELECT raw_blob FROM dlfr_packages WHERE package_id=?",
            (package_id,)
        ).fetchone()
    if not row:
        return None
    return unpack(row[0])


def list_packages(limit: int = 50) -> List[Dict[str, Any]]:
    """List recent packages (metadata only, not raw blobs)."""
    with _conn() as c:
        rows = c.execute(
            """SELECT package_id, label, format_version, size_bytes,
                      n_threads, n_nodes, n_weaves, has_rosetta, created_at
               FROM dlfr_packages
               ORDER BY created_at DESC
               LIMIT ?""", (limit,)
        ).fetchall()
    cols = ["package_id","label","format_version","size_bytes",
            "n_threads","n_nodes","n_weaves","has_rosetta","created_at"]
    return [dict(zip(cols, r)) for r in rows]


# ── Tiny utils ─────────────────────────────────────────────────────────────
def _histogram(items: List[Optional[str]]) -> Dict[str, int]:
    h: Dict[str,int] = {}
    for x in items:
        if x is None: continue
        h[x] = h.get(x, 0) + 1
    return h

def _b64(data: bytes) -> str:
    import base64; return base64.b64encode(data).decode("ascii")

def _unb64(data: str) -> bytes:
    import base64; return base64.b64decode(data.encode("ascii"))


# ── R615.0 — Query helpers ──────────────────────────────────────────────────

def find_nodes_by_kind(package_blob_or_body, kind: str) -> List[Dict[str, Any]]:
    """Return all nodes in a package matching the given kind.

    Accepts either raw bytes (DLF-R container) or an already-unpacked dict.
    Returns [] if kind is not in NODE_KINDS or no nodes match.
    """
    if kind not in NODE_KINDS:
        return []
    if isinstance(package_blob_or_body, (bytes, bytearray)):
        body = unpack(bytes(package_blob_or_body))
    else:
        body = package_blob_or_body
    layers = body.get("semantic_layers") or body.get("layers") or {}
    nodes = layers.get("nodes") or body.get("nodes") or []
    return [n for n in nodes if n.get("kind") == kind]


def find_weaves_by_type(package_blob_or_body, weave_type: str) -> List[Dict[str, Any]]:
    """Return all weaves in a package matching the given type.

    Accepts either raw bytes (DLF-R container) or an already-unpacked dict.
    """
    if weave_type not in WEAVE_TYPES:
        return []
    if isinstance(package_blob_or_body, (bytes, bytearray)):
        body = unpack(bytes(package_blob_or_body))
    else:
        body = package_blob_or_body
    layers = body.get("semantic_layers") or body.get("layers") or {}
    weaves = layers.get("weaves") or body.get("weaves") or []
    return [w for w in weaves if w.get("type") == weave_type]

