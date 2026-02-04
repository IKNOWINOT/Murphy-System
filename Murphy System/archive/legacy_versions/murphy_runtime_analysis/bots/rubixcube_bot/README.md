
# rubixcube_bot — Tensor hydration + Probability/Statistics reasoning (Bot-standards compliant)

**Scope:** Deterministic hydration/fold/visualization with fidelity/confidence ranking **AND** a full probability/stats toolkit:
- Distributions: Normal/Exponential/Binomial/Poisson (CDF/PDF/quantile)
- Summaries: mean/sd/quantiles/correlation
- Inference: CIs, z-tests, chi-square
- Bayesian updates: Beta-Binomial, Normal-Normal
- Monte Carlo simulation
- Forecasting: OLS trend

**Tasks:** hydrate, fold, score_path, visualize, optimize_from_feedback, report, store, stats, probability, ci, hypothesis, bayes_update, simulate, forecast, explain_prob.

**Standards:** Quotas/budgets, S(t) breaker, Golden Path reuse/record, observability, privacy (PII redaction).

## Example
```ts
await run({ task:"probability", params:{ dist:{name:"normal",params:[0,1]}, x: 1.96 } }, ctx);
await run({ task:"stats", params:{ data:[1,2,3,4,5] } }, ctx);
await run({ task:"simulate", params:{ dist:{name:"poisson",params:[3]}, runs:10000, event:{op:"ge", threshold:5} } }, ctx);
```
