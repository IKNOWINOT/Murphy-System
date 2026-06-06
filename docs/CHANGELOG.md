
## 2026-06-02 — HITL Outbound Pipeline (R449-R462)

- **R449** /api/auth/permissions with R432-resolved permissions catalog
- **R450** /admin role-aware redirect (founder→/os, owner→/welcome)
- **R451** /os approve/reject URL fix (was 404)
- **R454** Cadence routes through HITL gate before SMTP (Terms §1B compliant)
- **R454b** Dual-write to murphy_mail.db so /os shows queue
- **R454c** Bidirectional bridge between hitl_jobs and outbound_email_queue
- **R455+R455b** Murphy self-grep upgraded: 1500-file cap, priority ordering, html/sql/sh scopes
- **R456** Lineage capture in _compose_outreach (template_id, input_fields, placeholders, source)
- **R457** /api/hitl/items/{id}/drill returns lineage detail
- **R458** Drill modal UI in /welcome (4 cards, highlighted input values)
- **R459** Backfilled lineage for 39 in-flight pre-R456 items via regex template match
- **R460+R460b** /os panels wired to /api/prospector/stats, /api/status, /api/hitl/items
- **R461** Real SMTP after approve via local Postfix:25 (DKIM-signed)
- **R462** Documentation patch — /docs/HITL_PIPELINE.md
