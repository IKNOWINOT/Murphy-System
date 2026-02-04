# research_bot — Clockwork1 (TypeScript) — bots-only drop-in

Web/PDF/Doc research + synthesis with source tracking and cost/stability governance.
Compliant with Bot Standards & `bot_base` (quota/budget/S(t)/GP/observability). Designed to live only at:

`clockwork1/src/clockwork/bots/research_bot/*`

## External adapters (wired by Codex)
- ../../orchestration/model_proxy
- ../../orchestration/experience/golden_paths
- ../../orchestration/{stability, quota_mw, budget_governor}
- ../../observability/emit
- ../../io/web_fetch            (ASSUMED: fetchText(url) -> string, normalizeUrl(url) -> string)
- ../../io/pdf_reader           (ASSUMED: readPdf(url|bytes) -> string)
- ../../io/html_to_text         (ASSUMED: htmlToText(html) -> string)

## Capabilities
- Fetch and normalize a small set of URLs (or accept pasted text)
- Extract text from HTML/PDF; chunk + synthesize via model_proxy JSON mode
- Output structured summary with quoted snippets + references
- GP-first replay; KaiaMix heuristic Veritas 0.6 / Vallon 0.25 / Kiren 0.15
- Safety: configurable; redacts obvious PII in logs

## SLOs
- p95 ≤ 3.5s on mini profile for 2–3 short pages
- Avg cost ≤ $0.015 per research request
