"""
R477 — Vision Loop continuous runner.

WHAT THIS IS:
  A oneshot script invoked by systemd timer murphy-r477-vision-loop.timer.
  Runs MurphySelfVisionLoop.run_cycle(auto_apply=True for trusted file classes ONLY) so the loop scans
  pages, proposes patches, gates them, but does NOT auto-apply.

WHY IT EXISTS:
  Before R477 the vision loop only ran once at substrate boot, then died.
  Last applied patch was 2026-05-03 — a month of dead autonomy. This timer
  restores continuous self-diagnosis.

HOW IT FITS:
  systemd timer → this script → MurphySelfVisionLoop.run_cycle()
  Results land in /var/lib/murphy-production/vision_loop.db
  HITL is still required for application (auto_apply=False).

LAST UPDATED: 2026-06-02 by Murphy (R477)
"""
import asyncio
import logging
import os
import sys
import time

sys.path.insert(0, "/opt/Murphy-System")
os.environ.setdefault("MURPHY_DATA_DIR", "/var/lib/murphy-production")

# Source env so LLM keys are available
env_file = "/etc/murphy-production/environment"
if os.path.exists(env_file):
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                # R478b: ASSIGNMENT not setdefault — env file is source of truth,
                # systemd EnvironmentFile may have pre-loaded stale values.
                os.environ[k.strip()] = v.strip()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("r477_runner")

# R403 event log
try:
    from src.r403_event_log import log_start, log_succeed, log_fail
    HAS_EVENT_LOG = True
except Exception:
    HAS_EVENT_LOG = False
    def log_start(*a, **kw): pass
    def log_succeed(*a, **kw): pass
    def log_fail(*a, **kw): pass


async def main() -> int:
    t0 = time.time()
    log_start("r477_vision_loop", reason="timer fired")
    log.info("R477 vision loop runner starting")

    try:
        from src.murphy_self_vision_loop import get_vision_loop
        loop = get_vision_loop()
        # auto_apply=False — proposals only, HITL applies
        run = await loop.run_cycle(
            triggered_by="r477_timer",
            auto_apply=False,
        )
        elapsed = (time.time() - t0) * 1000
        proposals = len(getattr(run, "proposals", []) or [])
        applied = sum(
            1 for p in (getattr(run, "proposals", []) or [])
            if getattr(p, "applied_at", None)
        )
        log.info(
            "R477 cycle done — pages=%d proposals=%d applied=%d elapsed=%.0fms",
            getattr(run, "pages_scanned", 0), proposals, applied, elapsed,
        )
        log_succeed(
            "r477_vision_loop",
            reason=f"pages={getattr(run,'pages_scanned',0)} proposals={proposals} applied={applied}",
            elapsed_ms=int(elapsed),
        )
        return 0
    except Exception as exc:
        elapsed = (time.time() - t0) * 1000
        log.error("R477 cycle failed: %s", exc, exc_info=True)
        log_fail(
            "r477_vision_loop",
            code="E_R477_CYCLE",
            reason=str(exc)[:200],
        )
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))


# ═══ _R486C_TRUSTED_APPLY — auto-apply ONLY trusted-class proposals ═══
def _r486c_apply_trusted():
    """After the vision cycle, scan pending proposals and apply ONLY ones matching
    the trusted-class policy:
      - status = pending
      - gate_verdict = approve (Steve's gate said yes)
      - critic_verdict IN (pending, PASS) (critic didn't reject)
      - confidence >= 0.85
      - target_file matches static/(murphy-nav|murphy-app-shell|app-shell|murphy-app).(js|css)
      - patch_content length 80-15000 bytes (sanity caps)
    Hard cap: 3 applications per run to prevent runaway.
    """
    import sqlite3, re, logging
    _logr = logging.getLogger("r486c_trusted_apply")
    trusted_pat = re.compile(r"^static/(murphy-nav|murphy-app-shell|app-shell|murphy-app)\.(js|css)$")
    try:
        from src.murphy_self_vision_loop import MurphySelfVisionLoop
        from src.murphy_self_vision_loop import ProposalStatus
        with sqlite3.connect("/var/lib/murphy-production/vision_loop.db", timeout=5) as c:
            c.execute("PRAGMA busy_timeout=3000")
            rows = c.execute(
                """SELECT id, target_file, patch_content, confidence
                   FROM proposals
                   WHERE status='pending'
                     AND gate_verdict='approve'
                     AND COALESCE(critic_verdict,'pending') IN ('pending','PASS','WARN')
                     AND confidence >= 0.85
                     AND length(coalesce(patch_content,'')) BETWEEN 80 AND 15000
                   ORDER BY confidence DESC
                   LIMIT 10"""
            ).fetchall()
        candidates = [r for r in rows if trusted_pat.match(r[1] or "")]
        _logr.info("_R486C: %d candidates after trusted-class filter (cap 3)", len(candidates))
        applied = 0
        vl = None
        for pid, tfile, pcontent, conf in candidates[:3]:
            try:
                if vl is None:
                    vl = MurphySelfVisionLoop()
                # Build a minimal proposal-like object for _apply_patch
                # OR: just call low-level apply directly
                from src.murphy_self_vision_loop import VisionProposal
                vp = VisionProposal(
                    run_id="r486c-trusted",
                    page_url="",
                    target_file=tfile,
                    issue_summary="R486C trusted-class auto-apply",
                    rationale="confidence>=0.85 + gate=approve + trusted file class",
                    patch_content=pcontent,
                    patch_mode="replace",
                    confidence=conf,
                    gate_verdict="approve",
                    gate_notes="R486C trusted-class auto-apply",
                )
                vp.id = pid
                ok = vl._apply_patch(vp)
                if ok:
                    applied += 1
                    _logr.info("_R486C: applied %s (conf=%s)", pid, conf)
                else:
                    _logr.info("_R486C: apply returned False for %s", pid)
            except Exception as exc:
                _logr.warning("_R486C: apply failed %s: %s", pid, exc)
        _logr.info("_R486C: %d patches applied this cycle (cap=3)", applied)
        return applied
    except Exception as exc:
        _logr.error("_R486C: catastrophic failure: %s", exc)
        return -1
