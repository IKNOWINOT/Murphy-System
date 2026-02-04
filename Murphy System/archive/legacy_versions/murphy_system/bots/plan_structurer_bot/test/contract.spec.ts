
import bot from "../plan_structurer_bot";
import { InputSchema, OutputSchema } from "../schema";

describe("plan_structurer_bot v1.0", () => {
  it("clarifies then builds a template and plan", async () => {
    const input = { task:"build", params:{ goal:"Make me an app like Discord", domain:"product", return_explain:true, store:false } } as any;
    const p = InputSchema.safeParse(input); expect(p.success).toBe(true);
    const out = await (bot as any).run(input, { userId:"u", tier:"free", db:{} as any });
    const v = OutputSchema.safeParse(out);
    expect(v.success).toBe(true);
  });
});
