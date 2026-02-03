
import bot from "../librarian_bot";
import { InputSchema, OutputSchema } from "../schema";

describe("librarian_bot v1.1", () => {
  it("ingests and searches hybrid with facets", async () => {
    const ingest = { task:"ingest", params:{ doc:{ id:"doc1", title:"Spec", text:"Pump curve and spec doc", tags:["project:alpha","type:spec"] } } } as any;
    const out1 = await (bot as any).run(ingest, { userId:"u", tier:"free", db:{} as any });
    const search = { task:"search", params:{ query:"pump", tags:["project:alpha"], limit:10, rerank:true, facets:true } } as any;
    const out2 = await (bot as any).run(search, { userId:"u", tier:"pro", db:{} as any });
    const v = OutputSchema.safeParse(out2);
    expect(v.success).toBe(true);
  });
});
