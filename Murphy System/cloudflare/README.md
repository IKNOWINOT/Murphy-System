# Murphy System — Cloudflare Edge Gateway

This directory contains the Cloudflare Workers edge gateway for the Murphy System.

## Architecture

| Component              | Service              | Binding            |
|------------------------|----------------------|--------------------|
| Database               | Cloudflare D1        | `DB`               |
| Object Storage         | Cloudflare R2        | `AGENT_ARTIFACTS`  |
| Approval Queue         | Cloudflare Queues    | `APPROVAL_QUEUE`   |
| Negotiation Sessions   | Durable Objects      | `NEGOTIATION_SESSION` |
| Shadow Agent State     | Durable Objects      | `SHADOW_AGENT_STATE`  |

## Quick Start (Local Setup)

### Prerequisites

- Node.js 18+
- A Cloudflare account
- Stripe account (for marketplace features)

### One-Command Setup

```bash
cd "Murphy System/cloudflare"
npm install
npx wrangler login          # authenticate with Cloudflare
bash setup.sh               # creates all resources + runs migrations
```

The `setup.sh` script will:
1. Create the D1 database (`murphy-system-db`) and update `wrangler.toml`
2. Create the R2 bucket (`murphy-agent-artifacts`)
3. Create the Queue (`murphy-hitl-approvals`)
4. **Run D1 migrations** (creates all 12 tables + 9 indexes)
5. Prompt you to store each secret via `wrangler secret put`

### Manual Steps (if you prefer)

```bash
# 1. Create resources
npx wrangler d1 create murphy-system-db
# → Copy the database_id into wrangler.toml

npx wrangler r2 bucket create murphy-agent-artifacts
npx wrangler queues create murphy-hitl-approvals

# 2. Run migrations
npx wrangler d1 execute murphy-system-db --file=migrations/0001_initial.sql --remote

# 3. Store secrets (one at a time)
npx wrangler secret put JWT_SECRET
npx wrangler secret put STRIPE_SECRET_KEY
npx wrangler secret put STRIPE_PUBLISHABLE_KEY
npx wrangler secret put STRIPE_WEBHOOK_SECRET
npx wrangler secret put SERVICE_TOKEN
npx wrangler secret put FOUNDER_ASSIGNMENT_SECRET
npx wrangler secret put LLM_PROVIDER_KEYS_JSON

# 4. Deploy
npm run deploy
```

## CI/CD Deployment (GitHub Actions)

For automated deployments, use the GitHub Actions workflow at `.github/workflows/cloudflare-deploy.yml`.

### Required GitHub Secrets

Go to **repo → Settings → Secrets and variables → Actions** and add:

| Secret                   | Description                                      |
|--------------------------|--------------------------------------------------|
| `CLOUDFLARE_API_TOKEN`   | Cloudflare API token with Workers/D1/R2/Queue permissions |
| `CLOUDFLARE_ACCOUNT_ID`  | Your Cloudflare account ID                       |
| `D1_DATABASE_ID`         | The D1 database UUID (from `wrangler d1 list`)   |
| `CF_JWT_SECRET`          | JWT signing secret                               |
| `CF_STRIPE_SECRET_KEY`   | Stripe secret key                                |
| `CF_STRIPE_PUBLISHABLE_KEY` | Stripe publishable key                        |
| `CF_STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret                  |
| `CF_SERVICE_TOKEN`       | Service-to-service auth token                    |
| `CF_FOUNDER_SECRET`      | Founder role assignment secret                   |
| `CF_LLM_KEYS_JSON`      | *(Optional)* Platform-default LLM keys JSON      |

### Trigger Options

- **Auto**: Merges to `main` touching `Murphy System/cloudflare/**`
- **Manual**: Go to Actions → "Cloudflare Edge Deploy" → Run workflow
  - Check "Run D1 migrations" to run migrations
  - Check "Deploy worker" to deploy the worker

## Secrets Reference

All secrets are stored via `wrangler secret put` — **never** in source code:

| Secret                     | Format                          |
|----------------------------|---------------------------------|
| `JWT_SECRET`               | Any strong random string        |
| `STRIPE_SECRET_KEY`        | `sk_test_...` or `sk_live_...`  |
| `STRIPE_PUBLISHABLE_KEY`   | `pk_test_...` or `pk_live_...`  |
| `STRIPE_WEBHOOK_SECRET`    | `whsec_...`                     |
| `SERVICE_TOKEN`            | Any strong random string        |
| `FOUNDER_ASSIGNMENT_SECRET`| Any strong random string        |
| `LLM_PROVIDER_KEYS_JSON`  | `{}` or `{"openai":"sk-..."}` etc. |

## API Routes

| Method | Path                         | Auth     | Description                    |
|--------|------------------------------|----------|--------------------------------|
| GET    | `/api/health`                | Public   | Health check                   |
| GET    | `/api/providers`             | Public   | List supported LLM providers   |
| POST   | `/api/marketplace/webhook`   | Stripe   | Stripe webhook                 |
| GET    | `/api/context`               | JWT      | Current context                |
| PUT    | `/api/context`               | JWT      | Switch context                 |
| GET    | `/api/memberships`           | JWT      | List memberships               |
| POST   | `/api/memberships/attach`    | JWT      | Attach to org                  |
| POST   | `/api/memberships/detach`    | JWT      | Detach from org                |
| GET    | `/api/shadow-agents`         | JWT      | List shadow agents             |
| POST   | `/api/shadow-agents`         | JWT      | Create shadow agent            |
| GET    | `/api/llm-keys`              | JWT      | List LLM keys                  |
| PUT    | `/api/llm-keys`              | JWT      | Store LLM key                  |
| DELETE | `/api/llm-keys?provider=X`   | JWT      | Remove LLM key                 |
| POST   | `/api/marketplace/onboard`   | JWT      | Start Stripe onboarding        |
| POST   | `/api/marketplace/list`      | JWT      | List agent on marketplace      |
| GET    | `/api/marketplace/search`    | JWT      | Search marketplace             |
| POST   | `/api/marketplace/license`   | JWT      | Request license                |
| POST   | `/api/marketplace/pay`       | JWT      | Create payment intent          |
| POST   | `/api/marketplace/refund`    | JWT      | Refund license                 |
| GET    | `/api/marketplace/dashboard` | JWT      | Seller dashboard               |
| GET    | `/api/decisions`             | JWT      | List pending decisions         |
| POST   | `/api/decisions/:id/approve` | JWT      | Approve decision               |
| POST   | `/api/decisions/:id/reject`  | JWT      | Reject decision                |

## D1 Schema

12 tables created by `migrations/0001_initial.sql`:
- `users`, `organizations`, `memberships`
- `shadow_agents`, `agent_org_assignments`
- `user_llm_keys`, `provider_acknowledgements`
- `negotiations`
- `marketplace_listings`, `marketplace_licenses`
- `pending_decisions`, `audit_log`
