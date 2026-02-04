// src/clockwork/bots/kaia/kaia.ts
// Based on aionmind_core; adheres to the canvas Bot standards.
import { InputSchema, OutputSchema, Input, Output } from './schema';
import { runWithCore } from './internal/aionmind_core/core';

type Ctx = { userId?: string; tier?: string; kv?: any; db?: any; emit?: (e:string,d:any)=>any; logger?: { warn?: Function; error?: Function } };

const kaiaMix = {'kiren': 0.3, 'veritas': 0.3, 'vallon': 0.4};

export async function run(rawInput: unknown, ctx: Ctx = {}): Promise<Output> {
  const parsed = InputSchema.safeParse(rawInput);
  if (!parsed.success) { const e:any = new Error('Invalid input'); e.status=400; e.details = parsed.error.format(); throw e; }
  const input: Input = parsed.data;
  const out = await runWithCore(input, ctx, {
    name: 'kaia',
    systemPrompt: `You are Kaia, the meta-orchestrator. From inputs, propose clear handoffs to Kiren/Veritas/Vallon as 1-3 ordered microtasks. Output strict JSON only.`,
    kaiaMix
  });
  const v = OutputSchema.safeParse(out);
  if (!v.success) { return { result: { error:'validation_failed', details: out.result }, confidence: 0, notes:['validation_failed'], meta: out.meta } as any; }
  return out;
}

export default { run };
