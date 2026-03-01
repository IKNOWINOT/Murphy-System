import type { Env } from '../worker';

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
 * Stripe webhook handler — verifies Stripe signature, no JWT auth.
 * POST /api/marketplace/webhook
 */
export async function handleStripe(request: Request, env: Env): Promise<Response> {
  const signature = request.headers.get('stripe-signature');
  if (!signature) {
    return jsonResponse({ error: 'Missing stripe-signature header' }, 400);
  }

  const rawBody = await request.text();

  // Verify Stripe webhook signature using Web Crypto
  const verified = await verifyStripeSignature(rawBody, signature, env.STRIPE_WEBHOOK_SECRET);
  if (!verified) {
    return jsonResponse({ error: 'Invalid signature' }, 400);
  }

  const event = JSON.parse(rawBody) as {
    type: string;
    data: { object: Record<string, unknown> };
  };

  switch (event.type) {
    case 'payment_intent.succeeded': {
      const paymentIntent = event.data.object;
      const paymentIntentId = paymentIntent.id as string;
      // Activate license
      await env.DB.prepare(
        `UPDATE marketplace_licenses SET status = 'active', licensed_at = datetime('now')
         WHERE stripe_payment_intent_id = ? AND status IN ('awaiting_payment', 'pending_payment')`
      ).bind(paymentIntentId).run();
      // Update agent status
      const license = await env.DB.prepare(
        'SELECT ml.*, mli.shadow_agent_id FROM marketplace_licenses ml JOIN marketplace_listings mli ON ml.listing_id = mli.id WHERE ml.stripe_payment_intent_id = ?'
      ).bind(paymentIntentId).first();
      if (license) {
        await env.DB.prepare(
          'UPDATE shadow_agents SET status = ? WHERE id = ?'
        ).bind('licensed', license.shadow_agent_id).run();
      }
      await env.DB.prepare(
        'INSERT INTO audit_log (id, event, user_id, details) VALUES (?, ?, ?, ?)'
      ).bind(generateId(), 'payment_succeeded', null, JSON.stringify({ payment_intent_id: paymentIntentId })).run();
      break;
    }
    case 'payment_intent.payment_failed': {
      const paymentIntent = event.data.object;
      const paymentIntentId = paymentIntent.id as string;
      await env.DB.prepare(
        `UPDATE marketplace_licenses SET status = 'payment_failed'
         WHERE stripe_payment_intent_id = ?`
      ).bind(paymentIntentId).run();
      await env.DB.prepare(
        'INSERT INTO audit_log (id, event, user_id, details) VALUES (?, ?, ?, ?)'
      ).bind(generateId(), 'payment_failed', null, JSON.stringify({ payment_intent_id: paymentIntentId })).run();
      break;
    }
    case 'account.updated': {
      const account = event.data.object;
      const accountId = account.id as string;
      const chargesEnabled = account.charges_enabled as boolean;
      if (chargesEnabled) {
        await env.DB.prepare(
          'UPDATE users SET stripe_onboarding_complete = 1 WHERE stripe_account_id = ?'
        ).bind(accountId).run();
      }
      break;
    }
    default:
      // Unhandled event type — acknowledge receipt
      break;
  }

  return jsonResponse({ received: true });
}

/**
 * Verify Stripe webhook signature (v1 scheme) using Web Crypto API.
 */
async function verifyStripeSignature(
  payload: string,
  signatureHeader: string,
  secret: string
): Promise<boolean> {
  const elements = signatureHeader.split(',');
  let timestamp = '';
  let signatures: string[] = [];
  for (const element of elements) {
    const [key, value] = element.split('=');
    if (key === 't') timestamp = value;
    if (key === 'v1') signatures.push(value);
  }
  if (!timestamp || signatures.length === 0) return false;

  const signedPayload = `${timestamp}.${payload}`;
  const key = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  );
  const mac = await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(signedPayload));
  const expectedSignature = Array.from(new Uint8Array(mac))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');

  return signatures.some((sig) => timingSafeEqual(sig, expectedSignature));
}

function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let result = 0;
  for (let i = 0; i < a.length; i++) {
    result |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return result === 0;
}
