// src/clockwork/bots/optimizer_core_bot/test/contract.spec.ts
import { InputSchema, OutputSchema } from '../schema';
import { run } from '../optimizer_core_bot';

describe('optimizer_core_bot contract', () => {
  it('produces a normalized optimization plan', async () => {
    const input = { task: 'optimize learning rate and depth to minimize loss', params: { spec: { objective:'minimize loss', variables:[{name:'lr',type:'float',min:1e-5,max:1e-1},{name:'depth',type:'int',min:2,max:12}], budget_evals: 30 } } };
    const parsed = InputSchema.safeParse(input);
    expect(parsed.success).toBe(true);
    const out = await run(input as any, { userId: 'u1', tier: 'free' } as any);
    const v = OutputSchema.safeParse(out);
    expect(v.success).toBe(true);
    // @ts-ignore
    expect(out.result.optimization.core_spec.variables.length).toBeGreaterThan(0);
  });
});
