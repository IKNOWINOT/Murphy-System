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
 * Marketplace handler — authenticated routes.
 */
export async function handleMarketplace(request: Request, env: Env, auth: AuthContext): Promise<Response> {
  const url = new URL(request.url);
  const path = url.pathname;
  const method = request.method;

  // POST /api/marketplace/onboard — create Stripe Express connected account
  if (path === '/api/marketplace/onboard' && method === 'POST') {
    const stripeResponse = await fetch('https://api.stripe.com/v1/accounts', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${env.STRIPE_SECRET_KEY}`,
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: 'type=express',
    });
    const account = await stripeResponse.json() as { id: string };

    await env.DB.prepare(
      'UPDATE users SET stripe_account_id = ? WHERE id = ?'
    ).bind(account.id, auth.userId).run();

    // Create account link for onboarding
    const linkResponse = await fetch('https://api.stripe.com/v1/account_links', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${env.STRIPE_SECRET_KEY}`,
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: new URLSearchParams({
        account: account.id,
        refresh_url: `${url.origin}/api/marketplace/onboard`,
        return_url: `${url.origin}/api/marketplace/dashboard`,
        type: 'account_onboarding',
      }).toString(),
    });
    const link = await linkResponse.json() as { url: string };

    await env.DB.prepare(
      'INSERT INTO audit_log (id, event, user_id, details) VALUES (?, ?, ?, ?)'
    ).bind(generateId(), 'stripe_onboarding_started', auth.userId, JSON.stringify({ account_id: account.id })).run();

    return jsonResponse({ stripe_account_id: account.id, onboarding_url: link.url });
  }

  // POST /api/marketplace/list — list a shadow agent on marketplace
  if (path === '/api/marketplace/list' && method === 'POST') {
    const body = await request.json() as {
      shadow_agent_id: string;
      title: string;
      description?: string;
      infra_requirements?: string;
      license_terms?: string;
      human_in_loop_required?: boolean;
    };

    const agent = await env.DB.prepare(
      'SELECT * FROM shadow_agents WHERE id = ? AND owner_user_id = ?'
    ).bind(body.shadow_agent_id, auth.userId).first();
    if (!agent) {
      return jsonResponse({ error: 'Agent not found or not owned by you' }, 404);
    }

    const id = generateId();
    await env.DB.prepare(
      `INSERT INTO marketplace_listings (id, shadow_agent_id, listed_by_user_id, title, description, infra_requirements, license_terms, human_in_loop_required)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?)`
    ).bind(
      id, body.shadow_agent_id, auth.userId, body.title,
      body.description ?? null, body.infra_requirements ?? null,
      body.license_terms ?? null, body.human_in_loop_required !== false ? 1 : 0
    ).run();

    await env.DB.prepare(
      'UPDATE shadow_agents SET is_marketplace_listed = 1 WHERE id = ?'
    ).bind(body.shadow_agent_id).run();

    await env.DB.prepare(
      'INSERT INTO audit_log (id, event, user_id, details) VALUES (?, ?, ?, ?)'
    ).bind(generateId(), 'marketplace_listing_created', auth.userId, JSON.stringify({ listing_id: id })).run();

    return jsonResponse({ id }, 201);
  }

  // GET /api/marketplace/search?infra={JSON} — search with infra compatibility scoring
  if (path === '/api/marketplace/search' && method === 'GET') {
    const infraParam = url.searchParams.get('infra');
    const minScore = parseFloat(env.MIN_COMPATIBILITY_SCORE);
    const listings = await env.DB.prepare(
      `SELECT ml.*, sa.training_infra_fingerprint FROM marketplace_listings ml
       JOIN shadow_agents sa ON ml.shadow_agent_id = sa.id
       WHERE ml.status = 'active'`
    ).all();

    let infraQuery: Record<string, string> | null = null;
    if (infraParam) {
      try {
        infraQuery = JSON.parse(infraParam);
      } catch {
        return jsonResponse({ error: 'Invalid infra JSON' }, 400);
      }
    }

    const results = listings.results.map((listing) => {
      let score = 1.0;
      if (infraQuery && listing.infra_requirements) {
        score = computeInfraCompatibility(
          infraQuery,
          typeof listing.infra_requirements === 'string'
            ? JSON.parse(listing.infra_requirements)
            : listing.infra_requirements as Record<string, string>
        );
      }
      return { ...listing, compatibility_score: score };
    }).filter((r) => r.compatibility_score >= minScore)
      .sort((a, b) => b.compatibility_score - a.compatibility_score);

    return jsonResponse({ results });
  }

  // POST /api/marketplace/license — create pending license
  if (path === '/api/marketplace/license' && method === 'POST') {
    const body = await request.json() as {
      listing_id: string;
      licensee_org_id: string;
    };

    const listing = await env.DB.prepare(
      'SELECT * FROM marketplace_listings WHERE id = ? AND status = ?'
    ).bind(body.listing_id, 'active').first();
    if (!listing) {
      return jsonResponse({ error: 'Listing not found or not active' }, 404);
    }

    const id = generateId();
    await env.DB.prepare(
      `INSERT INTO marketplace_licenses (id, listing_id, licensee_org_id, license_terms_snapshot, status)
       VALUES (?, ?, ?, ?, 'pending_owner_approval')`
    ).bind(id, body.listing_id, body.licensee_org_id, listing.license_terms).run();

    // Queue HITL approval
    await env.APPROVAL_QUEUE.send({
      type: 'hitl_approval',
      decisionId: id,
      listingId: body.listing_id,
      licenseeOrgId: body.licensee_org_id,
    });

    await env.DB.prepare(
      'INSERT INTO audit_log (id, event, user_id, details) VALUES (?, ?, ?, ?)'
    ).bind(generateId(), 'license_requested', auth.userId, JSON.stringify({ license_id: id })).run();

    return jsonResponse({ id, status: 'pending_owner_approval' }, 201);
  }

  // POST /api/marketplace/pay — create Stripe PaymentIntent
  if (path === '/api/marketplace/pay' && method === 'POST') {
    const body = await request.json() as {
      license_id: string;
      amount: number;
      currency?: string;
    };

    const license = await env.DB.prepare(
      `SELECT ml.*, mli.listed_by_user_id FROM marketplace_licenses ml
       JOIN marketplace_listings mli ON ml.listing_id = mli.id
       WHERE ml.id = ?`
    ).bind(body.license_id).first();
    if (!license) {
      return jsonResponse({ error: 'License not found' }, 404);
    }

    // Get seller's stripe account
    const seller = await env.DB.prepare(
      'SELECT stripe_account_id FROM users WHERE id = ?'
    ).bind(license.listed_by_user_id).first();
    if (!seller?.stripe_account_id) {
      return jsonResponse({ error: 'Seller has not completed Stripe onboarding' }, 400);
    }

    const feePercent = parseFloat(env.PLATFORM_FEE_PERCENT);
    const applicationFee = Math.round(body.amount * feePercent / 100);

    const piResponse = await fetch('https://api.stripe.com/v1/payment_intents', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${env.STRIPE_SECRET_KEY}`,
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: new URLSearchParams({
        amount: body.amount.toString(),
        currency: body.currency ?? 'usd',
        application_fee_amount: applicationFee.toString(),
        'transfer_data[destination]': seller.stripe_account_id as string,
      }).toString(),
    });
    const paymentIntent = await piResponse.json() as { id: string; client_secret: string };

    await env.DB.prepare(
      `UPDATE marketplace_licenses SET stripe_payment_intent_id = ?, status = 'awaiting_payment'
       WHERE id = ?`
    ).bind(paymentIntent.id, body.license_id).run();

    return jsonResponse({
      payment_intent_id: paymentIntent.id,
      client_secret: paymentIntent.client_secret,
    });
  }

  // POST /api/marketplace/refund — refund via Stripe, revoke license
  if (path === '/api/marketplace/refund' && method === 'POST') {
    const body = await request.json() as { license_id: string };

    const license = await env.DB.prepare(
      'SELECT * FROM marketplace_licenses WHERE id = ?'
    ).bind(body.license_id).first();
    if (!license || !license.stripe_payment_intent_id) {
      return jsonResponse({ error: 'License not found or no payment to refund' }, 404);
    }

    await fetch('https://api.stripe.com/v1/refunds', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${env.STRIPE_SECRET_KEY}`,
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: new URLSearchParams({
        payment_intent: license.stripe_payment_intent_id as string,
      }).toString(),
    });

    await env.DB.prepare(
      'UPDATE marketplace_licenses SET status = ? WHERE id = ?'
    ).bind('revoked', body.license_id).run();

    await env.DB.prepare(
      'INSERT INTO audit_log (id, event, user_id, details) VALUES (?, ?, ?, ?)'
    ).bind(generateId(), 'license_refunded', auth.userId, JSON.stringify({ license_id: body.license_id })).run();

    return jsonResponse({ refunded: true });
  }

  // GET /api/marketplace/dashboard — seller dashboard
  if (path === '/api/marketplace/dashboard' && method === 'GET') {
    const user = await env.DB.prepare(
      'SELECT stripe_account_id, stripe_onboarding_complete FROM users WHERE id = ?'
    ).bind(auth.userId).first();
    if (!user?.stripe_account_id) {
      return jsonResponse({ error: 'No Stripe account connected' }, 400);
    }

    // Get balance
    const balanceResponse = await fetch(
      `https://api.stripe.com/v1/balance`,
      {
        headers: {
          'Authorization': `Bearer ${env.STRIPE_SECRET_KEY}`,
          'Stripe-Account': user.stripe_account_id as string,
        },
      }
    );
    const balance = await balanceResponse.json();

    // Count active licenses
    const myListings = await env.DB.prepare(
      'SELECT id FROM marketplace_listings WHERE listed_by_user_id = ?'
    ).bind(auth.userId).all();
    const listingIds = myListings.results.map((l) => l.id);

    let activeLicenses = 0;
    if (listingIds.length > 0) {
      // Use individual queries to avoid dynamic SQL interpolation
      let count = 0;
      for (const listingId of listingIds) {
        const result = await env.DB.prepare(
          `SELECT COUNT(*) as count FROM marketplace_licenses WHERE listing_id = ? AND status = 'active'`
        ).bind(listingId).first();
        count += (result?.count as number) ?? 0;
      }
      activeLicenses = count;
    }

    return jsonResponse({
      stripe_account_id: user.stripe_account_id,
      onboarding_complete: user.stripe_onboarding_complete,
      balance,
      active_licenses: activeLicenses,
    });
  }

  return jsonResponse({ error: 'Not found' }, 404);
}

/**
 * Murphy 5D uncertainty-based infrastructure compatibility scoring.
 * Dimensions: UD (platform), UI (runtime), UD (databases), UR (scale), UG (domain)
 */
function computeInfraCompatibility(
  query: Record<string, string>,
  requirements: Record<string, string>
): number {
  const dimensions = ['platform', 'runtime', 'databases', 'scale', 'domain'];
  const weights = [0.25, 0.2, 0.2, 0.15, 0.2];
  let totalScore = 0;

  for (let i = 0; i < dimensions.length; i++) {
    const dim = dimensions[i];
    const qVal = (query[dim] ?? '').toLowerCase();
    const rVal = (requirements[dim] ?? '').toLowerCase();
    if (!qVal || !rVal) {
      totalScore += weights[i]; // No constraint = full score
    } else if (qVal === rVal) {
      totalScore += weights[i];
    } else if (rVal === 'any' || qVal.includes(rVal) || rVal.includes(qVal)) {
      totalScore += weights[i] * 0.7;
    } else {
      totalScore += 0;
    }
  }

  return Math.round(totalScore * 100) / 100;
}
