// src/clockwork/bots/goldenpath_generator/rollcall.ts
import { z } from 'zod';
import { emit } from './internal/metrics';
import { selectPath } from './internal/shim_golden_paths';
const RollcallInputSchema = z.object({ task: z.string().min(1), params: z.record(z.any()).optional(), attachments: z.array(z.object({ type: z.string(), url: z.string().optional(), text: z.string().optional() })).optional(), userId: z.string().optional(), tier: z.string().optional() });
const RollcallOutputSchema = z.object({ can_help: z.boolean(), confidence: z.number().min(0).max(1), est_cost_usd: z.number(), must_have_inputs: z.array(z.string()), warnings: z.array(z.string()).optional(), gp_candidate: z.object({ id: z.string(), confidence: z.number() }).optional() });
export type RollcallInput = z.infer<typeof RollcallInputSchema>;
export type RollcallOutput = z.infer<typeof RollcallOutputSchema>;
export async function ping(raw: unknown, ctx: { db?: any; emit?: (e:string,d:any)=>any; logger?: any } = {}): Promise<RollcallOutput> {
  const parsed = RollcallInputSchema.safeParse(raw);
  if (!parsed.success) { const e:any = new Error('Invalid rollcall input'); e.status=400; e.details=parsed.error.format(); throw e; }
  const input = parsed.data; const task = input.task.toLowerCase();
  const keywords = ['upload','upload file','export','drive','create task','task','report','schedule','meeting','invite','calendar','send email','draft','attach'];
  let score = 0; for (const kw of keywords) if (task.includes(kw)) score += 0.14;
  if (input.attachments?.length) score += 0.18;
  if (task.split(/\s+/).length <= 8) score += 0.08;
  const confidence = Math.min(1, Math.max(0, score));
  const base_per_microtask = 0.002;
  const verbCount = Math.max(1, (task.match(/\b(upload|export|create|send|schedule|draft|attach|convert|archive|move)\b/g) || []).length);
  const est_microtasks = Math.min(3, verbCount);
  const est_cost_usd = +(base_per_microtask * est_microtasks).toFixed(6);
  const must_have_inputs: string[] = [];
  if (task.includes('upload') || task.includes('drive')) must_have_inputs.push('drive_api_token');
  if (task.includes('email') || task.includes('send email')) must_have_inputs.push('smtp_credentials');
  if (task.includes('schedule') || task.includes('calendar') || task.includes('invite')) must_have_inputs.push('calendar_access');
  const warnings: string[] = [];
  const piiRegex = /(\b\d{3}-\d{2}-\d{4}\b)|([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/;
  if (input.attachments) { for (const a of input.attachments) { const text = (a.text || '').toString(); if (piiRegex.test(text)) warnings.push('attachment_contains_pii'); } }
  let gp_candidate: { id:string; confidence:number } | undefined;
  try { const taskKey = { task_type: task.slice(0,128), params_preview: JSON.stringify(input.params || {}).slice(0, 512) }; const gp = await selectPath(ctx.db as any, taskKey as any, 1); if (gp && typeof gp.confidence === 'number' && gp.confidence > 0.75) gp_candidate = { id: gp.id, confidence: gp.confidence }; } catch (err) { ctx.logger?.warn?.('rollcall selectPath failed', err); }
  const out: RollcallOutput = { can_help: confidence >= 0.25, confidence, est_cost_usd, must_have_inputs, warnings: warnings.length ? warnings : undefined, gp_candidate };
  await emit('rollcall.nominees', { bot: 'goldenpath_generator', score: confidence, saved_cost_estimate_usd: est_cost_usd }, ctx);
  return RollcallOutputSchema.parse(out);
}
export default { ping };
