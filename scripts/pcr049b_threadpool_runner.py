#!/usr/bin/env python3
"""
PCR-049b — make PCR-049 runner truly fire-and-forget via threadpool

DIAGNOSIS:
  PCR-049 v3 (PCR-040d shape) shipped clean. The runner runs and
  completes. dispatch_jobs.db is populated with done rows. GET poll
  endpoint returns in <40ms.

  BUT: POST blocks 15-38 seconds before returning the {job_id}.

  Why: asyncio.create_task() schedules in the SAME event loop. The
  runner immediately starts and awaits the heavy _rosetta_dispatch
  coroutine, which holds the event loop. Starlette's BaseHTTPMiddleware
  doesn't yield back to the original handler's JSONResponse until the
  scheduled task either yields cleanly or completes.

  Effectively: even though the code structurally fires-and-forgets,
  the middleware chain stays bound until the work actually finishes.

FIX:
  Run the dispatch in a threadpool via run_in_executor. This puts it
  on a different thread entirely so the event loop is free to flush
  the POST response immediately.

  The runner doesn't need event-loop access except to call
  _rosetta_dispatch, which is itself async. So we run a sync wrapper
  in the threadpool that uses asyncio.run() to drive the dispatch
  from inside the thread.

  This is the standard pattern for fire-and-forget async work in
  FastAPI when the work is long-running.
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

APP = Path("/opt/Murphy-System/src/runtime/app.py")

# Anchor: the create_task line + surrounding context
OLD = '''            _conn.commit(); _conn.close()
            _aa040d.create_task(_run_dispatch_to_db_040d(job_id, prompt))
            return JSONResponse({'''

NEW = '''            _conn.commit(); _conn.close()
            # PCR-049b: run in threadpool — create_task on same loop
            # blocks the middleware chain. Threadpool detaches fully.
            import threading as _thr049b
            def _runner_thread_049b():
                try:
                    import asyncio as _aathr
                    _aathr.run(_run_dispatch_to_db_040d(job_id, prompt))
                except Exception as _e:
                    _log040d.exception("[PCR-049b] thread runner failed: %s", _e)
            _t049b = _thr049b.Thread(target=_runner_thread_049b, daemon=True, name=f"pcr049b-{job_id}")
            _t049b.start()
            return JSONResponse({'''


def apply(verify, revert):
    print(f"PCR-049b threadpool runner  verify={verify}  revert={revert}")
    src = APP.read_text(encoding="utf-8")

    if revert:
        if "PCR-049b" not in src:
            print("  · already absent"); return 0
        if NEW not in src:
            print("  ✗ new anchor not found"); return 1
        src = src.replace(NEW, OLD, 1)
        if verify: print("  ✓ would revert"); return 0
        APP.write_text(src, encoding="utf-8")
        print("  ✓ reverted"); return 0

    if "PCR-049b" in src:
        print("  · already applied"); return 0
    if OLD not in src:
        print(f"  ✗ OLD anchor not found"); return 1
    if src.count(OLD) > 1:
        print(f"  ✗ anchor matches {src.count(OLD)} places — refusing"); return 1
    src = src.replace(OLD, NEW, 1)
    if verify: print("  ✓ would apply"); return 0
    APP.write_text(src, encoding="utf-8")
    print("  ✓ applied — POST will return job_id immediately"); return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--revert", action="store_true")
    a = ap.parse_args()
    return apply(a.verify, a.revert)


if __name__ == "__main__":
    sys.exit(main())
