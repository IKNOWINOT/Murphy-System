// src/clockwork/bots/clarifier_bot/test/contract.spec.ts
import { InputSchema, OutputSchema } from '../schema';
import { run } from '../clarifier_bot';

describe('clarifier_bot contract', () => {
  it('produces a structured clarification plan', async () => {
    const input = { task: 'Prepare a report for leadership', attachments: [{ type:'text', text:'We need report, include budget and units' }] };
    const parsed = InputSchema.safeParse(input);
    expect(parsed.success).toBe(true);
    const out = await run(input as any, { userId: 'u1', tier: 'free' } as any);
    const v = OutputSchema.safeParse(out);
    expect(v.success).toBe(true);
    // @ts-ignore
    expect(out.result.clarification.questions.length).toBeGreaterThan(0);
  });
});
