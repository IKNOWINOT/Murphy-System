
import bot from "../optimization_bot";
import { InputSchema, OutputSchema } from "../schema";

describe("optimization_bot v1.0", () => {
  it("proposes and starts an experiment, assigns and tracks", async () => {
    const propose = { task:"propose", params:{ target_bot:"engineering_bot", area:"prompt_schema_mismatch" } } as any;
    const outP = await (bot as any).run(propose, { userId:"u", tier:"free", db:{} as any });
    const start = { task:"start", params:{ target_bot:"engineering_bot", area:"prompt_schema_mismatch", arms:[{arm_id:"A",spec:{}},{arm_id:"B",spec:{}}] } } as any;
    const outS = await (bot as any).run(start, { userId:"u", tier:"free", db:{} as any, kv:{} as any });
    const exp_id = outS.result.exp_id;
    const assign = { task:"assign", params:{ exp_id } } as any;
    const outA = await (bot as any).run(assign, { userId:"u", tier:"free", db:{} as any, kv:{} as any });
    const track = { task:"track", params:{ exp_id, arm_id: outA.result.assignment.arm_id, reward: 1.0 } } as any;
    const outT = await (bot as any).run(track, { userId:"u", tier:"free", db:{} as any });
    const v = OutputSchema.safeParse(outT);
    expect(v.success).toBe(true);
  });
});
