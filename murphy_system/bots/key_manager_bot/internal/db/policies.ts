
export async function upsertPolicy(db:D1Database, bot_name:string, scope:string, p:{max_calls:number, window_s:number, burst:number, tier?:string}){
  await db.prepare(`CREATE TABLE IF NOT EXISTS key_policies (bot_name TEXT, scope TEXT, max_calls INT, window_s INT, burst INT, tier TEXT, updated_ts TEXT, PRIMARY KEY(bot_name, scope))`).run();
  await db.prepare(`INSERT INTO key_policies (bot_name, scope, max_calls, window_s, burst, tier, updated_ts)
    VALUES (?1,?2,?3,?4,?5,?6,?7)
    ON CONFLICT(bot_name,scope) DO UPDATE SET max_calls=excluded.max_calls, window_s=excluded.window_s, burst=excluded.burst, tier=excluded.tier, updated_ts=excluded.updated_ts`)
    .bind(bot_name, scope, p.max_calls, p.window_s, p.burst, p.tier||null, new Date().toISOString()).run();
}
export async function getPolicy(db:D1Database, bot_name:string, scope:string){
  return await db.prepare(`SELECT * FROM key_policies WHERE bot_name=? AND scope=?`).bind(bot_name, scope).get<any>();
}
