export type ValidationResult = { microtask_id: string; passed: boolean; details: string; errors?: string[] };

export async function validateMicroTasks(
  mts: any[],
  dryRun = true,
  ctx?: { db?: any; fetch?: typeof globalThis.fetch; targetBot?: string; botCapabilities?: string[] }
): Promise<ValidationResult[]> {
  if (dryRun) {
    return mts.map((m: any) => ({ microtask_id: m.id, passed: true, details: 'dry-run pass' }));
  }

  // Live validation
  const results: ValidationResult[] = [];
  for (const m of mts) {
    const errors: string[] = [];
    const targetBot = ctx?.targetBot || m.target_bot;

    // 1) Check target bot health/ping
    if (targetBot) {
      try {
        const fetchFn = ctx?.fetch ?? globalThis.fetch;
        const pingUrl = `http://${targetBot}/ping`;
        const resp = await fetchFn(pingUrl, { signal: AbortSignal.timeout(5000) });
        if (!resp.ok) errors.push('bot unreachable');
      } catch {
        errors.push('bot unreachable');
      }
    }

    // 2) Validate required capabilities against bot_capabilities DB entry
    const requiredIntent = m.goal || m.action || '';
    if (ctx?.db && targetBot && requiredIntent) {
      try {
        const row: any = await ctx.db.prepare('SELECT intents_json FROM bot_capabilities WHERE bot_name = ?').bind(targetBot).first();
        if (row?.intents_json) {
          let intents: string[] = [];
          try { intents = JSON.parse(row.intents_json); } catch {}
          const hasCapability = intents.some((i: string) => requiredIntent.toLowerCase().includes(i.toLowerCase()));
          if (!hasCapability) errors.push(`capability mismatch: '${requiredIntent}' not in bot intents`);
        }
      } catch { /* DB unavailable — skip capability check */ }
    } else if (ctx?.botCapabilities && requiredIntent) {
      const hasCapability = ctx.botCapabilities.some((i: string) => requiredIntent.toLowerCase().includes(i.toLowerCase()));
      if (!hasCapability) errors.push(`capability mismatch: '${requiredIntent}' not in bot intents`);
    }

    // 3) Verify input schema: microtask steps must have required fields
    for (const step of (m.steps || [])) {
      if (!step.action) errors.push(`step missing 'action' field`);
    }

    results.push({ microtask_id: m.id, passed: errors.length === 0, details: errors.length === 0 ? 'live pass' : errors.join('; '), errors });
  }
  return results;
}