"""
Tests for BIZ-002: InvoiceProcessingPipeline.

Validates invoice submission, validation, approval routing,
lifecycle management, and EventBackbone integration.

Design Label: TEST-005 / BIZ-002
Owner: QA Team
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from invoice_processing_pipeline import (
    InvoiceProcessingPipeline,
    Invoice,
    InvoiceStatus,
    LineItem,
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
def pipeline():
    return InvoiceProcessingPipeline(auto_approve_threshold=500.0)


@pytest.fixture
def wired_pipeline(pm, backbone):
    return InvoiceProcessingPipeline(
        persistence_manager=pm,
        event_backbone=backbone,
        auto_approve_threshold=500.0,
    )


# ------------------------------------------------------------------
# Submission
# ------------------------------------------------------------------

class TestSubmission:
    def test_submit_invoice(self, pipeline):
        inv = pipeline.submit_invoice(vendor="Acme Corp", amount=250.0)
        assert inv.invoice_id.startswith("inv-")
        assert inv.vendor == "Acme Corp"
        assert inv.amount == 250.0
        assert inv.status == InvoiceStatus.SUBMITTED

    def test_submit_with_line_items(self, pipeline):
        inv = pipeline.submit_invoice(
            vendor="Widgets Inc",
            amount=150.0,
            line_items=[
                {"description": "Widget A", "quantity": 10, "unit_price": 15.0},
            ],
        )
        assert len(inv.line_items) == 1
        assert inv.line_items[0].total == 150.0

    def test_invoice_to_dict(self, pipeline):
        inv = pipeline.submit_invoice(vendor="Test", amount=100.0)
        d = inv.to_dict()
        assert "invoice_id" in d
        assert "vendor" in d
        assert "status" in d


# ------------------------------------------------------------------
# Validation
# ------------------------------------------------------------------

class TestValidation:
    def test_valid_invoice_auto_approved(self, pipeline):
        inv = pipeline.submit_invoice(vendor="Acme", amount=200.0)
        result = pipeline.validate_invoice(inv.invoice_id)
        assert result.status == InvoiceStatus.APPROVED
        assert result.approver == "auto-approve"

    def test_above_threshold_needs_approval(self, pipeline):
        inv = pipeline.submit_invoice(vendor="BigCo", amount=1000.0)
        result = pipeline.validate_invoice(inv.invoice_id)
        assert result.status == InvoiceStatus.PENDING_APPROVAL

    def test_invalid_vendor_rejected(self, pipeline):
        inv = pipeline.submit_invoice(vendor="", amount=100.0)
        result = pipeline.validate_invoice(inv.invoice_id)
        assert result.status == InvoiceStatus.REJECTED
        assert "Vendor name is required" in result.validation_errors

    def test_negative_amount_rejected(self, pipeline):
        inv = pipeline.submit_invoice(vendor="Acme", amount=-50.0)
        result = pipeline.validate_invoice(inv.invoice_id)
        assert result.status == InvoiceStatus.REJECTED

    def test_line_item_mismatch_rejected(self, pipeline):
        inv = pipeline.submit_invoice(
            vendor="Acme",
            amount=200.0,
            line_items=[
                {"description": "Item", "quantity": 1, "unit_price": 100.0},
            ],
        )
        result = pipeline.validate_invoice(inv.invoice_id)
        assert result.status == InvoiceStatus.REJECTED
        assert any("does not match" in e for e in result.validation_errors)

    def test_validate_nonexistent_returns_none(self, pipeline):
        assert pipeline.validate_invoice("nonexistent") is None


# ------------------------------------------------------------------
# Approval / Rejection
# ------------------------------------------------------------------

class TestApproval:
    def test_approve_pending(self, pipeline):
        inv = pipeline.submit_invoice(vendor="BigCo", amount=1000.0)
        pipeline.validate_invoice(inv.invoice_id)
        result = pipeline.approve_invoice(inv.invoice_id, approver="cfo")
        assert result.status == InvoiceStatus.APPROVED
        assert result.approver == "cfo"

    def test_reject_invoice(self, pipeline):
        inv = pipeline.submit_invoice(vendor="BadCo", amount=999.0)
        pipeline.validate_invoice(inv.invoice_id)
        result = pipeline.reject_invoice(inv.invoice_id, reason="Fraudulent")
        assert result.status == InvoiceStatus.REJECTED

    def test_mark_paid(self, pipeline):
        inv = pipeline.submit_invoice(vendor="Acme", amount=100.0)
        pipeline.validate_invoice(inv.invoice_id)  # auto-approved
        result = pipeline.mark_paid(inv.invoice_id)
        assert result.status == InvoiceStatus.PAID


# ------------------------------------------------------------------
# Query
# ------------------------------------------------------------------

class TestQuery:
    def test_get_invoice(self, pipeline):
        inv = pipeline.submit_invoice(vendor="Test", amount=50.0)
        result = pipeline.get_invoice(inv.invoice_id)
        assert result is not None
        assert result["vendor"] == "Test"

    def test_list_invoices(self, pipeline):
        pipeline.submit_invoice(vendor="A", amount=100.0)
        pipeline.submit_invoice(vendor="B", amount=200.0)
        invoices = pipeline.list_invoices()
        assert len(invoices) == 2

    def test_list_by_status(self, pipeline):
        inv1 = pipeline.submit_invoice(vendor="A", amount=100.0)
        pipeline.submit_invoice(vendor="B", amount=200.0)
        pipeline.validate_invoice(inv1.invoice_id)
        approved = pipeline.list_invoices(status="approved")
        assert len(approved) == 1


# ------------------------------------------------------------------
# EventBackbone integration
# ------------------------------------------------------------------

class TestEventBackboneIntegration:
    def test_validation_publishes_event(self, wired_pipeline, backbone):
        received = []
        backbone.subscribe(EventType.LEARNING_FEEDBACK, lambda e: received.append(e))
        inv = wired_pipeline.submit_invoice(vendor="Acme", amount=100.0)
        wired_pipeline.validate_invoice(inv.invoice_id)
        backbone.process_pending()
        assert len(received) >= 1
        assert received[0].payload["source"] == "invoice_processing_pipeline"


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

class TestStatus:
    def test_status_reflects_state(self, pipeline):
        pipeline.submit_invoice(vendor="Acme", amount=100.0)
        status = pipeline.get_status()
        assert status["total_invoices"] == 1
        assert "submitted" in status["by_status"]
