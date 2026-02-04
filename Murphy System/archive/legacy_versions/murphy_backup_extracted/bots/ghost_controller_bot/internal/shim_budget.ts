
const mem=new Map<string,{free:number,ts:string}>();
function mUTC(d=new Date()){return`${d.getUTCFullYear()}-${String(d.getUTCMonth()+1).padStart(2,'0')}`}
export async function budgetGuard(db:any,tierRaw:string,o?:{month?:string}){
  const tier=(tierRaw||'free_na').toLowerCase(); const req=(tier==='free_na'||tier==='free'||tier==='starter'); const month=o?.month||mUTC();
  if(!req) return {allowed:true, month, free_pool_cents:Infinity};
  if(db){ const row=await db.prepare('SELECT free_pool_cents FROM budgets WHERE month = ?').bind(month).get();
    if(!row){ await db.prepare('INSERT INTO budgets (month, founder_cap_cents, reinvest_pct, free_pool_cents, updated_ts) VALUES (?,?,?,?,?)').bind(month,45000,0.5,45000,new Date().toISOString()).run(); return {allowed:true,month,free_pool_cents:45000}; }
    return {allowed: row.free_pool_cents>0, month, free_pool_cents: row.free_pool_cents};
  }
  const r=mem.get(month)||{free:45000,ts:new Date().toISOString()}; mem.set(month,r); return {allowed:r.free>0,month,free_pool_cents:r.free};
}
export async function chargeCost(db:any,args:{amount_cents:number,month?:string,tier:string}){
  const month=args.month||mUTC(); const tier=(args.tier||'free_na').toLowerCase(); const req=(tier==='free_na'||tier==='free'||tier==='starter'); if(!req) return;
  if(db){ await db.prepare('UPDATE budgets SET free_pool_cents = free_pool_cents - ?, updated_ts=? WHERE month=? AND free_pool_cents >= ?').bind(args.amount_cents,new Date().toISOString(),month,args.amount_cents).run(); return; }
  const r=mem.get(month)||{free:45000,ts:new Date().toISOString()}; if(r.free>=args.amount_cents){ r.free-=args.amount_cents; r.ts=new Date().toISOString(); mem.set(month,r); }
}
