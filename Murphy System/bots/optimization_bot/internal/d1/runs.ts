
export async function logRun(db:D1Database, row:any){
  await db.prepare(`CREATE TABLE IF NOT EXISTS opt_runs (id TEXT PRIMARY KEY, exp_id TEXT, arm_id TEXT, ts TEXT, ctx_json TEXT, reward REAL, metrics_json TEXT, passed INT, tokens_in INT, tokens_out INT, cost_cents INT, latency_ms INT)`).run();
  await db.prepare(`INSERT INTO opt_runs (id,exp_id,arm_id,ts,ctx_json,reward,metrics_json,passed,tokens_in,tokens_out,cost_cents,latency_ms) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)`)
    .bind(row.id,row.exp_id,row.arm_id,row.ts,JSON.stringify(row.ctx||{}),row.reward||0,JSON.stringify(row.metrics||{}),row.passed?1:0,row.tokens_in||0,row.tokens_out||0,row.cost_cents||0,row.latency_ms||0).run();
}
