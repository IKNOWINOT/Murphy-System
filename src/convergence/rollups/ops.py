"""Ops domain — timers, schedulers, queues, slot controller, pulse."""
from typing import Dict, Any


def rollup_ops(tenant_id: str | None = None) -> Dict[str, Any]:
    # Call into existing executive_wiring layer
    try:
        from src.executive_wiring import build_status_payload
        live = build_status_payload()
    except Exception as e:
        live = {"errors": [f"executive_wiring unavailable: {e}"]}

    pulse = live.get("pulse", {})
    slots = live.get("slots", {})
    summary = {
        "pulse_color": pulse.get("color", "unknown"),
        "timer_sources_count": len(pulse.get("sources", [])),
        "stale_sources_count": sum(
            1 for s in pulse.get("sources", [])
            if s.get("status") == "stale"
        ),
        "free_slots": slots.get("free_slots", 0),
        "queue_depth": slots.get("queue_depth", 0),
    }
    items = []
    for s in pulse.get("sources", []):
        if s.get("status") == "stale":
            items.append({
                "id": s.get("source"),
                "type": "stale_timer",
                "title": s.get("display_name") or s.get("source"),
                "state": "stale",
                "drift_seconds": s.get("drift_seconds"),
            })
    return {
        "summary": summary,
        "items": items,
        "raw_endpoints": [
            "/api/executive/status",
            "/api/swarm/scheduler/status",
            "/api/hitl/queue",
        ],
    }
