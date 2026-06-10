# PCR-091 — Solute Safety Zones (QUEUED — founder-gated)

## Sovereign rule (locked 2026-06-10)
> The platform founder (Corey Post, Inoni LLC) has god mode.
> No other actor — tenants, tenant admins, Inoni hires, Murphy,
> any agent, any automation — can enter a solute zone, ever,
> regardless of role, plan tier, HITL approval, or instruction.

## v1 design (founder-approved direction, not yet built)
- Sovereign: Corey only (single key, no second sovereign)
- Substrate: application-kernel wrapper (Option C)
- Proof of founder presence:
    backend agents → P1 HMAC X-Founder-Signature
    UI initiated   → P3 SMS confirm to +17164003440
- Failure mode: refuse all non-founder mutations if kernel fails to load
- Recovery: cold paper manifest (no live second key)
- Hires: operational access only, never solute

## v1 CRITICAL invariants
1. Never modify /etc/murphy-production/solute_zones.json without founder sig
2. Never modify auth_middleware.py / whitelist without founder sig
3. Never delete user-owned data without founder sig OR tenant-owner sig
4. Never initiate outbound funds movement without founder sig

## v1.1 HIGH invariants (after a week clean)
5. Never write outside /var/lib/murphy-production /opt/Murphy-System /etc/murphy-production
6. Never POST/PUT/DELETE to non-allowlisted external domains
7. Never disable HITL, compliance gates, or solute kernel
8. Never modify regulated content (formalizes L161)

## Ship plan (when founder greenlights)
- v1.0  kernel module + 4 CRITICAL invariants + HMAC verify + fail-closed
- v1.0a live demo — synthetic non-founder refused, founder sig allowed
- v1.0b CI grep + git hook — fail any mutation site missing kernel.check()
- v1.1  extend to HIGH invariants
- v1.2  surface in /os signals panel (block count, recent refusals)

## Author-and-stage work allowed pre-greenlight
- Draft solute_kernel.py in workspace (not deployed)
- Draft solute_zones.json schema (not placed in /etc)
- Draft HMAC verify logic (not wired)
- Migration plan for existing safety modules (extend not duplicate)
- Test harness — synthetic actors, expected verdicts

## What is FORBIDDEN to do without founder greenlight
- Generate or place /etc/murphy-production/founder.key
- Touch /etc/murphy-production/
- Modify auth_middleware.py
- Create or wire solute_kernel.py into the live request path


---

## DEFERRAL — locked 2026-06-10

Founder explicit: "I'm afraid of getting locked out of my own system
so let's defer for now."

This applies to BOTH:
  - OS-FIX-3 (founder browser session-cookie path)
  - PCR-091 v1 (solute kernel + founder-key infrastructure)

Reason: any change to who-is-founder or how-founder-proves-identity
carries real lockout risk. The founder is the sovereign; if the
sovereign cannot reach their own system, the system is broken
regardless of how secure it is.

DO NOT RESUME without explicit founder go-ahead. Specifically:
  - Do not modify auth_middleware.py for session/founder paths
  - Do not generate or place /etc/murphy-production/founder.key
  - Do not create solute_kernel.py in the live tree
  - Do not wire HMAC verification into any request path
  - Do not propose these as "next steps" — they are gated

What stays acceptable WITHOUT founder go-ahead:
  - Continuing to whitelist new read-only public-safe endpoints
    (the OS-FIX-1/2 pattern), one at a time, with browser verify
  - Editing static UI to surface data we already have
  - Author-and-stage drafts in workspace ONLY (no /opt/, no /etc/)

When founder returns to this, the natural starting move is a
LOCKOUT REHEARSAL on staging:
  1. Stand up the founder-key path on a non-prod box
  2. Prove the key works
  3. Prove recovery works if the key is lost
  4. Only THEN consider any prod change

