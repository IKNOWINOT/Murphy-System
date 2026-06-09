#!/usr/bin/env python3
"""
PCR-051b — remove now-dead fixEnterprise() post-render hack

CONTEXT:
  PCR-051 made renderPlans() the source of truth for enterprise CTA
  by consuming the API's cta_text/cta_href/pricing_mode. The
  fixEnterprise() block (R442 era) was a setTimeout-based DOM patch
  that ran 500ms + 2000ms after page load to rewrite '$-1' → 'Contact
  us' and 'Start with Enterprise' → 'Contact sales'.

  As of PCR-051, the renderer produces the correct DOM on first paint:
    - price box shows 'Custom / Quoted per deployment'
    - CTA is an <a href="/book?intent=enterprise">Contact sales →</a>

  fixEnterprise() now runs and finds nothing matching its selectors
  (no '$-1' text, no buttons with 'Start|Subscribe' text inside an
  enterprise card). Harmless — but dead code is cognitive overhead
  for the next person reading the file and it executes two setTimeout
  callbacks for zero effect every page load.

FIX:
  Remove the entire IIFE block (the R442 _QUOTE_RENDER script). One
  anchor: the full block as a single string. Reversible via --revert.

VERIFICATION:
  - /pricing still 200
  - enterprise card still shows 'Custom' + 'Contact sales →' link
    routing to /book?intent=enterprise
  - browser console no longer logs setTimeout entries for fixEnterprise

NO RISK:
  - Backend untouched
  - Renderer (PCR-051) handles all the cases this hack covered
  - Even if PCR-051 ever regressed, the worst case is users see '$-1/mo'
    until we re-patch — they're already blocked from checkout by the
    PCR-047 backend gate
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

PRICING = Path("/opt/Murphy-System/pricing.html")

OLD_BLOCK = '''
<!-- _R442_QUOTE_RENDER -->
<script>
(function(){
  // Replace any rendered "$0/mo" or "$-1" for the Enterprise tier with "Contact us".
  // Runs after the plans renderer finishes.
  function fixEnterprise(){
    document.querySelectorAll('[data-tier="enterprise"], .plan-enterprise, .tier-enterprise').forEach(el=>{
      el.querySelectorAll('.price, .monthly, .annual, [data-price]').forEach(p=>{
        const t = (p.textContent||'').trim();
        if(t==='$0' || t==='$0/mo' || t==='$-1' || t==='$-1/mo' || t==='-$1' || t.includes('-1')){
          p.textContent = 'Contact us';
          p.style.fontSize = '1.4rem';
        }
      });
      // Replace CTA "Subscribe" → "Contact sales" on enterprise card
      el.querySelectorAll('a.btn, button.btn, .cta, [data-cta]').forEach(btn=>{
        if(/subscribe|start|sign up|get started/i.test(btn.textContent||'')){
          btn.textContent = 'Contact sales →';
          btn.href = '/book?intent=enterprise';
        }
      });
    });
    // Also handle the simpler case where price renders raw from API: any element
    // whose text starts with "$" and contains "-1" or "0/mo" inside enterprise card.
    document.querySelectorAll('.tier, .plan, .card').forEach(card=>{
      const name = (card.querySelector('h2,h3,.plan-name')||{}).textContent||'';
      if(/enterprise/i.test(name)){
        card.setAttribute('data-tier','enterprise');
        card.classList.add('plan-enterprise');
        // recursively fix
        card.querySelectorAll('*').forEach(n=>{
          if(n.children.length===0){
            const t = (n.textContent||'').trim();
            if(t==='$0' || t==='$0/mo' || t==='$-1' || t==='$-1/mo' || t==='Free'){
              n.textContent = 'Contact us';
            }
          }
        });
      }
    });
  }
  // Run after pricing populates
  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded', ()=>setTimeout(fixEnterprise, 500));
  } else { setTimeout(fixEnterprise, 500); }
  // Also re-run after 2s in case render is delayed
  setTimeout(fixEnterprise, 2000);
})();
</script>
'''

NEW_BLOCK = '''
<!-- PCR-051b — _R442_QUOTE_RENDER (fixEnterprise) removed; renderCTA in renderPlans now handles this -->
'''


def apply(verify, revert):
    print(f"PCR-051b remove dead fixEnterprise  verify={verify}  revert={revert}")
    src = PRICING.read_text(encoding="utf-8")

    if revert:
        if "PCR-051b — _R442_QUOTE_RENDER" not in src:
            print("  · already absent"); return 0
        if NEW_BLOCK not in src:
            print("  ✗ new anchor not found"); return 1
        src = src.replace(NEW_BLOCK, OLD_BLOCK, 1)
        if verify: print("  ✓ would revert"); return 0
        PRICING.write_text(src, encoding="utf-8"); print("  ✓ reverted"); return 0

    if "PCR-051b — _R442_QUOTE_RENDER" in src:
        print("  · already applied"); return 0
    if OLD_BLOCK not in src:
        print(f"  ✗ old anchor not found (file has {len(src)} chars)"); return 1
    if src.count(OLD_BLOCK) > 1:
        print(f"  ✗ anchor matches {src.count(OLD_BLOCK)} places — refusing"); return 1
    src = src.replace(OLD_BLOCK, NEW_BLOCK, 1)
    if verify: print("  ✓ would apply"); return 0
    PRICING.write_text(src, encoding="utf-8"); print("  ✓ applied"); return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--revert", action="store_true")
    a = ap.parse_args()
    return apply(a.verify, a.revert)


if __name__ == "__main__":
    sys.exit(main())
