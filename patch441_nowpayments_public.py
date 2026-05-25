"""
PATCH-441 — NOWPayments as the live income path
================================================

Goal: a customer can hit /pricing, click "Get Solo", and pay in crypto.
Currently: button calls /api/billing/checkout/stripe which requires
Stripe LIVE keys we don't have.

Three changes:
  1. Add a PUBLIC POST /api/payments/nowpayments/checkout that accepts
     guest account IDs (no auth needed for guest flow — same pattern as
     /api/billing/checkout/stripe used)
  2. Seed the nowpayments_plans table with the 3 paid tiers
  3. Update pricing.html startCheckout() to call the new endpoint

NOTE: Pricing values come from the existing TIER_PRICES dict already
inside the GET /api/payments/checkout handler — keep them in sync.

LAST UPDATED: 2026-05-25
"""
import ast
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

NL = chr(10)

# ─── Step 1: seed nowpayments_plans ───────────────────────────────
print("▶ Step 1: seed nowpayments_plans (3 tiers × 2 intervals)")
BILLING_DB = "/var/lib/murphy-production/billing.db"
conn = sqlite3.connect(BILLING_DB)
now_iso = datetime.now(timezone.utc).isoformat()

PLANS = [
    # tier, interval, plan_id (synthetic — NOWPayments uses invoice-per-checkout, not subscriptions), monthly USD
    ("solo",     "monthly",  "np_solo_m",     99.0),
    ("solo",     "annual",   "np_solo_a",     950.0),   # 20% off ~99×12
    ("team",     "monthly",  "np_team_m",     399.0),
    ("team",     "annual",   "np_team_a",     3830.0),  # 20% off
    ("business", "monthly",  "np_business_m", 799.0),
    ("business", "annual",   "np_business_a", 7670.0),  # 20% off
]

for tier, interval, plan_id, amount in PLANS:
    conn.execute(
        "INSERT OR REPLACE INTO nowpayments_plans "
        "(tier, interval, plan_id, amount_usd, created_at) VALUES (?,?,?,?,?)",
        (tier, interval, plan_id, amount, now_iso)
    )
    print(f"  ✓ {tier:<10} {interval:<8} ${amount:>8.2f}  plan_id={plan_id}")
conn.commit()
conn.close()

# ─── Step 2: add a public POST endpoint to app.py ────────────────
print()
print("▶ Step 2: add public POST /api/payments/nowpayments/checkout")
APP = Path("/opt/Murphy-System/src/runtime/app.py")
src = APP.read_text()

if "PATCH-441" in src:
    print("  ⚠ PATCH-441 marker already present")
else:
    # Insert AFTER the existing GET /api/payments/checkout (line ~25945)
    # Anchor: the existing route ends with a return for an invoice URL.
    # Easier: anchor on the webhook decorator since that's stable.
    anchor = '    @app.post("/api/payments/nowpayments/webhook")'
    if anchor not in src:
        print("  ✗ webhook anchor not found")
        raise SystemExit(1)

    # Build the new route — public, accepts guest account IDs
    NEW_ROUTE = NL.join([
        "    # ── PATCH-441: public NOWPayments checkout (no auth required) ──",
        '    @app.post("/api/payments/nowpayments/checkout")',
        "    async def nowpayments_checkout_public(request: Request):",
        '        """Create a NOWPayments invoice for a guest or authenticated buyer.',
        "",
        "        Body: {",
        '          "account_id": "guest_<uuid>" or real account_id,',
        '          "email": "buyer@example.com" (required for guest),',
        '          "tier": "solo"|"team"|"business",',
        '          "interval": "monthly"|"annual",',
        '          "add_on": "system_influence" (optional)',
        "        }",
        "        Returns: {ok, checkout_url, payment_id, amount_usd}",
        '        """',
        "        import urllib.request as _ur, urllib.error as _ue, json as _json441",
        "        import sqlite3 as _sq441",
        "        from datetime import datetime as _dt441, timezone as _tz441",
        "        try:",
        "            body = await request.json()",
        "        except Exception:",
        "            body = {}",
        "        tier = body.get('tier', 'solo')",
        "        interval = body.get('interval', 'monthly')",
        "        add_on = body.get('add_on', '')",
        "        account_id = body.get('account_id', '')",
        "        email = body.get('email', '') or f'{account_id}@guest.murphy.systems'",
        "",
        "        # Look up the price from nowpayments_plans (PATCH-441 seeded)",
        "        try:",
        "            _c = _sq441.connect('/var/lib/murphy-production/billing.db')",
        "            row = _c.execute(",
        "                'SELECT amount_usd FROM nowpayments_plans WHERE tier=? AND interval=?',",
        "                (tier, interval)",
        "            ).fetchone()",
        "            _c.close()",
        "        except Exception as e:",
        "            return JSONResponse({'ok': False, 'error': f'plan_lookup_failed: {e}'}, status_code=500)",
        "        if not row:",
        "            return JSONResponse({'ok': False, 'error': f'unknown_plan: {tier}/{interval}'}, status_code=400)",
        "        amount = float(row[0])",
        "",
        "        # Add-on pricing",
        "        ADD_ON_PRICES = {'system_influence': 50.0}",
        "        if add_on in ADD_ON_PRICES:",
        "            amount += ADD_ON_PRICES[add_on]",
        "",
        "        api_key = os.environ.get('NOWPAYMENTS_API_KEY', '')",
        "        if not api_key:",
        "            return JSONResponse({'ok': False, 'error': 'NOWPAYMENTS_API_KEY not set'}, status_code=500)",
        "",
        "        order_id = f'{email}|{tier}|{interval}|{add_on}|{int(_dt441.now(_tz441.utc).timestamp())}'",
        "        payload = _json441.dumps({",
        "            'price_amount': amount,",
        "            'price_currency': 'usd',",
        "            'order_id': order_id,",
        "            'order_description': f'Murphy Systems — {tier.title()} ({interval})' + (f' + {add_on}' if add_on else ''),",
        "            'ipn_callback_url': 'https://murphy.systems/api/payments/nowpayments/webhook',",
        "            'success_url': 'https://murphy.systems/pricing?payment=success',",
        "            'cancel_url': 'https://murphy.systems/pricing?payment=cancelled',",
        "            'is_fixed_rate': True,",
        "        }).encode()",
        "",
        "        req = _ur.Request(",
        "            'https://api.nowpayments.io/v1/invoice',",
        "            data=payload,",
        "            headers={'x-api-key': api_key, 'Content-Type': 'application/json'},",
        "            method='POST',",
        "        )",
        "        try:",
        "            with _ur.urlopen(req, timeout=15) as resp:",
        "                invoice = _json441.loads(resp.read().decode())",
        "        except _ue.HTTPError as e:",
        "            err_body = e.read().decode()[:300] if hasattr(e, 'read') else ''",
        "            return JSONResponse({'ok': False, 'error': f'nowpayments_http_{e.code}', 'detail': err_body}, status_code=502)",
        "        except Exception as e:",
        "            return JSONResponse({'ok': False, 'error': f'nowpayments_call_failed: {e}'}, status_code=502)",
        "",
        "        # Record the pending billing row",
        "        try:",
        "            _c = _sq441.connect('/var/lib/murphy-production/billing.db')",
        "            _c.execute(",
        "                'INSERT INTO billing_records (id, tenant_id, email, tier, interval, plan_id, payment_id, status, amount_usd, created_at) '",
        "                'VALUES (?,?,?,?,?,?,?,?,?,?)',",
        "                (invoice.get('id', order_id), account_id or email, email, tier, interval, '',",
        "                 str(invoice.get('id', '')), 'pending', amount, _dt441.now(_tz441.utc).isoformat())",
        "            )",
        "            _c.commit()",
        "            _c.close()",
        "        except Exception as e:",
        "            # Non-fatal — log + continue",
        "            logger.warning(f'PATCH-441 billing_records insert failed: {e}')",
        "",
        "        return JSONResponse({",
        "            'ok': True,",
        "            'checkout_url': invoice.get('invoice_url'),",
        "            'payment_id': invoice.get('id'),",
        "            'amount_usd': amount,",
        "            'tier': tier,",
        "            'interval': interval,",
        "            'provider': 'nowpayments',",
        "        })",
        "",
        "",
    ])
    src = src.replace(anchor, NEW_ROUTE + anchor, 1)
    ast.parse(src)
    shutil.copy(APP, APP.with_suffix(".py.pre-441"))
    APP.write_text(src)
    print(f"  ✓ app.py written ({len(src)} bytes)")

# ─── Step 3: update pricing.html startCheckout() ─────────────────
print()
print("▶ Step 3: rewire pricing.html startCheckout() to NOWPayments")
PRICING = Path("/opt/Murphy-System/static/pricing.html")
src = PRICING.read_text()

if "PATCH-441" in src:
    print("  ⚠ pricing.html already patched")
else:
    OLD = "      const res = await fetch('/api/billing/checkout/stripe', {"
    NEW = "      // PATCH-441: NOWPayments crypto checkout (replaces Stripe)\n      const res = await fetch('/api/payments/nowpayments/checkout', {"
    if OLD in src:
        src = src.replace(OLD, NEW, 1)
        shutil.copy(PRICING, PRICING.with_suffix('.html.pre-441'))
        PRICING.write_text(src)
        print("  ✓ pricing.html now POSTs to /api/payments/nowpayments/checkout")
    else:
        print("  ⚠ couldn't find Stripe fetch anchor in pricing.html")

print()
print("✓ PATCH-441 file edits done — restart needed")
