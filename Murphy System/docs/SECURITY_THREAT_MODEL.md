# Murphy System — Security Threat Model

> **Status:** Living document.  Updated alongside any
> trust-boundary-changing PR (per `CONTRIBUTING.md`).  Last
> trust-boundary change: ADR-0012 Release N (this document's §2.1).

This document enumerates the trust boundaries Murphy crosses and the
controls that defend each one.  It is the security-owner's reference
for code review of trust-boundary-changing PRs and for deployers
planning a production roll-out.

---

## 1. Scope

Murphy is a multi-tenant orchestration system that exposes:

* an HTTP API (`/api/*`) — the primary surface,
* a server-rendered UI (`/ui/*`) — Jinja2 per ADR-0013,
* a small set of internal machine-to-machine endpoints
  (`/api/v1/internal/*`) used by background workers and the
  blockchain audit-trail signer.

Out of scope (covered by other documents): physical security of the
host, hypervisor escape risks, supply-chain attacks against pinned
upstream dependencies (see `pip-audit` / GitHub Advisory Database
gating in CI).

---

## 2. Trust boundaries

### 2.1 Caller → API (REWRITTEN by ADR-0012 Release N)

**Before Release N.**  Every request to `/api/*` was authenticated by
a single shared API key (`MURPHY_API_KEY`).  A leaked key granted
full tenant impersonation across every request type.  Rotation was a
tenant-wide outage.  There was no per-user audit attribution.

**After Release N (this document's current state).**  The primary
trust signal is an **OIDC ID token** (or an opaque session cookie
minted from one).  The shared API key remains accepted *only* on a
narrow legacy machine-to-machine route allowlist
(`/api/v1/internal/*` by default), and only while
`MURPHY_ALLOW_API_KEY=true` (the Release-N default; flips to `false`
in Release N+1; the code path is removed in N+2).

#### Authentication order (enforced by `OIDCAuthMiddleware`)

1. **`Authorization: Bearer <jwt>`** — verified against the OIDC
   provider's JWKS.  The verifier is `src/oidc_verifier.py`.  Claims
   validated:
   * `iss` — must equal `MURPHY_OIDC_ISSUER`,
   * `aud` — must contain `MURPHY_OIDC_CLIENT_ID`,
   * `exp`, `nbf`, `iat` — with a 30-second leeway,
   * `sub` — required; becomes `request.state.actor_user_sub`,
   * `tenant` claim (configurable via `MURPHY_OIDC_TENANT_CLAIM`) —
     becomes `request.state.actor_tenant`.
2. **`Cookie: murphy_sid=<sid>`** — server-side session keyed by the
   OIDC identity, used by browser flows.
3. **`X-API-Key`** *(deprecated)* — accepted only when both
   `MURPHY_ALLOW_API_KEY=true` and the request matches
   `MURPHY_API_KEY_ROUTES` (default `/api/v1/internal/*`).  Every
   acceptance:
   * emits a `WARNING`-level "DEPRECATED" log line, and
   * increments the
     `murphy_api_key_requests_total{route="..."}` Prometheus-shaped
     counter exposed by
     `auth_middleware.api_key_deprecation_counter`.

#### Failure-mode contract

| Condition                                         | Status | Body code                  |
|---------------------------------------------------|:------:|----------------------------|
| Valid bearer JWT                                  | 200    | (route-specific)           |
| Token expired / wrong issuer / wrong audience     | 401    | `OIDC_TOKEN_INVALID`       |
| Unknown `kid` after one forced JWKS refresh       | 401    | `OIDC_TOKEN_INVALID`       |
| Token uses HS256 / other unsupported algorithm    | 401    | `OIDC_TOKEN_INVALID`       |
| OIDC discovery / JWKS fetch fails entirely        | **503**| `OIDC_DISCOVERY_FAILED`    |
| API key on a non-allowlisted route                | 401    | `API_KEY_ROUTE_DENIED`     |
| API key when `MURPHY_ALLOW_API_KEY=false`         | 401    | `API_KEY_DEPRECATED`       |
| Wrong API key value (constant-time compare)       | 401    | `AUTH_REQUIRED`            |
| No credentials, auth enforced                     | 401    | `AUTH_REQUIRED`            |

The 503-on-discovery-failure rule is load-bearing: the ADR forbids
silent fallback from a transport failure to the API-key path,
because automations would otherwise silently downgrade their
authentication every time the IdP hiccupped.

#### Residual risks (we accept these knowingly)

| # | Risk                                                                 | Mitigation                                                                                  |
|---|----------------------------------------------------------------------|---------------------------------------------------------------------------------------------|
| 1 | Provider compromise (the IdP itself signs malicious tokens)          | Out of scope.  Choose a reputable IdP; the deployment guide names Auth0 / Keycloak / Google / Okta as the four we test against. |
| 2 | JWKS spoofing if TLS validation is disabled                          | The default HTTP client uses `urllib.request` against the system trust store.  Operators MUST NOT inject a TLS-disabled client. |
| 3 | Replay within token TTL                                              | Tokens are accepted within `exp` ± 30 s leeway; the IdP issues short-lived tokens.  Refresh-token rotation is the IdP's responsibility. |
| 4 | Stale JWKS within the 5-minute grace window after refresh failure    | Bounded by `JWKS_GRACE_SECONDS = 300`.  A refresh failure beyond grace returns 503.         |
| 5 | API-key fallback path remains until Release N+2                      | Counted, logged, and route-restricted.  Release N+1 disables by default; N+2 removes code.  |

### 2.2 API → durable storage

Unchanged by ADR-0012.  See `docs/PERSISTENCE.md` (forthcoming) for
the durable-state contract.

### 2.3 API → external services (LLM providers, blockchain signer, etc.)

Unchanged by ADR-0012.  Each external service has its own credential
secret stored in the deployment's secret manager (per
`docs/DEPLOYMENT_GUIDE.md` §"Security Checklist").

### 2.4 Worker → API (loopback)

Workers authenticate using the API-key fallback on the
`/api/v1/internal/*` allowlist.  Release N+1 will require workers to
mint short-lived OIDC tokens via client-credentials grant; the
migration plan is tracked alongside ADR-0012.

---

## 3. Audit attribution

After Release N every audit-trail row gains:

* `actor_user_sub`  — the OIDC `sub` claim, or `NULL` when the
  caller used the API-key path.
* `actor_kind`      — one of `oidc`, `session`, `api_key`,
  `anonymous`.
* `actor_tenant`    — the configured tenant claim, when present.

The middleware stamps these on `request.state` so every downstream
audit-emitting code path can read them without re-parsing the
request.

---

## 4. Change-management gate

Per `CONTRIBUTING.md`, a PR that changes any of the boundaries above
MUST:

1. Update this document in the same PR.
2. Be reviewed by an owner from the security CODEOWNERS list.
3. Add or update an ADR if the boundary's *contract* (not just an
   implementation detail) changes.
