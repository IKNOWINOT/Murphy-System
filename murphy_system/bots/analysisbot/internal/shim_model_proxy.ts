// src/clockwork/bots/analysisbot/internal/shim_model_proxy.ts
type Msg = { role: 'system'|'user'|'assistant'; content: string };
export async function callModel(args: { profile: 'mini'|'turbo'; messages: Msg[]; json?: boolean; maxTokens?: number }) {
  const user = args.messages.find(m => m.role === 'user')?.content || '{}';
  let input: any = {}; try { input = JSON.parse(user).input || {}; } catch {}
  const base = String(input.task || 'analysis task').slice(0, 140);
  const verbs = ['analyze','assess','compare','risk','impact','validate','benchmark','audit','recommend'];
  const steps = verbs.filter(v => base.toLowerCase().includes(v)).slice(0,3);
  const use = steps.length ? steps : ['analyze','assess','recommend'].slice(0,3);
  const tasks = use.map((v,i)=>({ id:`t${i+1}`, title:`${v} — ${base}`, requires: [], est_time_min: 3+i }));
  const result = { chain_id:`analysis_gp_${Date.now()}`, level: Math.min(3,tasks.length), tasks, confidence: 0.82 };
  return { result, usage: { tokens_in: 220, tokens_out: 160, cost_usd: args.profile==='turbo' ? 0.009 : 0.0025, model: args.profile } };
}
