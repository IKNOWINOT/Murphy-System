
import { InputSchema, OutputSchema, Output } from "./schema";
import { emit } from "./internal/metrics";
import { checkQuota } from "./internal/shim_quota";
import { budgetGuard, chargeCost } from "./internal/shim_budget";
import { computeS, decideAction } from "./internal/shim_stability";
import { redact } from "./internal/privacy/redactor";
import * as docs from "./internal/db/docs";
import * as chunks from "./internal/db/chunks";
import * as queries from "./internal/db/queries";
import * as events from "./internal/db/events";
import { normalizeText } from "./internal/ingest/normalize";
import { chunkText } from "./internal/ingest/chunk";
import { getCache, setCache } from "./internal/cache/kv_cache";
import { lexScore } from "./internal/rank/lexical";
import { hybridRank } from "./internal/rank/hybrid";
import { safeFetch } from "./internal/fetch/safe_fetch";

type Ctx = { userId?: string; tier?: string; kv?: any; db?: D1Database; env?: any; emit?: (e:string,d:any)=>any; logger?: { warn?: Function; error?: Function } };

const KAIA_MIX = { veritas:0.45, kiren:0.35, vallon:0.20 };

export async function run(raw: unknown, ctx: Ctx = {}): Promise<Output> {
  const parsed = InputSchema.safeParse(raw);
  if (!parsed.success) { const e:any = new Error("invalid input"); e.status=400; e.details=parsed.error.format(); throw e; }
  const input = parsed.data;
  const tier = (ctx.tier || "free_na").toLowerCase();
  const userId = ctx.userId || "anonymous";

  const q = await checkQuota(ctx.kv, userId, tier);
  if (!q.allowed) { await emit("run.blocked",{bot:"librarian_bot",reason:"quota",tier},ctx); const e:any = new Error("quota"); e.status=429; e.body={reason:"quota"}; throw e; }
  const bg = await budgetGuard(ctx.db, tier);
  if (!bg.allowed) { await emit("run.blocked",{bot:"librarian_bot",reason:"hard_stop",tier},ctx); const e:any = new Error("hard_stop"); e.status=429; e.body={reason:"hard_stop"}; throw e; }

  const t0 = Date.now();

  // Ingest
  if (input.task==='ingest' && input.params?.doc){
    const d = input.params.doc;
    const cleanText = normalizeText(redact(d.text||""));
    await docs.upsertDoc(ctx.db!, {
      id: d.id, title: d.title||"", source_bot: d.meta?.source_bot||null, task_id: d.meta?.task_id||null,
      tags: d.tags||[], created_ts: new Date().toISOString(), updated_ts: new Date().toISOString(),
      size_bytes: new TextEncoder().encode(cleanText).length, content_uri: d.content_uri||null, meta: d.meta||{}
    });
    const projections = input.params?.ann?.projections || 64;
    const chs = chunkText(cleanText, 1800, 200, projections);
    await chunks.upsertChunks(ctx.db!, d.id, chs);
    await events.audit(ctx.db!, 'lib.ingest', userId, { id: d.id, tags: d.tags||[] });
    const out: Output = { result: { docs: [], usage: { from_cache:false, objects: chs.length } }, confidence: 0.95, notes: [], meta: { budget:{ cost_usd:0.0005, tier, pool:'mini' }, gp:{hit:false}, stability:{S:1, action:'continue'}, kaiaMix: KAIA_MIX } as any };
    await emit("run.complete",{bot:"librarian_bot",tier,success:true,task:"ingest"},ctx);
    return OutputSchema.parse(out);
  }

  // Safe remote fetch → ingest
  if (input.task==='fetch_remote' && input.params?.remote && (input.params.safe_remote || false)){
    const allowlist = (ctx.env?.LIBRARIAN_ALLOWLIST || "").split(',').map((s:string)=>s.trim()).filter(Boolean);
    const r = await safeFetch(input.params.remote.url, { allowlist, timeout_ms: input.params.remote.timeout_ms, max_bytes: input.params.remote.max_bytes });
    // store as a doc (basic)
    const id = 'remote_'+Date.now();
    await docs.upsertDoc(ctx.db!, { id, title: input.params.remote.url, tags: ['remote'], created_ts:new Date().toISOString(), updated_ts:new Date().toISOString(), size_bytes: r.text.length, content_uri: input.params.remote.url, meta:{ remote:true } });
    const chs = chunkText(normalizeText(redact(r.text)));
    await chunks.upsertChunks(ctx.db!, id, chs);
    const out: Output = { result: { docs:[{ id, title:input.params.remote.url, snippet:chs[0]?.text.slice(0,200), tags:['remote'] }], usage:{from_cache:false, objects: chs.length} }, confidence: 0.9, notes: [], meta:{ budget:{cost_usd:0.0008, tier, pool:'mini'}, gp:{hit:false}, stability:{S:1, action:'continue'}, kaiaMix: KAIA_MIX } as any };
    return OutputSchema.parse(out);
  }

  // Search
  if (input.task==='search'){
    const query = input.params?.query || "";
    const tagsReq = input.params?.tags || [];
    const limit = Math.min(100, Math.max(1, input.params?.limit||20));
    const blend = input.params?.blend || { lexical:0.4, semantic:0.5, freshness:0.1 };
    const cacheKey = `lib:search:${(ctx as any)?.tenant||'t'}:${btoa(query+JSON.stringify(tagsReq)+JSON.stringify(blend)).slice(0,64)}`;
    const cached = await getCache(ctx.kv, cacheKey);
    if (cached){ const out: Output = { result: cached, confidence: 0.9, notes: [], meta:{ budget:{cost_usd:0, tier, pool:'mini'}, gp:{hit:false}, stability:{S:1, action:'continue'}, kaiaMix: KAIA_MIX } as any }; return OutputSchema.parse(out); }

    // Candidates by tags (simple scan)
    const rows = await docs.scanByTags(ctx.db!, tagsReq||[], 1000);
    const candidates:any[]=[];
    for (const r of rows){
      const ch = await chunks.getChunks(ctx.db!, r.id, 1);
      const text = ch[0]?.text || "";
      candidates.push({ id:r.id, title:r.title, text, tags: JSON.parse(r.tags_json||'[]'), content_uri: r.content_uri, updated_ts: r.updated_ts, proj: ch[0]?.proj||null });
    }

    // Lexical base
    let ranked = candidates.map(c => ({ ...c, score: lexScore(c.text||'', query, tagsReq||[]) }));

    // Hybrid rerank (RP semantic proxy; if ctx.env.MODEL_PROXY_URL wired in your system, swap here)
    if (input.params?.rerank && (tier==='pro'||tier==='teams'||tier==='enterprise')){
      ranked = await hybridRank(ranked, query, tagsReq||[], blend, { ctx });
    }
    ranked.sort((a,b)=> (b.score||0)-(a.score||0));
    const hits = ranked.slice(0, limit).map(h => ({ id:h.id, title:h.title, snippet:(h.text||'').slice(0,300), tags:h.tags||[], score:h.score, content_uri:h.content_uri }));

    // Facets
    let facets:any=undefined;
    if (input.params?.facets){
      const tagBuckets = await docs.listAllTags(ctx.db!);
      facets = [{ field:'tags', buckets: tagBuckets.slice(0,50) }];
    }

    const latency_ms = Date.now()-t0; const cost_usd = 0.0004;
    await queries.logQuery(ctx.db!, 'anon', query, tagsReq||[], hits, latency_ms);

    const passProb = hits.length ? 0.95 : 0.6;
    const S = computeS(passProb, cost_usd, latency_ms);
    const decision = decideAction(S, { S_min: 0.45, gpAvailable:false });

    const result:any = { docs: hits, usage: { from_cache:false, objects: hits.length } };
    if (facets) result.facets = facets;
    await setCache(ctx.kv, cacheKey, result, 60);
    const out: Output = { result, confidence: passProb, notes: [], meta: { budget:{cost_usd, tier, pool:'mini'}, gp:{hit:false}, stability:{S, action:decision.action}, kaiaMix: KAIA_MIX } as any };
    await emit("run.complete",{bot:"librarian_bot",tier,success:true,task:"search",latency_ms,cost_usd},ctx);
    return OutputSchema.parse(out);
  }

  // Retrieve
  if (input.task==='retrieve' && input.params?.doc?.id){
    const row:any = await docs.getDoc(ctx.db!, input.params.doc.id);
    if (!row) { const out: Output = { result: { docs: [], usage:{from_cache:false, objects:0} }, confidence: 0.6, notes:['not_found'], meta:{ budget:{cost_usd:0, tier, pool:'mini'}, gp:{hit:false}, stability:{S:0.5, action:'continue'}, kaiaMix: KAIA_MIX } as any }; return OutputSchema.parse(out); }
    await docs.updatePopularity(ctx.db!, row.id, 1);
    const out: Output = { result: { docs:[{ id:row.id, title:row.title, snippet:undefined, tags: JSON.parse(row.tags_json||'[]'), score:undefined, content_uri: row.content_uri }], usage:{from_cache:false, objects:1} }, confidence: 0.9, notes: [], meta:{ budget:{cost_usd:0, tier, pool:'mini'}, gp:{hit:false}, stability:{S:1, action:'continue'}, kaiaMix: KAIA_MIX } as any };
    return OutputSchema.parse(out);
  }

  const out: Output = { result: { docs: [], usage:{from_cache:false, objects:0} }, confidence: 0.6, notes:['noop'], meta:{ budget:{cost_usd:0, tier, pool:'mini'}, gp:{hit:false}, stability:{S:1, action:'continue'}, kaiaMix: KAIA_MIX } as any };
  return OutputSchema.parse(out);
}

export default { run };
