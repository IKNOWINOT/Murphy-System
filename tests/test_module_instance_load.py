"""
Load tests for concurrent module instance spawning.

Validates thread-safety and performance under sustained concurrent
spawn/despawn operations.

Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · BSL 1.1
"""
from __future__ import annotations

import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from src.module_instance_manager import (
    InstanceState,
    ModuleInstanceManager,
    ResourceProfile,
    SpawnDecision,
)


class TestConcurrentSpawning:
    """Concurrent module-instance load scenarios."""

    def test_concurrent_spawn_50_instances(self) -> None:
        mgr = ModuleInstanceManager(max_instances_per_type=100)

        def _spawn(i: int) -> SpawnDecision:
            decision, _inst = mgr.spawn_instance(
                module_type="load-test-worker",
                config={"worker_index": i},
            )
            return decision

        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(_spawn, i) for i in range(50)]
            results = [f.result() for f in as_completed(futures)]

        assert len(results) == 50
        assert all(d == SpawnDecision.APPROVED for d in results)

    def test_concurrent_spawn_and_despawn_interleaved(self) -> None:
        mgr = ModuleInstanceManager(max_instances_per_type=50)

        instance_ids: list[str] = []
        for i in range(20):
            decision, inst = mgr.spawn_instance(
                module_type="interleave-worker",
                config={"idx": i},
            )
            assert decision == SpawnDecision.APPROVED
            assert inst is not None
            instance_ids.append(inst.instance_id)

        def _despawn(iid: str) -> bool:
            return mgr.despawn_instance(iid)

        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(_despawn, iid) for iid in instance_ids]
            results = [f.result() for f in as_completed(futures)]

        assert all(results), "Every despawn must succeed"

    def test_concurrent_mixed_operations(self) -> None:
        mgr = ModuleInstanceManager(max_instances_per_type=50)
        errors: list[str] = []

        def _spawn(i: int) -> None:
            try:
                mgr.spawn_instance(
                    module_type="mixed-op-worker",
                    config={"idx": i},
                )
            except Exception as exc:
                errors.append(f"spawn {i}: {exc}")

        def _list_instances() -> None:
            try:
                mgr.list_instances()
            except Exception as exc:
                errors.append(f"list: {exc}")

        def _status() -> None:
            try:
                mgr.get_status()
            except Exception as exc:
                errors.append(f"status: {exc}")

        with ThreadPoolExecutor(max_workers=15) as pool:
            futs: list[concurrent.futures.Future[None]] = []
            for i in range(30):
                futs.append(pool.submit(_spawn, i))
            for _ in range(10):
                futs.append(pool.submit(_list_instances))
            for _ in range(10):
                futs.append(pool.submit(_status))

            for f in as_completed(futs):
                f.result()

        assert errors == [], f"Unexpected errors: {errors}"
        assert len(mgr.list_instances()) >= 30

    def test_spawn_at_type_limit(self) -> None:
        mgr = ModuleInstanceManager(max_instances_per_type=10)

        def _spawn(_i: int) -> SpawnDecision:
            decision, _inst = mgr.spawn_instance(module_type="limited-type")
            return decision

        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(_spawn, i) for i in range(20)]
            decisions = [f.result() for f in as_completed(futures)]

        approved = [d for d in decisions if d == SpawnDecision.APPROVED]
        denied = [d for d in decisions if d != SpawnDecision.APPROVED]
        assert len(approved) == 10
        assert len(denied) == 10

    def test_concurrent_config_updates(self) -> None:
        mgr = ModuleInstanceManager()

        ids: list[str] = []
        for i in range(5):
            _, inst = mgr.spawn_instance(
                module_type="config-worker",
                config={"version": 0},
            )
            assert inst is not None
            ids.append(inst.instance_id)

        def _update(iid: str, version: int) -> bool:
            return mgr.update_instance_config(
                iid,
                {"version": version, "updated_by": f"thread-{version}"},
            )

        with ThreadPoolExecutor(max_workers=5) as pool:
            futs = [pool.submit(_update, iid, v) for v, iid in enumerate(ids, 1)]
            results = [f.result() for f in as_completed(futs)]

        assert all(results)
        for iid in ids:
            history = mgr.get_config_history(iid)
            assert len(history) >= 1, f"Instance {iid} has no config history"

    def test_bulk_despawn_under_load(self) -> None:
        mgr = ModuleInstanceManager(max_instances_per_type=50)

        ids: list[str] = []
        for i in range(30):
            _, inst = mgr.spawn_instance(
                module_type="bulk-worker",
                config={"idx": i},
            )
            assert inst is not None
            ids.append(inst.instance_id)

        result = mgr.bulk_despawn(ids)
        assert len(result["results"]) == 30
        assert all(result["results"].values())

    def test_audit_trail_under_concurrent_operations(self) -> None:
        mgr = ModuleInstanceManager(max_instances_per_type=50)
        spawned_ids: list[str] = []

        def _spawn(i: int) -> None:
            _, inst = mgr.spawn_instance(
                module_type="audit-worker",
                config={"idx": i},
            )
            if inst is not None:
                spawned_ids.append(inst.instance_id)

        def _despawn(iid: str) -> None:
            mgr.despawn_instance(iid)

        def _config_update(iid: str, v: int) -> None:
            mgr.update_instance_config(iid, {"v": v})

        # Phase 1: spawn 40 instances
        with ThreadPoolExecutor(max_workers=10) as pool:
            list(pool.map(_spawn, range(40)))

        ids_snapshot = list(spawned_ids)

        # Phase 2: mix despawn + config updates concurrently (60 ops)
        with ThreadPoolExecutor(max_workers=10) as pool:
            futs: list[concurrent.futures.Future[None]] = []
            for iid in ids_snapshot[:20]:
                futs.append(pool.submit(_despawn, iid))
            for idx, iid in enumerate(ids_snapshot[20:40]):
                futs.append(pool.submit(_config_update, iid, idx))
            for f in as_completed(futs):
                f.result()

        trail = mgr.get_audit_trail(limit=500)
        assert len(trail) >= 40, (
            f"Expected ≥40 audit entries, got {len(trail)}"
        )
