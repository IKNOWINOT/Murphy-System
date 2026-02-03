
export async function upsertArms(db:D1Database, exp_id:string, arms:any[]){
  await db.prepare(`CREATE TABLE IF NOT EXISTS opt_arms (exp_id TEXT, arm_id TEXT, spec_json TEXT, prior_alpha REAL, prior_beta REAL, weight REAL, status TEXT, PRIMARY KEY(exp_id,arm_id))`).run();
  for (const a of arms){
    await db.prepare(`INSERT OR REPLACE INTO opt_arms (exp_id,arm_id,spec_json,prior_alpha,prior_beta,weight,status) VALUES (?,?,?,?,?,?,?)`)
      .bind(exp_id, a.arm_id, JSON.stringify(a.spec||{}), a.prior_alpha||1, a.prior_beta||1, a.weight||0.5, a.status||'active').run();
  }
}
export async function listArms(db:D1Database, exp_id:string){
  const q = await db.prepare(`SELECT * FROM opt_arms WHERE exp_id=?`).bind(exp_id).all<any>();
  return q.results||[];
}
export async function updatePosterior(db:D1Database, exp_id:string, arm_id:string, reward:number){
  const row:any = await db.prepare(`SELECT prior_alpha, prior_beta FROM opt_arms WHERE exp_id=? AND arm_id=?`).bind(exp_id, arm_id).get<any>();
  if (!row) return;
  const a = (row.prior_alpha||1) + (reward>0 ? 1:0);
  const b = (row.prior_beta||1) + (reward<=0 ? 1:0);
  await db.prepare(`UPDATE opt_arms SET prior_alpha=?, prior_beta=? WHERE exp_id=? AND arm_id=?`).bind(a,b,exp_id,arm_id).run();
}
