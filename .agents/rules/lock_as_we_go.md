# Lock-As-We-Go — LOCKED 2026-05-26 by Corey

## The founder's directive (verbatim)
"Also both of you need to note if anything new needs to be locked from
editing as it progresses."

## The rule

Both Murphy AND the external agent (Claude/Cyborg) must proactively flag
anything that should be LOCKED from further editing as work progresses.

A thing gets locked when:
- It has been verified working end-to-end with loud-pass tests
- Changing it would silently break a dependency  
- It encodes a founder decision (NOWPayments-only, "ask before contacting Mark")
- It is a meta-rule (Audit First, Ask Murphy First, Check GitHub First)
- It is a contract between services (route paths, schema columns, signal shapes)

## How Murphy flags a lock candidate

When responding in chat or in a mind cycle, if I just verified something
that meets the criteria above, I include a line:

  🔒 LOCK CANDIDATE: <file:line> — <one-line reason>

The founder or the external agent then promotes it to a formal lock entry
in memory.md under "★ LOCKED ITEMS" with the date and breaking-change consequence.

## Format for locked items

```
### YYYY-MM-DD — <name of thing>
- <file path + line range or table.column>
- <what it does>
- <what depends on it>
- <what breaks if reverted>
```

## What "locked" means in practice

- LLM-generated patches that touch a locked region MUST be rejected
  by self_qc_pipeline.py with reason "locked_region_modification"
- The patcher_agent.py must check the locked-items list before proposing
  a diff that touches one
- The founder has final lock authority — can unlock, modify, or override

## Current locked items (mirrored from memory.md)

See `/opt/Murphy-System/.agents/memory.md` ★ LOCKED ITEMS section.
Active as of 2026-05-27:
1. CRM schema: deals.archived + archived_at + idx_deals_archived
2. Ops process autoseed (murphy_ops.py:152-160)
3. Dual-import pattern in capability_autoseed.py
4. Capability-Aware Fallback module (capability_fallback.py)
5. NOWPayments-only billing rail
6. Ask-before-contacting-Mark-Post rule
7. Email pipeline 4-bug fix (SendResult.success, STARTTLS, dovecot, ipv4)
8. Watchdog port-holder check
9. The 6+1 meta-rules (Audit First, Ask Murphy First, Check GitHub First,
   Doc standard, Correctness over cycles, This rule)

## How this composes with other rules

- **Audit First** = audit reality before answering
- **Ask Murphy First** = check Murphy's source before proposing architecture
- **Check GitHub First** = check the repo for prior outlines
- **Lock-As-We-Go (THIS RULE)** = flag verified things before they get
  edited away by the next mind cycle

The four rules are siblings, applied in sequence as work progresses.
