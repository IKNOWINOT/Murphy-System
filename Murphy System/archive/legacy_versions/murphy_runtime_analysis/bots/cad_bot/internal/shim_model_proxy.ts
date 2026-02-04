// src/clockwork/bots/cad_bot/internal/shim_model_proxy.ts
type Msg = { role: 'system'|'user'|'assistant'; content: string };
export async function callModel(args: { profile: 'mini'|'turbo'; messages: Msg[]; json?: boolean; maxTokens?: number }) {
  const user = args.messages.find(m => m.role === 'user')?.content || '{}';
  let input: any = {}; try { input = JSON.parse(user).input || {}; } catch {}
  const units = (input.params?.units || 'mm');
  const base = String(input.task || 'CAD spec').slice(0, 240).toLowerCase();

  // Simple heuristic -> choose entities
  const entities: any[] = [];
  if (base.includes('box') || base.includes('cube')) { entities.push({ type:'box', params:{ w: 10, h: 10, d: 10, fillet: 0 } }); }
  if (base.includes('cylinder')) { entities.push({ type:'cylinder', params:{ r: 5, h: 20 } }); }
  if (base.includes('plate') || entities.length===0) { entities.push({ type:'box', params:{ w: 100, h: 5, d: 100 } }); }

  const result = {
    cad_spec: { entities, units }
  };
  return { result, usage: { tokens_in: 180, tokens_out: 160, cost_usd: args.profile==='turbo' ? 0.009 : 0.0025, model: args.profile } };
}
