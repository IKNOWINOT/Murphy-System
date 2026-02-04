import { Input, Output, validateInput, KaiaMixMeta, Schema } from './schema';
import { withBotBase, type Ctx } from '../_base/bot_base';
import { select_path, record_path } from '../../orchestration/experience/golden_paths';
import { emit } from '../../observability/emit';
import { isReadOnly, enforceLimit } from './guards';

export const BOT_NAME = 'analysisbot';

function kaiaMix(): KaiaMixMeta {
  // SQL analysis favors correctness; then throughput; then creative rewriting
  return { veritas: 0.62, vallon: 0.23, kiren: 0.15, veritas_vallon: 0.1426, kiren_veritas: 0.093, vallon_kiren: 0.0345 };
}

function djb2(s:string): number { let h=5381; for (let i=0;i<s.length;i++) h=((h<<5)+h)+s.charCodeAt(i); return h>>>0; }
function hashObj(o:any): number { try { return djb2(JSON.stringify(o)); } catch { return djb2(String(o)); } }

async function getSchemaOrFetch(params:any): Promise<Schema|null> {
  if (params?.schema) return params.schema;
  if (params?.db?.id) {
    try {
      const mod:any = await import('../../io/sql_adapter');
      const sch = await mod.getSchema(params.db.id);
      if (sch && sch.tables) return sch as Schema;
    } catch {}
  }
  return null;
}

function makeGPKey(input: Input, sql: string|undefined, schemaHash: number) {
  return {
    bot: BOT_NAME,
    question: (input.params?.question || input.task || '').slice(0, 180),
    dialect: input.params?.dialect || 'generic',
    schema_hash: schemaHash,
    sql_hash: sql ? hashObj(sql) : undefined,
    project: input.context?.project, topic: input.context?.topic
  };
}

export const run = withBotBase({ name: BOT_NAME, cost_budget_ref: 0.012, latency_ref_ms: 2700, S_min: 0.47 }, async (raw: Input, ctx: Ctx): Promise<Output> => {
  const v = validateInput(raw);
  if (!v.ok) {
    return {
      result: { sql:'', warnings: v.errors },
      confidence: 0,
      meta: { budget: { tier: ctx.tier, pool: 'free' }, gp: { hit: false }, stability: { S: 0, action: 'halt' }, kaiaMix: kaiaMix() },
    } as unknown as Output;
  }
  const input = v.value;
  const p = input.params || {};
  const question = p.question || input.task;
  const dialect = p.dialect || 'postgres';
  const execute = !!p.execute;
  const max_rows = Math.max(1, Math.min(1000, p.max_rows ?? 200));

  // 1) Gather schema
  const schema = await getSchemaOrFetch(p);
  const schemaHash = hashObj(schema || {});

  // 2) GP try (question + schema)
  const keyNoSql = makeGPKey(input, undefined, schemaHash);
  const gp = await select_path(ctx.env.CLOCKWORK_DB, keyNoSql, 10000);
  if ((gp as any)?.hit && (gp as any)?.result) {
    const pk = (gp as any).result;
    return {
      result: pk,
      confidence: (gp as any).confidence ?? 0.94,
      meta: { budget: { tier: ctx.tier, pool: 'gp', cost_usd: (gp as any).cost_usd ?? 0 }, gp: { hit: true, key: keyNoSql, spec_id: (gp as any).spec_id }, stability: { S: 0.9, action:'continue' }, kaiaMix: kaiaMix() },
      provenance: 'analysisbot:gp'
    };
  }

  // 3) NL -> SQL via model_proxy (JSON mode)
  const prompt = [
    { role: 'system', content: 'You are SQLAnalyst. Return STRICT JSON: { "sql": "...", "rationale": "...", "warnings": [] }. SQL must be single-statement, READ-ONLY (SELECT/WITH) and use provided schema only.' },
    { role: 'user', content: JSON.stringify({ question, dialect, schema }) }
  ];

  let gen:any = null;
  try {
    const mp:any = await import('../../orchestration/model_proxy');
    const resp = await mp.callModel({ profile: 'mini', messages: prompt as any[], json: true, maxTokens: 700 });
    gen = (resp?.data) || resp;
  } catch {
    gen = { sql: '', rationale: 'model unavailable', warnings: ['offline'] };
  }

  let sql: string = String(gen?.sql || '').trim();
  const warnings: string[] = Array.isArray(gen?.warnings) ? gen.warnings.slice(0, 10) : [];
  const rationale: string = String(gen?.rationale || '').slice(0, 4000);

  // 4) Safety: enforce read-only
  let safeToRun = isReadOnly(sql);
  if (!safeToRun) warnings.push('unsafe_sql_blocked'); 
  if (execute && !safeToRun) {
    // downgrade to dry-run; keep the SQL for review
    await emit(ctx.env.CLOCKWORK_DB, 'hil.required', { bot: BOT_NAME, reason: 'unsafe_sql', sql_preview: sql.slice(0,200) });
  }

  // 5) Execution (optional, readonly)
  let executed = false, rows:any[]|undefined, columns:string[]|undefined, row_count:number|undefined;
  if (execute && safeToRun && p?.db?.id) {
    try {
      const mod:any = await import('../../io/sql_adapter');
      const sqlLimited = enforceLimit(sql, max_rows);
      const res = await mod.execute(p.db.id, sqlLimited, { limit: max_rows, readonly: true });
      rows = Array.isArray(res?.rows) ? res.rows : [];
      columns = Array.isArray(res?.columns) ? res.columns : (rows && rows[0] ? Object.keys(rows[0]) : []);
      row_count = rows.length;
      executed = true;
    } catch (e:any) {
      warnings.push('execution_failed:' + String(e?.message || e));
    }
  }

  // 6) Profile + optional summary
  const profile = profileRows(rows, columns);
  let summary = '';
  if (p?.style?.summarize && rows && rows.length) {
    const preview = rows.slice(0, Math.min(30, rows.length));
    try {
      const mp:any = await import('../../orchestration/model_proxy');
      const sresp = await mp.callModel({
        profile: 'mini',
        messages: [
          { role: 'system', content: 'You are SQLResultSummarizer. Return JSON: { "summary": "..." }' },
          { role: 'user', content: JSON.stringify({ question, sql, columns, sample: preview }) }
        ],
        json: true,
        maxTokens: 350
      });
      summary = String(sresp?.data?.summary || '');
    } catch {}
  }

  // 7) Record GP candidate
  const key = makeGPKey(input, sql, schemaHash);
  await record_path(ctx.env.CLOCKWORK_DB, {
    task_type: BOT_NAME,
    key,
    success: true,
    cost_tokens: 1000,
    confidence: 0.93,
    spec: {
      sql, rationale, warnings, executed, columns, row_count,
      schema_used: schema
    }
  });

  const out: Output = {
    result: { sql, rationale, warnings, executed, rows, columns, row_count, profile, summary, schema_used: schema || undefined },
    confidence: 0.93,
    meta: { budget: { tier: ctx.tier, pool: 'free', cost_usd: 0.006 }, gp: { hit: false }, stability: { S: 0, action: 'continue' }, kaiaMix: kaiaMix() },
    provenance: 'analysisbot:sql-analyst:v1.0'
  };
  return out;
});

function profileRows(rows?: any[], columns?: string[]) {
  if (!rows || !rows.length) return {};
  const cols = columns && columns.length ? columns : Object.keys(rows[0] || {});
  const nulls: Record<string, number> = {};
  const minmax: Record<string, {min?:any,max?:any}> = {};
  for (const c of cols) { nulls[c] = 0; minmax[c] = {}; }
  for (const r of rows) {
    for (const c of cols) {
      const v = (r as any)[c];
      if (v == null) nulls[c]++;
      if (typeof v === 'number') {
        if (minmax[c].min === undefined || v < (minmax[c].min as number)) minmax[c].min = v;
        if (minmax[c].max === undefined || v > (minmax[c].max as number)) minmax[c].max = v;
      }
    }
  }
  return { nulls, minmax };
}
