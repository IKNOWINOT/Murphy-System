// src/clockwork/bots/clarifier_bot/internal/adapters/from_code.ts
import type { Input } from '../../schema';
export function fromCodingBot(evt: any): Input {
  const task = evt?.summary || 'clarify failing tests and requirements';
  const attachments = evt?.diff ? [{ type: 'text', text: String(evt.diff).slice(0, 5000) }] : undefined;
  return { task, attachments, params: { path: evt?.path, tests: evt?.tests } };
}
