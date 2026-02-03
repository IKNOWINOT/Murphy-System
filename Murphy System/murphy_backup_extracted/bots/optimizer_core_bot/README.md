# optimizer_core_bot — PURE (no aionmind_core), Bot-standards compliant
Purpose: Normalize optimization specs (original or improved), plan the search (algorithm, budget), and emit 1–3 microtasks to execute an optimization job.

## Inputs
- Either a Python-style spec (variables/constraints/objective/algorithm/budget_evals), or
- A normalized core spec (direction/metric/variables/constraints/algorithm/stop), or
- A plain-text objective and hints, which the model proxy will synthesize into a core spec.

## Output
- `result.optimization.core_spec` — normalized spec for the optimizer
- Optional `initial_points`, `best_guess`, and `tasks` for execution

## Register
- run: `src/clockwork/bots/optimizer_core_bot/optimizer_core_bot.ts::run`
- ping: `src/clockwork/bots/optimizer_core_bot/rollcall.ts::ping`
