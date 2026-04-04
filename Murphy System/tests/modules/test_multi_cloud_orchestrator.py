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

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))

from multi_cloud_orchestrator import (  # noqa: E402
    CloudDeployment,
    CloudProvider,
    CostRecord,
    DeploymentStatus,
    FailoverRule,
    FailoverStrategy,
    HealthState,
    MultiCloudOrchestrator,
    ProviderConfig,
    SyncTask,
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


def _make_orchestrator() -> MultiCloudOrchestrator:
    return MultiCloudOrchestrator(max_providers=500, max_deployments=500)


def _add_provider(
    orch: MultiCloudOrchestrator,
    name: str = "my-aws",
    provider: str = "aws",
    region: str = "us-east-1",
    enabled: bool = True,
) -> ProviderConfig:
    return orch.register_provider(
        name=name, provider=provider, region=region, enabled=enabled,
    )


def _add_deployment(
    orch: MultiCloudOrchestrator,
    name: str = "web-app",
    provider: str = "aws",
    region: str = "us-east-1",
) -> CloudDeployment:
    return orch.create_deployment(name=name, provider=provider, region=region)


# ==========================================================================
# Tests
# ==========================================================================


class TestProviderManagement:
    """Provider registration, retrieval, update, deletion."""

    def test_register_provider(self) -> None:
        orch = _make_orchestrator()
        cfg = _add_provider(orch)
        record(
            "MCO-001", "register_provider returns ProviderConfig",
            True, isinstance(cfg, ProviderConfig),
            cause="register_provider called",
            effect="ProviderConfig returned",
            lesson="Factory must return typed config",
        )
        assert cfg.name == "my-aws"

    def test_register_provider_defaults(self) -> None:
        orch = _make_orchestrator()
        cfg = _add_provider(orch)
        record(
            "MCO-002", "provider enabled by default",
            True, cfg.enabled,
            cause="no enabled specified",
            effect="defaults to True",
            lesson="New providers start enabled",
        )

    def test_register_provider_enum(self) -> None:
        orch = _make_orchestrator()
        cfg = orch.register_provider(
            "gcp-prod", CloudProvider.gcp, "us-central1",
        )
        record(
            "MCO-003", "enum CloudProvider coerced to string",
            "gcp", cfg.provider,
            cause="CloudProvider enum passed",
            effect="stored as string",
            lesson="Enum coercion must work",
        )

    def test_get_provider(self) -> None:
        orch = _make_orchestrator()
        cfg = _add_provider(orch)
        got = orch.get_provider(cfg.id)
        record(
            "MCO-004", "get_provider returns correct provider",
            cfg.id, got.id if got else None,
            cause="get by ID",
            effect="same provider returned",
            lesson="Lookup must work",
        )

    def test_get_provider_missing(self) -> None:
        orch = _make_orchestrator()
        got = orch.get_provider("nonexistent")
        record(
            "MCO-005", "get_provider returns None for missing",
            True, got is None,
            cause="invalid ID",
            effect="None returned",
            lesson="Missing providers return None",
        )

    def test_list_providers(self) -> None:
        orch = _make_orchestrator()
        _add_provider(orch, "aws-1", provider="aws")
        _add_provider(orch, "gcp-1", provider="gcp")
        _add_provider(orch, "aws-2", provider="aws")
        providers = orch.list_providers(provider="aws")
        record(
            "MCO-006", "list_providers filters by provider type",
            2, len(providers),
            cause="2 aws providers, 1 gcp",
            effect="2 returned for aws",
            lesson="Provider filter must work",
        )

    def test_list_providers_enabled(self) -> None:
        orch = _make_orchestrator()
        _add_provider(orch, "p1", enabled=True)
        _add_provider(orch, "p2", enabled=False)
        providers = orch.list_providers(enabled=True)
        record(
            "MCO-007", "list_providers filters by enabled",
            1, len(providers),
            cause="1 enabled provider",
            effect="1 returned",
            lesson="Enabled filter must work",
        )

    def test_list_providers_limit(self) -> None:
        orch = _make_orchestrator()
        for i in range(20):
            _add_provider(orch, f"p{i}")
        providers = orch.list_providers(limit=5)
        record(
            "MCO-008", "list_providers respects limit",
            5, len(providers),
            cause="20 providers, limit=5",
            effect="5 returned",
            lesson="Limit must be respected",
        )

    def test_update_provider_enabled(self) -> None:
        orch = _make_orchestrator()
        cfg = _add_provider(orch)
        updated = orch.update_provider(cfg.id, enabled=False)
        record(
            "MCO-009", "update_provider changes enabled",
            False, updated.enabled if updated else None,
            cause="enabled changed to False",
            effect="enabled updated",
            lesson="Enabled updates must persist",
        )

    def test_update_provider_region(self) -> None:
        orch = _make_orchestrator()
        cfg = _add_provider(orch)
        updated = orch.update_provider(cfg.id, region="eu-west-1")
        record(
            "MCO-010", "update_provider changes region",
            "eu-west-1", updated.region if updated else None,
            cause="region changed",
            effect="region updated",
            lesson="Region updates must persist",
        )

    def test_update_provider_missing(self) -> None:
        orch = _make_orchestrator()
        result = orch.update_provider("missing")
        record(
            "MCO-011", "update_provider returns None for missing",
            True, result is None,
            cause="invalid ID",
            effect="None returned",
            lesson="Missing providers cannot be updated",
        )

    def test_remove_provider(self) -> None:
        orch = _make_orchestrator()
        cfg = _add_provider(orch)
        ok = orch.remove_provider(cfg.id)
        record(
            "MCO-012", "remove_provider returns True",
            True, ok,
            cause="valid provider removed",
            effect="True returned",
            lesson="Remove must succeed for existing providers",
        )
        assert orch.get_provider(cfg.id) is None

    def test_remove_provider_missing(self) -> None:
        orch = _make_orchestrator()
        ok = orch.remove_provider("nonexistent")
        record(
            "MCO-013", "remove_provider returns False for missing",
            False, ok,
            cause="invalid ID",
            effect="False returned",
            lesson="Remove of missing returns False",
        )

    def test_provider_id_unique(self) -> None:
        orch = _make_orchestrator()
        p1 = _add_provider(orch, "p1")
        p2 = _add_provider(orch, "p2")
        record(
            "MCO-014", "provider IDs are unique",
            True, p1.id != p2.id,
            cause="two providers created",
            effect="different IDs",
            lesson="UUID generation must be unique",
        )

    def test_provider_serialization(self) -> None:
        orch = _make_orchestrator()
        cfg = _add_provider(orch)
        d = cfg.to_dict()
        record(
            "MCO-015", "to_dict has all fields",
            True, "id" in d and "name" in d and "provider" in d,
            cause="to_dict called",
            effect="dict with all fields",
            lesson="Serialization must be complete",
        )

    def test_provider_tags(self) -> None:
        orch = _make_orchestrator()
        cfg = orch.register_provider(
            "tagged", "aws", "us-east-1", tags={"env": "prod"},
        )
        record(
            "MCO-016", "provider stores tags",
            {"env": "prod"}, cfg.tags,
            cause="tags passed at creation",
            effect="tags stored",
            lesson="Tags must be preserved",
        )

    def test_update_provider_priority(self) -> None:
        orch = _make_orchestrator()
        cfg = _add_provider(orch)
        updated = orch.update_provider(cfg.id, priority=10)
        record(
            "MCO-017", "update_provider changes priority",
            10, updated.priority if updated else None,
            cause="priority changed to 10",
            effect="priority updated",
            lesson="Priority updates must persist",
        )

    def test_update_provider_endpoint(self) -> None:
        orch = _make_orchestrator()
        cfg = _add_provider(orch)
        updated = orch.update_provider(cfg.id, endpoint="https://custom.api")
        record(
            "MCO-018", "update_provider changes endpoint",
            "https://custom.api", updated.endpoint if updated else None,
            cause="endpoint changed",
            effect="endpoint updated",
            lesson="Endpoint updates must persist",
        )


class TestDeploymentManagement:
    """Deployment creation, retrieval, status update, deletion."""

    def test_create_deployment(self) -> None:
        orch = _make_orchestrator()
        dep = _add_deployment(orch)
        record(
            "MCO-019", "create_deployment returns CloudDeployment",
            True, isinstance(dep, CloudDeployment),
            cause="create_deployment called",
            effect="CloudDeployment returned",
            lesson="Factory must return typed deployment",
        )
        assert dep.name == "web-app"

    def test_deployment_defaults(self) -> None:
        orch = _make_orchestrator()
        dep = _add_deployment(orch)
        record(
            "MCO-020", "deployment has pending status by default",
            "pending", dep.status,
            cause="no status specified",
            effect="defaults to pending",
            lesson="New deployments start pending",
        )

    def test_deployment_enum_provider(self) -> None:
        orch = _make_orchestrator()
        dep = orch.create_deployment(
            "api-svc", CloudProvider.azure, "eastus",
        )
        record(
            "MCO-021", "enum CloudProvider coerced to string on deployment",
            "azure", dep.provider,
            cause="CloudProvider.azure passed",
            effect="stored as string",
            lesson="Enum coercion in deployments must work",
        )

    def test_get_deployment(self) -> None:
        orch = _make_orchestrator()
        dep = _add_deployment(orch)
        got = orch.get_deployment(dep.id)
        record(
            "MCO-022", "get_deployment returns correct deployment",
            dep.id, got.id if got else None,
            cause="get by ID",
            effect="same deployment returned",
            lesson="Deployment lookup must work",
        )

    def test_get_deployment_missing(self) -> None:
        orch = _make_orchestrator()
        got = orch.get_deployment("nonexistent")
        record(
            "MCO-023", "get_deployment returns None for missing",
            True, got is None,
            cause="invalid ID",
            effect="None returned",
            lesson="Missing deployments return None",
        )

    def test_list_deployments(self) -> None:
        orch = _make_orchestrator()
        _add_deployment(orch, "d1", provider="aws")
        _add_deployment(orch, "d2", provider="gcp")
        _add_deployment(orch, "d3", provider="aws")
        deps = orch.list_deployments(provider="aws")
        record(
            "MCO-024", "list_deployments filters by provider",
            2, len(deps),
            cause="2 aws deployments, 1 gcp",
            effect="2 returned for aws",
            lesson="Provider filter must work for deployments",
        )

    def test_list_deployments_status(self) -> None:
        orch = _make_orchestrator()
        d1 = _add_deployment(orch, "d1")
        d2 = _add_deployment(orch, "d2")
        orch.update_deployment_status(d1.id, "running")
        deps = orch.list_deployments(status="running")
        record(
            "MCO-025", "list_deployments filters by status",
            1, len(deps),
            cause="1 running, 1 pending",
            effect="1 returned",
            lesson="Status filter must work for deployments",
        )

    def test_list_deployments_limit(self) -> None:
        orch = _make_orchestrator()
        for i in range(20):
            _add_deployment(orch, f"d{i}")
        deps = orch.list_deployments(limit=5)
        record(
            "MCO-026", "list_deployments respects limit",
            5, len(deps),
            cause="20 deployments, limit=5",
            effect="5 returned",
            lesson="Limit must be respected",
        )

    def test_update_deployment_status(self) -> None:
        orch = _make_orchestrator()
        dep = _add_deployment(orch)
        updated = orch.update_deployment_status(dep.id, "running")
        record(
            "MCO-027", "update_deployment_status changes status",
            "running", updated.status if updated else None,
            cause="status changed to running",
            effect="status updated",
            lesson="Status updates must persist",
        )

    def test_update_deployment_status_enum(self) -> None:
        orch = _make_orchestrator()
        dep = _add_deployment(orch)
        updated = orch.update_deployment_status(dep.id, DeploymentStatus.deploying)
        record(
            "MCO-028", "update_deployment_status accepts enum",
            "deploying", updated.status if updated else None,
            cause="DeploymentStatus.deploying passed",
            effect="stored as string",
            lesson="Enum coercion must work on status update",
        )

    def test_update_deployment_status_missing(self) -> None:
        orch = _make_orchestrator()
        result = orch.update_deployment_status("missing", "running")
        record(
            "MCO-029", "update_deployment_status returns None for missing",
            True, result is None,
            cause="invalid ID",
            effect="None returned",
            lesson="Missing deployments cannot be updated",
        )

    def test_delete_deployment(self) -> None:
        orch = _make_orchestrator()
        dep = _add_deployment(orch)
        ok = orch.delete_deployment(dep.id)
        record(
            "MCO-030", "delete_deployment returns True",
            True, ok,
            cause="valid deployment deleted",
            effect="True returned",
            lesson="Delete must succeed for existing deployments",
        )
        assert orch.get_deployment(dep.id) is None

    def test_delete_deployment_missing(self) -> None:
        orch = _make_orchestrator()
        ok = orch.delete_deployment("nonexistent")
        record(
            "MCO-031", "delete_deployment returns False for missing",
            False, ok,
            cause="invalid ID",
            effect="False returned",
            lesson="Delete of missing returns False",
        )

    def test_deployment_id_unique(self) -> None:
        orch = _make_orchestrator()
        d1 = _add_deployment(orch, "d1")
        d2 = _add_deployment(orch, "d2")
        record(
            "MCO-032", "deployment IDs are unique",
            True, d1.id != d2.id,
            cause="two deployments created",
            effect="different IDs",
            lesson="UUID generation must be unique",
        )

    def test_deployment_serialization(self) -> None:
        orch = _make_orchestrator()
        dep = _add_deployment(orch)
        d = dep.to_dict()
        record(
            "MCO-033", "deployment to_dict has all fields",
            True, "id" in d and "name" in d and "provider" in d and "status" in d,
            cause="to_dict called",
            effect="dict with all fields",
            lesson="Serialization must be complete",
        )

    def test_deployment_custom_resources(self) -> None:
        orch = _make_orchestrator()
        dep = orch.create_deployment(
            "heavy", "aws", "us-east-1",
            replicas=3, cpu_limit="4000m", memory_limit="8Gi",
            image="myapp:latest",
        )
        record(
            "MCO-034", "deployment stores resource limits",
            True, dep.replicas == 3 and dep.cpu_limit == "4000m",
            cause="custom resources passed",
            effect="stored correctly",
            lesson="Resource limits must be preserved",
        )

    def test_deployment_env_vars(self) -> None:
        orch = _make_orchestrator()
        dep = orch.create_deployment(
            "env-app", "aws", "us-east-1",
            env_vars={"LOG_LEVEL": "debug"},
        )
        record(
            "MCO-035", "deployment stores env_vars",
            {"LOG_LEVEL": "debug"}, dep.env_vars,
            cause="env_vars passed",
            effect="env_vars stored",
            lesson="Environment variables must be preserved",
        )

    def test_deployment_health_default(self) -> None:
        orch = _make_orchestrator()
        dep = _add_deployment(orch)
        record(
            "MCO-036", "deployment health defaults to unknown",
            "unknown", dep.health_state,
            cause="no health set",
            effect="defaults to unknown",
            lesson="New deployments have unknown health",
        )


class TestFailover:
    """Failover rule creation and evaluation."""

    def test_create_failover_rule(self) -> None:
        orch = _make_orchestrator()
        rule = orch.create_failover_rule("aws-to-gcp", "aws", "gcp")
        record(
            "MCO-037", "create_failover_rule returns FailoverRule",
            True, isinstance(rule, FailoverRule),
            cause="create_failover_rule called",
            effect="FailoverRule returned",
            lesson="Factory must return typed rule",
        )

    def test_failover_rule_defaults(self) -> None:
        orch = _make_orchestrator()
        rule = orch.create_failover_rule("r1", "aws", "gcp")
        record(
            "MCO-038", "failover rule defaults to active_passive",
            "active_passive", rule.strategy,
            cause="no strategy specified",
            effect="defaults to active_passive",
            lesson="Default strategy is active_passive",
        )

    def test_failover_rule_enum_strategy(self) -> None:
        orch = _make_orchestrator()
        rule = orch.create_failover_rule(
            "rr-rule", "aws", "gcp",
            strategy=FailoverStrategy.round_robin,
        )
        record(
            "MCO-039", "enum FailoverStrategy coerced to string",
            "round_robin", rule.strategy,
            cause="FailoverStrategy enum passed",
            effect="stored as string",
            lesson="Enum coercion must work for strategies",
        )

    def test_list_failover_rules(self) -> None:
        orch = _make_orchestrator()
        orch.create_failover_rule("r1", "aws", "gcp")
        orch.create_failover_rule("r2", "gcp", "azure")
        orch.create_failover_rule("r3", "aws", "azure")
        rules = orch.list_failover_rules(primary_provider="aws")
        record(
            "MCO-040", "list_failover_rules filters by primary_provider",
            2, len(rules),
            cause="2 rules with primary=aws",
            effect="2 returned",
            lesson="Primary provider filter must work",
        )

    def test_list_failover_rules_enabled(self) -> None:
        orch = _make_orchestrator()
        orch.create_failover_rule("r1", "aws", "gcp", enabled=True)
        orch.create_failover_rule("r2", "aws", "azure", enabled=False)
        rules = orch.list_failover_rules(enabled=True)
        record(
            "MCO-041", "list_failover_rules filters by enabled",
            1, len(rules),
            cause="1 enabled, 1 disabled",
            effect="1 returned",
            lesson="Enabled filter must work for failover rules",
        )

    def test_list_failover_rules_limit(self) -> None:
        orch = _make_orchestrator()
        for i in range(15):
            orch.create_failover_rule(f"r{i}", "aws", "gcp")
        rules = orch.list_failover_rules(limit=5)
        record(
            "MCO-042", "list_failover_rules respects limit",
            5, len(rules),
            cause="15 rules, limit=5",
            effect="5 returned",
            lesson="Limit must be respected for failover rules",
        )

    def test_evaluate_failover_healthy(self) -> None:
        orch = _make_orchestrator()
        dep = _add_deployment(orch)
        orch.update_health(dep.id, "healthy")
        orch.create_failover_rule("r1", "aws", "gcp")
        result = orch.evaluate_failover(dep.id)
        record(
            "MCO-043", "failover not triggered for healthy deployment",
            False, result["triggered"],
            cause="deployment is healthy",
            effect="triggered=False",
            lesson="Healthy deployments should not trigger failover",
        )

    def test_evaluate_failover_degraded(self) -> None:
        orch = _make_orchestrator()
        dep = _add_deployment(orch, provider="aws")
        orch.update_health(dep.id, "degraded")
        orch.create_failover_rule("r1", "aws", "gcp")
        result = orch.evaluate_failover(dep.id)
        record(
            "MCO-044", "failover triggered for degraded deployment",
            True, result["triggered"],
            cause="deployment is degraded",
            effect="triggered=True",
            lesson="Degraded deployments should trigger failover",
        )

    def test_evaluate_failover_no_matching_rule(self) -> None:
        orch = _make_orchestrator()
        dep = _add_deployment(orch, provider="azure")
        orch.update_health(dep.id, "unhealthy")
        orch.create_failover_rule("r1", "aws", "gcp")
        result = orch.evaluate_failover(dep.id)
        record(
            "MCO-045", "failover not triggered without matching rule",
            False, result["triggered"],
            cause="no rule for azure provider",
            effect="triggered=False",
            lesson="Failover requires a matching rule",
        )

    def test_evaluate_failover_missing_deployment(self) -> None:
        orch = _make_orchestrator()
        result = orch.evaluate_failover("nonexistent")
        record(
            "MCO-046", "failover returns not triggered for missing deployment",
            False, result["triggered"],
            cause="deployment not found",
            effect="triggered=False",
            lesson="Missing deployments cannot trigger failover",
        )

    def test_evaluate_failover_response_fields(self) -> None:
        orch = _make_orchestrator()
        dep = _add_deployment(orch, provider="aws")
        orch.update_health(dep.id, "unhealthy")
        rule = orch.create_failover_rule("r1", "aws", "gcp")
        result = orch.evaluate_failover(dep.id)
        record(
            "MCO-047", "failover response includes strategy and rule_id",
            True, result.get("strategy") == "active_passive" and "rule_id" in result,
            cause="failover triggered",
            effect="strategy and rule_id in response",
            lesson="Failover response must be informative",
        )

    def test_failover_rule_serialization(self) -> None:
        orch = _make_orchestrator()
        rule = orch.create_failover_rule("r1", "aws", "gcp")
        d = rule.to_dict()
        record(
            "MCO-048", "failover rule to_dict has all fields",
            True, "id" in d and "name" in d and "strategy" in d,
            cause="to_dict called",
            effect="dict with all fields",
            lesson="Failover rule serialization must be complete",
        )


class TestSync:
    """Resource synchronisation between providers."""

    def test_start_sync(self) -> None:
        orch = _make_orchestrator()
        task = orch.start_sync("aws", "gcp", "storage")
        record(
            "MCO-049", "start_sync returns SyncTask",
            True, isinstance(task, SyncTask),
            cause="start_sync called",
            effect="SyncTask returned",
            lesson="Factory must return typed sync task",
        )

    def test_sync_status_in_progress(self) -> None:
        orch = _make_orchestrator()
        task = orch.start_sync("aws", "gcp", "storage")
        record(
            "MCO-050", "sync starts in in_progress status",
            "in_progress", task.status,
            cause="sync started",
            effect="status=in_progress",
            lesson="New syncs must be in_progress",
        )

    def test_complete_sync_success(self) -> None:
        orch = _make_orchestrator()
        task = orch.start_sync("aws", "gcp", "storage")
        completed = orch.complete_sync(task.id, items_synced=42)
        record(
            "MCO-051", "complete_sync sets status to completed",
            "completed", completed.status if completed else None,
            cause="sync completed without errors",
            effect="status=completed",
            lesson="Successful sync must be completed",
        )

    def test_complete_sync_with_errors(self) -> None:
        orch = _make_orchestrator()
        task = orch.start_sync("aws", "gcp", "storage")
        completed = orch.complete_sync(task.id, errors=["timeout on bucket-3"])
        record(
            "MCO-052", "complete_sync with errors sets status to failed",
            "failed", completed.status if completed else None,
            cause="sync completed with errors",
            effect="status=failed",
            lesson="Sync with errors must be failed",
        )

    def test_complete_sync_missing(self) -> None:
        orch = _make_orchestrator()
        result = orch.complete_sync("nonexistent")
        record(
            "MCO-053", "complete_sync returns None for missing",
            True, result is None,
            cause="invalid sync ID",
            effect="None returned",
            lesson="Missing syncs return None",
        )

    def test_complete_sync_items_synced(self) -> None:
        orch = _make_orchestrator()
        task = orch.start_sync("aws", "gcp", "storage")
        completed = orch.complete_sync(task.id, items_synced=100)
        record(
            "MCO-054", "complete_sync records items_synced",
            100, completed.items_synced if completed else -1,
            cause="items_synced=100 passed",
            effect="items_synced stored",
            lesson="Item count must be recorded",
        )

    def test_list_syncs(self) -> None:
        orch = _make_orchestrator()
        orch.start_sync("aws", "gcp", "storage")
        orch.start_sync("gcp", "azure", "compute")
        orch.start_sync("aws", "azure", "dns")
        syncs = orch.list_syncs(source_provider="aws")
        record(
            "MCO-055", "list_syncs filters by source_provider",
            2, len(syncs),
            cause="2 syncs from aws",
            effect="2 returned",
            lesson="Source provider filter must work",
        )

    def test_list_syncs_status(self) -> None:
        orch = _make_orchestrator()
        t1 = orch.start_sync("aws", "gcp", "storage")
        orch.start_sync("aws", "gcp", "compute")
        orch.complete_sync(t1.id, items_synced=10)
        syncs = orch.list_syncs(status="completed")
        record(
            "MCO-056", "list_syncs filters by status",
            1, len(syncs),
            cause="1 completed, 1 in_progress",
            effect="1 returned",
            lesson="Status filter must work for syncs",
        )

    def test_list_syncs_limit(self) -> None:
        orch = _make_orchestrator()
        for i in range(15):
            orch.start_sync("aws", "gcp", f"res-{i}")
        syncs = orch.list_syncs(limit=5)
        record(
            "MCO-057", "list_syncs respects limit",
            5, len(syncs),
            cause="15 syncs, limit=5",
            effect="5 returned",
            lesson="Limit must be respected for syncs",
        )

    def test_sync_serialization(self) -> None:
        orch = _make_orchestrator()
        task = orch.start_sync("aws", "gcp", "storage")
        d = task.to_dict()
        record(
            "MCO-058", "sync to_dict has all fields",
            True, "id" in d and "source_provider" in d and "status" in d,
            cause="to_dict called",
            effect="dict with all fields",
            lesson="Sync serialization must be complete",
        )

    def test_sync_completed_at_populated(self) -> None:
        orch = _make_orchestrator()
        task = orch.start_sync("aws", "gcp", "storage")
        completed = orch.complete_sync(task.id, items_synced=5)
        record(
            "MCO-059", "completed sync has completed_at timestamp",
            True, bool(completed.completed_at) if completed else False,
            cause="sync completed",
            effect="completed_at populated",
            lesson="Completion timestamp must be set",
        )


class TestCostTracking:
    """Cloud cost recording and aggregation."""

    def test_record_cost(self) -> None:
        orch = _make_orchestrator()
        rec = orch.record_cost("aws", "us-east-1", "ec2", 150.50)
        record(
            "MCO-060", "record_cost returns CostRecord",
            True, isinstance(rec, CostRecord),
            cause="record_cost called",
            effect="CostRecord returned",
            lesson="Factory must return typed cost record",
        )

    def test_cost_defaults_currency(self) -> None:
        orch = _make_orchestrator()
        rec = orch.record_cost("aws", "us-east-1", "ec2", 100.0)
        record(
            "MCO-061", "cost defaults to USD currency",
            "USD", rec.currency,
            cause="no currency specified",
            effect="defaults to USD",
            lesson="Default currency must be USD",
        )

    def test_get_cost_summary(self) -> None:
        orch = _make_orchestrator()
        orch.record_cost("aws", "us-east-1", "ec2", 100.0)
        orch.record_cost("aws", "us-east-1", "s3", 50.0)
        orch.record_cost("gcp", "us-central1", "compute", 75.0)
        summary = orch.get_cost_summary()
        record(
            "MCO-062", "cost summary totals all providers",
            225.0, summary["total"],
            cause="3 cost records totalling 225",
            effect="total=225.0",
            lesson="Cost aggregation must be accurate",
        )

    def test_cost_summary_by_provider(self) -> None:
        orch = _make_orchestrator()
        orch.record_cost("aws", "us-east-1", "ec2", 100.0)
        orch.record_cost("gcp", "us-central1", "compute", 75.0)
        summary = orch.get_cost_summary()
        record(
            "MCO-063", "cost summary has by_provider breakdown",
            True, summary["by_provider"]["aws"] == 100.0 and summary["by_provider"]["gcp"] == 75.0,
            cause="2 providers with costs",
            effect="by_provider has both",
            lesson="Provider breakdown must be accurate",
        )

    def test_cost_summary_filter_provider(self) -> None:
        orch = _make_orchestrator()
        orch.record_cost("aws", "us-east-1", "ec2", 100.0)
        orch.record_cost("gcp", "us-central1", "compute", 75.0)
        summary = orch.get_cost_summary(provider="aws")
        record(
            "MCO-064", "cost summary filters by provider",
            100.0, summary["total"],
            cause="filter provider=aws",
            effect="total=100.0 (aws only)",
            lesson="Provider filter must work for cost summary",
        )

    def test_cost_summary_record_count(self) -> None:
        orch = _make_orchestrator()
        orch.record_cost("aws", "us-east-1", "ec2", 50.0)
        orch.record_cost("aws", "us-east-1", "s3", 30.0)
        summary = orch.get_cost_summary()
        record(
            "MCO-065", "cost summary has record_count",
            2, summary["record_count"],
            cause="2 cost records",
            effect="record_count=2",
            lesson="Record count must be accurate",
        )

    def test_list_costs(self) -> None:
        orch = _make_orchestrator()
        orch.record_cost("aws", "us-east-1", "ec2", 100.0)
        orch.record_cost("gcp", "us-central1", "compute", 75.0)
        costs = orch.list_costs(provider="aws")
        record(
            "MCO-066", "list_costs filters by provider",
            1, len(costs),
            cause="1 aws cost, 1 gcp cost",
            effect="1 returned for aws",
            lesson="Provider filter must work for cost listing",
        )

    def test_list_costs_limit(self) -> None:
        orch = _make_orchestrator()
        for i in range(20):
            orch.record_cost("aws", "us-east-1", f"svc-{i}", 10.0)
        costs = orch.list_costs(limit=5)
        record(
            "MCO-067", "list_costs respects limit",
            5, len(costs),
            cause="20 costs, limit=5",
            effect="5 returned",
            lesson="Limit must be respected for costs",
        )

    def test_cost_serialization(self) -> None:
        orch = _make_orchestrator()
        rec = orch.record_cost("aws", "us-east-1", "ec2", 100.0)
        d = rec.to_dict()
        record(
            "MCO-068", "cost to_dict has all fields",
            True, "id" in d and "provider" in d and "amount" in d,
            cause="to_dict called",
            effect="dict with all fields",
            lesson="Cost serialization must be complete",
        )

    def test_cost_summary_empty(self) -> None:
        orch = _make_orchestrator()
        summary = orch.get_cost_summary()
        record(
            "MCO-069", "cost summary handles empty state",
            0.0, summary["total"],
            cause="no costs recorded",
            effect="total=0.0",
            lesson="Empty cost state must return zero total",
        )

    def test_cost_multi_provider_aggregation(self) -> None:
        orch = _make_orchestrator()
        orch.record_cost("aws", "us-east-1", "ec2", 200.0)
        orch.record_cost("gcp", "us-central1", "compute", 150.0)
        orch.record_cost("azure", "eastus", "vm", 250.0)
        summary = orch.get_cost_summary()
        record(
            "MCO-070", "cost summary aggregates across 3 providers",
            3, len(summary["by_provider"]),
            cause="costs in 3 platforms",
            effect="3 platforms in summary",
            lesson="Multi-platform aggregation must work",
        )
        assert summary["total"] == 600.0


class TestHealth:
    """Deployment health tracking."""

    def test_update_health(self) -> None:
        orch = _make_orchestrator()
        dep = _add_deployment(orch)
        updated = orch.update_health(dep.id, "healthy")
        record(
            "MCO-071", "update_health changes health_state",
            "healthy", updated.health_state if updated else None,
            cause="health set to healthy",
            effect="health_state updated",
            lesson="Health updates must persist",
        )

    def test_update_health_enum(self) -> None:
        orch = _make_orchestrator()
        dep = _add_deployment(orch)
        updated = orch.update_health(dep.id, HealthState.degraded)
        record(
            "MCO-072", "update_health accepts HealthState enum",
            "degraded", updated.health_state if updated else None,
            cause="HealthState.degraded passed",
            effect="stored as string",
            lesson="Enum coercion must work for health",
        )

    def test_update_health_missing(self) -> None:
        orch = _make_orchestrator()
        result = orch.update_health("nonexistent", "healthy")
        record(
            "MCO-073", "update_health returns None for missing",
            True, result is None,
            cause="invalid deployment ID",
            effect="None returned",
            lesson="Missing deployments cannot have health updated",
        )

    def test_update_health_sets_timestamp(self) -> None:
        orch = _make_orchestrator()
        dep = _add_deployment(orch)
        updated = orch.update_health(dep.id, "healthy")
        record(
            "MCO-074", "update_health sets last_health_check",
            True, bool(updated.last_health_check) if updated else False,
            cause="health updated",
            effect="last_health_check populated",
            lesson="Health check timestamp must be set",
        )

    def test_get_health_overview(self) -> None:
        orch = _make_orchestrator()
        d1 = _add_deployment(orch, "d1")
        d2 = _add_deployment(orch, "d2")
        d3 = _add_deployment(orch, "d3")
        orch.update_health(d1.id, "healthy")
        orch.update_health(d2.id, "degraded")
        orch.update_health(d3.id, "unhealthy")
        overview = orch.get_health_overview()
        record(
            "MCO-075", "health overview counts by state",
            True,
            overview["healthy"] == 1 and overview["degraded"] == 1 and overview["unhealthy"] == 1,
            cause="1 healthy, 1 degraded, 1 unhealthy",
            effect="counts correct",
            lesson="Health overview must count accurately",
        )

    def test_health_overview_total(self) -> None:
        orch = _make_orchestrator()
        _add_deployment(orch, "d1")
        _add_deployment(orch, "d2")
        overview = orch.get_health_overview()
        record(
            "MCO-076", "health overview has total_deployments",
            2, overview["total_deployments"],
            cause="2 deployments exist",
            effect="total_deployments=2",
            lesson="Total count must be accurate",
        )

    def test_health_overview_empty(self) -> None:
        orch = _make_orchestrator()
        overview = orch.get_health_overview()
        record(
            "MCO-077", "health overview handles empty state",
            0, overview["total_deployments"],
            cause="no deployments",
            effect="total_deployments=0",
            lesson="Empty state must return zero counts",
        )

    def test_health_overview_unknown_default(self) -> None:
        orch = _make_orchestrator()
        _add_deployment(orch, "d1")
        overview = orch.get_health_overview()
        record(
            "MCO-078", "new deployments counted as unknown in overview",
            1, overview["unknown"],
            cause="1 deployment with default health",
            effect="unknown=1",
            lesson="Default health state must count as unknown",
        )


class TestExportAndClear:
    """State export and clear."""

    def test_export_state(self) -> None:
        orch = _make_orchestrator()
        _add_provider(orch, "p1")
        state = orch.export_state()
        record(
            "MCO-079", "export_state returns dict",
            True, isinstance(state, dict),
            cause="export_state called",
            effect="dict returned",
            lesson="Export must return plain dict",
        )
        assert "providers" in state
        assert "exported_at" in state

    def test_export_has_all_keys(self) -> None:
        orch = _make_orchestrator()
        state = orch.export_state()
        expected_keys = {"providers", "deployments", "failover_rules", "syncs", "costs", "exported_at"}
        record(
            "MCO-080", "export has all expected keys",
            expected_keys, set(state.keys()),
            cause="export_state called",
            effect="all keys present",
            lesson="Export must be comprehensive",
        )

    def test_export_includes_data(self) -> None:
        orch = _make_orchestrator()
        p = _add_provider(orch, "p1")
        d = _add_deployment(orch, "d1")
        state = orch.export_state()
        record(
            "MCO-081", "export includes registered data",
            True, p.id in state["providers"] and d.id in state["deployments"],
            cause="provider and deployment created",
            effect="both in export",
            lesson="Export must include all data",
        )

    def test_clear(self) -> None:
        orch = _make_orchestrator()
        _add_provider(orch, "p1")
        _add_deployment(orch, "d1")
        orch.clear()
        providers = orch.list_providers()
        deployments = orch.list_deployments()
        record(
            "MCO-082", "clear removes all state",
            True, len(providers) == 0 and len(deployments) == 0,
            cause="clear called",
            effect="no data remains",
            lesson="Clear must remove all data",
        )

    def test_get_multi_cloud_summary(self) -> None:
        orch = _make_orchestrator()
        _add_provider(orch, "p1")
        dep = _add_deployment(orch, "d1")
        orch.update_deployment_status(dep.id, "running")
        _add_deployment(orch, "d2")
        orch.create_failover_rule("r1", "aws", "gcp")
        orch.start_sync("aws", "gcp", "storage")
        orch.record_cost("aws", "us-east-1", "ec2", 100.0)
        summary = orch.get_multi_cloud_summary()
        record(
            "MCO-083", "summary returns correct counts",
            True,
            summary["providers"] == 1
            and summary["deployments"] == 2
            and summary["active_deployments"] == 1
            and summary["failover_rules"] == 1
            and summary["sync_tasks"] == 1
            and summary["cost_records"] == 1,
            cause="various resources created",
            effect="summary counts match",
            lesson="Summary must accurately reflect state",
        )


class TestWingmanAndSandbox:
    """Wingman pair validation and sandbox gating."""

    def test_wingman_match(self) -> None:
        result = validate_wingman_pair(["a", "b", "c"], ["a", "b", "c"])
        record(
            "MCO-084", "matching pair passes",
            True, result["passed"],
            cause="storyline matches actuals",
            effect="validation passes",
            lesson="Matching pairs must pass",
        )

    def test_wingman_mismatch(self) -> None:
        result = validate_wingman_pair(["a", "b"], ["a", "x"])
        record(
            "MCO-085", "mismatching pair fails",
            False, result["passed"],
            cause="actuals differ",
            effect="validation fails",
            lesson="Mismatches must be caught",
        )

    def test_wingman_empty_storyline(self) -> None:
        result = validate_wingman_pair([], ["a"])
        record(
            "MCO-086", "empty storyline fails",
            False, result["passed"],
            cause="empty storyline",
            effect="validation fails",
            lesson="Empty inputs must be rejected",
        )

    def test_wingman_empty_actuals(self) -> None:
        result = validate_wingman_pair(["a"], [])
        record(
            "MCO-087", "empty actuals fails",
            False, result["passed"],
            cause="empty actuals",
            effect="validation fails",
            lesson="Empty inputs must be rejected",
        )

    def test_wingman_length_mismatch(self) -> None:
        result = validate_wingman_pair(["a", "b"], ["a"])
        record(
            "MCO-088", "length mismatch fails",
            False, result["passed"],
            cause="different lengths",
            effect="validation fails",
            lesson="Length mismatches must be caught",
        )

    def test_wingman_pair_count(self) -> None:
        result = validate_wingman_pair(["x", "y", "z"], ["x", "y", "z"])
        record(
            "MCO-089", "pair_count in response",
            3, result.get("pair_count"),
            cause="3 pairs validated",
            effect="pair_count=3",
            lesson="Response must include pair_count",
        )

    def test_sandbox_pass(self) -> None:
        result = gate_mco_in_sandbox({"provider": "aws"})
        record(
            "MCO-090", "sandbox gate passes with provider",
            True, result["passed"],
            cause="provider key present",
            effect="gate passes",
            lesson="Valid context must pass gate",
        )

    def test_sandbox_missing_provider(self) -> None:
        result = gate_mco_in_sandbox({})
        record(
            "MCO-091", "sandbox gate fails without provider",
            False, result["passed"],
            cause="no provider key",
            effect="gate fails",
            lesson="Missing required keys must fail gate",
        )

    def test_sandbox_empty_provider(self) -> None:
        result = gate_mco_in_sandbox({"provider": ""})
        record(
            "MCO-092", "sandbox gate fails with empty provider",
            False, result["passed"],
            cause="empty provider string",
            effect="gate fails",
            lesson="Empty values must fail gate",
        )

    def test_sandbox_returns_provider(self) -> None:
        result = gate_mco_in_sandbox({"provider": "gcp"})
        record(
            "MCO-093", "sandbox gate returns provider",
            "gcp", result.get("provider"),
            cause="provider=gcp passed",
            effect="provider in response",
            lesson="Response must echo provider",
        )


class TestConcurrency:
    """Thread-safety tests."""

    def test_concurrent_provider_creation(self) -> None:
        orch = _make_orchestrator()
        errors: List[str] = []

        def create_batch(prefix: str) -> None:
            try:
                for i in range(50):
                    _add_provider(orch, f"{prefix}-{i}")
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=create_batch, args=(f"t{t}",))
                   for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        providers = orch.list_providers(limit=500)
        record(
            "MCO-094", "concurrent provider creation is thread-safe",
            True, len(providers) == 200 and not errors,
            cause="4 threads x 50 providers",
            effect="200 providers, no errors",
            lesson="Provider creation must be thread-safe",
        )

    def test_concurrent_deployment_creation(self) -> None:
        orch = _make_orchestrator()
        errors: List[str] = []

        def create_batch(tid: int) -> None:
            try:
                for i in range(25):
                    _add_deployment(orch, f"t{tid}-d{i}")
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=create_batch, args=(t,))
                   for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        deps = orch.list_deployments(limit=500)
        record(
            "MCO-095", "concurrent deployment creation is thread-safe",
            True, len(deps) == 100 and not errors,
            cause="4 threads x 25 deployments",
            effect="100 deployments, no errors",
            lesson="Deployment creation must be thread-safe",
        )


class TestFlaskAPI:
    """Flask Blueprint API endpoints."""

    def _make_app(self):
        try:
            from flask import Flask
        except ImportError:
            return None, None
        orch = _make_orchestrator()
        app = Flask(__name__)
        app.config["TESTING"] = True
        bp = create_multi_cloud_api(orch)
        app.register_blueprint(bp)
        return app, orch

    def test_api_create_provider(self) -> None:
        app, orch = self._make_app()
        if app is None:
            record("MCO-096", "Flask not installed -- skip", True, True)
            return
        with app.test_client() as c:
            resp = c.post("/api/mco/providers", json={
                "name": "aws-prod", "provider": "aws", "region": "us-east-1",
            })
        record(
            "MCO-096", "POST /mco/providers returns 201",
            201, resp.status_code,
            cause="valid provider data",
            effect="201 created",
            lesson="Provider creation must return 201",
        )

    def test_api_list_providers(self) -> None:
        app, orch = self._make_app()
        if app is None:
            record("MCO-097", "Flask not installed -- skip", True, True)
            return
        _add_provider(orch, "p1")
        with app.test_client() as c:
            resp = c.get("/api/mco/providers")
        record(
            "MCO-097", "GET /mco/providers returns 200",
            200, resp.status_code,
            cause="providers exist",
            effect="200 OK",
            lesson="List must return 200",
        )

    def test_api_get_provider(self) -> None:
        app, orch = self._make_app()
        if app is None:
            record("MCO-098", "Flask not installed -- skip", True, True)
            return
        cfg = _add_provider(orch, "p1")
        with app.test_client() as c:
            resp = c.get(f"/api/mco/providers/{cfg.id}")
        record(
            "MCO-098", "GET /mco/providers/<id> returns 200",
            200, resp.status_code,
            cause="valid provider ID",
            effect="200 OK",
            lesson="Get by ID must return 200",
        )

    def test_api_get_provider_404(self) -> None:
        app, _ = self._make_app()
        if app is None:
            record("MCO-099", "Flask not installed -- skip", True, True)
            return
        with app.test_client() as c:
            resp = c.get("/api/mco/providers/nonexistent")
        record(
            "MCO-099", "GET /mco/providers/<missing> returns 404",
            404, resp.status_code,
            cause="invalid provider ID",
            effect="404 Not Found",
            lesson="Missing provider must return 404",
        )

    def test_api_update_provider(self) -> None:
        app, orch = self._make_app()
        if app is None:
            record("MCO-100", "Flask not installed -- skip", True, True)
            return
        cfg = _add_provider(orch, "p1")
        with app.test_client() as c:
            resp = c.put(f"/api/mco/providers/{cfg.id}", json={"enabled": False})
        record(
            "MCO-100", "PUT /mco/providers/<id> returns 200",
            200, resp.status_code,
            cause="valid update data",
            effect="200 OK",
            lesson="Provider update must return 200",
        )

    def test_api_delete_provider(self) -> None:
        app, orch = self._make_app()
        if app is None:
            record("MCO-101", "Flask not installed -- skip", True, True)
            return
        cfg = _add_provider(orch, "p1")
        with app.test_client() as c:
            resp = c.delete(f"/api/mco/providers/{cfg.id}")
        record(
            "MCO-101", "DELETE /mco/providers/<id> returns 200",
            200, resp.status_code,
            cause="valid provider ID",
            effect="200 OK",
            lesson="Provider delete must return 200",
        )

    def test_api_create_deployment(self) -> None:
        app, orch = self._make_app()
        if app is None:
            record("MCO-102", "Flask not installed -- skip", True, True)
            return
        with app.test_client() as c:
            resp = c.post("/api/mco/deployments", json={
                "name": "web-app", "provider": "aws", "region": "us-east-1",
            })
        record(
            "MCO-102", "POST /mco/deployments returns 201",
            201, resp.status_code,
            cause="valid deployment data",
            effect="201 created",
            lesson="Deployment creation must return 201",
        )

    def test_api_list_deployments(self) -> None:
        app, orch = self._make_app()
        if app is None:
            record("MCO-103", "Flask not installed -- skip", True, True)
            return
        _add_deployment(orch, "d1")
        with app.test_client() as c:
            resp = c.get("/api/mco/deployments")
        record(
            "MCO-103", "GET /mco/deployments returns 200",
            200, resp.status_code,
            cause="deployments exist",
            effect="200 OK",
            lesson="List deployments must return 200",
        )

    def test_api_get_deployment(self) -> None:
        app, orch = self._make_app()
        if app is None:
            record("MCO-104", "Flask not installed -- skip", True, True)
            return
        dep = _add_deployment(orch, "d1")
        with app.test_client() as c:
            resp = c.get(f"/api/mco/deployments/{dep.id}")
        record(
            "MCO-104", "GET /mco/deployments/<id> returns 200",
            200, resp.status_code,
            cause="valid deployment ID",
            effect="200 OK",
            lesson="Get deployment must return 200",
        )

    def test_api_update_deployment_status(self) -> None:
        app, orch = self._make_app()
        if app is None:
            record("MCO-105", "Flask not installed -- skip", True, True)
            return
        dep = _add_deployment(orch, "d1")
        with app.test_client() as c:
            resp = c.put(f"/api/mco/deployments/{dep.id}/status", json={
                "status": "running",
            })
        record(
            "MCO-105", "PUT /mco/deployments/<id>/status returns 200",
            200, resp.status_code,
            cause="valid status update",
            effect="200 OK",
            lesson="Status update must return 200",
        )

    def test_api_delete_deployment(self) -> None:
        app, orch = self._make_app()
        if app is None:
            record("MCO-106", "Flask not installed -- skip", True, True)
            return
        dep = _add_deployment(orch, "d1")
        with app.test_client() as c:
            resp = c.delete(f"/api/mco/deployments/{dep.id}")
        record(
            "MCO-106", "DELETE /mco/deployments/<id> returns 200",
            200, resp.status_code,
            cause="valid deployment ID",
            effect="200 OK",
            lesson="Deployment delete must return 200",
        )

    def test_api_create_failover_rule(self) -> None:
        app, orch = self._make_app()
        if app is None:
            record("MCO-107", "Flask not installed -- skip", True, True)
            return
        with app.test_client() as c:
            resp = c.post("/api/mco/failover-rules", json={
                "name": "aws-to-gcp",
                "primary_provider": "aws",
                "secondary_provider": "gcp",
            })
        record(
            "MCO-107", "POST /mco/failover-rules returns 201",
            201, resp.status_code,
            cause="valid failover rule data",
            effect="201 created",
            lesson="Failover rule creation must return 201",
        )

    def test_api_list_failover_rules(self) -> None:
        app, orch = self._make_app()
        if app is None:
            record("MCO-108", "Flask not installed -- skip", True, True)
            return
        orch.create_failover_rule("r1", "aws", "gcp")
        with app.test_client() as c:
            resp = c.get("/api/mco/failover-rules")
        record(
            "MCO-108", "GET /mco/failover-rules returns 200",
            200, resp.status_code,
            cause="failover rules exist",
            effect="200 OK",
            lesson="List failover rules must return 200",
        )

    def test_api_evaluate_failover(self) -> None:
        app, orch = self._make_app()
        if app is None:
            record("MCO-109", "Flask not installed -- skip", True, True)
            return
        dep = _add_deployment(orch, "d1")
        with app.test_client() as c:
            resp = c.post(f"/api/mco/failover/{dep.id}/evaluate")
        record(
            "MCO-109", "POST /mco/failover/<id>/evaluate returns 200",
            200, resp.status_code,
            cause="valid deployment ID for failover eval",
            effect="200 OK",
            lesson="Failover evaluation must return 200",
        )

    def test_api_start_sync(self) -> None:
        app, orch = self._make_app()
        if app is None:
            record("MCO-110", "Flask not installed -- skip", True, True)
            return
        with app.test_client() as c:
            resp = c.post("/api/mco/syncs", json={
                "source_provider": "aws",
                "target_provider": "gcp",
                "resource_type": "storage",
            })
        record(
            "MCO-110", "POST /mco/syncs returns 201",
            201, resp.status_code,
            cause="valid sync data",
            effect="201 created",
            lesson="Sync creation must return 201",
        )

    def test_api_list_syncs(self) -> None:
        app, orch = self._make_app()
        if app is None:
            record("MCO-111", "Flask not installed -- skip", True, True)
            return
        orch.start_sync("aws", "gcp", "storage")
        with app.test_client() as c:
            resp = c.get("/api/mco/syncs")
        record(
            "MCO-111", "GET /mco/syncs returns 200",
            200, resp.status_code,
            cause="syncs exist",
            effect="200 OK",
            lesson="List syncs must return 200",
        )

    def test_api_complete_sync(self) -> None:
        app, orch = self._make_app()
        if app is None:
            record("MCO-112", "Flask not installed -- skip", True, True)
            return
        task = orch.start_sync("aws", "gcp", "storage")
        with app.test_client() as c:
            resp = c.post(f"/api/mco/syncs/{task.id}/complete", json={
                "items_synced": 42,
            })
        record(
            "MCO-112", "POST /mco/syncs/<id>/complete returns 200",
            200, resp.status_code,
            cause="valid sync completion",
            effect="200 OK",
            lesson="Sync completion must return 200",
        )

    def test_api_record_cost(self) -> None:
        app, orch = self._make_app()
        if app is None:
            record("MCO-113", "Flask not installed -- skip", True, True)
            return
        with app.test_client() as c:
            resp = c.post("/api/mco/costs", json={
                "provider": "aws", "service": "ec2", "amount": 150.50,
            })
        record(
            "MCO-113", "POST /mco/costs returns 201",
            201, resp.status_code,
            cause="valid cost data",
            effect="201 created",
            lesson="Cost recording must return 201",
        )

    def test_api_list_costs(self) -> None:
        app, orch = self._make_app()
        if app is None:
            record("MCO-114", "Flask not installed -- skip", True, True)
            return
        orch.record_cost("aws", "us-east-1", "ec2", 100.0)
        with app.test_client() as c:
            resp = c.get("/api/mco/costs")
        record(
            "MCO-114", "GET /mco/costs returns 200",
            200, resp.status_code,
            cause="costs exist",
            effect="200 OK",
            lesson="List costs must return 200",
        )

    def test_api_cost_summary(self) -> None:
        app, orch = self._make_app()
        if app is None:
            record("MCO-115", "Flask not installed -- skip", True, True)
            return
        with app.test_client() as c:
            resp = c.get("/api/mco/costs/summary")
        record(
            "MCO-115", "GET /mco/costs/summary returns 200",
            200, resp.status_code,
            cause="cost summary requested",
            effect="200 OK",
            lesson="Cost summary must return 200",
        )

    def test_api_update_health(self) -> None:
        app, orch = self._make_app()
        if app is None:
            record("MCO-116", "Flask not installed -- skip", True, True)
            return
        dep = _add_deployment(orch, "d1")
        with app.test_client() as c:
            resp = c.post(f"/api/mco/deployments/{dep.id}/health", json={
                "state": "healthy",
            })
        record(
            "MCO-116", "POST /mco/deployments/<id>/health returns 200",
            200, resp.status_code,
            cause="valid health update",
            effect="200 OK",
            lesson="Health update must return 200",
        )

    def test_api_health_overview(self) -> None:
        app, orch = self._make_app()
        if app is None:
            record("MCO-117", "Flask not installed -- skip", True, True)
            return
        with app.test_client() as c:
            resp = c.get("/api/mco/health/overview")
        record(
            "MCO-117", "GET /mco/health/overview returns 200",
            200, resp.status_code,
            cause="health overview requested",
            effect="200 OK",
            lesson="Health overview must return 200",
        )

    def test_api_health(self) -> None:
        app, _ = self._make_app()
        if app is None:
            record("MCO-118", "Flask not installed -- skip", True, True)
            return
        with app.test_client() as c:
            resp = c.get("/api/mco/health")
        data = resp.get_json()
        record(
            "MCO-118", "GET /mco/health returns module MCO-001",
            "MCO-001", data.get("module"),
            cause="health endpoint called",
            effect="module=MCO-001",
            lesson="Health must identify the module",
        )

    def test_api_export(self) -> None:
        app, _ = self._make_app()
        if app is None:
            record("MCO-119", "Flask not installed -- skip", True, True)
            return
        with app.test_client() as c:
            resp = c.post("/api/mco/export")
        record(
            "MCO-119", "POST /mco/export returns 200",
            200, resp.status_code,
            cause="export endpoint called",
            effect="200 OK",
            lesson="Export must return 200",
        )

    def test_api_summary(self) -> None:
        app, _ = self._make_app()
        if app is None:
            record("MCO-120", "Flask not installed -- skip", True, True)
            return
        with app.test_client() as c:
            resp = c.get("/api/mco/summary")
        record(
            "MCO-120", "GET /mco/summary returns 200",
            200, resp.status_code,
            cause="summary endpoint called",
            effect="200 OK",
            lesson="Summary must return 200",
        )

    def test_api_missing_provider_name(self) -> None:
        app, _ = self._make_app()
        if app is None:
            record("MCO-121", "Flask not installed -- skip", True, True)
            return
        with app.test_client() as c:
            resp = c.post("/api/mco/providers", json={})
        record(
            "MCO-121", "POST /mco/providers without name returns 400",
            400, resp.status_code,
            cause="missing name field",
            effect="400 Bad Request",
            lesson="Missing fields must return 400",
        )

    def test_api_missing_deployment_name(self) -> None:
        app, _ = self._make_app()
        if app is None:
            record("MCO-122", "Flask not installed -- skip", True, True)
            return
        with app.test_client() as c:
            resp = c.post("/api/mco/deployments", json={})
        record(
            "MCO-122", "POST /mco/deployments without name returns 400",
            400, resp.status_code,
            cause="missing name field",
            effect="400 Bad Request",
            lesson="Missing fields must return 400",
        )

    def test_api_missing_failover_name(self) -> None:
        app, _ = self._make_app()
        if app is None:
            record("MCO-123", "Flask not installed -- skip", True, True)
            return
        with app.test_client() as c:
            resp = c.post("/api/mco/failover-rules", json={})
        record(
            "MCO-123", "POST /mco/failover-rules without name returns 400",
            400, resp.status_code,
            cause="missing name field",
            effect="400 Bad Request",
            lesson="Missing fields must return 400",
        )

    def test_api_missing_sync_fields(self) -> None:
        app, _ = self._make_app()
        if app is None:
            record("MCO-124", "Flask not installed -- skip", True, True)
            return
        with app.test_client() as c:
            resp = c.post("/api/mco/syncs", json={})
        record(
            "MCO-124", "POST /mco/syncs without required fields returns 400",
            400, resp.status_code,
            cause="missing source_provider",
            effect="400 Bad Request",
            lesson="Missing fields must return 400",
        )

    def test_api_missing_cost_fields(self) -> None:
        app, _ = self._make_app()
        if app is None:
            record("MCO-125", "Flask not installed -- skip", True, True)
            return
        with app.test_client() as c:
            resp = c.post("/api/mco/costs", json={})
        record(
            "MCO-125", "POST /mco/costs without required fields returns 400",
            400, resp.status_code,
            cause="missing provider field",
            effect="400 Bad Request",
            lesson="Missing fields must return 400",
        )

    def test_api_missing_health_state(self) -> None:
        app, orch = self._make_app()
        if app is None:
            record("MCO-126", "Flask not installed -- skip", True, True)
            return
        dep = _add_deployment(orch, "d1")
        with app.test_client() as c:
            resp = c.post(f"/api/mco/deployments/{dep.id}/health", json={})
        record(
            "MCO-126", "POST /mco/deployments/<id>/health without state returns 400",
            400, resp.status_code,
            cause="missing state field",
            effect="400 Bad Request",
            lesson="Missing fields must return 400",
        )

    def test_api_missing_status_field(self) -> None:
        app, orch = self._make_app()
        if app is None:
            record("MCO-127", "Flask not installed -- skip", True, True)
            return
        dep = _add_deployment(orch, "d1")
        with app.test_client() as c:
            resp = c.put(f"/api/mco/deployments/{dep.id}/status", json={})
        record(
            "MCO-127", "PUT /mco/deployments/<id>/status without status returns 400",
            400, resp.status_code,
            cause="missing status field",
            effect="400 Bad Request",
            lesson="Missing fields must return 400",
        )

    def test_api_complete_sync_404(self) -> None:
        app, _ = self._make_app()
        if app is None:
            record("MCO-128", "Flask not installed -- skip", True, True)
            return
        with app.test_client() as c:
            resp = c.post("/api/mco/syncs/nonexistent/complete", json={})
        record(
            "MCO-128", "POST /mco/syncs/<missing>/complete returns 404",
            404, resp.status_code,
            cause="invalid sync ID",
            effect="404 Not Found",
            lesson="Missing sync must return 404",
        )


class TestBoundaryConditions:
    """Edge cases and boundary values."""

    def test_enum_cloud_provider_values(self) -> None:
        values = [e.value for e in CloudProvider]
        record(
            "MCO-129", "CloudProvider has expected values",
            True, "aws" in values and "gcp" in values and "azure" in values and "custom" in values,
            cause="CloudProvider enum inspected",
            effect="all expected values present",
            lesson="Enum must have all cloud providers",
        )

    def test_enum_deployment_status_values(self) -> None:
        values = [e.value for e in DeploymentStatus]
        record(
            "MCO-130", "DeploymentStatus has expected values",
            True, "pending" in values and "running" in values and "failed" in values,
            cause="DeploymentStatus enum inspected",
            effect="all expected values present",
            lesson="Enum must have all statuses",
        )

    def test_enum_health_state_values(self) -> None:
        values = [e.value for e in HealthState]
        record(
            "MCO-131", "HealthState has expected values",
            True, "healthy" in values and "degraded" in values and "unhealthy" in values and "unknown" in values,
            cause="HealthState enum inspected",
            effect="all expected values present",
            lesson="Enum must have all health states",
        )

    def test_enum_failover_strategy_values(self) -> None:
        values = [e.value for e in FailoverStrategy]
        record(
            "MCO-132", "FailoverStrategy has expected values",
            True, "active_passive" in values and "round_robin" in values and "cost_based" in values,
            cause="FailoverStrategy enum inspected",
            effect="all expected values present",
            lesson="Enum must have all strategies",
        )

    def test_special_chars_in_name(self) -> None:
        orch = _make_orchestrator()
        cfg = orch.register_provider(
            "AWS / GCP @ 2026", "aws", "us-east-1",
        )
        record(
            "MCO-133", "special characters in provider name",
            "AWS / GCP @ 2026", cfg.name,
            cause="special chars in name",
            effect="stored as-is",
            lesson="Names must accept arbitrary strings",
        )

    def test_zero_amount_cost(self) -> None:
        orch = _make_orchestrator()
        rec = orch.record_cost("aws", "us-east-1", "ec2", 0.0)
        record(
            "MCO-134", "zero amount cost is valid",
            0.0, rec.amount,
            cause="amount=0.0",
            effect="stored correctly",
            lesson="Zero cost must be accepted",
        )

    def test_large_replicas(self) -> None:
        orch = _make_orchestrator()
        dep = orch.create_deployment(
            "massive", "aws", "us-east-1", replicas=1000,
        )
        record(
            "MCO-135", "large replica count is stored",
            1000, dep.replicas,
            cause="replicas=1000",
            effect="stored correctly",
            lesson="Large values must be handled",
        )

    def test_provider_config_credentials_ref(self) -> None:
        orch = _make_orchestrator()
        cfg = orch.register_provider(
            "p1", "aws", "us-east-1",
            credentials_ref="skm://vault/aws-prod",
        )
        record(
            "MCO-136", "credentials_ref stores reference",
            "skm://vault/aws-prod", cfg.credentials_ref,
            cause="credentials_ref passed",
            effect="reference stored",
            lesson="Credential references must be stored",
        )

    def test_clear_then_export(self) -> None:
        orch = _make_orchestrator()
        _add_provider(orch, "p1")
        orch.clear()
        state = orch.export_state()
        record(
            "MCO-137", "export after clear returns empty state",
            True, len(state["providers"]) == 0 and len(state["deployments"]) == 0,
            cause="clear then export",
            effect="empty collections",
            lesson="Export after clear must be empty",
        )

    def test_deployment_all_statuses(self) -> None:
        orch = _make_orchestrator()
        dep = _add_deployment(orch)
        statuses_tested = []
        for s in ["deploying", "running", "failed", "stopped", "draining"]:
            orch.update_deployment_status(dep.id, s)
            got = orch.get_deployment(dep.id)
            statuses_tested.append(got.status == s if got else False)
        record(
            "MCO-138", "deployment supports all status transitions",
            True, all(statuses_tested),
            cause="all statuses applied",
            effect="all stored correctly",
            lesson="All status values must be accepted",
        )

    def test_failover_custom_params(self) -> None:
        orch = _make_orchestrator()
        rule = orch.create_failover_rule(
            "custom", "aws", "gcp",
            strategy="latency_based",
            threshold_ms=1000,
            max_retries=5,
            cooldown_sec=120,
        )
        record(
            "MCO-139", "failover rule stores custom parameters",
            True,
            rule.threshold_ms == 1000 and rule.max_retries == 5 and rule.cooldown_sec == 120,
            cause="custom params passed",
            effect="all stored correctly",
            lesson="Custom failover params must be preserved",
        )

    def test_sync_start_with_item_count(self) -> None:
        orch = _make_orchestrator()
        task = orch.start_sync("aws", "gcp", "storage", item_count=500)
        record(
            "MCO-140", "sync start stores initial item_count",
            500, task.items_synced,
            cause="item_count=500 at start",
            effect="items_synced=500",
            lesson="Initial item count must be stored",
        )

    def test_export_state_json_serializable(self) -> None:
        orch = _make_orchestrator()
        _add_provider(orch, "p1")
        _add_deployment(orch, "d1")
        orch.create_failover_rule("r1", "aws", "gcp")
        orch.start_sync("aws", "gcp", "storage")
        orch.record_cost("aws", "us-east-1", "ec2", 100.0)
        state = orch.export_state()
        try:
            json.dumps(state)
            serializable = True
        except (TypeError, ValueError):
            serializable = False
        record(
            "MCO-141", "export state is JSON serializable",
            True, serializable,
            cause="export_state called",
            effect="JSON serializable",
            lesson="Export must be JSON-safe",
        )

    def test_cost_period_fields(self) -> None:
        orch = _make_orchestrator()
        rec = orch.record_cost(
            "aws", "us-east-1", "ec2", 100.0,
            period_start="2025-01-01", period_end="2025-01-31",
        )
        record(
            "MCO-142", "cost record stores period fields",
            True, rec.period_start == "2025-01-01" and rec.period_end == "2025-01-31",
            cause="period fields passed",
            effect="period stored",
            lesson="Period metadata must be preserved",
        )
