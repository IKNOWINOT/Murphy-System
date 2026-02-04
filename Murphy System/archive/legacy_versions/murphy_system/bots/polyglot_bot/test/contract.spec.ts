
import bot from "../polyglot_bot";
import { InputSchema, OutputSchema } from "../schema";

describe("polyglot_bot v1.0", () => {
  it("translates a short text with glossary", async () => {
    const input = { task:"translate", params:{ source_lang:"en", target_lang:"ja", glossary:{ "Acme":"アクメ" } }, attachments:[{ type:"text", text:"Welcome to Acme" }] } as any;
    const p = InputSchema.safeParse(input); expect(p.success).toBe(true);
    const out = await (bot as any).run(input, { userId:"u", tier:"free", db:{} as any });
    const v = OutputSchema.safeParse(out); expect(v.success).toBe(true);
  });
  it("transpiles python to javascript", async () => {
    const input = { task:"transpile", params:{ transpile:{ to:"javascript" } }, attachments:[{ type:"code", language:"python", text:"def hello(name):\n    print(name)" }] } as any;
    const out = await (bot as any).run(input, { userId:"u", tier:"free", db:{} as any });
    const v = OutputSchema.safeParse(out); expect(v.success).toBe(true);
  });
});
