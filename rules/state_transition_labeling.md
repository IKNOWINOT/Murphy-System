# Rule: Universal State-Transition Labeling — LOCKED 2026-06-01

## The founder's directive (verbatim)
"Yes put labeling on what is happening nothing should start stop fail
or succeed without written information."

## The rule

**Nothing in the Murphy system should start, stop, fail, or succeed
without written information.**

If a process/job/scheduler/state-machine/HITL-item/email/patch goes
through any of these transitions, it MUST produce a durable, queryable
record.

## The transition vocabulary

The canonical verbs are stored in `src/r403_event_log.ALLOWED_TRANSITIONS`:

- **Lifecycle:** start, stop, fail, succeed, timeout, retry, skip
- **State control:** pause, resume
- **CRUD:** create, update, delete
- **Approval flow:** approve, reject, expire, archive
- **Comms:** send, receive, bounce
- **Gates/circuits:** open, close

If you need a verb that isn't on the list, ADD it to the list — don't
silently pick a different word that means the same thing. Discoverability
beats invention.

## How to log

### Python (most code)
```python
from src.r403_event_log import log_transition, log_start, log_succeed, log_fail

# Convenience (common case):
log_start("r386_auto_approve", reason="timer fired")
log_succeed("r386_auto_approve", reason="approved 2 drafts", elapsed_ms=140)
log_fail("r386_auto_approve", code="E_STATE_0030", reason="DB locked")

# Full form (when you need from_state/to_state):
log_transition(
    actor="founder",
    subject="scheduler:lead_prospector",
    transition="pause",
    from_state="running",
    to_state="paused",
    reason="manual pause pending product fit",
)
```

### Shell / systemd / cron
```bash
log-event --actor systemd --subject murphy-r386.timer \
          --transition succeed --reason "approved 2"

log-event --actor corey --subject scheduler:lead_prospector \
          --transition resume --reason "ready to outreach"
```

### From me (the assistant) over SSH
When I'm running ops scripts that change state, I MUST log them. Example
in any R-shipment bash block:

```bash
ssh ... 'log-event --actor murphy_assistant --subject "R401" \
                   --transition succeed --reason "3-fix cleanup batch shipped" \
                   --metadata "{\"fixes\":3,\"backups\":[...]}"'
```

## What this means for every patch I ship

Before I mark any R-shipment complete, I check:
- [ ] Process started? logged.
- [ ] Process ended? logged.
- [ ] Failure path exists? logs the fail.
- [ ] Scheduler paused/resumed? logged.
- [ ] HITL item state changed? logged.
- [ ] Email sent/bounced? logged.
- [ ] Gate opened/closed? logged.
- [ ] Patch applied to substrate? logged.

If any answer is "not logged", I'm not done.

## What it means for my replies to Corey

When I report status, I cite event_log evidence, not my memory.
"Substrate restarted at 17:35:00, ready at 17:35:52" is good.
"I just restarted the substrate" without a citation is no longer enough
when an event_log row would prove it.

## Querying the log

```bash
# Recent activity
sqlite3 /var/lib/murphy-production/event_log.db \
  "SELECT ts, actor, subject, transition, reason
   FROM state_transitions
   ORDER BY ts DESC LIMIT 20"

# Everything about a specific subject
sqlite3 /var/lib/murphy-production/event_log.db \
  "SELECT ts, actor, transition, reason
   FROM state_transitions
   WHERE subject = 'scheduler:lead_prospector'
   ORDER BY ts DESC"

# What failed in last 24h
sqlite3 /var/lib/murphy-production/event_log.db \
  "SELECT ts, actor, subject, code, reason
   FROM state_transitions
   WHERE transition = 'fail' AND ts > datetime('now','-1 day')"
```

## The deeper principle

A system without an audit trail is a system that lies to you by default.
Every silent failure, every "I think it worked", every uncertainty about
"is this scheduled?" is a tax we pay forever. R403's spine + this rule
removes the tax.

The cost of one extra log call is microseconds. The cost of being wrong
about state is hours.
