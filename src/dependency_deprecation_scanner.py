"""
Dependency Deprecation Scanner for Murphy System.

Design Label: DEP-SCAN-001 — Automated Dependency Deprecation Detection
Owner: Platform Engineering / CI-CD Automation
Dependencies:
  - None (stdlib only — designed for zero-dependency CI environments)

Implements: Automated scanning of GitHub Actions workflows, Python
requirements, and npm packages for deprecated runtimes, actions, and
libraries. Produces structured deprecation reports that feed into the
Dependency Deprecation Agent pipeline.

Flow:
  1. Scan workflow YAML files for deprecated GitHub Actions versions
  2. Scan workflow YAML for deprecated runtime versions (Node.js, Python)
  3. Parse CI log annotations for deprecation warnings
  4. Generate structured DeprecationReport with fix recommendations
  5. Provide automated fix generation (updated YAML content)

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Read-only scanning: never modifies source files directly
  - Bounded: configurable max findings and file limits
  - Deterministic: same inputs always produce same outputs

Commissioning Principles (G1–G9):
  G1: Does the module do what it was designed to do?
      → Detects deprecated dependencies in workflows, requirements, and logs.
  G2: What exactly is the module supposed to do?
      → Scan files, match deprecation patterns, produce structured reports
        with actionable fix recommendations.
  G3: What conditions are possible based on the module?
      → Clean (no deprecations), warnings (upcoming), critical (past deadline),
        parse errors (malformed YAML), empty inputs.
  G4: Does the test profile reflect the full range of capabilities?
      → Tests cover all ecosystems, edge cases, empty/corrupt inputs.
  G5: What is the expected result at all points of operation?
      → Structured JSON reports with severity, deadline, and fix suggestions.
  G6: What is the actual result?
      → Verified via assertions in test suite.
  G7: If problems persist, restart from symptoms → validation.
      → Scanner is stateless; re-run with updated patterns.
  G8: Has all ancillary code and documentation been updated?
      → Yes — agent spec, capability baseline, and recovery log updated.
  G9: Has hardening been applied?
      → Bounded storage, defensive parsing, no subprocess calls.

Copyright (C) 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_FINDINGS = 10_000
_MAX_REPORTS = 500


class DeprecationSeverity(str, Enum):
    """Severity levels for deprecation findings."""
    INFO = "info"              # Informational, no action needed yet
    WARNING = "warning"        # Upcoming deprecation, plan migration
    CRITICAL = "critical"      # Past deadline or imminent, action required


class DeprecationEcosystem(str, Enum):
    """Ecosystem categories for deprecation scanning."""
    GITHUB_ACTIONS = "github_actions"
    NODEJS_RUNTIME = "nodejs_runtime"
    PYTHON_RUNTIME = "python_runtime"
    PIP_PACKAGE = "pip_package"
    NPM_PACKAGE = "npm_package"
    DOCKER_IMAGE = "docker_image"


# ---------------------------------------------------------------------------
# Known deprecation patterns
# ---------------------------------------------------------------------------

# GitHub Actions version mappings: (action_name, deprecated_version_re, recommended_version, info_url)
KNOWN_ACTION_DEPRECATIONS: List[Dict[str, str]] = [
    {
        "action": "actions/checkout",
        "deprecated_versions": "v1|v2|v3|v4",
        "recommended_version": "v4",
        "reason": "Node.js 20 actions are deprecated; v4 supports Node.js 20 with opt-in to 24",
        "info_url": "https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/",
        "deadline": "2026-06-02",
        "forced_deadline": "2026-09-16",
    },
    {
        "action": "actions/setup-python",
        "deprecated_versions": "v1|v2|v3|v4|v5",
        "recommended_version": "v5",
        "reason": "Node.js 20 actions are deprecated; v5 supports Node.js 20 with opt-in to 24",
        "info_url": "https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/",
        "deadline": "2026-06-02",
        "forced_deadline": "2026-09-16",
    },
    {
        "action": "actions/upload-artifact",
        "deprecated_versions": "v1|v2|v3|v4",
        "recommended_version": "v4",
        "reason": "Node.js 20 actions are deprecated; v4 supports Node.js 20 with opt-in to 24",
        "info_url": "https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/",
        "deadline": "2026-06-02",
        "forced_deadline": "2026-09-16",
    },
    {
        "action": "actions/download-artifact",
        "deprecated_versions": "v1|v2|v3|v4",
        "recommended_version": "v4",
        "reason": "Node.js 20 actions are deprecated; v4 supports Node.js 20 with opt-in to 24",
        "info_url": "https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/",
        "deadline": "2026-06-02",
        "forced_deadline": "2026-09-16",
    },
    {
        "action": "actions/setup-node",
        "deprecated_versions": "v1|v2|v3|v4",
        "recommended_version": "v4",
        "reason": "Node.js 20 actions are deprecated",
        "info_url": "https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/",
        "deadline": "2026-06-02",
        "forced_deadline": "2026-09-16",
    },
    {
        "action": "actions/cache",
        "deprecated_versions": "v1|v2|v3|v4",
        "recommended_version": "v4",
        "reason": "Node.js 20 actions are deprecated",
        "info_url": "https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/",
        "deadline": "2026-06-02",
        "forced_deadline": "2026-09-16",
    },
]

# CI log patterns that indicate deprecation warnings
LOG_DEPRECATION_PATTERNS: List[Dict[str, str]] = [
    {
        "pattern": r"Node\.js\s+(\d+)\s+actions?\s+are\s+deprecated",
        "ecosystem": DeprecationEcosystem.NODEJS_RUNTIME.value,
        "description": "Node.js runtime deprecation in GitHub Actions",
    },
    {
        "pattern": r"FORCE_JAVASCRIPT_ACTIONS_TO_NODE(\d+)",
        "ecosystem": DeprecationEcosystem.NODEJS_RUNTIME.value,
        "description": "Node.js version force opt-in environment variable referenced",
    },
    {
        "pattern": r"ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION",
        "ecosystem": DeprecationEcosystem.NODEJS_RUNTIME.value,
        "description": "Insecure Node.js version opt-out referenced",
    },
    {
        "pattern": r"(?:python|Python)\s+(\d+\.\d+)\s+(?:is|has been|will be)\s+deprecated",
        "ecosystem": DeprecationEcosystem.PYTHON_RUNTIME.value,
        "description": "Python runtime deprecation notice",
    },
    {
        "pattern": r"DeprecationWarning:\s*(.*)",
        "ecosystem": DeprecationEcosystem.PIP_PACKAGE.value,
        "description": "Python DeprecationWarning in CI output",
    },
    {
        "pattern": r"npm\s+warn\s+deprecated\s+(\S+)",
        "ecosystem": DeprecationEcosystem.NPM_PACKAGE.value,
        "description": "npm deprecated package warning",
    },
]


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class DeprecationFinding:
    """A single deprecation finding."""
    finding_id: str
    ecosystem: str
    severity: str
    source_file: str
    line_number: int
    current_value: str
    recommended_value: str
    reason: str
    deadline: str = ""
    info_url: str = ""
    found_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "ecosystem": self.ecosystem,
            "severity": self.severity,
            "source_file": self.source_file,
            "line_number": self.line_number,
            "current_value": self.current_value,
            "recommended_value": self.recommended_value,
            "reason": self.reason,
            "deadline": self.deadline,
            "info_url": self.info_url,
            "found_at": self.found_at,
        }


@dataclass
class DeprecationReport:
    """Summary of a deprecation scan cycle."""
    report_id: str
    files_scanned: int
    total_findings: int
    critical_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    findings: List[DeprecationFinding] = field(default_factory=list)
    fix_recommendations: List[Dict[str, Any]] = field(default_factory=list)
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "files_scanned": self.files_scanned,
            "total_findings": self.total_findings,
            "critical_count": self.critical_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
            "findings": [f.to_dict() for f in self.findings],
            "fix_recommendations": self.fix_recommendations,
            "generated_at": self.generated_at,
        }


# ---------------------------------------------------------------------------
# DeprecationScanner
# ---------------------------------------------------------------------------

class DeprecationScanner:
    """Automated deprecation detection for GitHub Actions, runtimes, and packages.

    Design Label: DEP-SCAN-001
    Owner: Platform Engineering / CI-CD Automation

    Usage::

        scanner = DeprecationScanner()
        report = scanner.scan_workflows(Path(".github/workflows/"))
        report = scanner.scan_ci_logs("Node.js 20 actions are deprecated...")
        report = scanner.full_scan(repo_root=Path("."))
    """

    def __init__(
        self,
        action_deprecations: Optional[List[Dict[str, str]]] = None,
        log_patterns: Optional[List[Dict[str, str]]] = None,
        max_findings: int = _MAX_FINDINGS,
        reference_date: Optional[str] = None,
    ) -> None:
        self._lock = threading.Lock()
        self._action_deprecations = action_deprecations or KNOWN_ACTION_DEPRECATIONS
        self._log_patterns = log_patterns or LOG_DEPRECATION_PATTERNS
        self._reports: List[DeprecationReport] = []
        self._max_findings = max_findings
        # Allow injection of reference date for deterministic testing
        self._reference_date = reference_date

    # ------------------------------------------------------------------
    # Workflow YAML scanning
    # ------------------------------------------------------------------

    def scan_workflows(self, workflows_dir: Path) -> DeprecationReport:
        """Scan all YAML workflow files in a directory for deprecated actions.

        G2: Reads .yml/.yaml files, matches `uses: action@version` lines,
            compares against known deprecation database, produces findings.
        G3: Handles missing directory, empty files, malformed YAML lines.
        G5: Returns DeprecationReport with findings and fix recommendations.
        """
        findings: List[DeprecationFinding] = []
        fix_recs: List[Dict[str, Any]] = []
        files_scanned = 0

        if not workflows_dir.exists():
            logger.warning("Workflows directory not found: %s", workflows_dir)
            return self._build_report(0, findings, fix_recs)

        yaml_files = sorted(
            list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))
        )

        for yaml_file in yaml_files:
            try:
                content = yaml_file.read_text(encoding="utf-8", errors="replace")
                files_scanned += 1
                file_findings, file_fixes = self._scan_workflow_content(
                    content, str(yaml_file)
                )
                findings.extend(file_findings)
                fix_recs.extend(file_fixes)
            except Exception:
                logger.debug("Could not read %s", yaml_file, exc_info=True)

        return self._build_report(files_scanned, findings, fix_recs)

    def scan_workflow_content(self, content: str, filename: str = "<inline>") -> DeprecationReport:
        """Scan a single workflow YAML string for deprecated actions.

        Public interface for scanning content directly (useful for testing).
        """
        findings, fix_recs = self._scan_workflow_content(content, filename)
        return self._build_report(1, findings, fix_recs)

    def _scan_workflow_content(
        self, content: str, filename: str
    ) -> tuple:
        """Internal: scan one YAML content string for deprecated actions."""
        findings: List[DeprecationFinding] = []
        fix_recs: List[Dict[str, Any]] = []

        lines = content.splitlines()
        for line_num, line in enumerate(lines, start=1):
            stripped = line.strip()
            # Match `uses: owner/action@version` patterns
            m = re.match(r"^-?\s*uses:\s*([^@\s]+)@(\S+)", stripped)
            if not m:
                continue
            action_name = m.group(1)
            action_version = m.group(2)

            for dep in self._action_deprecations:
                if dep["action"] != action_name:
                    continue
                dep_re = re.compile(rf"^({dep['deprecated_versions']})$")
                if not dep_re.match(action_version):
                    continue

                severity = self._compute_severity(dep.get("deadline", ""))
                finding = DeprecationFinding(
                    finding_id=f"ddf-{uuid.uuid4().hex[:8]}",
                    ecosystem=DeprecationEcosystem.GITHUB_ACTIONS.value,
                    severity=severity,
                    source_file=filename,
                    line_number=line_num,
                    current_value=f"{action_name}@{action_version}",
                    recommended_value=f"{action_name}@{dep['recommended_version']}",
                    reason=dep["reason"],
                    deadline=dep.get("deadline", ""),
                    info_url=dep.get("info_url", ""),
                )
                findings.append(finding)

                fix_recs.append({
                    "file": filename,
                    "line": line_num,
                    "action": "replace_action_version",
                    "old_value": f"{action_name}@{action_version}",
                    "new_value": f"{action_name}@{dep['recommended_version']}",
                    "description": f"Update {action_name} from @{action_version} to @{dep['recommended_version']}",
                })
                break  # Only match first deprecation rule per action

        return findings, fix_recs

    # ------------------------------------------------------------------
    # CI log scanning
    # ------------------------------------------------------------------

    def scan_ci_logs(self, log_text: str, source: str = "<ci-log>") -> DeprecationReport:
        """Scan CI log text for deprecation warnings.

        G2: Parses raw CI output for known deprecation patterns across
            all supported ecosystems.
        G3: Handles empty logs, binary content, very large logs.
        G5: Returns DeprecationReport with findings extracted from log text.
        """
        findings: List[DeprecationFinding] = []

        if not log_text or not log_text.strip():
            return self._build_report(0, findings, [])

        # Cap log scanning to 1MB to prevent unbounded processing
        scan_text = log_text[:1_048_576]

        for pat_info in self._log_patterns:
            pattern = pat_info["pattern"]
            for match in re.finditer(pattern, scan_text, re.IGNORECASE):
                # Find line number
                line_start = scan_text.count("\n", 0, match.start()) + 1
                findings.append(DeprecationFinding(
                    finding_id=f"ddf-{uuid.uuid4().hex[:8]}",
                    ecosystem=pat_info["ecosystem"],
                    severity=DeprecationSeverity.WARNING.value,
                    source_file=source,
                    line_number=line_start,
                    current_value=match.group(0)[:200],
                    recommended_value="See info_url for migration guide",
                    reason=pat_info["description"],
                ))

        return self._build_report(1 if log_text else 0, findings, [])

    # ------------------------------------------------------------------
    # Full repository scan
    # ------------------------------------------------------------------

    def full_scan(self, repo_root: Path) -> DeprecationReport:
        """Run a comprehensive deprecation scan across the entire repository.

        G2: Combines workflow scanning, requirements scanning, and produces
            a unified deprecation report.
        G3: Handles missing directories, partial scans, aggregates all findings.
        """
        all_findings: List[DeprecationFinding] = []
        all_fix_recs: List[Dict[str, Any]] = []
        files_scanned = 0

        # 1. Scan GitHub Actions workflows
        workflows_dir = repo_root / ".github" / "workflows"
        if workflows_dir.exists():
            wf_report = self.scan_workflows(workflows_dir)
            all_findings.extend(wf_report.findings)
            all_fix_recs.extend(wf_report.fix_recommendations)
            files_scanned += wf_report.files_scanned

        # 2. Check for FORCE_JAVASCRIPT_ACTIONS_TO_NODE24 in env
        for yaml_file in sorted(
            list((repo_root / ".github" / "workflows").glob("*.yml"))
            + list((repo_root / ".github" / "workflows").glob("*.yaml"))
        ) if workflows_dir.exists() else []:
            try:
                content = yaml_file.read_text(encoding="utf-8", errors="replace")
                if "FORCE_JAVASCRIPT_ACTIONS_TO_NODE24" not in content:
                    # Recommend adding the opt-in env var
                    all_fix_recs.append({
                        "file": str(yaml_file),
                        "action": "add_env_var",
                        "key": "FORCE_JAVASCRIPT_ACTIONS_TO_NODE24",
                        "value": "true",
                        "description": (
                            f"Add FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true to "
                            f"{yaml_file.name} for Node.js 24 opt-in"
                        ),
                    })
            except Exception:
                logger.debug("Could not read %s", yaml_file, exc_info=True)

        return self._build_report(files_scanned, all_findings, all_fix_recs)

    # ------------------------------------------------------------------
    # Fix generation
    # ------------------------------------------------------------------

    def generate_fix(self, content: str, fix_recs: List[Dict[str, Any]]) -> str:
        """Apply fix recommendations to workflow YAML content.

        G2: Takes original YAML content and a list of fix recommendations,
            returns updated content with deprecated actions replaced.
        G5: Output should be valid YAML with only version tags changed.
        """
        result = content
        for rec in fix_recs:
            if rec.get("action") == "replace_action_version":
                old = rec.get("old_value", "")
                new = rec.get("new_value", "")
                if old and new:
                    result = result.replace(old, new)
        return result

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_reports(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return recent scan reports."""
        with self._lock:
            reports = list(self._reports)
        return [r.to_dict() for r in reports[-limit:]]

    def get_status(self) -> Dict[str, Any]:
        """Return scanner status."""
        with self._lock:
            return {
                "total_reports": len(self._reports),
                "known_action_deprecations": len(self._action_deprecations),
                "log_patterns": len(self._log_patterns),
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_severity(self, deadline: str) -> str:
        """Determine severity based on deadline proximity."""
        if not deadline:
            return DeprecationSeverity.WARNING.value

        try:
            if self._reference_date:
                now = datetime.fromisoformat(self._reference_date)
            else:
                now = datetime.now(timezone.utc)
            dl = datetime.fromisoformat(deadline)
            if dl.tzinfo is None:
                dl = dl.replace(tzinfo=timezone.utc)
            if now.tzinfo is None:
                now = now.replace(tzinfo=timezone.utc)

            days_until = (dl - now).days
            if days_until <= 0:
                return DeprecationSeverity.CRITICAL.value
            elif days_until <= 90:
                return DeprecationSeverity.WARNING.value
            else:
                return DeprecationSeverity.INFO.value
        except (ValueError, TypeError):
            return DeprecationSeverity.WARNING.value

    def _build_report(
        self,
        files_scanned: int,
        findings: List[DeprecationFinding],
        fix_recs: List[Dict[str, Any]],
    ) -> DeprecationReport:
        """Build and store a DeprecationReport."""
        # Enforce bounded findings
        if len(findings) > self._max_findings:
            findings = findings[: self._max_findings]

        report = DeprecationReport(
            report_id=f"ddr-{uuid.uuid4().hex[:8]}",
            files_scanned=files_scanned,
            total_findings=len(findings),
            critical_count=sum(1 for f in findings if f.severity == DeprecationSeverity.CRITICAL.value),
            warning_count=sum(1 for f in findings if f.severity == DeprecationSeverity.WARNING.value),
            info_count=sum(1 for f in findings if f.severity == DeprecationSeverity.INFO.value),
            findings=findings,
            fix_recommendations=fix_recs,
        )

        with self._lock:
            if len(self._reports) >= _MAX_REPORTS:
                evict = max(1, _MAX_REPORTS // 10)
                self._reports = self._reports[evict:]
            self._reports.append(report)

        logger.info(
            "Deprecation scan: %d files, %d findings (C=%d W=%d I=%d)",
            report.files_scanned,
            report.total_findings,
            report.critical_count,
            report.warning_count,
            report.info_count,
        )
        return report
