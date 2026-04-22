# ADR-0011: Promote Redis from optional to required

* **Status:** Accepted
* **Date:** 2026-04-22
* **Roadmap row closed:** Item 7
* **Unblocks:** [ADR-0010](0010-background-workers-arq.md)
* **Implementation spans:** `src/runtime/_deps.py`, `src/cache/`, `src/rate_limit/`,
  `src/sessions/`, `src/workers/`, `Dockerfile`, `docker-compose*.yml`, `k8s/`,
  `docs/DEPLOYMENT_GUIDE.md`

## Context

Today Redis is *optional*: every subsystem that wants it (rate limiter,
session store, cache, future job queue) carries a `try: import redis ...`
fallback to an in-memory implementation. The fallback is convenient for
single-process dev, but it has accumulated real costs:

* **Correctness drift.** Each subsystem's in-memory fallback is subtly
  different from the Redis path (different eviction, different atomicity
  guarantees). Bugs are filed against one and missed in the other.
* **Multi-replica is broken by default.** Two web workers each get their own
  in-memory rate-limit table; the global limit is silently the per-replica
  limit times N. No alarm fires.
* **Testing surface doubled.** Every feature ships two code paths and we test
  both incompletely.
* **ADR-0010 (background workers, Arq) requires Redis** as a backing store.

## Decision

Redis becomes a **required dependency** for any non-trivial deployment. The
in-memory fallbacks are **retained but constrained**:

1. **Single mode flag.** A new setting `MURPHY_RUNTIME_MODE` takes one of:
   - `single-node-dev` — in-memory fallbacks permitted; emits a startup
     `RuntimeWarning` so it cannot be used accidentally in prod.
   - `production` (default) — in-memory fallbacks raise `RuntimeError` at
     startup if Redis is unreachable. **The process refuses to start** rather
     than silently degrading. This matches the team-of-engineers rule
     "nothing allowing automations to perform or fail silently."
2. **Consolidated Redis client.** `src/runtime/redis_client.py` (new) is the
   single place that builds the connection (URL, TLS, sentinel, pool size,
   password). Every subsystem imports from there.
3. **Health check.** `/api/health` reports `redis: ok|degraded|down` with the
   ping latency. `/api/health` returns 503 when `redis: down` in production
   mode so load balancers actually take the pod out of rotation.
4. **Connection pool sizing.** Defaults: `max_connections=50` per replica,
   `socket_timeout=2s`, `socket_connect_timeout=2s`, `retry_on_timeout=True`.
   These are not configurable via env in this PR — over-configurability is the
   thing we are removing (CLAUDE.md §2).
5. **Backup/restore.** `docs/RUNBOOKS.md` gains a Redis snapshot/restore
   playbook; the production compose file enables AOF persistence.

## Consequences

* **Breaking deployment change.** Every operator must run Redis or set
  `MURPHY_RUNTIME_MODE=single-node-dev`. The release notes lead with this.
  The 6.2+ minor matters (we use streams in ADR-0010); compose pins
  `redis:7-alpine`.
* The `try/except ImportError` guards around `redis` in `src/runtime/_deps.py`
  are removed in the same PR; `redis` moves from `requirements.txt` "optional"
  comment block into the unconditional core list.
* The four in-memory fallback implementations (rate limiter, sessions, cache,
  pending queue) are *kept*, but now gated by `MURPHY_RUNTIME_MODE` and
  tagged with a module-level `__production_safe__ = False` constant so the
  ModuleLoader (Item 20) can refuse to use them in production mode.
* The threat model (`docs/SECURITY_THREAT_MODEL.md` §3.2) gets a Redis section:
  AUTH on by default, TLS in transit when `MURPHY_REDIS_URL` uses `rediss://`,
  Redis bound to internal network only.

## Rejected alternatives

* **Status quo (Redis optional).** Rejected — silent multi-replica
  miscounting is a correctness bug, not a config preference.
* **Make every fallback a separate hard error.** Rejected as cruel — the
  single startup-time check with a clear message is enough; we don't need
  a stack trace per subsystem.
* **Drop the in-memory fallbacks entirely.** Rejected — single-node-dev is
  the most common way new contributors start the app, and standing up Redis
  before they have a working hello-world is bad onboarding.

## Verification

`tests/runtime/test_runtime_mode.py` (new): asserts that `production` mode
raises on missing Redis, and that `single-node-dev` mode runs but emits the
`RuntimeWarning`. CI matrix runs the full suite in both modes.
