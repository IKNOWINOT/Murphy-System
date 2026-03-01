import { jwtVerify } from 'jose';
import { handleLLMKeys } from './handlers/llm-keys';
import { handleStripe } from './handlers/stripe';
import { handleMarketplace } from './handlers/marketplace';
import { handleContext } from './handlers/context';
import { handleMemberships } from './handlers/memberships';
import { handleDecisions } from './handlers/decisions';
import { NegotiationSession } from './durable-objects/negotiation-session';
import { ShadowAgentState } from './durable-objects/shadow-agent-state';

export { NegotiationSession, ShadowAgentState };

export interface Env {
  // D1
  DB: D1Database;
  // R2
  AGENT_ARTIFACTS: R2Bucket;
  // Queues
  APPROVAL_QUEUE: Queue;
  // Durable Objects
  NEGOTIATION_SESSION: DurableObjectNamespace;
  SHADOW_AGENT_STATE: DurableObjectNamespace;
  // Secrets (stored via wrangler secret put)
  STRIPE_SECRET_KEY: string;
  STRIPE_PUBLISHABLE_KEY: string;
  STRIPE_WEBHOOK_SECRET: string;
  JWT_SECRET: string;
  SERVICE_TOKEN: string;
  FOUNDER_ASSIGNMENT_SECRET: string;
  LLM_PROVIDER_KEYS_JSON: string;
  // Vars
  ENVIRONMENT: string;
  PLATFORM_FEE_PERCENT: string;
  FAIRNESS_THRESHOLD: string;
  MIN_COMPATIBILITY_SCORE: string;
}

export interface AuthContext {
  userId: string;
  displayName: string;
  activeContextType: string;
  activeOrgId: string | null;
  roles: string[];
}

export const SUPPORTED_LLM_PROVIDERS: Record<string, string> = {
  openai: 'https://openai.com/policies/terms-of-use',
  anthropic: 'https://www.anthropic.com/terms',
  google: 'https://ai.google.dev/gemini-api/terms',
  azure_openai: 'https://www.microsoft.com/licensing/terms',
  mistral: 'https://mistral.ai/terms/',
  groq: 'https://groq.com/terms-of-use/',
  cohere: 'https://cohere.com/terms-of-use',
  together: 'https://www.together.ai/terms-of-service',
  fireworks: 'https://fireworks.ai/terms-of-service',
  perplexity: 'https://www.perplexity.ai/hub/terms-of-service',
  deepseek: 'https://platform.deepseek.com/terms',
  xai: 'https://x.ai/legal/terms-of-service',
  meta_llama: 'https://ai.meta.com/llama/license/',
  aws_bedrock: 'https://aws.amazon.com/service-terms/',
  cloudflare_ai: 'https://www.cloudflare.com/terms/',
};

function jsonResponse(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

async function authenticate(request: Request, env: Env): Promise<AuthContext | Response> {
  const authHeader = request.headers.get('Authorization');
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return jsonResponse({ error: 'Missing or invalid Authorization header' }, 401);
  }
  const token = authHeader.slice(7);
  try {
    const secret = new TextEncoder().encode(env.JWT_SECRET);
    const { payload } = await jwtVerify(token, secret);
    const userId = payload.sub as string;
    if (!userId) {
      return jsonResponse({ error: 'Invalid token: missing subject' }, 401);
    }
    const user = await env.DB.prepare('SELECT * FROM users WHERE id = ?').bind(userId).first();
    if (!user) {
      return jsonResponse({ error: 'User not found' }, 401);
    }
    let roles: string[] = [];
    try {
      roles = JSON.parse(user.roles_json as string);
    } catch {
      roles = [];
    }
    return {
      userId: user.id as string,
      displayName: user.display_name as string,
      activeContextType: user.active_context_type as string,
      activeOrgId: user.active_org_id as string | null,
      roles,
    };
  } catch {
    return jsonResponse({ error: 'Invalid or expired token' }, 401);
  }
}

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);
    const path = url.pathname;
    const method = request.method;

    // Public routes (no auth)
    if (path === '/api/health' && method === 'GET') {
      return jsonResponse({ status: 'ok', environment: env.ENVIRONMENT });
    }

    if (path === '/api/providers' && method === 'GET') {
      return jsonResponse({ providers: SUPPORTED_LLM_PROVIDERS });
    }

    // Stripe webhook (verified by Stripe signature, not JWT)
    if (path === '/api/marketplace/webhook' && method === 'POST') {
      return handleStripe(request, env);
    }

    // All other routes require JWT auth
    const authResult = await authenticate(request, env);
    if (authResult instanceof Response) {
      return authResult;
    }
    const auth: AuthContext = authResult;

    // Context switching
    if (path.startsWith('/api/context')) {
      return handleContext(request, env, auth);
    }

    // Memberships
    if (path.startsWith('/api/memberships')) {
      return handleMemberships(request, env, auth);
    }

    // Shadow agents
    if (path.startsWith('/api/shadow-agents')) {
      return handleShadowAgents(request, env, auth);
    }

    // BYOK LLM keys
    if (path.startsWith('/api/llm-keys')) {
      return handleLLMKeys(request, env, auth);
    }

    // Negotiations
    if (path.startsWith('/api/negotiations')) {
      return handleNegotiations(request, env, auth);
    }

    // Marketplace (authenticated)
    if (path.startsWith('/api/marketplace')) {
      return handleMarketplace(request, env, auth);
    }

    // HITL decisions
    if (path.startsWith('/api/decisions')) {
      return handleDecisions(request, env, auth);
    }

    return jsonResponse({ error: 'Not found' }, 404);
  },

  async queue(batch: MessageBatch, env: Env): Promise<void> {
    for (const message of batch.messages) {
      const body = message.body as { type: string; decisionId: string; [key: string]: unknown };
      if (body.type === 'hitl_approval') {
        try {
          await env.DB.prepare(
            'UPDATE pending_decisions SET status = ? WHERE id = ? AND status = ?'
          ).bind('pending', body.decisionId, 'pending').run();
          message.ack();
        } catch {
          message.retry();
        }
      } else {
        message.ack();
      }
    }
  },
};

function generateId(): string {
  return crypto.randomUUID();
}

async function handleShadowAgents(request: Request, env: Env, auth: AuthContext): Promise<Response> {
  const url = new URL(request.url);
  const method = request.method;

  if (method === 'GET') {
    const agents = await env.DB.prepare(
      'SELECT * FROM shadow_agents WHERE owner_user_id = ?'
    ).bind(auth.userId).all();
    return jsonResponse({ agents: agents.results });
  }

  if (method === 'POST') {
    const body = await request.json() as Record<string, unknown>;
    const id = generateId();
    await env.DB.prepare(
      `INSERT INTO shadow_agents (id, owner_user_id, primary_role_id, department, position_context, training_infra_fingerprint, governance_boundary, permissions)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?)`
    ).bind(
      id, auth.userId,
      body.primary_role_id ?? null, body.department ?? null,
      body.position_context ?? null, body.training_infra_fingerprint ?? null,
      body.governance_boundary ?? null, body.permissions ? JSON.stringify(body.permissions) : null
    ).run();
    await env.DB.prepare(
      'INSERT INTO audit_log (id, event, user_id, details) VALUES (?, ?, ?, ?)'
    ).bind(generateId(), 'shadow_agent_created', auth.userId, JSON.stringify({ agent_id: id })).run();
    return jsonResponse({ id }, 201);
  }

  if (method === 'PUT') {
    const body = await request.json() as Record<string, unknown>;
    const agentId = url.pathname.split('/').pop();
    const agent = await env.DB.prepare(
      'SELECT * FROM shadow_agents WHERE id = ? AND owner_user_id = ?'
    ).bind(agentId, auth.userId).first();
    if (!agent) {
      return jsonResponse({ error: 'Agent not found or not owned by you' }, 404);
    }
    await env.DB.prepare(
      `UPDATE shadow_agents SET primary_role_id = ?, department = ?, position_context = ?, governance_boundary = ?, permissions = ?
       WHERE id = ? AND owner_user_id = ?`
    ).bind(
      body.primary_role_id ?? agent.primary_role_id,
      body.department ?? agent.department,
      body.position_context ?? agent.position_context,
      body.governance_boundary ?? agent.governance_boundary,
      body.permissions ? JSON.stringify(body.permissions) : agent.permissions,
      agentId, auth.userId
    ).run();
    return jsonResponse({ updated: true });
  }

  if (method === 'DELETE') {
    const agentId = url.pathname.split('/').pop();
    const agent = await env.DB.prepare(
      'SELECT * FROM shadow_agents WHERE id = ? AND owner_user_id = ?'
    ).bind(agentId, auth.userId).first();
    if (!agent) {
      return jsonResponse({ error: 'Agent not found or not owned by you' }, 404);
    }
    await env.DB.prepare(
      'UPDATE shadow_agents SET status = ? WHERE id = ?'
    ).bind('revoked', agentId).run();
    await env.DB.prepare(
      'INSERT INTO audit_log (id, event, user_id, details) VALUES (?, ?, ?, ?)'
    ).bind(generateId(), 'shadow_agent_revoked', auth.userId, JSON.stringify({ agent_id: agentId })).run();
    return jsonResponse({ revoked: true });
  }

  return jsonResponse({ error: 'Method not allowed' }, 405);
}

async function handleNegotiations(request: Request, env: Env, auth: AuthContext): Promise<Response> {
  const url = new URL(request.url);
  const method = request.method;

  if (method === 'POST' && url.pathname === '/api/negotiations') {
    const body = await request.json() as Record<string, unknown>;
    if (auth.activeContextType !== 'organization' || !auth.activeOrgId) {
      return jsonResponse({ error: 'Must be in organization context to negotiate' }, 403);
    }
    const id = generateId();
    const doId = env.NEGOTIATION_SESSION.idFromName(id);
    await env.DB.prepare(
      `INSERT INTO negotiations (id, initiator_org_id, responder_org_id, subject, durable_object_id, status, expires_at)
       VALUES (?, ?, ?, ?, ?, 'proposed', ?)`
    ).bind(
      id, auth.activeOrgId, body.responder_org_id as string,
      body.subject as string ?? null, doId.toString(),
      body.expires_at as string ?? null
    ).run();

    const stub = env.NEGOTIATION_SESSION.get(doId);
    await stub.fetch(new Request('https://internal/propose', {
      method: 'POST',
      body: JSON.stringify({
        negotiationId: id,
        initiatorOrgId: auth.activeOrgId,
        responderOrgId: body.responder_org_id,
        proposal: body.proposal,
        fairnessThreshold: parseFloat(env.FAIRNESS_THRESHOLD),
      }),
    }));

    return jsonResponse({ id, durable_object_id: doId.toString() }, 201);
  }

  if (method === 'GET' && url.pathname === '/api/negotiations') {
    if (auth.activeContextType !== 'organization' || !auth.activeOrgId) {
      return jsonResponse({ error: 'Must be in organization context' }, 403);
    }
    const negotiations = await env.DB.prepare(
      `SELECT * FROM negotiations WHERE initiator_org_id = ? OR responder_org_id = ? ORDER BY created_at DESC`
    ).bind(auth.activeOrgId, auth.activeOrgId).all();
    return jsonResponse({ negotiations: negotiations.results });
  }

  // Route to durable object for specific negotiation actions
  const parts = url.pathname.split('/');
  if (parts.length >= 4) {
    const negotiationId = parts[3];
    const action = parts[4];
    const negotiation = await env.DB.prepare(
      'SELECT * FROM negotiations WHERE id = ?'
    ).bind(negotiationId).first();
    if (!negotiation) {
      return jsonResponse({ error: 'Negotiation not found' }, 404);
    }
    const doId = env.NEGOTIATION_SESSION.idFromName(negotiationId);
    const stub = env.NEGOTIATION_SESSION.get(doId);
    const doUrl = `https://internal/${action || 'status'}`;
    const doRequest = new Request(doUrl, {
      method: method,
      body: method !== 'GET' ? JSON.stringify({
        ...(await request.json() as Record<string, unknown>),
        userId: auth.userId,
        orgId: auth.activeOrgId,
        fairnessThreshold: parseFloat(env.FAIRNESS_THRESHOLD),
      }) : undefined,
    });
    return stub.fetch(doRequest);
  }

  return jsonResponse({ error: 'Not found' }, 404);
}
