# ADR-0010: Move automation ticks to Arq workers

* **Status:** Accepted
* **Date:** 2026-04-22
* **Roadmap row closed:** Item 8
* **Depends on:** [ADR-0011](0011-redis-required.md) (Redis required)
* **Implementation spans:** `src/workers/` (new), `src/runtime/app.py` (tick wiring
  removal), `Dockerfile`, `docker-compose.prod.yml`, `k8s/`

## Context

Murphy's automation engine currently runs periodic ticks (rate-limit refill,
scheduled-action dispatch, billing-cycle close, HITL-timeout sweep, telemetry
flush) in *background tasks attached to the FastAPI process*. Today this means:

* Long ticks block the event loop and inflate p99 request latency.
* A worker-process restart (rolling deploy) drops in-flight tick state on the
  floor; no retry, no audit.
* Horizontal scaling multiplies tick frequency proportionally to replica count
  unless we add a leader-election dance, which we have not done.
* There is no structured retry, no dead-letter queue, no per-job tracing.

These symptoms map directly to the eight commissioning questions: the module
*does not* do what it was designed to do under realistic conditions, and there
is no hardening for the "process restart mid-tick" condition.

## Decision

Background work moves to a **separate worker process** running [Arq](https://arq-docs.helpmanual.io/),
a Redis-backed asyncio task queue. Arq is chosen over Celery and RQ for these
specific reasons (CLAUDE.md §1 — surface tradeoffs):

| Property | Arq | Celery | RQ |
|---|---|---|---|
| Native asyncio | ✅ matches our stack | ❌ sync-only worker | ❌ sync-only worker |
| Operational footprint | Single Redis | Redis + result backend + flower | Single Redis |
| Cron-style schedules | ✅ built-in | ✅ via celery-beat | ❌ needs rq-scheduler |
| Type-checked job signatures | ✅ | ⚠️ partial | ❌ |
| LOC to add | ~150 | ~400 | ~250 |

Concretely:

1. **`src/workers/queue.py`** wraps Arq's `WorkerSettings` with our settings
   loader; `create_arq_redis()` honours `MURPHY_REDIS_URL`.
2. **`src/workers/jobs.py`** holds the migrated tick functions. Each function
   is small, side-effect-isolated, and decorated with `@arq_job` so missing/bad
   arguments raise on enqueue, not at run time.
3. **The web process no longer schedules ticks.** The `app.on_event("startup")`
   hook that previously spawned `asyncio.create_task(tick_loop())` is removed.
   `app.py` instead enqueues a single `bootstrap` job that registers all
   recurring schedules (idempotent — safe under multiple replicas because Arq
   uses Redis SETNX to claim the schedule key).
4. **Worker is a separate container** in compose/k8s: `command: arq
   src.workers.queue.WorkerSettings`. Health checks point at a dedicated
   `/healthz` HTTP probe served by an Arq side-thread.
5. **No silent failure.** All jobs use `try/except` only at job boundaries,
   re-raising after structured logging so Arq's retry machinery sees the
   exception. Repeated failures land in the `arq:dead` Redis stream and emit
   a Prometheus counter `murphy_arq_dead_jobs_total`.

## Consequences

* **Breaking deployment change.** Every Murphy install must run a worker
  process. Documented in `docs/DEPLOYMENT_GUIDE.md` and called out in the
  release notes. The single-node `docker-compose.yml` is updated so quickstart
  Just Works.
* **Redis becomes a hard dependency.** ADR-0011 is the prerequisite that
  legitimises this; that ADR ships in the same release train.
* **Existing tests of tick functions move from "call the function inline" to
  "enqueue and let Arq's `worker_pool` fixture run it." Arq ships a test
  fixture; no new test infrastructure invented.
* **Monitoring.** Three new Grafana panels (queue depth, job duration p99,
  dead-letter rate) added to `grafana/dashboards/murphy-overview.json`.

## Rejected alternatives

* **Keep ticks in the web process and add leader election.** Rejected — adds
  complexity (etcd or postgres advisory lock) without solving event-loop
  blocking or restart-survival.
* **Celery.** Rejected on async mismatch and operational surface (separate
  result backend, flower, beat).
* **RQ.** Rejected on async mismatch (we'd have to wrap every job in
  `asyncio.run`) and missing native scheduler.
* **Cloud-managed queues (SQS, GCP Tasks).** Rejected for the default — forces
  a cloud relationship on every deployer. Remains an option for an adapter.

## Verification

New job in `.github/workflows/ci.yml` named `worker-smoke` boots a Redis
container, runs Arq with a minimal worker, enqueues one job per tick type,
and asserts each completes within its declared SLA. Added in the
implementation PR, not this ADR.
