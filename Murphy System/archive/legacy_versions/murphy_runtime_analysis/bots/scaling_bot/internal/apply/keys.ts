
export async function allocateKey(ctx:any, tenant:string, bot_type:string){
  const db = ctx.db as D1Database;
  await db.prepare(`CREATE TABLE IF NOT EXISTS scaling_instances (
    id TEXT PRIMARY KEY, tenant TEXT, bot_type TEXT, key_id TEXT, status TEXT, ts TEXT
  )`).run();
  // Find an active key not in use
  try{
    // api_keys table from key_manager_bot
    const row:any = await db.prepare(`SELECT id AS key_id FROM api_keys
      WHERE status='active' AND id NOT IN (SELECT key_id FROM scaling_instances WHERE status='active')
      ORDER BY created_ts ASC LIMIT 1`).get();
    const key_id = row?.key_id || null;
    if (!key_id) return null;
    const id = `inst_${Date.now()}`;
    await db.prepare(`INSERT INTO scaling_instances (id, tenant, bot_type, key_id, status, ts) VALUES (?,?,?,?,?,?)`)
      .bind(id, tenant, bot_type, key_id, 'active', new Date().toISOString()).run();
    return key_id;
  }catch(e){ return null; }
}
export async function revokeKey(ctx:any, tenant:string, bot_type:string){
  const db = ctx.db as D1Database;
  await db.prepare(`CREATE TABLE IF NOT EXISTS scaling_instances (
    id TEXT PRIMARY KEY, tenant TEXT, bot_type TEXT, key_id TEXT, status TEXT, ts TEXT
  )`).run();
  const row:any = await db.prepare(`SELECT id,key_id FROM scaling_instances WHERE tenant=? AND bot_type=? AND status='active' ORDER BY ts DESC LIMIT 1`).bind(tenant, bot_type).get();
  if (!row) return false;
  await db.prepare(`UPDATE scaling_instances SET status='released', ts=? WHERE id=?`).bind(new Date().toISOString(), row.id).run();
  return true;
}
