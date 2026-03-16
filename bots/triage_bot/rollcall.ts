export function ping({ task }: { task: string }) {
  const normalized = String(task || '').toLowerCase();
  const can_help = /(triage|route|assign|roll\s?call|delegate)/.test(normalized);
  return {
    can_help,
    confidence: can_help ? 0.93 : 0.5,
    est_cost_usd: 0.004,
    must_have_inputs: ['task','constraints.budget_hint_usd','constraints.time_s'],
    warnings: []
  };
}
