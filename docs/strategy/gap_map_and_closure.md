# Gap Map + Closure Priorities — PCR-019 / Phase 3 of Final Shape of Complete

**Plan:** `docs/strategy/final_shape_of_complete_plan.md`
**Inputs:** `ui_surface_audit.md` (Phase 1), `backend_function_catalog.md` (Phase 2)
**Output:** this file + `scripts/gap_map_check.py`
**Shipped:** 2026-06-08
**Composes with:** PCR-009 glossary, PCR-014 auto-doc, MPCS v2 Phase 1

---

## Purpose

Join the Phase 1 UI audit (116 CTAs) with the Phase 2 backend catalog
(2,164 routes) into a single decision matrix. For every gap, propose a
closure. Rank by founder-value. Map each closure to a sub-PCR
(PCR-019.1, .2, .3…) for execution in Phases 4–6.

**This phase makes decisions, not changes.** No production routes are
modified. The closure decisions are queued for Phases 4–6 to execute
with HITL approval where required.

---

## Three sections, three decisions

### A. UI without backend
Broken CTAs from Phase 1. **Fix or kill.**

### B. Backend without UI
GHOST routes from Phase 2 that 200 OK but have no UI consumer.
**Promote, document as internal, or deprecate.**

### C. UI labels not in user-description language
Where current button text is technical jargon. **Translate to human.**

---

## Section A — UI without backend (5 findings)

From Phase 1's FAKE classification:

| # | Surface | Path | Decision | Sub-PCR | Why |
|---|---|---|---|---|---|
| A1 | `/canvas` route | 404 | **FIX in Phase 5** | PCR-019.A1 | `murphy-work-canvas.html` exists at 1020 lines; needs route to serve it. Phase 5 already consolidates two canvases — this is the route mount. |
| A2 | `/api/canvas/items` | was 404, now 401 | **DOCUMENT in Phase 5** | PCR-019.A2 | Verifier discovered this is now 401-gated (auth required, real). Update Phase 1 audit to reclassify INTERNAL. Frontend just needs to authenticate. |
| A3 | `/api/canvas/attach` | was 404, now 401 | **DOCUMENT in Phase 5** | PCR-019.A3 | Same shape as A2. |
| A4 | `/api/canvas/save` | was 404, now 401 | **DOCUMENT in Phase 5** | PCR-019.A4 | Same shape as A2. |
| A5 | `/workshop`, `/dispatch`, `/workspace`, `/chain` | 404 | **KILL** | PCR-019.A5 | No HTML files exist for these. They were planned and abandoned. Remove from any nav references in `static/*.html`; no replacement needed. |

**Section A total:** 1 fix · 3 documentation reclassifications · 1 kill.
**Section A risk:** LOW. The "fix" is mounting an existing HTML file;
the "kill" removes nav entries (no production routes touched).

---

## Section B — Backend without UI (99 GHOST routes)

This is the directive's biggest finding. **99 backend routes return
200 OK with no UI handle.** Each one is one of:

- **PROMOTE** — has obvious user value, deserves a CTA
- **DOCUMENT** — legitimate machine-only endpoint, mark as INTERNAL in catalog
- **DEPRECATE** — orphan, no longer needed

Closure decisions below. **Default for ambiguous cases: DOCUMENT.**
Don't kill code we're not sure about.

### B.1 — Health/status endpoints (24 routes)

Pattern: every module ships its own `/health` or `/api/<X>/status` endpoint.

| Sample routes | Decision |
|---|---|
| `/api/audit/health`, `/api/client-solutions/health`, `/api/gate-synthesis/health`, `/api/identity/health`, `/api/internal/health`, `/api/phone/health`, `/api/vault/health` | **DOCUMENT — INTERNAL** |
| `/api/brain/status`, `/api/bus/status`, `/api/conductor/healthz`, `/api/crypto/status`, `/api/ledger/status`, `/api/pcc/status`, `/api/rosetta/status`, `/api/self-fix/status`, `/api/swarm/mind/status`, `/api/system/health`, `/api/trading/*/status` | **DOCUMENT — INTERNAL** but one is **PROMOTE** |
| **`/api/system/health`** | **PROMOTE** → new aggregate "Health" page that summarizes all `*/health` and `*/status` into one tile per subsystem (Phase 4 readout) |

**Decision rule:** 23 of 24 health endpoints stay INTERNAL. The 24th
(`/api/system/health` or equivalent aggregator) becomes a UI page —
**"System Health"** under the Shield tab.

### B.2 — Marketplace + connectors (5 routes)

| Routes | Decision |
|---|---|
| `/api/marketplace/agents`, `/api/marketplace/categories` | **PROMOTE** — `marketplace.html` likely exists somewhere; if not, build one. CTA: "Browse marketplace" |
| `/api/connectors/known`, `/api/connectors/stats` | **PROMOTE** — under Shield > Vault, add a "Connected services" tile |
| `/marketplace` (root path) | **PROMOTE** — already serves a page; just needs nav from OS |

### B.3 — Founder/admin views (8 routes)

| Routes | Decision |
|---|---|
| `/api/billing/products`, `/api/account/flow`, `/api/auth/role`, `/api/auth/whoami`, `/api/auth/providers` | **DOCUMENT — INTERNAL** (founder-control.html should consume these but they're admin-only) |
| `/founder` (page route) | **DOCUMENT** — already exists at `founder-control.html`, no gap |
| `/api/policy/autonomy/history`, `/api/repair/proposals` | **PROMOTE** — under Soul tab, add "Autonomy decisions" + "Self-repair queue" tiles |

### B.4 — Trading/wallet (6 routes)

| Routes | Decision |
|---|---|
| `/api/trading/emergency/status`, `/api/trading/graduation/status`, `/api/trading/paper/status`, `/api/trading/risk/assessment` | **DOCUMENT — INTERNAL** (trading is autonomous; UI is read-only summary, not control) |
| `/api/wallet/balances` | **PROMOTE** under llm-spend.html — extend to "Spend + Treasury" |
| `/api/crypto/status` | **DOCUMENT** |

### B.5 — Communications hub (4 routes)

| Routes | Decision |
|---|---|
| `/api/comms/email/inbox`, `/api/comms/email/outbox`, `/api/comms/video/sessions`, `/api/matrix/chat/rooms` | **PROMOTE** — Mail tab in OS dashboard only consumes outbox today. Extend to a true Comms Hub page consuming all four. Sub-PCR PCR-019.B5. |

### B.6 — Demo/export endpoints (5 routes)

| Routes | Decision |
|---|---|
| `/api/demo/deliverable/formats`, `/api/demo/export`, `/api/demo/forge-stream`, `/deck`, `/desktop`, `/desktop/install_murphy_desktop.bat` | **DOCUMENT — INTERNAL** (used by sales/demo flows, not core OS) |

### B.7 — Module instance routes (7 routes)

| Routes | Decision |
|---|---|
| `/module-instances/*` | **DOCUMENT — INTERNAL** (admin observability; not user-facing) |

### B.8 — World/business-domain endpoints (4 routes)

| Routes | Decision |
|---|---|
| `/api/world/business-domains`, `/api/corpus/stats`, `/api/visual/snapshots`, `/api/ui/links` | **DOCUMENT — INTERNAL** with one exception: `/api/ui/links` is a perfect candidate for the new aggregate Health page (B.1). |

### B.9 — Public-API surface (3 routes)

| Routes | Decision |
|---|---|
| `/api/v1/ping`, `/api/v1/docs`, `/api/v1/openapi.json` | **PROMOTE** — these are the public API surface. Build a "Developers" page under founder-control with the OpenAPI doc embedded. Sub-PCR PCR-019.B9. |

### B.10 — Roi/calendar (3 routes)

| Routes | Decision |
|---|---|
| `/api/roi-calendar/events`, `/api/cidp/stats`, `/api/info` | **PROMOTE** the ROI calendar — already referenced via `openPageDrill('roi-calendar')` in murphy-os.html as DEGRADED (the route exists but the drill is a nav stub, not a real page). Phase 4 wires the readout. |

### B.11 — Robotics / IoT (5 routes)

| Routes | Decision |
|---|---|
| `/api/picarx/spec`, `/api/phone/health`, `/household`, `/devices`, `/picarx`, `/phone` | **DOCUMENT — INTERNAL** (project work for Hawthorne's Colony / household; not a Murphy.systems product surface) |

### B.12 — Duplicate `/agents` + `/health` registrations (12+ routes)

| Pattern | Decision |
|---|---|
| `/agents` registered in `src/r604_agents_surface.py` AND `src/aionmind/chat_router.py` | **DEDUP** — one wins, other deprecated. Recommend keeping the r604 version (more recent, has artifacts). Sub-PCR PCR-019.B12. |
| `/health` registered in ~10 different module files | **DOCUMENT** — each module owns its own /health; aggregator is `/api/system/health` |
| `/audit` registered in 2 places | **DEDUP** — keep patch407_security_audit.py version |
| `/customers` registered in 2 places | **DEDUP** — investigate which is canonical |

### Section B summary

| Decision | Count | Phase |
|---|---|---|
| **PROMOTE** to new UI surface | ~14 routes → 5 new pages | Phase 4-5 |
| **DOCUMENT — INTERNAL** | ~75 routes | Phase 3 (this commit; catalog update) |
| **DEDUP** (duplicate registrations) | ~10 routes | Phase 6 (with HITL) |
| **DEPRECATE** | 0 — being conservative | future |

**The 5 new PROMOTE pages (mapped to sub-PCRs):**
1. **System Health page** (B.1) — aggregates all `*/health` endpoints → Shield tab tile
2. **Marketplace page** (B.2) — surfaces `/api/marketplace/*` → new top nav
3. **Comms Hub page** (B.5) — extends Mail tab to email + video + matrix
4. **Developers page** (B.9) — `/api/v1/openapi.json` embedded
5. **ROI Calendar page** (B.10) — make the existing drill stub a real page

---

## Section C — UI labels in jargon (translation targets)

Audit of current button text against the user-description test
("would a non-technical user understand this?"). Pulled from Phase 1's
murphy-os.html CTA list.

| Current label | User-description translation | Decision |
|---|---|---|
| ⚡ Brief Me | Get a quick brief | KEEP (already user-language) |
| 🩺 Health Check | Check the system | KEEP-ish |
| 🔄 Restart Idle | Wake up sleeping agents | TRANSLATE |
| 📜 View History | Show what changed recently | TRANSLATE |
| ✏️ Edit Soul | Adjust how I work | TRANSLATE |
| 🛡️ Run Audit | Check for problems | TRANSLATE |
| 📋 Tripwire Log | Show recent security alerts | TRANSLATE |
| 🎯 New Lead | Add a prospect | TRANSLATE |
| Bulk Approve | Approve selected | KEEP |
| `qaAction('audit')` | "Check for problems" | TRANSLATE |
| `qaAction('mind')` | "Recent thoughts" | TRANSLATE |
| `qaAction('ledger')` | "Cost log" | TRANSLATE |
| `qaAction('registry')` | "What I can do" | TRANSLATE |
| `qaAction('public_stats')` | "Live numbers" | TRANSLATE |
| Page: "Soul" | Page: "Personality" | TRANSLATE? **Open question — soul is the trademark term, may keep** |
| Page: "Shield" | Page: "Security" | TRANSLATE |
| Page: "Rosetta" (where present) | Page: "Route planner" | TRANSLATE |

**Section C decision:** ship a small translation pass in Phase 4 alongside
the drill-down wiring. ~12 button labels updated; "Soul" stays (brand term).
Sub-PCR PCR-019.C.

---

## The DEAD 122 — separate concern

The 122 DEAD routes from Phase 2 (probe returns 404/500) are NOT the
gap map — they're a **cleanup target**. Pattern analysis:

| Pattern | Count | Decision |
|---|---|---|
| `health/`, `/healthz`, `/healthz/ready` in unmounted module files | ~30 | **UNMOUNTED ROUTERS — verify intent.** Most of these are router files (`murphy_ops.py`, `murphy_edge.py`, `murphy_robotics.py`) whose APIRouter isn't mounted in app.py. Either mount them or remove the decorators. Default: KEEP (low-risk; just unused code). |
| Module-local routes with no prefix (`/customers`, `/forms`, `/history`, `/feed/*`) | ~50 | **PREFIX FIX** — these routers expect mount-prefixes like `/api/<module>/`; they fail because they're queried at root. Phase 6 or follow-up cleanup. |
| `/example`, `/git`, `/bugs`, `/bars` (tiny stubs in dev/test code) | ~15 | **DEPRECATE — KILL** in Phase 6 with HITL approval |
| Real broken handlers (500 errors) | 1 — `/api/auth/verify-email` | **FIX** — known broken auth path. Sub-PCR PCR-019.D1, **high priority**. |
| Unknown | ~26 | INVESTIGATE in Phase 6 |

**Single critical fix from the DEAD list:** `/api/auth/verify-email`
returns 500. That's a user-facing auth path. **Fix in Phase 6 with HITL.**

---

## Closure priorities (founder-value ranked)

If we ship one closure at a time, this is the order:

| Rank | Closure | Sub-PCR | Phase | Effort | Founder-value |
|---|---|---|---|---|---|
| 1 | Fix `/api/auth/verify-email` 500 | PCR-019.D1 | Phase 6 | LOW | HIGH (broken auth path) |
| 2 | Mount `/canvas` route | PCR-019.A1 | Phase 5 | LOW | HIGH (1020 lines of UI hidden behind 404) |
| 3 | System Health aggregator page | PCR-019.B1 | Phase 4 | MED | HIGH (24 routes → 1 page) |
| 4 | Comms Hub page | PCR-019.B5 | Phase 4 | MED | MED |
| 5 | Marketplace nav promotion | PCR-019.B2 | Phase 4 | LOW | MED |
| 6 | ROI Calendar page (was DEGRADED stub) | PCR-019.B10 | Phase 4 | MED | MED |
| 7 | Developers page (OpenAPI) | PCR-019.B9 | Phase 4 | LOW | LOW-MED |
| 8 | UI label translations (12 labels) | PCR-019.C | Phase 4 | LOW | MED |
| 9 | Kill `/workshop` `/dispatch` `/workspace` `/chain` nav refs | PCR-019.A5 | Phase 4 | LOW | LOW |
| 10 | Update Phase 1 audit re: canvas API now 401 | PCR-019.A2-4 | Phase 4 | LOW | LOW |
| 11 | Dedup `/agents` `/health` `/audit` `/customers` registrations | PCR-019.B12 | Phase 6 (HITL) | HIGH | MED |
| 12 | Document 75 INTERNAL routes | PCR-019.B-doc | Phase 3 (this commit) | n/a | LOW (clarity) |
| 13 | Mount or remove unmounted-router DEAD routes (~30) | PCR-019.D-mount | Phase 6 (HITL) | HIGH | LOW |
| 14 | Kill stub DEAD routes (`/example` `/bars`…) | PCR-019.D-stub | Phase 6 (HITL) | LOW | LOW |

---

## What this phase does NOT do

- Does not modify any production route
- Does not fix `/api/auth/verify-email` (that's Phase 6)
- Does not mount `/canvas` (that's Phase 5)
- Does not create the System Health page (that's Phase 4)
- Does not translate any UI label (that's Phase 4)
- Does not kill any DEAD route (that's Phase 6 with HITL)

What it DOES:
- Names every gap from Phases 1+2
- Proposes a closure for each
- Ranks closures by founder-value
- Maps closures to sub-PCRs for execution
- Identifies the ONE high-priority real bug: verify-email 500

---

## Verifier

`scripts/gap_map_check.py` is the verifier. It:

1. Confirms this doc exists with all expected sections
2. Confirms inputs (ui_surface_audit.md, backend_function_catalog.md) exist
3. Confirms every closure rank 1-10 has a sub-PCR ID
4. Re-probes the verify-email endpoint and confirms it still 500s
   (or reports if it's been fixed since this commit — regression check)
5. Confirms the `/canvas` route is still 404 (Phase 5 has not yet shipped)
6. Confirms /workshop /dispatch /workspace /chain still 404
   (Section A5 kill targets still in their pre-kill state)

Exit 0 = Phase 3 verifier green. Exit 2 = drift.

---

## Composition

- **Phase 4** consumes ranks 3, 4, 5, 6, 7, 8 (the 6 UI builds + label
  translations). 5 new pages + 12 translated labels.
- **Phase 5** consumes ranks 2, 10 (canvas mount + canvas API audit update).
- **Phase 6** consumes ranks 1, 11, 13, 14 (verify-email fix + dedup +
  unmounted router decisions + stub cleanups), all with HITL approval.
- Ranks 9 and 12 ship as part of Phase 4 alongside the UI builds (low
  effort, batched).

---

## Progress

Phase 3 status: **✓ COMPLETE.**

Total closures named: **14 sub-PCRs.**
- 7 ship in Phase 4 (UI builds + translations + minor cleanups)
- 2 ship in Phase 5 (canvas)
- 4 ship in Phase 6 (DEAD-list decisions, all with HITL)
- 1 documented as already-shipped (the 75 INTERNAL doc updates → catalog has them)

**3 of 6 phases done. 3 sessions remaining to FINAL SHAPE OF COMPLETE.**
