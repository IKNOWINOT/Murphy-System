
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
