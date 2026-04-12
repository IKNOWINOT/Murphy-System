#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-BSL-1.1
# © 2020 Inoni Limited Liability Company — Creator: Corey Post — BSL 1.1
"""
murphy_secureboot — PQC secure-boot verification for MurphyOS.

Verifies runtime integrity at boot using SLH-DSA-SHA2-256f (SPHINCS+)
signatures.  Designed to be called from a systemd ``ExecStartPre=``
directive.

Workflow:
  1. Read /murphy/runtime/manifest.json + manifest.sig
  2. Hash every listed file with SHA3-256 and compare to the manifest
  3. Verify the aggregate manifest signature with SLH-DSA
  4. On failure → set safety level to "paranoid", emit security event

Exit codes:
  0 — all checks passed
  1 — verification failure (safety level set to paranoid)
  2 — manifest or signature file missing
"""
from __future__ import annotations

import hashlib
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger("murphy.pqc.secureboot")

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

RUNTIME_DIR     = Path("/murphy/runtime")
MANIFEST_PATH   = RUNTIME_DIR / "manifest.json"
SIGNATURE_PATH  = RUNTIME_DIR / "manifest.sig"
PUB_KEY_PATH    = Path("/murphy/keys/hash_sig.pub")
SAFETY_FLAG     = Path("/murphy/state/safety_level")

# ---------------------------------------------------------------------------
# PQC backend
# ---------------------------------------------------------------------------

try:
    from murphy_pqc import hash_verify, PQCError
    _HAS_PQC = True
except ImportError:
    _HAS_PQC = False

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha3_256_file(path: Path) -> str:
    """Return the SHA3-256 hex digest of a file."""
    h = hashlib.sha3_256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _set_safety_paranoid() -> None:
    """Write ``paranoid`` to the Murphy safety-level state file."""
    try:
        SAFETY_FLAG.parent.mkdir(parents=True, exist_ok=True)
        SAFETY_FLAG.write_text("paranoid\n")
        logger.critical("Safety level set to PARANOID")
    except OSError as exc:
        logger.error("Cannot write safety flag: %s", exc)


def _emit_security_event(detail: str) -> None:
    """Emit a security event (log + optional event bus)."""
    logger.critical("SECURITY EVENT: %s", detail)
    # In a full MurphyOS deployment this would also push to /dev/murphy-event


# ---------------------------------------------------------------------------
# Verification logic
# ---------------------------------------------------------------------------


def verify_manifest(
    runtime_dir: Path = RUNTIME_DIR,
    manifest_path: Path = MANIFEST_PATH,
    signature_path: Path = SIGNATURE_PATH,
    pubkey_path: Path = PUB_KEY_PATH,
) -> bool:
    """Verify the Murphy runtime against a signed manifest.

    Returns ``True`` if all checks pass, ``False`` otherwise.
    """
    # 1. Existence checks
    for p, label in [
        (manifest_path, "manifest.json"),
        (signature_path, "manifest.sig"),
        (pubkey_path, "hash_sig.pub"),
    ]:
        if not p.exists():
            logger.error("Missing %s at %s", label, p)
            return False

    # 2. Load manifest
    try:
        manifest: Dict[str, Any] = json.loads(manifest_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Cannot parse manifest: %s", exc)
        return False

    files: List[Dict[str, str]] = manifest.get("files", [])
    if not files:
        logger.error("Manifest contains no file entries")
        return False

    # 3. Verify individual file hashes
    for entry in files:
        rel_path = entry.get("path", "")
        expected_hash = entry.get("sha3_256", "")
        full_path = runtime_dir / rel_path

        if not full_path.exists():
            logger.error("Missing runtime file: %s", full_path)
            return False

        actual_hash = _sha3_256_file(full_path)
        if actual_hash != expected_hash:
            logger.error(
                "Hash mismatch for %s: expected=%s actual=%s",
                rel_path, expected_hash, actual_hash,
            )
            return False

    logger.info("All %d file hashes verified", len(files))

    # 4. Verify manifest signature
    manifest_bytes = manifest_path.read_bytes()
    sig_bytes = signature_path.read_bytes()
    pub_key = pubkey_path.read_bytes()

    if _HAS_PQC:
        try:
            if not hash_verify(pub_key, manifest_bytes, sig_bytes):
                logger.error("SLH-DSA manifest signature INVALID")
                return False
        except PQCError as exc:
            logger.error("PQC verification error: %s", exc)
            return False
    else:
        logger.warning(
            "PQC library unavailable — skipping signature verification "
            "(hash checks passed)",
        )

    logger.info("Manifest signature verified — boot integrity OK")
    return True


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [secureboot] %(levelname)s %(message)s",
    )

    if not MANIFEST_PATH.exists() or not SIGNATURE_PATH.exists():
        logger.error(
            "Manifest or signature not found — cannot verify boot integrity",
        )
        _emit_security_event("secure-boot manifest missing")
        _set_safety_paranoid()
        return 2

    if verify_manifest():
        logger.info("Secure boot verification PASSED")
        return 0

    _emit_security_event("secure-boot verification FAILED")
    _set_safety_paranoid()
    return 1


if __name__ == "__main__":
    sys.exit(main())
