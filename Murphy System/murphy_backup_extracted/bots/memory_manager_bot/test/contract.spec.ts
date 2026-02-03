
import bot from "../memory_manager_bot";
import { InputSchema, OutputSchema } from "../schema";

describe("memory_manager_bot v1.0", () => {
  it("adds and searches a memory", async () => {
    const add = { task:"add", params:{ text:"remember to water plants", tenant:"t1" } } as any;
    const out1 = await (bot as any).run(add, { userId:"u", tier:"free", db:{} as any });
    const search = { task:"search", params:{ query:"water", tenant:"t1", top_k:10 } } as any;
    const out2 = await (bot as any).run(search, { userId:"u", tier:"free", db:{} as any });
    const v = OutputSchema.safeParse(out2);
    expect(v.success).toBe(true);
  });
});
