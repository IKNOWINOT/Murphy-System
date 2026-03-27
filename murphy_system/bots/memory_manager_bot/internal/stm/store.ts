
const mem = new Map<string,{exp:number, payload:any}>();
export async function storeSTM(kv:any, tenant:string, task_id:string, payload:any, ttl_s:number){
  mem.set(`${tenant}:${task_id}`, { exp: Date.now()+ttl_s*1000, payload });
}
export async function flushSTM(kv:any, tenant:string){
  const now=Date.now(); let flushed=0; for (const [k,v] of mem){
    if (!k.startsWith(tenant+':')) continue;
    if (v.exp<=now){ flushed++; mem.delete(k); }
  } return flushed;
}
