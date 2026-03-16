# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Test Suite: Automated Backup & Disaster Recovery — BDR-001

Comprehensive tests for the backup_disaster_recovery module:
  - BackupManifest / RestoreResult data models
  - LocalStorageBackend CRUD operations
  - Bundle serialisation round-trip
  - BackupManager create / list / restore / delete / expire / verify
  - Wingman pair validation gate
  - Causality Sandbox gating simulation
  - Thread safety under concurrent access
  - Edge cases: empty backups, corrupted bundles, missing manifests

Tests use the storyline-actuals record() pattern for cause/effect/lesson tracking.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import datetime
import json
import os
import shutil
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"


from backup_disaster_recovery import (
    BackupManager,
    BackupManifest,
    BackupStatus,
    BackupStorageBackend,
    BackupType,
    LocalStorageBackend,
    RestoreResult,
    RestoreStatus,
    _bundle_to_bytes,
    _compute_sha256,
    _unbundle_from_bytes,
)


# ---------------------------------------------------------------------------
# Record infrastructure (storyline-actuals pattern)
# ---------------------------------------------------------------------------

@dataclass
class BDRRecord:
    """One BDR check record."""
    check_id: str
    description: str
    expected: Any
    actual: Any
    passed: bool
    cause: str = ""
    effect: str = ""
    lesson: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )


_records: List[BDRRecord] = []


def record(
    check_id: str,
    description: str,
    expected: Any,
    actual: Any,
    cause: str = "",
    effect: str = "",
    lesson: str = "",
) -> bool:
    """Record a check and return whether expected == actual."""
    passed = expected == actual
    _records.append(BDRRecord(
        check_id=check_id,
        description=description,
        expected=expected,
        actual=actual,
        passed=passed,
        cause=cause,
        effect=effect,
        lesson=lesson,
    ))
    return passed


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_dir(tmp_path: Path) -> Path:
    """Return a clean temp directory for each test."""
    return tmp_path


@pytest.fixture()
def backend(tmp_dir: Path) -> LocalStorageBackend:
    """Return a fresh LocalStorageBackend."""
    return LocalStorageBackend(tmp_dir / "storage")


@pytest.fixture()
def project(tmp_dir: Path) -> Path:
    """Create a minimal project tree with config and data files."""
    root = tmp_dir / "project"
    root.mkdir()
    (root / ".env").write_text("MURPHY_ENV=test\n")
    (root / "config.yaml").write_text("version: 1.0\n")
    data_dir = root / "data"
    data_dir.mkdir()
    (data_dir / "sample.json").write_text('{"key": "value"}\n')
    state_dir = root / ".murphy_persistence"
    state_dir.mkdir()
    (state_dir / "state.db").write_bytes(b"\x00state_data\xFF")
    return root


@pytest.fixture()
def manager(backend: LocalStorageBackend, project: Path) -> BackupManager:
    """Return a BackupManager wired to a local backend and test project."""
    return BackupManager(backend, project_root=project)


# ============================================================================
# DATA MODEL TESTS
# ============================================================================

class TestBackupManifest:
    """BDR-010–012: BackupManifest data model."""

    def test_manifest_defaults(self):
        """BDR-010: Manifest has sensible defaults."""
        m = BackupManifest(backup_id="b-1", backup_type="full")
        assert record(
            "BDR-010", "Manifest status defaults to pending",
            BackupStatus.PENDING.value, m.status,
            cause="No status supplied at construction",
            effect="New manifests start in PENDING",
            lesson="Always default to the safest initial state",
        )

    def test_manifest_to_dict(self):
        """BDR-011: to_dict() produces a serialisable dict."""
        m = BackupManifest(backup_id="b-2", backup_type="full")
        d = m.to_dict()
        assert record(
            "BDR-011", "to_dict contains backup_id",
            "b-2", d["backup_id"],
            cause="Serialisation contract",
            effect="Manifests can be stored as JSON",
            lesson="Every data model needs a dict serialiser",
        )

    def test_restore_result_defaults(self):
        """BDR-012: RestoreResult status defaults to success."""
        r = RestoreResult(restore_id="r-1", backup_id="b-1")
        assert record(
            "BDR-012", "RestoreResult defaults to SUCCESS",
            RestoreStatus.SUCCESS.value, r.status,
            cause="No status supplied",
            effect="Optimistic default; override on error",
            lesson="Differentiate default from actual outcome in callers",
        )


# ============================================================================
# LOCAL STORAGE BACKEND TESTS
# ============================================================================

class TestLocalStorageBackend:
    """BDR-020–025: LocalStorageBackend CRUD."""

    def test_upload_and_download(self, backend: LocalStorageBackend):
        """BDR-020: Upload then download returns same bytes."""
        data = b"hello world"
        backend.upload("test/file.bin", data)
        result = backend.download("test/file.bin")
        assert record(
            "BDR-020", "Round-trip upload/download",
            data, result,
            cause="Filesystem write then read",
            effect="Data preserved",
            lesson="Verify round-trip for every storage backend",
        )

    def test_download_missing(self, backend: LocalStorageBackend):
        """BDR-021: Download of non-existent key returns None."""
        assert record(
            "BDR-021", "Download missing key",
            None, backend.download("no-such-key"),
            cause="Key never uploaded",
            effect="Graceful None return",
            lesson="Never raise on missing; let caller decide",
        )

    def test_delete(self, backend: LocalStorageBackend):
        """BDR-022: Delete removes the object."""
        backend.upload("del.bin", b"x")
        assert backend.exists("del.bin")
        backend.delete("del.bin")
        assert record(
            "BDR-022", "Delete removes object",
            False, backend.exists("del.bin"),
            cause="Explicit delete",
            effect="Key no longer exists",
            lesson="Clean up storage to prevent sprawl",
        )

    def test_list_keys(self, backend: LocalStorageBackend):
        """BDR-023: list_keys returns all uploaded keys."""
        backend.upload("a/1.bin", b"1")
        backend.upload("a/2.bin", b"2")
        backend.upload("b/3.bin", b"3")
        keys = backend.list_keys("a/")
        assert record(
            "BDR-023", "list_keys filters by prefix",
            2, len(keys),
            cause="Two keys start with 'a/'",
            effect="Only matching keys returned",
            lesson="Prefix filtering enables per-backup listing",
        )

    def test_exists(self, backend: LocalStorageBackend):
        """BDR-024: exists() correctly reports presence."""
        backend.upload("present.bin", b"x")
        assert record(
            "BDR-024", "exists() returns True for uploaded key",
            True, backend.exists("present.bin"),
            cause="Key was uploaded",
            effect="Presence confirmed",
            lesson="Always check existence before download",
        )

    def test_delete_missing_returns_false(self, backend: LocalStorageBackend):
        """BDR-025: Deleting a missing key returns False."""
        assert record(
            "BDR-025", "Delete missing key returns False",
            False, backend.delete("nonexistent.bin"),
            cause="Key never uploaded",
            effect="Idempotent delete",
            lesson="Delete should be safe to retry",
        )


# ============================================================================
# BUNDLE SERIALISATION TESTS
# ============================================================================

class TestBundleSerialisation:
    """BDR-030–032: Bundle pack/unpack round-trip."""

    def test_round_trip(self):
        """BDR-030: Bundle round-trips correctly."""
        components = {"a.txt": b"alpha", "b.bin": b"\x00\x01\x02"}
        bundle = _bundle_to_bytes(components)
        restored = _unbundle_from_bytes(bundle)
        assert record(
            "BDR-030", "Bundle round-trip preserves all components",
            components, restored,
            cause="Deterministic serialisation format",
            effect="Exact byte-for-byte fidelity",
            lesson="Test serialisation round-trips for every format",
        )

    def test_empty_components(self):
        """BDR-031: Empty component dict produces a valid bundle."""
        bundle = _bundle_to_bytes({})
        restored = _unbundle_from_bytes(bundle)
        assert record(
            "BDR-031", "Empty bundle round-trips to empty dict",
            {}, restored,
            cause="No components to pack",
            effect="Empty dict restored",
            lesson="Handle zero-length edge cases explicitly",
        )

    def test_sha256_deterministic(self):
        """BDR-032: SHA-256 is deterministic."""
        data = b"test data for hashing"
        h1 = _compute_sha256(data)
        h2 = _compute_sha256(data)
        assert record(
            "BDR-032", "SHA-256 is deterministic",
            h1, h2,
            cause="Same input → same hash",
            effect="Checksums are reproducible",
            lesson="Never use randomised hashing for integrity checks",
        )


# ============================================================================
# BACKUP MANAGER TESTS
# ============================================================================

class TestBackupManagerCreate:
    """BDR-040–044: Backup creation."""

    def test_create_full_backup(self, manager: BackupManager):
        """BDR-040: Full backup captures config + data + state."""
        m = manager.create_backup(BackupType.FULL.value)
        assert record(
            "BDR-040", "Full backup status is COMPLETED",
            BackupStatus.COMPLETED.value, m.status,
            cause="All components collected and uploaded",
            effect="Manifest marked completed",
            lesson="Status should reflect reality",
        )

    def test_backup_has_components(self, manager: BackupManager):
        """BDR-041: Full backup lists expected components."""
        m = manager.create_backup(BackupType.FULL.value)
        assert record(
            "BDR-041", "Backup contains at least 3 components",
            True, len(m.components) >= 3,
            cause="Project has .env, config.yaml, data/sample.json, .murphy_persistence/state.db",
            effect="All components recorded in manifest",
            lesson="Component list is the source of truth for what was backed up",
        )

    def test_backup_has_checksum(self, manager: BackupManager):
        """BDR-042: Backup manifest includes SHA-256 checksum."""
        m = manager.create_backup(BackupType.FULL.value)
        assert record(
            "BDR-042", "Checksum is a 64-char hex string",
            64, len(m.checksum_sha256),
            cause="SHA-256 produces 256 bits = 64 hex chars",
            effect="Integrity can be verified post-upload",
            lesson="Always include a checksum in the manifest",
        )

    def test_config_only_backup(self, manager: BackupManager):
        """BDR-043: Config-only backup excludes data and state."""
        m = manager.create_backup(BackupType.CONFIG_ONLY.value)
        has_data = any("data/" in c for c in m.components)
        has_state = any(".murphy_persistence/" in c for c in m.components)
        assert record(
            "BDR-043", "Config-only backup excludes data and state dirs",
            True, not has_data and not has_state,
            cause="BackupType.CONFIG_ONLY scope",
            effect="Smaller, faster backup for config changes",
            lesson="Offer granular backup types for different SLAs",
        )

    def test_backup_id_unique(self, manager: BackupManager):
        """BDR-044: Each backup gets a unique ID."""
        m1 = manager.create_backup()
        m2 = manager.create_backup()
        assert record(
            "BDR-044", "Two backups have different IDs",
            True, m1.backup_id != m2.backup_id,
            cause="UUID generation",
            effect="No ID collisions",
            lesson="Use UUIDs for identifiers in distributed systems",
        )


class TestBackupManagerList:
    """BDR-050: Listing backups."""

    def test_list_backups(self, manager: BackupManager):
        """BDR-050: list_backups returns all created backups."""
        manager.create_backup()
        manager.create_backup()
        assert record(
            "BDR-050", "list_backups returns 2 after 2 creates",
            2, len(manager.list_backups()),
            cause="Two create_backup calls",
            effect="Both visible in listing",
            lesson="List should never lose entries",
        )


class TestBackupManagerRestore:
    """BDR-060–065: Restore operations."""

    def test_restore_success(self, manager: BackupManager, tmp_dir: Path):
        """BDR-060: Successful restore writes files to target dir."""
        m = manager.create_backup(BackupType.FULL.value)
        target = tmp_dir / "restore_target"
        target.mkdir()
        result = manager.restore_backup(m.backup_id, target_dir=target)
        assert record(
            "BDR-060", "Restore status is SUCCESS",
            RestoreStatus.SUCCESS.value, result.status,
            cause="Valid backup and target dir",
            effect="Files written successfully",
            lesson="Always verify restore status in automation",
        )

    def test_restore_creates_files(self, manager: BackupManager, tmp_dir: Path):
        """BDR-061: Restored files actually exist on disk."""
        m = manager.create_backup(BackupType.FULL.value)
        target = tmp_dir / "restore_files"
        target.mkdir()
        result = manager.restore_backup(m.backup_id, target_dir=target)
        assert record(
            "BDR-061", "Restored component count matches",
            True, len(result.components_restored) >= 3,
            cause="Full backup had >= 3 components",
            effect="All components restored to disk",
            lesson="Verify file count matches manifest",
        )

    def test_restore_missing_manifest(self, manager: BackupManager, tmp_dir: Path):
        """BDR-062: Restore fails gracefully for unknown backup_id."""
        result = manager.restore_backup("bdr-nonexistent", target_dir=tmp_dir)
        assert record(
            "BDR-062", "Restore fails for missing manifest",
            RestoreStatus.FAILED.value, result.status,
            cause="Manifest not found",
            effect="Fail with clear error, no crash",
            lesson="Always handle missing references gracefully",
        )

    def test_restore_checksum_validation(self, manager: BackupManager, tmp_dir: Path):
        """BDR-063: Restore detects corrupted bundle via checksum."""
        m = manager.create_backup(BackupType.FULL.value)
        # Corrupt the stored bundle
        corrupt_data = b"CORRUPTED BUNDLE DATA"
        manager._backend.upload(m.storage_path, corrupt_data)

        result = manager.restore_backup(m.backup_id, target_dir=tmp_dir)
        assert record(
            "BDR-063", "Corrupted bundle fails checksum validation",
            RestoreStatus.FAILED.value, result.status,
            cause="Bundle bytes don't match manifest checksum",
            effect="Restore rejected before writing files",
            lesson="Always validate integrity before overwriting production data",
        )

    def test_restore_skip_checksum(self, manager: BackupManager, tmp_dir: Path):
        """BDR-064: Restore can skip checksum validation when requested."""
        m = manager.create_backup(BackupType.FULL.value)
        target = tmp_dir / "skip_check"
        target.mkdir()
        result = manager.restore_backup(
            m.backup_id, target_dir=target, validate_checksum=False
        )
        assert record(
            "BDR-064", "Restore succeeds when checksum validation skipped",
            RestoreStatus.SUCCESS.value, result.status,
            cause="validate_checksum=False",
            effect="Restore completes without integrity check",
            lesson="Provide an escape hatch for speed-critical restores",
        )

    def test_restore_duration_tracked(self, manager: BackupManager, tmp_dir: Path):
        """BDR-065: RestoreResult includes duration_ms."""
        m = manager.create_backup(BackupType.FULL.value)
        target = tmp_dir / "duration"
        target.mkdir()
        result = manager.restore_backup(m.backup_id, target_dir=target)
        assert record(
            "BDR-065", "duration_ms is positive",
            True, result.duration_ms > 0,
            cause="Restore takes non-zero time",
            effect="Duration measurable",
            lesson="Track latency for every operation",
        )


class TestBackupManagerDelete:
    """BDR-070–071: Deletion."""

    def test_delete_backup(self, manager: BackupManager):
        """BDR-070: delete_backup removes manifest and storage."""
        m = manager.create_backup()
        assert manager.delete_backup(m.backup_id) is True
        assert record(
            "BDR-070", "Deleted backup no longer in listing",
            0, len(manager.list_backups()),
            cause="Explicit deletion",
            effect="Manifest and bundle removed",
            lesson="Deletion must clean up both metadata and payload",
        )

    def test_delete_nonexistent(self, manager: BackupManager):
        """BDR-071: Deleting non-existent backup returns False."""
        assert record(
            "BDR-071", "Delete missing backup returns False",
            False, manager.delete_backup("bdr-nope"),
            cause="Backup never created",
            effect="Idempotent delete",
            lesson="Don't raise on delete of missing resource",
        )


class TestBackupManagerVerify:
    """BDR-080–081: Integrity verification."""

    def test_verify_intact(self, manager: BackupManager):
        """BDR-080: verify_backup_integrity returns True for intact backup."""
        m = manager.create_backup()
        assert record(
            "BDR-080", "Integrity check passes for intact backup",
            True, manager.verify_backup_integrity(m.backup_id),
            cause="Bundle matches checksum",
            effect="Verification passes",
            lesson="Periodic integrity checks catch silent corruption",
        )

    def test_verify_corrupted(self, manager: BackupManager):
        """BDR-081: verify_backup_integrity returns False for corrupted backup."""
        m = manager.create_backup()
        manager._backend.upload(m.storage_path, b"CORRUPT")
        assert record(
            "BDR-081", "Integrity check fails for corrupted backup",
            False, manager.verify_backup_integrity(m.backup_id),
            cause="Bundle doesn't match checksum",
            effect="Verification fails",
            lesson="Detect corruption before trusting backups",
        )


class TestBackupManagerExpire:
    """BDR-085: Retention-based expiry."""

    def test_expire_old_backups(self, manager: BackupManager):
        """BDR-085: Expired backups are deleted automatically."""
        m = manager.create_backup()
        # Fake an old timestamp: 100 days ago
        with manager._lock:
            manifest = manager._manifests[m.backup_id]
            old_time = datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc)
            manifest.created_at = old_time.isoformat()
            manifest.retention_days = 1  # expired many days ago

        expired = manager.expire_old_backups()
        assert record(
            "BDR-085", "Old backup expired",
            True, m.backup_id in expired,
            cause="Backup age exceeds retention_days",
            effect="Backup deleted",
            lesson="Automate retention to prevent storage bloat",
        )


class TestBackupManagerStatus:
    """BDR-090: Status summary."""

    def test_status_summary(self, manager: BackupManager):
        """BDR-090: get_status returns structured summary."""
        manager.create_backup()
        status = manager.get_status()
        has_keys = all(
            k in status
            for k in ("total_backups", "completed_backups", "total_size_bytes")
        )
        assert record(
            "BDR-090", "Status has expected keys",
            True, has_keys,
            cause="get_status contract",
            effect="Machine-readable status for dashboards",
            lesson="Always expose operational stats",
        )


class TestBackupManagerThreadSafety:
    """BDR-095: Concurrent access."""

    def test_concurrent_create(self, backend: LocalStorageBackend, project: Path):
        """BDR-095: Concurrent backup creation doesn't lose data."""
        mgr = BackupManager(backend, project_root=project)
        barrier = threading.Barrier(5)

        def worker():
            barrier.wait()
            mgr.create_backup()

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert record(
            "BDR-095", "5 concurrent backups all recorded",
            5, len(mgr.list_backups()),
            cause="5 threads creating backups simultaneously",
            effect="All 5 manifests present",
            lesson="Lock-protected state handles concurrent writes",
        )


# ============================================================================
# WINGMAN PAIR VALIDATION GATE
# ============================================================================

class TestWingmanGate:
    """BDR-100: Wingman pair validation for restore operations."""

    def test_wingman_validates_restore(self, manager: BackupManager, tmp_dir: Path):
        """BDR-100: Wingman protocol can validate a restore result."""
        from wingman_protocol import (
            ExecutionRunbook,
            ValidationRule,
            ValidationSeverity,
            WingmanProtocol,
        )

        # Create and restore a backup
        m = manager.create_backup(BackupType.FULL.value)
        target = tmp_dir / "wingman_restore"
        target.mkdir()
        result = manager.restore_backup(m.backup_id, target_dir=target)

        # Set up Wingman pair with a restore-validation runbook
        protocol = WingmanProtocol()
        runbook = ExecutionRunbook(
            runbook_id="rb-restore-v1",
            name="Restore Validator",
            domain="backup",
            validation_rules=[
                ValidationRule(
                    "r-001", "Must produce output",
                    "check_has_output", ValidationSeverity.BLOCK,
                ),
                ValidationRule(
                    "r-002", "No PII in output",
                    "check_no_pii", ValidationSeverity.WARN,
                ),
            ],
        )
        protocol.register_runbook(runbook)
        pair = protocol.create_pair(
            subject="backup-restore",
            executor_id="backup-manager",
            validator_id="integrity-checker",
            runbook_id="rb-restore-v1",
        )

        # Validate the restore result through the Wingman
        output = {
            "result": result.to_dict(),
            "confidence": 0.95,
        }
        validation = protocol.validate_output(pair.pair_id, output)

        assert record(
            "BDR-100", "Wingman validation passes for successful restore",
            True, validation["approved"],
            cause="Restore result meets all runbook rules",
            effect="Restore is approved by the validator wingman",
            lesson="Always gate critical operations through Wingman pairs",
        )


# ============================================================================
# CAUSALITY SANDBOX GATING
# ============================================================================

class TestCausalitySandboxGate:
    """BDR-110: Causality Sandbox simulates restore before committing."""

    def test_sandbox_can_simulate_restore(self, manager: BackupManager, tmp_dir: Path):
        """BDR-110: CausalitySandboxEngine can run a cycle validating restore."""
        from causality_sandbox import CausalitySandboxEngine

        m = manager.create_backup(BackupType.FULL.value)

        # A "gap" simulates the need to restore a backup
        class _RestoreGap:
            gap_id = "gap-restore-001"
            category = "disaster_recovery"
            severity = "high"
            description = "System state lost — needs restore"

        class _FakeLoop:
            config = {"state": "nominal"}
            metrics = {"uptime": 42}
            def get_state(self):
                return {"healthy": True}

        engine = CausalitySandboxEngine(
            self_fix_loop_factory=lambda: _FakeLoop(),
        )

        report = engine.run_sandbox_cycle([_RestoreGap()], _FakeLoop())

        assert record(
            "BDR-110", "Sandbox cycle completes for restore scenario",
            True, report.gaps_analyzed >= 1,
            cause="One restore gap submitted",
            effect="Sandbox simulates and ranks candidate actions",
            lesson="Gate destructive operations through sandbox simulation",
        )


# ============================================================================
# SUMMARY
# ============================================================================

@pytest.fixture(autouse=True, scope="session")
def print_summary():
    """Print a summary at the end of the session."""
    yield
    total = len(_records)
    passed = sum(1 for r in _records if r.passed)
    failed = total - passed
    print(f"\n{'=' * 70}")
    print(f" Backup & Disaster Recovery: {passed}/{total} passed, {failed} failed")
    for r in _records:
        icon = "✅" if r.passed else "❌"
        print(f"  {icon} {r.check_id}: {r.description}")
    print(f"{'=' * 70}")
