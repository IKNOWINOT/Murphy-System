// src/clockwork/bots/veritas/veritas.ts
// Based on aionmind_core; adheres to the canvas Bot standards.
import { InputSchema, OutputSchema, Input, Output } from './schema';
import { runWithCore } from './internal/aionmind_core/core';

type Ctx = { userId?: string; tier?: string; kv?: any; db?: any; emit?: (e:string,d:any)=>any; logger?: { warn?: Function; error?: Function } };

const kaiaMix = {'kiren': 0.1, 'veritas': 0.7, 'vallon': 0.2};

export async function run(rawInput: unknown, ctx: Ctx = {}): Promise<Output> {
  const parsed = InputSchema.safeParse(rawInput);
  if (!parsed.success) { const e:any = new Error('Invalid input'); e.status=400; e.details = parsed.error.format(); throw e; }
  const input: Input = parsed.data;
  const out = await runWithCore(input, ctx, {
    name: 'veritas',
    systemPrompt: `You are Veritas, a validator. Propose 1-3 validation microtasks (ordered) like check->compare->cite. Output strict JSON only.`,
    kaiaMix
  });
  const v = OutputSchema.safeParse(out);
  if (!v.success) { return { result: { error:'validation_failed', details: out.result }, confidence: 0, notes:['validation_failed'], meta: out.meta } as any; }
  return out;
}

export default { run };
