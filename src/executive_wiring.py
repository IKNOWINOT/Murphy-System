"""
executive_wiring.py — EXEC-02

Single registration point for the executive layer. Called once from
app.py lifespan, attaches all executive surfaces to the app.

Locked decisions (founder, 2026-06-09 PT):
  - Path A: wire orphans, do not build parallel kernel
  - v1=b: snapshot every graph mutation (replayable timeline)
  - v2=a: fork preserves history (Adjust+Rerun creates child dispatch)
  - v3=c: inline correspondence panel (CANVAS-03 round, not this one)

WHAT THIS WIRES (additive only — does not mutate existing routes):

  1. app.state.executive            → ExecutivePlanningEngine() facade
  2. app.state.slot_controller      → AgentSlotController(slot_count=2)
  3. app.state.exec_snapshot_writer → graph snapshot recorder
  4. /api/executive/status          → unified status (objectives, gates,
                                       slots, recent_ctas, pulse summary)
  5. /api/executive/cta/<id>/commit   → user accepts a CTA
  6. /api/executive/cta/<id>/dismiss  → user rejects a CTA
  7. /api/executive/snapshots/<dispatch_id> → list snapshots for a dispatch

REVERSIBILITY:
  Single registration call. To disable: comment out the import +
  register_executive(app) call in app.py lifespan. Zero mutation of
  existing app.py routes — pure addition.

DOES NOT WIRE (deferred to follow-up rounds):
  - Slot controller wrapping PCR-040b executor — needs careful in-place
    edit of app.py block at line 26030. Ship as EXEC-03 separately so
    rollback stays clean.
  - agent_accomplishment_writer pulse + CTA emission — a 15-line edit
    of that file, ship as EXEC-04 separately.
  - /os panel HTML/JS — ships as EXEC-05.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

LOG = logging.getLogger("murphy.executive_wiring")


def register_executive(app: Any) -> Dict[str, Any]:
    """Idempotent — safe to call multiple times. Returns status dict."""

    status = {
        "engine":           False,
        "slot_controller":  False,
        "snapshot_writer":  False,
        "routes_added":     [],
        "errors":           [],
    }

    # ─────────────────────────────────────────────────────────────
    # 1. Instantiate ExecutivePlanningEngine
    # ─────────────────────────────────────────────────────────────
    try:
        if not hasattr(app.state, "executive") or app.state.executive is None:
            from src.executive_planning_engine import ExecutivePlanningEngine
            app.state.executive = ExecutivePlanningEngine()
            LOG.info("EXEC-02: ExecutivePlanningEngine attached to app.state.executive")
        status["engine"] = True
    except Exception as e:
        LOG.warning("EXEC-02: engine instantiate failed: %s", e)
        status["errors"].append(f"engine: {e}")
        app.state.executive = None

    # ─────────────────────────────────────────────────────────────
    # 2. Slot controller singleton (already lazy in module; attach ref)
    # ─────────────────────────────────────────────────────────────
    try:
        if not hasattr(app.state, "slot_controller") or app.state.slot_controller is None:
            from src.agent_slot_controller import get_default_controller
            app.state.slot_controller = get_default_controller()
            LOG.info("EXEC-02: AgentSlotController attached to app.state.slot_controller")
        status["slot_controller"] = True
    except Exception as e:
        LOG.warning("EXEC-02: slot controller attach failed: %s", e)
        status["errors"].append(f"slot_controller: {e}")
        app.state.slot_controller = None

    # ─────────────────────────────────────────────────────────────
    # 3. Snapshot writer (v1=b — per-mutation snapshots)
    # ─────────────────────────────────────────────────────────────
    try:
        if not hasattr(app.state, "exec_snapshot_writer") or app.state.exec_snapshot_writer is None:
            from src.dispatch_graph_snapshots import GraphSnapshotWriter
            app.state.exec_snapshot_writer = GraphSnapshotWriter()
            LOG.info("EXEC-02: GraphSnapshotWriter attached to app.state.exec_snapshot_writer")
        status["snapshot_writer"] = True
    except Exception as e:
        LOG.warning("EXEC-02: snapshot writer attach failed: %s", e)
        status["errors"].append(f"snapshot_writer: {e}")
        app.state.exec_snapshot_writer = None

    # ─────────────────────────────────────────────────────────────
    # 4-7. Route registration (idempotent)
    # ─────────────────────────────────────────────────────────────
    if getattr(app.state, "_executive_routes_registered", False):
        LOG.info("EXEC-02: routes already registered, skipping")
        return status

    try:
        _register_routes(app)
        app.state._executive_routes_registered = True
        status["routes_added"] = [
            "GET  /api/executive/status",
            "POST /api/executive/cta/{cta_id}/commit",
            "POST /api/executive/cta/{cta_id}/dismiss",
            "GET  /api/executive/snapshots/{dispatch_id}",
        ]
        LOG.info("EXEC-02: %d routes registered", len(status["routes_added"]))
    except Exception as e:
        LOG.warning("EXEC-02: route registration failed: %s", e)
        status["errors"].append(f"routes: {e}")

    return status


# ─────────────────────────────────────────────────────────────
# Route handlers (separated so they can be unit-tested)
# ─────────────────────────────────────────────────────────────

def _register_routes(app: Any) -> None:
    """Attach the 4 executive endpoints to the FastAPI app."""
    try:
        from fastapi.responses import JSONResponse
    except ImportError:
        # Fail-soft for test environments without FastAPI
        return

    @app.get("/api/executive/status")
    async def executive_status():
        """Unified executive snapshot for /os panel.

        Returns:
          {
            objectives: [...],          # from ExecutivePlanningEngine
            gates: [...],
            slots: {...},               # current ping-pong state
            recent_ctas: [...],         # last 10 pending CTAs
            pulse: {...},               # cadence summary (last 15 min)
            generated_at: float,        # epoch
          }
        """
        out: Dict[str, Any] = {
            "objectives":   [],
            "gates":        [],
            "slots":        {"active": [], "queued": [], "free_slots": 2,
                             "slot_count": 2, "queue_depth": 0, "queue_cap": 20},
            "recent_ctas":  [],
            "pulse":        {},
            "generated_at": time.time(),
            "errors":       [],
        }

        # Slots
        try:
            ctrl = getattr(app.state, "slot_controller", None)
            if ctrl is not None:
                out["slots"] = ctrl.status()
        except Exception as e:
            out["errors"].append(f"slots: {e}")

        # CTAs
        try:
            from src.executive_cta import list_pending
            out["recent_ctas"] = list_pending(limit=10)
        except Exception as e:
            out["errors"].append(f"ctas: {e}")

        # Pulse
        try:
            from src.cadence_pulse import get_pulse_summary
            out["pulse"] = get_pulse_summary(since_minutes=15)
        except Exception as e:
            out["errors"].append(f"pulse: {e}")

        # Executive engine (objectives + gates if any are tracked)
        try:
            engine = getattr(app.state, "executive", None)
            if engine is not None:
                # Both _objectives and _gates are guarded lists per ExecPlanEngine
                planner = getattr(engine, "planner", None)
                if planner and hasattr(planner, "list_objectives"):
                    try:
                        out["objectives"] = planner.list_objectives()
                    except Exception:
                        pass
                gate_gen = getattr(engine, "gate_generator", None)
                if gate_gen and hasattr(gate_gen, "list_gates"):
                    try:
                        out["gates"] = gate_gen.list_gates()
                    except Exception:
                        pass
        except Exception as e:
            out["errors"].append(f"engine: {e}")

        return JSONResponse(out)

    @app.post("/api/executive/cta/{cta_id}/commit")
    async def executive_cta_commit(cta_id: str):
        """User clicks the CTA. Marks as committed in audit log.

        Locked rule: "Ask Murphy Before All Choices." If the CTA carries
        requires_hitl=True, the *commit endpoint* records the click but
        the underlying action still goes through the existing HITL-v2
        queue. This endpoint is the user's intent, not the execution.
        """
        try:
            from src.executive_cta import commit_cta
            result = commit_cta(cta_id, committed_by="user")
            status_code = 200 if result.get("ok") else 400
            return JSONResponse(result, status_code=status_code)
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    @app.post("/api/executive/cta/{cta_id}/dismiss")
    async def executive_cta_dismiss(cta_id: str):
        """User dismisses the CTA. Marks as dismissed in audit log."""
        try:
            from src.executive_cta import dismiss_cta
            result = dismiss_cta(cta_id, dismissed_by="user")
            status_code = 200 if result.get("ok") else 400
            return JSONResponse(result, status_code=status_code)
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    @app.get("/api/executive/snapshots/{dispatch_id}")
    async def executive_snapshots(dispatch_id: str, limit: int = 100):
        """List ArtifactGraph snapshots for a past dispatch.

        Feeds the canvas historical-load mode (CANVAS-03 round). Each
        snapshot is one mutation of the graph during dispatch.
        """
        try:
            writer = getattr(app.state, "exec_snapshot_writer", None)
            if writer is None:
                return JSONResponse({"snapshots": [], "error": "writer_unavailable"})
            snaps = writer.list_snapshots(dispatch_id, limit=limit)
            return JSONResponse({"dispatch_id": dispatch_id, "snapshots": snaps,
                                 "count": len(snaps)})
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)
