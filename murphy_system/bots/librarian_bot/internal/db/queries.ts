
export async function logQuery(db:D1Database, user_id_hash:string, query:string, tags:string[], results:any[], latency_ms:number){
  await db.prepare(`CREATE TABLE IF NOT EXISTS library_queries (id TEXT PRIMARY KEY, user_id_hash TEXT, query TEXT, tags_json TEXT, ts TEXT, results_json TEXT, latency_ms INT, clicks INT DEFAULT 0)`).run();
  await db.prepare(`INSERT INTO library_queries (id,user_id_hash,query,tags_json,ts,results_json,latency_ms) VALUES (?,?,?,?,?,?,?)`)
    .bind('lq_'+Date.now(), user_id_hash, query, JSON.stringify(tags||[]), new Date().toISOString(), JSON.stringify(results||[]), latency_ms).run();
}
export async function topFrequentQueries(db:D1Database, windowHours:number){
  const cutoff = new Date(Date.now()-windowHours*3600*1000).toISOString();
  const q = await db.prepare(`SELECT query, tags_json, COUNT(*) as c FROM library_queries WHERE ts>=? GROUP BY query, tags_json HAVING c>=3 ORDER BY c DESC LIMIT 10`).bind(cutoff).all<any>();
  return q.results||[];
}
