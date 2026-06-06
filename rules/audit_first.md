# Audit First — LOCKED 2026-05-25

## The founder's directive (verbatim)
"You need to note that there is no way for you to see everything at once
due to size so you have to make audits and checklists for every request
and choice."

## The truth this is built on

Murphy is too big to fit in my context window. As of 2026-05-25:
- 135+ HTML files on disk
- 1,727 routes across 270 prefixes
- 14+ SQLite databases
- 64+ patch modules

I cannot hold this in memory. Anything I claim from memory is a guess.
The only honest answers come from a fresh audit of the slice the
current request touches.

## The rule

**Every request triggers an audit + checklist before I answer.**

No exceptions. No "I think I remember." No "I just checked that last turn."
The cost of one bash command is lower than the cost of being wrong again.

## The audit pattern (apply to every request)

### Step 1 — Identify the slice
What does this request actually touch?
- A page? → that page's route + file + 5 gates
- A capability (HITL, Voice, GL)? → its registry entry + dependent routes + DB tables
- Multiple things? → audit each slice independently

### Step 2 — Build the checklist
Write the checklist BEFORE doing the work. Something like:
```
For request "add tabs to /hitl":
[ ] What HTML files claim to be HITL? (find + grep)
[ ] What routes serve them? (grep app.py)
[ ] What DB tables back them? (find + sqlite3 .tables)
[ ] What APIs do they call? (grep static/hitl.html for /api/)
[ ] Are dependencies real? (curl each /api endpoint)
[ ] What's broken? (5-gate score per slice)
```

### Step 3 — Run it, record results
Execute every checkbox. Paste real output, not summarized.
If a gate is 🟡 or ❌, that's a finding I must surface — not skip.

### Step 4 — Only then answer or act
Now I can speak. My answer cites what I just verified.
If I claim something I didn't verify in this turn, I mark it
"per memory, unverified" — never as fact.

## The registry is what makes this scalable

Without a registry, every audit means re-walking source. With a registry,
audits become fast lookups. That's why the founder asked for an active
registry/ledger — it's the only way audits stay cheap enough to do
every prompt.

When the registry exists, the pattern becomes:
1. Query registry for the slice
2. Confirm registry vs. live system (cheap — registry has expected state)
3. Report

## Anti-patterns I keep falling into

❌ Answering from <memory> in my system prompt
❌ Reusing audit results from earlier in the same conversation
   (they may be stale by the next turn)
❌ Saying "the system has X" without a fresh query
❌ Saying "X doesn't exist" without grepping
❌ Saying "X is done" without checking gates c/d/e
❌ Treating my context window as the source of truth

## What "audit" minimally means

For each request, before I speak or act, I run at least:
- `bash` or `grep` for the source-of-truth file
- `curl` for any URL/endpoint I'm about to claim status on
- `sqlite3` for any DB state I reference

Skipping these is a violation. Every violation costs the founder time
correcting me, and erodes trust further.

## The escape hatch — when audit isn't possible

If the user asks something genuinely opinion-based (e.g. "which should
I do first"), there's no system slice to audit. Then I say so explicitly
and answer as opinion. But I never disguise opinion as audited fact.
