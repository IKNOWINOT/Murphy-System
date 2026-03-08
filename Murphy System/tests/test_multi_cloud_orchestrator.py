# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Comprehensive test suite for multi_cloud_orchestrator — MCO-001.

Uses the storyline-actuals ``record()`` pattern to capture every check
as an auditable MCORecord with cause / effect / lesson annotations.
"""
from __future__ import annotations

import datetime
import json
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))

from multi_cloud_orchestrator import (  # noqa: E402
    CloudAccount,
    CloudOperation,
    CloudPlatform,
    CostAllocation,
    Deployment,
    DeploymentStatus,
    HealthCheck,
    ManagedResource,
    MultiCloudOrchestrator,
    OperationType,
    RegionStatus,
    ResourceType,
    create_multi_cloud_api,
    gate_mco_in_sandbox,
    validate_wingman_pair,
)

# -- Record pattern --------------------------------------------------------


@dataclass
class MCORecord:
    """One MCO check record."""

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


_RESULTS: List[MCORecord] = []


def record(
    check_id: str,
    description: str,
    expected: Any,
    actual: Any,
    *,
    cause: str = "",
    effect: str = "",
    lesson: str = "",
) -> None:
    passed = expected == actual
    _RESULTS.append(
        MCORecord(
            check_id=check_id,
            description=description,
            expected=expected,
            actual=actual,
            passed=passed,
            cause=cause,
            effect=effect,
            lesson=lesson,
        )
    )
    assert passed, (
        f"[{check_id}] {description}: expected={expected!r}, got={actual!r}"
    )


# -- Helpers ---------------------------------------------------------------


def _make_orch() -> MultiCloudOrchestrator:
    return MultiCloudOrchestrator(max_accounts=500, max_resources=500)


def _add_account(orch: MultiCloudOrchestrator, platform: str = "aws",
                 account_id: str = "123456", alias: str = "main",
                 region: str = "us-east-1") -> CloudAccount:
    return orch.register_account(
        platform=platform, account_id=account_id,
        alias=alias, region=region,
        credentials_ref="ENV_AWS_KEY",
    )


# ==========================================================================
# Tests
# ==========================================================================


class TestAccountManagement:
    """Cloud account registration and CRUD."""

    def test_register_basic(self) -> None:
        orch = _make_orch()
        acct = orch.register_account("aws", "111222333", alias="prod")
        record(
            "MCO-001", "register returns CloudAccount",
            True, isinstance(acct, CloudAccount),
            cause="register_account called",
            effect="CloudAccount returned",
            lesson="Factory must return typed account",
        )
        assert acct.alias == "prod"

    def test_register_default_alias(self) -> None:
        orch = _make_orch()
        acct = orch.register_account("gcp", "gcp-project-1")
        record(
            "MCO-002", "default alias is account_id",
            "gcp-project-1", acct.alias,
            cause="no alias specified",
            effect="alias defaults to account_id",
            lesson="Defaults must be sensible",
        )

    def test_register_enum_platform(self) -> None:
        orch = _make_orch()
        acct = orch.register_account(CloudPlatform.azure, "az-sub-1")
        record(
            "MCO-003", "enum CloudPlatform coerced to string",
            "azure", acct.platform,
            cause="CloudPlatform enum passed",
            effect="stored as string value",
            lesson="Enum coercion must work",
        )

    def test_get_account(self) -> None:
        orch = _make_orch()
        acct = _add_account(orch)
        got = orch.get_account(acct.id)
        record(
            "MCO-004", "get_account returns correct account",
            acct.id, got.id if got else None,
            cause="get by ID",
            effect="same account returned",
            lesson="Lookup must return existing accounts",
        )

    def test_get_account_missing(self) -> None:
        orch = _make_orch()
        got = orch.get_account("nonexistent")
        record(
            "MCO-005", "get_account returns None for missing",
            True, got is None,
            cause="invalid ID",
            effect="None returned",
            lesson="Missing accounts return None",
        )

    def test_list_accounts(self) -> None:
        orch = _make_orch()
        _add_account(orch, platform="aws", account_id="a1")
        _add_account(orch, platform="gcp", account_id="g1")
        _add_account(orch, platform="aws", account_id="a2")
        accounts = orch.list_accounts(platform="aws")
        record(
            "MCO-006", "list_accounts filters by platform",
            2, len(accounts),
            cause="2 aws accounts, 1 gcp",
            effect="2 returned for aws",
            lesson="Platform filter must work",
        )

    def test_list_accounts_enabled_filter(self) -> None:
        orch = _make_orch()
        _add_account(orch, account_id="a1")
        orch.register_account("aws", "a2", enabled=False)
        accounts = orch.list_accounts(enabled=True)
        record(
            "MCO-007", "list_accounts filters by enabled",
            1, len(accounts),
            cause="1 enabled, 1 disabled",
            effect="1 returned",
            lesson="Enabled filter must work",
        )

    def test_list_accounts_limit(self) -> None:
        orch = _make_orch()
        for i in range(20):
            orch.register_account("aws", f"acct-{i}")
        accounts = orch.list_accounts(limit=5)
        record(
            "MCO-008", "list_accounts respects limit",
            5, len(accounts),
            cause="20 accounts, limit=5",
            effect="5 returned",
            lesson="Limit must be respected",
        )

    def test_delete_account(self) -> None:
        orch = _make_orch()
        acct = _add_account(orch)
        ok = orch.delete_account(acct.id)
        record(
            "MCO-009", "delete_account returns True",
            True, ok,
            cause="valid account deleted",
            effect="True returned",
            lesson="Delete must succeed for existing accounts",
        )
        assert orch.get_account(acct.id) is None

    def test_delete_account_missing(self) -> None:
        orch = _make_orch()
        ok = orch.delete_account("nonexistent")
        record(
            "MCO-010", "delete_account returns False for missing",
            False, ok,
            cause="invalid ID",
            effect="False returned",
            lesson="Delete of missing account returns False",
        )

    def test_account_id_unique(self) -> None:
        orch = _make_orch()
        a1 = _add_account(orch, account_id="a1")
        a2 = _add_account(orch, account_id="a2")
        record(
            "MCO-011", "account IDs are unique",
            True, a1.id != a2.id,
            cause="two accounts registered",
            effect="different IDs",
            lesson="UUID generation must be unique",
        )

    def test_account_serialization(self) -> None:
        orch = _make_orch()
        acct = _add_account(orch)
        d = acct.to_dict()
        record(
            "MCO-012", "to_dict has all fields",
            True, "id" in d and "platform" in d and "account_id" in d,
            cause="to_dict called",
            effect="dict with all fields",
            lesson="Serialization must be complete",
        )

    def test_list_accounts_empty(self) -> None:
        orch = _make_orch()
        accounts = orch.list_accounts()
        record(
            "MCO-013", "empty list when no accounts",
            0, len(accounts),
            cause="no accounts registered",
            effect="empty list",
            lesson="Empty state must return empty list",
        )


class TestResourceManagement:
    """Managed resource registration and CRUD."""

    def test_register_resource_basic(self) -> None:
        orch = _make_orch()
        acct = _add_account(orch)
        res = orch.register_resource(acct.id, "web-server")
        record(
            "MCO-014", "register_resource returns ManagedResource",
            True, isinstance(res, ManagedResource),
            cause="register_resource called",
            effect="ManagedResource returned",
            lesson="Factory must return typed resource",
        )
        assert res.name == "web-server"

    def test_register_resource_inherits_platform(self) -> None:
        orch = _make_orch()
        acct = _add_account(orch, platform="gcp")
        res = orch.register_resource(acct.id, "gcp-vm")
        record(
            "MCO-015", "resource inherits account platform",
            "gcp", res.platform,
            cause="resource registered under gcp account",
            effect="platform is gcp",
            lesson="Platform must propagate from account",
        )

    def test_register_resource_enum_type(self) -> None:
        orch = _make_orch()
        acct = _add_account(orch)
        res = orch.register_resource(
            acct.id, "my-db", resource_type=ResourceType.database,
        )
        record(
            "MCO-016", "enum ResourceType coerced to string",
            "database", res.resource_type,
            cause="ResourceType enum passed",
            effect="stored as string value",
            lesson="Enum coercion for resource type",
        )

    def test_get_resource(self) -> None:
        orch = _make_orch()
        acct = _add_account(orch)
        res = orch.register_resource(acct.id, "vm-1")
        got = orch.get_resource(res.id)
        record(
            "MCO-017", "get_resource returns correct resource",
            res.id, got.id if got else None,
            cause="get by ID",
            effect="same resource returned",
            lesson="Lookup must return existing resources",
        )

    def test_get_resource_missing(self) -> None:
        orch = _make_orch()
        got = orch.get_resource("nonexistent")
        record(
            "MCO-018", "get_resource returns None for missing",
            True, got is None,
            cause="invalid ID",
            effect="None returned",
            lesson="Missing resources return None",
        )

    def test_list_resources_filter_platform(self) -> None:
        orch = _make_orch()
        a1 = _add_account(orch, platform="aws", account_id="a1")
        a2 = _add_account(orch, platform="gcp", account_id="g1")
        orch.register_resource(a1.id, "vm-1")
        orch.register_resource(a2.id, "vm-2")
        resources = orch.list_resources(platform="aws")
        record(
            "MCO-019", "list_resources filters by platform",
            1, len(resources),
            cause="1 aws, 1 gcp resource",
            effect="1 returned for aws",
            lesson="Platform filter must work",
        )

    def test_list_resources_filter_status(self) -> None:
        orch = _make_orch()
        acct = _add_account(orch)
        orch.register_resource(acct.id, "vm-1", status="running")
        orch.register_resource(acct.id, "vm-2", status="stopped")
        resources = orch.list_resources(status="running")
        record(
            "MCO-020", "list_resources filters by status",
            1, len(resources),
            cause="1 running, 1 stopped",
            effect="1 returned for running",
            lesson="Status filter must work",
        )

    def test_list_resources_filter_type(self) -> None:
        orch = _make_orch()
        acct = _add_account(orch)
        orch.register_resource(acct.id, "vm-1", resource_type="compute")
        orch.register_resource(acct.id, "db-1", resource_type="database")
        resources = orch.list_resources(resource_type="database")
        record(
            "MCO-021", "list_resources filters by resource_type",
            1, len(resources),
            cause="1 compute, 1 database",
            effect="1 returned for database",
            lesson="Type filter must work",
        )

    def test_list_resources_limit(self) -> None:
        orch = _make_orch()
        acct = _add_account(orch)
        for i in range(15):
            orch.register_resource(acct.id, f"vm-{i}")
        resources = orch.list_resources(limit=5)
        record(
            "MCO-022", "list_resources respects limit",
            5, len(resources),
            cause="15 resources, limit=5",
            effect="5 returned",
            lesson="Limit must be respected",
        )

    def test_update_resource_status(self) -> None:
        orch = _make_orch()
        acct = _add_account(orch)
        res = orch.register_resource(acct.id, "vm-1")
        updated = orch.update_resource_status(res.id, "stopped")
        record(
            "MCO-023", "update_resource_status changes status",
            "stopped", updated.status if updated else None,
            cause="status changed to stopped",
            effect="new status stored",
            lesson="Status updates must persist",
        )

    def test_update_resource_status_enum(self) -> None:
        orch = _make_orch()
        acct = _add_account(orch)
        res = orch.register_resource(acct.id, "vm-1")
        updated = orch.update_resource_status(res.id, DeploymentStatus.failed)
        record(
            "MCO-024", "update_resource_status with enum",
            "failed", updated.status if updated else None,
            cause="DeploymentStatus enum passed",
            effect="stored as string value",
            lesson="Enum coercion in updates",
        )

    def test_update_resource_status_missing(self) -> None:
        orch = _make_orch()
        result = orch.update_resource_status("missing", "stopped")
        record(
            "MCO-025", "update_resource_status None for missing",
            True, result is None,
            cause="invalid ID",
            effect="None returned",
            lesson="Missing resources cannot be updated",
        )

    def test_delete_resource(self) -> None:
        orch = _make_orch()
        acct = _add_account(orch)
        res = orch.register_resource(acct.id, "vm-1")
        ok = orch.delete_resource(res.id)
        record(
            "MCO-026", "delete_resource returns True",
            True, ok,
            cause="valid resource deleted",
            effect="True returned",
            lesson="Delete must succeed for existing resources",
        )
        assert orch.get_resource(res.id) is None

    def test_delete_resource_missing(self) -> None:
        orch = _make_orch()
        ok = orch.delete_resource("nonexistent")
        record(
            "MCO-027", "delete_resource returns False for missing",
            False, ok,
            cause="invalid ID",
            effect="False returned",
            lesson="Delete of missing resource returns False",
        )

    def test_resource_cost_nonnegative(self) -> None:
        orch = _make_orch()
        acct = _add_account(orch)
        res = orch.register_resource(acct.id, "vm-1", cost_per_hour=-5.0)
        record(
            "MCO-028", "negative cost clamped to 0",
            True, res.cost_per_hour >= 0.0,
            cause="negative cost passed",
            effect="clamped to non-negative",
            lesson="Costs cannot be negative",
        )

    def test_resource_serialization(self) -> None:
        orch = _make_orch()
        acct = _add_account(orch)
        res = orch.register_resource(acct.id, "vm-1")
        d = res.to_dict()
        record(
            "MCO-029", "resource to_dict has all fields",
            True, "id" in d and "name" in d and "platform" in d,
            cause="to_dict called",
            effect="dict with all fields",
            lesson="Serialization must be complete",
        )

    def test_resource_unknown_account(self) -> None:
        orch = _make_orch()
        res = orch.register_resource("no-such-account", "vm-orphan")
        record(
            "MCO-030", "resource for unknown account gets 'other' platform",
            "other", res.platform,
            cause="account_id not found",
            effect="platform defaults to other",
            lesson="Graceful fallback for missing account",
        )


class TestDeployments:
    """Deployment creation and management."""

    def test_create_deployment(self) -> None:
        orch = _make_orch()
        dep = orch.create_deployment("my-app", platforms=["aws", "gcp"])
        record(
            "MCO-031", "create_deployment returns Deployment",
            True, isinstance(dep, Deployment),
            cause="create_deployment called",
            effect="Deployment returned",
            lesson="Factory must return typed deployment",
        )
        assert dep.name == "my-app"
        assert dep.status == "pending"

    def test_deployment_platforms(self) -> None:
        orch = _make_orch()
        dep = orch.create_deployment("app", platforms=["aws", "azure"])
        record(
            "MCO-032", "deployment platforms stored",
            ["aws", "azure"], dep.platforms,
            cause="platforms list passed",
            effect="list persisted",
            lesson="Platforms must be stored",
        )

    def test_deployment_enum_platforms(self) -> None:
        orch = _make_orch()
        dep = orch.create_deployment(
            "app", platforms=[CloudPlatform.aws, CloudPlatform.gcp],
        )
        record(
            "MCO-033", "deployment enum platforms coerced",
            ["aws", "gcp"], dep.platforms,
            cause="CloudPlatform enums passed",
            effect="stored as string values",
            lesson="Enum coercion in platform list",
        )

    def test_get_deployment(self) -> None:
        orch = _make_orch()
        dep = orch.create_deployment("app")
        got = orch.get_deployment(dep.id)
        record(
            "MCO-034", "get_deployment returns correct deployment",
            dep.id, got.id if got else None,
            cause="get by ID",
            effect="same deployment returned",
            lesson="Lookup must work",
        )

    def test_get_deployment_missing(self) -> None:
        orch = _make_orch()
        got = orch.get_deployment("nonexistent")
        record(
            "MCO-035", "get_deployment returns None for missing",
            True, got is None,
            cause="invalid ID",
            effect="None returned",
            lesson="Missing deployments return None",
        )

    def test_list_deployments(self) -> None:
        orch = _make_orch()
        orch.create_deployment("app-1")
        orch.create_deployment("app-2")
        deps = orch.list_deployments()
        record(
            "MCO-036", "list_deployments returns all",
            2, len(deps),
            cause="2 deployments created",
            effect="2 returned",
            lesson="List must return all deployments",
        )

    def test_list_deployments_filter_status(self) -> None:
        orch = _make_orch()
        d1 = orch.create_deployment("app-1")
        d2 = orch.create_deployment("app-2")
        orch.update_deployment_status(d1.id, "running")
        deps = orch.list_deployments(status="running")
        record(
            "MCO-037", "list_deployments filters by status",
            1, len(deps),
            cause="1 running, 1 pending",
            effect="1 returned for running",
            lesson="Status filter must work",
        )

    def test_update_deployment_status(self) -> None:
        orch = _make_orch()
        dep = orch.create_deployment("app")
        updated = orch.update_deployment_status(dep.id, "running")
        record(
            "MCO-038", "update_deployment_status changes status",
            "running", updated.status if updated else None,
            cause="status changed to running",
            effect="new status stored",
            lesson="Status updates must persist",
        )

    def test_update_deployment_status_enum(self) -> None:
        orch = _make_orch()
        dep = orch.create_deployment("app")
        updated = orch.update_deployment_status(dep.id, DeploymentStatus.degraded)
        record(
            "MCO-039", "update_deployment with enum",
            "degraded", updated.status if updated else None,
            cause="DeploymentStatus enum passed",
            effect="stored as string",
            lesson="Enum coercion in deployment status",
        )

    def test_update_deployment_missing(self) -> None:
        orch = _make_orch()
        result = orch.update_deployment_status("missing", "running")
        record(
            "MCO-040", "update_deployment None for missing",
            True, result is None,
            cause="invalid ID",
            effect="None returned",
            lesson="Missing deployments cannot be updated",
        )

    def test_deployment_serialization(self) -> None:
        orch = _make_orch()
        dep = orch.create_deployment("app", platforms=["aws"])
        d = dep.to_dict()
        record(
            "MCO-041", "deployment to_dict has all fields",
            True, "id" in d and "name" in d and "platforms" in d,
            cause="to_dict called",
            effect="dict with all fields",
            lesson="Serialization must be complete",
        )

    def test_deployment_with_resources(self) -> None:
        orch = _make_orch()
        acct = _add_account(orch)
        r1 = orch.register_resource(acct.id, "vm-1")
        r2 = orch.register_resource(acct.id, "vm-2")
        dep = orch.create_deployment("app", resource_ids=[r1.id, r2.id])
        record(
            "MCO-042", "deployment stores resource_ids",
            2, len(dep.resource_ids),
            cause="2 resource IDs passed",
            effect="2 stored",
            lesson="Resource IDs must be stored",
        )

    def test_list_deployments_limit(self) -> None:
        orch = _make_orch()
        for i in range(10):
            orch.create_deployment(f"app-{i}")
        deps = orch.list_deployments(limit=3)
        record(
            "MCO-043", "list_deployments respects limit",
            3, len(deps),
            cause="10 deployments, limit=3",
            effect="3 returned",
            lesson="Limit must be respected",
        )


class TestOperations:
    """Orchestration operations."""

    def test_execute_operation(self) -> None:
        orch = _make_orch()
        dep = orch.create_deployment("app")
        op = orch.execute_operation(dep.id, "deploy", "aws", "us-east-1")
        record(
            "MCO-044", "execute_operation returns CloudOperation",
            True, isinstance(op, CloudOperation),
            cause="execute_operation called",
            effect="CloudOperation returned",
            lesson="Factory must return typed operation",
        )
        assert op.status == "completed"

    def test_execute_operation_enum_type(self) -> None:
        orch = _make_orch()
        dep = orch.create_deployment("app")
        op = orch.execute_operation(dep.id, OperationType.scale)
        record(
            "MCO-045", "enum OperationType coerced",
            "scale", op.operation_type,
            cause="OperationType enum passed",
            effect="stored as string",
            lesson="Enum coercion must work",
        )

    def test_execute_operation_result(self) -> None:
        orch = _make_orch()
        dep = orch.create_deployment("app")
        op = orch.execute_operation(dep.id, "migrate", "gcp")
        record(
            "MCO-046", "operation result has outcome",
            "completed", op.result.get("outcome"),
            cause="operation executed",
            effect="result dict populated",
            lesson="Operations must produce results",
        )

    def test_list_operations(self) -> None:
        orch = _make_orch()
        dep = orch.create_deployment("app")
        orch.execute_operation(dep.id, "deploy", "aws")
        orch.execute_operation(dep.id, "scale", "aws")
        ops = orch.list_operations()
        record(
            "MCO-047", "list_operations returns all",
            2, len(ops),
            cause="2 operations executed",
            effect="2 returned",
            lesson="List must return all operations",
        )

    def test_list_operations_filter_deployment(self) -> None:
        orch = _make_orch()
        d1 = orch.create_deployment("app-1")
        d2 = orch.create_deployment("app-2")
        orch.execute_operation(d1.id, "deploy", "aws")
        orch.execute_operation(d2.id, "deploy", "gcp")
        ops = orch.list_operations(deployment_id=d1.id)
        record(
            "MCO-048", "list_operations filters by deployment_id",
            1, len(ops),
            cause="1 op per deployment",
            effect="1 returned for d1",
            lesson="Deployment filter must work",
        )

    def test_list_operations_filter_platform(self) -> None:
        orch = _make_orch()
        dep = orch.create_deployment("app")
        orch.execute_operation(dep.id, "deploy", "aws")
        orch.execute_operation(dep.id, "deploy", "gcp")
        ops = orch.list_operations(platform="aws")
        record(
            "MCO-049", "list_operations filters by platform",
            1, len(ops),
            cause="1 aws, 1 gcp op",
            effect="1 returned for aws",
            lesson="Platform filter must work",
        )

    def test_list_operations_filter_type(self) -> None:
        orch = _make_orch()
        dep = orch.create_deployment("app")
        orch.execute_operation(dep.id, "deploy", "aws")
        orch.execute_operation(dep.id, "scale", "aws")
        ops = orch.list_operations(operation_type="deploy")
        record(
            "MCO-050", "list_operations filters by operation_type",
            1, len(ops),
            cause="1 deploy, 1 scale",
            effect="1 returned for deploy",
            lesson="Operation type filter must work",
        )

    def test_list_operations_limit(self) -> None:
        orch = _make_orch()
        dep = orch.create_deployment("app")
        for _ in range(10):
            orch.execute_operation(dep.id, "deploy", "aws")
        ops = orch.list_operations(limit=3)
        record(
            "MCO-051", "list_operations respects limit",
            3, len(ops),
            cause="10 ops, limit=3",
            effect="3 returned",
            lesson="Limit must be respected",
        )

    def test_operation_serialization(self) -> None:
        orch = _make_orch()
        dep = orch.create_deployment("app")
        op = orch.execute_operation(dep.id, "deploy", "aws")
        d = op.to_dict()
        record(
            "MCO-052", "operation to_dict has all fields",
            True, "id" in d and "deployment_id" in d and "result" in d,
            cause="to_dict called",
            effect="dict with all fields",
            lesson="Serialization must be complete",
        )

    def test_operation_completed_at_set(self) -> None:
        orch = _make_orch()
        dep = orch.create_deployment("app")
        op = orch.execute_operation(dep.id, "deploy", "aws")
        record(
            "MCO-053", "completed_at is set after execution",
            True, len(op.completed_at) > 0,
            cause="operation executed",
            effect="completed_at timestamp set",
            lesson="Completion time must be recorded",
        )

    def test_operation_with_parameters(self) -> None:
        orch = _make_orch()
        dep = orch.create_deployment("app")
        op = orch.execute_operation(
            dep.id, "scale", "aws",
            parameters={"replicas": 5},
        )
        record(
            "MCO-054", "operation parameters stored",
            5, op.parameters.get("replicas"),
            cause="parameters dict passed",
            effect="parameters persisted",
            lesson="Parameters passthrough must work",
        )


class TestHealthChecks:
    """Health check probes."""

    def test_run_health_check(self) -> None:
        orch = _make_orch()
        acct = _add_account(orch)
        hc = orch.run_health_check(acct.id)
        record(
            "MCO-055", "run_health_check returns HealthCheck",
            True, isinstance(hc, HealthCheck),
            cause="run_health_check called",
            effect="HealthCheck returned",
            lesson="Health check must return typed result",
        )
        assert hc.platform == "aws"

    def test_health_check_unknown_account(self) -> None:
        orch = _make_orch()
        hc = orch.run_health_check("nonexistent")
        record(
            "MCO-056", "health check for missing account returns unavailable",
            "unavailable", hc.status,
            cause="account not found",
            effect="unavailable status",
            lesson="Missing account = unavailable",
        )

    def test_health_check_latency(self) -> None:
        orch = _make_orch()
        acct = _add_account(orch)
        hc = orch.run_health_check(acct.id)
        record(
            "MCO-057", "health check has positive latency",
            True, hc.latency_ms > 0,
            cause="health check executed",
            effect="latency measured",
            lesson="Latency must be positive",
        )

    def test_health_check_status_valid(self) -> None:
        orch = _make_orch()
        acct = _add_account(orch)
        hc = orch.run_health_check(acct.id)
        record(
            "MCO-058", "health check status is valid",
            True, hc.status in ("available", "degraded"),
            cause="health check executed",
            effect="valid status returned",
            lesson="Status must be from expected set",
        )

    def test_list_health_checks(self) -> None:
        orch = _make_orch()
        acct = _add_account(orch)
        orch.run_health_check(acct.id)
        orch.run_health_check(acct.id)
        checks = orch.list_health_checks()
        record(
            "MCO-059", "list_health_checks returns all",
            2, len(checks),
            cause="2 checks performed",
            effect="2 returned",
            lesson="List must return all checks",
        )

    def test_list_health_checks_filter(self) -> None:
        orch = _make_orch()
        a1 = _add_account(orch, account_id="a1")
        a2 = _add_account(orch, account_id="a2")
        orch.run_health_check(a1.id)
        orch.run_health_check(a2.id)
        checks = orch.list_health_checks(account_id=a1.id)
        record(
            "MCO-060", "list_health_checks filters by account_id",
            1, len(checks),
            cause="1 check per account",
            effect="1 returned for a1",
            lesson="Account filter must work",
        )

    def test_health_check_serialization(self) -> None:
        orch = _make_orch()
        acct = _add_account(orch)
        hc = orch.run_health_check(acct.id)
        d = hc.to_dict()
        record(
            "MCO-061", "health check to_dict has all fields",
            True, "id" in d and "status" in d and "latency_ms" in d,
            cause="to_dict called",
            effect="dict with all fields",
            lesson="Serialization must be complete",
        )


class TestCostAllocation:
    """Cost recording and aggregation."""

    def test_record_cost(self) -> None:
        orch = _make_orch()
        dep = orch.create_deployment("app")
        cost = orch.record_cost(dep.id, "aws", 150.0, "2026-03")
        record(
            "MCO-062", "record_cost returns CostAllocation",
            True, isinstance(cost, CostAllocation),
            cause="record_cost called",
            effect="CostAllocation returned",
            lesson="Cost factory must return typed object",
        )
        assert cost.amount == 150.0

    def test_record_cost_enum_platform(self) -> None:
        orch = _make_orch()
        dep = orch.create_deployment("app")
        cost = orch.record_cost(dep.id, CloudPlatform.azure, 200.0, "2026-03")
        record(
            "MCO-063", "cost enum platform coerced",
            "azure", cost.platform,
            cause="CloudPlatform enum passed",
            effect="stored as string",
            lesson="Enum coercion for cost platform",
        )

    def test_cost_summary_empty(self) -> None:
        orch = _make_orch()
        summary = orch.get_cost_summary()
        record(
            "MCO-064", "cost summary empty state",
            0.0, summary["total"],
            cause="no costs recorded",
            effect="total is 0",
            lesson="Empty summary must be zero",
        )

    def test_cost_summary_aggregation(self) -> None:
        orch = _make_orch()
        dep = orch.create_deployment("app")
        orch.record_cost(dep.id, "aws", 100.0, "2026-03")
        orch.record_cost(dep.id, "gcp", 200.0, "2026-03")
        orch.record_cost(dep.id, "aws", 50.0, "2026-03")
        summary = orch.get_cost_summary()
        record(
            "MCO-065", "cost summary aggregates correctly",
            350.0, summary["total"],
            cause="100+200+50 = 350",
            effect="total is 350",
            lesson="Aggregation must be accurate",
        )
        assert summary["by_platform"]["aws"] == 150.0
        assert summary["by_platform"]["gcp"] == 200.0

    def test_list_costs(self) -> None:
        orch = _make_orch()
        dep = orch.create_deployment("app")
        orch.record_cost(dep.id, "aws", 100.0, "2026-01")
        orch.record_cost(dep.id, "aws", 200.0, "2026-02")
        costs = orch.list_costs()
        record(
            "MCO-066", "list_costs returns all",
            2, len(costs),
            cause="2 costs recorded",
            effect="2 returned",
            lesson="List must return all costs",
        )

    def test_list_costs_filter_deployment(self) -> None:
        orch = _make_orch()
        d1 = orch.create_deployment("app-1")
        d2 = orch.create_deployment("app-2")
        orch.record_cost(d1.id, "aws", 100.0, "2026-03")
        orch.record_cost(d2.id, "aws", 200.0, "2026-03")
        costs = orch.list_costs(deployment_id=d1.id)
        record(
            "MCO-067", "list_costs filters by deployment_id",
            1, len(costs),
            cause="1 cost per deployment",
            effect="1 returned for d1",
            lesson="Deployment filter must work",
        )

    def test_list_costs_filter_platform(self) -> None:
        orch = _make_orch()
        dep = orch.create_deployment("app")
        orch.record_cost(dep.id, "aws", 100.0, "2026-03")
        orch.record_cost(dep.id, "gcp", 200.0, "2026-03")
        costs = orch.list_costs(platform="gcp")
        record(
            "MCO-068", "list_costs filters by platform",
            1, len(costs),
            cause="1 aws, 1 gcp cost",
            effect="1 returned for gcp",
            lesson="Platform filter must work",
        )

    def test_list_costs_limit(self) -> None:
        orch = _make_orch()
        dep = orch.create_deployment("app")
        for i in range(10):
            orch.record_cost(dep.id, "aws", float(i), f"2026-{i+1:02d}")
        costs = orch.list_costs(limit=3)
        record(
            "MCO-069", "list_costs respects limit",
            3, len(costs),
            cause="10 costs, limit=3",
            effect="3 returned",
            lesson="Limit must be respected",
        )

    def test_cost_serialization(self) -> None:
        orch = _make_orch()
        dep = orch.create_deployment("app")
        cost = orch.record_cost(dep.id, "aws", 100.0, "2026-03")
        d = cost.to_dict()
        record(
            "MCO-070", "cost to_dict has all fields",
            True, "id" in d and "amount" in d and "platform" in d,
            cause="to_dict called",
            effect="dict with all fields",
            lesson="Serialization must be complete",
        )

    def test_cost_rounding(self) -> None:
        orch = _make_orch()
        dep = orch.create_deployment("app")
        cost = orch.record_cost(dep.id, "aws", 99.999, "2026-03")
        record(
            "MCO-071", "cost amount rounded to 2 decimals",
            100.0, cost.amount,
            cause="99.999 recorded",
            effect="rounded to 100.0",
            lesson="Costs must be rounded",
        )


class TestExportAndClear:
    """State export and clear."""

    def test_export_state(self) -> None:
        orch = _make_orch()
        acct = _add_account(orch)
        orch.register_resource(acct.id, "vm-1")
        dep = orch.create_deployment("app")
        state = orch.export_state()
        record(
            "MCO-072", "export_state includes all sections",
            True, "accounts" in state and "resources" in state
            and "deployments" in state,
            cause="export_state called",
            effect="full state dict returned",
            lesson="Export must include all sections",
        )

    def test_export_has_timestamp(self) -> None:
        orch = _make_orch()
        state = orch.export_state()
        record(
            "MCO-073", "export_state has exported_at timestamp",
            True, "exported_at" in state,
            cause="export_state called",
            effect="timestamp present",
            lesson="Exports must be timestamped",
        )

    def test_clear(self) -> None:
        orch = _make_orch()
        acct = _add_account(orch)
        orch.register_resource(acct.id, "vm-1")
        orch.create_deployment("app")
        orch.clear()
        record(
            "MCO-074", "clear removes all accounts",
            0, len(orch.list_accounts()),
            cause="clear called",
            effect="no accounts remain",
            lesson="Clear must remove everything",
        )
        assert len(orch.list_resources()) == 0
        assert len(orch.list_deployments()) == 0


class TestWingmanAndSandbox:
    """Wingman pair validation and Causality Sandbox gating."""

    def test_wingman_pass(self) -> None:
        result = validate_wingman_pair(["a", "b"], ["a", "b"])
        record(
            "MCO-075", "wingman pair passes when equal",
            True, result["passed"],
            cause="matching lists",
            effect="passed=True",
            lesson="Equal pairs must pass",
        )

    def test_wingman_mismatch(self) -> None:
        result = validate_wingman_pair(["a", "b"], ["a", "x"])
        record(
            "MCO-076", "wingman pair fails on mismatch",
            False, result["passed"],
            cause="mismatched element",
            effect="passed=False",
            lesson="Mismatches must fail",
        )

    def test_wingman_empty_storyline(self) -> None:
        result = validate_wingman_pair([], ["a"])
        record(
            "MCO-077", "wingman fails on empty storyline",
            False, result["passed"],
            cause="empty storyline",
            effect="passed=False",
            lesson="Empty storyline must fail",
        )

    def test_wingman_empty_actuals(self) -> None:
        result = validate_wingman_pair(["a"], [])
        record(
            "MCO-078", "wingman fails on empty actuals",
            False, result["passed"],
            cause="empty actuals",
            effect="passed=False",
            lesson="Empty actuals must fail",
        )

    def test_wingman_length_mismatch(self) -> None:
        result = validate_wingman_pair(["a", "b"], ["a"])
        record(
            "MCO-079", "wingman fails on length mismatch",
            False, result["passed"],
            cause="different lengths",
            effect="passed=False",
            lesson="Length mismatch must fail",
        )

    def test_wingman_pair_count(self) -> None:
        result = validate_wingman_pair(["a", "b", "c"], ["a", "b", "c"])
        record(
            "MCO-080", "wingman returns pair_count",
            3, result.get("pair_count"),
            cause="3-element matching lists",
            effect="pair_count=3",
            lesson="Pair count must be reported",
        )

    def test_sandbox_pass(self) -> None:
        result = gate_mco_in_sandbox({"platform": "aws"})
        record(
            "MCO-081", "sandbox gate passes with platform",
            True, result["passed"],
            cause="platform provided",
            effect="passed=True",
            lesson="Valid context must pass",
        )

    def test_sandbox_missing_key(self) -> None:
        result = gate_mco_in_sandbox({})
        record(
            "MCO-082", "sandbox gate fails without platform",
            False, result["passed"],
            cause="platform missing",
            effect="passed=False",
            lesson="Missing required keys must fail",
        )

    def test_sandbox_empty_platform(self) -> None:
        result = gate_mco_in_sandbox({"platform": ""})
        record(
            "MCO-083", "sandbox gate fails with empty platform",
            False, result["passed"],
            cause="empty platform string",
            effect="passed=False",
            lesson="Empty values must fail validation",
        )


class TestConcurrency:
    """Thread safety verification."""

    def test_concurrent_account_registration(self) -> None:
        orch = _make_orch()
        errors: List[str] = []

        def _register(idx: int) -> None:
            try:
                orch.register_account("aws", f"acct-{idx}")
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=_register, args=(i,))
                   for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        record(
            "MCO-084", "concurrent registration no errors",
            0, len(errors),
            cause="50 concurrent registrations",
            effect="no exceptions",
            lesson="Thread safety must hold under contention",
        )
        assert len(orch.list_accounts(limit=500)) == 50

    def test_concurrent_resource_ops(self) -> None:
        orch = _make_orch()
        acct = _add_account(orch)
        errors: List[str] = []

        def _op(idx: int) -> None:
            try:
                orch.register_resource(acct.id, f"vm-{idx}")
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=_op, args=(i,))
                   for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        record(
            "MCO-085", "concurrent resource ops no errors",
            0, len(errors),
            cause="50 concurrent resource registrations",
            effect="no exceptions",
            lesson="Thread safety for resources",
        )

    def test_concurrent_deployments_and_ops(self) -> None:
        orch = _make_orch()
        dep = orch.create_deployment("app")
        errors: List[str] = []

        def _op(idx: int) -> None:
            try:
                orch.execute_operation(dep.id, "deploy", "aws")
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=_op, args=(i,))
                   for i in range(30)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        record(
            "MCO-086", "concurrent operations no errors",
            0, len(errors),
            cause="30 concurrent operations",
            effect="no exceptions",
            lesson="Thread safety for operations",
        )


class TestFlaskAPI:
    """Flask Blueprint endpoint tests."""

    def _app(self):
        """Create a test Flask app with the MCO blueprint."""
        from flask import Flask
        orch = MultiCloudOrchestrator(max_accounts=100, max_resources=100)
        app = Flask(__name__)
        app.register_blueprint(create_multi_cloud_api(orch))
        app.config["TESTING"] = True
        return app, orch

    def test_api_register_account(self) -> None:
        app, _ = self._app()
        with app.test_client() as c:
            rv = c.post("/api/mco/accounts", json={
                "platform": "aws", "account_id": "111222",
            })
        record(
            "MCO-087", "POST /mco/accounts returns 201",
            201, rv.status_code,
            cause="valid payload",
            effect="account created",
            lesson="Create endpoint must return 201",
        )

    def test_api_register_account_missing_field(self) -> None:
        app, _ = self._app()
        with app.test_client() as c:
            rv = c.post("/api/mco/accounts", json={"platform": "aws"})
        record(
            "MCO-088", "POST /mco/accounts missing field returns 400",
            400, rv.status_code,
            cause="account_id missing",
            effect="400 error",
            lesson="Missing fields must return 400",
        )

    def test_api_list_accounts(self) -> None:
        app, orch = self._app()
        orch.register_account("aws", "a1")
        with app.test_client() as c:
            rv = c.get("/api/mco/accounts")
        data = rv.get_json()
        record(
            "MCO-089", "GET /mco/accounts returns list",
            True, isinstance(data, list) and len(data) == 1,
            cause="1 account exists",
            effect="list of 1 returned",
            lesson="List endpoint must return array",
        )

    def test_api_get_account(self) -> None:
        app, orch = self._app()
        acct = orch.register_account("aws", "a1")
        with app.test_client() as c:
            rv = c.get(f"/api/mco/accounts/{acct.id}")
        record(
            "MCO-090", "GET /mco/accounts/<id> returns 200",
            200, rv.status_code,
            cause="valid account ID",
            effect="account returned",
            lesson="Get endpoint must return 200",
        )

    def test_api_get_account_not_found(self) -> None:
        app, _ = self._app()
        with app.test_client() as c:
            rv = c.get("/api/mco/accounts/nonexistent")
        record(
            "MCO-091", "GET /mco/accounts/<id> returns 404",
            404, rv.status_code,
            cause="invalid ID",
            effect="404 returned",
            lesson="Missing resources must return 404",
        )

    def test_api_delete_account(self) -> None:
        app, orch = self._app()
        acct = orch.register_account("aws", "a1")
        with app.test_client() as c:
            rv = c.delete(f"/api/mco/accounts/{acct.id}")
        record(
            "MCO-092", "DELETE /mco/accounts/<id> returns 200",
            200, rv.status_code,
            cause="valid account deleted",
            effect="200 returned",
            lesson="Delete endpoint must return 200",
        )

    def test_api_register_resource(self) -> None:
        app, orch = self._app()
        acct = orch.register_account("aws", "a1")
        with app.test_client() as c:
            rv = c.post("/api/mco/resources", json={
                "account_id": acct.id, "name": "vm-1",
            })
        record(
            "MCO-093", "POST /mco/resources returns 201",
            201, rv.status_code,
            cause="valid resource payload",
            effect="resource created",
            lesson="Resource creation must return 201",
        )

    def test_api_create_deployment(self) -> None:
        app, _ = self._app()
        with app.test_client() as c:
            rv = c.post("/api/mco/deployments", json={
                "name": "my-app", "platforms": ["aws", "gcp"],
            })
        record(
            "MCO-094", "POST /mco/deployments returns 201",
            201, rv.status_code,
            cause="valid deployment payload",
            effect="deployment created",
            lesson="Deployment creation must return 201",
        )

    def test_api_execute_operation(self) -> None:
        app, orch = self._app()
        dep = orch.create_deployment("app")
        with app.test_client() as c:
            rv = c.post("/api/mco/operations", json={
                "deployment_id": dep.id, "operation_type": "deploy",
            })
        record(
            "MCO-095", "POST /mco/operations returns 201",
            201, rv.status_code,
            cause="valid operation payload",
            effect="operation executed",
            lesson="Operation execution must return 201",
        )

    def test_api_health_check(self) -> None:
        app, orch = self._app()
        acct = orch.register_account("aws", "a1")
        with app.test_client() as c:
            rv = c.post(f"/api/mco/health/{acct.id}")
        record(
            "MCO-096", "POST /mco/health/<id> returns 200",
            200, rv.status_code,
            cause="valid account for health check",
            effect="health check performed",
            lesson="Health check must return 200",
        )

    def test_api_record_cost(self) -> None:
        app, orch = self._app()
        dep = orch.create_deployment("app")
        with app.test_client() as c:
            rv = c.post("/api/mco/costs", json={
                "deployment_id": dep.id, "platform": "aws",
                "amount": 150.0, "period": "2026-03",
            })
        record(
            "MCO-097", "POST /mco/costs returns 201",
            201, rv.status_code,
            cause="valid cost payload",
            effect="cost recorded",
            lesson="Cost recording must return 201",
        )

    def test_api_cost_summary(self) -> None:
        app, orch = self._app()
        dep = orch.create_deployment("app")
        orch.record_cost(dep.id, "aws", 100.0, "2026-03")
        with app.test_client() as c:
            rv = c.get("/api/mco/costs/summary")
        data = rv.get_json()
        record(
            "MCO-098", "GET /mco/costs/summary returns total",
            100.0, data.get("total"),
            cause="100 cost recorded",
            effect="summary shows 100",
            lesson="Summary must aggregate correctly",
        )

    def test_api_export(self) -> None:
        app, _ = self._app()
        with app.test_client() as c:
            rv = c.post("/api/mco/export")
        data = rv.get_json()
        record(
            "MCO-099", "POST /mco/export returns state",
            True, "accounts" in data and "exported_at" in data,
            cause="export endpoint called",
            effect="full state returned",
            lesson="Export must return complete state",
        )

    def test_api_module_health(self) -> None:
        app, _ = self._app()
        with app.test_client() as c:
            rv = c.get("/api/mco/health/status")
        data = rv.get_json()
        record(
            "MCO-100", "GET /mco/health/status returns healthy",
            "healthy", data.get("status"),
            cause="module health endpoint called",
            effect="healthy status returned",
            lesson="Module health must report status",
        )


class TestBoundaryConditions:
    """Edge cases and boundary values."""

    def test_max_accounts_eviction(self) -> None:
        orch = MultiCloudOrchestrator(max_accounts=3, max_resources=100)
        orch.register_account("aws", "a1")
        orch.register_account("aws", "a2")
        orch.register_account("aws", "a3")
        orch.register_account("aws", "a4")  # should evict oldest
        accounts = orch.list_accounts(limit=500)
        record(
            "MCO-101", "max_accounts evicts oldest",
            3, len(accounts),
            cause="4 accounts, max=3",
            effect="oldest evicted, 3 remain",
            lesson="Capacity limits must be enforced",
        )

    def test_max_resources_eviction(self) -> None:
        orch = MultiCloudOrchestrator(max_accounts=100, max_resources=3)
        acct = orch.register_account("aws", "a1")
        orch.register_resource(acct.id, "vm-1")
        orch.register_resource(acct.id, "vm-2")
        orch.register_resource(acct.id, "vm-3")
        orch.register_resource(acct.id, "vm-4")  # should evict oldest
        resources = orch.list_resources(limit=500)
        record(
            "MCO-102", "max_resources evicts oldest",
            3, len(resources),
            cause="4 resources, max=3",
            effect="oldest evicted, 3 remain",
            lesson="Resource capacity limits must be enforced",
        )

    def test_empty_deployment_regions(self) -> None:
        orch = _make_orch()
        dep = orch.create_deployment("app", regions=[])
        record(
            "MCO-103", "deployment with empty regions list",
            [], dep.regions,
            cause="empty regions passed",
            effect="empty list stored",
            lesson="Empty lists must be handled",
        )

    def test_zero_cost_per_hour(self) -> None:
        orch = _make_orch()
        acct = _add_account(orch)
        res = orch.register_resource(acct.id, "free-tier", cost_per_hour=0.0)
        record(
            "MCO-104", "zero cost_per_hour accepted",
            0.0, res.cost_per_hour,
            cause="cost_per_hour=0",
            effect="stored as 0.0",
            lesson="Free resources must be supported",
        )

    def test_multiple_platforms_cost_summary(self) -> None:
        orch = _make_orch()
        dep = orch.create_deployment("app")
        orch.record_cost(dep.id, "aws", 100.0, "2026-03")
        orch.record_cost(dep.id, "gcp", 200.0, "2026-03")
        orch.record_cost(dep.id, "azure", 300.0, "2026-03")
        summary = orch.get_cost_summary()
        record(
            "MCO-105", "cost summary with 3 platforms",
            3, len(summary["by_platform"]),
            cause="costs in 3 platforms",
            effect="3 platforms in summary",
            lesson="Multi-platform aggregation must work",
        )
        assert summary["total"] == 600.0
