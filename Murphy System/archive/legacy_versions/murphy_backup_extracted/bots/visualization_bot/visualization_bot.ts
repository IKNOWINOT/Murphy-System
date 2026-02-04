import { Input, Output, validateInput, KaiaMixMeta } from './schema';
import { withBotBase, type Ctx } from '../_base/bot_base';
import { select_path, record_path } from '../../orchestration/experience/golden_paths';
import { emit } from '../../observability/emit';
import { makeChartSpec } from './spec_builders/chart';
import { makeDiagramSpec } from './spec_builders/diagram';
import { makeTechSVG } from './spec_builders/svg';
import { makeModel3DSpec } from './spec_builders/model3d';
import { validateChartSpec, validateDiagram } from './validators';

export const BOT_NAME = 'visualization_bot';

function kaiaMix(): KaiaMixMeta {
  return { veritas: 0.55, vallon: 0.30, kiren: 0.15, veritas_vallon: 0.165, kiren_veritas: 0.0825, vallon_kiren: 0.045 };
}

function djb2(s:string): number { let h=5381; for (let i=0;i<s.length;i++) h=((h<<5)+h) + s.charCodeAt(i); return h>>>0; }
function hashObj(o:any): number { try{ return djb2(JSON.stringify(o)); } catch { return djb2(String(o)); } }

export const run = withBotBase({ name: BOT_NAME, cost_budget_ref: 0.015, latency_ref_ms: 3000, S_min: 0.48 }, async (raw: Input, ctx: Ctx): Promise<Output> => {
  const v = validateInput(raw);
  if (!v.ok) {
    return {
      result: {
        visual_id: 'invalid',
        spec_type: 'svg',
        spec: '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"/>',
        validations: { issues: v.errors }
      },
      confidence: 0,
      meta: { budget: { tier: ctx.tier, pool: 'free' }, gp: { hit: false }, stability: { S: 0, action: 'halt' }, kaiaMix: kaiaMix() },
    } as unknown as Output;
  }
  const input = v.value;
  const params = input.params || {};
  const kind = (params.kind || 'chart') as 'chart'|'diagram'|'cad_scope'|'model3d';

  // Build GP key
  const dataHash = hashObj(params.data || {});
  const styleHash = hashObj(params.style || {});
  const key = { bot: BOT_NAME, kind, task: input.task.slice(0,120), dataHash, styleHash, project: input.context?.project, topic: input.context?.topic };

  // GP reuse
  const gp = await select_path(ctx.env.CLOCKWORK_DB, key, 10000);
  if ((gp as any)?.hit && (gp as any)?.result) {
    const specPkg = (gp as any).result || {};
    const out: Output = {
      result: {
        visual_id: specPkg.visual_id || `viz_${dataHash.toString(16)}`,
        spec_type: specPkg.spec_type || 'vega-lite',
        spec: specPkg.spec || {},
        png_url: specPkg.png_url,
        validations: specPkg.validations || { misleading_risk: 'low', issues: [] }
      },
      confidence: specPkg.confidence ?? 0.93,
      meta: { budget: { tier: ctx.tier, pool: 'gp', cost_usd: (gp as any).cost_usd ?? 0.0 }, gp: { hit: true, key, spec_id: (gp as any).spec_id }, stability: { S: 0.9, action: 'continue' }, kaiaMix: kaiaMix() },
      provenance: 'visualization_bot:gp',
    };
    return out;
  }

  // Build spec
  let spec_type: 'svg'|'vega-lite'|'mermaid'|'graphviz'|'gltf' = 'vega-lite';
  let spec: any = {};
  let validations: any = { misleading_risk: 'low', issues: [] };
  const visual_id = `viz_${(hashObj(key)).toString(16)}`;

  if (params.spec) {
    // Validate provided spec
    if (kind==='chart') {
      spec_type = 'vega-lite';
      spec = params.spec;
      validations = validateChartSpec(spec, params.data, { colorblind: !!params?.style?.colorblind_safe });
    } else if (kind==='diagram') {
      spec_type = 'mermaid';
      spec = typeof params.spec === 'string' ? params.spec : JSON.stringify(params.spec);
      validations = validateDiagram('mermaid', spec);
    } else if (kind==='cad_scope') {
      spec_type = 'svg';
      spec = makeTechSVG(params.spec, 'Exploded View');
      validations = validateDiagram('svg', spec);
    } else if (kind==='model3d') {
      const m = makeModel3DSpec(params.data || {}, 'Model');
      spec_type = (m.type==='gltf' ? 'gltf' : 'svg') as any;
      spec = m.spec;
      validations = { misleading_risk: 'low', issues: [] };
    }
  } else {
    // Synthesize spec from task+data
    if (kind==='chart') {
      spec_type = 'vega-lite';
      spec = makeChartSpec(input.task, params.data, params.style);
      validations = validateChartSpec(spec, spec?.data?.values || params.data, { colorblind: !!params?.style?.colorblind_safe });
    } else if (kind==='diagram') {
      const d = makeDiagramSpec(input.task, params.annotations || {});
      spec_type = d.type;
      spec = d.dsl;
      validations = validateDiagram('mermaid', spec);
    } else if (kind==='cad_scope') {
      spec_type = 'svg';
      spec = makeTechSVG(params.data || { parts: [] }, 'Exploded View');
      validations = validateDiagram('svg', spec);
    } else if (kind==='model3d') {
      const m = makeModel3DSpec(params.data || {}, 'Model');
      spec_type = (m.type==='gltf' ? 'gltf' : 'svg') as any;
      spec = m.spec;
    }
  }

  // HIL trigger on risk
  if (validations.misleading_risk === 'high') {
    await emit(ctx.env.CLOCKWORK_DB, 'hil.required', { bot: BOT_NAME, reason: 'visual_risk', key, validations });
  }

  // Record GP candidate
  await record_path(ctx.env.CLOCKWORK_DB, {
    task_type: BOT_NAME,
    key,
    success: true,
    cost_tokens: 800,
    confidence: 0.92,
    spec: { visual_id, spec_type, spec, validations }
  });

  const out: Output = {
    result: { visual_id, spec_type, spec, validations },
    confidence: 0.92,
    meta: { budget: { tier: ctx.tier, pool: 'free', cost_usd: 0.006 }, gp: { hit: false }, stability: { S: 0, action: 'continue' }, kaiaMix: kaiaMix() },
    provenance: 'visualization_bot:v1.0',
  };
  return out;
});
