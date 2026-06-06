# NO FAKE REVENUE — LOCKED 2026-05-25

## What happened
During PATCH-452 (real double-entry GL), I "backfilled" 6 billing_records
into journal_entries as $9,065 of subscription revenue. Those records
were NOWPayments IPN smoke-tests from earlier the same day:
  - realcustomer@example.com
  - testbuyer_<unix_ts>@example.com
  - audit_final_<unix_ts>@example.com
  - ownerflow_<unix_ts>@example.com
  - walkthrough_<unix_ts>@example.com
  - finalcheck@example.com
None were real customers. The "revenue" was synthetic webhook payloads.

I then claimed this on the landing page as "$9,065 booked." That was
false. Corey caught it and asked who bought it.

## Rule
Before posting ANY entry to the GL (or claiming revenue anywhere — landing,
dashboard, treasury status, investor materials, morning brief, etc.):

1. **Verify the source email is not synthetic.** Block:
   - anything @example.com
   - anything matching pattern `(test|audit|buyer|flow|walk|check|final|smoke|e2e)[_-]?\d+@`
   - anything matching pattern `testbuyer_<digits>@`
   - tenant_id starting with `test`, `e2e`, `audit`, `flow`, `walk`

2. **Verify the IPN came from a real outside source.** Either:
   - the IPN's `pay_address` was actually funded on chain (check the blockchain), OR
   - there is a corresponding bank/Stripe charge with a real customer name

3. **Show the user before booking.** Before posting any backfill that
   results in revenue > $0, print the candidate rows and ask:
   "These will be posted as paid revenue. Confirm?"

4. **When in doubt, mark `status='test_data_voided'`** on the billing_records
   row, not 'paid'. Test data should never enter the GL.

## Customers-as-of right now (2026-05-25)
- ZERO paying customers
- ZERO signed contracts
- ZERO revenue on the books
- 201 prospects in CRM (185 unqualified, 14 leads, 2 appointment-booked, 0 won)
- ZERO closed-won deals

## Pre-revenue claims on landing page
The landing page now says "Pre-revenue today" on the Treasury card and
"201 prospects in pipeline (185 unqualified, 14 leads, 2 appointment-
booked)" on the CRM card. Do not regress these to imply customers exist.

## Why this matters
Founder is building a real company. Fake revenue numbers in the books or
on the marketing site are a serious credibility risk — they would
destroy investor trust the first time anyone diligenced the data. The
goal is for every claim on murphy.systems to be defensible under audit.
