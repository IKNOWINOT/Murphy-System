
import bot from "../json_bot";
import { InputSchema, OutputSchema } from "../schema";

describe("json_bot v1.0", () => {
  it("parses JSON", async () => {
    const input = { task:"parse", params:{ input_format:"json" }, attachments:[{ type:"text", text:'{"a":1}' }] } as any;
    const p = InputSchema.safeParse(input); expect(p.success).toBe(true);
    const out = await (bot as any).run(input, { userId:"u", tier:"free" });
    const v = OutputSchema.safeParse(out); expect(v.success).toBe(true);
  });
  it("converts CSV to rows", async () => {
    const csv = "a,b\n1,2\n3,4\n";
    const input = { task:"convert", params:{ input_format:"csv" }, attachments:[{ type:"text", text: csv }] } as any;
    const out = await (bot as any).run(input, { userId:"u", tier:"free" });
    const v = OutputSchema.safeParse(out); expect(v.success).toBe(true);
    // @ts-ignore
    expect(Array.isArray(out.result.data.rows)).toBe(true);
  });
  it("diffs A/B", async () => {
    const input = { task:"diff", params:{}, attachments:[{type:"text",text:'{"x":1}'},{type:"text",text:'{"x":2}'}] } as any;
    const out = await (bot as any).run(input, { userId:"u", tier:"free" });
    const v = OutputSchema.safeParse(out); expect(v.success).toBe(true);
    // @ts-ignore
    expect(Array.isArray(out.result.diff)).toBe(true);
  });
});
