# Memory Hygiene — LOCKED 2026-05-25

## The pattern I keep failing at
I memorize "X is missing / not done / not installed" then continue
repeating it for days even after the founder has done it. Specific
recent cases the founder caught:
- Said "Twilio not added" the day AFTER founder set it up (2026-05-25)
- Said "PSM is dormant" while it had 20 verified ledger entries
- Said "$9,065 revenue" while it was actually test payloads
- Said "capital/proposals exists" — endpoint never existed
- Said "phone/dial unmounted" — it's mounted, just needs creds
- Said "vault.db is the vault" — that's a 0-byte decoy

This is the same root cause: I treat memory as ground truth instead
of as a hypothesis that must be re-verified.

## The rule
**Before stating that something is missing, not done, or not configured —
verify it RIGHT NOW.** Always.

If memory says "X isn't installed," I run a check. If the check confirms
it, I report it. If it contradicts memory, I update memory before
responding.

## What this looks like in practice

### BEFORE saying "Twilio not configured":
```bash
sqlite3 /var/lib/murphy-production/murphy_vault.db \
    "SELECT name FROM vault_secrets WHERE name LIKE '%TWILIO%';"
curl -X POST .../api/phone/dial  # see what error it returns
```

### BEFORE saying "no payment system":
```bash
curl .../api/billing/checkout
ls /var/lib/murphy-production/billing*.db
```

### BEFORE saying "endpoint X doesn't exist":
```bash
# Re-run /opt/Murphy-System/scripts/dump_routes.py
# Or grep src/ for the route
```

### BEFORE saying "no revenue / 0 customers":
```bash
sqlite3 .../billing.db "SELECT status, COUNT(*) FROM billing_records GROUP BY status;"
# And verify the records aren't synthetic test payloads
```

## Re-verification cadence

When I open a new session and need to talk about:
- **Vault contents** → query `murphy_vault.db` first
- **Endpoint reality** → check `endpoint_map.md` or rerun discovery
- **Revenue / customers** → query billing.db, check for test patterns
- **Service state** → systemctl + journalctl, don't trust prior memory
- **Pending tasks the founder said they'd do** → check if done before saying it isn't

## Why this matters

The founder gave Murphy access to their actual business — phone numbers,
banking, customer data, code repo. Every false claim from me erodes their
ability to trust the system. "Sorry, my memory was wrong" gets old fast.

Better to say "let me check" and take 5 seconds than to confidently state
something stale and waste their time correcting me.

## The kill-criterion

If I make a claim about system state without running a check in the
current session, that claim is **not credible**. Mark it with phrasing
like "my notes say X but let me verify" — never state it as current
fact.
