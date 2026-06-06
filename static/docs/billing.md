# Billing & Commerce (Pillar G)

Murphy accepts crypto payments via NOWPayments. Plans, invoices, and IPN events are tracked in `billing.db`.

## Plans (`nowpayments_plans` table)
| Tier     | Monthly | Annual | Users | Automations |
|----------|---------|--------|-------|-------------|
| Free     | $0      | $0     | 1     | 0           |
| Pilot    | $99     | $79    | 1     | 3           |
| Team     | TBD     | TBD    | 5+    | TBD         |
| Business | TBD     | TBD    | 25+   | TBD         |

Live source of truth: `GET /api/billing/plans`.

## Checkout
- **Endpoint:** `POST /api/payments/nowpayments/checkout`
- **Body:** `{account_id, tier, interval, email?}`
- **Returns:** `{ok, checkout_url, payment_id, amount_usd, tier, interval, provider:"nowpayments", method:"crypto"}`
- **Public UI:** `/pricing` → `startCheckout(tier)` → invoice → hosted NOWPayments checkout

## Webhook (IPN)
- **Endpoint:** `POST /api/payments/nowpayments/webhook`
- **Signed** with `NOWPAYMENTS_IPN_SECRET`
- **Events** logged to `ipn_events` table; tenant subscription state updated on `finished`

## Database tables
- `nowpayments_plans` — plan catalog
- `billing_records` — per-tenant ledger
- `ipn_events` — raw IPN payloads
- `tenant_subscriptions` — active subscription state
- `tenant_addons` — optional add-ons (e.g. `system_influence`)

## Env vars
- `NOWPAYMENTS_API_KEY` — REST API authentication
- `NOWPAYMENTS_IPN_SECRET` — webhook signature validation

## Reporting
- `GET /api/billing/revenue` — live revenue figure
- `GET /api/billing/revenue/history` — historical
- `GET /api/billing/token-ledger` — token-level accounting

## Status (2026-06-04)
End-to-end buy flow verified working. First paying tenant pending.

Last updated: 2026-06-04
