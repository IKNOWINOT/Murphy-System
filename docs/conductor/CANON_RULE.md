# Conductor Pattern (R510 series — LOCKED 2026-06-04)

Every cyborg-initiated multi-step action MUST go through `/conduct-and-reply`
on port 8091.

## Why
1. Filed in PSM ledger (audit chain).
2. Real tool registry grounding — no invented endpoints.
3. POSTs auto-route to HITL via PSM (never inline).
4. Persistence — every job recoverable from conductor_jobs.db.

## CLI shortcut
sudo -E /opt/Murphy-System/venv/bin/python3 \
    /opt/Murphy-System/scripts/conductor.py "<ask>"

## HTTP
curl -X POST -H "Content-Type: application/json" \
    -d '{"message":"<ask>"}' http://127.0.0.1:8091/conduct-and-reply

## Rule
- Never bypass conductor for "quick" actions — bypass = lose the audit trail.
- Never let any sub-agent call a POST without going through HITL.
- Always cite PSM seq when reporting actions.
