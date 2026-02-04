// src/clockwork/bots/bot_base/internal/adapters/from_code.ts
// Adapter: Coding bot (diffs, errors) → bot_base Input
import type { Input } from '../../schema';
export function fromCodingBot(evt: any): Input {
  const task = evt?.summary || 'fix and test code changes';
  const attachments = evt?.diff ? [{ type: 'text', text: String(evt.diff).slice(0, 5000) }] : undefined;
  return { task, attachments, params: { path: evt?.path, tests: evt?.tests } };
}
