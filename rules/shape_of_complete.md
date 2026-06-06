# The Shape of Complete — LOCKED 2026-05-25

## The founder's directive (verbatim)
"You need to know what is going on and your audits happen for every
request based on the context of what you are doing. What is the shape
of complete?"

## What this means

### 1. Audits are not a separate task. They are step 0 of every request.
Before I do anything, I audit the slice of reality the request touches.
- Asking about Twilio? → check vault + phone module + department_phones
- Asking about revenue? → check billing.db + GL + treasury
- Asking about an endpoint? → grep source, hit the route live
- Asking about a service? → systemctl + journalctl + curl

I do NOT rely on memory for current state. Memory is a hypothesis.
Reality is what I just queried.

### 2. The audit scope = the context of the request.
- Founder asks "did you build X?" → audit X end-to-end before answering
- Founder asks "what's broken?" → audit the surface area implied
- Founder asks "do Y" → audit the preconditions for Y before starting
- Founder asks a follow-up → audit what changed since last turn

This is not "be thorough." This is "never speak about state I haven't
just checked."

### 3. The shape of complete (what "done" actually means)

A piece of Murphy is COMPLETE when **all five** are true:

**a) The code exists.**
Source on disk in /opt/Murphy-System, committed to git.

**b) The code is wired.**
Imported by the runtime. Route mounted on the live app.
Verified by `curl` returning the expected status, not 404.

**c) The dependencies are real.**
Secrets in vault. DB tables exist with the right schema. External
services reachable. No "credentials_not_in_vault" or "table not found."

**d) The end-to-end path executes.**
Founder (or autonomous agent) can trigger it and the action actually
completes — the email sends, the call rings, the deal closes, the
ledger entry appears.

**e) The result is visible.**
There is a surface — page, API, log, dashboard — where the founder can
see that the action happened and inspect what it produced. If a thing
runs but the founder can't see it, it isn't complete.

### Worked example: Twilio (today, 2026-05-25)

| Gate | Status | Evidence |
|------|--------|----------|
| a) code exists | ✅ | `src/patch406a_voice_telephony.py` |
| b) code wired | ✅ | `POST /api/phone/dial` returns 200 |
| c) dependencies real | 🟡 | 3/4 vault secrets present; `TWILIO_PHONE_NUMBER` missing; 5 dept numbers in `department_phones` |
| d) end-to-end executes | ❌ | dial returns `credentials_not_in_vault` |
| e) result visible | ❌ | no call log surface for the founder |

Verdict: **NOT COMPLETE.** Looks ~80% done. Functionally 0% — no call has
ever rung. Closing the last 20% is what makes it real.

### Worked example: PSM gateway (today)

| Gate | Status | Evidence |
|------|--------|----------|
| a) code exists | ✅ | `src/platform_self_modification/endpoint.py` |
| b) code wired | ✅ | `/launch`, `/ledger`, `/console` all live |
| c) dependencies real | ✅ | RSC sink wired, ledger DB writable, operator token configured |
| d) end-to-end executes | ✅ | 20 hash-chained ledger entries from real proposals |
| e) result visible | 🟡 | minimal HTML console; needs a real founder UI |

Verdict: **FUNCTIONALLY COMPLETE.** Gate e is "nice to have" not "blocker."

### Worked example: Revenue pipeline (today)

| Gate | Status | Evidence |
|------|--------|----------|
| a) code | ✅ | Stripe + NOWPayments integrations |
| b) wired | ✅ | `/api/billing/*` 43 routes live |
| c) deps | 🟡 | NOWPayments live; Stripe still TEST keys |
| d) e2e | ❌ | $0 actual revenue, 0 paying customers |
| e) visible | ✅ | `/api/public/stats`, `/api/gl/*`, dashboard |

Verdict: **PLUMBING COMPLETE, OUTCOME ABSENT.** Not a code problem.
Sales problem. Different fix entirely.

## How I report status from now on

Instead of "X is built" or "X is live," I report against the 5 gates:

```
Twilio voice:        a✅ b✅ c🟡 d❌ e❌  → NOT COMPLETE (missing PHONE_NUMBER + call surface)
PSM gateway:         a✅ b✅ c✅ d✅ e🟡  → FUNCTIONAL (nice UI pending)
Outbound email:      a✅ b✅ c🟡 d❌ e✅  → BLOCKED (port 25)
Revenue:             a✅ b✅ c🟡 d❌ e✅  → NO CUSTOMERS YET (not a code issue)
Self-mod console:    a✅ b✅ c✅ d✅ e❌  → MISSING FOUNDER UI
```

This makes the gap between "looks done" and "is done" visible in one line.

## The kill criterion for "complete"

If I cannot point at a moment in production where the action actually
happened — a call ringing, an email arriving, a deal closing, a record
appearing — it is not complete, regardless of how much code I shipped.

Code without verified execution = theater.
