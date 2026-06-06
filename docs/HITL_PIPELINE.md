# HITL Outbound Email Pipeline

**Status:** Live as of 2026-06-02 (R449-R461).

## Architecture

```
Cadence (daily 09:00 PT)
    │
    ▼
lead_prospector.py
    │  _source_usaspending / _source_hn_hiring / _source_yc / _source_remoteok
    │
    ▼
_compose_outreach(lead, touch_number)
    │  Picks an OPENER_TEMPLATE, fills placeholders, captures LINEAGE
    │
    ▼
_r454_queue_outbound_for_hitl()
    │  Dual-writes to BOTH:
    │    - hitl_jobs.db  (HITL contract gate, R431)
    │    - murphy_mail.db (outbound_email_queue, /os surface)
    │
    ▼
Founder reviews at /welcome OR /os
    │  Both surfaces show the SAME items (queue_id == hitl_job_id)
    │  Drill-down modal shows: source doc → input fields → template → highlighted body
    │
    ▼
Approve / Reject
    │  R454c bidirectional bridge mirrors status across both DBs
    │
    ▼  (if approve)
R461 Postfix:25 SMTP send
    │  DKIM-signed via opendkim
    │  Delivered to recipient
```

## Surfaces

| URL              | Purpose                                    | Auth          |
|------------------|--------------------------------------------|---------------|
| `/welcome`       | Founder onboarding wizard + HITL inbox     | API key (URL or localStorage) |
| `/os`            | Operating system dashboard + outbound queue| API key (URL or localStorage) |
| `/admin`         | Role-aware redirect to correct surface     | OIDC or API key |
| `/api/hitl/items`| List founder's pending HITL items          | API key |
| `/api/hitl/items/{id}/drill` | Lineage drill-down for one item | API key |
| `/api/mail/outbound/queue` | Same items, mail-DB view         | API key |
| `/api/mail/outbound/{id}/approve` | Approve + fire SMTP         | API key |
| `/api/mail/outbound/{id}/reject`  | Reject (no send)            | API key |

## Lineage shape

Each composed message carries a `lineage` object stored in
`hitl_jobs.submitted_data.lineage` (JSON):

```python
{
  "version": "r456.1",
  "template_id": "opener_2",
  "template_raw": "<full template string>",
  "input_fields": {"first_name": "Andres", "company": "MovingLake", ...},
  "placeholders_in_body": [
    {"field": "first_name", "value": "Andres", "start": 54, "end": 60,
     "in": "body"}, ...
  ],
  "source": {
    "system": "hn_hiring",
    "lead_id": "hn_123",
    "source_url": "https://news.ycombinator.com/item?id=123",
    "raw_snippet": "...",
    "fetched_at": "..."
  },
  "lead_raw": {"name": "...", "email": "...", "company": "...", "title": "..."}
}
```

Pre-R456 items are backfilled by `R459` which re-matches templates via regex.

## Verified end-to-end

1. ✅ Real SMTP delivery: `to=<cpost@murphy.systems>... status=sent (250 ... Saved)`
2. ✅ DKIM-signed: `DKIM-Signature field added (s=mail, d=murphy.systems)`
3. ✅ Drill-down: source → input → template → highlighted body works for all 49 items
4. ✅ Approve in /welcome mirrors to /os queue (R454c)
5. ✅ Approve in /os fires real SMTP (R461)

## Recovery & debugging

- Postfix log: `/var/log/mail.log`
- HITL DB: `/var/lib/murphy-production/hitl_jobs.db`
- Mail queue DB: `/var/lib/murphy-production/murphy_mail.db`
- Live counts: `curl -H "X-API-Key: $KEY" https://murphy.systems/api/mail/outbound/stats`

## Patches involved

R431, R432, R449-R461 — see `docs/CHANGELOG.md` for individual patch notes.
