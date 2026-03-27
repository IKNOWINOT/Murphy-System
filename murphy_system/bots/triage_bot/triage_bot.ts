import { Input, Output, validateInput, KaiaMixMeta } from './schema';
import { pickBest, type CandidateFeatures } from './rank';
import { withBotBase, type Ctx } from '../_base/bot_base';
import { callModel } from '../../orchestration/model_proxy';
import { select_path, record_path } from '../../orchestration/experience/golden_paths';
import { emit } from '../../observability/emit';

export const BOT_NAME = 'triage_bot';

function kaiaMix(): KaiaMixMeta {
  return { veritas: 0.45, vallon: 0.35, kiren: 0.20, veritas_vallon: 0.1575, kiren_veritas: 0.09, vallon_kiren: 0.07 };
}

export const run = withBotBase({ name: BOT_NAME, cost_budget_ref: 0.01, latency_ref_ms: 2500, S_min: 0.46 }, async (raw: Input, ctx: Ctx): Promise<Output> => {
  const v = validateInput(raw);
  if (!v.ok) {
    return {
      result: { errors: v.errors },
      confidence: 0,
      meta: { budget: { tier: ctx.tier, pool: 'free' }, gp: { hit: false }, stability: { S: 0, action: 'halt' }, kaiaMix: kaiaMix() },
    };
  }
  const input = v.value;
const weights = await loadKaiaWeights(ctx) || kaiaMix();

  // 1) (Optional) Memory lookups could be added here via ../../memory/ltm_adapter

  // 2) Build candidate set from bot_capabilities
  const candidates = await fetchCandidates(ctx, input);

  // 3) Roll-call: ask each candidate if they can help (JSON mode, short)
  const rc = await rollcallCandidates(ctx, candidates, input);

  // 4) Score and pick best
  const refs = { cost_budget_ref: 0.01, latency_ref_ms: 2500, S_min: 0.46, kaia: weights };
  const best = pickBest(rc, refs);

  const choice = best ? { bot: best.bot_name, score: best.score, S_star: best.S_star } : null;
  const prNote = choice ? `Selected ${choice.bot} with score ${(choice.score).toFixed(2)}.` : 'No suitable candidate.';

  // 5) HIL trigger if weak
  if (!choice || choice.score < 0.6) {
    await emit(ctx.env.CLOCKWORK_DB, 'hil.required', { bot: BOT_NAME, reason: 'low_confidence', choice, task: input.task });
  }

  // 6) Record GP candidate for this routing decision (so repeated tasks replay faster)
  await record_path(ctx.env.CLOCKWORK_DB, {
    task_type: BOT_NAME,
    key: { action: 'triage', task: input.task.slice(0, 96), hints: Object.keys(input.params || {}).slice(0, 5) },
    success: !!choice,
    cost_tokens: 600,
    confidence: choice ? Math.min(0.99, choice.score) : 0.4,
    spec: { choice, candidates: rc.slice(0, 5) }
  });

  const out: Output = {
    result: {
      status: choice ? 'assigned' : 'no_candidate',
      chosen_bot: choice?.bot || null,
      triage_score: choice?.score || 0,
      notes: prNote,
    },
    confidence: choice ? Math.min(0.98, 0.75 + 0.25*choice.score) : 0.4,
    meta: {
      budget: { tier: ctx.tier, pool: 'free', cost_usd: 0.004 },
      gp: { hit: false },
      stability: { S: 0, action: 'continue' },
      kaiaMix: weights
    },
    provenance: 'triage_bot:v1.0',
  };
  return out;
});

async function fetchCandidates(ctx: Ctx, input: Input): Promise<{bot_name:string,intents:string[],domains:string[],stats:any}[]> {
  try {
    const res = await ctx.env.CLOCKWORK_DB.prepare('SELECT bot_name, intents_json, domains_json, stats_json FROM bot_capabilities').all();
    const rows = (res && (res.results || res)) || [];
    const list = [];
    for (const r of rows) {
      list.push({
        bot_name: r.bot_name,
        intents: safeJSON(r.intents_json, []),
        domains: safeJSON(r.domains_json, []),
        stats: safeJSON(r.stats_json, {}),
      });
    }
    return list;
  } catch { return []; }
}

async function rollcallCandidates(ctx: Ctx, cands: {bot_name:string,intents:string[],domains:string[],stats:any}[], input: Input): Promise<CandidateFeatures[]> {
  const task = input.task;
  const intentTokens = (input.params?.intent_tokens as string[] | undefined) || [];
  const results: CandidateFeatures[] = [];
  for (const c of cands) {
    const intent_match = jaccard(intentTokens, c.intents);
    const domain_match = jaccard([(input.context?.topic||'').toLowerCase()], c.domains);
    let self_conf = 0.5;
    try {
      const prompt = [
        { role: 'system', content: 'You are participating in a roll-call for task routing. Reply strictly in JSON.' },
        { role: 'user', content: JSON.stringify({ bot: c.bot_name, task }) }
      ];
      const resp = await callModel({ profile: 'mini', messages: prompt as any[], json: true, maxTokens: 200 });
      self_conf = clamp01((resp?.data?.confidence ?? resp?.confidence ?? 0.6));
    } catch { self_conf = 0.55; }
    const gp_pass = clamp01(parseFloat(c.stats?.gp_pass_rate ?? '0') || 0);
    const S_hist_avg = clamp01(avg(c.stats?.S_hist || []));
    const est_cost = parseFloat(c.stats?.avg_cost_usd ?? '0.004') || 0.004;
    const est_lat = parseFloat(c.stats?.avg_latency_ms ?? '1800') || 1800;
    results.push({ bot_name: c.bot_name, intent_match, domain_match, self_confidence: self_conf, gp_pass_rate: gp_pass, gp_runs: c.stats?.gp_runs || 0, S_hist_avg, est_cost_usd: est_cost, est_latency_ms: est_lat });
  }
  return results;
}

let _kaiaWeightsCacheEntry: { value: KaiaMixMeta | null; ts: number } | null = null;
const KAIA_WEIGHTS_CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes

export function _resetKaiaWeightsCache() { _kaiaWeightsCacheEntry = null; }

async function loadKaiaWeights(ctx: Ctx): Promise<KaiaMixMeta | null> {
  const now = Date.now();
  if (_kaiaWeightsCacheEntry && (now - _kaiaWeightsCacheEntry.ts) < KAIA_WEIGHTS_CACHE_TTL_MS) {
    return _kaiaWeightsCacheEntry.value;
  }
  let result: KaiaMixMeta | null = null;
  try {
    const db = ctx.env?.CLOCKWORK_DB;
    if (!db) { _kaiaWeightsCacheEntry = { value: null, ts: now }; return null; }
    const row: any = await db.prepare("SELECT stats_json FROM bot_capabilities WHERE bot_name = ?").bind('triage_bot').first();
    if (row?.stats_json) {
      const stats = safeJSON(row.stats_json, {});
      const km = stats?.['kaia_mix.triage'] ?? stats?.kaia_mix?.triage ?? null;
      if (km && typeof km === 'object' && typeof km.veritas === 'number' && typeof km.vallon === 'number' && typeof km.kiren === 'number') {
        result = km as KaiaMixMeta;
      }
    }
  } catch { result = null; }
  _kaiaWeightsCacheEntry = { value: result, ts: now };
  return result;
}

function jaccard(a: string[] = [], b: string[] = []): number {
  const A = new Set(a.map(x => String(x).toLowerCase()).filter(Boolean));
  const B = new Set(b.map(x => String(x).toLowerCase()).filter(Boolean));
  const inter = [...A].filter(x => B.has(x)).length;
  const uni = new Set([...A, ...B]).size || 1;
  return inter / uni;
}
function safeJSON(s: string, d: any) { try { return JSON.parse(s); } catch { return d; } }
function avg(arr: number[] = []) { if (!arr.length) return 0.5; return arr.reduce((a,b)=>a+b,0)/arr.length; }
function clamp01(x: number) { return Math.max(0, Math.min(1, x)); }
