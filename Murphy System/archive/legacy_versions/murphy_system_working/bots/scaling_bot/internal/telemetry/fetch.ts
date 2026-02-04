
export async function fetchTelemetry(ctx:any, tenant:string, bot_type:string){
  // Option A: external metrics endpoint
  const url = ctx?.env?.TELEMETRY_URL;
  if (url){
    try{
      const r = await fetch(`${url}?tenant=${encodeURIComponent(tenant)}&bot=${encodeURIComponent(bot_type)}`);
      if (r.ok){
        const j = await r.json();
        return j;
      }
    }catch{}
  }
  // Option B: D1 snapshots (latest)
  try{
    await ctx.db.prepare(`CREATE TABLE IF NOT EXISTS scaling_snapshots (
      id TEXT PRIMARY KEY, ts TEXT, tenant TEXT, bot_type TEXT,
      queue_depth INT, arrival_rate REAL, service_time REAL,
      p50 REAL, p95 REAL, error_rate REAL, cpu REAL, mem REAL,
      replicas INT, cost_usd_per_run REAL
    )`).run();
    const row:any = await ctx.db.prepare(`SELECT * FROM scaling_snapshots WHERE tenant=? AND bot_type=? ORDER BY ts DESC LIMIT 1`).bind(tenant, bot_type).get();
    if (row) return row;
  }catch{}
  // Fallback defaults
  return { queue_depth:0, arrival_rate:0.1, service_time:0.05, p50:200, p95:400, error_rate:0.005, cpu:40, mem:50, replicas:1, cost_usd_per_run:0.0005 };
}
