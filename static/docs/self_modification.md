# Self-Modification (Pillar A)

Murphy modifies its own code and runtime state through a structured pipeline:

## Components
- **`src/self_audit.py`** — periodic self-audit, emits `/api/self/audit` payload
- **Patcher** — applies code patches, tracks `applied`/`total` counts in audit
- **Shape-of-Complete verifier** — every 30 min, scores 49 pillars across 7 slices
- **Before/After Canon** — every mutation produces snapshots usable as restore points

## How a self-modification happens
1. Auditor / verifier identifies a gap (red pillar, missing route, drifted config)
2. Patch is proposed via Rosetta / vision-loop / direct edit
3. BEFORE snapshot captured to `/var/lib/murphy-production/state_snapshots/`
4. Patch applied
5. AFTER snapshot + verifier runs
6. If verifier red: automatic rollback from BEFORE

## Visibility
- `/api/self/audit` — live audit payload
- `/var/lib/murphy-production/shape_state.json` — latest verifier scores
- `/var/lib/murphy-production/shape_history.db` — historical runs
- `/var/lib/murphy-production/state_snapshots/manifest/manifest.jsonl` — all changes

## Constitution
No change ships without a BEFORE snapshot. Period.

Last updated: 2026-06-04
