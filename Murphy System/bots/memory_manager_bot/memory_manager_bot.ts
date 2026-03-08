
import { InputSchema, OutputSchema, Output } from "./schema";
import { emit } from "./internal/metrics";
import { checkQuota } from "./internal/shim_quota";
import { budgetGuard, chargeCost } from "./internal/shim_budget";
import { computeS, decideAction } from "./internal/shim_stability";
import { redact } from "./internal/privacy/redactor";
import * as entries from "./internal/db/entries";
import * as chunks from "./internal/db/chunks";
import * as hist from "./internal/db/history";
import * as events from "./internal/db/events";
import * as stats from "./internal/db/stats";
import { rpProject } from "./internal/vector/ann";
import { hybridRank } from "./internal/rank/hybrid";

type Ctx = { userId?: string; tier?: string; kv?: any; db?: D1Database; env?: any; emit?: (e:string,d:any)=>any; logger?: { warn?: Function; error?: Function } };

const KAIA_MIX = { veritas:0.45, kiren:0.35, vallon:0.2 };

function nowIso(){ return new Date().toISOString(); }
function sec(ts?:string){ return ts ? (Date.parse(ts)/1000) : 0; }

export async function run(raw: unknown, ctx: Ctx = {}): Promise<Output> {
  const p = InputSchema.safeParse(raw);
  if (!p.success) { const e:any = new Error("invalid input"); e.status=400; e.details=p.error.format(); throw e; }
  const input = p.data;
  const tier = (ctx.tier||'free_na').toLowerCase();
  const userId = ctx.userId || 'anonymous';
  const tenant = input.params?.tenant || 'default';

  const q = await checkQuota(ctx.kv, userId, tier);
  if (!q.allowed){ await emit('run.blocked',{bot:'memory_manager_bot',reason:'quota',tier},ctx); const e:any=new Error('quota'); e.status=429; e.body={reason:'quota'}; throw e; }
  const bg = await budgetGuard(ctx.db, tier);
  if (!bg.allowed){ await emit('run.blocked',{bot:'memory_manager_bot',reason:'hard_stop',tier},ctx); const e:any=new Error('hard_stop'); e.status=429; e.body={reason:'hard_stop'}; throw e; }

  // ADD
  if (input.task==='add' && input.params?.text){
    const id = 'm_'+Date.now();
    const text = redact(input.params.text||'');
    await entries.upsertEntry(ctx.db!, { id, tenant, text, trust: input.params?.trust||1.0, last_accessed: nowIso(), access_count:0, status:'active', created_ts: nowIso(), updated_ts: nowIso() });
    await chunks.upsertChunks(ctx.db!, id, [{ chunk_id:'c0', ord:0, text, proj: rpProject(text, 64) }]);
    await events.audit(ctx.db!, 'mm.add', userId, { tenant, id });
    const out: Output = { result: { memories: [{ id, text }] }, confidence: 0.95, notes: [], meta:{ budget:{cost_usd:0.0004,tier,pool:'mini'}, gp:{hit:false}, stability:{S:1, action:'continue'}, kaiaMix: KAIA_MIX } as any };
    return OutputSchema.parse(out);
  }

  // UPDATE
  if (input.task==='update' && input.params?.id && input.params?.text){
    const id = input.params.id;
    const row:any = await entries.getEntry(ctx.db!, id);
    if (!row) throw new Error('not_found');
    const newText = redact(input.params.text);
    await hist.appendHistory(ctx.db!, id, userId, 'update', `updated`);
    await entries.upsertEntry(ctx.db!, { id, tenant, text:newText, trust: row.trust||1.0, last_accessed: nowIso(), access_count: row.access_count||0, status:'active', created_ts: row.created_ts||nowIso(), updated_ts: nowIso() });
    await chunks.upsertChunks(ctx.db!, id, [{ chunk_id:'c0', ord:0, text:newText, proj: rpProject(newText, 64) }]);
    await events.audit(ctx.db!, 'mm.update', userId, { tenant, id });
    const out: Output = { result: { memories: [{ id, text:newText }] }, confidence: 0.95, notes: [], meta:{ budget:{cost_usd:0.0004,tier,pool:'mini'}, gp:{hit:false}, stability:{S:1, action:'continue'}, kaiaMix: KAIA_MIX } as any };
    return OutputSchema.parse(out);
  }

  // GET
  if (input.task==='get' && input.params?.id){
    const id = input.params.id;
    const row:any = await entries.getEntry(ctx.db!, id);
    if (!row || row.status!=='active'){ const out: Output = { result:{ memories:[] }, confidence:0.6, notes:['not_found'], meta:{ budget:{cost_usd:0,tier,pool:'mini'}, gp:{hit:false}, stability:{S:0.5, action:'continue'}, kaiaMix: KAIA_MIX } as any }; return OutputSchema.parse(out); }
    await entries.updateAccess(ctx.db!, id);
    const out: Output = { result:{ memories:[{ id, text: row.text, trust: row.trust, last_accessed: row.last_accessed }] }, confidence: 0.9, notes: [], meta:{ budget:{cost_usd:0,tier,pool:'mini'}, gp:{hit:false}, stability:{S:1, action:'continue'}, kaiaMix: KAIA_MIX } as any };
    return OutputSchema.parse(out);
  }

  // DELETE
  if (input.task==='delete' && input.params?.id){
    await entries.softDelete(ctx.db!, input.params.id);
    await events.audit(ctx.db!, 'mm.delete', userId, { tenant, id: input.params.id });
    const out: Output = { result:{ memories:[] }, confidence:0.9, notes:['deleted'], meta:{ budget:{cost_usd:0,tier,pool:'mini'}, gp:{hit:false}, stability:{S:1, action:'continue'}, kaiaMix: KAIA_MIX } as any };
    return OutputSchema.parse(out);
  }

  // SEARCH
  if (input.task==='search' && (input.params?.query||'').length>0){
    const query = input.params?.query||'';
    const blend = { lexical:0.4, semantic:0.5, freshness:0.1 };
    const rows = await entries.scanTenant(ctx.db!, tenant, 1000);
    const candidates = [];
    for (const r of rows){
      const ch = await chunks.getChunks(ctx.db!, r.id, 1);
      candidates.push({ id:r.id, text: ch[0]?.text||r.text||'', trust: r.trust||1, last_accessed: sec(r.last_accessed), access_count: r.access_count||0, proj: ch[0]?.proj||null });
    }
    let ranked = await hybridRank(candidates, query, blend);
    ranked = ranked.slice(0, Math.min(100, input.params?.top_k||10));
    for (const h of ranked){ await entries.updateAccess(ctx.db!, h.id); }
    const hits = ranked.map(h => ({ id:h.id, text:h.text, score:h.score, trust:h.trust, last_accessed: new Date((h.last_accessed||0)*1000).toISOString() }));
    const latency_ms = 150; const cost_usd = 0.0005;
    const passProb = hits.length ? 0.95 : 0.6;
    const S = computeS(passProb, cost_usd, latency_ms);
    const decision = decideAction(S, { S_min: 0.45, gpAvailable:false });
    const out: Output = { result:{ memories: hits }, confidence: passProb, notes: [], meta:{ budget:{cost_usd, tier, pool:'mini'}, gp:{hit:false}, stability:{S, action:decision.action}, kaiaMix: { veritas:0.45, kiren:0.35, vallon:0.2 } } as any };
    await emit('run.complete',{bot:'memory_manager_bot',tier,success:true,task:'search',latency_ms,cost_usd},ctx);
    return OutputSchema.parse(out);
  }

  // STM STORE
  if (input.task==='stm_store' && input.params?.stm && input.params?.text){
    const { storeSTM } = await import('./internal/stm/store');
    await storeSTM(ctx.kv, tenant, input.params.stm.task_id, { text: redact(input.params.text) }, input.params.stm.ttl_s||1800);
    const out: Output = { result:{ stm:{ flushed:0 }, memories:[] }, confidence:0.9, notes:[], meta:{ budget:{cost_usd:0,tier,pool:'mini'}, gp:{hit:false}, stability:{S:1, action:'continue'}, kaiaMix: { veritas:0.45, kiren:0.35, vallon:0.2 } } as any };
    return OutputSchema.parse(out);
  }

  // STM FLUSH
  if (input.task==='stm_flush'){
    const { flushSTM } = await import('./internal/stm/store');
    const flushed = await flushSTM(ctx.kv, tenant);
    const out: Output = { result:{ stm:{ flushed }, memories:[] }, confidence:0.9, notes:[], meta:{ budget:{cost_usd:0,tier,pool:'mini'}, gp:{hit:false}, stability:{S:1, action:'continue'}, kaiaMix: { veritas:0.45, kiren:0.35, vallon:0.2 } } as any };
    return OutputSchema.parse(out);
  }

  // PRUNE
  if (input.task==='prune'){
    if (!ctx.db) {
      const out: Output = { result:{ memories:[], pruned_count:0 }, confidence:0.5, notes:['no_db'], meta:{ budget:{cost_usd:0,tier,pool:'mini'}, gp:{hit:false}, stability:{S:1, action:'continue'}, kaiaMix: KAIA_MIX } as any };
      return OutputSchema.parse(out);
    }
    const threshold = (input.params as any)?.threshold ?? 0.25;
    const rows = await entries.scanTenant(ctx.db!, tenant, 10000);
    const nowSec = Date.now() / 1000;
    let pruned = 0;
    for (const r of rows){
      const ageSec = nowSec - (r.last_accessed ? Date.parse(r.last_accessed)/1000 : 0);
      const halfLife = 30 * 24 * 3600; // 30-day half-life
      const decay = Math.pow(0.5, ageSec / halfLife);
      const accessBoost = Math.log1p(r.access_count||0) * 0.05;
      const score = Math.min(1, (r.trust||1) * decay * (1 + accessBoost));
      if (score < threshold){
        await entries.softDelete(ctx.db!, r.id);
        pruned++;
      }
    }
    await emit('mm.prune', { tenant, pruned }, ctx);
    const out: Output = { result:{ memories:[], pruned_count:pruned }, confidence:0.9, notes:[], meta:{ budget:{cost_usd:0,tier,pool:'mini'}, gp:{hit:false}, stability:{S:1, action:'continue'}, kaiaMix: KAIA_MIX } as any };
    return OutputSchema.parse(out);
  }

  // COMPRESS
  if (input.task==='compress'){
    if (!ctx.db) {
      const out: Output = { result:{ memories:[], compressed_count:0 }, confidence:0.5, notes:['no_db'], meta:{ budget:{cost_usd:0,tier,pool:'mini'}, gp:{hit:false}, stability:{S:1, action:'continue'}, kaiaMix: KAIA_MIX } as any };
      return OutputSchema.parse(out);
    }
    const rows = await entries.scanTenant(ctx.db!, tenant, 10000);
    let compressed = 0;
    for (const r of rows){
      const meta = r.meta_json ? JSON.parse(r.meta_json) : {};
      if (!meta.compressed && r.text && r.text.length > 200){
        // Basic compression: deduplicate repeated whitespace first, then truncate to 70%
        const deduped = r.text.replace(/\s+/g, ' ').trim();
        const compressedText = deduped.slice(0, Math.ceil(deduped.length * 0.7));
        await entries.upsertEntry(ctx.db!, { id:r.id, tenant, text:compressedText, trust:r.trust||1, last_accessed:r.last_accessed||nowIso(), access_count:r.access_count||0, status:'active', compressed:1, created_ts:r.created_ts||nowIso(), updated_ts:nowIso(), meta:{ ...meta, compressed:true } });
        compressed++;
      }
    }
    await emit('mm.compress', { tenant, compressed }, ctx);
    const out: Output = { result:{ memories:[], compressed_count:compressed }, confidence:0.9, notes:[], meta:{ budget:{cost_usd:0,tier,pool:'mini'}, gp:{hit:false}, stability:{S:1, action:'continue'}, kaiaMix: KAIA_MIX } as any };
    return OutputSchema.parse(out);
  }

  // STATS
  if (input.task==='stats'){
    if (!ctx.db) {
      const out: Output = { result:{ memories:[], stats:{ total_count:0, active_count:0, deleted_count:0, compressed_count:0, avg_trust:0 } }, confidence:0.5, notes:['no_db'], meta:{ budget:{cost_usd:0,tier,pool:'mini'}, gp:{hit:false}, stability:{S:1, action:'continue'}, kaiaMix: KAIA_MIX } as any };
      return OutputSchema.parse(out);
    }
    await ctx.db.prepare(`CREATE TABLE IF NOT EXISTS mem_entries (id TEXT PRIMARY KEY, tenant TEXT, text TEXT, trust REAL, last_accessed TEXT, access_count INT, status TEXT, ttl_seconds INT, compressed INT, enc INT, meta_json TEXT, created_ts TEXT, updated_ts TEXT)`).run();
    const agg = await ctx.db.prepare(
      `SELECT COUNT(*) as total_count, SUM(CASE WHEN status='active' THEN 1 ELSE 0 END) as active_count, SUM(CASE WHEN status='deleted' THEN 1 ELSE 0 END) as deleted_count, SUM(CASE WHEN compressed=1 THEN 1 ELSE 0 END) as compressed_count, AVG(trust) as avg_trust FROM mem_entries WHERE tenant=?`
    ).bind(tenant).get<any>();
    const s = agg || {};
    const statsObj = { total_count: s.total_count||0, active_count: s.active_count||0, deleted_count: s.deleted_count||0, compressed_count: s.compressed_count||0, avg_trust: +(s.avg_trust||0).toFixed(3) };
    const out: Output = { result:{ memories:[], stats: statsObj }, confidence:0.9, notes:[], meta:{ budget:{cost_usd:0,tier,pool:'mini'}, gp:{hit:false}, stability:{S:1, action:'continue'}, kaiaMix: KAIA_MIX } as any };
    return OutputSchema.parse(out);
  }

  // EXPORT
  if (input.task==='export'){
    if (!ctx.db) {
      const out: Output = { result:{ memories:[] }, confidence:0.5, notes:['no_db'], meta:{ budget:{cost_usd:0,tier,pool:'mini'}, gp:{hit:false}, stability:{S:1, action:'continue'}, kaiaMix: KAIA_MIX } as any };
      return OutputSchema.parse(out);
    }
    const rows = await entries.scanTenant(ctx.db!, tenant, 10000);
    const exported = rows.map(r => ({ id:r.id, text:r.text, trust:r.trust, last_accessed:r.last_accessed, access_count:r.access_count }));
    const out: Output = { result:{ memories: exported }, confidence:0.9, notes:[], meta:{ budget:{cost_usd:0,tier,pool:'mini'}, gp:{hit:false}, stability:{S:1, action:'continue'}, kaiaMix: KAIA_MIX } as any };
    return OutputSchema.parse(out);
  }

  // IMPORT
  if (input.task==='import'){
    if (!ctx.db) {
      const out: Output = { result:{ memories:[], imported_count:0, skipped_count:0 }, confidence:0.5, notes:['no_db'], meta:{ budget:{cost_usd:0,tier,pool:'mini'}, gp:{hit:false}, stability:{S:1, action:'continue'}, kaiaMix: KAIA_MIX } as any };
      return OutputSchema.parse(out);
    }
    const importEntries: any[] = (input.params as any)?.entries || [];
    let imported = 0; let skipped = 0;
    for (const e of importEntries){
      if (!e || !e.id || typeof e.text !== 'string'){ skipped++; continue; }
      try {
        await entries.upsertEntry(ctx.db!, { id: e.id, tenant, text: redact(e.text), trust: e.trust??1.0, last_accessed: e.last_accessed||nowIso(), access_count: e.access_count||0, status:'active', created_ts: e.created_ts||nowIso(), updated_ts: nowIso() });
        imported++;
      } catch { skipped++; }
    }
    await emit('mm.import', { tenant, imported, skipped }, ctx);
    const out: Output = { result:{ memories:[], imported_count:imported, skipped_count:skipped }, confidence:0.9, notes:[], meta:{ budget:{cost_usd:0,tier,pool:'mini'}, gp:{hit:false}, stability:{S:1, action:'continue'}, kaiaMix: KAIA_MIX } as any };
    return OutputSchema.parse(out);
  }

  const out: Output = { result:{ memories:[] }, confidence:0.6, notes:['noop'], meta:{ budget:{cost_usd:0,tier,pool:'mini'}, gp:{hit:false}, stability:{S:1, action:'continue'}, kaiaMix: { veritas:0.45, kiren:0.35, vallon:0.2 } } as any };
  return OutputSchema.parse(out);
}

export default { run };
