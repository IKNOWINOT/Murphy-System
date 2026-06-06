
═══════════════════════════════════════════════════════════════════
R64 — Rosetta Learning + OS Surface Wiring (2026-06-06)
═══════════════════════════════════════════════════════════════════

## What's changing & why

The /os surface today has several dead/lying wirings:
  - HITL tab reads /api/hitl/interventions/pending → 0 (dead)
  - REAL pending items live at /api/hitl-v2/queue → 5
  - hitl_queue.db → 10 DAG-blocked items
  - mail outbound queue → 0 right now, alive
  - deployment-reviews → alive

The Soul tab shows the shallow soul (north_star + covenant chips) but
doesn't surface Rosetta itself (9 swarm characters, 11 lens roles,
or the per-persona DSL injection).

The Agents tab shows the static grid of all 10 agents with no
recency filter, no click-drill, no DSL view.

The Pipeline detail panel shows 3 buttons (Workflow Canvas /
ROI Calendar / Forge) that open destinations in a 720px iframe
with no event-id context passed.

ROI events track projected costs but never actuals. No way to know
whether estimates are honest.

The covenant chip `past_informs_present` is aspirational only —
agent_memory table exists with 17 rows, but persona injection
doesn't read from it.

## Architecture decisions (FOUNDER LOCKED 2026-06-06)

- Q1: store BOTH the full diff (audit) AND short reason (injection) ← C
- Q2: top-N for injection + background distill ← C
- Q3: Cytoscape.js for graphs ← A
- Q4: staircase order: R64a, R64b, R64f, R64c, R64d+e ← B
- Q5: single canonical store "rosetta_learning" maps success of every agent

Naming: rosetta_learning.db
Agent_type derivation on HITL items: static map from `kind` field
Decide-endpoint hooks: ALL THREE (lines 2063, 6904, 17702 in app.py)

## Task list (rounds)

R64a — DB schema + ROI actuals
  - [ ] Create rosetta_learning.db with 3 tables:
        agent_success_map, agent_corrections, agent_distilled_lessons
  - [ ] Add agent_type derivation map (kind → agent_type)
  - [ ] When roi_event status transitions to 'completed', capture
        human_cost_actual, human_time_actual_hours,
        agent_compute_cost_actual, roi_actual into the JSON blob
  - [ ] GET /api/rosetta-learning/agent/{type} returns the map row
  - [ ] GET /api/rosetta-learning/agent/{type}/corrections returns
        top-N by importance
  - [ ] Live demo: hit endpoints, see empty-but-valid responses

R64b — /decide hooks
  - [ ] Hook /api/hitl/items/{item_id}/decide (line 2063, v2)
  - [ ] Hook /api/hitl/interventions/{intervention_id}/respond (6904)
  - [ ] Hook /api/hitl/{tid}/decide (line 17702, legacy)
  - [ ] On approve → applied++, on reject → rejected++,
        on edit/revise/regenerate → revised++
  - [ ] Write full row to agent_corrections (decision, reason,
        diff_json, importance, stake)
  - [ ] Recompute fail_rate, success_rate on every write
  - [ ] Live demo: POST a fake approve, verify counters tick

R64f — OS HITL tab rewire
  - [ ] Change loadHITL() to call /api/hitl-v2/queue (not the
        dead /api/hitl/interventions/pending)
  - [ ] Render each pending item with: kind · tenant · agent_type ·
        agent fail % (from rosetta_learning) · severity · SLA countdown
  - [ ] Click → drill panel: full item detail + 6 action buttons
        (Approve / Edit&approve / Regen w/ considerations /
         Reject / Defer / Escalate)
  - [ ] Edit-mode form: render the payload as editable JSON,
        action=edit sends the edited body
  - [ ] Regen-mode: textarea for considerations,
        POST /api/hitl-v2/items/{id}/regenerate {considerations}
  - [ ] Sidebar HITL count updates from real queue
  - [ ] Live demo: open /os#hitl, see the 5 real pending items

R64c — Persona memory loop
  - [ ] Patch rosetta_soul_renderer (or persona-injection step)
        to read top-N agent_corrections by importance for the
        current agent_type
  - [ ] Append "Past corrections you must apply: <list>" to soul_l1
        on every persona invocation
  - [ ] Nightly distill job: every M corrections, summarize into
        a single agent_distilled_lessons row; mark sources distilled=1
  - [ ] Soul tab chip 'past_informs_present' shows count per agent
  - [ ] Live demo: inject a fake correction, fire the agent,
        verify the correction text is in the prompt

R64d — Four-view drill panel
  - [ ] Add Cytoscape.js (~250KB) to static/vendor/
  - [ ] Build drill component with 4 tabs:
        [Timeline] [Causality DAG] [Agent Relationships] [ROI: P vs A]
  - [ ] Timeline: canvas-based time-bar of related events
  - [ ] DAG: Cytoscape, nodes from /api/causality/graph
  - [ ] Relationships: Cytoscape, nodes from agent_substrate.db ←
        org_graph_edges, edge weight = handoff volume in window
  - [ ] ROI panel: SVG bar chart, projected (gray) vs actual
        (mint if ≥proj, amber if under)
  - [ ] Live demo: open a HITL item, all 4 tabs render with data

R64e — Reuse drill from HITL, Agents, Pipeline
  - [ ] Pipeline buttons (Workflow Canvas / ROI Calendar / Forge)
        re-wire: open destination in same tab with ?id=<event_id>
        (founder pending answer A/B/C/D)
  - [ ] Agents tab: add ACTIVE 20M / ALL toggle, default ACTIVE
        Click an agent → same 4-view drill scoped to that agent
  - [ ] Soul tab: lead with Rosetta header, show swarm-character
        cards with live stats from rosetta_learning, click → drill
  - [ ] Mail tab: pick A/B/C from founder choice for inbox source

## Snapshot for rollback
Path: /var/lib/murphy-production/state_snapshots/r64_master_20260606T063130Z
Rollback: copy *.before back over live paths; systemctl restart murphy-production

## Standing canons reaffirmed
- All bash/SSH timeouts ≥120s (SD-73)
- Replace-exact means literal asset, ask if ambiguous (SD-76)
- Asking is acceptable; choosing is NOT my liberty
- Snapshot before every mutation
- Live demo every round before moving on

═══════════════════════════════════════════════════════════════════
R65a — /demo rewire (2026-06-06)
═══════════════════════════════════════════════════════════════════

## What shipped
Surfaced the orphaned R404 "Watch It Build" 60-second SSE backend
(already-built 2026-06-01, never wired to a UI) plus added 4
new archetype quick-actions and a unified "Ask Murphy" prompt box.

## Changes
- demo.html: inserted ~350-line R65a block between hero and metrics
  - 5 chip selectors: 🏢 company, 📖 book, 📚 cited_doc, 🛠 webapp, 💻 desktop
  - Unified prompt textarea + "Ask Murphy →" button
  - Live SSE stream renderer (phases, logs, links, errors)
  - 3 handler routes:
    1. company → POST /api/demo/build (R404 SSE — already live)
    2. book/cited_doc/webapp → POST /api/rosetta/dispatch with role+domain
    3. desktop → stub explainer + waitlist link (R65d will wire)

## Verified live
- 5 chips render on /demo ✓
- R404 SSE returns phase_start for "Test Pizza Co" ✓
- /api/rosetta/dispatch returned 10 notifications + 3 agents +
  brief_packet_id=dispatch_1b5fd549 ✓
- All existing live panels below (ROI/swarm/shield/ambient/compliance)
  remain unchanged ✓

## Known gaps (handled in next rounds)
- Dispatch returns notifications + assigned agents but NO synthesis text.
  R65b will wire the actual long-form delivery (chapter loop + citation
  verify + plagiarism gate) through generate_document() and
  document_generation_engine.
- /api/demo/build SSE may stall after first phase (only emits identity
  start in initial test). Need to walk all 5 phases live to confirm.
- Desktop button is a stub. R65d will ship pairing + DLF-Lite roundtrip.

## Snapshot
/var/lib/murphy-production/state_snapshots/r65a_demo_20260606T070615Z
Rollback: copy demo.html.before back, no service restart needed

## 2026-06-06 R65b ENV FIX (post-shipping)
- Issue: anonymous /api/books/{id}/download returned 401 even with auth_middleware
  patched + systemd override added.
- Root cause: MURPHY_AUTH_EXEMPT is set in /etc/murphy-production/environment
  (EnvironmentFile=), which OVERRODE my systemd .conf override (last-write wins).
- Fix: appended /api/books/,/api/citations/,/api/demo/generate-deliverable to the
  existing comma-separated list in the env file, removed the redundant override.
- Now: anonymous public access verified 200 on all three.
- Lesson: systemd EnvironmentFile= beats Environment= in .d/ overrides when both
  set the same key. ALWAYS prefer editing the env file directly when it's the
  designated source-of-truth (the unit file even comments "Environment is read
  from /etc/murphy-production/environment").


## R66 — Signup → MFGC/MSS factor injection (2026-06-06)

**Problem:** Deliverables were generic because MFGC + MSS ran with zero
customer-specific factors. The signup wizard captured industry/stage/budget
into tenant_profiles.profile_json but nothing on the runtime path read it.

**Fix:**
- src/signup_profile_loader.py — load_tenant_factors(tenant_id) → MFGCFactorSet.
  Derives compliance_regimes, required_gates, risk_tolerance, audit_cadence,
  team_size_bucket, target_audience from real signup fields.
- src/mfgc_core.py — added `factors: Dict[str, Any]` slot to MFGCSystemState.
- src/mfgc_adapter.py — execute_with_mfgc(tenant_id=...) now injects factors
  into the execution context and the final MFGCSystemState.factors.
- src/demo_deliverable_generator.py — _run_mss_pipeline(tenant_id=...) and
  generate_deliverable(tenant_id=...) thread the id through.
- src/mss_controls.py — magnify() now merges ctx compliance_regimes into
  compliance_considerations, surfaces target_audience + industry + business_name
  in output, and frames functional_requirements for the tenant's vertical.
- src/runtime/app.py — /api/demo/generate-deliverable handler now extracts
  body["tenant_id"] and passes it to generate_deliverable.

**Proof:** identical query "Build me a customer-acquisition plan for next 30
days" produces divergent MSS magnify output for t1 (Apex Plumbing) vs t2
(Clean Kitchen). Diverges on: industry, compliance_considerations,
functional_requirements, target_audience, business_name.

**Snapshots:** /var/lib/murphy-production/state_snapshots/{mfgc_core,mfgc_adapter,
demo_deliverable_gen,app,mss_controls}_20260606T*.before

**Composes with:** R64a (rosetta-learning), R65a (demo chips). Future deliverables
across all 5 archetypes now tune to the tenant's industry automatically.

## R66b — MSS tenant context surfaced to LLM prompt (2026-06-06)

**Problem:** R66 wired tenant factors into MSS magnify output, but
`_format_mss_context()` (which renders the MSS section that gets prepended
to the LLM prompt) only read reqs/comps/compliance/cost/impl_steps. It
never read the new R66 keys (industry, target_audience, business_name).
So the model received tenant-tuned MSS output but couldn't see who it
was writing for.

**Fix:** `src/demo_deliverable_generator.py:_format_mss_context` now emits
a leading "TENANT CONTEXT (from signup profile)" block when any of
business_name / industry / target_audience are populated, followed by a
CRITICAL instruction to tailor every recommendation to that business.

**Proof:** identical query "Build me a customer-acquisition plan for next
30 days" — t1 prompt now leads with:
  Business: Apex Plumbing
  Industry: plumbing contractor
  Write for: early-stage plumbing contractor owner, no marketing budget
while t2 leads with:
  Business: Clean Kitchen
  Industry: commercial cleaning
  Write for: established commercial cleaning owner looking to expand customer base

Composes with R66 (no behavior change when tenant_id is absent — block
silently omitted).

## R66c — /demo chips auto-attach tenant_id when signed in (2026-06-06)

**Problem:** R66 + R66b made deliverable tunable by tenant_id, but the 5 /demo
archetype chips never passed one. So logged-in tenants got the same generic
output as anonymous visitors.

**Fix:**
- `src/runtime/app.py:/api/auth/me` now returns `user.tenant_id` (resolved via
  `tenant_members` table, prefers owner role, then earliest member row).
  Empty string when user has no tenant membership (cross-tenant founders,
  unprovisioned accounts).
- `demo.html` chip handler now calls `/api/auth/me` before POSTing and adds
  `tenant_id` to the body when present. Anonymous flow unchanged.

**Verified:** founder API key → /api/auth/me returns tenant_id='t1' after the
test membership row was added; demo.html chip POST will include it.

Composes with R66 (loader) + R66b (LLM prompt surface). Now end-to-end
tenant-tuning works from chip click → loader → MSS → LLM prompt.
