// src/clockwork/bots/code_translator_bot/internal/shim_stability.ts
export function computeS(passProb:number, costUsd:number, latencyMs:number, weights={qw:0.7,cw:0.2,lw:0.1}, refs={costRefUsd:0.01, latencyRefS:1.5}){
  const normalized_cost=(costUsd||0)/refs.costRefUsd;
  const normalized_latency=(latencyMs/1000)/refs.latencyRefS;
  const pp=Math.max(0,Math.min(1,passProb||0));
  const S=weights.qw*pp - weights.cw*normalized_cost - weights.lw*normalized_latency;
  return Math.max(-1, Math.min(1,S));
}
export function decideAction(S:number, opts:{S_min?:number,gpAvailable?:boolean}={}){
  const S_min=opts.S_min ?? 0.45; const gp=!!opts.gpAvailable;
  if (S>=S_min) return { S, action: 'continue' as const };
  if (gp) return { S, action: 'fallback_gp' as const, reason:'stability_below_threshold_with_gp' };
  return { S, action: 'downgrade' as const, reason:'stability_below_threshold_no_gp' };
}
