// src/clockwork/bots/goldenpath_generator/internal/shim_model_proxy.ts
type Msg = { role: 'system'|'user'|'assistant'; content: string };
export async function callModel(args: { profile: 'mini'|'turbo'; messages: Msg[]; json?: boolean; maxTokens?: number }) {
  const user = args.messages.find(m => m.role === 'user')?.content || '{}';
  let input: any = {}; try { input = JSON.parse(user).input || {}; } catch {}
  const base = String(input.task || 'perform task').slice(0, 120);
  const verbs = ['upload','create','send','schedule','draft','convert'];
  const steps = verbs.filter(v => base.toLowerCase().includes(v)).slice(0,3);
  const tasks = (steps.length?steps:['upload']).slice(0,3).map((v,i)=>({ id:`t${i+1}`, title:`${v} — ${base}`, requires: v==='upload'?['drive_api_token']: v==='send'?['smtp_credentials']:[], est_time_min:2+i }));
  const result = { chain_id:`gp_${Date.now()}`, level:Math.min(3,tasks.length), tasks, confidence:0.78 };
  return { result, usage: { tokens_in: 200, tokens_out: 150, cost_usd: args.profile==='turbo'?0.008:0.002, model: args.profile } };
}
