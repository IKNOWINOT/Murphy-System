
export type QuotaResult={allowed:boolean,remaining:number|typeof Infinity,max:number|typeof Infinity,resetAt:number,throttled?:boolean};
function hb(ms:number){const s=Math.floor(ms/3600000)*3600000;return{start:s,end:s+3600000}}
const mem=new Map<string,{c:number,exp:number}>();
export async function checkQuota(kv:any,u:string,tierRaw:string):Promise<QuotaResult>{
  const tier=(tierRaw||'free_na').toLowerCase();
  const pol=tier==='free_na'?{m:15,s:10}:tier==='free'?{m:30,s:20}:tier==='starter'?{m:30,s:25}:tier==='pro'?{m:120,s:200}:{m:Infinity,s:Infinity};
  if(pol.m===Infinity)return{allowed:true,remaining:Infinity,max:Infinity,resetAt:Date.now()+3600000};
  const now=Date.now(); const{start,end}=hb(now); const k=`quota:${tier}:${u}:${start}`; const ttl=Math.max(1,Math.floor((end-now)/1000));
  if(kv){ const raw=await kv.get(k); let c=0; try{c=raw?JSON.parse(raw).count||0:0}catch{} c++; await kv.put(k,JSON.stringify({count:c}),{expirationTtl:ttl}); const a=c<=pol.m; return{allowed:a,remaining:a?Math.max(0,pol.m-c):0,max:pol.m,resetAt:end,throttled:a&&c>pol.s};}
  const r=mem.get(k); let c=0; if(r&&r.exp>now)c=r.c; c++; mem.set(k,{c,exp:now+ttl*1000}); const a=c<=pol.m; return{allowed:a,remaining:a?Math.max(0,pol.m-c):0,max:pol.m,resetAt:end,throttled:a&&c>pol.s};
}
