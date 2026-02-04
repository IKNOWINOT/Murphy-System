
export async function upsertEntry(db:D1Database, row:any){
  await db.prepare(`CREATE TABLE IF NOT EXISTS mem_entries (id TEXT PRIMARY KEY, tenant TEXT, text TEXT, trust REAL, last_accessed TEXT, access_count INT, status TEXT, ttl_seconds INT, compressed INT, enc INT, meta_json TEXT, created_ts TEXT, updated_ts TEXT)`).run();
  await db.prepare(`INSERT INTO mem_entries (id,tenant,text,trust,last_accessed,access_count,status,ttl_seconds,compressed,enc,meta_json,created_ts,updated_ts)
    VALUES (?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,?12,?13)
    ON CONFLICT(id) DO UPDATE SET text=excluded.text, trust=excluded.trust, updated_ts=excluded.updated_ts, status=excluded.status, access_count=excluded.access_count`)
    .bind(row.id,row.tenant,row.text,row.trust,row.last_accessed,row.access_count,row.status||'active',row.ttl_seconds||0,row.compressed||0,row.enc||0,JSON.stringify(row.meta||{}),row.created_ts,row.updated_ts).run();
}
export async function getEntry(db:D1Database, id:string){
  return await db.prepare(`SELECT * FROM mem_entries WHERE id=?`).bind(id).get<any>();
}
export async function softDelete(db:D1Database, id:string){
  await db.prepare(`UPDATE mem_entries SET status='deleted', updated_ts=? WHERE id=?`).bind(new Date().toISOString(), id).run();
}
export async function scanTenant(db:D1Database, tenant:string, limit:number){
  const q = await db.prepare(`SELECT id,text,trust,last_accessed,access_count,meta_json FROM mem_entries WHERE tenant=? AND status='active' ORDER BY updated_ts DESC LIMIT ?`).bind(tenant, limit).all<any>();
  return q.results||[];
}
export async function updateAccess(db:D1Database, id:string){
  await db.prepare(`UPDATE mem_entries SET access_count=COALESCE(access_count,0)+1, last_accessed=? WHERE id=?`).bind(new Date().toISOString(), id).run();
}
