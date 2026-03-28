export function ping({ task }: { task: string }) {
  const t = String(task || '').toLowerCase();
  const can_help = /(visual|chart|diagram|svg|cad|model)/.test(t);
  return {
    can_help,
    confidence: can_help ? 0.94 : 0.5,
    est_cost_usd: 0.006,
    must_have_inputs: ['task','params.kind','params.data|params.spec'],
    warnings: []
  };
}
