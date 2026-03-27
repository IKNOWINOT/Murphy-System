
import bot from "../feedback_bot";
import { InputSchema, OutputSchema } from "../schema";
describe("feedback_bot", () => {
  it("ingests events", async () => {
    const input = { task:"ingest", params:{ events:[{ ts:new Date().toISOString(), bot:"ghost_controller_bot", value:1, meta:{category:"microtask.pass"} }] } } as any;
    const p = InputSchema.safeParse(input); expect(p.success).toBe(true);
    const out = await (bot as any).run(input, { userId:"u", tier:"free" });
    const v = OutputSchema.safeParse(out); expect(v.success).toBe(true);
  });
  it("analyzes scores", async () => {
    const input = { task:"analyze", params:{ strategy:"decay", half_life_days:3 } } as any;
    const out = await (bot as any).run(input, { userId:"u", tier:"free" });
    const v = OutputSchema.safeParse(out); expect(v.success).toBe(true);
  });
});
