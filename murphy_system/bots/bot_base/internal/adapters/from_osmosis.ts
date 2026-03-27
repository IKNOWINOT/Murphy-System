// src/clockwork/bots/bot_base/internal/adapters/from_osmosis.ts
// Adapter: Osmosis (document/semantic extraction) → bot_base Input
import type { Input } from '../../schema';
export function fromOsmosis(payload: any): Input {
  const task = payload?.intent?.summary || payload?.title || 'process osmosis content';
  const attachments = (payload?.snippets || []).map((s: any) => ({ type: 'text', text: s }));
  return { task, params: payload?.entities || {}, attachments };
}
