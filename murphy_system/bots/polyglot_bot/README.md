
# polyglot_bot — Multilingual translator & code transpiler (Bot-standards compliant)

**Scope:** Translation (text/code-aware), transpile (py↔js), language detection, TTC clarifiers/templates, caching, and Golden Paths. No raw SDK calls; budget/S(t)/quotas/observability integrated.

## Tasks
- `clarify` (5W1H), `translate`, `translate_batch`, `transpile`, `detect`, `explain`, `normalize`, `romanize`, `route`, `store_template`

## Example
```ts
await run({
  task: "translate",
  params: { source_lang: "en", target_lang: "ja", glossary:{ "Acme":"アクメ" } },
  attachments: [{ type:"text", text:"Welcome to Acme" }]
}, ctx);
```
