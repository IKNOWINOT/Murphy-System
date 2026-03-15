
export async function upsertDoc(db:D1Database, row:any){
  await db.prepare(`CREATE TABLE IF NOT EXISTS library_docs (id TEXT PRIMARY KEY, title TEXT, source_bot TEXT, task_id TEXT, tags_json TEXT, created_ts TEXT, updated_ts TEXT, size_bytes INT, popularity INT, content_uri TEXT, meta_json TEXT)`).run();
  await db.prepare(`INSERT INTO library_docs (id,title,source_bot,task_id,tags_json,created_ts,updated_ts,size_bytes,popularity,content_uri,meta_json)
    VALUES (?1,?2,?3,?4,?5,?6,?7,?8,COALESCE(?9,0),?10,?11)
    ON CONFLICT(id) DO UPDATE SET title=excluded.title, tags_json=excluded.tags_json, updated_ts=excluded.updated_ts, size_bytes=excluded.size_bytes, content_uri=excluded.content_uri, meta_json=excluded.meta_json`)
    .bind(row.id,row.title||'',row.source_bot||null,row.task_id||null,JSON.stringify(row.tags||[]),row.created_ts,row.updated_ts,row.size_bytes||0,row.popularity||0,row.content_uri||null,JSON.stringify(row.meta||{})).run();
}
export async function getDoc(db:D1Database, id:string){
  return await db.prepare(`SELECT * FROM library_docs WHERE id=?`).bind(id).get<any>();
}
export async function updatePopularity(db:D1Database, id:string, inc:number){
  await db.prepare(`UPDATE library_docs SET popularity = COALESCE(popularity,0)+? WHERE id=?`).bind(inc,id).run();
}
export async function scanByTags(db:D1Database, tags:string[], limit:number){
  const like = tags.map(()=>`tags_json LIKE ?`).join(' AND ');
  const args = tags.map(t=>`%${t}%`);
  const q = await db.prepare(`SELECT id,title,tags_json,content_uri,meta_json,updated_ts FROM library_docs ${tags.length? 'WHERE '+like: ''} ORDER BY updated_ts DESC LIMIT ?`).bind(...args, limit).all<any>();
  return q.results || [];
}
export async function listAllTags(db:D1Database){
  const q = await db.prepare(`SELECT tags_json FROM library_docs`).all<any>();
  const counts = new Map<string, number>();
  for (const r of (q.results||[])){ try{ for (const t of JSON.parse(r.tags_json||'[]')){ counts.set(t, (counts.get(t)||0)+1); } }catch{} }
  return [...counts.entries()].sort((a,b)=>b[1]-a[1]).map(([value,count])=>({value, count}));
}
