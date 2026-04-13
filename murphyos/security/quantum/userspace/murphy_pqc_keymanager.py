# SPDX-License-Identifier: LicenseRef-BSL-1.1
# © 2020 Inoni Limited Liability Company — Creator: Corey Post — BSL 1.1
"""
murphy_pqc_keymanager — PQC Key Management Daemon for MurphyOS.

Runs as a systemd service (murphy-pqc-keymanager.service).  Responsible for:

  • Generating and rotating ML-KEM / ML-DSA keypairs on schedule.
  • Pushing HMAC session keys to the kernel via ioctl on /dev/murphy-event.
  • Storing keys in /murphy/keys/ with strict POSIX permissions.
  • Distributing public keys to fleet peers over an async HTTP client.
  • Audit-logging every key operation.

---------------------------------------------------------------------------
Error-code registry
---------------------------------------------------------------------------
MURPHY-PQC-ERR-100  ioctl SET_PQC_KEY failed
MURPHY-PQC-ERR-101  Failed to load epoch file
MURPHY-PQC-ERR-102  aiohttp not available for fleet key distribution
MURPHY-PQC-ERR-103  Fleet key distribution to peer failed
MURPHY-PQC-ERR-104  PQC key rotation failed (PQCError)
MURPHY-PQC-ERR-105  Unexpected error during key rotation
MURPHY-PQC-ERR-106  Failed to load pqc.yaml configuration
---------------------------------------------------------------------------
"""
from __future__ import annotations

import asyncio
import ctypes
import fcntl
import hashlib
import json
import logging
import os
import signal
import struct
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from murphy_pqc import (
    PQCError,
    generate_hash_sig_keypair,
    generate_kem_keypair,
    generate_sig_keypair,
    hkdf_sha3_256,
)

# ---------------------------------------------------------------------------
# Configuration defaults
# ---------------------------------------------------------------------------

DEFAULT_KEY_DIR           = Path("/murphy/keys")
DEFAULT_AUDIT_LOG         = Path("/murphy/logs/pqc-audit.log")
DEFAULT_DEVICE_PATH       = "/dev/murphy-event"
DEFAULT_ROTATION_HOURS    = 24
DEFAULT_PEER_ENDPOINTS: List[str] = []

# Kernel ioctl constants — must match murphy_pqc_kmod.h
_MURPHY_PQC_IOC_MAGIC   = ord("M")
_MURPHY_PQC_KEY_SIZE     = 32
_IOC_WRITE               = 1
# _IOW('M', 1, struct murphy_pqc_key) — struct is 36 bytes (32 + 4)
_MURPHY_IOC_SET_PQC_KEY  = (
    (_IOC_WRITE << 30)
    | (_MURPHY_PQC_IOC_MAGIC << 8)
    | 1
    | (36 << 16)
)

# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------

logger = logging.getLogger("murphy.pqc.keymanager")


def _setup_audit_logger(path: Path) -> logging.Logger:
    """Create a dedicated file-based audit logger."""
    audit = logging.getLogger("murphy.pqc.keymanager.audit")
    audit.setLevel(logging.INFO)
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(str(path))
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s"),
    )
    audit.addHandler(handler)
    return audit


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class KeyBundle:
    """A timestamped collection of PQC keypairs."""

    epoch: int
    kem_pk: bytes = b""
    kem_sk: bytes = b""
    sig_pk: bytes = b""
    sig_sk: bytes = b""
    hash_sig_pk: bytes = b""
    hash_sig_sk: bytes = b""
    hmac_key: bytes = b""
    created_at: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Key Manager
# ---------------------------------------------------------------------------

class PQCKeyManager:
    """Core key-management logic."""

    def __init__(
        self,
        key_dir: Path = DEFAULT_KEY_DIR,
        device_path: str = DEFAULT_DEVICE_PATH,
        rotation_hours: int = DEFAULT_ROTATION_HOURS,
        audit_log_path: Path = DEFAULT_AUDIT_LOG,
        peer_endpoints: Optional[List[str]] = None,
    ) -> None:
        self.key_dir = key_dir
        self.device_path = device_path
        self.rotation_seconds = rotation_hours * 3600
        self.peer_endpoints = peer_endpoints or DEFAULT_PEER_ENDPOINTS
        self._epoch = self._load_epoch()
        self._bundle: Optional[KeyBundle] = None
        self._running = True
        self._audit = _setup_audit_logger(audit_log_path)

    # -- Epoch persistence --------------------------------------------------

    def _epoch_file(self) -> Path:
        return self.key_dir / "epoch"

    def _load_epoch(self) -> int:
        ef = self._epoch_file()
        if ef.exists():
            try:
                return int(ef.read_text().strip())
            except (ValueError, OSError) as exc:  # MURPHY-PQC-ERR-101
                logger.debug("MURPHY-PQC-ERR-101: failed to load epoch file: %s", exc)
        return 0

    def _save_epoch(self) -> None:
        ef = self._epoch_file()
        ef.parent.mkdir(parents=True, exist_ok=True)
        ef.write_text(str(self._epoch))
        os.chmod(ef, 0o600)

    # -- Key generation -----------------------------------------------------

    def generate_bundle(self) -> KeyBundle:
        """Generate a full set of PQC keypairs and an HMAC session key."""
        self._epoch += 1
        self._audit.info("KEYGEN epoch=%d", self._epoch)

        kem_pk, kem_sk = generate_kem_keypair()
        sig_pk, sig_sk = generate_sig_keypair()
        hash_sig_pk, hash_sig_sk = generate_hash_sig_keypair()
        hmac_key = hkdf_sha3_256(
            kem_sk[:32] + sig_sk[:32],
            info=b"murphy-hmac-session",
            length=32,
        )

        bundle = KeyBundle(
            epoch=self._epoch,
            kem_pk=kem_pk, kem_sk=kem_sk,
            sig_pk=sig_pk, sig_sk=sig_sk,
            hash_sig_pk=hash_sig_pk, hash_sig_sk=hash_sig_sk,
            hmac_key=hmac_key,
        )
        self._bundle = bundle
        self._save_epoch()
        self._persist_keys(bundle)
        self._audit.info("KEYGEN complete epoch=%d", self._epoch)
        return bundle

    # -- Persistence --------------------------------------------------------

    def _persist_keys(self, bundle: KeyBundle) -> None:
        """Write keypairs to disk with strict permissions."""
        self.key_dir.mkdir(parents=True, exist_ok=True)

        for name, data in [
            ("kem.pub", bundle.kem_pk),
            ("kem.sec", bundle.kem_sk),
            ("sig.pub", bundle.sig_pk),
            ("sig.sec", bundle.sig_sk),
            ("hash_sig.pub", bundle.hash_sig_pk),
            ("hash_sig.sec", bundle.hash_sig_sk),
            ("hmac.key", bundle.hmac_key),
        ]:
            p = self.key_dir / name
            p.write_bytes(data)
            os.chmod(p, 0o600)
            self._audit.info("PERSIST key=%s size=%d", name, len(data))

        meta = {
            "epoch": bundle.epoch,
            "created_at": bundle.created_at,
            "kem_pk_sha3": hashlib.sha3_256(bundle.kem_pk).hexdigest(),
            "sig_pk_sha3": hashlib.sha3_256(bundle.sig_pk).hexdigest(),
        }
        meta_path = self.key_dir / "meta.json"
        meta_path.write_text(json.dumps(meta, indent=2))
        os.chmod(meta_path, 0o600)

    # -- Kernel ioctl -------------------------------------------------------

    def push_key_to_kernel(self, bundle: KeyBundle) -> bool:
        """Push the HMAC session key to /dev/murphy-event via ioctl."""
        try:
            payload = bundle.hmac_key + struct.pack("<I", bundle.epoch)
            with open(self.device_path, "wb", buffering=0) as dev:
                fcntl.ioctl(dev.fileno(), _MURPHY_IOC_SET_PQC_KEY, payload)
            self._audit.info(
                "IOCTL SET_PQC_KEY epoch=%d", bundle.epoch,
            )
            return True
        except OSError as exc:
            logger.error(
                "MURPHY-PQC-ERR-100: ioctl failed: %s", exc,
            )
            self._audit.error(
                "IOCTL FAIL epoch=%d error=%s", bundle.epoch, exc,
            )
            return False

    # -- Fleet distribution -------------------------------------------------

    async def distribute_public_keys(self, bundle: KeyBundle) -> None:
        """Send public keys to trusted fleet peers."""
        if not self.peer_endpoints:
            return

        payload = json.dumps({
            "epoch": bundle.epoch,
            "kem_pk": bundle.kem_pk.hex(),
            "sig_pk": bundle.sig_pk.hex(),
            "hash_sig_pk": bundle.hash_sig_pk.hex(),
        }).encode()

        try:
            import aiohttp  # type: ignore[import-untyped]
        except ImportError:  # MURPHY-PQC-ERR-102
            logger.warning(
                "MURPHY-PQC-ERR-102: aiohttp not available — skipping fleet key distribution",
            )
            return

        async with aiohttp.ClientSession() as session:
            for endpoint in self.peer_endpoints:
                try:
                    async with session.post(
                        endpoint,
                        data=payload,
                        headers={"Content-Type": "application/json"},
                        timeout=aiohttp.ClientTimeout(total=10),
                    ) as resp:
                        self._audit.info(
                            "FLEET DISTRIBUTE peer=%s status=%d epoch=%d",
                            endpoint, resp.status, bundle.epoch,
                        )
                except Exception as exc:  # MURPHY-PQC-ERR-103
                    self._audit.error(
                        "MURPHY-PQC-ERR-103: FLEET FAIL peer=%s error=%s", endpoint, exc,
                    )

    # -- Rotation loop ------------------------------------------------------

    async def run(self) -> None:
        """Main rotation loop — runs until SIGTERM / SIGINT."""
        logger.info("PQC Key Manager starting (rotation every %ds)", self.rotation_seconds)
        self._audit.info("DAEMON START rotation=%ds", self.rotation_seconds)

        while self._running:
            try:
                bundle = self.generate_bundle()
                self.push_key_to_kernel(bundle)
                await self.distribute_public_keys(bundle)
            except PQCError as exc:  # MURPHY-PQC-ERR-104
                logger.error("MURPHY-PQC-ERR-104: Key rotation failed: %s", exc)
                self._audit.error("MURPHY-PQC-ERR-104: ROTATION FAIL: %s", exc)
            except Exception as exc:  # MURPHY-PQC-ERR-105
                logger.exception("MURPHY-PQC-ERR-105: Unexpected error during rotation: %s", exc)
                self._audit.error("MURPHY-PQC-ERR-105: ROTATION UNEXPECTED: %s", exc)

            # Sleep in small increments so we can respond to shutdown quickly
            remaining = self.rotation_seconds
            while remaining > 0 and self._running:
                await asyncio.sleep(min(remaining, 5))
                remaining -= 5

        self._audit.info("DAEMON STOP")
        logger.info("PQC Key Manager stopped")

    def stop(self) -> None:
        """Signal the daemon to shut down gracefully."""
        self._running = False


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _load_config() -> Dict[str, Any]:
    """Load configuration from pqc.yaml if available."""
    config_paths = [
        Path("/etc/murphy/pqc.yaml"),
        Path(__file__).resolve().parent.parent / "pqc.yaml",
    ]
    for p in config_paths:
        if p.exists():
            try:
                import yaml  # type: ignore[import-untyped]
                return yaml.safe_load(p.read_text()).get("pqc", {})
            except Exception as exc:  # MURPHY-PQC-ERR-106
                logger.debug("MURPHY-PQC-ERR-106: failed to load config %s: %s", p, exc)
    return {}


def main() -> None:
    """Daemon entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    )

    config = _load_config()
    manager = PQCKeyManager(
        key_dir=Path(config.get("key_storage", str(DEFAULT_KEY_DIR))),
        rotation_hours=int(config.get("key_rotation_hours", DEFAULT_ROTATION_HOURS)),
        audit_log_path=Path(config.get("audit_log", str(DEFAULT_AUDIT_LOG))),
    )

    loop = asyncio.new_event_loop()

    def _shutdown(signum: int, frame: Any) -> None:
        logger.info("Received signal %d — shutting down", signum)
        manager.stop()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    try:
        loop.run_until_complete(manager.run())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
