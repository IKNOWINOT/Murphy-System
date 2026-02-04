# meeting_notes_bot — Clockwork1 (TypeScript) — bots-only drop-in

Production-grade summarizer for meetings: summary, decisions, action items (owner/due), risks, and next steps.
Compliant with Bot Standards & `bot_base` (quota/budget/Stability S(t)/Golden Paths/observability). Designed to live only at:

`clockwork1/src/clockwork/bots/meeting_notes_bot/*`

## External adapters (wired by Codex)
- ../../orchestration/model_proxy          (LLM JSON-mode + optional STT)
- ../../orchestration/experience/golden_paths
- ../../orchestration/{stability, quota_mw, budget_governor}
- ../../observability/emit
- ../../io/audio_stt   (optional: stt(url|bytes) -> { text, diarization? })

## Capabilities
- Accept transcript text or audio pointer(s)
- Extract: summary, decisions, action items, owners, due dates, risks, follow-ups
- Timeline + blockers + next-meeting suggestion
- GP-first replay; KaiaMix Veritas 0.58 / Vallon 0.27 / Kiren 0.15

## SLOs
- p95 ≤ 2.5s (mini profile), ≤ 1.2s when GP hits
- Avg cost ≤ $0.012 per meeting
