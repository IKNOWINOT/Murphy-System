// src/clockwork/bots/anomaly_watcher_bot/test/contract.spec.ts
import { InputSchema, OutputSchema } from '../schema';
import { run } from '../anomaly_watcher_bot';

describe('anomaly_watcher_bot contract', () => {
  it('returns Output for a simple anomaly task', async () => {
    const input = { task: 'detect error rate spike and open incident if needed' };
    const parsed = InputSchema.safeParse(input);
    expect(parsed.success).toBe(true);
    const out = await run(input as any, { userId: 'u1', tier: 'free' } as any);
    const v = OutputSchema.safeParse(out);
    expect(v.success).toBe(true);
  });
});
