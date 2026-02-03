// src/clockwork/bots/bot_base/internal/shim_budget.ts
const mem = new Map<string,{free_pool_cents:number,updated_ts:string}>();
function monthUTC(d=new Date()){ return `${d.getUTCFullYear()}-${String(d.getUTCMonth()+1).padStart(2,'0')}`; }
export async function budgetGuard(db: any|undefined, tierRaw:string, opts?:{month?:string}){
  const tier=(tierRaw||'free_na').toLowerCase(); const requires=(tier==='free_na'||tier==='free'||tier==='starter'); const month=opts?.month||monthUTC();
  if (!requires) return {allowed:true, month, free_pool_cents:Number.POSITIVE_INFINITY};
  if (db){ const row=await db.prepare('SELECT free_pool_cents FROM budgets WHERE month=?').bind(month).get(); if (!row){ await db.prepare('INSERT INTO budgets (month, founder_cap_cents, reinvest_pct, free_pool_cents, updated_ts) VALUES (?, ?, ?, ?, ?)').bind(month,45000,0.5,45000,new Date().toISOString()).run(); return {allowed:true, month, free_pool_cents:45000}; } return {allowed: row.free_pool_cents>0, month, free_pool_cents: row.free_pool_cents}; }
  const r=mem.get(month)||{free_pool_cents:45000,updated_ts:new Date().toISOString()}; mem.set(month,r); return {allowed:r.free_pool_cents>0, month, free_pool_cents:r.free_pool_cents};
}
export async function chargeCost(db:any|undefined, args:{amount_cents:number, month?:string, tier:string}){
  const tier=(args.tier||'free_na').toLowerCase(); const requires=(tier==='free_na'||tier==='free'||tier==='starter'); if (!requires) return;
  const month=args.month||monthUTC();
  if (db){ await db.prepare('UPDATE budgets SET free_pool_cents = free_pool_cents - ?, updated_ts=? WHERE month=? AND free_pool_cents >= ?').bind(args.amount_cents, new Date().toISOString(), month, args.amount_cents).run(); return; }
  const r=mem.get(month)||{free_pool_cents:45000,updated_ts:new Date().toISOString()}; if (r.free_pool_cents>=args.amount_cents){ r.free_pool_cents-=args.amount_cents; r.updated_ts=new Date().toISOString(); mem.set(month,r); }
}
