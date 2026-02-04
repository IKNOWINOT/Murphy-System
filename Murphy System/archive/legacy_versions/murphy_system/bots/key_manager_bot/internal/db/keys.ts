
export async function insertKey(db:D1Database, row:any){
  await db.prepare(`INSERT INTO api_keys (id, bot_name, scope, status, enc_dek, enc_key, key_version, created_ts, last_used_ts, usage_count, meta_json)
    VALUES (?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11)`)
    .bind(row.id, row.bot_name, row.scope, row.status, JSON.stringify(row.enc_dek), JSON.stringify(row.enc_key), row.key_version, row.created_ts, row.last_used_ts, row.usage_count, JSON.stringify(row.meta_json||{})).run();
}
export async function selectKey(db:D1Database, id:string){
  return await db.prepare(`SELECT * FROM api_keys WHERE id=?`).bind(id).get<any>();
}
export async function updateStatus(db:D1Database, id:string, status:string){
  await db.prepare(`UPDATE api_keys SET status=?, last_used_ts=? WHERE id=?`).bind(status, new Date().toISOString(), id).run();
}
export async function allocateUnassigned(db:D1Database, bot_name:string){
  const row = await db.prepare(`SELECT * FROM api_keys WHERE assigned_to IS NULL AND status='active' LIMIT 1`).get<any>();
  if (!row) return null;
  await db.prepare(`UPDATE api_keys SET assigned_to=? WHERE id=?`).bind(bot_name, row.id).run();
  return row.id;
}
export async function incrementUsage(db:D1Database, id:string){
  await db.prepare(`UPDATE api_keys SET usage_count = COALESCE(usage_count,0)+1, last_used_ts=? WHERE id=?`).bind(new Date().toISOString(), id).run();
}
