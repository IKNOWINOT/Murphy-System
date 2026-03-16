
import { InputSchema } from '../schema';
import bot from '../ghost_controller_bot';
describe('ghost_controller_bot contract', ()=>{
  it('returns structured result', async ()=>{
    const input = { task:'synthesize_automation', params:{ privacy:{redact:true} }, attachments:[{ type:'events', text:'[2025-01-01T00:00:00Z] focus: {"title":"Docs"}' }] } as any;
    const p = InputSchema.safeParse(input); expect(p.success).toBe(true);
    const out = await (bot as any).run(input, { userId:'u', tier:'free' });
    expect(out.result).toBeTruthy();
  });
});
