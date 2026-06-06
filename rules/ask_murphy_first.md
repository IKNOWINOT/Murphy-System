# Ask Murphy First — LOCKED 2026-05-25

## The founder's directive (verbatim)
"Your recommendations are generally correct but ask Murphy what it
thinks too because it can see its own source code easily"

## The rule

Before proposing any architectural addition (new table, new module, new
naming scheme, new field, new endpoint), I must FIRST ask Murphy:
"do you already have this?"

Concretely, before recommending X, run at least one of:
1. `grep -rnE` on relevant patterns in /opt/Murphy-System/src/
2. `sqlite3 .schema` on candidate DBs
3. POST to `/api/rosetta/dispatch` with role=cto and the architecture
   question — let the 5-agent team weigh in
4. Check rosetta_models.py + agent_contracts schema for existing fields
5. Self-grep via `/api/self/grep` (within its 50-file cap)

## Why this matters

Murphy has 1,727 routes, 92 DBs, hundreds of modules, and source code
references I can't see from the outside. In BLOCK-A.1.3a it revealed
`job_number` already exists in rosetta_models.py — saving us from adding
a redundant column. My external-recommendation was strictly worse than
what Murphy could see in its own code.

I am ONE perspective. Murphy is the other. Both must be consulted on
architecture decisions.

## When this applies

ALWAYS, before:
- Adding a new column
- Adding a new table
- Adding a new file
- Adding a new naming scheme or ID format
- Proposing a new pattern that "fits" the existing system
- Marking any plan item as "needs new"

## When this doesn't apply

- Simple bug fixes inside known modules
- Updating an already-justified new file
- Pure documentation writes (rules, memory, build_log)
- Audit/inventory commands (those ARE the ask)

## How to compose with other rules

- **Rule A (Audit First)** = audit reality before answering
- **THIS rule (Ask Murphy First)** = check Murphy's own knowledge before
  proposing architecture
- They're siblings: A is for state questions, this is for design questions

## What to do with Murphy's answer

- If Murphy reveals an existing field/table/module → USE IT, log the find
- If Murphy reveals 1,000+ refs that would break → REVISE the recommendation
- If Murphy's dispatch returns a different verdict than mine → reconcile
  openly in chat, explain which I'm choosing and why
- If Murphy's answer is silence/no-match → proceed with original recommendation,
  noted as "Murphy had nothing — greenfield justified"
