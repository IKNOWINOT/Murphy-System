// model proxy (local shim) — kiren
type Msg = { role: 'system'|'user'|'assistant'; content: string };
export async function callModel(args: { profile: 'mini'|'turbo'; messages: Msg[]; json?: boolean; maxTokens?: number }) {
  const user = args.messages.find(m => m.role === 'user')?.content || '{}';
  let input: any = {}; try { input = JSON.parse(user).input || {}; } catch {}
  const base = String(input.task || 'kiren task').slice(0, 120);
  const verbs = ['plan', 'create', 'synthesize', 'draft', 'generate'];
  const steps = verbs.filter(v => base.toLowerCase().includes(v)).slice(0,3);
  const use = steps.length?steps:verbs.slice(0,3);
  const tasks = use.map((v,i)=>({ id:`t${i+1}`, title:`${v} — ${base}`, requires: [], est_time_min:2+i }));
  const result = { chain_id:`kiren_gp_${Date.now()}`, level:Math.min(3,tasks.length), tasks, confidence:0.8 };
  return { result, usage: { tokens_in: 180, tokens_out: 140, cost_usd: args.profile==='turbo'?0.008:0.002, model: args.profile } };
}
