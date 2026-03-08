"""
Test Suite: Infrastructure Gap Tracking — DEFICIENCY-8

Verifies:
  - QA_AUDIT_REPORT.md contains INFRA-001 through INFRA-004 tracking entries
  - STATUS.md contains INFRA-001 through INFRA-004

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"
QA_AUDIT_PATH = DOCS_DIR / "QA_AUDIT_REPORT.md"
STATUS_PATH = PROJECT_ROOT / "STATUS.md"

REQUIRED_INFRA_IDS = ["INFRA-001", "INFRA-002", "INFRA-003", "INFRA-004"]


class TestQaAuditReport:
    def test_qa_audit_report_exists(self):
        assert QA_AUDIT_PATH.exists(), f"QA_AUDIT_REPORT.md not found at {QA_AUDIT_PATH}"

    @pytest.mark.parametrize("infra_id", REQUIRED_INFRA_IDS)
    def test_infra_id_present(self, infra_id):
        content = QA_AUDIT_PATH.read_text(encoding="utf-8", errors="replace")
        assert infra_id in content, (
            f"{infra_id} not found in QA_AUDIT_REPORT.md"
        )

    def test_infra_001_is_deferred(self):
        content = QA_AUDIT_PATH.read_text(encoding="utf-8", errors="replace")
        # Find the INFRA-001 line and confirm DEFERRED status
        for line in content.splitlines():
            if "INFRA-001" in line:
                assert "DEFERRED" in line.upper() or "deferred" in line.lower(), (
                    f"INFRA-001 should be marked DEFERRED, got: {line}"
                )
                break

    def test_infra_002_is_deferred(self):
        content = QA_AUDIT_PATH.read_text(encoding="utf-8", errors="replace")
        for line in content.splitlines():
            if "INFRA-002" in line:
                assert "DEFERRED" in line.upper() or "deferred" in line.lower(), (
                    f"INFRA-002 should be marked DEFERRED, got: {line}"
                )
                break

    def test_infra_003_is_in_progress(self):
        content = QA_AUDIT_PATH.read_text(encoding="utf-8", errors="replace")
        for line in content.splitlines():
            if "INFRA-003" in line:
                assert "IN PROGRESS" in line.upper() or "progress" in line.lower(), (
                    f"INFRA-003 should be IN PROGRESS, got: {line}"
                )
                break

    def test_infra_004_is_in_progress(self):
        content = QA_AUDIT_PATH.read_text(encoding="utf-8", errors="replace")
        for line in content.splitlines():
            if "INFRA-004" in line:
                assert "IN PROGRESS" in line.upper() or "progress" in line.lower(), (
                    f"INFRA-004 should be IN PROGRESS, got: {line}"
                )
                break


class TestStatusMd:
    def test_status_md_exists(self):
        assert STATUS_PATH.exists(), f"STATUS.md not found at {STATUS_PATH}"

    @pytest.mark.parametrize("infra_id", REQUIRED_INFRA_IDS)
    def test_infra_id_present_in_status(self, infra_id):
        content = STATUS_PATH.read_text(encoding="utf-8", errors="replace")
        assert infra_id in content, (
            f"{infra_id} not found in STATUS.md"
        )
