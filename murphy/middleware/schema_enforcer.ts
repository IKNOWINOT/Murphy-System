// Copyright © 2020 Inoni Limited Liability Company
// Creator: Corey Post
// License: BSL 1.1
/**
 * Schema Enforcer Middleware — TypeScript mirror
 *
 * Design Label: MURPHY-MIDDLEWARE-SCHEMA-TS-001
 * Owner: Platform Engineering
 *
 * Validates every inter-agent message against the AgentOutput Zod schema.
 * Rejects non-conforming messages with a typed error.
 */

import {
  AgentOutputSchema,
  ContentType,
  RenderType,
  validateAgentOutput,
  agentOutputFromError,
} from "../schemas/agent_output";
import type { AgentOutput } from "../schemas/agent_output";

export class SchemaEnforcementError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SchemaEnforcementError";
  }
}

/**
 * Validate an inter-agent message against the AgentOutput schema.
 * Throws SchemaEnforcementError on failure — never returns undefined.
 */
export function validateAgentMessage(raw: unknown): AgentOutput {
  try {
    return validateAgentOutput(raw);
  } catch (err) {
    throw new SchemaEnforcementError(
      `SCHEMA-ENFORCE-ERR-001: Message does not conform to AgentOutput — ${err}`
    );
  }
}

/**
 * Decorator-style wrapper for agent-to-agent calls.
 * Validates the return value against AgentOutput schema.
 */
export function enforceSchema<T extends (...args: any[]) => AgentOutput>(
  fn: T
): T {
  const wrapped = function (this: any, ...args: any[]): AgentOutput {
    let result: unknown;
    try {
      result = fn.apply(this, args);
    } catch (err) {
      console.error(`SCHEMA-ENFORCE-ERR-003: Agent call raised: ${err}`);
      return agentOutputFromError(
        "schema-enforcer",
        "SchemaEnforcer",
        `enforcement/${fn.name}`,
        "platform-engineering",
        `SCHEMA-ENFORCE-ERR-003: Agent call raised: ${err}`
      );
    }

    try {
      return validateAgentMessage(result);
    } catch (err) {
      console.error(`SCHEMA-ENFORCE-ERR-001: ${err}`);
      return agentOutputFromError(
        "schema-enforcer",
        "SchemaEnforcer",
        `enforcement/${fn.name}`,
        "platform-engineering",
        `${err}`
      );
    }
  };
  return wrapped as T;
}
