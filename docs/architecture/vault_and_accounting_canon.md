# Murphy Vault + Accounting — Canonical Architecture
**Locked: 2026-06-08 by founder directive (Corey Post)**
**Status: CANON. Supersedes all prior secret-storage and cost-attribution patterns.**

---

## Part 1 — Vault: Two Classes of Secrets

### `platform` — Murphy's own infrastructure
Owned by Inoni LLC. The engine itself. Tenants USE these according to their
plan tier; they never see the raw values.

Examples:
- `TOGETHER_API_KEY` — every LLM call goes through this by default
- `TWILIO_ACCOUNT_SID/AUTH_TOKEN/PHONE_NUMBER` — Murphy's voice engine
- `NOWPAYMENTS_API_KEY` — for charging Inoni's own subscribers
- `NOWPAYMENTS_IPN_SECRET` — webhook verification for above
- `SMTP_RELAY_AUTH`, `DKIM_PRIVATE_KEY`, future weather/geocoder/etc.

### `tenant_identity` — tenant's own override
Tenant uploads their own credential for a vendor. Murphy stores encrypted,
scoped to that tenant only. When Murphy does work FOR that tenant against
that vendor, it uses THEIR key instead of the platform default.

Examples:
- Tenant's own `NOWPAYMENTS_API_KEY` — their customers pay them direct
- Tenant's own `TWILIO_AUTH_TOKEN` — calls come from their business
- Tenant's own `STRIPE_KEY`, `SENDGRID_KEY`, `DOCUSIGN_TOKEN`, etc.

---

## Part 2 — Access Matrix

| Reader                                  | platform | tenant_identity (own) | tenant_identity (other) |
|-----------------------------------------|----------|-----------------------|-------------------------|
| Founder (Corey, as Inoni)               | ✅       | ❌ refuse              | ❌ refuse                |
| Inoni admin                             | ✅       | ❌ refuse              | ❌ refuse                |
| Murphy engine serving tenant X          | ✅       | ✅ (X's only)          | ❌ refuse                |
| Tenant agent (Acmecorp)                 | via pass-through, metered | ✅       | ❌ refuse                |

**Privacy floor:** No one decrypts another tenant's identity values.
Founder/admins can SEE name + description + audit log + last-used metadata
but NOT the raw value. Support path = rotate, not read. Matches industry
best practice (AWS Secrets Manager, GCP Secret Manager, HashiCorp Vault,
Stripe Connect restricted keys).

---

## Part 3 — Default vs Override Behavior

**Default:** Tenant ops use platform secrets.
- Acmecorp's Murphy SDR agent makes an LLM call → uses Murphy's
  `TOGETHER_API_KEY` (platform). Cost is metered against Acmecorp +
  the specific job_id.

**Override:** If tenant has uploaded their own credential for that vendor,
Murphy uses theirs for that tenant's ops.
- Acmecorp uploaded their own `NOWPAYMENTS_API_KEY`. Acmecorp's customer
  buys something → invoice is created with Acmecorp's NOWPayments key,
  money lands in Acmecorp's bank, **Murphy takes ZERO from that
  transaction.**
- Acmecorp uploaded their own `TWILIO_AUTH_TOKEN`. Outbound calls from
  Acmecorp's agent show Acmecorp's business number, billed to
  Acmecorp's Twilio account.

---

## Part 4 — Accounting: the Job is the Unit

**The accounting unit is the JOB, not the tenant.**

Each tenant has a `jobs` table. Every billable resource Murphy consumes
on a tenant's behalf is tagged with both `tenant_id` AND `job_id` at
the moment of consumption:

- LLM calls (`llm_cost_ledger.calls`)
- Voice minutes (future `voice_cost_ledger`)
- SMS sends (future `sms_cost_ledger`)
- Compute tasks (future `compute_ledger`)
- Storage growth (future `storage_ledger`)

Tenants query their own ledger by job and get a clean line-item bill
they can pass to their own customers.

**Subscription tier** ($99/$499/$1,499/mo) covers platform access and
some allotment of work. Per-job costs above allotment are passed
through with full attribution. Tenants mark up however they want.

**Why this matters:** This is what makes Murphy a sellable agent for
operators. Acmecorp's "AI dispatcher" works Job #1234 for Customer X
→ Acmecorp invoices Customer X with provable AI cost line-items. Not
"AI overhead $???" — actual `(model, tokens, $cost)` rows.

---

## Part 5 — Schema (canonical, post-PATCH-408 + PATCH-409)

### Vault (`murphy_vault.db.vault_secrets`)
```sql
-- Existing columns retained. Add:
ALTER TABLE vault_secrets ADD COLUMN class TEXT NOT NULL DEFAULT 'platform';
ALTER TABLE vault_secrets ADD COLUMN tenant_id TEXT;  -- NULL for platform

-- New uniqueness rule:
-- (name, class, tenant_id) is unique
-- platform rows have tenant_id=NULL
-- tenant_identity rows have tenant_id=<the tenant>

-- Enforce: cross-tenant SELECT refused at lookup-helper layer
-- (cannot enforce at pure-SQL UNIQUE level; helper checks caller's tenant_id)
```

### Cost ledger (`llm_cost_ledger.calls`)
```sql
-- Existing tenant_id retained. Add:
ALTER TABLE calls ADD COLUMN job_id TEXT;
CREATE INDEX idx_calls_tenant_job ON calls(tenant_id, job_id);

-- Same pattern for future voice/sms/compute ledgers when built.
```

### Job table — defer to existing
Murphy has 8 job/project/work tables already
(`hitl_jobs.project_budgets`, `engineering_firm.projects`,
`manifold.projects`, etc.). DON'T canonicalize yet. Just have the
ledger accept any string as `job_id`. Future PATCH-410 can promote
one of those tables to canonical and add UI.

---

## Part 6 — Lookup API (post-PATCH-408)

```python
# Platform-only secret (Murphy's own engine)
key = vault.get("TOGETHER_API_KEY")
# → reads class='platform' row, tenant_id IS NULL

# Tenant op: tries tenant override first, falls back to platform
key = vault.get("NOWPAYMENTS_API_KEY", tenant_id="acmecorp")
# → tries class='tenant_identity', tenant_id='acmecorp'
# → if not present, falls back to class='platform' for default
# → BUT: if a tenant op is doing something the tenant should be
#   identified for (their customer's payment), the caller can pass
#   require_tenant_override=True to refuse fallback

# Cross-tenant read attempt — REFUSED
key = vault.get("NOWPAYMENTS_API_KEY",
                tenant_id="other_tenant",
                caller_tenant="acmecorp")
# → raises CrossTenantReadRefused
```

---

## Part 7 — Ledger-write API (post-PATCH-409)

```python
# Every LLM-call site already passes (model, tokens, cost). Now also:
log_llm_call(model="llama-3.3-70b", tokens=4521, cost_usd=0.018,
             tenant_id="acmecorp", job_id="JOB-2026-001234")

# job_id may be NULL for platform-internal calls (Murphy's own sales
# outreach, watchdog, etc.) — those roll up as tenant_id='platform'.
```

---

## Part 8 — Tenant `/os` UI (PATCH-408.P3, deferred)

Tenant-facing UI for "Connect your own [Twilio / NOWPayments / Stripe /
SendGrid]" with the existing INONI-style approval flow. Tenants upload
their credential, Murphy stores it `class='tenant_identity'`,
`tenant_id=<them>`. Used automatically when Murphy does that tenant's
work.

Initially this can just be the founder uploading on their behalf via
`/api/vault/request` + approval. UI build is separate patch when
tenants exist who want it.

---

## Part 9 — Migration of 7 existing rows (in-place, atomic)

The 7 `tenant_password_*` entries are name-mangled because old schema
had no `tenant_id` column. Migration:
- Add new columns (default `class='platform'`, `tenant_id=NULL`)
- Walk all `tenant_password_<X>` rows
- Rewrite each to `name='tenant_password'`, `class='tenant_identity'`,
  `tenant_id='<X>'`
- Atomic in one transaction
- Snapshot the .db file beforehand
- Verify roundtrip post-migration

---

## Part 10 — Out of scope for this canon

- Job table canonicalization (Murphy has 8 — pick later)
- Tenant `/os` upload UI (PATCH-408.P3, separate)
- Customer-facing invoice PDF (PATCH-410, separate)
- Pass-through cost markup ratios (founder decision, separate)
- Multi-tier plan allotment caps (founder decision, separate)

---

## Authority

Locked by Corey Post 2026-06-08 in conversation with Murphy.
Any future change to this architecture requires founder sign-off
recorded in build_log + an updated revision of this document.
