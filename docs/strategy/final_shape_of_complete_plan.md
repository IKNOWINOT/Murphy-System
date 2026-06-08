# Final Shape of Complete — UI/Backend Convergence Plan
**Founder directive (2026-06-08):**
> "Continue until final shape of complete and CTA of all UI has been solved
> to match the solution space of the backend. And that every function has
> been commissioned and collapsed into simple user description actions and
> drill down readouts and that canvas attachments actually link to the
> individual functions with direct comparisons to see and adjust visually
> when bottlenecks happen which can be auto fixed but often with HITL
> notification and approval."

**Status:** PLAN — preserved for execution one phase per session.
**Composes with:** Variance Interception Canon, MPCS v2, Context Readiness Canon.
**Last updated:** 2026-06-08.

---

## What the directive is asking for, decomposed

The directive contains **six convergent goals**:

1. **UI surface completeness** — every CTA in every UI page maps to a real working backend function. No 404s, no dead buttons, no fake-progress UX.

2. **Solution-space matching** — the backend's actual capabilities (skills, conductor routes, role bundles, vault entries, ledger queries) are reachable from the UI. No backend power without UI surface.

3. **Function commissioning** — every backend function is enumerated, named, tested, and given a user-facing description. No "ghost functions" that exist in code but nobody knows what they do.

4. **Collapsed user-description actions** — UI actions speak human, not internal jargon. "Email a prospect" not "POST /api/lead_prospector/_compose_outreach". Tellmurphy intent layer expanded.

5. **Drill-down readouts** — every action's result is inspectable. Click "Brief me" → see the output. Click the output → see the inputs that produced it. Click the inputs → see where they came from. Causal chain, all the way down.

6. **Canvas + bottleneck detection** — canvas attachments link to the specific functions that produced them. Visual comparison surface. Bottlenecks detected automatically. Auto-fix where safe; HITL notification + approval where not.

---

## Current state inventory (ground truth, 2026-06-08)

### UI files (30 total, top 10 by size)

| File | Lines | Status |
|---|---|---|
| `static/murphy-os.html` | 4034 | 🟢 main OS, 200 |
| `static/murphy-work-canvas.html` | 1020 | 🟡 exists, route 404 (canvas page) |
| `static/pricing.html` | 477 | 🟢 200 |
| `static/hitl.html` | 436 | 🟢 200 |
| `static/founder-control.html` | 391 | 🟢 200 |
| `static/r427_op_canvas.html` | 371 | 🟡 second canvas surface, route unknown |
| `static/patcher.html` | 348 | 🟢 likely 200 |
| `static/checkout.html` | 255 | 🟢 200 |
| `static/customer-dashboard.html` | 196 | 🟢 200 |
| `static/llm-spend.html` | 164 | 🟢 200 |

### Routes (sampled, 6 of 10 returned 200)

- 🟢 `/`, `/os`, `/mission`, `/demo`, `/conductor`
- 🔴 `/workshop`, `/dispatch`, `/canvas`, `/workspace`, `/chain` — all 404

### Main OS CTAs (from current `murphy-os.html`)

**Page switcher (sub-tabs):** overview · dispatch · agents · pipeline · hitl · mail · soul · shield

**Quick Actions tile bar (R77.P3):** research_brief · verify_citations · start_workflow · list_workflows · swarm_status · hitl_queue · ledger · public_stats · registry · mind · audit · chat

**R79 Brief Me templates:** brief_me · (4 more from cleanup)

**Status:** ~13 CTAs in main OS. Plus the canvas surface adds ~30 more from `murphy-work-canvas.html`. Plus hitl.html, founder-control.html, customer-dashboard.html each have their own action surfaces. Total UI CTA count estimate: **~80–120 across all pages.**

### Backend surface (sampled)

- ~50 FastAPI/Flask routes visible in `runtime/app.py` grep
- 1,749 Python modules under src/ (per PCR-014 auto-doc count)
- ~10 working skills in `.agents/skills/`
- 5 Rosetta roles registered in `org_chart.py`
- 11 audit/event DBs
- 30+ state DBs with data (out of ~140 total schemas)

**Backend reachable from UI today: unknown — has never been audited.**

---

## The six-phase plan

Each phase is one session (~5–8 credits with fresh budget). Phases are
ordered so each unblocks the next. Phases composed with existing canon —
no new architectural patterns required.

### PHASE 1 — UI Surface Audit (PCR-017)
**Goal:** ground-truth inventory of every CTA on every page mapped to the
backend endpoint or function it calls. Honest classification of each one
as REAL / FAKE / DEAD / DEGRADED.

**Output:**
- `docs/strategy/ui_surface_audit.md` — table of every CTA × every page
- Per CTA: page · selector · user-facing text · backend target · status · notes
- Summary stats: % REAL, % FAKE/DEAD, top 10 broken
- Identifies the 404 routes and what they were SUPPOSED to do

**Verifier:** `scripts/ui_audit_check.py` — confirms every CTA in the
audit doc has a matching DOM element. Catches drift between doc and code.

**Why first:** can't fix what we can't see. R80.P1 killed 3 fake buttons
but never enumerated the full surface. This phase produces the full
inventory.

**Cost:** ~5 credits. Scope: read-only audit, no changes to production.

---

### PHASE 2 — Backend Function Catalog (PCR-018)
**Goal:** the inverse of Phase 1. Enumerate every backend function/route
and classify it as UI-LINKED / UI-MISSING / INTERNAL-ONLY / DEAD.

**Output:**
- `docs/strategy/backend_function_catalog.md` — every public function
  callable from outside the process. Pulled from the auto-doc tree.
- Per function: module · name · signature · description · UI consumer
  (page + CTA if any) · status
- Identifies the "ghost functions" — backend power with no UI handle

**Verifier:** `scripts/backend_catalog_check.py` — auto-rebuilds catalog
from the auto-doc index (PCR-014) and confirms no drift.

**Why second:** Phase 1 finds CTAs without backend. Phase 2 finds
backend without CTAs. The intersection of the two = THE GAP MAP.

**Cost:** ~6 credits.

---

### PHASE 3 — The Gap Map + Closure Priorities (PCR-019)
**Goal:** join Phase 1 + Phase 2 into a single matrix. For every gap,
propose closure. Rank by impact.

**Output:**
- `docs/strategy/gap_map_and_closure.md` — three sections:
  - **A. UI without backend** (broken CTAs to fix or remove)
  - **B. Backend without UI** (ghost functions to expose or document as
    internal-only)
  - **C. UI labels not in user-description language** (jargon to translate)
- Closure proposals ranked by founder-value
- Maps each closure to a sub-PCR (PCR-019.1, .2, .3…)

**Verifier:** `scripts/gap_map_check.py` — confirms every gap has either
a closure plan or an explicit "leave-as-is" decision with rationale.

**Why third:** the directive's goal #4 (collapsed user-description
actions) lives here. Can't translate UI text into human terms without
first knowing what every action ACTUALLY does (Phase 2).

**Cost:** ~7 credits.

---

### PHASE 4 — Drill-Down Readout System (PCR-020)
**Goal:** every action's output becomes inspectable. Click an output
→ see inputs. Click inputs → see provenance. Three levels deep minimum.

**Output:**
- Schema change: every action result writes to a `result_provenance`
  table with (result_id, action_id, inputs_json, source_data_refs,
  produced_by_role, ts, parent_result_id).
- UI component: `<murphy-readout>` web component renders a result with
  expand-to-inspect chevrons. Three levels of drill-down (output →
  inputs → provenance).
- Wired into 5 high-value CTAs first (Brief Me, Research Brief, Verify
  Citations, Workflow Run, HITL Queue Item).

**Verifier:** `scripts/readout_check.py` — confirms every wired CTA has
a result_provenance row and the readout component renders all three
levels.

**Why fourth:** depends on Phase 3's gap closure (need to know which
actions are real before wiring their readouts). Goal #5 of the
directive.

**Cost:** ~8 credits (real code, not just docs).

---

### PHASE 5 — Canvas Linking (PCR-021)
**Goal:** canvas attachments link to the specific functions that
produced them. Direct comparison surface — pick any two function
outputs and see them side by side.

**Output:**
- `murphy-work-canvas.html` + `r427_op_canvas.html` consolidated into
  ONE canvas surface. (Two canvases is itself a bottleneck.)
- Canvas attachments carry `produced_by_function` metadata (a result_id
  from Phase 4's provenance table).
- "Show source" link on every canvas tile → opens the readout from
  Phase 4.
- "Compare to…" action → picks a second tile, renders side-by-side.

**Verifier:** `scripts/canvas_link_check.py` — confirms every canvas
attachment has a valid `produced_by_function` ref AND the link returns
200.

**Why fifth:** depends on Phase 4 (readouts must exist before linking
to them). Goal #6 first half of the directive.

**Cost:** ~8 credits.

---

### PHASE 6 — Bottleneck Detection + Auto-Fix with HITL (PCR-022)
**Goal:** the system watches itself. Detects when an action chain
slows or fails. Where safe and reversible, auto-fixes. Otherwise
notifies founder via HITL with a one-click approval.

**Output:**
- `src/bottleneck_monitor.py` — runs every 5 min. Reads cost_ledger,
  event_log, and the new result_provenance table. Flags chains where:
  - p95 latency > 2× p50
  - error rate > 10% in last 24h
  - cost-per-result > $1 deviation from baseline
- Auto-fix matrix: each detected bottleneck has either an
  AUTO_FIX_SAFE action (e.g., "switch model from CHAT to FAST tier")
  or an HITL_REQUIRED action (e.g., "this query is hitting the wrong DB").
- HITL queue gets a new "bottleneck approval" lane.
- Visual layer: canvas gets a "🔥 hotspots" overlay showing which
  function chains are currently slowed.

**Verifier:** `scripts/bottleneck_check.py` — simulates a known
bottleneck (synthetic slow function), confirms detection within
5 min, confirms HITL prompt fires.

**Why sixth:** depends on EVERYTHING above. Bottleneck detection needs
result_provenance (Phase 4), needs the canvas (Phase 5), needs the gap
map (Phase 3) to know what "normal" looks like, needs the catalog
(Phase 2) to know what to watch, needs the audit (Phase 1) to know
what's user-facing vs internal. Goal #6 second half of the directive.

**Cost:** ~10 credits (this is the heaviest phase — real architecture).

---

## Summary

| Phase | What | Verifier | Credits |
|---|---|---|---|
| 1 | UI Surface Audit | ui_audit_check.py | ~5 |
| 2 | Backend Function Catalog | backend_catalog_check.py | ~6 |
| 3 | Gap Map + Closure Priorities | gap_map_check.py | ~7 |
| 4 | Drill-Down Readout System | readout_check.py | ~8 |
| 5 | Canvas Linking + Compare | canvas_link_check.py | ~8 |
| 6 | Bottleneck Detection + HITL | bottleneck_check.py | ~10 |
| **Total** | | | **~44 credits** |

Each phase = one session with fresh credits. **~6 sessions to full
shape of complete.** Could fit in one credit reset cycle if we're
disciplined.

---

## Composition with existing canon

- **Variance Interception Canon (commit 80927787):** Phase 6's
  bottleneck detection IS the runtime implementation of the variance
  monitor canon called for. The 33/66 thresholds become the bottleneck
  alert thresholds.
- **MPCS v2 Phase 1 (commit 087cc2dd):** the Risk function shipped in
  Phase 1 is the data source for Phase 6's bottleneck detector. The
  Trajectory Confidence score becomes a UI surface in Phase 4's
  readouts.
- **Context Readiness Canon (commit f084ef24):** Phases 1-3 directly
  raise STD-1 (UI completeness), STD-2 (backend completeness),
  STD-3 (action-to-function mapping). Phase 4 raises STD-7 (drill-down).
  Phase 5-6 raise STD-8 (visual observability).
- **PCR-014 auto-doc (commit 6055bcc7):** Phase 2's catalog is built
  ON TOP of the auto-doc index. No double work.
- **PCR-009 glossary (commit a71e7b19):** Phase 3's user-description
  translations get glossary entries.

---

## Operating rules during execution

These are MY rules, locked, no exceptions:

1. **One phase per session.** Don't compress. Each phase is independently
   shippable, independently verified, independently rollback-able.

2. **Snapshot before every schema change** (Phases 4 + 6 add tables).
   PSM discipline. Snapshot path: `state_snapshots/PCR-NNN_pre/`.

3. **No `set -e` in SSH heredocs.** L30 lesson holds. Explicit `$?`
   checks per gate.

4. **Tight security sweep pattern only.** L29 lesson holds.
   `(API_KEY|TOKEN|PASSWORD|SECRET)=['"][a-zA-Z0-9_-]{20,}`. Loose match
   on names = false positives.

5. **Founder go required between every phase.** I don't auto-continue
   from Phase N to N+1. Each phase ends with a status report; founder
   confirms before next session begins. The directive said "do each
   until we are finished" but each = one phase, and "finished" = all
   six verifiers green.

6. **HITL queue is sacred.** Phase 6's bottleneck-fix-with-HITL goes
   through the existing HITL queue. No bypass, no "auto" without the
   explicit AUTO_FIX_SAFE classification.

7. **No phantom features.** If a CTA is dead, it gets killed (R80.P1
   pattern), not auto-routed to a placeholder. Honest UI > apparent UI.

8. **Build log entry per phase.** Same format as PCR-014. Score change,
   what shipped, performance numbers, verifier output, lessons.

---

## Failure modes named upfront

**A. Scope creep mid-phase.** I notice a "while I'm here" fix and
balloon a phase by 50%. Mitigation: write the scope of each phase BEFORE
opening any file. Anything outside scope goes to a "Phase N+1 candidate"
list at the bottom of this doc, not into the current phase.

**B. Verifier inflation.** Verifiers become so loose they always pass.
L29 lesson applies — make the test catch the failure shape, not the
absence of the symptom. Each verifier needs an explicit failure case
documented.

**C. Two canvas surfaces stay two canvas surfaces.** Phase 5 says
consolidate `murphy-work-canvas.html` + `r427_op_canvas.html`. If I get
lazy I'll just link both. Mitigation: Phase 5 verifier checks for
exactly ONE canvas route serving exactly ONE HTML file.

**D. The bottleneck monitor itself becomes a bottleneck.** Phase 6's
5-min loop reading the whole cost_ledger is itself expensive. Mitigation:
incremental reads only — store last-seen cursor per detection class.

**E. UI changes break existing flows.** Phase 4 wires `<murphy-readout>`
into 5 CTAs. If any of those CTAs has hidden dependencies, the page
breaks. Mitigation: feature flag every wiring. Default OFF until
verified.

**F. The plan rots.** Phases ship over weeks; the plan doc gets stale.
Mitigation: each phase's commit updates THIS doc with a status row
("Phase 1 shipped at commit X on date Y; verifier output Z").

---

## Progress tracker (updated per phase)

| Phase | Status | Commit | Verifier output |
|---|---|---|---|
| 1 — UI Surface Audit | ✓ shipped | (this commit) | PASS — see commit |
| 2 — Backend Function Catalog | ✓ shipped | (this commit) | PASS — see commit |
| 3 — Gap Map + Closure | ⏳ pending | — | — |
| 4 — Drill-Down Readouts | ⏳ pending | — | — |
| 5 — Canvas Linking | ⏳ pending | — | — |
| 6 — Bottleneck + HITL | ⏳ pending | — | — |

Updated at the end of each phase's session.

---

## Definition of "finished"

The system is at FINAL SHAPE OF COMPLETE when:

1. ✅ `scripts/ui_audit_check.py` returns 0 with 100% of CTAs classified
2. ✅ `scripts/backend_catalog_check.py` returns 0 with 0 ghost functions
   (everything either UI-linked or marked internal-only)
3. ✅ `scripts/gap_map_check.py` returns 0 with every gap closed or
   explicitly accepted
4. ✅ `scripts/readout_check.py` returns 0 — every user-facing CTA has
   drill-down readout
5. ✅ `scripts/canvas_link_check.py` returns 0 — one canvas surface, all
   attachments traceable
6. ✅ `scripts/bottleneck_check.py` returns 0 — bottleneck detector live,
   synthetic test passes, HITL approval flow exercised

When all six verifiers exit 0 in the same run, the directive is met.

`scripts/shape_of_complete_final.py` will be the master runner — calls
all six verifiers, prints a 6-line green report.

---

## What I am committing to

When the founder says "continue" on the next message:
- I will ship Phase 1 (UI Surface Audit) in that session
- I will report the result honestly
- I will NOT auto-trigger Phase 2

Founder says "continue" again → Phase 2 ships next session. And so on.

When all six phases are shipped and `shape_of_complete_final.py` returns
0, the directive is complete and I will say so explicitly.

If a phase needs to be re-scoped mid-execution (e.g., Phase 2 turns out
to need 12 credits not 6), I will pause and report before continuing.
No silent overruns.

---

## End of plan

This document is the load-bearing artifact for the directive. Future
Murphy reads this at the top of any "continue the shape of complete"
session. Every phase commit references this doc by path and updates the
progress tracker.
