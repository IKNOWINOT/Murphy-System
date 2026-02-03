
const mem = new Map<string,{exp:number, data:any}>();
export async function getCache(kv:any, key:string){ const now=Date.now(); const v=mem.get(key); if(v&&v.exp>now) return v.data; return null; }
export async function setCache(kv:any, key:string, data:any, ttl_s:number){ mem.set(key, {exp: Date.now()+ttl_s*1000, data}); }
