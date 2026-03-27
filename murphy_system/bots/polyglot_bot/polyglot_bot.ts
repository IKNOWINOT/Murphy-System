
import { InputSchema, OutputSchema, Output } from "./schema";
import { emit } from "./internal/metrics";
import { checkQuota } from "./internal/shim_quota";
import { budgetGuard, chargeCost } from "./internal/shim_budget";
import { computeS, decideAction } from "./internal/shim_stability";
import { selectPath, recordPath } from "./internal/shim_golden_paths";
import { redact } from "./internal/privacy/redactor";
import { detectLang } from "./internal/detect/langid";
import { segmentMixed } from "./internal/detect/segment";
import { translateBlock } from "./internal/translate/router";
import { jsToPy } from "./internal/code/transpile_js_py";
import { pyToJs } from "./internal/code/transpile_py_js";
import { explainCode } from "./internal/code/explain";
import { ttcQuestions } from "./internal/prompt/ttc_questions";
import { buildTemplate } from "./internal/prompt/template";
import { buildPrompt } from "./internal/prompt/build_prompt";
import { getCache, setCache } from "./internal/cache/kv";

type Ctx = { userId?: string; tier?: string; kv?: any; db?: any; env?: any; emit?: (e:string,d:any)=>any; logger?: { warn?: Function; error?: Function } };

const KAIA_MIX = { veritas:0.5, vallon:0.15, kiren:0.35 };

export async function run(raw: unknown, ctx: Ctx = {}): Promise<Output> {
  const p = InputSchema.safeParse(raw);
  if (!p.success){ const e:any=new Error('invalid input'); e.status=400; e.details=p.error.format(); throw e; }
  const input = p.data;
  const tier = (ctx.tier||'free_na').toLowerCase();
  const userId = ctx.userId || 'anonymous';
  const params = input.params||{};

  const q = await checkQuota(ctx.kv, userId, tier);
  if (!q.allowed){ await emit('run.blocked',{bot:'polyglot_bot',reason:'quota',tier},ctx); const e:any=new Error('quota'); e.status=429; e.body={reason:'quota'}; throw e; }
  const bg = await budgetGuard(ctx.db, tier);
  if (!bg.allowed){ await emit('run.blocked',{bot:'polyglot_bot',reason:'hard_stop',tier},ctx); const e:any=new Error('hard_stop'); e.status=429; e.body={reason:'hard_stop'}; throw e; }

  const cacheKey = JSON.stringify({ task: input.task, params, att: (input.attachments||[]).map(a=>a.text||'').join('|').slice(0,256) });
  const cached = await getCache(ctx.kv, cacheKey);
  if (cached){ const out: Output = { result: cached, confidence: 0.9, notes:['cache_hit'], meta:{ budget:{cost_usd:0,tier,pool:'mini'}, gp:{hit:false}, stability:{S:1,action:'continue'}, kaiaMix: KAIA_MIX } as any }; return OutputSchema.parse(out); }

  // GP reuse
  const gp = await selectPath(ctx.db, { task_type:'polyglot_bot', params_preview: cacheKey.slice(0,128) } as any, 1);
  if (gp?.spec && gp.confidence>=0.9){
    const out: Output = { result: gp.spec, confidence: gp.confidence, notes:['golden_path_reuse'], meta:{ budget:{tier, pool:'gp'}, gp:{hit:true,key:{fp:cacheKey.slice(0,64)},spec_id:gp.id}, stability:{S:1, action:'continue'}, kaiaMix: KAIA_MIX } as any };
    return OutputSchema.parse(out);
  }

  const result:any = {};
  let passProb = 0.9;
  const t0 = Date.now();
  const style = params.style||{};
  const glossary = params.glossary||{};
  const noTranslate = params.no_translate||[];

  if (input.task==='clarify'){
    result.template = buildTemplate(style, glossary, noTranslate);
    result.translations = [];
    result.questions = ttcQuestions(params.goal||'');
  }
  else if (input.task==='translate' || input.task==='translate_batch'){
    const blocks = [];
    if (params.batch && params.batch.length){
      blocks.push(...params.batch);
    }
    (input.attachments||[]).forEach(a=> { if (a.type==='text' && a.text) blocks.push(a.text); });

    const translations:any[] = [];
    for (const b of blocks){
      const segs = segmentMixed(redact(b||''));
      for (const s of segs){
        const t = await translateBlock(s.text, params.source_lang||'auto', params.target_lang||'en', style, glossary, noTranslate);
        translations.push({ original: s.text, ...t });
      }
    }
    result.translations = translations;
    passProb = Math.min(0.98, (translations.length? translations.map(x=>x.quality||0.8).reduce((a,b)=>a+b,0)/translations.length : 0.8));
  }
  else if (input.task==='transpile'){
    const code = (input.attachments||[])[0]?.text||'';
    const from = (input.attachments||[])[0]?.language || 'auto';
    const to = params.transpile?.to || 'javascript';
    let outCode = code;
    if (to==='javascript') outCode = pyToJs(code);
    else if (to==='python') outCode = jsToPy(code);
    result.transpiled = { from, to, code: outCode };
  }
  else if (input.task==='detect'){
    const text = (input.attachments||[])[0]?.text||'';
    const d = detectLang(text);
    result.detection = { language: d.lang, confidence: d.confidence };
  }
  else if (input.task==='explain'){
    const code = (input.attachments||[])[0]?.text||'';
    const lang = (input.attachments||[])[0]?.language || 'unknown';
    result.explanation = explainCode(code, lang);
  }
  else if (input.task==='normalize' || input.task==='romanize' || input.task==='route'){
    result.translations = [{ original:'', translated:'', source_lang: params.source_lang||'auto', target_lang: params.target_lang||'en', quality:1.0 }];
  }
  else if (input.task==='store_template'){
    result.template = buildTemplate(style, glossary, noTranslate);
  }

  const latency_ms = Date.now() - t0;
  const cost_usd = 0.0007;
  const S = computeS(passProb, cost_usd, latency_ms);
  const decision = decideAction(S, { S_min:0.45, gpAvailable: !!gp?.spec });

  await setCache(ctx.kv, cacheKey, result, 900);
  await recordPath(ctx.db, { task_type:'polyglot_bot', key:{ task_type:'polyglot_bot', params_preview: cacheKey.slice(0,128) } as any, success:true, confidence: passProb, spec: result });
  await chargeCost(ctx.db, { amount_cents: 1, tier });

  const out: Output = { result, confidence: passProb, notes: [], meta:{ budget:{ cost_usd, tier, pool:'mini' }, gp:{hit:false}, stability:{ S, action: decision.action }, kaiaMix: KAIA_MIX } as any };
  await emit('run.complete',{bot:'polyglot_bot',tier,cost_usd,latency_ms,gp_hit:false,success:true},ctx);
  return OutputSchema.parse(out);
}

export default { run };
