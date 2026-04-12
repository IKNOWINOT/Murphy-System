#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-BSL-1.1
# © 2020 Inoni Limited Liability Company — Creator: Corey Post — BSL 1.1
"""
murphy_manifest_sign — Build-time tool to sign the Murphy runtime manifest.

Walks /murphy/runtime/, hashes every ``.py`` file with SHA3-256, and
creates a signed manifest using SLH-DSA-SHA2-256f (SPHINCS+).

Outputs:
  • manifest.json  — file paths + SHA3-256 hashes
  • manifest.sig   — SLH-DSA signature over manifest.json bytes
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger("murphy.pqc.manifest_sign")

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_RUNTIME_DIR = Path("/murphy/runtime")
DEFAULT_OUTPUT_DIR  = Path("/murphy/runtime")
DEFAULT_KEY_DIR     = Path("/murphy/keys")

# ---------------------------------------------------------------------------
# PQC backend
# ---------------------------------------------------------------------------

try:
    from murphy_pqc import (
        PQCError,
        generate_hash_sig_keypair,
        hash_sign,
    )
    _HAS_PQC = True
except ImportError:
    _HAS_PQC = False

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha3_256_file(path: Path) -> str:
    h = hashlib.sha3_256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Manifest generation
# ---------------------------------------------------------------------------


def build_manifest(
    runtime_dir: Path,
    extensions: tuple[str, ...] = (".py",),
) -> Dict[str, Any]:
    """Walk *runtime_dir* and produce a manifest dictionary."""
    files: List[Dict[str, str]] = []

    for path in sorted(runtime_dir.rglob("*")):
        if not path.is_file():
            continue
        if extensions and path.suffix not in extensions:
            continue

        rel = str(path.relative_to(runtime_dir))
        digest = _sha3_256_file(path)
        files.append({"path": rel, "sha3_256": digest})
        logger.debug("Hashed %s → %s", rel, digest)

    manifest: Dict[str, Any] = {
        "version": 1,
        "created_at": time.time(),
        "runtime_dir": str(runtime_dir),
        "file_count": len(files),
        "files": files,
    }
    logger.info("Manifest built — %d files", len(files))
    return manifest


def sign_manifest(
    manifest_bytes: bytes,
    secret_key: bytes,
) -> bytes:
    """Sign *manifest_bytes* with SLH-DSA-SHA2-256f."""
    if _HAS_PQC:
        return hash_sign(secret_key, manifest_bytes)

    # Fallback: HMAC-SHA3-256
    import hmac as _hmac
    logger.warning("PQC unavailable — using HMAC-SHA3-256 fallback")
    return _hmac.new(secret_key[:64], manifest_bytes, hashlib.sha3_256).digest()


# ---------------------------------------------------------------------------
# Key handling
# ---------------------------------------------------------------------------


def load_or_generate_signing_key(key_dir: Path) -> tuple[bytes, bytes]:
    """Load SLH-DSA signing keys from *key_dir*, or generate new ones."""
    pub_path = key_dir / "hash_sig.pub"
    sec_path = key_dir / "hash_sig.sec"

    if pub_path.exists() and sec_path.exists():
        pk = pub_path.read_bytes()
        sk = sec_path.read_bytes()
        logger.info("Loaded existing SLH-DSA signing key from %s", key_dir)
        return (pk, sk)

    logger.info("Generating new SLH-DSA signing keypair")
    pk, sk = generate_hash_sig_keypair()

    key_dir.mkdir(parents=True, exist_ok=True)
    pub_path.write_bytes(pk)
    sec_path.write_bytes(sk)
    import os
    os.chmod(sec_path, 0o600)
    os.chmod(pub_path, 0o644)
    return (pk, sk)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sign the Murphy runtime manifest with SLH-DSA (SPHINCS+)",
    )
    parser.add_argument(
        "--runtime-dir",
        type=Path,
        default=DEFAULT_RUNTIME_DIR,
        help="Directory containing the Murphy runtime files",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory to write manifest.json and manifest.sig",
    )
    parser.add_argument(
        "--key-dir",
        type=Path,
        default=DEFAULT_KEY_DIR,
        help="Directory containing (or to store) SLH-DSA signing keys",
    )
    parser.add_argument(
        "--extensions",
        nargs="*",
        default=[".py"],
        help="File extensions to include in the manifest (default: .py)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [manifest-sign] %(levelname)s %(message)s",
    )

    if not args.runtime_dir.is_dir():
        logger.error("Runtime directory does not exist: %s", args.runtime_dir)
        return 1

    # Build manifest
    manifest = build_manifest(
        args.runtime_dir,
        extensions=tuple(args.extensions),
    )
    manifest_json = json.dumps(manifest, indent=2).encode("utf-8")

    # Sign
    _pk, sk = load_or_generate_signing_key(args.key_dir)
    signature = sign_manifest(manifest_json, sk)

    # Write outputs
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.output_dir / "manifest.json"
    sig_path = args.output_dir / "manifest.sig"

    manifest_path.write_bytes(manifest_json)
    sig_path.write_bytes(signature)

    logger.info("Wrote %s (%d bytes)", manifest_path, len(manifest_json))
    logger.info("Wrote %s (%d bytes)", sig_path, len(signature))
    return 0


if __name__ == "__main__":
    sys.exit(main())
