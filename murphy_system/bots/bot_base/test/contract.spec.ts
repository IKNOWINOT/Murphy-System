// src/clockwork/bots/bot_base/test/contract.spec.ts
import { InputSchema, OutputSchema } from '../schema';
import { run } from '../bot_base';

describe('bot_base contract', () => {
  it('returns Output for a simple task', async () => {
    const input = { task: 'plan and create a short draft' };
    const parsed = InputSchema.safeParse(input);
    expect(parsed.success).toBe(true);
    const out = await run(input as any, { userId: 'u1', tier: 'free' } as any);
    const v = OutputSchema.safeParse(out);
    expect(v.success).toBe(true);
  });
});
