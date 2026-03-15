
export async function create(db:D1Database, row:any){
  await db.prepare(`CREATE TABLE IF NOT EXISTS opt_experiments (id TEXT PRIMARY KEY, ts_created TEXT, owner TEXT, target_bot TEXT, area TEXT, hypothesis TEXT, method TEXT, status TEXT, params_json TEXT, guardrails_json TEXT, primary_metric TEXT, secondary_metrics_json TEXT)`).run();
  await db.prepare(`INSERT INTO opt_experiments (id,ts_created,owner,target_bot,area,hypothesis,method,status,params_json,guardrails_json,primary_metric,secondary_metrics_json)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)`).bind(row.id,row.ts_created,row.owner,row.target_bot,row.area,row.hypothesis,row.method,row.status,JSON.stringify(row.params||{}),JSON.stringify(row.guardrails||{}),row.primary_metric||'pass_rate',JSON.stringify(row.secondary_metrics||[])).run();
}
export async function get(db:D1Database, id:string){ return await db.prepare(`SELECT * FROM opt_experiments WHERE id=?`).bind(id).get<any>(); }
export async function setStatus(db:D1Database, id:string, status:string){ await db.prepare(`UPDATE opt_experiments SET status=? WHERE id=?`).bind(status,id).run(); }
