#!/usr/bin/env python3
"""
PCR-047 — block enterprise tier from automated NOWPayments checkout

FINDING (audit 2026-06-09 01:00 PT, Shape-of-Complete sweep):
  /api/payments/nowpayments/checkout happily creates a $0 NOWPayments
  invoice when called with tier=enterprise/* because the
  nowpayments_plans table has amount_usd=0.0 for enterprise rows.

  The source-of-truth comment in nowpayments_billing.py:66 says:
    # enterprise is manual invoice — not automated

  So this is a checked-in design intent that the runtime route never
  enforced. Result: an anonymous user can click "Buy Enterprise" and
  complete a $0 payment, potentially triggering an enterprise upgrade
  for free.

FIX:
  Add an explicit guard at the top of the checkout handler that
  returns a 400 with a customer-friendly message + sales-contact
  redirect for enterprise tier. This is a Pillar 4 fix
  (EXECUTES — produces designed output for the actual input set).

SCOPE: single marker patch at the checkout handler in app.py.

REVERSIBILITY: --verify and --revert. Marker-anchored, safe.
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

APP = Path("/opt/Murphy-System/src/runtime/app.py")

# The exact anchor — right after `tier = body.get('tier', 'solo')` block
OLD = '''        tier = body.get('tier', 'solo')
        interval = body.get('interval', 'monthly')
        add_on = body.get('add_on', '')
        account_id = body.get('account_id', '')
        email = body.get('email', '') or f'{account_id}@guest.murphy.systems'

        # Look up the price from nowpayments_plans (PATCH-441 seeded)'''

NEW = '''        tier = body.get('tier', 'solo')
        interval = body.get('interval', 'monthly')
        add_on = body.get('add_on', '')
        account_id = body.get('account_id', '')
        email = body.get('email', '') or f'{account_id}@guest.murphy.systems'

        # PCR-047 — enterprise is manual-invoice only (per
        # nowpayments_billing.py:66). Block automated checkout to
        # prevent the $0-invoice bypass and route buyer to sales.
        if (tier or '').lower() == 'enterprise':
            return JSONResponse({
                'ok': False,
                'error': 'enterprise_requires_sales_contact',
                'message': 'Enterprise tier is custom-quoted. Email sales@murphy.systems or use the Contact Sales button to get started.',
                'contact_email': 'sales@murphy.systems',
                'contact_url': '/contact?subject=Enterprise+inquiry',
            }, status_code=400)

        # Look up the price from nowpayments_plans (PATCH-441 seeded)'''


def _patch(verify, revert):
    src = APP.read_text(encoding="utf-8")
    marker = "PCR-047 — enterprise is manual-invoice only"
    if revert:
        if marker not in src:
            print("  · already absent"); return 0
        if NEW not in src:
            print("  ✗ new anchor not found in current file"); return 1
        src = src.replace(NEW, OLD, 1)
        if verify:
            print("  ✓ would revert"); return 0
        APP.write_text(src, encoding="utf-8")
        print("  ✓ reverted"); return 0
    if marker in src:
        print("  · already present"); return 0
    if OLD not in src:
        print("  ✗ old anchor not found"); return 1
    if src.count(OLD) > 1:
        print(f"  ✗ anchor matches {src.count(OLD)} places — refusing"); return 1
    src = src.replace(OLD, NEW, 1)
    if verify:
        print("  ✓ would apply"); return 0
    APP.write_text(src, encoding="utf-8")
    print("  ✓ applied"); return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--revert", action="store_true")
    a = ap.parse_args()
    print(f"PCR-047 enterprise checkout gate  verify={a.verify}  revert={a.revert}")
    return _patch(a.verify, a.revert)


if __name__ == "__main__":
    sys.exit(main())
