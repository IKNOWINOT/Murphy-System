export function ping({ task }: { task: string }) {
  const normalized = String(task || '').toLowerCase();
  const can_help = /(loader|register|catalog|bot\s?base|swisskiss)/.test(normalized);
  const warnings: string[] = [];
  if (!/(bot\s?base)/.test(normalized)) warnings.push('bot_base not mentioned — ensure compliance');
  let category = 'general';
  if (/(vision|opencv|image)/.test(normalized)) category = 'computer-vision';
  if (/(robot|motor|servo)/.test(normalized)) category = 'robotics';
  if (/(nlp|text|language)/.test(normalized)) category = 'nlp';
  return {
    can_help,
    confidence: can_help ? 0.92 : 0.4,
    est_cost_usd: 0.003,
    must_have_inputs: ['bot_name', 'bot_path', 'intents', 'manifest or code excerpt'],
    warnings,
    category
  };
}
