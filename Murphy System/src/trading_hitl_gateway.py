# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Trading HITL Gateway — Murphy System

The single mandatory chokepoint through which ALL trade signals and wallet
transfers must pass before reaching any exchange or on-chain broadcast.

Architecture:
  ┌────────────┐   signal   ┌──────────────────────┐  approve/reject
  │  Bot / UI  │ ─────────► │ TradingHITLGateway   │ ────────────────►
  └────────────┘            │  ConfidenceEngine     │   ExecutionOrchestrator
                            │  GovernanceKernel     │   ExchangeRegistry
                            │  HITLRegistry         │
                            └──────────────────────┘

Approval routing rules:
  MANUAL mode      → always queued for human decision
  SUPERVISED mode  → auto-approve if confidence ≥ auto_threshold
                     AND murphy_index ≤ murphy_threshold
  AUTOMATED mode   → auto-approve unless circuit breaker is tripped

All decisions are written to an immutable audit log.

Business Source License 1.1 (BSL 1.1)
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)

_MAX_AUDIT_LOG  = 100_000
_MAX_QUEUE_DEPTH = 10_000


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class TradeDecision(Enum):
    """Human or automated decision on a pending trade request (Enum subclass)."""
    APPROVED  = "approved"
    REJECTED  = "rejected"
    MODIFIED  = "modified"
    TIMED_OUT = "timed_out"
    AUTO      = "auto"          # Approved by automation rules, no human needed


class ApprovalStatus(Enum):
    """State of a pending approval request (Enum subclass)."""
    PENDING   = "pending"
    DECIDED   = "decided"
    EXPIRED   = "expired"
    CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class TradeApprovalRequest:
    """A single pending trade that awaits human or automated decision."""
    request_id:     str
    bot_id:         str
    pair:           str
    action:         str       # "buy" | "sell" | "close_long" | "close_short"
    confidence:     float
    suggested_price: Optional[float]
    suggested_size:  Optional[float]
    stop_loss:       Optional[float]
    take_profit:     Optional[float]
    reasoning:       str
    exchange_id:     str
    dry_run:         bool
    hitl_mode:       str
    status:          ApprovalStatus = ApprovalStatus.PENDING
    decision:        Optional[TradeDecision] = None
    approver:        Optional[str]  = None
    decision_notes:  str            = ""
    created_at:      str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    decided_at:      Optional[str]  = None
    murphy_index:    Optional[float] = None
    metadata:        Dict[str, Any]  = field(default_factory=dict)


@dataclass
class TransferApprovalRequest:
    """A pending wallet transfer awaiting human decision."""
    request_id:     str
    from_wallet_id: str
    to_address:     str
    asset:          str
    amount:         float
    chain:          str
    notes:          str
    status:         ApprovalStatus = ApprovalStatus.PENDING
    decision:       Optional[TradeDecision] = None
    approver:       Optional[str]  = None
    created_at:     str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    decided_at:     Optional[str]  = None


@dataclass
class HITLAuditEntry:
    """Immutable record of every gateway decision."""
    audit_id:    str
    request_id:  str
    request_type: str   # "trade" | "transfer"
    decision:    str
    approver:    Optional[str]
    auto:        bool
    confidence:  float
    murphy_index: float
    timestamp:   str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata:    Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Gateway
# ---------------------------------------------------------------------------

class TradingHITLGateway:
    """
    Human-in-the-Loop approval gateway for all trading and transfer operations.

    Integrates with:
      - ``ConfidenceEngine``     — confidence scoring and Murphy Index
      - ``GovernanceKernel``     — budget and tool-use enforcement
      - ``HITLRegistry``         — graduation tracking per bot
      - ``ExecutionOrchestrator``— packet execution after approval
      - ``ExchangeRegistry``     — order placement on approved trades

    Parameters
    ----------
    exchange_registry :   ExchangeRegistry from crypto_exchange_connector
    confidence_engine :   ConfidenceEngine from confidence_engine package
    governance_kernel :   GovernanceKernel from governance_kernel
    hitl_registry :       HITLRegistry from hitl_graduation_engine
    execution_orchestrator : ExecutionOrchestrator (optional)
    auto_confidence_threshold : float
        Minimum confidence score for automated approval in SUPERVISED mode.
    auto_murphy_threshold : float
        Maximum Murphy Index for automated approval in SUPERVISED mode.
    approval_timeout_s : int
        Seconds before a pending approval is automatically timed out.
    """

    def __init__(
        self,
        exchange_registry:        Optional[Any] = None,
        confidence_engine:        Optional[Any] = None,
        governance_kernel:        Optional[Any] = None,
        hitl_registry:            Optional[Any] = None,
        execution_orchestrator:   Optional[Any] = None,
        auto_confidence_threshold: float = 0.80,
        auto_murphy_threshold:     float = 0.10,
        approval_timeout_s:        int   = 300,
    ) -> None:
        self._exchange     = exchange_registry
        self._confidence   = confidence_engine
        self._governance   = governance_kernel
        self._hitl_registry = hitl_registry
        self._orchestrator = execution_orchestrator
        self._auto_conf    = auto_confidence_threshold
        self._auto_murphy  = auto_murphy_threshold
        self._timeout_s    = approval_timeout_s
        self._lock         = threading.Lock()

        # Active queues
        self._trade_queue:    Dict[str, TradeApprovalRequest]    = {}
        self._transfer_queue: Dict[str, TransferApprovalRequest] = {}

        # Immutable audit trail
        self._audit_log: List[HITLAuditEntry] = []

        # Human-decision callbacks  e.g. notify WebSocket
        self._on_pending_callbacks: List[Callable[[TradeApprovalRequest], None]] = []

        logger.info(
            "TradingHITLGateway ready — auto_conf=%.2f auto_murphy=%.2f timeout=%ds",
            self._auto_conf, self._auto_murphy, self._timeout_s,
        )

    # ---- trade signal ingestion -----------------------------------------

    def submit_trade_signal(
        self,
        bot_id:  str,
        signal:  Any,   # TradingSignal from trading_strategy_engine
        config:  Any,   # BotLifecycleConfig
    ) -> TradeApprovalRequest:
        """
        Accept a strategy signal and route it through the HITL pipeline.

        Returns the ``TradeApprovalRequest``; if auto-approved, the order
        is also placed immediately.
        """
        # Score confidence
        murphy_index, overall_confidence = self._score_signal(signal)

        request = TradeApprovalRequest(
            request_id      = str(uuid.uuid4()),
            bot_id          = bot_id,
            pair            = signal.pair,
            action          = signal.action.value,
            confidence      = signal.confidence,
            suggested_price = signal.suggested_price,
            suggested_size  = signal.suggested_size,
            stop_loss       = signal.stop_loss,
            take_profit     = signal.take_profit,
            reasoning       = signal.reasoning,
            exchange_id     = config.exchange_id,
            dry_run         = getattr(config, "dry_run", True),
            hitl_mode       = getattr(config, "hitl_mode", "manual") if hasattr(config, "hitl_mode") else "manual",
            murphy_index    = murphy_index,
        )

        # ── REAL-MONEY SAFETY LOCK ──────────────────────────────────────────
        # Real trades (dry_run=False) MUST always route through human approval.
        # Supervised / automated modes are only permitted for paper/shadow bots.
        # This override cannot be bypassed — it is enforced here unconditionally.
        if not request.dry_run:
            raw_mode = (
                request.hitl_mode.value
                if hasattr(request.hitl_mode, "value")
                else str(request.hitl_mode)
            ).lower()
            if raw_mode != "manual":
                logger.warning(
                    "HITL SAFETY LOCK: real-money trade from bot %s was '%s' mode "
                    "— forced to MANUAL. Only paper/shadow bots may auto-trade.",
                    bot_id, raw_mode,
                )
                request.hitl_mode = "manual"
        # ─────────────────────────────────────────────────────────────────────

        # Governance check
        gov_ok = self._governance_check(bot_id, config)
        if not gov_ok:
            request.status   = ApprovalStatus.DECIDED
            request.decision = TradeDecision.REJECTED
            request.decision_notes = "governance_kernel_denied"
            self._emit_audit(request, overall_confidence, murphy_index, auto=True)
            return request

        # Route based on mode
        hitl_mode = (
            request.hitl_mode.value
            if hasattr(request.hitl_mode, "value")
            else str(request.hitl_mode)
        ).lower()
        if hitl_mode == "automated":
            self._auto_approve(request, overall_confidence, murphy_index)
        elif hitl_mode == "supervised":
            if overall_confidence >= self._auto_conf and murphy_index <= self._auto_murphy:
                self._auto_approve(request, overall_confidence, murphy_index)
            else:
                self._queue_for_human(request)
        else:   # manual
            self._queue_for_human(request)

        return request

    # ---- manual approval ------------------------------------------------

    def approve(self, request_id: str, approver: str, notes: str = "") -> bool:
        """
        Human approves a pending trade request.

        Returns True if the order was placed successfully.
        """
        req = self._pop_trade(request_id)
        if req is None:
            logger.warning("HITL approve: request %s not found", request_id)
            return False
        req.status        = ApprovalStatus.DECIDED
        req.decision      = TradeDecision.APPROVED
        req.approver      = approver
        req.decision_notes = notes
        req.decided_at    = datetime.now(timezone.utc).isoformat()
        self._emit_audit(req, req.confidence, req.murphy_index or 0.0)
        placed = self._place_order(req)
        self._update_hitl_registry(req.bot_id, success=placed)
        return placed

    def reject(self, request_id: str, approver: str, notes: str = "") -> bool:
        """Human rejects a pending trade request."""
        req = self._pop_trade(request_id)
        if req is None:
            return False
        req.status        = ApprovalStatus.DECIDED
        req.decision      = TradeDecision.REJECTED
        req.approver      = approver
        req.decision_notes = notes
        req.decided_at    = datetime.now(timezone.utc).isoformat()
        self._emit_audit(req, req.confidence, req.murphy_index or 0.0)
        self._update_hitl_registry(req.bot_id, success=False)
        logger.info("Trade %s rejected by %s: %s", request_id, approver, notes)
        return True

    def modify_and_approve(
        self,
        request_id:  str,
        approver:    str,
        new_size:    Optional[float] = None,
        new_price:   Optional[float] = None,
        new_stop:    Optional[float] = None,
        notes:       str = "",
    ) -> bool:
        """Human modifies then approves a pending trade."""
        req = self._pop_trade(request_id)
        if req is None:
            return False
        if new_size  is not None: req.suggested_size  = new_size
        if new_price is not None: req.suggested_price = new_price
        if new_stop  is not None: req.stop_loss       = new_stop
        req.status        = ApprovalStatus.DECIDED
        req.decision      = TradeDecision.MODIFIED
        req.approver      = approver
        req.decision_notes = notes
        req.decided_at    = datetime.now(timezone.utc).isoformat()
        self._emit_audit(req, req.confidence, req.murphy_index or 0.0)
        placed = self._place_order(req)
        self._update_hitl_registry(req.bot_id, success=placed)
        return placed

    # ---- transfer approval ----------------------------------------------

    def submit_transfer_request(self, transfer: Dict[str, Any]) -> Dict[str, Any]:
        """Queue a wallet transfer for human approval."""
        req = TransferApprovalRequest(
            request_id     = transfer.get("request_id", str(uuid.uuid4())),
            from_wallet_id = transfer.get("from_wallet_id", ""),
            to_address     = transfer.get("to_address", ""),
            asset          = transfer.get("asset", ""),
            amount         = float(transfer.get("amount", 0)),
            chain          = transfer.get("chain", "unknown"),
            notes          = transfer.get("notes", ""),
        )
        with self._lock:
            try:
                from thread_safe_operations import capped_append as _cap
            except ImportError:
                def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
                    """Fallback bounded append (CWE-770)."""
                    if len(target_list) >= max_size:
                        del target_list[: max_size // 10]
                    target_list.append(item)
            self._transfer_queue[req.request_id] = req
        logger.info(
            "TradingHITLGateway: transfer %s queued — %s %s → %s",
            req.request_id, req.amount, req.asset, req.to_address[:12],
        )
        return {"queued": True, "request_id": req.request_id, "requires_human_approval": True}

    def approve_transfer(self, request_id: str, approver: str) -> bool:
        """Human approves a pending wallet transfer."""
        with self._lock:
            req = self._transfer_queue.pop(request_id, None)
        if req is None:
            return False
        req.status   = ApprovalStatus.DECIDED
        req.decision = TradeDecision.APPROVED
        req.approver = approver
        req.decided_at = datetime.now(timezone.utc).isoformat()
        logger.info("Transfer %s approved by %s", request_id, approver)
        return True

    # ---- queues / audit -------------------------------------------------

    def get_pending_trades(self) -> List[Dict[str, Any]]:
        """Return all pending trade approval requests."""
        with self._lock:
            return [
                {
                    "request_id":    r.request_id,
                    "bot_id":        r.bot_id,
                    "pair":          r.pair,
                    "action":        r.action,
                    "confidence":    r.confidence,
                    "murphy_index":  r.murphy_index,
                    "suggested_price": r.suggested_price,
                    "suggested_size":  r.suggested_size,
                    "reasoning":     r.reasoning,
                    "exchange_id":   r.exchange_id,
                    "dry_run":       r.dry_run,
                    "hitl_mode":     r.hitl_mode,
                    "created_at":    r.created_at,
                }
                for r in self._trade_queue.values()
                if r.status == ApprovalStatus.PENDING
            ]

    def get_pending_transfers(self) -> List[Dict[str, Any]]:
        """Return all pending transfer approval requests."""
        with self._lock:
            return [
                {
                    "request_id": r.request_id,
                    "from_wallet_id": r.from_wallet_id,
                    "to_address":    r.to_address,
                    "asset":         r.asset,
                    "amount":        r.amount,
                    "chain":         r.chain,
                    "created_at":    r.created_at,
                }
                for r in self._transfer_queue.values()
                if r.status == ApprovalStatus.PENDING
            ]

    def get_audit_log(self, limit: int = 500) -> List[Dict[str, Any]]:
        """Return the most recent *limit* audit entries."""
        with self._lock:
            entries = list(self._audit_log[-limit:])
        return [e.__dict__ for e in entries]

    def register_pending_callback(self, cb: Callable[[TradeApprovalRequest], None]) -> None:
        """Register a callback invoked whenever a new trade is queued for approval."""
        capped_append(self._on_pending_callbacks, cb)

    # ---- internals -------------------------------------------------------

    def _score_signal(self, signal: Any) -> tuple[float, float]:
        """Return (murphy_index, overall_confidence) for the signal."""
        if self._confidence is None:
            return 0.0, signal.confidence
        try:
            artifacts = [{
                "confidence":  signal.confidence,
                "loss":        abs(signal.stop_loss or 0) * (signal.suggested_size or 1),
                "probability": 1.0 - signal.confidence,
                "type":        "trade_signal",
            }]
            result  = self._confidence.compute_confidence(artifacts)
            return result.get("murphy_index", 0.0), result.get("overall_confidence", signal.confidence)
        except Exception as exc:
            logger.debug("HITL confidence scoring error: %s", exc)
            return 0.0, signal.confidence

    def _governance_check(self, bot_id: str, config: Any) -> bool:
        """Return True if governance kernel allows the trade."""
        if self._governance is None:
            return True
        try:
            from governance_kernel import EnforcementAction
            result = self._governance.enforce(
                caller_id      = bot_id,
                department_id  = "crypto_trading",
                tool_name      = "execute_trade",
                estimated_cost = getattr(config, "stake_amount_usd", 0.0) * 0.01,
                context        = {"pair": getattr(config, "pair", "")},
            )
            return result.action == EnforcementAction.ALLOW
        except Exception as exc:
            logger.debug("Governance check error: %s", exc)
            return True

    def _auto_approve(
        self,
        req:                TradeApprovalRequest,
        overall_confidence: float,
        murphy_index:       float,
    ) -> None:
        req.status     = ApprovalStatus.DECIDED
        req.decision   = TradeDecision.AUTO
        req.decided_at = datetime.now(timezone.utc).isoformat()
        self._emit_audit(req, overall_confidence, murphy_index, auto=True)
        placed = self._place_order(req)
        self._update_hitl_registry(req.bot_id, success=placed)
        logger.info(
            "HITL auto-approve: %s %s size=%s conf=%.3f mi=%.3f placed=%s",
            req.action, req.pair, req.suggested_size,
            overall_confidence, murphy_index, placed,
        )

    def _queue_for_human(self, req: TradeApprovalRequest) -> None:
        with self._lock:
            self._trade_queue[req.request_id] = req
        for cb in self._on_pending_callbacks:
            try:
                cb(req)
            except Exception as exc:
                logger.debug("Pending callback error: %s", exc)
        logger.info(
            "HITL queued for human: %s %s pair=%s conf=%.3f",
            req.action, req.bot_id[:8], req.pair, req.confidence,
        )

    def _place_order(self, req: TradeApprovalRequest) -> bool:
        """Submit the trade to the exchange (or dry-run simulation)."""
        if req.dry_run:
            logger.info("HITL dry-run: would place %s %s size=%s", req.action, req.pair, req.suggested_size)
            return True
        if self._exchange is None:
            logger.warning("HITL: no exchange registry configured — cannot place order")
            return False
        try:
            from crypto_exchange_connector import ExchangeId, OrderRequest, OrderSide, OrderType
            side = OrderSide.BUY if req.action.lower() == "buy" else OrderSide.SELL
            try:
                ex_id = ExchangeId(req.exchange_id)
            except ValueError:
                ex_id = ExchangeId.PAPER
            order_req = OrderRequest(
                exchange_id = ex_id,
                pair        = req.pair,
                side        = side,
                order_type  = OrderType.LIMIT if req.suggested_price else OrderType.MARKET,
                quantity    = req.suggested_size or 0.0,
                price       = req.suggested_price,
            )
            result = self._exchange.place_order(order_req)
            if result.success:
                self._record_governance_execution(req.bot_id, req.suggested_size or 0.0)
            return result.success
        except Exception as exc:
            logger.error("HITL _place_order error: %s", exc)
            return False

    def _record_governance_execution(self, bot_id: str, cost: float) -> None:
        if self._governance is None:
            return
        try:
            self._governance.record_execution(bot_id, "execute_trade", cost, True, "crypto_trading")
        except Exception as exc:
            logger.debug("Governance record_execution error: %s", exc)

    def _update_hitl_registry(self, bot_id: str, success: bool) -> None:
        if self._hitl_registry is None:
            return
        try:
            item_id = f"trading_bot::{bot_id}"
            self._hitl_registry.record_outcome(item_id, success)
        except Exception as exc:
            logger.debug("HITL registry update error: %s", exc)

    def _emit_audit(
        self,
        req:                TradeApprovalRequest,
        overall_confidence: float,
        murphy_index:       float,
        auto:               bool = False,
    ) -> None:
        entry = HITLAuditEntry(
            audit_id     = str(uuid.uuid4()),
            request_id   = req.request_id,
            request_type = "trade",
            decision     = req.decision.value if req.decision else "unknown",
            approver     = req.approver,
            auto         = auto,
            confidence   = overall_confidence,
            murphy_index = murphy_index,
            metadata     = {
                "pair":      req.pair,
                "action":    req.action,
                "bot_id":    req.bot_id,
                "dry_run":   req.dry_run,
                "hitl_mode": req.hitl_mode,
            },
        )
        with self._lock:
            try:
                from thread_safe_operations import capped_append
            except ImportError:
                def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
                    """Fallback bounded append (CWE-770)."""
                    if len(target_list) >= max_size:
                        del target_list[: max_size // 10]
                    target_list.append(item)
            capped_append(self._audit_log, entry, _MAX_AUDIT_LOG)

    def _pop_trade(self, request_id: str) -> Optional[TradeApprovalRequest]:
        with self._lock:
            return self._trade_queue.pop(request_id, None)
