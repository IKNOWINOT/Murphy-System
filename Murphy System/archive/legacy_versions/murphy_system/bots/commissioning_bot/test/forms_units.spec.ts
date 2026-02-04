// src/clockwork/bots/commissioning_bot/test/forms_units.spec.ts
import { InputSchema, OutputSchema } from '../schema';
import { run } from '../commissioning_bot';

describe('commissioning_bot enhancements', () => {
  it('generates FPT forms and normalizes units', async () => {
    const input = { task: 'Commission AHU-1', params: { system:'HVAC', assets_hint:['AHU-1'], desired_units: { '°F':'°C' } } };
    const parsed = InputSchema.safeParse(input);
    expect(parsed.success).toBe(true);
    const out = await run(input as any, { userId: 'u1', tier: 'free' } as any);
    const v = OutputSchema.safeParse(out);
    expect(v.success).toBe(true);
    // @ts-ignore
    expect(Array.isArray(out.meta.forms)).toBe(true);
  });
});
