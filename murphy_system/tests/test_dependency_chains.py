# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""Tests for all 8 dependency chains in the onboarding spec."""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.platform_onboarding.task_catalog import TASK_CATALOG

TASK_MAP = {t.task_id: t for t in TASK_CATALOG}


def test_chain1_ein_to_sam_gov():
    """1.02 → 1.01 → [1.03, 1.04, 1.05, 1.06, 1.07]"""
    assert "1.02" in TASK_MAP["1.01"].depends_on

    for downstream in ["1.03", "1.04", "1.05", "1.06", "1.07"]:
        assert "1.01" in TASK_MAP[downstream].depends_on, (
            f"Expected {downstream} to depend on 1.01"
        )


def test_chain1_ein_blocks_sam():
    sam = TASK_MAP["1.01"]
    assert "1.02" in sam.depends_on


def test_chain2_grant_apps_depend_on_sam_grants_sbir():
    """[1.01, 1.03, 1.05] → 2.01 (SBIR Phase I)"""
    sbir = TASK_MAP["2.01"]
    assert "1.01" in sbir.depends_on
    assert "1.03" in sbir.depends_on
    assert "1.05" in sbir.depends_on


def test_chain2_other_grant_apps():
    for grant_id in ["2.02", "2.04", "2.05", "2.07", "2.08", "2.09", "2.10", "2.11", "2.12"]:
        task = TASK_MAP[grant_id]
        assert "1.01" in task.depends_on, f"{grant_id} should depend on 1.01"
        assert "1.03" in task.depends_on, f"{grant_id} should depend on 1.03"
        assert "1.05" in task.depends_on, f"{grant_id} should depend on 1.05"


def test_chain3_cloud_credits_no_deps():
    """Cloud credits have no dependencies — start immediately."""
    for tid in ["4.01", "4.02", "4.03", "4.04", "4.05", "4.06", "4.07", "4.08"]:
        assert TASK_MAP[tid].depends_on == [], f"{tid} should have no dependencies"


def test_chain4_api_keys_no_deps():
    """API keys have no dependencies."""
    api_tasks = [t for t in TASK_CATALOG if t.section == "5"]
    for t in api_tasks:
        assert t.depends_on == [], f"{t.task_id} should have no dependencies"


def test_chain5_stripe_to_bnpl():
    """5.10 (Stripe) → 3.04, 3.05, 3.06, 3.07"""
    for bnpl_id in ["3.04", "3.05", "3.06", "3.07"]:
        assert "5.10" in TASK_MAP[bnpl_id].depends_on, (
            f"{bnpl_id} should depend on 5.10 (Stripe)"
        )


def test_chain5_paypal_to_paybright():
    """5.11 (PayPal) → 3.08 (PayBright)"""
    assert "5.11" in TASK_MAP["3.08"].depends_on


def test_chain6_aws_iam_to_aws_marketplace():
    """5.21 (AWS IAM) → 7.01 (AWS Marketplace)"""
    assert "5.21" in TASK_MAP["7.01"].depends_on


def test_chain6_gcp_to_gcp_marketplace():
    """5.45 (GCP SA) → 7.02 (GCP Marketplace)"""
    assert "5.45" in TASK_MAP["7.02"].depends_on


def test_chain6_azure_to_azure_marketplace():
    """5.46 (Azure SP) → 7.03 (Azure Marketplace)"""
    assert "5.46" in TASK_MAP["7.03"].depends_on


def test_chain7_compliance_self_assessments_are_level_0():
    """NIST CSF, CIS, GDPR, CCPA, privacy policy, vuln disclosure — no deps."""
    for tid in ["6.04", "6.05", "6.06", "6.07", "6.11", "6.12"]:
        assert TASK_MAP[tid].depends_on == [], f"{tid} should have no dependencies"


def test_chain8_sam_to_international_grants():
    """1.01 (SAM.gov) → 8.01–8.10 (all international grants)"""
    for i in range(1, 11):
        tid = f"8.{i:02d}"
        assert "1.01" in TASK_MAP[tid].depends_on, (
            f"{tid} should depend on 1.01 (SAM.gov)"
        )


def test_chain8_international_grants_are_conditional():
    """All international grants should have is_conditional=True."""
    for i in range(1, 11):
        tid = f"8.{i:02d}"
        assert TASK_MAP[tid].is_conditional is True, f"{tid} should be conditional"
        assert TASK_MAP[tid].condition is not None, f"{tid} should have a condition"


def test_blocks_reverse_consistency():
    """blocks must be the reverse of depends_on."""
    for task in TASK_CATALOG:
        for dep_id in task.depends_on:
            dep_task = TASK_MAP[dep_id]
            assert task.task_id in dep_task.blocks, (
                f"Expected {dep_id}.blocks to contain {task.task_id}"
            )
