# visualization_bot — Clockwork1 (TypeScript) — bots-only drop-in

Production visualization agent for charts, diagrams, and technical SVGs with optional CAD/Simulation collaboration.
Compliant with Bot Standards & `bot_base` (quota/budget/S(t)/GP/observability). Designed to live only at:

`clockwork1/src/clockwork/bots/visualization_bot/*`

External adapters (wired by Codex):
- ../../orchestration/{model_proxy, experience/golden_paths, stability, quota_mw, budget_governor}
- ../../observability/emit
- ../../storage/r2_adapter (optional for PNG storage)
- ../../bots/{cad_bot, simulation_bot} (optional; this bot can function without them)

## Capabilities
- Chart specs (Vega-Lite–style JSON) from task+data or provided spec
- Diagrams (Mermaid/Graphviz–like DSL as string spec)
- Technical SVG builder for simple CAD scopes (exploded views with labels)
- Validations: axis baseline, monotonic time, colorblind flags, misleading risk
- GP-first replay; records GP on success; KaiaMix heuristic Veritas 0.55 / Vallon 0.30 / Kiren 0.15

## SLOs
- p95 ≤ 3.0s (mini profile), ≤ 1.5s when GP hits
- Avg cost ≤ $0.015 per visualization request
