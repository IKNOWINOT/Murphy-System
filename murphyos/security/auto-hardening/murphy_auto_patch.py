# SPDX-License-Identifier: LicenseRef-BSL-1.1
# © 2020 Inoni Limited Liability Company — Creator: Corey Post — BSL 1.1
"""Self-updating security with safe rollback.

``AutoPatchEngine`` checks for upstream security patches, verifies their
PQC signatures, creates a filesystem snapshot (btrfs / LVM — falls back to
tar), applies the patch, and rolls back automatically on failure.

The engine **never** reboots without explicit user consent.

Error codes: MURPHY-AUTOSEC-ERR-011 .. MURPHY-AUTOSEC-ERR-020
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import pathlib
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("murphy.autosec.auto_patch")

# ---------------------------------------------------------------------------
# Optional dependency
# ---------------------------------------------------------------------------
try:
    import urllib.request as _urlreq
except ImportError as exc:  # MURPHY-AUTOSEC-ERR-011
    _urlreq = None  # type: ignore[assignment]
    logger.warning("MURPHY-AUTOSEC-ERR-011: urllib.request unavailable: %s", exc)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_PATCH_URL = "https://updates.murphyos.local/patches/latest.json"
SNAPSHOT_DIR = pathlib.Path("/var/lib/murphy/snapshots")
BACKUP_DIR = pathlib.Path("/var/lib/murphy/backups")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _run(cmd: List[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    """Run a subprocess, capturing output."""
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=300, **kwargs
    )


def _sha3_256(data: bytes) -> str:
    return hashlib.sha3_256(data).hexdigest()


# ---------------------------------------------------------------------------
# AutoPatchEngine
# ---------------------------------------------------------------------------
class AutoPatchEngine:
    """Self-updating security patch engine with rollback.

    Parameters
    ----------
    patch_url : str
        URL of the JSON manifest listing available patches.
    root_dir : pathlib.Path
        Root directory of the Murphy installation to patch.
    pqc_verify : callable, optional
        ``(data: bytes, signature: bytes) -> bool`` verifier using PQC keys.
    """

    def __init__(
        self,
        patch_url: str = DEFAULT_PATCH_URL,
        root_dir: Optional[pathlib.Path] = None,
        pqc_verify: Optional[object] = None,
    ) -> None:
        self.patch_url = patch_url
        self.root_dir = root_dir or pathlib.Path("/opt/murphy")
        self._pqc_verify = pqc_verify
        self._last_check: float = 0
        self._snapshot_method: Optional[str] = None
        self._detect_snapshot_backend()
        logger.info(
            "AutoPatchEngine initialised (snapshot backend=%s).",
            self._snapshot_method,
        )

    # -- snapshot backend detection -----------------------------------------

    def _detect_snapshot_backend(self) -> None:
        """Detect btrfs, LVM, or fall back to tar."""
        try:
            res = _run(["btrfs", "subvolume", "show", str(self.root_dir)])
            if res.returncode == 0:
                self._snapshot_method = "btrfs"
                return
        except FileNotFoundError:  # MURPHY-AUTOSEC-ERR-011
            logger.debug("MURPHY-AUTOSEC-ERR-011: btrfs not installed — skipping")
        except Exception as exc:  # MURPHY-AUTOSEC-ERR-012
            logger.debug("MURPHY-AUTOSEC-ERR-012: btrfs probe failed: %s", exc)

        try:
            res = _run(["lvs", "--noheadings", "-o", "lv_name"])
            if res.returncode == 0 and res.stdout.strip():
                self._snapshot_method = "lvm"
                return
        except FileNotFoundError:  # MURPHY-AUTOSEC-ERR-014
            logger.debug("MURPHY-AUTOSEC-ERR-014: LVM not installed — skipping")
        except Exception as exc:  # MURPHY-AUTOSEC-ERR-013
            logger.debug("MURPHY-AUTOSEC-ERR-013: LVM probe failed: %s", exc)

        self._snapshot_method = "tar"
        logger.info("Snapshot backend: tar (fallback).")

    # -- snapshot management ------------------------------------------------

    def _create_snapshot(self, label: str) -> Optional[pathlib.Path]:
        """Create a snapshot of *root_dir* and return the snapshot path."""
        ts = int(time.time())
        snap_name = f"murphy-snap-{label}-{ts}"

        try:
            if self._snapshot_method == "btrfs":
                dest = SNAPSHOT_DIR / snap_name
                _run(["btrfs", "subvolume", "snapshot", str(self.root_dir), str(dest)])
                logger.info("Created btrfs snapshot: %s", dest)
                return dest

            if self._snapshot_method == "lvm":
                _run(["lvcreate", "--snapshot", "--name", snap_name, "--size", "1G",
                      str(self.root_dir)])
                logger.info("Created LVM snapshot: %s", snap_name)
                return SNAPSHOT_DIR / snap_name

            # Fallback — tar
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            tar_path = BACKUP_DIR / f"{snap_name}.tar.gz"
            _run(["tar", "czf", str(tar_path), "-C", str(self.root_dir.parent),
                  self.root_dir.name])
            logger.info("Created tar snapshot: %s", tar_path)
            return tar_path

        except Exception as exc:  # MURPHY-AUTOSEC-ERR-014
            logger.error(
                "MURPHY-AUTOSEC-ERR-014: Snapshot creation failed: %s", exc
            )
            return None

    def _restore_snapshot(self, snap_path: pathlib.Path) -> bool:
        """Restore *root_dir* from a previously-created snapshot."""
        try:
            if self._snapshot_method == "btrfs":
                _run(["btrfs", "subvolume", "delete", str(self.root_dir)])
                _run(["btrfs", "subvolume", "snapshot", str(snap_path), str(self.root_dir)])
            elif self._snapshot_method == "lvm":
                _run(["lvconvert", "--merge", str(snap_path)])
            else:
                _run(["tar", "xzf", str(snap_path), "-C", str(self.root_dir.parent)])
            logger.info("Restored snapshot from %s.", snap_path)
            return True
        except Exception as exc:  # MURPHY-AUTOSEC-ERR-015
            logger.error(
                "MURPHY-AUTOSEC-ERR-015: Snapshot restore failed: %s", exc
            )
            return False

    # -- public API ---------------------------------------------------------

    def check_updates(self) -> List[Dict[str, Any]]:
        """Poll the upstream patch manifest and return available patches."""
        if _urlreq is None:
            logger.error("MURPHY-AUTOSEC-ERR-011: No HTTP client available.")
            return []

        try:
            req = _urlreq.Request(self.patch_url, headers={"User-Agent": "MurphyOS-AutoPatch/1.0"})
            with _urlreq.urlopen(req, timeout=30) as resp:
                manifest = json.loads(resp.read().decode())
            self._last_check = time.time()
            patches: List[Dict[str, Any]] = manifest.get("patches", [])
            logger.info("Found %d available patch(es).", len(patches))
            return patches
        except Exception as exc:  # MURPHY-AUTOSEC-ERR-016
            logger.error(
                "MURPHY-AUTOSEC-ERR-016: Update check failed: %s", exc
            )
            return []

    def _verify_patch(self, data: bytes, signature: bytes) -> bool:
        """Verify a patch payload against its PQC signature."""
        if callable(self._pqc_verify):
            try:
                return bool(self._pqc_verify(data, signature))
            except Exception as exc:  # MURPHY-AUTOSEC-ERR-017
                logger.error(
                    "MURPHY-AUTOSEC-ERR-017: PQC verification error: %s", exc
                )
                return False
        logger.warning(
            "MURPHY-AUTOSEC-ERR-017: No PQC verifier configured; "
            "skipping signature check (INSECURE)."
        )
        return True

    def apply_patch(self, patch_meta: Dict[str, Any]) -> bool:
        """Download, verify, snapshot, and apply a single patch.

        Returns *True* on success.  On failure the engine rolls back.
        """
        url: str = patch_meta.get("url", "")
        expected_hash: str = patch_meta.get("sha3_256", "")
        sig_hex: str = patch_meta.get("signature", "")

        if not url:
            logger.error("MURPHY-AUTOSEC-ERR-018: Patch URL missing.")
            return False

        # Download
        try:
            req = _urlreq.Request(url, headers={"User-Agent": "MurphyOS-AutoPatch/1.0"})  # type: ignore[union-attr]
            with _urlreq.urlopen(req, timeout=120) as resp:  # type: ignore[union-attr]
                data = resp.read()
        except Exception as exc:  # MURPHY-AUTOSEC-ERR-018
            logger.error("MURPHY-AUTOSEC-ERR-018: Download failed: %s", exc)
            return False

        # Integrity
        if expected_hash and _sha3_256(data) != expected_hash:
            logger.error("MURPHY-AUTOSEC-ERR-019: SHA3-256 mismatch — aborting.")
            return False

        # Signature
        if not self._verify_patch(data, bytes.fromhex(sig_hex) if sig_hex else b""):
            logger.error("MURPHY-AUTOSEC-ERR-017: Signature verification failed.")
            return False

        # Snapshot
        snap = self._create_snapshot("pre-patch")
        if snap is None:
            logger.error(
                "MURPHY-AUTOSEC-ERR-014: Cannot create pre-patch snapshot; aborting."
            )
            return False

        # Apply
        try:
            patch_file = self.root_dir / ".murphy_patch_tmp"
            patch_file.write_bytes(data)
            res = _run(["patch", "-d", str(self.root_dir), "-p1", "-i", str(patch_file)])
            patch_file.unlink(missing_ok=True)
            if res.returncode != 0:
                raise RuntimeError(res.stderr)
            logger.info("Patch applied successfully.")
            return True
        except Exception as exc:  # MURPHY-AUTOSEC-ERR-020
            logger.error(
                "MURPHY-AUTOSEC-ERR-020: Patch application failed: %s — rolling back.", exc
            )
            self.rollback(snap)
            return False

    def rollback(self, snapshot_path: Optional[pathlib.Path] = None) -> bool:
        """Roll back to a snapshot.  Never reboots without consent."""
        if snapshot_path is None:
            logger.error("MURPHY-AUTOSEC-ERR-015: No snapshot path provided for rollback.")
            return False
        ok = self._restore_snapshot(snapshot_path)
        if ok:
            logger.info("Rollback complete. No reboot performed (requires consent).")
        return ok
