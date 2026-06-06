# Before/After Snapshots — CANON (2026-06-04)

Every mutation produces a BEFORE and an AFTER. BEFORE must be a valid restore point.

Paths:
  /var/lib/murphy-production/state_snapshots/<mode>/<basename>.<UTC>.<reason>.{before,after}
  /var/lib/murphy-production/state_snapshots/manifest/manifest.jsonl

Helper:
  murphy-snapshot before <mode> <target> <reason>
  murphy-snapshot after  <mode> <target> <reason>
  murphy-snapshot restore <before_path> <dest>
  murphy-snapshot verify

Modes: systemd | nginx | code | db_schema | db_rows | env | automations | external
