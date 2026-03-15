// src/clockwork/bots/code_translator_bot/test/contract.spec.ts
import { InputSchema, OutputSchema } from '../schema';
import { run } from '../code_translator_bot';

describe('code_translator_bot contract', () => {
  it('produces patches and optional tests', async () => {
    const input = { task: 'translate to TypeScript and add tests', params: { source_code: 'var x = 1 == 1;', src_lang: 'JavaScript', target_lang: 'TypeScript', filename:'app.js', intent:'translate' } };
    const parsed = InputSchema.safeParse(input);
    expect(parsed.success).toBe(true);
    const out = await run(input as any, { userId: 'u1', tier: 'free' } as any);
    const v = OutputSchema.safeParse(out);
    expect(v.success).toBe(true);
    // @ts-ignore
    expect(out.result.patches.length).toBeGreaterThan(0);
  });
});
