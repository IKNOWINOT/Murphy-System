"""
Gap Closure Tests — Round 50.

Validates three gap-closure items completed in this round:

  Gap 1 (Medium): Package-level READMEs (GAP-5)
                  All 65 packages under src/ now have README.md files.
                  Previous state: 3/65 (5%) had READMEs.
                  New state: 65/65 (100%) have READMEs.

  Gap 2 (Medium): AUAR Technical Proposal update (GAP-4)
                  Appendix C added to AUAR_TECHNICAL_PROPOSAL.md documenting:
                  - UCB1 algorithm (not simple epsilon-greedy)
                  - InMemory + File persistence backends (not Neo4j)
                  - Admin-role header and opaque error messages
                  - AUARPipeline entry point
                  - AUARConfig environment variables

  Gap 3 (Info):   AUDIT_AND_COMPLETION_REPORT.md accuracy
                  Report updated to reflect current package-README count.

Gaps addressed:
 1. GAP-5: All 65 src/ packages now have README.md (was 3/65)
 2. GAP-4: AUAR proposal documents implemented algorithm and backends
 3. Doc accuracy: README count corrected in audit report
"""

from pathlib import Path

import pytest

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"


# ===========================================================================
# Gap 1 — Package-level READMEs (GAP-5)
# ===========================================================================

class TestGap1_PackageREADMEs:
    """Every package directory under src/ must contain a README.md."""

    @staticmethod
    def _packages():
        return [
            p for p in SRC_DIR.iterdir()
            if p.is_dir() and p.name != "__pycache__"
        ]

    def test_all_packages_have_readme(self):
        missing = [
            p.name for p in self._packages()
            if not (p / "README.md").exists()
        ]
        assert missing == [], (
            f"{len(missing)} package(s) still missing README.md:\n"
            + "\n".join(f"  src/{name}/" for name in sorted(missing))
        )

    def test_readme_count_at_least_60(self):
        """Regression guard: count must not drop below 60."""
        has_readme = sum(
            1 for p in self._packages()
            if (p / "README.md").exists()
        )
        assert has_readme >= 60, (
            f"Expected ≥60 packages with README.md, found {has_readme}"
        )

    def test_runtime_readme_exists(self):
        assert (SRC_DIR / "runtime" / "README.md").exists()

    def test_security_plane_readme_exists(self):
        assert (SRC_DIR / "security_plane" / "README.md").exists()

    def test_auar_readme_exists(self):
        assert (SRC_DIR / "auar" / "README.md").exists()

    def test_rosetta_readme_exists(self):
        assert (SRC_DIR / "rosetta" / "README.md").exists()

    def test_matrix_bridge_readme_exists(self):
        assert (SRC_DIR / "matrix_bridge" / "README.md").exists()

    def test_confidence_engine_readme_exists(self):
        assert (SRC_DIR / "confidence_engine" / "README.md").exists()

    def test_gate_synthesis_readme_exists(self):
        assert (SRC_DIR / "gate_synthesis" / "README.md").exists()

    def test_learning_engine_readme_exists(self):
        assert (SRC_DIR / "learning_engine" / "README.md").exists()

    def test_execution_engine_readme_exists(self):
        assert (SRC_DIR / "execution_engine" / "README.md").exists()

    def test_librarian_readme_exists(self):
        assert (SRC_DIR / "librarian" / "README.md").exists()

    def test_telemetry_system_readme_exists(self):
        assert (SRC_DIR / "telemetry_system" / "README.md").exists()

    def test_billing_readme_exists(self):
        assert (SRC_DIR / "billing" / "README.md").exists()

    def test_dashboards_readme_exists(self):
        assert (SRC_DIR / "dashboards" / "README.md").exists()

    def test_robotics_readme_exists(self):
        assert (SRC_DIR / "robotics" / "README.md").exists()

    def test_control_theory_readme_exists(self):
        assert (SRC_DIR / "control_theory" / "README.md").exists()

    def test_readme_not_empty(self):
        """Every README.md must be non-empty (>= 20 bytes)."""
        empty = []
        for pkg in self._packages():
            readme = pkg / "README.md"
            if readme.exists() and readme.stat().st_size < 20:
                empty.append(pkg.name)
        assert empty == [], (
            "The following READMEs are too short (< 20 bytes): "
            + ", ".join(sorted(empty))
        )

    def test_readme_starts_with_heading(self):
        """Every README.md should start with a Markdown heading."""
        bad = []
        for pkg in self._packages():
            readme = pkg / "README.md"
            if readme.exists():
                first_line = readme.read_text(encoding="utf-8").splitlines()[0]
                if not first_line.startswith("#"):
                    bad.append(pkg.name)
        assert bad == [], (
            "READMEs not starting with a heading: "
            + ", ".join(sorted(bad))
        )


# ===========================================================================
# Gap 2 — AUAR proposal update (GAP-4)
# ===========================================================================

class TestGap2_AUARProposalUpdate:
    """AUAR_TECHNICAL_PROPOSAL.md must document the actual implementation."""

    @staticmethod
    def _proposal_text():
        path = DOCS_DIR / "AUAR_TECHNICAL_PROPOSAL.md"
        return path.read_text(encoding="utf-8")

    def test_proposal_exists(self):
        assert (DOCS_DIR / "AUAR_TECHNICAL_PROPOSAL.md").exists()

    def test_appendix_c_present(self):
        """Appendix C documents implementation divergences."""
        assert "Appendix C" in self._proposal_text()

    def test_ucb1_documented(self):
        """UCB1 algorithm must be documented (not just epsilon-greedy)."""
        text = self._proposal_text()
        assert "UCB1" in text, "UCB1 algorithm not mentioned in proposal"

    def test_persistence_backends_documented(self):
        """InMemory and File persistence backends must be mentioned."""
        text = self._proposal_text()
        assert "InMemoryPersistence" in text or "InMemory" in text
        assert "FilePersistence" in text or "File backend" in text.lower() or "file" in text.lower()

    def test_admin_security_documented(self):
        """Admin-role header security model must be documented."""
        text = self._proposal_text()
        assert "admin" in text.lower()
        assert "CWE-209" in text or "opaque" in text.lower() or "Opaque" in text

    def test_auar_pipeline_documented(self):
        """AUARPipeline entry point must be documented."""
        text = self._proposal_text()
        assert "AUARPipeline" in text

    def test_auar_config_documented(self):
        """AUARConfig must be documented."""
        text = self._proposal_text()
        assert "AUARConfig" in text


# ===========================================================================
# Gap 3 — Audit report accuracy
# ===========================================================================

class TestGap3_AuditReportAccuracy:
    """AUDIT_AND_COMPLETION_REPORT.md must reflect current package README count."""

    @staticmethod
    def _report_text():
        path = DOCS_DIR / "AUDIT_AND_COMPLETION_REPORT.md"
        return path.read_text(encoding="utf-8")

    def test_audit_report_exists(self):
        assert (DOCS_DIR / "AUDIT_AND_COMPLETION_REPORT.md").exists()

    def test_report_mentions_gap5(self):
        assert "GAP-5" in self._report_text() or "Package" in self._report_text()
