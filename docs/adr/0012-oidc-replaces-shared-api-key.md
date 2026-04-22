# ADR-0012: Wire OIDC into auth_middleware; deprecate the shared API key

* **Status:** Accepted — **Release N landed 2026-04-22**
* **Date:** 2026-04-22
* **Roadmap row closed:** Item 3
* **Trust-boundary change:** YES — see `docs/SECURITY_THREAT_MODEL.md` §2.1
* **Implementation spans:** `src/auth_middleware.py`, `src/oidc_verifier.py`,
  `src/oauth_oidc_provider.py`, `src/runtime/app.py`,
  `docs/SECURITY_THREAT_MODEL.md`, `docs/DEPLOYMENT_GUIDE.md`

## Context

`src/oauth_oidc_provider.py` has existed for some time but is *not wired* into
`src/auth_middleware.py`. Production today still authenticates every request
with a single shared API key (`MURPHY_API_KEY`). The threat model already
flags this as the system's primary security weakness:

> **§2.1 Trust boundary: caller → API.** A leaked `MURPHY_API_KEY`
> grants full tenant impersonation across every request type. Rotation is a
> tenant-wide outage. There is no per-user audit attribution.

Continuing to ship without per-user identity is the largest single capability
gap blocking an A grade in *Security* on the Class S rubric.

## Decision

`auth_middleware.py` is rewired so that the **OIDC ID token** (or, equivalently,
an opaque session cookie minted from one) is the **primary** trust signal, and
the shared API key becomes a **deprecated, narrow-scope fallback** during a
defined transition period.

### Authentication order (after this lands)

1. `Authorization: Bearer <jwt>` — verified against the OIDC provider's JWKS
   (cached, ETag-aware, refresh on `kid` miss). The JWT's `sub` claim is the
   user identity; `tenant` claim (custom, configurable) is the tenant. Claims
   are validated for `iss`, `aud`, `exp`, `nbf`, and `iat` skew.
2. **Session cookie** (`murphy_sid`) — server-side session keyed by the OIDC
   identity, used by browser flows.
3. `X-API-Key` (deprecated) — accepted only if `MURPHY_ALLOW_API_KEY=true`
   *and* the request matches the legacy machine-to-machine route allowlist
   (`/api/v1/internal/*`). Every accepted API-key request emits a
   `DeprecationWarning`-flavoured log line plus a Prometheus counter
   `murphy_api_key_requests_total{route="..."}` so we can see usage drop to
   zero before flipping the default to `false`.

### Provider configuration

* OIDC provider is configured via four env vars only: `MURPHY_OIDC_ISSUER`,
  `MURPHY_OIDC_CLIENT_ID`, `MURPHY_OIDC_CLIENT_SECRET`, `MURPHY_OIDC_REDIRECT_URI`.
  No additional knobs in this PR — every extra setting is a footgun
  (CLAUDE.md §2).
* Discovery is automatic via `/.well-known/openid-configuration`.
* JWKS is cached for 1h with a 5m grace window; on `kid` miss we refresh
  immediately and retry once. Failure to refresh after one retry is a 503,
  not a silent fallback to API key — automations must not silently degrade.

### Migration plan (release-train, not single PR)

| Release | Behaviour |
|---|---|
| N (this ADR + wiring PR) | OIDC primary, API key fallback ON by default |
| N+1 | API key fallback OFF by default; ops can re-enable per-route |
| N+2 | API key code path deleted; env var removed; threat model updated |

## Consequences

* `docs/SECURITY_THREAT_MODEL.md` §2.1 is rewritten in the same PR that lands
  the wiring. The new section names the JWT validation path as the trust
  boundary and names the residual risks (provider compromise, JWKS spoofing
  if TLS validation is disabled, replay within token TTL).
* Every audit-trail row gains a non-null `actor_user_sub` column when the
  caller authenticated via OIDC; rows from the API-key path get
  `actor_user_sub = NULL` and `actor_kind = 'api_key'` so we can see the
  remaining surface in the audit DB.
* `docs/DEPLOYMENT_GUIDE.md` gains an "OIDC quickstart" with worked examples
  for Auth0, Keycloak, Google, and Okta — those four cover ~95% of expected
  deployers.
* The legacy SDK (`murphy_auth.js`, `murphy_overlay.js`) gains an OIDC
  Authorization-Code-with-PKCE path; the existing API-key path is kept and
  warns to console.

## Rejected alternatives

* **Mint our own JWTs (custom IdP).** Rejected — running a production IdP is a
  full subsystem and out of scope; OIDC delegation is the right call.
* **mTLS instead of OIDC.** Rejected for the user-facing surface; mTLS is the
  right answer for service-to-service and is already used internally for the
  HITL service. Browser-initiated flows need OIDC.
* **SAML.** Rejected — modern web stacks have walked away from it; we'd rather
  ship one open standard well than two badly.
* **Skip the API-key fallback (clean break).** Rejected — every existing
  integration would break on the upgrade. The two-release deprecation window
  is cheap insurance and forces visible measurement of remaining usage.

## Verification

* `tests/auth/test_oidc_middleware.py` (new) — 18 cases covering JWT happy
  path, expired token, wrong issuer, wrong audience, JWKS refresh on `kid`
  miss, API-key fallback when allowed, API-key rejection when disabled,
  session-cookie path.
* CI runs against a `mock-oauth2-server` container to exercise real HTTP
  discovery.
* The threat-model update is reviewed in the same PR by a security owner
  before merge — a checkbox in the PR template enforces this for
  trust-boundary changes (added in this PR).
