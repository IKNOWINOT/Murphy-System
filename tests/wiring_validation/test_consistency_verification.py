"""
Murphy System — Consistency Verification Tests

Validates that all claims in MODULE_CATALOG, README, and FULL_SYSTEM_ASSESSMENT
are consistent with actual source files, test files, and runtime behavior.
"""
import os
import re
import sys
import unittest

# Resolve project root
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)


def _load_runtime_source():
    """Load the full runtime source (wrapper + refactored modules).

    After INC-13, the monolithic runtime was split into:
      - murphy_system_1.0_runtime.py  (thin wrapper)
      - src/runtime/_deps.py          (imports & MODULE_CATALOG)
      - src/runtime/app.py            (FastAPI routes)
      - src/runtime/murphy_system_core.py (MurphySystem class)
    All four are concatenated for tests that grep the source.
    """
    parts: list[str] = []
    for rel in (
        "murphy_system_1.0_runtime.py",
        os.path.join("src", "runtime", "_deps.py"),
        os.path.join("src", "runtime", "app.py"),
        os.path.join("src", "runtime", "murphy_system_core.py"),
    ):
        path = os.path.join(ROOT, rel)
        if os.path.isfile(path):
            try:
                with open(path, "r") as f:
                    parts.append(f.read())
            except (OSError, UnicodeDecodeError):
                pass
    return "\n".join(parts)


def _extract_catalog_entries(source):
    """Extract MODULE_CATALOG entries as list of dicts."""
    entries = []
    for m in re.finditer(
        r'\{\s*"name":\s*"([^"]+)",\s*"path":\s*"([^"]+)"', source
    ):
        entries.append({"name": m.group(1), "path": m.group(2)})
    return entries


class TestModuleCatalogConsistency(unittest.TestCase):
    """Verify MODULE_CATALOG entries map to real source files."""

    @classmethod
    def setUpClass(cls):
        cls.source = _load_runtime_source()
        cls.catalog = _extract_catalog_entries(cls.source)
        # Known external modules that are try/except imported
        cls.EXTERNAL_MODULES = {
            "universal_control_plane",
            "inoni_business_automation",
            "two_phase_orchestrator",
        }

    def test_catalog_has_entries(self):
        """MODULE_CATALOG should have at least 75 entries."""
        self.assertGreaterEqual(len(self.catalog), 75)

    def test_catalog_names_unique(self):
        """All MODULE_CATALOG names must be unique."""
        names = [e["name"] for e in self.catalog]
        self.assertEqual(len(names), len(set(names)), f"Duplicate names: {[n for n in names if names.count(n) > 1]}")

    def test_internal_modules_resolve(self):
        """All non-external MODULE_CATALOG paths resolve to files or directories."""
        missing = []
        for entry in self.catalog:
            if entry["name"] in self.EXTERNAL_MODULES:
                continue
            path = entry["path"]
            parts = path.split(".")
            file_path = os.path.join(ROOT, *parts) + ".py"
            dir_path = os.path.join(ROOT, *parts)
            if not os.path.exists(file_path) and not os.path.isdir(dir_path):
                missing.append(f"{entry['name']} -> {path}")
        self.assertEqual(
            missing, [],
            f"MODULE_CATALOG entries without matching source: {missing}"
        )

    def test_external_modules_have_try_except(self):
        """External modules must be wrapped in try/except ImportError."""
        for name in self.EXTERNAL_MODULES:
            self.assertIn(
                f"except ImportError",
                self.source,
                f"External module {name} should have try/except ImportError guard"
            )


class TestSourceTestCoverage(unittest.TestCase):
    """Verify src/ modules have corresponding test files."""

    @classmethod
    def setUpClass(cls):
        cls.src_dir = os.path.join(ROOT, "src")
        cls.test_dir = os.path.join(ROOT, "tests")
        cls.src_modules = set()
        for f in os.listdir(cls.src_dir):
            if f.endswith(".py") and f != "__init__.py":
                cls.src_modules.add(f.replace(".py", ""))
            elif os.path.isdir(os.path.join(cls.src_dir, f)) and f != "__pycache__":
                cls.src_modules.add(f)

        cls.test_files = set()
        for dirpath, _, filenames in os.walk(cls.test_dir):
            for f in filenames:
                if f.startswith("test_") and f.endswith(".py"):
                    cls.test_files.add(os.path.join(dirpath, f))

    def test_critical_modules_have_tests(self):
        """Critical modules must have at least one test file referencing them."""
        critical = [
            "ml_strategy_engine",
            "building_automation_connectors",
            "energy_management_connectors",
            "manufacturing_automation_standards",
            "digital_asset_generator",
            "rosetta_stone_heartbeat",
            "content_creator_platform_modulator",
            "platform_connector_framework",
            "enterprise_integrations",
            "executive_planning_engine",
            "agentic_api_provisioner",
            "video_streaming_connector",
            "remote_access_connector",
            "ui_testing_framework",
        ]
        missing_tests = []
        for mod in critical:
            # Check if any test file references this module
            found = False
            for tf in self.test_files:
                with open(tf, "r") as fh:
                    if mod in fh.read():
                        found = True
                        break
            if not found:
                missing_tests.append(mod)
        self.assertEqual(
            missing_tests, [],
            f"Critical modules without test coverage: {missing_tests}"
        )


class TestSecurityConsistency(unittest.TestCase):
    """Verify security hardening claims are backed by actual code."""

    @classmethod
    def setUpClass(cls):
        cls.security_dir = os.path.join(ROOT, "src", "security_plane")

    def test_security_plane_exists(self):
        """Security plane directory must exist."""
        self.assertTrue(os.path.isdir(self.security_dir))

    def test_security_modules_present(self):
        """Core security modules must exist."""
        required = [
            "access_control.py",
            "authentication.py",
            "cryptography.py",
            "hardening.py",
            "middleware.py",
        ]
        for mod in required:
            self.assertTrue(
                os.path.exists(os.path.join(self.security_dir, mod)),
                f"Security module missing: {mod}"
            )

    def test_input_validation_exists(self):
        """Input validation module must exist."""
        self.assertTrue(
            os.path.exists(os.path.join(ROOT, "src", "input_validation.py"))
        )


class TestDocumentationConsistency(unittest.TestCase):
    """Verify doc claims match actual state."""

    @classmethod
    def setUpClass(cls):
        cls.readme_path = os.path.join(ROOT, "README.md")
        cls.assessment_path = os.path.join(ROOT, "archive", "murphy_integrated_archive", "FULL_SYSTEM_ASSESSMENT.md")
        cls.source = _load_runtime_source()
        cls.catalog = _extract_catalog_entries(cls.source)

    def test_readme_exists(self):
        """Root README.md must exist."""
        self.assertTrue(os.path.exists(self.readme_path))

    def test_assessment_exists(self):
        """FULL_SYSTEM_ASSESSMENT.md must exist (or archive is moved)."""
        if not os.path.isdir(os.path.join(ROOT, "archive")):
            # Archive was moved to external repository
            # (https://github.com/IKNOWINOT/murphy-system-archive)
            self.skipTest("archive directory moved to external repository")
        self.assertTrue(os.path.exists(self.assessment_path))

    def test_catalog_count_matches_docs(self):
        """MODULE_CATALOG count should be ≥75 as documented."""
        self.assertGreaterEqual(len(self.catalog), 75)


class TestHTMLUIConsistency(unittest.TestCase):
    """Verify all terminal HTML files use the neon terminal theme."""

    NEON_INDICATORS = [
        "#00ff41", "#0a0a0a", "monospace",
        "murphy-design-system.css",  # shared design system provides neon styling
        "murphy-theme.css",          # legacy theme file with neon colors
    ]

    # Legacy redirect files that forward to a neon-themed page
    LEGACY_REDIRECTS = {"murphy_ui_integrated.html", "murphy_ui_integrated_terminal.html"}

    # Standalone marketing / campaign pages that intentionally use their own
    # visual identity and are NOT part of the Murphy terminal UI.
    # PROD-HARD-UI-001: exempted from neon-theme enforcement.
    NON_APP_PAGES = {
        "stevewiki.html",        # Wikipedia-parody campaign page (own theme)
        "voteforsteve2028.html", # Campaign page (own theme)
        "steve2028merch.html",   # Merch page (own theme)
        "murphy_landing_page.html",  # Public marketing landing (own theme)
        "blog.html",             # Public blog (own theme)
        "careers.html",          # Public careers page (own theme)
        "legal.html",            # Public legal page (own theme)
        "financing_options.html",# Public financing page (own theme)
        "guest_portal.html",     # Guest portal (own theme)
    }

    @classmethod
    def setUpClass(cls):
        cls.html_files = []
        for f in os.listdir(ROOT):
            if f.endswith(".html"):
                cls.html_files.append(os.path.join(ROOT, f))

    def test_all_html_files_exist(self):
        """At least 5 HTML terminal files should exist."""
        self.assertGreaterEqual(len(self.html_files), 5)

    def test_neon_theme_consistency(self):
        """All terminal HTML files should use neon terminal styling."""
        non_neon = []
        for fp in self.html_files:
            basename = os.path.basename(fp)
            if basename in self.LEGACY_REDIRECTS or basename in self.NON_APP_PAGES:
                continue  # redirect stubs and standalone marketing pages use their own themes
            with open(fp, "r") as f:
                content = f.read()
            if not any(ind in content for ind in self.NEON_INDICATORS):
                non_neon.append(basename)
        self.assertEqual(
            non_neon, [],
            f"HTML files not using neon theme: {non_neon}"
        )


class TestLicenseOwnership(unittest.TestCase):
    """Verify ownership attribution to Corey Post / InonI LLC."""

    def test_runtime_copyright(self):
        """Runtime file must reference Inoni."""
        source = _load_runtime_source()
        self.assertTrue(
            "Inoni" in source or "Corey Post" in source,
            "Runtime must reference Inoni or Corey Post"
        )

    def test_license_file_exists(self):
        """LICENSE file should exist."""
        license_path = os.path.join(ROOT, "LICENSE")
        self.assertTrue(os.path.exists(license_path))


if __name__ == "__main__":
    unittest.main()
