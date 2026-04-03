#!/usr/bin/env python3
# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL-1.1
#
# Murphy System — Integration Parity Agent Script
# Label: INTEGRATION-PARITY-001
#
# Validates the full integration chain for every module:
# source → test → registry → server → baseline.
#
# Phases:
#   test-parity     — Check every module has a corresponding test file
#   registry-parity — Check every module is in module_registry.yaml
#   import-check    — Smoke-test module imports
#   server-wiring   — Check API-exposing modules are wired in server
#   baseline-check  — Check modules appear in capability_baseline.json
#   matrix          — Generate combined parity matrix

"""
Integration Parity Agent — full module lifecycle enforcement.

Usage:
    python integration_parity_agent.py --phase <phase> --output-dir <dir>
"""

from __future__ import annotations

import argparse
import importlib
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("integration-parity-agent")

# ── Constants ─────────────────────────────────────────────────────────────────
AGENT_VERSION = "1.0.0"
AGENT_LABEL = "INTEGRATION-PARITY-001"

REGISTRY_PATH = Path("module_registry.yaml")
BASELINE_PATH = Path("Murphy System/docs/capability_baseline.json")
SERVER_PATH = Path("murphy_production_server.py")


# ── Utilities ────────────────────────────────────────────────────────────────
def _get_source_modules() -> list[dict[str, str]]:
    """Get all non-init Python modules in src/."""
    src_dir = Path("src")
    modules = []
    for py_file in sorted(src_dir.rglob("*.py")):
        if py_file.name == "__init__.py":
            continue
        rel = py_file.relative_to(src_dir)
        module_key = "src." + str(rel).replace("/", ".").replace("\\", ".").removesuffix(".py")
        modules.append({
            "file": str(py_file),
            "module": module_key,
            "name": py_file.stem,
        })
    return modules


# ── Phase: Test Parity ───────────────────────────────────────────────────────
def phase_test_parity(output_dir: Path) -> dict[str, Any]:
    """Check every module has a corresponding test file."""
    log.info("Phase: TEST-PARITY — checking test coverage")
    modules = _get_source_modules()
    tests_dir = Path("tests")
    existing_tests = {f.stem for f in tests_dir.rglob("test_*.py")} if tests_dir.exists() else set()

    have_tests = 0
    missing_tests: list[str] = []

    for mod in modules:
        expected_test = f"test_{mod['name']}"
        if expected_test in existing_tests:
            have_tests += 1
        else:
            missing_tests.append(mod["name"])

    report = {
        "agent": AGENT_LABEL,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": "test-parity",
        "total_modules": len(modules),
        "have_tests": have_tests,
        "missing_tests_count": len(missing_tests),
        "missing_tests": missing_tests[:50],
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "test_parity.json").write_text(json.dumps(report, indent=2))
    log.info("Test parity: %d/%d modules have tests", have_tests, len(modules))
    return report


# ── Phase: Registry Parity ───────────────────────────────────────────────────
def phase_registry_parity(output_dir: Path) -> dict[str, Any]:
    """Check every module is registered in module_registry.yaml."""
    log.info("Phase: REGISTRY-PARITY — checking module registry")
    modules = _get_source_modules()

    registry_modules: set[str] = set()
    if REGISTRY_PATH.exists():
        try:
            import yaml
            data = yaml.safe_load(REGISTRY_PATH.read_text())
            for entry in data.get("modules", []):
                registry_modules.add(entry.get("key", ""))
        except Exception as exc:
            log.warning("Failed to parse registry: %s", exc)

    in_registry = 0
    missing_from_registry: list[str] = []

    for mod in modules:
        if mod["module"] in registry_modules:
            in_registry += 1
        else:
            missing_from_registry.append(mod["module"])

    report = {
        "agent": AGENT_LABEL,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": "registry-parity",
        "total_modules": len(modules),
        "in_registry": in_registry,
        "missing_count": len(missing_from_registry),
        "missing": missing_from_registry[:50],
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "registry_parity.json").write_text(json.dumps(report, indent=2))
    log.info("Registry parity: %d/%d modules registered", in_registry, len(modules))
    return report


# ── Phase: Import Check ─────────────────────────────────────────────────────
def phase_import_check(output_dir: Path) -> dict[str, Any]:
    """Smoke-test module imports."""
    log.info("Phase: IMPORT-CHECK — smoke-testing imports")
    modules = _get_source_modules()

    importable = 0
    import_failures: list[dict[str, str]] = []

    # Sample a subset to keep CI fast
    sample_size = min(50, len(modules))
    sample = modules[:sample_size]

    for mod in sample:
        try:
            importlib.import_module(mod["module"])
            importable += 1
        except Exception as exc:
            import_failures.append({
                "module": mod["module"],
                "error": str(exc),
            })

    report = {
        "agent": AGENT_LABEL,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": "import-check",
        "total_sampled": sample_size,
        "importable": importable,
        "failures": len(import_failures),
        "failure_details": import_failures[:30],
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "import_check.json").write_text(json.dumps(report, indent=2))
    log.info("Import check: %d/%d importable", importable, sample_size)
    return report


# ── Phase: Server Wiring ────────────────────────────────────────────────────
def phase_server_wiring(output_dir: Path) -> dict[str, Any]:
    """Check API-exposing modules are wired in murphy_production_server.py."""
    log.info("Phase: SERVER-WIRING — checking production server imports")

    server_content = ""
    if SERVER_PATH.exists():
        server_content = SERVER_PATH.read_text(encoding="utf-8", errors="replace")

    # Find modules that define API routes (contain @app or @router patterns)
    src_dir = Path("src")
    api_modules: list[dict[str, str]] = []
    wired = 0

    for py_file in sorted(src_dir.rglob("*.py")):
        if py_file.name.startswith("_"):
            continue
        try:
            content = py_file.read_text(encoding="utf-8", errors="replace")
            if "@app." in content or "@router." in content or "APIRouter" in content:
                mod_name = py_file.stem
                is_wired = mod_name in server_content
                api_modules.append({
                    "module": mod_name,
                    "file": str(py_file),
                    "wired": is_wired,
                })
                if is_wired:
                    wired += 1
        except (OSError, UnicodeDecodeError):
            continue

    report = {
        "agent": AGENT_LABEL,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": "server-wiring",
        "api_modules_found": len(api_modules),
        "server_wired": wired,
        "unwired": [m for m in api_modules if not m["wired"]][:30],
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "server_wiring.json").write_text(json.dumps(report, indent=2))
    log.info("Server wiring: %d/%d API modules wired", wired, len(api_modules))
    return report


# ── Phase: Baseline Check ───────────────────────────────────────────────────
def phase_baseline_check(output_dir: Path) -> dict[str, Any]:
    """Check modules appear in capability_baseline.json."""
    log.info("Phase: BASELINE-CHECK — validating capability baseline")
    modules = _get_source_modules()

    baseline_entries: set[str] = set()
    if BASELINE_PATH.exists():
        try:
            data = json.loads(BASELINE_PATH.read_text())
            if isinstance(data, dict):
                raw = data.get("modules", [])
                if isinstance(raw, dict):
                    baseline_entries = set(raw.keys())
                elif isinstance(raw, list):
                    baseline_entries = {
                        (item if isinstance(item, str) else item.get("module", ""))
                        for item in raw
                    }
            elif isinstance(data, list):
                baseline_entries = {
                    (item if isinstance(item, str) else item.get("module", ""))
                    for item in data
                }
        except (json.JSONDecodeError, KeyError) as exc:
            log.warning("Failed to parse baseline: %s", exc)

    in_baseline = sum(1 for m in modules if m["name"] in baseline_entries or m["module"] in baseline_entries)

    report = {
        "agent": AGENT_LABEL,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": "baseline-check",
        "total_modules": len(modules),
        "in_baseline": in_baseline,
        "baseline_entries": len(baseline_entries),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "baseline_check.json").write_text(json.dumps(report, indent=2))
    log.info("Baseline check: %d/%d modules in baseline", in_baseline, len(modules))
    return report


# ── Phase: Matrix ────────────────────────────────────────────────────────────
def phase_matrix(output_dir: Path) -> dict[str, Any]:
    """Generate combined parity matrix from all phase results."""
    log.info("Phase: MATRIX — building parity matrix")

    totals: dict[str, int] = {
        "total_modules": 0,
        "have_tests": 0,
        "in_registry": 0,
        "importable": 0,
        "server_wired": 0,
        "in_baseline": 0,
    }

    phase_files = {
        "test_parity": ("total_modules", "have_tests"),
        "registry_parity": ("total_modules", "in_registry"),
        "import_check": ("total_sampled", "importable"),
        "server_wiring": ("api_modules_found", "server_wired"),
        "baseline_check": ("total_modules", "in_baseline"),
    }

    for filename, (total_key, value_key) in phase_files.items():
        path = output_dir / f"{filename}.json"
        if path.exists():
            data = json.loads(path.read_text())
            if total_key == "total_modules" and totals["total_modules"] == 0:
                totals["total_modules"] = data.get(total_key, 0)
            totals[value_key] = data.get(value_key, 0)

    # Count gaps
    gap_count = 0
    for key in ["have_tests", "in_registry", "in_baseline"]:
        if totals[key] < totals["total_modules"]:
            gap_count += totals["total_modules"] - totals[key]

    report = {
        "agent": AGENT_LABEL,
        "version": AGENT_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": "matrix",
        **totals,
        "gap_count": gap_count,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "parity_report.json").write_text(json.dumps(report, indent=2))

    # Markdown report
    md_lines = [
        "## 🔗 Module Integration Parity Report",
        "",
        "| Check | Count | Total | Coverage |",
        "|-------|-------|-------|----------|",
    ]
    total = max(totals["total_modules"], 1)
    for label, key in [
        ("Test files", "have_tests"),
        ("In registry", "in_registry"),
        ("Importable (sample)", "importable"),
        ("Server-wired", "server_wired"),
        ("In baseline", "in_baseline"),
    ]:
        val = totals[key]
        pct = round(val / total * 100, 1) if key != "importable" else "N/A"
        md_lines.append(f"| {label} | {val} | {total} | {pct}% |")

    status = "✅ No gaps" if gap_count == 0 else f"⚠️ {gap_count} gap(s) found"
    md_lines.extend([
        "",
        f"**Status:** {status}",
        "",
        f"*Generated by {AGENT_LABEL} v{AGENT_VERSION}*",
    ])
    (output_dir / "parity_report.md").write_text("\n".join(md_lines))

    log.info("Parity matrix: %d total gaps", gap_count)
    return report


# ── CLI ──────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="Integration Parity Agent")
    parser.add_argument(
        "--phase", required=True,
        choices=["test-parity", "registry-parity", "import-check",
                 "server-wiring", "baseline-check", "matrix"],
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    dispatch = {
        "test-parity": lambda: phase_test_parity(args.output_dir),
        "registry-parity": lambda: phase_registry_parity(args.output_dir),
        "import-check": lambda: phase_import_check(args.output_dir),
        "server-wiring": lambda: phase_server_wiring(args.output_dir),
        "baseline-check": lambda: phase_baseline_check(args.output_dir),
        "matrix": lambda: phase_matrix(args.output_dir),
    }
    dispatch[args.phase]()


if __name__ == "__main__":
    main()
