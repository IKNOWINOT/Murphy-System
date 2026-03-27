
# key_manager_bot — Secure key orchestration (Bot-standards compliant)

Purpose: Store API keys **encrypted** (envelope crypto), enforce **rate limits & quotas**, mint **ephemeral tokens**, support **revocation/quarantine/rotation**, and **sign requests**. Integrates with budgets/quotas, S(t), and observability.

## Register
- run: `src/clockwork/bots/key_manager_bot/key_manager_bot.ts::run`
- ping: `src/clockwork/bots/key_manager_bot/rollcall.ts::ping`

## Tasks
- `register_key` { bot_name, scope, key_id, key_value }
- `allocate_key` { bot_name }
- `policy_set` / `policy_get` { bot_name, scope, policy }
- `mint_ephemeral` { bot_name, scope, ttl_s }
- `use_key` { bot_name, scope, key_id } // returns ephemeral (no plaintext)
- `get_key` { key_id, allow_plaintext_get:false } // default sealed
- `revoke_key` | `quarantine_key` | `rotate_key` { key_id }
- `sign_request` { request:{method,url,headers,body} }
- `audit_report`

## Security
- Envelope crypto: **DEK** (AES-GCM) encrypted by **KEK** (derived from `env.KEK_SECRET`).
- No plaintext at rest; no secrets in logs; PII redaction at ingest.
- Rate limits via KV-backed leaky bucket; D1 rollups recommended.

## Env
- `KEK_SECRET` (derive KEK), `EPHEMERAL_SECRET` (mint tokens), `REQUEST_SIGN_SECRET` (sign requests).
