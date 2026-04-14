# SPDX-License-Identifier: LicenseRef-BSL-1.1
# © 2020 Inoni Limited Liability Company — Creator: Corey Post — BSL 1.1
"""MurphyOS snapshot-based backup and disaster recovery module.

Provides OS-level backup for Murphy System state, keys, configuration, and
databases.  Four backup strategies are supported with automatic detection:

* **btrfs**  — instant copy-on-write subvolume snapshots
* **LVM**    — block-level LVM thin snapshots
* **restic** — incremental, encrypted, deduplicated (requires ``restic`` binary)
* **tar**    — gzip-compressed archive (universal fallback)

Strategy selection follows a priority waterfall unless an explicit strategy
is specified in ``backup.yaml``.

Typical usage::

    from murphy_backup import MurphyBackup

    bkp = MurphyBackup()                        # loads /etc/murphy/backup.yaml
    bid = bkp.create_backup("nightly")           # auto-detect strategy
    bkp.verify_backup(bid)                       # integrity check
    bkp.list_backups()                            # enumerate snapshots
    bkp.prune_backups(keep_daily=7)              # retention cleanup
    bkp.export_backup(bid, "/mnt/offsite/")      # off-site copy
    bkp.restore_backup(bid)                      # full restore

CLI entry point (used by systemd unit)::

    python3 murphy_backup.py --config /etc/murphy/backup.yaml create --label nightly
    python3 murphy_backup.py list
    python3 murphy_backup.py verify <backup_id>
    python3 murphy_backup.py restore <backup_id>
    python3 murphy_backup.py prune
    python3 murphy_backup.py export <backup_id> /mnt/offsite/
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import uuid
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import yaml  # PyYAML ships with every Murphy runtime; stdlib otherwise unused

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_LOG = logging.getLogger("murphy.backup")

_DEFAULT_CONFIG_PATH = Path("/etc/murphy/backup.yaml")
_DEFAULT_BACKUP_DIR = Path("/var/lib/murphy/backups")
_MANIFEST_FILENAME = "manifest.json"
_HASH_ALGORITHM = "sha3_256"

_DEFAULT_TARGETS: List[str] = [
    "/var/lib/murphy/",
    "/murphy/keys/",
    "/etc/murphy/",
]

_DEFAULT_RETENTION = {
    "keep_daily": 7,
    "keep_weekly": 4,
    "keep_monthly": 6,
}


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class BackupStrategy(str, Enum):
    """Available backup strategies, ordered by preference."""

    BTRFS = "btrfs"
    LVM = "lvm"
    RESTIC = "restic"
    TAR = "tar"
    AUTO = "auto"


class BackupStatus(str, Enum):
    """Lifecycle state of a single backup."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    VERIFIED = "verified"


# ---------------------------------------------------------------------------
# Error codes
# ---------------------------------------------------------------------------

class BackupError(Exception):
    """Base exception carrying a Murphy error code."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"[{code}] {message}")


# Catalogue of error codes — referenced by except blocks below.
_ERR_CONFIG_LOAD        = "MURPHY-BACKUP-ERR-001"  # Configuration load / parse failure
_ERR_DIR_CREATE         = "MURPHY-BACKUP-ERR-002"  # Backup directory creation failed
_ERR_STRATEGY_DETECT    = "MURPHY-BACKUP-ERR-003"  # No viable strategy detected
_ERR_BTRFS_SNAPSHOT     = "MURPHY-BACKUP-ERR-004"  # btrfs snapshot command failed
_ERR_LVM_SNAPSHOT       = "MURPHY-BACKUP-ERR-005"  # LVM snapshot creation failed
_ERR_RESTIC_BACKUP      = "MURPHY-BACKUP-ERR-006"  # restic backup command failed
_ERR_TAR_CREATE         = "MURPHY-BACKUP-ERR-007"  # tar archive creation failed
_ERR_MANIFEST_WRITE     = "MURPHY-BACKUP-ERR-008"  # Manifest write / serialise error
_ERR_RESTORE_FAILED     = "MURPHY-BACKUP-ERR-009"  # Restore operation failed
_ERR_VERIFY_FAILED      = "MURPHY-BACKUP-ERR-010"  # Integrity verification mismatch
_ERR_PRUNE_FAILED       = "MURPHY-BACKUP-ERR-011"  # Retention pruning error
_ERR_EXPORT_FAILED      = "MURPHY-BACKUP-ERR-012"  # Export / off-site copy error
_ERR_DB_DUMP            = "MURPHY-BACKUP-ERR-013"  # Database dump failure
_ERR_HOOK_FAILED        = "MURPHY-BACKUP-ERR-014"  # Pre/post hook execution error
_ERR_BACKUP_NOT_FOUND   = "MURPHY-BACKUP-ERR-015"  # Requested backup_id not found


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class BackupManifest:
    """JSON-serialisable manifest describing a single backup."""

    backup_id: str
    label: str
    timestamp: str
    strategy: str
    status: str
    targets: List[str]
    file_list: List[str] = dataclasses.field(default_factory=list)
    sha3_checksums: Dict[str, str] = dataclasses.field(default_factory=dict)
    size_bytes: int = 0
    db_included: bool = False
    db_engine: str = ""
    encryption_enabled: bool = False
    hostname: str = dataclasses.field(default_factory=lambda: os.uname().nodename)

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> BackupManifest:
        known = {f.name for f in dataclasses.fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclasses.dataclass
class BackupInfo:
    """Lightweight summary returned by :meth:`MurphyBackup.list_backups`."""

    backup_id: str
    label: str
    timestamp: str
    strategy: str
    status: str
    size_bytes: int


# ---------------------------------------------------------------------------
# Configuration loader
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class BackupConfig:
    """Typed representation of ``backup.yaml``."""

    enabled: bool = True
    strategy: str = "auto"
    backup_dir: Path = _DEFAULT_BACKUP_DIR
    targets: List[str] = dataclasses.field(default_factory=lambda: list(_DEFAULT_TARGETS))
    retention: Dict[str, int] = dataclasses.field(default_factory=lambda: dict(_DEFAULT_RETENTION))
    pre_hooks: List[str] = dataclasses.field(default_factory=list)
    post_hooks: List[str] = dataclasses.field(default_factory=list)
    encryption_enabled: bool = True
    encryption_key_source: str = "pqc"

    # Database settings (auto-detected when absent)
    db_engine: str = ""      # "postgresql" | "sqlite" | ""
    db_connection: str = ""   # DSN or file path


def _load_config(path: Path) -> BackupConfig:
    """Parse ``backup.yaml`` and return a :class:`BackupConfig`."""
    try:
        if not path.exists():
            _LOG.warning("Config %s not found — using defaults", path)
            return BackupConfig()

        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        section = raw.get("murphy_backup", raw)

        retention = section.get("retention", _DEFAULT_RETENTION)
        enc = section.get("encryption", {})

        return BackupConfig(
            enabled=section.get("enabled", True),
            strategy=section.get("strategy", "auto"),
            backup_dir=Path(section.get("backup_dir", str(_DEFAULT_BACKUP_DIR))),
            targets=section.get("targets", list(_DEFAULT_TARGETS)),
            retention={**_DEFAULT_RETENTION, **retention},
            pre_hooks=section.get("pre_hooks", []),
            post_hooks=section.get("post_hooks", []),
            encryption_enabled=enc.get("enabled", True),
            encryption_key_source=enc.get("key_source", "pqc"),
            db_engine=section.get("db_engine", ""),
            db_connection=section.get("db_connection", ""),
        )
    except Exception as exc:
        # MURPHY-BACKUP-ERR-001 — Configuration load / parse failure
        _LOG.error("[%s] Failed to load config %s: %s", _ERR_CONFIG_LOAD, path, exc)
        raise BackupError(_ERR_CONFIG_LOAD, f"Failed to load config {path}: {exc}") from exc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sha3_256_file(filepath: Path) -> str:
    """Return hex-encoded SHA3-256 digest of *filepath*."""
    h = hashlib.new(_HASH_ALGORITHM)
    with filepath.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _run(cmd: Sequence[str], *, check: bool = True, **kwargs: Any) -> subprocess.CompletedProcess[str]:
    """Execute a subprocess, logging the invocation."""
    _LOG.debug("exec: %s", " ".join(str(c) for c in cmd))
    return subprocess.run(cmd, capture_output=True, text=True, check=check, **kwargs)


def _run_hook(command: str) -> None:
    """Execute a single hook command string via the shell."""
    try:
        _LOG.info("Running hook: %s", command)
        subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        # MURPHY-BACKUP-ERR-014 — Pre/post hook execution error
        _LOG.error("[%s] Hook failed: %s — %s", _ERR_HOOK_FAILED, command, exc.stderr)
        raise BackupError(_ERR_HOOK_FAILED, f"Hook failed: {command}") from exc


def _dir_size(path: Path) -> int:
    """Recursively compute size in bytes of a directory tree."""
    total = 0
    if path.is_file():
        return path.stat().st_size
    if path.is_dir():
        for entry in path.rglob("*"):
            if entry.is_file():
                total += entry.stat().st_size
    return total


# ---------------------------------------------------------------------------
# Strategy detection
# ---------------------------------------------------------------------------

def _is_btrfs(target: str) -> bool:
    """Return True when *target* resides on a btrfs filesystem."""
    try:
        result = _run(["stat", "-f", "--format=%T", target], check=False)
        return result.returncode == 0 and "btrfs" in result.stdout.lower()
    except FileNotFoundError:
        return False


def _has_lvm() -> bool:
    """Return True when LVM thin-snapshot tooling is available."""
    return shutil.which("lvcreate") is not None


def _has_restic() -> bool:
    """Return True when the ``restic`` binary is on ``$PATH``."""
    return shutil.which("restic") is not None


def _detect_strategy(targets: List[str]) -> BackupStrategy:
    """Waterfall detection: btrfs → LVM → restic → tar."""
    if targets and _is_btrfs(targets[0]):
        _LOG.info("Detected btrfs filesystem — using btrfs strategy")
        return BackupStrategy.BTRFS
    if _has_lvm():
        _LOG.info("LVM tooling available — using LVM strategy")
        return BackupStrategy.LVM
    if _has_restic():
        _LOG.info("restic binary found — using restic strategy")
        return BackupStrategy.RESTIC
    _LOG.info("Falling back to tar strategy")
    return BackupStrategy.TAR


def _detect_db_engine() -> tuple[str, str]:
    """Best-effort auto-detection of the Murphy database engine.

    Returns ``(engine, connection_string)`` where *engine* is one of
    ``"postgresql"``, ``"sqlite"``, or ``""`` (not detected).
    """
    # Check for PostgreSQL via environment
    pg_dsn = os.environ.get("MURPHY_DATABASE_URL", "")
    if pg_dsn and "postgres" in pg_dsn.lower():
        return "postgresql", pg_dsn

    # Check for a well-known SQLite path
    sqlite_candidates = [
        Path("/var/lib/murphy/murphy.db"),
        Path("/var/lib/murphy/data/murphy.db"),
    ]
    for candidate in sqlite_candidates:
        if candidate.exists():
            return "sqlite", str(candidate)

    return "", ""


# ---------------------------------------------------------------------------
# Strategy implementations
# ---------------------------------------------------------------------------

def _backup_btrfs(targets: List[str], dest: Path) -> List[str]:
    """Create btrfs read-only snapshots for each target."""
    created: List[str] = []
    for target in targets:
        target_path = Path(target)
        if not target_path.exists():
            _LOG.warning("Target %s does not exist — skipping btrfs snapshot", target)
            continue
        snap_name = target_path.name or target_path.parent.name
        snap_dest = dest / f"snap-{snap_name}"
        try:
            _run(["btrfs", "subvolume", "snapshot", "-r", str(target_path), str(snap_dest)])
            created.append(str(snap_dest))
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            # MURPHY-BACKUP-ERR-004 — btrfs snapshot command failed
            _LOG.error("[%s] btrfs snapshot failed for %s: %s", _ERR_BTRFS_SNAPSHOT, target, exc)
            raise BackupError(_ERR_BTRFS_SNAPSHOT, f"btrfs snapshot failed for {target}") from exc
    return created


def _backup_lvm(targets: List[str], dest: Path, label: str) -> List[str]:
    """Create LVM thin snapshots for each target volume."""
    created: List[str] = []
    for target in targets:
        target_path = Path(target)
        if not target_path.exists():
            _LOG.warning("Target %s does not exist — skipping LVM snapshot", target)
            continue
        snap_name = f"murphy-snap-{label}-{target_path.name or 'root'}"
        try:
            # Determine the LV backing the target mount
            result = _run(["findmnt", "-no", "SOURCE", str(target_path)], check=False)
            if result.returncode != 0 or not result.stdout.strip():
                _LOG.warning("Cannot determine LV for %s — skipping", target)
                continue
            lv_path = result.stdout.strip()
            _run([
                "lvcreate", "--snapshot", "--name", snap_name,
                "--size", "5G", lv_path,
            ])
            created.append(snap_name)
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            # MURPHY-BACKUP-ERR-005 — LVM snapshot creation failed
            _LOG.error("[%s] LVM snapshot failed for %s: %s", _ERR_LVM_SNAPSHOT, target, exc)
            raise BackupError(_ERR_LVM_SNAPSHOT, f"LVM snapshot failed for {target}") from exc
    return created


def _backup_restic(targets: List[str], dest: Path, label: str) -> List[str]:
    """Run ``restic backup`` for each target into the repository at *dest*."""
    repo = str(dest / "restic-repo")
    created: List[str] = []
    try:
        # Initialise repository if it doesn't exist
        init_result = _run(["restic", "init", "--repo", repo], check=False)
        if init_result.returncode not in (0, 1):
            # returncode 1 = already initialised
            raise subprocess.CalledProcessError(init_result.returncode, "restic init")

        existing: List[str] = []
        for target in targets:
            if Path(target).exists():
                existing.append(target)
            else:
                _LOG.warning("Target %s does not exist — skipping restic backup", target)

        if existing:
            cmd = ["restic", "backup", "--repo", repo, "--tag", label, *existing]
            _run(cmd)
            created.extend(existing)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        # MURPHY-BACKUP-ERR-006 — restic backup command failed
        _LOG.error("[%s] restic backup failed: %s", _ERR_RESTIC_BACKUP, exc)
        raise BackupError(_ERR_RESTIC_BACKUP, f"restic backup failed: {exc}") from exc
    return created


def _backup_tar(targets: List[str], dest: Path, label: str) -> List[str]:
    """Create a gzip-compressed tar archive of all targets."""
    archive = dest / f"murphy-backup-{label}.tar.gz"
    existing: List[str] = []
    for target in targets:
        if Path(target).exists():
            existing.append(target)
        else:
            _LOG.warning("Target %s does not exist — skipping tar", target)

    if not existing:
        return []

    try:
        _run(["tar", "czf", str(archive), *existing])
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        # MURPHY-BACKUP-ERR-007 — tar archive creation failed
        _LOG.error("[%s] tar create failed: %s", _ERR_TAR_CREATE, exc)
        raise BackupError(_ERR_TAR_CREATE, f"tar create failed: {exc}") from exc
    return [str(archive)]


# ---------------------------------------------------------------------------
# Database dump helpers
# ---------------------------------------------------------------------------

def _dump_database(engine: str, connection: str, dest: Path) -> Optional[Path]:
    """Dump the Murphy database to *dest*.

    Returns the path of the dump file, or ``None`` if no DB was configured.
    """
    if not engine:
        return None

    if engine == "postgresql":
        dump_path = dest / "murphy_db.sql.gz"
        try:
            with dump_path.open("wb") as fh:
                pg = subprocess.Popen(
                    ["pg_dump", connection],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
                gz = subprocess.Popen(
                    ["gzip"],
                    stdin=pg.stdout, stdout=fh, stderr=subprocess.PIPE,
                )
                pg.stdout.close()  # type: ignore[union-attr]
                gz.communicate()
                pg.wait()
                if pg.returncode != 0:
                    raise subprocess.CalledProcessError(pg.returncode, "pg_dump")
            return dump_path
        except (subprocess.CalledProcessError, FileNotFoundError, OSError) as exc:
            # MURPHY-BACKUP-ERR-013 — Database dump failure
            _LOG.error("[%s] pg_dump failed: %s", _ERR_DB_DUMP, exc)
            raise BackupError(_ERR_DB_DUMP, f"pg_dump failed: {exc}") from exc

    if engine == "sqlite":
        src = Path(connection)
        if not src.exists():
            _LOG.warning("SQLite DB %s not found — skipping dump", src)
            return None
        dump_path = dest / src.name
        try:
            shutil.copy2(src, dump_path)
            return dump_path
        except OSError as exc:
            # MURPHY-BACKUP-ERR-013 — Database dump failure
            _LOG.error("[%s] SQLite copy failed: %s", _ERR_DB_DUMP, exc)
            raise BackupError(_ERR_DB_DUMP, f"SQLite copy failed: {exc}") from exc

    _LOG.warning("Unknown DB engine '%s' — skipping dump", engine)
    return None


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class MurphyBackup:
    """OS-level snapshot backup manager for Murphy System.

    Parameters
    ----------
    config_path:
        Path to ``backup.yaml``.  Falls back to built-in defaults when
        the file is absent.
    """

    def __init__(self, config_path: Path | str | None = None) -> None:
        path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH
        self._cfg = _load_config(path)
        self._backup_dir = self._cfg.backup_dir
        self._ensure_backup_dir()

    # -- internal helpers ---------------------------------------------------

    def _ensure_backup_dir(self) -> None:
        try:
            self._backup_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            # MURPHY-BACKUP-ERR-002 — Backup directory creation failed
            _LOG.error("[%s] Cannot create backup dir %s: %s", _ERR_DIR_CREATE, self._backup_dir, exc)
            raise BackupError(_ERR_DIR_CREATE, f"Cannot create {self._backup_dir}") from exc

    def _resolve_strategy(self, explicit: Optional[str] = None) -> BackupStrategy:
        choice = explicit or self._cfg.strategy
        if choice == "auto" or choice == BackupStrategy.AUTO:
            return _detect_strategy(self._cfg.targets)
        try:
            return BackupStrategy(choice)
        except ValueError:
            # MURPHY-BACKUP-ERR-003 — No viable strategy detected
            _LOG.error("[%s] Unknown strategy '%s'", _ERR_STRATEGY_DETECT, choice)
            raise BackupError(_ERR_STRATEGY_DETECT, f"Unknown strategy: {choice}")

    def _run_hooks(self, hooks: List[str]) -> None:
        for hook in hooks:
            _run_hook(hook)

    def _build_manifest(
        self,
        backup_id: str,
        label: str,
        strategy: BackupStrategy,
        dest: Path,
        db_included: bool,
        db_engine: str,
    ) -> BackupManifest:
        file_list: List[str] = []
        checksums: Dict[str, str] = {}
        for entry in sorted(dest.rglob("*")):
            if entry.is_file():
                rel = str(entry.relative_to(dest))
                file_list.append(rel)
                checksums[rel] = _sha3_256_file(entry)

        return BackupManifest(
            backup_id=backup_id,
            label=label,
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            strategy=strategy.value,
            status=BackupStatus.COMPLETED.value,
            targets=list(self._cfg.targets),
            file_list=file_list,
            sha3_checksums=checksums,
            size_bytes=_dir_size(dest),
            db_included=db_included,
            db_engine=db_engine,
            encryption_enabled=self._cfg.encryption_enabled,
        )

    def _write_manifest(self, manifest: BackupManifest, dest: Path) -> None:
        try:
            manifest_path = dest / _MANIFEST_FILENAME
            manifest_path.write_text(manifest.to_json(), encoding="utf-8")
        except OSError as exc:
            # MURPHY-BACKUP-ERR-008 — Manifest write / serialise error
            _LOG.error("[%s] Manifest write failed: %s", _ERR_MANIFEST_WRITE, exc)
            raise BackupError(_ERR_MANIFEST_WRITE, f"Manifest write failed: {exc}") from exc

    def _load_manifest(self, backup_id: str) -> BackupManifest:
        dest = self._backup_dir / backup_id
        manifest_path = dest / _MANIFEST_FILENAME
        if not manifest_path.exists():
            # MURPHY-BACKUP-ERR-015 — Requested backup_id not found
            _LOG.error("[%s] Backup '%s' not found", _ERR_BACKUP_NOT_FOUND, backup_id)
            raise BackupError(_ERR_BACKUP_NOT_FOUND, f"Backup '{backup_id}' not found")
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        return BackupManifest.from_dict(data)

    # -- public API ---------------------------------------------------------

    def create_backup(
        self,
        label: str = "manual",
        strategy: Optional[str] = None,
    ) -> str:
        """Create a named backup of all configured targets.

        Parameters
        ----------
        label:
            Human-readable label for the backup.
        strategy:
            Explicit strategy override (``btrfs``, ``lvm``, ``restic``,
            ``tar``).  ``None`` or ``"auto"`` triggers auto-detection.

        Returns
        -------
        str
            The unique ``backup_id`` assigned to the new backup.
        """
        resolved = self._resolve_strategy(strategy)
        backup_id = f"{label}-{datetime.datetime.now(datetime.timezone.utc):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"
        dest = self._backup_dir / backup_id
        dest.mkdir(parents=True, exist_ok=True)

        _LOG.info("Creating backup '%s' with strategy=%s → %s", backup_id, resolved.value, dest)

        # Pre-hooks
        self._run_hooks(self._cfg.pre_hooks)

        try:
            # Database dump
            db_engine, db_conn = self._cfg.db_engine, self._cfg.db_connection
            if not db_engine:
                db_engine, db_conn = _detect_db_engine()
            db_path = _dump_database(db_engine, db_conn, dest)

            # Filesystem backup
            if resolved == BackupStrategy.BTRFS:
                _backup_btrfs(self._cfg.targets, dest)
            elif resolved == BackupStrategy.LVM:
                _backup_lvm(self._cfg.targets, dest, label)
            elif resolved == BackupStrategy.RESTIC:
                _backup_restic(self._cfg.targets, dest, label)
            else:
                _backup_tar(self._cfg.targets, dest, label)

            # Manifest
            manifest = self._build_manifest(
                backup_id, label, resolved, dest,
                db_included=db_path is not None,
                db_engine=db_engine,
            )
            self._write_manifest(manifest, dest)

            _LOG.info("Backup '%s' completed (%d bytes)", backup_id, manifest.size_bytes)
        finally:
            # Post-hooks always execute, even on failure
            try:
                self._run_hooks(self._cfg.post_hooks)
            except BackupError:
                _LOG.warning("Post-hook failed after backup — services may need manual restart")

        return backup_id

    def restore_backup(self, backup_id: str) -> None:
        """Restore Murphy System state from a previous backup.

        Parameters
        ----------
        backup_id:
            The identifier returned by :meth:`create_backup`.

        Raises
        ------
        BackupError
            If the backup cannot be found or the restore operation fails.
        """
        manifest = self._load_manifest(backup_id)
        dest = self._backup_dir / backup_id
        strategy = BackupStrategy(manifest.strategy)

        _LOG.info("Restoring backup '%s' (strategy=%s)", backup_id, strategy.value)

        # Pre-hooks (stop services)
        self._run_hooks(self._cfg.pre_hooks)

        try:
            if strategy == BackupStrategy.BTRFS:
                self._restore_btrfs(manifest, dest)
            elif strategy == BackupStrategy.LVM:
                self._restore_lvm(manifest, dest)
            elif strategy == BackupStrategy.RESTIC:
                self._restore_restic(manifest, dest)
            else:
                self._restore_tar(manifest, dest)

            # Restore database if included
            if manifest.db_included:
                self._restore_database(manifest, dest)

            _LOG.info("Restore of '%s' completed successfully", backup_id)
        except BackupError:
            raise
        except Exception as exc:
            # MURPHY-BACKUP-ERR-009 — Restore operation failed
            _LOG.error("[%s] Restore failed for '%s': %s", _ERR_RESTORE_FAILED, backup_id, exc)
            raise BackupError(_ERR_RESTORE_FAILED, f"Restore failed: {exc}") from exc
        finally:
            # Post-hooks (start services)
            try:
                self._run_hooks(self._cfg.post_hooks)
            except BackupError:
                _LOG.warning("Post-hook failed after restore — services may need manual restart")

    def list_backups(self) -> List[BackupInfo]:
        """Enumerate all available backups with size and date.

        Returns
        -------
        list[BackupInfo]
            Sorted by timestamp descending (newest first).
        """
        results: List[BackupInfo] = []
        if not self._backup_dir.exists():
            return results

        for entry in sorted(self._backup_dir.iterdir(), reverse=True):
            manifest_path = entry / _MANIFEST_FILENAME
            if entry.is_dir() and manifest_path.exists():
                try:
                    data = json.loads(manifest_path.read_text(encoding="utf-8"))
                    results.append(BackupInfo(
                        backup_id=data.get("backup_id", entry.name),
                        label=data.get("label", ""),
                        timestamp=data.get("timestamp", ""),
                        strategy=data.get("strategy", ""),
                        status=data.get("status", ""),
                        size_bytes=data.get("size_bytes", 0),
                    ))
                except (json.JSONDecodeError, OSError) as exc:
                    _LOG.warning("Skipping %s — manifest unreadable: %s", entry.name, exc)

        return results

    def prune_backups(
        self,
        keep_daily: Optional[int] = None,
        keep_weekly: Optional[int] = None,
        keep_monthly: Optional[int] = None,
    ) -> List[str]:
        """Apply retention policy and remove old backups.

        Parameters
        ----------
        keep_daily:
            Number of daily backups to retain.
        keep_weekly:
            Number of weekly backups to retain.
        keep_monthly:
            Number of monthly backups to retain.

        Returns
        -------
        list[str]
            ``backup_id`` values of pruned backups.
        """
        kd = keep_daily if keep_daily is not None else self._cfg.retention.get("keep_daily", 7)
        kw = keep_weekly if keep_weekly is not None else self._cfg.retention.get("keep_weekly", 4)
        km = keep_monthly if keep_monthly is not None else self._cfg.retention.get("keep_monthly", 6)

        all_backups = self.list_backups()
        now = datetime.datetime.now(datetime.timezone.utc)

        keep_ids: set[str] = set()
        daily_slots: dict[str, BackupInfo] = {}
        weekly_slots: dict[str, BackupInfo] = {}
        monthly_slots: dict[str, BackupInfo] = {}

        for bk in all_backups:
            try:
                ts = datetime.datetime.fromisoformat(bk.timestamp)
            except (ValueError, TypeError):
                keep_ids.add(bk.backup_id)  # unparseable → keep safe
                continue

            day_key = ts.strftime("%Y-%m-%d")
            week_key = ts.strftime("%Y-W%W")
            month_key = ts.strftime("%Y-%m")

            if day_key not in daily_slots:
                daily_slots[day_key] = bk
            if week_key not in weekly_slots:
                weekly_slots[week_key] = bk
            if month_key not in monthly_slots:
                monthly_slots[month_key] = bk

        # Pick the newest N from each bucket
        for slot_dict, limit in [
            (daily_slots, kd),
            (weekly_slots, kw),
            (monthly_slots, km),
        ]:
            for key in sorted(slot_dict, reverse=True)[:limit]:
                keep_ids.add(slot_dict[key].backup_id)

        pruned: List[str] = []
        for bk in all_backups:
            if bk.backup_id not in keep_ids:
                target_dir = self._backup_dir / bk.backup_id
                try:
                    if target_dir.exists():
                        shutil.rmtree(target_dir)
                    pruned.append(bk.backup_id)
                    _LOG.info("Pruned backup '%s'", bk.backup_id)
                except OSError as exc:
                    # MURPHY-BACKUP-ERR-011 — Retention pruning error
                    _LOG.error("[%s] Prune failed for '%s': %s", _ERR_PRUNE_FAILED, bk.backup_id, exc)

        _LOG.info("Pruning complete: removed %d backup(s), kept %d", len(pruned), len(keep_ids))
        return pruned

    def verify_backup(self, backup_id: str) -> bool:
        """Verify integrity of a backup via SHA3-256 manifest checksums.

        Parameters
        ----------
        backup_id:
            The identifier of the backup to verify.

        Returns
        -------
        bool
            ``True`` if every file matches its recorded digest.

        Raises
        ------
        BackupError
            If any file fails verification.
        """
        manifest = self._load_manifest(backup_id)
        dest = self._backup_dir / backup_id

        mismatches: List[str] = []
        for rel_path, expected in manifest.sha3_checksums.items():
            full = dest / rel_path
            if not full.exists():
                mismatches.append(f"MISSING: {rel_path}")
                continue
            actual = _sha3_256_file(full)
            if actual != expected:
                mismatches.append(f"MISMATCH: {rel_path} (expected {expected[:16]}…, got {actual[:16]}…)")

        if mismatches:
            detail = "; ".join(mismatches[:5])
            # MURPHY-BACKUP-ERR-010 — Integrity verification mismatch
            _LOG.error("[%s] Verification failed for '%s': %s", _ERR_VERIFY_FAILED, backup_id, detail)
            raise BackupError(_ERR_VERIFY_FAILED, f"Verification failed: {detail}")

        _LOG.info("Backup '%s' verified — %d file(s) OK", backup_id, len(manifest.sha3_checksums))
        return True

    def export_backup(self, backup_id: str, dest_path: str | Path) -> Path:
        """Export a backup to an off-site destination.

        Parameters
        ----------
        backup_id:
            The identifier of the backup to export.
        dest_path:
            Destination directory (local path, NFS mount, etc.).

        Returns
        -------
        Path
            The path of the exported archive.
        """
        manifest = self._load_manifest(backup_id)
        src = self._backup_dir / backup_id
        dest = Path(dest_path)
        dest.mkdir(parents=True, exist_ok=True)

        archive = dest / f"{backup_id}.tar.gz"
        try:
            _run(["tar", "czf", str(archive), "-C", str(src), "."])
            _LOG.info("Exported backup '%s' → %s (%d bytes)", backup_id, archive, archive.stat().st_size)
        except (subprocess.CalledProcessError, FileNotFoundError, OSError) as exc:
            # MURPHY-BACKUP-ERR-012 — Export / off-site copy error
            _LOG.error("[%s] Export failed for '%s': %s", _ERR_EXPORT_FAILED, backup_id, exc)
            raise BackupError(_ERR_EXPORT_FAILED, f"Export failed: {exc}") from exc

        return archive

    # -- strategy-specific restore methods ----------------------------------

    def _restore_btrfs(self, manifest: BackupManifest, src: Path) -> None:
        """Restore btrfs snapshots to their original target locations."""
        for target in manifest.targets:
            target_path = Path(target)
            snap_name = target_path.name or target_path.parent.name
            snap_src = src / f"snap-{snap_name}"
            if not snap_src.exists():
                _LOG.warning("Snapshot %s not found — skipping", snap_src)
                continue
            try:
                # Remove existing and replace with snapshot
                if target_path.exists():
                    _run(["btrfs", "subvolume", "delete", str(target_path)], check=False)
                _run(["btrfs", "subvolume", "snapshot", str(snap_src), str(target_path)])
            except (subprocess.CalledProcessError, FileNotFoundError) as exc:
                # MURPHY-BACKUP-ERR-009 — Restore operation failed
                _LOG.error("[%s] btrfs restore failed for %s: %s", _ERR_RESTORE_FAILED, target, exc)
                raise BackupError(_ERR_RESTORE_FAILED, f"btrfs restore failed for {target}") from exc

    def _restore_lvm(self, manifest: BackupManifest, src: Path) -> None:
        """Merge LVM snapshots back to their origin volumes."""
        for target in manifest.targets:
            target_path = Path(target)
            snap_name = f"murphy-snap-{manifest.label}-{target_path.name or 'root'}"
            try:
                _run(["lvconvert", "--merge", f"/dev/mapper/{snap_name}"])
            except (subprocess.CalledProcessError, FileNotFoundError) as exc:
                # MURPHY-BACKUP-ERR-009 — Restore operation failed
                _LOG.error("[%s] LVM restore failed for %s: %s", _ERR_RESTORE_FAILED, target, exc)
                raise BackupError(_ERR_RESTORE_FAILED, f"LVM restore failed: {exc}") from exc

    def _restore_restic(self, manifest: BackupManifest, src: Path) -> None:
        """Restore from a restic repository."""
        repo = str(src / "restic-repo")
        try:
            _run(["restic", "restore", "latest", "--repo", repo, "--target", "/"])
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            # MURPHY-BACKUP-ERR-009 — Restore operation failed
            _LOG.error("[%s] restic restore failed: %s", _ERR_RESTORE_FAILED, exc)
            raise BackupError(_ERR_RESTORE_FAILED, f"restic restore failed: {exc}") from exc

    def _restore_tar(self, manifest: BackupManifest, src: Path) -> None:
        """Restore from a tar.gz archive."""
        archives = list(src.glob("*.tar.gz"))
        if not archives:
            _LOG.warning("No tar archive found in %s — nothing to restore", src)
            return
        for archive in archives:
            try:
                _run(["tar", "xzf", str(archive), "-C", "/"])
            except (subprocess.CalledProcessError, FileNotFoundError) as exc:
                # MURPHY-BACKUP-ERR-009 — Restore operation failed
                _LOG.error("[%s] tar restore failed: %s", _ERR_RESTORE_FAILED, exc)
                raise BackupError(_ERR_RESTORE_FAILED, f"tar restore failed: {exc}") from exc

    def _restore_database(self, manifest: BackupManifest, src: Path) -> None:
        """Restore the database dump from a backup."""
        if manifest.db_engine == "postgresql":
            dump_path = src / "murphy_db.sql.gz"
            if not dump_path.exists():
                _LOG.warning("PostgreSQL dump not found — skipping DB restore")
                return
            try:
                conn = self._cfg.db_connection or os.environ.get("MURPHY_DATABASE_URL", "murphy")
                gz = subprocess.Popen(
                    ["gunzip", "-c", str(dump_path)],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
                psql = subprocess.Popen(
                    ["psql", conn],
                    stdin=gz.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
                gz.stdout.close()  # type: ignore[union-attr]
                psql.communicate()
                gz.wait()
                if psql.returncode != 0:
                    raise subprocess.CalledProcessError(psql.returncode, "psql")
            except (subprocess.CalledProcessError, FileNotFoundError, OSError) as exc:
                # MURPHY-BACKUP-ERR-009 — Restore operation failed
                _LOG.error("[%s] PostgreSQL restore failed: %s", _ERR_RESTORE_FAILED, exc)
                raise BackupError(_ERR_RESTORE_FAILED, f"PostgreSQL restore failed: {exc}") from exc

        elif manifest.db_engine == "sqlite":
            db_files = list(src.glob("*.db"))
            for db_file in db_files:
                dest_path = Path("/var/lib/murphy") / db_file.name
                try:
                    shutil.copy2(db_file, dest_path)
                except OSError as exc:
                    # MURPHY-BACKUP-ERR-009 — Restore operation failed
                    _LOG.error("[%s] SQLite restore failed: %s", _ERR_RESTORE_FAILED, exc)
                    raise BackupError(_ERR_RESTORE_FAILED, f"SQLite restore failed: {exc}") from exc


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="murphy-backup",
        description="MurphyOS snapshot-based backup manager",
    )
    parser.add_argument(
        "--config", type=Path, default=_DEFAULT_CONFIG_PATH,
        help="Path to backup.yaml (default: %(default)s)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # create
    p_create = sub.add_parser("create", help="Create a new backup")
    p_create.add_argument("--label", default="manual", help="Backup label")
    p_create.add_argument("--strategy", default=None, help="Override strategy")

    # list
    sub.add_parser("list", help="List available backups")

    # verify
    p_verify = sub.add_parser("verify", help="Verify backup integrity")
    p_verify.add_argument("backup_id", help="Backup ID to verify")

    # restore
    p_restore = sub.add_parser("restore", help="Restore from backup")
    p_restore.add_argument("backup_id", help="Backup ID to restore")

    # prune
    p_prune = sub.add_parser("prune", help="Apply retention policy")
    p_prune.add_argument("--keep-daily", type=int, default=None)
    p_prune.add_argument("--keep-weekly", type=int, default=None)
    p_prune.add_argument("--keep-monthly", type=int, default=None)

    # export
    p_export = sub.add_parser("export", help="Export backup for off-site storage")
    p_export.add_argument("backup_id", help="Backup ID to export")
    p_export.add_argument("dest", help="Destination directory")

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    )

    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        bkp = MurphyBackup(config_path=args.config)

        if args.command == "create":
            bid = bkp.create_backup(label=args.label, strategy=args.strategy)
            print(f"Backup created: {bid}")

        elif args.command == "list":
            backups = bkp.list_backups()
            if not backups:
                print("No backups found.")
            else:
                print(f"{'ID':<50} {'Label':<12} {'Strategy':<8} {'Size':>12} {'Timestamp'}")
                print("-" * 110)
                for b in backups:
                    size = f"{b.size_bytes / (1024 * 1024):.1f}M"
                    print(f"{b.backup_id:<50} {b.label:<12} {b.strategy:<8} {size:>12} {b.timestamp}")

        elif args.command == "verify":
            bkp.verify_backup(args.backup_id)
            print(f"Backup '{args.backup_id}' verified OK")

        elif args.command == "restore":
            bkp.restore_backup(args.backup_id)
            print(f"Restore from '{args.backup_id}' completed")

        elif args.command == "prune":
            pruned = bkp.prune_backups(
                keep_daily=args.keep_daily,
                keep_weekly=args.keep_weekly,
                keep_monthly=args.keep_monthly,
            )
            print(f"Pruned {len(pruned)} backup(s)")

        elif args.command == "export":
            out = bkp.export_backup(args.backup_id, args.dest)
            print(f"Exported to {out}")

    except BackupError as exc:
        _LOG.error("%s", exc)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nAborted.", file=sys.stderr)
        return 130

    return 0


if __name__ == "__main__":
    sys.exit(main())
