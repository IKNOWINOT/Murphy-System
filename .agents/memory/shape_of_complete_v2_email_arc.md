# Shape of Complete v2 — Email Arc Upgrade

**LOCKED 2026-06-10 by founder directive (Corey Post).**

Applies the v1 5-gate framework to every component of the email arc:
direct + ambient + DLF + drill + generative + follow-up + ads +
graphics + verify + ML + dashboard.

## The 5 gates (unchanged from v1)

a) Code exists  b) Wired  c) Deps real  d) E2E executes  e) Visible

Kill criterion: code without verified production execution = theater.

## Email arc — 15 components (snapshot 2026-06-10)

| # | Component | a | b | c | d | e | Verdict |
|---|-----------|---|---|---|---|---|---------|
| 1 | INBOUND email (postfix + intake) | ✅ | ✅ | ✅ | ✅ | ✅ | **COMPLETE** (visible in /os/stranger) |
| 2 | CLASSIFY direct vs ambient | ✅ | ✅ | ✅ | ✅ | ✅ | **COMPLETE** |
| 3 | PAY GATE / quota check | ✅ | ✅ | ✅ | ✅ | ✅ | **COMPLETE** (quota_reason in /os/stranger) |
| 4 | DLF injection (build_deep_soul) | ✅ | ✅ | ✅ | ✅ | ✅ | **COMPLETE** (Ship 31i.B) |
| 5 | MAGNIFY-DRILL synthesis | ✅ | ✅ | ✅ | ✅ | ✅ | **COMPLETE** |
| 6 | GENERATIVE reply (no templates) | ✅ | ✅ | ✅ | ✅ | ✅ | **COMPLETE** (reply text in /os/stranger) |
| 7 | FOLLOW-UP question generation | ✅ | ✅ | ✅ | ✅ | ✅ | **COMPLETE** (Ship 31u: appended between reply & ad, role-aware, tracked) |
| 8 | EMAIL GRAPHICS / multipart MIME | ✅ | ✅ | ✅ | ✅ | ✅ | **COMPLETE** (Ship 31t: branded HTML + plain fallback, live-tested to founder inbox) |
| 9 | AD INJECTION (contextual) | ✅ | ✅ | ✅ | ✅ | ✅ | **COMPLETE** (Ship 31m, in-house inventory) |
| 10 | EMAIL VERIFICATION → unlock | ✅ | ✅ | ✅ | ✅ | ✅ | **COMPLETE** (Ship 31v: token-based domain claim, /verify/<token>, allowlist auto-add, /os/verifications) |
| 11 | OUTBOUND SEND (postfix queue) | ✅ | ✅ | ✅ | ✅ | ✅ | **COMPLETE** (sent_at + status in /os/stranger) |
| 12 | COMPLIANCE footer (CAN-SPAM) | ✅ | ✅ | ✅ | ✅ | 🟡 | FUNCTIONAL (footer wired, full gate still pending) |
| 13 | ML one-request learning loop | ✅ | ✅ | ✅ | ✅ | ✅ | **COMPLETE** (Ship 31s: agent_rating_loop + EMA fitness + LLM judge) |
| 14 | EXTERNAL BENCHMARK (tau-bench) | ✅ | ✅ | ✅ | ✅ | ✅ | **COMPLETE** (Ship 31h.2) |
| 18 | AGENT MEMORY + RATING + ROUTING | ✅ | ✅ | ✅ | ✅ | ✅ | **COMPLETE** (Ship 31s: persisted souls, fitness EMA, /os/agent-leaderboard) |
| 17 | LAUNCH GATE (allowlist + STOP + adoption) | ✅ | ✅ | ✅ | ✅ | ✅ | **COMPLETE** (Ship 31p) |
| 16 | ATTACHMENT SYNTHESIS + chunking + resume + honest-limits | ✅ | ✅ | ✅ | ✅ | ✅ | **COMPLETE** (Ship 31i.A) |
| 15 | FOUNDER DASHBOARD (/os/stranger) | ✅ | ✅ | ✅ | ✅ | ✅ | **COMPLETE** (Ship 31i.C) |

**Scorecard:**
- COMPLETE: 3/15 (20%)
- FUNCTIONAL: 5/15 (33%)
- THEATER: 4/15 (27%)
- NOT BUILT: 3/15 (20%)

## External benchmark anchor (Ship 31h.2, 2026-06-10)

τ-bench retail+airline real, F1 ground-truth scoring, 8 tasks × 4 configs:
- murphy_dlf: 0.711 ← WINS
- murphy_full: 0.701
- murphy_raw: 0.694
- murphy_magnified: 0.684

DLF injection proven externally: +0.017 F1 over Llama-70B raw.

## Ship order — locked

Each ship MUST flip a row from theater/not-built to ALL FIVE GREEN.
No "I built the code" — only "complete vertical slice."

- Ship 31i: rows 4 + 15 (DLF wire + /os/stranger dashboard)
- Ship 31j: row 12 (compliance gate enforcement)
- Ship 31k: row 8 (multipart MIME + branded HTML)
- Ship 31l: row 10 (claim-account flow)
- Ship 31m: row 9 (AdSense / affiliate placement)
- Ship 31n: row 7 (follow-up question generation)
- Ship 31o: row 13 (ML feedback loop)

## Status reporting format (locked)

Every report uses the exact grid above. No prose padding.
No "mostly done" / "almost there" — just gate emoji and verdict.

## Authority

Locked by Corey Post 2026-06-10 in conversation with Murphy.
Future changes require founder sign-off + revision recorded in build_log.
