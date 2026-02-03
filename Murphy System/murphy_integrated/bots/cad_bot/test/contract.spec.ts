// src/clockwork/bots/cad_bot/test/contract.spec.ts
import { InputSchema, OutputSchema } from '../schema';
import { run } from '../cad_bot';

describe('cad_bot (ported) contract', () => {
  it('returns CADSpec JSON in result.cad_spec', async () => {
    const input = { task: 'create a box 10x10x10 mm and export step' };
    const parsed = InputSchema.safeParse(input);
    expect(parsed.success).toBe(true);
    const out = await run(input as any, { userId: 'u1', tier: 'free' } as any);
    const v = OutputSchema.safeParse(out);
    expect(v.success).toBe(true);
    // rudimentary structural check
    // @ts-ignore
    expect(out.result.cad_spec.entities.length).toBeGreaterThan(0);
  });
});
