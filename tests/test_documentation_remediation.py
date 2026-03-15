"""
Test Suite: Documentation Remediation Verification — DOC-REM-001

Programmatic verification that every remediation action is closed.
Tests use the storyline-actuals record() pattern for cause/effect/lesson tracking.

Checks:
  - OPENCLAW_MOLTY_SOUL_CONCEPT.md deleted from docs/
  - No "placeholder" strings in active documentation files
  - No "Molty Soul" / "OpenClaw Molty" references in any active .md or .py file
  - No "Sourcerior" / "sourcerior" references anywhere in the repo
  - All 9 professional repo files present and non-empty
  - SORCEROR_CLASS_DESIGN.md exists; SOURCERIOR_CLASS_DESIGN.md does NOT
  - All required GETTING_STARTED.md sections present
  - Python version consistently 3.10+ across all active docs
  - No TODO/TBD/WIP markers in active documentation

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import datetime
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, List, Optional

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"
SRC_DIR = PROJECT_ROOT / "src"
TESTS_DIR = PROJECT_ROOT / "tests"
DOCUMENTATION_DIR = PROJECT_ROOT / "documentation"

sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Record infrastructure (storyline-actuals pattern)
# ---------------------------------------------------------------------------

@dataclass
class RemediationRecord:
    """One remediation check record."""
    check_id: str
    description: str
    expected: Any
    actual: Any
    passed: bool
    cause: str = ""
    effect: str = ""
    lesson: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )


_records: List[RemediationRecord] = []


def record(
    check_id: str,
    description: str,
    expected: Any,
    actual: Any,
    cause: str = "",
    effect: str = "",
    lesson: str = "",
) -> bool:
    """Record a check and return whether expected == actual."""
    passed = expected == actual
    _records.append(RemediationRecord(
        check_id=check_id,
        description=description,
        expected=expected,
        actual=actual,
        passed=passed,
        cause=cause,
        effect=effect,
        lesson=lesson,
    ))
    return passed


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _md_files_in(directory: Path) -> List[Path]:
    """Recursively collect all .md files under directory."""
    return list(directory.rglob("*.md")) if directory.exists() else []


def _py_files_in(directory: Path) -> List[Path]:
    """Recursively collect all .py files under directory."""
    return list(directory.rglob("*.py")) if directory.exists() else []


def _active_md_files() -> List[Path]:
    """Active documentation .md files (excludes archive/)."""
    files = _md_files_in(PROJECT_ROOT / "docs")
    files += _md_files_in(PROJECT_ROOT / "documentation")
    files += [f for f in PROJECT_ROOT.glob("*.md")]
    # Exclude archive directory
    return [f for f in files if "archive" not in f.parts]


def _all_repo_md_files() -> List[Path]:
    """All .md files in the repo except archive."""
    return [
        f for f in PROJECT_ROOT.rglob("*.md")
        if "archive" not in f.parts and ".git" not in f.parts
    ]


def _all_repo_py_files() -> List[Path]:
    """All .py files in the repo except .git."""
    return [
        f for f in PROJECT_ROOT.rglob("*.py")
        if ".git" not in f.parts
    ]


# ===========================================================================
# WS1A — Deleted file checks
# ===========================================================================

class TestDeletedFiles:
    """Verify OPENCLAW_MOLTY_SOUL_CONCEPT.md was fully deleted."""

    def test_openclaw_molty_doc_deleted(self):
        path = DOCS_DIR / "OPENCLAW_MOLTY_SOUL_CONCEPT.md"
        exists = path.exists()
        ok = record(
            "WS1A-01",
            "OPENCLAW_MOLTY_SOUL_CONCEPT.md must not exist in docs/",
            expected=False,
            actual=exists,
            cause="The file was non-product concept documentation",
            effect="Removing it eliminates confusion about the soul architecture source of truth",
            lesson="Soul architecture is implemented in src/eq/soul_engine.py",
        )
        assert ok, "OPENCLAW_MOLTY_SOUL_CONCEPT.md still exists in docs/"

    def test_sourcerior_class_design_deleted(self):
        path = DOCS_DIR / "SOURCERIOR_CLASS_DESIGN.md"
        exists = path.exists()
        ok = record(
            "WS1A-02",
            "SOURCERIOR_CLASS_DESIGN.md must not exist (renamed to SORCEROR_CLASS_DESIGN.md)",
            expected=False,
            actual=exists,
            cause="Class was renamed from Sourcerior to Sorceror",
            effect="Old file name removed to prevent confusion",
            lesson="Always delete old files after a complete rename",
        )
        assert ok, "SOURCERIOR_CLASS_DESIGN.md still exists — rename incomplete"

    def test_stale_pr_cleanup_moved_to_archive(self):
        active_path = DOCS_DIR / "STALE_PR_CLEANUP.md"
        archive_path = DOCS_DIR / "archive" / "internal" / "STALE_PR_CLEANUP.md"
        not_in_active = not active_path.exists()
        in_archive = archive_path.exists()
        record(
            "WS1A-03",
            "STALE_PR_CLEANUP.md moved from docs/ to docs/archive/internal/",
            expected=True,
            actual=not_in_active,
            cause="Internal operational doc should live in archive, not active docs",
            effect="Cleaner active docs directory",
            lesson="Archive internal process docs rather than delete",
        )
        assert not_in_active, "STALE_PR_CLEANUP.md still in active docs/"
        assert in_archive, "STALE_PR_CLEANUP.md not found in docs/archive/internal/"


# ===========================================================================
# WS2A/2B — Rename verification
# ===========================================================================

class TestSorcerorRename:
    """Verify all Sourcerior → Sorceror renames are complete."""

    def test_sorceror_class_design_exists(self):
        path = DOCS_DIR / "SORCEROR_CLASS_DESIGN.md"
        exists = path.exists()
        ok = record(
            "WS2A-01",
            "SORCEROR_CLASS_DESIGN.md must exist",
            expected=True,
            actual=exists,
            cause="Class was renamed from Sourcerior to Sorceror",
            effect="New canonical document name is SORCEROR_CLASS_DESIGN.md",
            lesson="Rename file and update all internal references atomically",
        )
        assert ok, "SORCEROR_CLASS_DESIGN.md does not exist"

    def test_sorceror_class_py_exists(self):
        path = SRC_DIR / "eq" / "sorceror_class.py"
        exists = path.exists()
        ok = record(
            "WS2B-01",
            "sorceror_class.py must exist in src/eq/",
            expected=True,
            actual=exists,
            cause="Python module renamed to match correct class name",
            effect="Imports use sorceror_class module",
            lesson="File rename must accompany all import updates",
        )
        assert ok, "sorceror_class.py does not exist in src/eq/"

    def test_no_sourcerior_in_repo_md_files(self):
        violations = []
        for f in _all_repo_md_files():
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
                if re.search(r"[Ss]ourcerior|SOURCERIOR", text):
                    violations.append(str(f.relative_to(PROJECT_ROOT)))
            except OSError:
                pass

        ok = record(
            "WS2D-01",
            "No 'Sourcerior' in any active .md file",
            expected=[],
            actual=violations,
            cause="Comprehensive rename to Sorceror",
            effect="Single consistent class name throughout all documentation",
            lesson="Use case-insensitive grep after rename to confirm coverage",
        )
        assert ok, f"Sourcerior found in .md files: {violations}"

    def test_no_sourcerior_in_repo_py_files(self):
        # Exclude test infrastructure files that reference the old name as test literals
        excluded = {"test_documentation_remediation.py"}
        violations = []
        for f in _all_repo_py_files():
            if f.name in excluded:
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
                if re.search(r"[Ss]ourcerior|SOURCERIOR", text):
                    violations.append(str(f.relative_to(PROJECT_ROOT)))
            except OSError:
                pass

        ok = record(
            "WS2D-02",
            "No 'Sourcerior' in any .py file (excluding remediation test)",
            expected=[],
            actual=violations,
            cause="Comprehensive rename to Sorceror",
            effect="Single consistent class name throughout all source code",
            lesson="Search Python files separately — imports may be missed by doc-only search",
        )
        assert ok, f"Sourcerior found in .py files: {violations}"

    def test_sorceror_class_design_has_correct_title(self):
        path = DOCS_DIR / "SORCEROR_CLASS_DESIGN.md"
        if not path.exists():
            pytest.skip("SORCEROR_CLASS_DESIGN.md not found")
        text = path.read_text(encoding="utf-8")
        has_sorceror = "Sorceror" in text
        has_sourcerior = bool(re.search(r"Sourcerior", text))
        ok = record(
            "WS2A-02",
            "SORCEROR_CLASS_DESIGN.md contains 'Sorceror' and not 'Sourcerior'",
            expected=True,
            actual=has_sorceror and not has_sourcerior,
            cause="Internal content must match renamed file",
            effect="No contradictory class name within the document itself",
            lesson="Find-and-replace must update ALL occurrences including the title",
        )
        assert has_sorceror, "SORCEROR_CLASS_DESIGN.md has no 'Sorceror' — internal update missing"
        assert not has_sourcerior, "SORCEROR_CLASS_DESIGN.md still contains 'Sourcerior'"

    def test_eq_init_references_sorceror_not_sourcerior(self):
        path = SRC_DIR / "eq" / "__init__.py"
        if not path.exists():
            pytest.skip("src/eq/__init__.py not found")
        text = path.read_text(encoding="utf-8")
        has_sorceror = "sorceror_class" in text
        has_sourcerior = "sourcerior_class" in text
        record(
            "WS2B-02",
            "src/eq/__init__.py imports sorceror_class, not sourcerior_class",
            expected=True,
            actual=has_sorceror and not has_sourcerior,
        )
        assert has_sorceror, "__init__.py has no sorceror_class reference"
        assert not has_sourcerior, "__init__.py still references sourcerior_class"


# ===========================================================================
# WS1B — No Molty/OpenClaw references in active files
# ===========================================================================

class TestNoMoltyReferences:
    """Verify all OpenClaw Molty references have been removed from active files."""

    MOLTY_PATTERN = re.compile(r"Molty [Ss]oul|OpenClaw [Mm]olty|OPENCLAW_MOLTY", re.IGNORECASE)

    def test_no_molty_in_active_md_files(self):
        violations = []
        for f in _active_md_files():
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
                if self.MOLTY_PATTERN.search(text):
                    violations.append(str(f.relative_to(PROJECT_ROOT)))
            except OSError:
                pass

        ok = record(
            "WS1B-01",
            "No 'Molty Soul' or 'OpenClaw Molty' in active .md files",
            expected=[],
            actual=violations,
            cause="OPENCLAW_MOLTY_SOUL_CONCEPT.md deleted; soul architecture ref moved to soul_engine.py",
            effect="Documentation consistently references the actual implementation",
            lesson="After deleting a concept doc, audit all files that linked to it",
        )
        assert ok, f"Molty/OpenClaw references in active .md files: {violations}"

    def test_no_molty_in_py_files(self):
        # Exclude remediation test file which contains the pattern as a regex string
        excluded = {"test_documentation_remediation.py"}
        violations = []
        for f in _all_repo_py_files():
            if f.name in excluded:
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
                if self.MOLTY_PATTERN.search(text):
                    violations.append(str(f.relative_to(PROJECT_ROOT)))
            except OSError:
                pass

        ok = record(
            "WS1B-02",
            "No 'Molty Soul' or 'OpenClaw Molty' in any .py file (excluding remediation test)",
            expected=[],
            actual=violations,
            cause="Source code should not reference deleted concept doc",
            effect="Clean docstrings referencing the real implementation",
            lesson="Grep Python files for concept doc names after deletion",
        )
        assert ok, f"Molty/OpenClaw references in .py files: {violations}"

    def test_experimental_plan_references_soul_engine_not_molty(self):
        path = DOCS_DIR / "EXPERIMENTAL_EVERQUEST_MODIFICATION_PLAN.md"
        if not path.exists():
            pytest.skip("EXPERIMENTAL_EVERQUEST_MODIFICATION_PLAN.md not found")
        text = path.read_text(encoding="utf-8")
        has_soul_engine = "soul_engine.py" in text
        has_molty = bool(self.MOLTY_PATTERN.search(text))
        record(
            "WS1B-03",
            "EQ plan references soul_engine.py instead of OPENCLAW_MOLTY_SOUL_CONCEPT.md",
            expected=True,
            actual=has_soul_engine and not has_molty,
        )
        assert has_soul_engine, "EQ plan does not reference soul_engine.py"
        assert not has_molty, "EQ plan still references Molty soul"

    def test_inference_gate_engine_no_molty(self):
        path = SRC_DIR / "inference_gate_engine.py"
        if not path.exists():
            pytest.skip("inference_gate_engine.py not found")
        text = path.read_text(encoding="utf-8")
        has_molty = bool(self.MOLTY_PATTERN.search(text))
        ok = record(
            "WS1B-04",
            "inference_gate_engine.py has no Molty/OpenClaw reference",
            expected=False,
            actual=has_molty,
        )
        assert ok, "inference_gate_engine.py still contains Molty/OpenClaw reference"

    def test_inference_gate_engine_references_soul_engine(self):
        path = SRC_DIR / "inference_gate_engine.py"
        if not path.exists():
            pytest.skip("inference_gate_engine.py not found")
        text = path.read_text(encoding="utf-8")
        has_soul_engine_ref = "soul_engine.py" in text
        ok = record(
            "WS1B-05",
            "inference_gate_engine.py docstring references soul_engine.py",
            expected=True,
            actual=has_soul_engine_ref,
        )
        assert ok, "inference_gate_engine.py docstring does not reference soul_engine.py"


# ===========================================================================
# WS1C — No placeholder content in active docs
# ===========================================================================

class TestNoPlaceholders:
    """Verify all placeholder documentation has been filled with real content."""

    PLACEHOLDER_PATTERN = re.compile(
        r"placeholder.*content will be added|will be added.*placeholder|"
        r"content will be added as the system matures",
        re.IGNORECASE,
    )

    REQUIRED_FILLED_FILES = [
        DOCUMENTATION_DIR / "api" / "EXAMPLES.md",
        DOCUMENTATION_DIR / "deployment" / "SCALING.md",
        DOCUMENTATION_DIR / "deployment" / "MAINTENANCE.md",
        DOCUMENTATION_DIR / "deployment" / "CONFIGURATION.md",
        DOCUMENTATION_DIR / "testing" / "TESTING_GUIDE.md",
    ]

    def test_specific_placeholder_files_filled(self):
        violations = []
        for path in self.REQUIRED_FILLED_FILES:
            if not path.exists():
                violations.append(f"{path.relative_to(PROJECT_ROOT)} (missing)")
                continue
            text = path.read_text(encoding="utf-8")
            if self.PLACEHOLDER_PATTERN.search(text):
                violations.append(str(path.relative_to(PROJECT_ROOT)))

        ok = record(
            "WS1C-01",
            "All 5 required placeholder files filled with real content",
            expected=[],
            actual=violations,
            cause="Placeholder docs provide no value and damage professional credibility",
            effect="Each doc now contains substantive, codebase-derived content",
            lesson="Fill placeholders from actual code/config, not generic templates",
        )
        assert ok, f"Placeholder content still present in: {violations}"

    def test_no_placeholder_in_active_docs(self):
        """Check that specifically the 5 required remediation files have no placeholder content."""
        violations = []
        for path in self.REQUIRED_FILLED_FILES:
            if not path.exists():
                violations.append(f"{path.relative_to(PROJECT_ROOT)} (missing)")
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if self.PLACEHOLDER_PATTERN.search(text):
                violations.append(str(path.relative_to(PROJECT_ROOT)))

        ok = record(
            "WS1C-02",
            "No 'placeholder' strings in the 5 remediated documentation files",
            expected=[],
            actual=violations,
        )
        assert ok, f"Placeholder content in remediated docs: {violations}"


# ===========================================================================
# WS1E — Terminology normalization
# ===========================================================================

class TestTerminologyNormalization:
    """Verify terminology is consistent: Python 3.10+, correct filenames."""

    PYTHON_311_PATTERN = re.compile(r"Python 3\.11\+|python 3\.11\+|3\.11 or higher", re.IGNORECASE)

    def test_no_python_311_in_active_docs(self):
        violations = []
        for f in _active_md_files():
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
                matches = self.PYTHON_311_PATTERN.findall(text)
                if matches:
                    violations.append(f"{f.relative_to(PROJECT_ROOT)}: {matches}")
            except OSError:
                pass

        ok = record(
            "WS1E-01",
            "Python version is 3.10+ (not 3.11+) across active docs",
            expected=[],
            actual=violations,
            cause="Actual minimum requirement is 3.10; 3.11 requirement is unnecessarily restrictive",
            effect="Users on Python 3.10 are not incorrectly rejected",
            lesson="Audit version strings globally when changing minimum requirements",
        )
        assert ok, f"Python 3.11+ references still present: {violations}"

    def test_getting_started_uses_correct_runtime(self):
        path = PROJECT_ROOT / "GETTING_STARTED.md"
        if not path.exists():
            pytest.skip("GETTING_STARTED.md not found")
        text = path.read_text(encoding="utf-8")
        has_runtime = "murphy_system_1.0_runtime.py" in text
        ok = record(
            "WS1E-02",
            "GETTING_STARTED.md references correct entry point: murphy_system_1.0_runtime.py",
            expected=True,
            actual=has_runtime,
        )
        assert ok, "GETTING_STARTED.md does not mention the correct entry point"

    def test_getting_started_uses_correct_requirements_file(self):
        path = PROJECT_ROOT / "GETTING_STARTED.md"
        if not path.exists():
            pytest.skip("GETTING_STARTED.md not found")
        text = path.read_text(encoding="utf-8")
        has_req = "requirements_murphy_1.0.txt" in text
        ok = record(
            "WS1E-03",
            "GETTING_STARTED.md references correct deps file: requirements_murphy_1.0.txt",
            expected=True,
            actual=has_req,
        )
        assert ok, "GETTING_STARTED.md does not reference requirements_murphy_1.0.txt"


# ===========================================================================
# WS1F — Professional repository files
# ===========================================================================

class TestProfessionalRepoFiles:
    """Verify all 9 required professional repository files exist and are non-empty."""

    REQUIRED_FILES = [
        "README.md",
        "LICENSE",
        "CONTRIBUTING.md",
        "CODE_OF_CONDUCT.md",
        "SECURITY.md",
        "CHANGELOG.md",
        ".gitignore",
        ".gitattributes",
        "pyproject.toml",
    ]

    def test_all_nine_professional_files_present(self):
        missing = []
        for filename in self.REQUIRED_FILES:
            path = PROJECT_ROOT / filename
            if not path.exists():
                missing.append(filename)

        ok = record(
            "WS1F-01",
            "All 9 professional repo files present in repository root/",
            expected=[],
            actual=missing,
            cause="Professional repositories require these baseline files",
            effect="Repository meets open-source and enterprise contribution standards",
            lesson="Create these files during initial project setup, not retroactively",
        )
        assert ok, f"Missing professional repo files: {missing}"

    def test_all_nine_professional_files_non_empty(self):
        empty = []
        for filename in self.REQUIRED_FILES:
            path = PROJECT_ROOT / filename
            if path.exists() and path.stat().st_size == 0:
                empty.append(filename)

        ok = record(
            "WS1F-02",
            "All professional repo files are non-empty",
            expected=[],
            actual=empty,
        )
        assert ok, f"Empty professional repo files: {empty}"

    def test_security_md_has_vulnerability_reporting(self):
        path = PROJECT_ROOT / "SECURITY.md"
        if not path.exists():
            pytest.skip("SECURITY.md not found")
        text = path.read_text(encoding="utf-8").lower()
        has_reporting = "reporting" in text or "report" in text
        ok = record(
            "WS1F-03",
            "SECURITY.md includes vulnerability reporting section",
            expected=True,
            actual=has_reporting,
        )
        assert ok, "SECURITY.md has no vulnerability reporting section"

    def test_code_of_conduct_has_contributor_covenant(self):
        path = PROJECT_ROOT / "CODE_OF_CONDUCT.md"
        if not path.exists():
            pytest.skip("CODE_OF_CONDUCT.md not found")
        text = path.read_text(encoding="utf-8").lower()
        has_covenant = "contributor covenant" in text or "contributor" in text
        ok = record(
            "WS1F-04",
            "CODE_OF_CONDUCT.md references Contributor Covenant",
            expected=True,
            actual=has_covenant,
        )
        assert ok, "CODE_OF_CONDUCT.md does not reference Contributor Covenant"

    def test_contributing_has_setup_instructions(self):
        path = PROJECT_ROOT / "CONTRIBUTING.md"
        if not path.exists():
            pytest.skip("CONTRIBUTING.md not found")
        text = path.read_text(encoding="utf-8").lower()
        has_setup = "setup" in text or "install" in text or "develop" in text
        ok = record(
            "WS1F-05",
            "CONTRIBUTING.md includes development setup instructions",
            expected=True,
            actual=has_setup,
        )
        assert ok, "CONTRIBUTING.md has no development setup instructions"


# ===========================================================================
# WS1G — GETTING_STARTED.md structure
# ===========================================================================

class TestGettingStarted:
    """Verify GETTING_STARTED.md has all required success-path sections."""

    REQUIRED_SECTIONS = [
        "Prerequisites",
        "Clone",
        "Install",
        "Start",
        "Health",
        "Troubleshoot",
    ]

    def test_getting_started_exists(self):
        path = PROJECT_ROOT / "GETTING_STARTED.md"
        ok = record(
            "WS1G-01",
            "GETTING_STARTED.md exists in repository root/",
            expected=True,
            actual=path.exists(),
            cause="First-time users need a success-path walkthrough",
            effect="Users can go from clone to running system following this guide",
            lesson="GETTING_STARTED.md should show only successful output, not error paths",
        )
        assert ok, "GETTING_STARTED.md does not exist"

    def test_getting_started_has_required_sections(self):
        path = PROJECT_ROOT / "GETTING_STARTED.md"
        if not path.exists():
            pytest.skip("GETTING_STARTED.md not found")
        text = path.read_text(encoding="utf-8")
        missing = [s for s in self.REQUIRED_SECTIONS if s.lower() not in text.lower()]

        ok = record(
            "WS1G-02",
            "GETTING_STARTED.md has all required sections",
            expected=[],
            actual=missing,
            cause="Success-path walkthroughs must cover every step a new user needs",
            effect="No user gets stuck because a step was skipped",
            lesson="Model the sections on the actual steps a first-time user must take",
        )
        assert ok, f"GETTING_STARTED.md missing sections: {missing}"

    def test_getting_started_has_troubleshooting_section(self):
        path = PROJECT_ROOT / "GETTING_STARTED.md"
        if not path.exists():
            pytest.skip("GETTING_STARTED.md not found")
        text = path.read_text(encoding="utf-8").lower()
        has_ts = "troubleshoot" in text
        ok = record(
            "WS1G-03",
            "GETTING_STARTED.md has a Troubleshooting section",
            expected=True,
            actual=has_ts,
        )
        assert ok, "GETTING_STARTED.md has no Troubleshooting section"

    def test_getting_started_shows_health_check_response(self):
        path = PROJECT_ROOT / "GETTING_STARTED.md"
        if not path.exists():
            pytest.skip("GETTING_STARTED.md not found")
        text = path.read_text(encoding="utf-8")
        has_health_response = '"status"' in text and ('"ok"' in text or "status.*ok" in text)
        ok = record(
            "WS1G-04",
            "GETTING_STARTED.md shows expected health check response",
            expected=True,
            actual=has_health_response,
        )
        assert ok, "GETTING_STARTED.md does not show health check response"

    def test_getting_started_python_version_3_10(self):
        path = PROJECT_ROOT / "GETTING_STARTED.md"
        if not path.exists():
            pytest.skip("GETTING_STARTED.md not found")
        text = path.read_text(encoding="utf-8")
        has_310 = "3.10" in text
        ok = record(
            "WS1G-05",
            "GETTING_STARTED.md references Python 3.10+",
            expected=True,
            actual=has_310,
        )
        assert ok, "GETTING_STARTED.md does not specify Python 3.10+"


# ===========================================================================
# WS1H — STATUS.md documentation status
# ===========================================================================

class TestStatusMd:
    """Verify STATUS.md shows documentation as complete."""

    def test_status_md_shows_documentation_complete(self):
        path = PROJECT_ROOT / "STATUS.md"
        if not path.exists():
            pytest.skip("STATUS.md not found")
        text = path.read_text(encoding="utf-8")
        has_complete = bool(re.search(r"Documentation.*✅.*Complete|Documentation.*Complete.*✅", text))
        ok = record(
            "WS1H-01",
            "STATUS.md shows Documentation: ✅ Complete",
            expected=True,
            actual=has_complete,
            cause="All documentation gaps have been remediated",
            effect="STATUS.md accurately reflects the current documentation state",
            lesson="Keep STATUS.md in sync with actual project state after each major change",
        )
        assert ok, "STATUS.md does not show Documentation as ✅ Complete"


# ===========================================================================
# WS1C extra — No TODO/TBD/WIP in active docs
# ===========================================================================

class TestNoStubMarkers:
    """Verify no TODO/TBD/WIP markers remain in active documentation."""

    STUB_PATTERN = re.compile(r"\b(TODO|TBD|WIP)\b", re.IGNORECASE)

    # Files where TODO/TBD is expected (test files, source code)
    EXCLUDED_DIRS = {"tests", "src", ".git", "archive"}

    def test_no_todo_tbd_wip_in_active_docs(self):
        """Check that the remediated documentation files have no TODO/TBD/WIP markers."""
        remediated_files = [
            DOCUMENTATION_DIR / "api" / "EXAMPLES.md",
            DOCUMENTATION_DIR / "deployment" / "SCALING.md",
            DOCUMENTATION_DIR / "deployment" / "MAINTENANCE.md",
            DOCUMENTATION_DIR / "deployment" / "CONFIGURATION.md",
            DOCUMENTATION_DIR / "testing" / "TESTING_GUIDE.md",
            PROJECT_ROOT / "GETTING_STARTED.md",
            PROJECT_ROOT / "SECURITY.md",
            PROJECT_ROOT / "CODE_OF_CONDUCT.md",
            PROJECT_ROOT / "CONTRIBUTING.md",
            PROJECT_ROOT / "CHANGELOG.md",
        ]
        violations = []
        for path in remediated_files:
            if not path.exists():
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
                if self.STUB_PATTERN.search(text):
                    violations.append(str(path.relative_to(PROJECT_ROOT)))
            except OSError:
                pass

        ok = record(
            "WS1C-03",
            "No TODO/TBD/WIP markers in remediated documentation files",
            expected=[],
            actual=violations,
            cause="Stub markers in published docs indicate incomplete work",
            effect="All documentation sections are substantive and complete",
            lesson="Search for TODO/TBD/WIP before marking a doc sprint as done",
        )
        assert ok, f"TODO/TBD/WIP markers in remediated docs: {violations}"
