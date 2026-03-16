# code_translator_bot — Combined Code Translator + Coding Bot (PURE), Bot-standards compliant
Capabilities:
- Translate between languages, refactor, fix, format, document, explain
- Generate diffs/patches and optional unit tests
- Integrates quotas, budgets, Golden Paths, stability S(t), and observability per the canvas

## Input
- `task`: natural-language goal (e.g., "translate to Go", "fix bug", "refactor and add tests")
- `params`: { source_code?, src_lang?, target_lang?, intent?, filename? }
- Attach code as text attachments if not passed in params

## Output
- `result.patches[]`: { before?, after, diff?, filename?, language? }
- `result.tests[]`: optional generated tests
- `result.explain`: optional summary & key points

## Register
- run: `src/clockwork/bots/code_translator_bot/code_translator_bot.ts::run`
- ping: `src/clockwork/bots/code_translator_bot/rollcall.ts::ping`
