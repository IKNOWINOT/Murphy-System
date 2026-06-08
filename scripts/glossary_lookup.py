#!/usr/bin/env python3
"""
glossary_lookup.py — verifier for PCR-009 (business glossary).

Usage:
    glossary_lookup.py TERM           # look up a single term
    glossary_lookup.py --list         # list all terms
    glossary_lookup.py --count        # print count + assertion check
    glossary_lookup.py --check TERM   # exit 0 if defined, 2 if not

The glossary lives at:
  - docs/architecture/glossary.md          (canonical, in repo)
  - .agents/rules/glossary.md              (sandbox copy)

This script reads whichever path exists, in that order.
"""

from __future__ import annotations
import os, re, sys

CANDIDATES = [
    "docs/architecture/glossary.md",
    ".agents/rules/glossary.md",
    "/opt/Murphy-System/docs/architecture/glossary.md",
    os.path.expanduser("~/.agents/rules/glossary.md"),
]

# Match  "- **TERM** (...)\n  body until next bullet or section"
ENTRY_RE = re.compile(
    r'^- \*\*(?P<term>[^*]+?)\*\*\s*\((?P<meta>[^)]*)\)\s*\n(?P<body>(?:(?!^- \*\*|^## ).+\n?)+)',
    re.MULTILINE
)


def find_glossary() -> str:
    for p in CANDIDATES:
        if os.path.isfile(p):
            return p
    raise FileNotFoundError(
        f"glossary not found in any of: {CANDIDATES}"
    )


def load_entries(path: str) -> dict[str, dict]:
    text = open(path).read()
    out = {}
    for m in ENTRY_RE.finditer(text):
        term = m.group("term").strip()
        # Normalize: strip wrapping spaces, split slash-separated aliases
        keys = [k.strip() for k in re.split(r"\s*/\s*", term) if k.strip()]
        entry = {
            "term": term,
            "meta": m.group("meta").strip(),
            "body": m.group("body").strip(),
        }
        for k in keys:
            out[k.lower()] = entry
    return out


def fuzzy_lookup(entries: dict, query: str) -> dict | None:
    q = query.strip().lower()
    if q in entries:
        return entries[q]
    # Strip trailing punctuation
    q2 = re.sub(r"[^a-z0-9_\-]+$", "", q)
    if q2 in entries:
        return entries[q2]
    # Partial match
    for k, v in entries.items():
        if q in k or k.startswith(q):
            return v
    return None


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1

    try:
        path = find_glossary()
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 3

    entries = load_entries(path)

    cmd = argv[1]
    if cmd == "--list":
        for k in sorted(entries.keys()):
            print(f"  {entries[k]['term']}  ({entries[k]['meta']})")
        return 0

    if cmd == "--count":
        # De-duplicate by entry identity
        unique = {id(v): v for v in entries.values()}
        n = len(unique)
        print(f"  glossary entries: {n}")
        print(f"  source: {path}")
        if n < 40:
            print(f"  ✗ FAIL: PCR-009 requires ≥ 40 entries (have {n})")
            return 2
        print(f"  ✓ PASS: PCR-009 verifier (≥ 40 entries)")
        return 0

    if cmd == "--check":
        if len(argv) < 3:
            print("usage: glossary_lookup.py --check TERM", file=sys.stderr)
            return 1
        e = fuzzy_lookup(entries, argv[2])
        return 0 if e else 2

    # Default: look up the term
    e = fuzzy_lookup(entries, cmd)
    if not e:
        print(f"  ✗ term not found: {cmd!r}", file=sys.stderr)
        return 2
    print(f"  {e['term']}  ({e['meta']})")
    print()
    for line in e["body"].splitlines():
        print(f"    {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
