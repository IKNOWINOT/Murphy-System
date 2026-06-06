# Cyborg Working Mode — LOCKED 2026-05-25

## The founder's directive (verbatim, two parts)

Part 1 (option-c from cyborg-mode choice):
"2 is c but I had toyed with a reply to any block or manifold or section
of a thought then I can change the thought process there which restarted
generation from that point on. And then runs a slight modification of
needed over prior aspects. Then does a full qc again."

Part 2 (continuous progression):
"3.) it means that I want you to continue working on the overall plan
referencing where you are in it that plan. then continuing where you
left off even if I don't respond."

## What this means in practice

### A. Work in addressable, named blocks

Every unit of work I produce gets a stable ID:
  - PHASE-A → STEP-A1 → BLOCK-A1.1 → BLOCK-A1.2 ...
  - Blocks are labeled IN-LINE in chat with their ID
  - The build log mirrors the same IDs

So the founder can say "fork at BLOCK-A1.2" and I know exactly what
slice of thinking to restart.

### B. Mid-stream fork handling

When the founder replies to ANY block at ANY time:

  1. Treat reply as a FORK POINT — note `FORK at BLOCK-X.Y: <correction>`
     in the build log under a `## Forks` section
  2. **Restart generation from that block forward** using the corrected
     thinking — not the original line of reasoning
  3. **Lightly re-touch upstream dependencies** — find blocks that built
     on the now-changed thought and modify them where needed (not a full
     rebuild; a targeted patch)
  4. **Re-run full QC on the entire thread**:
     - Block-scope tests for the forked block AND every touched upstream
     - Pipeline-scope tests end-to-end
     - All four input tiers (weak/good/precise/really-good)
  5. Update the build log with what was forked, what was re-touched,
     and the new QC verdict

### C. Continuous progression — no waiting for permission

Once the master build plan is approved, I work through it without
pausing for "ready for the next one?" prompts.

I keep moving down the task list, marking the build log:
  - `▶ NOW: STEP-A2 BLOCK-A2.3`
  - `✅ DONE: STEP-A1 (all blocks, pipeline verified)`
  - `⏸ BLOCKED: STEP-B4 — needs founder decision on X`

I ONLY pause for:
  - Hard external blockers (credentials, port 25, etc.)
  - Founder fork mid-stream
  - MSS verification failure I can't auto-resolve (escalate w/ context)
  - Task explicitly marked "founder-gated" in the plan

If the founder doesn't respond, I do NOT stop. I continue working the
plan in order. The plan is the contract; absence of response is consent
to keep going.

## Block addressing scheme

```
PHASE-X          (top-level phase: Foundation, See-it-live, etc.)
  STEP-X.N       (numbered step within phase)
    BLOCK-X.N.M  (specific unit of thought/work within step)
```

Examples:
- PHASE-A = Foundation
- STEP-A.2 = Build the registry tables
- BLOCK-A.2.3 = `registry_actions` schema design

Every block in chat output starts with `### BLOCK-X.N.M — <title>` so
forks land precisely.

## The build log (.agents/memory/build_log.md)

Structure:
```
# Murphy Master Build — Live Log

## Cursor
▶ NOW: STEP-A.2 BLOCK-A.2.3 (registry_actions schema)
Updated: <ISO timestamp>

## Forks
- FORK at BLOCK-A.1.2 (2026-05-25 14:50): founder said "use SQLite WAL
  mode not journal" — re-touched BLOCK-A.1.1 schema header, re-ran QC
  on PHASE-A pipeline, verdict ✅

## Progress
- ✅ STEP-A.1 (audit DBs)         — block + pipeline ✅, 4 tiers ✅
- ▶  STEP-A.2 (registry tables)   — in progress
- ⏳ STEP-A.3 (audit middleware)
- ⏸ STEP-B.4 (HITL email out)    — blocked: port 25

## Block ledger
### BLOCK-A.1.1 — DB inventory
  Intent: enumerate every .db file under /var/lib/murphy-production
  Tests: [weak]: empty dir → ✅ | [good]: real path → ✅ |
         [precise]: glob spec → ✅ | [really good]: w/ permissions check → ✅
  Block verdict: ✅
  Pipeline verdict: ✅ (feeds STEP-A.2 schema design correctly)
```

## What this is NOT

- Not "ask before every step" — that's option (a), rejected.
- Not "silent grinding" — that's the old failure mode.
- Not "rebuild from scratch on every correction" — fork = targeted patch,
  not full restart.
- Not "skip QC when in a hurry" — Rule E always applies; correctness
  over cycles always applies.

## How this composes with other rules

- Rule A (Audit First) — still runs before each step
- Rule B (5-gate) — still the structural completeness test
- Rule C (Audit every prompt) — still required
- Rule D (Correctness over Cycles) — still the exit condition
- Rule E (Does it do what designed) — still the verification rubric
- THIS rule (Cyborg Mode) — describes the *cadence and steering* of work,
  not the *quality bar*. The bar stays the same.
