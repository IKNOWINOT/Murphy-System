// src/clockwork/bots/analysisbot/test/contract.spec.ts
import { InputSchema, OutputSchema } from '../schema';
import { run } from '../analysisbot';

describe('analysisbot contract', () => {
  it('returns Output for a simple task', async () => {
    const input = { task: 'analyze risk and recommend next steps' };
    const parsed = InputSchema.safeParse(input);
    expect(parsed.success).toBe(true);
    const out = await run(input as any, { userId: 'u1', tier: 'free' } as any);
    const v = OutputSchema.safeParse(out);
    expect(v.success).toBe(true);
  });
});
