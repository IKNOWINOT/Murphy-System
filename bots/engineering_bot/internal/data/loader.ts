
export async function loadJSON(key: string, ctx?: { db?: any; kv?: any; logger?: { warn?: Function } }): Promise<Record<string, any>> {
  // 1. Try D1
  if (ctx?.db) {
    try {
      const row: any = await ctx.db.prepare('SELECT value FROM engineering_data WHERE key = ?').bind(key).first();
      if (row?.value) {
        try {
          return JSON.parse(row.value);
        } catch {
          ctx.logger?.warn?.(`loadJSON: malformed JSON in D1 for key '${key}'`);
          return {};
        }
      }
    } catch {
      ctx.logger?.warn?.(`loadJSON: D1 query failed for key '${key}'`);
    }
  }

  // 2. Try KV namespace
  if (ctx?.kv) {
    try {
      const raw = await ctx.kv.get(key);
      if (raw) {
        try {
          return JSON.parse(raw);
        } catch {
          ctx.logger?.warn?.(`loadJSON: malformed JSON in KV for key '${key}'`);
          return {};
        }
      }
    } catch {
      ctx.logger?.warn?.(`loadJSON: KV lookup failed for key '${key}'`);
    }
  }

  // 3. Neither available or key not found
  ctx?.logger?.warn?.(`loadJSON: no data found for key '${key}'`);
  return {};
}
