
import { z } from 'zod'; import { selectPath } from './internal/shim_golden_paths';
const RollcallInputSchema = z.object({ task: z.string().min(1), params: z.record(z.any()).optional(), attachments: z.array(z.object({ type: z.string(), url: z.string().optional(), text: z.string().optional(), filename: z.string().optional() })).optional(), userId: z.string().optional(), tier: z.string().optional() });
const RollcallOutputSchema = z.object({ can_help: z.boolean(), confidence: z.number().min(0).max(1), est_cost_usd: z.number(), must_have_inputs: z.array(z.string()), warnings: z.array(z.string()).optional(), gp_candidate: z.object({ id: z.string(), confidence: z.number() }).optional(), archetype: z.string().optional() });
export type RollcallInput = z.infer<typeof RollcallInputSchema>; export type RollcallOutput = z.infer<typeof RollcallOutputSchema>;
export async function ping(raw: unknown, ctx: { db?: any; logger?: any } = {}): Promise<RollcallOutput> {
  const parsed = RollcallInputSchema.safeParse(raw); if (!parsed.success) { const e:any = new Error('Invalid rollcall input'); e.status=400; e.details=parsed.error.format(); throw e; }
  const input = parsed.data; const t = input.task.toLowerCase();
  const kw=['calculate','size','design','dfma','tolerance','convert','units','heat','beam','stress','flow','pressure','optimize','simulation','rocket','3d print','aero','electrical','chemical','struct','mechanical','fluid']; let s=0; for(const k of kw) if(t.includes(k)) s+=0.16;
  if (input.attachments?.length) s+=0.06; if (t.split(/\s+/).length<=24) s+=0.04;
  const confidence=Math.min(1,Math.max(0,s)); const est_cost_usd=0.004; const must_have_inputs:string[]=[];
  let gp_candidate; try { const key={ task_type:t.slice(0,128), params_preview: JSON.stringify(input.params||{}).slice(0,512) } as any; const gp=await selectPath(ctx.db as any, key, 1); if(gp&&gp.confidence>0.75) gp_candidate={ id:gp.id, confidence:gp.confidence }; } catch(e){ ctx.logger?.warn?.('selectPath failed',e); }
  return RollcallOutputSchema.parse({ can_help: confidence>=0.25, confidence, est_cost_usd, must_have_inputs, warnings: undefined, gp_candidate, archetype:'kiren_veritas' as any });
}
export default { ping };
