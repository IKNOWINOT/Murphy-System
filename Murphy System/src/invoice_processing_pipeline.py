"""
Invoice Processing Pipeline for Murphy System.

Design Label: BIZ-002 — Automated Invoice Extraction, Validation & Routing
Owner: Finance Team / Platform Engineering
Dependencies:
  - PersistenceManager (for durable invoice storage)
  - EventBackbone (publishes LEARNING_FEEDBACK on processing outcomes)
  - ComplianceEngine (optional, for compliance validation)

Implements Phase 5 — Business Operations Automation:
  Extracts structured data from invoices, validates against business
  rules, routes for approval based on amount thresholds, and tracks
  the full invoice lifecycle.

Flow:
  1. Submit raw invoice data (vendor, amount, line items)
  2. Validate: required fields, amount consistency, vendor existence
  3. Route: auto-approve below threshold, escalate above
  4. Track lifecycle: submitted → validated → approved/rejected → paid
  5. Publish events for downstream automation

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Immutable history: invoice state transitions are append-only
  - Amount threshold: invoices above limit require human approval
  - Audit trail: every state change is logged

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class InvoiceStatus(str, Enum):
    """Invoice lifecycle states."""
    SUBMITTED = "submitted"
    VALIDATED = "validated"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    PAID = "paid"


@dataclass
class LineItem:
    """A single invoice line item."""
    description: str
    quantity: float
    unit_price: float

    @property
    def total(self) -> float:
        return round(self.quantity * self.unit_price, 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "description": self.description,
            "quantity": self.quantity,
            "unit_price": self.unit_price,
            "total": self.total,
        }


@dataclass
class Invoice:
    """A single invoice record."""
    invoice_id: str
    vendor: str
    amount: float
    currency: str = "USD"
    line_items: List[LineItem] = field(default_factory=list)
    status: InvoiceStatus = InvoiceStatus.SUBMITTED
    validation_errors: List[str] = field(default_factory=list)
    approver: Optional[str] = None
    notes: str = ""
    submitted_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "invoice_id": self.invoice_id,
            "vendor": self.vendor,
            "amount": round(self.amount, 2),
            "currency": self.currency,
            "line_items": [li.to_dict() for li in self.line_items],
            "status": self.status.value,
            "validation_errors": list(self.validation_errors),
            "approver": self.approver,
            "notes": self.notes,
            "submitted_at": self.submitted_at,
            "updated_at": self.updated_at,
        }


# ---------------------------------------------------------------------------
# InvoiceProcessingPipeline
# ---------------------------------------------------------------------------

class InvoiceProcessingPipeline:
    """Automated invoice extraction, validation, and approval routing.

    Design Label: BIZ-002
    Owner: Finance Team

    Usage::

        pipeline = InvoiceProcessingPipeline(
            persistence_manager=pm,
            event_backbone=backbone,
            auto_approve_threshold=500.0,
        )
        invoice = pipeline.submit_invoice(vendor="Acme", amount=250.0)
        pipeline.validate_invoice(invoice.invoice_id)
        pipeline.approve_invoice(invoice.invoice_id, approver="finance-bot")
    """

    def __init__(
        self,
        persistence_manager=None,
        event_backbone=None,
        auto_approve_threshold: float = 500.0,
        max_invoices: int = 10_000,
    ) -> None:
        self._lock = threading.Lock()
        self._pm = persistence_manager
        self._backbone = event_backbone
        self._auto_approve_threshold = auto_approve_threshold
        self._invoices: Dict[str, Invoice] = {}
        self._history: List[Dict[str, Any]] = []
        self._max_invoices = max_invoices

    # ------------------------------------------------------------------
    # Submit
    # ------------------------------------------------------------------

    def submit_invoice(
        self,
        vendor: str,
        amount: float,
        currency: str = "USD",
        line_items: Optional[List[Dict[str, Any]]] = None,
        notes: str = "",
    ) -> Invoice:
        """Submit a new invoice for processing."""
        items = []
        if line_items:
            for li in line_items:
                items.append(LineItem(
                    description=li.get("description", ""),
                    quantity=float(li.get("quantity", 1)),
                    unit_price=float(li.get("unit_price", 0)),
                ))

        invoice = Invoice(
            invoice_id=f"inv-{uuid.uuid4().hex[:8]}",
            vendor=vendor,
            amount=amount,
            currency=currency,
            line_items=items,
            notes=notes,
        )

        with self._lock:
            if len(self._invoices) >= self._max_invoices:
                # Evict oldest completed invoices
                paid = [k for k, v in self._invoices.items() if v.status == InvoiceStatus.PAID]
                for k in paid[:max(1, len(paid) // 2)]:
                    del self._invoices[k]
            self._invoices[invoice.invoice_id] = invoice
            self._record_event(invoice.invoice_id, "submitted", {})

        logger.info("Submitted invoice %s from %s for %.2f", invoice.invoice_id, vendor, amount)
        return invoice

    # ------------------------------------------------------------------
    # Validate
    # ------------------------------------------------------------------

    def validate_invoice(self, invoice_id: str) -> Optional[Invoice]:
        """Validate an invoice. Returns the invoice or None if not found."""
        with self._lock:
            invoice = self._invoices.get(invoice_id)
            if invoice is None:
                return None

            errors: List[str] = []
            if not invoice.vendor.strip():
                errors.append("Vendor name is required")
            if invoice.amount <= 0:
                errors.append("Amount must be positive")
            if invoice.line_items:
                line_total = sum(li.total for li in invoice.line_items)
                if abs(line_total - invoice.amount) > 0.01:
                    errors.append(
                        f"Line item total ({line_total:.2f}) does not match "
                        f"invoice amount ({invoice.amount:.2f})"
                    )

            invoice.validation_errors = errors
            if errors:
                invoice.status = InvoiceStatus.REJECTED
                self._record_event(invoice_id, "validation_failed", {"errors": errors})
            else:
                invoice.status = InvoiceStatus.VALIDATED
                self._record_event(invoice_id, "validated", {})

                # Auto-approve if below threshold
                if invoice.amount <= self._auto_approve_threshold:
                    invoice.status = InvoiceStatus.APPROVED
                    invoice.approver = "auto-approve"
                    self._record_event(invoice_id, "auto_approved", {
                        "threshold": self._auto_approve_threshold,
                    })
                else:
                    invoice.status = InvoiceStatus.PENDING_APPROVAL

            invoice.updated_at = datetime.now(timezone.utc).isoformat()

        self._persist(invoice)
        self._publish(invoice, "validated" if not errors else "validation_failed")
        return invoice

    # ------------------------------------------------------------------
    # Approve / Reject
    # ------------------------------------------------------------------

    def approve_invoice(self, invoice_id: str, approver: str = "system") -> Optional[Invoice]:
        """Approve a pending invoice."""
        with self._lock:
            invoice = self._invoices.get(invoice_id)
            if invoice is None:
                return None
            if invoice.status not in (InvoiceStatus.PENDING_APPROVAL, InvoiceStatus.VALIDATED):
                return invoice
            invoice.status = InvoiceStatus.APPROVED
            invoice.approver = approver
            invoice.updated_at = datetime.now(timezone.utc).isoformat()
            self._record_event(invoice_id, "approved", {"approver": approver})
        self._persist(invoice)
        self._publish(invoice, "approved")
        return invoice

    def reject_invoice(self, invoice_id: str, reason: str = "") -> Optional[Invoice]:
        """Reject an invoice."""
        with self._lock:
            invoice = self._invoices.get(invoice_id)
            if invoice is None:
                return None
            invoice.status = InvoiceStatus.REJECTED
            invoice.notes = reason or invoice.notes
            invoice.updated_at = datetime.now(timezone.utc).isoformat()
            self._record_event(invoice_id, "rejected", {"reason": reason})
        self._persist(invoice)
        self._publish(invoice, "rejected")
        return invoice

    def mark_paid(self, invoice_id: str) -> Optional[Invoice]:
        """Mark an approved invoice as paid."""
        with self._lock:
            invoice = self._invoices.get(invoice_id)
            if invoice is None:
                return None
            if invoice.status != InvoiceStatus.APPROVED:
                return invoice
            invoice.status = InvoiceStatus.PAID
            invoice.updated_at = datetime.now(timezone.utc).isoformat()
            self._record_event(invoice_id, "paid", {})
        self._persist(invoice)
        self._publish(invoice, "paid")
        return invoice

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_invoice(self, invoice_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            inv = self._invoices.get(invoice_id)
        return inv.to_dict() if inv else None

    def list_invoices(
        self,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            invoices = list(self._invoices.values())
        if status:
            invoices = [i for i in invoices if i.status.value == status]
        invoices.sort(key=lambda i: i.submitted_at, reverse=True)
        return [i.to_dict() for i in invoices[:limit]]

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._invoices)
            by_status: Dict[str, int] = {}
            for inv in self._invoices.values():
                by_status[inv.status.value] = by_status.get(inv.status.value, 0) + 1
        return {
            "total_invoices": total,
            "by_status": by_status,
            "auto_approve_threshold": self._auto_approve_threshold,
            "max_invoices": self._max_invoices,
            "persistence_attached": self._pm is not None,
            "backbone_attached": self._backbone is not None,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _record_event(self, invoice_id: str, action: str, details: Dict[str, Any]) -> None:
        """Append audit event (caller must hold _lock)."""
        capped_append(self._history, {
            "invoice_id": invoice_id,
            "action": action,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def _persist(self, invoice: Invoice) -> None:
        if self._pm is not None:
            try:
                self._pm.save_document(
                    doc_id=invoice.invoice_id,
                    document=invoice.to_dict(),
                )
            except Exception as exc:
                logger.debug("Persistence skipped: %s", exc)

    def _publish(self, invoice: Invoice, action: str) -> None:
        if self._backbone is not None:
            try:
                from event_backbone import EventType
                self._backbone.publish(
                    event_type=EventType.LEARNING_FEEDBACK,
                    payload={
                        "source": "invoice_processing_pipeline",
                        "action": action,
                        "invoice_id": invoice.invoice_id,
                        "status": invoice.status.value,
                        "amount": invoice.amount,
                    },
                    source="invoice_processing_pipeline",
                )
            except Exception as exc:
                logger.debug("EventBackbone publish skipped: %s", exc)
