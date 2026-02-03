// src/clockwork/bots/optimizer_core_bot/internal/shim_model_proxy.ts
type Msg = { role: 'system'|'user'|'assistant'; content: string };
export async function callModel(args: { profile: 'mini'|'turbo'; messages: Msg[]; json?: boolean; maxTokens?: number }) {
  const user = args.messages.find(m => m.role === 'user')?.content || '{}';
  let payload: any = {}; try { payload = JSON.parse(user); } catch {}
  const spec = payload?.input?.params?.spec || payload?.input?.spec || null;
  const objective = payload?.input?.params?.objective || payload?.input?.objective || 'minimize loss';

  // Construct a normalized core spec (toy logic for dev)
  const core_spec = {
    objective,
    direction: 'minimize',
    metric: 'loss',
    variables: [
      { name: 'lr',   kind: 'float', domain: { min: 1e-5, max: 1e-1 }, init: 1e-3 },
      { name: 'beta', kind: 'float', domain: { min: 0.7,  max: 0.999 }, init: 0.9 },
      { name: 'depth',kind: 'int',   domain: { min: 2,    max: 16 },    init: 6 }
    ],
    constraints: [],
    algorithm: 'bayes',
    stop: { max_evals: 50 }
  };
  const initial_points = [{ lr: 0.001, beta: 0.9, depth: 6 }];
  const best_guess = { lr: 0.0012, beta: 0.88, depth: 8 };
  const result = { optimization: { core_spec, initial_points, best_guess, notes: ['dev-proxy: replace with real proxy'] } };
  return { result, usage: { tokens_in: 200, tokens_out: 160, cost_usd: args.profile==='turbo' ? 0.008 : 0.002, model: args.profile } };
}
