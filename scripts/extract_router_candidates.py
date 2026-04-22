#!/usr/bin/env python3
"""
extract_router_candidates.py — Item 1 enabler.

Reads the two FastAPI entrypoints (`src/runtime/app.py` and
`murphy_production_server.py`) and produces a deterministic, safety-ranked
queue of route handlers ready for extraction into `src/routers/<domain>.py`.

This script does not modify code. It exists because Item 1 of the Class S
Roadmap ("Decompose `murphy_production_server.py` into routers") is a
~184-PR sequence and the only thing that turns "184 PRs" into a tractable
backlog is a deterministic order to do them in.

Ranking heuristic (safer = lower score, do these first):

    score = (
        2 * (uses module-level mutable globals)
      + 2 * (touches FastAPI app.state)
      + 1 * (calls async background scheduler / asyncio.create_task)
      + 1 * (registers a startup/shutdown hook nearby)
      + 1 * (declares >5 parameters — likely complex)
      + 0 if path starts with /api/ else 1   # marketing/HTML routes pull templates
    )

The lowest-scoring routes are pure-handler extractions: copy the function
into `src/routers/<domain>.py`, wrap it with `APIRouter().<verb>(path)`,
register the router in `app.py`, delete the inline handler. No state
threading, no startup ordering, no template plumbing.

Usage:
    python scripts/extract_router_candidates.py
    python scripts/extract_router_candidates.py --json > queue.json
    python scripts/extract_router_candidates.py --top 20

Domain grouping is suggested by the path prefix (`/api/hitl/*` → `hitl`,
`/api/billing/*` → `billing`, etc.) so that one PR == one domain router,
which matches the strategy documented in `src/routers/__init__.py`.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
ENTRYPOINTS: tuple[Path, ...] = (
    REPO_ROOT / "src" / "runtime" / "app.py",
    REPO_ROOT / "murphy_production_server.py",
)

_ROUTE_DECORATORS: frozenset[str] = frozenset(
    {"get", "post", "put", "delete", "patch", "options", "head", "websocket"}
)

# Patterns that, when present in the function body, indicate the handler
# is NOT a clean extraction target (it threads state through globals or
# requires startup-order handling).
_HAZARD_PATTERNS: dict[str, re.Pattern[str]] = {
    "app_state": re.compile(r"\bapp\.state\b|\brequest\.app\.state\b"),
    "create_task": re.compile(r"\basyncio\.create_task\b"),
    "module_global_assign": re.compile(r"^\s*global\s+\w+", re.MULTILINE),
    "startup_hook_nearby": re.compile(r"@app\.on_event\(['\"](startup|shutdown)"),
}


@dataclass
class RouteCandidate:
    """One route handler's extraction profile."""

    file: str
    line: int
    verb: str
    path: str
    function: str
    domain: str
    param_count: int
    hazards: list[str] = field(default_factory=list)
    score: int = 0

    def compute_score(self) -> None:
        s = 0
        if "app_state" in self.hazards:
            s += 2
        if "module_global_assign" in self.hazards:
            s += 2
        if "create_task" in self.hazards:
            s += 1
        if "startup_hook_nearby" in self.hazards:
            s += 1
        if self.param_count > 5:
            s += 1
        if not self.path.startswith("/api/"):
            s += 1
        self.score = s


def _domain_from_path(path: str) -> str:
    """Pick a router-module name from the URL path.

    /api/hitl/queue       → hitl
    /api/v1/billing/...   → billing
    /admin/panel          → admin
    /                     → root
    """
    parts = [p for p in path.split("/") if p]
    if not parts:
        return "root"
    # Strip the leading 'api' and any version segment.
    if parts[0] == "api":
        parts = parts[1:]
    if parts and re.fullmatch(r"v\d+", parts[0]):
        parts = parts[1:]
    if not parts:
        return "root"
    # Convert hyphenated paths to underscores so the file name is importable.
    return parts[0].replace("-", "_")


def _scan_file(path: Path) -> list[RouteCandidate]:
    """Return route handlers declared in *path*.

    Uses AST for the decorator/function shape and string scanning of the
    function body for the hazard patterns. AST is correct on the structural
    bits; regex is fine on the body because the hazards are syntactic
    fingerprints, not semantic claims.
    """
    if not path.exists():
        return []
    src = path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(src, filename=str(path))
    lines = src.splitlines()
    candidates: list[RouteCandidate] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for deco in node.decorator_list:
            verb_path = _decorator_verb_and_path(deco)
            if verb_path is None:
                continue
            verb, route_path = verb_path

            # Window the function body (plus a few lines above) for hazard scan.
            start = max(node.lineno - 5, 0)
            end = min(getattr(node, "end_lineno", node.lineno) or node.lineno, len(lines))
            window = "\n".join(lines[start:end])
            hazards = [name for name, pat in _HAZARD_PATTERNS.items() if pat.search(window)]

            cand = RouteCandidate(
                file=str(path.relative_to(REPO_ROOT)),
                line=node.lineno,
                verb=verb,
                path=route_path,
                function=node.name,
                domain=_domain_from_path(route_path),
                param_count=len(node.args.args),
                hazards=hazards,
            )
            cand.compute_score()
            candidates.append(cand)

    return candidates


def _decorator_verb_and_path(deco: ast.expr) -> tuple[str, str] | None:
    """Return (verb, path) if *deco* is `@<obj>.<verb>("path", ...)`, else None."""
    if not isinstance(deco, ast.Call):
        return None
    func = deco.func
    if not isinstance(func, ast.Attribute):
        return None
    verb = func.attr
    if verb not in _ROUTE_DECORATORS:
        return None
    if not deco.args:
        return None
    first = deco.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return verb, first.value
    return None


def _rank(candidates: Iterable[RouteCandidate]) -> list[RouteCandidate]:
    """Stable sort: lowest-risk first; ties broken by domain then path."""
    return sorted(candidates, key=lambda c: (c.score, c.domain, c.path, c.verb))


def _summarise_by_domain(candidates: list[RouteCandidate]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for c in candidates:
        bucket = out.setdefault(c.domain, {"count": 0, "max_score": 0})
        bucket["count"] += 1
        if c.score > bucket["max_score"]:
            bucket["max_score"] = c.score
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true",
                        help="emit JSON instead of the human-readable table")
    parser.add_argument("--top", type=int, default=0,
                        help="show only the N safest extraction candidates")
    args = parser.parse_args(argv)

    all_candidates: list[RouteCandidate] = []
    for entry in ENTRYPOINTS:
        all_candidates.extend(_scan_file(entry))

    ranked = _rank(all_candidates)
    if args.top > 0:
        ranked = ranked[: args.top]

    if args.json:
        print(json.dumps(
            {
                "candidates": [asdict(c) for c in ranked],
                "by_domain": _summarise_by_domain(all_candidates),
                "total": len(all_candidates),
            },
            indent=2,
            sort_keys=True,
        ))
        return 0

    print(f"Total handlers discovered: {len(all_candidates)}")
    print(f"Showing: {len(ranked)}")
    print()
    print(f"{'score':>5}  {'verb':<9} {'path':<55} {'domain':<14} hazards")
    print("-" * 110)
    for c in ranked:
        haz = ",".join(c.hazards) if c.hazards else "-"
        print(f"{c.score:>5}  {c.verb:<9} {c.path[:55]:<55} {c.domain:<14} {haz}")
    print()
    print("Suggested PR cadence: extract one full domain (all routes sharing the")
    print("same `domain` column) per PR, starting with the lowest-score domain.")
    print()
    print("By domain:")
    for dom, stats in sorted(
        _summarise_by_domain(all_candidates).items(),
        key=lambda kv: (kv[1]["max_score"], kv[0]),
    ):
        print(f"  {dom:<20} {stats['count']:>4} routes   max_score={stats['max_score']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
