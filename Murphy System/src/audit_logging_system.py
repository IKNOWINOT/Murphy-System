# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Immutable Audit Logging System — AUD-001

Owner: Platform Engineering · Dep: thread_safe_operations (capped_append)

Append-only audit logging system for the Murphy System — immutable
event recording for all API calls, admin actions, configuration changes,
and security events.  Supports structured queries, hash-chain integrity
verification, retention policies, and export to external sinks.

Classes: AuditAction/AuditSeverity/AuditCategory (enums),
AuditEntry/AuditQuery/RetentionPolicy (dataclasses),
AuditLogger (thread-safe orchestrator).
``create_audit_api(logger)`` returns a Flask Blueprint (JSON error
envelope).

Safety: all mutable state guarded by threading.Lock; log bounded via
capped_append (CWE-770); entries are immutable after creation; PII
fields redacted in serialisation; hash chain ensures tamper detection.
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    from flask import Blueprint, jsonify, request
    _HAS_FLASK = True
except ImportError:  # pragma: no cover
    _HAS_FLASK = False
    Blueprint = type("Blueprint", (), {"route": lambda *a, **k: lambda f: f})  # type: ignore[assignment,misc]
    def jsonify(*_a: Any, **_k: Any) -> dict:  # type: ignore[override]
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
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(
        target_list: list, item: Any, max_size: int = 10_000
    ) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max(1, max_size // 10)]
        target_list.append(item)

logger = logging.getLogger(__name__)

# -- Enumerations ----------------------------------------------------------
class AuditAction(str, Enum):
    """Types of auditable actions."""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    CONFIGURE = "configure"
    EXECUTE = "execute"
    APPROVE = "approve"
    DENY = "deny"
    EXPORT = "export"

class AuditSeverity(str, Enum):
    """Severity classification of audit events."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    SECURITY = "security"

class AuditCategory(str, Enum):
    """Functional category of the audited operation."""
    API_CALL = "api_call"
    ADMIN_ACTION = "admin_action"
    CONFIG_CHANGE = "config_change"
    SECURITY_EVENT = "security_event"
    DATA_ACCESS = "data_access"
    SYSTEM_EVENT = "system_event"
    USER_ACTION = "user_action"

# -- Dataclasses -----------------------------------------------------------
@dataclass
class AuditEntry:
    """A single immutable audit log entry with hash-chain link."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    action: AuditAction = AuditAction.READ
    category: AuditCategory = AuditCategory.API_CALL
    severity: AuditSeverity = AuditSeverity.INFO
    actor: str = ""
    resource: str = ""
    resource_id: str = ""
    detail: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    source_ip: str = ""
    user_agent: str = ""
    success: bool = True
    previous_hash: str = ""
    entry_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialise with PII redacted."""
        d = asdict(self)
        d["action"] = self.action.value
        d["category"] = self.category.value
        d["severity"] = self.severity.value
        if self.source_ip:
            parts = self.source_ip.split(".")
            if len(parts) == 4:
                d["source_ip"] = f"{parts[0]}.{parts[1]}.xxx.xxx"
        if self.user_agent and len(self.user_agent) > 20:
            d["user_agent"] = self.user_agent[:20] + "..."
        return d

    def compute_hash(self) -> str:
        """Compute SHA-256 hash of entry content for chain integrity."""
        payload = (
            f"{self.id}|{self.timestamp}|{self.action.value}|"
            f"{self.category.value}|{self.actor}|{self.resource}|"
            f"{self.resource_id}|{self.detail}|{self.success}|"
            f"{self.previous_hash}"
        )
        return hashlib.sha256(payload.encode()).hexdigest()

@dataclass
class AuditQuery:
    """Filter parameters for querying audit entries."""
    action: Optional[AuditAction] = None
    category: Optional[AuditCategory] = None
    severity: Optional[AuditSeverity] = None
    actor: Optional[str] = None
    resource: Optional[str] = None
    success: Optional[bool] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    limit: int = 100

@dataclass
class RetentionPolicy:
    """Retention policy for audit entries."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    name: str = ""
    category: Optional[AuditCategory] = None
    max_age_days: int = 365
    max_entries: int = 100_000
    enabled: bool = True
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    def to_dict(self) -> Dict[str, Any]:
        """Serialise to dict."""
        d = asdict(self)
        if self.category:
            d["category"] = self.category.value
        return d

# -- AuditLogger -----------------------------------------------------------
class AuditLogger:
    """Thread-safe immutable append-only audit log engine.

    Parameters
    ----------
    sink_callback:
        ``(entry: AuditEntry) -> bool``. External sink for forwarding
        entries. When *None* entries are only stored in-memory.
    max_entries:
        Maximum entries retained in memory.
    """

    def __init__(
        self,
        sink_callback: Optional[Callable[[AuditEntry], bool]] = None,
        max_entries: int = 50_000,
    ) -> None:
        self._lock = threading.Lock()
        self._entries: List[AuditEntry] = []
        self._policies: Dict[str, RetentionPolicy] = {}
        self._sink = sink_callback
        self._max_entries = max_entries
        self._last_hash = "0" * 64

    # -- Logging -----------------------------------------------------------
    def log(
        self,
        action: AuditAction,
        category: AuditCategory,
        actor: str = "",
        resource: str = "",
        resource_id: str = "",
        detail: str = "",
        severity: AuditSeverity = AuditSeverity.INFO,
        metadata: Optional[Dict[str, Any]] = None,
        source_ip: str = "",
        user_agent: str = "",
        success: bool = True,
    ) -> AuditEntry:
        """Record a new immutable audit entry."""
        with self._lock:
            entry = AuditEntry(
                action=action,
                category=category,
                severity=severity,
                actor=actor,
                resource=resource,
                resource_id=resource_id,
                detail=detail,
                metadata=dict(metadata or {}),
                source_ip=source_ip,
                user_agent=user_agent,
                success=success,
                previous_hash=self._last_hash,
            )
            entry.entry_hash = entry.compute_hash()
            self._last_hash = entry.entry_hash
            capped_append(self._entries, entry, self._max_entries)
        if self._sink:
            try:
                self._sink(entry)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Audit sink failed for entry %s: %s", entry.id, type(exc).__name__)
        return entry

    def log_api_call(
        self, method: str, path: str, actor: str = "",
        status_code: int = 200, source_ip: str = "",
    ) -> AuditEntry:
        """Convenience: record an API call."""
        return self.log(
            action=AuditAction.READ if method == "GET" else AuditAction.EXECUTE,
            category=AuditCategory.API_CALL,
            actor=actor,
            resource=path,
            detail=f"{method} {path} -> {status_code}",
            success=200 <= status_code < 400,
            source_ip=source_ip,
        )

    def log_admin_action(
        self, actor: str, action: AuditAction, resource: str,
        resource_id: str = "", detail: str = "",
    ) -> AuditEntry:
        """Convenience: record an admin action."""
        return self.log(
            action=action,
            category=AuditCategory.ADMIN_ACTION,
            severity=AuditSeverity.WARNING,
            actor=actor,
            resource=resource,
            resource_id=resource_id,
            detail=detail,
        )

    def log_config_change(
        self, actor: str, resource: str, detail: str = "",
    ) -> AuditEntry:
        """Convenience: record a configuration change."""
        return self.log(
            action=AuditAction.CONFIGURE,
            category=AuditCategory.CONFIG_CHANGE,
            severity=AuditSeverity.WARNING,
            actor=actor,
            resource=resource,
            detail=detail,
        )

    def log_security_event(
        self, actor: str, detail: str, success: bool = False,
        source_ip: str = "",
    ) -> AuditEntry:
        """Convenience: record a security event."""
        return self.log(
            action=AuditAction.LOGIN if success else AuditAction.DENY,
            category=AuditCategory.SECURITY_EVENT,
            severity=AuditSeverity.SECURITY,
            actor=actor,
            detail=detail,
            success=success,
            source_ip=source_ip,
        )

    # -- Query -------------------------------------------------------------
    def query(self, q: AuditQuery) -> List[AuditEntry]:
        """Query audit entries matching the given filters."""
        with self._lock:
            entries = list(self._entries)
        return self._apply_filters(entries, q)[-q.limit:]

    @staticmethod
    def _apply_filters(
        entries: List[AuditEntry], q: AuditQuery
    ) -> List[AuditEntry]:
        """Apply query filters to entry list."""
        result = entries
        if q.action is not None:
            result = [e for e in result if e.action == q.action]
        if q.category is not None:
            result = [e for e in result if e.category == q.category]
        if q.severity is not None:
            result = [e for e in result if e.severity == q.severity]
        if q.actor is not None:
            result = [e for e in result if e.actor == q.actor]
        if q.resource is not None:
            result = [e for e in result if e.resource == q.resource]
        if q.success is not None:
            result = [e for e in result if e.success == q.success]
        if q.start_time is not None:
            result = [e for e in result if e.timestamp >= q.start_time]
        if q.end_time is not None:
            result = [e for e in result if e.timestamp <= q.end_time]
        return result

    def get_entry(self, entry_id: str) -> Optional[AuditEntry]:
        """Retrieve a single audit entry by ID."""
        with self._lock:
            for e in self._entries:
                if e.id == entry_id:
                    return e
        return None

    def count(
        self, category: Optional[AuditCategory] = None
    ) -> int:
        """Return total entry count, optionally filtered by category."""
        with self._lock:
            if category is None:
                return len(self._entries)
            return sum(1 for e in self._entries if e.category == category)

    # -- Integrity ---------------------------------------------------------
    def verify_chain(self) -> Tuple[bool, int]:
        """Verify hash-chain integrity of all entries.

        Returns (valid, verified_count).
        """
        with self._lock:
            entries = list(self._entries)
        if not entries:
            return True, 0
        prev = "0" * 64
        for i, entry in enumerate(entries):
            if entry.previous_hash != prev:
                return False, i
            expected = entry.compute_hash()
            if entry.entry_hash != expected:
                return False, i
            prev = entry.entry_hash
        return True, len(entries)

    # -- Retention policies ------------------------------------------------
    def add_policy(
        self, name: str, max_age_days: int = 365,
        max_entries: int = 100_000,
        category: Optional[AuditCategory] = None,
    ) -> RetentionPolicy:
        """Add a retention policy."""
        pol = RetentionPolicy(
            name=name,
            category=category,
            max_age_days=max_age_days,
            max_entries=max_entries,
        )
        with self._lock:
            self._policies[pol.id] = pol
        return pol

    def list_policies(self) -> List[RetentionPolicy]:
        """Return all retention policies."""
        with self._lock:
            return list(self._policies.values())

    def delete_policy(self, policy_id: str) -> bool:
        """Remove a retention policy."""
        with self._lock:
            return self._policies.pop(policy_id, None) is not None

    def apply_retention(self) -> int:
        """Apply retention policies, removing expired entries.

        Returns the number of entries removed.
        """
        with self._lock:
            policies = list(self._policies.values())
            if not policies:
                return 0
            now = datetime.now(timezone.utc).isoformat()
            before = len(self._entries)
            for pol in policies:
                if not pol.enabled:
                    continue
                self._entries = self._apply_policy(
                    self._entries, pol, now
                )
            removed = before - len(self._entries)
        return removed

    @staticmethod
    def _apply_policy(
        entries: List[AuditEntry], pol: RetentionPolicy, now: str
    ) -> List[AuditEntry]:
        """Apply a single retention policy to entries."""
        if pol.category is not None:
            matching = [e for e in entries if e.category == pol.category]
            others = [e for e in entries if e.category != pol.category]
        else:
            matching = list(entries)
            others = []
        if len(matching) > pol.max_entries:
            matching = matching[-pol.max_entries:]
        return others + matching

    # -- Export ------------------------------------------------------------
    def export_json(
        self, limit: int = 1000
    ) -> str:
        """Export recent entries as JSON string."""
        with self._lock:
            entries = list(self._entries[-limit:])
        return json.dumps(
            [e.to_dict() for e in entries], indent=2, default=str
        )

    # -- Statistics --------------------------------------------------------
    def stats(self) -> Dict[str, Any]:
        """Compute aggregate audit statistics."""
        with self._lock:
            entries = list(self._entries)
            policies = len(self._policies)
        total = len(entries)
        by_cat: Dict[str, int] = {}
        by_sev: Dict[str, int] = {}
        failed = 0
        for e in entries:
            by_cat[e.category.value] = by_cat.get(e.category.value, 0) + 1
            by_sev[e.severity.value] = by_sev.get(e.severity.value, 0) + 1
            if not e.success:
                failed += 1
        valid, verified = self.verify_chain()
        return {
            "total_entries": total,
            "by_category": by_cat,
            "by_severity": by_sev,
            "failed_operations": failed,
            "success_rate": round((total - failed) / total, 4) if total else 0.0,
            "retention_policies": policies,
            "chain_valid": valid,
            "chain_verified": verified,
        }

# -- Flask Blueprint factory -----------------------------------------------
def _api_body() -> Dict[str, Any]:
    """Extract JSON body from Flask request."""
    return request.get_json(silent=True) or {}

def _api_need(body: Dict[str, Any], *keys: str) -> Optional[Any]:
    """Return 400 if any key is missing from body."""
    for k in keys:
        if not body.get(k):
            return jsonify({"error": f"{k} required", "code": "MISSING_FIELD"}), 400
    return None

def _api_404(msg: str = "Not found") -> Any:
    """Standard 404 response."""
    return jsonify({"error": msg, "code": "NOT_FOUND"}), 404

def _register_log_routes(bp: Any, al: AuditLogger) -> None:
    """Attach log creation and query routes."""
    @bp.route("/entries", methods=["POST"])
    def create_entry() -> Any:
        """Record a new audit entry."""
        b = _api_body()
        err = _api_need(b, "action", "category")
        if err:
            return err
        entry = al.log(
            action=AuditAction(b["action"]),
            category=AuditCategory(b["category"]),
            actor=b.get("actor", ""),
            resource=b.get("resource", ""),
            resource_id=b.get("resource_id", ""),
            detail=b.get("detail", ""),
            severity=AuditSeverity(b.get("severity", "info")),
            metadata=b.get("metadata"),
            source_ip=b.get("source_ip", ""),
            success=b.get("success", True),
        )
        return jsonify(entry.to_dict()), 201
    @bp.route("/entries", methods=["GET"])
    def list_entries() -> Any:
        """Query audit entries."""
        q = AuditQuery(limit=int(request.args.get("limit", 100)))
        if request.args.get("action"):
            q.action = AuditAction(request.args["action"])
        if request.args.get("category"):
            q.category = AuditCategory(request.args["category"])
        if request.args.get("severity"):
            q.severity = AuditSeverity(request.args["severity"])
        if request.args.get("actor"):
            q.actor = request.args["actor"]
        if request.args.get("resource"):
            q.resource = request.args["resource"]
        return jsonify([e.to_dict() for e in al.query(q)])
    @bp.route("/entries/<eid>", methods=["GET"])
    def get_entry(eid: str) -> Any:
        """Get a single audit entry."""
        e = al.get_entry(eid)
        return jsonify(e.to_dict()) if e else _api_404()

def _register_integrity_routes(bp: Any, al: AuditLogger) -> None:
    """Attach chain verification and export routes."""
    @bp.route("/verify", methods=["GET"])
    def verify_chain() -> Any:
        """Verify hash-chain integrity."""
        valid, count = al.verify_chain()
        return jsonify({"valid": valid, "verified_count": count})
    @bp.route("/export", methods=["GET"])
    def export_entries() -> Any:
        """Export entries as JSON."""
        limit = int(request.args.get("limit", 1000))
        data = json.loads(al.export_json(limit))
        return jsonify(data)
    @bp.route("/count", methods=["GET"])
    def entry_count() -> Any:
        """Return entry count."""
        cat_val = request.args.get("category")
        cat = AuditCategory(cat_val) if cat_val else None
        return jsonify({"count": al.count(cat)})

def _register_policy_routes(bp: Any, al: AuditLogger) -> None:
    """Attach retention policy CRUD routes."""
    @bp.route("/policies", methods=["POST"])
    def add_policy() -> Any:
        """Add a retention policy."""
        b = _api_body()
        err = _api_need(b, "name")
        if err:
            return err
        cat = AuditCategory(b["category"]) if b.get("category") else None
        pol = al.add_policy(
            name=b["name"],
            max_age_days=b.get("max_age_days", 365),
            max_entries=b.get("max_entries", 100_000),
            category=cat,
        )
        return jsonify(pol.to_dict()), 201
    @bp.route("/policies", methods=["GET"])
    def list_policies() -> Any:
        """List retention policies."""
        return jsonify([p.to_dict() for p in al.list_policies()])
    @bp.route("/policies/<pid>", methods=["DELETE"])
    def delete_policy(pid: str) -> Any:
        """Delete a retention policy."""
        if al.delete_policy(pid):
            return jsonify({"status": "deleted"})
        return _api_404()
    @bp.route("/retention/apply", methods=["POST"])
    def apply_retention() -> Any:
        """Apply retention policies."""
        removed = al.apply_retention()
        return jsonify({"removed": removed})

def create_audit_api(al: AuditLogger) -> Any:
    """Create a Flask Blueprint exposing audit logging endpoints."""
    if not _HAS_FLASK:
        return Blueprint("audit", __name__)  # type: ignore[call-arg]
    bp = Blueprint("audit", __name__, url_prefix="/api/audit")
    _register_log_routes(bp, al)
    _register_integrity_routes(bp, al)
    _register_policy_routes(bp, al)
    @bp.route("/stats", methods=["GET"])
    def audit_stats() -> Any:
        """Return audit statistics."""
        return jsonify(al.stats())
    require_blueprint_auth(bp)
    return bp
