# MPCS v2 Integration Plan — against current architecture
# Drafted: 2026-06-08
# Status: PROPOSAL — not committed, not promoted, not in canon

## Purpose

Map every MPCS v2 variable to existing Murphy infrastructure. Identify
the minimum changes to make MPCS computable from production data. Define
success and failure modes for each component. Ensure consistency across
the architecture (no MPCS island; it composes with what we have).

Same pattern as every other patch we've shipped: snapshot the current
state, write the plan, name the rfusks, propose the smallest change that
buys the most leverage, then ask before doing.

## What we already have (the floor)

Production canonical surfaces all 200 except `/api/self/audit` (401,
auth-gated, expected).

State databases (11 total at /var/lib/murphy-production/):
- `llm_cost_ledger.db` — PATCH-409 (tenant_id, job_id, cost, tokens)
- `event_spine.db` — PATCH-400 (event timeline, R403 transition log)
- `state_transitions.db` — R403 ALLOWED_TRANSITIONS spine
- `event_log.db` — R403 log (start, stop, fail, succeed, etc.)
- `audit.db` + `murphy_audit.db` + `executor_tool_audit.db` — audit triplet
- `psm_ledger.db` — before/after snapshot index
- `roi_ledger.db` — value-attribution
- `twilio_ledger.db` — comms ledger
- `backup_ledger.db` — backup index
- `murphy_logs.db` — system logs

Canons shipped:
- `variance_interception_canon.md` (33/66 thresholds)
- `context_readiness_canon.md` (15 standards)
- `vault_and_accounting_canon.md` (platform/tenant classes, job tags)

Code:
- Rosetta org chart at `src/rosetta/org_chart.py`, `src/rosetta_core.py`
- Conductor state machine at `src/conductor/`
- compliance_as_code_engine.py
- ~5 Rosetta role classes (small surface, room to grow)

## The mapping — MPCS variable to current infrastructure

| MPCS variable | Definition | Current source | Computable today? | Gap to close |
|---|---|---|---|---|
| **ID** (Information Density) | Open Q / Resolved Q | `outbound_review.db` + HITL queue + audit anomalies | 🟡 Partial | No clean "open question" counter. Need to instrument HITL items as questions with resolved/unresolved state. |
| **PC** (Perspective Coverage) | Unique viewpoints incorporated | Rosetta role bundles consulted per job | 🔴 No | No log of "which roles consulted on job X." Need to add `roles_consulted_json` to cost ledger. |
| **CI** (Convergence Index) | Shared constraints / total | compliance_as_code_engine + canon docs | 🔴 No | No canonical list of "constraints in flight per job." Hardest variable. Defer. |
| **BCD** (Boundary Condition Discovery) | Discovered boundaries / expected | compliance_as_code_engine catches + canon docs | 🟡 Partial | Have "discovered" (every refusal logged). Need "expected" — per-job-type baseline list. |
| **TC** (Trajectory Confidence) | Verified path segments / total | tripwire + before_after verifier + ship-it tests | 🟢 YES | Every patch has verifier output. Map 1:1. Already tracked in build_log. |
| **Risk function** | (Latency × Err growth) / Authority remaining | event_spine timestamps + cost_ledger + budget | 🟢 YES | All inputs exist. Just needs a script that joins them. |
| **Convergence Gate** | CI>0.70, ID<1.0, BCD>0.80, TC>0.60 | Composite of the above | 🔴 No | Blocked on CI. Until CI is real, gate cannot be gate. |

**Read:** 2 variables are computable today (TC, Risk). 2 partial (ID, BCD).
2 require new instrumentation (PC, CI). The Convergence Gate is blocked
on the hardest variable (CI).

## Proposed integration in three phases

### Phase 1 — Research doc + measurable variables (1 session, ~6 credits)

**Goal:** preserve the spec, ship the easy wins, no canon commitment.

1. Write `docs/research/mpcs_v2_spec.md` — your spec verbatim with a
   header marking it as a research target, not canon.
2. Add a cross-reference paragraph in `variance_interception_canon.md`:
   "MPCS v2 is the formal superset; variance canon is the operational
   floor; promotion of MPCS variables into canon happens per criteria
   in mpcs_integration_plan.md."
3. Ship `scripts/trajectory_confidence.py` — computes TC for any
   recent patch range. Reads tripwire + verifier-pass-rate from
   build_log. Verifier: `tc_compute.py --since 30d` returns a number.
4. Ship `scripts/mpcs_risk.py` — computes the risk function for any
   in-flight job. Reads event_spine + cost_ledger. Joins them.
   Verifier: `mpcs_risk.py --job JOB-2026-NNNNNN` returns scalar.
5. Add 4 glossary entries: ID, PC, CI, BCD, TC, Risk (and Convergence
   Gate) so future Murphy reads them as defined terms.

After phase 1: MPCS is a citable research artifact. TC and Risk are
production functions. No canon binding yet. No runtime behavior change.

### Phase 2 — Instrument the partial-measurable variables (1 session)

**Goal:** make ID and BCD real before promoting them.

6. Schema change to `outbound_review.db`: add `question_state` column
   (`open` | `resolved_yes` | `resolved_no` | `superseded`). Backfill
   all rows to `resolved_*` based on existing status. Snapshot before.
7. Schema change to `compliance_as_code_engine`: declare `expected_boundary_classes`
   per job type (regulatory, financial, contractual, scope, identity).
   Existing refusals already log the "discovered" side; this names the
   denominator.
8. Ship `scripts/id_compute.py` and `scripts/bcd_compute.py`. Both
   verifiers.
9. ONLY THEN promote ID and BCD into canon — add a section to
   `variance_interception_canon.md` referencing them as additional
   variance lenses.

After phase 2: 4 of 6 MPCS variables are real and canon-linked.

### Phase 3 — Real Convergence Gate (2-3 sessions, deferred)

**Goal:** CI + PC + Convergence Gate go live.

10. Rosetta dispatcher logs `roles_consulted_json` per job (PC source).
11. Per-job constraint registry — every job declares its constraints at
    creation; consulting roles vote shared/contested (CI source).
12. Gate function evaluates all 4 conditions every 5 min for in-flight
    work above $50 in projected cost.
13. HITL trip at gate-not-met by 33% resource burn (this is where the
    33% Hypothesis becomes runtime behavior).

Deferred because steps 10-12 require real Rosetta multi-role
infrastructure we don't have at production scale yet.

## Success modes — what "this worked" looks like

After **Phase 1:** Murphy can answer "what's the TC of patch X?" and
"what's the risk score of job Y?" with numbers from production data.
Outside reader can run the verifier and reproduce. Variance canon
cites MPCS as superset, so the two never contradict.

After **Phase 2:** Murphy can answer "how much unresolved question
density does this job have?" and "what fraction of expected boundaries
have we discovered?" with numbers. HITL prompts get more specific —
"BCD = 0.55, missing class = regulatory" instead of "variance exceeded."

After **Phase 3:** The full Convergence Gate runs as a real-time check.
At 33% resource burn on any job > $50, if gate not met, Murphy halts
and reports which of the four conditions failed and which perspective
or boundary is missing. The 33% Hypothesis becomes enforced behavior.

## Failure modes — what "this broke us" looks like

### Failure mode A: Performative canon
We lock CI > 0.70 as canon before CI is measurable. Every patch
dutifully cites "CI = 0.78" with no real basis. Commit messages start
lying to us. **Mitigation:** Phase 1 explicitly does NOT canonize any
variable that isn't measurable. CI stays in research-doc only until
Phase 3.

### Failure mode B: Two canons disagree silently
Variance canon says zone yellow at 33%; MPCS gate says gate not met
at 33%. If they fire on the same job at the same time with different
prescriptions, Murphy gets paralyzed or worse, picks the looser one.
**Mitigation:** Variance canon explicitly references MPCS as superset.
When they overlap, MPCS gate is authoritative for jobs above $50,
variance canon for everything else. Cited in both docs.

### Failure mode C: Instrumentation bloat
Adding `roles_consulted_json`, `question_state`, `expected_boundary_classes`
all at once creates a schema-change tsunami that breaks something
downstream. **Mitigation:** Phase 2 ships them sequentially, each in
its own snapshot/verify cycle. PSM discipline. No batched DB changes.

### Failure mode D: The 33% Hypothesis fires on jobs that shouldn't be
**gated.** Murphy refuses to continue a small-cost exploratory job because
gate not met at 33%. Real autonomy loss. **Mitigation:** Phase 3 gate
only triggers on jobs above $50 projected cost. Cheap work is allowed
to fail; expensive work is gated.

### Failure mode E: TC inflates because verifier weakens
If we count tripwire-pass as TC even when the tripwire is too lax, we
look converged when we aren't. **Mitigation:** TC excludes any patch
where verifier was a smoke test (we already mark these); only counts
verifiers that test actual outcomes. Same standard as PSM.

### Failure mode F: Information latency in event_spine
If the event_spine has high latency (event happens at T, written to DB
at T+10min), the risk function understates risk because "information
latency" looks low. **Mitigation:** Add `event_timestamp` AND
`recorded_timestamp` as separate columns. Latency = difference. Already
in the canonical R403 spine spec; verify it's actually populated.

## Fusks-and-error map (the variance-pattern audit)

Same lens we've used on every patch:

| Risk | Probability | Severity | Variance dimension affected | Mitigation |
|---|---|---|---|---|
| MPCS lockup as canon before measurable | High if rushed | Severe — lies in commits | Knowledge-fit (we don't know what we claim to know) | Phase 1 explicitly forbids it |
| Two canons fire contradictory prescriptions | Medium | Severe — paralysis | Time (delay), cost (no progress) | Explicit precedence rules in both docs |
| CI implementation drags forever | High | Medium — Phase 3 never lands | All three variances grow on the MPCS work itself | Phase 1+2 deliver value without CI. CI is optional in Phase 3. |
| TC inflation from weak verifiers | Medium | High — looks converged when not | Knowledge-fit, cost | Standard verifier discipline applies |
| event_spine latency understates risk | Medium | Medium | Time | Add separate timestamp columns |
| Schema migration on production breaks downstream | Low (we have PSM) | High | All three | Phase 2 ships changes sequentially, each snapshot-verified |
| Phase 3 gate triggers on small jobs | Medium | Low — but credibility loss | Cost (founder annoyance) | $50 threshold |
| Founder doesn't approve phase 2 — phase 1 sits as dead code | Low | Low | Cost (sunk research) | Phase 1 has standalone value as research doc |

**Variance dimensions covered:** all three from yesterday's canon (time,
cost, knowledge-fit). Consistent. No new risk class introduced.

## Cross-system consistency check — does this match patterns we already use

| Pattern | Used here? | Notes |
|---|---|---|
| Snapshot before change | ✓ Phase 2 schema changes are PSM-disciplined |
| Verifier per shape-of-complete | ✓ Every script ships with a verifier command |
| Standard ≥ canon ≥ implementation order | ✓ Research → operational → canon → runtime |
| Composition over replacement | ✓ MPCS composes with variance canon; doesn't replace |
| Job-tag attribution | ✓ Every MPCS metric is per-(tenant_id, job_id) |
| HITL refusal as runtime gate | ✓ Phase 3 gate IS a HITL refusal |
| Tripwire integrity | ✓ TC reads from tripwire output |
| Build-log citation in every commit | ✓ Each phase commits log "MPCS Phase N: X variables promoted" |
| 33/66 anchors as canon | ✓ Phase 3 enforces 33% Hypothesis as runtime check |
| Knowledge-fit variance gate at assignment | ✓ Phase 3 Rosetta dispatcher gate uses PC + CI |
| Glossary entry for every new term | ✓ Phase 1 adds 7 entries (ID, PC, CI, BCD, TC, Risk, Gate) |
| Tenant isolation enforced in code | ✓ All MPCS DBs already tenant-scoped via PATCH-408 |

**All twelve standing patterns satisfied.** No special-case for MPCS.
This is the test for "comparable across the system" — if any of these
were missing, MPCS would be an island.

## What needs to be adjusted in existing components

Five places where existing code/canon needs a touch to stay consistent
once MPCS lands:

1. **`variance_interception_canon.md`** — add one paragraph naming MPCS
   as the formal superset and stating precedence (MPCS gate authoritative
   above $50, variance canon for everything else).

2. **`docs/architecture/glossary.md`** — add 7 entries from MPCS spec.
   No removal needed; pure additions.

3. **`build_log.md`** — add a section "MPCS phasing" tracking which
   variables are canon vs research per phase.

4. **`compliance_as_code_engine.py`** — needs to declare
   `expected_boundary_classes` per job type. Small dict, no
   architecture change.

5. **`event_spine.db`** — verify `event_timestamp` and `recorded_timestamp`
   are both populated. If only one column, add the other. PSM-disciplined.

None of these require rewriting anything that exists. All are additions
or single-column expansions.

## Decision points the founder needs to make

Before any code ships:

1. **Phase 1 only, or commit to Phase 2 sequencing now?**
   Phase 1 alone is ~6 credits, no architectural lock-in. Adding Phase 2
   commitment doesn't change Phase 1 cost but signals follow-through.

2. **Is the $50 threshold for gate-applicability the right number?**
   Picked from gut. Could be $100, $10, or "all jobs above tenant cost
   tolerance configured per tenant." Default proposed: $50 platform-wide,
   configurable per tenant in vault.

3. **Should MPCS variables go into context_readiness_canon as new standards
   16-21?**
   Pro: keeps all measurable capabilities in one rubric. Con: makes the
   PCR ladder longer when we just locked it at 15.
   Default proposed: NO. MPCS gets its own canon when promoted. Cleaner
   composition.

4. **Phase 3 (Convergence Gate as runtime check) — do we even commit to
   it now?**
   Phase 1 and 2 deliver real value standalone. Phase 3 is the powerful
   one but also the expensive one. Default proposed: defer Phase 3
   decision until Phase 1+2 ship and we have data on whether the
   partial gate is already useful.

## Recommendation if you say "go"

Ship Phase 1 only. ~6 credits. Lands as:
- `docs/research/mpcs_v2_spec.md` (your spec preserved)
- `scripts/trajectory_confidence.py` + verifier
- `scripts/mpcs_risk.py` + verifier
- 7 glossary additions
- One cross-reference paragraph in variance canon
- One build_log entry

No canon binding. No runtime behavior change. TC and Risk become
computable in production. Phase 2 stays on the queue for a future
session when you've seen Phase 1 land.

Outcome: MPCS is integrated, not adopted. The spec lives in the system.
The easy variables are real. The hard ones are honestly named as not-yet.
And the variance canon we shipped yesterday is unchanged and authoritative
until MPCS earns its own promotion.

## What I will NOT do without your explicit go

- Touch any DB schema
- Lock any MPCS variable as canon
- Change runtime behavior
- Modify Rosetta dispatcher
- Ship Phase 2 or Phase 3
- Change the $50 threshold from a proposal to a binding number

This document is the plan. The plan is not the doing.
