// src/clockwork/bots/commissioning_bot/rollcall.ts
import { z } from 'zod';
import { selectPath } from './internal/shim_golden_paths';

const RollcallInputSchema = z.object({
  task: z.string().min(1),
  params: z.record(z.any()).optional(),
  attachments: z.array(z.object({ type: z.string(), url: z.string().optional(), text: z.string().optional(), filename: z.string().optional() })).optional(),
  userId: z.string().optional(),
  tier: z.string().optional(),
});
const RollcallOutputSchema = z.object({
  can_help: z.boolean(),
  confidence: z.number().min(0).max(1),
  est_cost_usd: z.number(),
  must_have_inputs: z.array(z.string()),
  warnings: z.array(z.string()).optional(),
  gp_candidate: z.object({ id: z.string(), confidence: z.number() }).optional(),
  archetype: z.string().optional()
});
export type RollcallInput = z.infer<typeof RollcallInputSchema>; export type RollcallOutput = z.infer<typeof RollcallOutputSchema>;

export async function ping(raw: unknown, ctx: { db?: any; logger?: any } = {}): Promise<RollcallOutput> {
  const parsed = RollcallInputSchema.safeParse(raw);
  if (!parsed.success) { const e:any = new Error('Invalid rollcall input'); e.status=400; e.details=parsed.error.format(); throw e; }
  const input = parsed.data; const t = input.task.toLowerCase();

  const keywords = ['commission','commissioning','fpt','functional performance test','tab','balancing','bas','bms','ahu','vav','vfd','chiller','boiler','trend','issue log','punchlist','acceptance'];
  let score = 0; for (const k of keywords) if (t.includes(k)) score += 0.16;
  if (input.attachments?.length) score += 0.10;
  if (t.split(/\s+/).length <= 20) score += 0.04;
  const confidence = Math.min(1, Math.max(0, score));

  const est_cost_usd = 0.003;
  const must_have_inputs: string[] = [];

  const warnings: string[] = [];
  const pii = /(\b\d{3}-\d{2}-\d{4}\b)|([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/;
  if (input.attachments) for (const a of input.attachments) { const x = (a.text||'')+''; if (pii.test(x)) warnings.push('attachment_contains_pii'); }

  let gp_candidate: { id:string; confidence:number } | undefined;
  try { const key = { task_type: t.slice(0,128), params_preview: JSON.stringify(input.params||{}).slice(0,512) }; const gp = await selectPath(ctx.db as any, key as any, 1); if (gp && gp.confidence>0.8) gp_candidate = { id: gp.id, confidence: gp.confidence }; } catch(e) { ctx.logger?.warn?.('selectPath failed', e); }

  return RollcallOutputSchema.parse({
    can_help: confidence>=0.25,
    confidence, est_cost_usd, must_have_inputs,
    warnings: warnings.length?warnings:undefined,
    gp_candidate,
    archetype: 'veritas'
  });
}
export default { ping };
