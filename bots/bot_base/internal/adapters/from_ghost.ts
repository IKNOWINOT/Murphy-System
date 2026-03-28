// src/clockwork/bots/bot_base/internal/adapters/from_ghost.ts
// Adapter: GhostController (telemetry) → bot_base Input
import type { Input } from '../../schema';
export function fromGhostController(session: any): Input {
  const task = session?.activeIntent || 'synthesize automation microtasks';
  const observations = (session?.events || []).slice(-50);
  return { task, observations, params: { windowMs: session?.windowMs } };
}
