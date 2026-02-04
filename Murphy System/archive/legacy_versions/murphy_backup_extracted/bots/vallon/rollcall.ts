// src/clockwork/bots/vallon/rollcall.ts
import { z } from 'zod';
import { selectPath } from './internal/shim_golden_paths';

const RollcallInputSchema = z.object({ task: z.string().min(1), params: z.record(z.any()).optional(), attachments: z.array(z.object({ type: z.string(), url: z.string().optional(), text: z.string().optional() })).optional(), userId: z.string().optional(), tier: z.string().optional() });
const RollcallOutputSchema = z.object({ can_help: z.boolean(), confidence: z.number().min(0).max(1), est_cost_usd: z.number(), must_have_inputs: z.array(z.string()), warnings: z.array(z.string()).optional(), gp_candidate: z.object({ id: z.string(), confidence: z.number() }).optional(), archetype: z.string().optional() });
export type RollcallInput = z.infer<typeof RollcallInputSchema>; export type RollcallOutput = z.infer<typeof RollcallOutputSchema>;

export async function ping(raw: unknown, ctx: { db?: any; logger?: any } = {}): Promise<RollcallOutput> {
  const parsed = RollcallInputSchema.safeParse(raw);
  if (!parsed.success) { const e:any = new Error('Invalid rollcall input'); e.status=400; e.details=parsed.error.format(); throw e; }
  const input = parsed.data; const task = input.task.toLowerCase();

  const keywords = ['budget', 'prioritize', 'throttle', 'schedule', 'gate', 'cost'];
  let score = 0; for (const k of keywords) if (task.includes(k)) score += 0.2;
  if (input.attachments?.length) score += 0.1;
  if (task.split(/\s+/).length <= 12) score += 0.05;
  const confidence = Math.min(1, Math.max(0, score));

  const est_cost_usd = 0.002;
  const must_have_inputs: string[] = [];
  if ('vallon'==='veritas' && (task.includes('validate')||task.includes('cite')||task.includes('compare'))) must_have_inputs.push('retriever_access');

  const warnings: string[] = [];
  const pii = /(\b\d{3}-\d{2}-\d{4}\b)|([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/;
  if (input.attachments) for (const a of input.attachments) { const t = (a.text||'')+''; if (pii.test(t)) warnings.push('attachment_contains_pii'); }

  let gp_candidate: { id:string; confidence:number } | undefined;
  try { const key = { task_type: task.slice(0,128), params_preview: JSON.stringify(input.params||{}).slice(0,512) }; const gp = await selectPath(ctx.db as any, key as any, 1); if (gp && gp.confidence>0.75) gp_candidate = { id: gp.id, confidence: gp.confidence }; } catch(e) { ctx.logger?.warn?.('selectPath failed', e); }

  return RollcallOutputSchema.parse({
    can_help: confidence>=0.25,
    confidence, est_cost_usd, must_have_inputs,
    warnings: warnings.length?warnings:undefined,
    gp_candidate,
    archetype: 'vallon'
  });
}

export default { ping };
