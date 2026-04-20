#!/usr/bin/env python3
"""
enforce_canonical_source.py — Source drift guard for Murphy System.

Dynamically discovers all files that exist in BOTH the repo root and
`Murphy System/` and verifies they are byte-identical.  Exits non-zero if
any discovered pair has drifted.

Usage:
    # Full scan (default) — checks all auto-discovered pairs:
    python scripts/enforce_canonical_source.py

    # Session-scoped (PR check) — verifies files changed in this session
    # also had their mirror counterpart updated:
    python scripts/enforce_canonical_source.py --changed-only

Can also be imported and called programmatically:
    from scripts.enforce_canonical_source import check_drift
    drifted = check_drift()   # returns list of (root_path, mirror_path) tuples
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# The name of the mirror subdirectory within the repo root.
_MIRROR_DIR_NAME: str = "Murphy System"

# ---------------------------------------------------------------------------
# Directory names to skip when discovering paired files (applied to every
# path component, not just the top level).
# ---------------------------------------------------------------------------
_SKIP_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        "dist",
        "build",
    }
)

# Individual file names to skip even when they appear in both locations.
_SKIP_FILES: frozenset[str] = frozenset({".DS_Store", "Thumbs.db"})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _should_skip(rel: Path) -> bool:
    """Return True if this relative path should be excluded from pairing."""
    for part in rel.parts[:-1]:
        if part in _SKIP_DIRS or part.endswith(".egg-info"):
            return True
    return rel.name in _SKIP_FILES


def _read_bytes(path: Path) -> bytes | None:
    """Return file contents or None if the file does not exist."""
    if not path.exists():
        return None
    return path.read_bytes()


def _iter_mirror_files(mirror_root: Path):
    """Yield relative paths for every trackable file under *mirror_root*."""
    for p in mirror_root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(mirror_root)
        if _should_skip(rel):
            continue
        # Skip any nested "Murphy System/" directory that may exist inside
        # the mirror (e.g. Murphy System/Murphy System/ — accidental nesting).
        if rel.parts and rel.parts[0] == _MIRROR_DIR_NAME:
            continue
        yield rel


# ---------------------------------------------------------------------------
# Full-scan mode (default)
# ---------------------------------------------------------------------------


def discover_pairs(
    repo_root: Path, mirror_root: Path
) -> list[tuple[Path, Path]]:
    """Return all (root_path, mirror_path) pairs that exist in both locations."""
    pairs: list[tuple[Path, Path]] = []
    for rel in _iter_mirror_files(mirror_root):
        root_file = repo_root / rel
        if root_file.exists() and root_file.is_file():
            pairs.append((root_file, mirror_root / rel))
    return pairs


def check_drift(
    repo_root: Path | None = None,
    *,
    verbose: bool = True,
) -> list[tuple[Path, Path]]:
    """Discover and compare all paired files between root and ``Murphy System/``.

    Returns a list of (root_path, mirror_path) tuples for every pair whose
    content differs.

    Args:
        repo_root: Path to the repository root.  Defaults to the parent of
            this script's directory (i.e. the repo root when run normally).
        verbose: Print progress and findings to stdout.
    """
    if repo_root is None:
        repo_root = Path(__file__).resolve().parent.parent

    mirror_root = repo_root / _MIRROR_DIR_NAME

    if not mirror_root.exists():
        if verbose:
            print("Murphy System/ directory not found — nothing to compare.")
        return []

    pairs = discover_pairs(repo_root, mirror_root)
    drifted: list[tuple[Path, Path]] = []

    for root_path, mirror_path in pairs:
        if _read_bytes(root_path) != _read_bytes(mirror_path):
            drifted.append((root_path, mirror_path))

    if verbose:
        if drifted:
            print(
                f"DRIFT DETECTED: {len(drifted)} file(s) differ between "
                "root and Murphy System/:\n"
            )
            for root_path, mirror_path in drifted:
                rel = root_path.relative_to(repo_root)
                root_size = root_path.stat().st_size
                mirror_size = mirror_path.stat().st_size
                print(f"  {rel}  (root={root_size:,}B  mirror={mirror_size:,}B)")
            print(
                "\nTo fix: copy the canonical Murphy System/ version to root "
                "or vice-versa so both copies are identical.\n"
                "Canonical direction: Murphy System/ → root"
            )
        else:
            print(
                f"OK: All {len(pairs)} auto-discovered paired files are "
                "byte-identical between root and Murphy System/."
            )

    return drifted


# ---------------------------------------------------------------------------
# Session-scoped mode (--changed-only)
# ---------------------------------------------------------------------------


def _get_changed_files(repo_root: Path) -> list[str]:
    """Return file paths changed in the current PR/push relative to main."""
    base_refs = ("origin/main", "origin/HEAD", "HEAD~1")
    for base_ref in base_refs:
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", f"{base_ref}...HEAD"],
                capture_output=True,
                text=True,
                check=True,
                cwd=repo_root,
            )
            files = [f.strip() for f in result.stdout.splitlines() if f.strip()]
            if files or base_ref == base_refs[-1]:
                return files
        except subprocess.CalledProcessError as exc:
            if base_ref != base_refs[-1]:
                print(f"  WARNING: git diff against {base_ref} failed ({exc}), trying next ref.")
            continue
    return []


def check_session_drift(
    repo_root: Path | None = None,
    *,
    verbose: bool = True,
) -> list[tuple[str, str]]:
    """Check only files changed in the current PR/push session.

    For each file changed in this session, verifies that its mirror
    counterpart (if one exists) was ALSO updated in the same changeset.
    Content-identical pairs are not flagged even if neither side appears in
    the changeset (e.g. trivial whitespace-only touches that hash the same).

    Returns a list of ``(changed_file, missing_mirror)`` string tuples for
    every file whose mirror was NOT updated and whose content now differs.
    """
    if repo_root is None:
        repo_root = Path(__file__).resolve().parent.parent

    mirror_root = repo_root / _MIRROR_DIR_NAME

    if not mirror_root.exists():
        if verbose:
            print("Murphy System/ directory not found — nothing to compare.")
        return []

    changed_files = _get_changed_files(repo_root)
    if not changed_files:
        if verbose:
            print("No changed files detected — nothing to check.")
        return []

    if verbose:
        print(f"Session-scoped check: {len(changed_files)} changed file(s).")

    changed_set: set[str] = set(changed_files)
    missing_mirrors: list[tuple[str, str]] = []

    for changed_rel in changed_files:
        changed_path = Path(changed_rel)
        parts = changed_path.parts
        if not parts:
            continue

        if parts[0] == _MIRROR_DIR_NAME:
            # Changed file lives inside Murphy System/ — check its root mirror.
            rel_in_mirror = Path(*parts[1:]) if len(parts) > 1 else None
            if rel_in_mirror is None:
                continue
            root_counterpart_str = str(rel_in_mirror)
            root_file = repo_root / rel_in_mirror
            if not (root_file.exists() and root_file.is_file()):
                continue
            if root_counterpart_str in changed_set:
                continue
            # Mirror was changed but root was not — verify content actually differs.
            mirror_bytes = _read_bytes(mirror_root / rel_in_mirror)
            root_bytes = _read_bytes(root_file)
            if root_bytes != mirror_bytes:
                missing_mirrors.append((changed_rel, root_counterpart_str))
                if verbose:
                    mirror_size = (mirror_root / rel_in_mirror).stat().st_size
                    root_size = root_file.stat().st_size
                    print(
                        f"  MISSING MIRROR UPDATE: {changed_rel} was changed but "
                        f"root/{root_counterpart_str} was NOT updated in this session "
                        f"(mirror={mirror_size:,}B  root={root_size:,}B)."
                    )
        else:
            # Changed file lives at root — check its Murphy System/ mirror.
            mirror_counterpart_str = f"{_MIRROR_DIR_NAME}/{changed_rel}"
            mirror_file = mirror_root / changed_path
            if not (mirror_file.exists() and mirror_file.is_file()):
                continue
            if mirror_counterpart_str in changed_set:
                continue
            # Root was changed but mirror was not — verify content actually differs.
            root_bytes = _read_bytes(repo_root / changed_path)
            mirror_bytes = _read_bytes(mirror_file)
            if root_bytes != mirror_bytes:
                missing_mirrors.append((changed_rel, mirror_counterpart_str))
                if verbose:
                    root_size = (repo_root / changed_path).stat().st_size
                    mirror_size = mirror_file.stat().st_size
                    print(
                        f"  MISSING MIRROR UPDATE: {changed_rel} was changed but "
                        f"{mirror_counterpart_str} was NOT updated in this session "
                        f"(root={root_size:,}B  mirror={mirror_size:,}B)."
                    )

    if verbose:
        if missing_mirrors:
            print(
                f"\nSESSION DRIFT: {len(missing_mirrors)} changed file(s) have "
                "out-of-sync mirrors.\n"
                "Canonical direction: Murphy System/ → root"
            )
        else:
            print(
                "OK: All changed files have consistent mirrors "
                "(or no paired mirror exists)."
            )

    return missing_mirrors


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Enforce byte-identical parity between root and Murphy System/ mirrors."
        )
    )
    parser.add_argument(
        "--changed-only",
        action="store_true",
        help=(
            "Session-scoped mode: only check files changed in the current "
            "PR/push (uses git diff --name-only <base>...HEAD). "
            "Exits non-zero if any changed file's mirror was not also updated."
        ),
    )
    args = parser.parse_args()

    if args.changed_only:
        missing = check_session_drift(verbose=True)
        return 1 if missing else 0
    else:
        drifted = check_drift(verbose=True)
        return 1 if drifted else 0


if __name__ == "__main__":
    sys.exit(main())
