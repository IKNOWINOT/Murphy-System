#!/usr/bin/env python3
"""
gap_detector.py — Murphy System Gap Detector

Runs a suite of automated checks against the Murphy System codebase and emits
GitHub Actions annotations (::warning / ::error) for every finding.

Checks performed:
  1. Storyline conformance  — run pytest -m storyline, report per chapter
  2. Capability baseline drift — compare src/ modules to docs/capability_baseline.json
  3. TODO/FIXME/HACK/STUB debt — count markers, fail if above threshold
  4. API endpoint validation — ensure documented endpoints appear in source
  5. Environment variable audit — ensure os.getenv/os.environ vars are in .env.example
  6. Documentation file reference check — every file path in *.md must exist

Usage (local):
    cd "Murphy System"
    python scripts/gap_detector.py

    # Regenerate the capability baseline after intentional changes:
    python scripts/gap_detector.py --generate-baseline

    # Override the TODO threshold (default 500):
    TODO_THRESHOLD=200 python scripts/gap_detector.py

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent          # Murphy System/scripts/
ROOT = HERE.parent                               # Murphy System/
SRC_DIR = ROOT / "src"
DOCS_DIR = ROOT / "docs"
TESTS_DIR = ROOT / "tests"
BASELINE_FILE = DOCS_DIR / "capability_baseline.json"
ENV_EXAMPLE = ROOT / ".env.example"
GETTING_STARTED = ROOT / "GETTING_STARTED.md"
REPO_ROOT = ROOT.parent                          # repository root

# ---------------------------------------------------------------------------
# Configurable thresholds (can be overridden via environment variables)
# ---------------------------------------------------------------------------
TODO_THRESHOLD = int(os.environ.get("TODO_THRESHOLD", "500"))

# ---------------------------------------------------------------------------
# Annotation helpers
# ---------------------------------------------------------------------------

def _gha(level: str, title: str, message: str) -> None:
    """Emit a GitHub Actions annotation, falling back to plain text."""
    # Escape newlines so the annotation renders properly
    safe = message.replace("\n", "%0A").replace("\r", "%0D")
    print(f"::{level} title={title}::{safe}", flush=True)


def warn(title: str, message: str) -> None:
    _gha("warning", title, message)


def error(title: str, message: str) -> None:
    _gha("error", title, message)


def notice(title: str, message: str) -> None:
    _gha("notice", title, message)


# ---------------------------------------------------------------------------
# Check 1: Storyline conformance tests
# ---------------------------------------------------------------------------

def check_storyline_conformance() -> bool:
    """Run pytest -m storyline and report pass/fail per chapter."""
    print("\n" + "=" * 60)
    print("CHECK 1: Storyline Conformance Tests")
    print("=" * 60)

    try:
        result = subprocess.run(
            [
                sys.executable, "-m", "pytest",
                "-m", "storyline",
                "-v",
                "--tb=short",
                "--timeout=120",
                "--override-ini=addopts=",  # strip coverage flags from pyproject.toml
                "--no-header",
            ],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        output = result.stdout + result.stderr
        print(output)

        # Parse per-chapter results from pytest -v output.
        # pytest -v format: "tests/file.py::Class::method PASSED [  3%]"
        passed: list[str] = re.findall(r"(tests/\S+)\s+PASSED", output)
        failed: list[str] = re.findall(r"(tests/\S+)\s+FAILED", output)
        errors_found: list[str] = re.findall(r"ERROR\s+(.*)", output)

        if passed:
            notice(
                "Storyline Conformance",
                f"{len(passed)} test(s) PASSED: " + ", ".join(passed[:10])
                + ("..." if len(passed) > 10 else ""),
            )

        if not passed and not failed and not errors_found:
            warn(
                "Storyline Conformance",
                "No tests matched pytest -m storyline. "
                "Add @pytest.mark.storyline to conformance tests in tests/.",
            )
            return True  # Not a hard failure — tests may not be marked yet

        if failed or errors_found:
            failing = failed + errors_found
            error(
                "Storyline Conformance",
                f"{len(failing)} test(s) FAILED:\n" + "\n".join(failing[:20]),
            )
            return False

        print(f"  ✅ Storyline conformance: {len(passed)} tests passed.")
        return True

    except FileNotFoundError:
        warn("Storyline Conformance", "pytest not found — skipping storyline conformance check.")
        return True


# ---------------------------------------------------------------------------
# Check 2: Capability baseline drift
# ---------------------------------------------------------------------------

def _scan_src_modules() -> set[str]:
    """Return the set of top-level module names in src/ (excluding __init__)."""
    modules: set[str] = set()
    if not SRC_DIR.exists():
        return modules
    for p in SRC_DIR.rglob("*.py"):
        # Only top-level files and immediate package __init__ files
        rel = p.relative_to(SRC_DIR)
        parts = rel.parts
        if len(parts) == 1:
            name = p.stem
            if name != "__init__":
                modules.add(name)
        elif len(parts) == 2 and parts[1] == "__init__.py":
            modules.add(parts[0])
    return modules


def check_capability_drift() -> bool:
    """Compare current src/ modules against docs/capability_baseline.json."""
    print("\n" + "=" * 60)
    print("CHECK 2: Capability Baseline Drift Detection")
    print("=" * 60)

    if not BASELINE_FILE.exists():
        warn(
            "Capability Drift",
            f"{BASELINE_FILE.relative_to(ROOT)} not found. "
            "Run: python scripts/gap_detector.py --generate-baseline",
        )
        return True  # Can't compare without baseline

    with open(BASELINE_FILE) as f:
        baseline_data = json.load(f)

    baseline: set[str] = set(baseline_data.get("modules", []))
    current: set[str] = _scan_src_modules()

    added = current - baseline
    removed = baseline - current

    passed = True

    if added:
        warn(
            "Capability Drift — New Modules",
            f"{len(added)} module(s) added since baseline:\n"
            + "\n".join(sorted(added))
            + "\n\nIf intentional, update docs/capability_baseline.json by running:\n"
            "  python scripts/gap_detector.py --generate-baseline",
        )
        passed = False

    if removed:
        error(
            "Capability Drift — Missing Modules",
            f"{len(removed)} module(s) removed since baseline:\n"
            + "\n".join(sorted(removed))
            + "\n\nIf intentional, update docs/capability_baseline.json by running:\n"
            "  python scripts/gap_detector.py --generate-baseline",
        )
        passed = False

    if not added and not removed:
        print(f"  ✅ Capability baseline matches ({len(current)} modules). No drift detected.")

    return passed


def generate_baseline() -> None:
    """Regenerate docs/capability_baseline.json from the current src/."""
    modules = sorted(_scan_src_modules())
    data: dict[str, Any] = {
        "_meta": {
            "description": (
                "Capability baseline for drift detection. Generated from the current "
                "scan of Murphy System src/. Update intentionally when adding or removing "
                "modules; the gap-detector workflow flags unreviewed drift."
            ),
            "version": "1.0.0",
            "generated_by": "scripts/gap_detector.py --generate-baseline",
            "instructions": (
                "To regenerate: cd 'Murphy System' && python scripts/gap_detector.py --generate-baseline"
            ),
        },
        "modules": modules,
    }
    BASELINE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(BASELINE_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print(f"✅ Baseline written to {BASELINE_FILE} ({len(modules)} modules)")


# ---------------------------------------------------------------------------
# Check 3: TODO/FIXME/HACK/STUB debt
# ---------------------------------------------------------------------------

_DEBT_PATTERN = re.compile(r"\b(TODO|FIXME|HACK|STUB)\b", re.IGNORECASE)
_SKIP_DIRS = {".git", "__pycache__", ".mypy_cache", ".ruff_cache", "node_modules", ".venv", "venv"}


def _iter_source_files(root: Path):
    """Yield all .py files under root, skipping unwanted directories."""
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune skip dirs in-place
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fname in filenames:
            if fname.endswith(".py"):
                yield Path(dirpath) / fname


def check_debt_markers() -> bool:
    """Count TODO/FIXME/HACK/STUB markers; fail if above TODO_THRESHOLD."""
    print("\n" + "=" * 60)
    print("CHECK 3: TODO/FIXME/HACK/STUB Debt Scanning")
    print("=" * 60)

    counts: dict[str, int] = {"TODO": 0, "FIXME": 0, "HACK": 0, "STUB": 0}
    examples: dict[str, list[str]] = {"TODO": [], "FIXME": [], "HACK": [], "STUB": []}
    max_examples = 5

    for py_file in _iter_source_files(SRC_DIR):
        try:
            text = py_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for marker in counts:
                if re.search(rf"\b{marker}\b", line, re.IGNORECASE):
                    counts[marker] += 1
                    if len(examples[marker]) < max_examples:
                        rel = py_file.relative_to(ROOT)
                        examples[marker].append(f"  {rel}:{lineno}: {line.strip()[:100]}")

    total = sum(counts.values())

    summary_lines = ["Debt marker summary:"]
    for marker, count in counts.items():
        summary_lines.append(f"  {marker}: {count}")
        if examples[marker]:
            summary_lines.extend(examples[marker])
    summary_lines.append(f"\nTotal: {total}  (threshold: {TODO_THRESHOLD})")
    summary = "\n".join(summary_lines)

    print(summary)

    if total > TODO_THRESHOLD:
        error(
            "Debt Markers Exceed Threshold",
            f"Found {total} TODO/FIXME/HACK/STUB markers (threshold: {TODO_THRESHOLD}).\n"
            + summary,
        )
        return False

    if total > 0:
        warn(
            "Debt Markers Detected",
            f"Found {total} TODO/FIXME/HACK/STUB markers (below threshold {TODO_THRESHOLD}).\n"
            + summary,
        )
    else:
        print("  ✅ No debt markers found.")

    return True


# ---------------------------------------------------------------------------
# Check 4: API endpoint validation
# ---------------------------------------------------------------------------

_ROUTE_DECORATOR_RE = re.compile(
    r'@\w+\.(get|post|put|patch|delete|head|options)\s*\(\s*["\']([^"\']+)["\']',
    re.IGNORECASE,
)

_MD_ENDPOINT_RE = re.compile(r"`((?:/api/|/ui/)[^`\s]+)`")


def _collect_code_endpoints() -> set[str]:
    """Extract all route paths from FastAPI decorator calls in src/."""
    endpoints: set[str] = set()
    for py_file in _iter_source_files(SRC_DIR):
        try:
            text = py_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for _method, path in _ROUTE_DECORATOR_RE.findall(text):
            # Normalise path params: /api/foo/{bar_id} → /api/foo/{param}
            normalised = re.sub(r"\{[^}]+\}", "{param}", path)
            endpoints.add(normalised)
    return endpoints


def _collect_doc_endpoints() -> set[str]:
    """Extract all documented API paths from *.md files."""
    endpoints: set[str] = set()
    md_files = list(ROOT.rglob("*.md")) + list(REPO_ROOT.glob("*.md"))
    for md_file in md_files:
        try:
            text = md_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for path in _MD_ENDPOINT_RE.findall(text):
            # Only keep concrete paths (no wildcards in docs)
            if "*" not in path:
                normalised = re.sub(r"\{[^}]+\}", "{param}", path)
                endpoints.add(normalised)
    return endpoints


def _endpoint_prefix_match(doc_path: str, code_endpoints: set[str]) -> bool:
    """
    Return True if doc_path (or a prefix of it) is covered by code_endpoints.

    Docs often reference a wildcard prefix like /api/forms/* — we match if
    any code endpoint starts with the non-wildcard portion.
    """
    prefix = doc_path.rstrip("/*").rstrip("/")
    # Direct match
    if doc_path in code_endpoints or prefix in code_endpoints:
        return True
    # Prefix match (e.g. doc has /api/forms/*, code has /api/forms/plan-generation)
    for ep in code_endpoints:
        if ep.startswith(prefix + "/") or ep == prefix:
            return True
    return False


def check_api_endpoints() -> bool:
    """Verify documented API endpoints appear in source code."""
    print("\n" + "=" * 60)
    print("CHECK 4: API Endpoint Validation")
    print("=" * 60)

    code_endpoints = _collect_code_endpoints()
    doc_endpoints = _collect_doc_endpoints()

    if not doc_endpoints:
        warn("API Endpoint Validation", "No /api/ endpoints found in Markdown docs — skipping.")
        return True

    missing: list[str] = []
    for ep in sorted(doc_endpoints):
        if not _endpoint_prefix_match(ep, code_endpoints):
            missing.append(ep)

    print(f"  Documented endpoints: {len(doc_endpoints)}")
    print(f"  Code endpoints: {len(code_endpoints)}")
    print(f"  Missing from code: {len(missing)}")

    if missing:
        warn(
            "Undeclared API Endpoints",
            f"{len(missing)} documented endpoint(s) have no matching route decorator in src/:\n"
            + "\n".join(f"  {e}" for e in missing[:30])
            + ("\n  ... (truncated)" if len(missing) > 30 else ""),
        )
        # Warn only (not error) — docs may reference future or external endpoints
        return True

    print(f"  ✅ All {len(doc_endpoints)} documented endpoints are declared in source.")
    return True


# ---------------------------------------------------------------------------
# Check 5: Environment variable audit
# ---------------------------------------------------------------------------

_GETENV_RE = re.compile(
    r'os\.(?:getenv|environ\.get)\s*\(\s*["\']([A-Z][A-Z0-9_]+)["\']'
    r'|os\.environ\s*\[\s*["\']([A-Z][A-Z0-9_]+)["\']',
)

# Words that look like env var names but are not — add to this set as needed.
_ENV_VAR_FALSE_POSITIVES: frozenset[str] = frozenset({
    "TRUE", "FALSE", "HTTP", "HTTPS", "URL", "API",
})


def _collect_code_env_vars() -> set[str]:
    """Extract all env var names referenced via os.getenv / os.environ."""
    env_vars: set[str] = set()
    for py_file in _iter_source_files(SRC_DIR):
        try:
            text = py_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for g1, g2 in _GETENV_RE.findall(text):
            name = g1 or g2
            if name:
                env_vars.add(name)
    return env_vars


def _collect_documented_env_vars() -> set[str]:
    """Extract env var names from .env.example and GETTING_STARTED.md."""
    env_vars: set[str] = set()
    # Pattern: lines like KEY=value or # KEY=value or bare KEY mentions in markdown
    line_pattern = re.compile(r"^#?\s*([A-Z][A-Z0-9_]{2,})\s*(?:=|$)", re.MULTILINE)

    for path in [ENV_EXAMPLE, GETTING_STARTED, ROOT / "GETTING_STARTED.md"]:
        if path.exists():
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for match in line_pattern.finditer(text):
                name = match.group(1)
                # Skip common false positives
                if len(name) >= 3 and name not in _ENV_VAR_FALSE_POSITIVES:
                    env_vars.add(name)
    return env_vars


def check_env_vars() -> bool:
    """Verify env vars used in code are documented in .env.example / GETTING_STARTED.md."""
    print("\n" + "=" * 60)
    print("CHECK 5: Environment Variable Audit")
    print("=" * 60)

    code_vars = _collect_code_env_vars()
    documented_vars = _collect_documented_env_vars()

    undocumented = code_vars - documented_vars

    print(f"  Env vars in code: {len(code_vars)}")
    print(f"  Env vars documented: {len(documented_vars)}")
    print(f"  Undocumented: {len(undocumented)}")

    if undocumented:
        warn(
            "Undocumented Environment Variables",
            f"{len(undocumented)} env var(s) used in src/ but not documented in "
            ".env.example or GETTING_STARTED.md:\n"
            + "\n".join(f"  {v}" for v in sorted(undocumented)[:40])
            + ("\n  ... (truncated)" if len(undocumented) > 40 else ""),
        )
        return True  # Warn only — not all code-vars need user-facing docs

    print(f"  ✅ All {len(code_vars)} env vars appear to be documented.")
    return True


# ---------------------------------------------------------------------------
# Check 6: Documentation file reference checking
# ---------------------------------------------------------------------------

# Matches references like `src/foo/bar.py`, src/foo/bar.py, `config/murphy.yaml` etc.
_FILE_REF_RE = re.compile(
    r"(?<![`\w/])"                      # not preceded by identifier chars
    r"(`?)?"                             # optional opening backtick
    r"((?:src|config|scripts|docs|tests|bots|static|k8s|templates)"
    r"(?:/[A-Za-z0-9_.@-]+)+)"          # path with at least one component
    r"(`)?",                             # optional closing backtick
)

# Directories to skip when walking for .md files
_MD_SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", "telemetry_evidence"}


def _iter_md_files(root: Path):
    """Yield all .md files under root, skipping noisy directories."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _MD_SKIP_DIRS]
        for fname in filenames:
            if fname.endswith(".md"):
                yield Path(dirpath) / fname


def check_doc_references() -> bool:
    """Parse all *.md files for file path references and verify they exist."""
    print("\n" + "=" * 60)
    print("CHECK 6: Documentation File Reference Checking")
    print("=" * 60)

    broken: list[str] = []
    checked = 0

    # Search in the Murphy System subdir AND the repo root
    for search_root in [ROOT, REPO_ROOT]:
        for md_file in _iter_md_files(search_root):
            try:
                text = md_file.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            for match in _FILE_REF_RE.finditer(text):
                ref_path = match.group(2)
                checked += 1

                # Resolve relative to Murphy System root first, then repo root
                candidate_murphy = ROOT / ref_path
                candidate_repo = REPO_ROOT / ref_path

                if not candidate_murphy.exists() and not candidate_repo.exists():
                    rel_md = md_file.relative_to(REPO_ROOT) if REPO_ROOT in md_file.parents else md_file
                    broken.append(f"  {rel_md}: {ref_path}")

    # Deduplicate
    broken = sorted(set(broken))

    print(f"  File references checked: {checked}")
    print(f"  Broken references: {len(broken)}")

    if broken:
        warn(
            "Broken Documentation References",
            f"{len(broken)} file reference(s) in *.md files point to non-existent paths:\n"
            + "\n".join(broken[:40])
            + ("\n  ... (truncated)" if len(broken) > 40 else ""),
        )
        return True  # Warn only — docs often reference files that will be created

    print(f"  ✅ All {checked} documented file references resolve to existing paths.")
    return True


# ---------------------------------------------------------------------------
# Summary printer
# ---------------------------------------------------------------------------

def _print_summary(results: dict[str, bool]) -> None:
    print("\n" + "=" * 60)
    print("GAP DETECTOR SUMMARY")
    print("=" * 60)
    all_pass = True
    for check, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}  {check}")
        if not passed:
            all_pass = False
    print("=" * 60)
    if all_pass:
        notice("Gap Detector", "All checks passed.")
        print("All checks passed. ✅")
    else:
        failed = [k for k, v in results.items() if not v]
        error("Gap Detector", f"Gap detector found failures: {', '.join(failed)}")
        print("Some checks FAILED. See annotations above. ❌")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Murphy System Gap Detector")
    parser.add_argument(
        "--generate-baseline",
        action="store_true",
        help="Regenerate docs/capability_baseline.json from current src/ and exit.",
    )
    args = parser.parse_args()

    if args.generate_baseline:
        generate_baseline()
        return 0

    results: dict[str, bool] = {}

    results["Storyline Conformance"] = check_storyline_conformance()
    results["Capability Drift"] = check_capability_drift()
    results["Debt Markers"] = check_debt_markers()
    results["API Endpoints"] = check_api_endpoints()
    results["Env Var Audit"] = check_env_vars()
    results["Doc References"] = check_doc_references()

    _print_summary(results)

    # Exit non-zero only if a hard-failure check failed
    hard_failures = [k for k, v in results.items() if not v]
    return 1 if hard_failures else 0


if __name__ == "__main__":
    sys.exit(main())
