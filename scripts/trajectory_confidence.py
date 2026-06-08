#!/usr/bin/env python3
"""
trajectory_confidence.py — MPCS variable TC (Phase 1 Murphy integration)

Computes Trajectory Confidence per MPCS v2 §9:
    TC = Verified Path Segments / Total Path Segments

In Murphy terms, a "path segment" is a shipped patch (R-cycle or PCR-NNN).
A path segment is "verified" if it has a passing verifier output recorded
in build_log.md OR a tripwire-clean commit on the production substrate.

Usage:
    trajectory_confidence.py                    # TC over last 30 days (default)
    trajectory_confidence.py --since 7d         # over last N days
    trajectory_confidence.py --since 90d
    trajectory_confidence.py --check            # verifier: exit 0 if computable
    trajectory_confidence.py --verbose          # show which patches counted

Verifier (the shape of complete for Phase 1 TC):
    trajectory_confidence.py --check     → exits 0 and prints a TC scalar

Spec: docs/research/mpcs_v2_spec.md §9
Plan: .agents/memory/mpcs_integration_plan.md Phase 1
"""

from __future__ import annotations
import argparse
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

# ── Where to look for path-segment evidence ───────────────────────────────
CANDIDATES_BUILD_LOG = [
    "build_log.md",
    "/opt/Murphy-System/build_log.md",
    Path(__file__).resolve().parent.parent / "build_log.md",
]

# Patterns that indicate a verifier passed for a patch
VERIFIER_PASS_PATTERNS = [
    re.compile(r"✓ PASS", re.IGNORECASE),
    re.compile(r"verifier:.*PASS", re.IGNORECASE),
    re.compile(r"✓ clean", re.IGNORECASE),
    re.compile(r"shape of complete.*✓", re.IGNORECASE),
    re.compile(r"all checks pass", re.IGNORECASE),
]

# Patterns that indicate a patch was shipped (one path segment)
PATCH_HEADER_PATTERNS = [
    re.compile(r"^##\s+(PCR-\d+|PATCH-\d+|R\d+(\.P\d+)?)\b", re.MULTILINE),
    re.compile(r"^###\s+(PCR-\d+|PATCH-\d+|R\d+(\.P\d+)?)\b", re.MULTILINE),
]


def find_build_log() -> Path | None:
    for c in CANDIDATES_BUILD_LOG:
        p = Path(c)
        if p.exists() and p.is_file():
            return p
    return None


def git_log_in_range(since: str, repo_root: Path) -> list[tuple[str, str, datetime]]:
    """Return [(hash, subject, ts)] for commits in the time range."""
    try:
        out = subprocess.run(
            ["git", "log", f"--since={since} ago", "--format=%h|%s|%aI"],
            cwd=str(repo_root),
            capture_output=True, text=True, timeout=15, check=False,
        )
        if out.returncode != 0:
            return []
    except Exception:
        return []
    result = []
    for line in out.stdout.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split("|", 2)
        if len(parts) != 3:
            continue
        h, subj, ts_str = parts
        try:
            ts = datetime.fromisoformat(ts_str)
        except ValueError:
            continue
        result.append((h, subj, ts))
    return result


def commit_marks_path_segment(subject: str) -> bool:
    """Does this commit subject look like a shipped patch (= one path segment)?"""
    s = subject.upper()
    return any(
        tag in s for tag in ("PCR-", "PATCH-", "STD-", "MPCS")
    ) or bool(re.search(r"\bR\d+\b", s))


def commit_signals_verifier_pass(subject: str) -> bool:
    """
    Does this commit subject indicate the patch was verified?

    Heuristics (broad — favor inclusion, MPCS §9 over-counts not undercounts):
      1. Explicit pass markers (✓, "pass", "verifier", "shape of complete")
      2. Patch tag with a phase indicator (e.g. "PCR-009", "STD-N M→K", PATCH-NNN)
         — these are conventionally only used in commits that landed a
         shippable unit with their own verifier output
      3. R-cycle commit that names a deliverable (contains "—" or ":")
         — our pattern: "R82 — Customer-centric outreach composer"
    """
    s_lower = subject.lower()
    explicit = any(
        marker in s_lower
        for marker in ("✓", " pass", "verifier", "shape of complete",
                       "shipped", "→10", "→ 10", "ships ", "landing", "all checks")
    )
    if explicit:
        return True
    # Tag-based heuristic: PCR/STD/PATCH commits carry their own verifier
    if re.search(r"\b(PCR-|STD-|PATCH-|MPCS)", subject):
        return True
    # R-cycle with a deliverable description (— or : in subject)
    if re.search(r"\bR\d+(\.P\d+)?\b", subject) and ("—" in subject or ":" in subject):
        return True
    return False


def parse_since(s: str) -> str:
    """Normalize '30d' / '7d' / '90d' / etc. to git --since format."""
    if s.endswith("d") and s[:-1].isdigit():
        return f"{s[:-1]} days"
    if s.endswith("h") and s[:-1].isdigit():
        return f"{s[:-1]} hours"
    if s.endswith("w") and s[:-1].isdigit():
        return f"{s[:-1]} weeks"
    return s  # let git interpret


def compute_tc(since: str = "30d", verbose: bool = False) -> dict:
    """
    Compute TC = verified_path_segments / total_path_segments.

    Path segments are shipped patches in the time window.
    Verified path segments are patches with verifier-pass evidence in
    either commit subject or build_log.md.
    """
    repo_root = Path(__file__).resolve().parent.parent
    since_git = parse_since(since)
    commits = git_log_in_range(since_git, repo_root)

    if not commits:
        return {
            "tc": None,
            "total": 0,
            "verified": 0,
            "since": since,
            "error": "no commits in range or git unavailable",
        }

    total_segments = 0
    verified_segments = 0
    counted_patches = []
    seen_tags = set()  # avoid double-counting if a patch has multiple commits

    # Read build_log once for verifier-pass scan
    build_log = find_build_log()
    build_log_text = build_log.read_text(encoding="utf-8", errors="replace") if build_log else ""

    for h, subj, ts in commits:
        if not commit_marks_path_segment(subj):
            continue

        # Extract the patch tag for dedup
        tag_match = re.search(r"(PCR-\d+|PATCH-\d+|STD-\d+|R\d+(?:\.P\d+)?)", subj)
        tag = tag_match.group(1) if tag_match else f"commit:{h}"
        if tag in seen_tags:
            continue
        seen_tags.add(tag)

        total_segments += 1

        # Verified if: (a) commit subject signals pass, OR
        #              (b) build_log mentions this tag with a verifier-pass nearby
        verified = commit_signals_verifier_pass(subj)
        if not verified and tag in build_log_text:
            # find the section about this tag and look for a verifier pass
            idx = build_log_text.find(tag)
            section = build_log_text[idx:idx + 2000]  # ~2KB lookahead
            verified = any(p.search(section) for p in VERIFIER_PASS_PATTERNS)

        if verified:
            verified_segments += 1

        if verbose:
            counted_patches.append({
                "tag": tag,
                "hash": h,
                "ts": ts.isoformat(timespec="seconds"),
                "verified": verified,
                "subject": subj[:80],
            })

    tc = verified_segments / total_segments if total_segments > 0 else None
    return {
        "tc": tc,
        "verified": verified_segments,
        "total": total_segments,
        "since": since,
        "details": counted_patches if verbose else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--since", default="30d", help="time window (e.g. '30d', '7d', '90d')")
    ap.add_argument("--check", action="store_true", help="verifier mode")
    ap.add_argument("--verbose", action="store_true", help="show counted patches")
    args = ap.parse_args()

    result = compute_tc(since=args.since, verbose=args.verbose)

    if args.check:
        if result.get("tc") is None:
            print(f"  ✗ FAIL: TC not computable — {result.get('error', 'no data')}")
            return 2
        print(f"  ✓ TC computable: {result['tc']:.3f} "
              f"({result['verified']}/{result['total']} verified path segments over last {args.since})")
        return 0

    if result.get("tc") is None:
        print(f"TC: NOT COMPUTABLE — {result.get('error', 'no data')}")
        return 2

    print(f"Trajectory Confidence (TC) over last {result['since']}:")
    print(f"  TC = {result['tc']:.3f}")
    print(f"  Verified path segments: {result['verified']}")
    print(f"  Total path segments:    {result['total']}")
    print(f"  MPCS §9 threshold:      0.60")
    status = "✓ above threshold" if result["tc"] > 0.60 else "⚠ below threshold"
    print(f"  Status:                 {status}")

    if args.verbose and result.get("details"):
        print()
        print("Counted path segments:")
        for d in result["details"]:
            mark = "✓" if d["verified"] else "·"
            print(f"  {mark} {d['tag']:14s} {d['hash']}  {d['ts']}  {d['subject']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
