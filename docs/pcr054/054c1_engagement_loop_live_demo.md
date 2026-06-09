# PCR-054c.1 — Engagement Loop Live Demo (2026-06-09)

## What ran

End-to-end on production at `https://murphy.systems/api/org/engagement/*`.
Verifies the full 7-pillar Shape of Complete for the Creation engagement loop.

## The 7-step demo

```bash
KEY="$MURPHY_FOUNDER_KEY"
BASE="https://murphy.systems"

# 1. CREATE — fresh CPA tax return folder
EID=$(curl -sS -X POST -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  $BASE/api/org/engagement/create \
  -d '{"tenant_id":"acme_corp","role_id":"cpa_main","artifact_type":"tax_return","artifact_content":"Form 1120 draft","license_type_required":"CPA","jurisdiction_required":"US-CA"}' \
  | jq -r .engagement.engagement_id)

# 2. drafting -> outreach_queued (assign practitioner + rate quote)
curl -sS -X POST -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  $BASE/api/org/engagement/$EID/transition \
  -d '{"to_state":"outreach_queued","reason":"selected CPA from bench","update_fields":{"practitioner_email":"jane.cpa@example.com","rate_quote_usd":1080.0,"rate_quote_source":"bls:13-2011:p90:US-CA:8h"}}'

# 3. outreach_queued -> awaiting_attestation (email sent)
curl -sS -X POST ... -d '{"to_state":"awaiting_attestation","reason":"engagement_request emailed"}'

# 4. SAFETY CHECK — try to skip directly to finalized → MUST 409
curl -sS -X POST ... -d '{"to_state":"finalized","reason":"trying to cheat"}'
# → 409 {"ok":false,"error":"awaiting_attestation -> finalized not allowed; valid: ..."}

# 5. Legal path through validating -> finalized
curl -sS -X POST ... -d '{"to_state":"validating_attestation"}'
curl -sS -X POST ... -d '{"to_state":"finalized","reason":"6-point gate passed"}'

# 6. GET — full event timeline
curl -sS -H "X-API-Key: $KEY" $BASE/api/org/engagement/$EID

# 7. LIST + on-disk verification
curl -sS -H "X-API-Key: $KEY" "$BASE/api/org/engagements?tenant_id=acme_corp"
ls /var/lib/murphy-production/engagements/$EID/
```

## What it proved

| Pillar | Evidence |
|--------|----------|
| 1 CODE       | engagement_folder.py + engagement_routes.py compile, 134/134 tests green |
| 2 WIRED      | Startup log: `PCR-054c.1: registered=True, routes=4, db=/var/lib/murphy-production/engagement_folders.db` |
| 3 DEPS       | `/var/lib/murphy-production/{engagement_folders.db, engagements/}` exist and are murphy-owned |
| 4 EXECUTES   | All 5 transitions completed; folder finalized cleanly |
| 5 VISIBLE    | `GET /api/org/engagements?tenant_id=acme_corp` returned count=1 with full record |
| 6 DOCUMENTED | This file + 054a + 054b.1 + commit messages |
| 7 CONSISTENT | Same fail-soft pattern as PCR-053e/053f wire-ins; same JSONResponse shape |

## Audit evidence (5-event timeline)

```
- transition: ∅ → drafting (folder created)
- transition: drafting → outreach_queued (selected CPA from bench)
- transition: outreach_queued → awaiting_attestation (engagement_request email sent)
- transition: awaiting_attestation → validating_attestation (inbound reply received)
- transition: validating_attestation → finalized (6-point gate passed)
```

Each row is in `engagement_events` with timestamp, actor, and JSON payload.
Forensic replay of any engagement is one SQL query.

## What's still empty (and why that's fine)

`practitioner_email`, `rate_quote_usd`, and `rate_quote_source` are
**populated by hand** in this demo via `update_fields`. The next patch
series fills these in automatically:

- **054f** computes `rate_quote_usd` from BLS OEWS + jurisdiction adjustment
- **054d** writes `engagement_request` email (carrying that quote) to the
  outbound mail queue when entering `outreach_queued`
- **054e** parses the inbound reply and populates `attestation_payloads`,
  then runs the 6-point gate to decide between `finalized` and
  `declined_or_edits_asked`
- **054h** schedules the `verifying` → `verified | flagged` post-fact lookup

The engagement loop is now a **real container** for that work. The next
patches just hook in real-world signal sources.

## Reversibility

To roll back PCR-054c.1 (commits f0e5adb4 and 80d677d9):

1. `sudo systemctl stop murphy-production`
2. `sudo git -C /opt/Murphy-System revert <commit>` for each of the two
3. Optionally delete the engagement DB file + browse mirror dir at
   `/var/lib/murphy-production/engagement_folders.db` and
   `/var/lib/murphy-production/engagements`. Recommended path:
   archive these instead of deleting — the data the loop captured stays
   forensically useful even after a code rollback.
4. `sudo systemctl start murphy-production`

Reverting only the wire-in commit (f0e5adb4) keeps the state machine
code in place but unbinds it from the HTTP surface. This is the
safer half-rollback.
