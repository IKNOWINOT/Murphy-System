# `src/billing` — Billing & Subscription

PayPal-first subscription and multi-currency billing API for the Murphy System.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The billing package provides the subscription and payment processing backbone for Murphy SaaS offerings. It exposes a FastAPI router for plan management, subscription lifecycle (create, upgrade, cancel), and webhook processing for payment provider events. Multi-currency support is handled by the currency module, which normalises amounts across supported fiat currencies. PayPal is the primary payment provider with the architecture open to additional connectors.

## Key Components

| Module | Purpose |
|--------|---------|
| `api.py` | FastAPI router for subscription CRUD and payment webhook ingestion |
| `currency.py` | Currency normalisation, conversion helpers, and supported-currency registry |

## Usage

```python
from billing.api import create_billing_router

app.include_router(create_billing_router(), prefix="/api/billing")
```

## Configuration

| Variable | Description |
|----------|-------------|
| `PAYPAL_CLIENT_ID` | PayPal application client ID |
| `PAYPAL_CLIENT_SECRET` | PayPal application client secret |
| `PAYPAL_ENVIRONMENT` | `sandbox` or `live` |

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*
