// src/clockwork/bots/clarifier_bot/internal/adapters/from_ghost.ts
import type { Input } from '../../schema';
export function fromGhostController(session: any): Input {
  const task = session?.activeIntent || 'clarify next steps from user activity';
  const observations = (session?.events || []).slice(-50);
  return { task, observations, params: { windowMs: session?.windowMs } };
}
