# Correctness Over Cycles — LOCKED 2026-05-25

## The founder's directive (verbatim)
"Correct is always more important than numbered cycles which are guidelines."

## What this means

The 3-cycle generator-critic pattern (Generate → Critic → Polish) is a
**guideline, not a gate**. The actual gate is: **is the output correct?**

- 1 cycle is fine if the work is correct.
- 5 cycles are required if cycle 3 still wasn't correct.
- Skipping critique entirely is a violation if the work isn't right.
- Running 3 cycles on garbage doesn't promote garbage to truth.

The number is a budget hint, not a quality certificate.

## How this changes my behavior

### Before this rule, I would have:
- Designed "3 cycles before commit" as a hard architectural gate
- Marked a job "ready for HITL" after exactly 3 cycles regardless of state
- Treated "passed cycle 3" as equivalent to "correct"

### After this rule, I must:
- Treat correctness as the actual exit condition
- Run as many cycles as correctness requires (1 to N)
- If after N cycles it's still wrong, **escalate to HITL with the failure trail**,
  not promote a wrong answer through the pipeline
- Mark each job with `correctness_state` (not `cycles_completed`):
  - `correct` — exits the pipeline
  - `correct_pending_human_judgment` — generator-critic agree, but the
    domain requires a human (financial, customer-facing, irreversible)
  - `inconclusive_after_n_cycles` — escalate with full diff history
  - `incorrect_known` — caught by critic, sent back with reason
  - `unknowable_by_machine` — escalate immediately

## The corollary

**Cycle count is a metric we track for tuning, not a rule we enforce.**

If cycles are usually 1, the system is working well.
If cycles are usually 5+, the generator needs better prompts or context.
If cycles drift up over time, something is rotting and we should look.

## Applies to

- Generator-critic for all agent output (email drafts, code, proposals)
- HITL queue items (don't auto-expire something that's correct just because
  it hit a cycle count)
- Self-modification (PSM) — code change is committed when correct, not at
  cycle N
- Mind cycle proposals — Murphy proposes a fix when the analysis is correct,
  not when the cycle counter ticks

## Anti-patterns to refuse

❌ "It passed 3 cycles, ship it" (correctness wasn't actually verified)
❌ "Force a 3rd cycle even though cycle 1 was perfect" (waste)
❌ "Reject after exactly 3 failed cycles" (might need a 4th, or might need
   a human RIGHT NOW)
❌ "Use cycle count as the trigger for HITL escalation" (use correctness
   state instead)

## The deeper principle

Numbers can lie. Correctness can be argued about but it's the only thing
that matters. Build for the thing that matters; let numbers serve it.
