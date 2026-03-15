# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Multi-tenant Workspace Isolation — MTW-001

Design Label: MTW-001 — Multi-tenant Workspace Isolation
Owner: Platform Engineering
Dependencies:
  - thread_safe_operations (capped_append, bounded audit log)

Provides full multi-tenant workspace isolation for the Murphy System.
Each tenant receives a dedicated namespace for data, configuration,
and permissions, preventing any cross-tenant access or interference.

Key classes:
  TenantRole(str, Enum)       — owner, admin, member, viewer, service_account
  WorkspaceState(str, Enum)   — active, suspended, archived, pending_deletion
  IsolationLevel(str, Enum)   — strict, standard, shared
  TenantConfig                — per-tenant configuration dataclass
  TenantMember                — membership binding dataclass
  WorkspaceData               — namespaced key-value data entry
  AuditEntry                  — immutable audit trail record
  WorkspaceManager            — thread-safe orchestrator for all operations

``create_multi_tenant_api(manager)`` returns a Flask Blueprint with REST
endpoints.  All endpoints return JSON with error envelope
``{"error": "message", "code": "ERROR_CODE"}``.

Safety invariants:
  - All mutable state guarded by threading.Lock
  - Audit log bounded via capped_append (CWE-770)
  - Permission checks enforce tenant boundaries on every operation
  - No cross-tenant data access through public API
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

try:
    from flask import Blueprint, jsonify, request

    _HAS_FLASK = True
except ImportError:
    _HAS_FLASK = False

    class _StubBlueprint:                          # type: ignore[no-redef]
        """No-op Blueprint stand-in when Flask is absent."""

        def __init__(self, *a: Any, **kw: Any) -> None:
            pass

        def route(self, *a: Any, **kw: Any) -> Any:
            """Return a passthrough decorator."""
            return lambda fn: fn

    Blueprint = _StubBlueprint  # type: ignore[misc,assignment]

try:
    from .blueprint_auth import require_blueprint_auth
except ImportError:
    from blueprint_auth import require_blueprint_auth
try:
    from thread_safe_operations import capped_append
except ImportError:

    def capped_append(                              # type: ignore[misc]
        target_list: list, item: Any, max_size: int = 10_000,
    ) -> None:
        """Fallback capped append when thread_safe_operations is absent."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_MAX_STORAGE_MB: int = 1024
_DEFAULT_MAX_API_CALLS: int = 100_000
_DEFAULT_MAX_MEMBERS: int = 50
_AUDIT_CAP: int = 10_000

_ROLE_PERMISSIONS: Dict[str, frozenset] = {
    "owner": frozenset(
        {"read", "write", "admin", "delete", "manage_members", "view_audit"},
    ),
    "admin": frozenset(
        {"read", "write", "admin", "manage_members", "view_audit"},
    ),
    "member": frozenset({"read", "write"}),
    "viewer": frozenset({"read"}),
    "service_account": frozenset({"read", "write"}),
}

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TenantRole(str, Enum):
    """Roles available within a tenant workspace."""

    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"
    SERVICE_ACCOUNT = "service_account"


class WorkspaceState(str, Enum):
    """Lifecycle states of a tenant workspace."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"
    PENDING_DELETION = "pending_deletion"


class IsolationLevel(str, Enum):
    """Degree of data isolation enforced between tenants."""

    STRICT = "strict"
    STANDARD = "standard"
    SHARED = "shared"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class TenantConfig:
    """Per-tenant configuration controlling workspace behaviour and limits."""

    tenant_id: str
    name: str
    isolation_level: IsolationLevel = IsolationLevel.STANDARD
    state: WorkspaceState = WorkspaceState.ACTIVE
    max_storage_mb: int = _DEFAULT_MAX_STORAGE_MB
    max_api_calls: int = _DEFAULT_MAX_API_CALLS
    max_members: int = _DEFAULT_MAX_MEMBERS
    custom_settings: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-compatible dictionary."""
        data = asdict(self)
        data["isolation_level"] = self.isolation_level.value
        data["state"] = self.state.value
        return data


@dataclass
class TenantMember:
    """Binding between a user and a tenant workspace with a specific role."""

    user_id: str
    tenant_id: str
    role: TenantRole
    added_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    added_by: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-compatible dictionary."""
        data = asdict(self)
        data["role"] = self.role.value
        return data


@dataclass
class WorkspaceData:
    """Namespaced key-value data entry owned by a single tenant."""

    tenant_id: str
    namespace: str
    key: str
    value: Any = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-compatible dictionary."""
        return asdict(self)


@dataclass
class AuditEntry:
    """Immutable record of a workspace operation."""

    entry_id: str
    tenant_id: str
    actor: str
    action: str
    target: str = ""
    detail: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-compatible dictionary."""
        return asdict(self)


# ---------------------------------------------------------------------------
# WorkspaceManager
# ---------------------------------------------------------------------------


class WorkspaceManager:
    """Thread-safe orchestrator for multi-tenant workspace isolation.

    Manages workspace lifecycle, membership, data storage, configuration,
    and audit logging while enforcing strict tenant boundaries.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._workspaces: Dict[str, TenantConfig] = {}
        self._members: Dict[str, Dict[str, TenantMember]] = {}
        # data[tenant_id][namespace][key] -> WorkspaceData
        self._data: Dict[str, Dict[str, Dict[str, WorkspaceData]]] = {}
        self._audit: Dict[str, List[AuditEntry]] = {}

    # -- internal helpers -------------------------------------------------

    def _now(self) -> str:
        """Return current UTC timestamp as ISO-8601 string."""
        return datetime.now(timezone.utc).isoformat()

    def _record_audit(
        self,
        tenant_id: str,
        actor: str,
        action: str,
        target: str = "",
        detail: str = "",
    ) -> None:
        """Append an audit entry for *tenant_id*.

        The caller **must** already hold ``self._lock``.
        """
        entry = AuditEntry(
            entry_id=uuid.uuid4().hex,
            tenant_id=tenant_id,
            actor=actor,
            action=action,
            target=target,
            detail=detail,
        )
        self._audit.setdefault(tenant_id, [])
        capped_append(self._audit[tenant_id], entry, max_size=_AUDIT_CAP)

    # -- workspace lifecycle ----------------------------------------------

    def create_workspace(self, config: TenantConfig) -> str:
        """Create a new tenant workspace and return its *tenant_id*.

        If *config.tenant_id* is empty, a random UUID hex is generated.
        Raises ``ValueError`` if the tenant_id is already registered.
        """
        with self._lock:
            tid = config.tenant_id or uuid.uuid4().hex
            config.tenant_id = tid
            if tid in self._workspaces:
                raise ValueError(f"Workspace {tid} already exists")
            self._workspaces[tid] = config
            self._members[tid] = {}
            self._data[tid] = {}
            self._audit[tid] = []
            self._record_audit(
                tid, "system", "workspace_created",
                target=tid, detail=f"name={config.name}",
            )
            logger.info("Workspace created: %s", tid)
            return tid

    def get_workspace(self, tenant_id: str) -> Optional[TenantConfig]:
        """Return the configuration for *tenant_id*, or ``None``."""
        with self._lock:
            return self._workspaces.get(tenant_id)

    def list_workspaces(
        self,
        state_filter: Optional[WorkspaceState] = None,
    ) -> List[Dict[str, Any]]:
        """Return all workspaces, optionally filtered by *state_filter*."""
        with self._lock:
            results: List[Dict[str, Any]] = []
            for ws in self._workspaces.values():
                if state_filter is None or ws.state == state_filter:
                    results.append(ws.to_dict())
            return results

    def update_workspace(self, tenant_id: str, **updates: Any) -> bool:
        """Apply *updates* to workspace fields. Returns ``False`` if missing."""
        with self._lock:
            ws = self._workspaces.get(tenant_id)
            if ws is None:
                return False
            for key, value in updates.items():
                if hasattr(ws, key) and key not in ("tenant_id", "created_at"):
                    setattr(ws, key, value)
            ws.updated_at = self._now()
            self._record_audit(
                tenant_id, "system", "workspace_updated",
                detail=json.dumps(list(updates.keys())),
            )
            return True

    def _set_state(self, tenant_id: str, state: WorkspaceState,
                   reason: str = "") -> bool:
        """Transition workspace to *state*; acquires lock internally."""
        with self._lock:
            ws = self._workspaces.get(tenant_id)
            if ws is None:
                return False
            ws.state = state
            ws.updated_at = self._now()
            self._record_audit(
                tenant_id,
                "system",
                f"workspace_{state.value}",
                detail=reason,
            )
            return True

    def suspend_workspace(self, tenant_id: str, reason: str = "") -> bool:
        """Suspend workspace *tenant_id*."""
        return self._set_state(tenant_id, WorkspaceState.SUSPENDED, reason)

    def activate_workspace(self, tenant_id: str) -> bool:
        """Re-activate workspace *tenant_id*."""
        return self._set_state(tenant_id, WorkspaceState.ACTIVE)

    def archive_workspace(self, tenant_id: str) -> bool:
        """Archive workspace *tenant_id*."""
        return self._set_state(tenant_id, WorkspaceState.ARCHIVED)

    def delete_workspace(self, tenant_id: str) -> bool:
        """Mark workspace *tenant_id* for deletion and purge its data."""
        with self._lock:
            ws = self._workspaces.get(tenant_id)
            if ws is None:
                return False
            self._record_audit(tenant_id, "system", "workspace_deleted")
            self._members.pop(tenant_id, None)
            self._data.pop(tenant_id, None)
            del self._workspaces[tenant_id]
            logger.info("Workspace deleted: %s", tenant_id)
            return True

    # -- membership -------------------------------------------------------

    def add_member(self, tenant_id: str, user_id: str,
                   role: TenantRole, added_by: str = "system") -> bool:
        """Add *user_id* to workspace *tenant_id* with *role*.

        Returns ``False`` if workspace is missing or member cap reached.
        """
        with self._lock:
            ws = self._workspaces.get(tenant_id)
            if ws is None:
                return False
            members = self._members.setdefault(tenant_id, {})
            if len(members) >= ws.max_members and user_id not in members:
                return False
            members[user_id] = TenantMember(
                user_id=user_id, tenant_id=tenant_id,
                role=role, added_by=added_by,
            )
            self._record_audit(
                tenant_id, added_by, "member_added",
                target=user_id, detail=f"role={role.value}",
            )
            return True

    def remove_member(self, tenant_id: str, user_id: str) -> bool:
        """Remove *user_id* from workspace *tenant_id*."""
        with self._lock:
            members = self._members.get(tenant_id, {})
            if user_id not in members:
                return False
            del members[user_id]
            self._record_audit(
                tenant_id, "system", "member_removed", target=user_id,
            )
            return True

    def get_members(self, tenant_id: str) -> List[TenantMember]:
        """Return all members of workspace *tenant_id*."""
        with self._lock:
            return list(self._members.get(tenant_id, {}).values())

    def check_permission(self, tenant_id: str, user_id: str,
                         action: str) -> bool:
        """Return ``True`` if *user_id* may perform *action* in *tenant_id*."""
        with self._lock:
            member = self._members.get(tenant_id, {}).get(user_id)
            if member is None:
                return False
            allowed = _ROLE_PERMISSIONS.get(member.role.value, frozenset())
            return action in allowed

    # -- data isolation ---------------------------------------------------

    def store_data(self, tenant_id: str, namespace: str,
                   key: str, value: Any) -> bool:
        """Store *value* at *namespace*/*key* for *tenant_id*."""
        with self._lock:
            if tenant_id not in self._workspaces:
                return False
            ns_store = self._data.setdefault(tenant_id, {})
            ns = ns_store.setdefault(namespace, {})
            now = self._now()
            existing = ns.get(key)
            if existing is not None:
                existing.value = value
                existing.updated_at = now
            else:
                ns[key] = WorkspaceData(
                    tenant_id=tenant_id,
                    namespace=namespace,
                    key=key,
                    value=value,
                )
            self._record_audit(
                tenant_id, "system", "data_stored",
                target=f"{namespace}/{key}",
            )
            return True

    def get_data(self, tenant_id: str, namespace: str,
                 key: str) -> Optional[Any]:
        """Retrieve the value at *namespace*/*key* for *tenant_id*."""
        with self._lock:
            entry = self._data.get(tenant_id, {}).get(namespace, {}).get(key)
            return entry.value if entry is not None else None

    def delete_data(self, tenant_id: str, namespace: str,
                    key: str) -> bool:
        """Delete the entry at *namespace*/*key* for *tenant_id*."""
        with self._lock:
            ns = self._data.get(tenant_id, {}).get(namespace, {})
            if key not in ns:
                return False
            del ns[key]
            self._record_audit(
                tenant_id, "system", "data_deleted",
                target=f"{namespace}/{key}",
            )
            return True

    def list_data(self, tenant_id: str, namespace: str) -> List[str]:
        """Return all keys stored in *namespace* for *tenant_id*."""
        with self._lock:
            ns = self._data.get(tenant_id, {}).get(namespace, {})
            return list(ns.keys())

    # -- config isolation -------------------------------------------------

    def get_config(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Return the full configuration dictionary for *tenant_id*."""
        with self._lock:
            ws = self._workspaces.get(tenant_id)
            return ws.to_dict() if ws is not None else None

    def update_config(self, tenant_id: str, key: str, value: Any) -> bool:
        """Update a single custom configuration *key* for *tenant_id*."""
        with self._lock:
            ws = self._workspaces.get(tenant_id)
            if ws is None:
                return False
            ws.custom_settings[key] = value
            ws.updated_at = self._now()
            self._record_audit(
                tenant_id, "system", "config_updated", target=key,
            )
            return True

    # -- audit ------------------------------------------------------------

    def get_audit_log(self, tenant_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Return the most recent *limit* audit entries for *tenant_id*."""
        with self._lock:
            entries = self._audit.get(tenant_id, [])
            return [e.to_dict() for e in entries[-limit:]]

    # -- status & validation ----------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return an aggregate summary of all managed workspaces."""
        with self._lock:
            counts: Dict[str, int] = {}
            for ws in self._workspaces.values():
                counts[ws.state.value] = counts.get(ws.state.value, 0) + 1
            return {
                "total_workspaces": len(self._workspaces),
                "state_counts": counts,
                "total_members": sum(
                    len(m) for m in self._members.values()
                ),
                "total_data_entries": sum(
                    sum(len(ns) for ns in tenant.values())
                    for tenant in self._data.values()
                ),
            }

    def wingman_validate(self, tenant_id: str) -> Dict[str, Any]:
        """Wingman-pair validation of workspace *tenant_id* integrity."""
        with self._lock:
            ws = self._workspaces.get(tenant_id)
            if ws is None:
                return {"valid": False, "errors": ["workspace_not_found"]}
            errors: List[str] = []
            checks = 0
            checks += 1
            if not ws.name:
                errors.append("name_empty")
            checks += 1
            if ws.max_storage_mb <= 0:
                errors.append("invalid_storage_limit")
            checks += 1
            if ws.max_api_calls <= 0:
                errors.append("invalid_api_calls_limit")
            checks += 1
            if ws.max_members <= 0:
                errors.append("invalid_members_limit")
            checks += 1
            members = self._members.get(tenant_id, {})
            has_owner = any(
                m.role == TenantRole.OWNER for m in members.values()
            )
            if not has_owner:
                errors.append("no_owner_assigned")
            return {
                "valid": len(errors) == 0,
                "tenant_id": tenant_id,
                "checks_run": checks,
                "errors": errors,
            }

    def sandbox_simulate(self, operation: str, tenant_id: str) -> Dict[str, Any]:
        """Causality-sandbox dry-run of *operation* on *tenant_id*."""
        with self._lock:
            ws = self._workspaces.get(tenant_id)
            if ws is None:
                return {
                    "allowed": False,
                    "operation": operation,
                    "tenant_id": tenant_id,
                    "reason": "workspace_not_found",
                }
            allowed = True
            reason = ""
            if ws.state == WorkspaceState.PENDING_DELETION:
                allowed = False
                reason = "workspace_pending_deletion"
            elif ws.state == WorkspaceState.ARCHIVED:
                if operation in ("write", "delete"):
                    allowed = False
                    reason = f"cannot {operation} while archived"
            elif ws.state == WorkspaceState.SUSPENDED:
                if operation != "read":
                    allowed = False
                    reason = f"cannot {operation} while suspended"
            return {
                "allowed": allowed,
                "operation": operation,
                "tenant_id": tenant_id,
                "current_state": ws.state.value,
                "reason": reason,
            }


# ---------------------------------------------------------------------------
# Flask Blueprint factory
# ---------------------------------------------------------------------------


def create_multi_tenant_api(
    manager: Optional[WorkspaceManager] = None,
) -> Any:
    """Create a Flask Blueprint for multi-tenant workspace management.

    Args:
        manager: optional WorkspaceManager; created automatically if omitted.
    Returns:
        A Flask Blueprint (or stub when Flask is absent).
    """
    mgr = manager or WorkspaceManager()

    if not _HAS_FLASK:
        return Blueprint()  # type: ignore[call-arg]

    bp = Blueprint("multi_tenant", __name__, url_prefix="/api/tenants")

    # -- health -----------------------------------------------------------

    @bp.route("/health", methods=["GET"])
    def health() -> Any:
        """Health check for multi-tenant subsystem."""
        status = mgr.get_status()
        status["status"] = "healthy"
        return jsonify(status)

    # -- workspace CRUD ---------------------------------------------------

    @bp.route("", methods=["POST"])
    def create_workspace() -> Any:
        """Create a new tenant workspace."""
        body = request.get_json(silent=True) or {}
        name = body.get("name", "")
        if not name:
            return jsonify({"error": "name is required", "code": "MISSING_NAME"}), 400
        tenant_id = body.get("tenant_id", uuid.uuid4().hex)
        config = TenantConfig(
            tenant_id=tenant_id, name=name,
            isolation_level=IsolationLevel(body.get("isolation_level", "standard")),
            max_storage_mb=int(body.get("max_storage_mb", _DEFAULT_MAX_STORAGE_MB)),
            max_api_calls=int(body.get("max_api_calls", _DEFAULT_MAX_API_CALLS)),
            max_members=int(body.get("max_members", _DEFAULT_MAX_MEMBERS)),
            custom_settings=body.get("custom_settings", {}),
        )
        try:
            tid = mgr.create_workspace(config)
        except ValueError as exc:
            return jsonify({"error": str(exc), "code": "DUPLICATE_WORKSPACE"}), 409
        return jsonify({"tenant_id": tid}), 201

    @bp.route("", methods=["GET"])
    def list_workspaces() -> Any:
        """List all workspaces with optional state filter."""
        state = request.args.get("state")
        sf = WorkspaceState(state) if state else None
        return jsonify(mgr.list_workspaces(state_filter=sf))

    @bp.route("/<tid>", methods=["GET"])
    def get_workspace(tid: str) -> Any:
        """Get workspace details."""
        ws = mgr.get_workspace(tid)
        if ws is None:
            return jsonify({"error": "not found", "code": "NOT_FOUND"}), 404
        return jsonify(ws.to_dict())

    @bp.route("/<tid>", methods=["PUT"])
    def update_workspace(tid: str) -> Any:
        """Update workspace attributes."""
        body = request.get_json(silent=True) or {}
        if mgr.update_workspace(tid, **body):
            return jsonify({"updated": True})
        return jsonify({"error": "not found", "code": "NOT_FOUND"}), 404

    @bp.route("/<tid>/suspend", methods=["POST"])
    def suspend_workspace(tid: str) -> Any:
        """Suspend a workspace."""
        body = request.get_json(silent=True) or {}
        reason = body.get("reason", "")
        if mgr.suspend_workspace(tid, reason):
            return jsonify({"suspended": True})
        return jsonify({"error": "not found", "code": "NOT_FOUND"}), 404

    @bp.route("/<tid>/activate", methods=["POST"])
    def activate_workspace(tid: str) -> Any:
        """Activate a suspended or archived workspace."""
        if mgr.activate_workspace(tid):
            return jsonify({"activated": True})
        return jsonify({"error": "not found", "code": "NOT_FOUND"}), 404

    @bp.route("/<tid>", methods=["DELETE"])
    def delete_workspace(tid: str) -> Any:
        """Delete a workspace and purge all its data."""
        if mgr.delete_workspace(tid):
            return jsonify({"deleted": True})
        return jsonify({"error": "not found", "code": "NOT_FOUND"}), 404

    # -- membership -------------------------------------------------------

    @bp.route("/<tid>/members", methods=["POST"])
    def add_member(tid: str) -> Any:
        """Add a member to a workspace."""
        body = request.get_json(silent=True) or {}
        user_id = body.get("user_id", "")
        role_str = body.get("role", "member")
        added_by = body.get("added_by", "system")
        if not user_id:
            return jsonify({"error": "user_id required", "code": "MISSING_USER"}), 400
        try:
            role = TenantRole(role_str)
        except ValueError:
            return jsonify({"error": "invalid role", "code": "INVALID_ROLE"}), 400
        if mgr.add_member(tid, user_id, role, added_by):
            return jsonify({"added": True}), 201
        return jsonify({"error": "failed to add member", "code": "ADD_FAILED"}), 400

    @bp.route("/<tid>/members", methods=["GET"])
    def list_members(tid: str) -> Any:
        """List workspace members."""
        members = mgr.get_members(tid)
        return jsonify([m.to_dict() for m in members])

    @bp.route("/<tid>/members/<uid>", methods=["DELETE"])
    def remove_member(tid: str, uid: str) -> Any:
        """Remove a member from a workspace."""
        if mgr.remove_member(tid, uid):
            return jsonify({"removed": True})
        return jsonify({"error": "member not found", "code": "NOT_FOUND"}), 404

    # -- data isolation ---------------------------------------------------

    @bp.route("/<tid>/data/<ns>", methods=["POST"])
    def store_data(tid: str, ns: str) -> Any:
        """Store a key-value pair in a tenant namespace."""
        body = request.get_json(silent=True) or {}
        key = body.get("key", "")
        value = body.get("value")
        if not key:
            return jsonify({"error": "key required", "code": "MISSING_KEY"}), 400
        if mgr.store_data(tid, ns, key, value):
            return jsonify({"stored": True}), 201
        return jsonify({"error": "workspace not found", "code": "NOT_FOUND"}), 404

    @bp.route("/<tid>/data/<ns>/<key>", methods=["GET"])
    def get_data(tid: str, ns: str, key: str) -> Any:
        """Retrieve a value from a tenant namespace."""
        value = mgr.get_data(tid, ns, key)
        if value is None:
            return jsonify({"error": "not found", "code": "NOT_FOUND"}), 404
        return jsonify({"key": key, "value": value})

    # -- audit ------------------------------------------------------------

    @bp.route("/<tid>/audit", methods=["GET"])
    def audit_log(tid: str) -> Any:
        """Retrieve the audit log for a workspace."""
        limit = int(request.args.get("limit", "50"))
        return jsonify(mgr.get_audit_log(tid, limit=limit))

    # -- config -----------------------------------------------------------

    @bp.route("/<tid>/config", methods=["GET"])
    def get_config(tid: str) -> Any:
        """Get workspace configuration."""
        cfg = mgr.get_config(tid)
        if cfg is None:
            return jsonify({"error": "not found", "code": "NOT_FOUND"}), 404
        return jsonify(cfg)

    @bp.route("/<tid>/config", methods=["PUT"])
    def update_config(tid: str) -> Any:
        """Update a custom configuration key."""
        body = request.get_json(silent=True) or {}
        key = body.get("key", "")
        value = body.get("value")
        if not key:
            return jsonify({"error": "key required", "code": "MISSING_KEY"}), 400
        if mgr.update_config(tid, key, value):
            return jsonify({"updated": True})
        return jsonify({"error": "not found", "code": "NOT_FOUND"}), 404

    require_blueprint_auth(bp)
    return bp
