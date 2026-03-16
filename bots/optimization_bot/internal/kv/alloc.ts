
const mem = new Map<string, any>();
export async function getAlloc(kv:any, exp_id:string){ return mem.get(exp_id)||null; }
export async function setAlloc(kv:any, exp_id:string, alloc:any){ mem.set(exp_id, alloc); }
