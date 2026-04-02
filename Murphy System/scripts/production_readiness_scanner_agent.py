#!/usr/bin/env python3
# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL-1.1
#
# Murphy System — Production Readiness Scanner Agent
# Label: READINESS-SCANNER-001
#
# Runs daily at 1 AM PST to scan the entire Murphy System for production
# readiness.  Produces a dated checklist that separates human-only tasks
# from tasks that the Executor Agent can handle autonomously at 3 AM PST.
#
# Commissioning Principles (evaluated at every phase):
#   G1: Does the module do what it was designed to do?
#   G2: What exactly is the module supposed to do?
#   G3: What conditions are possible based on the module?
#   G4: Does the test profile reflect the full range of capabilities?
#   G5: What is the expected result at all points of operation?
#   G6: What is the actual result?
#   G7: If problems persist, restart from symptoms → validation.
#   G8: Has all ancillary code and documentation been updated?
#   G9: Has hardening been applied and the module recommissioned?

"""
Production Readiness Scanner Agent — daily system-wide production readiness audit.

Scans every module in Murphy System/src/ and evaluates production readiness
using the G1–G9 commissioning principles.  Outputs a dated JSON checklist
with two sections: ``human_tasks`` (require manual intervention) and
``agent_tasks`` (can be executed by the Executor Agent at 3 AM PST).

Usage:
    python production_readiness_scanner_agent.py --output-dir <dir>
    python production_readiness_scanner_agent.py --output-dir <dir> --scan-depth full
"""

from __future__ import annotations

import argparse
import ast
import importlib
import json
import logging
import os
import re
import subprocess
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("readiness-scanner")

# ── Constants ─────────────────────────────────────────────────────────────────
AGENT_VERSION = "1.0.0"
AGENT_LABEL = "READINESS-SCANNER-001"

# Repo structure
REPO_ROOT = Path(os.environ.get("MURPHY_REPO_ROOT", Path.cwd()))
MURPHY_SYSTEM = REPO_ROOT / "Murphy System"
MURPHY_SRC = MURPHY_SYSTEM / "src"
MURPHY_TESTS = MURPHY_SYSTEM / "tests"
MURPHY_DOCS = MURPHY_SYSTEM / "docs"
MURPHY_SCRIPTS = MURPHY_SYSTEM / "scripts"
ROOT_SRC = REPO_ROOT / "src"

# Minimum test-to-module ratio considered acceptable
MIN_TEST_RATIO = 0.3  # At least 30% of modules should have dedicated tests

# Known critical modules that must have tests
CRITICAL_MODULES = [
    "errors",
    "swarm_rate_governor",
    "forge_rate_limiter",
    "tool_registry",
    "feature_flags",
    "persistent_memory",
    "skill_system",
    "mcp_plugin",
    "multi_agent_coordinator",
    "gate_bypass_controller",
    "lcm_engine",
    "llm_provider",
    "rosetta",
    "runtime",
    "readiness_scanner",
    "deployment_readiness",
    "security_hardening_config",
    "auth_middleware",
    "input_validation",
]

# Debt markers
DEBT_MARKERS = ["TODO", "FIXME", "HACK", "STUB", "XXX", "NOQA"]

# Required env vars for production
REQUIRED_ENV_VARS = [
    "MURPHY_SECRET_KEY",
    "MURPHY_ENV",
    "DATABASE_URL",
]

# Required config files
REQUIRED_CONFIG_FILES = [
    "requirements_ci.txt",
    "pyproject.toml",
    ".env.example",
    "Dockerfile",
    "docker-compose.yml",
    "gunicorn.conf.py",
]


# ── Scan Checks ──────────────────────────────────────────────────────────────


def scan_module_inventory(src_dir: Path) -> dict[str, Any]:
    """
    G1/G2: Inventory all Python modules in src/ and determine what each does.

    Returns a dict with module names, file counts, and package status.
    """
    log.info("Scanning module inventory in %s", src_dir)
    modules: list[dict[str, Any]] = []
    py_files: list[Path] = []

    if not src_dir.exists():
        return {"total_modules": 0, "modules": [], "py_files": 0}

    for item in sorted(src_dir.iterdir()):
        if item.name.startswith(("__", ".")):
            continue
        if item.is_dir() and (item / "__init__.py").exists():
            py_count = len(list(item.rglob("*.py")))
            modules.append({
                "name": item.name,
                "type": "package",
                "file_count": py_count,
                "path": str(item.relative_to(REPO_ROOT)),
            })
        elif item.is_file() and item.suffix == ".py":
            py_files.append(item)
            modules.append({
                "name": item.stem,
                "type": "module",
                "file_count": 1,
                "path": str(item.relative_to(REPO_ROOT)),
            })

    return {
        "total_modules": len(modules),
        "packages": sum(1 for m in modules if m["type"] == "package"),
        "single_files": sum(1 for m in modules if m["type"] == "module"),
        "modules": modules,
    }


def scan_test_coverage(tests_dir: Path, modules: list[dict[str, Any]]) -> dict[str, Any]:
    """
    G4: Does the test profile reflect the full range of capabilities?

    Checks which modules have corresponding test files.
    """
    log.info("Scanning test coverage in %s", tests_dir)
    test_files: set[str] = set()
    if tests_dir.exists():
        for tf in tests_dir.rglob("test_*.py"):
            # Extract the module name from test_<name>.py
            test_files.add(tf.stem.removeprefix("test_"))

    covered: list[str] = []
    uncovered: list[str] = []
    for mod in modules:
        name = mod["name"]
        if name in test_files or f"test_{name}" in test_files:
            covered.append(name)
        else:
            uncovered.append(name)

    ratio = len(covered) / max(len(modules), 1)
    return {
        "total_modules": len(modules),
        "covered": len(covered),
        "uncovered": len(uncovered),
        "coverage_ratio": round(ratio, 3),
        "covered_modules": sorted(covered),
        "uncovered_modules": sorted(uncovered),
        "meets_minimum": ratio >= MIN_TEST_RATIO,
    }


def scan_critical_module_tests(tests_dir: Path) -> dict[str, Any]:
    """
    G4 (critical): Ensure all critical/crown-jewel modules have tests.
    """
    log.info("Checking critical module test coverage")
    test_files: set[str] = set()
    if tests_dir.exists():
        for tf in tests_dir.rglob("test_*.py"):
            test_files.add(tf.stem.removeprefix("test_"))

    missing: list[str] = []
    present: list[str] = []
    for mod in CRITICAL_MODULES:
        if mod in test_files:
            present.append(mod)
        else:
            missing.append(mod)

    return {
        "total_critical": len(CRITICAL_MODULES),
        "tested": len(present),
        "missing_tests": missing,
        "present_tests": present,
        "all_covered": len(missing) == 0,
    }


def scan_smoke_imports(src_dir: Path) -> dict[str, Any]:
    """
    G1/G6: Verify that all modules can be imported without errors.
    """
    log.info("Running smoke import checks")
    passed: list[str] = []
    failed: list[dict[str, str]] = []

    if not src_dir.exists():
        return {"passed": 0, "failed": 0, "failures": []}

    for item in sorted(src_dir.iterdir()):
        if item.name.startswith(("__", ".")):
            continue
        mod_name = item.stem if item.is_file() and item.suffix == ".py" else item.name
        import_path = f"src.{mod_name}"
        try:
            importlib.import_module(import_path)
            passed.append(mod_name)
        except Exception as exc:
            failed.append({"module": mod_name, "error": str(exc)[:200]})

    return {
        "passed": len(passed),
        "failed": len(failed),
        "failures": failed[:50],  # Cap for report size
    }


def scan_debt_markers(src_dir: Path) -> dict[str, Any]:
    """
    G3/G7: Find TODO/FIXME/HACK/STUB markers that indicate unfinished work.
    """
    log.info("Scanning for debt markers")
    markers: dict[str, int] = {m: 0 for m in DEBT_MARKERS}
    total = 0
    files_with_debt: list[dict[str, Any]] = []

    if not src_dir.exists():
        return {"total": 0, "by_type": markers, "files_with_debt": []}

    for py_file in sorted(src_dir.rglob("*.py")):
        try:
            content = py_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        file_markers: dict[str, int] = {}
        for marker in DEBT_MARKERS:
            count = len(re.findall(rf"\b{marker}\b", content, re.IGNORECASE))
            if count > 0:
                file_markers[marker] = count
                markers[marker] += count
                total += count
        if file_markers:
            files_with_debt.append({
                "file": str(py_file.relative_to(REPO_ROOT)),
                "markers": file_markers,
            })

    return {
        "total": total,
        "by_type": markers,
        "files_with_debt_count": len(files_with_debt),
        "top_files": sorted(
            files_with_debt,
            key=lambda f: sum(f["markers"].values()),
            reverse=True,
        )[:20],
    }


def scan_docstring_coverage(src_dir: Path) -> dict[str, Any]:
    """
    G2/G8: Check that modules have docstrings explaining what they do.
    """
    log.info("Scanning docstring coverage")
    with_docstring: int = 0
    without_docstring: list[str] = []
    total_files: int = 0

    if not src_dir.exists():
        return {"total": 0, "with_docstring": 0, "missing": []}

    for py_file in sorted(src_dir.glob("*.py")):
        if py_file.name.startswith("__"):
            continue
        total_files += 1
        try:
            content = py_file.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(content)
            if ast.get_docstring(tree):
                with_docstring += 1
            else:
                without_docstring.append(str(py_file.relative_to(REPO_ROOT)))
        except Exception:
            without_docstring.append(str(py_file.relative_to(REPO_ROOT)))

    return {
        "total_files": total_files,
        "with_docstring": with_docstring,
        "without_docstring": len(without_docstring),
        "missing_docstrings": without_docstring[:50],
        "coverage_pct": round(with_docstring / max(total_files, 1) * 100, 1),
    }


def scan_error_handling(src_dir: Path) -> dict[str, Any]:
    """
    G3/G9: Check for bare except clauses that violate hardening practices.
    """
    log.info("Scanning error handling patterns")
    bare_excepts: list[dict[str, Any]] = []

    if not src_dir.exists():
        return {"bare_except_count": 0, "violations": []}

    for py_file in sorted(src_dir.rglob("*.py")):
        try:
            content = py_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for i, line in enumerate(content.splitlines(), 1):
            stripped = line.strip()
            # Detect `except:` or `except Exception: pass` patterns
            if re.match(r"except\s*:", stripped):
                bare_excepts.append({
                    "file": str(py_file.relative_to(REPO_ROOT)),
                    "line": i,
                    "content": stripped[:100],
                })
            elif re.match(r"except\s+\w+.*:\s*$", stripped):
                # Check if next non-blank line is just 'pass'
                lines = content.splitlines()
                if i < len(lines):
                    next_line = lines[i].strip()
                    if next_line == "pass":
                        bare_excepts.append({
                            "file": str(py_file.relative_to(REPO_ROOT)),
                            "line": i,
                            "content": f"{stripped} / {next_line}",
                        })

    return {
        "bare_except_count": len(bare_excepts),
        "violations": bare_excepts[:30],
    }


def scan_source_parity(murphy_src: Path, root_src: Path) -> dict[str, Any]:
    """
    G8: Check that Murphy System/src/ and root src/ are in sync.
    """
    log.info("Scanning source parity")
    murphy_files: set[str] = set()
    root_files: set[str] = set()

    if murphy_src.exists():
        for f in murphy_src.rglob("*.py"):
            murphy_files.add(str(f.relative_to(murphy_src)))
    if root_src.exists():
        for f in root_src.rglob("*.py"):
            root_files.add(str(f.relative_to(root_src)))

    only_in_murphy = sorted(murphy_files - root_files)
    only_in_root = sorted(root_files - murphy_files)

    return {
        "murphy_files": len(murphy_files),
        "root_files": len(root_files),
        "only_in_murphy": only_in_murphy[:50],
        "only_in_root": only_in_root[:50],
        "in_sync": len(only_in_murphy) == 0 and len(only_in_root) == 0,
        "drift_count": len(only_in_murphy) + len(only_in_root),
    }


def scan_config_files(repo_root: Path) -> dict[str, Any]:
    """
    G8/G9: Verify all required configuration files exist.
    """
    log.info("Scanning configuration files")
    results: list[dict[str, Any]] = []
    for cfg in REQUIRED_CONFIG_FILES:
        path = repo_root / cfg
        results.append({
            "file": cfg,
            "exists": path.exists(),
            "size_bytes": path.stat().st_size if path.exists() else 0,
        })

    return {
        "total_required": len(REQUIRED_CONFIG_FILES),
        "present": sum(1 for r in results if r["exists"]),
        "missing": [r["file"] for r in results if not r["exists"]],
        "details": results,
    }


def scan_env_example(murphy_system: Path) -> dict[str, Any]:
    """
    G3: Ensure .env.example documents all required environment variables.
    """
    log.info("Scanning .env.example for required variables")
    env_file = murphy_system / ".env.example"
    documented_vars: set[str] = set()
    if env_file.exists():
        try:
            content = env_file.read_text(encoding="utf-8", errors="replace")
            for line in content.splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    var_name = line.split("=", 1)[0].strip()
                    documented_vars.add(var_name)
        except Exception:
            pass

    missing = [v for v in REQUIRED_ENV_VARS if v not in documented_vars]
    return {
        "documented_vars": len(documented_vars),
        "required_vars_missing": missing,
        "all_required_documented": len(missing) == 0,
    }


def scan_security_hardening(src_dir: Path) -> dict[str, Any]:
    """
    G9: Check for basic security hardening patterns.
    """
    log.info("Scanning security hardening")
    findings: list[dict[str, str]] = []

    # Check for hardcoded secrets patterns
    secret_patterns = [
        (r'(?:password|secret|key|token)\s*=\s*["\'][^"\']{8,}["\']', "Potential hardcoded secret"),
        (r'(?:sk-|sk_test_|sk_live_)[a-zA-Z0-9]{20,}', "Potential API key in source"),
    ]

    if src_dir.exists():
        for py_file in sorted(src_dir.rglob("*.py")):
            try:
                content = py_file.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            for pattern, desc in secret_patterns:
                for match in re.finditer(pattern, content, re.IGNORECASE):
                    # Skip if in a comment or env var assignment
                    line_start = content.rfind("\n", 0, match.start()) + 1
                    line = content[line_start:content.find("\n", match.start())]
                    if line.strip().startswith("#") or "os.environ" in line or "getenv" in line:
                        continue
                    findings.append({
                        "file": str(py_file.relative_to(REPO_ROOT)),
                        "description": desc,
                        "line_preview": line.strip()[:100],
                    })

    # Check for security-related modules
    security_modules = [
        "auth_middleware.py",
        "input_validation.py",
        "security_hardening_config.py",
        "csrf_protection.py",
        "fastapi_security.py",
    ]
    missing_security = [
        m for m in security_modules
        if not (src_dir / m).exists()
    ]

    return {
        "potential_secrets": len(findings),
        "secret_findings": findings[:20],
        "missing_security_modules": missing_security,
        "security_modules_complete": len(missing_security) == 0,
    }


def scan_workflow_health(repo_root: Path) -> dict[str, Any]:
    """
    G1/G5: Verify CI/CD workflows exist and are well-formed.
    """
    log.info("Scanning workflow health")
    workflows_dir = repo_root / ".github" / "workflows"
    results: list[dict[str, Any]] = []

    required_workflows = [
        "ci.yml",
        "hetzner-deploy.yml",
        "hetzner-deploy-recovery.yml",
        "gap-detector.yml",
        "source-drift-guard.yml",
    ]

    if workflows_dir.exists():
        for wf in required_workflows:
            path = workflows_dir / wf
            results.append({
                "workflow": wf,
                "exists": path.exists(),
                "size_bytes": path.stat().st_size if path.exists() else 0,
            })

    return {
        "total_required": len(required_workflows),
        "present": sum(1 for r in results if r["exists"]),
        "missing": [r["workflow"] for r in results if not r["exists"]],
        "details": results,
    }


def scan_api_documentation(murphy_system: Path, repo_root: Path) -> dict[str, Any]:
    """
    G2/G8: Check that API endpoints are documented.
    """
    log.info("Scanning API documentation")
    api_docs_path = repo_root / "API_ROUTES.md"
    api_doc_path_2 = repo_root / "API_DOCUMENTATION.md"

    return {
        "api_routes_exists": api_docs_path.exists(),
        "api_documentation_exists": api_doc_path_2.exists(),
        "docs_directory_exists": (murphy_system / "docs").exists(),
        "has_deployment_guide": (repo_root / "DEPLOYMENT_GUIDE.md").exists(),
        "has_getting_started": (murphy_system / "GETTING_STARTED.md").exists(),
    }


# ── Task Classification ─────────────────────────────────────────────────────


def classify_tasks(scan_results: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Classify findings into human-only tasks and agent-executable tasks.

    Human tasks: require judgment, external access, infrastructure changes,
                 or design decisions.
    Agent tasks: can be fixed programmatically — missing files, syncing,
                 documentation updates, adding test stubs.
    """
    human_tasks: list[dict[str, Any]] = []
    agent_tasks: list[dict[str, Any]] = []

    # ── Source parity drift ──────────────────────────────────────────────
    parity = scan_results.get("source_parity", {})
    if not parity.get("in_sync", True):
        agent_tasks.append({
            "id": "PARITY-001",
            "category": "source_parity",
            "priority": "HIGH",
            "title": "Fix source parity drift between Murphy System/src/ and root src/",
            "description": (
                f"Found {parity.get('drift_count', 0)} files out of sync. "
                "Run enforce_canonical_source.py to sync Murphy System/ → root."
            ),
            "commissioning": "G8: Ancillary code must be updated to reflect changes",
            "action": "sync_source_parity",
            "details": {
                "only_in_murphy": parity.get("only_in_murphy", [])[:20],
                "only_in_root": parity.get("only_in_root", [])[:20],
            },
        })

    # ── Missing critical module tests ────────────────────────────────────
    critical_tests = scan_results.get("critical_module_tests", {})
    for mod in critical_tests.get("missing_tests", []):
        agent_tasks.append({
            "id": f"TEST-CRIT-{mod.upper()}",
            "category": "test_coverage",
            "priority": "HIGH",
            "title": f"Create test file for critical module: {mod}",
            "description": (
                f"Critical module '{mod}' has no test file. "
                "Create tests/test_{mod}.py with commissioning G1–G9 docstring."
            ),
            "commissioning": "G4: Test profile must reflect full range of capabilities",
            "action": "create_test_stub",
            "details": {"module": mod},
        })

    # ── Smoke import failures ────────────────────────────────────────────
    imports = scan_results.get("smoke_imports", {})
    for failure in imports.get("failures", []):
        mod = failure["module"]
        err = failure["error"]
        if "No module named" in err:
            agent_tasks.append({
                "id": f"IMPORT-{mod.upper()}",
                "category": "import_error",
                "priority": "HIGH",
                "title": f"Fix import error for module: {mod}",
                "description": f"Module src.{mod} fails to import: {err}",
                "commissioning": "G1: Module must do what it was designed to do",
                "action": "fix_import",
                "details": {"module": mod, "error": err},
            })
        else:
            human_tasks.append({
                "id": f"IMPORT-REVIEW-{mod.upper()}",
                "category": "import_error",
                "priority": "MEDIUM",
                "title": f"Review import failure for module: {mod}",
                "description": f"Module src.{mod} fails to import with non-trivial error: {err}",
                "commissioning": "G7: Restart from symptoms and work back through validation",
            })

    # ── Bare except violations ───────────────────────────────────────────
    error_handling = scan_results.get("error_handling", {})
    if error_handling.get("bare_except_count", 0) > 0:
        agent_tasks.append({
            "id": "HARDENING-BARE-EXCEPT",
            "category": "hardening",
            "priority": "MEDIUM",
            "title": "Fix bare except clauses for production hardening",
            "description": (
                f"Found {error_handling['bare_except_count']} bare except clauses. "
                "Replace with specific exception types and add logging."
            ),
            "commissioning": "G9: Hardening must be applied",
            "action": "fix_bare_excepts",
            "details": {"violations": error_handling.get("violations", [])[:10]},
        })

    # ── Missing config files ─────────────────────────────────────────────
    config = scan_results.get("config_files", {})
    for missing in config.get("missing", []):
        human_tasks.append({
            "id": f"CONFIG-{missing.upper().replace('.', '-')}",
            "category": "configuration",
            "priority": "HIGH",
            "title": f"Create missing configuration file: {missing}",
            "description": f"Required config file '{missing}' is missing from repo root.",
            "commissioning": "G3: All conditions must be covered",
        })

    # ── Missing security modules ─────────────────────────────────────────
    security = scan_results.get("security_hardening", {})
    for mod in security.get("missing_security_modules", []):
        human_tasks.append({
            "id": f"SECURITY-{mod.upper().replace('.', '-')}",
            "category": "security",
            "priority": "HIGH",
            "title": f"Security module missing: {mod}",
            "description": f"Security-critical module '{mod}' not found in src/.",
            "commissioning": "G9: Hardening must be applied",
        })

    if security.get("potential_secrets", 0) > 0:
        human_tasks.append({
            "id": "SECURITY-SECRETS-REVIEW",
            "category": "security",
            "priority": "CRITICAL",
            "title": "Review potential hardcoded secrets",
            "description": (
                f"Found {security['potential_secrets']} potential hardcoded secrets. "
                "These must be manually reviewed and moved to environment variables."
            ),
            "commissioning": "G9: Hardening must be applied",
        })

    # ── Missing workflows ────────────────────────────────────────────────
    workflows = scan_results.get("workflow_health", {})
    for wf in workflows.get("missing", []):
        human_tasks.append({
            "id": f"WORKFLOW-{wf.upper().replace('.', '-')}",
            "category": "ci_cd",
            "priority": "HIGH",
            "title": f"Missing CI/CD workflow: {wf}",
            "description": f"Required workflow '{wf}' not found in .github/workflows/.",
            "commissioning": "G5: Expected results must be defined at all operation points",
        })

    # ── Debt markers ─────────────────────────────────────────────────────
    debt = scan_results.get("debt_markers", {})
    if debt.get("total", 0) > 100:
        agent_tasks.append({
            "id": "DEBT-INVENTORY",
            "category": "technical_debt",
            "priority": "LOW",
            "title": "Catalog and prioritize technical debt markers",
            "description": (
                f"Found {debt['total']} debt markers across the codebase. "
                "Generate a prioritized debt report with resolution recommendations."
            ),
            "commissioning": "G7: Restart from symptoms and work back through validation",
            "action": "catalog_debt",
            "details": {"total": debt["total"], "by_type": debt.get("by_type", {})},
        })

    # ── Missing docstrings ───────────────────────────────────────────────
    docstrings = scan_results.get("docstring_coverage", {})
    if docstrings.get("without_docstring", 0) > 0:
        agent_tasks.append({
            "id": "DOCS-DOCSTRINGS",
            "category": "documentation",
            "priority": "LOW",
            "title": "Add module-level docstrings to undocumented modules",
            "description": (
                f"{docstrings['without_docstring']} modules lack docstrings. "
                "Add G2-compliant docstrings describing module purpose."
            ),
            "commissioning": "G2/G8: Purpose must be documented",
            "action": "add_docstrings",
            "details": {
                "missing": docstrings.get("missing_docstrings", [])[:20],
            },
        })

    # ── Missing env vars in .env.example ─────────────────────────────────
    env = scan_results.get("env_example", {})
    if not env.get("all_required_documented", True):
        agent_tasks.append({
            "id": "ENV-MISSING-VARS",
            "category": "configuration",
            "priority": "MEDIUM",
            "title": "Add missing required env vars to .env.example",
            "description": (
                f"Missing required env vars: {env.get('required_vars_missing', [])}. "
                "Add them to .env.example with appropriate defaults."
            ),
            "commissioning": "G3: All conditions must be covered",
            "action": "update_env_example",
            "details": {"missing_vars": env.get("required_vars_missing", [])},
        })

    # ── Missing API documentation ────────────────────────────────────────
    api_docs = scan_results.get("api_documentation", {})
    if not api_docs.get("api_routes_exists", True):
        human_tasks.append({
            "id": "DOCS-API-ROUTES",
            "category": "documentation",
            "priority": "MEDIUM",
            "title": "Create API_ROUTES.md documentation",
            "description": "API_ROUTES.md is missing — document all API endpoints.",
            "commissioning": "G2/G8: All documentation must be updated",
        })

    return human_tasks, agent_tasks


# ── Report Generation ────────────────────────────────────────────────────────


def generate_checklist(
    scan_results: dict[str, Any],
    human_tasks: list[dict[str, Any]],
    agent_tasks: list[dict[str, Any]],
    output_dir: str,
) -> dict[str, Any]:
    """
    Produce the final dated checklist as both JSON and Markdown.
    """
    timestamp = datetime.now(timezone.utc)
    date_str = timestamp.strftime("%Y-%m-%d")

    checklist: dict[str, Any] = {
        "agent_version": AGENT_VERSION,
        "agent_label": AGENT_LABEL,
        "scan_timestamp": timestamp.isoformat(),
        "scan_date": date_str,
        "summary": {
            "total_modules": scan_results.get("module_inventory", {}).get("total_modules", 0),
            "test_coverage_ratio": scan_results.get("test_coverage", {}).get("coverage_ratio", 0),
            "critical_tests_complete": scan_results.get("critical_module_tests", {}).get("all_covered", False),
            "source_in_sync": scan_results.get("source_parity", {}).get("in_sync", False),
            "debt_markers": scan_results.get("debt_markers", {}).get("total", 0),
            "smoke_import_failures": scan_results.get("smoke_imports", {}).get("failed", 0),
            "bare_except_count": scan_results.get("error_handling", {}).get("bare_except_count", 0),
            "total_human_tasks": len(human_tasks),
            "total_agent_tasks": len(agent_tasks),
        },
        "commissioning_assessment": {
            "G1_modules_functional": scan_results.get("smoke_imports", {}).get("failed", 0) == 0,
            "G2_purpose_documented": scan_results.get("docstring_coverage", {}).get("coverage_pct", 0) > 80,
            "G3_conditions_covered": scan_results.get("env_example", {}).get("all_required_documented", False),
            "G4_test_profile_complete": scan_results.get("critical_module_tests", {}).get("all_covered", False),
            "G5_expected_results_defined": scan_results.get("workflow_health", {}).get("present", 0) > 3,
            "G6_actual_results_verified": scan_results.get("smoke_imports", {}).get("passed", 0) > 0,
            "G7_validation_loop_active": True,  # This agent IS the validation loop
            "G8_documentation_updated": scan_results.get("api_documentation", {}).get("api_routes_exists", False),
            "G9_hardening_applied": scan_results.get("error_handling", {}).get("bare_except_count", 0) < 10,
        },
        "human_tasks": human_tasks,
        "agent_tasks": agent_tasks,
        "scan_results": scan_results,
    }

    # Write JSON
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    json_file = output_path / f"readiness_checklist_{date_str}.json"
    json_file.write_text(json.dumps(checklist, indent=2, default=str), encoding="utf-8")
    log.info("Checklist JSON written to %s", json_file)

    # Also write as the "latest" for the executor agent to find
    latest_file = output_path / "readiness_checklist_latest.json"
    latest_file.write_text(json.dumps(checklist, indent=2, default=str), encoding="utf-8")

    # Write Markdown report
    md_file = output_path / f"readiness_checklist_{date_str}.md"
    md_content = _render_markdown(checklist)
    md_file.write_text(md_content, encoding="utf-8")
    log.info("Checklist Markdown written to %s", md_file)

    return checklist


def _render_markdown(checklist: dict[str, Any]) -> str:
    """Render the checklist as a Markdown document."""
    summary = checklist["summary"]
    assessment = checklist["commissioning_assessment"]
    date_str = checklist["scan_date"]

    lines = [
        f"# Murphy System — Production Readiness Checklist",
        f"",
        f"**Date:** {date_str}",
        f"**Agent:** {AGENT_LABEL} v{AGENT_VERSION}",
        f"**Generated:** {checklist['scan_timestamp']}",
        f"",
        f"---",
        f"",
        f"## Summary",
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total Modules | {summary['total_modules']} |",
        f"| Test Coverage Ratio | {summary['test_coverage_ratio']:.1%} |",
        f"| Critical Tests Complete | {'✅' if summary['critical_tests_complete'] else '❌'} |",
        f"| Source In Sync | {'✅' if summary['source_in_sync'] else '❌'} |",
        f"| Debt Markers | {summary['debt_markers']} |",
        f"| Smoke Import Failures | {summary['smoke_import_failures']} |",
        f"| Bare Except Violations | {summary['bare_except_count']} |",
        f"| Human Tasks | {summary['total_human_tasks']} |",
        f"| Agent Tasks | {summary['total_agent_tasks']} |",
        f"",
        f"---",
        f"",
        f"## Commissioning Assessment (G1–G9)",
        f"",
    ]

    g_labels = {
        "G1_modules_functional": "G1: Modules do what they're designed to do",
        "G2_purpose_documented": "G2: Module purpose is documented",
        "G3_conditions_covered": "G3: All conditions are covered",
        "G4_test_profile_complete": "G4: Test profile reflects full capabilities",
        "G5_expected_results_defined": "G5: Expected results defined",
        "G6_actual_results_verified": "G6: Actual results verified",
        "G7_validation_loop_active": "G7: Validation loop is active",
        "G8_documentation_updated": "G8: Documentation is updated",
        "G9_hardening_applied": "G9: Hardening is applied",
    }

    for key, label in g_labels.items():
        status = "✅" if assessment.get(key, False) else "❌"
        lines.append(f"- [{('x' if assessment.get(key, False) else ' ')}] {label} {status}")

    lines.extend([
        f"",
        f"---",
        f"",
        f"## 🧑 Human Tasks (Require Manual Intervention)",
        f"",
    ])

    if checklist["human_tasks"]:
        for task in checklist["human_tasks"]:
            priority = task.get("priority", "MEDIUM")
            lines.append(f"### [{priority}] {task['title']}")
            lines.append(f"")
            lines.append(f"- **ID:** {task['id']}")
            lines.append(f"- **Category:** {task['category']}")
            lines.append(f"- **Description:** {task['description']}")
            lines.append(f"- **Commissioning:** {task.get('commissioning', 'N/A')}")
            lines.append(f"")
    else:
        lines.append("No human tasks identified — all items can be handled by the Executor Agent.")
        lines.append("")

    lines.extend([
        f"---",
        f"",
        f"## 🤖 Agent Tasks (Executor Agent @ 3 AM PST)",
        f"",
    ])

    if checklist["agent_tasks"]:
        for task in checklist["agent_tasks"]:
            priority = task.get("priority", "MEDIUM")
            lines.append(f"### [{priority}] {task['title']}")
            lines.append(f"")
            lines.append(f"- **ID:** {task['id']}")
            lines.append(f"- **Category:** {task['category']}")
            lines.append(f"- **Action:** `{task.get('action', 'N/A')}`")
            lines.append(f"- **Description:** {task['description']}")
            lines.append(f"- **Commissioning:** {task.get('commissioning', 'N/A')}")
            lines.append(f"")
    else:
        lines.append("No agent tasks identified — system appears production-ready!")
        lines.append("")

    lines.extend([
        f"---",
        f"",
        f"*Generated by {AGENT_LABEL} v{AGENT_VERSION}*",
        f"",
    ])

    return "\n".join(lines)


# ── Main Scanner ─────────────────────────────────────────────────────────────


def run_scan(output_dir: str, scan_depth: str = "standard") -> dict[str, Any]:
    """
    Execute the full production readiness scan.

    G2: This function orchestrates all scan checks and produces the checklist.
    G5: Expected: a comprehensive JSON + Markdown checklist with dated findings.
    """
    log.info("╔══════════════════════════════════════════════════════════╗")
    log.info("║   MURPHY PRODUCTION READINESS SCANNER — v%s         ║", AGENT_VERSION)
    log.info("╠══════════════════════════════════════════════════════════╣")
    log.info("║  Scan Depth: %-40s  ║", scan_depth)
    log.info("║  Output Dir: %-40s  ║", output_dir[:40])
    log.info("╚══════════════════════════════════════════════════════════╝")

    scan_results: dict[str, Any] = {}

    # Phase 1: Module inventory
    scan_results["module_inventory"] = scan_module_inventory(MURPHY_SRC)

    # Phase 2: Test coverage
    modules = scan_results["module_inventory"].get("modules", [])
    scan_results["test_coverage"] = scan_test_coverage(MURPHY_TESTS, modules)

    # Phase 3: Critical module tests
    scan_results["critical_module_tests"] = scan_critical_module_tests(MURPHY_TESTS)

    # Phase 4: Smoke imports (skip in CI-only mode to avoid heavy imports)
    if scan_depth == "full":
        scan_results["smoke_imports"] = scan_smoke_imports(MURPHY_SRC)
    else:
        scan_results["smoke_imports"] = {"passed": 0, "failed": 0, "failures": [], "skipped": True}

    # Phase 5: Debt markers
    scan_results["debt_markers"] = scan_debt_markers(MURPHY_SRC)

    # Phase 6: Docstring coverage
    scan_results["docstring_coverage"] = scan_docstring_coverage(MURPHY_SRC)

    # Phase 7: Error handling
    scan_results["error_handling"] = scan_error_handling(MURPHY_SRC)

    # Phase 8: Source parity
    scan_results["source_parity"] = scan_source_parity(MURPHY_SRC, ROOT_SRC)

    # Phase 9: Config files
    scan_results["config_files"] = scan_config_files(REPO_ROOT)

    # Phase 10: Environment variable documentation
    scan_results["env_example"] = scan_env_example(MURPHY_SYSTEM)

    # Phase 11: Security hardening
    scan_results["security_hardening"] = scan_security_hardening(MURPHY_SRC)

    # Phase 12: Workflow health
    scan_results["workflow_health"] = scan_workflow_health(REPO_ROOT)

    # Phase 13: API documentation
    scan_results["api_documentation"] = scan_api_documentation(MURPHY_SYSTEM, REPO_ROOT)

    # Classify tasks
    human_tasks, agent_tasks = classify_tasks(scan_results)

    # Generate checklist
    checklist = generate_checklist(scan_results, human_tasks, agent_tasks, output_dir)

    log.info("═══════════════════════════════════════════════════════════")
    log.info("  Scan complete: %d human tasks, %d agent tasks",
             len(human_tasks), len(agent_tasks))
    log.info("═══════════════════════════════════════════════════════════")

    return checklist


# ── CLI entrypoint ────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Murphy Production Readiness Scanner Agent — daily production audit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Scans the Murphy System for production readiness and generates
            a dated checklist with human tasks and agent-executable tasks.

            The checklist is consumed by the Production Readiness Executor Agent
            at 3 AM PST to automatically resolve actionable items.
        """),
    )
    parser.add_argument("--output-dir", required=True,
                        help="Directory for output artifacts (checklist JSON + Markdown)")
    parser.add_argument("--scan-depth", choices=["standard", "full"], default="standard",
                        help="Scan depth: 'standard' (fast) or 'full' (includes smoke imports)")
    parser.add_argument("--version", action="version",
                        version=f"%(prog)s {AGENT_VERSION}")

    args = parser.parse_args()
    run_scan(args.output_dir, args.scan_depth)


if __name__ == "__main__":
    main()
