# SPDX-License-Identifier: LicenseRef-BSL-1.1
# © 2020 Inoni Limited Liability Company — Creator: Corey Post — BSL 1.1
"""Tests for murphy_backup — OS-level snapshot backup manager."""

from __future__ import annotations

import datetime
import json
import pathlib
import sys
from unittest import mock

import pytest

# ---------------------------------------------------------------------------
# PYTHONPATH
# ---------------------------------------------------------------------------
_MURPHYOS = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_MURPHYOS / "userspace" / "murphy-backup"))

from murphy_backup import (
    BackupConfig,
    BackupError,
    BackupInfo,
    BackupManifest,
    BackupStatus,
    BackupStrategy,
    MurphyBackup,
    _load_config,
    _sha3_256_file,
)


# ── helpers ───────────────────────────────────────────────────────────────
def _make_manifest(backup_id: str = "test-backup-001", **overrides) -> dict:
    base = {
        "backup_id": backup_id,
        "label": "test",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "strategy": "tar",
        "status": "completed",
        "targets": ["/murphy"],
        "file_list": ["data.tar.gz"],
        "sha3_checksums": {"data.tar.gz": "abc123"},
        "size_bytes": 4096,
        "db_included": False,
        "db_engine": "",
        "encryption_enabled": False,
    }
    base.update(overrides)
    return base


# ── initialisation ────────────────────────────────────────────────────────
class TestMurphyBackupInit:
    @mock.patch.object(pathlib.Path, "mkdir")
    @mock.patch("murphy_backup._load_config", return_value=BackupConfig())
    def test_init_creates_backup_directory(self, _cfg, mock_mkdir):
        MurphyBackup()
        mock_mkdir.assert_called()

    @mock.patch.object(pathlib.Path, "mkdir", side_effect=OSError("perm denied"))
    @mock.patch("murphy_backup._load_config", return_value=BackupConfig())
    def test_init_raises_on_mkdir_failure(self, _cfg, _mkdir):
        with pytest.raises(BackupError):
            MurphyBackup()


# ── create_backup with tar ────────────────────────────────────────────────
class TestCreateBackup:
    @mock.patch("murphy_backup._dump_database", return_value=None)
    @mock.patch("murphy_backup._detect_db_engine", return_value=("", ""))
    @mock.patch("murphy_backup._backup_tar", return_value=["archive.tar.gz"])
    @mock.patch("murphy_backup._sha3_256_file", return_value="deadbeef" * 8)
    @mock.patch("murphy_backup._dir_size", return_value=8192)
    @mock.patch.object(pathlib.Path, "rglob", return_value=[])
    @mock.patch.object(pathlib.Path, "write_text")
    @mock.patch.object(pathlib.Path, "mkdir")
    @mock.patch("murphy_backup._load_config", return_value=BackupConfig())
    def test_create_backup_tar_returns_backup_id(self, *_mocks):
        b = MurphyBackup()
        backup_id = b.create_backup(label="daily", strategy="tar")
        assert isinstance(backup_id, str)
        assert "daily" in backup_id

    @mock.patch("murphy_backup._is_btrfs", return_value=True)
    @mock.patch("murphy_backup.shutil.which", return_value="/usr/bin/btrfs")
    @mock.patch("murphy_backup._dump_database", return_value=None)
    @mock.patch("murphy_backup._detect_db_engine", return_value=("", ""))
    @mock.patch("murphy_backup._backup_btrfs", return_value=["snap1"])
    @mock.patch("murphy_backup._sha3_256_file", return_value="aabbcc" * 10 + "dd")
    @mock.patch("murphy_backup._dir_size", return_value=4096)
    @mock.patch.object(pathlib.Path, "rglob", return_value=[])
    @mock.patch.object(pathlib.Path, "write_text")
    @mock.patch.object(pathlib.Path, "mkdir")
    @mock.patch("murphy_backup._load_config", return_value=BackupConfig())
    def test_create_backup_auto_detects_btrfs(self, *_mocks):
        b = MurphyBackup()
        backup_id = b.create_backup(label="auto-test", strategy="btrfs")
        assert isinstance(backup_id, str)


# ── list_backups ──────────────────────────────────────────────────────────
class TestListBackups:
    @mock.patch.object(pathlib.Path, "mkdir")
    @mock.patch("murphy_backup._load_config", return_value=BackupConfig())
    def test_list_backups_reads_manifests(self, _cfg, _mkdir):
        manifest_data = _make_manifest()
        manifest_file = mock.MagicMock()
        manifest_file.exists.return_value = True
        manifest_file.read_text.return_value = json.dumps(manifest_data)

        entry = mock.MagicMock()
        entry.is_dir.return_value = True
        entry.name = "test-backup-001"
        entry.__truediv__ = mock.MagicMock(return_value=manifest_file)

        b = MurphyBackup()
        with mock.patch.object(pathlib.Path, "exists", return_value=True):
            with mock.patch.object(pathlib.Path, "iterdir", return_value=[entry]):
                results = b.list_backups()
        assert len(results) >= 1
        assert isinstance(results[0], BackupInfo)

    @mock.patch.object(pathlib.Path, "mkdir")
    @mock.patch("murphy_backup._load_config", return_value=BackupConfig())
    def test_list_backups_empty_when_no_dir(self, _cfg, _mkdir):
        b = MurphyBackup()
        with mock.patch.object(pathlib.Path, "exists", return_value=False):
            results = b.list_backups()
        assert results == []


# ── verify_backup ─────────────────────────────────────────────────────────
class TestVerifyBackup:
    @mock.patch.object(pathlib.Path, "mkdir")
    @mock.patch("murphy_backup._load_config", return_value=BackupConfig())
    def test_verify_backup_passes_matching_checksums(self, _cfg, _mkdir):
        checksum = "a1b2c3d4e5f6" * 5 + "ab"
        manifest_data = _make_manifest(
            sha3_checksums={"data.tar.gz": checksum},
            file_list=["data.tar.gz"],
        )
        b = MurphyBackup()
        with mock.patch.object(b, "_load_manifest", return_value=BackupManifest.from_dict(manifest_data)):
            with mock.patch("murphy_backup._sha3_256_file", return_value=checksum):
                with mock.patch.object(pathlib.Path, "exists", return_value=True):
                    assert b.verify_backup("test-backup-001") is True

    @mock.patch.object(pathlib.Path, "mkdir")
    @mock.patch("murphy_backup._load_config", return_value=BackupConfig())
    def test_verify_backup_raises_on_mismatch(self, _cfg, _mkdir):
        manifest_data = _make_manifest(
            sha3_checksums={"data.tar.gz": "expected_hash"},
            file_list=["data.tar.gz"],
        )
        b = MurphyBackup()
        with mock.patch.object(b, "_load_manifest", return_value=BackupManifest.from_dict(manifest_data)):
            with mock.patch("murphy_backup._sha3_256_file", return_value="wrong_hash"):
                with mock.patch.object(pathlib.Path, "exists", return_value=True):
                    with pytest.raises(BackupError):
                        b.verify_backup("test-backup-001")


# ── prune_backups ─────────────────────────────────────────────────────────
class TestPruneBackups:
    @mock.patch.object(pathlib.Path, "mkdir")
    @mock.patch("murphy_backup._load_config", return_value=BackupConfig())
    def test_prune_backups_retention_logic(self, _cfg, _mkdir):
        now = datetime.datetime.now(datetime.timezone.utc)
        backups = []
        for i in range(10):
            ts = (now - datetime.timedelta(days=i)).isoformat()
            backups.append(BackupInfo(
                backup_id=f"backup-{i}",
                label="auto",
                timestamp=ts,
                strategy="tar",
                status="completed",
                size_bytes=1024,
            ))
        b = MurphyBackup()
        with mock.patch.object(b, "list_backups", return_value=backups):
            with mock.patch("shutil.rmtree"):
                pruned = b.prune_backups(keep_daily=3, keep_weekly=1, keep_monthly=1)
        assert isinstance(pruned, list)


# ── restore_backup ────────────────────────────────────────────────────────
class TestRestoreBackup:
    @mock.patch.object(pathlib.Path, "mkdir")
    @mock.patch("murphy_backup._load_config", return_value=BackupConfig())
    def test_restore_backup_runs_hooks(self, _cfg, _mkdir):
        manifest_data = _make_manifest()
        b = MurphyBackup()
        b._cfg.pre_hooks = ["echo pre"]
        b._cfg.post_hooks = ["echo post"]
        with mock.patch.object(b, "_load_manifest", return_value=BackupManifest.from_dict(manifest_data)):
            with mock.patch("murphy_backup._run_hook") as mock_hook:
                with mock.patch.object(b, "_restore_tar"):
                    b.restore_backup("test-backup-001")
        assert mock_hook.call_count >= 2


# ── export_backup ─────────────────────────────────────────────────────────
class TestExportBackup:
    @mock.patch("murphy_backup._run")
    @mock.patch("shutil.copytree")
    @mock.patch.object(pathlib.Path, "mkdir")
    @mock.patch("murphy_backup._load_config", return_value=BackupConfig())
    @mock.patch.object(pathlib.Path, "is_dir", return_value=True)
    def test_export_backup_copies_to_dest(self, _isd, _cfg, _mkdir, mock_copy, _mock_run):
        manifest_data = _make_manifest()
        b = MurphyBackup()
        fake_stat = mock.MagicMock()
        fake_stat.st_size = 4096
        with mock.patch.object(b, "_load_manifest", return_value=BackupManifest.from_dict(manifest_data)):
            with mock.patch.object(pathlib.Path, "stat", return_value=fake_stat):
                result = b.export_backup("test-backup-001", "/mnt/offsite")
        assert isinstance(result, pathlib.Path)


# ── configuration ─────────────────────────────────────────────────────────
class TestBackupConfig:
    def test_default_config_has_expected_fields(self):
        cfg = BackupConfig()
        assert cfg.enabled is True
        assert cfg.strategy == "auto"
        assert isinstance(cfg.targets, list)
        assert isinstance(cfg.retention, dict)
