
# plan_structurer_bot — Clarify → Template → Build (Bot-standards compliant)

**Purpose:** detect ambiguity and run **Third Times the Charm** (5W1H clarifiers → template → hierarchical plan + advanced prompt). Saves reusable templates and Golden Path candidates; budget/S(t)/GP rails baked in.

## Tasks
- `clarify` (questions only), `template` (template from answers), `structure` (plan tree only),
  `build` (template + plan + prompt), `prompt` (prompts only), `store` (save template/prompt).

## Example
```ts
await run({
  task:"build",
  params:{ goal:"Make me an app like Discord", domain:"product", return_explain:true, store:true }
}, ctx);
```

**SLO:** P50 full build < ~1.2s; avg cost/run ≤ $0.002.
