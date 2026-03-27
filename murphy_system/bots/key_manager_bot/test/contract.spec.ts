
import bot from "../key_manager_bot";
import { InputSchema, OutputSchema } from "../schema";

describe("key_manager_bot contract", () => {
  it("registers and mints ephemeral token", async () => {
    const reg = { task:"register_key", params:{ bot_name:"ghost_controller_bot", scope:"openai.read", key_id:"k_test", key_value:"sk_XXXX" } } as any;
    const out1 = await (bot as any).run(reg, { userId:"u", tier:"free", env:{KEK_SECRET:"dev"}, db:{} as any });
    const mint = { task:"mint_ephemeral", params:{ bot_name:"ghost_controller_bot", scope:"openai.read", ttl_s:120 } } as any;
    const out2 = await (bot as any).run(mint, { userId:"u", tier:"free", env:{EPHEMERAL_SECRET:"dev"} });
    expect(out2.result.artifact).toBeTruthy();
  });
});
