
import { InputSchema, OutputSchema, Output } from "./schema";
import { emit } from "./internal/metrics";
import { checkQuota } from "./internal/shim_quota";
import { budgetGuard, chargeCost } from "./internal/shim_budget";
import { selectPath, recordPath } from "./internal/shim_golden_paths";
import { computeS, decideAction } from "./internal/shim_stability";
import { parseJson } from "./internal/convert/json";
import { parseYaml } from "./internal/convert/yaml";
import { parseCSV } from "./internal/convert/csv";
import { parseXML } from "./internal/convert/xml";
import { parseINI } from "./internal/convert/ini";
import { parseTextBlob } from "./internal/convert/text";
import { validate as validateJsonSchema } from "./internal/validate/jsonschema_min";
import { applyKeyPolicy } from "./internal/normalize/key_policy";
import { applyNumberPolicy } from "./internal/normalize/number_policy";
import { canonicalize } from "./internal/normalize/canonical";
import { parseNDJSON } from "./internal/stream/ndjson";
import { parseJSONArray } from "./internal/stream/array_stream";
import { jsonDiff, applyJsonPatch } from "./internal/diff/patch";
import { applyMergePatch } from "./internal/diff/merge_patch";
import { redact } from "./internal/privacy/redactor";

type Ctx = { userId?: string; tier?: string; kv?: any; db?: any; emit?: (e:string,d:any)=>any; logger?: { warn?: Function; error?: Function } };

const KAIA_MIX = { veritas: 0.6, vallon: 0.25, kiren: 0.15 };

function autoDetectFormat(txt:string): 'json'|'yaml'|'csv'|'xml'|'ini'|'text' {
  const s = txt.trim();
  if (s.startsWith('{') || s.startsWith('[')) return 'json';
  if (s.startsWith('<')) return 'xml';
  if (s.includes('\n') && s.split(/\r?\n/)[0].includes(',')) return 'csv';
  if (s.includes('=') && s.includes('[')) return 'ini';
  if (s.includes(':') && s.includes('\n')) return 'yaml';
  return 'text';
}

export async function run(raw: unknown, ctx: Ctx = {}): Promise<Output> {
  const parsed = InputSchema.safeParse(raw);
  if (!parsed.success) { const e:any = new Error("invalid input"); e.status=400; e.details=parsed.error.format(); throw e; }
  const input = parsed.data;
  const tier = (ctx.tier || "free_na").toLowerCase();
  const userId = ctx.userId || "anonymous";

  // Quota & budget
  const q = await checkQuota(ctx.kv, userId, tier);
  if (!q.allowed) { await emit("run.blocked",{bot:"json_bot",reason:"quota",tier},ctx); const e:any = new Error("quota"); e.status=429; e.body={reason:"quota"}; throw e; }
  const bg = await budgetGuard(ctx.db, tier);
  if (!bg.allowed) { await emit("run.blocked",{bot:"json_bot",reason:"hard_stop",tier},ctx); const e:any = new Error("hard_stop"); e.status=429; e.body={reason:"hard_stop"}; throw e; }

  // GP reuse
  const taskKey = { task_type:"json_bot", task: input.task, fmt: input.params?.input_format, out: input.params?.output_format };
  const gp = await selectPath(ctx.db, taskKey as any, 1);

  const src = (input.attachments||[]).find(a=>a.type==='text')?.text || '';
  const strict = !!input.params?.strict;
  const inputFmt = (input.params?.input_format==='auto') ? autoDetectFormat(src) : input.params?.input_format || 'json';
  const issues:any[] = [];
  let data:any = null;
  let size_bytes = src ? new TextEncoder().encode(src).length : 0;

  const safeSrc = (input.params?.privacy?.redact ?? true) ? redact(src) : src;

  try {
    if (input.task==='parse' || input.task==='convert' || input.task==='normalize' || input.task==='validate' || input.task==='stream'){
      if (inputFmt==='json')      ({data, issues} = parseJson(safeSrc, strict));
      else if (inputFmt==='yaml') ({data, issues} = parseYaml(safeSrc, strict));
      else if (inputFmt==='csv')  ({data, issues} = parseCSV(safeSrc, strict));
      else if (inputFmt==='xml')  ({data, issues} = parseXML(safeSrc, strict));
      else if (inputFmt==='ini')  ({data, issues} = parseINI(safeSrc));
      else                        ({data, issues} = parseTextBlob(safeSrc));

      if (input.task==='stream'){
        if (inputFmt==='json' && safeSrc.trim().startsWith('[')) {
          const r=parseJSONArray(safeSrc, input.params?.stream?.max_objects||100000);
          data = r.items; issues.push(...r.issues);
        } else {
          const r=parseNDJSON(safeSrc, input.params?.stream?.max_objects||100000);
          data = r.items; issues.push(...r.issues);
        }
      }
    }

    if (input.task==='normalize' && data){
      data = applyKeyPolicy(data, input.params?.key_policy||'none');
      data = applyNumberPolicy(data, input.params?.number_policy||'as_is');
      if (input.params?.output_format==='canonical_json' || input.params?.output_format==='jcs'){
        const canon = canonicalize(data);
        try { data = JSON.parse(canon); } catch { data = { canonical: canon }; }
      }
    }

    if (input.task==='validate' && data && input.params?.schema_json){
      const vIssues = validateJsonSchema(input.params.schema_json, data);
      issues.push(...vIssues);
    }

    if (input.task==='diff'){
      const aTxt = (input.attachments||[])[0]?.text || '';
      const bTxt = (input.attachments||[])[1]?.text || '';
      const a = parseJson(aTxt, false).data;
      const b = parseJson(bTxt, false).data;
      const ops = jsonDiff(a, b, '');
      const out = { result: { data: undefined, issues, diff: ops, size_bytes, objects_count: undefined }, confidence: 0.9, notes: [], meta: { kaiaMix: { veritas:0.6, vallon:0.25, kiren:0.15 } } } as any;
      return OutputSchema.parse(out);
    }

    if (input.task==='patch' && input.params?.patch){
      const base = parseJson(safeSrc, false).data;
      let patched = base;
      if (input.params.patch.type==='json_patch') patched = applyJsonPatch(base, input.params.patch.ops);
      else patched = applyMergePatch(base, input.params.patch.ops[0]||{});
      const out = { result: { data: patched, issues, size_bytes, objects_count: Array.isArray(patched)?patched.length:undefined }, confidence: 0.9, notes: [], meta: { kaiaMix: { veritas:0.6, vallon:0.25, kiren:0.15 } } } as any;
      return OutputSchema.parse(out);
    }
  } catch (e:any){
    issues.push({ level:'error', message: String(e) });
  }

  const latency_ms = 120; const cost_usd = 0.0005;
  const passProb = issues.filter(i=>i.level==='error').length ? 0.7 : 0.95;
  const S = computeS(passProb, cost_usd, latency_ms);
  const decision = decideAction(S, { S_min: 0.45, gpAvailable: !!gp?.spec });

  await chargeCost(ctx.db, { amount_cents: Math.round(cost_usd*100), tier });

  if (!issues.some(i=>i.level==='error') && (input.task==='convert'||input.task==='normalize')){
    await recordPath(ctx.db, { task_type: "json_bot", key: taskKey as any, success: true, confidence: 0.92, spec: { inputFmt, key_policy: input.params?.key_policy } });
  }

  const res = { data, issues, size_bytes, objects_count: Array.isArray(data)?data.length:undefined };
  const out: Output = { result: res, confidence: 0.92, notes: [], meta: { budget:{cost_usd, tier, pool:'mini'}, gp:{hit: !!gp}, stability:{S, action: decision.action}, kaiaMix: KAIA_MIX } as any };
  await emit("run.complete",{bot:"json_bot",tier,success:true,task:input.task,latency_ms,cost_usd},ctx);
  return OutputSchema.parse(out);
}

export default { run };
