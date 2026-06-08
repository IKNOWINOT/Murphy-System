#!/usr/bin/env python3
"""
auto_doc_generator.py — verifier for PCR-014 (auto-documentation).

Walks src/ (or a configured root), extracts for each Python module:
  - Purpose: module docstring
  - Public API: top-level classes + functions with docstrings + signatures
  - Recent changes: last N git commits touching the file (subject + date)
  - Dependencies: import lines
  - Last regenerated: ISO timestamp

Writes one file per module to docs/auto/<module_path>.md.
Also writes docs/auto/INDEX.md with a one-line summary per module.

Usage:
    auto_doc_generator.py                 # generate, default settings
    auto_doc_generator.py --root src      # specify source root
    auto_doc_generator.py --out docs/auto # output dir
    auto_doc_generator.py --check         # verifier: count must match
                                          # module count; timestamps < 24h
    auto_doc_generator.py --no-git        # skip git history (faster)

Verifier (the shape of complete for PCR-014):
    auto_doc_generator.py --check

Performance: ~1750 modules in ~10s with batched git lookup (vs. ~175s
with per-file git calls).
"""
from __future__ import annotations
import argparse
import ast
import os
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

DEFAULT_ROOT = "src"
DEFAULT_OUT = "docs/auto"
EXCLUDE_DIRS = {"__pycache__", "_archive", ".git", "venv", ".venv", "node_modules"}
RECENT_COMMITS_N = 5
GIT_LOOKBACK_COMMITS = 500  # how many recent commits to scan for per-file history


def find_modules(root: Path) -> list[Path]:
    out = []
    for path in root.rglob("*.py"):
        if any(part in EXCLUDE_DIRS for part in path.parts):
            continue
        if path.name == "__init__.py" and path.stat().st_size < 20:
            continue
        out.append(path)
    return sorted(out)


def parse_module(path: Path) -> dict:
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"docstring": "", "imports": [], "classes": [], "functions": []}

    try:
        tree = ast.parse(src, filename=str(path))
    except SyntaxError as e:
        return {
            "docstring": f"(parse error: {e})",
            "imports": [],
            "classes": [],
            "functions": [],
        }

    doc = ast.get_docstring(tree) or ""
    imports, classes, functions = [], [], []

    for node in tree.body:
        if isinstance(node, ast.Import):
            for a in node.names:
                imports.append(f"import {a.name}" + (f" as {a.asname}" if a.asname else ""))
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            names = ", ".join(
                a.name + (f" as {a.asname}" if a.asname else "") for a in node.names
            )
            imports.append(f"from {mod} import {names}")
        elif isinstance(node, ast.ClassDef):
            classes.append({
                "name": node.name,
                "docstring": (ast.get_docstring(node) or "").strip(),
                "methods": [
                    m.name for m in node.body
                    if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and not m.name.startswith("_")
                ][:10],
            })
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("_"):
                continue
            args = [a.arg for a in node.args.args]
            sig = f"{node.name}({', '.join(args)})"
            functions.append({
                "name": node.name,
                "signature": sig,
                "docstring": (ast.get_docstring(node) or "").strip(),
            })

    return {
        "docstring": doc.strip(),
        "imports": imports,
        "classes": classes,
        "functions": functions,
    }


def batch_git_history(repo_root: Path, lookback: int = GIT_LOOKBACK_COMMITS) -> dict[str, list[str]]:
    """ONE git log call. Returns {file_relative_path: [commit_lines...]}.

    Massively faster than calling git per file. Uses --name-only to map
    commits → files in a single stream.
    """
    out: dict[str, list[str]] = defaultdict(list)
    try:
        result = subprocess.run(
            ["git", "log", f"-n{lookback}", "--name-only",
             "--format=__COMMIT__%h %ad %s", "--date=short"],
            cwd=str(repo_root),
            capture_output=True, text=True, timeout=30, check=False,
        )
        if result.returncode != 0:
            return {}
    except Exception:
        return {}

    current_commit_line = None
    for line in result.stdout.split("\n"):
        if line.startswith("__COMMIT__"):
            current_commit_line = line[len("__COMMIT__"):].strip()
        elif line.strip() and current_commit_line:
            # Each non-empty non-commit line is a file path touched by this commit
            path = line.strip()
            if len(out[path]) < RECENT_COMMITS_N:
                out[path].append(current_commit_line)
    return out


def first_line(text: str, fallback: str = "(no description)") -> str:
    if not text:
        return fallback
    for line in text.split("\n"):
        line = line.strip()
        if line:
            return (line[:140] + "…") if len(line) > 140 else line
    return fallback


def render_module_doc(mod_path: Path, repo_root: Path, info: dict,
                      commits: list[str]) -> str:
    rel = mod_path.relative_to(repo_root)
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out = [f"# `{rel}` — auto-generated", ""]
    out.append(f"> _Last regenerated: {ts}_")
    out.append("")

    if info["docstring"]:
        out.append("## Purpose")
        out.append("")
        out.append(info["docstring"])
        out.append("")

    if info["classes"]:
        out.append("## Classes")
        out.append("")
        for c in info["classes"]:
            out.append(f"### `{c['name']}`")
            if c["docstring"]:
                out.append("")
                out.append(c["docstring"])
            if c["methods"]:
                out.append("")
                out.append(f"Methods: " + ", ".join(f"`{m}`" for m in c["methods"]))
            out.append("")

    if info["functions"]:
        out.append("## Functions")
        out.append("")
        for f in info["functions"]:
            out.append(f"### `{f['signature']}`")
            if f["docstring"]:
                out.append("")
                out.append(f["docstring"])
            out.append("")

    if info["imports"]:
        out.append("## Dependencies")
        out.append("")
        out.append("```python")
        for imp in info["imports"][:20]:
            out.append(imp)
        if len(info["imports"]) > 20:
            out.append(f"# ... +{len(info['imports']) - 20} more")
        out.append("```")
        out.append("")

    if commits:
        out.append(f"## Recent changes (last {len(commits)})")
        out.append("")
        for c in commits:
            out.append(f"- `{c}`")
        out.append("")

    return "\n".join(out) + "\n"


def render_index(modules: list[tuple[Path, dict]], repo_root: Path) -> str:
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out = [
        "# Auto-Documentation Index",
        "",
        f"> _Last regenerated: {ts}_",
        f"> _Modules indexed: {len(modules)}_",
        "",
        "| Module | Purpose |",
        "|---|---|",
    ]
    for path, info in modules:
        rel = path.relative_to(repo_root)
        summary = first_line(info["docstring"], "(no module docstring)")
        summary = summary.replace("|", "\\|")
        link = str(rel).replace(os.sep, "/") + ".md"
        out.append(f"| [`{rel}`]({link}) | {summary} |")
    return "\n".join(out) + "\n"


def generate(root: Path, out_dir: Path, repo_root: Path,
             use_git: bool = True) -> int:
    modules = find_modules(root)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ONE git call instead of N
    git_history = batch_git_history(repo_root) if use_git else {}

    rendered = []
    for path in modules:
        info = parse_module(path)
        rel_str = str(path.relative_to(repo_root))
        commits = git_history.get(rel_str, [])
        doc = render_module_doc(path, repo_root, info, commits)
        rel = path.relative_to(repo_root)
        target = out_dir / (str(rel) + ".md")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(doc, encoding="utf-8")
        rendered.append((path, info))

    index = render_index(rendered, repo_root)
    (out_dir / "INDEX.md").write_text(index, encoding="utf-8")
    return len(rendered)


def check(out_dir: Path, root: Path) -> int:
    modules = find_modules(root)
    expected = len(modules)
    if not out_dir.exists():
        print(f"  ✗ FAIL: out dir {out_dir} does not exist")
        return 2

    generated = list(out_dir.rglob("*.py.md"))
    actual = len(generated)
    if actual < expected:
        print(f"  ✗ FAIL: have {actual} auto-docs, expected {expected} modules")
        return 2
    print(f"  ✓ doc count: {actual}/{expected}")

    index = out_dir / "INDEX.md"
    if not index.exists():
        print("  ✗ FAIL: INDEX.md missing")
        return 2

    text = index.read_text()
    import re
    m = re.search(r"_Last regenerated:\s*([0-9T:+\-]+)_", text)
    if not m:
        print("  ✗ FAIL: INDEX.md has no timestamp")
        return 2
    try:
        ts = datetime.fromisoformat(m.group(1))
    except ValueError as e:
        print(f"  ✗ FAIL: INDEX.md timestamp parse error: {e}")
        return 2

    age = datetime.now(timezone.utc) - ts
    if age > timedelta(hours=24):
        print(f"  ✗ FAIL: INDEX.md is {age} old (limit 24h)")
        return 2
    print(f"  ✓ INDEX.md timestamp fresh ({age} old)")
    print("  ✓ PASS: PCR-014 verifier")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=DEFAULT_ROOT, help="source root (default: src)")
    ap.add_argument("--out", default=DEFAULT_OUT, help="output dir (default: docs/auto)")
    ap.add_argument("--repo-root", default=".", help="repo root for relative paths")
    ap.add_argument("--check", action="store_true", help="verifier mode")
    ap.add_argument("--no-git", action="store_true", help="skip git history")
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    root = (repo_root / args.root).resolve()
    out_dir = (repo_root / args.out).resolve()

    if not root.exists():
        print(f"ERROR: source root {root} does not exist", file=sys.stderr)
        return 3

    if args.check:
        return check(out_dir, root)

    n = generate(root, out_dir, repo_root, use_git=not args.no_git)
    print(f"  ✓ generated {n} auto-doc files in {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
