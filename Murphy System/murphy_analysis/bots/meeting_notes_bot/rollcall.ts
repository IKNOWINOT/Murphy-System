export function ping({ task }: { task: string }) {
  const t = String(task || '').toLowerCase();
  const can_help = /(meeting|minutes|summary|action|notes|decisions)/.test(t);
  return {
    can_help,
    confidence: can_help ? 0.95 : 0.5,
    est_cost_usd: 0.006,
    must_have_inputs: ['params.transcript OR attachments.audio/text', 'params.title?','params.date?'],
    warnings: []
  };
}
