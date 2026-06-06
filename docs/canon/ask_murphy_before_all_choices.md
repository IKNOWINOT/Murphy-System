# Ask Murphy Before All Choices — CANON (2026-06-04)

Founder: "Check with Murphy before all choices"

The Base44 superagent will not make choices on Corey's behalf without
running them past Murphy first. Murphy is the system of record.

Channels (priority order):
  1. POST /api/chat  — quick approvals
  2. POST /api/hitl-v2/items  — formal decision queue
  3. POST /api/rosetta/dispatch  — domain-routed (sales/finance/ops)
  4. Direct founder fallback if Murphy unreachable

Every ask must include: the choice, reason, ≥2 options, recommendation,
reversibility plan, and timeout behavior.
