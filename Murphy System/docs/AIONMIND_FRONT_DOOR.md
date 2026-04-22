# AionMind Front Door — Identity, Approval, and Capability Bridges

> **Phase 1 + 2 reference for the `/api/execute`, `/api/forms/*`, and
> `/api/aionmind/*` surface.**

This document captures the contract between the AionMind cognitive
kernel (`src/aionmind/`) and the HTTP front door
(`src/runtime/app.py`).  It is the canonical reference for:

1. how a caller's identity is resolved into an approval policy,
2. how `cognitive_execute` enforces the no-autonomy invariant,
3. what subsystem capabilities are auto-registered at boot,
4. the observability surface (status, capabilities, metrics, audit
   log) the front door exposes.

---

## 1. Caller resolution (`_resolve_caller`)

Every front-door route that talks to the AionMind kernel calls
`_resolve_caller(request)` from `src/runtime/app.py`.  It returns a
single normalised dict — `{account_id, email, role, tier}` — or
`None` for unauthenticated traffic.

Resolution order:

1. **Session** — cookie or `Authorization: Bearer <token>` via
   `_get_account_from_session`.
2. **`X-User-ID` header** — the legacy header the RBAC dependency
   already consumes.  May be either an `account_id` or an `email`.
3. **Bare-email fallback** (Phase 2 / A3) — when `X-User-ID` is an
   email and the user store has no record at all, an unseeded
   identity stub `{email, role: "user"}` is constructed.  This
   prevents the founder from being rejected on a fresh deployment
   that hasn't yet seeded their account.

### Founder override (A3)

If the resolved email matches `MURPHY_FOUNDER_EMAIL` (default
`cpost@murphy.systems`) and the stored role is anything other than
`"owner"`, the role is forced to `"owner"`.  This closes the
"founder seeding race": the founder always retains owner-tier
authority on their own deployment, regardless of what the user store
currently records.

## 2. Approval policy (`_auto_approve_for`)

Returns `(auto_approve: bool, max_auto_approve_risk: RiskLevel)`
suitable for passing straight into
`AionMindKernel.cognitive_execute`.

| Role               | Auto-approve | Ceiling |
|--------------------|--------------|---------|
| `owner`            | yes          | MEDIUM  |
| `admin`            | yes          | LOW     |
| anyone else / anon | no           | LOW     |

The kernel's `_risk_le(actual, ceiling)` ordering is what enforces
the ceiling; the front door cannot bypass it.

## 3. `cognitive_execute` outcomes

| Status            | Meaning                                                  |
|-------------------|----------------------------------------------------------|
| `no_candidates`   | Reasoner produced nothing — front door falls back to legacy. |
| `pending_approval`| Auto-approval declined; graph awaits a human.            |
| `completed`       | Graph executed successfully end-to-end.                  |
| `failed`          | Execution started but a node failed.                     |

Every successful return now carries an `auto_approved: bool` field so
callers can distinguish "owner self-approved" from "graph was already
approved on input".

### B8 — HITL hand-off

When `cognitive_execute` returns `pending_approval`, `/api/execute`
calls `_enqueue_hitl_handoff(...)` which inserts an
`aionmind_approval` record into `murphy.hitl_interventions`.  The
existing `/api/hitl/queue`, `/api/hitl/pending`, and
`/api/hitl/{id}/decide` endpoints surface and resolve it unchanged.

The hand-off is best-effort — failures are logged at DEBUG and
swallowed so a broken HITL store never breaks the request path.  On
success the intervention id is echoed back as
`aionmind_result["hitl_intervention_id"]`.

## 4. Capability bridges (Phase 2 / C9–C16)

`AionMindKernel.__init__` auto-loads seven subsystem bridges in
`_bridge_subsystem_capabilities()`.  Each bridge is wrapped in its
own try/except so a single broken subsystem cannot block the others.

| Bridge            | Caps | Highest risk | Notes                                               |
|-------------------|------|--------------|-----------------------------------------------------|
| `automations`     | 6    | HIGH         | `workflows.delete` requires approval                |
| `hitl`            | 4    | MEDIUM       | queue / pending / decide / respond                  |
| `boards`          | 5    | MEDIUM       | CRUD; delete requires approval                      |
| `founder`         | 3    | HIGH         | gated by `metadata.requires_founder`                |
| `production`      | 5    | HIGH         | `proposals.delete` is `never_auto_approve`          |
| `integration_bus` | 1    | MEDIUM       | generic `process(action, payload)` dispatch         |
| `document`        | 4    | MEDIUM       | Living-Document gates + block ops                   |

When a subsystem cannot be imported the bridge still registers its
capabilities but binds them to `make_unavailable_handler(...)` which
returns `{"status": "unavailable", "subsystem": ..., "reason": ...}`
at execute time.  Plans therefore always surface every capability;
only execution distinguishes "wired" from "unwired".

### Schema discipline (C17)

`BridgeCapability.to_capability()` raises `CapabilitySchemaError` if
either `input_schema` or `output_schema` is empty.  This makes the
"every capability has schemas" rule a runtime invariant, not a
convention.

## 5. Observability surface

| Endpoint                                  | Purpose                                                  |
|-------------------------------------------|----------------------------------------------------------|
| `GET  /api/aionmind/status`               | total registered caps + per-subsystem `bridge_counts`    |
| `GET  /api/aionmind/capabilities`         | full capability list, filterable by `provider` / `tag`   |
| `GET  /api/aionmind/metrics`              | snapshot of `cognitive_execute` outcome counters         |
| `POST /api/aionmind/orchestrate`          | plan-only; returns candidate graphs                       |
| `POST /api/aionmind/execute`              | execute pre-approved graph                                |

### E25 — outcome metrics

`kernel.metrics()` returns a dict of monotonic counters, pre-seeded
to `0`:

```json
{
  "calls_total": 0,
  "auto_approved": 0,
  "pending_approval": 0,
  "no_candidates": 0,
  "executed": 0,
  "failed": 0
}
```

Snapshot semantics: counters are process-local and reset on restart.
Consumers wanting deltas should diff successive snapshots.

### E26 — append-only audit log

When `MURPHY_AUDIT_LOG_PATH` is set (e.g.
`/var/log/murphy/aionmind-audit.jsonl`), every `cognitive_execute`
call appends one JSON line:

```json
{"ts":1714000000.0,"actor":"alice@example.com","task_type":"general",
 "status":"completed","context_id":"...","graph_id":"...",
 "execution_id":"...","auto_approved":true}
```

The writer creates parent directories as needed and is best-effort:
write failures are logged at DEBUG and swallowed.  Log rotation is
the operator's responsibility.

### D19 / D20 / D21 / D23 — terminal-architect front-door panels

The single-page UI at `aionmind.html` reuses the existing dark-teal
design tokens (Inter / JetBrains Mono, `--teal: #00D4AA`).  The tab
bar grows from four entries to five — one new **Audit** tab; D19 and
D20 enrich the existing **Status** tab in place rather than adding
new panels, on the explicit "simplified UX" requirement.

| Ticket | Where | Bound to |
|--------|-------|----------|
| D19 — capabilities table | Status tab, replacing the flat chip list | `GET /api/aionmind/capabilities` |
| D20 — outcome metrics card | Status tab, above kernel-info | `GET /api/aionmind/metrics` |
| D21 — audit-log endpoint  | new `aionmind.api.get_audit` | `GET /api/aionmind/audit` |
| D23 — audit tab           | new tab between Proposals and Memory | `GET /api/aionmind/audit?limit=100` |

`GET /api/aionmind/audit?limit=N` (1 ≤ N ≤ 500, default 50) returns
the most recent JSONL entries newest-first:

```json
{
  "enabled": true,
  "path":    "/var/log/murphy/aionmind-audit.jsonl",
  "limit":   100,
  "count":   12,
  "entries": [{"ts": 1714000000.0, "actor": "alice@example.com", ...}]
}
```

When `MURPHY_AUDIT_LOG_PATH` is **not** set the response is
`{enabled: false, path: null, count: 0, entries: []}` and the UI
shows an instructional empty state pointing back to this section.
Malformed JSONL lines are silently skipped — the audit log is
best-effort by design (E26) and the viewer must never crash on bad
input.  The endpoint is read-only; there is no write surface.

## 6. Out of scope (tracked separately)

Each item below names the **open question that blocks it** and the
**decision-maker scope**.  Engineering effort is not the bottleneck for
any of these; ratifying the decision is.  Each item should land as its
own PR once the open question is answered — bundling them together
defeats the per-PR review boundary.

* **A4** — full JWT/OIDC replacement of the legacy session token is
  ADR-0012's separate 2-release deprecation window.
  *Open question:* none — schedule is fixed in ADR-0012.
  *Owner:* platform.
* **E27** — distributed tracing (OTel) for AionMind routes.
  **The cross-cutting decision is already made** in
  [ADR-0007 (OpenTelemetry tracing is opt-in, not on-by-default)][adr0007]:
  OTel + OTLP, opt-in via `MURPHY_OTEL_ENABLED`, SDK as a production
  extra.  Because every `/api/aionmind/*` route is a FastAPI route on
  the same `app` that ADR-0007 instruments, AionMind tracing comes for
  free the moment an operator flips `MURPHY_OTEL_ENABLED=1` and
  installs the production extras.  No AionMind-specific ADR is
  required.
  *Open question:* deployment-time only — which collector endpoint
  does production point at, and what sampling ratio (`OTEL_TRACES_SAMPLER`)
  do we ship with?
  *Owner:* operations / observability platform.
* **E28** — request-rate limiting on `/api/aionmind/*`.
  *Open question:* do AionMind routes share the existing
  `forge_rate_limiter` per-tier budget, get their own per-tier
  bucket, or front-end onto a global token bucket (e.g. Redis-backed)?
  Each choice has different fairness and noisy-neighbour properties.
  *Owner:* platform + product (the choice affects what tier customers
  perceive).
* **E29** — SSE notifications on the `/api/aionmind/*` surface.
  *Open question:* payload schema (per-event-type vs. envelope) and
  client consumer plan (does the existing UI subscribe, or is this for
  external integrators?).  Without a consumer the channel is dead
  weight.
  *Owner:* product + frontend.
* **E30** — structured-log rotation for the AionMind audit JSONL.
  *Open question:* in-process rotation (Python's `RotatingFileHandler`
  / `TimedRotatingFileHandler`) vs. operator-managed rotation
  (`logrotate`, container log driver).  In-process is portable but
  conflicts with append-only audit semantics; operator-managed
  preserves the JSONL invariant at the cost of a deployment runbook.
  *Owner:* operations.
* **E31** — long-haul audit-log shipping.
  *Open question:* sink choice (S3 / Loki / a SIEM / blob storage)
  and retention policy.  Same shape as E27 — the engineering work is
  small once the sink is named.
  *Owner:* operations + compliance.

[adr0007]: adr/0007-opentelemetry-opt-in.md
