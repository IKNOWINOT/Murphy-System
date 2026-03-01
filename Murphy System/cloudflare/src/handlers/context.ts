import type { Env, AuthContext } from '../worker';

function jsonResponse(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

/**
 * Context switching handler.
 * GET /api/context — return current context
 * PUT /api/context — switch between personal and organization
 */
export async function handleContext(request: Request, env: Env, auth: AuthContext): Promise<Response> {
  const method = request.method;

  // GET /api/context
  if (method === 'GET') {
    return jsonResponse({
      active_context_type: auth.activeContextType,
      active_org_id: auth.activeOrgId,
      user_id: auth.userId,
      display_name: auth.displayName,
    });
  }

  // PUT /api/context
  if (method === 'PUT') {
    const body = await request.json() as {
      context_type: 'personal' | 'organization';
      org_id?: string;
    };

    if (body.context_type === 'organization') {
      if (!body.org_id) {
        return jsonResponse({ error: 'org_id is required for organization context' }, 400);
      }

      // Verify active membership exists
      const membership = await env.DB.prepare(
        `SELECT * FROM memberships WHERE user_id = ? AND org_id = ? AND status = 'active'`
      ).bind(auth.userId, body.org_id).first();
      if (!membership) {
        return jsonResponse({ error: 'No active membership in this organization' }, 403);
      }

      await env.DB.prepare(
        'UPDATE users SET active_context_type = ?, active_org_id = ? WHERE id = ?'
      ).bind('organization', body.org_id, auth.userId).run();

      return jsonResponse({
        active_context_type: 'organization',
        active_org_id: body.org_id,
      });
    }

    if (body.context_type === 'personal') {
      await env.DB.prepare(
        'UPDATE users SET active_context_type = ?, active_org_id = NULL WHERE id = ?'
      ).bind('personal', auth.userId).run();

      return jsonResponse({
        active_context_type: 'personal',
        active_org_id: null,
      });
    }

    return jsonResponse({ error: 'Invalid context_type. Must be personal or organization' }, 400);
  }

  return jsonResponse({ error: 'Method not allowed' }, 405);
}
