// src/clockwork/bots/optimizer_core_bot/internal/shim_quota.ts
export type QuotaResult = { allowed: boolean; remaining: number|typeof Infinity; max: number|typeof Infinity; resetAt: number; throttled?: boolean; };
function hourBucket(ms:number){ const s=Math.floor(ms/3600000)*3600000; return {start:s, end:s+3600000}; }
const mem = new Map<string,{count:number,exp:number}>();
export async function checkQuota(kv: {get:(k:string)=>Promise<string|null>,put:(k:string,v:string,o?:{expirationTtl?:number})=>Promise<void>}|undefined, userId:string, tierRaw:string): Promise<QuotaResult>{
  const tier=(tierRaw||'free_na').toLowerCase();
  const policy = tier==='free_na'?{max:15,slow:10}: tier==='free'?{max:30,slow:20}: tier==='starter'?{max:30,slow:25}: tier==='pro'?{max:120,slow:200}:{max:Infinity,slow:Infinity};
  if (policy.max===Infinity) return {allowed:true, remaining:Infinity, max:Infinity, resetAt:Date.now()+3600000};
  const now=Date.now(); const {start,end}=hourBucket(now); const key=`quota:${tier}:${userId}:${start}`; const ttl=Math.max(1, Math.floor((end-now)/1000));
  if (kv){ const raw=await kv.get(key); let c=0; try{ c=raw?JSON.parse(raw).count||0:0 }catch{} c+=1; await kv.put(key, JSON.stringify({count:c}), {expirationTtl:ttl}); const allowed=c<=policy.max; return {allowed, remaining: allowed?Math.max(0,policy.max-c):0, max:policy.max, resetAt:end, throttled: allowed && c>policy.slow}; }
  const r=mem.get(key); let c=0; if (r && r.exp>now) c=r.count; c+=1; mem.set(key, {count:c, exp: now+ttl*1000}); const allowed=c<=policy.max; return {allowed, remaining: allowed?Math.max(0,policy.max-c):0, max:policy.max, resetAt:end, throttled: allowed && c>policy.slow};
}
