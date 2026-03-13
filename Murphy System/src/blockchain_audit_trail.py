# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Blockchain Audit Trail — BAT-001

Owner: Platform Engineering · Dep: thread_safe_operations (capped_append)

File-based blockchain-inspired audit trail for compliance-critical operations.
Each block stores a hash of the previous block, creating a tamper-evident,
immutable append-only log.  Blocks contain typed audit entries (API calls,
admin actions, config changes) with nanosecond timestamps.

Classes: EntryType/BlockStatus/ChainIntegrity (enums),
AuditEntry/Block/ChainVerification/ChainStats (dataclasses),
BlockchainAuditTrail (thread-safe engine).
``create_bat_api(engine)`` returns a Flask Blueprint (JSON error envelope).

Safety: all mutable state under threading.Lock; bounded lists via capped_append;
no external dependencies beyond stdlib + Flask.
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union

try:
    from flask import Blueprint, jsonify, request

    _HAS_FLASK = True
except ImportError:
    _HAS_FLASK = False
    Blueprint = type("Blueprint", (), {"route": lambda *a, **k: lambda f: f})  # type: ignore[assignment,misc]

    def jsonify(*_a: Any, **_k: Any) -> dict:  # type: ignore[misc]
        return {}

    class _FakeReq:  # type: ignore[no-redef]
        args: dict = {}

        @staticmethod
        def get_json(silent: bool = True) -> dict:
            return {}

    request = _FakeReq()  # type: ignore[assignment]

try:
    from .blueprint_auth import require_blueprint_auth
except ImportError:
    from blueprint_auth import require_blueprint_auth
try:
    from thread_safe_operations import capped_append, capped_append_paired
except ImportError:

    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max(1, max_size // 10)]
        target_list.append(item)

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _enum_val(v: Any) -> str:
    """Return the string value whether *v* is an Enum or already a str."""
    return v.value if hasattr(v, "value") else str(v)


# -- Enums ------------------------------------------------------------------

class EntryType(str, Enum):
    """EntryType enumeration."""
    api_call = "api_call"
    admin_action = "admin_action"
    config_change = "config_change"
    security_event = "security_event"
    data_access = "data_access"
    system_event = "system_event"


class BlockStatus(str, Enum):
    """BlockStatus enumeration."""
    sealed = "sealed"
    pending = "pending"


class ChainIntegrity(str, Enum):
    """ChainIntegrity enumeration."""
    valid = "valid"
    broken = "broken"
    empty = "empty"


# -- Dataclasses ------------------------------------------------------------

@dataclass
class AuditEntry:
    """A single auditable event within a block."""
    entry_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    entry_type: EntryType = EntryType.system_event
    actor: str = ""
    action: str = ""
    resource: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=_now)
    ip_address: str = ""
    outcome: str = "success"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to plain dict."""
        d = asdict(self)
        d["entry_type"] = _enum_val(self.entry_type)
        return d


@dataclass
class Block:
    """A sealed block in the audit chain."""
    block_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    index: int = 0
    previous_hash: str = "0" * 64
    entries: List[AuditEntry] = field(default_factory=list)
    timestamp: str = field(default_factory=_now)
    nonce: int = 0
    block_hash: str = ""
    status: BlockStatus = BlockStatus.pending

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to plain dict."""
        d = asdict(self)
        d["status"] = _enum_val(self.status)
        d["entries"] = [e.to_dict() for e in self.entries]
        return d


@dataclass
class ChainVerification:
    """Result of a full chain integrity verification."""
    integrity: ChainIntegrity = ChainIntegrity.empty
    total_blocks: int = 0
    verified_blocks: int = 0
    broken_at_index: int = -1
    message: str = ""
    verified_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to plain dict."""
        d = asdict(self)
        d["integrity"] = _enum_val(self.integrity)
        return d


@dataclass
class ChainStats:
    """Aggregate statistics about the audit chain."""
    total_blocks: int = 0
    total_entries: int = 0
    pending_entries: int = 0
    integrity: str = "unknown"
    entry_type_counts: Dict[str, int] = field(default_factory=dict)
    oldest_block: str = ""
    newest_block: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to plain dict."""
        return asdict(self)


# -- Hashing ----------------------------------------------------------------

def _compute_hash(index: int, previous_hash: str, timestamp: str,
                  entries_data: str, nonce: int) -> str:
    """Compute SHA-256 hash for a block."""
    payload = f"{index}{previous_hash}{timestamp}{entries_data}{nonce}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _entries_fingerprint(entries: List[AuditEntry]) -> str:
    """Deterministic JSON fingerprint of the entries list."""
    data = [e.to_dict() for e in entries]
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


# -- BlockchainAuditTrail --------------------------------------------------

class BlockchainAuditTrail:
    """Thread-safe blockchain-inspired audit trail with bounded storage."""

    def __init__(self, max_blocks: int = 50_000,
                 entries_per_block: int = 100) -> None:
        self._lock = threading.Lock()
        self._chain: List[Block] = []
        self._pending: List[AuditEntry] = []
        self._block_index: Dict[str, Block] = {}
        self._max_blocks = max_blocks
        self._entries_per_block = entries_per_block
        self._block_order: List[str] = []

    # -- Entry recording ----------------------------------------------------

    def record_entry(self, entry_type: Union[str, EntryType],
                     actor: str, action: str, resource: str = "",
                     details: Optional[Dict[str, Any]] = None,
                     ip_address: str = "",
                     outcome: str = "success") -> AuditEntry:
        """Append an audit entry to the pending buffer."""
        et = EntryType(entry_type) if not isinstance(entry_type, EntryType) else entry_type
        entry = AuditEntry(
            entry_type=et, actor=actor, action=action,
            resource=resource, details=details or {},
            ip_address=ip_address, outcome=outcome,
        )
        with self._lock:
            capped_append(self._pending, entry, self._entries_per_block * 10)
            if len(self._pending) >= self._entries_per_block:
                self._seal_block()
        return entry

    # -- Block sealing ------------------------------------------------------

    def seal_current_block(self) -> Optional[Block]:
        """Force-seal whatever entries are pending into a new block."""
        with self._lock:
            if not self._pending:
                return None
            return self._seal_block()

    def _seal_block(self) -> Block:
        """Internal: seal pending entries into a new block (lock held)."""
        prev_hash = self._chain[-1].block_hash if self._chain else "0" * 64
        idx = len(self._chain)
        entries = list(self._pending)
        self._pending.clear()
        ts = _now()
        fp = _entries_fingerprint(entries)
        h = _compute_hash(idx, prev_hash, ts, fp, 0)
        blk = Block(
            index=idx, previous_hash=prev_hash, entries=entries,
            timestamp=ts, block_hash=h, status=BlockStatus.sealed,
        )
        capped_append_paired(self._chain, blk, self._block_order, blk.block_id, max_size=self._max_blocks)
        self._block_index[blk.block_id] = blk
        self._enforce_capacity()
        return blk

    def _enforce_capacity(self) -> None:
        """Evict oldest blocks when capacity is exceeded (lock held)."""
        while len(self._chain) > self._max_blocks:
            old = self._chain.pop(0)
            self._block_index.pop(old.block_id, None)
            if self._block_order and self._block_order[0] == old.block_id:
                self._block_order.pop(0)

    # -- Querying -----------------------------------------------------------

    def get_block(self, block_id: str) -> Optional[Block]:
        """Return a block by its ID."""
        with self._lock:
            return self._block_index.get(block_id)

    def get_block_by_index(self, index: int) -> Optional[Block]:
        """Return a block by its chain index."""
        with self._lock:
            if 0 <= index < len(self._chain):
                return self._chain[index]
            return None

    def list_blocks(self, limit: int = 50,
                    offset: int = 0) -> List[Block]:
        """Return a paginated list of blocks (newest first)."""
        with self._lock:
            rev = list(reversed(self._chain))
            return rev[offset: offset + limit]

    def search_entries(self, entry_type: Optional[str] = None,
                       actor: Optional[str] = None,
                       resource: Optional[str] = None,
                       action: Optional[str] = None,
                       limit: int = 100) -> List[AuditEntry]:
        """Search across all blocks for matching entries."""
        with self._lock:
            return self._do_search(entry_type, actor, resource,
                                   action, limit)

    def _do_search(self, entry_type: Optional[str], actor: Optional[str],
                   resource: Optional[str], action: Optional[str],
                   limit: int) -> List[AuditEntry]:
        results: List[AuditEntry] = []
        for blk in reversed(self._chain):
            for e in reversed(blk.entries):
                if entry_type and _enum_val(e.entry_type) != entry_type:
                    continue
                if actor and e.actor != actor:
                    continue
                if resource and e.resource != resource:
                    continue
                if action and e.action != action:
                    continue
                results.append(e)
                if len(results) >= limit:
                    return results
        return results

    # -- Verification -------------------------------------------------------

    def verify_chain(self) -> ChainVerification:
        """Verify the full chain integrity by recalculating hashes."""
        with self._lock:
            return self._do_verify()

    def _do_verify(self) -> ChainVerification:
        if not self._chain:
            return ChainVerification(
                integrity=ChainIntegrity.empty, message="Chain is empty")
        for i, blk in enumerate(self._chain):
            expected_prev = (
                self._chain[i - 1].block_hash if i > 0 else "0" * 64
            )
            if blk.previous_hash != expected_prev:
                return ChainVerification(
                    integrity=ChainIntegrity.broken,
                    total_blocks=len(self._chain),
                    verified_blocks=i,
                    broken_at_index=i,
                    message=f"Previous-hash mismatch at block {i}",
                )
            fp = _entries_fingerprint(blk.entries)
            recalc = _compute_hash(
                blk.index, blk.previous_hash, blk.timestamp, fp, blk.nonce,
            )
            if blk.block_hash != recalc:
                return ChainVerification(
                    integrity=ChainIntegrity.broken,
                    total_blocks=len(self._chain),
                    verified_blocks=i,
                    broken_at_index=i,
                    message=f"Hash mismatch at block {i}",
                )
        return ChainVerification(
            integrity=ChainIntegrity.valid,
            total_blocks=len(self._chain),
            verified_blocks=len(self._chain),
            message="All blocks verified",
        )

    # -- Statistics ---------------------------------------------------------

    def get_stats(self) -> ChainStats:
        """Return aggregate chain statistics."""
        with self._lock:
            return self._build_stats()

    def _build_stats(self) -> ChainStats:
        total_entries = sum(len(b.entries) for b in self._chain)
        counts: Dict[str, int] = {}
        for blk in self._chain:
            for e in blk.entries:
                k = _enum_val(e.entry_type)
                counts[k] = counts.get(k, 0) + 1
        oldest = self._chain[0].timestamp if self._chain else ""
        newest = self._chain[-1].timestamp if self._chain else ""
        v = self._do_verify()
        return ChainStats(
            total_blocks=len(self._chain),
            total_entries=total_entries,
            pending_entries=len(self._pending),
            integrity=_enum_val(v.integrity),
            entry_type_counts=counts,
            oldest_block=oldest,
            newest_block=newest,
        )

    # -- Pending info -------------------------------------------------------

    def pending_count(self) -> int:
        """Return the number of entries awaiting sealing."""
        with self._lock:
            return len(self._pending)

    def chain_length(self) -> int:
        """Return the number of sealed blocks."""
        with self._lock:
            return len(self._chain)

    # -- Export -------------------------------------------------------------

    def export_chain(self) -> List[Dict[str, Any]]:
        """Export the entire chain as a list of dicts."""
        with self._lock:
            return [b.to_dict() for b in self._chain]


# -- Wingman pair validation ------------------------------------------------

def validate_wingman_pair(storyline: List[str], actuals: List[str]) -> dict:
    """BAT-001 Wingman gate.

    Validate that storyline and actuals lists are non-empty, equal-length,
    and each pair matches.  Returns a pass/fail dict with diagnostics.
    """
    if not storyline:
        return {"passed": False, "message": "Storyline list is empty"}
    if not actuals:
        return {"passed": False, "message": "Actuals list is empty"}
    if len(storyline) != len(actuals):
        return {"passed": False,
                "message": f"Length mismatch: storyline={len(storyline)} "
                           f"actuals={len(actuals)}"}
    mismatches: List[int] = []
    for i, (s, a) in enumerate(zip(storyline, actuals)):
        if s != a:
            mismatches.append(i)
    if mismatches:
        return {"passed": False,
                "message": f"Pair mismatches at indices {mismatches}"}
    return {"passed": True, "message": "Wingman pair validated",
            "pair_count": len(storyline)}


# -- Causality Sandbox gating -----------------------------------------------

def gate_bat_in_sandbox(context: dict) -> dict:
    """BAT-001 Causality Sandbox gate.

    Verify that the provided context contains the required keys for a
    BAT action and that the values are acceptable within the sandbox.
    """
    required_keys = {"actor", "action", "entry_type"}
    missing = required_keys - set(context.keys())
    if missing:
        return {"passed": False,
                "message": f"Missing context keys: {sorted(missing)}"}
    if not context.get("actor"):
        return {"passed": False, "message": "actor must be non-empty"}
    if not context.get("action"):
        return {"passed": False, "message": "action must be non-empty"}
    allowed_types = {t.value for t in EntryType}
    if context["entry_type"] not in allowed_types:
        return {"passed": False,
                "message": f"entry_type '{context['entry_type']}' not in "
                           f"{sorted(allowed_types)}"}
    return {"passed": True, "message": "Sandbox gate passed",
            "actor": context["actor"]}


# -- Flask helpers ----------------------------------------------------------

def _api_body() -> Dict[str, Any]:
    """Extract JSON body from the current request."""
    return request.get_json(silent=True) or {}


def _api_need(body: Dict[str, Any], *keys: str) -> Optional[Any]:
    """Return an error tuple if any *keys* are missing from *body*."""
    for k in keys:
        if not body.get(k):
            return jsonify({"error": f"{k} required", "code": "BAT_MISSING"}), 400
    return None


def _not_found(msg: str = "Not found") -> Any:
    return jsonify({"error": msg, "code": "BAT_404"}), 404


# -- Flask Blueprint factory ------------------------------------------------

def create_bat_api(engine: BlockchainAuditTrail) -> Any:
    """Create a Flask Blueprint exposing blockchain audit trail endpoints.

    All routes live under ``/api/bat/`` and return JSON with an error
    envelope ``{"error": "…", "code": "BAT_*"}`` on failure.
    """
    if not _HAS_FLASK:
        return Blueprint("bat_api", __name__)  # type: ignore[call-arg]
    bp = Blueprint("bat_api", __name__, url_prefix="/api")
    _register_health_routes(bp, engine)
    _register_entry_routes(bp, engine)
    _register_block_routes(bp, engine)
    _register_verify_routes(bp, engine)
    _register_search_routes(bp, engine)
    _register_stats_routes(bp, engine)
    require_blueprint_auth(bp)
    return bp


def _register_health_routes(bp: Any, eng: BlockchainAuditTrail) -> None:
    """Register health-check endpoint."""

    @bp.route("/bat/health", methods=["GET"])
    def health() -> Any:
        return jsonify({"status": "healthy", "module": "BAT-001"})


def _register_entry_routes(bp: Any, eng: BlockchainAuditTrail) -> None:
    """Register audit entry endpoints."""

    @bp.route("/bat/entries", methods=["POST"])
    def record_entry() -> Any:
        b = _api_body()
        err = _api_need(b, "entry_type", "actor", "action")
        if err:
            return err
        try:
            et = EntryType(b["entry_type"])
        except ValueError:
            return jsonify({"error": "Invalid entry_type",
                            "code": "BAT_INVALID"}), 400
        entry = eng.record_entry(
            entry_type=et, actor=b["actor"], action=b["action"],
            resource=b.get("resource", ""),
            details=b.get("details", {}),
            ip_address=b.get("ip_address", ""),
            outcome=b.get("outcome", "success"),
        )
        return jsonify(entry.to_dict()), 201

    @bp.route("/bat/entries/search", methods=["GET"])
    def search_entries() -> Any:
        a = request.args
        results = eng.search_entries(
            entry_type=a.get("entry_type"),
            actor=a.get("actor"),
            resource=a.get("resource"),
            action=a.get("action"),
            limit=int(a.get("limit", "100")),
        )
        return jsonify([e.to_dict() for e in results])


def _register_block_routes(bp: Any, eng: BlockchainAuditTrail) -> None:
    """Register block query endpoints."""

    @bp.route("/bat/blocks", methods=["GET"])
    def list_blocks() -> Any:
        a = request.args
        blocks = eng.list_blocks(
            limit=int(a.get("limit", "50")),
            offset=int(a.get("offset", "0")),
        )
        return jsonify([bl.to_dict() for bl in blocks])

    @bp.route("/bat/blocks/<block_id>", methods=["GET"])
    def get_block(block_id: str) -> Any:
        bl = eng.get_block(block_id)
        if not bl:
            return _not_found("Block not found")
        return jsonify(bl.to_dict())

    @bp.route("/bat/blocks/seal", methods=["POST"])
    def seal_block() -> Any:
        bl = eng.seal_current_block()
        if not bl:
            return jsonify({"error": "No pending entries",
                            "code": "BAT_EMPTY"}), 400
        return jsonify(bl.to_dict()), 201

    @bp.route("/bat/blocks/index/<int:idx>", methods=["GET"])
    def get_block_by_index(idx: int) -> Any:
        bl = eng.get_block_by_index(idx)
        if not bl:
            return _not_found("Block not found at index")
        return jsonify(bl.to_dict())


def _register_verify_routes(bp: Any, eng: BlockchainAuditTrail) -> None:
    """Register chain verification endpoints."""

    @bp.route("/bat/verify", methods=["GET"])
    def verify_chain() -> Any:
        result = eng.verify_chain()
        return jsonify(result.to_dict())


def _register_search_routes(bp: Any, eng: BlockchainAuditTrail) -> None:
    """Register export endpoint."""

    @bp.route("/bat/export", methods=["GET"])
    def export_chain() -> Any:
        data = eng.export_chain()
        return jsonify(data)


def _register_stats_routes(bp: Any, eng: BlockchainAuditTrail) -> None:
    """Register statistics endpoint."""

    @bp.route("/bat/stats", methods=["GET"])
    def stats() -> Any:
        return jsonify(eng.get_stats().to_dict())
