# leadgen_crm_bot — Clockwork1 (TypeScript) — bots-only (v1.2 consolidated)

Production **Lead Generation + CRM** agent aligned to the Clockwork1 Bot Standards canvas.
This package consolidates all features discussed:
- Lead ingestion (forms/webhooks/CSV), **enrichment**, **scoring**, dedupe
- **Lead discovery (scrubbing)** from allowed sources (URL/HTML/text) via adapters that must respect robots.txt & site TOS
- **Mailbox sync** (auto-unsubscribe/stop, bounce handling, positive reply harvesting)
- **Verification & hygiene** (MX/SMTP via adapter; role/disposable filters; unsubscribed suppression)
- Sequencing & **campaign launch** (email/SMS/social) with throttling (dry-run or execute via adapters)
- **Asset generation** (emails, landing page spec+HTML, ads) using `model_proxy` JSON mode
- Built-in **CRM** (D1) — contacts, companies, deals, activities, campaigns, sequences, unsubscribes, suppression events, lists, list_members, mailbox_state
- **Compliance**: suppression enforced before sends; opt-in/opt-out; audit trail
- Bot Standards: `bot_base` (quota/budget/Stability S(t)), **Golden Paths** reuse/record, **observability/ledger**

This folder is designed to live **only** at:
`clockwork1/src/clockwork/bots/leadgen_crm_bot/*`

## External adapters (wired by Codex)
- ../../orchestration/model_proxy
- ../../orchestration/experience/golden_paths
- ../../orchestration/{stability, quota_mw, budget_governor}
- ../../observability/emit
- ../../integrations/email_adapter         (sendEmail)
- ../../integrations/sms_adapter           (sendSms)
- ../../integrations/social_adapter        (send)
- ../../integrations/tracking_adapter      (createTrackingLinks, pixel)
- ../../integrations/enrichment_adapter    (enrich)
- ../../integrations/mailbox_adapter       (fetchNew)
- ../../integrations/verification_adapter  (verify)
- ../../io/web_fetch, ../../io/html_to_text (for lawful fetching + text extraction)

## Actions (params.action)
- `discover` — find leads from sources (URL/HTML/text), verify+score, upsert
- `ingest` — upsert leads (array/CSV), enrich+score, dedupe
- `verify_emails` — batch verify
- `clean_list` — hygiene filters (role/disposable/unsubscribed)
- `mailbox_sync` — unsubscribe/stop, bounces, positive replies → CRM activities; stores mailbox cursor
- `opt_in` / `opt_out` — consent management (audited)
- `upsert_contact`, `upsert_company`, `create_deal`, `log_activity`
- `score` — compute lead scores/grades
- `generate_assets` — email templates, landing page spec+HTML, ads (JSON-mode)
- `enroll` — enroll leads in a multi-step sequence (dry-run / execute via adapters)
- `launch_campaign` — single-step outbound (dry-run / execute)
- `search` — CRM search
- `unsubscribe` — one-off unsubscribe
- `report` — totals

## SLOs & KaiaMix
- p95 ≤ 3.0–3.2s on mini profile; avg cost ≤ $0.018/action
- KaiaMix heuristic: Veritas 0.60 • Vallon 0.25 • Kiren 0.15

## Compliance
- You are responsible for lawful sources, consent, and honoring CAN-SPAM/CASL/GDPR/CCPA
- Adapters must respect robots.txt and site TOS
