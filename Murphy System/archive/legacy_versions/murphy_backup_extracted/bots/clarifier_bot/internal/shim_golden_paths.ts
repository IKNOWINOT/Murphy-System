// src/clockwork/bots/clarifier_bot/internal/shim_golden_paths.ts
type TaskKey = { task_type:string; params_preview?:string; software_signature_preview?:string; [k:string]:any };
type SelectPath = { id:string; spec:any; confidence:number; runs:number; pass_rate:number };
const mem = new Map<string, SelectPath>();
function canonicalKey(key: TaskKey): string {
  const sorter=(o:any):any => (o && typeof o==='object' && !Array.isArray(o)) ? Object.keys(o).sort().reduce((a:any,k)=>{a[k]=sorter(o[k]);return a;},{}) : Array.isArray(o)?o.map(sorter):o;
  return JSON.stringify(sorter(key));
}
export async function selectPath(_db: any|undefined, key: TaskKey, _budgetTokens=1): Promise<SelectPath|null>{
  const k = `${key.task_type}:${canonicalKey(key)}`;
  const row = mem.get(k) || null;
  if (!row) return null;
  let conf = row.confidence;
  if (row.runs>=20 && row.pass_rate>=0.9) conf = Math.max(conf, 0.95);
  if (row.runs>=5 && row.pass_rate<0.8) conf = Math.min(conf, 0.6);
  return { ...row, confidence: conf };
}
export async function recordPath(_db:any|undefined, args:{ task_type:string; key:TaskKey; success:boolean; confidence:number; spec:any }){
  const k = `${args.task_type}:${canonicalKey(args.key)}`;
  const existing = mem.get(k);
  if (!existing){
    mem.set(k, { id:`gp_${Date.now()}`, spec: args.spec, confidence: Math.max(0,Math.min(1,args.confidence)), runs:1, pass_rate: args.success?1:0 });
  } else {
    const runs = existing.runs + 1;
    const pass_rate = ((existing.pass_rate * existing.runs) + (args.success?1:0))/runs;
    let conf = Math.max(0,Math.min(1, (existing.confidence*0.7) + (Math.max(0,Math.min(1,args.confidence))*0.3) ));
    if (runs>=20 && pass_rate>=0.9) conf = Math.max(conf, 0.95);
    if (runs>=5 && pass_rate<0.8) conf = Math.min(conf, 0.6);
    mem.set(k, { id: existing.id, spec: args.spec, confidence: conf, runs, pass_rate });
  }
}
