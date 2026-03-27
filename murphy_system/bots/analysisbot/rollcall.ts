export function ping({ task }: { task: string }) {
  const t = String(task || '').toLowerCase();
  const can_help = /(sql|query|dataset|analytics|kpi|report)/.test(t);
  return {
    can_help,
    confidence: can_help ? 0.96 : 0.5,
    est_cost_usd: 0.006,
    must_have_inputs: ['params.question','params.schema OR params.db.id','params.execute?','params.max_rows?'],
    warnings: []
  };
}
