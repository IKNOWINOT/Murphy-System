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
 * Memberships handler.
 * GET /api/memberships — list user's memberships
 * POST /api/memberships/attach — attach to org (or reactivate)
 * POST /api/memberships/detach — detach from org
 */
export async function handleMemberships(request: Request, env: Env, auth: AuthContext): Promise<Response> {
  const url = new URL(request.url);
  const path = url.pathname;
  const method = request.method;

  // GET /api/memberships
  if (path === '/api/memberships' && method === 'GET') {
    const memberships = await env.DB.prepare(
      `SELECT m.*, o.name as org_name, o.slug as org_slug
       FROM memberships m JOIN organizations o ON m.org_id = o.id
       WHERE m.user_id = ?`
    ).bind(auth.userId).all();
    return jsonResponse({ memberships: memberships.results });
  }

  // POST /api/memberships/attach
  if (path === '/api/memberships/attach' && method === 'POST') {
    const body = await request.json() as {
      org_id: string;
      position_title?: string;
      hierarchy_level?: number;
      reports_to_membership_id?: string;
      employment_contract_ref?: string;
    };

    // Check if membership exists (possibly detached)
    const existing = await env.DB.prepare(
      'SELECT * FROM memberships WHERE user_id = ? AND org_id = ?'
    ).bind(auth.userId, body.org_id).first();

    if (existing) {
      if (existing.status === 'active') {
        return jsonResponse({ error: 'Already an active member of this organization' }, 409);
      }
      // Reactivate
      await env.DB.prepare(
        `UPDATE memberships SET status = 'active', detached_at = NULL, attached_at = datetime('now')
         WHERE id = ?`
      ).bind(existing.id).run();

      // Reactivate suspended agent_org_assignments
      await env.DB.prepare(
        `UPDATE agent_org_assignments SET active = 1
         WHERE membership_id = ? AND active = 0`
      ).bind(existing.id).run();

      await env.DB.prepare(
        'INSERT INTO audit_log (id, event, user_id, details) VALUES (?, ?, ?, ?)'
      ).bind(generateId(), 'membership_reattached', auth.userId, JSON.stringify({ org_id: body.org_id })).run();

      return jsonResponse({ membership_id: existing.id, reattached: true });
    }

    // Create new membership
    const id = generateId();
    await env.DB.prepare(
      `INSERT INTO memberships (id, user_id, org_id, position_title, hierarchy_level, reports_to_membership_id, employment_contract_ref)
       VALUES (?, ?, ?, ?, ?, ?, ?)`
    ).bind(
      id, auth.userId, body.org_id,
      body.position_title ?? null,
      body.hierarchy_level ?? 0,
      body.reports_to_membership_id ?? null,
      body.employment_contract_ref ?? null
    ).run();

    await env.DB.prepare(
      'INSERT INTO audit_log (id, event, user_id, details) VALUES (?, ?, ?, ?)'
    ).bind(generateId(), 'membership_attached', auth.userId, JSON.stringify({ org_id: body.org_id })).run();

    return jsonResponse({ membership_id: id }, 201);
  }

  // POST /api/memberships/detach
  if (path === '/api/memberships/detach' && method === 'POST') {
    const body = await request.json() as { org_id: string };

    const membership = await env.DB.prepare(
      `SELECT * FROM memberships WHERE user_id = ? AND org_id = ? AND status = 'active'`
    ).bind(auth.userId, body.org_id).first();
    if (!membership) {
      return jsonResponse({ error: 'No active membership in this organization' }, 404);
    }

    // Set status to detached
    await env.DB.prepare(
      `UPDATE memberships SET status = 'detached', detached_at = datetime('now') WHERE id = ?`
    ).bind(membership.id).run();

    // Suspend (not delete) agent_org_assignments
    await env.DB.prepare(
      `UPDATE agent_org_assignments SET active = 0 WHERE membership_id = ?`
    ).bind(membership.id).run();

    // If detached org was active context, auto-switch to personal
    if (auth.activeContextType === 'organization' && auth.activeOrgId === body.org_id) {
      await env.DB.prepare(
        'UPDATE users SET active_context_type = ?, active_org_id = NULL WHERE id = ?'
      ).bind('personal', auth.userId).run();
    }

    await env.DB.prepare(
      'INSERT INTO audit_log (id, event, user_id, details) VALUES (?, ?, ?, ?)'
    ).bind(generateId(), 'membership_detached', auth.userId, JSON.stringify({ org_id: body.org_id })).run();

    return jsonResponse({ detached: true });
  }

  return jsonResponse({ error: 'Not found' }, 404);
}
