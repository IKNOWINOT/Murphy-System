
const mem = new Map<string,{count:number, ts:number, tokens:number}>();
export async function checkAndConsume(kv:any, key:string, maxCalls:number, window_s:number, burst:number){
  const now=Date.now()/1000; const rec = mem.get(key) || {count:0, ts:now, tokens:burst};
  // rolling window count
  if (now - rec.ts > window_s){ rec.ts=now; rec.count=0; rec.tokens=burst; }
  if (rec.tokens<=0 || rec.count>=maxCalls){ return {allowed:false, resetAt: (rec.ts+window_s)*1000}; }
  rec.count++; rec.tokens = Math.max(0, rec.tokens-1);
  mem.set(key, rec);
  return {allowed:true, resetAt:(rec.ts+window_s)*1000};
}
