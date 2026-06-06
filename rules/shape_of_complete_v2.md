# Shape of Complete — Master Definition (2026-05-26)

## Why this exists
"Done" has been ambiguous. Murphy and Cyborg have both shipped things that
passed individual gates but didn't deliver. This document is the canonical
definition the entire system measures against. Every block, every page,
every doc, every promise must reach this shape to be marked complete.

## The 7 Pillars

A unit (block, page, capability, channel, doc) is COMPLETE only when ALL
seven pillars are green.

### Pillar 1 — CODE
- File exists at the canonical path
- Compiles / parses without error
- No TODOs marked "must-fix"
- No hardcoded secrets, no `localhost`, no test-only values
- VERIFY: `py_compile`, `grep -i "todo\|fixme\|hardcoded"`, lint pass

### Pillar 2 — WIRED
- Code is imported / route is registered / handler is bound
- Reachable from outside (HTTP, CLI, channel handler)
- Listed in module_registry where applicable
- VERIFY: registry query OR `curl` returns non-404 OR import succeeds

### Pillar 3 — DEPENDENCIES
- Every external dependency is real and reachable:
  - DB tables exist with the expected schema
  - Secrets in vault under the right name
  - OAuth/API tokens valid
  - Sister services on the network
- VERIFY: schema query, `_vault_use`, ping, version check

### Pillar 4 — EXECUTES
- Runs end-to-end on a real input and produces the designed output
- Test array (locked rule): weak / good / precise / really-good inputs all
  behave as designed
- Side effects happen as intended (DB row written, email sent, etc.)
- VERIFY: actual invocation against live system, output captured

### Pillar 5 — VISIBLE
- Founder can see it from the OS page or a dedicated UI
- Status flows into self_audit snapshot if it's a system component
- Metrics flow into a registry / dashboard
- VERIFY: page renders the data, audit endpoint includes it

### Pillar 6 — DOCUMENTED
- One paragraph in README / docs explaining what it does
- One example call / screenshot / sample output
- Mentioned in landing page IF it's customer-facing
- Listed in CHANGELOG with date
- VERIFY: grep docs, check landing page, check CHANGELOG

### Pillar 7 — CONSISTENT
- Voice matches src/murphy_voice.py (warmth, brevity, founder=Corey)
- Naming matches the canonical registry
- Same fact stated in code = on landing page = in docs = in audit endpoint
- Pre-revenue claims stay pre-revenue (no fake $9,065)
- VERIFY: cross-check landing vs docs vs API responses

## Verdict states
- 🟢 GREEN — all 7 pillars verified in this turn
- 🟡 YELLOW — code works but at least 1 pillar missing (visible, docs, consistent)
- 🔴 RED — not running or contradictory

## Application to each system slice

### Slice A — Self-Modification Loop
GREEN means: Murphy proposes → QC gates → applies → audit shows it →
landing page describes it accurately → docs mention how to review →
voice is consistent.

### Slice B — Direct Chat (/chat)
GREEN means: page exists → endpoint works → memory persists →
voice is murphy_voice.py → ground truth from self_audit →
linked from OS page → documented → consistent.

### Slice C — Channels (SMS / Voice / Email)
GREEN means: every channel handler calls murphy_voice.reply_in_voice() →
same personality across all → audit visible → docs cover it →
landing page accurate.

### Slice D — Autonomous Loops (Mind, Scheduler, Patcher, Sales)
GREEN means: loop runs on schedule → heartbeats present → produces
output to a place founder can see → outputs match what the loop
promised → docs name what it produces.

### Slice E — Reporting (Audit, Pulse, Patcher, Registry)
GREEN means: endpoint returns ground truth → OS page renders it →
docs link to it → voice can cite it.

### Slice F — Landing page & docs
GREEN means: every claim has a corresponding live capability →
no fabricated revenue → no fabricated features → "What Murphy
does today" matches what self_audit says is running.

## Driver: auto-retry until shape met
Every block has a verifier function. After build, run verifier:
- 🟢 → mark complete, move on
- 🟡 → dispatch the missing pillar(s) as a follow-up patch
- 🔴 → dispatch a fix, retry up to N times, then escalate to founder

Max retries: 3 per block.
Hard timeout per block: 30 minutes.
Escalation: surface the failing pillars to /api/self/audit and notify Corey.

