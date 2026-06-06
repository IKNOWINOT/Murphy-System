# SCHEMA NIGH PLAN — 2026-05-27
# LOCKED CONTRACT for future patches.
# All new columns/tables for the next 30 days MUST conform to this plan.
# Founder directive: stop adding columns piecemeal. Lay out everything now.

## Cross-cutting required fields (every new table)

| Column | Type | Required | Why |
|---|---|---|---|
| id | INTEGER PK autoinc OR TEXT PK | yes | universal join key |
| created_at | TEXT NOT NULL ISO8601 UTC | yes | observability |
| tenant_id | TEXT NULL (NULL = system-owned) | yes (indexed) | sellable multi-tenant |
| schema_version | INTEGER DEFAULT 1 | yes | migration safety — bump on each alter |
| updated_at | TEXT | when mutable | |
| retention_until | TEXT | for time-bound data | |
| source_actor | TEXT | for audit trails | |
| correlation_id | TEXT | for multi-step traces | |

## Surface 1 — rosetta_dispatch_log
Existing 13 cols. Add: tenant_id, schema_version, correlation_id,
parent_dispatch_id, pattern_id, dlfr_package_id, cost_credits, retention_until.
Indexes: tenant_id, correlation_id, parent_dispatch_id.

## Surface 2 — covenant_breaches
Existing 3 cols. Add: tenant_id, schema_version, severity, reason,
signal_id, dispatch_id (FK rosetta_dispatch_log), resolved_at, resolution_kind.
Indexes: active strikes (where resolved_at IS NULL), dispatch_id.

## Surface 3 — registry_routes
Existing: id, path, method, handler_name, module_file, capability, gate_a..gate_e.
Add: tenant_id, service ('monolith'|'ops'|'robotics'|'edge'), last_gate_check_at,
gate_evidence_a..e (file:line / probe / dep / e2e ts / visible URL),
deprecation_status, owns_subsystem.
Required by: murphy-shape-verifier revival.

## Surface 4 — tenants_v2 (NEW, replaces tenants)
Full schema in plan doc. Includes:
- Identity (tenant_id, name, owner_email, owner_phone, domain)
- Lifecycle (status, trial_ends_at, activated_at, churned_at, churn_reason)
- Plan (plan_id, plan_tier, seat_count)
- Commerce (primary_payment_method, billing_currency, last_payment_at,
  next_billing_at, lifetime_revenue)
- Soul (soul_profile_id, north_star_override, harm_threshold_override)
- Compliance (data_region, pii_handling, audit_log_retention_days)
- Limits (monthly_dispatch_quota, monthly_dispatch_used, storage_*)
- Onboarding (onboarding_completed_at, onboarding_step, founder_notes)

## Surface 5 — timeline_events (NEW unified table)
Replaces multi-source UNION at read time with single write-through table.
Cols: id, ts, schema_version, tenant_id, source, source_event_id, trigger,
outcome_status, latency_ms, effect_artifact_url, correlation_id,
parent_event_id, severity, visibility, payload_json, retention_until.
Indexes: ts DESC, (tenant_id, ts DESC), (source, source_event_id),
correlation_id, severity (partial).

## Surface 6 — patterns (extend pattern_library)
Add: tenant_id, schema_version, agent_id, avg_latency_ms, last_failure_at,
decay_rate, confidence_score, deprecated_at.
Indexes: (tenant_id, domain), confidence_score DESC.

## Surface 7 — schema_migrations (meta-table)
Existing in murphy_audit.db. Cols required:
migration_id, applied_at, target_db, target_table, description,
reversible, rollback_sql.
Used to prevent double-apply.

## Implementation order (locked)

### Round 1 (THIS ROUND): cross-cutting fields on existing tables
- rosetta_dispatch_log: +tenant_id, +schema_version, +correlation_id
- covenant_breaches: +tenant_id, +schema_version, +severity, +dispatch_id
- patterns: +tenant_id, +schema_version, +agent_id
- schema_migrations: extend to track these
~10 ALTERs. No service restart. SQLite ALTER ADD is non-blocking.

### Round 2 (future): registry_routes evidence cols + revive shape-verifier
### Round 3 (future): timeline_events table + write-through from 5 sources
### Round 4 (future): tenants_v2 + migration from tenants

## Anti-patterns this plan blocks

1. Adding a column without bumping schema_version (silent migration drift)
2. Adding a tenant-scoped feature without tenant_id (re-do later)
3. Adding new tables without retention_until (data accumulates forever)
4. Building UI against multi-source UNION reads (slow, brittle)
5. Reviving murphy-shape-verifier before evidence cols exist (writes have nowhere to land)

LOCKED 2026-05-27 by founder directive.
