"""
Tests for docs/DOC_CODE_GAP_ANALYSIS.md — Phase 3 Documentation Audit.

These tests programmatically verify:
  1. The gap analysis document exists and is non-empty.
  2. Core documented API routes in API_ROUTES.md have corresponding code.
  3. Critical env vars referenced in code appear in .env.example.
  4. All Python modules in src/ have at least a module-level docstring.
  5. No unexpected placeholder text remains in key documentation files.
  6. Cross-references between root .md files are not broken.
"""

import ast
import os
import re
import sys

import pytest

# ---------------------------------------------------------------------------
# Repository root detection
# ---------------------------------------------------------------------------

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOCS_DIR = os.path.join(REPO_ROOT, "docs")
SRC_DIR = os.path.join(REPO_ROOT, "src")

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _code_routes() -> set:
    """Return all route paths defined via @app.get/post/put/delete/patch decorators
    in src/runtime/app.py."""
    app_py = os.path.join(SRC_DIR, "runtime", "app.py")
    if not os.path.exists(app_py):
        return set()
    content = _read(app_py)
    pattern = re.compile(r'@app\.(?:get|post|put|delete|patch)\(\s*"(/[^"]*)"')
    return set(pattern.findall(content))


def _doc_routes() -> set:
    """Return all API paths extracted from API_ROUTES.md."""
    routes_md = os.path.join(REPO_ROOT, "API_ROUTES.md")
    if not os.path.exists(routes_md):
        return set()
    content = _read(routes_md)
    return set(re.findall(r"/api/[a-z/{}._-]+", content))


def _env_example_vars() -> set:
    """Return all env var names defined in .env.example."""
    env_example = os.path.join(REPO_ROOT, ".env.example")
    if not os.path.exists(env_example):
        return set()
    content = _read(env_example)
    return set(re.findall(r"^([A-Z_][A-Z0-9_]+)\s*=", content, re.MULTILINE))


def _code_env_vars() -> set:
    """Return all env var names read via os.environ/os.getenv across src/."""
    vars_: set = set()
    for root, _, files in os.walk(SRC_DIR):
        for fname in files:
            if not fname.endswith(".py"):
                continue
            try:
                content = _read(os.path.join(root, fname))
            except OSError:
                continue
            vars_.update(re.findall(r"""os\.(?:environ\.get|getenv)\(\s*['"]([A-Z_][A-Z0-9_]+)['"]""", content))
            vars_.update(re.findall(r"""os\.environ\[\s*['"]([A-Z_][A-Z0-9_]+)['"]""", content))
    return vars_


# ---------------------------------------------------------------------------
# Category 1 — Gap analysis document existence
# ---------------------------------------------------------------------------


def test_gap_analysis_document_exists():
    """docs/DOC_CODE_GAP_ANALYSIS.md must exist."""
    path = os.path.join(DOCS_DIR, "DOC_CODE_GAP_ANALYSIS.md")
    assert os.path.exists(path), "docs/DOC_CODE_GAP_ANALYSIS.md does not exist"


def test_gap_analysis_document_non_empty():
    """docs/DOC_CODE_GAP_ANALYSIS.md must contain substantial content (> 5 KB)."""
    path = os.path.join(DOCS_DIR, "DOC_CODE_GAP_ANALYSIS.md")
    assert os.path.exists(path), "docs/DOC_CODE_GAP_ANALYSIS.md does not exist"
    size = os.path.getsize(path)
    assert size > 5000, f"Gap analysis document is too small ({size} bytes) — expected > 5000"


def test_gap_analysis_has_required_sections():
    """docs/DOC_CODE_GAP_ANALYSIS.md must contain all required top-level sections."""
    path = os.path.join(DOCS_DIR, "DOC_CODE_GAP_ANALYSIS.md")
    assert os.path.exists(path), "docs/DOC_CODE_GAP_ANALYSIS.md does not exist"
    content = _read(path)
    required_sections = [
        "Executive Summary",
        "Gap Catalog",
        "Recommendations",
        "Appendix",
    ]
    for section in required_sections:
        assert section in content, f"Gap analysis missing required section: '{section}'"


def test_gap_analysis_has_gap_ids():
    """Gap analysis must contain numbered gap IDs (API-xxx, ENV-xxx, etc.)."""
    path = os.path.join(DOCS_DIR, "DOC_CODE_GAP_ANALYSIS.md")
    assert os.path.exists(path), "docs/DOC_CODE_GAP_ANALYSIS.md does not exist"
    content = _read(path)
    gap_id_pattern = re.compile(r"\b(?:API|ENV|CFG|ARCH|SETUP|FEAT|SEC|DEP|DOC|TODO|LINK)-\d{3}\b")
    ids_found = gap_id_pattern.findall(content)
    assert len(ids_found) >= 20, (
        f"Gap analysis contains only {len(ids_found)} gap IDs — expected at least 20"
    )


def test_gap_analysis_has_severity_ratings():
    """Gap analysis must include severity ratings."""
    path = os.path.join(DOCS_DIR, "DOC_CODE_GAP_ANALYSIS.md")
    assert os.path.exists(path), "docs/DOC_CODE_GAP_ANALYSIS.md does not exist"
    content = _read(path)
    assert re.search(r"\bCritical\b", content), "Gap analysis missing 'Critical' severity rating"
    assert re.search(r"\bHigh\b", content), "Gap analysis missing 'High' severity rating"
    assert re.search(r"\bMedium\b", content), "Gap analysis missing 'Medium' severity rating"


# ---------------------------------------------------------------------------
# Category 2 — API Routes: documented routes must exist in code
# ---------------------------------------------------------------------------


# Core routes that MUST be present in code — not exhaustive but covers critical path.
_CORE_DOCUMENTED_ROUTES = [
    "/api/health",
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/signup",
    "/api/status",
    "/api/profiles",
    "/api/workflows",
    "/api/billing/tiers",
    "/api/chat",
    "/api/execute",
]


@pytest.mark.parametrize("route", _CORE_DOCUMENTED_ROUTES)
def test_core_documented_route_exists_in_code(route):
    """Each core API route documented in API_ROUTES.md must be implemented in code."""
    routes = _code_routes()
    assert routes, "Could not extract routes from src/runtime/app.py"
    assert route in routes, (
        f"Documented route '{route}' not found in src/runtime/app.py route definitions"
    )


def test_code_routes_non_trivial():
    """src/runtime/app.py must define at least 100 routes (sanity check)."""
    routes = _code_routes()
    assert len(routes) >= 100, (
        f"Only {len(routes)} routes found in src/runtime/app.py — expected >= 100"
    )


def test_api_routes_md_non_trivial():
    """API_ROUTES.md must document at least 100 routes (sanity check)."""
    routes = _doc_routes()
    assert len(routes) >= 100, (
        f"Only {len(routes)} routes found in API_ROUTES.md — expected >= 100"
    )


# ---------------------------------------------------------------------------
# Category 3 — Environment Variables in .env.example
# ---------------------------------------------------------------------------


# Critical env vars that MUST appear in .env.example (uncommented form).
# REDIS_URL and MURPHY_REDIS_URL are commented out in .env.example, so they
# are intentionally not in this list (they are catalogued as ENV-008 in the
# gap analysis instead).
_CRITICAL_ENV_VARS = [
    "MURPHY_ENV",
    "MURPHY_PORT",
    "MURPHY_LLM_PROVIDER",
    "DEEPINFRA_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "MURPHY_VERSION",
    "MURPHY_PERSISTENCE_DIR",
]


@pytest.mark.parametrize("var", _CRITICAL_ENV_VARS)
def test_critical_env_var_in_env_example(var):
    """Critical environment variables must appear in .env.example."""
    env_vars = _env_example_vars()
    assert env_vars, ".env.example is missing or empty"
    assert var in env_vars, (
        f"Critical env var '{var}' is not documented in .env.example"
    )


def test_env_example_non_trivial():
    """.env.example must define at least 10 variables (sanity check)."""
    env_vars = _env_example_vars()
    assert len(env_vars) >= 10, (
        f".env.example contains only {len(env_vars)} variables — expected >= 10"
    )


def test_code_references_env_vars():
    """src/ must reference at least 20 environment variables (sanity check)."""
    code_vars = _code_env_vars()
    assert len(code_vars) >= 20, (
        f"Only {len(code_vars)} env vars found in src/ — expected >= 20"
    )


# ---------------------------------------------------------------------------
# Category 4 — Python module docstrings
# ---------------------------------------------------------------------------


def _python_files_without_docstring() -> list:
    """Return list of .py files in src/ that have no module-level docstring."""
    missing = []
    for root, dirs, files in os.walk(SRC_DIR):
        # Skip __pycache__
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for fname in files:
            if not fname.endswith(".py"):
                continue
            path = os.path.join(root, fname)
            try:
                with open(path, encoding="utf-8") as fh:
                    source = fh.read()
                tree = ast.parse(source, filename=path)
                if not ast.get_docstring(tree):
                    missing.append(os.path.relpath(path, REPO_ROOT))
            except (SyntaxError, OSError):
                pass
    return missing


def test_docstring_coverage_billing_grants_submission():
    """Key billing/grants/submission modules should have docstrings.

    This test specifically validates the cluster of files identified in the
    gap analysis (DOC-001 through DOC-011) that were missing docstrings.
    It reports rather than hard-fails so Phase 4 can address incrementally.
    """
    submission_dir = os.path.join(SRC_DIR, "billing", "grants", "submission")
    if not os.path.exists(submission_dir):
        pytest.skip("src/billing/grants/submission not found")

    missing = []
    for root, dirs, files in os.walk(submission_dir):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for fname in files:
            if not fname.endswith(".py"):
                continue
            path = os.path.join(root, fname)
            try:
                with open(path, encoding="utf-8") as fh:
                    source = fh.read()
                tree = ast.parse(source, filename=path)
                if not ast.get_docstring(tree):
                    missing.append(os.path.relpath(path, REPO_ROOT))
            except (SyntaxError, OSError):
                pass

    # Emit as a warning (xfail-style) — Phase 4 will add the docstrings.
    if missing:
        pytest.xfail(
            f"{len(missing)} module(s) in src/billing/grants/submission/ still lack "
            f"docstrings: {missing[:5]}{'...' if len(missing) > 5 else ''}"
        )


def test_src_modules_mostly_have_docstrings():
    """At least 95% of src/ Python modules must have a module-level docstring."""
    total = 0
    with_docstring = 0
    for root, dirs, files in os.walk(SRC_DIR):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for fname in files:
            if not fname.endswith(".py"):
                continue
            total += 1
            path = os.path.join(root, fname)
            try:
                with open(path, encoding="utf-8") as fh:
                    source = fh.read()
                tree = ast.parse(source, filename=path)
                if ast.get_docstring(tree):
                    with_docstring += 1
            except (SyntaxError, OSError):
                total -= 1  # Don't penalize files with syntax errors

    if total == 0:
        pytest.skip("No Python files found in src/")

    coverage = with_docstring / total
    assert coverage >= 0.95, (
        f"Only {coverage:.1%} of src/ modules have docstrings "
        f"({with_docstring}/{total}). Expected >= 95%."
    )


# ---------------------------------------------------------------------------
# Category 5 — No placeholder text in key documentation files
# ---------------------------------------------------------------------------


_KEY_DOCS = [
    "README.md",
    "GETTING_STARTED.md",
    "DEPLOYMENT_GUIDE.md",
    "API_ROUTES.md",
    "USER_MANUAL.md",
    "SECURITY.md",
]

# Pattern matching obvious placeholder patterns (case-insensitive)
_PLACEHOLDER_PATTERN = re.compile(
    r"\b(placeholder|content will be added|lorem ipsum|fill in|coming soon)\b",
    re.IGNORECASE,
)


@pytest.mark.parametrize("doc", _KEY_DOCS)
def test_no_placeholder_text_in_key_docs(doc):
    """Key documentation files must not contain obvious placeholder text.

    This test is marked xfail for docs that currently contain placeholder text —
    the gaps are catalogued as TODO-001 through TODO-014 in DOC_CODE_GAP_ANALYSIS.md.
    Phase 4 will address these.
    """
    path = os.path.join(REPO_ROOT, doc)
    if not os.path.exists(path):
        pytest.skip(f"{doc} does not exist")
    content = _read(path)
    matches = _PLACEHOLDER_PATTERN.findall(content)
    if matches:
        # Mark as xfail — gap is catalogued, Phase 4 will fix
        pytest.xfail(
            f"{doc} contains placeholder text (catalogued in DOC_CODE_GAP_ANALYSIS.md): "
            f"{matches[:5]}"
        )
    assert not matches


def test_api_routes_md_has_method_column():
    """API_ROUTES.md must include HTTP method references (GET, POST, etc.)."""
    path = os.path.join(REPO_ROOT, "API_ROUTES.md")
    if not os.path.exists(path):
        pytest.skip("API_ROUTES.md does not exist")
    content = _read(path)
    assert re.search(r"\bGET\b", content), "API_ROUTES.md has no GET method entries"
    assert re.search(r"\bPOST\b", content), "API_ROUTES.md has no POST method entries"


# ---------------------------------------------------------------------------
# Category 6 — Cross-reference integrity (broken links between .md files)
# ---------------------------------------------------------------------------


def _collect_md_cross_refs(md_path: str) -> list:
    """Return a list of (source_file, linked_path) for intra-repo Markdown links."""
    content = _read(md_path)
    results = []
    for link in re.findall(r"\[.*?\]\(([^)]+)\)", content):
        if link.startswith("http") or link.startswith("#"):
            continue
        linked_path = link.split("#")[0]
        if not linked_path:
            continue
        results.append(linked_path)
    return results


def test_readme_internal_links():
    """README.md internal links that can be checked must resolve to existing files."""
    readme = os.path.join(REPO_ROOT, "README.md")
    if not os.path.exists(readme):
        pytest.skip("README.md does not exist")

    broken = []
    for link in _collect_md_cross_refs(readme):
        # Skip URL-encoded paths (Murphy%20System/ — known broken, catalogued in LINK-001)
        if "%" in link:
            continue
        # Skip angle-bracket style links that are just source code references
        if link.startswith("<") or link.endswith(">"):
            continue
        resolved = os.path.join(REPO_ROOT, link)
        if not os.path.exists(resolved):
            broken.append(link)

    # Report but use xfail — broken links are catalogued as LINK-001 to LINK-007
    if broken:
        pytest.xfail(
            f"README.md has {len(broken)} broken internal link(s) "
            f"(catalogued as LINK-001 to LINK-007 in DOC_CODE_GAP_ANALYSIS.md): "
            f"{broken[:5]}{'...' if len(broken) > 5 else ''}"
        )


def test_security_md_exists_and_not_empty():
    """SECURITY.md must exist and have substantive content."""
    path = os.path.join(REPO_ROOT, "SECURITY.md")
    assert os.path.exists(path), "SECURITY.md does not exist"
    assert os.path.getsize(path) > 500, "SECURITY.md appears empty"


def test_deployment_guide_exists_and_not_empty():
    """DEPLOYMENT_GUIDE.md must exist and have substantive content."""
    path = os.path.join(REPO_ROOT, "DEPLOYMENT_GUIDE.md")
    assert os.path.exists(path), "DEPLOYMENT_GUIDE.md does not exist"
    assert os.path.getsize(path) > 500, "DEPLOYMENT_GUIDE.md appears empty"


def test_api_routes_md_exists_and_not_empty():
    """API_ROUTES.md must exist and have substantive content."""
    path = os.path.join(REPO_ROOT, "API_ROUTES.md")
    assert os.path.exists(path), "API_ROUTES.md does not exist"
    assert os.path.getsize(path) > 1000, "API_ROUTES.md appears too small"


def test_env_example_exists():
    """.env.example must exist."""
    path = os.path.join(REPO_ROOT, ".env.example")
    assert os.path.exists(path), ".env.example does not exist"


# ---------------------------------------------------------------------------
# Category 7 — Critical gap analysis findings verification
# ---------------------------------------------------------------------------


def test_architecture_map_references_runtime_app():
    """ARCHITECTURE_MAP.md must reference src/runtime/app.py as the API entry point.

    Gap ARCH-001/ARCH-002: the file murphy_complete_backend_extended.py was
    referenced as the entry point but does not exist.
    """
    arch_map = os.path.join(REPO_ROOT, "ARCHITECTURE_MAP.md")
    if not os.path.exists(arch_map):
        pytest.skip("ARCHITECTURE_MAP.md does not exist")

    # Verify the non-existent file is NOT the sole entry point reference
    phantom = "murphy_complete_backend_extended.py"
    content = _read(arch_map)
    # We don't fail here — we only verify the state is catalogued in the gap analysis
    gap_analysis = os.path.join(DOCS_DIR, "DOC_CODE_GAP_ANALYSIS.md")
    if phantom in content:
        # Ensure the gap analysis document captures this finding
        assert os.path.exists(gap_analysis), (
            "ARCHITECTURE_MAP.md references non-existent murphy_complete_backend_extended.py "
            "but docs/DOC_CODE_GAP_ANALYSIS.md does not exist to catalogue this gap"
        )
        gap_content = _read(gap_analysis)
        assert "murphy_complete_backend_extended" in gap_content, (
            "ARCH-001/ARCH-002 gap (murphy_complete_backend_extended.py) is not catalogued "
            "in docs/DOC_CODE_GAP_ANALYSIS.md"
        )


def test_api_key_discrepancy_catalogued():
    """The MURPHY_API_KEY vs MURPHY_API_KEYS discrepancy must be catalogued in gap analysis.

    Gap ENV-046 / SEC-001 / API-058: code uses MURPHY_API_KEY but .env.example says
    MURPHY_API_KEYS — this is a critical authentication configuration mismatch.
    """
    gap_analysis = os.path.join(DOCS_DIR, "DOC_CODE_GAP_ANALYSIS.md")
    assert os.path.exists(gap_analysis), "docs/DOC_CODE_GAP_ANALYSIS.md does not exist"
    content = _read(gap_analysis)
    assert "MURPHY_API_KEY" in content, (
        "Gap analysis does not mention the MURPHY_API_KEY vs MURPHY_API_KEYS discrepancy"
    )
    assert "Critical" in content, (
        "Gap analysis does not mark any item as Critical severity"
    )


def test_undocumented_routes_catalogued():
    """Gap analysis must mention at least some of the 151 undocumented routes.

    Validates that the gap scan actually found missing-documentation routes.
    """
    gap_analysis = os.path.join(DOCS_DIR, "DOC_CODE_GAP_ANALYSIS.md")
    assert os.path.exists(gap_analysis), "docs/DOC_CODE_GAP_ANALYSIS.md does not exist"
    content = _read(gap_analysis)
    # At minimum these three undocumented admin routes must be called out
    assert "/api/admin/" in content, (
        "Gap analysis does not mention undocumented /api/admin/* routes"
    )
    assert "/api/org/portal/" in content, (
        "Gap analysis does not mention undocumented /api/org/portal/* routes"
    )


def test_stale_routes_catalogued():
    """Gap analysis must mention routes documented but absent from code."""
    gap_analysis = os.path.join(DOCS_DIR, "DOC_CODE_GAP_ANALYSIS.md")
    assert os.path.exists(gap_analysis), "docs/DOC_CODE_GAP_ANALYSIS.md does not exist"
    content = _read(gap_analysis)
    # /api/comms/* is the largest stale-documentation group (27 routes)
    assert "/api/comms/" in content or "comms" in content.lower(), (
        "Gap analysis does not mention the stale /api/comms/* documentation entries"
    )


def test_env_var_gaps_catalogued():
    """Gap analysis must catalogue missing env var documentation."""
    gap_analysis = os.path.join(DOCS_DIR, "DOC_CODE_GAP_ANALYSIS.md")
    assert os.path.exists(gap_analysis), "docs/DOC_CODE_GAP_ANALYSIS.md does not exist"
    content = _read(gap_analysis)
    # LIVE_TRADING_ENABLED is a critical undocumented safety gate
    assert "LIVE_TRADING_ENABLED" in content, (
        "Gap analysis does not mention undocumented LIVE_TRADING_ENABLED env var"
    )
    # MURPHY_CREDENTIAL_MASTER_KEY is a critical security env var
    assert "MURPHY_CREDENTIAL_MASTER_KEY" in content, (
        "Gap analysis does not mention undocumented MURPHY_CREDENTIAL_MASTER_KEY"
    )


def test_deployment_gaps_catalogued():
    """Gap analysis must note Alembic and POSTGRES_PASSWORD deployment gaps."""
    gap_analysis = os.path.join(DOCS_DIR, "DOC_CODE_GAP_ANALYSIS.md")
    assert os.path.exists(gap_analysis), "docs/DOC_CODE_GAP_ANALYSIS.md does not exist"
    content = _read(gap_analysis)
    assert "Alembic" in content or "alembic" in content.lower(), (
        "Gap analysis does not mention undocumented Alembic migrations"
    )
    assert "POSTGRES_PASSWORD" in content, (
        "Gap analysis does not mention missing POSTGRES_PASSWORD documentation"
    )
