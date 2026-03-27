export function ping({ task }: { task: string }) {
  const t = String(task || '').toLowerCase();
  const can_help = /(lead|prospect|crm|campaign|sequence|outreach|landing|ad|email|sms|social|discover|verify|unsubscribe)/.test(t);
  return { can_help, confidence: can_help ? 0.95 : 0.5, est_cost_usd: 0.012, must_have_inputs: ['params.action','params.owner?','params.execute?'], warnings: [] };
}
