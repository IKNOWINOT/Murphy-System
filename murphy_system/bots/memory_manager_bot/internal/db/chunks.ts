
export async function upsertChunks(db:D1Database, mem_id:string, chunks:any[]){
  await db.prepare(`CREATE TABLE IF NOT EXISTS mem_chunks (mem_id TEXT, chunk_id TEXT, ord INT, text TEXT, proj TEXT, meta_json TEXT, PRIMARY KEY(mem_id, chunk_id))`).run();
  const stmt = await db.prepare(`INSERT OR REPLACE INTO mem_chunks (mem_id,chunk_id,ord,text,proj,meta_json) VALUES (?,?,?,?,?,?)`);
  for (const c of chunks){ await stmt.bind(mem_id, c.chunk_id, c.ord, c.text, c.proj||null, JSON.stringify(c.meta||{})).run(); }
}
export async function getChunks(db:D1Database, mem_id:string, limit:number){
  const q = await db.prepare(`SELECT chunk_id,ord,text,proj FROM mem_chunks WHERE mem_id=? ORDER BY ord ASC LIMIT ?`).bind(mem_id, limit).all<any>();
  return q.results||[];
}
export async function scanSamples(db:D1Database, tenant:string, limit:number){
  const q = await db.prepare(`SELECT c.mem_id,c.chunk_id,c.text,c.proj,e.trust,e.last_accessed,e.access_count FROM mem_chunks c JOIN mem_entries e ON e.id=c.mem_id WHERE e.tenant=? AND e.status='active' ORDER BY RANDOM() LIMIT ?`).bind(tenant, limit).all<any>();
  return q.results||[];
}
