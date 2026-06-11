
### N+1. PCR-054n: dedupe inbound_replies processing
**Tier:** important
**Surfaced:** 2026-06-09 (PCR-054j live demo)
**What I saw:** process-inbound re-processes the same inbound_replies.db rows on every call because there's no `processed` flag. In the 054j live demo, the same clarifying question appeared 3 times on the thread (once per process-inbound call) with different state_at_time values.
**My take:** Add `processed_at REAL, processed_for_engagement TEXT` columns to inbound_replies. Update process_pending_replies to skip rows where processed_at IS NOT NULL.
**Cost to address:** ~30 min. Simple schema + one query change.
**Founder input needed:** None — clear bug, clear fix. Just confirm timing (slot it between 054k and 054l?).
---
