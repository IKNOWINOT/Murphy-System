
import { InputSchema, OutputSchema } from '../schema';
import { run } from '../engineering_bot';

describe('engineering_bot max contract', () => {
  it('runs structural deflection', async () => {
    const input = { task:'struct beam deflection', params:{ mode:'domain', domain:'structural', spec:{ span:6, span_unit:'m', w:2000, E:200e9, I:1e-5, deflection:0.01 } } };
    const p = InputSchema.safeParse(input); expect(p.success).toBe(true);
    const out = await run(input as any, { userId:'u1', tier:'free' } as any);
    const v = OutputSchema.safeParse(out); expect(v.success).toBe(true);
  });
  it('runs rocket delta-v', async () => {
    const input = { task:'rocket delta-v', params:{ mode:'domain', domain:'aero', spec:{ Isp:320, m0:5000, mf:3000 } } };
    const out = await run(input as any, { userId:'u1', tier:'free' } as any);
    const v = OutputSchema.safeParse(out); expect(v.success).toBe(true);
  });
});
