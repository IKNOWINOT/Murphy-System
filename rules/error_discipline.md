# Error Discipline — LOCKED 2026-05-31 (R355)

## The founder's directive (R355, verbatim)

"Every choice has only a certain number of things that can go wrong. If you
analyze everything that can go wrong and solve for that in those ways and all
the ways it can go right too. And plan for all the ways properly. Then you
number all of them you have full error coding for reporting what is wrong.
Who what when where how why, plan for ancillary code changes as they occur."

## What this means operationally

Every patch from R355 forward must produce SIX artifacts before shipping:

### 1. FAILURE MODE ENUMERATION (FME)
List ALL ways this can fail. Not just "what's likely" — what's *possible*.
Categories: input invalid, dependency missing, timeout, race, permission,
state-corrupt, downstream-cascade, partial-success-then-fail, silent-pass-wrong.

### 2. SUCCESS MODE ENUMERATION (SME)
List ALL ways this can succeed. "What does correct output look like?" forces
you to define correct. "What does partial-correct look like?" forces you to
define graceful degradation.

### 3. NUMBERED ERROR CODES
Each failure mode gets a unique code. Format:
`E<bucket><nnnn>` — e.g. `E_PROMPT_0001`, `E_DB_0042`, `E_NET_0073`.
Register in `/var/lib/murphy-production/error_codes.json`. New code = registry
entry. Reusing existing code = look it up first.

### 4. WHO/WHAT/WHEN/WHERE/HOW/WHY in every error response
Each error response must answer:
- WHO: which caller/agent/tenant
- WHAT: what operation was attempted
- WHEN: timestamp ISO-8601
- WHERE: file:line of the gate that fired
- HOW: which check failed
- WHY: business reason (not just technical)

### 5. ANCILLARY CHANGES MAP
Before shipping, list which OTHER code/tables/docs change as a consequence.
Patch X often requires:
  - Migration on table Y
  - New row in error_codes.json
  - Updated test in test_X.py
  - Docs touch in section Z
  - Backward-compat shim for old callers
Surface these BEFORE writing the patch, not after.

### 6. ROLLBACK PLAN
Every patch ships with: how to undo. Backup file path + restore command
+ verification step + the cascade-undo if ancillary changes also need
reverting.

## The 6-artifact patch template

```markdown
# Rxxx — <patch name>

## 1. FME (Failure Modes Enumerated)
- E_<BUCKET>_<nnnn>: <one-line description> → response: <code>, status <N>
- E_<BUCKET>_<nnnn>: ...

## 2. SME (Success Modes Enumerated)
- S1: <happy path>
- S2: <degraded but correct>
- S3: <partial-correct + log>

## 3. Error code registry deltas
- ADD E_<BUCKET>_<nnnn> "<desc>"

## 4. Error response shape
{
  "ok": false,
  "error": {
    "code": "E_<BUCKET>_<nnnn>",
    "who": "<caller>", "what": "<op>", "when": "<iso>",
    "where": "<file:line>", "how": "<check>", "why": "<reason>"
  }
}

## 5. Ancillary changes
- /path/to/other_file.py — <what changes>
- /var/lib/.../db.sql — <migration>
- .agents/rules/<x>.md — <update>

## 6. Rollback
- Backup: <path>
- Restore: cp <backup> <target>
- Verify: <command that proves system is back>
- Cascade-undo: <if needed>
```

## When this applies

ALWAYS, before ANY substrate patch. Exemptions:
- Pure documentation (rule files, build_log)
- Read-only audits (R208 dumps)
- One-line typo fixes with zero behavior change

Exemption ≠ rule abandonment. Even exempt work mentions which FME items it
deliberately doesn't touch.

## Composition with existing rules

- **Audit First (R208)**: still required — audit BEFORE the FME analysis
- **Ask Murphy First**: still required — Murphy is one of the FME inputs
- **Check GitHub First**: still required — anchor FME in real prior art
- **Correctness Over Cycles**: now reinforced — FME is how you DEFINE correctness
- **This rule**: makes the cycle output explicit + auditable

## The deeper principle

Surprise is the cost of incomplete enumeration. When something fails in a way
I didn't anticipate, it means I shipped without finishing the FME. Finishing
the FME is cheaper than the surprise.

Error codes are a forcing function — they make me name what I'm protecting
against. Naming is the work.
