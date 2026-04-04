# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Comprehensive test suite for blockchain_audit_trail — BAT-001.

Uses the storyline-actuals ``record()`` pattern to capture every check
as an auditable BATRecord with cause / effect / lesson annotations.
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

from blockchain_audit_trail import (  # noqa: E402
    AuditEntry,
    Block,
    BlockchainAuditTrail,
    BlockStatus,
    ChainIntegrity,
    ChainStats,
    ChainVerification,
    EntryType,
    create_bat_api,
    gate_bat_in_sandbox,
    validate_wingman_pair,
)

# -- Record pattern --------------------------------------------------------


@dataclass
class BATRecord:
    """One BAT check record."""

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


_RESULTS: List[BATRecord] = []


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
        BATRecord(
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


# -- Helpers ---------------------------------------------------------------

def _make_engine(**kw: Any) -> BlockchainAuditTrail:
    return BlockchainAuditTrail(**kw)


def _flask_client(engine: BlockchainAuditTrail) -> Any:
    try:
        from flask import Flask
    except ImportError:
        return None
    app = Flask(__name__)
    app.register_blueprint(create_bat_api(engine))
    app.config["TESTING"] = True
    return app.test_client()


# -- Tests -----------------------------------------------------------------

class TestBlockchainAuditTrailCore:
    """Core engine tests."""

    def test_bat_001_record_single_entry(self) -> None:
        eng = _make_engine()
        e = eng.record_entry("api_call", "alice", "GET /users")
        ok = record("BAT-001", "record single entry",
                     True, isinstance(e, AuditEntry),
                     cause="record_entry called",
                     effect="AuditEntry returned",
                     lesson="Basic recording works")
        assert ok
        assert e.actor == "alice"
        assert e.action == "GET /users"

    def test_bat_002_entry_type_enum(self) -> None:
        eng = _make_engine()
        e = eng.record_entry(EntryType.admin_action, "bob", "reset_password")
        ok = record("BAT-002", "entry with enum type",
                     "admin_action", e.entry_type.value,
                     cause="EntryType enum passed",
                     effect="entry_type set correctly")
        assert ok

    def test_bat_003_auto_seal_on_capacity(self) -> None:
        eng = _make_engine(entries_per_block=5)
        for i in range(5):
            eng.record_entry("api_call", "user", f"action_{i}")
        ok = record("BAT-003", "auto seal at capacity",
                     1, eng.chain_length(),
                     cause="5 entries recorded with capacity 5",
                     effect="one block auto-sealed")
        assert ok
        assert eng.pending_count() == 0

    def test_bat_004_manual_seal(self) -> None:
        eng = _make_engine()
        eng.record_entry("api_call", "user", "test")
        blk = eng.seal_current_block()
        ok = record("BAT-004", "manual seal",
                     True, blk is not None,
                     cause="seal_current_block called",
                     effect="block returned")
        assert ok
        assert blk.status == BlockStatus.sealed

    def test_bat_005_seal_empty_returns_none(self) -> None:
        eng = _make_engine()
        blk = eng.seal_current_block()
        ok = record("BAT-005", "seal with no pending",
                     True, blk is None,
                     cause="no pending entries",
                     effect="None returned")
        assert ok

    def test_bat_006_chain_hashes_link(self) -> None:
        eng = _make_engine(entries_per_block=2)
        for i in range(4):
            eng.record_entry("api_call", "user", f"act_{i}")
        ok = record("BAT-006", "chain has 2 blocks",
                     2, eng.chain_length(),
                     cause="4 entries with cap 2",
                     effect="2 sealed blocks")
        assert ok
        b0 = eng.get_block_by_index(0)
        b1 = eng.get_block_by_index(1)
        assert b1.previous_hash == b0.block_hash

    def test_bat_007_verify_valid_chain(self) -> None:
        eng = _make_engine(entries_per_block=2)
        for i in range(6):
            eng.record_entry("api_call", "user", f"a{i}")
        v = eng.verify_chain()
        ok = record("BAT-007", "verify valid chain",
                     "valid", v.integrity.value,
                     cause="3 blocks sealed properly",
                     effect="chain verified as valid")
        assert ok
        assert v.verified_blocks == 3

    def test_bat_008_verify_empty_chain(self) -> None:
        eng = _make_engine()
        v = eng.verify_chain()
        ok = record("BAT-008", "verify empty chain",
                     "empty", v.integrity.value,
                     cause="no blocks",
                     effect="empty status")
        assert ok

    def test_bat_009_tamper_detection(self) -> None:
        eng = _make_engine(entries_per_block=2)
        for i in range(4):
            eng.record_entry("api_call", "user", f"a{i}")
        # Tamper with block 0's hash
        with eng._lock:
            eng._chain[0].block_hash = "deadbeef" * 8
        v = eng.verify_chain()
        ok = record("BAT-009", "detect tampered block",
                     "broken", v.integrity.value,
                     cause="block 0 hash corrupted",
                     effect="chain detected as broken")
        assert ok

    def test_bat_010_get_block_by_id(self) -> None:
        eng = _make_engine()
        eng.record_entry("api_call", "user", "test")
        blk = eng.seal_current_block()
        found = eng.get_block(blk.block_id)
        ok = record("BAT-010", "get block by ID",
                     blk.block_id, found.block_id if found else None,
                     cause="block sealed and queried by ID",
                     effect="same block returned")
        assert ok

    def test_bat_011_get_block_by_index(self) -> None:
        eng = _make_engine()
        eng.record_entry("api_call", "user", "test")
        blk = eng.seal_current_block()
        found = eng.get_block_by_index(0)
        ok = record("BAT-011", "get block by index",
                     blk.block_id, found.block_id if found else None,
                     cause="get_block_by_index(0)",
                     effect="genesis block returned")
        assert ok

    def test_bat_012_get_block_invalid_index(self) -> None:
        eng = _make_engine()
        found = eng.get_block_by_index(999)
        ok = record("BAT-012", "invalid index returns None",
                     True, found is None,
                     cause="no such index",
                     effect="None returned")
        assert ok

    def test_bat_013_list_blocks_pagination(self) -> None:
        eng = _make_engine(entries_per_block=1)
        for i in range(5):
            eng.record_entry("api_call", "user", f"a{i}")
        page = eng.list_blocks(limit=2, offset=1)
        ok = record("BAT-013", "list blocks pagination",
                     2, len(page),
                     cause="5 blocks, limit=2, offset=1",
                     effect="2 blocks returned")
        assert ok

    def test_bat_014_search_by_actor(self) -> None:
        eng = _make_engine()
        eng.record_entry("api_call", "alice", "login")
        eng.record_entry("api_call", "bob", "logout")
        eng.seal_current_block()
        results = eng.search_entries(actor="alice")
        ok = record("BAT-014", "search by actor",
                     1, len(results),
                     cause="1 alice entry, 1 bob entry",
                     effect="only alice found")
        assert ok

    def test_bat_015_search_by_entry_type(self) -> None:
        eng = _make_engine()
        eng.record_entry("api_call", "user", "test")
        eng.record_entry("admin_action", "admin", "reset")
        eng.seal_current_block()
        results = eng.search_entries(entry_type="admin_action")
        ok = record("BAT-015", "search by entry type",
                     1, len(results),
                     cause="1 api_call + 1 admin_action",
                     effect="only admin found")
        assert ok

    def test_bat_016_search_limit(self) -> None:
        eng = _make_engine()
        for i in range(10):
            eng.record_entry("api_call", "user", f"a{i}")
        eng.seal_current_block()
        results = eng.search_entries(limit=3)
        ok = record("BAT-016", "search with limit",
                     3, len(results),
                     cause="10 entries, limit=3",
                     effect="3 returned")
        assert ok

    def test_bat_017_stats(self) -> None:
        eng = _make_engine(entries_per_block=3)
        for i in range(6):
            eng.record_entry("api_call", "user", f"a{i}")
        s = eng.get_stats()
        ok = record("BAT-017", "stats accuracy",
                     True, isinstance(s, ChainStats) and s.total_blocks == 2,
                     cause="6 entries, 3 per block",
                     effect="2 blocks, 6 entries")
        assert ok
        assert s.total_entries == 6

    def test_bat_018_export_chain(self) -> None:
        eng = _make_engine(entries_per_block=2)
        eng.record_entry("api_call", "user", "a")
        eng.record_entry("api_call", "user", "b")
        data = eng.export_chain()
        ok = record("BAT-018", "export chain",
                     1, len(data),
                     cause="1 sealed block",
                     effect="list of 1 dict")
        assert ok
        assert "block_hash" in data[0]

    def test_bat_019_entry_details(self) -> None:
        eng = _make_engine()
        e = eng.record_entry("config_change", "admin", "update_config",
                             resource="/api/config",
                             details={"key": "rate_limit", "value": 100},
                             ip_address="10.0.0.1",
                             outcome="success")
        ok = record("BAT-019", "entry with full details",
                     True, e.details.get("key") == "rate_limit",
                     cause="details dict passed",
                     effect="stored in entry")
        assert ok
        assert e.ip_address == "10.0.0.1"
        assert e.outcome == "success"

    def test_bat_020_capacity_eviction(self) -> None:
        eng = _make_engine(max_blocks=3, entries_per_block=1)
        for i in range(5):
            eng.record_entry("api_call", "user", f"a{i}")
        ok = record("BAT-020", "capacity eviction",
                     3, eng.chain_length(),
                     cause="5 blocks sealed, max=3",
                     effect="oldest evicted, 3 remain")
        assert ok

    def test_bat_021_entry_to_dict(self) -> None:
        e = AuditEntry(entry_type=EntryType.security_event,
                       actor="guard", action="block_ip")
        d = e.to_dict()
        ok = record("BAT-021", "entry to_dict",
                     "security_event", d["entry_type"],
                     cause="to_dict called",
                     effect="enum serialized to string")
        assert ok

    def test_bat_022_block_to_dict(self) -> None:
        eng = _make_engine()
        eng.record_entry("api_call", "user", "test")
        blk = eng.seal_current_block()
        d = blk.to_dict()
        ok = record("BAT-022", "block to_dict",
                     "sealed", d["status"],
                     cause="to_dict on sealed block",
                     effect="status serialized correctly")
        assert ok
        assert isinstance(d["entries"], list)


class TestBlockchainAuditTrailThreadSafety:
    """Thread-safety tests."""

    def test_bat_030_concurrent_recording(self) -> None:
        eng = _make_engine(entries_per_block=50)
        errors: List[str] = []

        def writer(n: int) -> None:
            try:
                for i in range(20):
                    eng.record_entry("api_call", f"thread_{n}", f"op_{i}")
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        eng.seal_current_block()

        total = sum(len(b.entries) for b in eng._chain)
        ok = record("BAT-030", "concurrent recording",
                     100, total,
                     cause="5 threads × 20 entries",
                     effect="all 100 entries recorded")
        assert ok
        assert not errors

    def test_bat_031_concurrent_seal_and_verify(self) -> None:
        eng = _make_engine(entries_per_block=5)
        errors: List[str] = []

        def write_entries() -> None:
            try:
                for i in range(25):
                    eng.record_entry("api_call", "writer", f"w{i}")
            except Exception as exc:
                errors.append(str(exc))

        def verify_loop() -> None:
            try:
                for _ in range(10):
                    eng.verify_chain()
            except Exception as exc:
                errors.append(str(exc))

        t1 = threading.Thread(target=write_entries)
        t2 = threading.Thread(target=verify_loop)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        ok = record("BAT-031", "concurrent seal and verify",
                     True, not errors,
                     cause="writer + verifier in parallel",
                     effect="no errors")
        assert ok


class TestBlockchainAuditTrailWingman:
    """Wingman pair validation tests."""

    def test_bat_040_wingman_pass(self) -> None:
        result = validate_wingman_pair(["a", "b"], ["a", "b"])
        ok = record("BAT-040", "wingman pass",
                     True, result["passed"],
                     cause="matching pairs",
                     effect="validation passes")
        assert ok

    def test_bat_041_wingman_empty_storyline(self) -> None:
        result = validate_wingman_pair([], ["a"])
        ok = record("BAT-041", "wingman empty storyline",
                     False, result["passed"],
                     cause="empty storyline",
                     effect="validation fails")
        assert ok

    def test_bat_042_wingman_empty_actuals(self) -> None:
        result = validate_wingman_pair(["a"], [])
        ok = record("BAT-042", "wingman empty actuals",
                     False, result["passed"],
                     cause="empty actuals",
                     effect="validation fails")
        assert ok

    def test_bat_043_wingman_length_mismatch(self) -> None:
        result = validate_wingman_pair(["a", "b"], ["a"])
        ok = record("BAT-043", "wingman length mismatch",
                     False, result["passed"],
                     cause="different lengths",
                     effect="validation fails")
        assert ok

    def test_bat_044_wingman_value_mismatch(self) -> None:
        result = validate_wingman_pair(["a", "b"], ["a", "c"])
        ok = record("BAT-044", "wingman value mismatch",
                     False, result["passed"],
                     cause="b != c at index 1",
                     effect="fails with mismatch indices")
        assert ok


class TestBlockchainAuditTrailSandbox:
    """Causality Sandbox gating tests."""

    def test_bat_050_sandbox_pass(self) -> None:
        ctx = {"actor": "admin", "action": "test", "entry_type": "api_call"}
        result = gate_bat_in_sandbox(ctx)
        ok = record("BAT-050", "sandbox pass",
                     True, result["passed"],
                     cause="all required keys present",
                     effect="gate passes")
        assert ok

    def test_bat_051_sandbox_missing_key(self) -> None:
        ctx = {"actor": "admin"}
        result = gate_bat_in_sandbox(ctx)
        ok = record("BAT-051", "sandbox missing keys",
                     False, result["passed"],
                     cause="action and entry_type missing",
                     effect="gate fails")
        assert ok

    def test_bat_052_sandbox_empty_actor(self) -> None:
        ctx = {"actor": "", "action": "test", "entry_type": "api_call"}
        result = gate_bat_in_sandbox(ctx)
        ok = record("BAT-052", "sandbox empty actor",
                     False, result["passed"],
                     cause="actor is empty string",
                     effect="gate fails")
        assert ok

    def test_bat_053_sandbox_invalid_entry_type(self) -> None:
        ctx = {"actor": "admin", "action": "test", "entry_type": "bogus"}
        result = gate_bat_in_sandbox(ctx)
        ok = record("BAT-053", "sandbox invalid entry_type",
                     False, result["passed"],
                     cause="bogus not in EntryType",
                     effect="gate fails")
        assert ok


class TestBlockchainAuditTrailAPI:
    """Flask API endpoint tests."""

    def test_bat_060_api_health(self) -> None:
        eng = _make_engine()
        client = _flask_client(eng)
        if not client:
            return
        resp = client.get("/api/bat/health")
        ok = record("BAT-060", "API health",
                     200, resp.status_code,
                     cause="GET /api/bat/health",
                     effect="200 healthy")
        assert ok
        data = resp.get_json()
        assert data["module"] == "BAT-001"

    def test_bat_061_api_record_entry(self) -> None:
        eng = _make_engine()
        client = _flask_client(eng)
        if not client:
            return
        resp = client.post("/api/bat/entries", json={
            "entry_type": "api_call",
            "actor": "alice",
            "action": "GET /status",
        })
        ok = record("BAT-061", "API record entry",
                     201, resp.status_code,
                     cause="POST /api/bat/entries",
                     effect="201 created")
        assert ok

    def test_bat_062_api_record_entry_missing_field(self) -> None:
        eng = _make_engine()
        client = _flask_client(eng)
        if not client:
            return
        resp = client.post("/api/bat/entries", json={"entry_type": "api_call"})
        ok = record("BAT-062", "API missing field",
                     400, resp.status_code,
                     cause="actor and action missing",
                     effect="400 error")
        assert ok

    def test_bat_063_api_record_entry_invalid_type(self) -> None:
        eng = _make_engine()
        client = _flask_client(eng)
        if not client:
            return
        resp = client.post("/api/bat/entries", json={
            "entry_type": "invalid",
            "actor": "bob",
            "action": "test",
        })
        ok = record("BAT-063", "API invalid entry_type",
                     400, resp.status_code,
                     cause="invalid not in EntryType",
                     effect="400 error")
        assert ok

    def test_bat_064_api_seal_block(self) -> None:
        eng = _make_engine()
        client = _flask_client(eng)
        if not client:
            return
        client.post("/api/bat/entries", json={
            "entry_type": "api_call",
            "actor": "user",
            "action": "test",
        })
        resp = client.post("/api/bat/blocks/seal")
        ok = record("BAT-064", "API seal block",
                     201, resp.status_code,
                     cause="POST /api/bat/blocks/seal",
                     effect="201 block sealed")
        assert ok

    def test_bat_065_api_seal_empty(self) -> None:
        eng = _make_engine()
        client = _flask_client(eng)
        if not client:
            return
        resp = client.post("/api/bat/blocks/seal")
        ok = record("BAT-065", "API seal empty",
                     400, resp.status_code,
                     cause="no pending entries",
                     effect="400 error")
        assert ok

    def test_bat_066_api_list_blocks(self) -> None:
        eng = _make_engine(entries_per_block=1)
        client = _flask_client(eng)
        if not client:
            return
        for _ in range(3):
            client.post("/api/bat/entries", json={
                "entry_type": "api_call", "actor": "u", "action": "a",
            })
        resp = client.get("/api/bat/blocks")
        ok = record("BAT-066", "API list blocks",
                     200, resp.status_code,
                     cause="GET /api/bat/blocks",
                     effect="200 with blocks")
        assert ok
        assert len(resp.get_json()) == 3

    def test_bat_067_api_get_block(self) -> None:
        eng = _make_engine()
        client = _flask_client(eng)
        if not client:
            return
        client.post("/api/bat/entries", json={
            "entry_type": "api_call", "actor": "u", "action": "a",
        })
        seal_resp = client.post("/api/bat/blocks/seal")
        block_id = seal_resp.get_json()["block_id"]
        resp = client.get(f"/api/bat/blocks/{block_id}")
        ok = record("BAT-067", "API get block by ID",
                     200, resp.status_code,
                     cause="GET /api/bat/blocks/<id>",
                     effect="200 with block data")
        assert ok

    def test_bat_068_api_get_block_not_found(self) -> None:
        eng = _make_engine()
        client = _flask_client(eng)
        if not client:
            return
        resp = client.get("/api/bat/blocks/nonexistent")
        ok = record("BAT-068", "API block not found",
                     404, resp.status_code,
                     cause="invalid block ID",
                     effect="404 error")
        assert ok

    def test_bat_069_api_get_block_by_index(self) -> None:
        eng = _make_engine()
        client = _flask_client(eng)
        if not client:
            return
        client.post("/api/bat/entries", json={
            "entry_type": "api_call", "actor": "u", "action": "a",
        })
        client.post("/api/bat/blocks/seal")
        resp = client.get("/api/bat/blocks/index/0")
        ok = record("BAT-069", "API get block by index",
                     200, resp.status_code,
                     cause="GET /api/bat/blocks/index/0",
                     effect="200 with genesis block")
        assert ok

    def test_bat_070_api_verify(self) -> None:
        eng = _make_engine()
        client = _flask_client(eng)
        if not client:
            return
        client.post("/api/bat/entries", json={
            "entry_type": "api_call", "actor": "u", "action": "a",
        })
        client.post("/api/bat/blocks/seal")
        resp = client.get("/api/bat/verify")
        ok = record("BAT-070", "API verify chain",
                     200, resp.status_code,
                     cause="GET /api/bat/verify",
                     effect="200 with valid integrity")
        assert ok
        assert resp.get_json()["integrity"] == "valid"

    def test_bat_071_api_search(self) -> None:
        eng = _make_engine()
        client = _flask_client(eng)
        if not client:
            return
        client.post("/api/bat/entries", json={
            "entry_type": "api_call", "actor": "alice", "action": "login",
        })
        client.post("/api/bat/entries", json={
            "entry_type": "admin_action", "actor": "bob", "action": "reset",
        })
        client.post("/api/bat/blocks/seal")
        resp = client.get("/api/bat/entries/search?actor=alice")
        ok = record("BAT-071", "API search entries",
                     200, resp.status_code,
                     cause="search by actor=alice",
                     effect="1 result returned")
        assert ok
        assert len(resp.get_json()) == 1

    def test_bat_072_api_export(self) -> None:
        eng = _make_engine()
        client = _flask_client(eng)
        if not client:
            return
        client.post("/api/bat/entries", json={
            "entry_type": "api_call", "actor": "u", "action": "a",
        })
        client.post("/api/bat/blocks/seal")
        resp = client.get("/api/bat/export")
        ok = record("BAT-072", "API export chain",
                     200, resp.status_code,
                     cause="GET /api/bat/export",
                     effect="200 with chain data")
        assert ok
        assert len(resp.get_json()) == 1

    def test_bat_073_api_stats(self) -> None:
        eng = _make_engine()
        client = _flask_client(eng)
        if not client:
            return
        client.post("/api/bat/entries", json={
            "entry_type": "api_call", "actor": "u", "action": "a",
        })
        client.post("/api/bat/blocks/seal")
        resp = client.get("/api/bat/stats")
        ok = record("BAT-073", "API stats",
                     200, resp.status_code,
                     cause="GET /api/bat/stats",
                     effect="200 with stats")
        assert ok
        data = resp.get_json()
        assert data["total_blocks"] == 1


class TestBlockchainAuditTrailEdgeCases:
    """Edge case and boundary tests."""

    def test_bat_080_search_empty_chain(self) -> None:
        eng = _make_engine()
        results = eng.search_entries(actor="nobody")
        ok = record("BAT-080", "search empty chain",
                     0, len(results),
                     cause="no blocks exist",
                     effect="empty list")
        assert ok

    def test_bat_081_multiple_entry_types(self) -> None:
        eng = _make_engine()
        for t in EntryType:
            eng.record_entry(t, "user", "test")
        eng.seal_current_block()
        s = eng.get_stats()
        ok = record("BAT-081", "all entry types",
                     len(EntryType), len(s.entry_type_counts),
                     cause="one entry per type",
                     effect="all types counted")
        assert ok

    def test_bat_082_chain_verification_serialization(self) -> None:
        v = ChainVerification(integrity=ChainIntegrity.valid,
                              total_blocks=5, verified_blocks=5,
                              message="ok")
        d = v.to_dict()
        ok = record("BAT-082", "verification to_dict",
                     "valid", d["integrity"],
                     cause="to_dict on verification",
                     effect="enum serialized")
        assert ok

    def test_bat_083_chain_stats_serialization(self) -> None:
        s = ChainStats(total_blocks=3, total_entries=30)
        d = s.to_dict()
        ok = record("BAT-083", "stats to_dict",
                     3, d["total_blocks"],
                     cause="to_dict on stats",
                     effect="correct values")
        assert ok

    def test_bat_084_search_by_resource(self) -> None:
        eng = _make_engine()
        eng.record_entry("api_call", "user", "get",
                         resource="/api/users")
        eng.record_entry("api_call", "user", "get",
                         resource="/api/config")
        eng.seal_current_block()
        results = eng.search_entries(resource="/api/users")
        ok = record("BAT-084", "search by resource",
                     1, len(results),
                     cause="1 matching resource",
                     effect="1 result")
        assert ok

    def test_bat_085_search_by_action(self) -> None:
        eng = _make_engine()
        eng.record_entry("api_call", "user", "login")
        eng.record_entry("api_call", "user", "logout")
        eng.seal_current_block()
        results = eng.search_entries(action="login")
        ok = record("BAT-085", "search by action",
                     1, len(results),
                     cause="1 login action",
                     effect="1 result")
        assert ok

    def test_bat_086_pending_count(self) -> None:
        eng = _make_engine()
        eng.record_entry("api_call", "u", "a")
        eng.record_entry("api_call", "u", "b")
        ok = record("BAT-086", "pending count",
                     2, eng.pending_count(),
                     cause="2 entries not yet sealed",
                     effect="pending_count=2")
        assert ok

    def test_bat_087_sandbox_empty_action(self) -> None:
        ctx = {"actor": "admin", "action": "", "entry_type": "api_call"}
        result = gate_bat_in_sandbox(ctx)
        ok = record("BAT-087", "sandbox empty action",
                     False, result["passed"],
                     cause="action is empty",
                     effect="gate fails")
        assert ok

    def test_bat_088_large_details_payload(self) -> None:
        eng = _make_engine()
        big = {f"key_{i}": f"val_{i}" for i in range(100)}
        e = eng.record_entry("api_call", "user", "bulk",
                             details=big)
        ok = record("BAT-088", "large details payload",
                     100, len(e.details),
                     cause="100-key details dict",
                     effect="all keys stored")
        assert ok

    def test_bat_089_block_previous_hash_genesis(self) -> None:
        eng = _make_engine()
        eng.record_entry("api_call", "u", "a")
        blk = eng.seal_current_block()
        ok = record("BAT-089", "genesis previous_hash",
                     "0" * 64, blk.previous_hash,
                     cause="first block in chain",
                     effect="previous_hash is all zeros")
        assert ok

    def test_bat_090_data_access_entry(self) -> None:
        eng = _make_engine()
        e = eng.record_entry("data_access", "analyst", "export_report",
                             resource="sales_db",
                             outcome="success")
        ok = record("BAT-090", "data_access entry type",
                     "data_access", e.entry_type.value,
                     cause="data_access type used",
                     effect="properly categorized")
        assert ok
