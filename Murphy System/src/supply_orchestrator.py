"""
Supply Orchestrator for Murphy System Runtime

Wires together WingmanProtocol, TelemetryAdapter, and GoldenPathBridge to
manage supply chain monitoring and automated reorder recommendations.

Key capabilities:
- Item registration with configurable reorder points and lead times
- Consumption tracking with automatic reorder triggering
- Receipt recording to update current stock
- Days-remaining estimation from rolling consumption average
- Pending order management
- Thread-safe operation

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from golden_path_bridge import GoldenPathBridge
from telemetry_adapter import TelemetryAdapter
from wingman_protocol import (
    ExecutionRunbook,
    ValidationRule,
    ValidationSeverity,
    WingmanProtocol,
)

logger = logging.getLogger(__name__)

_SUPPLY_RUNBOOK_ID = "supply_chain"
# Multiplier applied to lead_time_days to determine early-reorder warning threshold
_LEAD_TIME_BUFFER_MULTIPLIER: float = 1.5


def _build_supply_runbook() -> ExecutionRunbook:
    """Create the supply-chain validation runbook."""
    return ExecutionRunbook(
        runbook_id=_SUPPLY_RUNBOOK_ID,
        name="Supply Chain Runbook",
        domain="supply_chain",
        validation_rules=[
            ValidationRule(
                rule_id="check_has_output",
                description="Supply transaction must contain a non-empty result",
                check_fn_name="check_has_output",
                severity=ValidationSeverity.BLOCK,
                applicable_domains=["supply_chain"],
            ),
            ValidationRule(
                rule_id="check_confidence_threshold",
                description="Transaction confidence must meet minimum threshold",
                check_fn_name="check_confidence_threshold",
                severity=ValidationSeverity.WARN,
                applicable_domains=["supply_chain"],
            ),
        ],
    )


def _compute_daily_consumption(usage_log: List[Dict[str, Any]]) -> float:
    """Estimate average daily consumption from *usage_log*."""
    if not usage_log:
        return 0.0
    total_qty = sum(entry["quantity"] for entry in usage_log)
    return total_qty / (len(usage_log) or 1)


class SupplyOrchestrator:
    """Manages supply chain monitoring and automated ordering.

    Starts working immediately — learns reorder points from history.
    Wires WingmanProtocol + TelemetryAdapter + GoldenPathBridge.
    """

    def __init__(
        self,
        wingman_protocol: Optional[WingmanProtocol] = None,
        telemetry: Optional[TelemetryAdapter] = None,
        golden_paths: Optional[GoldenPathBridge] = None,
    ) -> None:
        self._lock = threading.Lock()
        self.wingman = wingman_protocol or WingmanProtocol()
        self.telemetry = telemetry or TelemetryAdapter()
        self.golden_paths = golden_paths or GoldenPathBridge()

        # item metadata indexed by item_id
        self._items: Dict[str, Dict[str, Any]] = {}
        # usage log per item_id
        self._usage_log: Dict[str, List[Dict[str, Any]]] = {}
        # receipt log per item_id
        self._receipt_log: Dict[str, List[Dict[str, Any]]] = {}
        # pending orders: {order_id: {item_id, qty, triggered_at, status}}
        self._pending_orders: Dict[str, Dict[str, Any]] = {}
        # wingman pair_id for supply validation
        self._pair_id: Optional[str] = None

        self._setup()

    def _setup(self) -> None:
        """Register the supply runbook and create a validation pair."""
        runbook = _build_supply_runbook()
        self.wingman.register_runbook(runbook)
        pair = self.wingman.create_pair(
            subject="supply_chain",
            executor_id="supply_sensor",
            validator_id="supply_validator",
            runbook_id=runbook.runbook_id,
        )
        with self._lock:
            self._pair_id = pair.pair_id
        logger.info("SupplyOrchestrator ready (pair=%s)", pair.pair_id)

    # ------------------------------------------------------------------
    # Item registration
    # ------------------------------------------------------------------

    def register_item(
        self,
        item_id: str,
        name: str,
        unit: str,
        reorder_point: float,
        reorder_qty: float,
        lead_time_days: int = 7,
    ) -> Dict[str, Any]:
        """Register a new inventory item.

        Returns a dict with registration status and item details.
        """
        item: Dict[str, Any] = {
            "item_id": item_id,
            "name": name,
            "unit": unit,
            "reorder_point": reorder_point,
            "reorder_qty": reorder_qty,
            "lead_time_days": lead_time_days,
            "current_stock": 0.0,
            "registered_at": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            self._items[item_id] = item
            self._usage_log[item_id] = []
            self._receipt_log[item_id] = []

        self.golden_paths.record_success(
            task_pattern=f"register_item_{item_id}",
            domain="supply_chain",
            execution_spec={"item_id": item_id, "name": name},
        )

        logger.info(
            "Registered supply item '%s' (%s) — reorder at %.2f %s",
            name, item_id, reorder_point, unit,
        )
        return {
            "registered": True,
            "item_id": item_id,
            "name": name,
            "unit": unit,
            "reorder_point": reorder_point,
            "reorder_qty": reorder_qty,
            "lead_time_days": lead_time_days,
        }

    # ------------------------------------------------------------------
    # Consumption tracking
    # ------------------------------------------------------------------

    def record_usage(self, item_id: str, quantity: float) -> Dict[str, Any]:
        """Track consumption of *quantity* units of *item_id*.

        Returns a dict with:
            recorded          – True on success
            current_stock     – stock remaining after this usage
            days_remaining    – estimated days of stock remaining
            reorder_triggered – True if stock dropped below reorder point
            recommendation    – human-readable action string
        """
        with self._lock:
            item = self._items.get(item_id)

        if item is None:
            return {
                "recorded": False,
                "current_stock": None,
                "days_remaining": None,
                "reorder_triggered": False,
                "recommendation": (
                    f"Item '{item_id}' is not registered. "
                    "Call register_item() before recording usage."
                ),
            }

        entry: Dict[str, Any] = {
            "quantity": quantity,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }

        with self._lock:
            item["current_stock"] = max(0.0, item["current_stock"] - quantity)
            self._usage_log[item_id].append(entry)
            current_stock: float = item["current_stock"]
            reorder_point: float = item["reorder_point"]
            reorder_qty: float = item["reorder_qty"]
            usage_log_copy = list(self._usage_log[item_id])

        daily_rate = _compute_daily_consumption(usage_log_copy)
        days_remaining = (
            current_stock / daily_rate if daily_rate > 0 else None
        )

        # Validate through wingman
        output = {
            "result": {
                "item_id": item_id,
                "quantity": quantity,
                "remaining": current_stock,
            }
        }
        self.wingman.validate_output(self._pair_id, output)

        reorder_triggered = current_stock <= reorder_point
        order_id: Optional[str] = None

        if reorder_triggered:
            order_id = f"ord-{uuid.uuid4().hex[:8]}"
            order: Dict[str, Any] = {
                "item_id": item_id,
                "item_name": item["name"],
                "quantity": reorder_qty,
                "unit": item["unit"],
                "triggered_at": datetime.now(timezone.utc).isoformat(),
                "status": "pending",
            }
            with self._lock:
                self._pending_orders[order_id] = order

            self.golden_paths.record_success(
                task_pattern=f"reorder_{item_id}",
                domain="supply_chain",
                execution_spec={"item_id": item_id, "order_qty": reorder_qty},
            )
            logger.info(
                "Reorder triggered for '%s' — order %s (qty=%.2f)",
                item["name"], order_id, reorder_qty,
            )

        self.telemetry.collect_metric(
            metric_type="system_events",
            metric_name=f"supply_usage_{item_id}",
            value=quantity,
            labels={"item_id": item_id, "reorder_triggered": str(reorder_triggered)},
        )

        if reorder_triggered:
            recommendation = (
                f"Stock for '{item['name']}' has reached or passed the reorder point "
                f"({current_stock:.2f} {item['unit']} remaining). "
                f"Order {reorder_qty:.2f} {item['unit']} has been queued (order {order_id}). "
                "Confirm with your supplier and update receipt when stock arrives."
            )
        elif days_remaining is not None and days_remaining < item["lead_time_days"] * _LEAD_TIME_BUFFER_MULTIPLIER:
            recommendation = (
                f"'{item['name']}' has approximately {days_remaining:.1f} days of stock remaining — "
                f"approaching lead time of {item['lead_time_days']} days. "
                "Consider placing an early order to avoid stock-out."
            )
        else:
            recommendation = (
                f"'{item['name']}' usage recorded. "
                f"Current stock: {current_stock:.2f} {item['unit']}. "
                "Stock levels are adequate."
            )

        return {
            "recorded": True,
            "current_stock": round(current_stock, 4),
            "days_remaining": round(days_remaining, 1) if days_remaining is not None else None,
            "reorder_triggered": reorder_triggered,
            "recommendation": recommendation,
        }

    # ------------------------------------------------------------------
    # Receipt recording
    # ------------------------------------------------------------------

    def record_receipt(
        self,
        item_id: str,
        quantity: float,
        order_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record receipt of *quantity* units for *item_id*.

        Returns a dict with updated stock level and status.
        """
        with self._lock:
            item = self._items.get(item_id)

        if item is None:
            return {
                "recorded": False,
                "current_stock": None,
                "recommendation": (
                    f"Item '{item_id}' is not registered. "
                    "Call register_item() before recording receipts."
                ),
            }

        receipt: Dict[str, Any] = {
            "quantity": quantity,
            "order_id": order_id,
            "received_at": datetime.now(timezone.utc).isoformat(),
        }

        with self._lock:
            item["current_stock"] += quantity
            self._receipt_log[item_id].append(receipt)
            current_stock: float = item["current_stock"]

            if order_id and order_id in self._pending_orders:
                self._pending_orders[order_id]["status"] = "received"

        self.telemetry.collect_metric(
            metric_type="system_events",
            metric_name=f"supply_receipt_{item_id}",
            value=quantity,
            labels={"item_id": item_id},
        )

        recommendation = (
            f"Received {quantity:.2f} {item['unit']} of '{item['name']}'. "
            f"Updated stock: {current_stock:.2f} {item['unit']}."
        )
        if order_id:
            recommendation += f" Order {order_id} marked as received."

        return {
            "recorded": True,
            "current_stock": round(current_stock, 4),
            "recommendation": recommendation,
        }

    # ------------------------------------------------------------------
    # Recommendations and dashboard
    # ------------------------------------------------------------------

    def get_reorder_recommendations(self) -> List[Dict[str, Any]]:
        """Return items approaching or past their reorder point with AI recommendation."""
        with self._lock:
            items_snapshot = {k: dict(v) for k, v in self._items.items()}
            usage_snapshot = {k: list(v) for k, v in self._usage_log.items()}

        recommendations: List[Dict[str, Any]] = []
        for item_id, item in items_snapshot.items():
            current_stock = item["current_stock"]
            reorder_point = item["reorder_point"]
            daily_rate = _compute_daily_consumption(usage_snapshot.get(item_id, []))
            days_remaining = (
                current_stock / daily_rate if daily_rate > 0 else None
            )
            urgency = "normal"
            if current_stock <= reorder_point:
                urgency = "critical"
            elif days_remaining is not None and days_remaining < item["lead_time_days"] * _LEAD_TIME_BUFFER_MULTIPLIER:
                urgency = "high"
            elif days_remaining is not None and days_remaining < item["lead_time_days"] * 2:
                urgency = "medium"
            else:
                continue  # stock is adequate

            if urgency == "critical":
                rec = (
                    f"'{item['name']}' is at or below the reorder point "
                    f"({current_stock:.2f}/{reorder_point:.2f} {item['unit']}). "
                    f"Order {item['reorder_qty']:.2f} {item['unit']} immediately."
                )
            else:
                rec = (
                    f"'{item['name']}' has approximately "
                    f"{days_remaining:.1f} days of stock remaining — "
                    f"lead time is {item['lead_time_days']} days. "
                    "Place a reorder soon to avoid disruption."
                )

            recommendations.append({
                "item_id": item_id,
                "name": item["name"],
                "current_stock": round(current_stock, 4),
                "reorder_point": reorder_point,
                "reorder_qty": item["reorder_qty"],
                "unit": item["unit"],
                "days_remaining": (
                    round(days_remaining, 1) if days_remaining is not None else None
                ),
                "urgency": urgency,
                "recommendation": rec,
            })

        recommendations.sort(
            key=lambda x: {"critical": 0, "high": 1, "medium": 2, "normal": 3}.get(
                x["urgency"], 9
            )
        )
        return recommendations

    def get_supply_dashboard(self) -> Dict[str, Any]:
        """Return inventory levels, pending orders, and consumption trends."""
        with self._lock:
            items_snapshot = {k: dict(v) for k, v in self._items.items()}
            usage_snapshot = {k: list(v) for k, v in self._usage_log.items()}
            pending_orders_snapshot = dict(self._pending_orders)

        inventory: List[Dict[str, Any]] = []
        for item_id, item in items_snapshot.items():
            daily_rate = _compute_daily_consumption(usage_snapshot.get(item_id, []))
            days_remaining = (
                item["current_stock"] / daily_rate if daily_rate > 0 else None
            )
            inventory.append({
                "item_id": item_id,
                "name": item["name"],
                "current_stock": round(item["current_stock"], 4),
                "unit": item["unit"],
                "reorder_point": item["reorder_point"],
                "days_remaining": (
                    round(days_remaining, 1) if days_remaining is not None else None
                ),
                "daily_consumption": round(daily_rate, 4),
                "status": (
                    "critical"
                    if item["current_stock"] <= item["reorder_point"]
                    else "ok"
                ),
            })

        pending = [
            dict(v) for v in pending_orders_snapshot.values()
            if v.get("status") == "pending"
        ]

        return {
            "inventory": inventory,
            "pending_orders": pending,
            "total_items": len(items_snapshot),
            "items_at_reorder": sum(
                1 for item in items_snapshot.values()
                if item["current_stock"] <= item["reorder_point"]
            ),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
