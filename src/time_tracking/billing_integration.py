# Copyright © 2020 Inoni Limited Liability Company
"""
Time Tracking – Billing Integration Service
=============================================

Connects time tracking data to the invoice processing pipeline.
Provides billable summary, client rate management, invoice generation
from approved time entries, and double-billing protection.

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import threading
import uuid
from typing import Any, Dict, List, Optional

from .models import EntryStatus, TimeEntry

# ---------------------------------------------------------------------------
# Default configuration
# ---------------------------------------------------------------------------

_DEFAULT_HOURLY_RATE = 150.00
_DEFAULT_CURRENCY = "USD"


class BillingIntegrationService:
    """Connect time tracking to the invoice processing pipeline.

    Works standalone (without real pipeline) or with an
    :class:`~invoice_processing_pipeline.InvoiceProcessingPipeline`
    injected via *invoice_pipeline*.
    """

    def __init__(
        self,
        invoice_pipeline=None,
        subscription_manager=None,
        entries: Optional[Dict[str, TimeEntry]] = None,
        default_hourly_rate: float = _DEFAULT_HOURLY_RATE,
        default_currency: str = _DEFAULT_CURRENCY,
    ) -> None:
        self._pipeline = invoice_pipeline
        self._subscription_manager = subscription_manager
        # Shared time entry store; callers should pass tracker._entries
        self._entries: Dict[str, TimeEntry] = entries if entries is not None else {}
        self._lock = threading.Lock()
        self._default_rate = default_hourly_rate
        self._default_currency = default_currency
        # {client_id: {"rate": float, "currency": str}}
        self._client_rates: Dict[str, Dict[str, Any]] = {}
        # {entry_id: invoice_id}
        self._invoiced_entries: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # Client-rate management
    # ------------------------------------------------------------------

    def set_client_rate(
        self, client_id: str, hourly_rate: float, currency: str = "USD"
    ) -> Dict[str, Any]:
        """Store a billing rate for *client_id*."""
        with self._lock:
            self._client_rates[client_id] = {
                "rate": hourly_rate,
                "currency": currency,
            }
        return {"client_id": client_id, "rate": hourly_rate, "currency": currency}

    def get_client_rate(self, client_id: str) -> Dict[str, Any]:
        """Retrieve rate for *client_id*, falling back to the default."""
        with self._lock:
            info = self._client_rates.get(client_id)
        if info:
            return dict(info)
        return {"rate": self._default_rate, "currency": self._default_currency}

    def list_client_rates(self) -> List[Dict[str, Any]]:
        """Return all client-specific rates."""
        with self._lock:
            return [
                {"client_id": cid, "rate": v["rate"], "currency": v["currency"]}
                for cid, v in self._client_rates.items()
            ]

    # ------------------------------------------------------------------
    # Invoice generation
    # ------------------------------------------------------------------

    def generate_invoice_from_entries(
        self,
        client_id: str,
        entry_ids: List[str],
        hourly_rate: Optional[float] = None,
        currency: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create an invoice from *approved* time entries.

        Raises :class:`ValueError` if any entry is not approved or has
        already been invoiced.

        Returns a dict with ``invoice_id``, ``total_amount``,
        ``line_items``, ``currency``, and ``status``.
        """
        with self._lock:
            entries = self._resolve_entries(entry_ids)
            rate = self._effective_rate(client_id, hourly_rate)
            cur = currency or self._client_rates.get(client_id, {}).get(
                "currency", self._default_currency
            )

            for entry in entries:
                if entry.status != EntryStatus.APPROVED:
                    raise ValueError(
                        f"Entry {entry.id!r} is not approved "
                        f"(status={entry.status.value!r})"
                    )
                if entry.id in self._invoiced_entries:
                    raise ValueError(
                        f"Entry {entry.id!r} has already been invoiced "
                        f"(invoice {self._invoiced_entries[entry.id]!r})"
                    )

            line_items = self._build_line_items(entries, rate)
            total_hours = sum(e.duration_seconds for e in entries) / 3600.0
            total_amount = round(total_hours * rate, 2)
            invoice_id = f"tt-inv-{uuid.uuid4().hex[:8]}"

            # Persist to pipeline if available
            if self._pipeline is not None:
                pipeline_items = [
                    {
                        "description": li["description"],
                        "quantity": li["hours"],
                        "unit_price": rate,
                    }
                    for li in line_items
                ]
                inv = self._pipeline.submit_invoice(
                    vendor=client_id,
                    amount=total_amount,
                    currency=cur,
                    line_items=pipeline_items,
                    notes=f"Time tracking invoice for client {client_id}",
                )
                invoice_id = inv.invoice_id

            # Mark entries as invoiced (inside lock)
            for entry in entries:
                self._invoiced_entries[entry.id] = invoice_id

        return {
            "invoice_id": invoice_id,
            "client_id": client_id,
            "total_amount": total_amount,
            "total_hours": round(total_hours, 4),
            "hourly_rate": rate,
            "line_items": line_items,
            "currency": cur,
            "status": "draft",
        }

    def calculate_invoice_preview(
        self,
        entry_ids: List[str],
        client_id: str = "",
        hourly_rate: Optional[float] = None,
        currency: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Preview an invoice without creating it.

        Does not require entries to be approved and does not modify any
        state.
        """
        with self._lock:
            entries = self._resolve_entries(entry_ids)
            rate = self._effective_rate(client_id, hourly_rate)
            cur = currency or self._client_rates.get(client_id, {}).get(
                "currency", self._default_currency
            )
            line_items = self._build_line_items(entries, rate)
            total_hours = sum(e.duration_seconds for e in entries) / 3600.0
            total_amount = round(total_hours * rate, 2)

        return {
            "preview": True,
            "client_id": client_id,
            "total_amount": total_amount,
            "total_hours": round(total_hours, 4),
            "hourly_rate": rate,
            "line_items": line_items,
            "currency": cur,
        }

    # ------------------------------------------------------------------
    # Double-billing protection
    # ------------------------------------------------------------------

    def mark_entries_invoiced(
        self, entry_ids: List[str], invoice_id: str
    ) -> Dict[str, Any]:
        """Mark *entry_ids* as billed on *invoice_id*.

        Returns counts of entries newly marked vs. already invoiced.
        """
        newly_marked: List[str] = []
        already_invoiced: List[str] = []
        with self._lock:
            for eid in entry_ids:
                if eid in self._invoiced_entries:
                    already_invoiced.append(eid)
                else:
                    self._invoiced_entries[eid] = invoice_id
                    newly_marked.append(eid)
        return {
            "invoice_id": invoice_id,
            "newly_marked": newly_marked,
            "already_invoiced": already_invoiced,
        }

    def is_entry_invoiced(self, entry_id: str) -> bool:
        with self._lock:
            return entry_id in self._invoiced_entries

    # ------------------------------------------------------------------
    # Billable summary
    # ------------------------------------------------------------------

    def get_billable_summary(
        self,
        client_id: Optional[str] = None,
        date_range: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Return a summary of all billable, un-invoiced entries.

        *client_id* maps to ``board_id`` on :class:`~.models.TimeEntry`.
        *date_range* is ``{"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}``.
        """
        with self._lock:
            entries = list(self._entries.values())
            invoiced = set(self._invoiced_entries.keys())

        entries = [
            e for e in entries
            if e.billable and e.id not in invoiced
        ]
        if client_id:
            entries = [e for e in entries if e.board_id == client_id]
        if date_range:
            start = date_range.get("start", "")
            end = date_range.get("end", "")
            if start:
                entries = [e for e in entries if e.started_at >= start]
            if end:
                entries = [e for e in entries if e.started_at <= end + "Z"]

        total_seconds = sum(e.duration_seconds for e in entries)
        total_hours = round(total_seconds / 3600.0, 4)

        # Per-project breakdown
        by_project: Dict[str, Dict[str, Any]] = {}
        for entry in entries:
            proj = entry.board_id or "unassigned"
            if proj not in by_project:
                by_project[proj] = {"hours": 0.0, "entries_count": 0}
            by_project[proj]["hours"] = round(
                by_project[proj]["hours"] + entry.duration_seconds / 3600.0, 4
            )
            by_project[proj]["entries_count"] += 1

        # Estimated amount using client or default rate
        rate_info = (
            self._client_rates.get(client_id, {})
            if client_id
            else {}
        )
        rate = rate_info.get("rate", self._default_rate)
        estimated_amount = round(total_hours * rate, 2)

        return {
            "client_id": client_id,
            "total_hours": total_hours,
            "entries_count": len(entries),
            "estimated_amount": estimated_amount,
            "currency": rate_info.get("currency", self._default_currency),
            "by_project": by_project,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_entries(self, entry_ids: List[str]) -> List[TimeEntry]:
        """Return entries for *entry_ids*; raises ``KeyError`` if missing."""
        result: List[TimeEntry] = []
        for eid in entry_ids:
            entry = self._entries.get(eid)
            if entry is None:
                raise KeyError(f"Entry {eid!r} not found")
            result.append(entry)
        return result

    def _effective_rate(
        self, client_id: str, override: Optional[float]
    ) -> float:
        if override is not None:
            return override
        return self._client_rates.get(client_id, {}).get(
            "rate", self._default_rate
        )

    def _build_line_items(
        self, entries: List[TimeEntry], rate: float
    ) -> List[Dict[str, Any]]:
        """Aggregate entries by project and build line items."""
        projects: Dict[str, float] = {}
        for entry in entries:
            proj = entry.board_id or "General"
            projects[proj] = projects.get(proj, 0.0) + entry.duration_seconds / 3600.0

        items: List[Dict[str, Any]] = []
        for proj, hours in sorted(projects.items()):
            items.append(
                {
                    "description": f"Time tracking — {proj}",
                    "project": proj,
                    "hours": round(hours, 4),
                    "unit_price": rate,
                    "amount": round(hours * rate, 2),
                }
            )
        return items
