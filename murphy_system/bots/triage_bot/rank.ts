import type { KaiaMixMeta } from './schema';

export type CandidateFeatures = {
  bot_name: string;
  intent_match: number;   // 0..1
  domain_match: number;   // 0..1
  self_confidence: number;// 0..1 (from roll-call JSON)
  gp_pass_rate?: number;  // 0..1
  gp_runs?: number;       // integer
  S_hist_avg?: number;    // 0..1
  est_cost_usd?: number;  // predicted cost
  est_latency_ms?: number;// predicted latency
};

export type ScoreRefs = {
  cost_budget_ref: number;   // USD
  latency_ref_ms: number;    // ms
  S_min: number;
  kaia: KaiaMixMeta;
};

export type Scored = CandidateFeatures & { S_star: number; score: number };

export function scoreCandidate(c: CandidateFeatures, refs: ScoreRefs): Scored {
  const intent = clamp01(c.intent_match);
  const domain = clamp01(c.domain_match);
  const gp = clamp01(c.gp_pass_rate ?? 0);
  const Sh = clamp01(c.S_hist_avg ?? 0.5);
  const selfc = clamp01(c.self_confidence ?? 0.5);

  // pass probability heuristic from multi-signal blend
  const pass_prob_hat = 0.35*intent + 0.25*gp + 0.15*Sh + 0.15*selfc + 0.10*domain;

  const cost_norm = refs.cost_budget_ref > 0 ? (c.est_cost_usd ?? refs.cost_budget_ref*0.5) / refs.cost_budget_ref : 0;
  const lat_norm = refs.latency_ref_ms > 0 ? (c.est_latency_ms ?? refs.latency_ref_ms*0.8) / refs.latency_ref_ms : 0;

  const S_star = clamp01(0.7*pass_prob_hat - 0.2*cost_norm - 0.1*lat_norm);

  // KaiaMix weighting: prioritize correctness (veritas) then throughput (vallon), then creativity (kiren)
  const k = refs.kaia;
  const blended = clamp01(k.veritas*S_star + k.vallon*(1 - lat_norm) + k.kiren*pass_prob_hat*0.5);

  return { ...c, S_star, score: blended };
}

export function pickBest(list: CandidateFeatures[], refs: ScoreRefs): Scored | null {
  if (!list.length) return null;
  let best: Scored | null = null;
  for (const c of list) {
    const s = scoreCandidate(c, refs);
    if (!best || s.score > best.score) best = s;
  }
  return best;
}

function clamp01(x: number) { return Math.max(0, Math.min(1, x)); }
