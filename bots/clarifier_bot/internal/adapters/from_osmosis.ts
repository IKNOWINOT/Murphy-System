// src/clockwork/bots/clarifier_bot/internal/adapters/from_osmosis.ts
import type { Input } from '../../schema';
export function fromOsmosis(payload: any): Input {
  const task = payload?.intent?.summary || payload?.title || 'clarify document requirements';
  const attachments = (payload?.snippets || []).map((s: any) => ({ type: 'text', text: s }));
  return { task, attachments, params: payload?.entities || {} };
}
