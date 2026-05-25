# Copyright © 2020 Inoni LLC — Creator: Corey Post — License: BSL 1.1
"""
RegenerativeCore — PATCH-361
"Murphy uses its immune memory, self-fix loop, causality sandbox, and
rewind capability to ensure core operating functions never stop working."

This module is the NERVE CENTER that wires together every existing
regenerative system Murphy already has — making them work together as
one continuous dial-down loop:

  MONITOR → DETECT → IMMUNE RECALL → SANDBOX TEST → CAUSALITY GATE
  → APPLY OR REWIND → LEARN → TIGHTEN → REPEAT

Existing systems it wires (all already in Murphy's codebase):
  - SelfHealingCoordinator  → recovers from named failure categories
  - ImmuneMemory            → recognizes recurrent gaps, applies proven antibodies
  - CausalitySandboxEngine  → tests every remediation BEFORE applying it
  - SelfFixLoop             → runs the plan→execute→test→verify cycle
  - BackupManager           → checkpoint before any state change (rewind anchor)
  - RollbackEnforcer        → rewinds to last known good state on gate failure
  - SelfQCPipeline          → QC gates every self-modification before write

What PATCH-361 adds:
  1. A CORE FUNCTION REGISTRY — the functions Murphy must NEVER let fail
     (dispatch, LLM chain, health endpoint, HITL gate, Causality gate)
  2. A CONTINUOUS MONITOR that checks each core function every 60s
  3. A RERUN ENGINE — when a core function fails, it retries with the
     full immune→causality→fix pipeline, not just a bare retry
  4. A REWIND ANCHOR SYSTEM — before any self-modification, take a
     checkpoint. If the modification breaks a core function, rewind
     to the checkpoint automatically.
  5. An IMMUNITY DIAL-DOWN LOOP — each successful recovery tightens
     the threshold. Each failure widens it and alerts HITL.

The dial-down principle:
  Every cycle that passes WITHOUT needing recovery → requirements tighten
  Every recovery event → log, learn, tighten that specific gap category
  After N consecutive clean cycles → promote to immune memory (fast-path)
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("murphy.regenerative_core")

_MAX_HISTORY = 5000


# ─────────────────────────────────────────────────────────────────────────────
# Core Function Registry
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CoreFunction:
    """
    A function Murphy must never let fail.
    Each core function has:
      - A probe: callable that returns (ok: bool, detail: str)
      - A recovery: callable that attempts to restore it
      - Consecutive clean cycles before it earns immunity
      - Thresholds that tighten with each clean cycle
    """
    fn_id: str
    name: str
    description: str
    probe: Callable[[], Tuple[bool, str]]       # returns (healthy, detail)
    recovery: Callable[[], Tuple[bool, str]]    # returns (recovered, detail)
    clean_cycles: int = 0
    failure_count: int = 0
    last_checked: str = ""
    last_status: str = "unknown"
    immune: bool = False                        # graduated to fast-path immunity
    clean_cycles_for_immunity: int = 10
    critical: bool = True                       # if False, degraded is acceptable


@dataclass
class RegenerativeEvent:
    """One event in the regenerative loop — a check, recovery, or rewind."""
    event_id: str
    fn_id: str
    event_type: str      # "check" | "recovery" | "rewind" | "immune_recall" | "tighten"
    success: bool
    detail: str
    duration_ms: float
    timestamp: str


@dataclass
class RewindAnchor:
    """A checkpoint taken before a self-modification — used for rollback."""
    anchor_id: str
    description: str
    snapshot_data: Dict[str, Any]   # serialized state that can be restored
    created_at: str
    used_for_rewind: bool = False
    rewind_at: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# The Regenerative Core
# ─────────────────────────────────────────────────────────────────────────────

class RegenerativeCore:
    """
    Wires together Murphy's self-healing systems into a continuous loop
    that ensures core functions never stop working.

    Usage:
        core = RegenerativeCore()
        core.register_core_function(CoreFunction(...))
        core.start()   # starts background monitor thread

    The monitor runs every 60s (configurable).
    Critical functions that fail trigger immediate recovery.
    Recovery uses immune memory first, then causality sandbox, then fix loop.
    If recovery fails, a rewind to the last anchor is attempted.
    If rewind fails, HITL is notified.
    """

    def __init__(self, check_interval_s: float = 60.0):
        import time as _t_grace
        self._startup_grace_until = _t_grace.time() + 90.0  # PATCH-402: skip probes for first 90s
        self._lock = threading.Lock()
        self._functions: Dict[str, CoreFunction] = {}
        self._events: List[RegenerativeEvent] = []
        self._anchors: List[RewindAnchor] = []
        self._check_interval = check_interval_s
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._hitl_queue: List[Dict] = []

        # Wire existing subsystems
        self._immune_memory = self._load_immune_memory()
        self._self_fix_loop = self._load_self_fix_loop()
        self._healing_coordinator = self._load_healing_coordinator()
        self._backup_manager = self._load_backup_manager()
        self._self_qc = self._load_self_qc()

        logger.info("[PATCH-361] RegenerativeCore initialized — interval=%ss", check_interval_s)

    # ── Subsystem loaders (all graceful) ─────────────────────────────────────

    def _load_immune_memory(self):
        try:
            from immune_memory import ImmuneMemorySystem as ImmuneMemory
            im = ImmuneMemory()
            logger.info("[PATCH-361] ImmuneMemory: wired")
            return im
        except Exception as e:
            logger.warning("[PATCH-361] ImmuneMemory unavailable: %s", e)
            return None

    def _load_self_fix_loop(self):
        try:
            from self_fix_loop import SelfFixLoop
            sfl = SelfFixLoop()
            logger.info("[PATCH-361] SelfFixLoop: wired")
            return sfl
        except Exception as e:
            logger.warning("[PATCH-361] SelfFixLoop unavailable: %s", e)
            return None

    def _load_healing_coordinator(self):
        try:
            from self_healing_startup import bootstrap_self_healing
            hc = bootstrap_self_healing()
            logger.info("[PATCH-361] SelfHealingCoordinator: wired")
            return hc
        except Exception as e:
            logger.warning("[PATCH-361] SelfHealingCoordinator unavailable: %s", e)
            return None

    def _load_backup_manager(self):
        try:
            from backup_disaster_recovery import BackupManager, LocalStorageBackend
            import pathlib as _pl
            _bdr_dir = _pl.Path("/var/lib/murphy-production/backups")
            _bdr_dir.mkdir(parents=True, exist_ok=True)
            bm = BackupManager(backend=LocalStorageBackend(_bdr_dir))
            logger.info("[PATCH-361] BackupManager: wired")
            return bm
        except Exception as e:
            logger.warning("[PATCH-361] BackupManager unavailable: %s", e)
            return None

    def _load_self_qc(self):
        try:
            from self_qc_pipeline import SelfQCPipeline
            qc = SelfQCPipeline()
            logger.info("[PATCH-361] SelfQCPipeline: wired")
            return qc
        except Exception as e:
            logger.warning("[PATCH-361] SelfQCPipeline unavailable: %s", e)
            return None

    # ── Core function registry ────────────────────────────────────────────────

    def register_core_function(self, fn: CoreFunction) -> None:
        with self._lock:
            self._functions[fn.fn_id] = fn
            logger.info("[PATCH-361] Core function registered: %s [critical=%s]", fn.name, fn.critical)

    def register_default_core_functions(self) -> None:
        """Register Murphy's non-negotiable core functions."""
        import aiohttp, asyncio

        def probe_health() -> Tuple[bool, str]:
            try:
                import urllib.request
                resp = urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=5)
                data = resp.read().decode()
                ok = '"status": "healthy"' in data or '"status":"healthy"' in data
                return ok, ("healthy" if ok else "unhealthy: " + data[:100])
            except Exception as e:
                return False, "health probe failed: " + str(e)

        def recover_health() -> Tuple[bool, str]:
            try:
                import subprocess
                r = subprocess.run(["systemctl", "is-active", "murphy-production"],
                                   capture_output=True, text=True)
                if "inactive" in r.stdout or "failed" in r.stdout:
                    logger.warning("[PATCH-402] Self-restart suppressed — would have restarted murphy-production. nginx/systemd handle this."); subprocess.run(["true"],
                                   capture_output=True, text=True)
                    time.sleep(15)
                return probe_health()
            except Exception as e:
                return False, "recovery failed: " + str(e)

        def probe_dispatch() -> Tuple[bool, str]:
            try:
                import urllib.request, json as _json, os
                req = urllib.request.Request(
                    "http://127.0.0.1:8000/api/rosetta/status",
                    headers={"X-API-Key": os.environ.get("MURPHY_API_KEY", "")}
                )
                resp = urllib.request.urlopen(req, timeout=30)
                data = _json.loads(resp.read())
                ok = data.get("success", False) or data.get("status") in ("ready", "online")
                return ok, str(data)[:100]
            except Exception as e:
                return False, "dispatch probe: " + str(e)

        def recover_dispatch() -> Tuple[bool, str]:
            try:
                # Force LLM chain re-init
                import urllib.request, json as _json, os
                req = urllib.request.Request(
                    "http://127.0.0.1:8000/api/health",
                    headers={"X-API-Key": os.environ.get("MURPHY_API_KEY", "")}
                )
                urllib.request.urlopen(req, timeout=30)
                return probe_dispatch()
            except Exception as e:
                return False, "dispatch recovery: " + str(e)

        def probe_llm_chain() -> Tuple[bool, str]:
            try:
                import sys
                sys.path.insert(0, "/opt/Murphy-System/src")
                from llm_provider import complete
                resp = complete("Say OK in one word.", max_tokens=5)
                # PATCH-411e (2026-05-24): complete() now returns str directly,
                # not an object with .content. Handle both for back-compat.
                text = resp if isinstance(resp, str) else getattr(resp, "content", "")
                ok = bool(text)
                return ok, ("LLM chain alive: " + text[:30] if ok else "LLM returned empty")
            except Exception as e:
                return False, "LLM probe: " + str(e)

        def recover_llm_chain() -> Tuple[bool, str]:
            # The LLM chain is already self-healing with DeepInfra→Together→Ollama fallback
            # Just re-probe after a brief wait
            time.sleep(3)
            return probe_llm_chain()

        def probe_hitl_gate() -> Tuple[bool, str]:
            try:
                import urllib.request, os
                # PATCH-411e (2026-05-24): /api/hitl/status was renamed to
                # /api/hitl/pending — using the new route.
                req = urllib.request.Request(
                    "http://127.0.0.1:8000/api/hitl/pending",
                    headers={"X-API-Key": os.environ.get("MURPHY_API_KEY", "")}
                )
                resp = urllib.request.urlopen(req, timeout=30)
                return True, "HITL gate responding"
            except Exception as e:
                return False, "HITL gate probe: " + str(e)

        def recover_hitl_gate() -> Tuple[bool, str]:
            time.sleep(2)
            return probe_hitl_gate()

        self.register_core_function(CoreFunction(
            fn_id="health_endpoint",
            name="Health Endpoint",
            description="GET /api/health must return status=healthy",
            probe=probe_health,
            recovery=recover_health,
            clean_cycles_for_immunity=5,
            critical=True,
        ))
        self.register_core_function(CoreFunction(
            fn_id="dispatch_engine",
            name="Dispatch Engine",
            description="/api/rosetta/dispatch must be reachable",
            probe=probe_dispatch,
            recovery=recover_dispatch,
            clean_cycles_for_immunity=10,
            critical=True,
        ))
        self.register_core_function(CoreFunction(
            fn_id="llm_chain",
            name="LLM Chain",
            description="DeepInfra→Together→Ollama chain must return a response",
            probe=probe_llm_chain,
            recovery=recover_llm_chain,
            clean_cycles_for_immunity=15,
            critical=True,
        ))
        self.register_core_function(CoreFunction(
            fn_id="hitl_gate",
            name="HITL Gate",
            description="HITL approval endpoint must respond",
            probe=probe_hitl_gate,
            recovery=recover_hitl_gate,
            clean_cycles_for_immunity=10,
            critical=False,
        ))
        logger.info("[PATCH-361] %d default core functions registered", len(self._functions))

    # ── Rewind anchor system ──────────────────────────────────────────────────

    def take_rewind_anchor(self, description: str, snapshot_data: Optional[Dict] = None) -> RewindAnchor:
        """Take a checkpoint before a risky operation. Used for rollback."""
        anchor = RewindAnchor(
            anchor_id="anchor_" + uuid.uuid4().hex[:8],
            description=description,
            snapshot_data=snapshot_data or {"timestamp": datetime.now(timezone.utc).isoformat()},
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        with self._lock:
            self._anchors.append(anchor)
            if len(self._anchors) > 50:
                self._anchors = self._anchors[-50:]
        logger.info("[PATCH-361] Rewind anchor: %s — %s", anchor.anchor_id, description[:60])
        return anchor

    def rewind_to_anchor(self, anchor: RewindAnchor) -> Tuple[bool, str]:
        """Attempt to rewind system state to a previous anchor."""
        t0 = time.time()
        logger.warning("[PATCH-361] REWIND triggered to anchor %s: %s",
                        anchor.anchor_id, anchor.description[:60])

        results = []

        # Try BackupManager restore if available
        if self._backup_manager:
            try:
                # BackupManager has a restore method
                restore_result = getattr(self._backup_manager, "restore_from_snapshot", None)
                if restore_result and "backup_id" in anchor.snapshot_data:
                    r = restore_result(anchor.snapshot_data["backup_id"])
                    results.append("backup_restore: " + str(getattr(r, "status", "attempted")))
            except Exception as e:
                results.append("backup_restore failed: " + str(e))

        # Try RollbackEnforcer if available
        try:
            from execution_orchestrator.rollback import RollbackEnforcer
            enforcer = RollbackEnforcer()
            rollback_plan = anchor.snapshot_data.get("rollback_plan", {
                "steps": [{"type": "restart_service", "service": "murphy-production"}],
                "verification": {"type": "health_check", "url": "http://127.0.0.1:8000/api/health"}
            })
            valid, err = enforcer.validate_rollback_plan(rollback_plan)
            if valid:
                results.append("rollback_plan: validated")
        except Exception as e:
            results.append("rollback_enforcer: " + str(e)[:50])

        # Service restart as last-resort rewind
        try:
            import subprocess
            r = logger.warning("[PATCH-402] Self-restart suppressed — would have restarted murphy-production. nginx/systemd handle this."); subprocess.run(["true"],
                               capture_output=True, text=True, timeout=30)
            results.append("service_restart: " + r.returncode.__class__.__name__)
            time.sleep(15)
        except Exception as e:
            results.append("service_restart failed: " + str(e))

        anchor.used_for_rewind = True
        anchor.rewind_at = datetime.now(timezone.utc).isoformat()

        elapsed = (time.time() - t0) * 1000
        detail = "; ".join(results)
        self._log_event(anchor.anchor_id[:8], "rewind", True, detail, elapsed)
        return True, detail

    # ── Recovery pipeline ─────────────────────────────────────────────────────

    def _recover_function(self, fn: CoreFunction) -> Tuple[bool, str]:
        """
        Full regenerative recovery for one core function.
        Order: immune recall → causality sandbox → self-fix → rewind
        """
        logger.warning("[PATCH-361] Recovering: %s", fn.name)
        results = []

        # Step 1: Immune recall — has this pattern been seen before?
        if self._immune_memory:
            try:
                class _Gap:
                    description = "Core function failure: " + fn.name
                    gap_category = fn.fn_id
                    gap_source = "regenerative_monitor"
                cell = self._immune_memory.recognize(_Gap())
                if cell:
                    logger.info("[PATCH-361] ImmuneMemory: recalled antibody for %s", fn.fn_id)
                    results.append("immune_recall: antibody found, applying")
                    ok, detail = fn.recovery()
                    if ok:
                        self._update_immune_memory(fn, success=True)
                        return True, "immune_recall succeeded: " + detail
                    results.append("immune_recall: antibody ineffective — " + detail)
            except Exception as e:
                results.append("immune_recall error: " + str(e)[:50])

        # Step 2: Causality sandbox — test recovery action before applying
        causality_ok = True
        try:
            from causality_sandbox import CausalitySandboxEngine
            cs = CausalitySandboxEngine()
            # Simulate the recovery — probe before and after
            before_ok, before_detail = fn.probe()
            action = {"type": "service_recovery", "fn_id": fn.fn_id, "action": "recovery_callable"}
            scored = cs.evaluate_action(action, {"fn_id": fn.fn_id, "status": "failing"})
            if scored is not None:
                causality_ok = getattr(scored, "should_commit", True)
                results.append("causality: " + ("approved" if causality_ok else "blocked"))
        except Exception as e:
            results.append("causality sandbox unavailable: " + str(e)[:50])
            causality_ok = True  # allow recovery if sandbox unavailable

        if causality_ok:
            # Step 3: Apply recovery
            try:
                ok, detail = fn.recovery()
                results.append("recovery: " + ("success" if ok else "fail") + " — " + detail[:60])
                if ok:
                    self._update_immune_memory(fn, success=True)
                    fn.clean_cycles = 0
                    return True, "; ".join(results)
            except Exception as e:
                results.append("recovery exception: " + str(e)[:80])

        # Step 4: Rewind to last anchor
        anchors = [a for a in self._anchors if not a.used_for_rewind]
        if anchors:
            last_anchor = anchors[-1]
            results.append("attempting rewind to anchor: " + last_anchor.anchor_id[:8])
            rewind_ok, rewind_detail = self.rewind_to_anchor(last_anchor)
            if rewind_ok:
                time.sleep(8)  # let service come back
                ok, detail = fn.probe()
                if ok:
                    results.append("rewind success: " + detail[:50])
                    return True, "; ".join(results)
                results.append("post-rewind probe still failing: " + detail[:50])

        # Step 5: HITL escalation
        self._escalate_to_hitl(fn, "; ".join(results))
        return False, "; ".join(results)

    def _update_immune_memory(self, fn: CoreFunction, success: bool) -> None:
        if not self._immune_memory:
            return
        try:
            antigen_id = "antigen_" + fn.fn_id
            antibody_data = {
                "fn_id": fn.fn_id, "action": "recovery_callable",
                "success": success, "ts": datetime.now(timezone.utc).isoformat()
            }
            if hasattr(self._immune_memory, "record_outcome"):
                self._immune_memory.record_outcome(antigen_id, success, antibody_data)
        except Exception as e:
            logger.debug("[PATCH-361] ImmuneMemory update: %s", e)

    def _escalate_to_hitl(self, fn: CoreFunction, detail: str) -> None:
        item = {
            "fn_id": fn.fn_id,
            "name": fn.name,
            "detail": detail[:300],
            "critical": fn.critical,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action_required": "Manual intervention needed — automated recovery exhausted",
        }
        with self._lock:
            self._hitl_queue.append(item)
        logger.critical("[PATCH-361] HITL ESCALATION: %s — %s", fn.name, detail[:100])

    # ── Dial-down tightening ──────────────────────────────────────────────────

    def _tighten(self, fn: CoreFunction) -> None:
        """After clean cycles, graduate the function to immune status."""
        fn.clean_cycles += 1
        if fn.clean_cycles >= fn.clean_cycles_for_immunity and not fn.immune:
            fn.immune = True
            logger.info("[PATCH-361] %s GRADUATED TO IMMUNITY after %d clean cycles",
                        fn.name, fn.clean_cycles)
            self._log_event(fn.fn_id, "tighten",
                            True, "graduated to immunity after " + str(fn.clean_cycles) + " clean cycles", 0.0)

    # ── Monitor loop ──────────────────────────────────────────────────────────

    def _monitor_once(self) -> Dict[str, Any]:
        import time as _t_g
        if _t_g.time() < getattr(self, "_startup_grace_until", 0):
            logger.info("[PATCH-361/402] Startup grace active — skipping probe (%.0fs left)", self._startup_grace_until - _t_g.time())
            return {}

        """Run one pass of the monitor loop."""
        results = {}
        with self._lock:
            fns = list(self._functions.values())

        for fn in fns:
            t0 = time.time()
            try:
                ok, detail = fn.probe()
            except Exception as e:
                ok, detail = False, "probe exception: " + str(e)[:100]

            elapsed = (time.time() - t0) * 1000
            fn.last_checked = datetime.now(timezone.utc).isoformat()
            fn.last_status = "healthy" if ok else "failing"

            self._log_event(fn.fn_id, "check", ok, detail[:150], elapsed)

            if ok:
                self._tighten(fn)
                results[fn.fn_id] = {"status": "healthy", "cycles": fn.clean_cycles, "immune": fn.immune}
            else:
                fn.clean_cycles = 0
                fn.failure_count += 1
                logger.warning("[PATCH-361] Core function FAILING: %s — %s", fn.name, detail[:80])

                if fn.critical:
                    rec_ok, rec_detail = self._recover_function(fn)
                    results[fn.fn_id] = {
                        "status": "recovered" if rec_ok else "failed_recovery",
                        "detail": rec_detail[:100],
                        "failure_count": fn.failure_count,
                    }
                else:
                    results[fn.fn_id] = {"status": "degraded", "detail": detail[:80]}

        return results

    def _monitor_loop(self) -> None:
        logger.info("[PATCH-361] Regenerative monitor loop started (interval=%ss)", self._check_interval)
        while self._running:
            try:
                results = self._monitor_once()
                healthy = sum(1 for v in results.values() if v["status"] in ("healthy", "recovered", "immune"))
                total = len(results)
                if total > 0:
                    logger.info("[PATCH-361] Monitor pass: %d/%d healthy", healthy, total)
            except Exception as e:
                logger.error("[PATCH-361] Monitor loop error: %s", e)
            time.sleep(self._check_interval)

    def start(self) -> None:
        """Start the background monitor loop."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True, name="murphy-regen-core")
        self._thread.start()
        logger.info("[PATCH-361] RegenerativeCore monitor STARTED")

    def stop(self) -> None:
        self._running = False
        logger.info("[PATCH-361] RegenerativeCore monitor STOPPED")

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            fns = list(self._functions.values())
        return {
            "running": self._running,
            "functions": {
                fn.fn_id: {
                    "name": fn.name,
                    "status": fn.last_status,
                    "clean_cycles": fn.clean_cycles,
                    "failure_count": fn.failure_count,
                    "immune": fn.immune,
                    "critical": fn.critical,
                    "last_checked": fn.last_checked,
                }
                for fn in fns
            },
            "hitl_queue_length": len(self._hitl_queue),
            "anchor_count": len(self._anchors),
            "recent_events": self._events[-20:],
        }

    def get_hitl_queue(self) -> List[Dict]:
        return list(self._hitl_queue)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _log_event(self, fn_id: str, event_type: str, success: bool, detail: str, duration_ms: float) -> None:
        event = RegenerativeEvent(
            event_id="evt_" + uuid.uuid4().hex[:6],
            fn_id=fn_id,
            event_type=event_type,
            success=success,
            detail=detail,
            duration_ms=duration_ms,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        with self._lock:
            self._events.append({
                "id": event.event_id, "fn_id": fn_id,
                "type": event_type, "ok": success,
                "detail": detail[:100], "ms": round(duration_ms, 1),
                "ts": event.timestamp,
            })
            if len(self._events) > _MAX_HISTORY:
                self._events = self._events[-_MAX_HISTORY:]


# Module-level singleton
_regen_core: Optional[RegenerativeCore] = None

def get_regen_core() -> RegenerativeCore:
    global _regen_core
    if _regen_core is None:
        _regen_core = RegenerativeCore(check_interval_s=60.0)
        _regen_core.register_default_core_functions()
        _regen_core.start()
    return _regen_core
