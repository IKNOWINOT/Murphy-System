
import bot from "../rubixcube_bot";
import { InputSchema, OutputSchema } from "../schema";

describe("rubixcube_bot v1.0", () => {
  it("computes stats and a CI", async () => {
    const input = { task:"stats", params:{ data:[1,2,3,4,5] } } as any;
    const out1 = await (bot as any).run(input, { userId:"u", tier:"free", db:{} as any });
    const ci = await (bot as any).run({ task:"ci", params:{ data:[1,2,3,4,5], alpha:0.05 } }, { userId:"u", tier:"free", db:{} as any });
    const v = OutputSchema.safeParse(ci);
    expect(v.success).toBe(true);
  });
  it("simulates probability event", async () => {
    const sim = await (bot as any).run({ task:"simulate", params:{ dist:{name:"normal",params:[0,1]}, runs:5000, event:{op:"gt", threshold:1.96} } }, { userId:"u", tier:"free", db:{} as any });
    const v = OutputSchema.safeParse(sim);
    expect(v.success).toBe(true);
  });
});
