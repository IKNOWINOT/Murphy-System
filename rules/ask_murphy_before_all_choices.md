# Ask Murphy Before All Choices — CANON (2026-06-04)

Founder directive, verbatim: *"Check with Murphy before all choices"*

## The rule

**No choice gets made without consulting Murphy first.**

"Murphy" = the live system at murphy.systems and its agents.
I (the Base44 superagent) am Corey's assistant, not Murphy's brain.
Murphy is the system of record for what Murphy should do next.

## What counts as "a choice"

Any of these:
- Editing code in /opt/Murphy-System
- Changing a systemd unit, nginx config, env file, DB schema, DB rows
- Enabling/disabling/changing any automation (Base44 or systemd timer)
- Sending an outbound email, SMS, or call
- Spending money or moving money
- Authorising an OAuth connector
- Mutating any external API (Stripe, Twilio, NOWPayments, Wix, GitHub)
- Picking a strategy ("should we do X or Y") that affects revenue or risk
- Marking work complete
- Closing an open thread

## What does NOT count (always allowed without asking)

- Reading files, querying DBs, curling endpoints (observation)
- Taking BEFORE snapshots (defensive, can't hurt)
- Reporting status to Corey
- Asking Murphy clarifying questions
- Reading session logs or memory

## How to ask Murphy

In priority order:

1. **Direct chat:** `POST https://murphy.systems/api/chat` with my proposal
   and ask "approve / modify / reject?"
2. **HITL queue (v2):** `POST /api/hitl-v2/items` to put it in the
   formal decision queue when the choice is non-trivial.
3. **Rosetta dispatch:** `POST /api/rosetta/dispatch` with role=relevant-dept
   when the choice is domain-specific (sales, finance, ops).
4. **Founder-watch channel** when Murphy doesn't respond in 60s and
   the choice is time-sensitive — escalate to Corey directly.

If Murphy is unreachable AND Corey is unreachable AND the choice is
genuinely urgent: take the most reversible path, snapshot BEFORE, and
report immediately on next contact.

## What the ask looks like

Every ask must include:
1. **The choice** — one line, plain English
2. **The reason** — why this came up
3. **Options** — at least 2, with pros/cons
4. **My recommendation** — what I'd do if I had to choose
5. **Reversibility** — how I'd undo it (links to snapshot plan per canon)
6. **Timeout behavior** — what I'll do if no answer in N minutes

Example:
```
CHOICE: Add NOWPAYMENTS_API_KEY to secrets.env and restart murphy.service
REASON: Buy button on /pricing returns 404 because monolith env is missing the key
OPTIONS:
  A) Copy key from /etc/murphy-production/environment to secrets.env — 5 min
  B) Update unit file to load both env files — 10 min, cleaner
  C) Do nothing, route customers to a Stripe link instead — different product call
RECOMMEND: B (cleaner, no key duplication)
REVERSE: BEFORE snapshot of secrets.env + unit file; restore = swap back
TIMEOUT: If no answer in 10 min and no objection from Corey, do A as the safer fast path
```

## Why this is canon

- I'm an assistant. Murphy is the agent that owns its own roadmap.
- I've been making product/strategy calls (which email to send, which
  microservice to fix, which doc to write) without checking with Murphy.
  That's me overstepping.
- Murphy's shape-verifier already reports the slice priorities every
  30 min. I should be reading those priorities and aligning, not picking
  my own.

## Standing exception — emergencies

If a paying customer is being charged incorrectly, data is being
destroyed, or a security incident is active: act first, snapshot,
report immediately. No paying customer exists today, so this exception
is currently theoretical.

## Today's checkpoint

I had three "asks" ready to fire on my own initiative when Corey said
"check with Murphy first":
1. Verify the NOWPayments end-to-end buy flow
2. Write the 3 missing doc files
3. Add Hawthorne to standing CC

None happen until I run them past Murphy.
