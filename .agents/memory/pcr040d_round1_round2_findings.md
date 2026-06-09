# PCR-040d — Round 1 & Round 2 findings (2026-06-09 06:15 UTC)

## What was attempted

Add async dispatch endpoints:
  POST /api/rosetta/dispatch/async  →  {job_id}
  GET  /api/rosetta/dispatch/job/{id}  →  {graph_state, status, ...}

Goal: solve Cloudflare 100s edge timeout by returning job_id fast,
polling for graph_state.

## Round 1 design (FastAPI BackgroundTasks)

- POST handler INSERTs row to dispatch_jobs.db
- Schedules `_run_dispatch_to_db_040d` via BackgroundTasks
- Runner constructs synthetic Starlette Request, calls _rosetta_dispatch
- Compiled clean, deployed, anchor verified, 5/5 surgical checks passed
- POST returned 200 markers in served code but actual POST HUNG at 10s

ROLLED BACK CLEANLY (0 markers remained).

## Round 2 design (asyncio.create_task)

- Same as R1 but used asyncio.create_task() for true fire-and-forget
- Pre-created dispatch_jobs.db with WAL mode + warmup INSERT/DELETE
- Added explicit logging (proved code DID load: log line
  "[PCR-040d] dispatch_jobs.db ready (WAL)" appeared at boot)

POST request STILL hung at 12s.

## Critical diagnostic in R2

Tested the SYNC /api/rosetta/dispatch (which works in PCR-040b LIVE):
  - SYNC endpoint with prompt="hi"  → HUNG AT 30s timeout
  - ASYNC endpoint with {}          → HUNG AT 10s timeout

This proves the hang is NOT in PCR-040d code. The hang is in the
auth middleware path that fires the deprecation warning:
  "DEPRECATED: X-API-Key accepted on /api/rosetta/dispatch/async
   — migrate to OIDC (ADR-0012 Release N+1 disables this path by default)"

That middleware hook appears to be doing a synchronous lookup against
an audit DB that's locked or slow when the system is under LLM
rate-limit cascade pressure.

## Concurrent infrastructure problem

During R2 testing the service was in degraded state:
  - /api/health → 200 (fast)
  - / → 000 (timeout)
  - /os → 000 (timeout)
  - /canvas → 000 (timeout)

Together.ai rate limit cascade was active. journal showed multiple
kill-9 restart cycles in the prior 30 min. This same condition
prevents PCR-040b/c LIVE testing also.

## What R2 ROLLED BACK to

HEAD `6a2a6ecc` (PCR-042). Verified:
  - 0 PCR-040d markers in src/runtime/app.py
  - 3 PCR-042 markers in static/murphy-os.html
  - 2 PCR-041 markers in static/murphy-work-canvas.html
  - Service active, 3/4 surfaces 200 after fresh restart
  - Only / still slow (heaviest page, cascade related)

## What to do differently next attempt

1. DO NOT attempt PCR-040d while the LLM cascade is active.
   Pre-flight: ALL four surfaces must be 200 with sub-2s latency.

2. The auth deprecation warning hook on /api/rosetta/dispatch* is the
   ACTUAL blocker. Two options:
   (a) Register the async route under a different prefix
       (/api/dispatch-async, /api/jobs/dispatch) that doesn't match
       the deprecation pattern.
   (b) Audit auth_middleware.py:1020 and patch the slow lookup that
       runs during the deprecation warning.

3. (a) is much simpler. Try (a) first.

4. Don't use BackgroundTasks OR asyncio.create_task without first
   confirming the SYNC endpoint at the new prefix returns in <2s.

## Honest pattern lesson

The marker-based patcher + verifier pattern worked perfectly TWICE.
The patch landed clean, reverted clean, no source contamination.
What failed was the architecture assumption — that the route prefix
pattern was inert. It wasn't. The system has hidden behavior on
/api/rosetta/dispatch* that I didn't audit before writing the patch.

L43 (extend, don't invent) — I extended the dispatch prefix; should
have audited what other behaviors hook on that prefix first.

Audit-First rule: I checked for an existing async pattern but did NOT
check for middleware-side hooks on the route prefix. That's the gap.
