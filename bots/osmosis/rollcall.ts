/**
 * Cost-aware minimal ping: nominate Osmosis only when it likely helps.
 * Triggers on words like “learn/infer/pattern/replicate/workflow/reverse engineer”.
 */
export function pingOsmosis(input: { task: string; budget_hint_usd?: number }) {
  const t = (input.task || "").toLowerCase();
  const hits = ["learn","infer","pattern","replicate","workflow","reverse","engineer","macro","template"]
    .reduce((s,w)=> s + (t.includes(w) ? 1 : 0), 0);

  const can_help = hits >= 1;
  // cost estimate on mini Medium-Task (adjust as metrics learn)
  const est_cost_usd = 0.0018 * (hits > 2 ? 1.2 : 1.0);
  const confidence = Math.min(0.9, 0.4 + hits*0.15);

  return {
    can_help,
    confidence,
    est_cost_usd,
    must_have_inputs: [],
    warnings: [],
  };
}
