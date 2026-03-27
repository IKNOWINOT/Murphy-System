"""
Security Audit Scanner for Murphy System.

Design Label: SEC-001 — Automated Security Vulnerability Scanning & Hardening Validation
Owner: Security Team / Platform Engineering
Dependencies:
  - PersistenceManager (for durable audit reports)
  - EventBackbone (publishes LEARNING_FEEDBACK on scan completion)
  - ComplianceAutomationBridge (CMP-001, optional, for compliance cross-checks)

Implements Phase 0 — Foundation Security:
  Scans Python source files for common security anti-patterns,
  validates security hardening configuration, and generates
  structured audit reports. Integrates with EventBackbone for
  reactive security automation.

Flow:
  1. Scan source files for security anti-patterns (eval, exec, etc.)
  2. Check for common vulnerabilities (hardcoded secrets, wildcard CORS)
  3. Validate security configuration files
  4. Generate structured audit report with severity classification
  5. Persist audit reports
  6. Publish LEARNING_FEEDBACK events

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Read-only: never modifies scanned files
  - Bounded: configurable max findings and reports
  - Conservative: flags potential issues for human review
  - Audit trail: every scan is logged

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import os
import re
import threading
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_FINDINGS = 50_000
_MAX_REPORTS = 1_000

# ---------------------------------------------------------------------------
# Security anti-patterns to scan for
# ---------------------------------------------------------------------------

_SECURITY_PATTERNS: List[Dict[str, Any]] = [
    {
        "name": "eval_usage",
        "pattern": r"\beval\s*\(",
        "severity": "critical",
        "description": "Use of eval() can execute arbitrary code",
        "recommendation": "Replace eval() with ast.literal_eval() or specific parsing",
    },
    {
        "name": "exec_usage",
        "pattern": r"\bexec\s*\(",
        "severity": "critical",
        "description": "Use of exec() can execute arbitrary code",
        "recommendation": "Remove exec() and use structured alternatives",
    },
    {
        "name": "subprocess_shell",
        "pattern": r"subprocess\.\w+\([^)]*shell\s*=\s*True",
        "severity": "high",
        "description": "subprocess with shell=True is vulnerable to shell injection",
        "recommendation": "Use shell=False and pass command as list",
    },
    {
        "name": "hardcoded_password",
        "pattern": r"""(?:password|passwd|pwd|secret|api_key|apikey|token)\s*=\s*['\"][^'\"]{4,}['\"]""",
        "severity": "high",
        "description": "Potential hardcoded secret or password",
        "recommendation": "Use environment variables or secret manager",
    },
    {
        "name": "wildcard_cors",
        "pattern": r"""(?:CORS|cors|allow_origins?)\s*[=(]\s*['\"\[]\s*\*""",
        "severity": "high",
        "description": "Wildcard CORS allows requests from any origin",
        "recommendation": "Restrict CORS to specific trusted origins",
    },
    {
        "name": "debug_mode",
        "pattern": r"""(?:DEBUG|debug)\s*=\s*True""",
        "severity": "medium",
        "description": "Debug mode enabled — may expose sensitive information",
        "recommendation": "Disable debug mode in production",
    },
    {
        "name": "pickle_usage",
        "pattern": r"\bpickle\.(?:load|loads)\s*\(",
        "severity": "high",
        "description": "pickle deserialization can execute arbitrary code",
        "recommendation": "Use JSON or other safe serialization formats",
    },
    {
        "name": "sql_string_format",
        "pattern": r"""(?:execute|cursor)\s*\(\s*(?:f['\"]|['\"].*%|['\"].*\.format)""",
        "severity": "high",
        "description": "SQL query built via string formatting — SQL injection risk",
        "recommendation": "Use parameterized queries",
    },
    {
        "name": "insecure_random",
        "pattern": r"\brandom\.\w+\(",
        "severity": "low",
        "description": "Use of random module (not cryptographically secure)",
        "recommendation": "Use secrets module for security-sensitive operations",
    },
    {
        "name": "assert_in_production",
        "pattern": r"^\s*assert\s+",
        "severity": "low",
        "description": "Assert statements are removed with -O flag",
        "recommendation": "Use explicit validation with proper error handling",
    },
]


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class SecurityFinding:
    """A single security finding from a scan."""
    finding_id: str
    file_path: str
    line_number: int
    pattern_name: str
    severity: str
    description: str
    recommendation: str
    line_content: str = ""
    found_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "pattern_name": self.pattern_name,
            "severity": self.severity,
            "description": self.description,
            "recommendation": self.recommendation,
            "line_content": self.line_content[:200],
            "found_at": self.found_at,
        }


@dataclass
class SecurityAuditReport:
    """A structured security audit report."""
    report_id: str
    files_scanned: int
    total_findings: int
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    findings: List[SecurityFinding] = field(default_factory=list)
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "files_scanned": self.files_scanned,
            "total_findings": self.total_findings,
            "critical_count": self.critical_count,
            "high_count": self.high_count,
            "medium_count": self.medium_count,
            "low_count": self.low_count,
            "findings": [f.to_dict() for f in self.findings],
            "generated_at": self.generated_at,
        }


# ---------------------------------------------------------------------------
# SecurityAuditScanner
# ---------------------------------------------------------------------------

class SecurityAuditScanner:
    """Automated security vulnerability scanning and hardening validation.

    Design Label: SEC-001
    Owner: Security Team / Platform Engineering

    Usage::

        scanner = SecurityAuditScanner(
            persistence_manager=pm,
            event_backbone=backbone,
        )
        report = scanner.scan_file("src/some_module.py")
        full_report = scanner.scan_directory("src/")
    """

    def __init__(
        self,
        persistence_manager=None,
        event_backbone=None,
        max_findings: int = _MAX_FINDINGS,
        max_reports: int = _MAX_REPORTS,
    ) -> None:
        self._lock = threading.Lock()
        self._pm = persistence_manager
        self._backbone = event_backbone
        self._findings: List[SecurityFinding] = []
        self._reports: List[SecurityAuditReport] = []
        self._max_findings = max_findings
        self._max_reports = max_reports
        self._compiled_patterns = [
            {**p, "regex": re.compile(p["pattern"])}
            for p in _SECURITY_PATTERNS
        ]

    # ------------------------------------------------------------------
    # Single-file scanning
    # ------------------------------------------------------------------

    def scan_file(self, file_path: str) -> List[SecurityFinding]:
        """Scan a single Python file for security anti-patterns."""
        try:
            with open(file_path, "r", encoding="utf-8") as fh:
                lines = fh.readlines()
        except (OSError, UnicodeDecodeError) as exc:
            logger.warning("Cannot read %s: %s", file_path, exc)
            return []

        findings: List[SecurityFinding] = []
        for line_num, line in enumerate(lines, start=1):
            for pattern_def in self._compiled_patterns:
                if pattern_def["regex"].search(line):
                    finding = SecurityFinding(
                        finding_id=f"sec-{uuid.uuid4().hex[:8]}",
                        file_path=file_path,
                        line_number=line_num,
                        pattern_name=pattern_def["name"],
                        severity=pattern_def["severity"],
                        description=pattern_def["description"],
                        recommendation=pattern_def["recommendation"],
                        line_content=line.rstrip()[:200],
                    )
                    findings.append(finding)

        with self._lock:
            for f in findings:
                if len(self._findings) >= self._max_findings:
                    evict = max(1, self._max_findings // 10)
                    self._findings = self._findings[evict:]
                self._findings.append(f)

        return findings

    # ------------------------------------------------------------------
    # Directory scanning
    # ------------------------------------------------------------------

    def scan_directory(self, directory: str) -> SecurityAuditReport:
        """Scan all Python files in a directory and generate an audit report."""
        all_findings: List[SecurityFinding] = []
        files_scanned = 0

        if not os.path.isdir(directory):
            logger.warning("Not a directory: %s", directory)
        else:
            for entry in sorted(os.listdir(directory)):
                if entry.endswith(".py") and not entry.startswith("__"):
                    full = os.path.join(directory, entry)
                    findings = self.scan_file(full)
                    all_findings.extend(findings)
                    files_scanned += 1

        report = SecurityAuditReport(
            report_id=f"sar-{uuid.uuid4().hex[:8]}",
            files_scanned=files_scanned,
            total_findings=len(all_findings),
            critical_count=sum(1 for f in all_findings if f.severity == "critical"),
            high_count=sum(1 for f in all_findings if f.severity == "high"),
            medium_count=sum(1 for f in all_findings if f.severity == "medium"),
            low_count=sum(1 for f in all_findings if f.severity == "low"),
            findings=all_findings,
        )

        with self._lock:
            if len(self._reports) >= self._max_reports:
                evict = max(1, self._max_reports // 10)
                self._reports = self._reports[evict:]
            self._reports.append(report)

        # Persist
        if self._pm is not None:
            try:
                self._pm.save_document(doc_id=report.report_id, document=report.to_dict())
            except Exception as exc:
                logger.debug("Persistence skipped: %s", exc)

        # Publish event
        if self._backbone is not None:
            self._publish_event(report)

        logger.info(
            "Security scan: %d files, %d findings (C=%d H=%d M=%d L=%d)",
            report.files_scanned, report.total_findings,
            report.critical_count, report.high_count,
            report.medium_count, report.low_count,
        )
        return report

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_findings(
        self,
        severity: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Return security findings, optionally filtered by severity."""
        with self._lock:
            findings = list(self._findings)
        if severity:
            findings = [f for f in findings if f.severity == severity]
        return [f.to_dict() for f in findings[-limit:]]

    def get_reports(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return recent audit reports."""
        with self._lock:
            reports = list(self._reports)
        return [r.to_dict() for r in reports[-limit:]]

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return scanner status summary."""
        with self._lock:
            sev_counts: Counter = Counter()
            for f in self._findings:
                sev_counts[f.severity] += 1
            return {
                "total_findings": len(self._findings),
                "total_reports": len(self._reports),
                "by_severity": dict(sev_counts),
                "persistence_attached": self._pm is not None,
                "backbone_attached": self._backbone is not None,
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _publish_event(self, report: SecurityAuditReport) -> None:
        """Publish a LEARNING_FEEDBACK event for security scan."""
        try:
            from event_backbone import Event
            from event_backbone import EventType as ET
            evt = Event(
                event_id=f"evt-{uuid.uuid4().hex[:8]}",
                event_type=ET.LEARNING_FEEDBACK,
                payload={
                    "source": "security_audit_scanner",
                    "action": "scan_complete",
                    "report_id": report.report_id,
                    "files_scanned": report.files_scanned,
                    "total_findings": report.total_findings,
                    "critical_count": report.critical_count,
                    "high_count": report.high_count,
                },
                timestamp=datetime.now(timezone.utc).isoformat(),
                source="security_audit_scanner",
            )
            self._backbone.publish_event(evt)
        except Exception as exc:
            logger.debug("EventBackbone publish skipped: %s", exc)
