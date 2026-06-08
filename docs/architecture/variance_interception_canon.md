# Variance Interception Canon — LOCKED 2026-06-08

## Founder principle (verbatim, paraphrased for canon)

> "Problems on average show up at 30 or 70% statistically. 33.33 and 66.66
> represent points where if key information isn't assigned and known then
> problems can begin to compound. One being novelization and the other is
> where the problems from 33.333 as symptoms unchecked become massive
> offsets of issues. The middle path suggests that if the variance from
> timeline or cost line exceeds past 33% then the possibility of the end
> inversion through Pythagorean run suggests that it becomes quite more
> timely or more costly to intercept. Calculus of success means we need
> to know a plan that follows the requirements of whatever solution with
> correct knowledge in the correct arena."
>
> — Corey Post, 2026-06-08

## The mathematical anchors

- **33.33%** (one-third) — the **novelization threshold**. The point in
  a plan, run, or budget at which unhandled symptoms STOP being noise
  and START being a story. They take recognizable shape. If the right
  knowledge isn't already assigned to the right node by this point, the
  problem begins to compound.
- **66.66%** (two-thirds) — the **inversion threshold**. The point at
  which the symptoms that emerged at 33% have compounded past
  recoverable scope. Cost-to-fix exceeds cost-to-have-prevented.
  Pythagorean run: variance grows along the hypotenuse of (time-lost² +
  cost-overrun²), not linearly.

## The empirical clusters

- Real-world failures bunch at **~30%** (early symptom emergence) and
  **~70%** (full compounding). 33.33/66.66 are the mathematical anchors;
  30/70 is where the data actually clusters. We treat 30 and 33 as the
  same warning zone, and 66 and 70 as the same critical zone.

## The middle path (interception window)

Between 33% and 66% is the **only window where intervention costs less
than the problem will cost.** Inside this window, course-correction is
linear. Outside it (above 66%), correction goes diagonal — cost grows
geometrically, not additively.

This is why **continuous variance tracking matters more than periodic
review**. By the time a quarterly review catches a problem, you're past
66%.

## The three variances we track

Every job, patch, customer interaction, or in-flight plan in Murphy
must carry continuous measurement on:

1. **Time variance** — `% of planned schedule consumed vs. % of
   work delivered`. If you've burned 40% of planned time but delivered
   only 20% of work, time variance = +20 percentage points.

2. **Cost variance** — `% of planned budget consumed vs. % of value
   delivered`. Burned 40% of dollars to deliver 20% of value =
   +20pp cost variance.

3. **Knowledge-fit variance** — `% of required-knowledge actually
   present in the assigned node vs. what the task demands`. This is the
   leading indicator. An SDR-role agent making compliance decisions is
   already at high knowledge-fit variance even if time and cost are still
   on plan. This is the variance that creates the symptoms which
   eventually become time and cost overruns.

**Knowledge-fit variance is the early warning.** It precedes time and
cost variance by definition — wrong-arena assignments are why plans go
wrong in the first place.

## The four interception zones

| Variance | Zone | Murphy response |
|---|---|---|
| 0–33% | 🟢 Green | Proceed. Log to ledger. No action required. |
| 33–50% | 🟡 Yellow | Soft signal. Murphy proposes a correction in chat. No blocking. |
| 50–66% | 🟠 Orange | Soft HITL. Murphy stops auto-proceeding, asks founder for a decision. Continues only with founder go. |
| > 66% | 🔴 Red | Hard HITL. Murphy refuses to proceed. Records inversion. Post-mortem required before any continuation. |

## "Correct knowledge in the correct arena" — Murphy definition

The Rosetta architecture already speaks this language. Concretely:

- **Right role** — the Rosetta title matches the work-class (SDR for
  outbound, compliance officer for policy decisions, bookkeeper for
  ledger writes, etc.).
- **Right skills** — the typed-dispatch skills the agent can invoke
  are sufficient for the task. Missing skill = knowledge-fit gap.
- **Right docs in context** — glossary entries, canon docs, prior
  decisions relevant to the task are loaded into the agent's context
  window before it acts.
- **Right scope** — the action falls inside the agent's authority
  boundary (no SDR sending wire transfers, no bookkeeper writing
  customer emails).

Any one of these missing = knowledge-fit variance starts climbing.

## Verifier (shape of complete)

The canon is enforced when:

1. **Every (tenant_id, job_id) row in the cost ledger carries:**
   `planned_minutes`, `planned_cost_usd`, `assigned_role`, `required_skills_json`.

2. **A monitor recomputes variance every 5 min for in-flight jobs:**
   `variance_monitor.compute(job_id) -> {time_var, cost_var, knowledge_var, zone}`

3. **The monitor triggers HITL automatically when zone crosses 50% (orange)
   or 66% (red).** HITL prompt cites which of the three variances caused
   the trip, and the suggested correction.

4. **Post-mortems on red-zone trips name the arena/knowledge gap
   that drove the drift** and are logged to
   `var/lib/murphy-production/variance_postmortems.db`. Murphy reads these
   when assigning future jobs of similar shape.

5. **Verifier command:**
   `python3 scripts/variance_check.py --in-flight`
   returns a table of all live jobs with current variance % and zone.

## Operating rules

1. **No job runs without `planned_*` fields populated.** A plan without
   numbers cannot have variance, which means it cannot be intercepted.
2. **Knowledge-fit variance is checked AT ASSIGNMENT, not at deadline.**
   The Rosetta dispatcher refuses assignments where the assigned role's
   skills/scope are < 67% of the task's declared needs.
3. **No silent course corrections past 33%.** Any patch that lands while
   a job is in the yellow zone or above must log "variance state at
   commit" to the build_log.
4. **Red-zone post-mortems are mandatory and public.** They get a
   `docs/postmortems/<job_id>.md` entry. The pattern is what trains
   future assignments.
5. **The 33/66 anchors are not configurable.** They're the canon. Per-job
   tolerances are allowed only as TIGHTER thresholds (some critical
   work uses 20/50 instead of 33/66), never looser.

## Why this matters for an AI swarm specifically

A human team gets variance signals through standups, hallway
conversation, and the manager's intuition. An agent swarm has none of
that. **Without explicit variance interception, an autonomous system
will faithfully run a doomed plan all the way to 99% before noticing.**

This canon is the swarm's standup. The variance monitor is the manager
walking the floor. The HITL trip at 50% is the team lead pulling people
into a room. The hard HITL at 66% is the executive sponsor stopping the
project.

Without these, autonomy compounds wrongness as fast as it compounds
rightness.

## Composition with existing canon

- **Composes with context_readiness_canon.md (STD-6 Data SLAs):**
  variance thresholds ARE the SLAs for in-flight work.
- **Composes with vault_and_accounting_canon.md (PATCH-409 job ledger):**
  the (tenant_id, job_id) tag is the unit of measurement.
- **Composes with before_after_canon.md (PSM):** snapshot before any
  variance-triggered course correction.
- **Composes with the Rosetta architecture:** "right arena" means right
  Rosetta role, which means knowledge-fit variance is computable from
  role-bundle introspection.

## Lessons embedded

- **L25 (new):** 33/66 is not just a heuristic — it's a forcing function.
  Without explicit thresholds, "we should have caught this earlier" is
  the most expensive sentence in any post-mortem. With thresholds, the
  system catches it for you.
- **L26 (new):** Knowledge-fit variance is the leading indicator. By the
  time time-variance shows up, you've already wasted a third of the
  plan. The Rosetta dispatcher is where this gets caught — at
  assignment, not at deadline.

## Promotion path

This canon graduates to PCR-016 (Variance Interception, new patch in the
context readiness ladder) when:
- `planned_*` columns added to the cost ledger
- `variance_monitor.py` shipped + verifier passes
- Rosetta dispatcher gates on knowledge-fit variance
- First HITL trip fires correctly (test or real)
