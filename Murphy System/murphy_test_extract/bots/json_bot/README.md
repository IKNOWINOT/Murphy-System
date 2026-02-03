
# JSONBot v1.0 — Trusted JSON I/O Gate (Bot-standards compliant)

**Scope**: safe parse/convert/validate/normalize/diff/patch/stream for JSON & nearby formats (safe YAML & XML subsets, CSV, INI, text), with privacy redaction, streaming, diagnostics, and Golden Path reuse.

## Register
- run: `src/clockwork/bots/json_bot/json_bot.ts::run`
- ping: `src/clockwork/bots/json_bot/rollcall.ts::ping`

## Examples
- Parse JSON:
```ts
await run({ task:"parse", params:{ input_format:"json" }, attachments:[{type:"text", text:'{"a":1}'}] }, ctx);
```
- Convert CSV:
```ts
await run({ task:"convert", params:{ input_format:"csv" }, attachments:[{type:"text", text:'a,b\n1,2\n'}] }, ctx);
```
- Validate:
```ts
await run({ task:"validate", params:{ input_format:"json", schema_json:{ type:"object", required:["a"], properties:{ a:{ type:"number" } } } }, attachments:[{type:"text", text:'{"a":1}'}] }, ctx);
```
- Normalize (keys & canonical JSON):
```ts
await run({ task:"normalize", params:{ input_format:"json", key_policy:"snake", output_format:"canonical_json" }, attachments:[{type:"text", text:'{"A Key":1}'}] }, ctx);
```
- Diff / Patch:
```ts
await run({ task:"diff", attachments:[{type:"text", text:'{"x":1}'},{type:"text", text:'{"x":2}'}] }, ctx);
await run({ task:"patch", params:{ patch:{ type:"json_patch", ops:[{op:"replace",path:"/x",value:2}] } }, attachments:[{type:"text", text:'{"x":1}'}] }, ctx);
```
- Stream NDJSON or arrays:
```ts
await run({ task:"stream", params:{ input_format:"json", stream:{max_objects:1000} }, attachments:[{type:"text", text:'{"a":1}\n{"a":2}\n'}] }, ctx);
```
