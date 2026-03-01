import type { Env, AuthContext } from '../worker';
import { SUPPORTED_LLM_PROVIDERS } from '../worker';

function jsonResponse(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function generateId(): string {
  return crypto.randomUUID();
}

export async function handleLLMKeys(request: Request, env: Env, auth: AuthContext): Promise<Response> {
  const url = new URL(request.url);
  const method = request.method;

  // GET /api/llm-keys — list user's configured providers + all available providers
  if (method === 'GET') {
    const keys = await env.DB.prepare(
      'SELECT id, provider, display_label, is_active, created_at FROM user_llm_keys WHERE user_id = ?'
    ).bind(auth.userId).all();

    const configuredProviders = keys.results.map((k) => ({
      provider: k.provider,
      display_label: k.display_label,
      is_active: k.is_active,
      created_at: k.created_at,
    }));

    const allProviders = Object.entries(SUPPORTED_LLM_PROVIDERS).map(([provider, termsUrl]) => {
      const configured = keys.results.find((k) => k.provider === provider);
      return {
        provider,
        terms_url: termsUrl,
        configured: !!configured,
        is_active: configured ? configured.is_active : false,
      };
    });

    return jsonResponse({
      configured: configuredProviders,
      available: allProviders,
    });
  }

  // PUT /api/llm-keys — store a key (requires terms acceptance)
  if (method === 'PUT') {
    const body = await request.json() as {
      provider: string;
      key: string;
      displayLabel?: string;
      acceptTerms?: boolean;
    };

    if (!body.provider || !body.key) {
      return jsonResponse({ error: 'provider and key are required' }, 400);
    }

    if (!SUPPORTED_LLM_PROVIDERS[body.provider]) {
      return jsonResponse({ error: `Unsupported provider: ${body.provider}` }, 400);
    }

    if (!body.acceptTerms) {
      return jsonResponse({
        error: 'You must accept the provider terms of service',
        terms_url: SUPPORTED_LLM_PROVIDERS[body.provider],
        provider: body.provider,
      }, 400);
    }

    const termsUrl = SUPPORTED_LLM_PROVIDERS[body.provider];

    // Record terms acknowledgement
    await env.DB.prepare(
      `INSERT INTO provider_acknowledgements (id, user_id, provider, terms_url, ip_address)
       VALUES (?, ?, ?, ?, ?)
       ON CONFLICT(user_id, provider) DO UPDATE SET acknowledged_at = datetime('now'), terms_url = ?, ip_address = ?`
    ).bind(
      generateId(), auth.userId, body.provider, termsUrl,
      request.headers.get('CF-Connecting-IP') ?? 'unknown',
      termsUrl, request.headers.get('CF-Connecting-IP') ?? 'unknown'
    ).run();

    // Store the key (encrypted_key stores the raw key — in production, encrypt with a KMS)
    await env.DB.prepare(
      `INSERT INTO user_llm_keys (id, user_id, provider, encrypted_key, display_label)
       VALUES (?, ?, ?, ?, ?)
       ON CONFLICT(user_id, provider) DO UPDATE SET encrypted_key = ?, display_label = ?, is_active = 1`
    ).bind(
      generateId(), auth.userId, body.provider, body.key,
      body.displayLabel ?? body.provider,
      body.key, body.displayLabel ?? body.provider
    ).run();

    // Audit log
    await env.DB.prepare(
      'INSERT INTO audit_log (id, event, user_id, details) VALUES (?, ?, ?, ?)'
    ).bind(
      generateId(), 'llm_key_stored', auth.userId,
      JSON.stringify({ provider: body.provider, terms_accepted: true, terms_url: termsUrl })
    ).run();

    return jsonResponse({ stored: true, provider: body.provider });
  }

  // DELETE /api/llm-keys?provider=X — remove a key
  if (method === 'DELETE') {
    const provider = url.searchParams.get('provider');
    if (!provider) {
      return jsonResponse({ error: 'provider query parameter is required' }, 400);
    }

    await env.DB.prepare(
      'DELETE FROM user_llm_keys WHERE user_id = ? AND provider = ?'
    ).bind(auth.userId, provider).run();

    await env.DB.prepare(
      'INSERT INTO audit_log (id, event, user_id, details) VALUES (?, ?, ?, ?)'
    ).bind(
      generateId(), 'llm_key_removed', auth.userId,
      JSON.stringify({ provider })
    ).run();

    return jsonResponse({ deleted: true, provider });
  }

  return jsonResponse({ error: 'Method not allowed' }, 405);
}
