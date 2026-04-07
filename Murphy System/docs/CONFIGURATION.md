# Murphy System — Configuration Reference

## Rate Limiting Backend (Gap 5)

By default, both `SubscriptionManager` and `ForgeRateLimiter` use **in-memory
dictionaries** to track daily build counters.  In a single-process deployment
this works perfectly.  However, when running multiple Gunicorn workers (or
multiple Railway / Render instances), each worker maintains its own memory
space.  A visitor who hits different workers gets a fresh counter each time,
effectively multiplying their rate limit by the worker count.

### Recommended: Redis backend for production multi-worker deployments

Set the following environment variables before starting the server:

```env
# Enable the Redis rate-limit backend
MURPHY_RATE_LIMIT_BACKEND=redis

# Standard Redis connection URL (redis://[:password@]host[:port][/db])
REDIS_URL=redis://localhost:6379/0
```

When `MURPHY_RATE_LIMIT_BACKEND=redis` and `REDIS_URL` is set:

- `SubscriptionManager.record_anon_usage()` stores counters in Redis under the
  key `murphy:anon:<fingerprint>:<YYYY-MM-DD>` using `INCR` + `EXPIREAT`
  (expires at next midnight UTC).
- `SubscriptionManager.record_usage()` stores counters under
  `murphy:usage:<account_id>:<YYYY-MM-DD>`.
- `ForgeRateLimiter.check_and_record()` stores daily counters under
  `murphy:forge:<key>:<YYYY-MM-DD>`.

All keys expire automatically at midnight UTC so no manual cleanup is needed.

### Graceful degradation

If Redis is unavailable at startup, or if the connection drops at runtime, both
modules **fall back to in-memory tracking automatically** and emit a warning:

```
WARNING  Rate limiting running in per-worker mode — limits not shared across workers.
```

The application continues to serve requests; the only consequence is that rate
limits are enforced per-worker instead of globally.

### In-memory mode (default, development)

```env
# Explicit (also the default when MURPHY_RATE_LIMIT_BACKEND is unset)
MURPHY_RATE_LIMIT_BACKEND=memory
```

In-memory mode is fine for local development and single-worker deployments.

---

## Daily Build Limits

| Visitor type   | Builds / day | Tracked by              |
|----------------|-------------|-------------------------|
| Anonymous      | 5           | IP + User-Agent hash    |
| Free account   | 10          | `account_id`            |
| Solo / paid    | 100+        | `account_id`            |
| Enterprise     | Unlimited   | n/a                     |

Daily counters reset at **midnight UTC**.  Every rate-limit response includes
a `reset_at` field (ISO-8601 timestamp) so the frontend can display a countdown.

---

## Forge Rate Limiter — Hourly Buckets

Hourly limits use an **in-process token-bucket** algorithm.  Even when the
daily counter is stored in Redis, the hourly bucket remains in-memory (per
worker) because hourly smoothing is a best-effort, not a hard guarantee.

---

## Auth — Register Free Tier

`POST /api/auth/register-free` accepts `{ email, password }` and creates a
free-tier subscription record.  The response includes:

```json
{
  "success": true,
  "account_id": "<uuid>",
  "token": "<session-token>",
  "tier": "free",
  "daily_limit": 10
}
```

The `token` should be stored in `localStorage` as `murphy_session_token` and
sent in subsequent requests as `Authorization: Bearer <token>` or via the
`X-User-ID` header so the server can route to per-account tracking instead of
anonymous fingerprint tracking.

---

*Last updated: production commissioning audit — Wave 12*
