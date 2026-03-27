
import bot from "../multimodal_describer_bot";
import { InputSchema, OutputSchema } from "../schema";

describe("multimodal_describer_bot v1.0", () => {
  it("describes a tiny image and audio", async () => {
    const image = [[[255,0,0],[0,255,0]],[[0,0,255],[255,255,255]]];  // 2x2 pixels
    const audio = [0,1000,-1000,500,-500,0];
    const input = { task:"describe", params:{ verbosity:"normal" }, attachments:[
      { type:"image", text: JSON.stringify(image) },
      { type:"audio", text: JSON.stringify(audio) }
    ] } as any;
    const p = InputSchema.safeParse(input); expect(p.success).toBe(true);
    const out = await (bot as any).run(input, { userId:"u", tier:"free" } as any);
    const v = OutputSchema.safeParse(out); expect(v.success).toBe(true);
  });
});
