# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Comprehensive test suite for multi_tenant_workspace — MTW-001.

Uses the storyline-actuals ``record()`` pattern to capture every check
as an auditable MTWRecord with cause / effect / lesson annotations.
"""

from __future__ import annotations

import datetime
import json
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))

from multi_tenant_workspace import (  # noqa: E402
    AuditEntry,
    IsolationLevel,
    TenantConfig,
    TenantMember,
    TenantRole,
    WorkspaceData,
    WorkspaceManager,
    WorkspaceState,
    create_multi_tenant_api,
)

# ---------------------------------------------------------------------------
# Record pattern
# ---------------------------------------------------------------------------


@dataclass
class MTWRecord:
    """One MTW check record."""

    check_id: str
    description: str
    expected: Any
    actual: Any
    passed: bool
    cause: str = ""
    effect: str = ""
    lesson: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat()
    )


_RESULTS: List[MTWRecord] = []


def record(
    check_id: str,
    desc: str,
    expected: Any,
    actual: Any,
    cause: str = "",
    effect: str = "",
    lesson: str = "",
) -> bool:
    ok = expected == actual
    _RESULTS.append(
        MTWRecord(
            check_id=check_id,
            description=desc,
            expected=expected,
            actual=actual,
            passed=ok,
            cause=cause,
            effect=effect,
            lesson=lesson,
        )
    )
    return ok


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fresh_manager() -> WorkspaceManager:
    """Return a new WorkspaceManager with no state."""
    return WorkspaceManager()


def _make_config(
    tenant_id: str = "t1",
    name: str = "Workspace One",
    **kwargs: Any,
) -> TenantConfig:
    return TenantConfig(tenant_id=tenant_id, name=name, **kwargs)


# ====================================================================
# Model tests
# ====================================================================


def test_mtw_001_tenant_role_values():
    expected = {"owner", "admin", "member", "viewer", "service_account"}
    actual = {r.value for r in TenantRole}
    ok = record(
        "MTW-001",
        "TenantRole enum has correct values",
        expected,
        actual,
        cause="Enum definition in module",
        effect="Role-based access control is correct",
        lesson="Always verify enum members after changes",
    )
    assert ok


def test_mtw_002_workspace_state_values():
    expected = {"active", "suspended", "archived", "pending_deletion"}
    actual = {s.value for s in WorkspaceState}
    ok = record(
        "MTW-002",
        "WorkspaceState enum has correct values",
        expected,
        actual,
        cause="Enum definition in module",
        effect="Lifecycle management is complete",
        lesson="Missing states break lifecycle transitions",
    )
    assert ok


def test_mtw_003_isolation_level_values():
    expected = {"strict", "standard", "shared"}
    actual = {lv.value for lv in IsolationLevel}
    ok = record(
        "MTW-003",
        "IsolationLevel enum has correct values",
        expected,
        actual,
        cause="Enum definition in module",
        effect="Tenant isolation enforced at correct levels",
        lesson="New isolation levels require tests",
    )
    assert ok


def test_mtw_004_tenant_config_creation():
    cfg = TenantConfig(tenant_id="tc4", name="Test Config")
    checks = (
        cfg.tenant_id == "tc4"
        and cfg.name == "Test Config"
        and cfg.isolation_level == IsolationLevel.STANDARD
        and cfg.state == WorkspaceState.ACTIVE
        and cfg.max_storage_mb == 1024
        and cfg.max_api_calls == 100_000
        and cfg.max_members == 50
        and isinstance(cfg.custom_settings, dict)
        and cfg.created_at != ""
        and cfg.updated_at != ""
    )
    ok = record(
        "MTW-004",
        "TenantConfig defaults are correct",
        True,
        checks,
        cause="Dataclass field defaults",
        effect="New workspaces start with sane limits",
        lesson="Defaults must match documented constants",
    )
    assert ok


def test_mtw_005_tenant_config_to_dict():
    cfg = TenantConfig(tenant_id="tc5", name="Dict Test")
    d = cfg.to_dict()
    checks = (
        isinstance(d, dict)
        and d["tenant_id"] == "tc5"
        and d["name"] == "Dict Test"
        and d["isolation_level"] == "standard"
        and d["state"] == "active"
    )
    ok = record(
        "MTW-005",
        "TenantConfig.to_dict() serialises enums to strings",
        True,
        checks,
        cause="to_dict converts enums via .value",
        effect="JSON serialisation is safe",
        lesson="Always serialise enums as their value strings",
    )
    assert ok


def test_mtw_006_tenant_member_creation():
    m = TenantMember(user_id="u1", tenant_id="t1", role=TenantRole.MEMBER)
    checks = (
        m.user_id == "u1"
        and m.tenant_id == "t1"
        and m.role == TenantRole.MEMBER
        and m.added_at != ""
        and m.added_by == ""
    )
    ok = record(
        "MTW-006",
        "TenantMember fields initialise correctly",
        True,
        checks,
        cause="Dataclass construction",
        effect="Member binding is valid",
        lesson="added_by defaults to empty string when not specified",
    )
    assert ok


def test_mtw_007_workspace_data_creation():
    wd = WorkspaceData(
        tenant_id="t1", namespace="ns", key="k1", value="hello"
    )
    checks = (
        wd.tenant_id == "t1"
        and wd.namespace == "ns"
        and wd.key == "k1"
        and wd.value == "hello"
        and wd.created_at != ""
    )
    ok = record(
        "MTW-007",
        "WorkspaceData fields initialise correctly",
        True,
        checks,
        cause="Dataclass construction",
        effect="Namespaced data entry is valid",
        lesson="Ensure value field accepts arbitrary types",
    )
    assert ok


def test_mtw_008_audit_entry_creation():
    ae = AuditEntry(
        entry_id="e1",
        tenant_id="t1",
        actor="system",
        action="created",
        target="t1",
        detail="init",
    )
    checks = (
        ae.entry_id == "e1"
        and ae.tenant_id == "t1"
        and ae.actor == "system"
        and ae.action == "created"
        and ae.target == "t1"
        and ae.detail == "init"
        and ae.timestamp != ""
    )
    ok = record(
        "MTW-008",
        "AuditEntry fields initialise correctly",
        True,
        checks,
        cause="Dataclass construction",
        effect="Audit records are complete",
        lesson="Every operation must be auditable",
    )
    assert ok


# ====================================================================
# Workspace CRUD tests
# ====================================================================


def test_mtw_009_create_workspace():
    mgr = _fresh_manager()
    cfg = _make_config("t9", "Nine")
    tid = mgr.create_workspace(cfg)
    ok = record(
        "MTW-009",
        "create_workspace returns tenant_id",
        "t9",
        tid,
        cause="WorkspaceManager.create_workspace()",
        effect="Workspace is registered and accessible",
        lesson="Returned id must match config.tenant_id",
    )
    assert ok


def test_mtw_010_get_workspace():
    mgr = _fresh_manager()
    mgr.create_workspace(_make_config("t10", "Ten"))
    ws = mgr.get_workspace("t10")
    ok = record(
        "MTW-010",
        "get_workspace returns correct config",
        "Ten",
        ws.name if ws else None,
        cause="Workspace lookup by tenant_id",
        effect="Config is retrievable after creation",
        lesson="get_workspace returns None for unknown ids",
    )
    assert ok


def test_mtw_011_list_workspaces():
    mgr = _fresh_manager()
    mgr.create_workspace(_make_config("t11a", "A"))
    mgr.create_workspace(_make_config("t11b", "B"))
    results = mgr.list_workspaces()
    ok = record(
        "MTW-011",
        "list_workspaces returns all workspaces",
        2,
        len(results),
        cause="Two workspaces created",
        effect="Full inventory available to callers",
        lesson="list_workspaces returns dicts via to_dict()",
    )
    assert ok


def test_mtw_012_list_workspaces_filter():
    mgr = _fresh_manager()
    mgr.create_workspace(_make_config("t12a", "Active"))
    mgr.create_workspace(_make_config("t12b", "Suspended"))
    mgr.suspend_workspace("t12b")
    active = mgr.list_workspaces(state_filter=WorkspaceState.ACTIVE)
    ok = record(
        "MTW-012",
        "list_workspaces with state_filter works",
        1,
        len(active),
        cause="One workspace suspended, filter for active",
        effect="Only matching workspaces returned",
        lesson="State filter uses enum comparison",
    )
    assert ok


def test_mtw_013_update_workspace():
    mgr = _fresh_manager()
    mgr.create_workspace(_make_config("t13", "Before"))
    mgr.update_workspace("t13", name="After")
    ws = mgr.get_workspace("t13")
    ok = record(
        "MTW-013",
        "update_workspace modifies fields",
        "After",
        ws.name if ws else None,
        cause="update_workspace called with name='After'",
        effect="Workspace name changed in-place",
        lesson="Immutable fields (tenant_id, created_at) are protected",
    )
    assert ok


def test_mtw_014_suspend_workspace():
    mgr = _fresh_manager()
    mgr.create_workspace(_make_config("t14", "Suspend Me"))
    mgr.suspend_workspace("t14", reason="maintenance")
    ws = mgr.get_workspace("t14")
    ok = record(
        "MTW-014",
        "suspend changes state to suspended",
        WorkspaceState.SUSPENDED,
        ws.state if ws else None,
        cause="suspend_workspace called",
        effect="Workspace no longer accepts writes",
        lesson="Suspension is reversible via activate",
    )
    assert ok


def test_mtw_015_activate_workspace():
    mgr = _fresh_manager()
    mgr.create_workspace(_make_config("t15", "Reactivate"))
    mgr.suspend_workspace("t15")
    mgr.activate_workspace("t15")
    ws = mgr.get_workspace("t15")
    ok = record(
        "MTW-015",
        "activate changes state back to active",
        WorkspaceState.ACTIVE,
        ws.state if ws else None,
        cause="activate_workspace after suspend",
        effect="Workspace is operational again",
        lesson="State transitions must be idempotent-safe",
    )
    assert ok


def test_mtw_016_archive_workspace():
    mgr = _fresh_manager()
    mgr.create_workspace(_make_config("t16", "Archive"))
    mgr.archive_workspace("t16")
    ws = mgr.get_workspace("t16")
    ok = record(
        "MTW-016",
        "archive changes state to archived",
        WorkspaceState.ARCHIVED,
        ws.state if ws else None,
        cause="archive_workspace called",
        effect="Workspace is read-only",
        lesson="Archived workspaces block writes in sandbox",
    )
    assert ok


def test_mtw_017_delete_workspace():
    mgr = _fresh_manager()
    mgr.create_workspace(_make_config("t17", "Delete Me"))
    result = mgr.delete_workspace("t17")
    ws = mgr.get_workspace("t17")
    checks = result is True and ws is None
    ok = record(
        "MTW-017",
        "delete removes workspace completely",
        True,
        checks,
        cause="delete_workspace called",
        effect="Workspace and all data purged",
        lesson="Deletion is irreversible; guard with confirmation",
    )
    assert ok


# ====================================================================
# Member management tests
# ====================================================================


def test_mtw_018_add_member():
    mgr = _fresh_manager()
    mgr.create_workspace(_make_config("t18", "Members"))
    added = mgr.add_member("t18", "user1", TenantRole.MEMBER, "admin1")
    members = mgr.get_members("t18")
    checks = added is True and len(members) == 1 and members[0].user_id == "user1"
    ok = record(
        "MTW-018",
        "add_member registers user with role",
        True,
        checks,
        cause="add_member called with MEMBER role",
        effect="User visible in membership list",
        lesson="Member cap enforced in add_member",
    )
    assert ok


def test_mtw_019_remove_member():
    mgr = _fresh_manager()
    mgr.create_workspace(_make_config("t19", "Remove"))
    mgr.add_member("t19", "user1", TenantRole.VIEWER)
    removed = mgr.remove_member("t19", "user1")
    members = mgr.get_members("t19")
    checks = removed is True and len(members) == 0
    ok = record(
        "MTW-019",
        "remove_member removes user from workspace",
        True,
        checks,
        cause="remove_member called",
        effect="User no longer in membership list",
        lesson="Removing nonexistent member returns False",
    )
    assert ok


# ====================================================================
# Permissions / RBAC tests
# ====================================================================


def test_mtw_020_permission_owner():
    mgr = _fresh_manager()
    mgr.create_workspace(_make_config("t20", "RBAC"))
    mgr.add_member("t20", "owner1", TenantRole.OWNER)
    perms = all(
        mgr.check_permission("t20", "owner1", action)
        for action in ("read", "write", "admin", "delete", "manage_members", "view_audit")
    )
    ok = record(
        "MTW-020",
        "owner has all permissions",
        True,
        perms,
        cause="Owner role maps to full permission set",
        effect="Owner can perform every action",
        lesson="Owner is the only role with delete permission",
    )
    assert ok


def test_mtw_021_permission_viewer():
    mgr = _fresh_manager()
    mgr.create_workspace(_make_config("t21", "ViewerRBAC"))
    mgr.add_member("t21", "v1", TenantRole.VIEWER)
    can_read = mgr.check_permission("t21", "v1", "read")
    cannot_write = not mgr.check_permission("t21", "v1", "write")
    cannot_admin = not mgr.check_permission("t21", "v1", "admin")
    checks = can_read and cannot_write and cannot_admin
    ok = record(
        "MTW-021",
        "viewer only has read permission",
        True,
        checks,
        cause="Viewer role maps to {read} only",
        effect="Viewer cannot modify workspace",
        lesson="Principle of least privilege for viewers",
    )
    assert ok


def test_mtw_022_permission_member():
    mgr = _fresh_manager()
    mgr.create_workspace(_make_config("t22", "MemberRBAC"))
    mgr.add_member("t22", "m1", TenantRole.MEMBER)
    can_read = mgr.check_permission("t22", "m1", "read")
    can_write = mgr.check_permission("t22", "m1", "write")
    cannot_admin = not mgr.check_permission("t22", "m1", "admin")
    cannot_delete = not mgr.check_permission("t22", "m1", "delete")
    checks = can_read and can_write and cannot_admin and cannot_delete
    ok = record(
        "MTW-022",
        "member has read and write only",
        True,
        checks,
        cause="Member role maps to {read, write}",
        effect="Members collaborate without admin power",
        lesson="Member role is the default for new users",
    )
    assert ok


# ====================================================================
# Data isolation tests
# ====================================================================


def test_mtw_023_cross_tenant_data_isolation():
    mgr = _fresh_manager()
    mgr.create_workspace(_make_config("tA", "Tenant A"))
    mgr.create_workspace(_make_config("tB", "Tenant B"))
    mgr.store_data("tA", "secrets", "api_key", "secret-A")
    val_b = mgr.get_data("tB", "secrets", "api_key")
    ok = record(
        "MTW-023",
        "data in tenant A is NOT visible to tenant B",
        None,
        val_b,
        cause="Data stored only in tA namespace",
        effect="Cross-tenant data leakage prevented",
        lesson="Isolation is the primary security invariant",
    )
    assert ok


def test_mtw_024_store_and_get_data():
    mgr = _fresh_manager()
    mgr.create_workspace(_make_config("t24", "DataStore"))
    mgr.store_data("t24", "cache", "key1", {"x": 42})
    val = mgr.get_data("t24", "cache", "key1")
    ok = record(
        "MTW-024",
        "store_data then get_data returns value",
        {"x": 42},
        val,
        cause="store_data stores value in namespace/key",
        effect="Data is retrievable by same tenant",
        lesson="Values can be any JSON-serialisable type",
    )
    assert ok


def test_mtw_025_delete_data():
    mgr = _fresh_manager()
    mgr.create_workspace(_make_config("t25", "DataDel"))
    mgr.store_data("t25", "ns", "k1", "v1")
    deleted = mgr.delete_data("t25", "ns", "k1")
    after = mgr.get_data("t25", "ns", "k1")
    checks = deleted is True and after is None
    ok = record(
        "MTW-025",
        "delete_data removes entry",
        True,
        checks,
        cause="delete_data called on existing key",
        effect="Key no longer accessible",
        lesson="Double-delete returns False",
    )
    assert ok


# ====================================================================
# Config isolation tests
# ====================================================================


def test_mtw_026_config_isolation():
    mgr = _fresh_manager()
    mgr.create_workspace(_make_config("tC", "Config C"))
    mgr.create_workspace(_make_config("tD", "Config D"))
    mgr.update_config("tC", "theme", "dark")
    cfg_d = mgr.get_config("tD")
    theme_d = cfg_d.get("custom_settings", {}).get("theme") if cfg_d else None
    ok = record(
        "MTW-026",
        "config update in tenant C does not affect tenant D",
        None,
        theme_d,
        cause="update_config only targets tC",
        effect="Tenant D config unchanged",
        lesson="Config isolation prevents cross-tenant bleed",
    )
    assert ok


# ====================================================================
# Audit trail tests
# ====================================================================


def test_mtw_027_audit_log():
    mgr = _fresh_manager()
    mgr.create_workspace(_make_config("t27", "Audit"))
    mgr.add_member("t27", "u1", TenantRole.MEMBER)
    mgr.store_data("t27", "ns", "k", "v")
    log = mgr.get_audit_log("t27")
    actions = [e["action"] for e in log]
    checks = (
        "workspace_created" in actions
        and "member_added" in actions
        and "data_stored" in actions
        and len(log) >= 3
    )
    ok = record(
        "MTW-027",
        "operations create audit entries",
        True,
        checks,
        cause="create, add_member, store_data all audit",
        effect="Full operation history available",
        lesson="Audit log is capped at 10,000 entries",
    )
    assert ok


# ====================================================================
# Flask API endpoint tests
# ====================================================================


def _flask_client():
    """Build a Flask test client with the multi-tenant API blueprint."""
    from flask import Flask

    app = Flask(__name__)
    mgr = WorkspaceManager()
    bp = create_multi_tenant_api(mgr)
    app.register_blueprint(bp)
    return app.test_client(), mgr


def test_mtw_028_flask_create_tenant():
    client, _ = _flask_client()
    resp = client.post(
        "/api/tenants",
        json={"name": "FlaskTenant", "tenant_id": "ft28"},
    )
    ok = record(
        "MTW-028",
        "POST /api/tenants returns 201",
        201,
        resp.status_code,
        cause="Valid JSON body with name",
        effect="Tenant created via REST API",
        lesson="Missing name returns 400",
    )
    assert ok


def test_mtw_029_flask_list_tenants():
    client, _ = _flask_client()
    client.post("/api/tenants", json={"name": "A", "tenant_id": "ft29a"})
    client.post("/api/tenants", json={"name": "B", "tenant_id": "ft29b"})
    resp = client.get("/api/tenants")
    data = resp.get_json()
    ok = record(
        "MTW-029",
        "GET /api/tenants returns list",
        True,
        isinstance(data, list) and len(data) == 2,
        cause="Two tenants created",
        effect="API returns both",
        lesson="State filter via query param supported",
    )
    assert ok


def test_mtw_030_flask_get_tenant():
    client, _ = _flask_client()
    client.post("/api/tenants", json={"name": "Detail", "tenant_id": "ft30"})
    resp = client.get("/api/tenants/ft30")
    data = resp.get_json()
    checks = resp.status_code == 200 and data.get("name") == "Detail"
    ok = record(
        "MTW-030",
        "GET /api/tenants/<tid> returns detail",
        True,
        checks,
        cause="Workspace exists",
        effect="Full config returned as JSON",
        lesson="to_dict() serialises enums for JSON safety",
    )
    assert ok


def test_mtw_031_flask_not_found():
    client, _ = _flask_client()
    resp = client.get("/api/tenants/nonexistent")
    ok = record(
        "MTW-031",
        "GET unknown tenant returns 404",
        404,
        resp.status_code,
        cause="No workspace with this tenant_id",
        effect="Error envelope returned",
        lesson="Always check for NOT_FOUND code in clients",
    )
    assert ok


# ====================================================================
# Thread safety tests
# ====================================================================


def test_mtw_032_thread_safety():
    mgr = _fresh_manager()
    errors: List[str] = []

    def _create(i: int) -> None:
        try:
            mgr.create_workspace(_make_config(f"thread-{i}", f"T{i}"))
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))

    threads = [threading.Thread(target=_create, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    count = len(mgr.list_workspaces())
    checks = count == 10 and len(errors) == 0
    ok = record(
        "MTW-032",
        "concurrent create_workspace from 10 threads succeeds",
        True,
        checks,
        cause="10 threads call create_workspace simultaneously",
        effect="All workspaces created without race conditions",
        lesson="Lock guards all mutable state in WorkspaceManager",
    )
    assert ok


# ====================================================================
# Wingman gate tests
# ====================================================================


def test_mtw_033_wingman_validation():
    mgr = _fresh_manager()
    mgr.create_workspace(_make_config("t33", "Wingman"))
    mgr.add_member("t33", "o1", TenantRole.OWNER)
    result = mgr.wingman_validate("t33")
    checks = (
        result.get("valid") is True
        and result.get("tenant_id") == "t33"
        and result.get("checks_run", 0) > 0
        and result.get("errors") == []
    )
    ok = record(
        "MTW-033",
        "wingman_validate returns valid structure",
        True,
        checks,
        cause="Workspace has name, limits, and owner",
        effect="Validation passes all checks",
        lesson="Missing owner triggers no_owner_assigned error",
    )
    assert ok


# ====================================================================
# Sandbox gate tests
# ====================================================================


def test_mtw_034_sandbox_simulation():
    mgr = _fresh_manager()
    mgr.create_workspace(_make_config("t34", "Sandbox"))
    mgr.suspend_workspace("t34")
    result = mgr.sandbox_simulate("write", "t34")
    checks = (
        result.get("allowed") is False
        and result.get("operation") == "write"
        and result.get("tenant_id") == "t34"
        and result.get("current_state") == "suspended"
        and result.get("reason") != ""
    )
    ok = record(
        "MTW-034",
        "sandbox_simulate returns simulated results",
        True,
        checks,
        cause="Write attempted on suspended workspace",
        effect="Sandbox blocks the operation",
        lesson="Sandbox dry-run prevents destructive actions",
    )
    assert ok


# ====================================================================
# Summary
# ====================================================================


def test_mtw_035_summary():
    total = len(_RESULTS)
    passed = sum(1 for r in _RESULTS if r.passed)
    failed = [r for r in _RESULTS if not r.passed]
    for f in failed:
        print(f"FAIL {f.check_id}: expected={f.expected!r} actual={f.actual!r}")
    print(f"\nMTW-001 Test Suite: {passed}/{total} passed")
    assert passed == total, f"{passed}/{total} passed"
