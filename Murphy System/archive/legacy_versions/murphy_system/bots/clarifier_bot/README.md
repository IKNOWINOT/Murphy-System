# clarifier_bot — PURE (no aionmind_core), Bot-standards compliant
Purpose: detect ambiguity and generate a prioritized set of clarifying questions, assumptions, and next steps to unblock execution. Groups questions by blocking/non-blocking and provides safe defaults when possible.

## Output (primary)
`result.clarification`:
- `questions[]`: { id, field, text, short?, expected_format?, example?, options?, default?, blocking, rationale, when? }
- `assumptions[]`: inferred defaults with confidence
- `missing_fields[]`: blocking fields
- `next_steps[]`: microtasks to resolve questions or apply defaults
- `field_schema[]`: recommended fields with types/required

## Register
- run: `src/clockwork/bots/clarifier_bot/clarifier_bot.ts::run`
- ping: `src/clockwork/bots/clarifier_bot/rollcall.ts::ping`

## Quickstart
```ts
import { run } from 'src/clockwork/bots/clarifier_bot/clarifier_bot';
const out = await run({ task: 'Draft SOW for data pipeline' }, { userId: 'u1', tier: 'free' });
console.log(out.result.clarification);
```
