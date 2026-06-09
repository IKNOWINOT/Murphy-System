# PCR-054 — Creation vs Operation Roles
## Audit + design doc (054a)

**Author:** Murphy
**Date:** 2026-06-09
**Status:** locked-in plan — proceeding to 054b on founder "continue"
**Predecessors:** PCR-053a-f (operation gate + shadow loop, 78/78 green, HEAD 9cd42680)

---

## 1. Why this exists

PCR-053 built a single gate (multi-dim N floor) that asks
"is there enough evidence to let the AI take this role over?"
That model is correct for **Operation** roles — the ones that produce
repeatable patterns whose correctness can be inferred from observation.

It is **categorically wrong** for **Creation** roles, where the output
itself derives its legal force from a licensed human's signature/stamp.
A Professional Engineer's seal on construction plans, a CPA's signature
on an audited financial statement, an attorney's signature on a pleading
of record — these aren't just "approvals," they are the product. Without
the licensed human in the loop, the artifact is not just lower quality;
it is legally invalid and in many jurisdictions criminal to produce.

PCR-054 introduces the second gate.

## 2. Three role classes

| Class      | Output                                        | AI's role         | Gate                         |
|------------|-----------------------------------------------|-------------------|------------------------------|
| OPERATION  | Repeatable patterns (send_quote, code review) | Auto-execute      | PCR-053 multi-dim N          |
| CREATION   | Stamped artifacts (PE plans, CPA returns)     | Draft + assist    | PCR-054 6-point creation gate|
| HYBRID     | Mix per task                                  | Per-task routing  | One or the other per task    |

The role-class field lives on RoleTemplate. Hybrid routing relies on a
new `task_class` field on the observation event so the gate is chosen at
artifact creation, not at role-promotion.

## 3. The 6-point Creation Gate

For any draft flagged as a Creation artifact, finalization is blocked
unless **all six** are true:

| # | Check                       | What it verifies                                       | Source of truth                       |
|---|-----------------------------|--------------------------------------------------------|---------------------------------------|
| 1 | License presence            | A named, licensed practitioner is on record            | `licensed_practitioners` table        |
| 2 | License currency            | License is current and unsuspended                     | State board / NCEES / AICPA / Bar     |
| 3 | Scope of practice           | License type matches artifact type                     | `practice_scope_map` static config    |
| 4 | QC pass                     | Artifact-type-specific QC checklist signed off         | `qc_checklists` per artifact type     |
| 5 | Direct-validation pass      | Independent reviewer (not author) signed off           | `validation_log` rows                 |
| 6 | Practitioner attestation    | The licensed human explicitly attested + signed envelope| `attestations` table                 |

Missing any → `passes=False`, `fail_closed=True`, audit row written.

## 4. License-currency verification (Q2 = option c)

**Hybrid policy, founder-approved direction:**
- Cache the last-known-good license status per practitioner with `last_verified_at`.
- On attestation: attempt live lookup against the state board API.
  - PE / surveyor → NCEES Records API
  - CPA → AICPA / NASBA verification
  - Architect → state board (varies; start with TX, CA, NY)
  - Attorney → state bar API where available, fallback list otherwise
  - Notary → state-specific
- If live lookup succeeds → update cache, proceed.
- If live lookup fails → use cache **only if** `last_verified_at` is within 30 days.
- If cache is stale → **fail closed**, log loudly, founder sees in audit.

We don't ship state-board integrations in 054 — we ship the **shape**
that accepts them. v1 wire stubs for NCEES + AICPA; the rest fail closed
with a clear "license_lookup_unimplemented_for_jurisdiction" reason.

## 5. v1 role roster (Q1 = 5 roles, founder-approved direction)

| Role               | Common artifact types               | Jurisdictions in v1 |
|--------------------|-------------------------------------|---------------------|
| Professional Engineer | structural_plan, electrical_plan, mech_plan | US-CA, US-TX, US-NY |
| CPA                | tax_return, audited_financials      | US-CA, US-NY        |
| Architect          | sealed_building_plan                | US-CA, US-TX        |
| Attorney           | court_filing, signed_contract       | US-CA, US-NY        |
| Notary Public      | notarized_affidavit                 | US-CA, US-TX        |

v2 backlog (not in 054 unless founder pulls forward):
Doctor (MD/DEA), Land Surveyor, Insurance Adjuster, Patent Agent, Real Estate Broker.

## 6. Per-task classification (Q3 = task_class field, founder-approved direction)

Every observation event gets an optional `task_class`:
  - `"operation"` (default for backward compat with PCR-053 data)
  - `"creation"`
  - `"hybrid_op"` / `"hybrid_creation"` for explicit Hybrid-role tasks

Existing data has no task_class → it inherits "operation" so PCR-053's
78 tests stay green. The Operation gate ignores creation tasks; the
Creation gate is fired only on creation tasks.

## 7. The 7 patches

| Patch | What it ships                                              | LoC est | Tests |
|-------|------------------------------------------------------------|---------|-------|
| 054a  | This doc                                                   | 0       | 0     |
| 054b  | Schema additions (role_class, task_class, practitioner)    | ~120    | ~10   |
| 054c  | practitioner_registry.py (license storage + currency)      | ~280    | ~15   |
| 054d  | creation_gate.py (6-point gate, returns CreationVerdict)   | ~320    | ~20   |
| 054e  | Seed 5 creation roles + extend REGULATORY_FLOOR class field| ~80     | ~5    |
| 054f  | HTTP surface (4 new endpoints)                             | ~180    | ~15   |
| 054g  | Wire into runtime + live demo end-to-end                   | ~40     | live  |
| **Total** |                                                       | ~1,020  | **~65** |

Style: same as PCR-053. Fail-soft on wire-in, idempotent registration,
case-insensitive lookups, JSONResponse with explicit status codes,
deferred scheduler attachment, manual entry points for verification.

## 8. Composition with PCR-053

The Operation shadow loop keeps running unchanged. The Creation gate is
**additional**, not a replacement. A Hybrid role's shadow audit table
will end up with both kinds of snapshots:

  shadow_audit_snapshots         — operation verdicts (PCR-053f, unchanged)
  creation_audit_snapshots (NEW) — creation verdicts (PCR-054d)

The OS page reads from both. The founder sees per-role "where is the AI
authorized to act on its own (op) and where is the human-in-the-loop
mandatory (creation)" at a glance.

## 9. What this is NOT

- Not a replacement for the licensed human. Ever.
- Not an attempt to automate stamps or sealing.
- Not a license-issuance system.
- Not legal advice — fail-closed by default, escalate ambiguity to founder.
- Not a substitute for the firm's own QC procedures; it **enforces** them.

## 10. What "done" looks like (Shape of Complete)

PILLAR 1 CODE       — files exist, py_compile clean, no TODOs
PILLAR 2 WIRED      — register_creation_gate(app) in lifespan, 4 routes hot
PILLAR 3 DEPS       — practitioners table created, regulatory_floor extended
PILLAR 4 EXECUTES   — live demo: draft CPA return -> fail-closed -> attest -> pass
PILLAR 5 VISIBLE    — /api/org/audit returns creation snapshots too
PILLAR 6 DOCUMENTED — this doc + 054g demo writeup + log lines
PILLAR 7 CONSISTENT — same voice, same patterns, same naming as PCR-053

---

**Next move on founder "continue":** ship 054b (schema additions),
then 054c (practitioner_registry), then 054d (the gate itself).
