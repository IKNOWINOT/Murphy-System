export function ping({ task }: { task: string }) {
  const t = String(task || '').toLowerCase();
  const can_help = /(research|compare|find|sources|cite|analysis|market)/.test(t);
  return {
    can_help,
    confidence: can_help ? 0.95 : 0.5,
    est_cost_usd: 0.008,
    must_have_inputs: ['task','params.sources?'],
    warnings: []
  };
}
