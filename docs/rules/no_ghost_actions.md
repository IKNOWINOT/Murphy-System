# No Ghost Actions — CANON (2026-06-19)

Founder directive, verbatim: *"Look for gaps like this."*
Context: discovered the Approve button in /os/review was a status-only
write that flipped a DB flag and returned ok=True while never invoking
SMTP. The reply pipeline read a different status, so the "approved"
items sat in the DB for weeks and Mike never got an email. The DB
showed "sent". Reality showed nothing arrived. The system was lying.

## The rule

**A handler that returns ok=True MUST cause the named action to
actually happen, end-to-end. If the action requires a downstream
side effect (SMTP send, queue dispatch, external API call, file
write, message publish), the handler MUST invoke that side effect
synchronously OR atomically enqueue it for a worker that we
verify is running.**

Writing a status field that NOTHING reads = ghost action.
Writing a status field that A WORKER reads = real action, IF and ONLY IF
the worker is verified running and verified to read that status.

## Gap signatures (the patterns I keep missing)

1. **Hardcoded success in the persisted record.**
   `record["status"] = "sent"` written immediately, before any SMTP call.
   Litmus: search every email/send/dispatch/publish function for the
   string `"sent"`, `"delivered"`, `"completed"`, `"approved"` set
   BEFORE the network call.

2. **Status writes with no reader.**
   Handler writes `status='founder_approved_send'`. grep the codebase:
   if NOTHING ever queries WHERE status='founder_approved_send', it's
   a dead-letter flag.

3. **Status reader exists but worker doesn't run.**
   `process_X()` reads the queue but its scheduler isn't registered.
   Check: is the function actually wired into APScheduler / asyncio
   tasks / a systemd timer? grep `add_job\|create_task\|scheduler.add`.

4. **Handler returns ok=True from the try block before the action.**
   ```python
   db.commit()           # ← row says "sent"
   return {"ok": True}   # ← returned BEFORE smtp call
   try:
       _send_email(...)  # ← if this fails, response already shipped
   except: pass
   ```

5. **Symmetric reject/approve pair where reject works but approve doesn't.**
   Reject = "set status to rejected" = the action itself (status change
   IS the action). Approve = "set status to approved" but approval
   should TRIGGER something downstream. If reject and approve have
   identical 1-line implementations, approve is probably broken.

6. **UI shows toast "✅ Sent" because handler returned 200.**
   Verify with: postfix log, network capture, or the receiving system's
   log. Toast says success ≠ bytes left the building.

## The verification protocol — required before claiming any handler works

Before claiming any /api/* endpoint that names an action is "wired":

1. **Grep the handler body** for the side-effect call:
   - email: `_send_sendmail`, `_send_branded`, `sendmail`, `smtp.send`
   - dispatch: `_queue_outbound`, `enqueue`, `process_`, `dispatch`
   - external API: `requests.post`, `httpx.post`
   - file write outside DB: `Path(...).write`, `open(...).write`
   - cross-system publish: `redis.publish`, `nats.publish`, `_emit_`
2. **Trace the call chain** at least 2 levels deep:
   handler → service func → actual side effect.
3. **For status-write handlers**: prove a reader exists AND its worker
   is running:
   ```
   grep -rn "status='<value>'" → must find SELECT, not just UPDATE.
   systemctl status <worker>   → must be active.
   journalctl -u <worker> | grep "<value>" → must show recent reads.
   ```
4. **End-to-end proof**: trigger the action, then check the EXTERNAL
   side (postfix log, external API response, target system's record).
   DB-side "success" is never proof of action.

## Standing audit

The "Approve drafts and sends" pattern means this audit runs on every
handler that has an action verb in its path: `send`, `approve`,
`dispatch`, `publish`, `notify`, `email`, `sms`, `call`, `trigger`,
`run`, `execute`, `fire`, `deploy`, `kick`, `launch`, `process`,
`reply`, `generate`.

Run quarterly. Last sweep: 2026-06-19. 473 handlers analyzed. 1 ghost
confirmed (`/api/meeting-intelligence/email-report` → fixed Ship 31cz.G).
The Approve bug had been live since pre-31aq.

## What I owe the founder

When I claim a handler works, I owe verification, not assertion. The
phrase "I confirmed it" must mean "I saw the postfix delivery line"
or equivalent external proof — not "the response was 200" or "the
DB shows sent".

When I'm wrong about a previous claim, I say so directly. No hedging
with "the system MAY have been..." or "depending on...". Either it
sent or it didn't. The mail log knows.
