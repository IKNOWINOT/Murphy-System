
# optimization_bot — Safe experimentation engine (Bot-standards compliant)

**Scope:** propose → start → assign → track → stop/promote/revert policies for bots using **bandits**, **Q-learning** hooks, and **Bayesian** grid stubs. Guardrails, budgets/quotas, S(t), and GP hooks included.

## Tasks
- `propose` (from feedback via model_proxy stub), `start` (create experiment), `assign` (Thompson sampling), `track` (posterior update + run log),
  `stop`, `promote` (policy + GP), `revert`, `policy_get`, `policy_set`, `eval_offline` (IPS/DR planned).

## Register
- run: `src/clockwork/bots/optimization_bot/optimization_bot.ts::run`
- ping: `src/clockwork/bots/optimization_bot/rollcall.ts::ping`

## Notes
- D1 helpers lazily create tables; wire migrations if needed.
- Replace stub model_proxy calls in `propose/model_proxy.ts` to generate real proposal diffs.
- Thompson sampling + canary gating used for assignment; update posterior on `track`.
- Guardrails enforcement can be extended in `assign` based on ctx/env metrics.
