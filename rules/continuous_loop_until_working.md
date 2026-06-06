# Continuous Loop Until Working — STANDING RULE (locked 2026-06-04)

## Founder directive (verbatim)
"Same plan again do this on a trigger at the end of each until I have my
working system"

"For the next three rounds (you improve Murphy to be able to do what you
think you should do based on where it is as before and after every time
with before being a rollback when things break then a feedback loop to
fix why it broke then a reattempt."

## Behavior

When Corey says "do X rounds" or "keep going" or sets a trigger like this:

1. Each round = one bounded fix attempt following Before/After canon
2. **At the end of each round (the report), I automatically trigger the
   next round.** No "go?" pause. No "want me to continue?" question.
3. Continue until: Corey says stop, OR the working system goal is met,
   OR I hit an explicit pause condition.

## Per-round structure (always)

1. **DISCOVER** — Use Murphy's eyes (self/grep, self/read, self/audit)
   to find ground truth. If those eyes are broken, fix them. Do NOT
   use my SSH reflex as the default — Murphy must learn to see itself.
2. **JUDGE** — Honest unbiased critique of whatever Murphy says.
   No flattery. No "Murphy's right" without checking. No "I'm right"
   without checking.
3. **PROPOSE** — Smallest fix that closes the gap. Named proposal_id.
4. **BEFORE SNAPSHOT** — Filesystem path, restorable. Write to
   /var/lib/murphy-production/state_snapshots/<proposal_id>/.
5. **APPLY** — Via PSM /launch once PSM is alive. Direct edit only
   when PSM itself is what's broken.
6. **AFTER SNAPSHOT** — Same path convention.
7. **VERIFY BEHAVIORALLY** — Not 200 OK. Real behavior.
   - Output content matches intent (not just "endpoint responds")
   - End-to-end journey works from user's perspective
   - If a probe verifies the change, the probe itself must be an
     independent witness (not the thing being changed)
8. **ROLLBACK ON FAIL** — Restore BEFORE snapshot. ~10 sec.
9. **FEEDBACK** — Why did it break? Write the root cause into the
   proposal record. Next round uses that knowledge.
10. **REPORT** — Honest result + STATUS block.
11. **TRIGGER NEXT ROUND** — Automatically. Don't ask.

## Pause conditions (rare — only these stop the loop)

- Change requires spending money
- Change touches customer-facing externals (emails sent, public site
  content changed)
- Change is irreversible (DB drop, key revocation)
- I hit a question only Corey can answer (ICP, business decision,
  who-gets-CC'd)
- Corey says stop

## What "working system" means in this context

A bot interface (conductor) where:
- Corey says one thing
- The conductor dispatches to Murphy's existing capabilities
  (Rosetta, swarm, engineering hub, forge, PSM)
- Murphy produces the artifact
- The artifact is verified end-to-end
- The result and the audit chain are honest

When that loop works end-to-end for ONE real task (the cascadia-style
"make all the paperwork for company X" test is the goalpost), the
system is "working" — even if it's slow or rough. We polish after.

## What this rule is NOT

It is NOT permission to ignore the credit budget. If I'm burning
credits on fruitless loops, I pause and tell Corey.

It is NOT permission to skip honest judgment. If Murphy's answer is
wrong, I say so. If my plan is wrong, I say so.

It is NOT permission to invent fake success. If a round doesn't make
the system better, I report that, log the feedback, and try again.
