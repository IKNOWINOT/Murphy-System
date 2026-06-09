# PCR-054b.1 — Engagement Loop for Creation Artifacts
## Rename + reshape doc

**Author:** Murphy
**Date:** 2026-06-09
**Status:** locked-in plan — proceeding to 054c on founder "continue"
**Predecessor:** PCR-054a (creation gate architecture doc, HEAD 55ab0452)
**Predecessor:** PCR-054b (RoleClass + LicensedPractitioner schema, HEAD 3da3c7d5)

---

## 1. What changed since 054a

054a designed a **synchronous Creation Gate**: at finalization time, the
system checks 6 things and either passes the artifact or fails closed.
That model assumed the licensed practitioner was sitting inside Murphy's
UI waiting to click "I attest."

Founder reframed (2026-06-09):

> **HITL becomes a request outreach from the mail writing type system to
> someone hiring them for the review or what is provided. Designated human
> rate per national average or GSA.**
>
> **Attestation is HITL process where they are providing their license for
> the review and driving information that pushes the system folder.**

Three structural consequences:

1. The licensed practitioner is **external** to Murphy. They have a
   practice, a billing rate, an inbox. They are not waiting on us.
2. Engagement is an **outbound procurement loop**, not a UI panel.
   We reuse `mail_writing` to send an Engagement Request the same way
   we send any other outbound message in the system.
3. Attestation is **inbound**, **credential-bearing**, and **mutates state**.
   The practitioner's reply carries their license claim + attestation
   language, and *that payload* is what advances the artifact's folder.

054 is renamed: **Engagement Loop for Creation Artifacts** (not "Creation Gate").
The gate is now one phase inside the loop.

## 2. The loop in 7 states

```
                  ┌──────────────┐
                  │  drafting    │  AI generates artifact + QC checklist
                  └──────┬───────┘
                         │ draft ready
                         ▼
                  ┌──────────────┐
                  │  outreach    │  mail_writing sends Engagement Request
                  │   queued     │  to bench practitioner with rate quote
                  └──────┬───────┘
                         │ sent
                         ▼
                  ┌──────────────┐
                  │  awaiting    │  practitioner reviewing externally
                  │  attestation │  inbound parser watching mailbox
                  └──────┬───────┘
                         │ reply received
                         ▼
                  ┌──────────────┐
                  │  validating  │  6-point gate runs against attestation
                  │  attestation │  payload (license + scope + language)
                  └──────┬───────┘
                  pass   │   fail
                ┌────────┴─────────┐
                ▼                  ▼
        ┌──────────────┐  ┌──────────────┐
        │  finalized   │  │  declined or │  re-route to next bench
        │              │  │  edits asked │  practitioner OR back to draft
        └──────┬───────┘  └──────────────┘
               │
               ▼
        ┌──────────────┐
        │ verifying    │  async post-fact lookup against NCEES/AICPA/Bar
        │ (background) │  to confirm the claimed license is real
        └──────────────┘
```

## 3. Folder location decision

The engagement folder is the persistent state container for one
engagement. Three options were on the table:

| Option | Pros | Cons |
|--------|------|------|
| (a) Base44 entity | RLS, fast queryable | Cross-system sync, weak coupling to gate |
| (b) Murphy SQLite | Colocated with audit tables, single source | No RLS without app-layer enforcement |
| (c) Filesystem dir | Browseable, matches word "folder" | Hard to query, no atomicity |

**Decision (founder-implicit on "follow your own recommendations"):**

- (b) **Murphy SQLite is the system of record** — three new tables
  alongside `shadow_audit_snapshots` and the future `creation_audit_snapshots`:
  - `engagement_folders` — one row per engagement, state machine
  - `engagement_events` — append-only log of state transitions and external touches
  - `attestation_payloads` — every inbound attestation, raw + parsed
- (c) **A browse path is generated** at `/var/murphy/engagements/<engagement_id>/`
  containing: `draft.pdf`, `qc.json`, `engagement_request.eml`,
  `attestation.eml`, `audit.json`. Tenants can rsync or web-browse the dir.
  SQLite is canonical; filesystem is a mirror for human eyes.

## 4. Where the schema from 054b stands

PCR-054b shipped `LicensedPractitioner` with pre-populated license fields
and `is_current()` / `covers()` methods. Founder reframe changes the
**source of truth** for those fields:

- **Before:** Murphy/tenant pre-populates license info at bench-add time.
- **After:** License info is **first written by the practitioner's attestation
  reply**, and re-asserted on every subsequent attestation. The bench row
  starts as a contact card (name, email, license_type, jurisdiction); the
  full license_number, expires_at, scope_endorsements come from the
  first attestation payload.

`LicensedPractitioner` as a dataclass is still correct. Lifecycle changes:

| Bench state           | What we know about license           |
|-----------------------|--------------------------------------|
| **invited**           | name, email, license_type, jurisdiction (claim) |
| **first_attestation** | license_number, expires_at, scope_endorsements arrive in payload |
| **verified**          | post-fact NCEES/AICPA/Bar lookup confirmed claim |
| **flagged**           | post-fact lookup contradicted claim — bench removal |

`is_current()` and `covers()` continue to work; they just have nothing
to operate on until a first attestation lands.

## 5. The 6-point gate, reshaped

The gate runs at **state transition** `awaiting_attestation → validating_attestation`,
fed by the inbound attestation payload (not by Murphy's stored state):

| # | Check | Source in inbound payload |
|---|-------|---------------------------|
| 1 | License presence | Payload includes `license_type` + `license_number` |
| 2 | License currency | Payload includes `expires_at` in future; status claim = "active" |
| 3 | Scope of practice | Payload `license_type` covers the artifact's `artifact_type` (uses 054b `covers()`) |
| 4 | QC pass | Payload acknowledges QC checklist items in attestation language |
| 5 | Direct-validation pass | Payload identifies independent reviewer OR practitioner serves as reviewer with explicit second-look attestation |
| 6 | Attestation language | Payload contains the exact attestation template Murphy provided, signed with practitioner identity |

All six must be present in the **single inbound payload** for the folder
to advance. Missing any → state goes to `declined_or_edits_asked`, audit
row written, mail_writing composes a clarification reply to practitioner.

## 6. Rate quoting (the "designated human rate" part)

Per founder direction: **national average or GSA.**

Built as a small `engagement_rates.py` module:

```python
def quote_rate(license_type, jurisdiction, hours_estimated,
               source="bls", percentile=90) -> RateQuote
```

Defaults per my own recommendations on the previous turn:
- **source = "bls"** (BLS OEWS public API, no auth)
- **percentile = 90** (license-on-the-line work justifies top-of-market)
- **jurisdiction-adjusted** (state-level BLS data preferred over national when available)
- **override = "gsa"** when caller wants GSA Schedule rate instead
- **cache** BLS responses locally — series IDs are stable, values update yearly

The rate quote ships in the outbound Engagement Request with a citation
footer: *"Rate derived from BLS OEWS May 2025 — SOC 13-2011 (Accountants &
Auditors) 90th-percentile hourly × 8h estimated engagement"*. Practitioners
see a number that's defensibly anchored to a public benchmark.

## 7. Patch series (reshaped)

| Patch | What it ships | LoC est | Tests |
|-------|--------------|---------|-------|
| 054a  | Architecture doc (creation gate) | 149 | 0 | ✅ |
| 054b  | RoleClass + LicensedPractitioner | 292 | 21 | ✅ |
| **054b.1** | **This doc (reshape to engagement loop)** | 0 | 0 | ⏳ |
| 054c  | `EngagementFolder` state machine + 3 SQLite tables | ~360 | ~20 |
| 054d  | Extend `mail_writing` with `engagement_request` envelope type | ~240 | ~12 |
| 054e  | Inbound attestation parser (`attestation_inbound.py`) | ~300 | ~18 |
| 054f  | `engagement_rates.py` (BLS + GSA, jurisdiction-adjusted) | ~220 | ~14 |
| 054g  | Bench management endpoints (invite/list/remove practitioner) | ~180 | ~10 |
| 054h  | Async post-fact license verification (NCEES/AICPA/Bar stubs) | ~200 | ~8 |
| 054i  | Wire into runtime + live demo end-to-end | ~50 | live verify |
| **Total beyond 054b.1** |                       | **~1,550** | **~82** |

## 8. Composition with PCR-053 and earlier 054

- PCR-053f shadow loop keeps running unchanged on OPERATION roles.
- PCR-054b RoleClass enum determines which loop fires per role:
  OPERATION → PCR-053 shadow loop, CREATION → PCR-054 engagement loop,
  HYBRID → per-task routing on `task_class`.
- PCR-054b `LicensedPractitioner.covers()` is reused by the gate at check 3.
- `engagement_folders.role_id` references `RoleTemplate.role_id` so the
  org chart compiler stays the org-shape source of truth.

## 9. What this is NOT

- Not a replacement for the licensed human. Murphy never stamps anything.
- Not a marketplace — tenant brings their own bench in v1.
- Not a recruiting tool — bench is curated by tenant.
- Not a billing system — rate quote is informational; payment happens
  out-of-band between tenant and practitioner.
- Not a substitute for the tenant's existing QC procedures; it surfaces
  and timestamps them.

## 10. Shape of Complete for PCR-054 (revised)

| Pillar | What "done" means |
|--------|-------------------|
| 1 CODE | All files exist, py_compile clean, no TODOs |
| 2 WIRED | `register_engagement_loop(app)` in lifespan, ~10 routes hot |
| 3 DEPS | 3 new SQLite tables created, BLS cache directory writable |
| 4 EXECUTES | Live demo: draft CPA return → outreach email composed → fake inbound attestation → gate passes → folder finalized → post-fact lookup queued |
| 5 VISIBLE | `/api/org/engagements` returns active engagements + folder URLs |
| 6 DOCUMENTED | This doc + 054i demo writeup + log lines for every state transition |
| 7 CONSISTENT | Same voice, same patterns, same naming as PCR-053f |

---

**Next move on founder "continue":** ship 054c (state machine + tables),
then 054f (rate quoting — needed by 054d so outreach can include a price),
then 054d (mail outreach), then 054e (inbound parser).

Order is shaped so each patch can be live-demoed independently against
the previous patch's output.
