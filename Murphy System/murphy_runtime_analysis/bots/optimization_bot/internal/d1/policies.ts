
export async function setPolicy(db:D1Database, target_bot:string, policy:any){
  await db.prepare(`CREATE TABLE IF NOT EXISTS opt_policies (target_bot TEXT PRIMARY KEY, policy_json TEXT, updated_ts TEXT)`).run();
  await db.prepare(`INSERT OR REPLACE INTO opt_policies (target_bot,policy_json,updated_ts) VALUES (?,?,?)`).bind(target_bot, JSON.stringify(policy||{}), new Date().toISOString()).run();
}
export async function getPolicy(db:D1Database, target_bot:string){
  await db.prepare(`CREATE TABLE IF NOT EXISTS opt_policies (target_bot TEXT PRIMARY KEY, policy_json TEXT, updated_ts TEXT)`).run();
  const q = await db.prepare(`SELECT policy_json FROM opt_policies WHERE target_bot=?`).bind(target_bot).get<any>();
  return q ? JSON.parse(q.policy_json||'{}') : null;
}
