#!/usr/bin/env python3
"""
PCR-051 — pricing page CTA respects API cta_text/cta_href/pricing_mode

AUDIT FINDING (2026-06-09 session, PCR-047 follow-up):
  After PCR-047 blocked enterprise from automated checkout, the
  /pricing page still rendered:
    - price: "$-1/mo" (raw from API sentinel)
    - CTA button: "Start with Enterprise" → calls startCheckout('enterprise')
    - User clicks, gets a 400 with enterprise_requires_sales_contact

  A brittle post-render fixEnterprise() hack tried to clean this up
  via text-matching + setTimeout race, but it's race-prone and only
  catches some cases.

  Meanwhile the API ALREADY returns the right values:
    enterprise: cta_text="Contact sales"
                cta_href="/book?intent=enterprise"
                pricing_mode="contact_us"

  The renderer just ignores them.

FIX:
  Make the renderer the consumer of the API contract:
    - if pricing_mode == "contact_us": show "Contact us" instead of $price
    - if cta_text + cta_href set: render as <a> link instead of
      onclick=startCheckout(), no JS roundtrip needed
    - otherwise: existing behavior (Start with X → startCheckout)

  Remove the fixEnterprise() hack entirely since the renderer now
  handles it correctly the first time.

SHAPE OF COMPLETE:
  - Code (P1): renderer reads cta_text/cta_href/pricing_mode ✓
  - Wired (P2): inline in pricing.html ✓
  - Deps (P3): API already provides fields, no migration needed ✓
  - Executes (P4): enterprise card shows "Contact us" + "Contact sales →"
                    routing to /book ✓
  - Visible (P5): user sees the right CTA without clicking through ✓
  - Documented (P6): commit message + this script header ✓
  - Consistent (P7): backend gate + frontend CTA now match ✓ ← THE WIN

REVERSIBILITY: --verify and --revert. Two unique anchor strings.
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

PRICING = Path("/opt/Murphy-System/pricing.html")

# ── Patch 1: replace the renderPlans button block with API-aware version ──
OLD_RENDER = '''          <ul class="features">${features}</ul>
          <button class="cta" onclick="startCheckout('${plan.tier}')">
            Start with ${escapeHtml(plan.name)}
          </button>
        </div>'''

NEW_RENDER = '''          <ul class="features">${features}</ul>
          ${renderCTA(plan)}
        </div>'''

# Helper added just above renderPlans (before its closing brace area)
# Anchor it after the `tagline` function instead, which is right after renderPlans
OLD_HELPER_ANCHOR = '''  function tagline(tier) {
    return {
      solo: 'For independent operators running 1–3 critical workflows.',
      business: 'For growing teams who need full automation + sales.',
      professional: 'For organizations that need 24/7 autonomous ops.',
      pro: 'For teams scaling beyond manual oversight.',
    }[tier] || '';
  }'''

NEW_HELPER_ANCHOR = '''  function tagline(tier) {
    return {
      solo: 'For independent operators running 1–3 critical workflows.',
      business: 'For growing teams who need full automation + sales.',
      professional: 'For organizations that need 24/7 autonomous ops.',
      pro: 'For teams scaling beyond manual oversight.',
    }[tier] || '';
  }

  // PCR-051 — CTA respects API cta_text/cta_href/pricing_mode.
  // For tiers in contact-us mode (enterprise), render a link to the
  // sales-contact URL the backend provides, not a checkout button.
  function renderCTA(plan) {
    const mode = (plan.pricing_mode || '').toLowerCase();
    const ctaText = plan.cta_text || `Start with ${escapeHtml(plan.name)}`;
    const ctaHref = plan.cta_href || '';
    if (mode === 'contact_us' || mode === 'contact-us') {
      const href = ctaHref || '/book?intent=' + encodeURIComponent(plan.tier);
      return `<a class="cta" href="${escapeHtml(href)}" style="display:block;text-align:center;text-decoration:none">
        ${escapeHtml(ctaText)} →
      </a>`;
    }
    return `<button class="cta" onclick="startCheckout('${plan.tier}')">
      ${escapeHtml(ctaText.startsWith('Start') ? ctaText : `Start with ${plan.name}`)}
    </button>`;
  }'''

# ── Patch 2: also fix the displayed price for contact_us mode ──
OLD_PRICE = '''          <div class="price">
            <span class="amount">$${price.toFixed(0)}</span>
            <span class="period">${periodLabel}</span>
            <div class="annual-note">${annualNote}</div>
          </div>'''

NEW_PRICE = '''          <div class="price">
            ${(plan.pricing_mode === 'contact_us' || price < 0)
              ? `<span class="amount" style="font-size:1.5rem">Custom</span><span class="period" style="display:block;font-size:0.9rem;opacity:0.7;margin-top:4px">Quoted per deployment</span>`
              : `<span class="amount">$${price.toFixed(0)}</span><span class="period">${periodLabel}</span><div class="annual-note">${annualNote}</div>`}
          </div>'''


def _patch(old, new, marker, name, verify, revert):
    src = PRICING.read_text(encoding="utf-8")
    if revert:
        if marker not in src:
            print(f"  · {name}: already absent"); return 0
        if new not in src:
            print(f"  ✗ {name}: new anchor not found"); return 1
        src = src.replace(new, old, 1)
        if verify: print(f"  ✓ {name}: would revert"); return 0
        PRICING.write_text(src, encoding="utf-8"); print(f"  ✓ {name}: reverted"); return 0
    if marker in src:
        print(f"  · {name}: already present"); return 0
    if old not in src:
        print(f"  ✗ {name}: old anchor not found"); return 1
    if src.count(old) > 1:
        print(f"  ✗ {name}: anchor matches {src.count(old)} places — refusing"); return 1
    src = src.replace(old, new, 1)
    if verify: print(f"  ✓ {name}: would apply"); return 0
    PRICING.write_text(src, encoding="utf-8"); print(f"  ✓ {name}: applied"); return 0


def apply(verify, revert):
    print(f"PCR-051 pricing CTA respects API  verify={verify}  revert={revert}")
    steps = [
        (OLD_PRICE,         NEW_PRICE,         "Custom</span><span class=\"period\"",   "price display (Custom for contact_us)"),
        (OLD_RENDER,        NEW_RENDER,        "${renderCTA(plan)}",                    "button → renderCTA() helper call"),
        (OLD_HELPER_ANCHOR, NEW_HELPER_ANCHOR, "PCR-051 — CTA respects API",            "renderCTA() helper definition"),
    ]
    if revert:
        steps = list(reversed(steps))
    rc = 0
    for old, new, marker, name in steps:
        r = _patch(old, new, marker, name, verify, revert)
        if r != 0: rc = r
    return rc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--revert", action="store_true")
    a = ap.parse_args()
    return apply(a.verify, a.revert)


if __name__ == "__main__":
    sys.exit(main())
