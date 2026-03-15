
export async function upsertChunks(db:D1Database, doc_id:string, chunks:any[]){
  await db.prepare(`CREATE TABLE IF NOT EXISTS library_chunks (doc_id TEXT, chunk_id TEXT, ord INT, text TEXT, proj TEXT NULL, meta_json TEXT, PRIMARY KEY(doc_id, chunk_id))`).run();
  const stmt = await db.prepare(`INSERT OR REPLACE INTO library_chunks (doc_id,chunk_id,ord,text,proj,meta_json) VALUES (?,?,?,?,?,?)`);
  for (const c of chunks){
    await stmt.bind(doc_id, c.chunk_id, c.ord, c.text, c.proj||null, JSON.stringify(c.meta||{})).run();
  }
}
export async function getChunks(db:D1Database, doc_id:string, limit:number){
  const q = await db.prepare(`SELECT chunk_id, ord, text, proj FROM library_chunks WHERE doc_id=? ORDER BY ord ASC LIMIT ?`).bind(doc_id, limit).all<any>();
  return q.results||[];
}
export async function scanChunkSamples(db:D1Database, limit:number){
  const q = await db.prepare(`SELECT doc_id,chunk_id,text,proj FROM library_chunks ORDER BY RANDOM() LIMIT ?`).bind(limit).all<any>();
  return q.results||[];
}
