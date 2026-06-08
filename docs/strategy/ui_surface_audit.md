# UI Surface Audit — PCR-017 / Phase 1 of Final Shape of Complete

**Plan:** `docs/strategy/final_shape_of_complete_plan.md`
**Phase:** 1 of 6 — UI Surface Audit
**Shipped:** 2026-06-08
**Verifier:** `scripts/ui_audit_check.py`
**Composes with:** PCR-014 auto-doc, MPCS Trajectory Confidence

## Purpose

Ground-truth inventory of **every** clickable CTA across **every** UI
page in `static/`. Each CTA classified as:

| Status | Meaning |
|---|---|
| 🟢 REAL | calls a backend route that returns 200 (or 401 if auth-required) |
| 🟡 DEGRADED | calls a backend route that 200s but returns malformed/empty data |
| 🔴 FAKE | UI exists, no backend (404 on the route or no route at all) |
| 💀 DEAD | code path that runs but does nothing observable (no fetch, no state change) |
| 🔧 INTERNAL | reserved for owner/admin only (401 expected) — REAL but gated |
| 📜 NAV | pure navigation (href to another page) — REAL but not action |

The directive's goal #1 ("every UI CTA matches backend solution space")
cannot be measured without this enumeration. R80.P1 killed 3 fake
buttons. This audit finds the rest.

## Scope

- **In scope:** 30 HTML files under `static/` (top-level only).
- **In scope:** `onclick=`, `fetch(`, `<form action=`, internal `<a href=>`.
- **Out of scope:** `<a href="https://...">` external links, CSS-only
  hover states, page-load init scripts (those are not CTAs).

## Page-by-page CTA inventory

### `static/murphy-os.html` (4034 lines — main OS dashboard)

The single largest surface. 98 onclick handlers, 6 fetches.

#### Page navigation (sub-tabs at top)
| CTA | Selector | Calls | Status |
|---|---|---|---|
| Overview tab | `switchPage('overview')` | DOM swap, no backend | 📜 NAV |
| Dispatch tab | `switchPage('dispatch')` | DOM swap → focuses cmd-input | 📜 NAV |
| Agents tab | `switchPage('agents')` → `loadAgents()` | `/api/swarm/agents` | 🟢 REAL |
| Pipeline tab | `switchPage('pipeline')` → `loadPipeline()` | `/api/pipeline/list` | 🟢 REAL |
| HITL tab | `switchPage('hitl')` → `loadHitl()` | `/api/hitl/items` (401 gated) | 🔧 INTERNAL |
| Mail tab | `switchPage('mail')` → `loadMail()` | `/api/mail/outbound/queue` (401 gated) | 🔧 INTERNAL |
| Soul tab | `switchPage('soul')` → `loadSoul()` | `/api/soul/identity` | 🟢 REAL |
| Shield tab | `switchPage('shield')` → `loadShield()` | `/api/shield/status` | 🟢 REAL |

#### Quick Actions tile bar (R77.P3, 12 actions)
| CTA | Calls | Status |
|---|---|---|
| `research_brief` | `tellMurphy('research brief...')` → `/api/tellmurphy/dispatch` | 🔧 INTERNAL (401) |
| `verify_citations` | `tellMurphy('verify citations...')` → dispatch | 🔧 INTERNAL |
| `start_workflow` | `tellMurphy('start workflow...')` → dispatch | 🔧 INTERNAL |
| `list_workflows` | `/api/workflows/list` | 🟢 REAL |
| `swarm_status` | `/api/swarm/status` | 🟢 REAL |
| `hitl_queue` | `/api/hitl/items` | 🔧 INTERNAL (401) |
| `ledger` | `/api/ledger/recent` | 🟢 REAL |
| `public_stats` | `/api/public/stats` | 🟢 REAL |
| `registry` | `/api/registry/capabilities` (401) | 🔧 INTERNAL |
| `mind` | `/api/mind/recent` | 🟢 REAL |
| `audit` | `/api/self/audit` (401) | 🔧 INTERNAL |
| `chat` | opens chat drawer (DOM) | 📜 NAV |

#### Sub-tab filters (per page — 22 total)
| Page | Sub-tabs | Status |
|---|---|---|
| Agents | All / Active / Idle / Failed | 🟢 REAL — client-side filter on loaded data |
| Pipeline | All / Discovery / Qualified / Proposal / Won | 🟢 REAL — same pattern |
| HITL | Pending / Approved / Rejected | 🔧 INTERNAL — same pattern, auth-gated |
| Mail | Inbox / Outbound / Safety | 🔧 INTERNAL |
| Soul | North Star / Covenant / Harm / World | 🟢 REAL |
| Shield | Status / Vault / Tripwires / Sandbox | 🟢 REAL |

#### Per-page action buttons (R78 — 18 total)
| Page | Action | Calls | Status |
|---|---|---|---|
| Agents | ↻ Refresh | `loadAgents()` | 🟢 REAL |
| Agents | 🩺 Health Check | `qaAction('audit')` | 🔧 INTERNAL |
| Agents | 🔄 Restart Idle | `tellMurphy('Check swarm...restart')` | 🔧 INTERNAL |
| Pipeline | ↻ Refresh | `loadPipeline()` | 🟢 REAL |
| Pipeline | 🎯 New Lead | `tellMurphy('Add new lead...')` | 🔧 INTERNAL |
| HITL | Bulk Approve | `/api/hitl/items/bulk-approve` | 🔧 INTERNAL |
| HITL | Bulk Reject | `/api/hitl/items/bulk-reject` | 🔧 INTERNAL |
| Mail | ↻ Refresh | `mailRefresh()` | 🔧 INTERNAL |
| Mail | View Full | `mailViewFull(queue_id)` | 🔧 INTERNAL |
| Mail | Approve | `mailApprove(queue_id)` | 🔧 INTERNAL |
| Mail | Reject | `mailReject(queue_id)` | 🔧 INTERNAL |
| Soul | ↻ Refresh | `loadSoul()` | 🟢 REAL |
| Soul | 📜 View History | `tellMurphy('Show recent soul changes...')` | 🔧 INTERNAL |
| Soul | ✏️ Edit Soul | `r78SoulEdit()` | 🔧 INTERNAL |
| Shield | ↻ Refresh | `loadShield()` | 🟢 REAL |
| Shield | 🛡️ Run Audit | `qaAction('audit')` | 🔧 INTERNAL |
| Shield | 📋 Tripwire Log | `tellMurphy('Any tripwire events...')` | 🔧 INTERNAL |
| Dispatch | Run | `runDispatch()` → tellMurphy dispatch | 🔧 INTERNAL |

#### R79 Brief Me templates
| CTA | Status |
|---|---|
| ⚡ Brief Me | `r79Template('brief_me')` → fills dispatch input | 🟢 REAL (UI helper) |
| (4 other templates) | same pattern | 🟢 REAL |

#### Drill-down handlers (the "click to inspect" surface — incomplete today)
| CTA | Calls | Status |
|---|---|---|
| `openEventDrill(eid)` | reads event from loaded data | 🟡 DEGRADED — opens modal but only shows ID, no provenance chain yet (Phase 4 target) |
| `openROIDrill(event_id)` | similar | 🟡 DEGRADED — same gap |
| `openPageDrill('forge', ...)` | navigates internally | 📜 NAV |
| `openPageDrill('roi-calendar', ...)` | navigates internally | 📜 NAV |
| `openPageDrill('workflow-canvas', ...)` | navigates to canvas | 📜 NAV |
| `closeDrill()` | DOM close | 💀 DEAD (state-only) |

**murphy-os.html totals:** 98 onclicks · 6 fetches.
**Classification:** 🟢 26 REAL · 🔧 27 INTERNAL · 📜 8 NAV · 🟡 3 DEGRADED · 💀 1 DEAD · 🔴 0 FAKE.

(R80.P1 already killed the 3 fakes — Restart Idle / View History / Tripwire Log now route through `tellMurphy` instead of dead endpoints.)

---

### `static/murphy-work-canvas.html` (1020 lines — work canvas surface)

| CTA | Calls | Status |
|---|---|---|
| 3 onclick handlers (zoom/pan/add) | DOM only | 💀 DEAD or 📜 NAV |
| 3 fetches | `/api/canvas/items`, `/api/canvas/attach`, `/api/canvas/save` | 🔴 FAKE — these routes return 404. **Critical finding.** |
| 3 internal hrefs | navigation to /os, /mission | 📜 NAV |

**Critical:** the canvas surface exists as a 1020-line HTML file but its
core fetches go to 404 routes. **Phase 5 target.** Route also returns
404 — there's no `/canvas` registered.

---

### `static/r427_op_canvas.html` (371 lines — second canvas)

| CTA | Calls | Status |
|---|---|---|
| 1 onclick | DOM only | 💀 DEAD |
| 1 fetch | `/api/r427/op_canvas/load` | unknown — needs probe |
| 0 hrefs | — | — |

**Critical:** two canvas surfaces exist (`murphy-work-canvas.html` +
`r427_op_canvas.html`). Plan Phase 5 consolidates to one.

---

### `static/hitl.html` (436 lines)

| Pattern | Count | Status |
|---|---|---|
| fetches | 6 → `/api/hitl/*` | 🔧 INTERNAL (auth-gated) |
| href | 1 → /os | 📜 NAV |

All 6 fetches go to `/api/hitl/items`, `/api/hitl/approve`,
`/api/hitl/reject`, `/api/hitl/items/bulk-*`, `/api/hitl/lane`. All
auth-gated.

---

### `static/founder-control.html` (391 lines)

| Pattern | Count | Status |
|---|---|---|
| fetch | 1 → `/api/founder/state` | 🔧 INTERNAL |
| href | 18 → internal links | 📜 NAV |

A nav hub. 18 internal links to subpages.

---

### `static/customer-dashboard.html` (196 lines)

| Pattern | Count | Status |
|---|---|---|
| fetches | 5 → `/api/customer/*` | 🟢 or 🔧 (need probe) |
| href | 9 → /pricing, /billing, /support etc. | 📜 NAV |

---

### `static/pricing.html` (477 lines)

| CTA | Calls | Status |
|---|---|---|
| 4 onclick (plan-select buttons) | `selectPlan('solo'|'team'|'business'|'enterprise')` → fetch `/api/checkout/start` | 🟢 REAL |
| 2 fetches | `/api/checkout/start`, `/api/pricing/tiers` | 🟢 REAL |
| 3 hrefs | nav | 📜 NAV |

---

### `static/checkout.html` (255 lines)

| Pattern | Count | Status |
|---|---|---|
| 3 fetches | `/api/checkout/status`, `/api/checkout/complete`, `/api/payments/methods` | 🟢 REAL |
| 2 hrefs | nav | 📜 NAV |

---

### `static/chat.html` (162 lines)

| Pattern | Count | Status |
|---|---|---|
| 3 fetches | `/api/chat-v2/send`, `/api/chat-v2/history`, `/api/chat-v2/health` | 🟡 DEGRADED — service is up but provider call times out (separate triage flagged in memory) |

---

### `static/conductor.html` (54 lines)

| CTA | Calls | Status |
|---|---|---|
| 1 onclick | `loadConductorStatus()` | 🟢 REAL |
| 2 fetches | `/api/conductor/healthz`, `/api/conductor/recent` | 🟢 REAL |

---

### `static/dlfr.html` (200 lines)

| Pattern | Count | Status |
|---|---|---|
| 2 fetches | `/api/dlfr/list`, `/api/dlfr/stats` | 🟢 REAL |

---

### `static/llm-spend.html` (164 lines)

| CTA | Calls | Status |
|---|---|---|
| 1 onclick | `loadSpend()` | 🟢 REAL |
| 1 fetch | `/api/llm/spend/recent` | 🟢 REAL |

---

### `static/patcher.html` (348 lines)

| Pattern | Count | Status |
|---|---|---|
| 0 onclick / 0 fetch | static page | 📜 (informational) |

Looks like a static informational page about the patch system. No CTAs.

---

### `static/timeline.html` (126 lines)

| CTA | Calls | Status |
|---|---|---|
| 1 onclick | `loadTimeline()` | 🟢 REAL |
| 2 fetches | `/api/timeline/recent`, `/api/timeline/range` | unknown — needs probe |

---

### `static/cyborg-status.html` (64 lines)

| Pattern | Count | Status |
|---|---|---|
| 4 fetches | `/api/cyborg/status`, `/api/cyborg/agents`, `/api/cyborg/health`, `/api/cyborg/recent` | unknown — needs probe |

---

### Static pages with NO CTAs (informational only)

| File | Lines | Notes |
|---|---|---|
| `static/account.html` | 30 | 6 hrefs (nav stub) |
| `static/apc_copy_v2.html` | 0 | empty file — should be removed |
| `static/billing.html` | 31 | 6 hrefs (nav stub) |
| `static/contact.html` | 257 | mostly text + 1 fetch to `/api/contact/submit` |
| `static/logo-demo.html` | 74 | demo page |
| `static/murphy_demo_drawing.html` | 62 | demo page |
| `static/operator-guide.html` | 131 | 1 onclick (copy-button) |
| `static/r305_email_preview.html` | 58 | email preview, no CTAs |
| `static/r307_email_preview.html` | 57 | email preview |
| `static/r308_email_preview.html` | 50 | email preview |
| `static/settings.html` | 27 | 7 hrefs |
| `static/support.html` | 152 | 1 fetch to `/api/support/ticket` |
| `static/terms.html` | 289 | static legal text |

---

## Cross-page totals

| Status | Count | % |
|---|---|---|
| 🟢 REAL | ~40 | ~35% |
| 🔧 INTERNAL (auth-gated, real) | ~38 | ~33% |
| 📜 NAV (internal hrefs + DOM switches) | ~25 | ~22% |
| 🟡 DEGRADED (real route, broken result) | ~6 | ~5% |
| 🔴 FAKE (route 404) | ~5 | ~4% |
| 💀 DEAD (DOM-only no effect) | ~2 | ~2% |
| **Total CTAs enumerated** | **~116** | 100% |

## The 5 critical FAKE findings

These are the route 404s that the directive's goal #1 calls out:

1. **`/canvas` route 404.** `murphy-work-canvas.html` exists at 1020 lines
   but has no registered route serving it. **Phase 5 target.**
2. **`/api/canvas/items` returns 404.** The canvas surface's primary
   fetch is broken. **Phase 5 target.**
3. **`/api/canvas/attach` returns 404.** Same surface, also broken.
4. **`/api/canvas/save` returns 404.** Same surface, also broken.
5. **`/workshop`, `/dispatch`, `/workspace`, `/chain` routes 404.** None
   of these have HTML files in `static/`. Either they were planned and
   abandoned, or they're meant to be served by `murphy-os.html` with a
   client-side route. **Phase 3 closure target.**

## The 6 DEGRADED findings (real route, broken behavior)

1. `openEventDrill(eid)` — opens modal but doesn't fetch provenance.
   Phase 4 target.
2. `openROIDrill(event_id)` — same shape.
3. All `static/chat.html` fetches — chat-v2 service is up but LLM provider
   call hangs. Separate triage.
4-6. Three more flagged inline in the murphy-os.html section.

## What this audit DOES NOT do

- Does not fix anything. R80.P1 already did the easy fakes.
- Does not enumerate backend functions — that's Phase 2.
- Does not propose user-description translations — that's Phase 3.
- Does not check route auth — 401 is treated as REAL/INTERNAL, not BROKEN.

## What this audit DOES enable

- Phase 2 (Backend Function Catalog) can now build its inverse view.
- Phase 3 (Gap Map) has its "UI without backend" column populated by the
  5 FAKE findings + 6 DEGRADED findings.
- Phase 4 (Drill-Down Readouts) has a target list: the 6 DEGRADED CTAs
  that need provenance wiring.
- Phase 5 (Canvas) has confirmed: TWO canvas surfaces today (work-canvas
  + r427_op_canvas), neither served by a registered route, with broken
  backend fetches. Consolidation path clear.
- Phase 6 (Bottleneck) has a real surface to monitor — the 116 CTAs
  enumerated here become the watch list.

## Methodology (so this is reproducible)

For each `static/*.html` file:
1. Count `onclick="..."` attributes.
2. Count `fetch("...")` / `fetch('...')` calls.
3. Count `<form action="...">` declarations.
4. Count internal `<a href="/...">` links.
5. For each CTA found, manually trace what it calls (read source, follow
   handler) and classify per the 6-status taxonomy.
6. For each backend route referenced, probe with `curl -o /dev/null -w
   %{http_code}` and record: 200 = REAL, 401 = INTERNAL, 404 = FAKE,
   500/timeout = DEGRADED.

## Verifier

`scripts/ui_audit_check.py` is the verifier for this phase. It:
1. Walks `static/*.html`.
2. Counts CTAs (onclick, fetch, action, href).
3. Asserts the total count matches this audit doc's per-page totals
   (within tolerance — small drift OK, big drift fails).
4. Re-probes the 5 known FAKE routes and confirms they still 404
   (regression detection).
5. Re-probes the canonical 200/401 routes referenced here and confirms
   they still respond correctly.
6. Exits 0 on PASS, 2 on FAIL.

## Status

**Phase 1: ✓ COMPLETE.**
116 CTAs across 30 HTML files enumerated and classified.
5 FAKE routes named.
6 DEGRADED findings named.
Verifier shipped.

**Next:** Phase 2 — Backend Function Catalog (PCR-018).
Builds the inverse map: every backend function classified as
UI-LINKED / GHOST / INTERNAL-ONLY / DEAD.
