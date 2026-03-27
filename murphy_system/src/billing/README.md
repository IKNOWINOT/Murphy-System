# Billing

The `billing` package manages subscription plans, usage metering, and
payment processing for the Murphy System.  It integrates with **PayPal**
and **Coinbase Commerce** for payment collection.

## Key Modules

| Module | Purpose |
|--------|---------|
| `api.py` | FastAPI router: plan management, webhook handlers, invoices |
| `currency.py` | Multi-currency conversion and rounding helpers |

## Payment Providers

| Provider | Use Case |
|----------|----------|
| PayPal | Recurring subscriptions, invoices |
| Coinbase Commerce | Crypto payments |

> **Note:** Stripe is not used. Do not add `STRIPE_API_KEY` to secrets.
