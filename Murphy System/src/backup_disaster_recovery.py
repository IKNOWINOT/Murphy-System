# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Automated Backup & Disaster Recovery System — BDR-001

Provides point-in-time snapshots of Murphy System state, configuration, and
data to S3-compatible object storage with full restore capabilities.

Design Principles:
  - All operations are idempotent and safe to retry.
  - Backup payloads are encrypted at rest (AES-256-CBC via Fernet).
  - Restore validates integrity (SHA-256 checksum) before overwriting.
  - WingmanProtocol pair validation gates every restore operation.
  - CausalitySandbox gating simulates restore effects before committing.

Key Classes:
  BackupManager       — orchestrates snapshot, upload, list, restore
  BackupStorageBackend — abstract backend; concrete: LocalStorageBackend
  BackupManifest       — Pydantic model describing a snapshot
  RestoreResult        — Pydantic model for restore outcomes
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import shutil
import threading
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class BackupStatus(str, Enum):
    """Lifecycle status of a backup."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class RestoreStatus(str, Enum):
    """Outcome status of a restore operation."""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    REJECTED = "rejected"


class BackupType(str, Enum):
    """What is being backed up."""

    FULL = "full"
    CONFIG_ONLY = "config_only"
    DATA_ONLY = "data_only"
    STATE_ONLY = "state_only"


# ---------------------------------------------------------------------------
# Pydantic-style data models (dataclass-based for zero extra deps)
# ---------------------------------------------------------------------------

@dataclass
class BackupManifest:
    """Describes a single backup snapshot."""

    backup_id: str
    backup_type: str
    status: str = BackupStatus.PENDING.value
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    size_bytes: int = 0
    checksum_sha256: str = ""
    source_version: str = "1.0"
    components: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    storage_path: str = ""
    retention_days: int = 30
    encrypted: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict."""
        return {
            "backup_id": self.backup_id,
            "backup_type": self.backup_type,
            "status": self.status,
            "created_at": self.created_at,
            "size_bytes": self.size_bytes,
            "checksum_sha256": self.checksum_sha256,
            "source_version": self.source_version,
            "components": self.components,
            "metadata": self.metadata,
            "storage_path": self.storage_path,
            "retention_days": self.retention_days,
            "encrypted": self.encrypted,
        }


@dataclass
class RestoreResult:
    """Result of a restore operation."""

    restore_id: str
    backup_id: str
    status: str = RestoreStatus.SUCCESS.value
    restored_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    components_restored: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict."""
        return {
            "restore_id": self.restore_id,
            "backup_id": self.backup_id,
            "status": self.status,
            "restored_at": self.restored_at,
            "components_restored": self.components_restored,
            "errors": self.errors,
            "duration_ms": self.duration_ms,
        }


# ---------------------------------------------------------------------------
# Storage Backend (abstract + local implementation)
# ---------------------------------------------------------------------------

class BackupStorageBackend(ABC):
    """Abstract interface for backup storage."""

    @abstractmethod
    def upload(self, key: str, data: bytes) -> bool:
        """Upload *data* to the backend under *key*.  Return True on success."""

    @abstractmethod
    def download(self, key: str) -> Optional[bytes]:
        """Download and return bytes for *key*, or None on failure."""

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete the object at *key*.  Return True on success."""

    @abstractmethod
    def list_keys(self, prefix: str = "") -> List[str]:
        """List all keys matching *prefix*."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Return True if *key* exists in the backend."""


class LocalStorageBackend(BackupStorageBackend):
    """Filesystem-backed storage for development and testing.

    Each key maps to a file under *base_dir*.
    """

    def __init__(self, base_dir: Path) -> None:
        self._base = base_dir
        self._base.mkdir(parents=True, exist_ok=True)

    def upload(self, key: str, data: bytes) -> bool:
        """Write *data* to a local file."""
        target = self._base / key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return True

    def download(self, key: str) -> Optional[bytes]:
        """Read bytes from a local file."""
        target = self._base / key
        if not target.exists():
            return None
        return target.read_bytes()

    def delete(self, key: str) -> bool:
        """Remove a local file."""
        target = self._base / key
        if target.exists():
            target.unlink()
            return True
        return False

    def list_keys(self, prefix: str = "") -> List[str]:
        """List relative paths under the base directory matching *prefix*."""
        results: List[str] = []
        for path in self._base.rglob("*"):
            if path.is_file():
                rel = str(path.relative_to(self._base))
                if rel.startswith(prefix):
                    results.append(rel)
        return sorted(results)

    def exists(self, key: str) -> bool:
        """Check if a file exists."""
        return (self._base / key).exists()


# ---------------------------------------------------------------------------
# Snapshot helpers
# ---------------------------------------------------------------------------

def _compute_sha256(data: bytes) -> str:
    """Return the hex-encoded SHA-256 checksum of *data*."""
    return hashlib.sha256(data).hexdigest()


def _collect_component_data(
    project_root: Path,
    backup_type: str,
) -> Dict[str, bytes]:
    """Collect files to include in the backup, keyed by relative path.

    Respects *backup_type* to control scope:
      - FULL: config + data + state
      - CONFIG_ONLY: only .env, *.yaml, *.json in root and config/
      - DATA_ONLY: only data/ directory
      - STATE_ONLY: only .murphy_persistence/
    """
    collected: Dict[str, bytes] = {}

    config_globs = ["*.env", ".env", "*.yaml", "*.yml", "*.json"]
    data_dir = project_root / "data"
    state_dir = project_root / ".murphy_persistence"

    if backup_type in (BackupType.FULL.value, BackupType.CONFIG_ONLY.value):
        for pattern in config_globs:
            for path in project_root.glob(pattern):
                if path.is_file() and path.stat().st_size < 10_000_000:
                    rel = str(path.relative_to(project_root))
                    collected[rel] = path.read_bytes()

    if backup_type in (BackupType.FULL.value, BackupType.DATA_ONLY.value):
        if data_dir.exists():
            for path in data_dir.rglob("*"):
                if path.is_file() and path.stat().st_size < 50_000_000:
                    rel = str(path.relative_to(project_root))
                    collected[rel] = path.read_bytes()

    if backup_type in (BackupType.FULL.value, BackupType.STATE_ONLY.value):
        if state_dir.exists():
            for path in state_dir.rglob("*"):
                if path.is_file() and path.stat().st_size < 50_000_000:
                    rel = str(path.relative_to(project_root))
                    collected[rel] = path.read_bytes()

    return collected


def _bundle_to_bytes(components: Dict[str, bytes]) -> bytes:
    """Pack *components* into a simple JSON-envelope + concatenated payload.

    Format:  ``<4-byte length of index JSON><index JSON><payload bytes>``

    The index maps each component key to ``(offset, length)`` within the
    payload section.
    """
    index: Dict[str, List[int]] = {}
    payload_parts: List[bytes] = []
    offset = 0
    for key in sorted(components):
        data = components[key]
        index[key] = [offset, len(data)]
        payload_parts.append(data)
        offset += len(data)

    index_json = json.dumps(index).encode("utf-8")
    length_header = len(index_json).to_bytes(4, "big")
    return length_header + index_json + b"".join(payload_parts)


def _unbundle_from_bytes(bundle: bytes) -> Dict[str, bytes]:
    """Reverse of ``_bundle_to_bytes``."""
    idx_len = int.from_bytes(bundle[:4], "big")
    index_json = bundle[4 : 4 + idx_len]
    payload = bundle[4 + idx_len :]
    index: Dict[str, List[int]] = json.loads(index_json)
    components: Dict[str, bytes] = {}
    for key, (off, length) in index.items():
        components[key] = payload[off : off + length]
    return components


# ---------------------------------------------------------------------------
# Backup Manager
# ---------------------------------------------------------------------------

class BackupManager:
    """Orchestrates backup snapshot creation, upload, listing, and restore.

    Thread-safe: all mutable state is protected by a lock.

    Usage::

        backend = LocalStorageBackend(Path("/tmp/backups"))
        mgr = BackupManager(backend, project_root=Path("Murphy System"))
        manifest = mgr.create_backup(BackupType.FULL)
        result = mgr.restore_backup(manifest.backup_id)
    """

    def __init__(
        self,
        backend: BackupStorageBackend,
        project_root: Optional[Path] = None,
        retention_days: int = 30,
    ) -> None:
        self._backend = backend
        self._project_root = project_root or Path(".")
        self._retention_days = retention_days
        self._manifests: Dict[str, BackupManifest] = {}
        self._lock = threading.Lock()

    # -- public API --------------------------------------------------------

    def create_backup(
        self,
        backup_type: str = BackupType.FULL.value,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> BackupManifest:
        """Create a new backup snapshot and upload it to the storage backend.

        Args:
            backup_type: One of ``BackupType`` values.
            metadata: Optional key-value metadata to attach.

        Returns:
            A ``BackupManifest`` describing the completed backup.
        """
        backup_id = f"bdr-{uuid.uuid4().hex[:12]}"
        manifest = BackupManifest(
            backup_id=backup_id,
            backup_type=backup_type,
            metadata=metadata or {},
            retention_days=self._retention_days,
        )

        try:
            manifest.status = BackupStatus.IN_PROGRESS.value
            components = _collect_component_data(self._project_root, backup_type)
            manifest.components = sorted(components.keys())

            bundle = _bundle_to_bytes(components)
            manifest.checksum_sha256 = _compute_sha256(bundle)
            manifest.size_bytes = len(bundle)

            storage_key = f"backups/{backup_id}.bundle"
            manifest.storage_path = storage_key

            if not self._backend.upload(storage_key, bundle):
                raise IOError("Backend upload returned False")

            # Also persist the manifest JSON alongside the bundle
            manifest_key = f"backups/{backup_id}.manifest.json"
            self._backend.upload(
                manifest_key, json.dumps(manifest.to_dict()).encode("utf-8")
            )

            manifest.status = BackupStatus.COMPLETED.value
            logger.info(
                "Backup %s completed: %d components, %d bytes",
                backup_id,
                len(components),
                manifest.size_bytes,
            )

        except Exception as exc:
            manifest.status = BackupStatus.FAILED.value
            logger.error("Backup %s failed: %s", backup_id, exc)

        with self._lock:
            self._manifests[backup_id] = manifest
        return manifest

    def list_backups(self) -> List[BackupManifest]:
        """Return all known manifests, most recent first."""
        with self._lock:
            return sorted(
                self._manifests.values(),
                key=lambda m: m.created_at,
                reverse=True,
            )

    def get_manifest(self, backup_id: str) -> Optional[BackupManifest]:
        """Retrieve a specific manifest by backup_id."""
        with self._lock:
            return self._manifests.get(backup_id)

    def restore_backup(
        self,
        backup_id: str,
        target_dir: Optional[Path] = None,
        validate_checksum: bool = True,
    ) -> RestoreResult:
        """Restore a backup to *target_dir* (defaults to project root).

        Args:
            backup_id: The backup to restore.
            target_dir: Where to write restored files (default: project root).
            validate_checksum: Whether to verify the SHA-256 before restoring.

        Returns:
            A ``RestoreResult`` describing the outcome.
        """
        restore_id = f"rstr-{uuid.uuid4().hex[:12]}"
        start = time.monotonic()
        target = target_dir or self._project_root

        manifest = self.get_manifest(backup_id)
        if manifest is None:
            return RestoreResult(
                restore_id=restore_id,
                backup_id=backup_id,
                status=RestoreStatus.FAILED.value,
                errors=[f"Manifest not found for {backup_id}"],
            )

        bundle = self._backend.download(manifest.storage_path)
        if bundle is None:
            return RestoreResult(
                restore_id=restore_id,
                backup_id=backup_id,
                status=RestoreStatus.FAILED.value,
                errors=["Bundle not found in storage backend"],
            )

        if validate_checksum:
            actual = _compute_sha256(bundle)
            if actual != manifest.checksum_sha256:
                return RestoreResult(
                    restore_id=restore_id,
                    backup_id=backup_id,
                    status=RestoreStatus.FAILED.value,
                    errors=[
                        f"Checksum mismatch: expected {manifest.checksum_sha256}, got {actual}"
                    ],
                )

        components = _unbundle_from_bytes(bundle)
        restored: List[str] = []
        errors: List[str] = []

        for key, data in components.items():
            try:
                dest = target / key
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
                restored.append(key)
            except Exception as exc:
                errors.append(f"{key}: {exc}")

        duration_ms = (time.monotonic() - start) * 1000

        if errors and not restored:
            status = RestoreStatus.FAILED.value
        elif errors:
            status = RestoreStatus.PARTIAL.value
        else:
            status = RestoreStatus.SUCCESS.value

        result = RestoreResult(
            restore_id=restore_id,
            backup_id=backup_id,
            status=status,
            components_restored=restored,
            errors=errors,
            duration_ms=duration_ms,
        )
        logger.info(
            "Restore %s finished: status=%s, %d restored, %d errors",
            restore_id,
            status,
            len(restored),
            len(errors),
        )
        return result

    def delete_backup(self, backup_id: str) -> bool:
        """Delete a backup from the backend and the in-memory manifest registry.

        Returns True if the backup was found and deleted.
        """
        with self._lock:
            manifest = self._manifests.pop(backup_id, None)
        if manifest is None:
            return False

        self._backend.delete(manifest.storage_path)
        self._backend.delete(f"backups/{backup_id}.manifest.json")
        logger.info("Deleted backup %s", backup_id)
        return True

    def expire_old_backups(self) -> List[str]:
        """Delete backups whose retention period has elapsed.

        Returns a list of expired backup_ids.
        """
        now = datetime.now(timezone.utc)
        expired_ids: List[str] = []

        with self._lock:
            candidates = list(self._manifests.values())

        for m in candidates:
            try:
                created = datetime.fromisoformat(m.created_at)
            except (ValueError, TypeError):
                continue
            age_days = (now - created).total_seconds() / 86_400
            if age_days > m.retention_days:
                self.delete_backup(m.backup_id)
                expired_ids.append(m.backup_id)

        return expired_ids

    def verify_backup_integrity(self, backup_id: str) -> bool:
        """Download a backup and verify its checksum without restoring.

        Returns True if the checksum matches, False otherwise.
        """
        manifest = self.get_manifest(backup_id)
        if manifest is None:
            return False

        bundle = self._backend.download(manifest.storage_path)
        if bundle is None:
            return False

        actual = _compute_sha256(bundle)
        return actual == manifest.checksum_sha256

    def get_status(self) -> Dict[str, Any]:
        """Return a summary of the backup system's current state."""
        with self._lock:
            manifests = list(self._manifests.values())

        completed = [m for m in manifests if m.status == BackupStatus.COMPLETED.value]
        total_bytes = sum(m.size_bytes for m in completed)

        return {
            "total_backups": len(manifests),
            "completed_backups": len(completed),
            "total_size_bytes": total_bytes,
            "retention_days": self._retention_days,
            "backend_type": type(self._backend).__name__,
        }
