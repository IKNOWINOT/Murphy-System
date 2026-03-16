"""
Tests for SEC-001: SecurityAuditScanner.

Validates file scanning, directory scanning, finding classification,
persistence integration, and EventBackbone event publishing.

Design Label: TEST-013 / SEC-001
Owner: QA Team
"""

import os
import pytest


from security_audit_scanner import (
    SecurityAuditScanner,
    SecurityFinding,
    SecurityAuditReport,
)
from persistence_manager import PersistenceManager
from event_backbone import EventBackbone, EventType


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def pm(tmp_path):
    return PersistenceManager(persistence_dir=str(tmp_path / "test_persist"))


@pytest.fixture
def backbone():
    return EventBackbone()


@pytest.fixture
def scanner():
    return SecurityAuditScanner()


@pytest.fixture
def wired_scanner(pm, backbone):
    return SecurityAuditScanner(
        persistence_manager=pm,
        event_backbone=backbone,
    )


@pytest.fixture
def vuln_file(tmp_path):
    """Create a file with known security issues."""
    code = '''import os
import subprocess

def bad_eval(data):
    return eval(data)

def bad_exec(code):
    exec(code)

def bad_shell(cmd):
    subprocess.run(cmd, shell=True)

PASSWORD = "supersecret123"
DEBUG = True
'''
    p = tmp_path / "vulnerable.py"
    p.write_text(code)
    return str(p)


@pytest.fixture
def clean_file(tmp_path):
    """Create a file with no security issues."""
    code = '''import json

def safe_func(x, y):
    return x + y

def parse_data(raw):
    return json.loads(raw)
'''
    p = tmp_path / "clean.py"
    p.write_text(code)
    return str(p)


@pytest.fixture
def scan_dir(tmp_path):
    """Create a directory with mixed files."""
    vuln = '''def danger():\n    return eval("1+1")\n'''
    clean = '''def safe():\n    return 42\n'''
    (tmp_path / "vuln.py").write_text(vuln)
    (tmp_path / "clean.py").write_text(clean)
    return str(tmp_path)


# ------------------------------------------------------------------
# File scanning
# ------------------------------------------------------------------

class TestFileScanning:
    def test_scan_vulnerable_file(self, scanner, vuln_file):
        findings = scanner.scan_file(vuln_file)
        assert len(findings) >= 3  # eval, exec, shell, password, debug
        severities = {f.severity for f in findings}
        assert "critical" in severities  # eval or exec

    def test_scan_clean_file(self, scanner, clean_file):
        findings = scanner.scan_file(clean_file)
        assert len(findings) == 0

    def test_scan_nonexistent(self, scanner):
        findings = scanner.scan_file("/nonexistent/file.py")
        assert findings == []

    def test_finding_to_dict(self, scanner, vuln_file):
        findings = scanner.scan_file(vuln_file)
        assert len(findings) > 0
        d = findings[0].to_dict()
        assert "finding_id" in d
        assert "severity" in d
        assert "recommendation" in d


# ------------------------------------------------------------------
# Directory scanning
# ------------------------------------------------------------------

class TestDirectoryScanning:
    def test_scan_directory(self, scanner, scan_dir):
        report = scanner.scan_directory(scan_dir)
        assert report.files_scanned == 2
        assert report.total_findings >= 1

    def test_scan_nonexistent_dir(self, scanner):
        report = scanner.scan_directory("/nonexistent/dir")
        assert report.files_scanned == 0
        assert report.total_findings == 0

    def test_report_to_dict(self, scanner, scan_dir):
        report = scanner.scan_directory(scan_dir)
        d = report.to_dict()
        assert "report_id" in d
        assert "files_scanned" in d
        assert "findings" in d


# ------------------------------------------------------------------
# Query
# ------------------------------------------------------------------

class TestQuery:
    def test_get_findings(self, scanner, vuln_file):
        scanner.scan_file(vuln_file)
        findings = scanner.get_findings()
        assert len(findings) >= 3

    def test_filter_by_severity(self, scanner, vuln_file):
        scanner.scan_file(vuln_file)
        critical = scanner.get_findings(severity="critical")
        assert all(f["severity"] == "critical" for f in critical)

    def test_get_reports(self, scanner, scan_dir):
        scanner.scan_directory(scan_dir)
        reports = scanner.get_reports()
        assert len(reports) == 1


# ------------------------------------------------------------------
# Persistence
# ------------------------------------------------------------------

class TestPersistence:
    def test_report_persisted(self, wired_scanner, pm, scan_dir):
        report = wired_scanner.scan_directory(scan_dir)
        loaded = pm.load_document(report.report_id)
        assert loaded is not None
        assert loaded["files_scanned"] == 2


# ------------------------------------------------------------------
# EventBackbone integration
# ------------------------------------------------------------------

class TestEventBackboneIntegration:
    def test_scan_publishes_event(self, wired_scanner, backbone, scan_dir):
        received = []
        backbone.subscribe(EventType.LEARNING_FEEDBACK, lambda e: received.append(e))
        wired_scanner.scan_directory(scan_dir)
        backbone.process_pending()
        assert len(received) >= 1
        assert received[0].payload["source"] == "security_audit_scanner"


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

class TestStatus:
    def test_status(self, scanner, vuln_file):
        scanner.scan_file(vuln_file)
        status = scanner.get_status()
        assert status["total_findings"] >= 3
        assert status["persistence_attached"] is False

    def test_status_wired(self, wired_scanner):
        status = wired_scanner.get_status()
        assert status["persistence_attached"] is True
        assert status["backbone_attached"] is True
