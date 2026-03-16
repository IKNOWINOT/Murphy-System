
export async function savePolicy(db:D1Database, row:any){
  await db.prepare(`CREATE TABLE IF NOT EXISTS scaling_policies (
    id TEXT PRIMARY KEY, tenant TEXT, bot_type TEXT,
    slo_json TEXT, limits_json TEXT, cost_cap_cents INT, cooldown_s INT, headroom REAL,
    created_ts TEXT, updated_ts TEXT
  )`).run();
  const id = row.id || `pol_${Date.now()}`;
  await db.prepare(`INSERT OR REPLACE INTO scaling_policies
    (id, tenant, bot_type, slo_json, limits_json, cost_cap_cents, cooldown_s, headroom, created_ts, updated_ts)
    VALUES (?,?,?,?,?,?,?,?,COALESCE((SELECT created_ts FROM scaling_policies WHERE id=?),?),?)`)
    .bind(id, row.tenant, row.bot_type, JSON.stringify(row.slo||{}), JSON.stringify(row.limits||{}),
          Math.round((row.cost_cap_usd||100)*100), row.cooldown_s||120, row.headroom||0.3,
          new Date().toISOString(), id, new Date().toISOString(), new Date().toISOString()).run();
  return { id };
}
export async function getPolicy(db:D1Database, tenant:string, bot_type:string){
  await db.prepare(`CREATE TABLE IF NOT EXISTS scaling_policies (
    id TEXT PRIMARY KEY, tenant TEXT, bot_type TEXT,
    slo_json TEXT, limits_json TEXT, cost_cap_cents INT, cooldown_s INT, headroom REAL,
    created_ts TEXT, updated_ts TEXT
  )`).run();
  const row:any = await db.prepare(`SELECT * FROM scaling_policies WHERE tenant=? AND bot_type=? ORDER BY updated_ts DESC LIMIT 1`).bind(tenant, bot_type).get();
  if (!row) return null;
  return {
    id: row.id,
    tenant: row.tenant,
    bot_type: row.bot_type,
    slo: JSON.parse(row.slo_json||'{}'),
    limits: JSON.parse(row.limits_json||'{}'),
    cost_cap_usd: (row.cost_cap_cents||0)/100,
    cooldown_s: row.cooldown_s,
    headroom: row.headroom,
    updated_ts: row.updated_ts
  };
}
export async function logEvent(db:D1Database, row:any){
  await db.prepare(`CREATE TABLE IF NOT EXISTS scaling_events (
    id TEXT PRIMARY KEY, ts TEXT, tenant TEXT, bot_type TEXT,
    action TEXT, from_n INT, to_n INT, reason TEXT, meta_json TEXT
  )`).run();
  const id = `evt_${Date.now()}`;
  await db.prepare(`INSERT INTO scaling_events (id, ts, tenant, bot_type, action, from_n, to_n, reason, meta_json)
    VALUES (?,?,?,?,?,?,?,?,?)`)
    .bind(id, row.ts||new Date().toISOString(), row.tenant, row.bot_type, row.action, row.from_n||0, row.to_n||0, row.reason||'', JSON.stringify(row.meta||{})).run();
  return true;
}
export async function saveSnapshot(db:D1Database, row:any){
  await db.prepare(`CREATE TABLE IF NOT EXISTS scaling_snapshots (
    id TEXT PRIMARY KEY, ts TEXT, tenant TEXT, bot_type TEXT,
    queue_depth INT, arrival_rate REAL, service_time REAL,
    p50 REAL, p95 REAL, error_rate REAL, cpu REAL, mem REAL,
    replicas INT, cost_usd_per_run REAL
  )`).run();
  const id = `snap_${Date.now()}`;
  await db.prepare(`INSERT INTO scaling_snapshots (id, ts, tenant, bot_type, queue_depth, arrival_rate, service_time, p50, p95, error_rate, cpu, mem, replicas, cost_usd_per_run)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)`)
    .bind(id, row.ts||new Date().toISOString(), row.tenant, row.bot_type, row.queue_depth||0, row.arrival_rate||0, row.service_time||0, row.p50||0, row.p95||0, row.error_rate||0, row.cpu||0, row.mem||0, row.replicas||0, row.cost_usd_per_run||0).run();
  return true;
}
