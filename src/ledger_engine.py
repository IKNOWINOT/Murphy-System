"""
ledger_engine.py — Murphy System
PATCH-097f — Part 2 of 3

THE DEPLOYMENT LEDGER

Three phases. No exceptions.

  PHASE 1 — ESTIMATE
    Negotiated before any deployment is commissioned.
    Not a guess. A promise.
    What this deployment will cost. What it will provide.
    What the expected net is. Why that estimate is defensible.
    This becomes the expected result that causality tests at succession.

  PHASE 2 — LIVE
    Actual costs incurred. Actual provisions delivered.
    Real signals. Real accounting.
    The estimate is held alongside the actual at every step.
    Neither is hidden from the other.

  PHASE 3 — RECONCILE
    At succession: actual vs estimated. Honest delta.
    If positive — ledger advances. Successor inherits clean books.
    If negative — the delta becomes the successor's PRIMARY OBLIGATION.
    Not optional. Not aspirational.
    The 10:1 standard: for every unit of net harm,
    ten units of improvement are owed before positive net can be claimed.

DEFERRED OBLIGATIONS
    The resource is not yet present. The commitment is genuine.
    Record the obligation now. Execute when resource allows.
    The obligation does not disappear because resource is absent.
    Cannot claim provision credit for deferred commitments.
    The tree that will be planted is not the tree that was planted.

THE LEDGER CANNOT BE RESET. IT CAN ONLY BE PAID FORWARD.

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ENUMS
# ---------------------------------------------------------------------------

class LedgerPhase(str, Enum):
    ESTIMATE   = "estimate"    # negotiated before commissioning
    LIVE       = "live"        # accumulating during execution
    RECONCILED = "reconciled"  # actual vs estimate settled at succession
    DEFERRED   = "deferred"    # obligation recorded, resource not yet present


class LedgerVerdict(str, Enum):
    POSITIVE  = "positive"   # provision exceeded cost
    NEUTRAL   = "neutral"    # within tolerance — no debt, no credit
    NEGATIVE  = "negative"   # cost exceeded provision — debt owed
    DEFERRED  = "deferred"   # commitment genuine, execution pending resource


# ---------------------------------------------------------------------------
# LEDGER ENTRY
# ---------------------------------------------------------------------------

@dataclass
class LedgerEntry:
    """
    One deployment's full accounting — from estimate through succession.

    The estimate is the promise made at commissioning.
    The actual is what happened.
    The delta is what the successor inherits.
    """
    entry_id:            str  = field(default_factory=lambda: str(uuid.uuid4())[:12])
    deployment_id:       str  = ""
    deployment_desc:     str  = ""
    domain:              str  = ""
    phase:               LedgerPhase = LedgerPhase.ESTIMATE

    # Phase 1 — Estimate
    est_cost:            str  = ""   # what this is expected to cost
    est_provision:       str  = ""   # what this is expected to provide
    est_net:             str  = ""   # expected net — stated plainly
    est_rationale:       str  = ""   # why this estimate is defensible
    estimated_at:        str  = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Phase 2 — Live
    actual_costs:        List[Dict] = field(default_factory=list)
    actual_provisions:   List[Dict] = field(default_factory=list)
    net_delta:           float = 0.0
    execution_started:   Optional[str] = None

    # Phase 3 — Reconcile
    verdict:             Optional[LedgerVerdict] = None
    debt_owed:           float = 0.0
    ten_x_obligation:    float = 0.0
    successor_id:        Optional[str] = None
    reconciled_at:       Optional[str] = None
    reconcile_note:      str  = ""

    # Deferred obligations
    deferred_items:      List[Dict] = field(default_factory=list)

    def start(self):
        self.phase = LedgerPhase.LIVE
        self.execution_started = datetime.now(timezone.utc).isoformat()

    def cost(self, description: str, magnitude: float = 0.0):
        """Record an actual cost incurred during execution."""
        self.actual_costs.append({
            "desc": description,
            "magnitude": magnitude,
            "at": datetime.now(timezone.utc).isoformat(),
        })
        self.net_delta -= magnitude

    def provision(self, description: str, magnitude: float = 0.0):
        """Record an actual provision delivered during execution."""
        self.actual_provisions.append({
            "desc": description,
            "magnitude": magnitude,
            "at": datetime.now(timezone.utc).isoformat(),
        })
        self.net_delta += magnitude

    def defer(self, obligation: str, trigger_condition: str, magnitude: float = 0.0):
        """
        Record a deferred obligation.
        The commitment is genuine. The resource is not yet present.
        Cannot claim credit. The obligation accumulates until paid.
        """
        self.deferred_items.append({
            "obligation":        obligation,
            "trigger_condition": trigger_condition,
            "magnitude":         magnitude,
            "note":              "Cannot claim provision credit until executed.",
            "recorded_at":       datetime.now(timezone.utc).isoformat(),
            "status":            "outstanding",
        })
        logger.info("Deferred obligation recorded: %s (trigger: %s)", obligation, trigger_condition)

    def reconcile(self, successor_id: str = None) -> LedgerVerdict:
        """
        Close this deployment. Compare actual to estimate. Set verdict.
        If negative — register debt for successor at 10:1.
        """
        self.phase        = LedgerPhase.RECONCILED
        self.reconciled_at = datetime.now(timezone.utc).isoformat()
        self.successor_id  = successor_id

        if self.net_delta > 0.05:
            self.verdict = LedgerVerdict.POSITIVE
            self.debt_owed = 0.0
            self.ten_x_obligation = 0.0
        elif self.net_delta >= -0.05:
            self.verdict = LedgerVerdict.NEUTRAL
            self.debt_owed = 0.0
            self.ten_x_obligation = 0.0
        else:
            self.verdict = LedgerVerdict.NEGATIVE
            self.debt_owed = abs(self.net_delta)
            self.ten_x_obligation = self.debt_owed * 10.0  # 10:1 standard

        deferred_note = (
            f" {len(self.deferred_items)} deferred obligation(s) outstanding."
            if self.deferred_items else ""
        )
        debt_note = (
            f" Debt: {self.debt_owed:.3f} → successor owes {self.ten_x_obligation:.3f} (10:1)."
            if self.debt_owed > 0 else " No debt carried forward."
        )

        self.reconcile_note = (
            f"Net delta: {self.net_delta:+.3f}. "
            f"Verdict: {self.verdict.value}."
            + debt_note
            + deferred_note
        )

        if self.debt_owed > 0:
            logger.warning(
                "Ledger debt: %.3f — successor %s owes %.3f (10:1)",
                self.debt_owed, successor_id, self.ten_x_obligation
            )
        else:
            logger.info("Ledger reconciled: %s — %s", self.verdict.value, self.reconcile_note)

        return self.verdict

    def to_dict(self) -> Dict:
        return {
            "entry_id":          self.entry_id,
            "deployment_id":     self.deployment_id,
            "deployment_desc":   self.deployment_desc,
            "domain":            self.domain,
            "phase":             self.phase.value,
            "estimate": {
                "cost":       self.est_cost,
                "provision":  self.est_provision,
                "net":        self.est_net,
                "rationale":  self.est_rationale,
                "at":         self.estimated_at,
            },
            "actual": {
                "costs":      self.actual_costs,
                "provisions": self.actual_provisions,
                "net_delta":  round(self.net_delta, 4),
            },
            "reconciliation": {
                "verdict":           self.verdict.value if self.verdict else None,
                "debt_owed":         round(self.debt_owed, 4),
                "ten_x_obligation":  round(self.ten_x_obligation, 4),
                "successor_id":      self.successor_id,
                "note":              self.reconcile_note,
                "at":                self.reconciled_at,
            },
            "deferred": self.deferred_items,
        }


# ---------------------------------------------------------------------------
# LEDGER ENGINE
# ---------------------------------------------------------------------------

class LedgerEngine:
    """
    Manages the full deployment ledger lifecycle.

    Rules:
    1. Every deployment opens an estimate before commissioning.
    2. Execution records actual costs and provisions as they occur.
    3. Reconciliation at succession is mandatory — honest delta always.
    4. Negative net becomes the successor's primary obligation.
    5. The 10:1 standard applies — ten units of improvement per unit of harm.
    6. Deferred obligations are real. Record now. Execute when resource allows.
    7. Cannot claim credit for deferred commitments.
    8. The ledger cannot be reset. It can only be paid forward.
    """

    TEN_TO_ONE = 10.0

    def __init__(self):
        self._entries:  Dict[str, LedgerEntry] = {}
        self._debts:    List[Dict] = []

    # ------------------------------------------------------------------
    # Phase 1 — open estimate
    # ------------------------------------------------------------------

    def open_estimate(
        self,
        deployment_id:  str,
        deployment_desc:str,
        domain:         str,
        est_cost:       str,
        est_provision:  str,
        est_net:        str,
        est_rationale:  str,
    ) -> LedgerEntry:
        """
        Negotiate and record the pre-deployment estimate.
        This is the commitment. Causality will test actual against it.
        """
        entry = LedgerEntry(
            deployment_id  = deployment_id,
            deployment_desc= deployment_desc,
            domain         = domain,
            est_cost       = est_cost,
            est_provision  = est_provision,
            est_net        = est_net,
            est_rationale  = est_rationale,
        )
        self._entries[entry.entry_id] = entry
        logger.info("Ledger estimate opened: %s [%s]", deployment_id, domain)
        return entry

    # ------------------------------------------------------------------
    # Phase 3 — reconcile at succession
    # ------------------------------------------------------------------

    def reconcile(self, entry_id: str, successor_id: str = None) -> Dict:
        """
        Close the deployment. Compute verdict. Register debt if negative.
        The successor's first commissioning check: what did I inherit?
        """
        if entry_id not in self._entries:
            return {"error": f"Entry {entry_id} not found"}

        entry   = self._entries[entry_id]
        verdict = entry.reconcile(successor_id)

        if entry.debt_owed > 0:
            self._debts.append({
                "debt_id":       str(uuid.uuid4())[:8],
                "from_entry":    entry_id,
                "from_deploy":   entry.deployment_id,
                "to_successor":  successor_id,
                "debt":          round(entry.debt_owed, 4),
                "ten_x_owed":    round(entry.ten_x_obligation, 4),
                "verdict":       verdict.value,
                "registered_at": datetime.now(timezone.utc).isoformat(),
                "status":        "outstanding",
                "note": (
                    f"Successor {successor_id} must demonstrate "
                    f"{entry.ten_x_obligation:.3f} units of improvement "
                    f"before claiming positive net. This is the first item "
                    f"on the commissioning checklist."
                ),
            })

        return entry.to_dict()

    # ------------------------------------------------------------------
    # Deferred obligations summary
    # ------------------------------------------------------------------

    def all_deferred(self) -> Dict:
        """All outstanding deferred obligations across all entries."""
        deferred = []
        for e in self._entries.values():
            for d in e.deferred_items:
                if d["status"] == "outstanding":
                    deferred.append({
                        "deployment": e.deployment_id,
                        **d,
                    })
        return {
            "count":  len(deferred),
            "note":   "Cannot claim provision credit until these are executed.",
            "principle": "The tree that will be planted is not the tree that was planted.",
            "items":  deferred,
        }

    # ------------------------------------------------------------------
    # Outstanding debts
    # ------------------------------------------------------------------

    def outstanding_debts(self) -> Dict:
        outstanding = [d for d in self._debts if d["status"] == "outstanding"]
        return {
            "count":       len(outstanding),
            "total_debt":  round(sum(d["debt"] for d in outstanding), 4),
            "total_10x":   round(sum(d["ten_x_owed"] for d in outstanding), 4),
            "principle":   "10:1 — for every unit of harm, ten units of improvement owed.",
            "rule":        "Negative net becomes the successor's primary obligation. Cannot be bypassed.",
            "debts":       outstanding,
        }

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def status(self) -> Dict:
        total     = len(self._entries)
        by_phase  = {}
        by_verdict= {}
        for e in self._entries.values():
            by_phase[e.phase.value] = by_phase.get(e.phase.value, 0) + 1
            if e.verdict:
                by_verdict[e.verdict.value] = by_verdict.get(e.verdict.value, 0) + 1

        debts    = self.outstanding_debts()
        deferred = self.all_deferred()

        return {
            "layer":             "LedgerEngine",
            "active":            True,
            "phases":            ["estimate", "live", "reconcile", "inherit"],
            "ten_to_one":        "For every unit of harm, ten units of improvement owed.",
            "deferred_rule":     "Cannot claim credit for deferred commitments.",
            "reset_rule":        "The ledger cannot be reset. It can only be paid forward.",
            "entries_total":     total,
            "by_phase":          by_phase,
            "by_verdict":        by_verdict,
            "outstanding_debts": debts["count"],
            "total_debt":        debts["total_debt"],
            "total_10x_owed":    debts["total_10x"],
            "deferred_items":    deferred["count"],
        }


# ---------------------------------------------------------------------------
# GLOBAL INSTANCE
# ---------------------------------------------------------------------------

ledger_engine = LedgerEngine()
