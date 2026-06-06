# Before/After Snapshots — CANON (2026-06-04)

Founder directive, verbatim: *"Before and after should exist for every mode
so before can replace a fail this is canon."*

## The rule

**Every change of state must produce two snapshots: a BEFORE and an AFTER.**
**The BEFORE must be a valid restore point — usable to undo if AFTER fails.**

This applies to every "mode" of change:
- systemd unit files (mask, unmask, edit, replace)
- nginx configs
- app code (any file under /opt/Murphy-System)
- database schemas (DDL)
- database rows (when bulk-updating > 1 record)
- environment variables / secrets
- automation function_args
- entity records that drive behavior
- DNS / Cloudflare settings
- any external API state change Murphy initiates (Stripe, Twilio, NOWPayments, Wix)

## What "valid restore point" means

A BEFORE snapshot is valid when ALL of:
1. It captures the **complete** prior state (not a diff, not a summary)
2. It is stored at a **canonical, predictable path** (so a human or another agent can find it)
3. It is **immutable** (read-only, never overwritten by a subsequent BEFORE)
4. It has a **verifier** — a one-liner that proves the restore would work
5. It is **named with a timestamp + reason** so the audit trail is obvious

## Canonical paths

```
/var/lib/murphy-production/snapshots/
  systemd/             # unit files
  nginx/               # nginx configs
  code/                # individual file snapshots from /opt/Murphy-System
  db_schema/           # CREATE TABLE / ALTER TABLE statements
  db_rows/             # JSONL of affected rows before update
  env/                 # secrets.env, .env files
  automations/         # function_args snapshots from Base44
  external/            # external API states (Stripe object dumps, etc)
```

Sandbox-side mirror for cross-session visibility:
```
.agents/.memory/snapshots/         # Murphy desktop / Base44 side
```

## Naming convention

```
<canonical_filename>.<UTC-iso>.<reason>.before
<canonical_filename>.<UTC-iso>.<reason>.after
```

Example:
```
murphy.service.20260604T165245Z.unmask_for_thread1.before
murphy.service.20260604T165245Z.unmask_for_thread1.after
```

The pair shares the same timestamp + reason so they grep together.

## The protocol (every mode)

Before any state-changing operation, Murphy MUST:

1. **Capture BEFORE** to the canonical path with full content.
2. **Write a verifier line** to the snapshot manifest:
   `.agents/.memory/snapshots/manifest.jsonl`
   Entry: `{ts, mode, target, before_path, restore_cmd, reason, requested_by}`
3. **Execute the change.**
4. **Capture AFTER** to the matching path.
5. **Run AFTER verifier** (does the system work?). If it fails:
   a. Immediately restore from BEFORE.
   b. Mark the attempt as `rolled_back` in the manifest.
   c. Surface the failure to the founder with the exact error.
6. If AFTER verifier passes, mark the manifest entry `success`.

## "Mode" coverage matrix

| Mode               | BEFORE captures                          | AFTER captures              | Verifier example                    |
|--------------------|------------------------------------------|-----------------------------|-------------------------------------|
| systemd unit       | full unit file (or `masked` symlink)     | full new unit file          | `systemctl is-active && curl /health` |
| nginx config       | full config file                         | full new config             | `nginx -t && curl /`                |
| code edit          | full file content + git ref              | full new content + git ref  | `python -c "import X"` + smoke test |
| DB schema          | `pg_dump -s` of table                    | `pg_dump -s` of table       | `SELECT * FROM table LIMIT 1`        |
| DB rows (bulk)     | `SELECT * WHERE ...` JSONL of all hits   | same query post-update      | row count + checksum match expected |
| env var            | full env file                            | full new env file           | service restart succeeds            |
| automation args    | `function_args` JSON                     | new `function_args` JSON    | next run produces expected shape    |
| external API state | `GET /resource` response body            | `GET /resource` after change| field present and equals expected   |

## Exceptions — what does NOT need a snapshot

- Read-only operations (`SELECT`, `curl GET`, `cat`)
- Log writes (logs are append-only)
- Ephemeral temp files (`/tmp/*`, sandbox `/app/*` scratch)
- Snapshots themselves (no recursion)

## Retention

- Last **30 days** of snapshots kept verbatim.
- After 30 days, prune to **one snapshot per (target, day)**.
- Never delete snapshots referenced by an unresolved incident.
- Manifest (`manifest.jsonl`) is append-only and never pruned.

## Drift detection

Once a day (suggested 04:00 UTC), the auditor walks the manifest and:
- Verifies every BEFORE still exists at its path.
- Verifies every AFTER matches current live state (no silent overwrites).
- Reports drift to `/api/self/audit`.

## Why this is canon

We just lived through it this morning: `murphy.service` was masked on
2026-05-25 with no BEFORE captured. When we tried to unmask, the original
unit file was gone — I had to reconstruct it from a `.bak` + a `.RETIRED`
file + reading source code to figure out how the monolith was launched.
That's not acceptable for a system that is supposed to be reversible.

From here forward: **no change without a restore point.**
