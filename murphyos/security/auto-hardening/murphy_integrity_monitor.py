# SPDX-License-Identifier: LicenseRef-BSL-1.1
# © 2020 Inoni Limited Liability Company — Creator: Corey Post — BSL 1.1
"""File integrity monitoring — ``IntegrityMonitor``.

Builds SHA3-256 baselines for protected paths, continuously verifies file
hashes, and on tampering detection quarantines the compromised file and
restores from a known-good backup.

Baselines may optionally be PQC-signed to prevent an attacker from
silently replacing the baseline itself.

Error codes: MURPHY-AUTOSEC-ERR-061 .. MURPHY-AUTOSEC-ERR-075
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import pathlib
import shutil
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("murphy.autosec.integrity_monitor")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BASELINE_DIR = pathlib.Path("/var/lib/murphy/integrity")
QUARANTINE_DIR = pathlib.Path("/var/lib/murphy/quarantine")
BACKUP_DIR = pathlib.Path("/var/lib/murphy/integrity_backups")
CHECK_INTERVAL = 300  # seconds


def _sha3_256_file(path: pathlib.Path) -> str:
    """Compute SHA3-256 hex digest of *path* (streaming)."""
    h = hashlib.sha3_256()
    try:
        with open(path, "rb") as fh:
            while True:
                chunk = fh.read(1 << 16)
                if not chunk:
                    break
                h.update(chunk)
    except OSError as exc:  # MURPHY-AUTOSEC-ERR-061
        logger.error("MURPHY-AUTOSEC-ERR-061: Cannot hash %s: %s", path, exc)
        return ""
    return h.hexdigest()


# ---------------------------------------------------------------------------
# IntegrityMonitor
# ---------------------------------------------------------------------------
class IntegrityMonitor:
    """File integrity monitoring engine.

    Parameters
    ----------
    watched_paths : list[str]
        Directories / files to monitor.
    baseline_dir : pathlib.Path
        Where to store baseline files.
    pqc_sign : callable, optional
        ``(data: bytes) -> bytes`` signer for the baseline.
    pqc_verify : callable, optional
        ``(data: bytes, signature: bytes) -> bool`` verifier.
    check_interval : int
        Seconds between periodic integrity checks.
    """

    def __init__(
        self,
        watched_paths: Optional[List[str]] = None,
        baseline_dir: pathlib.Path = BASELINE_DIR,
        pqc_sign: Optional[Callable[[bytes], bytes]] = None,
        pqc_verify: Optional[Callable[[bytes, bytes], bool]] = None,
        check_interval: int = CHECK_INTERVAL,
    ) -> None:
        self._watched: List[pathlib.Path] = [
            pathlib.Path(p) for p in (watched_paths or [])
        ]
        self._baseline_dir = baseline_dir
        self._pqc_sign = pqc_sign
        self._pqc_verify = pqc_verify
        self._check_interval = check_interval
        self._baseline: Dict[str, str] = {}  # path → sha3-256
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        logger.info("IntegrityMonitor initialised (%d paths).", len(self._watched))

    # -- baseline management ------------------------------------------------

    def build_baseline(self) -> Dict[str, str]:
        """Walk all watched paths and compute SHA3-256 digests.

        Returns the baseline dict ``{path: hash}``.
        """
        baseline: Dict[str, str] = {}
        for root in self._watched:
            if root.is_file():
                h = _sha3_256_file(root)
                if h:
                    baseline[str(root)] = h
                continue
            if not root.is_dir():
                logger.warning(
                    "MURPHY-AUTOSEC-ERR-062: Watched path %s does not exist.", root
                )
                continue
            for dirpath, _, filenames in os.walk(root):
                for fn in filenames:
                    fp = pathlib.Path(dirpath) / fn
                    h = _sha3_256_file(fp)
                    if h:
                        baseline[str(fp)] = h

        with self._lock:
            self._baseline = baseline

        self._persist_baseline()
        self._create_backups()
        logger.info("Baseline built: %d files.", len(baseline))
        return baseline

    def _persist_baseline(self) -> None:
        """Write the baseline to disk, optionally PQC-signed."""
        try:
            self._baseline_dir.mkdir(parents=True, exist_ok=True)
            payload = json.dumps(self._baseline, sort_keys=True).encode()
            path = self._baseline_dir / "baseline.json"
            path.write_bytes(payload)

            if callable(self._pqc_sign):
                try:
                    sig = self._pqc_sign(payload)
                    (self._baseline_dir / "baseline.sig").write_bytes(sig)
                    logger.debug("Baseline PQC-signed.")
                except Exception as exc:  # MURPHY-AUTOSEC-ERR-063
                    logger.warning(
                        "MURPHY-AUTOSEC-ERR-063: Baseline signing failed: %s", exc
                    )
        except Exception as exc:  # MURPHY-AUTOSEC-ERR-064
            logger.error("MURPHY-AUTOSEC-ERR-064: Baseline persist failed: %s", exc)

    def load_baseline(self) -> bool:
        """Load baseline from disk and optionally verify PQC signature."""
        path = self._baseline_dir / "baseline.json"
        try:
            payload = path.read_bytes()
        except FileNotFoundError:
            logger.warning("MURPHY-AUTOSEC-ERR-065: No baseline file found.")
            return False
        except Exception as exc:  # MURPHY-AUTOSEC-ERR-066
            logger.error("MURPHY-AUTOSEC-ERR-066: Baseline read error: %s", exc)
            return False

        # Verify signature
        sig_path = self._baseline_dir / "baseline.sig"
        if callable(self._pqc_verify) and sig_path.exists():
            try:
                sig = sig_path.read_bytes()
                if not self._pqc_verify(payload, sig):
                    logger.error(
                        "MURPHY-AUTOSEC-ERR-067: Baseline signature INVALID — "
                        "possible tampering!"
                    )
                    return False
            except Exception as exc:  # MURPHY-AUTOSEC-ERR-068
                logger.error(
                    "MURPHY-AUTOSEC-ERR-068: Baseline sig verification error: %s", exc
                )
                return False

        with self._lock:
            self._baseline = json.loads(payload)
        logger.info("Baseline loaded: %d files.", len(self._baseline))
        return True

    # -- verification -------------------------------------------------------

    def verify_integrity(self) -> List[str]:
        """Compare current file hashes against the baseline.

        Returns a list of paths that have changed or are missing.
        """
        changed: List[str] = []
        with self._lock:
            baseline = dict(self._baseline)

        for filepath, expected in baseline.items():
            p = pathlib.Path(filepath)
            if not p.exists():
                logger.warning(
                    "MURPHY-AUTOSEC-ERR-069: File missing: %s", filepath
                )
                changed.append(filepath)
                continue
            current = _sha3_256_file(p)
            if current != expected:
                logger.warning(
                    "MURPHY-AUTOSEC-ERR-070: Integrity mismatch: %s "
                    "(expected=%s, got=%s)",
                    filepath,
                    expected[:16],
                    current[:16],
                )
                changed.append(filepath)

        if changed:
            logger.warning(
                "Integrity check: %d file(s) changed or missing.", len(changed)
            )
        else:
            logger.debug("Integrity check passed (%d files).", len(baseline))
        return changed

    # -- tamper response ----------------------------------------------------

    def on_tampering_detected(self, filepath: str) -> bool:
        """Quarantine a tampered file and restore from backup.

        Returns *True* if restore succeeded.
        """
        src = pathlib.Path(filepath)
        # Quarantine
        try:
            QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
            ts = int(time.time())
            dest = QUARANTINE_DIR / f"{src.name}.{ts}.quarantined"
            if src.exists():
                shutil.move(str(src), str(dest))
                logger.info("Quarantined %s → %s", filepath, dest)
        except Exception as exc:  # MURPHY-AUTOSEC-ERR-071
            logger.error(
                "MURPHY-AUTOSEC-ERR-071: Quarantine failed for %s: %s",
                filepath,
                exc,
            )

        # Restore from backup
        backup = BACKUP_DIR / hashlib.sha256(filepath.encode()).hexdigest()
        if backup.exists():
            try:
                shutil.copy2(str(backup), filepath)
                logger.info("Restored %s from backup.", filepath)
                return True
            except Exception as exc:  # MURPHY-AUTOSEC-ERR-072
                logger.error(
                    "MURPHY-AUTOSEC-ERR-072: Restore failed for %s: %s",
                    filepath,
                    exc,
                )
                return False
        else:
            logger.warning(
                "MURPHY-AUTOSEC-ERR-073: No backup available for %s.", filepath
            )
            return False

    def _create_backups(self) -> None:
        """Create backup copies of all baselined files."""
        try:
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        except Exception as exc:  # MURPHY-AUTOSEC-ERR-074
            logger.error("MURPHY-AUTOSEC-ERR-074: Backup dir creation failed: %s", exc)
            return

        with self._lock:
            baseline = dict(self._baseline)

        for filepath in baseline:
            src = pathlib.Path(filepath)
            if not src.is_file():
                continue
            dest = BACKUP_DIR / hashlib.sha256(filepath.encode()).hexdigest()
            try:
                shutil.copy2(str(src), str(dest))
            except Exception as exc:  # MURPHY-AUTOSEC-ERR-074
                logger.error(
                    "MURPHY-AUTOSEC-ERR-074: Backup of %s failed: %s",
                    filepath,
                    exc,
                )

    # -- continuous monitoring -----------------------------------------------

    def start(self) -> None:
        """Start background integrity checking."""
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("IntegrityMonitor continuous checking started.")

    def stop(self) -> None:
        """Stop background integrity checking."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=10)
        logger.info("IntegrityMonitor stopped.")

    def _run_loop(self) -> None:
        """Periodically verify integrity."""
        while self._running:
            try:
                changed = self.verify_integrity()
                for fp in changed:
                    self.on_tampering_detected(fp)
            except Exception as exc:  # MURPHY-AUTOSEC-ERR-075
                logger.error(
                    "MURPHY-AUTOSEC-ERR-075: Monitoring loop error: %s", exc
                )
            time.sleep(self._check_interval)
