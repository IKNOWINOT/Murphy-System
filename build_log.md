
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

## R66e — book_chapter_loop character extractor stopword expansion (2026-06-06)

**Problem:** extract_characters caught "Her", "Just", "Detective", "Could" as
"characters" because the original skip set only had ~30 entries. Real characters
got crowded out of the top-N ledger; subsequent chapters had to hallucinate
new ones because the ledger looked stale.

**Fix:** stopword set expanded from ~30 to ~120 entries — articles, pronouns,
possessives, conjunctions, modals, adverbs, generic titles (Detective, Officer,
Doctor), narrative connectives, weekday/month names, structural words.

**Proof:** Detective Ada Stein test passage with 4 real names (Ada, Hawthorne,
Eliot, Stein) buried in 14 capitalized stopwords → extractor returns exactly
['Ada', 'Hawthorne', 'Stein', 'Eliot'], zero leaks.

NER would be more robust but heavier. This fix unblocks the immediate
ledger-pollution problem at zero LLM cost.

## R66f — Phantom DEEPINFRA_TIMEOUT=60 mutator EXORCISED (2026-06-06)

**Mystery:** /etc/murphy-production/environment had DEEPINFRA_TIMEOUT=180,
secrets.env had 120, systemd drop-in had 120. /proc/PID/environ showed 120.
Yet MurphyLLMProvider.__init__ kept logging "DEEPINFRA_TIMEOUT was 60.0s —
clamped to 120.0s". SD-73 floor caught it but root cause unknown.

**Root cause:** /opt/Murphy-System/.env line had DEEPINFRA_TIMEOUT=60.
app.py:4013 (and two other sites) called load_dotenv(.env, override=True)
which clobbered systemd's value at startup. The .env file is a leftover
from development setup — secrets.env + systemd environment file are the
canonical sources.

**Fix:** Updated /opt/Murphy-System/.env: DEEPINFRA_TIMEOUT 60 → 120 with
inline comment explaining the SD-73 floor.

**Proof:** After restart, /proc/PID/environ shows DEEPINFRA_TIMEOUT=120.
SD-73 FLOOR warning count in journalctl since restart: 0 (was firing every
few seconds before).

The in-code max() floor (R65b SD-73) stays as defense in depth — it just
no longer has work to do.

**Lesson:** When env-var override mysteries persist, check ALL three
override layers: systemd Environment=, EnvironmentFile=, AND app-level
load_dotenv(override=True). Last write wins. Add a "where's this value
really coming from" debug endpoint someday.

## R64c — Persona memory loop: HITL corrections → next persona prompt (2026-06-06)

**Problem:** R64a built rosetta_learning.db with agent_corrections rows.
R64b hooked the /decide endpoints so HITL decisions get recorded. But the
loop was open — personas had no way to READ their corrections back. Each
new run started from the same base prompt, repeating the same mistakes
humans had just corrected.

**Fix:**
- NEW src/persona_memory_loop.py
  - render_correction_block(agent_type, limit=5) → formatted prompt block
    listing recent corrections by importance, with verb markers
    (✗ rejected, ✎ revised, ↻ regenerated, ✓ approved-with-note)
  - prepend_to_prompt(base, agent_type) → convenience wrapper
  - Read-only; all writes still go through R64b /decide hooks
  - Returns "" gracefully when DB is missing or empty (zero behavior change
    for unaffected agent types)
- src/rosetta_selling_bridge.py:inject_selling_persona — both return paths
  (PersonaInjector-enabled and fallback) now prepend the correction block
  using persona.department or persona.agent_id as the agent_type key

**Proof:** Inserted 3 test corrections for agent_type='sales' (rejection,
revision, rejection). render_correction_block('sales') produced a 462-char
formatted block with all 3 lessons sorted by importance (0.90 → 0.85 → 0.65).
render_correction_block('trial_intelligence') returned "" (no corrections =
no block, no spam).

**Composes with:** R64a (DB), R64b (writes), R66/R66b (tenant tuning is
orthogonal — persona memory + tenant context both prepend to the prompt,
both work).

**Snapshots:** /var/lib/murphy-production/state_snapshots/
rosetta_selling_bridge_20260606T213039Z.before

**Future wiring:** R64c1 — extend to autonomous_engine.build_personality_for_role
so non-selling personas also benefit. Cheap follow-up.

## R64c1 — Persona memory loop extended to ALL personas (2026-06-06)

**Problem:** R64c wired persona_memory_loop into rosetta_selling_bridge, but
that only covers sales/outreach personas. Executive, ops, eng, customer
success, communications personas had no path to receive HITL corrections.

**Fix:** src/rosetta/rosetta_soul_renderer.py:render_from_persona — after
boundaries are rendered, append a "## Learning" section using
persona_memory_loop.render_correction_block. agent_type derivation tries
persona.agent_type → department → role → name in that order, lowercased.

This is the ONE place every Rosetta persona passes through to become a
SOUL.md, so this wire covers the whole persona library.

**Proof:** "Executive Advisor" persona with 2 test corrections (rejection
+ revision) for agent_type='executive' renders cleanly with both lessons
in importance order. "Marketing Brain" persona (no corrections) renders
without a Learning section (no spam when nothing to teach).

**Composes with:** R64c (selling bridge wire) — both paths now active.
Coverage: 100% of personas in the dispatch pipeline.

**Snapshot:** /var/lib/murphy-production/state_snapshots/
rosetta_soul_renderer_20260606T213550Z.before

## R66g — /api/debug/env/{key} env-var layer tracer (2026-06-06)

**Problem:** R66f burned 45 minutes finding that /opt/Murphy-System/.env
was clobbering systemd's DEEPINFRA_TIMEOUT via load_dotenv(override=True).
The pattern: env var has correct value somewhere, but a later layer
overrides it silently. Without a tool, the only way to find the truth is
grep across 3-4 file locations and inspect /proc/PID/environ.

**Fix:** New founder-only endpoint GET /api/debug/env/{key} that scans all
four layers (systemd unit + drop-ins, EnvironmentFile, secrets.env,
/opt/Murphy-System/.env) and reports:
- live runtime value from /proc/PID/environ (effectively)
- per-layer value where set
- winning_layer (which layer's value matches runtime)
- _hint about load_dotenv(override=True) at app.py:4013

**FME (failure modes enumerated):**
- E_DEBUG_0001 caller lacks founder API key → 403
- E_DEBUG_0002 key has invalid chars → 400
- E_DEBUG_0003 key > 64 chars → 400
- E_DEBUG_0004 key empty → 400
- E_DEBUG_0005 key absent everywhere → 200 ok=true, sources=[]
- E_DEBUG_0006 file unreadable → soft-warn in warnings[], continue
- E_DEBUG_0007 file missing → silently skip layer
- E_DEBUG_0008 secret-shaped key (contains KEY/TOKEN/SECRET/PASS) → redact
- E_DEBUG_0009 /proc unreadable → runtime_value=null, warn

**Defensive design notes:**
- Cloudflare 301-redirects path components to lowercase before they hit
  origin. Added uppercase normalization with `requested_key` echo so the
  caller can see what they asked for vs. what was looked up.
- Secret detection is conservative: any key whose name contains KEY, TOKEN,
  SECRET, PASSWORD, PASS, or PWD gets value-redacted (e.g. "hg***FZ").
- All 4 file readers are wrapped in try/except — any single file failure
  becomes a non-blocking warning, not a 500.

**Proof:**
- S1 (DEEPINFRA_TIMEOUT): showed all 4 layers with R66f forensic detail —
  systemd=120, environment_file=180, secrets_env=120, dotenv_override=120
  (winning); runtime=120. The 180 vs 120 conflict between systemd Environment
  and EnvironmentFile is now visible.
- S3 (DEEPINFRA_API_KEY): redacted as "hg***FZ" across all layers, redacted=true
  in response.
- S4 (NONSENSE_KEY_XYZ): 200 ok=true, sources=[], runtime_value=null
- E_DEBUG_0002 (foo-bar): 400 with code
- E_DEBUG_0001 (anonymous): 403

**Composes with:** R66f (lesson encoded), Error Discipline canon (full FME + SME + codes + response shape + rollback documented).

**Snapshot:** /var/lib/murphy-production/state_snapshots/
app_20260606T214034Z.r66g.before

## R64c2 — Recent corrections visible on OS agent cards (2026-06-06)

**Problem:** R64a + R64b + R64c + R64c1 built the full HITL → persona
learning loop, but the only way to see what was accumulating was SQL
queries against rosetta_learning.db. Corey couldn't see at a glance
which personas were getting corrected and what for.

**Fix:** static/murphy-os.html:loadAgents() now does a Promise.all to
fetch /api/rosetta-learning/agent/{type}/corrections?limit=3 for every
agent on the dashboard. If any come back, an "Recent lessons (N)" mini-
panel is appended to that agent's card with verb glyphs (✗ rejected,
✎ revised, ↻ regenerated, ✓ approved) and the truncated reason text.

agent_type derivation: department → role → agent_id, lowercased and
URL-encoded (same precedence rule as R64c1 persona builder).

**Defensive:**
- Per-agent fetch failure is silently swallowed (try/catch around each).
  An agent with no corrections shows the normal card, no panel.
- Promise.all keeps the dashboard load fast (~1 RTT for N agents in
  parallel vs N serial RTTs).

**Proof:**
- Inserted test correction (agent_type='sales', "omit price in first
  outreach email"). /api/rosetta-learning/agent/sales/corrections?limit=3
  returned it correctly with ok=true, reason intact.
- Patched HTML on disk verified (grep shows the new comment + code).
- Test row deleted; no real metrics polluted.

**Composes with:** R64a (DB), R64b (writes), R64c (selling-bridge inject),
R64c1 (universal Rosetta inject). Now the loop is visible too.

**Frontend-only — no restart needed; static HTML auto-served on next
dashboard load.**

**Snapshot:** /var/lib/murphy-production/state_snapshots/
murphy-os_20260606T214732Z.r64c2.before

## R64d — 4-view drill panel (Timeline / Causality / Agents / ROI) (2026-06-06)

**Problem:** Agent cards in /os surface name + stats + recent corrections
(R64c2) but no way to drill into a specific dispatch event to see the full
picture. Founder wanted: timeline, causality DAG, agent details, ROI
projected-vs-actual — and a "re-dispatch" button.

**Fix:**
- NEW src/drill_aggregator.py (read-only):
  - aggregate(event_key) returns a 4-view payload by joining:
    - murphy_audit.db.rosetta_dispatch_log (timeline + causality via correlation_id chain)
    - rosetta_learning.db.{agent_corrections,agent_success_map} (agent stats + last lesson)
    - roi_ledger.db.{roi_entries,roi_targets} (actual + projected ROI)
- NEW route GET /api/drill/{event_key} (founder-only, X-API-Key)
- NEW route GET /api/drill/recent_for_agent/{agent_id}
- NEW overlay in static/murphy-os.html — fixed-position modal with 4 tabs.
  Agent cards now have onclick → fetches recent event_key → opens drill.
  "Re-dispatch" button posts intent_hint back to /api/rosetta/dispatch.

**FME documented:**
- E_DRILL_0001 invalid event_key → 400
- E_DRILL_0002 event not found → 404
- E_DRILL_0003 aggregator import fails → 503
- E_DRILL_0004 DB read fails → 500 with reason
- E_DRILL_0007 missing/wrong API key → 401

**Proof (live data):**
- /api/drill/recent_for_agent/executor returned signal_id c9e9181b...
- /api/drill/c9e9181b... returned: head agent=executor verdict=proceed,
  timeline=1, causality nodes=1, agents=1 with success_rate, roi structure.
- 401 unauth ✓, 404 bogus_key ✓, 200 happy path ✓.

**Connects to dispatch:** Re-dispatch button calls /api/rosetta/dispatch
with prompt=head.intent_hint, tenant_id, source=r64d_redispatch — the
real PATCH-292 pipeline (soul→Rosetta→MFGC→MSS→swarm), not a stub.

**Composes with:** R64a (DB), R64c+R64c1 (persona memory), R64c2 (card panel).
The drill becomes the single visibility surface that R64e can reuse from
HITL, Agents, Pipeline, Soul tabs.

**Snapshots:** /var/lib/murphy-production/state_snapshots/
app_20260606T223101Z.r64d.before
murphy-os_20260606T223101Z.r64d.before

## R69 — archetype POST field wired into deliverable generator (2026-06-07)

### R69-A diagnosis
The cited_doc archetype test from R68 produced real LLM output (190s, 21KB)
but ZERO citations. Forensic read of /var/lib/murphy-production/state_snapshots/cited_r68.json showed:
- The output rendered the generic engineering-PRD template (FUNCTIONAL REQUIREMENTS,
  STAKEHOLDER ANALYSIS, RACI MATRIX) — not the cited-research template
- Tail had two Librarian-onboarding sections ("5U-Identity", "tell me a bit about")
- `grep archetype demo_deliverable_generator.py` → zero hits
- The _is_cited_doc detection at line 4530 fires only on natural-language keyword
  match. Query "generative AI in 2026 with real sources" → zero keyword matches
  ("sources" was not in the keyword list)

### R69-B fix
Three-file surgical patch (Murphy approved with dict-mapping suggestion):

1. `src/demo_deliverable_generator.py`
   - `_generate_llm_content` gains optional `archetype` kwarg
   - `_is_cited_doc` detection now combines explicit-archetype dict-lookup OR keyword backstop
   - Added _ARCHETYPE_FLAGS dict — single point of extension for future archetypes
   - Added "sources", "evidence-based", "footnote" to keyword backstop
   - `generate_custom_deliverable` and `generate_deliverable` both thread `archetype` through

2. `src/runtime/app.py`
   - Both POST `/api/demo/generate-deliverable` handlers (line 22381 `demo_run`
     and line 22565 `demo_generate_deliverable`) now extract `archetype` from
     the JSON body and forward it
   - First attempt patched only the wrong handler — caught by HTTP 500
     "name 'archetype' is not defined", fixed in iteration

### Verification
Snapshot: /var/lib/murphy-production/state_snapshots/cited_r69b_v2.json
- HTTP 200 in 94s (vs 190s on R68 — faster because no off-archetype padding)
- 10,944 chars of cited content
- 6 numbered references with real arXiv IDs (Goodfellow GAN, Vaswani Attention,
  Kingma VAE, Zhang Colorization, Bowman Continuous-Space, Dosovitskiy ViT)
- Inline [1]..[5] citations embedded in body text
- Provider: llm-remote:deepinfra (real, not stub)
- Quality: 96/100 (honest — stub never fired)
- Zero "Librarian" / "5U-Identity" / "business name" — persona drift eliminated

### Lesson learned
When grepping for a duplicate code pattern (here: `tenant_id = ... # R66`
appears in 2 handlers), VERIFY which handler the line numbers fall in
before patching. I assumed the first match was the right one; it wasn't.
Always: `awk 'NR<=LINE && /async def/{lastdef=$0} END{print lastdef}'`
to confirm the enclosing function.

## R70-A — request-aware hang-watchdog (2026-06-07)

### Root cause (found during R69b verification)
`/usr/local/bin/murphy-hang-watchdog.sh` runs every 3 min, probes
`/api/health` 8 times with 12s timeouts. If ≥6 fail, it calls
`systemctl restart murphy-production`. Long LLM work (90-130s)
blocks the event loop enough that the health probe times out
6+ times in the 136s window, triggering an automatic restart that
kills the in-flight customer request mid-generation.

Verified pre-fix: white_paper test 08:26 → watchdog probed 08:26:36
during LLM work → 08:27:52 SIGKILL → customer got "Empty reply from
server" after 112s. Six similar self-kills logged in watchdog_events.db
in the 2 hours preceding the fix.

### R70-A fix
1. New middleware in `src/runtime/app.py` (after `_ResponseSizeLimitMiddleware`):
   counts in-flight HTTP requests with a thread-safe lock. Skips counting
   health endpoints themselves.
2. New endpoint `GET /api/health/inflight` returns
   `{in_flight, peak_since_boot, total_since_boot}`.
3. `murphy-hang-watchdog.sh` updated: before issuing the restart, query
   `/api/health/inflight`. If `in_flight > 0`, log "suppressed" event and
   exit 0 instead of restarting.

### Verification (post-fix)
- white_paper test that previously died at 112s now completes at 125s
  with HTTP 200 (success=True)
- Watchdog fired 5 times in 25 min after the fix, all completed cleanly
  without restarting the service
- Endpoint smoke test: `{"in_flight":0,"peak_since_boot":35,"total_since_boot":508}`
- Service uptime preserved through ongoing background load

### Honest caveat
The white_paper test return came from `provider=local` (stub fallback)
not the LLM — citations were absent. This is a separate issue
(rate-limit fallback path) tracked as R71. R70-A fixes the
service-killing-itself bug; it doesn't fix LLM rate-limit handling.


## R71-B — explicit archetype wins over keyword detection (2026-06-07)

### Root cause (found during R70-A verification)
The R70-A white_paper test returned `provider=local` with zero
citations. Forensic trace showed the pipeline emitted
`FORGE-PIPELINE-SUMMARY path=[CODE-PROJ-001:start → ... → zip-built]` —
the code-project assembly pipeline, not the cited-research pipeline.

The query was "zero-trust network architecture for enterprise SaaS".
The substring "saas" is in `_CODE_PROJECT_KEYWORDS`. The keyword check
on `demo_deliverable_generator.py:6841` ran BEFORE archetype was
consulted, routed to `generate_code_project_deliverable()`, which
silently drops the `archetype` and `tenant_id` kwargs and tags output
as `provider=local`. So the request was technically successful (115s,
real DeepInfra calls under the hood) but produced the wrong product.

### R71-B fix
Two-line guard at the top of `generate_custom_deliverable`:
- if explicit archetype is one of {cited_doc, research_brief, white_paper},
  SKIP the keyword check and stay on the prose/cited pipeline
- if explicit archetype is "code_project", FORCE the code-project path
  even without a keyword match
- otherwise (no explicit archetype), preserve existing keyword behavior

### Verified post-fix
Snapshot: /var/lib/murphy-production/state_snapshots/r71b_white.json
- Query unchanged: "zero-trust network architecture for enterprise SaaS"
- HTTP 200 in 154s (longer because cited pipeline does more LLM work)
- provider=llm-remote:deepinfra (real LLM, NOT stub)
- deliverable_type=(none) — not code_project
- 5 real industry-standard citations:
  [1] NIST SP 800-207 Zero Trust Architecture
  [2] ISO/IEC 27001:2013
  [3] AICPA SOC 2 Trust Services Criteria
  [4] OWASP Security Cheat Sheet
  [5] SANS Institute Cyber Security Awareness
- Zero CODE-PROJ-001 markers in output

### Lesson learned (added to canon)
A keyword detector is a heuristic, not a contract. When a caller
provides explicit intent (an archetype parameter), explicit intent
must win over the heuristic. Same rule applies to any future
auto-detection: explicit > inferred.

## R70-B — restore tiered model routing (2026-06-07)

### Audit finding
`llm_provider.py:60` collapsed `DEEPINFRA_FAST_MODEL` and `_CODE_MODEL`
to `PRIMARY_MODEL` (Llama-3.3-70B-Turbo) during R67 with the rationale
"one model does everything well". This was correct then. But existing
callsites in `murphy_system_core.py:12282` (MFGC `_try_llm_generate`)
and `llm_self_check.py:423` were already requesting
`model_hint="fast"`, silently getting the 70B model anyway.

### Fix
Removed the FAST_MODEL alias override. `DEEPINFRA_FAST_MODEL` now
correctly resolves to `Llama-3.1-8B-Instruct` (the value declared on
line 57). CHAT and CODE stay on PRIMARY. Together's fast stays on 70B
(Together is fast enough that downgrading risks quality with no win).

### Verified post-fix
- `MFGC-LLM-GEN-001 external_llm model=Meta-Llama-3.1-8B-Instruct latency=7.06s`
  (was 24s on 70B-Turbo in R71-B's run)
- cited_doc test on "transformer attention mechanisms": HTTP 200,
  13.2KB content, real Vaswani Attention and Bahdanau NMT citations
- success=True, provider=llm-remote:deepinfra (no regression)

### Honest latency finding (NOT a win)
Total cited_doc time was 136s vs ~94s pre-R70-B. Slower, not faster.
Why: only ONE callsite (MFGC) actually requests fast. The dominant
cost (~129s) is a single 70B call during final deliverable composition
which correctly uses model_hint="chat" — and that's right; the final
prose needs quality, not speed. R70-B saves ~17s per request on the
MFGC hop (24s → 7s) but other run-to-run variance dominates.

### Lesson (added to canon)
Wiring a fast model is necessary but not sufficient for a latency win.
Audit which callsites actually request fast BEFORE projecting a win.
If the long-pole call legitimately needs quality (final composition,
cited research), the fast model can only help peripheral hops, and
the win will be modest.

### Next obvious optimization (R70-C candidate, not done here)
The 129s single-call cost dominates. Options:
  (a) Enable streaming on the final composition (LLM_USE_STREAMING=1
      already set globally; verify it's actually engaging here)
  (b) Reduce max_tokens cap for cited_doc (current: 32768)
  (c) Run MFGC and MSS in parallel rather than serial
