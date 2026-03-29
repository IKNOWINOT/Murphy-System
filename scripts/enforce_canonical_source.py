#!/usr/bin/env python3
"""
enforce_canonical_source.py — Source drift guard for Murphy System.

Compares files that exist in BOTH the repo root and `Murphy System/` to
verify they are byte-identical.  Exits non-zero if any pair has drifted.

Usage:
    python scripts/enforce_canonical_source.py

Can also be imported and called programmatically:
    from scripts.enforce_canonical_source import check_drift
    drifted = check_drift()   # returns list of (root_path, mirror_path) tuples
"""

from __future__ import annotations

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Files that MUST be byte-identical between root and Murphy System/
# ---------------------------------------------------------------------------
PAIRED_FILES: list[str] = [
    ".env.example",
    ".coveragerc",
    ".dockerignore",
    ".gitattributes",
    "Dockerfile",
    "docker-compose.yml",
    "requirements.txt",
    "ARCHITECTURE_MAP.md",
    "inoni_business_automation.py",
    "Makefile",
    "LICENSE",
    "setup.py",
    "pyproject.toml",
]


def _read_bytes(path: Path) -> bytes | None:
    """Return file contents or None if the file does not exist."""
    if not path.exists():
        return None
    return path.read_bytes()


def check_drift(
    repo_root: Path | None = None,
    *,
    verbose: bool = True,
) -> list[tuple[Path, Path]]:
    """Compare paired files between root and ``Murphy System/``.

    Returns a list of (root_path, mirror_path) tuples for every pair that
    has drifted (differs in content).  Files that don't exist in *either*
    location are silently skipped.  Files that exist in only one location
    are reported as warnings but do NOT cause a non-zero exit by themselves
    (the authoritative copy may not have been promoted yet).

    Args:
        repo_root: Path to the repository root.  Defaults to the parent of
            this script's directory (i.e. the repo root when run normally).
        verbose: Print progress and findings to stdout.
    """
    if repo_root is None:
        repo_root = Path(__file__).resolve().parent.parent

    mirror_root = repo_root / "Murphy System"

    if not mirror_root.exists():
        if verbose:
            print("Murphy System/ directory not found — nothing to compare.")
        return []

    drifted: list[tuple[Path, Path]] = []
    skipped: list[str] = []

    for rel in PAIRED_FILES:
        root_path = repo_root / rel
        mirror_path = mirror_root / rel

        root_bytes = _read_bytes(root_path)
        mirror_bytes = _read_bytes(mirror_path)

        if root_bytes is None and mirror_bytes is None:
            # Neither copy exists — nothing to enforce.
            continue

        if root_bytes is None:
            skipped.append(f"  ONLY IN MIRROR: {rel}")
            continue

        if mirror_bytes is None:
            skipped.append(f"  ONLY IN ROOT:   {rel}")
            continue

        if root_bytes != mirror_bytes:
            drifted.append((root_path, mirror_path))

    if verbose:
        if skipped:
            print("Files present in only one location (warnings, not errors):")
            for msg in skipped:
                print(msg)
            print()

        if drifted:
            print(
                f"DRIFT DETECTED: {len(drifted)} file(s) differ between "
                "root and Murphy System/:\n"
            )
            for root_path, mirror_path in drifted:
                rel = root_path.relative_to(repo_root)
                root_size = root_path.stat().st_size
                mirror_size = mirror_path.stat().st_size
                print(
                    f"  {rel}  "
                    f"(root={root_size:,}B  mirror={mirror_size:,}B)"
                )
            print(
                "\nTo fix: copy the canonical Murphy System/ version to root "
                "or vice-versa so both copies are identical.\n"
                "Canonical direction: Murphy System/ → root"
            )
        else:
            print(
                f"OK: All {len(PAIRED_FILES)} paired files are byte-identical "
                "between root and Murphy System/."
            )

    return drifted


def main() -> int:
    drifted = check_drift(verbose=True)
    return 1 if drifted else 0


if __name__ == "__main__":
    sys.exit(main())
