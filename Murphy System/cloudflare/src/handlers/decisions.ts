import type { Env, AuthContext } from '../worker';

function jsonResponse(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function generateId(): string {
  return crypto.randomUUID();
}

/**
 * HITL (Human-in-the-Loop) decisions handler.
 * GET /api/decisions — list pending decisions for user's org
 * POST /api/decisions/:id/approve — approve a decision
 * POST /api/decisions/:id/reject — reject a decision
 */
export async function handleDecisions(request: Request, env: Env, auth: AuthContext): Promise<Response> {
  const url = new URL(request.url);
  const path = url.pathname;
  const method = request.method;

  // GET /api/decisions — list pending decisions for user's org
  if (path === '/api/decisions' && method === 'GET') {
    if (auth.activeContextType !== 'organization' || !auth.activeOrgId) {
      return jsonResponse({ error: 'Must be in organization context to view decisions' }, 403);
    }

    const decisions = await env.DB.prepare(
      `SELECT pd.* FROM pending_decisions pd
       JOIN agent_org_assignments aoa ON pd.agent_assignment_id = aoa.id
       JOIN memberships m ON aoa.membership_id = m.id
       WHERE m.org_id = ? AND pd.status = 'pending'
       ORDER BY pd.priority DESC, pd.created_at ASC`
    ).bind(auth.activeOrgId).all();

    return jsonResponse({ decisions: decisions.results });
  }

  // POST /api/decisions/:id/approve
  const approveMatch = path.match(/^\/api\/decisions\/([^/]+)\/approve$/);
  if (approveMatch && method === 'POST') {
    const decisionId = approveMatch[1];

    if (auth.activeContextType !== 'organization' || !auth.activeOrgId) {
      return jsonResponse({ error: 'Must be in organization context' }, 403);
    }

    const decision = await env.DB.prepare(
      `SELECT pd.*, aoa.membership_id FROM pending_decisions pd
       JOIN agent_org_assignments aoa ON pd.agent_assignment_id = aoa.id
       WHERE pd.id = ? AND pd.status = 'pending'`
    ).bind(decisionId).first();
    if (!decision) {
      return jsonResponse({ error: 'Decision not found or already processed' }, 404);
    }

    // Check hierarchy — higher level can approve lower
    const approverMembership = await env.DB.prepare(
      `SELECT * FROM memberships WHERE user_id = ? AND org_id = ? AND status = 'active'`
    ).bind(auth.userId, auth.activeOrgId).first();
    const targetMembership = await env.DB.prepare(
      'SELECT * FROM memberships WHERE id = ?'
    ).bind(decision.membership_id).first();

    if (approverMembership && targetMembership) {
      if ((approverMembership.hierarchy_level as number) <= (targetMembership.hierarchy_level as number)) {
        return jsonResponse({ error: 'Insufficient hierarchy level to approve this decision' }, 403);
      }
    }

    await env.DB.prepare(
      `UPDATE pending_decisions SET status = 'approved', decided_by = ?, decided_at = datetime('now')
       WHERE id = ?`
    ).bind(auth.userId, decisionId).run();

    await env.DB.prepare(
      'INSERT INTO audit_log (id, event, user_id, details) VALUES (?, ?, ?, ?)'
    ).bind(generateId(), 'decision_approved', auth.userId, JSON.stringify({ decision_id: decisionId })).run();

    return jsonResponse({ approved: true });
  }

  // POST /api/decisions/:id/reject
  const rejectMatch = path.match(/^\/api\/decisions\/([^/]+)\/reject$/);
  if (rejectMatch && method === 'POST') {
    const decisionId = rejectMatch[1];

    if (auth.activeContextType !== 'organization' || !auth.activeOrgId) {
      return jsonResponse({ error: 'Must be in organization context' }, 403);
    }

    const decision = await env.DB.prepare(
      'SELECT * FROM pending_decisions WHERE id = ? AND status = ?'
    ).bind(decisionId, 'pending').first();
    if (!decision) {
      return jsonResponse({ error: 'Decision not found or already processed' }, 404);
    }

    const body = await request.json() as { notes?: string };

    await env.DB.prepare(
      `UPDATE pending_decisions SET status = 'rejected', decided_by = ?, decided_at = datetime('now'), notes = ?
       WHERE id = ?`
    ).bind(auth.userId, body.notes ?? null, decisionId).run();

    await env.DB.prepare(
      'INSERT INTO audit_log (id, event, user_id, details) VALUES (?, ?, ?, ?)'
    ).bind(generateId(), 'decision_rejected', auth.userId, JSON.stringify({ decision_id: decisionId, notes: body.notes })).run();

    return jsonResponse({ rejected: true });
  }

  return jsonResponse({ error: 'Not found' }, 404);
}
