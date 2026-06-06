# Suggestion Queue — LOCKED 2026-05-25

## The founder's directive (verbatim)
"If things can be improved Like this you are welcome to make suggestions
that become a list when I say checking in. Then I go through all of
the questions and suggestions"

## The rule

As I work, I maintain a running list of:
- Improvements I notice in the system
- Things that look off but aren't blocking my current task
- Suggestions for architecture, naming, UX, performance
- Questions I'd ask if the founder were on the call
- Tradeoffs that deserve founder input (not blocking, but worth a call)

I do NOT interrupt the work to surface each one. They go in the queue.

When the founder says **"checking in"** (or any equivalent like "what
do you have," "questions?", "suggestions?", "queue", "list"), I dump
the full queue at once, ordered by importance, and clear it after
the founder addresses each.

## File location

The live queue lives at `.agents/memory/suggestion_queue.md`.

## Queue entry format

Each entry:
```
### [N]. <one-line title>
**Tier:** important / nice-to-have / question / fyi
**Surfaced:** YYYY-MM-DD (where in the work I noticed it: PHASE/STEP/BLOCK)
**What I saw:** plain-English description
**My take:** what I'd recommend
**Cost to address:** rough effort estimate
**Founder input needed:** what kind of answer would unblock action
---
```

## Tiers (so founder can triage fast)

- **important** — could affect correctness, cost, or direction; address soon
- **nice-to-have** — quality/polish wins; address when there's time
- **question** — I'm not sure which way is right; need founder call
- **fyi** — informational, no action needed, just want it visible

## When to ADD to the queue (not chat)

- Mid-build observation that's not blocking
- Architectural smell I'd refactor later
- A potentially better way to do something I'm doing now
- A pattern I'd want to apply elsewhere too
- A test result that's "passing but suspicious"
- A piece of memory/docs I'd want to update

## When to INTERRUPT (not queue) — hard blockers only

- Cannot proceed without founder decision
- Discovered something dangerous (data loss risk, security hole)
- About to do something irreversible without explicit consent
- Fork triggered by founder directly

## Composes with other rules

- **Cyborg Mode** — queue doesn't pause progression; it accumulates while
  I keep working
- **Audit First** — observations from audits go into queue if not blocking
- **Ask Murphy First** — Murphy's "no" answers can become queue items
- **Does It Do What Designed** — "passing but suspicious" cases queue up
